#!/usr/bin/env bash
# Root frame probe (debt dcb46a): compare the MCP server env CLAUDE_CODE_SESSION_ID
# with the Claude Code hook session_id for the same tool call. See README.md.
#   probe_root_frame.sh setup   scratch project ROOT/proj with the whoami probe
#                               server (.mcp.json) and its PreToolUse hook
#   probe_root_frame.sh check   pair ROOT/mcp.jsonl with ROOT/hook.jsonl
# ROOT is /tmp/chr-gate-smoke/root-frame-probe unless PROBE_ROOT is set.
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PROBE="$REPO/scripts/smoke/root_frame_probe.py"
ROOT="${PROBE_ROOT:-/tmp/chr-gate-smoke/root-frame-probe}"

usage() {
  echo "usage: probe_root_frame.sh setup|check   (ROOT=$ROOT; set PROBE_ROOT to change it)" >&2
  exit 2
}
[ "$#" -eq 1 ] || usage

case "$1" in
  setup)
    if [ -e "$ROOT" ]; then
      STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
      mv "$ROOT" "$ROOT.prev.$STAMP"
      echo "moved previous $ROOT to $ROOT.prev.$STAMP"
    fi
    mkdir -p "$ROOT/proj/.claude"
    ROOT="$(cd "$ROOT" && pwd)"
    git -C "$ROOT/proj" init -q
    python3 - "$PROBE" "$ROOT" <<'PY'
import json, shlex, sys
from pathlib import Path
probe, root = sys.argv[1], Path(sys.argv[2])
proj = root / "proj"
mcp = {"mcpServers": {"whoami": {"type": "stdio", "command": "python3",
                                 "args": [probe, "server", "--log", str(root / "mcp.jsonl")]}}}
hook = " ".join(shlex.quote(part) for part in
                ("python3", probe, "hook", "--log", str(root / "hook.jsonl")))
settings = {"enableAllProjectMcpServers": True,
            "hooks": {"PreToolUse": [{"matcher": "mcp__whoami__whoami",
                                      "hooks": [{"type": "command", "command": hook}]}]}}
(proj / ".mcp.json").write_text(json.dumps(mcp, indent=2) + "\n", encoding="utf-8")
(proj / ".claude" / "settings.json").write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
PY
    cat <<NEXT
probe project: $ROOT/proj (.mcp.json, .claude/settings.json); logs: $ROOT/mcp.jsonl, $ROOT/hook.jsonl
next steps (in your own terminal):
  cd $ROOT/proj && claude --setting-sources project
    > call the whoami tool     /clear     > call the whoami tool     /exit
  cd $ROOT/proj && claude --setting-sources project --resume
    (pick the latest session)  > call the whoami tool     /exit
  bash $REPO/scripts/smoke/probe_root_frame.sh check
NEXT
    ;;
  check)
    exec python3 "$PROBE" check --mcp-log "$ROOT/mcp.jsonl" --hook-log "$ROOT/hook.jsonl"
    ;;
  *)
    usage
    ;;
esac
