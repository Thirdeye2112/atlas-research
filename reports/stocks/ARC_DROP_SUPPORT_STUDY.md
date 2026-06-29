# Arc drop-target & support study — 5m (10 names, 8,531 arcs)

The whole arc as one object: **throw → top → bounce → next rise**. We don't forecast the pullback from launch dynamics (that was ~R²0.13); instead we (1) propose drop-distance **targets** from where the bounce actually lands, and (2) test whether **support built on the way up** is where the drop stops.

## 1. Proposable drop-distance targets

Drop (peak→bounce low) as a fraction of the run — **retrace** percentiles:

| p10 | p25 | median | p75 | p90 |
|---|---|---|---|---|
| 0.264 | 0.373 | 0.557 | 0.845 | 1.252 |

Typical drop ≈ **0.73%** off the top over ~5 bars. By run size (bigger run → shallower retrace):

| run size | n | median retrace | median drop % |
|---|---|---|---|
| small | 2133 | 0.76 | 0.63% |
| medium | 2133 | 0.57 | 0.62% |
| big | 2132 | 0.52 | 0.73% |
| huge | 2133 | 0.44 | 1.01% |

**Bid rule:** target ≈ peak − retrace×run; use ~0.30 for big/huge runs, ~0.45 for small/medium. Band the bid between p25 and p75 retrace.

## 2. Does the drop stop at support built on the way up?

- Avg footholds (higher-lows/local bases) built during the ascent: **2.6**.
- The bounce lands **at/above the nearest higher-low** (holds the last support) in **78%** of arcs; within 10%-of-run of *some* support level in **20%**.
- More support built on the way up → shallower drop: corr(#supports, drop%) = **-0.141**, corr(#supports, retrace) = **-0.217**.
- Vertical room down to the nearest support tracks the drop: corr(room-to-support, drop%) = **0.17**.

## 3. Which drop target lands closest to the actual bounce?

Median |target − actual bounce| as % of the run (lower = sharper), and how often the target is within 10%-of-run of the real bounce:

| drop target | median error | within 10% of run |
|---|---|---|
| fixed 50% retrace | 0.198 | 25% |
| fixed 35% retrace | 0.215 | 28% |
| most-recent foothold | 0.365 | 14% |
| nearest higher-low support | 0.383 | 14% |
| full retrace to launch | 0.495 | 8% |

_5m only (2023+). Survivorship: arcs are confirmed swing highs with a same-session bounce; in real time gate the rebuy with oversold/VWAP confirmation._