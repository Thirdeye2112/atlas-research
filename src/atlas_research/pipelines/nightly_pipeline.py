"""
Nightly pipeline — Phase 1.5 orchestrator.

Steps (in order):
    1.  Create research_run record
    2.  Load active universe from securities table
    3.  Download latest OHLCV (yahoo_ingest)
    4.  Upsert raw_bars
    5.  Validate bars (validate.py) — skip bad tickers, log issues
    6.  Generate features → feature_snapshots (EAV)
    7.  Generate labels where future data exists
    8.  Export wide feature matrix → parquet file
    9.  Export JSON feature snapshot → production_exports table
    10. [NEW] Predict-only: score today's parquet with latest model
    10.5 [META] Attach meta-signal scores to today's predictions (uses prior night combo scores)
    11. [NEW] Compute prediction outcomes (retroactive, all mature parquets)
    12. [NEW] Compute feature reliability (rolling IC, 30d/90d/180d windows)
    13. [NEW] Check retrain needed (7 triggers, recommendation only unless --auto-retrain)
    14. Calibration sync + score decomp
    15. Attribution pipeline
    16. Wide table refresh
    16.5 [META] Compute signal combination scores (updates combo scores for tomorrow's tagging)
    17. Mark run complete
    18. [INTRADAY] Ingest 5-min bars, detect setups, compute outcomes (if enabled)
    18.5 [INTRADAY] Update intraday candidate watchlist
    19. [INTRADAY WEEKLY] Run adaptive rule refinement (Mondays or when forced)
    20. [INTRADAY] Incremental candle memory build + similarity_latest refresh

Each step is isolated — failure in one step marks run as partial, not fatal.
Validation failures are warnings, not errors (partial data is normal).
"""

from __future__ import annotations

import traceback
from datetime import date, timedelta

from config import settings
from atlas_research.db import repository
from atlas_research.exports.parquet_export import run_parquet_export
from atlas_research.exports.production_export import run_export
from atlas_research.features.feature_factory import build_features
from atlas_research.ingest.yahoo_ingest import download_universe
from atlas_research.ingest.validate import validate_bars, summary as validation_summary
from atlas_research.labels.label_factory import build_labels_for_universe
from atlas_research.utils.logging import get_logger

log = get_logger(__name__)


def run_nightly(
    run_date: date | None = None,
    *,
    force_full_ingest: bool = False,
    skip_ingest: bool = False,
    skip_features: bool = False,
    skip_labels: bool = False,
    skip_parquet: bool = False,
    skip_json_export: bool = False,
    skip_predict: bool = False,
    skip_outcomes: bool = False,
    skip_reliability: bool = False,
    skip_retrain_check: bool = False,
    skip_meta_scoring: bool = False,
    skip_intraday: bool = False,
    intraday_only: bool = False,
    run_weekly_refinement: bool = False,
    auto_retrain: bool = False,
    triggered_by: str = "scheduler",
    snapshot_version: str | None = None,
) -> dict:
    """
    Run the full nightly pipeline.

    Args:
        run_date:          Date to process. Defaults to today.
        force_full_ingest: Re-download full BACKFILL_YEARS of history.
        skip_*:            Skip individual steps for re-runs / debugging.
        skip_intraday:         Skip Steps 18/18.5 (5-min intraday collection).
        intraday_only:         Run only Steps 18/18.5; skip all daily steps.
        run_weekly_refinement: Force Step 19 (adaptive rule refinement). Auto-runs on Mondays.
        triggered_by:      'scheduler' | 'cli' | 'test'
        snapshot_version:  Tag written to every feature_snapshots row this run.
                           Defaults to 'run_YYYY-MM-DD'.

    Returns:
        Summary dict with run_id, status, and per-step metrics.
    """
    if run_date is None:
        run_date = date.today()

    snap_ver = snapshot_version or f"run_{run_date.isoformat()}"

    log.info("pipeline.started", date=str(run_date), snapshot_version=snap_ver)

    # ── Step 1: create research_run ───────────────────────────
    run_id = repository.create_research_run(run_type="nightly")

    counters = {
        "tickers_processed": 0,
        "bars_inserted":     0,
        "features_generated": 0,
        "labels_generated":   0,
    }
    errors: list[str] = []      # fatal — flip the run to 'failed'
    warnings: list[str] = []    # non-fatal — recorded but run stays complete/partial
    step_results: dict = {}
    _quality_scores: dict[str, float] = {}
    _quality_flags:  dict[str, str]   = {}

    # intraday_only: skip all daily steps below
    _run_daily = not intraday_only

    try:
        # ── Step 2: load universe ─────────────────────────────
        tickers = repository.get_active_tickers()
        if not tickers:
            raise RuntimeError(
                "No active tickers in securities table. Run scripts/init_db.py first."
            )
        log.info("pipeline.universe", count=len(tickers))

        # ── Steps 3 & 4: ingest ───────────────────────────────
        if not _run_daily:
            counters["tickers_processed"] = len(tickers)
            log.info("pipeline.daily_skipped", reason="intraday_only=True")
        if _run_daily and not skip_ingest:
            start_date = _ingest_start(run_date, force_full_ingest)
            log.info("pipeline.ingest", start=str(start_date), end=str(run_date))
            bars_ok, failed = download_universe(
                tickers,
                start_date=start_date,
                end_date=run_date,
                batch_size=settings.DOWNLOAD_BATCH_SIZE,
                batch_delay=settings.DOWNLOAD_BATCH_DELAY_S,
            )
            counters["bars_inserted"]    = bars_ok
            counters["tickers_processed"] = len(tickers) - len(failed)
            step_results["ingest"] = {
                "bars": bars_ok,
                "failed": len(failed),
                "failed_tickers": [t for t, _ in failed[:20]],
            }
            # A handful of tickers failing to ingest (delisted symbols, brief
            # Yahoo gaps) is normal and must not fail the whole run. Record as a
            # non-fatal warning so it stays visible in the health report.
            if failed:
                warnings.append(f"ingest_failures({len(failed)}): {[t for t, _ in failed[:5]]}")
            log.info("pipeline.ingest_done", bars=bars_ok, failed=len(failed))
        else:
            counters["tickers_processed"] = len(tickers)
            log.info("pipeline.ingest_skipped")

        # ── Step 5: validate + step 6: features ───────────────
        if _run_daily and not skip_features:
            spy_bars = repository.get_bars("SPY", end=run_date)
            features_written, val_summary = _run_features(
                tickers, run_date, spy_bars, snap_ver
            )
            counters["features_generated"] = features_written
            step_results["features"] = {
                "rows_written":      features_written,
                "validation_clean":  val_summary.get("clean", 0),
                "validation_warned": val_summary.get("warnings", 0),
                "validation_fatal":  val_summary.get("fatal", 0),
            }
            log.info(
                "pipeline.features_done",
                written=features_written,
                fatal=val_summary.get("fatal", 0),
                warned=val_summary.get("warnings", 0),
            )
            # Quality scores / flags for the parquet step
            _quality_scores = val_summary.get("quality_scores", {})
            _quality_flags  = val_summary.get("quality_flags", {})
        elif not _run_daily:
            _quality_scores, _quality_flags = {}, {}
        else:
            log.info("pipeline.features_skipped")
            _quality_scores, _quality_flags = {}, {}

        # ── Step 7: labels ────────────────────────────────────
        if _run_daily and not skip_labels:
            labels_n = build_labels_for_universe(tickers, as_of=run_date)
            counters["labels_generated"] = labels_n
            step_results["labels"] = {"rows": labels_n}
            log.info("pipeline.labels_done", rows=labels_n)
        else:
            log.info("pipeline.labels_skipped")

        # ── Step 8: parquet export ────────────────────────────
        if _run_daily and not skip_parquet:
            try:
                parquet_path = run_parquet_export(
                    run_date,
                    feature_version=settings.FEATURE_VERSION,
                    feature_names=settings.ALL_FEATURES,
                    quality_scores=_quality_scores,
                    quality_flags=_quality_flags,
                )
                step_results["parquet"] = {"path": str(parquet_path) if parquet_path else None}
                log.info("pipeline.parquet_done", path=str(parquet_path) if parquet_path else None)
            except Exception as exc:
                log.error("pipeline.parquet_failed", error=str(exc))
                errors.append(f"parquet_failed: {exc}")
        else:
            log.info("pipeline.parquet_skipped")

        # ── Step 9: JSON export ───────────────────────────────
        if _run_daily and not skip_json_export:
            try:
                records = run_export(run_date, feature_version=settings.FEATURE_VERSION)
                step_results["json_export"] = {"records": len(records)}
                log.info("pipeline.json_export_done", records=len(records))
            except Exception as exc:
                log.error("pipeline.json_export_failed", error=str(exc))
                errors.append(f"json_export_failed: {exc}")
        else:
            log.info("pipeline.json_export_skipped")

    except Exception as exc:
        log.error("pipeline.fatal_error", error=str(exc))
        log.debug(traceback.format_exc())
        errors.append(str(exc))

    # ── Step 10: Predict-only (non-fatal) ─────────────────
    # Score today's parquet with the latest trained model + adaptive calibrator.
    if _run_daily and not skip_predict:
        try:
            import glob as _glob
            model_dir = settings.MODEL_DIR
            artifacts = sorted(model_dir.glob("**/model.joblib"), key=lambda p: str(p))
            if artifacts:
                latest_artifact = artifacts[-1]
                from atlas_research.models.predict import run_prediction_pipeline
                n_preds = run_prediction_pipeline(
                    pred_date=run_date,
                    model_artifact_path=latest_artifact,
                    parquet_dir=settings.PARQUET_OUTPUT_DIR,
                    feature_cols=settings.TRAIN_FEATURES,
                    model_name="return_regressor",
                    model_version=settings.MODEL_VERSION,
                    use_calibrator=True,
                )
                step_results["predict"] = {"predictions": n_preds, "artifact": str(latest_artifact)}
                log.info("pipeline.predict_done", predictions=n_preds)
            else:
                step_results["predict"] = {"predictions": 0, "reason": "no_model_artifact"}
                log.info("pipeline.predict_skipped", reason="no_model_artifact")
        except Exception as exc:
            log.error("pipeline.predict_failed", error=str(exc))
            step_results["predict"] = {"status": "failed", "error": str(exc)}
    else:
        log.info("pipeline.predict_skipped")

    # ── Step 10.5: Attach meta-signal scores (non-fatal) ─
    # Tags today's predictions with combo_key and meta_score from yesterday's
    # signal_combination_scores table. Requires signal_combination_scores to have
    # been populated by at least one prior run of compute_signal_combination_scores.py.
    if _run_daily and not skip_meta_scoring and not skip_predict:
        try:
            import importlib.util as _ilu_meta
            import sys as _sys_meta
            _script_meta = settings.ROOT_DIR / "scripts" / "attach_meta_scores.py"
            if _script_meta.exists():
                _spec_meta = _ilu_meta.spec_from_file_location("attach_meta_scores", _script_meta)
                _mod_meta  = _ilu_meta.module_from_spec(_spec_meta)
                _sys_meta.modules["attach_meta_scores"] = _mod_meta
                _spec_meta.loader.exec_module(_mod_meta)
                import os as _os_meta
                from sqlalchemy import create_engine as _ce_meta
                _engine_meta = _ce_meta(_os_meta.environ["DATABASE_URL"])
                _n_meta = _mod_meta.attach_meta_scores(run_date, _engine_meta)
                step_results["meta_tagging"] = {"predictions_tagged": _n_meta}
                log.info("pipeline.meta_tagging_done", tagged=_n_meta)
            else:
                step_results["meta_tagging"] = {"status": "skipped", "reason": "script_not_found"}
        except Exception as exc:
            log.warning("pipeline.meta_tagging_failed", error=str(exc))
            step_results["meta_tagging"] = {"status": "failed", "error": str(exc)}
    else:
        log.info("pipeline.meta_tagging_skipped")

    # ── Step 11: Prediction outcomes (non-fatal) ──────────
    # Retroactively scores mature predictions and upserts to prediction_outcomes.
    if _run_daily and not skip_outcomes:
        try:
            import sys as _sys
            import importlib.util as _ilu
            _script = settings.ROOT_DIR / "scripts" / "compute_prediction_outcomes.py"
            if _script.exists():
                _spec = _ilu.spec_from_file_location("compute_prediction_outcomes", _script)
                _mod  = _ilu.module_from_spec(_spec)
                _sys.modules["compute_prediction_outcomes"] = _mod
                _spec.loader.exec_module(_mod)
                # Call the core functions directly (avoid re-parsing args)
                from compute_prediction_outcomes import (
                    build_outcomes, upsert_outcomes,
                )
                from run_confluence_backtest import (
                    load_static_stats, build_model_map, compute_forward_returns,
                )
                from run_conviction_backtest import add_conviction
                from run_edge_hierarchy import load_and_score_extended
                import os as _os2
                from sqlalchemy import create_engine as _ce2
                _engine2 = _ce2(_os2.environ["DATABASE_URL"])
                _pstats, _cstats, _rstats = load_static_stats()
                _mmap = build_model_map(settings.MODEL_DIR)
                _scored = load_and_score_extended(
                    run_date - timedelta(days=30), run_date,
                    settings.PARQUET_OUTPUT_DIR, _mmap,
                    _pstats, _cstats, _rstats,
                )
                if not _scored.empty:
                    _scored = compute_forward_returns(_scored)
                    _scored = add_conviction(_scored)
                    _outcomes = build_outcomes(_scored)
                    _n = upsert_outcomes(_outcomes, _engine2) if not _outcomes.empty else 0
                    step_results["prediction_outcomes"] = {"upserted": _n}
                    log.info("pipeline.outcomes_done", rows=_n)
                else:
                    step_results["prediction_outcomes"] = {"upserted": 0}
        except Exception as exc:
            log.error("pipeline.outcomes_failed", error=str(exc))
            step_results["prediction_outcomes"] = {"status": "failed", "error": str(exc)}
    else:
        log.info("pipeline.outcomes_skipped")

    # ── Step 12: Feature reliability (non-fatal) ──────────
    if _run_daily and not skip_reliability:
        try:
            _script_r = settings.ROOT_DIR / "scripts" / "compute_feature_reliability.py"
            if _script_r.exists():
                import importlib.util as _ilu2
                _spec2 = _ilu2.spec_from_file_location("compute_feature_reliability", _script_r)
                _mod2  = _ilu2.module_from_spec(_spec2)
                _spec2.loader.exec_module(_mod2)
                import os as _os3
                from sqlalchemy import create_engine as _ce3
                _engine3 = _ce3(_os3.environ["DATABASE_URL"])
                _rel_df = _mod2.compute_reliability(
                    run_date, settings.PARQUET_OUTPUT_DIR, settings.ALL_FEATURES,
                )
                _n_rel = _mod2.upsert_reliability(_rel_df, _engine3) if not _rel_df.empty else 0
                step_results["feature_reliability"] = {"features": _n_rel}
                log.info("pipeline.reliability_done", features=_n_rel)
        except Exception as exc:
            log.error("pipeline.reliability_failed", error=str(exc))
            step_results["feature_reliability"] = {"status": "failed", "error": str(exc)}
    else:
        log.info("pipeline.reliability_skipped")

    # ── Step 13: Retrain check (non-fatal) ────────────────
    if _run_daily and not skip_retrain_check:
        try:
            _script_rt = settings.ROOT_DIR / "scripts" / "check_retrain_needed.py"
            if _script_rt.exists():
                import importlib.util as _ilu3
                import os as _os4
                from sqlalchemy import create_engine as _ce4
                _spec3 = _ilu3.spec_from_file_location("check_retrain_needed", _script_rt)
                _mod3  = _ilu3.module_from_spec(_spec3)
                _spec3.loader.exec_module(_mod3)
                _engine4 = _ce4(_os4.environ["DATABASE_URL"])
                triggered_results = []
                for _name, _fn, _desc in _mod3.TRIGGERS:
                    try:
                        _fired, _reason = _fn(_engine4)
                    except Exception:
                        _fired, _reason = False, "check_failed"
                    triggered_results.append((_name, _fired, _reason))
                n_fired = sum(1 for _, f, _ in triggered_results if f)
                recommend = n_fired >= _mod3.RETRAIN_SCORE_NEEDED
                step_results["retrain_check"] = {
                    "triggered": n_fired,
                    "recommend_retrain": recommend,
                    "triggers": {n: {"fired": f, "reason": r} for n, f, r in triggered_results},
                }
                log.info("pipeline.retrain_check_done",
                         triggered=n_fired, recommend=recommend)

                if auto_retrain and recommend:
                    log.info("pipeline.auto_retrain_starting")
                    import subprocess as _sp
                    ret = _sp.call(
                        [sys.executable, str(settings.ROOT_DIR / "scripts" / "run_training.py")],
                        cwd=str(settings.ROOT_DIR),
                    )
                    step_results["auto_retrain"] = {"exit_code": ret}
                    log.info("pipeline.auto_retrain_done", exit_code=ret)
        except Exception as exc:
            log.error("pipeline.retrain_check_failed", error=str(exc))
            step_results["retrain_check"] = {"status": "failed", "error": str(exc)}
    else:
        log.info("pipeline.retrain_check_skipped")

    # ── Steps 14–16.5 are skipped in intraday_only mode ─────────────────────────
    if _run_daily:
        # ── Step 14: wide table refresh (non-fatal) ──────────────
        try:
            import os as _os2
            _research_url_wide = _os2.environ.get("DATABASE_URL", "")
            if _research_url_wide:
                from atlas_research.exports.wide_export import refresh_wide
                _n_wide = refresh_wide(run_date, _research_url_wide,
                                       feature_version=settings.FEATURE_VERSION)
                step_results["wide_refresh"] = {"rows": _n_wide}
                log.info("pipeline.wide_refresh_done", rows=_n_wide)
            else:
                step_results["wide_refresh"] = {"rows": 0, "reason": "no DATABASE_URL"}
        except Exception as exc:
            log.error("pipeline.wide_refresh_failed", error=str(exc))
            step_results["wide_refresh"] = {"status": "failed", "error": str(exc)}

        # ── Step 15: calibration (non-fatal) ─────────────────────
        try:
            import os as _os
            alpha_url    = _os.environ.get("DATABASE_URL_ALPHA")
            research_url = _os.environ.get("DATABASE_URL", "")
            if alpha_url and research_url:
                from atlas_research.calibration.engine import sync_snapshots
                n_synced = sync_snapshots(alpha_url, research_url)
                log.info("pipeline.calibration_sync_done", n_synced=n_synced)
            else:
                n_synced = 0
                log.info("pipeline.calibration_sync_skipped",
                         reason="DATABASE_URL_ALPHA not configured")
            from atlas_research.calibration.score_decomp import run_nightly_calibration
            cal = run_nightly_calibration(run_date=run_date, research_url=research_url)
            step_results["calibration"] = {**cal, "n_synced": n_synced}
            log.info("pipeline.calibration_done", **cal)
        except Exception as exc:
            log.error("pipeline.calibration_failed", error=str(exc))
            step_results["calibration"] = {"status": "failed", "error": str(exc)}

        # ── Step 16: attribution pipeline (non-fatal) ────────────
        try:
            from atlas_research.attribution.outcomes import compute_matured_outcomes
            from atlas_research.attribution.classifier import attribute_errors
            from atlas_research.attribution.reliability import compute_signal_reliability
            from atlas_research.attribution.recommendations import generate_recommendations
            attr_outcomes = compute_matured_outcomes(as_of=run_date)
            n_attributed  = attribute_errors()
            compute_signal_reliability(as_of=run_date)
            n_recs = generate_recommendations(as_of=run_date)
            step_results["attribution"] = {
                "outcomes":        attr_outcomes,
                "attributed":      n_attributed,
                "recommendations": n_recs,
            }
            log.info("pipeline.attribution_done",
                     outcomes=attr_outcomes, attributed=n_attributed, recs=n_recs)
        except Exception as exc:
            log.error("pipeline.attribution_failed", error=str(exc))
            step_results["attribution"] = {"status": "failed", "error": str(exc)}

        # ── Step 16.5: Compute signal combination scores (non-fatal) ─
        # Updates rolling 30/60/90d combo scores after attribution has run.
        # These scores are used by Step 10.5 in the NEXT nightly run.
        if not skip_meta_scoring:
            try:
                import importlib.util as _ilu_scs
                import sys as _sys_scs
                _script_scs = settings.ROOT_DIR / "scripts" / "compute_signal_combination_scores.py"
                if _script_scs.exists():
                    _spec_scs = _ilu_scs.spec_from_file_location(
                        "compute_signal_combination_scores", _script_scs
                    )
                    _mod_scs  = _ilu_scs.module_from_spec(_spec_scs)
                    _sys_scs.modules["compute_signal_combination_scores"] = _mod_scs
                    _spec_scs.loader.exec_module(_mod_scs)
                    import os as _os_scs
                    from sqlalchemy import create_engine as _ce_scs
                    _engine_scs = _ce_scs(_os_scs.environ["DATABASE_URL"])
                    _ta_df  = _mod_scs.load_trade_attribution(_engine_scs)
                    _sc_df  = _mod_scs.compute_scores(_ta_df, run_date)
                    _n_scs  = _mod_scs.upsert_scores(_sc_df, _engine_scs)
                    step_results["combo_scoring"] = {"combos_upserted": _n_scs}
                    log.info("pipeline.combo_scoring_done", combos=_n_scs)
                else:
                    step_results["combo_scoring"] = {"status": "skipped", "reason": "script_not_found"}
            except Exception as exc:
                log.warning("pipeline.combo_scoring_failed", error=str(exc))
                step_results["combo_scoring"] = {"status": "failed", "error": str(exc)}
        else:
            log.info("pipeline.combo_scoring_skipped")

    # end if _run_daily

    # ── Step 17: mark complete ────────────────────────────────
    # Fatal errors flip the run to 'failed'; non-fatal warnings (e.g. ingest
    # failures for delisted tickers) keep it 'complete' but remain visible in
    # error_message for the health report.
    all_msgs = errors + warnings
    error_str = "; ".join(all_msgs) if all_msgs else None
    run_status = "failed" if errors else "complete"
    repository.complete_research_run(run_id, error=error_str, status=run_status, **counters)

    # ── Step 18: Intraday 5-min collection (non-fatal) ───────
    # Fetches today's 5-min bars, detects setups, computes outcomes,
    # attaches daily context. Runs after the daily pipeline so daily
    # predictions are available for context attachment.
    # Enabled by default; disable with skip_intraday=True.
    if not skip_intraday:
        try:
            import importlib.util as _ilu_id
            import sys as _sys_id
            import os as _os_id
            from sqlalchemy import create_engine as _ce_id
            _script_id = settings.ROOT_DIR / "scripts" / "ingest_intraday_5m.py"
            if _script_id.exists():
                _spec_id = _ilu_id.spec_from_file_location("ingest_intraday_5m", _script_id)
                _mod_id  = _ilu_id.module_from_spec(_spec_id)
                _sys_id.modules["ingest_intraday_5m"] = _mod_id
                _spec_id.loader.exec_module(_mod_id)
                _engine_id  = _ce_id(_os_id.environ["DATABASE_URL"])
                _vendor_id  = _mod_id.YahooVendor()
                _daily_ctx  = _mod_id.load_daily_context(tickers, _engine_id)
                _id_bars = _id_setups = _id_outcomes = 0
                for _t in tickers:
                    _res = _mod_id.process_ticker(
                        _t, _vendor_id, "5d", _daily_ctx, False, _engine_id
                    )
                    _id_bars     += _res.get("bars", 0)
                    _id_setups   += _res.get("setups", 0)
                    _id_outcomes += _res.get("outcomes", 0)
                step_results["intraday_collection"] = {
                    "bars":     _id_bars,
                    "setups":   _id_setups,
                    "outcomes": _id_outcomes,
                }
                log.info("pipeline.intraday_collection_done",
                         bars=_id_bars, setups=_id_setups, outcomes=_id_outcomes)
            else:
                step_results["intraday_collection"] = {"status": "skipped", "reason": "script_not_found"}
        except Exception as exc:
            log.warning("pipeline.intraday_collection_failed", error=str(exc))
            step_results["intraday_collection"] = {"status": "failed", "error": str(exc)}

        # ── Step 18.5: Update intraday candidate watchlist ────
        try:
            import importlib.util as _ilu_ic
            import sys as _sys_ic
            import os as _os_ic
            from sqlalchemy import create_engine as _ce_ic
            _script_ic = settings.ROOT_DIR / "scripts" / "update_intraday_candidates.py"
            if _script_ic.exists():
                _spec_ic = _ilu_ic.spec_from_file_location("update_intraday_candidates", _script_ic)
                _mod_ic  = _ilu_ic.module_from_spec(_spec_ic)
                _sys_ic.modules["update_intraday_candidates"] = _mod_ic
                _spec_ic.loader.exec_module(_mod_ic)
                _engine_ic = _ce_ic(_os_ic.environ["DATABASE_URL"])
                _ic_result = _mod_ic.run_candidate_update(_engine_ic, run_date)
                step_results["intraday_candidates"] = _ic_result
                log.info("pipeline.intraday_candidates_done", **{
                    k: v for k, v in _ic_result.items() if k != "by_status"
                })
            else:
                step_results["intraday_candidates"] = {"status": "skipped", "reason": "script_not_found"}
        except Exception as exc:
            log.warning("pipeline.intraday_candidates_failed", error=str(exc))
            step_results["intraday_candidates"] = {"status": "failed", "error": str(exc)}
    else:
        log.info("pipeline.intraday_skipped")

    # ── Step 19: Weekly adaptive rule refinement (non-fatal) ─────────────
    # Runs on Mondays (weekday 0) or when run_weekly_refinement=True.
    # Full refinement is expensive; daily ingestion is sufficient nightly.
    import datetime as _dt
    _is_monday = run_date.weekday() == 0
    if not skip_intraday and (run_weekly_refinement or _is_monday):
        try:
            import importlib.util as _ilu_rr
            import sys as _sys_rr
            import os as _os_rr
            from sqlalchemy import create_engine as _ce_rr
            _script_rr = settings.ROOT_DIR / "scripts" / "run_intraday_rule_refinement.py"
            if _script_rr.exists():
                _spec_rr = _ilu_rr.spec_from_file_location("run_intraday_rule_refinement", _script_rr)
                _mod_rr  = _ilu_rr.module_from_spec(_spec_rr)
                _sys_rr.modules["run_intraday_rule_refinement"] = _mod_rr
                _spec_rr.loader.exec_module(_mod_rr)
                _engine_rr = _ce_rr(_os_rr.environ["DATABASE_URL"])
                _rr_df     = _mod_rr.load_full_df(_engine_rr, _mod_rr.ANALYSIS_HORIZON)
                if not _rr_df.empty:
                    _rr_attr = _mod_rr.compute_attribution(_rr_df, run_date)
                    _mod_rr.upsert_attribution(_rr_attr, _engine_rr)
                    _rr_rules: list = []
                    for (_st, _dir), _grp in _rr_df.groupby(["setup_type", "direction"]):
                        _grp = _grp.sort_values("ts").reset_index(drop=True)
                        _sa  = _rr_attr[(_rr_attr["setup_type"] == _st) & (_rr_attr["direction"] == _dir)]
                        _rr_rules.extend(_mod_rr.generate_refinements(_st, _dir, _grp, _sa, run_date))
                    _mod_rr.upsert_refined_rules(_rr_rules, _engine_rr)
                    n_promo = sum(1 for r in _rr_rules if r.get("status") == "promoted")
                    n_cand  = sum(1 for r in _rr_rules if r.get("status") == "candidate")
                    step_results["weekly_refinement"] = {
                        "rules_generated": len(_rr_rules),
                        "promoted": n_promo,
                        "candidates": n_cand,
                    }
                    log.info("pipeline.weekly_refinement_done",
                             rules=len(_rr_rules), promoted=n_promo, candidates=n_cand)
                else:
                    step_results["weekly_refinement"] = {"status": "skipped", "reason": "no_data"}
            else:
                step_results["weekly_refinement"] = {"status": "skipped", "reason": "script_not_found"}
        except Exception as exc:
            log.warning("pipeline.weekly_refinement_failed", error=str(exc))
            step_results["weekly_refinement"] = {"status": "failed", "error": str(exc)}
    else:
        log.info("pipeline.weekly_refinement_skipped",
                 reason="not Monday" if not run_weekly_refinement else "intraday disabled")

    # ── Step 20: Incremental candle memory + similarity latest update ─────────
    # Runs nightly after collection; adds only new bars to intraday_candle_memory
    # and refreshes intraday_similarity_latest for the API.
    if not skip_intraday:
        try:
            import importlib.util as _ilu_cm
            import sys as _sys_cm
            import os as _os_cm
            from sqlalchemy import create_engine as _ce_cm
            _script_cm = settings.ROOT_DIR / "scripts" / "build_intraday_candle_memory.py"
            if _script_cm.exists():
                _spec_cm = _ilu_cm.spec_from_file_location("build_intraday_candle_memory", _script_cm)
                _mod_cm  = _ilu_cm.module_from_spec(_spec_cm)
                _sys_cm.modules["build_intraday_candle_memory"] = _mod_cm
                _spec_cm.loader.exec_module(_mod_cm)
                _engine_cm = _ce_cm(_os_cm.environ["DATABASE_URL"])
                _cm_result = _mod_cm.run_incremental(_engine_cm)
                step_results["candle_memory"] = _cm_result
                log.info("pipeline.candle_memory_done", **_cm_result)
            else:
                step_results["candle_memory"] = {"status": "skipped", "reason": "script_not_found"}
        except Exception as exc:
            log.warning("pipeline.candle_memory_failed", error=str(exc))
            step_results["candle_memory"] = {"status": "failed", "error": str(exc)}

    status = "complete" if not errors else "partial"
    log.info("pipeline.finished", run_id=run_id, status=status, **counters)

    return {
        "run_id":           run_id,
        "status":           status,
        "date":             str(run_date),
        "snapshot_version": snap_ver,
        "steps":            step_results,
        **counters,
    }


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _ingest_start(run_date: date, force_full: bool) -> date:
    if force_full:
        return run_date - timedelta(days=365 * settings.BACKFILL_YEARS)
    latest = repository.get_all_tickers_latest_date()
    if not latest:
        log.info("pipeline.first_run")
        return run_date - timedelta(days=365 * settings.BACKFILL_YEARS)
    return run_date - timedelta(days=30)


def _run_features(
    tickers: list[str],
    run_date: date,
    spy_bars,
    snapshot_version: str,
) -> tuple[int, dict]:
    """
    Validate bars then compute and upsert features.
    Returns (total_eav_rows_written, validation_summary_dict).
    """
    total_rows   = 0
    val_results  = {}

    for ticker in tickers:
        try:
            bars = repository.get_bars(ticker, end=run_date)
            if bars.empty:
                continue

            bars = bars.tail(300).reset_index(drop=True)

            # ── Validate before computing ─────────────────────
            vr = validate_bars(ticker, bars, run_date)
            val_results[ticker] = vr
            if not vr.ok:
                log.warning(
                    "pipeline.validation_failed",
                    ticker=ticker,
                    issues=vr.issues,
                )
                continue   # skip feature computation for bad data

            spy_tail = (
                spy_bars.tail(300).reset_index(drop=True)
                if spy_bars is not None and not spy_bars.empty
                else None
            )

            # ── Compute features ──────────────────────────────
            fv = build_features(ticker, bars, spy_tail)
            if fv is None:
                continue

            # Inject data_quality_score into EAV so it lands in feature_snapshots_wide.
            fv["data_quality_score"] = float(vr.data_quality_score)

            rows = repository.upsert_features(
                ticker, run_date, fv,
                version=settings.FEATURE_VERSION,
                snapshot_version=snapshot_version,
            )
            total_rows += rows

        except Exception as exc:
            log.warning("pipeline.feature_error", ticker=ticker, error=str(exc))

    return total_rows, validation_summary(val_results)
