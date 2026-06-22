# Options data: what this connector can and can't see

This account does not have the OPRA market-data agreement signed (confirmed
directly via the API -- see `scripts/options_market_data_test.py`, which
prints `OPRA: NOT entitled` and the underlying `403` response on every run).
That one fact determines everything below. It is the reason this overlay is
built on **open interest / reference data**, not trade flow, and why it must
not be described as Ghost Prints-style flow analysis.

## Available on this account

- **Contract reference data** -- `TradingClient.get_option_contracts()`
  (the Trading API, not the Data API). Works fully, no OPRA needed.
- **`open_interest`** -- real, current open-interest figures per contract.
  Confirmed populated for roughly 60-75% of contracts in a given snapshot
  (varies by ticker/liquidity); the remainder report `null`, not zero --
  see `oi_coverage_pct` in `options_build_oi_structure_features.py`'s output.
- **`open_interest_date`** -- the as-of date for the open_interest figure above.
- **`close_price`** -- the contract's last settlement/close price (reference
  data, not a live quote).
- **`close_price_date`** -- the as-of date for `close_price`.
- **Current indicative quote/trade/snapshot**, where available -- the free
  `OptionsFeed.INDICATIVE` feed answers "what is the market showing right
  now," for whichever contracts have any quoting activity at all. This is a
  point-in-time read at the moment the script runs, not a series.

## Not available on this account

- **Historical OPRA trade tape.** The consolidated, real options trade feed
  is gated behind OPRA ("Algo Trader Plus"), which is not signed. Every
  historical trade/bar request for option contracts returns at most a
  handful of indicative-marker rows (`conditions='I'`) or a hard `403`.
- **Historical bid/ask-at-trade.** Without the trade tape, there is no way
  to reconstruct what the spread looked like at the moment any historical
  trade occurred.
- **Real historical option volume.** `OptionBarsRequest` on this feed
  returns near-empty bars (observed: 1 bar with `trade_count=2` across a
  ~2.5 year window) -- there is no real daily volume series to compute
  `volume_oi_ratio` or any volume-based feature from. This connector leaves
  `volume_oi_ratio` as `NaN` everywhere rather than approximate it from a
  single trade's `size` (not the same thing as daily volume).
- **Aggressor-side classification.** Without a trade tape with timestamped
  bid/ask context, there is no basis for labeling a print as buyer- or
  seller-initiated.
- **A true Ghost Prints-style historical flow backtest.** That style of
  signal is fundamentally a trade-tape signal (large/unusual prints,
  aggressor side, relative to volume) -- none of its required inputs exist
  on this account's current entitlement. Nothing in this connector should be
  read as an approximation of it.

## What this means for the overlay

The OI-structure overlay built on top of this connector
(`options_snapshot_universe.py` + `options_build_oi_structure_features.py`)
answers a different, real question: **where is existing open interest
parked right now, and how is it distributed across strikes, moneyness, and
expiration** -- a structural/positioning snapshot, refreshed once per run,
not a flow signal. It can be informative on its own terms (e.g. OI
concentration at a strike, put/call OI skew) but it cannot detect "who
traded what, when, in what size, and on which side" -- that requires OPRA.

If real flow analysis becomes a priority, the path is: sign the OPRA
agreement on this account (a paid subscription), then re-test
`scripts/options_market_data_test.py` -- it already probes OPRA entitlement
explicitly on every run and will report `OPRA: ENTITLED` the moment that
changes, with no code changes needed to detect it.
