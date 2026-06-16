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
    10. Mark run complete

Each step is isolated — failure in one step does not abort later steps.
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
    triggered_by: str = "scheduler",
    snapshot_version: str | None = None,
) -> dict:
    """
    Run the full nightly pipeline.

    Args:
        run_date:          Date to process. Defaults to today.
        force_full_ingest: Re-download full BACKFILL_YEARS of history.
        skip_*:            Skip individual steps for re-runs / debugging.
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
    errors: list[str] = []
    step_results: dict = {}
    _quality_scores: dict[str, float] = {}
    _quality_flags:  dict[str, str]   = {}

    try:
        # ── Step 2: load universe ─────────────────────────────
        tickers = repository.get_active_tickers()
        if not tickers:
            raise RuntimeError(
                "No active tickers in securities table. Run scripts/init_db.py first."
            )
        log.info("pipeline.universe", count=len(tickers))

        # ── Steps 3 & 4: ingest ───────────────────────────────
        if not skip_ingest:
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
            step_results["ingest"] = {"bars": bars_ok, "failed": len(failed)}
            if failed:
                errors.append(f"ingest_failures: {[t for t, _ in failed[:5]]}")
            log.info("pipeline.ingest_done", bars=bars_ok, failed=len(failed))
        else:
            counters["tickers_processed"] = len(tickers)
            log.info("pipeline.ingest_skipped")

        # ── Step 5: validate + step 6: features ───────────────
        if not skip_features:
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
        else:
            log.info("pipeline.features_skipped")
            _quality_scores, _quality_flags = {}, {}

        # ── Step 7: labels ────────────────────────────────────
        if not skip_labels:
            labels_n = build_labels_for_universe(tickers, as_of=run_date)
            counters["labels_generated"] = labels_n
            step_results["labels"] = {"rows": labels_n}
            log.info("pipeline.labels_done", rows=labels_n)
        else:
            log.info("pipeline.labels_skipped")

        # ── Step 8: parquet export ────────────────────────────
        if not skip_parquet:
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
        if not skip_json_export:
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

    # ── Step 10: wide table refresh (non-fatal) ──────────────
    # Pivots EAV feature_snapshots → feature_snapshots_wide for today.
    # Failure must not stop ingestion.
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
        # Intentionally not appended to errors — wide refresh failure is non-fatal

    # ── Step 11: calibration (non-fatal) ─────────────────────
    # Syncs alpha signal snapshots then runs score component decomposition.
    # Requires DATABASE_URL_ALPHA env var for the sync phase.
    # Failure here must never stop ingestion — all errors are logged only.
    try:
        import os as _os
        alpha_url = _os.environ.get("DATABASE_URL_ALPHA")
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
        # Intentionally not appended to errors — calibration failure is non-fatal

    # ── Step 12: attribution pipeline (non-fatal) ────────────
    # Runs after labels are computed so matured outcomes are available.
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

    # ── Step 13: mark complete ────────────────────────────────
    error_str = "; ".join(errors) if errors else None
    repository.complete_research_run(run_id, error=error_str, **counters)

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
