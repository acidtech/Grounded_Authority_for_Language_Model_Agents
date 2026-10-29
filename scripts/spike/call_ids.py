"""CHR gate spike: per-run tool-call id summary (throwaway tooling).

Usage (run_codex_probe.sh calls it after every run):
    python3 call_ids.py OUT_DIR LABEL HOOKS_FROM MCP_FROM

HOOKS_FROM / MCP_FROM are the line counts of OUT_DIR/hooks.jsonl and
OUT_DIR/mcp.jsonl taken just before run LABEL started, so every line after them
belongs to that run whatever label (if any) the host passed through. Appends to
OUT_DIR/call-ids.jsonl one record per tool call seen during the run:
- source "hook": PreToolUse, PermissionRequest and PostToolUse records, with
  every hook payload field and value except tool_input and tool_response;
- source "mcp": every probe-server tools/call, with the JSON-RPC id, the
  params keys and the full params._meta (null when absent).
Each record carries "label" (the runner's run label) and "record_label" (the
label the raw record itself carries), so a per-cell identifier, if one exists,
shows up as a field that differs between cells and is shared within one.
"""

import json
import os
import sys

TOOL_EVENTS = ("PreToolUse", "PermissionRequest", "PostToolUse")
OMIT_FIELDS = ("tool_input", "tool_response")


def _records_from(path: str, start: int) -> list[dict]:
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    return [json.loads(line) for line in lines[start:] if line.strip()]


def main(argv: list[str]) -> int:
    if len(argv) != 5:
        print("usage: call_ids.py OUT_DIR LABEL HOOKS_FROM MCP_FROM", file=sys.stderr)
        return 2
    out_dir, label = argv[1], argv[2]
    hooks_from, mcp_from = int(argv[3]), int(argv[4])
    rows = []
    for record in _records_from(os.path.join(out_dir, "hooks.jsonl"), hooks_from):
        if record["event"] not in TOOL_EVENTS:
            continue
        payload = record["payload"] if isinstance(record["payload"], dict) else {}
        rows.append({
            "label": label,
            "record_label": record["label"],
            "source": "hook",
            "event": record["event"],
            "tool_name": payload.get("tool_name"),
            "fields": {k: v for k, v in payload.items() if k not in OMIT_FIELDS},
        })
    for record in _records_from(os.path.join(out_dir, "mcp.jsonl"), mcp_from):
        if record["kind"] != "tools/call":
            continue
        rows.append({
            "label": label,
            "record_label": record["label"],
            "source": "mcp",
            "tool_name": record["tool"],
            "rpc_id": record["id"],
            "params_keys": record["params_keys"],
            "meta": record.get("meta"),
        })
    with open(os.path.join(out_dir, "call-ids.jsonl"), "a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")
    print(f"call_ids: {label}: {len(rows)} tool-call record(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
