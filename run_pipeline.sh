#!/usr/bin/env bash
unset ANKI_BASE
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: ./run_pipeline.sh [options]

Options:
  --dry-run            Process entries but skip CSV writes / Anki
  --limit N            Limit number of normalized items to process (default 0 = no limit)
  --deck NAME          Override target Anki deck
  --model NAME         Override target Anki model
  --log-level LEVEL    Transformer log level (DEBUG|INFO|WARN|ERROR|SILENT)
  --inbox PATH         Override inbox quick.jsonl path (for testing)
  --clear-inbox        After a successful production run, archive & blank quick.jsonl
  -h, --help           Show this help and exit

Environment defaults:
  PIPELINE_LOG_LEVEL / PIPELINE_INBOX
  ANKI_DECK / ANKI_MODEL
Dry-run and limit default to full production unless a CLI flag is provided.
EOF
}

# ---- Defaults / options ----
DRY_RUN=0
LIMIT=0
LOG_LEVEL="${PIPELINE_LOG_LEVEL:-INFO}"
DECK="${ANKI_DECK:-Portuguese Mastery (pt-PT)}"
MODEL="${ANKI_MODEL:-GPT Vocabulary Automater}"
INBOX_OVERRIDE="${PIPELINE_INBOX:-}"
CLEAR_INBOX=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1 ;;
    --limit) LIMIT="${2:?--limit requires an argument}"; shift ;;
    --deck) DECK="${2:?--deck requires an argument}"; shift ;;
    --model) MODEL="${2:?--model requires an argument}"; shift ;;
    --log-level) LOG_LEVEL="${2:?--log-level requires an argument}"; shift ;;
    --inbox) INBOX_OVERRIDE="${2:?--inbox requires a path}"; shift ;;
    --clear-inbox) CLEAR_INBOX=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "[err] Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

# ---- Env ----
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
export PYTHONIOENCODING=UTF-8

ICLOUD_ROOT="$HOME/Library/Mobile Documents/com~apple~CloudDocs"
DEFAULT_DATA_DIR="$ICLOUD_ROOT/Portuguese/Anki"
if [[ -n "$INBOX_OVERRIDE" ]]; then
  QUICK="$INBOX_OVERRIDE"
  INBOX="$(dirname "$QUICK")"
  ANKI_DATA_DIR="$(dirname "$INBOX")"
else
  [[ -d "$ICLOUD_ROOT" ]] || { echo "[err] iCloud root not found: $ICLOUD_ROOT"; exit 1; }
  ANKI_DATA_DIR="$DEFAULT_DATA_DIR"
  INBOX="$ANKI_DATA_DIR/inbox"
  QUICK="$INBOX/quick.jsonl"
fi

TODAY="$(date +%F)"
LOGDIR="$ANKI_DATA_DIR/logs"
mkdir -p "$INBOX" "$LOGDIR"

IS_DRY_RUN=0
if [[ "$DRY_RUN" =~ ^(1|true|TRUE|yes|YES)$ ]]; then
  IS_DRY_RUN=1
fi

echo "[config] deck='$DECK' model='$MODEL' limit=$LIMIT dry_run=$IS_DRY_RUN log_level=$LOG_LEVEL"
echo "[config] inbox source: $QUICK"

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
OPENAI_PROJECT="${OPENAI_PROJECT:-}"
if [[ -z "$OPENAI_PROJECT" ]]; then
  for SVC in "anki-tools-openai-project" "OPENAI_PROJECT" "openai_project"; do
    if PROJ_FROM_KC="$(/usr/bin/security find-generic-password -a "$USER" -s "$SVC" -w 2>/dev/null)"; then
      OPENAI_PROJECT="$PROJ_FROM_KC"
      break
    fi
  done
fi
if [[ -n "$OPENAI_PROJECT" ]]; then
  OPENAI_PROJECT="$(printf %s "$OPENAI_PROJECT" | LC_ALL=C tr -d '\r\n' | tr -d '“”‘’')"
  export OPENAI_PROJECT
fi
# Verify the key before continuing (keep tracing off to avoid leaking secrets)
verify_openai_key() {
  local base="${OPENAI_BASE_URL:-https://api.openai.com}"
  base="${base%/}"
  if [[ "$base" != */v1 ]]; then
    base="$base/v1"
  fi
  local url
  if [[ -n "$OPENAI_PROJECT" ]]; then
    url="$base/models?project_id=$OPENAI_PROJECT"
  else
    url="$base/models"
  fi
  local tmp status
  tmp="$(mktemp -t openai_check.XXXXXX)"
  local -a headers=(
    "-H" "Authorization: Bearer $OPENAI_API_KEY"
    "-H" "Accept: application/json"
  )
  if [[ -n "$OPENAI_PROJECT" ]]; then
    headers+=("-H" "OpenAI-Project: $OPENAI_PROJECT")
  fi
  status="$(curl -sS -o "$tmp" -w "%{http_code}" \
    "${headers[@]}" \
    "$url" || echo "000")"
  if [[ "$status" != 2* ]]; then
    local body
    body="$(<"$tmp")"
    rm -f "$tmp"
    echo "[auth] OpenAI credential check failed (status $status)." >&2
    if [[ -n "$body" ]]; then
      echo "[auth] Response: $body" >&2
    fi
    if [[ "$status" == 401 ]]; then
      echo "[auth] Tip: update the Keychain entry (security add-generic-password -a \"$USER\" -s \"anki-tools-openai\" -w 'sk-...' -U)." >&2
    fi
    exit 1
  fi
  rm -f "$tmp"
  echo "[auth] OpenAI key verified (status $status)"
}
verify_openai_key
# If you use Azure, set OPENAI_BASE_URL, OPENAI_API_VERSION, and LLM_MODEL via Keychain or env and DO NOT unset them.
unset OPENAI_BASE_URL OPENAI_API_BASE OPENAI_ORG_ID

# re-enable xtrace if it was on
[[ -n "$XTRACE_WAS_ON" ]] && set -x
echo "key_prefix=${OPENAI_API_KEY:0:6}"
if (( IS_DRY_RUN == 1 )); then
  echo "[mode] dry-run enabled (CSV/Anki writes skipped)"
else
  echo "[mode] production run (writes + Anki enabled)"
fi

# ---- Ensure inbox exists and copy to scratch ----
if [[ ! -r "$QUICK" ]]; then
  echo "[inbox] ERROR: inbox file missing or unreadable: $QUICK" >&2
  exit 1
fi
SCRATCH="$(mktemp -t quick_copy.XXXXXX.jsonl)"
/bin/cp -f "$QUICK" "$SCRATCH"
if command -v stat >/dev/null 2>&1; then
  SRC_BYTES="$(stat -f %z "$QUICK" 2>/dev/null || stat -c %s "$QUICK" 2>/dev/null || echo '?')"
  SCR_BYTES="$(stat -f %z "$SCRATCH" 2>/dev/null || stat -c %s "$SCRATCH" 2>/dev/null || echo '?')"
  echo "[inbox] source bytes: $SRC_BYTES"
  echo "[inbox] scratch bytes: $SCR_BYTES"
fi

# Bail clearly when there's nothing to do
if [[ ! -s "$SCRATCH" ]]; then
  echo "[inbox] scratch is empty; nothing to process."
  exit 0
fi

# ---- Run transformer ----
PY="$HOME/anki-tools/.venv/bin/python"
[ -x "$PY" ] || PY="$(command -v python3)"

declare -a PY_ARGS=(
  --deck "$DECK"
  --model "$MODEL"
  --inbox-file "$SCRATCH"
  --limit "$LIMIT"
  --log-level "$LOG_LEVEL"
)
if (( IS_DRY_RUN == 1 )); then
  PY_ARGS+=(--dry-run 1)
fi
"$PY" -u "$HOME/anki-tools/transform_inbox_to_csv.py" "${PY_ARGS[@]}"

# ---- Sync Anki (optional but nice) ----
if (( IS_DRY_RUN == 0 )); then
  curl -s http://127.0.0.1:8765 -X POST \
       -d '{"action":"sync","version":6}' >/dev/null 2>&1 || true
fi

if (( CLEAR_INBOX == 1 )) && (( IS_DRY_RUN == 0 )); then
  ARCHIVE_DIR="$INBOX/archive"
  mkdir -p "$ARCHIVE_DIR"
  if [[ -f "$QUICK" ]]; then
    STAMP="$(date +%F_%H%M%S)"
    ARCHIVE_PATH="$ARCHIVE_DIR/quick.$STAMP.jsonl"
    if cp -p "$QUICK" "$ARCHIVE_PATH" 2>/dev/null; then
      : > "$QUICK"
      echo "[inbox] Archived quick.jsonl to $ARCHIVE_PATH and cleared original."
    else
      echo "[inbox] WARN: could not archive $QUICK; leaving file untouched." >&2
    fi
  else
    echo "[inbox] WARN: quick file missing; nothing to clear." >&2
  fi
fi

echo "[done] $TODAY"
