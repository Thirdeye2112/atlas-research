# 5-Minute Pattern Coverage — Full-Universe Pass

_As of 2026-06-20. Coverage/throughput task: extend the 5m candlestick + chart-pattern
pass (`build_candle_memory.py` 5m path, reused verbatim) toward the full clean universe.
Resumable; driven by `scripts/run_5m_fullpass.py`. Branch `data/5m-fullpass`._

## Step 0 — gap diagnosis (read-only, index-only count; no full-table DISTINCT)

| | count |
|---|---:|
| Clean universe (`config/clean_universe.csv`) | 3,361 |
| WITH ≥260 5m bars in `intraday_bars` | 3,353 |
| MISSING 5m data (<260 bars) | 8 |
| Already patterned at 5m (skip-set, pre-run) | 102 |
| **Worklist (have bars, not yet patterned)** | **3,251** |

5m bar-count distribution (tickers with data): min 302 · p25 22,793 · median 53,152 ·
p75 83,410 · max 106,422.

## Worklist & ETA
- Initial worklist: 3,251 tickers. Honest ETA at the smoke-observed ~50s/ticker avg:
  **~45–48 hours (~2 days)**. (The 74s figure was the largest ticker; median is ~half.)
- Multi-day, resumable: stop/restart freely — on restart the runner re-queries
  `pattern_memory(5m)` and skips completed tickers.

## Step 2 — smoke test (2 × `--limit 5`, 0 errors)
| ticker | instances | seconds |
|---|---:|---:|
| AIZ | 24,690 | 38.0 |
| AJG | 56,561 | 80.6 |
| AKAM | 62,888 | 93.6 |
| AKAN | 2,003 | 2.7 |
| AKR | 37,151 | 51.6 |

Per-ticker commit verified; re-running `--limit 5` skipped AIZ–AKR and processed the next
five (AKTX/ALAB/ALB/ALC/ALCO) — **idempotent / resumable**. No O(n²) hotspot (bisect S/R,
`sr_window=40`); per-ticker watchdog skips any ticker > 600s.

## Runner design (`scripts/run_5m_fullpass.py`)
- Worklist = `clean_universe.csv` minus a `pattern_memory(5m)` skip-set (never a full-table DISTINCT).
- One ticker per **committed** transaction (`_flush` commits each); crash at N keeps 1..N-1.
- Reuses `build_candle_memory.py` (import, no edits): same detection, enrichment, denoise.
- Logs per-ticker `(ticker, instances, seconds)` + running `N/M, %, ETA` to
  `reports/validity/5m_fullpass.log` (gitignored — large).
- `--limit N` (smoke) / `--resume` (default) / `--timeout` (per-ticker watchdog).

## Current coverage
- Pre-full-run: **112 / 3,353** tickers-with-bars patterned at 5m (~3.3%).
- Full run launched 2026-06-20 (PID 21872, detached via `Start-Process`); on completion
  coverage → ~3,353 / 3,353 (the 8 no-data tickers cannot be covered).
- Monitor: `tail reports/validity/5m_fullpass.log`. Re-run D
  (`build_pattern_event_context.py --rebuild`) afterward to refresh the causal layer.

## Note
The 5m intraday layer's tradeable edge is unconfirmed (prior iters: "marginally positive,
not deployable") and the base model is OOS-degraded (§3). This is coverage completion for
the knowledge base, not a deployable signal.
