# Multi-timeframe Layer-4 — REFINED gate (10 names)

Quality-weighted daily ceiling (cap only on walls formed by a ≥1-ATR rejection) applied to confident entries (d_rsi ≤ 45 & daily trend ≠ down). Split-safe; target ladder ±1/2/3 daily-ATR; stop −1 ATR; 10d forward; chronological 60/40. n=7,681; confident = 14% of setups.

## Walk-forward holdout — expectancy (R) & target-hit

| strategy | expectancy (R) | hit | n |
|---|---|---|---|
| always T3 | +0.253 | 19% | 3073 |
| naive gate (nearest wall) | +0.149 | 50% | 3073 |
| QUALITY gate (strong walls) | +0.148 | 49% | 3073 |
| always T3 — confident entries | +0.414 | 19% | 412 |
| QUALITY gate — confident entries | +0.335 | 57% | 412 |

## Verdict

- **The entry filter is the real lever.** Confident entries (oversold dip, not down-trend) lift always-T3 expectancy **+0.253R → +0.414R** (**64%**) — the higher-timeframe context pays off mostly through *entry selection*, validating the layered-confluence principle.
- **The target gate is a consistency dial, not an expectancy boost.** On confident entries the quality gate hits **57% vs 19%** for always-T3 at **+0.335R vs +0.414R** — ~3× the win-rate for a modest expectancy give-up. Use aim-far to maximise compounding; use the gate to smooth the equity curve / size up.
- The naive vs quality gate are near-identical because the daily wall (not its quality) is usually the binding cap once the trend allows T3; the **strong-wall filter matters most for *where to take profit*, not whether to enter.**

_Aim far by default; trim to the rung below a STRONG daily wall when one is within reach; trade the high-confidence dip-in-uptrend setups — your 'trade within the pattern when direction + run-ability are confident' principle, quantified._