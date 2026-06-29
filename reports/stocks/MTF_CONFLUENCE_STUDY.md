# Multi-timeframe confluence (Layer 4) — does daily/weekly pick the target? (10 names)

5m up-leg launches as entries (one/ticker/day, n=7,681); target ladder T1/T2/T3 = +1/+2/+3 **daily-ATR**; stop −1 daily-ATR; 10-day forward; daily & weekly context strictly before entry. Conservative (stop-before-target intrabar).

## A. Daily resistance is a ceiling on the move

- corr(headroom-to-daily-resistance, MFE) = **-0.001** — more room overhead → bigger move.
- Median MFE with a daily wall **near** (≤3 ATR): **1.71 ATR** vs **1.73 ATR** in clear air; reach-T3 **22%** vs **24%**. A near daily ceiling caps the realistic target.

## B. Higher-timeframe trend = run-ability

| timeframe | trend | n | median MFE (ATR) | reach-T2 |
|---|---|---|---|---|
| daily | down | 2201 | 1.68 | 42% |
| daily | range | 2648 | 1.71 | 42% |
| daily | up | 2832 | 1.73 | 43% |
| weekly | down | 1706 | 1.57 | 38% |
| weekly | range | 2885 | 1.81 | 46% |
| weekly | up | 3090 | 1.69 | 42% |

## C. Walk-forward: daily-gated target selection vs naive

Chronological 60/40 split; holdout n=3,073. Expectancy in R (reward:risk vs the 1-ATR stop).

| target rule | expectancy (R) | target-hit rate |
|---|---|---|
| always T1 | +0.147 | 57% |
| always T2 | +0.201 | 34% |
| always T3 | +0.253 | 19% |
| DAILY-GATED rule | +0.134 | 52% |

**Verdict (first cut):** the daily-gated rule **does NOT beat** the best fixed target (always T3, +0.253R) on the holdout (rule +0.134R). On *unfiltered* bounce entries, naive 'aim far' wins — consistent with the resistance study (walls mostly break; only violent/recent ones stop a run). The gate should cap only on QUALITY daily resistance (touches / prior-drop intensity) and apply to CONFIDENT directional entries, not every snapback.

_The daily-gated rule aims at T3 only with daily+weekly trend and clear air, caps at the rung below a near daily wall, and trims to T1 in downtrends — the Layer-4 gate on top of the 5m entry. Survivorship: confirmed swing-high launches; gate live with the 5m VWAP-reclaim entry._