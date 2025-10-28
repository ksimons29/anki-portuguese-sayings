#!/bin/bash
set -euo pipefail
# -e : exit on error | -u : error on unset vars | -o pipefail : fail on pipeline error

# ---- Basic diagnostic output ----
echo "START $(date)"
echo "whoami=$(whoami)"
echo "pwd=$(pwd)"

/usr/bin/caffeinate -i -w $$ &  # keep system awake for the life of this script

# ---- Log to iCloud (one file per day) ----
LOGDIR="$HOME/Library/Mobile Documents/com~apple~CloudDocs/Portuguese/Anki/logs"
mkdir -p "$LOGDIR"
exec >>"$LOGDIR/pipeline.$(date +%F).log" 2>>"$LOGDIR/pipeline.$(date +%F).err"

echo "START $(date)"
echo "whoami=$(whoami)"
echo "pwd=$(pwd)"

# ---- PATH + encoding (launchd-safe) ----
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
export PYTHONIOENCODING=UTF-8
set +x 2>/dev/null || true

# ---- Network gate ----
require_network() {
  local tries=6
  while ! /sbin/ping -q -c1 -t1 1.1.1.1 >/dev/null 2>&1 ; do
    tries=$((tries-1))
    [ $tries -le 0 ] && { echo "[net] offline; skipping this run"; return 1; }
    echo "[net] no connectivity; retrying..."
    sleep 10
  done
  return 0
}

# ---- (kept for reference; not used right now) ----
atomic_overwrite() {
  local target="$1"
  local tmp="${target}.tmp.$$"
  cat > "$tmp" || return 1
  local i=0 max=30
  while ! mv -f "$tmp" "$target" 2>/dev/null; do
    i=$((i+1)); [ $i -ge $max ] && { echo "[atomic] failed after $max retries: $target"; rm -f "$tmp"; return 1; }
    echo "[atomic] target locked (retry $i/$max)"
    sleep 1
  done
  return 0
}

# ---- Wake-after-sleep note (diagnostic) ----
if pmset -g log | tail -n 80 | grep -q "Wake from Sleep"; then
  echo "[info] Detected recent system wake; this run may be a catch-up after sleep."
fi

# ---- Paths ----
ANKI_BASE="$HOME/Library/Mobile Documents/com~apple~CloudDocs/Portuguese/Anki"
INBOX="$ANKI_BASE/inbox"
QUICK="$INBOX/quick.jsonl"
TODAY="$(date +%F)"
ROTATE_STAMP="$INBOX/.rotated-$TODAY"
mkdir -p "$INBOX"

# remove old rotation stamps (keep today's)
for f in "$INBOX"/.rotated-*; do
  [ -e "$f" ] || continue
  [ "$(basename "$f")" = ".rotated-$TODAY" ] && continue
  rm -f "$f"
done

# ---- OpenAI key (Keychain -> env) + sanitize quotes/newlines ----
if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  if KEY_FROM_KC="$(security find-generic-password -a "$USER" -s "anki-tools-openai" -w 2>/dev/null)"; then
    OPENAI_API_KEY="$KEY_FROM_KC"
  else
    echo "[err] OPENAI_API_KEY not set and Keychain item 'anki-tools-openai' not found."
    echo "      Add it with: security add-generic-password -a \"$USER\" -s \"anki-tools-openai\" -w 'sk-...'"
    exit 1
  fi
fi
# sanitize (remove CR/LF + smart quotes)
OPENAI_API_KEY="$(printf %s "$OPENAI_API_KEY" | LC_ALL=C tr -d '\r\n' | tr -d '“”‘’')"
export OPENAI_API_KEY
unset OPENAI_BASE_URL OPENAI_API_BASE OPENAI_ORG_ID
echo "key_prefix=${OPENAI_API_KEY:0:6}"

# ---- Ensure Anki/AnkiConnect is up ----
open -gj -a "Anki" || true
require_network || exit 0
# wait up to ~20s for AnkiConnect to come up
for i in {1..20}; do
  if curl -sS --max-time 1 localhost:8765 >/dev/null ; then
    echo "[anki] AnkiConnect reachable."
    break
  fi
  sleep 1
done
if ! curl -sS --max-time 1 localhost:8765 >/dev/null ; then
  echo "[anki] AnkiConnect not reachable; skipping this run"
  exit 0
fi

# ---- Copy iCloud inbox to a local scratch file (READ-ONLY access to iCloud) ----
SCRATCH="$(mktemp -t quick_copy.XXXXXX.jsonl)"
/bin/cp -f "$QUICK" "$SCRATCH" || echo "[warn] Could not copy $QUICK (maybe empty)."

# ---- Run the transformer (pass the scratch file) ----
set +e
"$HOME/anki-tools/.venv/bin/python" -u "$HOME/anki-tools/transform_inbox_to_csv.py" \
  --deck "Portuguese Mastery (pt-PT)" --model "GPT Vocabulary Automater" \
  --inbox-file "$SCRATCH"
STATUS=$?
set -e

# ---- Optional: rotate/clear iCloud inbox (disabled by default) ----
# Enable by exporting ROTATE_INBOX=1 (and grant Full Disk Access to bash/python if needed).
if [[ "${ROTATE_INBOX:-0}" == "1" && $STATUS -eq 0 && ! -f "$ROTATE_STAMP" ]]; then
  echo "[rotate] status=$STATUS stamp=$ROTATE_STAMP quick=$QUICK"
  mv -f "$QUICK" "$QUICK.$(date +%H%M%S).bak" 2>/dev/null || true
  : > "$QUICK"
  touch "$ROTATE_STAMP"
  echo "[rotate] quick.jsonl cleared for $TODAY"
fi