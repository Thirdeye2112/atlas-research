# Channels + Full-Universe 5m — Build Report

_As of 2026-06-20. Branch `feat/channels-and-5m` (off `data/5m-fullpass`). Descriptive-layer
infrastructure: channel detection (both timeframes) as an additive layer on `pattern_memory`,
plus the ongoing full-universe 5m coverage. No merge/push pending review._

## Design decisions (confirmed)
- **Additive, no schema change.** Channels are new rows: formation
  `pattern_type ∈ {channel_ascending, channel_descending, channel_horizontal}` and breaks
  `pattern_type = channel_break` (with `channel_type`/`break_dir` in the existing `extra` jsonb).
  Existing 2.58M daily + base 5m rows are untouched. `pattern_memory` is not altered.
- **Timeframe tag** = `daily` (matches existing daily rows) and `5m` — queryable alongside patterns.
- **Horizontal channels** tagged distinctly — there is **no existing rectangle/range pattern** in
  `patterns.py` to dedupe against.
- **Idempotent/resumable**: a run skips tickers that already have channel rows for that timeframe.

## Phase 1 — `ta/channels.py` (validated, 0 errors)
Channels fit from swing pivots (reuses `structure.swing_pivots`): support line through recent swing
lows + roughly-parallel resistance through swing highs (≥2 touches each, ≥`min_bars` duration,
width-constancy ≤2× for "parallel"). Classified asc/desc/horizontal by price-normalized slope.

**LOOK-AHEAD GUARD:** the channel is fit on swings with index ≤ the detection bar only. The break is
a separate **forward** event — the first close beyond a boundary after detection, logged at the bar it
occurs, never retroactively.

Validation (10 known tickers, 0 errors): ascending 885 · horizontal 661 · descending 483; breaks
down 975 / up 1,032 / none 0. **End-to-end example** — AAPL ascending channel formed bars 56–92
(2011-08-31 → 2011-10-21), 3/3 touches, width 14.1%, **broke down at bar 106 (2011-11-10)**;
`detect_idx 92 < break_idx 106` confirms the break is forward (no look-ahead).

## Phase 2 — daily channel backfill (`timeframe='daily'`)
Full clean universe via `scripts/build_channel_memory.py --timeframe daily` (additive, idempotent,
per-ticker commit). ~0.3s/ticker (daily series are short) → full run ≈ ~15 min. In progress at write
time (~75K+ channel rows by 18%); final counts land in `reports/validity/channel_backfill_daily.log`.

## Phase 3 — full-universe 5m

### Step 0 — gap diagnosis (read-only, index-only; no full-table DISTINCT)
- Clean universe 3,361 · WITH ≥260 5m bars **3,353** · MISSING 3,353 8 · bar-count distribution
  min 302 / median 53,152 / max 106,422.
- Two independent 5m efforts run concurrently (channels are separate rows):
  1. **Base 5m pattern pass** (candles + chart patterns) — `run_5m_fullpass.py`, PID 21872, resumable,
     ~3–4% at write time, ETA ~30h.
  2. **5m channel backfill** — `build_channel_memory.py --timeframe 5m`, PID 12216, ETA ~13h.

### Calibration note (parameter, not outcome-tuning)
`slope_thr` is a **per-bar** threshold; the daily default (0.0008) on 5m (~78× shorter bars) collapsed
~99% of channels to "horizontal" (smoke: 34 asc / 53 desc / 9,110 horiz). Scaled to **0.0001 for 5m**
restores a meaningful split (AAPL: 830 asc / 690 desc / 1,089 horiz / 2,596 break). Exposed as
`--slope-thr`.

### Smoke timings (0 errors)
- daily: AAPL/MSFT/KO ~1–1.8s/ticker.
- 5m: AAPL/MSFT/KO ~9–16s/ticker; idempotent re-run skips done tickers.

## Current 5m coverage
Base 5m pattern coverage and 5m channel coverage both climbing in the background. Monitor:
`tail reports/validity/channel_backfill_5m.log` and `tail reports/validity/5m_fullpass.log`.
On completion, re-run D (`build_pattern_event_context.py --rebuild`) to attach the "why" layer to the
new rows.

## Note
Descriptive-layer infrastructure. Base model is OOS-degraded (§3) and 5m's tradeable edge is
unconfirmed — channels are a trend-change DESCRIPTOR; whether they predict is a question for the
diagnosis/learning loop, not this task. Coverage + resumability is the goal, not tuning.
