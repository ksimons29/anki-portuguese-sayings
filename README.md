# 🇵🇹 Anki Portuguese Automation (pt‑PT)

End‑to‑end, zero‑click pipeline to capture vocabulary anywhere, enrich it to C1‑level European Portuguese with GPT, and auto‑add cards to Anki via AnkiConnect.  
Built for European Portuguese with scheduled runs on macOS.

> **Why Anki**
> This system leans on Anki’s spaced‑repetition system to build a durable, searchable knowledge base. Your cards live locally and resurface on an optimal schedule for retention.

---

## What changed in this update

**Code changes reflected here:**

1. **No more dynamic image fetching**  
   Images are no longer downloaded or uploaded by the pipeline. Card visuals are now handled **statically in your Anki note template**. This removes flakiness and keeps the transform step fast and deterministic.  
   _Source: `transform_inbox_to_csv.py` top‑level docstring._

2. **UTF‑8‑safe LLM wrapper**  
   Introduced `_openai_compat.py` which calls the Chat Completions API via raw HTTP with strict UTF‑8 handling and an optional `MOCK_LLM=1` offline mode.  
   _Source: `_openai_compat.py`._

3. **Token‑usage logging**  
   Each run writes a monthly CSV at `{ANKI_BASE}/logs/tokens_YYYY‑MM.csv` with columns: `timestamp, model, calls, prompt_tokens, completion_tokens, total_tokens`.  
   _Source: `transform_inbox_to_csv.py` around usage summary._

4. **Helper scripts**  
   - `merge_quick.py` merges any `quick*.json/jsonl` fragments into the canonical `inbox/quick.jsonl` and archives fragments with a timestamp suffix.  
   - `check_anki_adds_today.py` prints a friendly summary of cards added **today** by reading `sayings.csv`.  
   - `import_all.sh` builds an `.apkg` from `sayings.csv` using an external tool (`anki_from_csv_dual_audio.py`) when you want a package export.

5. **Robust scheduled runner**  
   `run_pipeline.sh` now:
   - Logs `START`, `whoami`, and `pwd` for debugging scheduled runs
   - Detects “Wake from Sleep” events to annotate wake‑triggered runs
   - Pulls `OPENAI_API_KEY` from Keychain service **anki-tools-openai**
   - Clears leftover OpenAI env vars for a clean environment
   - Opens Anki quietly and runs Python unbuffered

6. **Cleaner normalization + strict mode**  
   The transformer supports `--strict` to skip long sentences and keep 1–3‑token phrases. It also has an improved lemma extractor with stopword removal and a “to VERB” heuristic.

If your old README mentioned dynamic image fetching or a different key setup, those instructions are now **removed/updated** below.

---

## TLDR

- Drop words or short phrases into:  
  `iCloud Drive/Portuguese/Anki/inbox/quick.jsonl`  
  Accepted formats per line:  
  ```json
  { "word": "print" }
  { "entries": "romantic dinner, bike lanes" }
  { "entries": ["print", "pay the bill"] }
  ```
- The scheduled runner opens Anki then executes the transformer which:
  1) normalizes each entry to a target lemma or short phrase  
  2) asks GPT for **pt‑PT** translation plus a **C1‑level** 12–22‑word example sentence  
  3) appends to `sayings.csv` and writes `last_import.csv` snapshot  
  4) adds notes via **AnkiConnect** to your deck and model  
- **Images** are not fetched by the pipeline. Use a **static image** in your Anki template if you want a logo or icon on every card.

---

## Architecture

```
iCloud (inbox) ──► merge_quick.py ──► quick.jsonl
                               ▼
                      transform_inbox_to_csv.py
                               │
                 ┌─────────────┴─────────────┐
                 ▼                           ▼
            sayings.csv                last_import.csv
                 │                           │
                 └──── addNotes via AnkiConnect (localhost:8765) ──► Anki deck

Support:
- _openai_compat.py  → UTF‑8 safe Chat Completions wrapper (OpenAI API)
- run_pipeline.sh    → Scheduled shell runner that sets env, opens Anki, runs Python
- check_anki_adds_today.py → Quick verification of today’s additions
- import_all.sh      → Optional export to .apkg (offline packaging)
```

Key properties:

- **Idempotent inputs**: duplicates are skipped if already in `sayings.csv` or within the same batch.  
- **C1 emphasis**: `sentence_pt` is explicitly requested at C1 level in pt‑PT (12–22 words).  
- **UTF‑8 safety**: stdout/stderr are forced to UTF‑8, smart quotes are sanitized.  
- **Usage telemetry**: token counts per run are logged to monthly CSVs.

---

## Files and what they do

- **`transform_inbox_to_csv.py`**  
  Main pipeline. Reads `inbox/quick.jsonl`, normalizes to lemmas, calls GPT, appends to `sayings.csv`, writes `last_import.csv`, and adds notes via AnkiConnect.  
  CLI options:  
  - `--deck` default `"Portuguese (pt-PT)"`  
  - `--model` default `"GPT Vocabulary Automater"`  
  - `--limit N` process only the first N items after de‑duplication  
  - `--strict` skip entries with more than 3 tokens or sentence‑like inputs

- **`_openai_compat.py`**  
  Minimal HTTP client for Chat Completions with strict UTF‑8 handling. Supports `MOCK_LLM=1` for an offline deterministic JSON reply.

- **`run_pipeline.sh`**  
  Scheduled runner. Gets `OPENAI_API_KEY` from Keychain service **anki-tools-openai**, clears other OpenAI env vars, opens Anki, then runs the transformer unbuffered.

- **`merge_quick.py`**  
  Consolidates `quick*.json/jsonl` fragments into `inbox/quick.jsonl`, de‑duping lines and archiving fragments with `.YYYYMMDD-HHMMSS.done` suffix.

- **`check_anki_adds_today.py`**  
  Reads `sayings.csv` and prints the English→Portuguese pairs added on today’s date.

- **`import_all.sh`**  
  Optional exporter to create an `.apkg` from `sayings.csv` with TTS, using an external tool `anki_from_csv_dual_audio.py`.

---

## Requirements

- macOS with iCloud Drive enabled
- Python 3.11+ in a virtualenv at `~/anki-tools/.venv`
- Anki desktop with **AnkiConnect** add‑on enabled (default on `http://127.0.0.1:8765`)
- OpenAI API key stored in macOS Keychain under service **anki-tools-openai**

Environment variables (all optional):

- `ANKI_BASE` defaults to `~/Library/Mobile Documents/com~apple~CloudDocs/Portuguese/Anki`  
  Note: On newer macOS this path may appear as `~/Library/CloudStorage/iCloud Drive/...`; either works if consistent.
- `LLM_MODEL` defaults to `gpt-4o-mini`
- `ANKI_URL` defaults to `http://127.0.0.1:8765`
- `MOCK_LLM=1` enables a predictable offline response for testing

---

## Setup

1) **Create folders**  
```
~/Library/Mobile Documents/com~apple~CloudDocs/Portuguese/Anki/{inbox,logs}
```

2) **Virtualenv**  
```
python3 -m venv ~/anki-tools/.venv
~/anki-tools/.venv/bin/pip install --upgrade pip
~/anki-tools/.venv/bin/pip install requests
```

3) **Store your API key in Keychain**  
```
security add-generic-password -a "$USER" -s "anki-tools-openai" -w "<YOUR_OPENAI_API_KEY>"
```

4) **AnkiConnect**  
Install and enable the AnkiConnect add‑on. Keep Anki running or let the script open it.

5) **Model and deck**  
Ensure your deck and model exist and have fields that match exactly:
```
word_en, word_pt, sentence_pt, sentence_en, date_added
```
Defaults are deck `"Portuguese (pt-PT)"` and model `"GPT Vocabulary Automater"`.
If your model has different names or fields, either update the model or run with `--deck/--model`.

---

## Running

**Manual run**
```
# Optional: merge fragments first
python3 merge_quick.py

# Transform and add to Anki
~/anki-tools/.venv/bin/python -u ~/anki-tools/transform_inbox_to_csv.py   --deck "Portuguese (pt-PT)" --model "GPT Vocabulary Automater"
```

**Quick verification**
```
python3 check_anki_adds_today.py
# Example output:
# ✅ 3 new card(s) added on 2025-10-23:
#  1. print → imprimir
#  2. romantic dinner → jantar romântico
#  3. bike lanes → ciclovias
```

**Offline test mode**
```
MOCK_LLM=1 ~/anki-tools/.venv/bin/python -u ~/anki-tools/transform_inbox_to_csv.py --limit 3
# Produces deterministic mock JSON and exercises the whole pipeline without using the API.
```

---

## Scheduling on macOS

Use `launchd` to run at 09:00, 13:00, and 19:00 local time.

1) Save a LaunchAgent plist at `~/Library/LaunchAgents/com.anki.tools.autorun.plist`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.anki.tools.autorun</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>-lc</string>
    <string>~/anki-tools/run_pipeline.sh</string>
  </array>
  <key>StartCalendarInterval</key>
  <array>
    <dict><key>Hour</key><integer>9</integer><key>Minute</key><integer>0</integer></dict>
    <dict><key>Hour</key><integer>13</integer><key>Minute</key><integer>0</integer></dict>
    <dict><key>Hour</key><integer>19</integer><key>Minute</key><integer>0</integer></dict>
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><false/>
  <key>StandardOutPath</key><string>/tmp/anki_vocab_sync.log</string>
  <key>StandardErrorPath</key><string>/tmp/anki_vocab_sync.err</string>
</dict>
</plist>
```

2) Load it:
```
launchctl unload ~/Library/LaunchAgents/com.anki.tools.autorun.plist 2>/dev/null || true
launchctl load ~/Library/LaunchAgents/com.anki.tools.autorun.plist
```

3) Verify status:
```
tail -n 100 /tmp/anki_vocab_sync.log
tail -n 100 /tmp/anki_vocab_sync.err
```

The scheduled runner uses `run_pipeline.sh`, which will open Anki quietly, retrieve your key from Keychain, and run the transformer.

---

## Input normalization rules

- If the input is **1–3 tokens**, keep as a short phrase.  
- If the input contains **“to VERB”**, extract that verb as the lemma.  
- Otherwise remove **stopwords** and pick a meaningful content token, preferring `"print"` when present, else the longest remaining token.  
- `--strict` additionally skips any entry with more than 3 tokens or that looks like a sentence.  
- Duplicates are skipped if the lemma is already present in `sayings.csv` or repeated within the same batch.

---

## Output format

`sayings.csv` header:
```
word_en,word_pt,sentence_pt,sentence_en,date_added
```

`last_import.csv` is a snapshot of the most recent batch only.  
Anki notes are created with the same fields. Use your Anki template for any static images or extra styling.

---

## Checking usage and logs

- **OpenAI portal**: review API usage at https://platform.openai.com/usage  
- **Local token logs**: monthly CSV at `{ANKI_BASE}/logs/tokens_YYYY-MM.csv`  
  Example:
  ```
  timestamp,model,calls,prompt_tokens,completion_tokens,total_tokens
  2025-10-23T19:05:12,gpt-4o-mini,6,312,420,732
  ```
- **Run logs**: see `/tmp/anki_vocab_sync.log` and `.err`, plus any printouts from `run_pipeline.sh`

---

## Troubleshooting

- **“Missing OPENAI/AZURE key”**  
  Ensure you added the key to Keychain with service **anki-tools-openai** and that `run_pipeline.sh` is used to launch the job.

- **“AnkiConnect error / connection refused”**  
  Make sure the Anki app is running and the AnkiConnect add‑on is enabled. `run_pipeline.sh` will try to open Anki for you.

- **“All candidate notes already exist”**  
  The transformer de‑dupes against `sayings.csv` and within the batch. This message is expected when there is nothing new to add.

- **Encoding issues**  
  The pipeline forces UTF‑8 on stdout/stderr and sanitizes quotes. If you see odd characters in the CSV, confirm your editor is set to UTF‑8.

---

## Security notes

- The Keychain‑stored API key is never printed. `run_pipeline.sh` only echoes a short prefix for sanity checks.  
- Avoid running with shell tracing that might echo environment variables.  
- Logs are plaintext. Do not copy complete secrets into logs.

---

## Roadmap ideas

- Optional WatchPaths trigger when new inbox files land  
- More explicit pt‑PT word choices for frequent EN→PT confusions  
- Per‑topic tagging support in the CSV

---

## License

Private, personal automation. Adapt with care.

_Last updated: 2025-10-23 22:34_
