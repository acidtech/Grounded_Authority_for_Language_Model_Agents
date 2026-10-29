#!/usr/bin/env bash
# CHR gate spike: Claude Code probe runner (throwaway measurement tooling).
# Usage: bash run_claude_probe.sh            # four non-interactive measurements
#        bash run_claude_probe.sh compact    # interactive session for /compact
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1

KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT=/tmp/chr-gate-spike
OUT="$ROOT/claude"
PROJ="$ROOT/claude-proj"
export CHR_SPIKE_OUT="$OUT"
MODE="${1:-batch}"
case "$MODE" in
  batch|compact) ;;
  *) echo "usage: $0 [compact]" >&2; exit 2 ;;
esac

if [ "$MODE" = batch ] && [ -e "$OUT" ]; then
  PREV="$OUT.prev.$(date -u +%Y%m%dT%H%M%SZ)"
  mv "$OUT" "$PREV"
  echo "previous output moved to $PREV"
fi
mkdir -p "$OUT"
if [ ! -d "$PROJ/.git" ]; then
  mkdir -p "$PROJ"
  git -C "$PROJ" init -q
  printf '# CHR gate spike scratch project\n' > "$PROJ/README.md"
  git -C "$PROJ" add README.md
  git -C "$PROJ" -c user.name=chr-spike -c user.email=chr-spike@localhost commit -qm init
fi
claude --version > "$OUT/claude-version.txt" 2>&1

# --setting-sources project: the scratch project has no .claude/, so no user or
# local settings (global hooks, enabled plugins) load; the login is not a setting
# and stays. --strict-mcp-config: only the probe MCP server loads.
COMMON=(
  --settings "$KIT/claude/settings.json"
  --mcp-config "$KIT/claude/mcp.json"
  --strict-mcp-config
  --setting-sources project
  --allowedTools "mcp__probe__probe_write mcp__probe__probe_read Write Agent Task"
)

if [ "$MODE" = compact ]; then
  export CHR_SPIKE_LABEL=compact
  cat <<MSG
Interactive Claude Code session for the compact measurement.
  1. Let it answer the first prompt (one probe_read call).
  2. Type /compact and wait for it to finish.
  3. Type /exit.
Hooks log to $OUT/hooks.jsonl (label "compact").
MSG
  (cd "$PROJ" && claude "${COMMON[@]}" "Measurement run. Call probe_read with path notes.txt, then reply DONE.") || echo "claude exited $?"
  python3 "$KIT/transcript_summary.py" "$OUT"
  echo "compact outputs: $OUT (hooks.jsonl, transcripts-summary.jsonl)"
  exit 0
fi

run() {
  local label="$1" prompt="$2" rc
  export CHR_SPIKE_LABEL="$label"
  echo "running $label ..."
  set +e
  (cd "$PROJ" && timeout 600 claude -p "$prompt" "${COMMON[@]}" \
      --output-format stream-json --verbose --include-hook-events) \
    < /dev/null > "$OUT/$label.stream.jsonl" 2> "$OUT/$label.stderr.txt"
  rc=$?
  set -e
  echo "$label exit=$rc" | tee -a "$OUT/exit-codes.txt"
}

run m1_parallel "Measurement run. First write exactly this sentence as plain text: CITE-NONCE-7 I rely on the work order. Then, in that SAME assistant message, call the tool probe_write TWICE IN PARALLEL (two tool calls in one message). Call one: claim 'parallel call A for the spike', path 'a.txt', content 'alpha'. Call two: claim 'parallel call B for the spike', path 'b.txt', content 'beta'. Give the arguments in the order claim, path, content. After both results arrive, reply DONE."
run m2_turns "Measurement run. Step 1: call probe_read with path 'notes.txt' and make no other tool call in that message. Step 2: only after you have seen its result, in a NEW message call probe_write with claim 'turn two write for the spike', path 'notes.txt', content 'gamma'. Then reply DONE."
run m3_subagent "Measurement run. Use the Agent tool to launch exactly one general-purpose subagent. Its prompt must contain the marker DELEG-123 and must tell it to call the tool mcp__probe__probe_write with claim 'child write DELEG-123', path 'child.txt', content 'delta', and then stop. Do not call probe_write yourself. Wait for the subagent to finish, then reply DONE."
run m4_builtin_write "Measurement run. First list the names of every tool you have available, one per line. Then use your built-in Write tool (not probe_write, not a shell) to create the file builtin.txt containing the word epsilon. If the tool is denied or unavailable, say exactly what happened and do not retry with any other tool. Then reply DONE."

python3 "$KIT/transcript_summary.py" "$OUT"
echo "claude outputs: $OUT"
echo "  claude-version.txt, exit-codes.txt, <label>.stream.jsonl, <label>.stderr.txt,"
echo "  hooks.jsonl (probe_hook), mcp.jsonl (probe server), transcripts-summary.jsonl"
