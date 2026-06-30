"""
pattern_outcomes_study.py — learn each chart pattern's DATA-DRIVEN direction,
projected target, expected low, and time-to-fulfillment.

The textbook direction of a pattern is not always the profitable one (the universe
mine showed descending_triangle / rectangle "breakdowns" actually rise). So for
every detected pattern occurrence we measure the REAL forward path over the next H
daily bars from the confirmation bar:
  * MFE%   = max favorable excursion (high above entry)      -> the projected TARGET
  * MAE%   = max adverse excursion  (low below entry)        -> the expected LOW (bid/stop)
  * bars_to_peak = bars until the MFE high                   -> time to fulfillment
  * net5   = close-to-close 5-bar return                      -> direction edge sign

Aggregated per pattern we emit, to reports/stocks/pattern_edge.json:
  direction (data-driven = sign of the net move), avg_target_pct, avg_low_pct,
  median_bars_to_target, win_rate, n. daily_scan reads this so each pattern alert
  ships its profitable side + projected target + expected low + expected duration.

Usage:
    python scripts/pattern_outcomes_study.py                 # liquid universe
    python scripts/pattern_outcomes_study.py --tickers AAPL NVDA
    python scripts/pattern_outcomes_study.py --limit 300
"""
from __future__ import annotations
import sys, argparse, json
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "src"))
import aapl_deep_dive as dd
from atlas_research.ta import structure as ta_structure, patterns as ta_patterns

OUT = ROOT / "reports/stocks/pattern_edge.json"


def universe(which, limit):
    if which == "500":
        f = ROOT / "config/universe_500.csv"
    else:
        f = ROOT / "config/clean_universe.csv"
    df = pd.read_csv(f); col = "ticker" if "ticker" in df.columns else df.columns[0]
    u = [str(t).strip().upper() for t in df[col].dropna().tolist()]
    return u[:limit] if limit else u


def collect(tk, H, width):
    d = dd.load_daily(tk)
    if d is None or len(d) < 300:
        return []
    d = d.drop_duplicates("ts").sort_values("ts").reset_index(drop=True)
    for c in ("open", "high", "low", "close"):
        d[c] = pd.to_numeric(d[c], errors="coerce")
    h = d["high"].values; l = d["low"].values; c = d["close"].values
    N = len(d)
    piv = ta_structure.swing_pivots(h, l, width=width)
    rows = []
    for p in ta_patterns.detect_all(piv, h, l, c):
        i = p.confirm_idx
        if i < 20 or i + H >= N:
            continue
        e = c[i]
        if e <= 0:
            continue
        fwd_h = h[i+1:i+1+H]; fwd_l = l[i+1:i+1+H]; fwd_c = c[i+1:i+1+H]
        if len(fwd_h) < H:
            continue
        mfe = (fwd_h.max() - e) / e * 100
        mae = (fwd_l.min() - e) / e * 100
        bars_to_peak = int(np.argmax(fwd_h) + 1)
        net5 = (fwd_c[min(4, len(fwd_c)-1)] - e) / e * 100
        net_full = (fwd_c[-1] - e) / e * 100
        rows.append(dict(ticker=tk, name=p.name, textbook_dir=p.direction,
                         entry=e, mfe=mfe, mae=mae, bars_to_peak=bars_to_peak,
                         net5=net5, net_full=net_full))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tickers", nargs="+")
    ap.add_argument("--universe", choices=["clean", "500"], default="500")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--H", type=int, default=10)       # forward bars (fulfillment window)
    ap.add_argument("--width", type=int, default=3)
    ap.add_argument("--min-n", type=int, default=200)
    a = ap.parse_args()

    tickers = a.tickers or universe(a.universe, a.limit)
    rows = []
    import time; t0 = time.time()
    for k, tk in enumerate(tickers, 1):
        try:
            rows += collect(tk, a.H, a.width)
        except Exception as e:
            pass
        if k % 100 == 0:
            print(f"  [{k}/{len(tickers)}] rows={len(rows):,} ({k/max(time.time()-t0,1e-9):.1f} tk/s)", flush=True)
    R = pd.DataFrame(rows).replace([np.inf, -np.inf], np.nan).dropna(subset=["mfe", "mae", "net5"])
    print(f"\n{len(R):,} pattern occurrences across {R['ticker'].nunique()} names\n", flush=True)

    # winsorize tails per pattern so microcap spikes don't distort target/low
    def wins(s, lo=0.02, hi=0.98):
        a_, b_ = s.quantile(lo), s.quantile(hi)
        return s.clip(a_, b_)

    edge = {}
    summary = []
    for name, g in R.groupby("name"):
        if len(g) < a.min_n:
            continue
        net = wins(g["net_full"])
        data_dir = "long" if net.mean() >= 0 else "short"
        # in the profitable direction: target = favorable excursion, low = adverse
        if data_dir == "long":
            tgt = wins(g["mfe"]).median(); low = wins(g["mae"]).median()
            win = (g["net_full"] > 0).mean() * 100
            btp = g.loc[g["mfe"] > 0, "bars_to_peak"].median()
        else:
            tgt = -wins(g["mae"]).median(); low = -wins(g["mfe"]).median()   # short: target is down move
            win = (g["net_full"] < 0).mean() * 100
            btp = g["bars_to_peak"].median()
        textbook = g["textbook_dir"].mode().iloc[0]
        flipped = (data_dir == "long") != (textbook in ("long", "bullish", "rise"))
        edge[name] = dict(direction=data_dir, textbook_dir=textbook, flipped=bool(flipped),
                          avg_target_pct=round(float(tgt), 2), avg_low_pct=round(float(low), 2),
                          median_bars_to_target=int(btp) if pd.notna(btp) else None,
                          win_rate=round(float(win), 1), avg_net_pct=round(float(net.mean()), 3),
                          n=int(len(g)))
        summary.append((name, data_dir, flipped, round(float(net.mean()), 3), round(float(tgt), 2),
                        round(float(low), 2), int(btp) if pd.notna(btp) else 0, round(float(win), 1), len(g)))

    OUT.write_text(json.dumps(edge, indent=2))
    print(f"{'pattern':24}{'dir':6}{'flip':6}{'net%':>7}{'tgt%':>7}{'low%':>7}{'bars':>6}{'win%':>7}{'n':>8}", flush=True)
    for s in sorted(summary, key=lambda x: -x[3] if x[1] == "long" else x[3]):
        nm, dr, fl, net, tg, lo, bt, wn, n = s
        print(f"{nm:24}{dr:6}{'YES' if fl else '-':6}{net:>7}{tg:>7}{lo:>7}{bt:>6}{wn:>7}{n:>8}", flush=True)
    print(f"\nwrote {OUT} ({len(edge)} patterns with >= {a.min_n} samples)", flush=True)


if __name__ == "__main__":
    main()
