# Pattern → Event Context (the "why" layer)

> **Coverage numbers below are PROVISIONAL** — the 5m pattern pass is still
> accumulating in the background, so 5m coverage will rise as more tickers land.

Links each `pattern_memory` instance to the corporate actions and news around
its decision bar, in the new `pattern_event_context` table (migration 0045).
Recognition + linkage only; pattern_memory is not altered.

## The look-ahead rule (why this isn't a leak)

- **Decision bar** = `daily`: **close** of confirm_date (16:00 America/New_York,
  DST-aware); `5m`: **open** of confirm_date (09:30 ET).
- An event is a valid cause (`relation='before'`) only if `event_time <= decision_bar`.
- **5m caveat:** `pattern_memory` stores only the DATE for 5m (no intraday timestamp),
  so same-session news cannot be proven to precede the bar — it is tagged
  **`same_day_unverified`**, never `before`. Storing the bar's `ts` in pattern_memory
  would let us tighten this to exact intraday precision.
- **News `created_at` is `timestamptz` (true UTC)** — verified — so the comparison is sound.
- **Predictive uses MUST filter to `relation='before'` (offset_days <= 0).**
  `after` and `same_day_unverified` are explanatory only.

## Windows
- Corporate actions: COALESCE(ex_date, effective_date, process_date) within
  **[-3, +1] NYSE trading days** of confirm_date (offsets via SPY session dates).
- News: `created_at` within **[-2, +1] days** of the decision bar, capped to the
  nearest links per (pattern, relation).

## Coverage (provisional) — 5,448,168 total links

| timeframe | pattern instances | % with ≥1 corp action | % with ≥1 PRIOR news (before) | % with any news (incl after) |
|---|---:|---:|---:|---:|
| 5m | 2,492,680 | 3.56% | 32.83% | 42.21% |
| daily | 2,906,433 | 4.92% | 19.53% | 24.59% |

### Links by kind × relation (before/after reported separately)

| event_kind | relation | links |
|---|---|---:|
| corporate_action | after | 46,644 |
| corporate_action | before | 185,871 |
| news | after | 1,161,455 |
| news | before | 3,081,506 |
| news | same_day_unverified | 972,692 |

### Corporate-action links by type

| ca_type | links |
|---|---:|
| cash_dividends | 230,212 |
| reverse_splits | 746 |
| forward_splits | 598 |
| spin_offs | 268 |
| name_changes | 265 |
| rights_distributions | 131 |
| stock_dividends | 123 |
| stock_mergers | 112 |
| stock_and_cash_mergers | 30 |
| cash_mergers | 20 |
| unit_splits | 10 |

Earliest linked news event_time: **2012-04-17 11:49:53-07:00**

## Honest coverage caveats
- News is universe-filtered and Alpaca news is **sparse pre-2016 and for small caps**,
  so a large share of older / thin-name pattern instances have **no** news "why" available.
- **KNOWN GAP (stated, not solved):** Alpaca news carries no analyst-estimate /
  earnings-surprise magnitude. The "why" here is *"news existed / an event occurred"*,
  not *"earnings beat by X%"*. A fundamentals/earnings-calendar feed would deepen this.
