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
