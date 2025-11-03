#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Builds an Anki .apkg from a CSV with this exact schema (order must match):
date_added,word_pt,word_en,sentence_pt,sentence_en

No audio files are bundled. Cards render TTS via Anki:
  {{tts pt_PT voices=Joana:sentence_pt}}

Defaults are pt-PT + Joana, but can be overridden with --tts-lang/--tts-voice.
"""

import argparse
import csv
import os
import random
import sys
import genanki


def parse_args():
    p = argparse.ArgumentParser(description="Generate EN↔PT deck with TTS (no media).")
    p.add_argument("--csv", required=True, help="Path to input CSV (UTF-8).")
    p.add_argument("--out", required=True, help="Output .apkg path.")
    p.add_argument("--deck-name", default="Portuguese (pt-PT)", help="Deck name.")
    p.add_argument("--model-name", default="Portuguese (pt-PT) 5-Field", help="Note type name.")
    p.add_argument("--tts-lang", default="pt_PT", help="TTS language code for {{tts ...}} (default: pt_PT).")
    p.add_argument("--tts-voice", default="Joana", help="Preferred system voice (default: Joana).")
    p.add_argument("--has-header", action="store_true", help="Set if the CSV includes a header row.")
    return p.parse_args()


def make_model(model_name: str, tts_lang: str, tts_voice: str) -> genanki.Model:
    model_id = random.randrange(1 << 30, 1 << 31)
    tts_tag = f"{{{{tts {tts_lang} voices={tts_voice}:sentence_pt}}}}"

    return genanki.Model(
        model_id,
        model_name,
        fields=[
            {"name": "date_added"},
            {"name": "word_pt"},
            {"name": "word_en"},
            {"name": "sentence_pt"},
            {"name": "sentence_en"},
        ],
        templates=[
            # EN → PT
            {
                "name": "EN→PT",
                "qfmt": "{{word_en}}",
                "afmt": (
                    "{{FrontSide}}<hr id=answer>"
                    "{{word_pt}}<br><br>"
                    "{{sentence_pt}}<br>"
                    f"{tts_tag}<br><br>"
                    "{{sentence_en}}"
                ),
            },
            # PT → EN
            {
                "name": "PT→EN",
                "qfmt": "{{word_pt}}",
                "afmt": (
                    "{{FrontSide}}<hr id=answer>"
                    "{{word_en}}<br><br>"
                    "{{sentence_pt}}<br>"
                    f"{tts_tag}<br><br>"
                    "{{sentence_en}}"
                ),
            },
        ],
        css="""
.card { font-family: -apple-system, Helvetica, Arial; font-size: 20px; line-height: 1.45; }
hr#answer { margin: 12px 0; }
""",
    )


def read_rows(csv_path: str, has_header: bool):
    rows = []
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        if has_header:
            next(reader, None)  # skip header
        for i, r in enumerate(reader, start=1):
            if len(r) != 5:
                raise ValueError(
                    f"Row {i}: expected 5 columns (date_added,word_pt,word_en,sentence_pt,sentence_en) but got {len(r)}"
                )
            rows.append(r)
    return rows


def main():
    args = parse_args()

    # Build model and deck
    model = make_model(args.model_name, args.tts_lang, args.tts_voice)
    deck_id = random.randrange(1 << 30, 1 << 31)
    deck = genanki.Deck(deck_id, args.deck_name)

    # Read CSV (strict order)
    data_rows = read_rows(args.csv, args.has_header)

    for date_added, word_pt, word_en, sentence_pt, sentence_en in data_rows:
        note = genanki.Note(
            model=model,
            fields=[date_added, word_pt, word_en, sentence_pt, sentence_en],
        )
        deck.add_note(note)

    # Write package (no media files)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    pkg = genanki.Package(deck)
    pkg.write_to_file(args.out)
    print(f"✅ Wrote deck: {args.out}")


if __name__ == "__main__":
    sys.exit(main())
