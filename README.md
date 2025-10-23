# 🇵🇹 Anki Portuguese Automation (pt‑PT)

End‑to‑end, zero‑click pipeline to capture vocabulary anywhere, enrich it to C1‑level European Portuguese with GPT, and auto‑add cards to Anki via AnkiConnect.

> **Why Anki**
> This system leans on Anki’s spaced‑repetition system to build a durable, searchable knowledge base. Cards resurface on an optimal schedule for long‑term retention.

---

## TLDR

- Drop words/short phrases into: `iCloud Drive/Portuguese/Anki/inbox/quick.jsonl`
- The runner opens Anki, normalizes inputs, asks GPT for **pt‑PT** translation + **C1‑level** example sentence, appends to `sayings.csv`, snapshots `last_import.csv`, and adds notes via **AnkiConnect**.
- **Images**: handled by your Anki template (static). The pipeline does **not** fetch images.

---

## Architecture

![Architecture](docs/architecture.png)

**Key properties**
- **Idempotent inputs**: duplicates skipped (existing `sayings.csv` or same batch).  
- **C1 emphasis**: `sentence_pt` requested at C1 in pt‑PT (≈12–22 words).  
- **UTF‑8 safety** throughout.  
- **Usage telemetry**: monthly token logs in `{ANKI_BASE}/logs/tokens_YYYY‑MM.csv`.

---

## Files and what they do

- **`transform_inbox_to_csv.py`** – Main pipeline (normalize → LLM → CSVs → AnkiConnect).  
  CLI: `--deck`, `--model`, `--limit N`, `--strict`.
- **`_openai_compat.py`** – Minimal, UTF‑8‑safe Chat Completions client. `MOCK_LLM=1` for offline tests.
- **`run_pipeline.sh`** – Scheduled runner: pulls key from Keychain **anki-tools-openai**, clears stray env vars, opens Anki, runs Python unbuffered.
- **`merge_quick.py`** – Merges `quick*.json/jsonl` into `inbox/quick.jsonl` and archives fragments.
- **`check_anki_adds_today.py`** – Lists cards added today from `sayings.csv`.
- **`import_all.sh`** – Optional exporter to `.apkg` with external CSV→Anki tooling.

---

## Requirements

- macOS with iCloud Drive enabled
- Python 3.11+ (virtualenv at `~/anki-tools/.venv`)
- Anki desktop + **AnkiConnect** (default `http://127.0.0.1:8765`)
- OpenAI API key stored in Keychain service **anki-tools-openai**

Optional env vars:
- `ANKI_BASE` → defaults to `~/Library/Mobile Documents/com~apple~CloudDocs/Portuguese/Anki`  
- `LLM_MODEL` → default `gpt-4o-mini`  
- `ANKI_URL` → default `http://127.0.0.1:8765`  
- `MOCK_LLM=1` → deterministic offline responses (no API calls)

---

## Setup

```bash
# Folders
mkdir -p ~/Library/Mobile\ Documents/com~apple~CloudDocs/Portuguese/Anki/{inbox,logs}

# Virtualenv
python3 -m venv ~/anki-tools/.venv
~/anki-tools/.venv/bin/pip install --upgrade pip requests

# Store API key in Keychain
security add-generic-password -a "$USER" -s "anki-tools-openai" -w "<YOUR_OPENAI_API_KEY>"
```

Ensure your Anki deck/model exist with fields:
```
word_en,word_pt,sentence_pt,sentence_en,date_added
```

---

## Running

```bash
# Optional: merge fragments first
python3 merge_quick.py

# Transform and add to Anki
~/anki-tools/.venv/bin/python -u ~/anki-tools/transform_inbox_to_csv.py   --deck "Portuguese (pt-PT)" --model "GPT Vocabulary Automater"
```

**Quick verification**
```bash
python3 check_anki_adds_today.py
```

**Offline test mode (no billing)**
```bash
MOCK_LLM=1 ~/anki-tools/.venv/bin/python -u ~/anki-tools/transform_inbox_to_csv.py --limit 3
```

---

## Scheduling (launchd)

Create `~/Library/LaunchAgents/com.anki.tools.autorun.plist` to run at 09:00, 13:00, 19:00:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.anki.tools.autorun</string>
  <key>ProgramArguments</key>
  <array><string>/bin/bash</string><string>-lc</string><string>~/anki-tools/run_pipeline.sh</string></array>
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
</dict></plist>
```
Load it:
```bash
launchctl unload ~/Library/LaunchAgents/com.anki.tools.autorun.plist 2>/dev/null || true
launchctl load ~/Library/LaunchAgents/com.anki.tools.autorun.plist
```

---

## Input normalization (summary)

- 1–3 tokens → keep as short phrase.  
- “to VERB” → extract lemma (verb).  
- Otherwise strip stopwords and keep a meaningful content token (prefer “print”, else longest).  
- `--strict` skips sentence‑like entries or >3 tokens.  
- De‑dupe against existing `sayings.csv` and within batch.

---

## Output format

`sayings.csv`:
```
word_en,word_pt,sentence_pt,sentence_en,date_added
```
`last_import.csv` holds only the latest batch. Anki fields mirror the CSV.

---

## Logs & usage

- OpenAI usage: https://platform.openai.com/usage  
- Local token log: `{ANKI_BASE}/logs/tokens_YYYY-MM.csv`  
- Runner logs: `/tmp/anki_vocab_sync.log` and `.err`

---

## Troubleshooting

- **Key missing**: confirm Keychain item `anki-tools-openai` exists.  
- **AnkiConnect not found**: ensure Anki is running & add‑on enabled.  
- **“All candidate notes already exist”**: nothing new after de‑duplication.

---

## Security

Keychain‑stored API key is never printed; runner only prints a short prefix for sanity checks. Avoid echoing secrets in logs.

---

## License

Private, personal automation. Adapt with care.

---

## Changelog (recent)

- **2025-10-23**  
  - Moved “What changed” to the end (this section).  
  - Restored a **visible architecture image** at `docs/architecture.png` and embedded it.  
  - Clarified that images are static in the Anki template (no fetching).  
  - Documented `MOCK_LLM=1` offline mode, token logs, and helper scripts.
