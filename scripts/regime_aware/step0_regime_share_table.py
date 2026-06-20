#!/usr/bin/env python
"""
Regime-aware rebuild — STEP 0: define the regime labeling and report the
regime-share table across full history and per year.

Regime definition (reused verbatim from the prior OOS diagnosis session's
Angle 2, itself matching scripts/compute_feature_reliability.py:
load_regime_context):
    regime_market = "bull"  if market_trend > 0
                    "bear"  if market_trend < 0
                    "range" otherwise
    regime_vol    = "high_vol" if realized_vol_20 > 0.30 else "low_vol"
    regime        = regime_market + "_" + regime_vol   (6 buckets)

Point-in-time check (read-only inspection, not re-derived here):
src/atlas_research/features/regime.py:compute() is a stateless pure
function operating on spy_close[-N:] trailing slices only (SMA50/200 use
the last 50/200 elements of whatever array is passed; 20d return uses
spy_close[-21]). src/atlas_research/features/volatility.py:_realized_vol()
is the same shape: window = close[-(days+1):]. Both are backward-looking by
construction -- the caller passes an array sliced up to and including the
current bar, never future bars. The parquet columns used here are the
already-exported, already-point-in-time production feature values (the
same ones V1 trains on) -- no new look-ahead is introduced by this script.

Read-only: column-only parquet reads, no scoring, no training, no DB writes.

Usage:
    python scripts/regime_aware/step0_regime_share_table.py
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv
load_dotenv(override=True)

from config import settings

OUT_DIR = _ROOT / "reports" / "validity"
OUT_DIR.mkdir(parents=True, exist_ok=True)

VOL_THRESHOLD = 0.30


def tag_regime(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["regime_market"] = np.where(df["market_trend"] > 0, "bull",
                           np.where(df["market_trend"] < 0, "bear", "range"))
    df["regime_vol"] = np.where(df["realized_vol_20"] > VOL_THRESHOLD, "high_vol", "low_vol")
    df["regime"] = df["regime_market"] + "_" + df["regime_vol"]
    return df


def main() -> None:
    parquet_dir = settings.PARQUET_OUTPUT_DIR
    parquet_files = sorted(parquet_dir.glob("feature_matrix_*.parquet"))

    print(f"[STEP 0] Regime definition: regime_market = bull/bear/range from "
          f"market_trend sign; regime_vol = high_vol if realized_vol_20 > "
          f"{VOL_THRESHOLD} else low_vol. 6 buckets. Reused verbatim from the "
          f"prior OOS diagnosis (Angle 2) / compute_feature_reliability.py.")
    print(f"[STEP 0] Reading market_trend + realized_vol_20 (column-only) from "
          f"{len(parquet_files)} parquet files, full history.")

    frames = []
    for fp in parquet_files:
        try:
            d = date.fromisoformat(fp.stem.replace("feature_matrix_", ""))
        except ValueError:
            continue
        try:
            df = pd.read_parquet(fp, engine="pyarrow",
                                  columns=["ticker", "date", "market_trend", "realized_vol_20"])
        except Exception:
            continue
        frames.append(df)

    full = pd.concat(frames, ignore_index=True)
    full = tag_regime(full)
    full["date"] = pd.to_datetime(full["date"])
    full["year"] = full["date"].dt.year
    print(f"[STEP 0] Total rows: {len(full):,}  date range: {full['date'].min().date()} -> "
          f"{full['date'].max().date()}")

    full_mix = full["regime"].value_counts(normalize=True).rename("pct").reset_index()
    full_mix.columns = ["regime", "pct"]
    full_mix["pct"] = (full_mix["pct"] * 100).round(2)
    full_mix = full_mix.sort_values("regime")
    print("\n[STEP 0] Regime share, FULL history:")
    print(full_mix.to_string(index=False))
    full_mix.to_csv(OUT_DIR / "step0_regime_share_full_history.csv", index=False)

    print("\n[STEP 0] Regime share, BY YEAR:")
    yearly = full.groupby(["year", "regime"]).size().unstack(fill_value=0)
    yearly_pct = yearly.div(yearly.sum(axis=1), axis=0) * 100
    yearly_pct = yearly_pct.round(2)
    print(yearly_pct.to_string())
    yearly_pct.to_csv(OUT_DIR / "step0_regime_share_by_year.csv")

    # Embargo boundary marker, for visibility -- this script does not score
    # or train anything, so it does not "read the OOS slice" in the sense
    # the cardinal rule cares about; it only tags regime columns already
    # read in full above. Flagged here for transparency only.
    oos_start = date(2025, 6, 15)
    print(f"\n[STEP 0] Note: WF_OOS_MONTHS={settings.WF_OOS_MONTHS} reserves "
          f"{oos_start} -> latest data as the embargoed year in the production "
          f"walk-forward. The by-year table above includes 2025/2026 rows for "
          f"regime-mix VISIBILITY only (descriptive stats, not scoring/training) "
          f"-- consistent with how the diagnosis session already read this same "
          f"regime mix in Angle 2.")


if __name__ == "__main__":
    main()
