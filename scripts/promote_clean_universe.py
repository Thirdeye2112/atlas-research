"""
Gated, atomic promotion of a candidate clean-universe whitelist to the canonical path.

Single responsibility: take a freshly-computed candidate whitelist CSV (+ optional scan
metadata), validate it against a series of safety gates, and -- only if every gate passes
-- atomically replace the canonical whitelist, archiving the prior version first. If any
gate fails, the canonical file is left byte-for-byte untouched and the process exits
non-zero with a clear reason.

This exists so a scheduled (e.g. weekly) auto-regeneration of the whitelist cannot let a
bad or partial scan silently clobber a known-good canonical list that downstream backtests
depend on via settings.CLEAN_UNIVERSE_CSV.

This module knows nothing about the database or the audit's internals. It operates purely
on CSV files and a few numeric metadata inputs, so it stays decoupled from whatever the
upstream audit script looks like. The audit (or a weekly wrapper) computes a candidate and
calls this to promote it.

Gates (ALL must pass, else abort without touching canonical):
  1. Candidate parses: exactly one column named 'ticker', no nulls, no duplicates, >=1 row.
  2. Not degenerate: len(candidate) >= --min-tickers.
  3. Full-scan check (only if --scanned-tickers given): scanned >= --min-scanned. This is how
     a --limit smoke-test candidate gets rejected -- a partial scan reports few scanned tickers.
  4. Size drift vs current canonical: (1-max_shrink)*cur <= new <= (1+max_grow)*cur.
  5. Overlap vs current canonical: Jaccard(new, cur) >= --min-overlap.
  --force bypasses gates 2-5 (and 1's duplicate/null *hard-stops still apply* -- a malformed
  file is never promotable, see note below) but prints a loud warning, and still archives +
  swaps atomically.

On first-ever run (no existing canonical file): gates 4 and 5 are skipped (nothing to compare
against); gates 1-3 still apply.

Exit codes:
  0  promoted (or --force promoted)
  2  a gate failed; canonical untouched
  3  usage / IO error (missing candidate, unreadable, etc.)

Usage:
    python scripts/promote_clean_universe.py \
        --candidate reports/validity/2026-06-19/clean_universe.csv \
        --canonical config/clean_universe.csv \
        --scanned-tickers 6221
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
from datetime import date, datetime, timezone


EXIT_OK = 0
EXIT_GATE_FAILED = 2
EXIT_USAGE = 3


def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--candidate", required=True,
                    help="Path to the freshly-computed candidate whitelist CSV (single 'ticker' column).")
    p.add_argument("--canonical", default="config/clean_universe.csv",
                    help="Path to the canonical whitelist this promotes into (default: config/clean_universe.csv).")
    p.add_argument("--scanned-tickers", type=int, default=None,
                    help="How many tickers the upstream scan covered. If given, gate 3 enforces "
                         ">= --min-scanned so a --limit smoke test can't be promoted.")
    p.add_argument("--min-tickers", type=int, default=1000,
                    help="Gate 2: reject a candidate smaller than this (default: 1000).")
    p.add_argument("--min-scanned", type=int, default=5000,
                    help="Gate 3: minimum --scanned-tickers to count as a full-universe scan (default: 5000).")
    p.add_argument("--max-shrink", type=float, default=0.30,
                    help="Gate 4: max fractional shrink vs current canonical (default: 0.30 = 30%%).")
    p.add_argument("--max-grow", type=float, default=0.50,
                    help="Gate 4: max fractional growth vs current canonical (default: 0.50 = 50%%).")
    p.add_argument("--min-overlap", type=float, default=0.80,
                    help="Gate 5: minimum Jaccard overlap vs current canonical (default: 0.80).")
    p.add_argument("--archive-dir", default="config/clean_universe_history",
                    help="Where the prior canonical is archived before swap "
                         "(default: config/clean_universe_history).")
    p.add_argument("--force", action="store_true",
                    help="Bypass the drift/overlap/size gates (2-5) with a loud warning. A "
                         "structurally malformed candidate (gate 1) is NEVER promotable, even "
                         "with --force.")
    return p.parse_args(argv)


def _fail(msg: str, code: int = EXIT_GATE_FAILED) -> "NoReturn":  # type: ignore[name-defined]
    print(f"ABORT: {msg}", file=sys.stderr)
    print("Canonical whitelist left untouched.", file=sys.stderr)
    sys.exit(code)


def read_ticker_csv(path: str, *, label: str, strict: bool = True) -> list[str]:
    """
    Parse a single-column 'ticker' CSV. Returns the ordered list of tickers.

    strict=True (candidates): any structural problem -- bad header, multi-column row, null,
    or duplicate -- is a hard-stop via _fail (this is gate 1, and it applies even under
    --force). A candidate is never promotable if malformed.

    strict=False (the existing canonical): we must never let a pre-existing corrupted
    canonical brick the promote path (it would block even the --force rescue). So we tolerate
    duplicates (dedupe, preserving first-seen order) and skip blank lines, emitting warnings
    rather than failing. A genuinely unreadable/empty canonical is treated as "no canonical".
    """
    if not os.path.exists(path):
        _fail(f"{label} file does not exist: {path}", EXIT_USAGE)
    try:
        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            lines = [ln.rstrip("\r\n") for ln in f]
    except OSError as e:
        _fail(f"could not read {label} file {path}: {e}", EXIT_USAGE)

    # drop trailing blank lines
    while lines and lines[-1] == "":
        lines.pop()
    if not lines:
        _fail(f"{label} file is empty: {path}")

    header = lines[0].strip().lstrip("\ufeff")
    if header != "ticker":
        if strict:
            _fail(f"{label} must have a single column with header exactly 'ticker'; "
                  f"first line was {header!r}")
        print(f"WARNING: {label} header is {header!r}, not 'ticker'; treating first line as "
              f"header anyway.", file=sys.stderr)

    tickers: list[str] = []
    seen: set[str] = set()
    dups: set[str] = set()
    for i, raw in enumerate(lines[1:], start=2):
        val = raw.strip()
        if "," in raw:
            if strict:
                _fail(f"{label} line {i} looks multi-column (contains a comma): {raw!r}; "
                      f"expected a single 'ticker' column")
            print(f"WARNING: {label} line {i} multi-column; taking first field.", file=sys.stderr)
            val = raw.split(",")[0].strip()
        if val == "":
            if strict:
                _fail(f"{label} line {i} is a null/blank ticker")
            continue  # tolerate: skip blank canonical rows
        if val in seen:
            dups.add(val)
            if strict:
                pass  # collected and reported below
            else:
                continue  # tolerate: dedupe canonical
        seen.add(val)
        tickers.append(val)

    if dups and strict:
        sample = ", ".join(sorted(dups)[:10])
        _fail(f"{label} contains {len(dups)} duplicate ticker(s): {sample}"
              + (" ..." if len(dups) > 10 else ""))
    if dups and not strict:
        print(f"WARNING: {label} had {len(dups)} duplicate ticker(s); de-duplicated for "
              f"comparison.", file=sys.stderr)
    if not tickers:
        if strict:
            _fail(f"{label} has a header but no ticker rows: {path}")
        _fail(f"{label} has no usable ticker rows: {path}")
    return tickers


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 1.0


def atomic_replace_csv(canonical_path: str, tickers: list[str]) -> None:
    """
    Write the new whitelist to a temp file in the SAME directory as the canonical, fsync it,
    then os.replace() it into place. Same-dir temp guarantees the replace is a same-filesystem
    rename (atomic); a crash before the replace leaves the old canonical intact, and the
    replace itself is never partially-visible to a reader.
    """
    canon_dir = os.path.dirname(os.path.abspath(canonical_path)) or "."
    os.makedirs(canon_dir, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=".clean_universe_", suffix=".tmp", dir=canon_dir)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write("ticker\n")
            for t in tickers:
                f.write(f"{t}\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, canonical_path)  # atomic on POSIX and Windows for same-dir paths
        tmp_path = None
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


def archive_prior(canonical_path: str, archive_dir: str) -> str | None:
    """Copy the current canonical (if any) into archive_dir/clean_universe_YYYY-MM-DD.csv."""
    if not os.path.exists(canonical_path):
        return None
    os.makedirs(archive_dir, exist_ok=True)
    stamp = date.today().isoformat()
    dest = os.path.join(archive_dir, f"clean_universe_{stamp}.csv")
    # if run twice in one day, suffix with a counter so we never silently overwrite history
    if os.path.exists(dest):
        n = 1
        while os.path.exists(os.path.join(archive_dir, f"clean_universe_{stamp}_{n}.csv")):
            n += 1
        dest = os.path.join(archive_dir, f"clean_universe_{stamp}_{n}.csv")
    with open(canonical_path, "r", encoding="utf-8-sig") as src, \
         open(dest, "w", encoding="utf-8", newline="") as out:
        out.write(src.read())
    return dest


def main(argv=None) -> None:
    args = parse_args(argv)

    # --- Gate 1: candidate parses cleanly (hard-stop, applies even under --force) ---
    cand_list = read_ticker_csv(args.candidate, label="candidate")
    cand = set(cand_list)
    new_size = len(cand)

    canonical_exists = os.path.exists(args.canonical)
    cur: set[str] = set()
    cur_size = 0
    if canonical_exists:
        cur_list = read_ticker_csv(args.canonical, label="canonical", strict=False)
        cur = set(cur_list)
        cur_size = len(cur)

    print(f"[promote] candidate: {args.candidate} -> {new_size} tickers")
    if canonical_exists:
        print(f"[promote] current canonical: {args.canonical} -> {cur_size} tickers")
    else:
        print(f"[promote] no existing canonical at {args.canonical} (first-ever run; "
              f"drift/overlap gates skipped)")

    gate_failures: list[str] = []

    # --- Gate 2: not degenerate ---
    if new_size < args.min_tickers:
        gate_failures.append(
            f"[gate2/min-tickers] candidate has {new_size} tickers, below floor {args.min_tickers}")

    # --- Gate 3: full-universe scan, not a smoke test ---
    if args.scanned_tickers is not None:
        if args.scanned_tickers < args.min_scanned:
            gate_failures.append(
                f"[gate3/min-scanned] scan covered {args.scanned_tickers} tickers, below "
                f"{args.min_scanned} -- looks like a --limit smoke test, not a full scan")
    else:
        print("[promote] note: --scanned-tickers not provided; gate 3 (full-scan check) skipped")

    overlap = None
    if canonical_exists:
        # --- Gate 4: size drift ---
        lo = (1.0 - args.max_shrink) * cur_size
        hi = (1.0 + args.max_grow) * cur_size
        if new_size < lo:
            shrink_pct = (1 - new_size / cur_size) * 100 if cur_size else 0
            gate_failures.append(
                f"[gate4/shrink] candidate ({new_size}) is {shrink_pct:.1f}% smaller than "
                f"current ({cur_size}); max allowed shrink is {args.max_shrink:.0%} "
                f"(floor {lo:.0f})")
        if new_size > hi:
            grow_pct = (new_size / cur_size - 1) * 100 if cur_size else 0
            gate_failures.append(
                f"[gate4/grow] candidate ({new_size}) is {grow_pct:.1f}% larger than current "
                f"({cur_size}); max allowed growth is {args.max_grow:.0%} (ceiling {hi:.0f})")

        # --- Gate 5: overlap ---
        overlap = jaccard(cand, cur)
        if overlap < args.min_overlap:
            gate_failures.append(
                f"[gate5/overlap] Jaccard overlap with current canonical is {overlap:.3f}, "
                f"below {args.min_overlap:.2f} -- candidate is suspiciously different "
                f"({len(cand & cur)} shared / {len(cand | cur)} union)")

    if gate_failures:
        print()
        for fl in gate_failures:
            print("  " + fl, file=sys.stderr)
        if args.force:
            print()
            print("=" * 70, file=sys.stderr)
            print("WARNING: --force set. Bypassing the above gate failure(s) and promoting "
                  "anyway.", file=sys.stderr)
            print("This overrides safety checks designed to stop a bad/partial scan from "
                  "clobbering a good whitelist. Make sure this is intentional.", file=sys.stderr)
            print("=" * 70, file=sys.stderr)
        else:
            print()
            _fail(f"{len(gate_failures)} gate(s) failed (see above). Re-run with --force to "
                  f"override if this is intentional.")

    # --- All gates passed (or forced): archive + atomic swap ---
    archived = archive_prior(args.canonical, args.archive_dir)
    atomic_replace_csv(args.canonical, cand_list)

    print()
    print("=" * 70)
    print("PROMOTED" + (" (FORCED)" if (gate_failures and args.force) else ""))
    print(f"  canonical:   {args.canonical}")
    if canonical_exists:
        drift = (new_size / cur_size - 1) * 100 if cur_size else float("nan")
        print(f"  size:        {cur_size} -> {new_size}  ({drift:+.1f}%)")
        if overlap is not None:
            print(f"  overlap:     {overlap:.3f} Jaccard  "
                  f"({len(cand & cur)} shared, {len(cand - cur)} added, {len(cur - cand)} dropped)")
    else:
        print(f"  size:        (bootstrap) -> {new_size}")
    if archived:
        print(f"  archived:    prior canonical -> {archived}")
    print(f"  timestamp:   {datetime.now(timezone.utc).isoformat()}")
    print("=" * 70)
    sys.exit(EXIT_OK)


if __name__ == "__main__":
    main()
