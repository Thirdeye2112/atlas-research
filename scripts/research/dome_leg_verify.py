#!/usr/bin/env python
"""
dome_leg_verify.py
=====================
ADVERSARIAL verification of the dome-leg early-signature result
(research/dome-leg-signature, commits e2b6d60 + 318c4ba). Read-only on all
existing tables (intraday_bars, research_dome_leg*). Writes only to a new
table research_dome_leg_verification (created by this branch's own
migration) and to reports/research/DOME_LEG_VERIFICATION.md.

The prior run reported r(early_gain, leg_amp) = 0.61-0.75, "non-
tautological," stable OOS, replicated on 13 stocks. This script tries to
BREAK that result: tautology via shared accounting (not just shared bars),
look-ahead in pivot-confirmation timing, triviality vs. a momentum
baseline, and independent re-replication on fresh tickers and fresh code.

Usage (cwd = C:\\Atlas\\atlas-research):
    .venv\\Scripts\\python.exe scripts\\research\\dome_leg_verify.py
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

import sys
_WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_WORKTREE_ROOT / "src"))
sys.path.insert(0, str(_WORKTREE_ROOT))

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv(usecwd=True), override=True)

import config.settings as settings
from atlas_research.intraday.features import compute_features
from atlas_research.ta.structure import swing_pivots, Pivot

DATABASE_URL = settings.DATABASE_URL
REPORTS_DIR = _WORKTREE_ROOT / "reports" / "research"

ORIGINAL_3 = ["AAPL", "NKE", "INTC"]
PRIOR_10 = ["TSLA", "META", "AMD", "XOM", "WFC", "KO", "PFE", "UBER", "CSX", "DKNG"]
FRESH_5 = ["CSCO", "CMCSA", "MU", "AAL", "GM"]

PIVOT_WIDTH = 3
AMP_MULT = 2.5
EARLY_N = 5
TRAIN_FRACTION = 0.70


# ---------------------------------------------------------------------------
# Stats helpers (independent re-implementation, not imported from the
# branch under test)
# ---------------------------------------------------------------------------

def pearson_p(a, b):
    a = np.asarray(a, float); b = np.asarray(b, float)
    mask = ~(np.isnan(a) | np.isnan(b))
    a, b = a[mask], b[mask]
    n = len(a)
    if n < 4:
        return np.nan, n, np.nan
    r = float(np.corrcoef(a, b)[0, 1])
    rc = max(min(r, 0.999999), -0.999999)
    z = np.arctanh(rc)
    se = 1.0 / np.sqrt(n - 3)
    from math import erf, sqrt
    p = float(2 * (1 - 0.5 * (1 + erf(abs(z / se) / sqrt(2)))))
    return r, n, p


def permutation_test(a, b, n_perm=2000, seed=20260623):
    """Null distribution of r under random re-pairing of b relative to a."""
    a = np.asarray(a, float); b = np.asarray(b, float)
    mask = ~(np.isnan(a) | np.isnan(b))
    a, b = a[mask], b[mask]
    real_r = float(np.corrcoef(a, b)[0, 1])
    rng = np.random.default_rng(seed)
    perm_rs = np.empty(n_perm)
    for i in range(n_perm):
        b_shuf = rng.permutation(b)
        perm_rs[i] = np.corrcoef(a, b_shuf)[0, 1]
    p_value = float((np.abs(perm_rs) >= abs(real_r)).mean())
    return real_r, perm_rs, p_value


# ---------------------------------------------------------------------------
# Independent data loading + pivot/leg reconstruction
# ---------------------------------------------------------------------------

def load_5m_bars(engine, ticker: str) -> pd.DataFrame:
    df = pd.read_sql(
        text("SELECT ticker, ts, open, high, low, close, volume FROM intraday_bars "
             "WHERE ticker = :t AND timeframe = '5m' ORDER BY ts"),
        engine, params={"t": ticker},
    )
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    return df.reset_index(drop=True)


def significant_pivots(piv: list[Pivot], atr: np.ndarray, amp_mult: float = AMP_MULT) -> list[Pivot]:
    """Independent re-implementation, byte-for-byte logic check against
    dome_leg_signature_common.significant_pivots -- intentionally written
    fresh here rather than imported, so a bug in the original isn't blindly
    re-used by the verifier."""
    out, last_opp_price = [], None
    for p in piv:
        if last_opp_price is not None and not np.isnan(atr[p.idx]) and atr[p.idx] > 0:
            if abs(p.price - last_opp_price) >= amp_mult * atr[p.idx]:
                out.append(p)
        last_opp_price = p.price
    return out


@dataclass
class LegRecord:
    ticker: str
    leg_dir: str
    a_idx: int
    b_idx: int
    c_idx: int | None
    leg_amp: float
    leg_bars: int
    corr_depth: float | None
    corr_bars: int | None
    # CHECK 1 variants
    early_gain_naive: float        # original definition: window starts AT a.idx
    early_bars_naive: int
    remaining_amp_naive: float | None   # b vs close[e_end] -- disjoint-in-accounting version
    # CHECK 2 variant: window starts at CONFIRMATION bar (a.idx + width), not a.idx
    early_gain_confirmed: float | None
    early_bars_confirmed: int | None
    remaining_amp_confirmed: float | None
    # trivial baseline: single-bar move right after the start
    first_bar_move: float
    in_sample: bool


def build_legs_with_variants(ticker: str, sig_pivots: list[Pivot], close: np.ndarray,
                              open_: np.ndarray, n_bars_total: int, in_sample_mask: np.ndarray,
                              early_n: int = EARLY_N, width: int = PIVOT_WIDTH) -> list[LegRecord]:
    legs = []
    n = len(close)
    for i in range(len(sig_pivots) - 1):
        a, b = sig_pivots[i], sig_pivots[i + 1]
        if a.kind == "L" and b.kind == "H":
            leg_dir = "up"
        elif a.kind == "H" and b.kind == "L":
            leg_dir = "down"
        else:
            continue
        if a.price <= 0 or b.price <= 0:
            continue

        leg_amp = abs(b.price - a.price) / a.price
        leg_bars = b.idx - a.idx
        if leg_bars <= early_n:
            continue  # non-tautological filter applied UPFRONT in this verifier (not optional)

        c = sig_pivots[i + 2] if i + 2 < len(sig_pivots) else None
        corr_depth = corr_bars = None
        if c is not None:
            if leg_dir == "up" and c.kind == "L":
                corr_depth = (b.price - c.price) / b.price
                corr_bars = c.idx - b.idx
            elif leg_dir == "down" and c.kind == "H":
                corr_depth = (c.price - b.price) / b.price
                corr_bars = c.idx - b.idx

        # ---- naive (original) early window: starts AT a.idx ---------------
        e_end = a.idx + early_n  # guaranteed < b.idx since leg_bars > early_n
        if leg_dir == "up":
            early_gain_naive = (close[e_end] - a.price) / a.price
            remaining_amp_naive = (b.price - close[e_end]) / close[e_end] if close[e_end] > 0 else None
        else:
            early_gain_naive = (a.price - close[e_end]) / a.price
            remaining_amp_naive = (close[e_end] - b.price) / close[e_end] if close[e_end] > 0 else None

        # ---- CHECK 2: window starts at the CONFIRMATION bar (a.idx+width) -
        conf_idx = a.idx + width
        early_gain_confirmed = remaining_amp_confirmed = None
        if conf_idx < b.idx and conf_idx + early_n < b.idx and conf_idx < n:
            conf_price = close[conf_idx]
            e_end2 = conf_idx + early_n
            if conf_price > 0:
                if leg_dir == "up":
                    early_gain_confirmed = (close[e_end2] - conf_price) / conf_price
                    remaining_amp_confirmed = (b.price - close[e_end2]) / close[e_end2] if close[e_end2] > 0 else None
                else:
                    early_gain_confirmed = (conf_price - close[e_end2]) / conf_price
                    remaining_amp_confirmed = (close[e_end2] - b.price) / close[e_end2] if close[e_end2] > 0 else None

        # ---- trivial baseline: the single bar right after the start -------
        nb = a.idx + 1
        if leg_dir == "up":
            first_bar_move = (close[nb] - open_[nb]) / open_[nb] if nb < n and open_[nb] > 0 else np.nan
        else:
            first_bar_move = (open_[nb] - close[nb]) / open_[nb] if nb < n and open_[nb] > 0 else np.nan

        legs.append(LegRecord(
            ticker=ticker, leg_dir=leg_dir, a_idx=a.idx, b_idx=b.idx, c_idx=(c.idx if c else None),
            leg_amp=leg_amp, leg_bars=leg_bars, corr_depth=corr_depth, corr_bars=corr_bars,
            early_gain_naive=early_gain_naive, early_bars_naive=early_n,
            remaining_amp_naive=remaining_amp_naive,
            early_gain_confirmed=early_gain_confirmed, early_bars_confirmed=(early_n if early_gain_confirmed is not None else None),
            remaining_amp_confirmed=remaining_amp_confirmed,
            first_bar_move=first_bar_move,
            in_sample=bool(in_sample_mask[a.idx]),
        ))
    return legs


def process_ticker(engine, ticker: str) -> list[LegRecord]:
    bars = load_5m_bars(engine, ticker)
    feat_df = compute_features(bars)
    h = feat_df["high"].to_numpy(float); l = feat_df["low"].to_numpy(float)
    c = feat_df["close"].to_numpy(float); o = feat_df["open"].to_numpy(float)
    atr = feat_df["atr14"].to_numpy(float)
    n = len(c)
    in_sample_mask = np.arange(n) < int(n * TRAIN_FRACTION)

    piv = swing_pivots(h, l, width=PIVOT_WIDTH)
    sig = significant_pivots(piv, atr, AMP_MULT)
    legs = build_legs_with_variants(ticker, sig, c, o, n, in_sample_mask)
    return legs


def legs_to_df(legs: list[LegRecord]) -> pd.DataFrame:
    return pd.DataFrame([vars(l) for l in legs])


# ---------------------------------------------------------------------------
# CHECK 4: recompute the original report's headline numbers from raw rows
# ---------------------------------------------------------------------------

def check4_recompute_from_raw(engine) -> dict:
    out = {}
    df = pd.read_sql(text("SELECT * FROM research_dome_leg_signature "
                           "WHERE run_id = '20260621T225140Z-93e39c70'"), engine)
    for leg_dir in ("up", "down"):
        sub = df[df["leg_dir"] == leg_dir]
        long_legs = sub[sub["leg_bars"] > EARLY_N]
        cell = {}
        for portion_name, flag in (("in_sample", True), ("held_out", False)):
            p = long_legs[long_legs["in_sample_flag"] == flag]
            r, n, pval = pearson_p(p["early_gain"], p["leg_amp"])
            r2, n2, pval2 = pearson_p(p["early_slope"], p["corr_depth"])
            cell[portion_name] = {"n": n, "r_early_leg_amp": r, "p": pval,
                                   "n_corr": n2, "r_early_slope_corr_depth": r2, "p_corr": pval2}
        out[leg_dir] = cell

    df10 = pd.read_sql(text("SELECT * FROM research_dome_leg_signature "
                             "WHERE run_id = '20260622T004346Z-75e29887'"), engine)
    out["10stock"] = {}
    for leg_dir in ("up", "down"):
        sub = df10[df10["leg_dir"] == leg_dir]
        long_legs = sub[sub["leg_bars"] > EARLY_N]
        cell = {}
        for portion_name, flag in (("in_sample", True), ("held_out", False)):
            p = long_legs[long_legs["in_sample_flag"] == flag]
            r, n, pval = pearson_p(p["early_gain"], p["leg_amp"])
            cell[portion_name] = {"n": n, "r_early_leg_amp": r, "p": pval}
        out["10stock"][leg_dir] = cell

    # in-sample/held-out split sanity: confirm chronological, non-overlapping by ticker
    raw3 = pd.read_sql(text("SELECT ticker, start_ts, in_sample_flag FROM research_dome_leg_signature "
                             "WHERE run_id = '20260621T225140Z-93e39c70' ORDER BY ticker, start_ts"), engine)
    split_check = {}
    for ticker, g in raw3.groupby("ticker"):
        is_max = g[g["in_sample_flag"]]["start_ts"].max()
        ho_min = g[~g["in_sample_flag"]]["start_ts"].min()
        split_check[ticker] = {"in_sample_max_ts": str(is_max), "held_out_min_ts": str(ho_min),
                                "clean_chronological": bool(pd.isna(is_max) or pd.isna(ho_min) or is_max <= ho_min)}
    out["split_sanity"] = split_check
    return out


def main():
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)

    print("=" * 78)
    print("Loading legs (non-tautological, leg_bars > EARLY_N only) for original 3 + fresh 5 ...")
    print("=" * 78)
    all_legs = {}
    for ticker in ORIGINAL_3 + FRESH_5:
        legs = process_ticker(engine, ticker)
        all_legs[ticker] = legs
        print(f"  {ticker}: {len(legs)} non-tautological legs")

    results = {"timestamp_utc": datetime.now(timezone.utc).isoformat()}

    # ================= CHECK 1 =================================================
    print("\n" + "=" * 78 + "\nCHECK 1 -- tautology / accounting overlap\n" + "=" * 78)
    check1 = {}
    for scope, tickers in [("original_3", ORIGINAL_3), ("fresh_5", FRESH_5)]:
        df = legs_to_df([l for t in tickers for l in all_legs[t]])
        cell = {}
        for leg_dir in ("up", "down"):
            sub = df[df["leg_dir"] == leg_dir]
            r_naive, n_naive, p_naive = pearson_p(sub["early_gain_naive"], sub["leg_amp"])
            valid_rem = sub.dropna(subset=["remaining_amp_naive"])
            r_disjoint, n_disjoint, p_disjoint = pearson_p(valid_rem["early_gain_naive"], valid_rem["remaining_amp_naive"])
            cell[leg_dir] = {
                "r_early_vs_TOTAL_leg_amp": r_naive, "n": n_naive, "p": p_naive,
                "r_early_vs_REMAINING_amp_disjoint": r_disjoint, "n_disjoint": n_disjoint, "p_disjoint": p_disjoint,
            }
            print(f"  [{scope}] {leg_dir}-leg: r(early, TOTAL leg_amp)={r_naive:.3f} (n={n_naive})   "
                  f"r(early, REMAINING amp, disjoint)={r_disjoint:.3f} (n={n_disjoint})")
        check1[scope] = cell
    results["check1_tautology"] = check1

    # ================= CHECK 2 =================================================
    print("\n" + "=" * 78 + "\nCHECK 2 -- look-ahead in pivot confirmation timing\n" + "=" * 78)
    check2 = {}
    for scope, tickers in [("original_3", ORIGINAL_3), ("fresh_5", FRESH_5)]:
        df = legs_to_df([l for t in tickers for l in all_legs[t]])
        cell = {}
        for leg_dir in ("up", "down"):
            sub = df[df["leg_dir"] == leg_dir].dropna(subset=["early_gain_confirmed", "remaining_amp_confirmed"])
            r_total, n_total, p_total = pearson_p(sub["early_gain_confirmed"],
                                                     sub["early_gain_confirmed"] + sub["remaining_amp_confirmed"])
            r_disjoint, n_disjoint, p_disjoint = pearson_p(sub["early_gain_confirmed"], sub["remaining_amp_confirmed"])
            cell[leg_dir] = {
                "n": n_disjoint,
                "r_confirmed_early_vs_remaining_disjoint": r_disjoint, "p_disjoint": p_disjoint,
            }
            print(f"  [{scope}] {leg_dir}-leg (window starts at confirmation, a.idx+{PIVOT_WIDTH}): "
                  f"r(early, REMAINING amp, disjoint)={r_disjoint:.3f} (n={n_disjoint})")
        check2[scope] = cell
    results["check2_lookahead"] = check2

    # ================= CHECK 3 =================================================
    print("\n" + "=" * 78 + "\nCHECK 3 -- permutation null model + trivial baseline\n" + "=" * 78)
    check3 = {}
    for scope, tickers in [("original_3", ORIGINAL_3), ("fresh_5", FRESH_5)]:
        df = legs_to_df([l for t in tickers for l in all_legs[t]])
        cell = {}
        for leg_dir in ("up", "down"):
            sub = df[df["leg_dir"] == leg_dir]
            valid = sub.dropna(subset=["remaining_amp_naive"])
            real_r, perm_rs, perm_p = permutation_test(valid["early_gain_naive"], valid["remaining_amp_naive"], n_perm=2000)
            r_trivial, n_trivial, p_trivial = pearson_p(sub["first_bar_move"], sub["leg_amp"])
            r_trivial_rem, n_trivial_rem, p_trivial_rem = pearson_p(
                sub.dropna(subset=["remaining_amp_naive"])["first_bar_move"],
                sub.dropna(subset=["remaining_amp_naive"])["remaining_amp_naive"])
            cell[leg_dir] = {
                "real_r_disjoint": real_r, "perm_null_mean": float(perm_rs.mean()), "perm_null_std": float(perm_rs.std()),
                "perm_p_value": perm_p,
                "trivial_baseline_r_first_bar_vs_TOTAL_leg_amp": r_trivial, "n_trivial": n_trivial,
                "trivial_baseline_r_first_bar_vs_REMAINING_amp": r_trivial_rem, "n_trivial_rem": n_trivial_rem,
            }
            print(f"  [{scope}] {leg_dir}-leg: real_r(disjoint)={real_r:.3f}  perm_null=N({perm_rs.mean():.4f},{perm_rs.std():.4f})  "
                  f"perm_p={perm_p:.4f}  trivial(1st bar vs TOTAL)={r_trivial:.3f}  trivial(1st bar vs REMAINING)={r_trivial_rem:.3f}")
        check3[scope] = cell
    results["check3_permutation_and_baseline"] = check3

    # ================= CHECK 4 =================================================
    print("\n" + "=" * 78 + "\nCHECK 4 -- recompute prior report's headline numbers from raw DB rows\n" + "=" * 78)
    check4 = check4_recompute_from_raw(engine)
    for leg_dir in ("up", "down"):
        for portion in ("in_sample", "held_out"):
            d = check4[leg_dir][portion]
            print(f"  [3-stock,{leg_dir},{portion}] r(early_gain,leg_amp)={d['r_early_leg_amp']:.3f} (n={d['n']})  "
                  f"r(early_slope,corr_depth)={d['r_early_slope_corr_depth']:.3f} (n={d['n_corr']})")
    print("  split sanity (is in-sample strictly before held-out, per ticker):")
    for t, s in check4["split_sanity"].items():
        print(f"    {t}: {s}")
    results["check4_recompute"] = check4

    out_path = REPORTS_DIR / "dome_leg_verify_results.json"
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nWrote {out_path}")

    return results, all_legs


if __name__ == "__main__":
    main()
