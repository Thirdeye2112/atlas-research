"""
Mean-reversion features.

PURITY CONTRACT — stateless pure function. See trend.py for the full contract.
No DB, no side effects; inputs are ascending-date numpy float64 arrays; output is
the feature dict for the FINAL bar.

Validated cross-stock (10-name basket, embargoed walk-forward, net of costs):
oversold / extended-down / high-vol states precede positive forward returns
(rsi_oversold +IC 10/10 stocks, dist_ema200 -IC 9/10). The composite `mr_score`
below ranks how oversold/extended-down a bar is; higher = more mean-reversion
upside. It is an ENTRY-TIMING / ranking feature (it does not beat buy & hold as a
standalone in/out strategy — cash drag), best used in combination and confirmed
intraday (next-day close > VWAP roughly doubled the daily edge).

Produces:
    mr_score      composite z-scored mean-reversion score (final bar), trailing-252
                  standardized: -z(rsi) -z(bb_pct) -z(dist_ema20) -z(dist_ema200)
                  -z(stoch_k) +z(atr_pct), averaged. Higher = more oversold/extended.
    mr_oversold   1 if mr_score >= 1.0 (the validated entry threshold) else 0
"""
from __future__ import annotations
import numpy as np
import pandas as pd

LOOKBACK = 252   # trailing window for standardizing the components
MIN_BARS = 220


def _components(close, high, low) -> pd.DataFrame:
    c = pd.Series(close); h = pd.Series(high); l = pd.Series(low)
    d = c.diff()
    g = d.clip(lower=0).ewm(com=13, adjust=False).mean()
    ls = (-d.clip(upper=0)).ewm(com=13, adjust=False).mean()
    rsi = 100 - 100 / (1 + g / ls.replace(0, np.nan))
    bb_mid = c.rolling(20).mean(); bb_std = c.rolling(20).std()
    bb_pct = (c - (bb_mid - 2 * bb_std)) / ((bb_mid + 2 * bb_std) - (bb_mid - 2 * bb_std)).replace(0, np.nan)
    ema20 = c.ewm(span=20, adjust=False).mean(); ema200 = c.ewm(span=200, adjust=False).mean()
    dist_ema20 = (c - ema20) / ema20 * 100
    dist_ema200 = (c - ema200) / ema200 * 100
    lo14 = l.rolling(14).min(); hi14 = h.rolling(14).max()
    stoch_k = (c - lo14) / (hi14 - lo14).replace(0, np.nan) * 100
    tr = pd.concat([(h - l), (h - c.shift(1)).abs(), (l - c.shift(1)).abs()], axis=1).max(axis=1)
    atr_pct = tr.ewm(com=13, adjust=False).mean() / c * 100
    return pd.DataFrame({"rsi": rsi, "bb_pct": bb_pct, "dist_ema20": dist_ema20,
                         "dist_ema200": dist_ema200, "stoch_k": stoch_k, "atr_pct": atr_pct})


def compute(close: np.ndarray, high: np.ndarray, low: np.ndarray) -> dict[str, float | None]:
    if close is None or len(close) < MIN_BARS:
        return {"mr_score": None, "mr_oversold": None}
    comp = _components(close, high, low)
    neg = ["rsi", "bb_pct", "dist_ema20", "dist_ema200", "stoch_k"]; pos = ["atr_pct"]
    score = 0.0; k = 0
    for col in neg + pos:
        s = comp[col].iloc[-LOOKBACK:]
        m, sd = s.mean(), s.std()
        if sd is None or np.isnan(sd) or sd == 0 or np.isnan(s.iloc[-1]):
            return {"mr_score": None, "mr_oversold": None}
        z = (s.iloc[-1] - m) / sd
        score += (-z if col in neg else z); k += 1
    score = float(score / k)
    return {"mr_score": round(score, 4), "mr_oversold": 1 if score >= 1.0 else 0}
