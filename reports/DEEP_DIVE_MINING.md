# Data-mining the deep dive — `deep_dive_events`

One row per significant move / candlestick / chart-structure fulfillment across
the daily universe, with the decision-bar TA snapshot, the validated `mr_score`,
forward outcomes, and a confluence read. Lives in **atlas_research** (table
`deep_dive_events`) — `atlas-alpha` reads it via `DATABASE_URL_RESEARCH`.

Built by `scripts/mine_universe.py` (checkpointed/resumable, idempotent upsert).
Schema: `db/migrations/0055_deep_dive_events.sql`.

**Predictive-use rule:** filter on TA / `mr_score` columns; `fwd_ret_*` are
OUTCOMES (future) — labels only, never predictors.

## Research mining (find/confirm edges)

Which setups have the best forward edge, universe-wide:
```sql
SELECT name, direction, count(*) n,
       round(avg(fwd_ret_5)::numeric,3) avg_fwd5,
       round((100.0*sum((fwd_ret_5>0)::int)/count(*))::numeric,1) win5
FROM deep_dive_events
WHERE event_type='candlestick'
GROUP BY 1,2 HAVING count(*)>=500
ORDER BY avg_fwd5 DESC;
```

Does the mean-reversion score add edge inside a setup (mine the interaction):
```sql
SELECT name, mr_oversold, count(*) n, round(avg(fwd_ret_5)::numeric,3) avg_fwd5
FROM deep_dive_events
WHERE name IN ('inverted_hammer','bullish_harami','double_bottom')
GROUP BY 1,2 ORDER BY 1,2;
```

Discover hidden conditions — best forward returns by TA bucket:
```sql
SELECT width_bucket(mr_score,-2,3,5) AS mr_bucket,
       round(avg(fwd_ret_5)::numeric,3) avg_fwd5, count(*) n
FROM deep_dive_events GROUP BY 1 ORDER BY 1;
```

Per-stock generalization of a setup:
```sql
SELECT ticker, count(*) n, round(avg(fwd_ret_5)::numeric,3) avg_fwd5
FROM deep_dive_events WHERE name='bull_flag' AND direction='long'
GROUP BY 1 HAVING count(*)>=10 ORDER BY avg_fwd5 DESC;
```

## Alpha mining (live signal lookup)

Today's actionable mean-reversion candidates (most recent bar oversold + confluence):
```sql
SELECT ticker, ts, name, mr_score, confluence_n, explained_by, rsi, dist_ema200
FROM deep_dive_events
WHERE ts = (SELECT max(ts) FROM deep_dive_events)
  AND mr_oversold=1 AND above_ema200=1 AND confluence_n>=3
ORDER BY mr_score DESC;
```

Historical base-rate for a live setup (what usually happens next):
```sql
SELECT count(*) n, round(avg(fwd_ret_5)::numeric,3) avg_fwd5,
       round((100.0*sum((fwd_ret_5>0)::int)/count(*))::numeric,1) win5
FROM deep_dive_events
WHERE name='inverted_hammer' AND mr_oversold=1 AND above_ema200=1;
```

## Notes / next
- 5m confirmation (next-day close>VWAP roughly doubled the daily edge) is computed
  on demand for live signals; a `deep_dive_events_5m` companion can be added the
  same way once intraday mining is prioritized (5m only exists 2023+).
- To promote into a model: `mr_score` is already a nightly feature; add it to a V4
  feature-set version and walk it forward alongside V3.
