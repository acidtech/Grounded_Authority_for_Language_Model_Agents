"""CHR gate spike: one hook script for every event on both hosts (throwaway tooling).

Usage (from a host hook command):
    python3 probe_hook.py --host claude|codex --event EVENT_NAME

Appends one JSON line per invocation to $CHR_SPIKE_OUT/hooks.jsonl holding the
full raw stdin payload, the parsed payload, the event name, the environment
variable NAMES (never values) and, for every transcript file named in the
payload, a summary taken at hook time by transcript_summary.summarize(): size,
line count and marker hits (line number and record kind) for DELEG-123,
CITE-NONCE-7 and SPIKE-CTX-n, never any transcript text. That shows whether
assistant text written before a tool call is already visible to PreToolUse.

Output on stdout:
- PreToolUse on a built-in write tool (Claude Code Write; Codex apply_patch and
  shell): a deny decision, so the deny path is exercised.
- Other events that accept additionalContext on that host: a unique marker
  SPIKE-CTX-n, so delivery to the model can be found in the transcript.
- Anything else: no output.
"""

import argparse
import fcntl
import json
import os
import sys
import time

from transcript_summary import TRANSCRIPT_KEYS, summarize

DENY_TOOLS = {
    "claude": {"Write"},
    "codex": {"apply_patch", "Bash", "shell", "exec_command", "Edit", "Write"},
}
# Claude Code: documented additionalContext events plus PostToolBatch (unknown,
# measured here). Codex 0.162: the documented additionalContext event list.
CONTEXT_EVENTS = {
    "claude": {"PreToolUse", "PostToolUse", "PostToolBatch", "UserPromptSubmit", "SessionStart", "SubagentStart"},
    "codex": {
        "SessionStart", "PreToolUse", "PostToolUse", "UserPromptSubmit", "SubagentStart",
        "SubagentStop", "Stop", "PreCompact", "PostCompact",
    },
}


def _next_marker(out_dir: str) -> str:
    counter_path = os.path.join(out_dir, "ctx_counter")
    with open(counter_path, "a+", encoding="utf-8") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        fh.seek(0)
        current = int(fh.read().strip() or "0") + 1
        fh.seek(0)
        fh.truncate()
        fh.write(str(current))
    return f"SPIKE-CTX-{current}"


def decide(host: str, event: str, payload: dict, out_dir: str) -> dict | None:
    if event == "PreToolUse" and payload.get("tool_name") in DENY_TOOLS[host]:
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": "CHR spike probe: built-in write denied (deny-path measurement).",
            }
        }
    if event in CONTEXT_EVENTS[host]:
        return {"hookSpecificOutput": {"hookEventName": event, "additionalContext": _next_marker(out_dir)}}
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", required=True, choices=sorted(DENY_TOOLS))
    parser.add_argument("--event", help="event name from the host config (payload hook_event_name wins)")
    args = parser.parse_args()

    out_dir = os.environ.get("CHR_SPIKE_OUT")
    if not out_dir:
        print("probe_hook: CHR_SPIKE_OUT is not set", file=sys.stderr)
        return 1
    os.makedirs(out_dir, exist_ok=True)

    stdin_raw = sys.stdin.buffer.read().decode("utf-8", errors="replace")
    record: dict = {
        "ts": time.time(),
        "host": args.host,
        "arg_event": args.event,
        "label": os.environ.get("CHR_SPIKE_LABEL"),
        "pid": os.getpid(),
        "ppid": os.getppid(),
        "cwd": os.getcwd(),
        "env_names": sorted(os.environ),
        "stdin_raw": stdin_raw,
    }
    try:
        payload = json.loads(stdin_raw)
    except json.JSONDecodeError as exc:
        payload = None
        record["parse_error"] = str(exc)
    record["payload"] = payload
    if not isinstance(payload, dict):
        payload = {}

    event = payload.get("hook_event_name") or args.event
    record["event"] = event
    record["transcripts"] = [
        summarize(payload[key]) for key in TRANSCRIPT_KEYS if isinstance(payload.get(key), str)
    ]
    output = decide(args.host, event, payload, out_dir) if event else None
    record["emitted"] = output

    with open(os.path.join(out_dir, "hooks.jsonl"), "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")

    if not event:
        print("probe_hook: no event name in payload or --event", file=sys.stderr)
        return 1
    if output is not None:
        sys.stdout.write(json.dumps(output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
