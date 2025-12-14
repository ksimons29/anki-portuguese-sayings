# Aurora Pilot – Local Test Project

This folder is a self-contained staging area for a new customer (“Aurora Language Lab”) who wants to send curated vocabulary into their own Anki collection. It reuses the main `transform_inbox_to_csv.py` pipeline but isolates all data, logs, and config inside `clients/new_customer_demo/anki_base/` so we can rehearse the workflow without touching the production iCloud inbox.

## Folder layout

```
clients/new_customer_demo/
├─ README.md                # this file
├─ run_demo.sh              # helper runner that wires up env + inbox overrides
└─ anki_base/
   ├─ inbox/
   │  └─ quick.jsonl        # sample words Aurora handed over for QA
   ├─ logs/                 # token + pipeline logs (created on demand)
   ├─ sayings.csv           # will be generated after a successful dry-run/production pass
   └─ last_import.csv       # last batch snapshot for the customer
```

## Sample inbox

`anki_base/inbox/quick.jsonl` already contains a small slice of Aurora's backlog so we can verify the experience end-to-end before pointing the Shortcut at their iCloud Drive.

```
{"word": "orçamento"}
{"entries": ["manter compromisso", "deadline flexível"]}
{"word": "bureaucracy"}
{"entries": ["negociação difícil", "fazer follow-up com o cliente"]}
```

Feel free to replace this file with real exports from the customer—`run_demo.sh` never overwrites it.

## How to run the customer’s test pipeline

```bash
cd ~/anki-tools
./clients/new_customer_demo/run_demo.sh            # default: dry-run to avoid touching Anki
CUSTOMER_DRY_RUN=0 ./clients/new_customer_demo/run_demo.sh   # production (writes CSV + pushes to Anki)
```

What the script does:
1. Sets `ANKI_BASE` to `clients/new_customer_demo/anki_base`, so the Python transformer reads/writes inside this folder only.
2. Points the inbox override at `anki_base/inbox/quick.jsonl`.
3. Uses customer-specific defaults: deck `Aurora Portuguese (pt-PT)` and note type `Customer GPT Vocabulary`.
4. Runs the existing `transform_inbox_to_csv.py`, forwarding `--dry-run` unless you set `CUSTOMER_DRY_RUN=0`.

> **Prereqs**: Have the usual OpenAI credentials in Keychain (`anki-tools-openai` + project id) and Anki+AnkiConnect running. Because this is a staging project you can optionally run with `MOCK_LLM=1` to keep everything offline.

## Customizing for another customer

- Copy this folder, rename it (e.g., `clients/acme_beta/`), and update the deck/model variables inside `run_demo.sh`.
- Drop the customer’s JSONL export into the new `anki_base/inbox/quick.jsonl`.
- Run the script in dry-run mode first to confirm normalization and dedupe rules behave as expected.

This setup keeps each customer’s assets isolated while still exercising the exact same ingestion logic that will run in production.
