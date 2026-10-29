#!/usr/bin/env bash
# chr-gate live smoke session for Claude Code (T7a). Run it from your own shell
# (it needs an authenticated claude) after:
#   uv tool install --editable <repo>/chr-gate
# Outputs under /tmp/chr-gate-smoke/: claude-code-proj/ (scratch project),
# claude-code-state/ (XDG_STATE_HOME), claude-code-streams/ (one stream per
# turn), claude-code-version.txt, claude-code-session.txt. See README.md.
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1
HOST=claude-code
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PLUGIN="$REPO/plugins/claude-code"
ROOT=/tmp/chr-gate-smoke
PROJ="$ROOT/$HOST-proj"
STATE="$ROOT/$HOST-state"
STREAMS="$ROOT/$HOST-streams"
SESSION_FILE="$ROOT/$HOST-session.txt"
PY=(uv run --frozen --project "$REPO/chr-gate" python)
SERVER=plugin_chr-gate_chr-gate  # the CHR_GATE_SERVER plugins/claude-code/hooks/hooks.json passes

die() { echo "smoke: $*" >&2; exit 1; }
for tool in claude uv git chrgate-mcp chrgate-hook chrgate-setup; do
  command -v "$tool" > /dev/null || die "$tool is not on PATH (uv tool install --editable $REPO/chr-gate)"
done

mkdir -p "$ROOT"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
for old in "$PROJ" "$STATE" "$STREAMS" "$SESSION_FILE" "$ROOT/$HOST-version.txt"; do
  if [ -e "$old" ]; then mv "$old" "$old.prev.$STAMP"; echo "moved previous $old to $old.prev.$STAMP"; fi
done
export XDG_STATE_HOME="$STATE" CHR_GATE_PROJECT="$PROJ"
mkdir -p "$PROJ" "$STREAMS"
git -C "$PROJ" init -q
chrgate-setup --project "$PROJ"
claude --version > "$ROOT/$HOST-version.txt" 2>&1

A_TEXT="$("${PY[@]}" -c 'from chrgate.smoke_check import EXPECTED_FILES as E; print(E["a.txt"])')"
B_TEXT="$("${PY[@]}" -c 'from chrgate.smoke_check import EXPECTED_FILES as E; print(E["b.txt"])')"
ALLOWED="$("${PY[@]}" -c "from chrgate.server.tools import TOOLS; print(' '.join('mcp__${SERVER}__' + t.name for t in TOOLS))")"
# --setting-sources project: the scratch project has no .claude/settings.json, so
# your user settings (global hooks, enabled plugins) stay out of the session; the
# login is not a setting. The plugin comes from --plugin-dir, the built-in write
# denials from --settings.
COMMON=(--plugin-dir "$PLUGIN" --settings "$PLUGIN/settings/chr-gate-settings.json"
        --setting-sources project --allowedTools "$ALLOWED"
        --output-format stream-json --verbose --include-hook-events)

session_id() {
  "${PY[@]}" - "$1" <<'PY'
import json, sys
for line in open(sys.argv[1], encoding="utf-8"):
    if line.startswith("{") and json.loads(line).get("session_id"):
        print(json.loads(line)["session_id"])
        break
else:
    sys.exit(f"smoke: no session_id in {sys.argv[1]}")
PY
}

SID=""
turn() {  # turn LABEL PROMPT: one claude -p turn, resuming SID after the first
  local label="$1" prompt="$2" rc resume=()
  local out="$STREAMS/$label.stream.jsonl"
  [ -n "$SID" ] && resume=(--resume "$SID")
  echo "turn $label ..."
  set +e
  (cd "$PROJ" && timeout 600 claude -p "$prompt" "${resume[@]}" "${COMMON[@]}") \
    < /dev/null > "$out" 2> "$STREAMS/$label.stderr.txt"
  rc=$?
  set -e
  echo "$label exit=$rc" >> "$STREAMS/exit-codes.txt"
  [ "$rc" -eq 0 ] || echo "smoke: WARNING turn $label exited $rc (see $STREAMS/$label.stderr.txt)" >&2
  SID="$(session_id "$out")"
  grep -qxF "$SID" "$SESSION_FILE" 2> /dev/null || echo "$SID" >> "$SESSION_FILE"
}

plan_id() {
  "${PY[@]}" - "$STATE" <<'PY'
import json, sys
from pathlib import Path
found = sorted(Path(sys.argv[1]).rglob("proposals.json"))
if len(found) != 1:
    sys.exit(f"smoke: expected one proposals.json under {sys.argv[1]}, found {len(found)}: the "
             "chr-gate server did not record propose_plan in the smoke state root (see the "
             "1-propose stream)")
plans = sorted(json.loads(found[0].read_text(encoding="utf-8")))
if len(plans) != 1:
    sys.exit(f"smoke: expected one proposal, found {plans}")
print(plans[0])
PY
}

WO_TEXT="Create a.txt containing exactly '$A_TEXT' and b.txt containing exactly '$B_TEXT' in the project root with the chr-gate write_file tool."
turn 1-propose "chr-gate smoke test, step 1. Call the chr-gate tool propose_plan with exactly this text: $WO_TEXT Make no other tool call, then reply with the plan id."
PLAN="$(plan_id)"
turn 2-approve "approve $PLAN
(chr-gate smoke test, step 2: make no tool call in this turn; reply OK.)"
turn 3-wrong-witness "chr-gate smoke test, step 3. Call the chr-gate tool open_gate with witness 'wit:00000000000000000000000000000000', which is deliberately wrong. Make no other tool call, then reply with the exact result text."
turn 4-status-open "chr-gate smoke test, step 4. Call the chr-gate tool status. Then, in a later step after you have seen its result, call open_gate with the witness status returned. Make no other tool call, then reply with the work order text open_gate returned."
turn 5-parallel-writes "chr-gate smoke test, step 5. In ONE message make TWO PARALLEL calls of the chr-gate tool write_file: one with path a.txt and content '$A_TEXT', one with path b.txt and content '$B_TEXT'. Each call carries its own claim as its FIRST argument, citing your work order reference (wo:ID.vN). Make no other tool call, then reply DONE."
turn 6-builtin-write "chr-gate smoke test, step 6. Use your built-in Write tool (not the chr-gate write_file tool, not a shell) to create c.txt containing 'charlie'. If it is denied or unavailable, say exactly what happened and do not retry with any other tool."

echo
echo "smoke check ($HOST):"
set +e
"${PY[@]}" -m chrgate.smoke_check --host "$HOST" --state "$STATE" --project "$PROJ"
rc=$?
set -e
echo "outputs: $PROJ $STATE $STREAMS $ROOT/$HOST-version.txt $SESSION_FILE"
exit "$rc"
