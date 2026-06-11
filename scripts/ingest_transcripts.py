"""
Oscar Carboni transcript ingestion pipeline.

Reads chartwhisperer_transcripts_1780591128929.txt, cleans YouTube captions,
splits into per-video sessions, chunks at ~500 words, calls Claude to extract
structured market hypotheses, and stores everything in atlas_research DB.

Usage:
    python scripts/ingest_transcripts.py [--max-videos N] [--start-from N] [--dry-run]

Default: 50 most-recent videos.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

import anthropic
from sqlalchemy import text

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from atlas_research.db.connection import get_raw_engine

# ── Configuration ─────────────────────────────────────────────────────────────

TRANSCRIPT_PATH = (
    r"C:\Atlas\atlas-alpha\attached_assets\chartwhisperer_transcripts_1780591128929.txt"
)
SPEAKER = "Oscar Carboni"
SOURCE_TYPE = "transcript"
CHUNK_WORDS = 500
CHUNK_OVERLAP = 50   # words of overlap between chunks
MODEL = "claude-haiku-4-5-20251001"
MAX_RETRIES = 3
RETRY_DELAY = 2.0

# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class VideoSession:
    raw_title: str       # full VIDEO TITLE: ... line content
    video_id: str
    event_date: Optional[date]
    title: str
    text: str            # cleaned transcript text
    word_count: int


@dataclass
class Chunk:
    index: int
    text: str
    char_start: int
    char_end: int


@dataclass
class Hypothesis:
    extracted_claim: str
    market_object: Optional[str]
    condition: Optional[str]
    condition_params: Optional[dict]
    target: Optional[str]
    horizons: Optional[list]
    direction: Optional[str]
    regime_filter: Optional[str]
    sector_filter: Optional[str]
    confidence_prior: float
    source_text: str


# ── Text cleaning ─────────────────────────────────────────────────────────────

# YouTube VTT timestamp tag pattern
_TS_TAG = re.compile(r"<\d{2}:\d{2}:\d{2}\.\d+>")
# Words tagged as newly-added to the display in each VTT cue
_C_WORD_RE = re.compile(r"<c>\s*([^<]+?)\s*</c>")
# "Kind: captions Language: en" header line
_KIND_HDR = re.compile(r"^Kind:\s+captions\s+Language:\s+\w+\s*", re.MULTILINE)


def _clean_text(raw: str) -> str:
    """
    Strip YouTube VTT rolling-window artifact.

    YouTube auto-captions render by prepending the full current display window
    before each new <c>word</c>. Naively concatenating lines produces:
        "A B C  A B C D  A B C D E"  (every phrase repeated 2-3×)

    Fix: collect only the <c>-tagged words (uniquely-new per cue) plus the
    initial untagged prefix of the first cue. This gives clean non-repeated text.
    Falls back to word-level dedup when no <c> tags are present.
    """
    text = _KIND_HDR.sub("", raw)
    c_words = _C_WORD_RE.findall(text)

    if c_words:
        # Primary path: extract <c> tokens (one new word/phrase per cue)
        words: list[str] = []

        # Initial untagged prefix (text before the first timestamp or <c> tag)
        init_match = re.match(r"^([^<]+)", text.strip())
        if init_match:
            init_text = _TS_TAG.sub("", init_match.group(1))
            prev_key: str | None = None
            for w in init_text.split():
                key = w.lower().strip(",.!?;:'\"")
                if key and key != prev_key:
                    words.append(w)
                    prev_key = key

        words.extend(w.strip() for w in c_words if w.strip())
        result = " ".join(words)
    else:
        # Fallback for segments without <c> tags
        clean = _TS_TAG.sub("", text)
        clean = re.sub(r"</?c>", "", clean)
        clean = re.sub(r"\s{2,}", " ", clean).strip()
        result = _dedup_word_sequences(clean)

    return re.sub(r"\s{2,}", " ", result).strip()


def _dedup_word_sequences(text: str, min_len: int = 5) -> str:
    """
    Fallback word-level dedup for non-VTT segments.
    Removes immediately-repeated sequences of min_len+ words.
    """
    words = text.split()
    n = len(words)
    out: list[str] = []
    i = 0
    while i < n:
        matched = False
        max_seq = min(30, (n - i) // 2)
        for seq_len in range(max_seq, min_len - 1, -1):
            if tuple(words[i:i + seq_len]) == tuple(words[i + seq_len:i + 2 * seq_len]):
                out.extend(words[i:i + seq_len])
                skip = i + seq_len
                seq_tuple = tuple(words[i:i + seq_len])
                while skip + seq_len <= n and tuple(words[skip:skip + seq_len]) == seq_tuple:
                    skip += seq_len
                i = skip
                matched = True
                break
        if not matched:
            out.append(words[i])
            i += 1
    return " ".join(out)


# ── Video session parsing ─────────────────────────────────────────────────────

_VIDEO_TITLE_RE = re.compile(r"^VIDEO TITLE:\s*(.+)$", re.MULTILINE)
_DASH_SEP = re.compile(r"^-{10,}$", re.MULTILINE)


def _parse_date(token: str) -> Optional[date]:
    try:
        return datetime.strptime(token[:8], "%Y%m%d").date()
    except ValueError:
        return None


def parse_sessions(raw: str) -> list[VideoSession]:
    """Split transcript into per-video sessions, newest-first."""
    # Find all VIDEO TITLE positions
    title_matches = list(_VIDEO_TITLE_RE.finditer(raw))
    if not title_matches:
        raise ValueError("No VIDEO TITLE: markers found in transcript")

    sessions = []
    for i, m in enumerate(title_matches):
        title_line = m.group(1).strip()
        body_start = m.end()
        body_end = title_matches[i + 1].start() if i + 1 < len(title_matches) else len(raw)
        body = raw[body_start:body_end]

        # Strip leading dashes separator
        body = _DASH_SEP.sub("", body, count=1).strip()

        # Parse title tokens: YYYYMMDD Z videoId rest...
        parts = title_line.split(None, 3)
        if len(parts) >= 3:
            event_date = _parse_date(parts[0])
            video_id = parts[2] if len(parts) > 2 else parts[0]
            display_title = parts[3] if len(parts) > 3 else title_line
        else:
            event_date = None
            video_id = hashlib.sha1(title_line.encode()).hexdigest()[:12]
            display_title = title_line

        # Remove trailing date/video# artifacts from title (e.g. "06§03§26 Video #3080")
        display_title = re.sub(r"\s+\d{2}[â§¸]+\d{2}[â§¸]+\d{2}\s+Video\s+#\d+.*", "", display_title).strip()

        cleaned = _clean_text(body)
        words = cleaned.split()

        sessions.append(VideoSession(
            raw_title=title_line,
            video_id=video_id,
            event_date=event_date,
            title=display_title,
            text=cleaned,
            word_count=len(words),
        ))

    # Newest first (sort by event_date desc, None at end)
    sessions.sort(key=lambda s: s.event_date or date(1900, 1, 1), reverse=True)
    return sessions


# ── Chunking ──────────────────────────────────────────────────────────────────

def chunk_session(session: VideoSession) -> list[Chunk]:
    """Split session text into ~CHUNK_WORDS word chunks with overlap."""
    words = session.text.split()
    if not words:
        return []

    chunks = []
    step = CHUNK_WORDS - CHUNK_OVERLAP
    i = 0
    chunk_idx = 0

    # Build word→char_start map once
    char_positions = []
    pos = 0
    for w in words:
        char_positions.append(session.text.index(w, pos))
        pos = char_positions[-1] + len(w)

    while i < len(words):
        end = min(i + CHUNK_WORDS, len(words))
        chunk_words = words[i:end]
        chunk_text = " ".join(chunk_words)
        char_start = char_positions[i]
        char_end = char_positions[end - 1] + len(words[end - 1]) if end > i else char_start

        chunks.append(Chunk(
            index=chunk_idx,
            text=chunk_text,
            char_start=char_start,
            char_end=char_end,
        ))
        chunk_idx += 1
        i += step
        if end == len(words):
            break

    return chunks


# ── Claude extraction ─────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a market microstructure researcher extracting testable trading hypotheses from trading educator transcripts.

Extract ONLY concrete, specific, testable market claims — not general investment advice, risk warnings, or commentary.

A testable claim must have:
1. A specific market object (ticker, ETF, index, or "universe" for multi-stock)
2. A condition (what must be true before a trade/signal)
3. A direction (what the educator predicts will happen next)
4. An implied time horizon (days)

Return ONLY a JSON array of hypothesis objects. Return [] if no testable claims are found.

── SECTOR AND TICKER MAPPING ──────────────────────────────────────────────────
Translate Oscar's language to tradeable symbols:

Sectors → ETFs:
  "tech" / "technology" / "semiconductors" → XLK
  "financials" / "banks" / "finance"        → XLF
  "energy" / "oil" / "crude oil"            → XLE
  "healthcare" / "health" / "biotech"       → XLV
  "industrials" / "industrial"              → XLI
  "consumer staples" / "staples"            → XLP
  "utilities"                               → XLU
  "consumer discretionary" / "retail"       → XLY
  "materials" / "commodities" / "copper"    → XLB
  "real estate" / "REIT"                    → XLRE
  "communication" / "media" / "telecom"     → XLC
  "gold" / "precious metals"               → GLD
  "bonds" / "treasuries" / "fixed income"  → TLT
  "small caps" / "Russell"                 → IWM
  "Nasdaq" / "QQQ" / "tech-heavy"          → QQQ
  "Dow" / "blue chips" / "DJIA"            → DIA
  "S&P" / "SPY" / "the market"             → SPY
  "VIX" / "volatility" / "fear index"      → VIX

Named stocks (AAPL, NVDA, TSLA, etc.) → use ticker directly.

── CONDITION TYPES ────────────────────────────────────────────────────────────
Standard:
  "consecutive_down"  — N days closing lower
  "consecutive_up"    — N days closing higher
  "oversold_rsi"      — RSI below threshold
  "overbought_rsi"    — RSI above threshold
  "gap_down"          — gap-down open > pct%
  "gap_up"            — gap-up open > pct%
  "near_52w_low"      — within pct% of 52-week low
  "near_52w_high"     — within pct% of 52-week high
  "high_volume"       — volume > N× 20-day avg
  "above_level"       — price / index above absolute threshold (use for VIX > 30)
  "below_sma"         — price below N-day moving average (use for "below 200-day")
  "above_sma"         — price above N-day moving average

Macro/seasonal:
  "seasonal"          — time-of-year pattern (end_of_month, january_first_week, Q4)
  "fed_event"         — pattern around Fed meeting (pre_fomc, post_fomc)
  "macro_event"       — CPI, jobs, earnings-related
  "sector_rotation"   — money flowing from one sector to another

── TIME-BASED PARAMETERS ──────────────────────────────────────────────────────
  "end of month"           → condition_type: "seasonal", params: {"period": "end_of_month"}
  "first week of year"     → condition_type: "seasonal", params: {"period": "january_first_week"}
  "before Fed meeting"     → condition_type: "fed_event",  params: {"timing": "pre_fomc"}
  "after CPI"              → condition_type: "macro_event", params: {"event": "cpi_release"}
  "Q4" / "fourth quarter"  → condition_type: "seasonal",  params: {"quarter": 4}

── FIELD SCHEMA ───────────────────────────────────────────────────────────────
Each object must have exactly these fields:
{
  "extracted_claim": "Plain English description of the testable hypothesis",
  "market_object": "SPY" | "QQQ" | "XLK" | "VIX" | "AAPL" | "universe" | null,
  "condition": one of the condition type strings above,
  "condition_params": {"n_days": 3} | {"threshold": 30} | {"period": 200} | {"period": "end_of_month"} | {} | null,
  "target": "forward_return_1d" | "forward_return_5d" | "forward_return_10d" | "forward_return_20d",
  "horizons": [5] | [1, 5] | [5, 10] | [10, 20] | [1],
  "direction": "mean_reversion_long" | "momentum_long" | "momentum_short" | "mean_reversion_short" | "neutral",
  "regime_filter": "bull_only" | "bear_only" | null,
  "sector_filter": "XLK" | "XLE" | "XLF" | null,
  "confidence_prior": 0.3-0.9 (float),
  "source_text": "verbatim quote max 200 chars"
}

── CONFIDENCE GUIDELINES ──────────────────────────────────────────────────────
  0.8-0.9: Educator states a specific rule they trade by ("When SPY drops 5 days, I always buy")
  0.6-0.7: Clear directional assertion with reasoning ("usually leads to a bounce")
  0.4-0.5: Suggestive observation ("tends to", "often", "historically")
  0.3:     Vague or anecdotal ("sometimes", "might")"""


def extract_hypotheses(
    client: anthropic.Anthropic,
    session: VideoSession,
    chunk: Chunk,
) -> list[Hypothesis]:
    """Call Claude to extract hypotheses from a chunk."""
    user_msg = f"""Source: {session.title} ({session.event_date})
Speaker: Oscar Carboni

Transcript chunk:
{chunk.text}

Extract all testable market hypotheses. Return JSON array only."""

    for attempt in range(MAX_RETRIES):
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=2048,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_msg}],
            )
            raw = response.content[0].text.strip()

            # Extract JSON from response (may have markdown fences)
            json_match = re.search(r"\[.*\]", raw, re.DOTALL)
            if not json_match:
                return []
            data = json.loads(json_match.group())

            hypotheses = []
            for item in data:
                if not isinstance(item, dict):
                    continue
                if not item.get("extracted_claim") or not item.get("direction"):
                    continue
                hypotheses.append(Hypothesis(
                    extracted_claim=item.get("extracted_claim", "")[:1000],
                    market_object=item.get("market_object"),
                    condition=item.get("condition"),
                    condition_params=item.get("condition_params"),
                    target=item.get("target"),
                    horizons=item.get("horizons"),
                    direction=item.get("direction"),
                    regime_filter=item.get("regime_filter"),
                    sector_filter=item.get("sector_filter"),
                    confidence_prior=float(item.get("confidence_prior", 0.5)),
                    source_text=item.get("source_text", chunk.text[:200]),
                ))
            return hypotheses

        except (json.JSONDecodeError, KeyError, ValueError):
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
        except anthropic.RateLimitError:
            wait = RETRY_DELAY * (attempt + 2)
            print(f"    [rate limit] sleeping {wait}s...")
            time.sleep(wait)
        except anthropic.APIError as e:
            print(f"    [API error] {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)

    return []


# ── Database operations ───────────────────────────────────────────────────────

def make_source_id(raw_title: str) -> str:
    """Hash the full raw title line — unique per video, no collision from shared tokens."""
    return hashlib.sha256(f"carboni:{raw_title}".encode()).hexdigest()[:32]


def upsert_source(conn, session: VideoSession, source_id: str, chunk_count: int):
    conn.execute(text("""
        INSERT INTO transcript_sources
            (source_id, file_path, source_type, title, speaker, event_date,
             word_count, chunk_count, processed_at)
        VALUES
            (:sid, :fp, :st, :title, :speaker, :dt, :wc, :cc, now())
        ON CONFLICT (source_id) DO UPDATE SET
            title       = EXCLUDED.title,
            word_count  = EXCLUDED.word_count,
            chunk_count = EXCLUDED.chunk_count,
            processed_at = now()
    """), {
        "sid": source_id,
        "fp": TRANSCRIPT_PATH,
        "st": SOURCE_TYPE,
        "title": session.title[:500],
        "speaker": SPEAKER,
        "dt": session.event_date,
        "wc": session.word_count,
        "cc": chunk_count,
    })


def upsert_chunk(conn, source_id: str, chunk: Chunk) -> int:
    row = conn.execute(text("""
        INSERT INTO transcript_chunks
            (source_id, chunk_index, chunk_text, char_start, char_end)
        VALUES (:sid, :idx, :txt, :cs, :ce)
        ON CONFLICT (source_id, chunk_index) DO UPDATE SET
            chunk_text = EXCLUDED.chunk_text,
            char_start = EXCLUDED.char_start,
            char_end   = EXCLUDED.char_end
        RETURNING id
    """), {
        "sid": source_id,
        "idx": chunk.index,
        "txt": chunk.text,
        "cs": chunk.char_start,
        "ce": chunk.char_end,
    }).fetchone()
    return row[0]


def upsert_hypothesis(conn, hyp: Hypothesis, source_id: str, chunk_id: int) -> bool:
    hyp_id = str(uuid.uuid4())
    try:
        conn.execute(text("""
            INSERT INTO research_hypotheses
                (hypothesis_id, source_id, chunk_id, source_text, extracted_claim,
                 market_object, condition, condition_params, target, horizons,
                 direction, regime_filter, sector_filter, confidence_prior,
                 test_status, created_at, updated_at)
            VALUES
                (:hid, :sid, :cid, :src, :claim, :mo, :cond, :cp, :tgt, :hz,
                 :dir, :rf, :sf, :cp2, 'queued', now(), now())
        """), {
            "hid": hyp_id,
            "sid": source_id,
            "cid": chunk_id,
            "src": hyp.source_text[:2000],
            "claim": hyp.extracted_claim,
            "mo": hyp.market_object,
            "cond": hyp.condition,
            "cp": json.dumps(hyp.condition_params) if hyp.condition_params else None,
            "tgt": hyp.target,
            "hz": hyp.horizons,
            "dir": hyp.direction,
            "rf": hyp.regime_filter,
            "sf": hyp.sector_filter,
            "cp2": max(0.0, min(1.0, hyp.confidence_prior)),
        })
        return True
    except Exception as e:
        print(f"    [db] hypothesis insert failed: {e}")
        return False


# ── Main pipeline ─────────────────────────────────────────────────────────────

def run_ingestion(
    max_videos: int = 50,
    start_from: int = 0,
    dry_run: bool = False,
    skip_extract: bool = False,
) -> dict:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not skip_extract and not dry_run:
        if not api_key:
            print("ERROR: ANTHROPIC_API_KEY not set. Add it to atlas-research/.env")
            print("       Re-run with --skip-extract to ingest sources/chunks without hypothesis extraction.")
            sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key or "sk-dummy") if not skip_extract and not dry_run else None
    engine = get_raw_engine()

    print(f"Reading transcript file...")
    with open(TRANSCRIPT_PATH, "r", encoding="utf-8", errors="replace") as f:
        raw = f.read()
    print(f"  {len(raw):,} chars loaded")

    print("Parsing video sessions...")
    sessions = parse_sessions(raw)
    total = len(sessions)
    print(f"  {total} sessions found (newest first)")

    target_sessions = sessions[start_from: start_from + max_videos]
    print(f"  Processing sessions {start_from}–{start_from + len(target_sessions) - 1} of {total}")

    stats = {
        "sessions_processed": 0,
        "chunks_processed": 0,
        "hypotheses_extracted": 0,
        "api_calls": 0,
        "errors": 0,
    }

    for vidx, session in enumerate(target_sessions):
        print(f"\n[{vidx + 1}/{len(target_sessions)}] {session.event_date} — {session.title[:70]}")
        print(f"  words={session.word_count}")

        if session.word_count < 100:
            print("  Skipping (too short)")
            continue

        source_id = make_source_id(session.raw_title)
        chunks = chunk_session(session)
        print(f"  {len(chunks)} chunks")

        if dry_run:
            print("  [dry-run] skipping DB + API calls")
            stats["sessions_processed"] += 1
            stats["chunks_processed"] += len(chunks)
            continue

        session_hypotheses = 0

        with engine.begin() as conn:
            upsert_source(conn, session, source_id, len(chunks))

        for chunk in chunks:
            words_in_chunk = len(chunk.text.split())
            if words_in_chunk < 50:
                continue

            with engine.begin() as conn:
                chunk_id = upsert_chunk(conn, source_id, chunk)

            stats["chunks_processed"] += 1

            if skip_extract:
                continue

            hyps = extract_hypotheses(client, session, chunk)
            stats["api_calls"] += 1

            if hyps:
                with engine.begin() as conn:
                    for hyp in hyps:
                        if upsert_hypothesis(conn, hyp, source_id, chunk_id):
                            session_hypotheses += 1
                            stats["hypotheses_extracted"] += 1

            # Brief pause to respect rate limits
            time.sleep(0.2)

        action = "chunks stored" if skip_extract else "hypotheses extracted"
        count = stats["chunks_processed"] if skip_extract else session_hypotheses
        print(f"  → {session_hypotheses} hypotheses | {stats['chunks_processed']} chunks stored")
        stats["sessions_processed"] += 1

    return stats


def show_top_hypotheses(n: int = 10):
    engine = get_raw_engine()
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT
                h.extracted_claim,
                h.market_object,
                h.condition,
                h.direction,
                h.confidence_prior,
                h.horizons,
                ts.event_date,
                ts.title
            FROM research_hypotheses h
            LEFT JOIN transcript_sources ts ON ts.source_id = h.source_id
            ORDER BY h.confidence_prior DESC, h.created_at DESC
            LIMIT :n
        """), {"n": n}).fetchall()

    if not rows:
        print("\nNo hypotheses found in database.")
        return

    print(f"\n{'='*100}")
    print(f"TOP {n} HYPOTHESES BY CONFIDENCE PRIOR")
    print(f"{'='*100}")
    for i, r in enumerate(rows, 1):
        claim, mobj, cond, direction, conf, horizons, edate, title = r
        print(f"\n#{i} [{conf:.2f}] {claim}")
        print(f"   Market: {mobj or 'n/a'} | Condition: {cond or 'n/a'} | Direction: {direction}")
        print(f"   Horizons: {horizons} | Date: {edate} | Source: {(title or '')[:60]}")
    print()


def main():
    parser = argparse.ArgumentParser(description="Ingest Oscar Carboni transcripts")
    parser.add_argument("--max-videos", type=int, default=50, help="Max videos to process")
    parser.add_argument("--start-from", type=int, default=0, help="Start from video index N")
    parser.add_argument("--dry-run", action="store_true", help="Parse but don't call API or DB")
    parser.add_argument("--skip-extract", action="store_true", help="Write sources+chunks to DB, skip Claude extraction")
    parser.add_argument("--show-only", "--show", action="store_true", help="Only show existing hypotheses")
    args = parser.parse_args()

    if args.show_only:
        show_top_hypotheses()
        return

    t0 = time.time()
    stats = run_ingestion(
        max_videos=args.max_videos,
        start_from=args.start_from,
        dry_run=args.dry_run,
        skip_extract=args.skip_extract,
    )
    elapsed = time.time() - t0

    print(f"\n{'='*60}")
    print(f"INGESTION COMPLETE ({elapsed:.1f}s)")
    print(f"  Sessions: {stats['sessions_processed']}")
    print(f"  Chunks:   {stats['chunks_processed']}")
    print(f"  API calls:{stats['api_calls']}")
    print(f"  Hypotheses: {stats['hypotheses_extracted']}")
    print(f"{'='*60}")

    if not args.dry_run:
        show_top_hypotheses()


if __name__ == "__main__":
    main()
