#!/usr/bin/env bash
# CHR gate spike: Codex probe runner (throwaway measurement tooling).
# Usage: bash run_codex_probe.sh            # non-interactive measurements + tool-disable candidates
#        bash run_codex_probe.sh compact    # interactive session for /compact
# ~/.codex is never edited: the kit's codex/*.toml fragments become -c overrides.
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1

KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT=/tmp/chr-gate-spike
OUT="$ROOT/codex"
PROJ="$ROOT/codex-proj"
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
codex --version > "$OUT/codex-version.txt" 2>&1

# Turn each second-level table of the given TOML fragments into one
# NUL-terminated "key=<inline TOML>" string for codex -c.
overrides() {
  python3 - "$@" <<'PY'
import json, sys, tomllib

def inline(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, str):
        return json.dumps(v)
    if isinstance(v, list):
        return "[" + ", ".join(inline(x) for x in v) + "]"
    if isinstance(v, dict):
        return "{" + ", ".join(f"{json.dumps(k)} = {inline(x)}" for k, x in v.items()) + "}"
    raise TypeError(f"unsupported TOML value {type(v)}")

for path in sys.argv[1:]:
    with open(path, "rb") as fh:
        data = tomllib.load(fh)
    for top, value in data.items():
        pairs = value.items() if isinstance(value, dict) else [(None, value)]
        for sub, v in pairs:
            key = top if sub is None else f"{top}.{sub}"
            sys.stdout.write(f"{key}={inline(v)}\0")
PY
}

to_c_args() {  # read NUL-separated overrides file into C_ARGS as -c pairs
  C_ARGS=()
  local item
  while IFS= read -r -d '' item; do C_ARGS+=(-c "$item"); done < "$1"
}

overrides "$KIT/codex/probe.toml" > "$OUT/overrides-probe.bin"
tr '\0' '\n' < "$OUT/overrides-probe.bin" > "$OUT/overrides-probe.txt"
to_c_args "$OUT/overrides-probe.bin"
PROBE_C=("${C_ARGS[@]}")

if [ "$MODE" = compact ]; then
  export CHR_SPIKE_LABEL=compact
  cat <<MSG
Interactive Codex session for the compact measurement.
  1. Let it answer the first prompt (one probe_read call).
  2. Type /compact and wait for it to finish.
  3. Type /quit.
Hooks log to $OUT/hooks.jsonl (label "compact").
Note: interactive codex has no --ignore-user-config, so ~/.codex/config.toml loads too.
MSG
  codex -C "$PROJ" --dangerously-bypass-hook-trust -s workspace-write -a never "${PROBE_C[@]}" \
    "Measurement run. Call probe_read with path notes.txt, then reply DONE." || echo "codex exited $?"
  python3 "$KIT/transcript_summary.py" "$OUT"
  echo "compact outputs: $OUT (hooks.jsonl, transcripts-summary.jsonl)"
  exit 0
fi

count_lines() { if [ -f "$1" ]; then wc -l < "$1"; else echo 0; fi; }

# run LABEL PROMPT [extra codex args...]
# After each run, call_ids.py appends that run's tool calls (hook payload fields,
# MCP _meta) to call-ids.jsonl, labelled by the lines the run added.
run() {
  local label="$1" prompt="$2" rc hooks_from mcp_from
  shift 2
  export CHR_SPIKE_LABEL="$label"
  hooks_from="$(count_lines "$OUT/hooks.jsonl")"
  mcp_from="$(count_lines "$OUT/mcp.jsonl")"
  echo "running $label ..."
  set +e
  timeout 600 codex exec --json --strict-config -C "$PROJ" --ignore-user-config --dangerously-bypass-hook-trust \
      -c 'sandbox_mode="workspace-write"' -c 'approval_policy="never"' "${PROBE_C[@]}" "$@" \
      -o "$OUT/$label.last-message.txt" "$prompt" \
    < /dev/null > "$OUT/$label.stream.jsonl" 2> "$OUT/$label.stderr.txt"
  rc=$?
  set -e
  echo "$label exit=$rc" | tee -a "$OUT/exit-codes.txt"
  python3 "$KIT/call_ids.py" "$OUT" "$label" "$hooks_from" "$mcp_from"
}

M1="Measurement run. First write exactly this sentence as plain text: CITE-NONCE-7 I rely on the work order. Then call the tool probe_write TWICE IN PARALLEL (two tool calls issued together in one step). Call one: claim 'parallel call A for the spike', path 'a.txt', content 'alpha'. Call two: claim 'parallel call B for the spike', path 'b.txt', content 'beta'. Give the arguments in the order claim, path, content. After both results arrive, reply DONE."
M2="Measurement run. Step 1: call probe_read with path 'notes.txt' and make no other tool call in that step. Step 2: only after you have seen its result, call probe_write with claim 'turn two write for the spike', path 'notes.txt', content 'gamma'. Then reply DONE."
M6="Measurement run. Use your code-mode exec tool to run exactly ONE JavaScript cell, and do all of the following inside that single cell: first await the probe_read tool from the global tools object (its JavaScript name starts with mcp__probe__) with path 'notes.txt'; only after that call has resolved, in the same cell, await the probe_write tool with claim 'one cell write for the spike', path 'cell.txt', content 'zeta' (arguments in the order claim, path, content). Do not call probe_read or probe_write outside that cell and do not split the work across cells. After the cell finishes, reply DONE."
# Code mode off: the fallback if no per-cell identifier exists.
NOCODE=(-c features.code_mode_host=false)

M4="Measurement run. First list the names of every tool you have available, one per line. Then try your built-in apply_patch tool to create the file builtin.txt containing the word epsilon. Then try your shell tool to run: echo epsilon > shell.txt. Do not use probe_write. If a tool is denied or unavailable, say exactly what happened and do not retry with any other tool. Then reply DONE."

codex features list > "$OUT/features-baseline.txt" 2>&1
run m1_parallel "$M1"
run m2_turns "$M2"
run m3_subagent "Measurement run. Spawn exactly one sub-agent with your agent-spawning tool. Its instructions must contain the marker DELEG-123 and must tell it to call the tool probe_write with claim 'child write DELEG-123', path 'child.txt', content 'delta', and then stop. Do not call probe_write yourself. Wait for the sub-agent to finish, then reply DONE."
run m4_builtin_write "$M4"
run m6_one_cell "$M6"
codex "${NOCODE[@]}" features list > "$OUT/features-code_mode_host_off.txt" 2>&1
run m1_parallel_nocode "$M1" "${NOCODE[@]}"
run m2_turns_nocode "$M2" "${NOCODE[@]}"

# Catalog for candidate D: every model with shell_type disabled and no apply_patch tool type.
codex debug models > "$OUT/catalog-original.json" 2> "$OUT/catalog.stderr.txt"
python3 - "$OUT" <<'PY'
import json, os, sys
out = sys.argv[1]
with open(os.path.join(out, "catalog-original.json"), encoding="utf-8") as fh:
    catalog = json.load(fh)
for model in catalog["models"]:
    model["shell_type"] = "disabled"
    model["apply_patch_tool_type"] = None
with open(os.path.join(out, "catalog-no-builtins.json"), "w", encoding="utf-8") as fh:
    json.dump(catalog, fh, indent=2)
print(f"wrote catalog-no-builtins.json for {len(catalog['models'])} model(s)")
PY

for cand in "$KIT"/codex/candidate_*.toml; do
  name="$(basename "$cand" .toml)"
  overrides "$cand" > "$OUT/overrides-$name.bin"
  tr '\0' '\n' < "$OUT/overrides-$name.bin" > "$OUT/overrides-$name.txt"
  to_c_args "$OUT/overrides-$name.bin"
  codex "${C_ARGS[@]}" features list > "$OUT/features-$name.txt" 2>&1 || echo "features list failed for $name" | tee -a "$OUT/exit-codes.txt"
  run "m5_$name" "$M4" "${C_ARGS[@]}"
done

python3 "$KIT/transcript_summary.py" "$OUT"
echo "codex outputs: $OUT"
echo "  codex-version.txt, features-*.txt, overrides-*.txt, exit-codes.txt,"
echo "  <label>.stream.jsonl, <label>.stderr.txt, <label>.last-message.txt,"
echo "  hooks.jsonl (probe_hook), mcp.jsonl (probe server), call-ids.jsonl,"
echo "  transcripts-summary.jsonl"
