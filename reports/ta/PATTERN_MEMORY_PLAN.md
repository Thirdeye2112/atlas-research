# Pattern Memory — agreed plan (the foundation)

Build the LIBRARY first: catalog and fully understand every pattern that ever
happened, before predicting anything. No win-rate claims in Step 1 — it's the
knowledge base the rest reads from.

## Step 1 — Pattern Memory (BUILD FIRST)
For every stock in the CLEAN universe (config/clean_universe.csv), on DAILY first
then 5-min, scan all history and log EVERY detected instance of:
  - candlestick patterns (all 19 names)
  - chart patterns (bull/bear flag, head&shoulders +inverse, double top/bottom,
    triangles, wedges, ...)
  - swing_leg / "dome" (rise from support -> peak -> correction)  [see below]
Overlaps and patterns-inside-patterns are KEPT, not deduped. No-pattern stretches
are fine (not logged as instances).

For each instance, log the full STORY into a queryable `pattern_memory` table:
  BEFORE  : prior trend (this TF + higher TF), the move into it, distance to key
            MAs and to nearest support/resistance.
  THROUGH : the pattern's bars + candles inside; indicators at confirm
            (RSI, MACD-hist, ADX, ATR%, volume vs average).
  AFTER   : bar-by-bar resolution — run/pullback/run sequence, max favorable &
            adverse move, distance run vs the pattern's measured move, time taken.
After-window: ~60 daily bars / ~78 five-min bars (full run/pullback sequence within).

Storage: Postgres table `pattern_memory` (queryable, joins to bars). The dated
audit/whitelist stays in config/ + reports/validity/.

Build order: chart patterns (daily, clean) -> add standalone candles -> add 5-min
-> add swing_leg/dome. Each populates the SAME table.

## Step 1b — Swing-leg / "dome" study (the user's macro-shape idea)
swing_leg = swing low (support) -> peak -> correction low (the hump).
EARLY SIGNATURE (first 2-5 bars off the low): combined % gain, body sizes,
slope/angle, volume, RSI slope, gaps.
LEARN: does the early signature predict (a) leg height %, (b) bars to peak,
(c) correction depth %, (d) correction duration? Conditional stats + simple model.

## Step 2 — Candle-by-candle foresight
Walk forward one candle; using the memory, recognize "this is starting to look
like X" / "this candle often leads to Y"; predict next candle direction + RANGE
with historical run/pullback percentages.

## Step 3 — Learn from misses (overfitting-safe)
Re-examine wrong predictions, find what context differed, refine, retry — keep a
change ONLY if it holds on data the system did not learn from. Forward paper-test
is the ultimate check.

## Step 4 — Macro/events + omni transcripts
Tag major events; test the hypothesis that many "event" moves were patterns
already setting up. Re-mine the omni video transcripts for that fulfillment logic.

## Design choices (agreed)
- Storage = Postgres `pattern_memory` table.
- Daily first, then 5-min.
- After-window ~60 daily / ~78 five-min, full run/pullback sequence recorded.
- Clean universe via settings.CLEAN_UNIVERSE_CSV (3,361 tickers).
