#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unified Transcribe - YouTube download + audio inbox transcription.

This script:
1. Downloads audio from YouTube URLs listed in video_urls.txt
2. Transcribes all audio files in the inbox folder using OpenAI Whisper
3. Tracks processed files to avoid duplicates

Usage:
    python unified_transcribe.py ~/path/to/Transcrições
    python unified_transcribe.py ~/path/to/Transcrições --skip-youtube
    python unified_transcribe.py ~/path/to/Transcrições --move-to processed
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

from openai import OpenAI

from keychain_utils import require_api_key

# Configuration via environment variables
MODEL = os.environ.get("TRANSCRIBE_MODEL", "whisper-1")
LANGUAGE = os.environ.get("TRANSCRIBE_LANG", "pt")

AUDIO_EXTS = {
    ".m4a", ".mp3", ".wav", ".aac", ".mp4",
    ".mpeg", ".mpga", ".webm", ".aiff", ".flac", ".caf", ".ogg", ".opus"
}

# File names for tracking
VIDEO_URLS_FILE = "video_urls.txt"
YOUTUBE_ARCHIVE_FILE = "youtube_downloaded_archive.txt"
TRANSCRIBED_INDEX_FILE = "transcribed_index.jsonl"


def safe_stem(name: str) -> str:
    """Create a safe filename stem."""
    s = re.sub(r"\s+", " ", name).strip()
    s = re.sub(r"[^\w\s\(\)\[\]\.\-]", "_", s)
    s = s.replace(" ", "_")
    return s[:120] if len(s) > 120 else s


def ensure_dir(p: Path) -> None:
    """Create directory if it doesn't exist."""
    p.mkdir(parents=True, exist_ok=True)


def file_hash(path: Path) -> str:
    """Calculate SHA256 hash of a file."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def load_transcribed_index(index_path: Path) -> set[str]:
    """Load set of already-transcribed file hashes."""
    hashes = set()
    if index_path.exists():
        with index_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        data = json.loads(line)
                        if "hash" in data:
                            hashes.add(data["hash"])
                    except json.JSONDecodeError:
                        pass
    return hashes


def append_transcribed_index(index_path: Path, file_hash: str, filename: str, transcript_path: str) -> None:
    """Append a new entry to the transcribed index."""
    entry = {
        "hash": file_hash,
        "filename": filename,
        "transcript": transcript_path,
        "timestamp": datetime.now().isoformat()
    }
    with index_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def check_yt_dlp() -> bool:
    """Check if yt-dlp is available."""
    return shutil.which("yt-dlp") is not None


def download_youtube_audio(url: str, output_dir: Path, archive_file: Path) -> Optional[Path]:
    """
    Download audio from a YouTube URL using yt-dlp.

    Returns the path to the downloaded file, or None if failed/skipped.
    """
    # yt-dlp command with archive to skip already downloaded
    cmd = [
        "yt-dlp",
        "--extract-audio",
        "--audio-format", "m4a",
        "--audio-quality", "0",
        "--output", str(output_dir / "%(title)s.%(ext)s"),
        "--download-archive", str(archive_file),
        "--no-playlist",
        "--restrict-filenames",
        url
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600  # 10 minute timeout
        )

        if result.returncode == 0:
            # Check if it was skipped (already in archive)
            if "has already been recorded in the archive" in result.stdout:
                print(f"  Skipped (already downloaded): {url}")
                return None

            # Find the downloaded file (most recent m4a in output_dir)
            m4a_files = sorted(
                [f for f in output_dir.iterdir() if f.suffix.lower() == ".m4a"],
                key=lambda f: f.stat().st_mtime,
                reverse=True
            )
            if m4a_files:
                return m4a_files[0]
        else:
            print(f"  yt-dlp error: {result.stderr[:200]}")

    except subprocess.TimeoutExpired:
        print(f"  Timeout downloading: {url}")
    except Exception as e:
        print(f"  Error downloading {url}: {e}")

    return None


def process_youtube_urls(base: Path, archive_file: Path) -> list[Path]:
    """
    Read video_urls.txt and download any new YouTube videos.

    Returns list of newly downloaded audio files.
    """
    urls_file = base / VIDEO_URLS_FILE
    if not urls_file.exists():
        return []

    downloaded = []

    with urls_file.open("r", encoding="utf-8") as f:
        urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]

    if not urls:
        return []

    print(f"\n=== Processing {len(urls)} YouTube URL(s) ===")

    for url in urls:
        print(f"Downloading: {url}")
        audio_path = download_youtube_audio(url, base, archive_file)
        if audio_path:
            print(f"  Downloaded: {audio_path.name}")
            downloaded.append(audio_path)

    return downloaded


def transcribe_one_file(client: OpenAI, audio_path: Path) -> str:
    """Transcribe a single audio file using OpenAI Whisper."""
    with audio_path.open("rb") as f:
        r = client.audio.transcriptions.create(
            model=MODEL,
            file=f,
            language=LANGUAGE,
            response_format="text",
        )
    return str(r).strip()


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Unified transcription: YouTube download + audio inbox → text transcripts."
    )
    ap.add_argument("folder", help="Folder containing audio files (and video_urls.txt for YouTube).")
    ap.add_argument("--out-subdir", default="transcripts_txt", help="Subfolder for transcripts (default: transcripts_txt).")
    ap.add_argument("--move-to", default="", help="Move processed audio to this subfolder.")
    ap.add_argument("--skip-existing", action="store_true", help="Skip files already transcribed (by hash).")
    ap.add_argument("--skip-youtube", action="store_true", help="Skip YouTube download, only process local audio.")
    args = ap.parse_args()

    base = Path(args.folder).expanduser()
    if not base.exists():
        print(f"Folder not found: {base}")
        return 2

    # Get API key
    try:
        api_key = require_api_key()
    except RuntimeError as e:
        print(str(e))
        return 3

    client = OpenAI(api_key=api_key)

    # Setup directories
    out_dir = base / args.out_subdir
    ensure_dir(out_dir)

    move_dir = None
    if args.move_to:
        move_dir = base / args.move_to
        ensure_dir(move_dir)

    # Index files
    transcribed_index = base / TRANSCRIBED_INDEX_FILE
    youtube_archive = base / YOUTUBE_ARCHIVE_FILE

    # Load already-transcribed hashes
    transcribed_hashes = load_transcribed_index(transcribed_index) if args.skip_existing else set()

    # Step 1: Download YouTube videos (if not skipped)
    if not args.skip_youtube:
        if check_yt_dlp():
            process_youtube_urls(base, youtube_archive)
        else:
            urls_file = base / VIDEO_URLS_FILE
            if urls_file.exists():
                print("Warning: yt-dlp not found. Install with: brew install yt-dlp")
                print("Skipping YouTube downloads, processing local audio only.")

    # Step 2: Find all audio files
    audio_files = [
        p for p in sorted(base.iterdir())
        if p.is_file() and p.suffix.lower() in AUDIO_EXTS
    ]

    if not audio_files:
        print("No audio files found in folder.")
        return 0

    print(f"\n=== Transcribing {len(audio_files)} audio file(s) ===")

    errors_log = out_dir / "errors.log"
    ok = 0
    skipped = 0
    fail = 0

    for audio_path in audio_files:
        # Check if already transcribed (by hash)
        if args.skip_existing:
            audio_hash = file_hash(audio_path)
            if audio_hash in transcribed_hashes:
                print(f"Skip (already transcribed): {audio_path.name}")
                skipped += 1
                continue
        else:
            audio_hash = None

        # Generate output filename
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_name = f"{ts}_{safe_stem(audio_path.stem)}.txt"
        out_path = out_dir / out_name

        print(f"Transcribing: {audio_path.name}")
        try:
            text = transcribe_one_file(client, audio_path)
            out_path.write_text(text + "\n", encoding="utf-8")
            ok += 1

            # Record in index
            if audio_hash is None:
                audio_hash = file_hash(audio_path)
            append_transcribed_index(transcribed_index, audio_hash, audio_path.name, out_path.name)
            transcribed_hashes.add(audio_hash)

            # Move processed file if requested
            if move_dir is not None:
                audio_path.replace(move_dir / audio_path.name)

            print(f"  Wrote: {out_path.name}")

        except Exception as e:
            fail += 1
            with errors_log.open("a", encoding="utf-8") as f:
                f.write(f"{datetime.now().isoformat()}  {audio_path.name}  {e}\n")
            print(f"  Failed: {e}")

    print(f"\nDone. success={ok} skipped={skipped} failed={fail}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
