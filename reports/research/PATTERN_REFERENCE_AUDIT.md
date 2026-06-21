# Pattern Reference Audit
**Branch:** `research/pattern-reference`
**Date:** 2026-06-21
**Status:** Step 1 (inventory) + Step 2 (build) complete. Step 3 (reconciliation) complete.

---

## Purpose

Ground-truth taught-behavior reference for every TA tool and pattern the system detects. This is **what textbooks and traders teach** — NOT a claim these patterns work in live trading. Whether they do is the job of the fulfillment backtest (later step).

No rows in `pattern_memory` were altered. The new `pattern_reference` table is standalone.

---

## Step 1 — Inventory

### Existing metadata coverage (pre-this-work)

| Source table | Rows | Covers | Fields present | Verdict |
|---|---|---|---|---|
| `candlestick_concepts` | 19 | 19 candlestick patterns | `plain_english_meaning`, `confirmation_rules`, `invalidation_rules`, `expected_next_behavior` | **PARTIAL** — missing `invalidation_becomes`, `source_note`; name format mismatch (Title Case vs `snake_case`); `category` is structural (single/double/triple), not trading-category |
| `behavior_definitions` | 20 | 20 market behaviors | `description`, `category`, `direction`, `parameter_json` | **PARTIAL** — missing `taught_expectation`, `confirmation_condition`, `invalidation_condition` |
| `market_behavior_concepts` | 20 | same 20 behaviors | `description`, `category`, `direction` | **PARTIAL** — duplicate of above, same gaps |
| `feature_metadata` | 27 | 27 computed features | `feature_name`, `category`, `description` | **PARTIAL** — context description only; no confirmation/invalidation/expectation |
| Chart patterns (double_top, double_bottom, hs_top, hs_bottom, bull_flag, bear_flag) | — | — | — | **ABSENT** |
| Channel patterns (channel_ascending, channel_descending, channel_horizontal, channel_break) | — | — | — | **ABSENT** |
| `swing_leg` | — | — | — | **ABSENT** |
| VWAP (`vwap_5m` table) | — | — | — | **ABSENT** |
| Gaps / FVG (`gaps` table) | — | — | — | **ABSENT** |
| OMNI-82 / OSCAR | — | — | — | **ABSENT** |

### pattern_memory type inventory

All 30 distinct `pattern_type` values in `pattern_memory`, with pre-work metadata verdict:

| pattern_type | Rows | Category | Pre-work verdict |
|---|---|---|---|
| `marubozu` | 31,509,476 | candlestick | PARTIAL (`candlestick_concepts` — incomplete) |
| `tweezer_top` | 7,508,157 | candlestick | PARTIAL |
| `tweezer_bottom` | 7,116,865 | candlestick | PARTIAL |
| `channel_break` | 5,825,978 | channel | ABSENT |
| `double_bottom` | 2,708,436 | chart pattern | ABSENT |
| `double_top` | 2,655,949 | chart pattern | ABSENT |
| `channel_ascending` | 2,261,256 | channel | ABSENT |
| `channel_descending` | 2,213,346 | channel | ABSENT |
| `bearish_engulfing` | 2,162,703 | candlestick | PARTIAL |
| `bullish_engulfing` | 2,155,230 | candlestick | PARTIAL |
| `bearish_harami` | 2,138,546 | candlestick | PARTIAL |
| `bullish_harami` | 2,066,814 | candlestick | PARTIAL |
| `channel_horizontal` | 1,369,571 | channel | ABSENT |
| `hanging_man` | 1,264,793 | candlestick | PARTIAL |
| `shooting_star` | 1,236,366 | candlestick | PARTIAL |
| `hammer` | 1,212,951 | candlestick | PARTIAL |
| `inverted_hammer` | 1,193,738 | candlestick | PARTIAL |
| `evening_star` | 604,116 | candlestick | PARTIAL |
| `morning_star` | 599,453 | candlestick | PARTIAL |
| `spinning_top` | 466,481 | candlestick | PARTIAL |
| `doji` | 415,711 | candlestick | PARTIAL |
| `dark_cloud_cover` | 370,777 | candlestick | PARTIAL |
| `piercing` | 364,235 | candlestick | PARTIAL |
| `swing_leg` | 172,707 | structural | ABSENT |
| `hs_bottom` | 149,597 | chart pattern | ABSENT |
| `hs_top` | 146,613 | chart pattern | ABSENT |
| `three_white_soldiers` | 127,155 | candlestick | PARTIAL |
| `three_black_crows` | 121,840 | candlestick | PARTIAL |
| `bull_flag` | 40,027 | chart pattern | ABSENT |
| `bear_flag` | 34,091 | chart pattern | ABSENT |

**Summary:** 19 PARTIAL (candlestick_concepts had some metadata), 11 ABSENT (chart patterns, channels, swing_leg). Zero PRESENT (no existing table had full taught-behavior with all required fields).

---

## Step 2 — Build: `pattern_reference` Table

### Schema

```sql
CREATE TABLE pattern_reference (
    pattern_type           TEXT PRIMARY KEY,
    category               TEXT NOT NULL CHECK (category IN ('continuation','reversal','bilateral','context')),
    expected_direction     TEXT NOT NULL CHECK (expected_direction IN ('up','down','trend_continuation','bidirectional','n/a')),
    description            TEXT NOT NULL,
    taught_expectation     TEXT NOT NULL,
    confirmation_condition TEXT NOT NULL,
    invalidation_condition TEXT NOT NULL,
    invalidation_becomes   TEXT,       -- NULL when invalidation has no clean flip signal
    source_note            TEXT,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

Migration: `db/migrations/0050_pattern_reference.sql`
Seed: `scripts/seed_pattern_reference.py`

### Coverage summary

| Category | Count | Pattern types |
|---|---|---|
| `reversal` | 18 | hammer, hanging_man, inverted_hammer, shooting_star, bullish/bearish engulfing, bullish/bearish harami, piercing, dark_cloud_cover, tweezer_top/bottom, morning_star, evening_star, double_top/bottom, hs_top/bottom |
| `context` | 14 | vwap, classic_gap_up/down, fvg_bullish/bearish, omni_82, oscar_87, rsi, macd, adx, atr, volume_ratio, sma_stack, swing_leg |
| `bilateral` | 7 | doji, spinning_top, marubozu, channel_ascending, channel_descending, channel_horizontal, channel_break |
| `continuation` | 4 | three_white_soldiers, three_black_crows, bull_flag, bear_flag |
| **Total** | **43** | |

| Expected direction | Count |
|---|---|
| `up` | 13 |
| `down` | 13 |
| `bidirectional` | 10 |
| `n/a` | 7 |

### All 43 rows

#### Candlestick patterns (bilateral / reversal)

| pattern_type | category | direction | Confirmation condition | Has flip? |
|---|---|---|---|---|
| `doji` | bilateral | bidirectional | Next bar closes decisively above high (bull) or below low (bear) | No |
| `spinning_top` | bilateral | bidirectional | Next bar's direction and close | No |
| `marubozu` | bilateral | bidirectional | Next bar holds above (bull) or below (bear) close | Yes — engulfed by opposite bar → trap |
| `hammer` | reversal | up | Next bar closes above hammer's body | No |
| `hanging_man` | reversal | down | Next bar closes below hanging man's body | No |
| `inverted_hammer` | reversal | up | Next bar closes above inverted hammer's high | No |
| `shooting_star` | reversal | down | Next bar closes below shooting star's body | No |
| `bullish_engulfing` | reversal | up | Subsequent close above engulfing bar's close | Yes — failed engulfing → downtrend continues |
| `bearish_engulfing` | reversal | down | Subsequent close below engulfing bar's close | Yes — failed engulfing → trapped shorts, bull continuation |
| `bullish_harami` | reversal | up | Third bar closes above mother bar's body | No |
| `bearish_harami` | reversal | down | Third bar closes below mother bar's body | No |
| `piercing` | reversal | up | Subsequent close above piercing bar's close | No |
| `dark_cloud_cover` | reversal | down | Subsequent close below dark cloud bar's close | No |
| `tweezer_top` | reversal | down | Close below two-bar pattern's low | Yes — break above highs + holds on retest → LONG |
| `tweezer_bottom` | reversal | up | Close above two-bar pattern's high | Yes — break below lows + holds on retest → SHORT |
| `morning_star` | reversal | up | Bar-3 close above bar-1 midpoint (built into detection) | No |
| `evening_star` | reversal | down | Bar-3 close below bar-1 midpoint (built into detection) | No |
| `three_white_soldiers` | continuation | up | Day-4 holds above third bar's close | Yes — immediate reversal bar → climactic exhaustion → SHORT |
| `three_black_crows` | continuation | down | Day-4 holds below third bar's close | Yes — immediate reversal bar → climactic exhaustion → LONG |

#### Chart patterns

| pattern_type | category | direction | Confirmation | Target | Has flip? |
|---|---|---|---|---|---|
| `double_top` | reversal | down | Close below neckline | neckline − pattern height | Yes — break above 2nd peak + holds on retest → LONG continuation |
| `double_bottom` | reversal | up | Close above neckline | neckline + pattern height | Yes — break below 2nd trough + holds from below → SHORT |
| `hs_top` | reversal | down | Close below neckline | neckline − head-to-neckline distance | Yes (rare) — no clean flip; complex re-distribution |
| `hs_bottom` | reversal | up | Close above neckline | neckline + head-to-neckline distance | No |
| `bull_flag` | continuation | up | Close above flag's upper boundary | pole height added from breakout | Yes — close below flag → FAILED BULL FLAG → strong SHORT |
| `bear_flag` | continuation | down | Close below flag's lower boundary | pole height subtracted from breakdown | Yes — close above flag → FAILED BEAR FLAG → strong LONG |

#### Channel patterns

| pattern_type | category | direction | Confirmation | Has flip? |
|---|---|---|---|---|
| `channel_ascending` | bilateral | bidirectional | Bounce off lower line (bull cont.) or close outside either boundary | Yes — breakdown below lower line → potential SHORT |
| `channel_descending` | bilateral | bidirectional | Bounce off upper line (bear cont.) or close above upper line | Yes — close above upper line → LONG |
| `channel_horizontal` | bilateral | bidirectional | Close above resistance (bull) or below support (bear) | Yes — false break reversal → opposite direction trap |
| `channel_break` | bilateral | bidirectional | Close outside channel IS the signal; retest-and-hold is secondary | Yes — false break (back inside channel) → strong opposite signal |
| `swing_leg` | context | n/a | N/A — structural descriptor | No |

#### TA context tools

| pattern_type | category | direction | Key teaching | Has flip? |
|---|---|---|---|---|
| `vwap` | context | n/a | Price above VWAP = bull intraday; reclaim = long setup | No |
| `classic_gap_up` | context | up | Gaps often hold; gap-fill = potential exhaustion | Yes — same-session fill → bearish reversal |
| `classic_gap_down` | context | down | Gaps often hold; gap-fill = potential exhaustion | Yes — same-session fill → bullish reversal |
| `fvg_bullish` | context | up | FVG zone acts as support on pullback | Yes — filled and broken → was support, now resistance → SHORT |
| `fvg_bearish` | context | down | FVG zone acts as resistance on bounce | Yes — filled and broken → was resistance, now support → LONG |
| `omni_82` | context | n/a | EMA(Low, 82); bounce off line = bull entry; cross below = breakdown | Yes — cross below + no reclaim → bearish bias |
| `oscar_87` | context | bidirectional | OSCAR oscillator; cross above 50 = bull; cross below = bear | No |
| `rsi` | context | bidirectional | RSI reclaim (>30 cross) = long trigger; divergence = leading reversal | No |
| `macd` | context | bidirectional | Zero-line cross = trend signal; histogram divergence = reversal warning | No |
| `adx` | context | n/a | ADX >25 = trending; <20 = ranging; direction agnostic | No |
| `atr` | context | n/a | Volatility context; position sizing input; compression → breakout | No |
| `volume_ratio` | context | n/a | Amplifier; vol >1.5× on signal = confirmation; low vol break = weak | No |
| `sma_stack` | context | n/a | SMA 50>150>200 all rising = ideal long-term uptrend regime | Yes — stack inversion → downtrend regime; golden cross → recovery |

---

## Step 3 — Reconciliation

### Detection vs. Reference alignment

**All 30 `pattern_memory` pattern_types are covered in `pattern_reference`.** No gaps.

**13 TA context tools added** that are computed by the system but stored outside `pattern_memory` (in `vwap_5m`, `gaps`, or as columns in `pattern_memory`):
`adx`, `atr`, `classic_gap_down`, `classic_gap_up`, `fvg_bearish`, `fvg_bullish`, `macd`, `omni_82`, `oscar_87`, `rsi`, `sma_stack`, `volume_ratio`, `vwap`

### Bilateral patterns requiring direction field at use-time

These 10 patterns have `expected_direction = 'bidirectional'` in `pattern_reference`. At query time, the `direction` column in `pattern_memory` (long/short) must be consulted to determine the specific directional bias for any individual instance:

- `doji`, `spinning_top`, `marubozu` — candlestick bilateral
- `channel_ascending`, `channel_descending`, `channel_horizontal`, `channel_break` — channel bilateral
- `oscar_87`, `rsi`, `macd` — oscillator context (cross direction determines bias)

### Patterns with meaningful invalidation_becomes (flip signals)

22 of 43 rows have a populated `invalidation_becomes` field — these are the patterns where an invalidation is NOT simply a "signal fails, do nothing" but rather becomes a tradeable signal in the opposite direction:

**High-priority flips** (strongest textbook flip signals):
| Pattern | Invalidation trigger | Becomes |
|---|---|---|
| `double_top` | Close above 2nd peak + retest holds | LONG continuation |
| `double_bottom` | Close below 2nd trough + retest holds | SHORT continuation |
| `bull_flag` | Close below flag lower boundary | Strong SHORT (trapped longs) |
| `bear_flag` | Close above flag upper boundary | Strong LONG (trapped shorts) |
| `tweezer_top` | Break above highs + holds on retest | LONG continuation |
| `tweezer_bottom` | Break below lows + holds on retest | SHORT continuation |
| `channel_break` | False break (back inside channel) | Strong OPPOSITE direction (trap) |
| `fvg_bullish` | FVG zone filled and broken below | Support → resistance; SHORT on retest |
| `fvg_bearish` | FVG zone filled and broken above | Resistance → support; LONG on retest |

**Exhaustion flips** (context-dependent, lower confidence):
- `three_white_soldiers` / `three_black_crows`: extended moves followed by immediate reversal candle = climactic exhaustion
- `marubozu`: immediately engulfed by opposing candle = trap signal
- `bullish_engulfing` / `bearish_engulfing`: failed engulfing = continuation of prior trend (trapped position)

### Gaps vs. candlestick_concepts — reconciliation note

The existing `candlestick_concepts` table (19 rows) has confirmation and invalidation rules in plain English, but uses different field names, a different category taxonomy (single/double/triple structural form), and Title Case names (`"Bullish Engulfing"` not `"bullish_engulfing"`). It has NO `invalidation_becomes` field.

`pattern_reference` is not a replacement for `candlestick_concepts` — that table remains valuable for its `shape_definition` and `psychological_interpretation` fields. The two tables are **complementary**: `candlestick_concepts` has the "how to identify it" layer; `pattern_reference` has the "what to do with it" trading layer.

### Category assignment notes

- **`swing_leg`** assigned `context` because it is a structural measurement primitive, not a trade signal. It records the anatomy of a completed swing for research feature extraction.
- **`marubozu`** assigned `bilateral` (not `continuation`) because the pattern type encompasses both bullish and bearish instances; the specific direction is only known from the `direction` field of the individual `pattern_memory` row.
- **`three_white_soldiers` / `three_black_crows`** assigned `continuation` per classical teaching. However, `invalidation_becomes` records the textbook exhaustion scenario — these patterns empirically show mixed continuation/reversal outcomes (Bulkowski). The fulfillment backtest should specifically test the exhaustion-flip hypothesis.

---

## Honest caveats

1. **This is textbook expectation, not validated behavior.** No empirical claim is made. The taught_expectation fields reflect classical TA literature (Nison, Bulkowski, Edwards & Magee, Murphy, etc.). Whether Atlas patterns show these outcomes in practice is the job of the fulfillment backtest.

2. **Context dependencies are encoded in description text only.** Many patterns require a prior trend context (hammer → downtrend; hanging_man → uptrend) that is already baked into detection logic but cannot be fully encoded in a single `expected_direction` field. The `description` field documents this.

3. **Bilateral patterns need the `direction` field.** 10 patterns cannot be interpreted from `pattern_reference.expected_direction` alone — the `pattern_memory.direction` column (long/short) is required.

4. **`invalidation_becomes` is NOT a trading rule.** It describes a higher-level decision tree path if the primary pattern fails. Backtesting the flip conditions is a separate research task.

5. **Market behaviors in `behavior_definitions`/`market_behavior_concepts`** (ABOVE_ALL_EMAS, GOLDEN_CROSS, RSI_OVERBOUGHT, etc.) are partially covered here via the TA context tool rows. A future pass could add the 20 behavior IDs as explicit `pattern_reference` rows to create a single lookup for ALL system-computed states.

---

## Files changed

| File | Type | Description |
|---|---|---|
| `db/migrations/0050_pattern_reference.sql` | new | DDL: creates `pattern_reference` table |
| `scripts/seed_pattern_reference.py` | new | Seeds all 43 rows (re-runnable UPSERT) |
| `reports/research/PATTERN_REFERENCE_AUDIT.md` | new | This report |
