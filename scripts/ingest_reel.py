#!/usr/bin/env python
"""
ingest_reel.py — pull a social reel/post into mineable text + frames.

Instagram (and most platforms) expose NO transcript API, so this DOWNLOADS the
media and produces the content locally:
  1. yt-dlp downloads the video + caption/description metadata.
  2. ffmpeg (bundled via imageio-ffmpeg, no system install) extracts deduped
     keyframes as PNGs  -> these capture the ON-SCREEN TEXT of infographic reels
     (read them directly; far more reliable than OCR for this content).
  3. faster-whisper transcribes the spoken AUDIO (often just music for these
     reels -> empty, which is fine).
Outputs reports/reels/<id>/ : video, caption.txt, transcript.txt, frames/*.png,
and summary.md.

USAGE
  python scripts/ingest_reel.py <url> [<url> ...]
  python scripts/ingest_reel.py --url-file urls.txt
  python scripts/ingest_reel.py <url> --cookies-from-browser chrome   # IG login-gated
  python scripts/ingest_reel.py <url> --no-transcribe --frames-every 1.5

NOTES / CAVEATS
  - Instagram usually requires a logged-in session: pass --cookies-from-browser
    chrome|firefox|edge (reads your browser's cookies; you must be logged in).
  - Scraping is against IG's ToS — keep it modest and personal-research only
    (a few URLs you choose), not bulk account harvesting.
  - Everything is local/free (yt-dlp, venv ffmpeg, faster-whisper). First run
    downloads the Whisper model (~150 MB for 'base').
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTROOT = ROOT / "reports" / "reels"


def _ffmpeg() -> str:
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def download(url: str, outdir: Path, cookies_browser: str | None) -> tuple[Path | None, dict]:
    import yt_dlp
    opts = {
        "outtmpl": str(outdir / "video.%(ext)s"),
        "format": "mp4/bestvideo*+bestaudio/best",
        "writeinfojson": True,
        "quiet": True, "no_warnings": True,
        "ffmpeg_location": str(Path(_ffmpeg()).parent),
        "noplaylist": True,
    }
    if cookies_browser:
        opts["cookiesfrombrowser"] = (cookies_browser,)
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        fn = Path(ydl.prepare_filename(info))
    if not fn.exists():
        cand = list(outdir.glob("video.*"))
        fn = cand[0] if cand else None
    return fn, info


def extract_frames(video: Path, outdir: Path, every: float, max_frames: int) -> list[Path]:
    fdir = outdir / "frames"; fdir.mkdir(exist_ok=True)
    # one frame every `every` seconds, downscaled; dedupe near-identical frames
    vf = f"fps=1/{every},mpdecimate=hi=64*48,scale=720:-1"
    cmd = [_ffmpeg(), "-y", "-i", str(video), "-vf", vf, "-vsync", "vfr",
           "-frames:v", str(max_frames), "-q:v", "3", str(fdir / "frame_%03d.png")]
    subprocess.run(cmd, capture_output=True)
    return sorted(fdir.glob("frame_*.png"))


def transcribe(video: Path, model_size: str) -> str:
    from faster_whisper import WhisperModel
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    segments, _info = model.transcribe(str(video), vad_filter=True)
    return " ".join(s.text.strip() for s in segments).strip()


def process(url: str, args) -> None:
    import hashlib
    rid = hashlib.md5(url.encode()).hexdigest()[:10]
    outdir = OUTROOT / rid; outdir.mkdir(parents=True, exist_ok=True)
    print(f"\n[{rid}] {url}")

    try:
        video, info = download(url, outdir, args.cookies_from_browser)
    except Exception as e:
        print(f"  download FAILED: {e}")
        print("  (Instagram usually needs --cookies-from-browser chrome and a logged-in session)")
        return
    if not video:
        print("  no media file produced"); return
    print(f"  downloaded: {video.name}")

    caption = (info.get("description") or info.get("title") or "").strip()
    (outdir / "caption.txt").write_text(caption, encoding="utf-8")

    frames = []
    try:
        frames = extract_frames(video, outdir, args.frames_every, args.max_frames)
        print(f"  frames: {len(frames)} -> {outdir/'frames'}")
    except Exception as e:
        print(f"  frame extraction failed: {e}")

    transcript = ""
    if not args.no_transcribe:
        try:
            transcript = transcribe(video, args.whisper_model)
            print(f"  transcript: {len(transcript)} chars"
                  + ("" if transcript else " (no speech — likely music)"))
        except Exception as e:
            print(f"  transcription failed: {e}")
    (outdir / "transcript.txt").write_text(transcript, encoding="utf-8")

    summary = [
        f"# Reel {rid}", f"URL: {url}", f"Uploader: {info.get('uploader','?')}",
        "", "## Caption", caption or "(none)", "",
        "## Transcript (spoken audio)", transcript or "(none / music)", "",
        f"## Frames ({len(frames)}) — read these for on-screen text",
        *[f"- {p.relative_to(outdir)}" for p in frames],
    ]
    (outdir / "summary.md").write_text("\n".join(summary), encoding="utf-8")
    print(f"  summary -> {outdir/'summary.md'}")
    print(f"  >> point Claude at {outdir}/frames/*.png + transcript.txt to mine it")


def main():
    ap = argparse.ArgumentParser(description="Download a reel into mineable text + frames")
    ap.add_argument("urls", nargs="*")
    ap.add_argument("--url-file", default=None, help="File with one URL per line")
    ap.add_argument("--cookies-from-browser", default=None,
                    help="chrome|firefox|edge — needed for Instagram login-gated content")
    ap.add_argument("--frames-every", type=float, default=2.0, help="seconds between sampled frames")
    ap.add_argument("--max-frames", type=int, default=80)
    ap.add_argument("--whisper-model", default="base", help="tiny|base|small|medium")
    ap.add_argument("--no-transcribe", action="store_true")
    args = ap.parse_args()

    urls = list(args.urls)
    if args.url_file:
        urls += [ln.strip() for ln in Path(args.url_file).read_text().splitlines() if ln.strip()]
    if not urls:
        ap.error("provide at least one URL or --url-file")

    OUTROOT.mkdir(parents=True, exist_ok=True)
    print(f"ingest_reel | {len(urls)} url(s) -> {OUTROOT}")
    for u in urls:
        process(u, args)


if __name__ == "__main__":
    main()
