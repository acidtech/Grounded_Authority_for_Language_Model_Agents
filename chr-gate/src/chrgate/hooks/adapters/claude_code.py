"""Claude Code adapter (docs/spike-findings.md).

Frame: agent_id in a subagent, else session_id. PreToolUse writes the
tool_use_id-keyed ticket (the server matches _meta['claudecode/toolUseId']).
PostToolBatch ends the tool batch (batch_end, note_turn for research
batches); UserPromptSubmit and Stop end it too, as backstops. The assistant
text is not in the transcript in time (item 4 FALLBACK): no transcript
citation check; the agent uses cite(). Compaction is
SessionStart source=compact (PostCompact output is not delivered).

Built-ins are denied unless READ_ONLY_BUILTINS lists them (names from
code.claude.com/docs/en/tools-reference; Task is Agent's name before Claude
Code 2.1.63, code.claude.com/docs/en/sub-agents, and the init record still
lists it).
"""

from typing import Any

from chrgate.hooks.adapters import builtin_write, chr_gate_tool
from chrgate.hooks.engine import (BATCH_END, COMPACT, POST_TOOL, PRE_TOOL, STOP, SUBAGENT_START,
                                  USER_PROMPT, Event)

HOST = "claude-code"
READ_ONLY_BUILTINS = frozenset({"Read", "Glob", "Grep", "ToolSearch", "WebFetch", "WebSearch",
                                "Skill", "Task", "Agent", "ListAgents", "TaskStop",
                                "ReportFindings", "CronList"})
CONTEXT_EVENTS = frozenset({"SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse",
                            "PostToolBatch", "SubagentStart"})


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
                     tool_use_id=payload["tool_use_id"],
                     builtin_write=builtin_write(host_tool, READ_ONLY_BUILTINS),
                     writes_tickets=True, **base)
    if name == "PostToolBatch":
        calls = payload["tool_calls"]
        return Event(kind=BATCH_END, batch_tool_use_ids=tuple(c["tool_use_id"] for c in calls),
                     batch_tools=tuple(chr_gate_tool(c["tool_name"]) for c in calls),
                     reports_turns=True, **base)
    if name == "UserPromptSubmit":
        return Event(kind=USER_PROMPT, text=payload["prompt"], ends_batch=True, **base)
    if name == "Stop":
        return Event(kind=STOP, text=payload["last_assistant_message"], ends_batch=True, **base)
    if name == "SessionStart" and payload["source"] == "compact":
        return Event(kind=COMPACT, **base)
    if name == "SubagentStart":
        return Event(kind=SUBAGENT_START, **base)
    return None
