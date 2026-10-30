"""Root frame probe (debt dcb46a): does the MCP server env match the hook session?

chr-gate's tickets.root_frame() reads CLAUDE_CODE_SESSION_ID from the MCP
server's environment; the Claude Code hooks see the payload session_id. This
stdlib-only kit records both for the same tool call so the user can compare
them in a live interactive session (including after /clear and --resume).

Modes:
  server --log PATH   minimal stdio MCP server (newline-delimited JSON-RPC) with
                      one tool, whoami; appends a 'start' record at start and a
                      'call' record on every tools/call.
  hook --log PATH     PreToolUse hook: appends the payload's session_id,
                      tool_use_id and tool_name; prints nothing, exits 0.
  check --mcp-log PATH --hook-log PATH
                      pairs call and hook records by tool use id and prints one
                      row per call; exits 0 only when at least one pair exists
                      and every row is MATCH.

Driver and user steps: probe_root_frame.sh and README.md (same directory).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

ENV_SESSION_ID = "CLAUDE_CODE_SESSION_ID"
META_TOOL_USE_ID = "claudecode/toolUseId"  # chr-gate's tickets.CLAUDE_TOOL_USE_ID
TOOL = "whoami"
DEFAULT_PROTOCOL = "2025-06-18"
MATCH, MISMATCH, UNPAIRED = "MATCH", "MISMATCH", "UNPAIRED"


def _append(path: str, record: dict) -> None:
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")


def _send(message: dict) -> None:
    sys.stdout.write(json.dumps(message) + "\n")
    sys.stdout.flush()


def _result(msg_id, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def _error(msg_id, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}


def serve(log: str) -> int:
    pid = os.getpid()
    env_id = os.environ.get(ENV_SESSION_ID)
    _append(log, {"kind": "start", "ts": time.time(), "pid": pid, "env_session_id": env_id})
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError as exc:
            print(f"root_frame_probe server: unparsable line {line!r}: {exc}", file=sys.stderr)
            _send(_error(None, -32700, f"parse error: {exc}"))
            continue
        if not isinstance(message, dict) or "method" not in message or "id" not in message:
            continue  # a notification (no id) or a response: nothing to answer
        msg_id, method = message["id"], message["method"]
        params = message.get("params") or {}
        if method == "initialize":
            _send(_result(msg_id, {
                "protocolVersion": params.get("protocolVersion") or DEFAULT_PROTOCOL,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "root-frame-probe", "version": "1"},
            }))
        elif method == "tools/list":
            _send(_result(msg_id, {"tools": [{
                "name": TOOL,
                "description": "Root frame probe: reports this MCP server's pid and its "
                               f"{ENV_SESSION_ID} environment value. Takes no arguments.",
                "inputSchema": {"type": "object", "properties": {}},
            }]}))
        elif method == "tools/call":
            if params.get("name") != TOOL:
                _send(_error(msg_id, -32602, f"unknown tool {params.get('name')!r}"))
                continue
            meta = params.get("_meta") or {}
            _append(log, {"kind": "call", "ts": time.time(), "pid": pid, "env_session_id": env_id,
                          "tool_use_id": meta.get(META_TOOL_USE_ID)})
            text = f"whoami: MCP server pid {pid}, {ENV_SESSION_ID}={env_id!r}"
            _send(_result(msg_id, {"content": [{"type": "text", "text": text}]}))
        elif method == "ping":
            _send(_result(msg_id, {}))
        else:
            _send(_error(msg_id, -32601, f"method not found: {method}"))
    return 0


def hook(log: str) -> int:
    payload = json.load(sys.stdin)
    _append(log, {"kind": "hook", "ts": time.time(), "session_id": payload.get("session_id"),
                  "tool_use_id": payload.get("tool_use_id"), "tool_name": payload.get("tool_name")})
    return 0


@dataclass(frozen=True)
class Row:
    tool_use_id: str | None
    pid: int | None
    env_session_id: str | None
    hook_session_id: str | None
    verdict: str


def pair(mcp_records: list[dict], hook_records: list[dict]) -> list[Row]:
    """One row per whoami call, then one UNPAIRED row per hook record no call claimed.

    A call pairs with the first unclaimed hook record of the same tool use id; the
    pair is MATCH only when the server env id is set and equals the hook session_id.
    """
    pending: dict[str, list[dict]] = {}
    for rec in hook_records:
        if rec.get("kind") == "hook":
            pending.setdefault(rec.get("tool_use_id"), []).append(rec)
    rows = []
    for rec in mcp_records:
        if rec.get("kind") != "call":
            continue
        use_id, env_id = rec.get("tool_use_id"), rec.get("env_session_id")
        hooks = pending.get(use_id) if use_id is not None else None
        if not hooks:
            rows.append(Row(use_id, rec.get("pid"), env_id, None, UNPAIRED))
            continue
        hook_sid = hooks.pop(0).get("session_id")
        verdict = MATCH if env_id is not None and env_id == hook_sid else MISMATCH
        rows.append(Row(use_id, rec.get("pid"), env_id, hook_sid, verdict))
    for left in pending.values():
        for rec in left:
            rows.append(Row(rec.get("tool_use_id"), None, None, rec.get("session_id"), UNPAIRED))
    return rows


def _load(path: str) -> list[dict]:
    file = Path(path)
    if not file.exists():
        print(f"note: {path} does not exist (no record was written)")
        return []
    return [json.loads(line) for line in file.read_text(encoding="utf-8").splitlines() if line.strip()]


def check(mcp_log: str, hook_log: str) -> int:
    rows = pair(_load(mcp_log), _load(hook_log))
    print("tool_use_id\tpid\tenv_session_id\thook_session_id\tverdict")
    for row in rows:
        print(f"{row.tool_use_id}\t{row.pid}\t{row.env_session_id}\t{row.hook_session_id}\t{row.verdict}")
    paired = [row for row in rows if row.verdict != UNPAIRED]
    ok = bool(paired) and all(row.verdict == MATCH for row in rows)
    pids = sorted({row.pid for row in paired})
    print(f"result: {'PASS' if ok else 'FAIL'} ({len(rows)} rows, {len(paired)} paired, "
          f"server pids {pids})")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    modes = parser.add_subparsers(dest="mode", required=True)
    for name in ("server", "hook"):
        modes.add_parser(name).add_argument("--log", required=True)
    check_parser = modes.add_parser("check")
    check_parser.add_argument("--mcp-log", required=True)
    check_parser.add_argument("--hook-log", required=True)
    args = parser.parse_args(argv)
    if args.mode == "server":
        return serve(args.log)
    if args.mode == "hook":
        return hook(args.log)
    return check(args.mcp_log, args.hook_log)


if __name__ == "__main__":
    sys.exit(main())
