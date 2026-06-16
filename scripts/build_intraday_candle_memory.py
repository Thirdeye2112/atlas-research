"""
Atlas Intraday Candle Memory Builder v1
========================================
Loads 5-min bars from intraday_bars, computes features + multi-horizon outcomes,
builds normalized similarity vectors, and upserts to intraday_candle_memory.

Also runs the per-ticker similarity query and updates intraday_similarity_latest.

Usage:
    python scripts/build_intraday_candle_memory.py --full
    python scripts/build_intraday_candle_memory.py --incremental
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, timedelta

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from atlas_research.intraday.features import compute_features
from atlas_research.intraday.similarity.features import (
    FEATURE_NAMES, build_vectors_batch,
)
from atlas_research.intraday.similarity.search import SimilaritySearch
from atlas_research.intraday.similarity.outcomes import aggregate_outcomes

DB_URL  = os.environ["DATABASE_URL"]
BATCH   = 500          # upsert batch size
K_QUERY = 50           # K for latest-candle similarity result
ATR_HORIZON = 24       # bars to look forward for ATR hits
MFE_HORIZONS = [6, 12, 24]
RETURN_HORIZONS = [1, 3, 6, 12, 24]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sf(v, default=None):
    """Safe float, returns default on None/NaN."""
    if v is None:
        return default
    try:
        f = float(v)
        return default if f != f else f
    except (TypeError, ValueError):
        return default


def _si(v):
    f = _sf(v)
    return None if f is None else int(f)


def _sb(v):
    if v is None:
        return None
    if isinstance(v, (bool, np.bool_)):
        return bool(v)
    return bool(v)


def _load_daily_context(engine, tickers: list[str]) -> pd.DataFrame:
    """Load per-(ticker, date) daily context from prediction_outcomes."""
    ticker_list = ", ".join(f"'{t}'" for t in tickers)
    sql = f"""
        SELECT
            ticker,
            prediction_date::date   AS pred_date,
            ml_signal_strength      AS daily_ml_rank,
            conviction_level        AS daily_conviction,
            confluence_score        AS daily_confluence,
            sector_regime           AS daily_regime,
            vix_regime              AS daily_vix,
            jarvis_green            AS daily_jarvis
        FROM prediction_outcomes
        WHERE ticker IN ({ticker_list})
    """
    df = pd.read_sql(sql, engine)
    df["pred_date"] = pd.to_datetime(df["pred_date"]).dt.date
    # If multiple rows per (ticker, date) keep latest (highest run)
    df = df.sort_values(["ticker", "pred_date"]).drop_duplicates(
        subset=["ticker", "pred_date"], keep="last"
    )
    return df


def _compute_forward_outcomes(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add multi-horizon returns, MFE, MAE, and ATR hit flags to a single-ticker
    sorted DataFrame.  All per-ticker; no day-boundary restriction (overnight
    returns are included -- matches real P&L for held positions).
    """
    close = df["close"].values.astype(np.float64)
    high  = df["high"].values.astype(np.float64)
    low   = df["low"].values.astype(np.float64)
    atr   = df["atr14"].values.astype(np.float64)
    n     = len(df)

    # Forward close-to-close returns
    for h in RETURN_HORIZONS:
        arr = np.full(n, np.nan)
        end = n - h
        if end > 0:
            arr[:end] = (close[h:n] - close[:end]) / close[:end] * 100
        df[f"future_return_{h}"] = arr

    # EOD return: close -> last close of same calendar day
    df["_date_local"] = pd.to_datetime(df["ts"]).dt.tz_convert("America/New_York").dt.date
    eod_close_map = df.groupby("_date_local")["close"].last().to_dict()
    df["future_return_eod"] = df.apply(
        lambda r: _sf(
            (eod_close_map.get(r["_date_local"], np.nan) - r["close"]) / r["close"] * 100
        ),
        axis=1,
    )

    # MFE / MAE at each horizon
    for h in MFE_HORIZONS:
        mfe = np.full(n, np.nan)
        mae = np.full(n, np.nan)
        for i in range(n - h):
            fh = high[i + 1: i + h + 1]
            fl = low[i + 1: i + h + 1]
            c  = close[i]
            if c > 0:
                mfe[i] = (fh.max() - c) / c * 100
                mae[i] = (fl.min() - c) / c * 100
        df[f"mfe_{h}"] = mfe
        df[f"mae_{h}"] = mae

    # ATR target hits over next ATR_HORIZON bars
    hit_p05 = np.full(n, np.nan)
    hit_p10 = np.full(n, np.nan)
    hit_m05 = np.full(n, np.nan)
    hit_m10 = np.full(n, np.nan)

    for i in range(n - ATR_HORIZON):
        entry = close[i]
        a     = atr[i]
        if entry <= 0 or a != a:
            continue
        fh = high[i + 1: i + ATR_HORIZON + 1]
        fl = low[i + 1: i + ATR_HORIZON + 1]
        hit_p05[i] = float(fh.max() >= entry + 0.5 * a)
        hit_p10[i] = float(fh.max() >= entry + 1.0 * a)
        hit_m05[i] = float(fl.min() <= entry - 0.5 * a)
        hit_m10[i] = float(fl.min() <= entry - 1.0 * a)

    df["hit_plus_0_5_atr"]  = hit_p05
    df["hit_plus_1_0_atr"]  = hit_p10
    df["hit_minus_0_5_atr"] = hit_m05
    df["hit_minus_1_0_atr"] = hit_m10

    df = df.drop(columns=["_date_local"], errors="ignore")
    return df


def _add_derived_features(df: pd.DataFrame) -> pd.DataFrame:
    """Compute fields that compute_features() drops or doesn't include."""
    # Normalized wick ratios (body_pct in features.py is 0-100 already)
    rng = df["candle_rng"].clip(lower=1e-8)
    df["upper_wick_ratio"] = (df["upper_wick"] / rng).clip(0.0, 1.0)
    df["lower_wick_ratio"] = (df["lower_wick"] / rng).clip(0.0, 1.0)

    # tod_min (dropped as internal by compute_features)
    local_ts       = df["ts"].dt.tz_convert("America/New_York")
    df["tod_min"]  = local_ts.dt.hour * 60 + local_ts.dt.minute

    # Volume z-score (20-bar rolling)
    vol_std        = df["volume"].rolling(20).std().clip(lower=1)
    df["vol_zscore"] = ((df["volume"] - df["vol_ma20"]) / vol_std).clip(-4, 4)

    return df


def _upsert_batch(engine, rows: list[dict]) -> int:
    if not rows:
        return 0
    sql = text("""
        INSERT INTO intraday_candle_memory (
            ticker, ts, timeframe, feature_version,
            open_price, high_price, low_price, close_price, volume,
            body_pct, upper_wick_ratio, lower_wick_ratio, is_green, range_pct,
            vol_ratio, vol_zscore,
            vwap_dist_pct, or_position, ema9_slope_norm,
            rsi14, macd_hist_norm, atr_pct,
            tod_min, time_of_day, candle_num,
            daily_ml_rank, daily_conviction, daily_confluence,
            daily_regime, daily_vix, daily_jarvis,
            feature_vector,
            future_return_1, future_return_3, future_return_6,
            future_return_12, future_return_24, future_return_eod,
            mfe_6, mae_6, mfe_12, mae_12, mfe_24, mae_24,
            hit_plus_0_5_atr, hit_plus_1_0_atr,
            hit_minus_0_5_atr, hit_minus_1_0_atr
        ) VALUES (
            :ticker, :ts, :timeframe, :feature_version,
            :open_price, :high_price, :low_price, :close_price, :volume,
            :body_pct, :upper_wick_ratio, :lower_wick_ratio, :is_green, :range_pct,
            :vol_ratio, :vol_zscore,
            :vwap_dist_pct, :or_position, :ema9_slope_norm,
            :rsi14, :macd_hist_norm, :atr_pct,
            :tod_min, :time_of_day, :candle_num,
            :daily_ml_rank, :daily_conviction, :daily_confluence,
            :daily_regime, :daily_vix, :daily_jarvis,
            :feature_vector,
            :future_return_1, :future_return_3, :future_return_6,
            :future_return_12, :future_return_24, :future_return_eod,
            :mfe_6, :mae_6, :mfe_12, :mae_12, :mfe_24, :mae_24,
            :hit_plus_0_5_atr, :hit_plus_1_0_atr,
            :hit_minus_0_5_atr, :hit_minus_1_0_atr
        ) ON CONFLICT (ticker, ts, timeframe) DO UPDATE SET
            feature_vector    = EXCLUDED.feature_vector,
            future_return_6   = EXCLUDED.future_return_6,
            future_return_12  = EXCLUDED.future_return_12,
            future_return_24  = EXCLUDED.future_return_24,
            future_return_eod = EXCLUDED.future_return_eod,
            mfe_12            = EXCLUDED.mfe_12,
            mae_12            = EXCLUDED.mae_12,
            hit_plus_1_0_atr  = EXCLUDED.hit_plus_1_0_atr,
            hit_minus_1_0_atr = EXCLUDED.hit_minus_1_0_atr,
            daily_ml_rank     = EXCLUDED.daily_ml_rank,
            daily_conviction  = EXCLUDED.daily_conviction,
            daily_regime      = EXCLUDED.daily_regime
    """)
    with engine.begin() as conn:
        conn.execute(sql, rows)
    return len(rows)


def _row_to_dict(r, vec: list, ctx: dict | None) -> dict:
    ctx = ctx or {}
    atr  = _sf(r.get("atr14"), 0.1) or 0.1

    def macd_norm():
        h = _sf(r.get("macd_hist"), 0.0) or 0.0
        return float(np.clip((h / atr + 2.0) / 4.0, 0.0, 1.0))

    def ema9_norm():
        sl = _sf(r.get("ema9_slope"), 0.0) or 0.0
        return float(np.clip((sl / atr + 2.0) / 4.0, 0.0, 1.0))

    def or_pos():
        if _sf(r.get("above_or_high"), 0):
            return 1.0
        if _sf(r.get("below_or_low"), 0):
            return 0.0
        return 0.5

    return {
        "ticker":          r["ticker"],
        "ts":              r["ts"],
        "timeframe":       "5m",
        "feature_version": "v1",
        "open_price":      _sf(r.get("open")),
        "high_price":      _sf(r.get("high")),
        "low_price":       _sf(r.get("low")),
        "close_price":     _sf(r.get("close")),
        "volume":          _si(r.get("volume")),
        "body_pct":        _sf(r.get("body_pct")),
        "upper_wick_ratio":_sf(r.get("upper_wick_ratio")),
        "lower_wick_ratio":_sf(r.get("lower_wick_ratio")),
        "is_green":        _sb(r.get("is_green")),
        "range_pct":       _sf(r.get("atr_pct")),
        "vol_ratio":       _sf(r.get("vol_ratio")),
        "vol_zscore":      _sf(r.get("vol_zscore")),
        "vwap_dist_pct":   _sf(r.get("dist_vwap_pct")),
        "or_position":     or_pos(),
        "ema9_slope_norm": ema9_norm(),
        "rsi14":           _sf(r.get("rsi14")),
        "macd_hist_norm":  macd_norm(),
        "atr_pct":         _sf(r.get("atr_pct")),
        "tod_min":         _si(r.get("tod_min")),
        "time_of_day":     str(r.get("time_bucket") or ""),
        "candle_num":      _si(r.get("candle_num")),
        "daily_ml_rank":   _sf(ctx.get("daily_ml_rank")),
        "daily_conviction":ctx.get("daily_conviction"),
        "daily_confluence":_sf(ctx.get("daily_confluence")),
        "daily_regime":    ctx.get("daily_regime"),
        "daily_vix":       ctx.get("daily_vix"),
        "daily_jarvis":    _sb(ctx.get("daily_jarvis")),
        "feature_vector":  vec,
        "future_return_1": _sf(r.get("future_return_1")),
        "future_return_3": _sf(r.get("future_return_3")),
        "future_return_6": _sf(r.get("future_return_6")),
        "future_return_12":_sf(r.get("future_return_12")),
        "future_return_24":_sf(r.get("future_return_24")),
        "future_return_eod":_sf(r.get("future_return_eod")),
        "mfe_6":           _sf(r.get("mfe_6")),
        "mae_6":           _sf(r.get("mae_6")),
        "mfe_12":          _sf(r.get("mfe_12")),
        "mae_12":          _sf(r.get("mae_12")),
        "mfe_24":          _sf(r.get("mfe_24")),
        "mae_24":          _sf(r.get("mae_24")),
        "hit_plus_0_5_atr":  _sb(r.get("hit_plus_0_5_atr")),
        "hit_plus_1_0_atr":  _sb(r.get("hit_plus_1_0_atr")),
        "hit_minus_0_5_atr": _sb(r.get("hit_minus_0_5_atr")),
        "hit_minus_1_0_atr": _sb(r.get("hit_minus_1_0_atr")),
    }


# ---------------------------------------------------------------------------
# Per-ticker processing
# ---------------------------------------------------------------------------

def process_ticker(engine, ticker: str, ctx_df: pd.DataFrame,
                   since_ts=None) -> int:
    """Load bars, compute features + outcomes, upsert. Returns rows written."""
    # Use f-string for ticker (alphanumeric, safe); ts handled via text() params
    bars = pd.read_sql(
        text(f"SELECT ticker,ts,open,high,low,close,volume FROM intraday_bars WHERE ticker = '{ticker}' ORDER BY ts"),
        engine,
    )
    if len(bars) < 30:
        return 0

    bars["ts"] = pd.to_datetime(bars["ts"], utc=True)

    # Compute features (uses full history for rolling windows -- always load all)
    if since_ts is not None:
        all_bars = pd.read_sql(
            text(f"SELECT ticker,ts,open,high,low,close,volume FROM intraday_bars WHERE ticker = '{ticker}' ORDER BY ts"),
            engine,
        )
        all_bars["ts"] = pd.to_datetime(all_bars["ts"], utc=True)
        feat_df = compute_features(all_bars)
        feat_df = _add_derived_features(feat_df)
        feat_df = _compute_forward_outcomes(feat_df)
        # Filter to only new rows
        cutoff = pd.Timestamp(since_ts, tz="UTC") if since_ts is not None else None
        if cutoff is not None:
            feat_df = feat_df[feat_df["ts"] > cutoff]
    else:
        feat_df = compute_features(bars)
        feat_df = _add_derived_features(feat_df)
        feat_df = _compute_forward_outcomes(feat_df)

    if feat_df.empty:
        return 0

    # Join daily context (by date)
    ticker_ctx = ctx_df[ctx_df["ticker"] == ticker].copy()
    feat_df["_date"] = feat_df["ts"].dt.tz_convert("America/New_York").dt.date
    feat_df["_date"] = feat_df["_date"].astype(str)
    ticker_ctx["pred_date"] = ticker_ctx["pred_date"].astype(str)
    feat_df = feat_df.merge(
        ticker_ctx.rename(columns={"pred_date": "_date"}),
        on=["_date"],
        how="left",
        suffixes=("", "_ctx"),
    )
    # Drop duplicate ticker_ctx column if present
    if "ticker_ctx" in feat_df.columns:
        feat_df = feat_df.drop(columns=["ticker_ctx"])

    # Build batch feature vectors
    feat_mat = build_vectors_batch(feat_df)   # (N, 16)

    rows = []
    for i, (_, row) in enumerate(feat_df.iterrows()):
        vec = feat_mat[i].tolist()
        ctx = {
            "daily_ml_rank":    row.get("daily_ml_rank"),
            "daily_conviction": row.get("daily_conviction"),
            "daily_confluence": row.get("daily_confluence"),
            "daily_regime":     row.get("daily_regime"),
            "daily_vix":        row.get("daily_vix"),
            "daily_jarvis":     row.get("daily_jarvis"),
        }
        rows.append(_row_to_dict(row, vec, ctx))

    written = 0
    for start in range(0, len(rows), BATCH):
        written += _upsert_batch(engine, rows[start: start + BATCH])
    return written


# ---------------------------------------------------------------------------
# Similarity query for latest candle per ticker
# ---------------------------------------------------------------------------

def _update_similarity_latest(engine) -> None:
    """
    For each ticker's most recent candle, find K=50 similar historical candles
    and store the aggregated result in intraday_similarity_latest.
    """
    mem_df = pd.read_sql(
        """
        SELECT id, ticker, ts, time_of_day, daily_regime, daily_conviction,
               feature_vector,
               future_return_6, mfe_12, mae_12,
               hit_plus_1_0_atr, hit_minus_1_0_atr
        FROM intraday_candle_memory
        ORDER BY ts ASC
        """,
        engine,
    )
    if mem_df.empty:
        print("  [similarity] No candle memory -- skipping latest update")
        return

    # Deserialize feature_vector (stored as pg array, comes back as list)
    mem_df["feature_vector"] = mem_df["feature_vector"].apply(
        lambda v: list(v) if v is not None else None
    )
    mem_df = mem_df[mem_df["feature_vector"].notna()]

    if len(mem_df) < K_QUERY + 1:
        print(f"  [similarity] Only {len(mem_df)} rows -- need {K_QUERY + 1} minimum")
        return

    # Latest candle per ticker
    latest = (
        mem_df.sort_values("ts")
        .groupby("ticker")
        .last()
        .reset_index()
    )

    search = SimilaritySearch()
    # Index does NOT include the latest candles themselves (use all prior)
    cutoff_ts = latest["ts"].min()
    history   = mem_df[mem_df["ts"] < cutoff_ts].copy()
    if len(history) < K_QUERY:
        history = mem_df  # fallback

    search.fit(history)

    rows = []
    for _, lrow in latest.iterrows():
        ticker = lrow["ticker"]
        vec    = np.array(lrow["feature_vector"])
        time_gate   = str(lrow.get("time_of_day") or "")
        regime_gate = str(lrow.get("daily_regime") or "")

        matches = search.query(
            vec,
            k=K_QUERY,
            gate_time=time_gate if time_gate else None,
            gate_regime=regime_gate if regime_gate else None,
        )

        agg = aggregate_outcomes(matches, horizon=6)

        top5 = []
        for _, m in matches.head(5).iterrows():
            top5.append({
                "ticker": str(m.get("ticker", "")),
                "ts":     str(m.get("ts", "")),
                "dist":   round(float(m.get("distance", 99.0)), 4),
                "ret6":   round(float(m.get("future_return_6") or 0.0), 3),
            })

        rows.append({
            "ticker":               ticker,
            "as_of_ts":             lrow["ts"],
            "k_used":               K_QUERY,
            "matched_sample":       agg.get("valid_count", 0),
            "time_gate":            time_gate or None,
            "regime_gate":          regime_gate or None,
            "similarity_return_6":  agg.get("mean_return"),
            "similarity_hitrate":   agg.get("hit_rate"),
            "similarity_mfe_12":    agg.get("mfe_12_mean"),
            "similarity_mae_12":    agg.get("mae_12_mean"),
            "pct_hit_plus_1atr":    agg.get("pct_hit_plus_1atr"),
            "pct_hit_minus_1atr":   agg.get("pct_hit_minus_1atr"),
            "top_neighbors":        json.dumps(top5),
            "raw_summary":          json.dumps({
                k: v for k, v in agg.items() if k != "horizon_summary"
            }),
        })

    # Clean NaN strings before upsert
    for r in rows:
        for k in ("time_gate", "regime_gate"):
            v = r.get(k)
            if v is not None and str(v).lower() in ("nan", "none", ""):
                r[k] = None

    upsert_sql = text("""
        INSERT INTO intraday_similarity_latest (
            ticker, as_of_ts, k_used, matched_sample,
            time_gate, regime_gate,
            similarity_return_6, similarity_hitrate,
            similarity_mfe_12, similarity_mae_12,
            pct_hit_plus_1atr, pct_hit_minus_1atr,
            top_neighbors, raw_summary, updated_at
        ) VALUES (
            :ticker, :as_of_ts, :k_used, :matched_sample,
            :time_gate, :regime_gate,
            :similarity_return_6, :similarity_hitrate,
            :similarity_mfe_12, :similarity_mae_12,
            :pct_hit_plus_1atr, :pct_hit_minus_1atr,
            CAST(:top_neighbors AS jsonb), CAST(:raw_summary AS jsonb), now()
        )
        ON CONFLICT (ticker) DO UPDATE SET
            as_of_ts           = EXCLUDED.as_of_ts,
            k_used             = EXCLUDED.k_used,
            matched_sample     = EXCLUDED.matched_sample,
            time_gate          = EXCLUDED.time_gate,
            regime_gate        = EXCLUDED.regime_gate,
            similarity_return_6= EXCLUDED.similarity_return_6,
            similarity_hitrate = EXCLUDED.similarity_hitrate,
            similarity_mfe_12  = EXCLUDED.similarity_mfe_12,
            similarity_mae_12  = EXCLUDED.similarity_mae_12,
            pct_hit_plus_1atr  = EXCLUDED.pct_hit_plus_1atr,
            pct_hit_minus_1atr = EXCLUDED.pct_hit_minus_1atr,
            top_neighbors      = EXCLUDED.top_neighbors,
            raw_summary        = EXCLUDED.raw_summary,
            updated_at         = now()
    """)
    with engine.begin() as conn:
        conn.execute(upsert_sql, rows)
    print(f"  [similarity] Updated similarity_latest for {len(rows)} tickers")


# ---------------------------------------------------------------------------
# Entry points callable from nightly_pipeline
# ---------------------------------------------------------------------------

def run_full(engine) -> dict:
    """Full rebuild -- processes all tickers from scratch."""
    print("[candle-memory] Full build starting...")
    with engine.connect() as _conn:
        tickers = [r[0] for r in _conn.execute(
            text("SELECT DISTINCT ticker FROM intraday_bars ORDER BY ticker")
        )]
    ctx_df  = _load_daily_context(engine, tickers)

    total = 0
    for tk in tickers:
        n = process_ticker(engine, tk, ctx_df, since_ts=None)
        total += n
        print(f"  {tk}: {n} rows written")

    _update_similarity_latest(engine)
    print(f"[candle-memory] Full build done -- {total} total rows, {len(tickers)} tickers")
    return {"rows_written": total, "tickers": len(tickers)}


def run_incremental(engine) -> dict:
    """Incremental -- only processes bars newer than latest memory timestamp per ticker."""
    print("[candle-memory] Incremental update starting...")
    latest_ts = pd.read_sql(
        "SELECT ticker, MAX(ts) AS max_ts FROM intraday_candle_memory GROUP BY ticker",
        engine,
    ).set_index("ticker")["max_ts"].to_dict()

    with engine.connect() as _conn:
        tickers = [r[0] for r in _conn.execute(
            text("SELECT DISTINCT ticker FROM intraday_bars ORDER BY ticker")
        )]
    ctx_df = _load_daily_context(engine, tickers)

    total = 0
    for tk in tickers:
        since = latest_ts.get(tk)
        n = process_ticker(engine, tk, ctx_df, since_ts=since)
        total += n
        if n > 0:
            print(f"  {tk}: {n} new rows")

    _update_similarity_latest(engine)
    print(f"[candle-memory] Incremental done -- {total} new rows")
    return {"rows_written": total, "tickers": len(tickers)}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Build intraday candle memory")
    grp = parser.add_mutually_exclusive_group(required=True)
    grp.add_argument("--full",        action="store_true", help="Full rebuild")
    grp.add_argument("--incremental", action="store_true", help="Incremental update")
    args = parser.parse_args()

    engine = create_engine(DB_URL)

    if args.full:
        result = run_full(engine)
    else:
        result = run_incremental(engine)

    print(f"\nResult: {result}")


if __name__ == "__main__":
    main()
