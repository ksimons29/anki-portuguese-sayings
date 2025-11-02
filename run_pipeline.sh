#!/usr/bin/env bash
unset ANKI_BASE
set -euo pipefail

# ---- Env ----
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
export PYTHONIOENCODING=UTF-8

ICLOUD_ROOT="$HOME/Library/Mobile Documents/com~apple~CloudDocs"
[ -d "$ICLOUD_ROOT" ] || { echo "[err] iCloud root not found: $ICLOUD_ROOT"; exit 1; }

ANKI_DATA_DIR="$ICLOUD_ROOT/Portuguese/Anki"
INBOX="$ANKI_DATA_DIR/inbox"
QUICK="$INBOX/quick.jsonl"
TODAY="$(date +%F)"
ROTATE_STAMP="$INBOX/.rotated-$TODAY"
LOGDIR="$ANKI_DATA_DIR/logs"

mkdir -p "$INBOX" "$LOGDIR"

# ---- Optional log redirection (default ON unless NO_REDIRECT=1) ----
if [[ -z "${NO_REDIRECT:-}" ]]; then
  exec >>"$LOGDIR/pipeline.$TODAY.log" 2>>"$LOGDIR/pipeline.$TODAY.err"
fi

# Start tracing after redirection so logs include the trace
set -x

# ---- Keep system awake during this run ----
/usr/bin/caffeinate -i -w $$ &

# ---- Network gate ----
require_network() {
  local tries=6
  while ! /sbin/ping -q -c1 -t1 1.1.1.1 >/dev/null 2>&1; do
    ((tries--)) || return 1
    sleep 3
  done
}
require_network || { echo "[net] offline; aborting"; exit 0; }

# ---- Open Anki and wait for AnkiConnect ----
open -gj -a "Anki" || true

wait_for_anki() {
  local tries=30
  while :; do
    if curl -s http://127.0.0.1:8765 -X POST \
         -d '{"action":"version","version":6}' | grep -q '"result"'; then
      echo "[anki] AnkiConnect ready"
      return 0
    fi
    ((tries--)) || break
    sleep 1
  done
  return 1
}
wait_for_anki || { echo "[anki] AnkiConnect not ready after 30s"; exit 0; }

# ---- Secrets from Keychain (mask xtrace while reading) ----
XTRACE_WAS_ON="${-//[^x]/}"
set +x
# Try service names in order: customize to your setup
OPENAI_API_KEY="${OPENAI_API_KEY:-}"
if [[ -z "$OPENAI_API_KEY" ]]; then
  for SVC in "anki-tools-openai" "OPENAI_API_KEY" "openai_api_key"; do
    if KEY_FROM_KC="$(/usr/bin/security find-generic-password -a "$USER" -s "$SVC" -w 2>/dev/null)"; then
      OPENAI_API_KEY="$KEY_FROM_KC"
      break
    fi
  done
fi
if [[ -z "$OPENAI_API_KEY" ]]; then
  echo "[err] OPENAI_API_KEY not set and not found in Keychain." >&2
  exit 1
fi
# sanitize curly quotes and newlines
OPENAI_API_KEY="$(printf %s "$OPENAI_API_KEY" | LC_ALL=C tr -d '\r\n' | tr -d '“”‘’')"
export OPENAI_API_KEY
# If you use Azure, set OPENAI_BASE_URL, OPENAI_API_VERSION, and LLM_MODEL via Keychain or env and DO NOT unset them.
# For public OpenAI we keep these unset:
unset OPENAI_BASE_URL OPENAI_API_BASE OPENAI_ORG_ID

# re-enable xtrace if it was on
[[ -n "$XTRACE_WAS_ON" ]] && set -x
echo "key_prefix=${OPENAI_API_KEY:0:6}"

# ---- Prepare scratch copy of the inbox ----
SCRATCH="$(mktemp -t quick_copy.XXXXXX.jsonl)"
if ! /bin/cp -f "$QUICK" "$SCRATCH" 2>/dev/null; then
  echo "[inbox] WARN: $QUICK not found; creating empty scratch"
  : > "$SCRATCH"
fi

# Bail clearly when there's nothing to do
if [ ! -s "$SCRATCH" ]; then
  echo "[inbox] scratch is empty; nothing to process."
  exit 0
fi

# ---- Run transformer ----
PY="$HOME/anki-tools/.venv/bin/python"
[ -x "$PY" ] || PY="$(command -v python3)"

# Allow deck/model overrides via env
: "${ANKI_DECK:=Portuguese Mastery (pt-PT)}"
: "${ANKI_MODEL:=GPT Vocabulary Automater}"

"$PY" -u "$HOME/anki-tools/transform_inbox_to_csv.py" \
  --deck "$ANKI_DECK" \
  --model "$ANKI_MODEL" \
  --inbox-file "$SCRATCH" \
  --limit 1

# ---- Sync Anki (optional but nice) ----
curl -s http://127.0.0.1:8765 -X POST \
     -d '{"action":"sync","version":6}' >/dev/null 2>&1 || true

echo "[done] $TODAY"
