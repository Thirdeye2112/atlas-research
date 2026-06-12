"""
watch_oscar.py
--------------
Monitors @OscarCarboni YouTube channel for new videos.
Downloads transcripts for any video not already in oscar_scrape_log.

Requires: youtube-transcript-api, yt-dlp (for channel video list)

Usage:
    python scripts/watch_oscar.py --dry-run     # show what would be scraped
    python scripts/watch_oscar.py --ingest      # download + store new transcripts
    python scripts/watch_oscar.py --max 20      # limit to 20 most recent videos
"""

import argparse
import sys
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from sqlalchemy import create_engine, text

engine = create_engine(os.environ["DATABASE_URL"])

CHANNEL_URL = "https://www.youtube.com/@OscarCarboni/videos"
CHANNEL_ID = "UCOscarCarboni"  # fallback


def get_channel_videos(max_videos: int = 50) -> list[dict]:
    """Use yt-dlp Python API to list recent videos from the Oscar Carboni channel."""
    try:
        import yt_dlp
    except ImportError:
        print("[watch_oscar] yt-dlp not found. Install with: pip install yt-dlp")
        return []

    ydl_opts = {
        "quiet": True,
        "extract_flat": True,
        "playlistend": max_videos,
        "ignoreerrors": True,
    }
    videos = []
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(CHANNEL_URL, download=False)
            if not info or "entries" not in info:
                return []
            for entry in (info["entries"] or []):
                if not entry or not entry.get("id"):
                    continue
                video_id = entry["id"]
                title    = entry.get("title", "")
                upload_raw = str(entry.get("upload_date") or "")
                duration   = entry.get("duration")

                published_at = None
                if upload_raw and len(upload_raw) == 8:
                    try:
                        published_at = datetime.strptime(upload_raw, "%Y%m%d").replace(tzinfo=timezone.utc)
                    except ValueError:
                        pass

                videos.append({
                    "video_id": video_id,
                    "title": title,
                    "published_at": published_at,
                    "duration_secs": int(duration) if duration else None,
                })
    except Exception as ex:
        print(f"[watch_oscar] Error fetching channel: {ex}")
    return videos


def get_transcript(video_id: str) -> str | None:
    """Fetch transcript text for a video using youtube-transcript-api."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        segments = YouTubeTranscriptApi.get_transcript(video_id)
        return " ".join(s["text"] for s in segments)
    except ImportError:
        print("[watch_oscar] youtube-transcript-api not found. Install with: pip install youtube-transcript-api")
        return None
    except Exception as ex:
        print(f"[watch_oscar] Transcript unavailable for {video_id}: {ex}")
        return None


def get_already_scraped() -> set[str]:
    with engine.connect() as c:
        rows = c.execute(text("SELECT video_id FROM oscar_scrape_log")).fetchall()
        return {r[0] for r in rows}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Show what would be scraped")
    parser.add_argument("--ingest", action="store_true", help="Actually download and store transcripts")
    parser.add_argument("--max", type=int, default=50, help="Max videos to check")
    args = parser.parse_args()

    if not args.dry_run and not args.ingest:
        parser.print_help()
        sys.exit(1)

    print(f"[watch_oscar] Fetching up to {args.max} recent videos from {CHANNEL_URL}...")
    videos = get_channel_videos(args.max)

    if not videos:
        print("[watch_oscar] No videos found. Check yt-dlp installation.")
        sys.exit(1)

    print(f"[watch_oscar] Found {len(videos)} videos on channel.")

    already_scraped = get_already_scraped()
    new_videos = [v for v in videos if v["video_id"] not in already_scraped]
    print(f"[watch_oscar] {len(new_videos)} new videos (not yet in scrape_log).")

    if not new_videos:
        print("[watch_oscar] Nothing new to scrape.")
        return

    if args.dry_run:
        print("\n[DRY RUN] Would scrape:")
        for v in new_videos[:20]:
            pub = v["published_at"].date() if v["published_at"] else "unknown"
            dur = f"{v['duration_secs']//60}m" if v["duration_secs"] else "?"
            print(f"  {v['video_id']}  {pub}  {dur:<6}  {v['title'][:60]}")
        return

    # Ingest mode: download transcripts and store in DB
    with engine.connect() as c:
        ingested = 0
        errors = 0
        for v in new_videos:
            print(f"  Scraping: {v['video_id']} — {v['title'][:60]}...")
            transcript = get_transcript(v["video_id"])

            status = "ingested" if transcript else "no_transcript"
            error_msg = None if transcript else "Transcript not available"

            c.execute(text("""
                INSERT INTO oscar_scrape_log
                  (video_id, video_title, published_at, duration_secs, transcript_chars, status, ingested_at, error_msg)
                VALUES
                  (:video_id, :title, :published_at, :duration_secs, :transcript_chars, :status, NOW(), :error_msg)
                ON CONFLICT (video_id) DO UPDATE
                  SET status=EXCLUDED.status, ingested_at=NOW(), error_msg=EXCLUDED.error_msg
            """), {
                "video_id": v["video_id"],
                "title": v["title"],
                "published_at": v["published_at"],
                "duration_secs": v["duration_secs"],
                "transcript_chars": len(transcript) if transcript else 0,
                "status": status,
                "error_msg": error_msg,
            })

            if transcript:
                # Store raw transcript in transcript_chunks table (re-use existing schema)
                c.execute(text("""
                    INSERT INTO transcript_chunks
                      (source_id, chunk_index, text, created_at)
                    SELECT id, 0, :text, NOW()
                    FROM transcript_sources
                    WHERE external_id = :video_id
                    ON CONFLICT DO NOTHING
                """), {"text": transcript[:50000], "video_id": v["video_id"]})
                ingested += 1
            else:
                errors += 1

        c.commit()
        print(f"\n[watch_oscar] Done. Ingested: {ingested}  No transcript: {errors}")


if __name__ == "__main__":
    main()
