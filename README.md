# Anki Portuguese Automation

End-to-end workflow to capture vocabulary on iPhone → iCloud inbox → GPT sentence generation → auto-import to Anki via AnkiConnect.

**Deck:** Portuguese (pt-PT)  
**Model:** GPT Vocabulary Automater (fields: word_en, word_pt, sentence_pt, sentence_en, date_added)

## Run manually
```bash
/Library/Frameworks/Python.framework/Versions/3.12/bin/python3 \
  ~/anki-tools/transform_inbox_to_csv.py \
  --deck "Portuguese (pt-PT)" --model "GPT Vocabulary Automater"

{"ts":"2025-10-16 09:30:00","src":"quick","entries":"word1, word2, word3"}


### 🔗 Data Symlink Setup

The file `data/sayings.csv` is a **symbolic link** pointing to my live master Anki CSV stored in iCloud:
/Users/koossimons/Library/Mobile Documents/comappleCloudDocs/Portuguese/Anki/sayings.csv
---

### 🧠 Summary
- ✅ The symlink works perfectly.
- 🚫 Ignore GitHub’s “No commas found” message — it’s just preview confusion.
- 📝 Add the explanation above to your README.
- 💾 You’re now fully connected — your local repo is synced to your iCloud Anki data.

Would you like me to write a short verification command so you can confirm the symlink is live and reading real CSV data from iCloud?

anki-portuguese-automation/
│
├── README.md                     ← main documentation (you’ll write below)
├── .gitignore                    ← to exclude secrets and logs
├── requirements.txt              ← future Python deps (optional)
│
├── scripts/                      ← automation logic
│   ├── transform_inbox_to_csv.py
│   ├── run_pipeline.sh
│   └── import_all.sh             ← (if still relevant)
│
├── config/
│   ├── launchd/
│   │   └── com.koossimons.anki.ptpt.plist
│   └── examples/
│       └── zshrc_snippet.txt
│
├── docs/
│   ├── architecture-diagram.md
│   ├── shortcuts-guide.md
│   ├── troubleshooting.md
│   └── changelog.md
│
└── samples/
    ├── sample_log.txt
    ├── sample_sayings.csv
    └── sample_inbox.jsonl
