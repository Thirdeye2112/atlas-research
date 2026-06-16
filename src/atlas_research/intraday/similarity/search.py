"""
Atlas Intraday Similarity Search v1
=====================================
KNN search over intraday_candle_memory using weighted Euclidean distance.
Category gates (time-of-day, regime, conviction) narrow the candidate pool
before distance ranking so the K nearest matches share meaningful context.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.neighbors import NearestNeighbors

from .features import DEFAULT_WEIGHTS, N_FEATURES, build_feature_vector


class SimilaritySearch:
    """
    Fit against a candle memory DataFrame, then query for similar candles.

    Usage
    -----
    search = SimilaritySearch()
    search.fit(memory_df)
    matches = search.query(query_vec, k=50)
    """

    def __init__(self, weights: np.ndarray | None = None, algorithm: str = "ball_tree"):
        self._weights  = weights if weights is not None else DEFAULT_WEIGHTS
        self._algo     = algorithm
        self._nbrs: NearestNeighbors | None = None
        self._memory:  pd.DataFrame | None  = None
        self._weighted_matrix: np.ndarray | None = None

    # ------------------------------------------------------------------
    def fit(self, memory_df: pd.DataFrame) -> "SimilaritySearch":
        """
        Build the KNN index from a DataFrame that has a 'feature_vector' column
        (list/array of length N_FEATURES per row).
        """
        if memory_df.empty:
            raise ValueError("memory_df is empty -- cannot build KNN index")

        vecs = np.stack(memory_df["feature_vector"].values).astype(np.float64)
        if vecs.shape[1] != N_FEATURES:
            raise ValueError(f"Expected {N_FEATURES} features, got {vecs.shape[1]}")

        self._weighted_matrix = vecs * self._weights   # (N, 16), weighted
        k_max = min(len(memory_df), 600)
        self._nbrs = NearestNeighbors(
            n_neighbors=k_max,
            metric="euclidean",
            algorithm=self._algo,
        )
        self._nbrs.fit(self._weighted_matrix)
        self._memory = memory_df.reset_index(drop=True)
        return self

    # ------------------------------------------------------------------
    def query(
        self,
        query_vec: np.ndarray,
        k: int = 50,
        gate_time: str | None = None,
        gate_regime: str | None = None,
        gate_conviction: str | None = None,
        exclude_tickers: set[str] | None = None,
        exclude_before_ts=None,
    ) -> pd.DataFrame:
        """
        Find the K most similar historical candles.

        Parameters
        ----------
        query_vec       : 1-D array of length N_FEATURES (already normalized)
        k               : number of neighbors to return after gating
        gate_time       : if set, only return candles in this time_of_day bucket
        gate_regime     : if set, only return candles with this daily_regime
        gate_conviction : if set, only return candles with this daily_conviction
        exclude_tickers : set of ticker strings to exclude (e.g., current ticker)
        exclude_before_ts: exclude candles at or after this timestamp (future exclusion)
        """
        if self._nbrs is None or self._memory is None:
            raise RuntimeError("Call .fit() before .query()")

        q = (query_vec * self._weights).reshape(1, -1)

        # Request more neighbors when gating to ensure we get k after filtering
        gate_factor = 1
        if gate_time:       gate_factor *= 4
        if gate_regime:     gate_factor *= 2
        if gate_conviction: gate_factor *= 2
        k_req = min(len(self._memory), k * gate_factor + 50)

        dists, idxs = self._nbrs.kneighbors(q, n_neighbors=k_req)
        matches = self._memory.iloc[idxs[0]].copy()
        matches["distance"] = dists[0]

        # Apply gates
        if exclude_before_ts is not None and "ts" in matches.columns:
            matches = matches[matches["ts"] < exclude_before_ts]
        if gate_time and "time_of_day" in matches.columns:
            matches = matches[matches["time_of_day"] == gate_time]
        if gate_regime and "daily_regime" in matches.columns:
            matches = matches[matches["daily_regime"] == gate_regime]
        if gate_conviction and "daily_conviction" in matches.columns:
            matches = matches[matches["daily_conviction"] == gate_conviction]
        if exclude_tickers and "ticker" in matches.columns:
            matches = matches[~matches["ticker"].isin(exclude_tickers)]

        return matches.head(k).reset_index(drop=True)

    # ------------------------------------------------------------------
    def query_row(
        self,
        row: "pd.Series | dict",
        k: int = 50,
        apply_gates: bool = True,
        exclude_before_ts=None,
    ) -> pd.DataFrame:
        """
        Convenience wrapper: build vector from a row dict/Series and query.
        When apply_gates=True, uses time_of_day and daily_regime from the row.
        """
        vec = build_feature_vector(row)

        def _get(key):
            if hasattr(row, "get"):
                return row.get(key)
            return getattr(row, key, None)

        gate_time   = _get("time_of_day")   if apply_gates else None
        gate_regime = _get("daily_regime")  if apply_gates else None

        return self.query(
            vec,
            k=k,
            gate_time=gate_time,
            gate_regime=gate_regime,
            exclude_before_ts=exclude_before_ts,
        )

    # ------------------------------------------------------------------
    @property
    def n_indexed(self) -> int:
        return 0 if self._memory is None else len(self._memory)
