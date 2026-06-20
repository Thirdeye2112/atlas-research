# Atlas Research — Development Log

Chronological record of what was built each session. Updated at end of every session before commit.

---

## 2026-06-11 — OMNI Backfill + UI Rework + Retrain

### atlas-alpha
- **UI rework:** Replaced stacked ML/Context/Sector badges with `SignalContextTabs` — 3-tab panel (ML / CONTEXT / SECTOR)
- **Intelligent default:** Auto-selects active tab based on live API data: SPY bear streak ≥4d → CONTEXT; non-neutral sector regime → SECTOR; else ML
- **Nav cleanup:** "Lab" → "Research", "Bot Lab" → "Bot"; visual separator between operational/analytical nav groups
- **Research page:** Eliminated double-header conflict with AppLayout; sticky header uses app card color
- **BotLab tabs:** Separator between operational (Config/Positions/History) and analytical (AI Brain/Learning/Sim Lab) tabs
- **Commits:** `dd227a0` feat: streamlined UI — tabbed ML/Context/Sector panel, nav cleanup, Research header

### atlas-research
- **OMNI backfill:** Completed — 192/192 tickers have `omni_82_above` in `feature_snapshots`
- **Full retrain (v1.5):** 12 walk-forward folds, mean AUC 0.5239, **mean rank IC 0.0546** (doubled from 0.0269)
- **Feature importance:** `omni_82_above` = #2 regressor, #3 classifier — OMNI confirmed top feature
- **Scripts added:** `feature_importance.py`, `scripts/rank_dist.py`, `top10_omni.py`
- **Unicode fixes:** Replaced box-drawing chars in `run_training.py`, `test_system.py`, `run_conditional.py`
- **Commits:** `60b8251`, `a5bd703`

---

## 2026-06-12 — Model Quality Update + Health Endpoint

### atlas-alpha
- **MLSignalBadge:** Updated edge label tiers — Early stage (<0.02) / Developing (<0.04) / **Moderate edge** (<0.06) / Strong edge (≥0.06). Badge now shows "Moderate edge" at IC=0.0546
- **`/api/health`:** Added route (was 404, now `{"status":"ok","ts":"..."}`) — test_system.py now 15/15 checks pass
- **Commits:** `cb03f76`

### atlas-research
- **CONSENSUS.md:** Added ML Model Quality section: v1.4→v1.5 comparison table, feature importance rankings, edge tier thresholds
- **Commits:** `a5bd703`

---

## 2026-06-12 — Price Targets + IPO Engine + Oscar Scraper

### atlas-alpha
- **`GET /api/targets/:ticker`:** ATR14-based price targets. Returns stop (0.75×ATR), T1 (1.5×), T2 (3×), T3 (5×), Fibonacci 2.618× extension, 20d swing high/low
- **`SignalTargets.tsx`:** Compact target table in Dashboard right panel — color coded stop/T1/T2/T3, shows R/R ratio per level
- **Dashboard.tsx:** `SignalTargets` inserted below `SignalContextTabs`

### atlas-research
- **Migration 0020:** `ipo_registry` + `ipo_backtest_results` tables
- **Migration 0021:** `oscar_scrape_log` table
- **`scripts/build_ipo_registry.py`:** Infers IPO dates from `raw_bars` first-appearance (2015+)
- **`scripts/run_ipo_backtest.py`:** Returns at 1/5/10/20/30/60/90/120/180/252d vs SPY benchmark; reports best entry window and lockup effect
- **`scripts/watch_oscar.py`:** YouTube channel monitor — uses `yt-dlp` + `youtube-transcript-api`, stores in `oscar_scrape_log`

### Existing scrapers found
- `scripts/ingest_transcripts.py` — reads local `.txt` file of Oscar transcripts, calls Claude API to extract hypotheses, stores in `transcript_chunks`
- `scripts/run_transcript_pipeline.py` — full nightly pipeline: extract → backtest hypotheses → promote validated ones

---

## 2026-06-12 — Jarvis Rename + IntelPanel 3-Tabs + Scanner Filters

### atlas-alpha
- **Jarvis rename (UI only):** All display text "OMNI" → "Jarvis"; backend features remain `omni_82_*` internally
- **`/api/research/signal/:ticker`:** Added `jarvis_green`, `jarvis_distance_pct`, `jarvis_slope` aliases alongside existing `omni_*` fields
- **`/api/research/signals` batch:** Added `jarvis_green` via `DISTINCT ON (ticker)` query on `feature_snapshots`
- **`IntelPanel.tsx`:** New 3-tab component replacing `SignalContextTabs` + `SignalTargets`:
  - **SCORE tab** (default): Sector regime line + signal narrative
  - **INTEL tab**: Jarvis dot + distance%, ML Rank + edge label, P(+5d) bar, SPY streak, sector, model WF IC note; shows green 🟢 dot in tab label when Jarvis is green
  - **TARGETS tab**: Stop/T1/T2/T3 price targets (SignalTargets component)
- **`Dashboard.tsx`:** `<IntelPanel ticker={urlTicker} analysis={displayAnalysis} />` replaces stacked components; ticker change resets to SCORE tab
- **`Scanner.tsx`:** Jarvis filter preset buttons above results: [All] [🟢 Long Ideas] [🔴 Short Ideas] [⭐ Jarvis + ML] with live count badges; filters on jarvis_green + ml_rank_percentile + ml_direction
- **AAPL price targets confirmed:** Stop $288.08, T1 $303.97 (2:1), T2 $314.56 (4:1), T3 $328.69 (6:1), Fib $364.77
- **Commits:** `e479b3d`

### atlas-research
- **`CONSENSUS.md`:** Updated "OMNI Indicator" section header → "Jarvis Indicator"; v1.5 table updated
- **Commits:** `f925906`

---

## 2026-06-19 — Model Validity Fixes (correctness pass, no tuning)

### atlas-research
- **Audit:** Fix 1 (Platt calibration leak), Fix 2 (calendar-day purge), and
  Fix 3 (no OOS embargo) were all **already fixed** in `train.py`/
  `dataset.py`/`walk_forward.py` before this session — verified via `git log`
  to ancestor commit `63a105e`. Fix 4 (`ingest_alpaca_corpactions_news.py`)
  didn't exist in the repo at session start; appeared mid-session as
  untracked, concurrent work with the fix already applied — left untouched.
- **Hardened Fix 1:** Added `tests/test_train.py` (real-LightGBM, asserts
  Platt is fit on the ES holdout, never the val fold) and fixed a stale
  module docstring still describing the old leaky behavior.
- **Hardened Fix 3:** Added an explicit `[OOS] Reserved hold-out...` console
  print to `run_training.py` (previously only in structlog debug output) and
  `scripts/score_oos.py` — a driver that scores the embargoed OOS block
  exactly once via `walk_forward.run_fold()`.
- **Re-ran clean V1 walk-forward:** 11 folds (OOS-embargoed), mean rank IC
  **0.0712**, mean AUC 0.5248 — vs `CONSENSUS.md`'s stale 12-fold/no-embargo
  baseline of 0.0599; difference fully explained by the 12th (now-embargoed)
  fold + a 39→38 feature count decision that predates this session, not a
  regression.
- **Re-ran the single OOS score:** rank IC -0.0061, mean IC -0.0052 — matches
  the prior session's independently-computed -0.0052 almost exactly.
  Reconfirms (does not revisit) "KEEP V1 BUT MARK DEGRADED."
- **Re-ran confluence + conviction backtests:** found the comparison is
  confounded — `build_model_map`'s tie-break shadows 11/11 of this session's
  retrained fold artifacts behind same-dated `_clean_` artifacts from
  concurrent clean-universe work; only the new OOS artifact (10/2,880 signal
  dates) is actually this session's. The observed HR/significance drop
  (VERY_HIGH 55.6%→54.2%, 5+ aligned 58.1%→54.4%, both permutation tests
  flipping from p<0.05 to non-significant) is dominated by a +67% change in
  scored population and a probability-tier activation between report
  snapshots — not isolable as a calibration effect.
- **Full report:** `reports/validity/MODEL_VALIDITY_FIXES_REPORT.md`.
- **Commits:** `3f07b1c`, `4a8fdd5`, plus this entry's commit.

---

## 2026-06-18 — Intraday 5-minute engine: bulk Alpaca history

- `AlpacaVendor` multi-year IEX 5m ingest; COPY bulk-load + concurrent download workers;
  `--all/--resume/--bars-only/--min-dvol`.
- **Commits:** `2c9bffd`, `0618a0a`, `10561d3`.

---

## 2026-06-19 — Candlesticks, 5m pattern pass, external data, causal-context layer

Large build day. Four layers landed — **B** on branch `data/alpaca-ingest`, **C** + **D** on
`fix/model-validity`. Both branches pushed to origin; neither merged.

**B — Alpaca external data** (`4025484`, report `8c0380d`; migration `0044`)
- New `scripts/ingest_alpaca_corpactions_news.py`: `corporate_actions` (52,125 rows, all CA types,
  merger cash zero-bug fixed via `rate if rate is not None else cash_rate`) and `news_events`
  (1,624,214 rows / 3,343 tickers, fan-out per (article,symbol), HTML not stored). Real data,
  earliest news 2012-04-17 → 2026-06-19.

**C — 19 candlesticks + 5-min pattern pass** (`9ac8ef8`, perf fix `cdbe4c0`)
- New `src/atlas_research/ta/candlesticks.py`: the 19 named patterns, trend-disambiguated
  (hammer vs hanging_man, inverted_hammer vs shooting_star).
- New `scripts/build_candle_memory.py`: logs into the SAME `pattern_memory` table with the SAME
  enrichment as the chart patterns. Daily (`timeframe='daily'`): **2,577,719** candlestick
  instances, 0 errors. 5m (`timeframe='5m'`): chart patterns + candlesticks, daily-context joined,
  denoised. Perf fix (bounded `sr_window` S/R + CSV ticker sourcing) turned a 2h+ stall into
  ~74s/ticker; stopped at **102 tickers / 3,664,303 instances** (resumable via `--resume`).

**D — `pattern_event_context`: the look-ahead-safe "why" layer** (`d40ec8e`; migrations `0045`+`0046`)
- New table links each pattern instance to corporate actions ([-3,+1] NYSE trading days, offsets
  via SPY session dates) and news ([-2,+1] days, joined on TIMESTAMP). **Look-ahead guard:** an
  event is a valid cause (`relation='before'`) only if `event_time <= decision_bar` — daily = 16:00 ET
  close (DST-aware), 5m = 09:30 ET open. Because `pattern_memory` stores only the DATE for 5m,
  same-session 5m news is tagged `same_day_unverified` (never `before`); daily is cleanly
  before/after (invariant verified: **daily `same_day_unverified` = 0**). Predictive uses MUST
  filter to `relation='before'`.
- Coverage (frozen 5m set): **6,789,899** links. daily 2.91M instances (4.92% with a corp action,
  19.53% with prior news); 5m 3.66M (5.31% CA, 33.21% prior news). Report:
  `reports/validity/PATTERN_EVENT_CONTEXT.md`. Known gap: Alpaca news has no earnings-surprise
  magnitude — the "why" is "event existed", not "beat by X%".

**Highest-leverage open question — §3 generalization gap.** V1 walk-forward IC = +0.0131 (t=+4.72,
Bonferroni p=7.5e-6) did **not** generalize: the embargoed OOS year (2025-06-15 → 2026-06-14) gave
rank IC = **−0.0052 (t=−2.20)** and the regressor collapsed to **1 tree**. Verdict: **KEEP V1 BUT
MARK DEGRADED**. All of B/C/D is context for a base signal whose out-of-sample edge is unconfirmed.
Next session: branch `research/oos-diagnosis` — sub-period IC stability, OOS-year regime breakdown,
a second embargoed slice, and the single-tree collapse.
- **Commits:** `9ac8ef8`, `cdbe4c0`, `d40ec8e`, `4025484`, `8c0380d`, plus this entry's commit.

---

## Reference

### Key Metrics (as of 2026-06-12)
| Metric | Value |
|--------|-------|
| WF Mean IC | 0.0546 (Moderate edge) |
| WF Folds | 12 |
| Mean AUC | 0.5239 |
| Universe | 192 tickers |
| Conditional patterns | 95+ |
| OMNI backfill | 100% (192/192) |
| Top feature | omni_82_above (#2 regressor, #3 classifier) |

### Repos
- `atlas-alpha`: Thirdeye2112/atlas-alpha — Node/Express API + React frontend
- `atlas-research`: Thirdeye2112/atlas-research — Python ML pipeline
