# compute_features() VWAP Bug: Fix + Sibling-Bug Audit

**Foundation repair, not a new research signal.** Numbers first, verdict second throughout. This report
fixes a real bug found by `research/foundation-retest` (commit `45c392f`), and audits every other
cross/event-style feature in `compute_features()` for the same failure family.

## Step 1. Reproducing the bug (before the fix)

**Location:** `src/atlas_research/intraday/features.py`, lines 104-107 (pre-fix):

```python
df["above_vwap"]    = df["close"] > df["vwap"]
df["above_vwap_prev"] = df["above_vwap"].shift(1).fillna(False)
df["vwap_cross_up"]   = df["above_vwap"] & ~df["above_vwap_prev"]
df["vwap_cross_down"] = ~df["above_vwap"] & df["above_vwap_prev"]
```

**Root cause:** `above_vwap` is genuine `bool` dtype. `.shift(1)` cannot represent the leading `NaN` in a
bool array, so pandas upcasts `above_vwap_prev` to `object` dtype (holding real Python `True`/`False`
objects). Python's unary `~` on a `bool` does **bitwise-int** negation, not logical negation: `~True == -2`,
`~False == -1` -- **both nonzero, both truthy.** So `df["above_vwap"] & ~df["above_vwap_prev"]` collapses to
`df["above_vwap"] & (always-truthy)`, i.e. just `df["above_vwap"]` itself. (Python 3.14 itself emits a
`DeprecationWarning` for this exact pattern: *"Bitwise inversion '~' on bool is deprecated... usually not
what you expect from negating a bool."*)

**Reproduced on AAPL 5m** (the same ticker `research/foundation-retest` used), via the binary-crossing
identity (any genuine alternating on/off series must have equal, +-1, up- and down-transition counts):

| | stored (pre-fix) | manual independent recount |
|---|---|---|
| `vwap_cross_up` | **34,954** | 3,121 |
| `vwap_cross_down` | 3,121 | 3,121 |

`vwap_cross_up` (pre-fix) sum (34,954) equals `above_vwap.sum()` (34,954) exactly -- direct confirmation of
the collapse. `vwap_cross_down` was unaffected: its `~` applies to `above_vwap` directly (never shifted),
not to the upcast `above_vwap_prev`.

## Step 2. The fix

**Change:** `shift(1).fillna(False)` -> `shift(1, fill_value=False)`, everywhere this pattern occurs.
`fill_value` tells pandas the fill value up front, so it never needs to introduce a `NaN` and never upcasts
the dtype -- the column stays genuine `bool` through the whole expression, and `~` does correct logical
negation.

**After the fix, same ticker, same identity check:**

| | before | after | manual recount |
|---|---|---|---|
| `vwap_cross_up` | 34,954 | **3,121** | 3,121 |
| `vwap_cross_down` | 3,121 | 3,121 | 3,121 |
| `vwap_cross_up == above_vwap`? | True (the bug signature) | **False** | -- |
| dtype | `bool` (column), `object` (the shift) | `bool` throughout | -- |

Balanced, matches the manual recount exactly, and `vwap_cross_up` is now demonstrably different from
`above_vwap` (the regression signature is gone).

**Regression test added:** `tests/test_intraday_features.py` (7 tests, pure synthetic data, no DB/file I/O).
Verified to **fail against the pre-fix code** (4 of 7 tests fail, including the exact balance and
non-collapse assertions) and **pass against the post-fix code** -- confirmed by temporarily reverting the
fix (`git stash`) and re-running, then restoring it. Full existing suite (`tests/`, 164 tests total) also
passes with the fix applied -- no other regression introduced.

## Step 3. Sibling-bug audit (every cross/event feature in compute_features())

Grepped the entire file for every `~` usage (4 total) and every `.shift()` call (24 total), classifying
each by the exact mechanism: does it apply `~` (or any negation) to a column that passed through
`.shift()` on a bool-dtype Series? That combination is the only way to trigger this bug; everything else
either shifts a float column (safe -- comparisons produce fresh bools) or never negates a shifted bool
column (safe -- `&` between bool and object-dtype-of-real-booleans coerces correctly via truthiness).

| Feature | Mechanism | Status | Evidence |
|---|---|---|---|
| `vwap_cross_up` | `~` on shifted bool | **BROKEN -> FIXED** | 34,954 -> 3,121, now balanced with cross_down |
| `vwap_cross_down` | `~` on non-shifted bool | OK | always 3,121, matched manual recount before and after |
| `orb_bull_signal` | `~` on shifted bool (`_above_or_prev`) | **BROKEN -> FIXED** | was 16,648 = `above_or_high & ~in_or` exactly (collapsed); now 1,292 |
| `orb_bear_signal` | `~` on shifted bool (`_below_or_prev`) | **BROKEN -> FIXED** | was 14,485 = `below_or_low & ~in_or` exactly (collapsed); now 1,212 |
| `macd_bull_cross` / `macd_bear_cross` | `.shift(1)` on FLOAT columns (`macd`, `macd_signal_line`), then comparison -- no bool-shift, no `~` on a shifted bool | OK | 2,558 vs 2,557 (balanced, matches manual recount) |
| `rsi_reclaim_bull` / `rsi_reclaim_bear` | `.shift(1)` on FLOAT `rsi14`, asymmetric threshold comparison (not a pure crossing identity, but no `~`/bool-shift risk) | OK | rates plausible (1,980 / 2,037 on AAPL 5m); mechanism inspected, no negation-of-shifted-bool anywhere |
| `bullish_engulf` / `bearish_engulf` | `.shift(1).fillna(False)` on bool `is_red`/`is_green`, used in `&` only, never negated | OK | manual recount matched exactly (3,789) |
| `consec_green` / `consec_red` | `.shift(1)`/`.shift(2)` on bool, ANDed only, never negated | OK | manual recount matched exactly (8,218) |
| `higher_high` / `lower_low` / `higher_low` / `lower_high` | `.shift(1)`/`.shift(2)` on FLOAT `high`/`low`, comparisons only | OK | manual recount matched exactly (17,848) |
| `hammer` / `shooting_star` / `inside_bar` | No `.shift()` of a boolean at all (single-bar geometry or float-only shifts) | OK (not in this bug family) | inspected, no risk pattern present |
| `hh_count` / `ll_count` | `.rolling(3).sum()` of already-verified-OK `higher_high`/`lower_low` | OK | derived from clean inputs |

**Dtype audit:** every boolean-INTENDED column in the post-fix output (32 columns checked: all `is_*`,
`above_*`, `below_*`, `*_cross_*`, `*_signal`, `*_reclaim_*`, `*_cross`, candle-shape, and trend-structure
columns) is confirmed genuine `bool` dtype -- no other silent object/float-coercion found.

**Missing-shift audit:** no cross/event feature was found comparing a bar to itself (i.e. missing a
`shift(1)` where one is structurally required) -- every "cross" correctly compares current-bar state to
prior-bar state.

**Verdict for Step 3: 3 of ~15 audited cross/event features were broken (vwap_cross_up, orb_bull_signal,
orb_bear_signal), all from the identical mechanism, all now fixed. No other instance of this bug family
exists in `compute_features()`.**

## Step 4. Impact map (blast radius -- not re-run here)

### Production pipeline (found during this audit, not mentioned in the original report)

`src/atlas_research/intraday/setups.py::detect_all_setups()` -- a 28-detector registry -- consumes
`orb_bull_signal`, `orb_bear_signal`, and `vwap_cross_up` directly in 3 of its 28 detectors (`_orb_bull`,
`_orb_bear`, `_vwap_reclaim_bull`). This is called from `scripts/ingest_intraday_5m.py`, which writes to the
live `intraday_setups` and `intraday_outcomes` tables.

**Quantified, read-only, as of this audit:**

| Table | Affected rows | Total rows | Share |
|---|---|---|---|
| `intraday_setups` (`vwap_reclaim_bull` + `orb_bull` + `orb_bear`) | 2,334 + 1,074 + 686 = **4,094** | 49,261 | 8.3% |
| `intraday_outcomes` (joined to the above setup_ids) | **20,470** | 246,305 | 8.3% |

`vwap_reject_bear` (149 rows, uses the unaffected `vwap_cross_down`) and all other 24 setup types in the
registry are NOT affected. These setups were likely over-detected (the broken signal persists as "true" for
every bar a state holds, not just the crossing bar), meaning a meaningful fraction of the 4,094 rows are
probably repeat/stale re-detections of the same breakout or reclaim moment rather than distinct events --
not re-computed or deleted here, per the brief's instruction to map, not re-run.

### Research branches

| Branch | What it consumed | Effect |
|---|---|---|
| `research/setup-formation-v2` (`b0623f1`) | `vwap_cross_up`/`vwap_cross_down` (the "vwap" confluence tool) AND `orb_bull_signal`/`orb_bear_signal` (the "orb" confluence tool) | **Both tools partially affected** -- this is a second finding beyond what the originating report flagged (it only named the vwap tool). The bearish/loss sides of each (`vwap_cross_down`) were fine; the bullish/reclaim sides were inflated. Confluence counts and the "tool active rate" numbers for `vwap` and `orb` in that report should be treated as unreliable on the bullish side. |
| `research/pattern-fulfillment` (`a896ba2`) | `vwap_cross_up`/`vwap_cross_down` (the "vwap" pattern -- its single largest instance population, 151,692 rows) | Bullish/reclaim instance count and downstream expectancy for "vwap" are unreliable; bearish/rejection side (`vwap_cross_down`) unaffected. Does not use `orb_bull_signal`/`orb_bear_signal` (not in `pattern_reference`'s 43 patterns). |
| `research/foundation-retest` (`45c392f`) | Found the bug; computed its own VWAP cross safely from `above_vwap` directly, never consumed the broken column. Does not use `orb_bull_signal`/`orb_bear_signal` at all. | **Not affected** -- this report's own findings stand as reported. |
| `research/dome-leg-signature`, `research/dome-leg-verify`, `research/setup-formation` (v1) | Neither feature referenced anywhere in these branches (grepped, no matches) | **Not affected.** |

**Re-running any of these is explicitly out of scope for this report** (per the brief) -- this is a map of
what to distrust and what would need re-verification if revisited, not a re-verification itself.

## Verdict

- **3 features were broken**, all from one root cause (bitwise-`~` on a pandas object-dtype-upcast bool
  series): `vwap_cross_up`, `orb_bull_signal`, `orb_bear_signal`.
- **All 3 are now fixed** (`shift(1, fill_value=False)`), verified via the binary-crossing identity on real
  AAPL 5m data, confirmed by a regression test suite that demonstrably fails on the pre-fix code and passes
  on the post-fix code, with the full existing 164-test suite still green.
- **~12 sibling cross/event features were audited and found sound** -- the bug is isolated, not symptomatic
  of a wider pattern across the file.
- **Prior results affected:** two research branches (`setup-formation-v2`'s vwap AND orb confluence tools;
  `pattern-fulfillment`'s vwap pattern, bullish side only in both cases) -- flagged for re-check, not
  re-run. `foundation-retest`'s own findings are unaffected (it worked around the bug from the start).
- **The bigger finding: this bug had live production impact.** `src/atlas_research/intraday/setups.py`'s
  setup-detection registry, wired into `scripts/ingest_intraday_5m.py`, has been writing over-detected
  `orb_bull`/`orb_bear`/`vwap_reclaim_bull` setups into the live `intraday_setups` table -- 4,094 of 49,261
  rows (8.3%), with a further 20,470 `intraday_outcomes` rows attached to them. This was not part of the
  originating report's known impact (which only named two research branches) and was found by following
  the grep trail one step further than the brief asked. Going forward, the fix in this commit corrects
  `detect_all_setups()`'s behavior automatically (it consumes whatever `compute_features()` produces); the
  already-written rows in `intraday_setups`/`intraday_outcomes` are unaffected by this commit and remain a
  cleanup decision for whoever owns that pipeline.
