"""Codex adapter (docs/spike-findings.md).

Frame: agent_id (the child thread id) in a subagent, else session_id (equal
to the server's _meta.threadId). No ticket: the server takes the frame from
_meta. The assistant text is in the rollout at PreToolUse (item 4), so
pre_tool checks citations from transcript_path. There is no PostToolBatch;
cells are tracked by the server (_meta.itemId), and Stop and the next
UserPromptSubmit end the turn's batch as backstops. Compaction is PostCompact,
whose output Codex never delivers, so the resurfaced work order is queued for
the next event that takes additionalContext.
"""

from typing import Any

from chrgate.hooks.adapters import chr_gate_tool
from chrgate.hooks.engine import (COMPACT, POST_TOOL, PRE_TOOL, STOP, SUBAGENT_START, USER_PROMPT,
                                  Event)

HOST = "codex"
BUILTIN_WRITES = frozenset({"shell", "Bash", "apply_patch"})
CONTEXT_EVENTS = frozenset({"SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse",
                            "SubagentStart"})


def parse(payload: dict[str, Any]) -> Event | None:
    name = payload["hook_event_name"]
    session = payload["session_id"]
    agent = payload.get("agent_id")
    base = dict(host=HOST, hook_event=name, frame=agent or session, session_id=session,
                agent_id=agent, agent_type=payload.get("agent_type"),
                transcript_path=payload.get("transcript_path"),
                accepts_context=name in CONTEXT_EVENTS)
    if name in ("PreToolUse", "PostToolUse"):
        host_tool = payload["tool_name"]
        return Event(kind=PRE_TOOL if name == "PreToolUse" else POST_TOOL, host_tool=host_tool,
                     tool=chr_gate_tool(host_tool), tool_input=payload["tool_input"],
                     tool_use_id=payload["tool_use_id"], batch_key=payload["turn_id"],
                     builtin_write=host_tool in BUILTIN_WRITES,
                     reads_transcript=name == "PreToolUse", **base)
    if name == "UserPromptSubmit":
        return Event(kind=USER_PROMPT, text=payload["prompt"], ends_batch=True, **base)
    if name == "Stop":
        return Event(kind=STOP, text=payload["last_assistant_message"],
                     batch_key=payload["turn_id"], ends_batch=True, **base)
    if name == "PostCompact":
        return Event(kind=COMPACT, **base)
    if name == "SubagentStart":
        return Event(kind=SUBAGENT_START, **base)
    return None
