#!/usr/bin/env bash
# chr-gate live smoke session for Codex (T7a). Run it from your own shell (it
# needs an authenticated codex) after:
#   uv tool install --editable <repo>/chr-gate
# It installs the chr-gate Codex plugin into your Codex home and prints the
# removal commands at the end. Outputs under /tmp/chr-gate-smoke/: codex-proj/,
# codex-state/ (XDG_STATE_HOME), codex-streams/, codex-version.txt,
# codex-session.txt. See README.md.
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1
HOST=codex
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PLUGIN="$REPO/plugins/codex"
MARKETPLACE=chr-gate-local
PLUGIN_ID=chr-gate@chr-gate-local
ROOT=/tmp/chr-gate-smoke
PROJ="$ROOT/$HOST-proj"
STATE="$ROOT/$HOST-state"
STREAMS="$ROOT/$HOST-streams"
SESSION_FILE="$ROOT/$HOST-session.txt"
PY=(uv run --frozen --project "$REPO/chr-gate" python)

removal() {
  echo
  echo "To remove the chr-gate Codex plugin:"
  echo "  codex plugin remove $PLUGIN_ID"
  echo "  codex plugin marketplace remove $MARKETPLACE"
}
trap removal EXIT
die() { echo "smoke: $*" >&2; exit 1; }
for tool in codex uv git chrgate-mcp chrgate-hook chrgate-setup; do
  command -v "$tool" > /dev/null || die "$tool is not on PATH (uv tool install --editable $REPO/chr-gate)"
done

mkdir -p "$ROOT"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
for old in "$PROJ" "$STATE" "$STREAMS" "$SESSION_FILE" "$ROOT/$HOST-version.txt"; do
  if [ -e "$old" ]; then mv "$old" "$old.prev.$STAMP"; echo "moved previous $old to $old.prev.$STAMP"; fi
done
# plugins/codex/.mcp.json forwards both variables to chrgate-mcp (env_vars); the
# hooks inherit them, so server and hooks share one state root.
export XDG_STATE_HOME="$STATE" CHR_GATE_PROJECT="$PROJ"
mkdir -p "$PROJ" "$STREAMS"
git -C "$PROJ" init -q
chrgate-setup --project "$PROJ"
codex --version > "$ROOT/$HOST-version.txt" 2>&1

# Install the plugin (T5 commands); the plugin list is the check, not the exit codes.
codex plugin marketplace add "$PLUGIN" || echo "smoke: marketplace add failed (already added?)" >&2
codex plugin add "$PLUGIN_ID" || echo "smoke: plugin add failed (already installed?)" >&2
codex plugin list --json | "${PY[@]}" -c '
import json, sys
installed = json.load(sys.stdin)["installed"]
if not any(p["pluginId"] == sys.argv[1] and p["installed"] and p["enabled"] for p in installed):
    sys.exit(f"smoke: {sys.argv[1]} is not installed and enabled: {installed}")
' "$PLUGIN_ID"

# plugins/codex/config/chr-gate.toml as -c session overrides: Codex loads a
# project .codex/config.toml only for a project trusted in your user config, and
# -c cannot grant that trust, so the fragment rides every call as session flags.
PAIRS=()  # bare key=value pairs
while IFS= read -r -d '' item; do PAIRS+=("$item"); done < <("${PY[@]}" "$REPO/scripts/smoke/fragment_pairs.py" "$PLUGIN/config/chr-gate.toml")
[ "${#PAIRS[@]}" -gt 0 ] || die "no overrides read from $PLUGIN/config/chr-gate.toml"
C_ARGS=()
for pair in "${PAIRS[@]}"; do C_ARGS+=(-c "$pair"); done

# Pre-flight, before the first model turn: the app-server's mcpServerStatus/list
# must list a chr-gate server with its tools, and config/read must show every
# fragment value in effect. Otherwise no session can pass: stop here.
# codex_preflight.py passes one -c per bare pair and reports the app-server's
# exit code and stderr when it gets no reply.
(cd "$PROJ" && "${PY[@]}" "$REPO/scripts/smoke/codex_preflight.py" "$PROJ" "${PAIRS[@]}")

# --dangerously-bypass-hook-trust: Codex skips plugin hooks until their hash is
# trusted (hooks.state.<key>.trusted_hash, written by the interactive /hooks
# review); this flag runs the enabled hooks for this invocation without that.
EXEC_ARGS=(--json --dangerously-bypass-hook-trust -c 'approval_policy="never"' "${C_ARGS[@]}")

thread_id() {
  "${PY[@]}" - "$1" <<'PY'
import json, sys
for line in open(sys.argv[1], encoding="utf-8"):
    if line.startswith("{") and json.loads(line).get("type") == "thread.started":
        print(json.loads(line)["thread_id"])
        break
else:
    sys.exit(f"smoke: no thread.started event in {sys.argv[1]}")
PY
}

TID=""
turn() {  # turn LABEL PROMPT: codex exec, then codex exec resume TID
  local label="$1" prompt="$2" rc cmd=(codex exec)
  local out="$STREAMS/$label.stream.jsonl"
  [ -n "$TID" ] && cmd=(codex exec resume "$TID")
  echo "turn $label ..."
  set +e
  (cd "$PROJ" && timeout 600 "${cmd[@]}" "${EXEC_ARGS[@]}" "$prompt") \
    < /dev/null > "$out" 2> "$STREAMS/$label.stderr.txt"
  rc=$?
  set -e
  echo "$label exit=$rc" >> "$STREAMS/exit-codes.txt"
  [ "$rc" -eq 0 ] || echo "smoke: WARNING turn $label exited $rc (see $STREAMS/$label.stderr.txt)" >&2
  TID="$(thread_id "$out")"
  grep -qxF "$TID" "$SESSION_FILE" 2> /dev/null || echo "$TID" >> "$SESSION_FILE"
}

plan_id() {
  "${PY[@]}" - "$STATE" <<'PY'
import json, sys
from pathlib import Path
found = sorted(Path(sys.argv[1]).rglob("proposals.json"))
if len(found) != 1:
    sys.exit(f"smoke: expected one proposals.json under {sys.argv[1]}, found {len(found)}: the "
             "chr-gate server did not record propose_plan in the smoke state root (see the "
             "1-propose stream; does chrgate-mcp receive XDG_STATE_HOME?)")
plans = sorted(json.loads(found[0].read_text(encoding="utf-8")))
if len(plans) != 1:
    sys.exit(f"smoke: expected one proposal, found {plans}")
print(plans[0])
PY
}

A_TEXT="$("${PY[@]}" -c 'from chrgate.smoke_check import EXPECTED_FILES as E; print(E["a.txt"])')"
B_TEXT="$("${PY[@]}" -c 'from chrgate.smoke_check import EXPECTED_FILES as E; print(E["b.txt"])')"
WO_TEXT="Create a.txt containing exactly '$A_TEXT' and b.txt containing exactly '$B_TEXT' in the project root with the chr-gate write_file tool."
turn 1-propose "chr-gate smoke test, step 1. Call the chr-gate tool propose_plan with its text argument set to exactly this text: $WO_TEXT Make no other tool call, then reply with the plan id."
PLAN="$(plan_id)"
turn 2-approve "approve $PLAN
(chr-gate smoke test, step 2: make no tool call in this turn; reply OK.)"
turn 3-wrong-witness "chr-gate smoke test, step 3. Call the chr-gate tool open_gate with witness 'wit:00000000000000000000000000000000', which is deliberately wrong. Make no other tool call, then reply with the exact result text."
turn 4-status-open "chr-gate smoke test, step 4. Call the chr-gate tool status. Then, in a later step after you have seen its result, call open_gate with the witness status returned. Make no other tool call, then reply with the work order text open_gate returned."
turn 5-parallel-writes "chr-gate smoke test, step 5. In ONE step make TWO PARALLEL calls of the chr-gate tool write_file: one with path a.txt and content '$A_TEXT', one with path b.txt and content '$B_TEXT'. Each call carries its own claim as its FIRST argument, citing your work order reference (wo:ID.vN). Make no other tool call, then reply DONE."
turn 6-builtin-write "chr-gate smoke test, step 6. Use your built-in apply_patch tool (or, if it is unavailable, your built-in shell) to create c.txt containing 'charlie'. Do not use the chr-gate write_file tool. If it is denied or unavailable, say exactly what happened and do not retry with any other tool."

echo
echo "smoke check ($HOST):"
set +e
"${PY[@]}" -m chrgate.smoke_check --host "$HOST" --state "$STATE" --project "$PROJ"
rc=$?
set -e
echo "outputs: $PROJ $STATE $STREAMS $ROOT/$HOST-version.txt $SESSION_FILE"
exit "$rc"
