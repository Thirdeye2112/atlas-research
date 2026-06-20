# Atlas-Research — System Assessment & Running Scope

_As of 2026-06-19. A single-page snapshot of what is built, what it rests on, and the one
question that decides whether any of it trades._

---

## 1. What is built (the evidence & context engine)

| Layer | Artifact | State |
|---|---|---|
| Clean universe | `config/clean_universe.csv` | 3,361 real tickers (gated) |
| Daily bars / features | `raw_bars`, feature snapshots | full history |
| Intraday 5m bars | `intraday_bars` (Alpaca IEX) | ~210M rows, 5,561 tickers |
| Chart patterns + swing legs | `pattern_memory` (daily) | enriched, committed `8aacd83` |
| **19 candlestick patterns** | `ta/candlesticks.py` → `pattern_memory` | daily **2,577,719** instances, 0 err (`9ac8ef8`) |
| **5-min pattern pass** | `build_candle_memory.py` (`timeframe='5m'`) | **102 tickers / 3,664,303** instances (partial, resumable, `cdbe4c0`) |
| **External data** | `corporate_actions` 52,125 · `news_events` 1,624,214 | real, 2012→2026 (`4025484`/`8c0380d`, branch `data/alpaca-ingest`) |
| **Causal "why" layer** | `pattern_event_context` | **6,789,899** look-ahead-safe links (`d40ec8e`, migrations `0045`/`0046`) |

### Causal layer — coverage (frozen 5m set, provisional)
| timeframe | instances | ≥1 corp action | ≥1 PRIOR news (`before`) | any news |
|---|---:|---:|---:|---:|
| daily | 2,906,433 | 4.92% | 19.53% | 24.59% |
| 5m | 3,664,303 | 5.31% | 33.21% | 43.46% |

**Look-ahead discipline:** an event is a valid cause only if `event_time ≤ decision_bar`
(daily = 16:00 ET close, DST-aware; 5m = 09:30 ET open). 5m stores only the DATE, so same-session
news is tagged `same_day_unverified`, never `before`. Daily is cleanly before/after — invariant
verified (daily `same_day_unverified` = 0). **Predictive uses MUST filter to `relation='before'`.**

---

## 2. What it rests on — THE open question (highest leverage)

The whole apparatus above enriches one base signal (V1, 38 features). That signal's status:

| Metric | Walk-forward (in-sample) | Embargoed OOS (2025-06-15 → 2026-06-14) |
|---|---|---|
| Per-day rank IC | **+0.0131** | **−0.0052** |
| IC t-stat | **+4.72** (Bonferroni p=7.5e-6) | **−2.20** (single trial, p≈0.03) |
| Regressor trees | (full folds) | **1** (early-stopped) |

**Verdict on record: KEEP V1 BUT MARK DEGRADED.** The walk-forward edge did **not** generalize to
the one year nothing was tuned against; OOS IC sits at the noise floor with mixed sign. No amount of
"why" makes a non-generalizing signal generalize.

**→ The next real research is the diagnosis, not more enrichment:** branch `research/oos-diagnosis`,
four angles — (1) sub-period IC stability (is +0.0131 steady or episodic?), (2) regime breakdown of
the OOS year (hostile regime vs uniform decay?), (3) a second embargoed slice (unlucky year vs
confirmed failure?), (4) the single-tree collapse (no signal vs input distribution shift?).

---

## 3. Known gaps (stated, not solved)
- **No earnings-surprise magnitude.** Alpaca news gives "an event occurred", not "beat by X%".
  A fundamentals/earnings-calendar feed would deepen the causal layer.
- **5m intraday timestamp not stored** in `pattern_memory` (DATE only) → same-session 5m news is
  `same_day_unverified`. Storing the bar `ts` would allow exact intraday before/after.
- **5m pattern pass is partial** (102 tickers). Resumable via `build_candle_memory.py --timeframe 5m
  --resume`; refresh the causal layer afterward with `build_pattern_event_context.py --rebuild`.
- **Tweezer / marubozu noise on 5m** — denoised (tighter tolerance, doji/spinning_top dropped) but
  still high-frequency; treat 5m single-bar patterns with care.

---

## 4. Branch / backup state
- `fix/model-validity` — model-validity fixes + C (candlesticks/5m) + D (causal layer). Pushed.
- `data/alpaca-ingest` — B (external data). Pushed. Neither merged to `main` pending review.
