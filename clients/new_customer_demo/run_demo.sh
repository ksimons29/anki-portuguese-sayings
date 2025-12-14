#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}" )" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ANKI_BASE_PATH="${ANKI_BASE:-$SCRIPT_DIR/anki_base}"
INBOX_FILE="${CUSTOMER_INBOX:-$ANKI_BASE_PATH/inbox/quick.jsonl}"
DECK="${CUSTOMER_DECK:-Aurora Portuguese (pt-PT)}"
MODEL="${CUSTOMER_MODEL:-Customer GPT Vocabulary}"
LOG_LEVEL="${CUSTOMER_LOG_LEVEL:-INFO}"
LIMIT="${CUSTOMER_LIMIT:-0}"
DRY_RUN_FLAG="${CUSTOMER_DRY_RUN:-1}"
PY_BIN="${CUSTOMER_PYTHON:-python3}"
EXTRA_ARGS=${CUSTOMER_EXTRA_ARGS:-}

mkdir -p "$ANKI_BASE_PATH/inbox" "$ANKI_BASE_PATH/logs"
export ANKI_BASE="$ANKI_BASE_PATH"

if [[ ! -f "$INBOX_FILE" ]]; then
  echo "[err] Expected inbox file at $INBOX_FILE" >&2
  exit 1
fi

CMD=("$PY_BIN" "$REPO_ROOT/transform_inbox_to_csv.py"
     --deck "$DECK"
     --model "$MODEL"
     --log-level "$LOG_LEVEL"
     --inbox-file "$INBOX_FILE"
     --dry-run "$DRY_RUN_FLAG"
)

if [[ "$LIMIT" != "0" ]]; then
  CMD+=(--limit "$LIMIT")
fi

if [[ -n "$EXTRA_ARGS" ]]; then
  # shellcheck disable=SC2206
  EXTRA=( $EXTRA_ARGS )
  CMD+=("${EXTRA[@]}")
fi

printf '[config] repo=%s\n[config] anki_base=%s\n[config] deck=%s | model=%s\n' \
  "$REPO_ROOT" "$ANKI_BASE" "$DECK" "$MODEL"
printf '[config] inbox=%s\n[config] dry_run=%s limit=%s log_level=%s\n' \
  "$INBOX_FILE" "$DRY_RUN_FLAG" "$LIMIT" "$LOG_LEVEL"

exec "${CMD[@]}"
