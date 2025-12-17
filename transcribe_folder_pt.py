#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import os
import re
from pathlib import Path
from datetime import datetime

from openai import OpenAI

from keychain_utils import require_api_key

MODEL = os.environ.get("TRANSCRIBE_MODEL", "whisper-1")
LANGUAGE = os.environ.get("TRANSCRIBE_LANG", "pt")

AUDIO_EXTS = {
    ".m4a", ".mp3", ".wav", ".aac", ".mp4",
    ".mpeg", ".mpga", ".webm", ".aiff", ".flac", ".caf"
}

def safe_stem(name: str) -> str:
    s = re.sub(r"\s+", " ", name).strip()
    s = re.sub(r"[^\w\s\(\)\[\]\.]", "_", s)
    s = s.replace(" ", "_")
    return s[:120] if len(s) > 120 else s

def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)

def transcribe_one_file(client: OpenAI, audio_path: Path) -> str:
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
        description="Transcribe all audio files in a folder to Portuguese text using OpenAI + macOS Keychain."
    )
    ap.add_argument("folder", help="Folder containing audio files to transcribe.")
    ap.add_argument("--out-subdir", default="transcripts_txt", help="Subfolder name to write transcripts into.")
    ap.add_argument("--move-to", default="", help="If set, move processed audio files into this subfolder.")
    ap.add_argument("--skip-existing", action="store_true", help="Skip if transcript file already exists.")
    args = ap.parse_args()

    base = Path(args.folder).expanduser()
    if not base.exists():
        print(f"Folder not found: {base}")
        return 2

    try:
        api_key = require_api_key()
    except RuntimeError as e:
        print(str(e))
        return 3

    client = OpenAI(api_key=api_key)

    out_dir = base / args.out_subdir
    ensure_dir(out_dir)

    move_dir = None
    if args.move_to:
        move_dir = base / args.move_to
        ensure_dir(move_dir)

    audio_files = [p for p in sorted(base.iterdir()) if p.is_file() and p.suffix.lower() in AUDIO_EXTS]
    if not audio_files:
        print("No audio files found in folder.")
        return 0

    errors_log = out_dir / "errors.log"
    ok = 0
    fail = 0

    for audio_path in audio_files:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_name = f"{ts}_{safe_stem(audio_path.stem)}.txt"
        out_path = out_dir / out_name

        if args.skip_existing and out_path.exists() and out_path.stat().st_size > 20:
            print(f"Skip existing: {out_path.name}")
            continue

        print(f"Transcribing: {audio_path.name}")
        try:
            text = transcribe_one_file(client, audio_path)
            out_path.write_text(text + "\n", encoding="utf-8")
            ok += 1

            if move_dir is not None:
                audio_path.replace(move_dir / audio_path.name)

            print(f"Wrote: {out_path}")
        except Exception as e:
            fail += 1
            with errors_log.open("a", encoding="utf-8") as f:
                f.write(f"{datetime.now().isoformat()}  {audio_path.name}  {e}\n")
            print(f"Failed: {audio_path.name}  Error: {e}")

    print(f"Done. success={ok} failed={fail}")
    return 0 if fail == 0 else 1

if __name__ == "__main__":
    raise SystemExit(main())
