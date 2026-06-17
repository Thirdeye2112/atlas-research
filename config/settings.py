"""
Central settings for atlas-research.
Loaded from environment variables / .env file.
All pipeline modules import `settings` from here.
"""

from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Base paths
# ---------------------------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT_DIR / "config"
SCRIPTS_DIR = ROOT_DIR / "scripts"

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
DATABASE_URL: str = os.environ.get(
    "DATABASE_URL",
    "postgresql://atlas:password@localhost:5432/atlas_research",
)

# ---------------------------------------------------------------------------
# Universe
# ---------------------------------------------------------------------------
UNIVERSE_CSV: Path = Path(
    os.environ.get("UNIVERSE_CSV", str(CONFIG_DIR / "universe.csv"))
)

# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------
DOWNLOAD_BATCH_SIZE: int = int(os.environ.get("DOWNLOAD_BATCH_SIZE", "50"))
DOWNLOAD_BATCH_DELAY_S: float = float(os.environ.get("DOWNLOAD_BATCH_DELAY_S", "2.0"))
DOWNLOAD_MAX_RETRIES: int = int(os.environ.get("DOWNLOAD_MAX_RETRIES", "3"))
BACKFILL_YEARS: int = int(os.environ.get("BACKFILL_YEARS", "15"))

# ---------------------------------------------------------------------------
# Features
# ---------------------------------------------------------------------------
FEATURE_VERSION: str = os.environ.get("FEATURE_VERSION", "v1")

# snapshot_version is set once per pipeline run so every row written in that
# run carries the same tag.  Format: "run_YYYY-MM-DD" by default.
# Override via env for ad-hoc backfills: SNAPSHOT_VERSION=backfill_2015_2020
SNAPSHOT_VERSION: str | None = os.environ.get("SNAPSHOT_VERSION")  # None → pipeline sets it

# The 23 canonical Phase-1 features produced by the feature modules.
# EAV rows use these exact strings as feature_name.
# NOTE: regime features (spy_above_sma50, market_trend, etc.) are written
# alongside but kept separate so the ML feature set is explicit.
PHASE1_FEATURES: list[str] = [
    # Returns
    "return_1d",
    "return_3d",
    "return_5d",
    "return_10d",
    "return_20d",
    "return_60d",
    # Trend
    "distance_sma20",
    "distance_sma50",
    "distance_sma200",
    "above_sma20",
    "above_sma50",
    "above_sma200",
    # Momentum
    "rsi_14",
    "macd_histogram",
    "roc_20",
    # Volatility
    "atr_14",
    "realized_vol_20",
    "realized_vol_60",
    # Volume
    "volume_ratio_20",
    "dollar_volume_20",
    # Relative strength vs SPY
    "rs_spy_20",
    "rs_spy_60",
    "rs_spy_120",
]

# Regime features — computed from SPY; written to feature_snapshots per-ticker
# so ML models can condition on market context.  Kept separate from PHASE1_FEATURES
# so it is explicit which features are ticker-specific vs market-wide.
REGIME_FEATURES: list[str] = [
    "spy_above_sma50",
    "spy_above_sma200",
    "spy_return_20d",
    "market_trend",
]

# OMNI-82 features (Oscar Carboni's OMNI confirmed as EMA(Low, 82))
OMNI_FEATURES: list[str] = [
    "omni_82_value",
    "omni_82_above",
    "omni_82_distance",
    "omni_82_slope",
    "omni_82_bounce",
]

# Momentum v2 — rate-of-change features for rank discrimination
# These continuous delta features give the model 50+ distinct rank buckets
# vs the 8-bucket collapse caused by over-reliance on binary above/below flags.
MOMENTUM_V2_FEATURES: list[str] = [
    "omni_82_distance_5d_change",  # how fast price is moving vs OMNI support
    "omni_82_slope_10d",           # longer-horizon OMNI slope vs 5-bar slope
    "rsi_momentum_5d",             # RSI velocity (today minus 5d ago)
    "distance_sma20_momentum",     # SMA20 distance velocity
    "volume_trend_5d",             # recent 5-bar avg vol / prior 5-bar avg vol
    "rs_spy_20_momentum",          # change in 20d RS vs SPY over 5 bars
]

# All features written to feature_snapshots in Phase 1.5
# = PHASE1_FEATURES + REGIME_FEATURES + OMNI_FEATURES + MOMENTUM_V2_FEATURES
ALL_FEATURES: list[str] = PHASE1_FEATURES + REGIME_FEATURES + OMNI_FEATURES + MOMENTUM_V2_FEATURES

# Inference-only columns: computed in feature_factory / omni_proxy, written to EAV,
# but intentionally excluded from ALL_FEATURES to avoid changing ML training shape.
# These columns are exported alongside ALL_FEATURES in parquet and wide exports
# for use in confluence scoring, edge hierarchy, and Jarvis gating.
INFERENCE_EXTRA_COLS: list[str] = [
    "jarvis_quality_adjusted",  # Tier-adjusted OMNI signal (Jarvis logic)
    "quality_tier",             # Stock quality tier: 1=large/mid cap, 4=micro/junk
    "oscar_87_above_50",        # OSCAR(87) oscillator above 50 threshold flag
    "hma_87_above",             # HMA(87) above/below close flag
]

# ---------------------------------------------------------------------------
# Feature metadata — canonical registry entries for Phase-1 features.
# Seeded into feature_metadata table by init_db.py.
# category / source_module / description are institution-standard fields.
# ---------------------------------------------------------------------------
FEATURE_METADATA: list[dict] = [
    # Returns
    {"feature_name": "return_1d",          "category": "return",            "source_module": "atlas_research.features.momentum",         "description": "Log return over 1 trading day",                        "data_type": "float"},
    {"feature_name": "return_3d",          "category": "return",            "source_module": "atlas_research.features.momentum",         "description": "Log return over 3 trading days",                       "data_type": "float"},
    {"feature_name": "return_5d",          "category": "return",            "source_module": "atlas_research.features.momentum",         "description": "Log return over 5 trading days",                       "data_type": "float"},
    {"feature_name": "return_10d",         "category": "return",            "source_module": "atlas_research.features.momentum",         "description": "Log return over 10 trading days",                      "data_type": "float"},
    {"feature_name": "return_20d",         "category": "return",            "source_module": "atlas_research.features.momentum",         "description": "Log return over 20 trading days",                      "data_type": "float"},
    {"feature_name": "return_60d",         "category": "return",            "source_module": "atlas_research.features.momentum",         "description": "Log return over 60 trading days",                      "data_type": "float"},
    # Trend
    {"feature_name": "distance_sma20",     "category": "trend",             "source_module": "atlas_research.features.trend",            "description": "(close - SMA20) / SMA20",                              "data_type": "float"},
    {"feature_name": "distance_sma50",     "category": "trend",             "source_module": "atlas_research.features.trend",            "description": "(close - SMA50) / SMA50",                              "data_type": "float"},
    {"feature_name": "distance_sma200",    "category": "trend",             "source_module": "atlas_research.features.trend",            "description": "(close - SMA200) / SMA200",                            "data_type": "float"},
    {"feature_name": "above_sma20",        "category": "trend",             "source_module": "atlas_research.features.trend",            "description": "1.0 if close > SMA20 else 0.0",                        "data_type": "float"},
    {"feature_name": "above_sma50",        "category": "trend",             "source_module": "atlas_research.features.trend",            "description": "1.0 if close > SMA50 else 0.0",                        "data_type": "float"},
    {"feature_name": "above_sma200",       "category": "trend",             "source_module": "atlas_research.features.trend",            "description": "1.0 if close > SMA200 else 0.0",                       "data_type": "float"},
    # Momentum
    {"feature_name": "rsi_14",             "category": "momentum",          "source_module": "atlas_research.features.momentum",         "description": "Wilder RSI 14-period (0-100)",                          "data_type": "float"},
    {"feature_name": "macd_histogram",     "category": "momentum",          "source_module": "atlas_research.features.momentum",         "description": "MACD(12,26,9) histogram value",                        "data_type": "float"},
    {"feature_name": "roc_20",             "category": "momentum",          "source_module": "atlas_research.features.momentum",         "description": "Rate of change over 20 days (simple return)",          "data_type": "float"},
    # Volatility
    {"feature_name": "atr_14",             "category": "volatility",        "source_module": "atlas_research.features.volatility",       "description": "Average True Range 14-period",                         "data_type": "float"},
    {"feature_name": "realized_vol_20",    "category": "volatility",        "source_module": "atlas_research.features.volatility",       "description": "Annualised realised volatility over 20 days",          "data_type": "float"},
    {"feature_name": "realized_vol_60",    "category": "volatility",        "source_module": "atlas_research.features.volatility",       "description": "Annualised realised volatility over 60 days",          "data_type": "float"},
    # Volume
    {"feature_name": "volume_ratio_20",    "category": "volume",            "source_module": "atlas_research.features.volume",           "description": "Today volume / 20-day average volume",                 "data_type": "float"},
    {"feature_name": "dollar_volume_20",   "category": "volume",            "source_module": "atlas_research.features.volume",           "description": "20-day average dollar volume (close * volume)",        "data_type": "float"},
    # Relative strength
    {"feature_name": "rs_spy_20",          "category": "relative_strength", "source_module": "atlas_research.features.relative_strength", "description": "Log return (20d) minus SPY log return (20d)",         "data_type": "float"},
    {"feature_name": "rs_spy_60",          "category": "relative_strength", "source_module": "atlas_research.features.relative_strength", "description": "Log return (60d) minus SPY log return (60d)",         "data_type": "float"},
    {"feature_name": "rs_spy_120",         "category": "relative_strength", "source_module": "atlas_research.features.relative_strength", "description": "Log return (120d) minus SPY log return (120d)",       "data_type": "float"},
    # Regime
    {"feature_name": "spy_above_sma50",    "category": "regime",            "source_module": "atlas_research.features.regime",           "description": "1.0 if SPY > SMA50 else 0.0",                         "data_type": "float"},
    {"feature_name": "spy_above_sma200",   "category": "regime",            "source_module": "atlas_research.features.regime",           "description": "1.0 if SPY > SMA200 else 0.0",                        "data_type": "float"},
    {"feature_name": "spy_return_20d",     "category": "regime",            "source_module": "atlas_research.features.regime",           "description": "SPY 20-day log return",                                "data_type": "float"},
    {"feature_name": "market_trend",       "category": "regime",            "source_module": "atlas_research.features.regime",           "description": "+1 bull / 0 neutral / -1 bear (SPY SMA composite)",   "data_type": "float"},
]

# ---------------------------------------------------------------------------
# Parquet export
# ---------------------------------------------------------------------------
PARQUET_OUTPUT_DIR: Path = Path(
    os.environ.get("PARQUET_OUTPUT_DIR", str(ROOT_DIR / "exports" / "parquet"))
)
PARQUET_COMPRESSION: str = os.environ.get("PARQUET_COMPRESSION", "snappy")

# ---------------------------------------------------------------------------
# Phase 2 — Model training
# ---------------------------------------------------------------------------
MODEL_DIR: Path = Path(os.environ.get("MODEL_DIR", str(ROOT_DIR / "models")))

# Quality filter: rows with data_quality_score below this are excluded from
# training entirely.  Q1 resolution: hard filter, not a feature weight.
TRAIN_MIN_QUALITY_SCORE: float = float(os.environ.get("TRAIN_MIN_QUALITY_SCORE", "0.70"))

# Walk-forward purge gap: number of trading days between the last training
# bar and the first validation bar.  Prevents label leakage for 5-day returns
# (a bar on day T with label fwd_5d uses data through T+5, so we need at least
# 5 days of gap before the validation period starts).
WF_PURGE_DAYS: int = int(os.environ.get("WF_PURGE_DAYS", "5"))

# Walk-forward fold configuration (expanding window)
# Each fold adds one year of training data; validation = next 12 months.
WF_MIN_TRAIN_YEARS: int = int(os.environ.get("WF_MIN_TRAIN_YEARS", "3"))
WF_VAL_MONTHS: int = int(os.environ.get("WF_VAL_MONTHS", "12"))

# Out-of-sample embargo: the final WF_OOS_MONTHS of data are reserved as a
# hold-out that fold generation never touches.  All fold selection / tuning
# happens strictly before this window; the OOS is scored exactly once, at the
# end, on the single chosen model.  Set to 0 to disable (use all data for folds).
WF_OOS_MONTHS: int = int(os.environ.get("WF_OOS_MONTHS", "12"))

# Parallel fold execution — deferred to Phase 3.
# Set to 1 (sequential) until walk-forward correctness is proven on real data.
# When ready: set > 1 and implement ProcessPoolExecutor in walk_forward.py.
WF_PARALLEL_FOLDS: int = int(os.environ.get("WF_PARALLEL_FOLDS", "1"))

# LightGBM default hyperparameters (not tuned nightly — stable baselines)
LGBM_PARAMS_REGRESSOR: dict = {
    "objective":        "regression",
    "metric":           "rmse",
    "n_estimators":     500,
    "learning_rate":    0.05,
    "max_depth":        6,
    "num_leaves":       31,
    "min_child_samples": 50,
    "subsample":        0.8,
    "colsample_bytree": 0.8,
    "reg_alpha":        0.1,
    "reg_lambda":       1.0,
    "n_jobs":           -1,
    "random_state":     42,
    "verbose":          -1,
}

LGBM_PARAMS_CLASSIFIER: dict = {
    "objective":        "binary",
    "metric":           "binary_logloss",
    "n_estimators":     500,
    "learning_rate":    0.05,
    "max_depth":        6,
    "num_leaves":       31,
    "min_child_samples": 50,
    "subsample":        0.8,
    "colsample_bytree": 0.8,
    "reg_alpha":        0.1,
    "reg_lambda":       1.0,
    "n_jobs":           -1,
    "random_state":     42,
    "verbose":          -1,
}

# ---------------------------------------------------------------------------
# Feature sets for training
# ---------------------------------------------------------------------------

# Features classified as degrading by inspect_feature_health.py (2026-06-14):
# sign-unstable across walk-forward folds (sign_stability < 0.45).
# These remain in ALL_FEATURES and feature_snapshots — only excluded from training.
_DEGRADING_FEATURES: list[str] = [
    "roc_20",
    "rs_spy_20",
    "return_20d",
    "rsi_14",
    "above_sma20",
    "return_5d",
    "return_3d",
    "distance_sma20",
    "return_10d",
    "return_1d",
    "macd_histogram",
    "omni_82_value",
]

# V1 — full feature set.  Baseline / rollback.
#
# data_quality_score is intentionally EXCLUDED: across the entire parquet corpus
# (2011-2026) it is a dead constant == 1.0 (nunique==1), because the ingest
# validation layer never emits a discriminating score.  As a model feature it is
# pure noise/overhead; as the TRAIN_MIN_QUALITY_SCORE>=0.70 hard filter it never
# drops a row (quality_dropped==0 on every fold).  The filter is therefore inert
# today — fixing the upstream scorer to discriminate is a separate pipeline task
# (would require re-running ingest validation and re-exporting all parquet).
# Until then we neither feed nor rely on the constant.
TRAIN_FEATURES_V1: list[str] = list(ALL_FEATURES)

# V2 — degrading features removed (27 features).
# Holdout-validated: V2 did NOT beat V1 on holdout (V1 wins 4/7 metrics).
TRAIN_FEATURES_V2: list[str] = [f for f in TRAIN_FEATURES_V1 if f not in _DEGRADING_FEATURES]

# V3 — V1 base (39) + regime-interaction features (10). Experimental.
# Each interaction = base_feature * binary_regime_mask.
# Rationale: regime sensitivity study showed OMNI useful only above 200DMA,
# realized_vol useful only below 200DMA, RS features useful only in bull markets.
REGIME_INTERACTION_FEATURES: list[str] = [
    "omni_82_distance_x_above_200dma",   # OMNI support distance when above 200DMA
    "omni_82_above_x_above_200dma",      # OMNI flag when above 200DMA
    "omni_82_slope_x_above_200dma",      # OMNI slope when above 200DMA
    "realized_vol_20_x_below_200dma",    # vol signal when below 200DMA
    "realized_vol_60_x_below_200dma",    # vol signal (60d) when below 200DMA
    "return_1d_x_below_200dma",          # 1d return mean-reversion in downtrend
    "return_3d_x_below_200dma",          # 3d return mean-reversion in downtrend
    "return_5d_x_below_200dma",          # 5d return mean-reversion in downtrend
    "rs_spy_20_x_bull",                  # RS vs SPY in bull market only
    "rs_spy_60_x_bull",                  # RS vs SPY (60d) in bull market only
]
TRAIN_FEATURES_V3: list[str] = TRAIN_FEATURES_V1 + REGIME_INTERACTION_FEATURES

# Active feature set version — controls which set the pipeline uses.
# Override via env: MODEL_FEATURE_SET_VERSION=v2 or MODEL_FEATURE_SET_VERSION=v3
MODEL_FEATURE_SET_VERSION: str = os.environ.get("MODEL_FEATURE_SET_VERSION", "v1")

# TRAIN_FEATURES resolves to the active version's list.
TRAIN_FEATURES: list[str] = (
    TRAIN_FEATURES_V2 if MODEL_FEATURE_SET_VERSION == "v2"
    else TRAIN_FEATURES_V3 if MODEL_FEATURE_SET_VERSION == "v3"
    else TRAIN_FEATURES_V1
)

# Model versioning: incremented manually when training logic changes
MODEL_VERSION: str = os.environ.get("MODEL_VERSION", "v1")

# ---------------------------------------------------------------------------
# Labels
# ---------------------------------------------------------------------------
LABEL_HORIZONS_DAYS: list[int] = [1, 5, 10, 20, 60]

# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------
PIPELINE_CRON: str = os.environ.get("PIPELINE_CRON", "0 2 * * 1-5")
PIPELINE_TIMEZONE: str = os.environ.get("PIPELINE_TIMEZONE", "America/New_York")

# ---------------------------------------------------------------------------
# Atlas Alpha integration (optional, read-only)
# ---------------------------------------------------------------------------
ATLAS_ALPHA_API_URL: str | None = os.environ.get("ATLAS_ALPHA_API_URL")

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO").upper()
LOG_FORMAT: str = os.environ.get("LOG_FORMAT", "console")  # 'console' | 'json'
