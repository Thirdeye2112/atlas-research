# Swing-Leg / "Dome" Detection — Directional Symmetry Audit

_Read-only investigation. Branch `research/dome-symmetry` (off `fix/model-validity`), isolated
worktree so the active sessions on the main tree were not disturbed. No detection code changed, no
writes to `pattern_memory`._

## Verdict: **ASYMMETRIC** — bullish up-leg ("dome/hump") only; bearish down-leg ("valley/bowl") is missed.

The detector captures **rise-from-support → peak → correction** (LOW→HIGH→LOW) and never the mirror
**fall-from-resistance → trough → bounce** (HIGH→LOW→HIGH). Confirmed by both the code and the data.

## 1. The detection logic, in plain terms

`src/atlas_research/ta/patterns.py :: swing_legs()` walks the swing-pivot sequence two at a time and
keeps a pair **only if the first pivot is a swing LOW and the second is a swing HIGH** — i.e. an
up-leg. Direction is **baked into the geometry**; there is no direction flag and no trough-first path.

The orientation gate (line 169):

```python
for i in range(len(piv) - 1):
    a, b = piv[i], piv[i+1]
    if not (a.kind == 'L' and b.kind == 'H' and a.price > 0):   # <-- LOW then HIGH only
        continue
    leg_amp = (b.price - a.price) / a.price                     # assumes b > a (up-leg)
    if leg_amp < min_amp:                                       # negative amps (down-legs) rejected
        continue
    ...
    c = piv[i+2] if i+2 < len(piv) and piv[i+2].kind == 'L' else None   # correction = next LOW
    ...
    early_gain = (close[e_end] - a.price) / a.price             # rise off the low (positive)
```

The module docstring states the intent explicitly: *"a rise from a swing LOW to the next swing HIGH
(the up-leg), then the correction down to the following swing LOW."* The mirror case
(`a.kind == 'H' and b.kind == 'L'`, then a bounce up to the next HIGH) is never evaluated.

The driver hardcodes the direction when logging (`scripts/build_pattern_memory.py`):

```python
for sl in P.swing_legs(piv, h, l, cl):
    ...
    rows.append([tk, "daily", "swing_leg", "long", ...])   # direction literal: always "long"
```

## 2. Empirical confirmation (read-only, from `pattern_memory`)

| check | result | implication |
|---|---|---|
| `swing_leg` rows by `direction` | **`long` = 172,707; `short` = 0** | only one orientation ever logged |
| `extra.leg_amp` range | **all positive** (min +0.050, max +83.06, avg +0.203) | all up-legs; min = the `min_amp` floor |
| `extra.early_gain` range | **all ≥ 0** (0.0 → +63.0) | every early signature is a *rise*, never a *fall* |
| `timeframe` | all `daily` (172,707) | swing_legs are not run on 5m at all (separate gap) |

A 100%-`long`, strictly-non-negative `leg_amp`/`early_gain` population is exactly the fingerprint of
a one-sided detector.

## 3. Known-case sanity check

Because the gate rejects any HIGH→LOW pair before measuring, a clear **valley/bottom** (down-leg then
bounce) can never be logged as a `swing_leg`: the pivot pair at the bottom is HIGH→LOW (failing line
169), and the bounce LOW→HIGH that follows is logged as an *up-leg* (the recovery), not as the valley
itself. So down-moves are represented only by their *recovery up-legs*, and the descent structure —
the thing a bowl/valley study would need — is absent. The data agrees: there is no row whose
`leg_amp` or `early_gain` is negative, i.e. no descent leg exists in 172,707 instances.

## 4. Does the early-signature math generalize to a down-leg?

Yes, by mirroring — and it needs explicit sign handling:
- **Up-leg (current):** `leg_amp = (peak - low) / low > 0`; `early_gain = (close[e_end] - low) / low ≥ 0`
  (rise off the low); `early_slope = early_gain / bars ≥ 0`.
- **Down-leg (mirror):** anchor at a swing HIGH; `leg_amp = (high - trough) / high > 0` (use magnitude,
  not the raw signed difference, so the `min_amp` filter still works); the early signature is a
  **fall** off the high: `early_loss = (high - close[e_end]) / high ≥ 0`, `early_slope ≤ 0` in signed
  terms. The "does the first N bars predict the eventual depth & bounce?" study is the exact mirror of
  the current "predict the hump height & correction" study.

So the study is well-defined for both directions; the current code simply never computes the down side.

## 5. Look-ahead note (applies to BOTH orientations — flagging, not introducing)

The swing_leg is logged at `peak_idx` (the leg's end), but `extra` already carries **forward** fields:
`corr_depth` / `corr_bars` come from `c = piv[i+2]`, a swing low that occurs **after** the peak. These
are *outcomes* (the dependent variables of the early-signature study), not point-in-time features — fine
for the study as designed, but **any predictive use must not consume `corr_*` (or the mirror's bounce
fields) as features at decision time**; that would be look-ahead. The proposed mirror must obey the
identical rule: detect the leg from past pivots (`a`,`b`), treat the bounce (`c`) as a forward outcome.

## 6. Proposed mirror plan (NOT implemented — for your go)

Edit **only** `src/atlas_research/ta/patterns.py` (and the one logging line in
`scripts/build_pattern_memory.py`, which is owned/contested — hand that one line to the owner if needed):

1. **Detection.** Add a down-leg branch (or generalize `swing_legs` with a `direction` arg):
   - gate: `a.kind == 'H' and b.kind == 'L' and a.price > 0`;
   - `leg_amp = (a.price - b.price) / a.price` (magnitude, so `min_amp` still applies);
   - correction → next HIGH: `c = piv[i+2] if piv[i+2].kind == 'H' else None`;
     `bounce_depth = (c.price - b.price) / b.price`;
   - early signature off the high: `early_move = (close[e_end] - a.price) / a.price` (≤ 0);
     keep sign so up vs down legs are distinguishable.
2. **Schema / representation.** Two options:
   - simplest, queryable now: log down-legs with `direction = 'short'` and the same `extra` keys, where
     `leg_amp` stays a positive magnitude and a new `extra.leg_dir` ∈ {`up`,`down`} (or rely on
     `direction`) disambiguates; `early_gain` becomes signed (negative for down-legs) OR add
     `extra.early_signed`. Recommend an explicit `extra.leg_dir` so existing `leg_amp ≥ 0` queries
     don't silently mix orientations.
   - keep `corr_depth`/`corr_bars` field names for both (they mean "the move that ends the leg":
     correction-down for up-legs, bounce-up for down-legs) and rely on `leg_dir` for interpretation.
3. **Look-ahead guard.** Unchanged from §5 — leg from past pivots, ending move is a forward outcome.
4. **Backfill.** A new additive pass (do not rewrite the 172,707 existing up-leg rows); idempotent skip
   like the channel backfill. **Decision needed:** whether to also run swing_legs (both directions) on
   5m, where they are currently absent entirely.

## Recommendation
The detector is asymmetric and the blind spot is real — any analysis weighting swing-legs is currently
bull-biased. The fix is a contained mirror in one module plus an additive backfill.

## Implementation status (mirror added — detection only)

Implemented in **`src/atlas_research/ta/patterns.py`** only (no other files changed, no DB writes):
- `_legs(..., direction)` — shared up/down detector; magnitudes positive; adds `leg_dir`.
- `swing_legs()` — unchanged up-leg behavior (backward-compatible) + new `leg_dir='up'` key.
- `swing_legs_down()` — the mirror bowl/valley (HIGH→LOW→bounce), `leg_dir='down'`.
- `swing_legs_all()` — both, ordered by terminal-extreme bar.

Synthetic validation (L,H,L,H,L series): up-legs and down-legs both detected, all `leg_amp ≥ 0`,
`early_gain` = early move magnitude per direction, `corr_depth` = the leg-ending move (correction-down /
bounce-up), look-ahead preserved (`corr_*` from the forward pivot only).

**Still pending your go (NOT done — would write to pattern_memory, which this task forbids):**
1. One-line integration in `scripts/build_pattern_memory.py` (contested file — for the owner):
   change `for sl in P.swing_legs(piv,h,l,cl):` → `P.swing_legs_all(...)`, set
   `direction = "long" if sl["leg_dir"]=="up" else "short"`, and add `leg_dir` to the logged `extra`.
2. An **additive** down-leg backfill (idempotent; do not rewrite the 172,707 existing up-leg rows).
3. Decide whether to also run swing_legs on 5m (currently absent there).
