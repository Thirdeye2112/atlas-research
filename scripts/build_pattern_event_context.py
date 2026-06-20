#!/usr/bin/env python
"""
build_pattern_event_context.py — STEP D: attach the real-world "why" to patterns.

For every pattern_memory instance, link the corporate actions and news that sit
around its decision bar, with an explicit LOOK-AHEAD-safe before/after split, into
the NEW pattern_event_context table (migration 0045). Pattern_memory, the pattern
builder, and the ingester are NOT touched.

LOOK-AHEAD RULE (the whole point):
  decision_bar = daily -> close of confirm_date  (16:00 America/New_York, DST-aware)
                 5m    -> open  of confirm_date  (09:30 America/New_York)
  An event counts as a valid "why" (relation='before') only if event_time <= decision_bar.
  Because pattern_memory stores only the DATE for 5m (no intraday ts), same-session
  5m news cannot be proven to precede the bar and is tagged 'same_day_unverified'
  (never 'before'). Predictive uses MUST filter to relation='before'.

Windows:
  corporate_actions: COALESCE(ex_date, effective_date, process_date) within
                     [-3, +1] NYSE trading days of confirm_date (offset via SPY dates).
  news_events:       created_at within [-2, +1] days of the decision bar (joined on
                     TIMESTAMP), capped to the --news-cap nearest per (pattern, relation).

Usage:
    python scripts/build_pattern_event_context.py --rebuild              # full
    python scripts/build_pattern_event_context.py --rebuild --tickers AAPL TSLA NVDA
    python scripts/build_pattern_event_context.py --report-only
"""
from __future__ import annotations
import argparse, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv; load_dotenv(ROOT / ".env", override=True)

import os
from sqlalchemy import create_engine, text

ENGINE = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)

# DST-aware decision bar (16:00 ET close for daily, 09:30 ET open for 5m).
DB_EXPR = ("(CASE WHEN P.timeframe='5m' "
           "THEN ((P.confirm_date + TIME '09:30') AT TIME ZONE 'America/New_York') "
           "ELSE ((P.confirm_date + TIME '16:00') AT TIME ZONE 'America/New_York') END)")

CA_DATE = "COALESCE(CA.ex_date, CA.effective_date, CA.process_date)"


def _tk_filter(tickers):
    return ("", {}) if not tickers else (" AND P.ticker = ANY(:tks)", {"tks": list(tickers)})


def build(tickers, news_cap):
    tkf, tkp = _tk_filter(tickers)
    with ENGINE.begin() as conn:
        # SPY trading-day calendar (the real NYSE sessions) for trading-day offsets.
        conn.execute(text("""
            CREATE TEMP TABLE spy_td ON COMMIT DROP AS
            SELECT date, row_number() OVER (ORDER BY date) AS ord
            FROM (SELECT DISTINCT date FROM raw_bars WHERE ticker='SPY') s
        """))
        conn.execute(text("CREATE INDEX ON spy_td(date)"))

        # ---- corporate actions: ex/effective date within [-3,+1] trading days ----
        ca_sql = f"""
        INSERT INTO pattern_event_context
            (pattern_id, ticker, timeframe, decision_bar, event_kind, event_type,
             event_ref, event_time, offset_days, offset_trading_days, relation, headline, detail)
        SELECT P.id, P.ticker, P.timeframe, {DB_EXPR} AS db,
               'corporate_action', CA.ca_type,
               concat_ws('|', CA.ca_type, CA.symbol, COALESCE(CA.cusip,''), {CA_DATE}::text),
               (({CA_DATE} + TIME '16:00') AT TIME ZONE 'America/New_York') AS ev_time,
               EXTRACT(EPOCH FROM ((({CA_DATE} + TIME '16:00') AT TIME ZONE 'America/New_York') - {DB_EXPR}))/86400.0,
               (tde.ord - tdc.ord),
               CASE WHEN (tde.ord - tdc.ord) <= 0 THEN 'before' ELSE 'after' END,
               NULL,
               jsonb_build_object('ex_date',CA.ex_date,'effective_date',CA.effective_date,
                   'process_date',CA.process_date,'old_rate',CA.old_rate,'new_rate',CA.new_rate,
                   'rate',CA.rate,'cash_amount',CA.cash_amount,'related_symbol',CA.related_symbol)
        FROM pattern_memory P
        JOIN spy_td tdc ON tdc.date = P.confirm_date
        JOIN corporate_actions CA ON CA.symbol = P.ticker
        JOIN spy_td tde ON tde.date = {CA_DATE}
        WHERE (tde.ord - tdc.ord) BETWEEN -3 AND 1{tkf};
        """
        ca_n = conn.execute(text(ca_sql), tkp).rowcount

        # ---- news: created_at within [-2,+1] days of the decision bar ----
        news_sql = f"""
        INSERT INTO pattern_event_context
            (pattern_id, ticker, timeframe, decision_bar, event_kind, event_type,
             event_ref, event_time, offset_days, offset_trading_days, relation, headline, detail)
        WITH cand AS (
            SELECT P.id AS pid, P.ticker, P.timeframe, P.confirm_date,
                   {DB_EXPR} AS db,
                   N.news_id, N.source, N.created_at, N.headline, N.summary, N.url,
                   (N.created_at AT TIME ZONE 'America/New_York')::date AS ny_date
            FROM pattern_memory P
            JOIN news_events N ON N.symbol = P.ticker
             AND N.created_at >= {DB_EXPR} - INTERVAL '2 days'
             AND N.created_at <= {DB_EXPR} + INTERVAL '1 day'
            WHERE TRUE{tkf}
        ),
        scored AS (
            SELECT *, EXTRACT(EPOCH FROM (created_at - db))/86400.0 AS off,
                   CASE WHEN created_at <= db THEN 'before'
                        WHEN timeframe='5m' AND ny_date = confirm_date THEN 'same_day_unverified'
                        ELSE 'after' END AS rel
            FROM cand
        ),
        ranked AS (
            SELECT *, row_number() OVER (PARTITION BY pid, rel ORDER BY abs(off)) AS rn
            FROM scored
        )
        SELECT pid, ticker, timeframe, db, 'news', source, news_id::text, created_at,
               off, NULL, rel, headline,
               jsonb_build_object('summary',summary,'url',url,'source',source)
        FROM ranked WHERE rn <= :cap;
        """
        p2 = dict(tkp); p2["cap"] = news_cap
        news_n = conn.execute(text(news_sql), p2).rowcount
        return ca_n, news_n


def report(md_path=None):
    with ENGINE.begin() as c:
        out = []
        def q(sql): return c.execute(text(sql)).fetchall()
        pm = dict((tf, n) for tf, n in q("SELECT timeframe,count(*) FROM pattern_memory GROUP BY 1"))
        pec_total = c.execute(text("SELECT count(*) FROM pattern_event_context")).scalar()

        # % of pattern instances with >=1 corporate action, and with >=1 PRIOR news (relation='before')
        cov = {}
        for tf in pm:
            base = pm[tf]
            ca = c.execute(text("SELECT count(DISTINCT pattern_id) FROM pattern_event_context "
                                "WHERE event_kind='corporate_action' AND timeframe=:t"), {"t": tf}).scalar()
            news_before = c.execute(text("SELECT count(DISTINCT pattern_id) FROM pattern_event_context "
                                "WHERE event_kind='news' AND relation='before' AND timeframe=:t"), {"t": tf}).scalar()
            news_any = c.execute(text("SELECT count(DISTINCT pattern_id) FROM pattern_event_context "
                                "WHERE event_kind='news' AND timeframe=:t"), {"t": tf}).scalar()
            cov[tf] = (base, ca, news_before, news_any)
        rel = q("SELECT event_kind, relation, count(*) FROM pattern_event_context GROUP BY 1,2 ORDER BY 1,2")
        catypes = q("SELECT event_type, count(*) FROM pattern_event_context "
                    "WHERE event_kind='corporate_action' GROUP BY 1 ORDER BY 2 DESC")
        news_min = c.execute(text("SELECT min(event_time) FROM pattern_event_context WHERE event_kind='news'")).scalar()

    L = []
    L.append("# Pattern → Event Context (the \"why\" layer)")
    L.append("")
    L.append("> **Coverage numbers below are PROVISIONAL** — the 5m pattern pass is still")
    L.append("> accumulating in the background, so 5m coverage will rise as more tickers land.")
    L.append("")
    L.append("Links each `pattern_memory` instance to the corporate actions and news around")
    L.append("its decision bar, in the new `pattern_event_context` table (migration 0045).")
    L.append("Recognition + linkage only; pattern_memory is not altered.")
    L.append("")
    L.append("## The look-ahead rule (why this isn't a leak)")
    L.append("")
    L.append("- **Decision bar** = `daily`: **close** of confirm_date (16:00 America/New_York,")
    L.append("  DST-aware); `5m`: **open** of confirm_date (09:30 ET).")
    L.append("- An event is a valid cause (`relation='before'`) only if `event_time <= decision_bar`.")
    L.append("- **5m caveat:** `pattern_memory` stores only the DATE for 5m (no intraday timestamp),")
    L.append("  so same-session news cannot be proven to precede the bar — it is tagged")
    L.append("  **`same_day_unverified`**, never `before`. Storing the bar's `ts` in pattern_memory")
    L.append("  would let us tighten this to exact intraday precision.")
    L.append("- **News `created_at` is `timestamptz` (true UTC)** — verified — so the comparison is sound.")
    L.append("- **Predictive uses MUST filter to `relation='before'` (offset_days <= 0).**")
    L.append("  `after` and `same_day_unverified` are explanatory only.")
    L.append("")
    L.append("## Windows")
    L.append("- Corporate actions: COALESCE(ex_date, effective_date, process_date) within")
    L.append("  **[-3, +1] NYSE trading days** of confirm_date (offsets via SPY session dates).")
    L.append("- News: `created_at` within **[-2, +1] days** of the decision bar, capped to the")
    L.append("  nearest links per (pattern, relation).")
    L.append("")
    L.append(f"## Coverage (provisional) — {pec_total:,} total links")
    L.append("")
    L.append("| timeframe | pattern instances | % with ≥1 corp action | % with ≥1 PRIOR news (before) | % with any news (incl after) |")
    L.append("|---|---:|---:|---:|---:|")
    for tf, (base, ca, nb, na) in cov.items():
        L.append(f"| {tf} | {base:,} | {100*ca/base:.2f}% | {100*nb/base:.2f}% | {100*na/base:.2f}% |")
    L.append("")
    L.append("### Links by kind × relation (before/after reported separately)")
    L.append("")
    L.append("| event_kind | relation | links |")
    L.append("|---|---|---:|")
    for k, r, n in rel:
        L.append(f"| {k} | {r} | {n:,} |")
    L.append("")
    L.append("### Corporate-action links by type")
    L.append("")
    L.append("| ca_type | links |")
    L.append("|---|---:|")
    for t, n in catypes:
        L.append(f"| {t} | {n:,} |")
    L.append("")
    L.append(f"Earliest linked news event_time: **{news_min}**")
    L.append("")
    L.append("## Honest coverage caveats")
    L.append("- News is universe-filtered and Alpaca news is **sparse pre-2016 and for small caps**,")
    L.append("  so a large share of older / thin-name pattern instances have **no** news \"why\" available.")
    L.append("- **KNOWN GAP (stated, not solved):** Alpaca news carries no analyst-estimate /")
    L.append("  earnings-surprise magnitude. The \"why\" here is *\"news existed / an event occurred\"*,")
    L.append("  not *\"earnings beat by X%\"*. A fundamentals/earnings-calendar feed would deepen this.")
    L.append("")
    md = "\n".join(L)
    print(md)
    if md_path:
        Path(md_path).write_text(md, encoding="utf-8")
        print(f"\nWrote {md_path}")


def main():
    for stream in (sys.stdout, sys.stderr):   # Windows cp1252 -> UTF-8 for report glyphs
        try: stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception: pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--rebuild", action="store_true", help="TRUNCATE pattern_event_context first")
    ap.add_argument("--tickers", nargs="+", default=None, help="restrict to these tickers (validation)")
    ap.add_argument("--news-cap", type=int, default=5, help="max news links per (pattern, relation)")
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--report-md", default=None)
    args = ap.parse_args()

    if not args.report_only:
        if args.rebuild and not args.tickers:
            with ENGINE.begin() as c:
                c.execute(text("TRUNCATE pattern_event_context RESTART IDENTITY"))
            print("[rebuild] truncated pattern_event_context")
        elif args.rebuild and args.tickers:
            with ENGINE.begin() as c:
                c.execute(text("DELETE FROM pattern_event_context WHERE ticker = ANY(:t)"), {"t": args.tickers})
            print(f"[rebuild] cleared rows for {args.tickers}")
        print(f"[build] tickers={args.tickers or 'ALL'} news_cap={args.news_cap}")
        ca_n, news_n = build(args.tickers, args.news_cap)
        print(f"[build] inserted corporate_action links={ca_n:,}  news links={news_n:,}")

    report(args.report_md)


if __name__ == "__main__":
    main()
