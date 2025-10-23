# 🇵🇹 Anki Portuguese Automation — Unified README
*Updated: 2025-10-23*

End‑to‑end system to **capture vocabulary on any Apple device (iPhone, iPad, Mac)**,
enrich it to **C1‑level European Portuguese**, and **load into Anki** via **AnkiConnect**.
This version matches your preferred unified structure, includes a clean **architecture diagram**,
and explains **embedded audio (pt‑PT TTS)** on cards.

---

## 🧭 What this does (in 30 seconds)
- You **add** English or Portuguese words/short phrases from any device.
- They’re **appended** to a single **iCloud JSONL inbox**:
  ```
  /Users/koossimons/Library/Mobile Documents/com~apple~CloudDocs/Portuguese/Anki/inbox/quick.jsonl
  ```
- The transformer **normalizes, deduplicates, and enriches** items using GPT, producing **pt‑PT** translations
  with a **C1** example sentence (≈12–22 words).
- Notes are inserted into Anki (Deck **Portuguese (pt‑PT)**, Model **GPT Vocabulary Automater**) via **AnkiConnect**.

> **Images:** the pipeline does **not** fetch images anymore. If desired, add a **static image** to the Anki card template.

---

## 🧱 Architecture

![Architecture](docs/architecture.png)

**Key properties**
- **Idempotent inputs** (skips duplicates already in `sayings.csv` or same batch)
- **C1 emphasis** (C1‑level pt‑PT example sentence)
- **UTF‑8 safety** throughout
- **Usage telemetry**: monthly token logs in `{ANKI_BASE}/logs/tokens_YYYY‑MM.csv`

Text‑only fallback:

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

---

## 🔊 Audio (pt‑PT TTS on every Portuguese sentence)

You want **every Portuguese sentence to have voice automatically**. Use Anki’s built‑in **TTS** tag in your
note templates so audio is generated **at review time** (no audio files needed).

**Recommended Back template snippet**
```html
<div>{word_en} → <b>{word_pt}</b></div>
<div>{sentence_pt}</div>

<!-- macOS/iOS pt‑PT voice (Joana). Adjust speed/pitch if you like. -->
{tts pt_PT voices=Joana:sentence_pt}
```

**Why this works**
- Anki (desktop + AnkiMobile) renders the `{tts ...:FIELD}` tag using the platform’s pt‑PT system voice (e.g., **Joana** on macOS/iOS).
- No MP3 files are stored; audio is generated on‑the‑fly, keeping the collection lean.
- This guarantees **every card** with `sentence_pt` will **speak** when shown.

**Alternative (pre‑render audio)**  
If you prefer actual audio files baked into the deck, use `import_all.sh` with an external CSV→APKG tool
that generates audio from `sentence_pt`. This makes cards portable without relying on local voices, at the cost
of larger media size.

---

## 📂 Data contract (JSONL inbox)
Accepted shapes per line in `quick.jsonl`:
```json
{ "entries": "print, romantic dinner, bike lanes" }
{ "entries": ["print", "pay the bill"] }
{ "word": "print" }
```
Notes:
- The transformer splits `entries`, trims, lowercases, and de‑dupes per run.
- Use **short words/phrases** (1–3 tokens). “to VERB” extracts the verb lemma.
- `--strict` mode skips sentence‑like inputs or >3 tokens.

---

## ⚙️ Setup (once)

```bash
# Folders
mkdir -p ~/Library/Mobile\ Documents/com~apple~CloudDocs/Portuguese/Anki/{inbox,logs}

# Python env
python3 -m venv ~/anki-tools/.venv
~/anki-tools/.venv/bin/pip install --upgrade pip requests

# Store OpenAI API key in Keychain
security add-generic-password -a "$USER" -s "anki-tools-openai" -w "<YOUR_OPENAI_API_KEY>"

# Ensure Anki has the AnkiConnect add-on enabled
```

Optional env overrides:
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
Create `~/Library/LaunchAgents/com.anki.tools.autorun.plist` (09:00, 13:00, 19:00). Then:
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
```bash
MOCK_LLM=1 ~/anki-tools/.venv/bin/python -u ~/anki-tools/transform_inbox_to_csv.py --limit 3
```

---

## 🧯 Troubleshooting
- **Key missing** → ensure Keychain item `anki-tools-openai` exists.
- **AnkiConnect refused** → Anki running & add‑on enabled.
- **“All candidate notes already exist”** → nothing new after de‑duplication.
- **Encoding** → editor must be UTF‑8; pipeline enforces UTF‑8 on stdout/stderr.

---

## 📝 License
Private, personal automation. Adapt with care.

---

## 🗒️ Changelog (recent)
- **2025-10-23** — Docs: added **proper architecture diagram** image and an explicit **Audio (pt‑PT TTS)** section.
  Re‑confirmed that **dynamic image fetching** is removed; visuals should be **static** in the Anki template.
