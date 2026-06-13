"""
atlas_research.probability.ipo.studies
-----------------------------------------
Aggregate probability studies computed from ipo_events.

Each study function takes a list of event dicts and returns
a list of ipo_outcomes dicts ready for DB insertion.

Studies
-------
  revisit_open_overall      — % of all IPOs that revisit opening price
  revisit_offer_overall     — % of all IPOs that revisit offer price
  revisit_by_gap_bucket     — revisit rates segmented by opening gap (open_vs_offer)
  day1_close_range          — distribution of Day 1 close vs open
  peak_expansion_analysis   — peak stats segmented by peak_vs_open bucket
  week1_momentum            — post-week1 outcomes segmented by week1_return
  month1_momentum           — post-month1 outcomes segmented by month1_return
"""

from __future__ import annotations

import statistics
from typing import Optional

import numpy as np

from sqlalchemy import text
from atlas_research.db.connection import get_connection


# ── Stat helpers ──────────────────────────────────────────────────────────────

def _pct_notnone(values: list) -> Optional[float]:
    """Fraction of non-None values in list, as a percentage."""
    if not values:
        return None
    nn = sum(1 for v in values if v is not None)
    return round(nn / len(values) * 100, 1)


def _median(values: list) -> Optional[float]:
    clean = [v for v in values if v is not None]
    if not clean:
        return None
    return round(float(np.median(clean)), 1)


def _p25(values: list) -> Optional[float]:
    clean = [v for v in values if v is not None]
    if not clean:
        return None
    return round(float(np.percentile(clean, 25)), 1)


def _p75(values: list) -> Optional[float]:
    clean = [v for v in values if v is not None]
    if not clean:
        return None
    return round(float(np.percentile(clean, 75)), 1)


def _avg(values: list) -> Optional[float]:
    clean = [v for v in values if v is not None]
    if not clean:
        return None
    return round(float(np.mean(clean)), 1)


def _pct_hit(bools: list) -> Optional[float]:
    if not bools:
        return None
    return round(sum(1 for b in bools if b) / len(bools) * 100, 1)


# ── Outcome row builder ───────────────────────────────────────────────────────

def _outcome(study_name: str, bucket_name: str, bucket_label: str,
             events: list[dict], pct_key: str, metric_key: str,
             notes: str = "") -> dict:
    """Build one ipo_outcomes dict from a list of events."""
    n      = len(events)
    pct    = _pct_notnone([e.get(pct_key) for e in events])
    metric = [e.get(metric_key) for e in events]
    return {
        "study_name":   study_name,
        "bucket_name":  bucket_name,
        "bucket_label": bucket_label,
        "n":            n,
        "pct_positive": pct,
        "median_value": _median(metric),
        "p25_value":    _p25(metric),
        "p75_value":    _p75(metric),
        "avg_value":    _avg(metric),
        "notes":        notes or f"n={n}",
    }


# ── Study functions ───────────────────────────────────────────────────────────

def study_revisit_overall(events: list[dict]) -> list[dict]:
    """Overall probability of revisiting opening price and offer price."""
    e = [ev for ev in events if ev.get("opening_price")]
    n = len(e)
    if n == 0:
        return []

    n_rev_open  = sum(1 for ev in e if ev.get("days_to_revisit_open") is not None)
    n_rev_offer = sum(1 for ev in e if ev.get("days_to_revisit_offer") is not None)

    revisit_open_days  = [ev.get("days_to_revisit_open")  for ev in e]
    revisit_offer_days = [ev.get("days_to_revisit_offer") for ev in e]

    return [
        {
            "study_name":   "revisit_open_overall",
            "bucket_name":  "",
            "bucket_label": "All IPOs",
            "n":            n,
            "pct_positive": round(n_rev_open / n * 100, 1),
            "median_value": _median(revisit_open_days),
            "p25_value":    _p25(revisit_open_days),
            "p75_value":    _p75(revisit_open_days),
            "avg_value":    _avg(revisit_open_days),
            "notes":        f"{n_rev_open}/{n} revisit opening price",
        },
        {
            "study_name":   "revisit_offer_overall",
            "bucket_name":  "",
            "bucket_label": "All IPOs",
            "n":            n,
            "pct_positive": round(n_rev_offer / n * 100, 1),
            "median_value": _median(revisit_offer_days),
            "p25_value":    _p25(revisit_offer_days),
            "p75_value":    _p75(revisit_offer_days),
            "avg_value":    _avg(revisit_offer_days),
            "notes":        f"{n_rev_offer}/{n} revisit offer price",
        },
    ]


_GAP_BUCKET_ORDER = ["neg", "0-10", "10-20", "20-50", "50+"]
_GAP_BUCKET_LABEL = {
    "neg":   "Below offer (<0%)",
    "0-10":  "0–10% pop",
    "10-20": "10–20% pop",
    "20-50": "20–50% pop",
    "50+":   "50%+ pop",
}


def study_revisit_by_gap(events: list[dict]) -> list[dict]:
    """
    Revisit probability segmented by opening gap bucket.
    Answers: 'After a +30% Day-1 expansion, what % eventually revisit open?'
    """
    rows = []
    for bucket in _GAP_BUCKET_ORDER:
        group = [ev for ev in events
                 if ev.get("bucket_open_vs_offer") == bucket
                 and ev.get("opening_price")]
        if len(group) < 3:
            continue

        n = len(group)
        n_rev_open  = sum(1 for ev in group if ev.get("days_to_revisit_open")  is not None)
        n_rev_offer = sum(1 for ev in group if ev.get("days_to_revisit_offer") is not None)
        days_open   = [ev.get("days_to_revisit_open")  for ev in group]
        days_offer  = [ev.get("days_to_revisit_offer") for ev in group]

        rows.append({
            "study_name":   "revisit_open_by_gap",
            "bucket_name":  bucket,
            "bucket_label": _GAP_BUCKET_LABEL.get(bucket, bucket),
            "n":            n,
            "pct_positive": round(n_rev_open / n * 100, 1),
            "median_value": _median(days_open),
            "p25_value":    _p25(days_open),
            "p75_value":    _p75(days_open),
            "avg_value":    _avg(days_open),
            "notes":        (f"{n_rev_open}/{n} revisit open; "
                             f"{n_rev_offer}/{n} revisit offer "
                             f"(med {_median(days_offer) or 'N/A'}d)"),
        })
    return rows


def study_day1_close_range(events: list[dict]) -> list[dict]:
    """
    Distribution of Day-1 close vs open (close_vs_open) — answers
    'How many close Day 1 within 20% of opening?'
    """
    e = [ev for ev in events
         if ev.get("close_vs_open") is not None]
    if not e:
        return []

    n = len(e)
    buckets = {
        "within_10":  sum(1 for ev in e if abs(ev["close_vs_open"]) <= 10),
        "within_20":  sum(1 for ev in e if abs(ev["close_vs_open"]) <= 20),
        "positive":   sum(1 for ev in e if ev["close_vs_open"] > 0),
        "negative":   sum(1 for ev in e if ev["close_vs_open"] < 0),
    }

    rows = []
    for bname, cnt in buckets.items():
        rows.append({
            "study_name":   "day1_close_range",
            "bucket_name":  bname,
            "bucket_label": {
                "within_10": "Close within 10% of open",
                "within_20": "Close within 20% of open",
                "positive":  "Close above open",
                "negative":  "Close below open",
            }[bname],
            "n":            n,
            "pct_positive": round(cnt / n * 100, 1),
            "median_value": _median([ev["close_vs_open"] for ev in e]),
            "p25_value":    _p25([ev["close_vs_open"] for ev in e]),
            "p75_value":    _p75([ev["close_vs_open"] for ev in e]),
            "avg_value":    _avg([ev["close_vs_open"] for ev in e]),
            "notes":        f"{cnt}/{n}",
        })
    return rows


_PEAK_BUCKET_ORDER = ["neg", "0-10", "10-20", "20-40", "40-60", "60+"]
_PEAK_BUCKET_LABEL = {
    "neg":   "Peak below open (<0%)",
    "0-10":  "0–10% peak expansion",
    "10-20": "10–20% peak expansion",
    "20-40": "20–40% peak expansion",
    "40-60": "40–60% peak expansion",
    "60+":   "60%+ peak expansion",
}


def study_peak_expansion(events: list[dict]) -> list[dict]:
    """
    Peak analysis: how long after Day-1 before contraction.
    Segmented by peak_vs_open bucket.
    """
    rows = []
    for bucket in _PEAK_BUCKET_ORDER:
        group = [ev for ev in events
                 if ev.get("bucket_peak_vs_open") == bucket]
        if len(group) < 3:
            continue

        days_to_peak    = [ev.get("days_to_peak")         for ev in group]
        retracement     = [ev.get("retracement_from_peak") for ev in group]
        revisit_days    = [ev.get("days_to_revisit_open")  for ev in group]
        n_rev           = sum(1 for ev in group if ev.get("days_to_revisit_open") is not None)

        rows.append({
            "study_name":   "peak_expansion",
            "bucket_name":  bucket,
            "bucket_label": _PEAK_BUCKET_LABEL.get(bucket, bucket),
            "n":            len(group),
            "pct_positive": round(n_rev / len(group) * 100, 1),  # % that revisit open
            "median_value": _median(days_to_peak),                 # median days to peak
            "p25_value":    _p25(retracement),                     # p25 retracement
            "p75_value":    _p75(retracement),                     # p75 retracement
            "avg_value":    _avg(retracement),                     # avg retracement
            "notes":        (f"med {_median(days_to_peak) or 'N/A'}d to peak; "
                             f"avg retracement {_avg(retracement) or 'N/A'}%; "
                             f"{n_rev}/{len(group)} revisit open"),
        })
    return rows


def _week1_bucket(ret: Optional[float]) -> Optional[str]:
    if ret is None:
        return None
    if ret < -10:
        return "loss_big"
    if ret < 0:
        return "loss"
    if ret < 10:
        return "gain_small"
    if ret < 20:
        return "gain_10_20"
    return "gain_big"


_WEEK1_ORDER = ["loss_big", "loss", "gain_small", "gain_10_20", "gain_big"]
_WEEK1_LABEL = {
    "loss_big":    "Week1 loss >10%",
    "loss":        "Week1 loss 0-10%",
    "gain_small":  "Week1 gain 0-10%",
    "gain_10_20":  "Week1 gain 10-20%",
    "gain_big":    "Week1 gain >20%",
}


def study_week1_momentum(events: list[dict]) -> list[dict]:
    """
    After Week-1 momentum, what is median future drawdown and 20d return?
    Answers: 'After Week 1 gain >20%, what is median future drawdown?'
    """
    rows = []
    for bucket in _WEEK1_ORDER:
        group = [ev for ev in events
                 if _week1_bucket(ev.get("week1_return")) == bucket]
        if len(group) < 3:
            continue

        future_ret   = [ev.get("post_week1_return_20d")  for ev in group]
        retracement  = [ev.get("retracement_from_peak")  for ev in group]

        rows.append({
            "study_name":   "week1_momentum",
            "bucket_name":  bucket,
            "bucket_label": _WEEK1_LABEL.get(bucket, bucket),
            "n":            len(group),
            "pct_positive": _pct_hit([r is not None and r > 0 for r in future_ret]),
            "median_value": _median(future_ret),
            "p25_value":    _p25(future_ret),
            "p75_value":    _p75(future_ret),
            "avg_value":    _avg(retracement),
            "notes":        (f"med post-week1 20d ret: {_median(future_ret) or 'N/A'}%; "
                             f"med eventual retracement: {_median(retracement) or 'N/A'}%"),
        })
    return rows


def _month1_bucket(ret: Optional[float]) -> Optional[str]:
    if ret is None:
        return None
    if ret < -20:
        return "loss_big"
    if ret < 0:
        return "loss"
    if ret < 20:
        return "gain_small"
    if ret < 50:
        return "gain_20_50"
    return "gain_big"


_MONTH1_ORDER = ["loss_big", "loss", "gain_small", "gain_20_50", "gain_big"]
_MONTH1_LABEL = {
    "loss_big":    "Month1 loss >20%",
    "loss":        "Month1 loss 0-20%",
    "gain_small":  "Month1 gain 0-20%",
    "gain_20_50":  "Month1 gain 20-50%",
    "gain_big":    "Month1 gain >50%",
}


def study_month1_momentum(events: list[dict]) -> list[dict]:
    """After Month-1 momentum, what happens at 252d?"""
    rows = []
    for bucket in _MONTH1_ORDER:
        group = [ev for ev in events
                 if _month1_bucket(ev.get("month1_return")) == bucket]
        if len(group) < 3:
            continue

        retracement = [ev.get("retracement_from_peak")  for ev in group]
        revisit     = [ev.get("days_to_revisit_open")   for ev in group]
        n_rev       = sum(1 for ev in group if ev.get("days_to_revisit_open") is not None)

        rows.append({
            "study_name":   "month1_momentum",
            "bucket_name":  bucket,
            "bucket_label": _MONTH1_LABEL.get(bucket, bucket),
            "n":            len(group),
            "pct_positive": round(n_rev / len(group) * 100, 1),
            "median_value": _median(retracement),
            "p25_value":    _p25(retracement),
            "p75_value":    _p75(retracement),
            "avg_value":    _avg(retracement),
            "notes":        (f"med retracement: {_median(retracement) or 'N/A'}%; "
                             f"{n_rev}/{len(group)} revisit open"),
        })
    return rows


# ── DB persistence ────────────────────────────────────────────────────────────

_UPSERT_OUTCOME = text("""
    INSERT INTO ipo_outcomes
        (study_name, bucket_name, bucket_label, n,
         pct_positive, median_value, p25_value, p75_value, avg_value, notes,
         computed_at)
    VALUES
        (:study_name, :bucket_name, :bucket_label, :n,
         :pct_positive, :median_value, :p25_value, :p75_value, :avg_value, :notes,
         now())
    ON CONFLICT (study_name, bucket_name) DO UPDATE SET
        bucket_label  = EXCLUDED.bucket_label,
        n             = EXCLUDED.n,
        pct_positive  = EXCLUDED.pct_positive,
        median_value  = EXCLUDED.median_value,
        p25_value     = EXCLUDED.p25_value,
        p75_value     = EXCLUDED.p75_value,
        avg_value     = EXCLUDED.avg_value,
        notes         = EXCLUDED.notes,
        computed_at   = now()
""")


def run_all_studies(events: list[dict], save: bool = True) -> dict[str, list[dict]]:
    """
    Run all IPO probability studies.
    Returns {study_name: [result_rows]}.
    If save=True, upserts results into ipo_outcomes.
    """
    all_rows: dict[str, list[dict]] = {}

    study_fns = [
        study_revisit_overall,
        study_revisit_by_gap,
        study_day1_close_range,
        study_peak_expansion,
        study_week1_momentum,
        study_month1_momentum,
    ]

    flat_rows: list[dict] = []
    for fn in study_fns:
        rows = fn(events)
        for r in rows:
            name = r["study_name"]
            all_rows.setdefault(name, []).append(r)
            flat_rows.append(r)

    if save and flat_rows:
        with get_connection() as conn:
            for row in flat_rows:
                conn.execute(_UPSERT_OUTCOME, row)

    return all_rows
