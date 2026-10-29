"""Per-host adapters: parse(payload) -> engine.Event | None (None: an event the
gate ignores) and render(event, decision) -> stdout text. Both hosts take the
same output shape (docs/spike-findings.md 'Layout notes'): {"hookSpecificOutput":
{"hookEventName", "permissionDecision": "deny", "permissionDecisionReason"}} for
a PreToolUse deny and {"hookSpecificOutput": {"hookEventName",
"additionalContext"}} for context; nothing to say prints nothing.

chr_gate_tool matches tool names that start with mcp__<CHR_GATE_SERVER>__. The
default, chr-gate, matches only a Claude Code server named chr-gate declared in a
project or user .mcp.json. A Claude Code server declared by a plugin reaches hooks
as mcp__plugin_<plugin>_<server>__<tool>, which is why
plugins/claude-code/hooks/hooks.json sets CHR_GATE_SERVER=plugin_chr-gate_chr-gate
for the chr-gate plugin's chr-gate server. Codex sanitizes the server name,
turning chr-gate into chr_gate (sanitize in chr-gate/tests/test_plugin_codex.py),
so the chr-gate server's tools reach Codex hooks as mcp__chr_gate__<tool>, which
is why plugins/codex/hooks/hooks.json sets CHR_GATE_SERVER=chr_gate on every hook
command.
"""

import json
import os

from chrgate.hooks.engine import PRE_TOOL, Decision, Event

SERVER_ENV = "CHR_GATE_SERVER"
DEFAULT_SERVER = "chr-gate"
PRE_TOOL_EVENT = "PreToolUse"


def chr_gate_tool(host_tool: str) -> str | None:
    """The bare chr-gate tool name of HOST_TOOL, or None for any other tool."""
    if not isinstance(host_tool, str):
        raise TypeError(f"tool_name must be a string, got {host_tool!r}")
    prefix = f"mcp__{os.environ.get(SERVER_ENV) or DEFAULT_SERVER}__"
    return host_tool[len(prefix):] or None if host_tool.startswith(prefix) else None


def deny_json(hook_event: str, reason: str) -> str:
    return json.dumps({"hookSpecificOutput": {"hookEventName": hook_event,
                                              "permissionDecision": "deny",
                                              "permissionDecisionReason": reason}})


def render(event: Event, decision: Decision) -> str:
    if decision.deny is not None:
        if event.kind != PRE_TOOL:
            raise ValueError(f"only pre_tool can deny, got {event.kind}")
        return deny_json(event.hook_event, decision.deny)
    if decision.context is not None:
        if not event.accepts_context:
            raise ValueError(f"{event.hook_event} takes no additionalContext")
        return json.dumps({"hookSpecificOutput": {"hookEventName": event.hook_event,
                                                  "additionalContext": decision.context}})
    return ""
