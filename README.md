# Anki Portuguese Automation

End-to-end workflow to capture vocab on iPhone → iCloud inbox → GPT sentence generation → auto-import to Anki via AnkiConnect.

- **Deck:** `Portuguese (pt-PT)`  
- **Model:** `GPT Vocabulary Automater`  
  **Fields:** `word_en, word_pt, sentence_pt, sentence_en, date_added`

---

## What it does

1. You add words on iPhone/Mac via a Shortcut.
2. The Shortcut appends one JSON line to **iCloud** at:
   ```
   ~/Library/CloudStorage/iCloud Drive/Portuguese/Anki/inbox/quick.jsonl
   ```
3. Twice a day (09:00 & 21:00), a macOS LaunchAgent runs `run_pipeline.sh`:
   - opens Anki (AnkiConnect),
   - **sanitizes** the inbox (fixes … — – “ ” ’ etc.),
   - calls GPT to generate bilingual example sentences,
   - adds notes to Anki,
   - archives a copy as `quick.YYYYMMDD-HHMMSS.done`,
   - **truncates** `quick.jsonl` so the Shortcut keeps appending to the same file.
4. CSV snapshots are written under `data/` (git-ignored).

---

## Requirements

- macOS + iCloud Drive
- **Anki** desktop with **AnkiConnect** add-on
- Python 3.11+ (repo uses a local `.venv`)
- OpenAI API key (project or classic)

---

## Setup

```bash
cd ~/anki-tools
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip "openai>=1.0.0"
```

---

## iPhone/Mac Shortcut (append to **one** file)

Create a Shortcut with these actions (in order):

1. **Ask for Text** — Prompt: `Word(s) (English or Portuguese)`
2. **Current Date** → **Format Date** — `yyyy-MM-dd HH:mm:ss`
3. **Text**
   ```
   {"ts":"${Formatted Date}","src":"quick","entries":"${Provided Input}"}
   ```
4. **Append Text**
   - **To:** _Folder_ → `iCloud Drive → Portuguese → Anki → inbox`
   - **File Path:** `quick.jsonl`
   - **Make New Line:** ✅

This guarantees a single file at:
```
~/Library/CloudStorage/iCloud Drive/Portuguese/Anki/inbox/quick.jsonl
```

---

## Scripts (what each file does)

### `run_pipeline.sh`
- Opens Anki (safe if already open)
- (Optional) runs `merge_inbox.sh`
- Runs **sanitizer** → **transformer**
- Archives **copy** and **truncates** `quick.jsonl` (keeps the filename)
- Uses the venv’s Python and reads `OPENAI_API_KEY`

### `sanitize_quick_jsonl.py`
Normalizes Unicode punctuation (`, … — – “ ” ’`) to ASCII to avoid legacy encoder errors.

### `transform_inbox_to_csv.py`
- Reads JSONL lines from `quick.jsonl`
- Calls GPT (via `_openai_compat.py`) to produce bilingual sentences
- Adds notes to Anki via AnkiConnect
- Writes/updates CSV under `data/`

### `_openai_compat.py`
Shim that supports **project keys (`sk-proj-…`)** using the new OpenAI SDK while returning the **old response shape** so the transformer code doesn’t change.

---

## Manual run

Add a line (or use your Shortcut), then run the pipeline:

```bash
# Append a quick test entry
printf '{"ts":"%s","src":"quick","entries":"window, receive"}\n' \
  "$(date '+%Y-%m-%d %H:%M:%S')" >> \
  "$HOME/Library/CloudStorage/iCloud Drive/Portuguese/Anki/inbox/quick.jsonl"

# Run once
source .venv/bin/activate
export OPENAI_API_KEY='sk-…'   # project or classic
bash ./run_pipeline.sh
```

Optional “transform only” run:

```bash
/Library/Frameworks/Python.framework/Versions/3.12/bin/python3 \
  ~/anki-tools/transform_inbox_to_csv.py \
  --deck "Portuguese (pt-PT)" --model "GPT Vocabulary Automater"
```

**Example JSONL line:**
```json
{"ts":"2025-10-16 09:30:00","src":"quick","entries":"word1, word2, word3"}
```

---

## Scheduling (twice a day)

An example LaunchAgent template lives at:
```
launch/com.koos.anki-pipeline.plist.example
```

Install it like this:

```bash
cp launch/com.koos.anki-pipeline.plist.example \
   ~/Library/LaunchAgents/com.koos.anki-pipeline.plist

# Edit the copy to insert your API key:
#   <key>OPENAI_API_KEY</key><string>sk-…</string>

plutil -lint ~/Library/LaunchAgents/com.koos.anki-pipeline.plist
launchctl bootstrap gui/$UID ~/Library/LaunchAgents/com.koos.anki-pipeline.plist
launchctl enable   gui/$UID/com.koos.anki-pipeline
launchctl kickstart -k gui/$UID/com.koos.anki-pipeline
```

Verify:

```bash
launchctl print gui/$UID/com.koos.anki-pipeline | grep -E 'state|last exit|calendar'
tail -n 50 "$HOME/Library/CloudStorage/iCloud Drive/Portuguese/Anki/logs/autorun.out.log"
```

---

## Data & symlink

`data/sayings.csv` is a **symlink** to the live Anki CSV in iCloud:

```
~/Library/CloudStorage/iCloud Drive/Portuguese/Anki/sayings.csv
```

Verify:

```bash
ls -l data/sayings.csv
head -n 3 data/sayings.csv
```

> If anything still points at the legacy `Mobile Documents` path, create a bridge:
> ```bash
> mkdir -p "$HOME/Library/Mobile Documents"
> ln -sfn "$HOME/Library/CloudStorage/iCloud Drive" \
>        "$HOME/Library/Mobile Documents/com~apple~CloudDocs"
> ```

---

## Repo layout

```
anki-tools/
├── run_pipeline.sh
├── sanitize_quick_jsonl.py
├── _openai_compat.py
├── merge_inbox.sh
├── transform_inbox_to_csv.py
├── launch/
│   └── com.koos.anki-pipeline.plist.example
├── data/                  # CSV output (git-ignored)
├── logs/                  # runtime logs (git-ignored)
└── README.md
```

---

## .gitignore (recommended)

``>
.DS_Store
.venv/
__pycache__/
*.pyc
logs/
*.log
*.done
data/*.csv
*.apkg
*.env
*.env.local
*.plist
!launch/*.plist.example
backups/
```

Never commit your real API key or your machine’s LaunchAgent.

---

## Troubleshooting

- **401 Unauthorized**  
  The OpenAI key isn’t in the environment. Add it to your shell or LaunchAgent `<EnvironmentVariables>`.

- **`'latin-1' codec can't encode …`**  
  The sanitizer handles this automatically. Ensure `sanitize_quick_jsonl.py` runs before the transformer (it does in `run_pipeline.sh`).

- **“No quick.jsonl to process”**  
  The file is empty (expected after a successful run). Add words via the Shortcut and run again (or wait for the next schedule).

- **Shortcut writes to the wrong place**  
  In **Append Text**, target the **inbox folder** and set **File Path = `quick.jsonl`**. Don’t feed variables into any “Get File from Folder” action.

---

## Verify end-to-end

```bash
INBOX="$HOME/Library/CloudStorage/iCloud Drive/Portuguese/Anki/inbox"

# Add a test line
printf '{"ts":"%s","src":"quick","entries":"window, receive"}\n' \
  "$(date '+%Y-%m-%d %H:%M:%S')" >> "$INBOX/quick.jsonl"

# Run once
source .venv/bin/activate
export OPENAI_API_KEY='sk-…'
bash ./run_pipeline.sh

# Confirm archive + CSV
ls -lt "$INBOX" | head
ls -l  "$INBOX/quick.jsonl"     # should exist, usually 0 bytes (truncated)
NEW=$(ls -t data/*.csv 2>/dev/null | head -1); echo "$NEW"; [ -n "$NEW" ] && sed -n '1,10p' "$NEW"
```
