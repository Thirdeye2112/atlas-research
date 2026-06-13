"""
atlas_research.transcripts.hypothesis_pipeline
-------------------------------------------------
Rule-based transcript → hypothesis extractor.

Converts natural-language claims into structured research_hypotheses rows
without requiring an API call.  Complements the Claude-based extractor.py
for cases where patterns are recognizable and an API key is unavailable.

Usage
-----
    from atlas_research.transcripts.hypothesis_pipeline import (
        ingest_text,
        ingest_file,
        print_extracted,
    )

    # Parse a block of text
    hypotheses = ingest_text(
        text="Markets rarely drop 4 days straight. Gap-downs over 1% usually bounce.",
        source_title="Manual claim set",
    )
    print_extracted(hypotheses)

    # Parse a file
    hypotheses = ingest_file("/path/to/notes.txt")

Supported patterns
------------------
  "down N days [in a row]"     → down_streak n=N (SPY)
  "up N days [in a row]"       → up_streak   n=N (SPY)
  "gap down [over|above] X%"   → gap_down  threshold_pct=X
  "gap up   [over|above] X%"   → gap_up    threshold_pct=X
  "[hammer|shooting star|doji|engulfing|inside day|outside day]"
                                → candle pattern (SPY)
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from pathlib import Path
from typing import Optional

from sqlalchemy import text

from atlas_research.db.connection import get_connection


# ── Pattern registry ──────────────────────────────────────────────────────────

def _streak_extractor(direction: str):
    """Return an extractor for down/up streaks."""
    def extract(m: re.Match, sentence: str) -> Optional[dict]:
        n = int(m.group("n"))
        if not (2 <= n <= 10):
            return None
        ctype = f"{direction}_streak"
        claim = (
            f"After {n} consecutive {'down' if direction=='down' else 'up'} days "
            f"in the S&P, what tends to happen?"
        )
        return {
            "extracted_claim": claim,
            "source_text": sentence.strip(),
            "market_object": "SPY",
            "condition": ctype,
            "condition_params": {"n": n},
            "target": "forward return",
            "horizons": [1, 5, 10, 20],
            "direction": "bullish" if direction == "down" else "bearish",
        }
    return extract


def _gap_extractor(direction: str):
    """Return an extractor for gap-down/up patterns."""
    def extract(m: re.Match, sentence: str) -> Optional[dict]:
        threshold = float(m.group("pct").replace(",", "."))
        if not (0.1 <= threshold <= 20):
            return None
        ctype = f"gap_{direction}"
        arrow = "down" if direction == "down" else "up"
        claim = (
            f"After SPY gaps {arrow} more than {threshold}%, "
            f"what tends to happen?"
        )
        return {
            "extracted_claim": claim,
            "source_text": sentence.strip(),
            "market_object": "SPY",
            "condition": ctype,
            "condition_params": {"threshold_pct": threshold},
            "target": "forward return",
            "horizons": [1, 5, 10, 20],
            "direction": "bullish" if direction == "down" else "bearish",
        }
    return extract


def _candle_extractor(pattern: str, direction: str):
    """Return an extractor for a named candlestick pattern."""
    def extract(m: re.Match, sentence: str) -> Optional[dict]:
        claim = f"After a {pattern.replace('_', ' ')} candlestick, what tends to happen?"
        return {
            "extracted_claim": claim,
            "source_text": sentence.strip(),
            "market_object": "SPY",
            "condition": "candle",
            "condition_params": {"pattern": pattern},
            "target": "forward return",
            "horizons": [1, 5, 10],
            "direction": direction,
        }
    return extract


PATTERNS: list[tuple[re.Pattern, callable]] = [
    # "down 4 days", "dropped 3 days", "drops 5 days in a row", "fell 4 days"
    (re.compile(
        r"(?:down|drops?|dropped?|fell?|declin(?:ed?|ing))\s+(?P<n>[2-9]|10)\s+(?:day|session)s?",
        re.IGNORECASE,
    ), _streak_extractor("down")),
    # "3 consecutive down days", "4 straight down sessions"
    (re.compile(
        r"(?P<n>[2-9]|10)\s+(?:consecutive|straight)\s+down\s+(?:day|session)s?",
        re.IGNORECASE,
    ), _streak_extractor("down")),
    # "bounce after 3 down days" / "3 down days"
    (re.compile(
        r"(?P<n>[2-9]|10)\s+(?:consecutive\s+)?down\s+(?:day|session)s?",
        re.IGNORECASE,
    ), _streak_extractor("down")),
    # up streaks
    (re.compile(
        r"(?:up|rose?|gained?|ral(?:ly|lied?)|rallied|rallying)\s+(?P<n>[2-9]|10)\s+(?:day|session)s?",
        re.IGNORECASE,
    ), _streak_extractor("up")),
    (re.compile(
        r"(?P<n>[2-9]|10)\s+(?:consecutive|straight)\s+up\s+(?:day|session)s?",
        re.IGNORECASE,
    ), _streak_extractor("up")),
    # gap down/up: "gap down 1%", "gaps down over 2 percent", "gapped down over 1%"
    (re.compile(
        r"gap(?:ped?|s?)\s+down\s+(?:over|above|more\s+than)?\s*"
        r"(?P<pct>\d+(?:[.,]\d+)?)\s*(?:%|percent)",
        re.IGNORECASE,
    ), _gap_extractor("down")),
    (re.compile(
        r"gap(?:ped?|s?)\s+up\s+(?:over|above|more\s+than)?\s*"
        r"(?P<pct>\d+(?:[.,]\d+)?)\s*(?:%|percent)",
        re.IGNORECASE,
    ), _gap_extractor("up")),
    # Candlestick patterns (fire on any mention)
    (re.compile(r"\bhammer\b", re.IGNORECASE),
     _candle_extractor("hammer", "bullish")),
    (re.compile(r"\bshooting\s+star\b", re.IGNORECASE),
     _candle_extractor("shooting_star", "bearish")),
    (re.compile(r"\bdoji\b", re.IGNORECASE),
     _candle_extractor("doji", "neutral")),
    (re.compile(r"\bbullish\s+engulf(?:ing)?\b", re.IGNORECASE),
     _candle_extractor("bullish_engulfing", "bullish")),
    (re.compile(r"\bbearish\s+engulf(?:ing)?\b", re.IGNORECASE),
     _candle_extractor("bearish_engulfing", "bearish")),
    (re.compile(r"\binside\s+day\b", re.IGNORECASE),
     _candle_extractor("inside_day", "neutral")),
    (re.compile(r"\boutside\s+day\b", re.IGNORECASE),
     _candle_extractor("outside_day", "neutral")),
]


# ── Text chunking ─────────────────────────────────────────────────────────────

def _sentences(text: str) -> list[str]:
    """Split text into sentence-like segments."""
    return [s.strip() for s in re.split(r"[.!?\n]+", text) if len(s.strip()) > 10]


# ── Core extraction ───────────────────────────────────────────────────────────

def extract_from_text(text: str) -> list[dict]:
    """
    Apply all patterns to text and return a list of hypothesis dicts.
    Deduplicates by (condition, condition_params).
    """
    sentences = _sentences(text)
    seen: set[str] = set()
    results: list[dict] = []

    for sentence in sentences:
        for pattern, extractor in PATTERNS:
            m = pattern.search(sentence)
            if not m:
                continue
            hyp = extractor(m, sentence)
            if hyp is None:
                continue

            key = json.dumps(
                {"c": hyp["condition"], "p": hyp["condition_params"]},
                sort_keys=True,
            )
            if key in seen:
                continue
            seen.add(key)
            results.append(hyp)

    return results


# ── DB persistence ────────────────────────────────────────────────────────────

def _ensure_source(
    source_id: str,
    title: str,
    source_type: str = "manual",
    event_date: Optional[str] = None,
) -> str:
    """Upsert a transcript_sources row and return source_id."""
    with get_connection() as conn:
        conn.execute(text("""
            INSERT INTO transcript_sources
                (source_id, file_path, source_type, title, event_date, processed_at)
            VALUES (:sid, :fp, :st, :title, :date, now())
            ON CONFLICT (source_id) DO NOTHING
        """), {
            "sid":   source_id,
            "fp":    f"manual:{source_id}",
            "st":    source_type,
            "title": title,
            "date":  event_date,
        })
    return source_id


def _save_hypotheses(source_id: str, hypotheses: list[dict]) -> list[str]:
    """Insert extracted hypotheses. Returns list of hypothesis_ids created."""
    created: list[str] = []
    with get_connection() as conn:
        for hyp in hypotheses:
            hyp_id = "h-" + hashlib.sha1(
                json.dumps({
                    "source": source_id,
                    "cond": hyp["condition"],
                    "params": hyp["condition_params"],
                }, sort_keys=True).encode()
            ).hexdigest()[:12]

            conn.execute(text("""
                INSERT INTO research_hypotheses
                    (hypothesis_id, source_id, source_text, extracted_claim,
                     market_object, condition, condition_params,
                     target, horizons, direction, test_status)
                VALUES
                    (:hid, :sid, :src_text, :claim,
                     :obj, :cond, :params,
                     :target, :horizons, :direction, 'queued')
                ON CONFLICT (hypothesis_id) DO NOTHING
            """), {
                "hid":       hyp_id,
                "sid":       source_id,
                "src_text":  hyp["source_text"],
                "claim":     hyp["extracted_claim"],
                "obj":       hyp.get("market_object"),
                "cond":      hyp.get("condition"),
                "params":    json.dumps(hyp.get("condition_params", {})),
                "target":    hyp.get("target"),
                "horizons":  hyp.get("horizons"),
                "direction": hyp.get("direction"),
            })
            created.append(hyp_id)

    return created


# ── Public API ────────────────────────────────────────────────────────────────

def ingest_text(
    text: str,
    source_title: str = "Manual input",
    source_type: str = "manual",
    event_date: Optional[str] = None,
    save: bool = True,
) -> list[dict]:
    """
    Extract hypotheses from a text string and optionally persist to DB.

    Returns list of extracted hypothesis dicts (same shape as extract_from_text).
    """
    hypotheses = extract_from_text(text)
    if not hypotheses or not save:
        return hypotheses

    source_id = "src-" + hashlib.sha1(
        (source_title + (event_date or "")).encode()
    ).hexdigest()[:12]
    _ensure_source(source_id, source_title, source_type, event_date)
    ids = _save_hypotheses(source_id, hypotheses)

    for hyp, hid in zip(hypotheses, ids):
        hyp["hypothesis_id"] = hid
        hyp["source_id"]     = source_id

    return hypotheses


def ingest_file(
    path: str,
    source_title: Optional[str] = None,
    source_type: str = "manual",
    event_date: Optional[str] = None,
    save: bool = True,
) -> list[dict]:
    """Extract hypotheses from a text file."""
    p = Path(path)
    text = p.read_text(encoding="utf-8", errors="replace")
    title = source_title or p.name
    return ingest_text(text, source_title=title, source_type=source_type,
                       event_date=event_date, save=save)


# ── Console output ────────────────────────────────────────────────────────────

def print_extracted(hypotheses: list[dict]) -> None:
    """Print a summary of extracted hypotheses."""
    if not hypotheses:
        print("  No hypotheses extracted.")
        return

    print(f"  Extracted {len(hypotheses)} hypothesis(es):")
    for i, h in enumerate(hypotheses, 1):
        params = h.get("condition_params", {})
        print(
            f"  {i:>2}. [{h.get('condition'):<15} {str(params):<20}] "
            f"{h['extracted_claim'][:70]}"
        )
