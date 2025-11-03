#!/usr/bin/env python3
import csv
import datetime
import os
from pathlib import Path

BASE = Path(os.environ.get(
    "ANKI_BASE",
    "/Users/koossimons/Library/Mobile Documents/com~apple~CloudDocs/Portuguese/Anki",
))
MASTER = BASE / "sayings.csv"

def load_today_cards():
    today = datetime.date.today().isoformat()

    if not MASTER.exists():
        print(f"No sayings.csv file found at: {MASTER}")
        return

    with MASTER.open("r", encoding="utf-8", newline="") as f:
        r = csv.reader(f)
        header = next(r, [])
        idx = {name: i for i, name in enumerate(header)}

        required = ["word_en", "word_pt", "sentence_pt", "sentence_en", "date_added"]
        if not all(k in idx for k in required):
            print(f"CSV header missing expected columns. Found: {header}")
            return

        found = []
        for row in r:
            if len(row) < len(required):
                continue
            if row[idx["date_added"]] == today:
                en = row[idx["word_en"]]
                pt = row[idx["word_pt"]]
                found.append((en, pt))

    if not found:
        print(f"⚠️  No new cards added on {today}.")
    else:
        print(f"✅ {len(found)} new card(s) added on {today}:")
        for i, (en, pt) in enumerate(found, 1):
            print(f"{i:>2}. {en} → {pt}")

if __name__ == "__main__":
    load_today_cards()
