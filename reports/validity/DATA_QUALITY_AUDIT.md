# Data Quality Audit — raw_bars

Generated: 2026-06-19T19:06:31.572665+00:00  |  Scan time: 27.7s
Tickers scanned: 6,221 (full universe)
Table max date observed: 2026-06-12

## Methodology / thresholds used

- Min trading days required: **260**
- 'Likely delisted' = no bar within the most recent **10** distinct trading dates in the table (cutoff date: **2026-06-01**)
- Liquidity window: most recent **60** distinct trading dates
- Large-gap threshold: **15** calendar days between consecutive bars (same ticker)
- Implausible-move thresholds (on adjusted_close daily return): **>50%** and **>100%**
- Split classification: among bars where raw `close` return exceeds 50%, if the `close/adjusted_close` ratio also shifts by more than 30% we treat it as a **handled split** (adjusted_close correctly absorbs it — informational only, not counted as bad data). If the ratio stays roughly flat despite the big raw-close move, that means adjusted_close did *not* absorb a real price-level jump — classified as **unhandled_split_or_bad_print** and counted as bad data. *Caveat: this will not catch smaller-ratio splits (e.g. 3:2, 5:4) whose raw return is below the 50% detection threshold — a known limitation of reusing a single move threshold for split detection.*
- Clean-universe filter: recent median price ≥ **$5.00**, recent avg dollar volume ≥ **$1,000,000**, bad-bar fraction < **0.50%**, trading days ≥ **260**, AND not likely-delisted (this last condition is *not* one of the four criteria in the original spec — I added it because a name that delisted 11–60 days ago can still clear the price/liquidity bars on its last active days yet isn't actually tradeable today; flag this assumption if you'd rather keep delisted names in the whitelist for survivorship-bias-aware backtests.) Bad-bar fraction is computed over **distinct flagged dates**, not raw flagged rows — a duplicated (ticker,date) with 2 copies counts as 1 bad day, not 2, so duplicates aren't double-weighted.

## Headline counts

| Issue | Count |
|---|---|
| Invalid bars (bad OHLC / null / negative volume) | 16 |
| Implausible adjusted_close moves (>50%) | 5,570 |
| ...of which >100% | 1,399 |
| Handled splits (informational, not 'bad') | 11 |
| Unhandled split / bad print (counted as bad) | 5,566 |
| Duplicate (ticker,date) rows | 0 across 0 tickers |
| Tickers with < 260 trading days | 715 |
| Tickers with a gap > 15d | 4 |
| Tickers likely delisted (no bar in last 10 sessions) | 17 |
| **Clean-universe tickers** | **3,361** / 6,221 |

## Top offenders by bad-bar count

_Counts here are raw flagged issues — a single bar that trips two checks (e.g. an invalid-OHLC bar that also produces an implausible return) counts twice here. The clean-universe filter below instead uses **distinct flagged dates** per ticker, so a ticker can show a higher number here than its actual bad-day percentage would suggest._

| Ticker | Bad bar count |
|---|---|
| VAXX | 174 |
| SMFL | 120 |
| FXLV | 84 |
| EBET | 54 |
| KLDO | 54 |
| CIIT | 51 |
| AFIB | 48 |
| EPWK | 48 |
| KBNT | 46 |
| SSM | 46 |
| PPCB | 43 |
| HPCO | 41 |
| SCPS | 39 |
| JEWL | 38 |
| MGAM | 36 |

## Example flagged bars

**Invalid OHLC examples:**

| Ticker | Date | Issue | Open | High | Low | Close | Volume |
|---|---|---|---|---|---|---|---|
| ACLX | 2026-05-15 | close_outside_high_low | 115.02999877929688 | 115.05000305175781 | 115.05000305175781 | 115.06999969482422 | 13191486 |
| CNL | 2021-10-08 | nonpositive_price | 1.2050000429153442 | 2.4100000858306885 | 0.0 | 1.2050000429153442 | 500 |
| DATS | 2026-06-08 | nonpositive_price | 0.0 | 0.0 | 0.0 | 2.6549999713897705 | 0 |
| EM | 2026-05-15 | open_outside_high_low | 1.2000000476837158 | 1.1950000524520874 | 1.1950000524520874 | 1.1950000524520874 | 1384616 |
| EWCZ | 2026-05-15 | nonpositive_price | 0.0 | 5.820000171661377 | 5.820000171661377 | 5.820000171661377 | 0 |
| GPAK | 2025-01-17 | open_outside_high_low | 0.00860000029206276 | 0.012000000104308128 | 0.012000000104308128 | 0.012000000104308128 | 1500 |
| LKSPR | 2026-06-11 | open_outside_high_low | 1.149999976158142 | 1.0 | 1.0 | 1.0 | 270 |
| LNKB | 2026-05-15 | open_outside_high_low | 8.609999656677246 | 8.6899995803833 | 8.6899995803833 | 8.6899995803833 | 194788 |
| MCW | 2026-06-08 | open_outside_high_low | 7.090000152587891 | 7.099999904632568 | 7.099999904632568 | 7.099999904632568 | 14603854 |
| MEG | 2023-06-05 | open_outside_high_low | 36.470001220703125 | 39.709999084472656 | 36.650001525878906 | 39.56999969482422 | 365762 |

**Implausible move / split examples:**

| Ticker | Date | Issue | Prev close | Close | Adj. return | Ratio Δ |
|---|---|---|---|---|---|---|
| ^VIX | 2021-11-26 | implausible_move+unhandled_split_or_bad_print | 18.58 | 28.62 | 54.0% | 0.0% |
| ^VIX | 2024-08-05 | implausible_move+unhandled_split_or_bad_print | 23.39 | 38.57 | 64.9% | 0.0% |
| ^VIX | 2024-12-18 | implausible_move+unhandled_split_or_bad_print | 15.87 | 27.62 | 74.0% | 0.0% |
| ^VIX | 2025-04-04 | implausible_move+unhandled_split_or_bad_print | 30.02 | 45.31 | 50.9% | 0.0% |
| AAOI | 2022-09-16 | implausible_move+unhandled_split_or_bad_print | 2.50 | 3.76 | 50.4% | 0.0% |
| AAOI | 2023-08-04 | implausible_move+unhandled_split_or_bad_print | 6.59 | 11.01 | 67.1% | 0.0% |
| AAOI | 2024-11-08 | implausible_move+unhandled_split_or_bad_print | 17.90 | 27.76 | 55.1% | 0.0% |
| AAOI | 2026-02-27 | implausible_move+unhandled_split_or_bad_print | 53.69 | 84.23 | 56.9% | 0.0% |
| AAP | 2025-05-22 | implausible_move+unhandled_split_or_bad_print | 31.31 | 49.17 | 57.0% | -0.0% |
| AARD | 2026-03-02 | implausible_move+unhandled_split_or_bad_print | 12.49 | 5.47 | -56.2% | 0.0% |

## Overall data-health stats

- Total rows scanned: 6,945,605
- Distinct tickers scanned: 6,221
- Bad-bar rate (flagged rows / total rows): 0.0804%
- Median trading days per ticker: 1256
- Tickers passing every clean-universe gate: 3,361 (54.0% of scanned universe)

## Output files

- `reports/validity/bad_bars.parquet` — bar-level flagged issues (invalid OHLC, implausible/unhandled-split moves, duplicates)
- `reports/validity/clean_universe.csv` — recommended whitelist (`ticker` column)
