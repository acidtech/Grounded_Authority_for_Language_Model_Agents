"""Frame attribution for MCP tool calls (docs/spike-findings.md, 'Mechanism
choices'). The MCP server cannot see which agent frame made a call; each host
tells it differently.

- Claude Code: the T3 PreToolUse hook writes a ticket into the state root
  (tickets.json) under the call's tool_use_id: {tool, session_id, agent_id,
  agent_type, transcript_path, turn_key}. The server finds it through
  _meta["claudecode/toolUseId"] (equal to the PreToolUse tool_use_id) and
  consumes it. The frame is agent_id in a subagent, else session_id; turn_key
  is the tool-batch key. A ticket names its tool (the bare MCP tool name) and
  matches no other tool.
- Codex: no ticket. The frame is _meta.threadId, the turn key is the code
  cell _meta.itemId, and a subagent call carries
  _meta["x-codex-turn-metadata"].parent_thread_id. A Codex call (client name
  codex*, or any Codex _meta key) without threadId or itemId is refused,
  fail closed.
- A Claude Code call (non-empty claudecode/toolUseId) without a ticket naming
  its tool is refused (claude-no-ticket), fail closed. Like the Codex refusal
  it is recorded on root_frame(), because the server env
  CLAUDE_CODE_SESSION_ID is not the session's frame after /clear or --resume
  (bug 327e55).
- Anything else (no host identity): the root session frame
  (CLAUDE_CODE_SESSION_ID when set, else "root"), no turn key, not mediated.
  tools.py refuses a consequential call that is not mediated.
"""

import os
from dataclasses import dataclass
from typing import Any

from chrgate.core.store import Store

TICKETS = "tickets.json"
CLAUDE = "claude-code"
CODEX = "codex"
NO_HOST = "none"
CLAUDE_TOOL_USE_ID = "claudecode/toolUseId"
CODEX_TURN_METADATA = "x-codex-turn-metadata"
CODEX_META_KEYS = ("threadId", "itemId", "callId", "sessionId", CODEX_TURN_METADATA)
CODEX_CLIENT_PREFIX = "codex"
ROOT_FRAME_ENV = "CLAUDE_CODE_SESSION_ID"
ROOT_FRAME = "root"
CODEX_NO_ITEM_ID = "codex-no-item-id"
CLAUDE_NO_TICKET = "claude-no-ticket"


class AttributionRefused(Exception):
    """The call cannot be attributed to a frame; refused, fail closed."""

    def __init__(self, code: str, message: str, frame: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.frame = frame


@dataclass(frozen=True)
class Caller:
    host: str
    frame: str
    turn_key: str | None
    mediated: bool
    subagent: bool
    parent_frame: str | None = None


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def root_frame() -> str:
    """The root session frame of calls that carry no frame identity."""
    return os.environ.get(ROOT_FRAME_ENV) or ROOT_FRAME


def put_ticket(store: Store, tool_use_id: str, *, tool: str, session_id: str, turn_key: str,
               agent_id: str | None = None, agent_type: str | None = None,
               transcript_path: str | None = None) -> None:
    """Record the PreToolUse ticket of Claude Code call TOOL_USE_ID (T3)."""
    for name, value in (("tool_use_id", tool_use_id), ("tool", tool),
                        ("session_id", session_id), ("turn_key", turn_key)):
        if not _text(value):
            raise ValueError(f"{name} must be a non-empty string, got {value!r}")
    if agent_id is not None and not _text(agent_id):
        raise ValueError(f"agent_id must be a non-empty string or None, got {agent_id!r}")
    with store.lock():
        tickets = store.read(TICKETS, {})
        if tool_use_id in tickets:
            raise ValueError(f"a ticket for tool_use_id {tool_use_id!r} already exists")
        tickets[tool_use_id] = {"tool": tool, "session_id": session_id, "turn_key": turn_key,
                                "agent_id": agent_id, "agent_type": agent_type,
                                "transcript_path": transcript_path}
        store.write(TICKETS, tickets)


def take_ticket(store: Store, tool_use_id: str, tool: str) -> dict[str, Any] | None:
    """Consume the ticket of TOOL_USE_ID when it names TOOL; else None (a
    ticket for another tool is left in place)."""
    with store.lock():
        tickets = store.read(TICKETS, {})
        ticket = tickets.get(tool_use_id)
        if ticket is None or ticket["tool"] != tool:
            return None
        del tickets[tool_use_id]
        store.write(TICKETS, tickets)
    return ticket


def attribute(store: Store, tool: str, meta: dict[str, Any] | None,
              client_name: str | None = None) -> Caller:
    """The calling frame of TOOL from the request _meta (and ticket)."""
    meta = meta or {}
    codex = ((client_name or "").startswith(CODEX_CLIENT_PREFIX)
             or any(key in meta for key in CODEX_META_KEYS))
    if codex:
        thread, item = meta.get("threadId"), meta.get("itemId")
        if not (_text(thread) and _text(item)):
            raise AttributionRefused(
                CODEX_NO_ITEM_ID, f"{tool} refused: a Codex call must carry _meta.threadId and "
                "_meta.itemId (run Codex with code mode on); refused, fail closed",
                thread if _text(thread) else root_frame())
        turn_meta = meta.get(CODEX_TURN_METADATA)
        parent = turn_meta.get("parent_thread_id") if isinstance(turn_meta, dict) else None
        return Caller(CODEX, thread, item, mediated=True, subagent=_text(parent),
                      parent_frame=parent if _text(parent) else None)
    tool_use_id = meta.get(CLAUDE_TOOL_USE_ID)
    if _text(tool_use_id):
        ticket = take_ticket(store, tool_use_id, tool)
        if ticket is not None:
            agent = ticket["agent_id"]
            return Caller(CLAUDE, agent or ticket["session_id"], ticket["turn_key"],
                          mediated=True, subagent=agent is not None)
        raise AttributionRefused(
            CLAUDE_NO_TICKET, f"{tool} refused: the chr-gate PreToolUse hook did not ticket this "
            f"Claude Code call (no ticket names {tool} under its claudecode/toolUseId); the "
            "chr-gate plugin hooks must be installed and enabled for this project; refused, "
            "fail closed", root_frame())
    return Caller(NO_HOST, root_frame(), None, mediated=False, subagent=False)
