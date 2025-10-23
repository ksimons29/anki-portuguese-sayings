# 🇵🇹 Anki Portuguese Automation — Unified README
*Updated: 2025-10-23*

End‑to‑end system to **capture vocabulary on any Apple device (iPhone, iPad, Mac)**,
enrich it to **C1‑level European Portuguese**, and **load into Anki** via **AnkiConnect**.
This README keeps your preferred unified structure and wording while aligning with the
current codebase.

---

## 🧭 What this does (in 30 seconds)
- You **add** English or Portuguese words/short phrases from any device.
- They’re **appended** to a single **iCloud JSONL inbox**:
  ```
  /Users/koossimons/Library/Mobile Documents/com~apple~CloudDocs/Portuguese/Anki/inbox/quick.jsonl
  ```
- The transformer **normalizes, deduplicates, and enriches** items using GPT, producing **pt‑PT** translations
  with **C1** example sentences (≈12–22 words).
- Notes are inserted into Anki (Deck **Portuguese (pt‑PT)**, Model **GPT Vocabulary Automater**) via **AnkiConnect**.

> **Images:** the pipeline no longer fetches images. If you want visuals, add a **static image** to the Anki card template.

---

## 🧱 Architecture

```
iCloud Inbox (quick*.json / quick*.jsonl)
        │
        ▼
merge_quick.py  ──►  inbox/quick.jsonl
        │
        ▼
transform_inbox_to_csv.py      ──►  sayings.csv        (canonical store)
        │                      └──► last_import.csv    (last batch snapshot)
        │
        └──► AnkiConnect (http://127.0.0.1:8765) ──► Anki deck “Portuguese (pt‑PT)”

Support:
- _openai_compat.py      UTF‑8‑safe Chat Completions client (MOCK_LLM=1 offline test mode)
- run_pipeline.sh        Scheduled runner (Keychain key load, open Anki, run Python unbuffered)
- check_anki_adds_today.py  Quick verification of today's adds from sayings.csv
- import_all.sh          Optional: export CSV to .apkg with external tool
```

**Key properties**
- **Idempotent inputs** (skips duplicates already in `sayings.csv` or same batch)
- **C1 emphasis** (C1‑level pt‑PT example sentence)
- **UTF‑8 safety** throughout
- **Usage telemetry**: monthly token logs in `{ANKI_BASE}/logs/tokens_YYYY‑MM.csv`

---

## 📂 Data contract (JSONL inbox)
Each line in `quick.jsonl` is a **valid JSON object**. Accepted shapes:

```json
{ "entries": "print, romantic dinner, bike lanes" }
{ "entries": ["print", "pay the bill"] }
{ "word": "print" }
```

**Notes**
- The transformer splits `entries`, trims, lowercases, and dedupes per run.
- Use **short words/phrases** (1–3 tokens). For “to VERB” inputs, it extracts the **verb lemma**.
- `--strict` mode skips long/sentence‑like inputs.

---

## ⚙️ Setup (once)

```bash
# Folders
mkdir -p ~/Library/Mobile\ Documents/com~apple~CloudDocs/Portuguese/Anki/{inbox,logs}

# Python env
python3 -m venv ~/anki-tools/.venv
~/anki-tools/.venv/bin/pip install --upgrade pip requests

# Store OpenAI API key in Keychain (service name is fixed)
security add-generic-password -a "$USER" -s "anki-tools-openai" -w "<YOUR_OPENAI_API_KEY>"

# Ensure Anki has the AnkiConnect add-on enabled
```

Default paths and env (overrides optional):
- `ANKI_BASE=~/Library/Mobile Documents/com~apple~CloudDocs/Portuguese/Anki`
- `LLM_MODEL=gpt-4o-mini`
- `ANKI_URL=http://127.0.0.1:8765`
- `MOCK_LLM=1` for offline tests (no API calls)

---

## 🚀 Run options

### A) One‑liner (manual)
```bash
~/anki-tools/.venv/bin/python -u ~/anki-tools/transform_inbox_to_csv.py   --deck "Portuguese (pt-PT)" --model "GPT Vocabulary Automater"
```

### B) Full pipeline runner (recommended)
```bash
bash ~/anki-tools/run_pipeline.sh
```
What it does:
- Logs start time, `whoami`, and `pwd` for scheduled run debugging
- Pulls `OPENAI_API_KEY` from Keychain service **anki-tools-openai**
- Clears stray OpenAI env vars
- Opens Anki quietly and runs Python unbuffered

### C) Merge fragments first (optional)
```bash
python3 ~/anki-tools/merge_quick.py
```

---

## ⏰ Scheduling (launchd)
Run at 09:00, 13:00, and 19:00 local time. Create `~/Library/LaunchAgents/com.anki.tools.autorun.plist`:

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
launchctl load  ~/Library/LaunchAgents/com.anki.tools.autorun.plist
```

---

## 🔍 Verification & logs
```bash
python3 ~/anki-tools/check_anki_adds_today.py
tail -n 100 /tmp/anki_vocab_sync.log
tail -n 100 /tmp/anki_vocab_sync.err
```
- OpenAI usage: https://platform.openai.com/usage  
- Monthly token log: `{ANKI_BASE}/logs/tokens_YYYY-MM.csv`

---

## 🧪 Offline test mode
Run without billing the API:
```bash
MOCK_LLM=1 ~/anki-tools/.venv/bin/python -u ~/anki-tools/transform_inbox_to_csv.py --limit 3
```

---

## 🧯 Troubleshooting
- **Key missing** → ensure Keychain item `anki-tools-openai` exists.
- **AnkiConnect refused** → Anki must be running; add‑on enabled.
- **“All candidate notes already exist”** → nothing new after de‑duplication.
- **Encoding** → editor must be UTF‑8; pipeline enforces UTF‑8 on stdout/stderr.

---

## 📝 License
Private, personal automation. Adapt with care.

---

## 🗒️ Changelog (recent)
- **2025-10-23** — Docs: aligned to the **Unified** layout you prefer; **removed dynamic image fetching** from the pipeline and clarified that visuals should be handled **statically in the Anki template**. Kept GitHub‑friendly formatting and added an ASCII architecture diagram.
