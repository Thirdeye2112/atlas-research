"""
atlas_research.transcripts.extractor
=====================================
Parses transcript source files (.jsonl or plain text), chunks them into
semantic units, then calls the Claude API to extract structured research
hypotheses from each chunk.

Each extracted hypothesis becomes a row in research_hypotheses with a
fully structured test specification ready for automated backtesting.

Usage
-----
    from atlas_research.transcripts.extractor import TranscriptExtractor
    ext = TranscriptExtractor()
    ext.process_file("/path/to/call.jsonl")
    ext.process_directory("/path/to/transcripts/")
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import textwrap
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Any

import structlog

from atlas_research.db.connection import get_connection
from config import settings

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
CHUNK_SIZE_CHARS = 1_500          # target chunk size
CHUNK_OVERLAP_CHARS = 200         # overlap between adjacent chunks
MIN_CHUNK_CHARS = 100             # skip tiny fragments
MAX_HYPOTHESES_PER_CHUNK = 5      # cap Claude's output per chunk

# Promotion thresholds (used later by backtester; stored here for reference)
MIN_SAMPLE_SIZE = 20              # minimum events to be testable
MIN_HIT_RATE_THRESHOLD = 0.55     # must beat coin flip by 5pp
MIN_P_VALUE_THRESHOLD = 0.10      # lenient: this is idea generation, not trading

SYSTEM_PROMPT = textwrap.dedent("""
You are a quantitative research assistant for an equity research database.

Your job is to extract EVERY trading-relevant claim from the provided transcript
chunk — both explicit predictions and implicit market observations.

For EACH claim, produce a JSON object with this exact structure:
{
  "source_text": "verbatim quote or very close paraphrase",
  "extracted_claim": "clean one-sentence statement of the claim",
  "market_object": "SPY | QQQ | <TICKER> | sector_name | universe | null",
  "condition": "snake_case descriptor of the trigger condition",
  "condition_params": {"key": value, ...},
  "target": "forward_return_1d | forward_return_5d | forward_return_20d | hit_rate | volatility",
  "horizons": [1, 5],
  "direction": "mean_reversion_long | momentum_long | momentum_short | mean_reversion_short | volatility_expansion | neutral",
  "regime_filter": "bull_only | bear_only | high_vol | low_vol | null",
  "sector_filter": "technology | financials | energy | null",
  "confidence_prior": 0.0 to 1.0
}

Rules:
- Extract BOTH explicit ("SPY is never down 5 days in a row") AND implicit
  observations ("liquidity was thin so the move was probably noise").
- If the claim is about a single ticker, use that ticker for market_object.
- If the claim is about the broad market, use SPY or QQQ.
- If the claim is cross-sectional ("momentum stocks outperform"), use "universe".
- condition_params must be a valid JSON object. Use {} if no parameters.
- confidence_prior: 0.9 if speaker has historical accuracy, 0.5 if speculative.
- Return ONLY a JSON array. No markdown, no explanation, no preamble.
- If there are no testable claims, return [].
""").strip()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _source_hash(path: Path) -> str:
    """Deterministic source_id from file path + modification time."""
    mtime = int(path.stat().st_mtime)
    raw = f"{path.resolve()}:{mtime}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def _chunk_text(text: str) -> list[dict]:
    """
    Split text into overlapping chunks. Returns list of
    {'chunk_index': int, 'chunk_text': str, 'char_start': int, 'char_end': int}.
    """
    chunks = []
    idx = 0
    chunk_index = 0
    length = len(text)

    while idx < length:
        end = min(idx + CHUNK_SIZE_CHARS, length)
        # Try to break at sentence boundary
        if end < length:
            for sep in (". ", ".\n", "\n\n", "\n"):
                pos = text.rfind(sep, idx + MIN_CHUNK_CHARS, end)
                if pos != -1:
                    end = pos + len(sep)
                    break

        chunk = text[idx:end].strip()
        if len(chunk) >= MIN_CHUNK_CHARS:
            chunks.append({
                "chunk_index": chunk_index,
                "chunk_text": chunk,
                "char_start": idx,
                "char_end": end,
            })
            chunk_index += 1

        idx = end - CHUNK_OVERLAP_CHARS
        if idx >= length:
            break

    return chunks


def _parse_jsonl(path: Path) -> tuple[str, str | None, date | None, list[str]]:
    """
    Parse a .jsonl transcript file.
    Expected format: one JSON object per line with keys:
        text, speaker (optional), date (optional), tickers (optional)
    Returns (full_text, title, event_date, tickers).
    """
    lines = []
    title = path.stem
    event_date: date | None = None
    tickers: list[str] = []

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                text = obj.get("text", "")
                speaker = obj.get("speaker", "")
                if speaker:
                    text = f"{speaker}: {text}"
                lines.append(text)
                if not event_date and obj.get("date"):
                    try:
                        event_date = date.fromisoformat(str(obj["date"])[:10])
                    except ValueError:
                        pass
                if obj.get("tickers"):
                    tickers.extend(obj["tickers"])
            except json.JSONDecodeError:
                # Treat line as plain text
                lines.append(line)

    return "\n".join(lines), title, event_date, list(set(tickers))


def _parse_plain(path: Path) -> tuple[str, str | None, date | None, list[str]]:
    """Parse plain text / markdown transcripts."""
    text = path.read_text(encoding="utf-8", errors="replace")
    # Try to extract a date from the first 200 chars
    event_date = None
    m = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", text[:200])
    if m:
        try:
            event_date = date.fromisoformat(m.group(1))
        except ValueError:
            pass
    # Extract uppercase ticker-like tokens mentioned in the text
    tickers = list(set(re.findall(r"\b([A-Z]{1,5})\b", text[:2000])))[:20]
    return text, path.stem, event_date, tickers


def _call_claude(chunk_text: str) -> list[dict]:
    """
    Call Claude claude-sonnet-4-20250514 to extract hypotheses from a chunk.
    Returns list of raw hypothesis dicts (pre-validation).
    Falls back gracefully on API errors.
    """
    try:
        import anthropic
        client = anthropic.Anthropic()
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": f"Extract all testable trading claims from this transcript chunk:\n\n{chunk_text}"
            }]
        )
        raw = message.content[0].text.strip()
        # Strip markdown code fences if present
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return parsed[:MAX_HYPOTHESES_PER_CHUNK]
        if isinstance(parsed, dict):
            return [parsed]
        return []
    except Exception as exc:
        log.warning("extractor.claude_call_failed", error=str(exc))
        return []


def _validate_hypothesis(h: dict) -> bool:
    """Basic validation — must have claim and market_object at minimum."""
    return bool(h.get("extracted_claim")) and bool(h.get("market_object"))


def _to_db_record(
    h: dict,
    source_id: str,
    chunk_db_id: int,
) -> dict:
    """Convert raw extraction dict to DB insert record."""
    # Normalise fields
    horizons = h.get("horizons", [5])
    if isinstance(horizons, int):
        horizons = [horizons]
    horizons = [int(x) for x in horizons if x]

    params = h.get("condition_params", {}) or {}
    if not isinstance(params, dict):
        params = {}

    try:
        confidence = float(h.get("confidence_prior", 0.5))
        confidence = max(0.0, min(1.0, confidence))
    except (TypeError, ValueError):
        confidence = 0.5

    return {
        "hypothesis_id":    str(uuid.uuid4()),
        "source_id":        source_id,
        "chunk_id":         chunk_db_id,
        "source_text":      (h.get("source_text") or "")[:2000],
        "extracted_claim":  (h.get("extracted_claim") or "")[:1000],
        "market_object":    (h.get("market_object") or "universe")[:50],
        "condition":        (h.get("condition") or "unspecified")[:100],
        "condition_params": json.dumps(params),
        "target":           (h.get("target") or "forward_return_5d")[:100],
        "horizons":         horizons,
        "direction":        (h.get("direction") or "neutral")[:50],
        "regime_filter":    h.get("regime_filter"),
        "sector_filter":    h.get("sector_filter"),
        "confidence_prior": confidence,
        "test_status":      "queued",
    }


# ---------------------------------------------------------------------------
# Main extractor class
# ---------------------------------------------------------------------------

class TranscriptExtractor:
    """
    Parse transcript files and upsert extracted hypotheses to the DB.

    Flow:
        file → parse → chunk → Claude extraction → validate → upsert
    """

    def __init__(self) -> None:
        pass

    def process_file(self, path: str | Path) -> int:
        """
        Process a single transcript file.
        Returns the number of hypotheses extracted.
        """
        path = Path(path)
        if not path.exists():
            log.error("extractor.file_not_found", path=str(path))
            return 0

        log.info("extractor.processing_file", path=str(path))

        source_id = _source_hash(path)

        # Check if already processed
        with get_connection() as conn:
            existing = conn.execute(
                __import__("sqlalchemy").text(
                    "SELECT processed_at FROM transcript_sources WHERE source_id = :sid"
                ),
                {"sid": source_id}
            ).fetchone()

        if existing and existing[0] is not None:
            log.info("extractor.already_processed", path=str(path))
            return 0

        # Parse file
        suffix = path.suffix.lower()
        if suffix == ".jsonl":
            full_text, title, event_date, tickers = _parse_jsonl(path)
        else:
            full_text, title, event_date, tickers = _parse_plain(path)

        if not full_text.strip():
            log.warning("extractor.empty_file", path=str(path))
            return 0

        # Chunk text
        chunks = _chunk_text(full_text)
        log.info("extractor.chunked", path=str(path), n_chunks=len(chunks))

        # Upsert transcript_source
        self._upsert_source(
            source_id=source_id,
            file_path=str(path),
            title=title,
            event_date=event_date,
            tickers=tickers,
            word_count=len(full_text.split()),
            chunk_count=len(chunks),
        )

        # Process each chunk
        total_hypotheses = 0
        for chunk in chunks:
            chunk_db_id = self._upsert_chunk(source_id, chunk)
            if chunk_db_id is None:
                continue

            raw_hypotheses = _call_claude(chunk["chunk_text"])
            log.info(
                "extractor.chunk_done",
                chunk_index=chunk["chunk_index"],
                n_hypotheses=len(raw_hypotheses),
            )

            for h in raw_hypotheses:
                if not _validate_hypothesis(h):
                    continue
                record = _to_db_record(h, source_id, chunk_db_id)
                self._upsert_hypothesis(record)
                total_hypotheses += 1

        # Mark source as processed
        self._mark_processed(source_id)

        log.info(
            "extractor.file_done",
            path=str(path),
            n_chunks=len(chunks),
            n_hypotheses=total_hypotheses,
        )
        return total_hypotheses

    def process_directory(
        self,
        directory: str | Path,
        glob: str = "**/*.jsonl",
        also_txt: bool = True,
    ) -> int:
        """
        Recursively process all transcript files in a directory.
        Returns total hypotheses extracted.
        """
        directory = Path(directory)
        total = 0
        patterns = [glob]
        if also_txt:
            patterns += ["**/*.txt", "**/*.md"]

        for pattern in patterns:
            for fpath in sorted(directory.glob(pattern)):
                total += self.process_file(fpath)

        log.info("extractor.directory_done", directory=str(directory), total=total)
        return total

    # ------------------------------------------------------------------
    # DB helpers
    # ------------------------------------------------------------------

    def _upsert_source(
        self,
        source_id: str,
        file_path: str,
        title: str | None,
        event_date: date | None,
        tickers: list[str],
        word_count: int,
        chunk_count: int,
    ) -> None:
        from sqlalchemy import text
        with get_connection() as conn:
            conn.execute(text("""
                INSERT INTO transcript_sources
                    (source_id, file_path, title, event_date, ticker_context,
                     word_count, chunk_count, source_type)
                VALUES
                    (:sid, :fp, :title, :edate, :tickers,
                     :wc, :cc, 'transcript')
                ON CONFLICT (source_id) DO UPDATE SET
                    chunk_count = EXCLUDED.chunk_count,
                    word_count  = EXCLUDED.word_count
            """), {
                "sid":     source_id,
                "fp":      file_path,
                "title":   title,
                "edate":   event_date,
                "tickers": tickers,
                "wc":      word_count,
                "cc":      chunk_count,
            })
            conn.commit()

    def _upsert_chunk(self, source_id: str, chunk: dict) -> int | None:
        from sqlalchemy import text
        with get_connection() as conn:
            result = conn.execute(text("""
                INSERT INTO transcript_chunks
                    (source_id, chunk_index, chunk_text, char_start, char_end)
                VALUES
                    (:sid, :cidx, :ctext, :cstart, :cend)
                ON CONFLICT (source_id, chunk_index) DO UPDATE SET
                    chunk_text = EXCLUDED.chunk_text
                RETURNING id
            """), {
                "sid":    source_id,
                "cidx":   chunk["chunk_index"],
                "ctext":  chunk["chunk_text"],
                "cstart": chunk["char_start"],
                "cend":   chunk["char_end"],
            })
            conn.commit()
            row = result.fetchone()
            return row[0] if row else None

    def _upsert_hypothesis(self, record: dict) -> None:
        from sqlalchemy import text
        with get_connection() as conn:
            conn.execute(text("""
                INSERT INTO research_hypotheses (
                    hypothesis_id, source_id, chunk_id,
                    source_text, extracted_claim,
                    market_object, condition, condition_params,
                    target, horizons, direction,
                    regime_filter, sector_filter,
                    confidence_prior, test_status
                ) VALUES (
                    :hypothesis_id, :source_id, :chunk_id,
                    :source_text, :extracted_claim,
                    :market_object, :condition, CAST(:condition_params AS jsonb),
                    :target, :horizons, :direction,
                    :regime_filter, :sector_filter,
                    :confidence_prior, :test_status
                )
                ON CONFLICT (hypothesis_id) DO NOTHING
            """), record)
            conn.commit()

    def _mark_processed(self, source_id: str) -> None:
        from sqlalchemy import text
        with get_connection() as conn:
            conn.execute(text("""
                UPDATE transcript_sources
                SET processed_at = now()
                WHERE source_id = :sid
            """), {"sid": source_id})
            conn.commit()
