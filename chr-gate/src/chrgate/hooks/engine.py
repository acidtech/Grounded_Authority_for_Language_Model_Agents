"""All chrgate-hook behaviour, on neutral events (adapters build them).

- pre_tool: deny host built-in writes (second line of defence behind host
  config). For a consequential chr-gate tool, deny early when the caller is a
  subagent with no delegated work order (read-only) or when no gate is current
  (gate.gate_is_current: the check never consumes the gate; only the server's
  take_gate does). Record the call in the frame's open batch (Claude Code: a
  hook-minted batch key B-..., Codex: turn_id) and, on Claude Code, write the
  tool_use_id-keyed ticket (tickets.put_ticket) carrying the batch key and the
  subagent agent_id. When the host's assistant text is readable in time
  (Codex), check the citations written since the last check and queue
  warnings for the frame.
- post_tool: issue a context nonce for the tool result (additionalContext).
- batch_end (Claude Code PostToolBatch; Codex Stop and UserPromptSubmit as
  backstops): a batch that held a consequential chr-gate call, or whose gate
  the server consumed, ends with close_gate; any other Claude Code batch is
  reported with gate.note_turn (Codex turns are reported by the server).
- user_prompt: 'approve P-xxxxxxxx' activates exactly that proposal.
- stop: check the final assistant text's citations; warnings are queued.
- compact: new_epoch for the frame, then resurface the work-order TEXT with
  the read_work_order instruction; no witness ever appears in hook output.
- subagent_start: tell the child how to bind its delegation (the server binds
  it on the child's first status call, findings item 3); until then the child
  is read-only.

Queued text (citation warnings, a resurfaced work order on a host whose compact
event takes no additionalContext) rides the next event of that frame that
accepts additionalContext. Nothing to say means an empty Decision, and the
hook prints nothing.
"""

import re
import secrets
from dataclasses import dataclass
from typing import Any

from chrgate.core import citations, gate, nonces, workorder
from chrgate.core.store import Store
from chrgate.hooks import transcript
from chrgate.server import tickets
from chrgate.server.tools import NONCE_LABEL, TOOLS_BY_NAME

PRE_TOOL = "pre_tool"
POST_TOOL = "post_tool"
BATCH_END = "batch_end"
USER_PROMPT = "user_prompt"
STOP = "stop"
COMPACT = "compact"
SUBAGENT_START = "subagent_start"
KINDS = (PRE_TOOL, POST_TOOL, BATCH_END, USER_PROMPT, STOP, COMPACT, SUBAGENT_START)

QUEUE = "hook_queue.json"      # {frame: [text, ...]}
BATCHES = "hook_batches.json"  # {frame: {"key": str, "calls": {tool_use_id: {...}}}}
BATCH_PREFIX = "B-"
APPROVE_RE = re.compile(r"\bapprove (P-[0-9a-f]{8})\b")

BUILTIN_DENY_TEXT = ("chr-gate: the built-in tool {tool} is disabled in this project; make changes "
                     "through the chr-gate MCP tools (write_file, edit_file, mutate_shell after "
                     "open_gate; research_shell to read)")
NO_GATE_TEXT = ("chr-gate: {tool} needs an open gate: call open_gate first with the witness "
                "from read_work_order (status), then make the call in a later turn")
READ_ONLY_TEXT = ("chr-gate: {tool} refused: this subagent has no delegated work order, so it is "
                  "read-only; a consequential subagent first calls status with the "
                  "delegation_id from its launch prompt")
FAIL_CLOSED_TEXT = "chr-gate: the hook failed ({error}); {tool} refused, fail closed"
ACTIVATED_TEXT = ("chr-gate: the user approved {plan}; work order {ref} is now active. Call "
                  "read_work_order (status) on the chr-gate server for its text and your witness.")
UNKNOWN_PLAN_TEXT = "chr-gate: {plan} is not a proposed plan id; nothing was activated."
COMPACT_TEXT = ("chr-gate: your context was compacted, which ended your witness and any open gate. "
                "Your active work order is {ref}:\n--- work order text ---\n{text}\n"
                "--- end of work order ---\nCall read_work_order (status) on the chr-gate server "
                "for a new witness before open_gate.")
SUBAGENT_TEXT = ("chr-gate: if your launch prompt carries a chr-gate delegation id (D-...), call "
                 "status with delegation_id set to it before any consequential call; without a "
                 "delegation you are read-only.")


@dataclass(frozen=True)
class Event:
    kind: str
    host: str
    hook_event: str          # the host's event name, echoed in the output
    frame: str               # agent_id in a subagent, else session_id
    session_id: str
    accepts_context: bool    # the host delivers additionalContext for this event
    agent_id: str | None = None
    agent_type: str | None = None
    transcript_path: str | None = None
    tool: str | None = None        # bare chr-gate tool name, None for other tools
    host_tool: str | None = None   # the host's tool name
    tool_input: Any = None
    tool_use_id: str | None = None
    builtin_write: bool = False
    text: str | None = None        # user prompt, or final assistant text at stop
    batch_key: str | None = None   # host batch key (Codex turn_id); None: hook-minted
    batch_tool_use_ids: tuple[str, ...] = ()
    batch_tools: tuple[str | None, ...] = ()
    reads_transcript: bool = False  # citations from transcript.py at pre_tool
    writes_tickets: bool = False    # Claude Code: frame tickets for the server
    reports_turns: bool = False     # Claude Code: note_turn at batch_end
    ends_batch: bool = False        # Codex stop/user_prompt backstop

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise ValueError(f"unknown event kind {self.kind!r}")
        if not isinstance(self.frame, str) or not self.frame:
            raise ValueError(f"frame must be a non-empty string, got {self.frame!r}")


@dataclass(frozen=True)
class Decision:
    deny: str | None = None
    context: str | None = None


def is_consequential(tool: str | None) -> bool:
    return tool is not None and tool in TOOLS_BY_NAME and TOOLS_BY_NAME[tool].consequential


def fails_closed(event: Event) -> bool:
    """A hook error on EVENT denies the call (consequential or built-in write)."""
    return event.kind == PRE_TOOL and (event.builtin_write or is_consequential(event.tool))


def failure_decision(event: Event, error: BaseException) -> Decision:
    if fails_closed(event):
        return Decision(deny=FAIL_CLOSED_TEXT.format(error=type(error).__name__,
                                                     tool=event.host_tool))
    return Decision()


# queued text per frame

def _queue(store: Store, frame: str, text: str) -> None:
    with store.lock():
        queue = store.read(QUEUE, {})
        queue.setdefault(frame, []).append(text)
        store.write(QUEUE, queue)


def _drain(store: Store, frame: str) -> list[str]:
    with store.lock():
        queue = store.read(QUEUE, {})
        pending = queue.pop(frame, [])
        if pending:
            store.write(QUEUE, queue)
    return pending


def _respond(store: Store, event: Event, frame: str, parts: list[str]) -> Decision:
    """Deliver queued text plus PARTS now, or queue PARTS when the host does
    not take additionalContext on this event."""
    if not event.accepts_context:
        for part in parts:
            _queue(store, frame, part)
        return Decision()
    texts = _drain(store, frame) + parts
    return Decision(context="\n\n".join(texts) if texts else None)


def _check_citations(store: Store, frame: str, text: str | None) -> None:
    if not text:
        return
    cited = citations.parse(text)
    if not cited:
        return
    warning = citations.warning_text(citations.check(store, frame, cited))
    if warning is not None:
        _queue(store, frame, warning)


# batches

def _record_call(store: Store, event: Event) -> str:
    """Add the call to the frame's open batch; returns the batch key."""
    if not event.tool_use_id:
        raise ValueError("a tool event needs a tool_use_id")
    with store.lock():
        batches = store.read(BATCHES, {})
        batch = batches.get(event.frame)
        if batch is None or (event.batch_key is not None and batch["key"] != event.batch_key):
            batch = batches[event.frame] = {
                "key": event.batch_key or BATCH_PREFIX + secrets.token_hex(8), "calls": {}}
        batch["calls"][event.tool_use_id] = {"tool": event.tool,
                                             "consequential": is_consequential(event.tool)}
        store.write(BATCHES, batches)
    return batch["key"]


def _gate_consumed(store: Store, frame: str) -> bool:
    with store.lock():
        current, _ = gate.current_gate(store, store.read(workorder.FRAMES, {}), frame)
    return current is not None and current["consumed_by"] is not None


def _end_batch(store: Store, event: Event) -> str:
    """End the open batch of the event's frame (found by its tool_use_ids
    first); returns that frame."""
    with store.lock():
        batches = store.read(BATCHES, {})
        frame = next((f for f, b in batches.items()
                      if any(i in b["calls"] for i in event.batch_tool_use_ids)), event.frame)
        batch = batches.pop(frame, None)
        if batch is not None:
            store.write(BATCHES, batches)
    if batch is not None:
        key: str | None = batch["key"]
        consequential = any(c["consequential"] for c in batch["calls"].values())
    else:
        key = event.batch_key
        consequential = False
    consequential = consequential or any(is_consequential(t) for t in event.batch_tools)
    if consequential or _gate_consumed(store, frame):
        gate.close_gate(store, frame)
    elif event.reports_turns and key is not None:
        gate.note_turn(store, frame, key)
    return frame


# handlers

def _early_refusal(store: Store, event: Event) -> str | None:
    if event.agent_id is not None:
        with store.lock():
            bound = event.frame in store.read(workorder.FRAMES, {})
        if not bound:
            return READ_ONLY_TEXT.format(tool=event.tool)
    if not gate.gate_is_current(store, event.frame):
        return NO_GATE_TEXT.format(tool=event.tool)
    return None


def _pre_tool(store: Store, event: Event) -> Decision:
    if event.builtin_write:
        return Decision(deny=BUILTIN_DENY_TEXT.format(tool=event.host_tool))
    text = None
    if event.reads_transcript:
        if not event.transcript_path:
            raise ValueError("this host's pre_tool event needs a transcript_path")
        text = transcript.new_assistant_text(store, event.frame, event.transcript_path)
    if is_consequential(event.tool):
        refusal = _early_refusal(store, event)
        if refusal is not None:
            _check_citations(store, event.frame, text)
            return Decision(deny=refusal)
    key = _record_call(store, event)
    if event.tool is not None and event.writes_tickets:
        assert event.tool_use_id is not None
        tickets.put_ticket(store, event.tool_use_id, tool=event.tool,
                           session_id=event.session_id, turn_key=key, agent_id=event.agent_id,
                           agent_type=event.agent_type, transcript_path=event.transcript_path)
    decision = _respond(store, event, event.frame, [])
    _check_citations(store, event.frame, text)  # after delivery: it rides the NEXT event
    return decision


def _post_tool(store: Store, event: Event) -> Decision:
    return _respond(store, event, event.frame, [NONCE_LABEL + nonces.issue(store, event.frame)])


def _batch_end(store: Store, event: Event) -> Decision:
    return _respond(store, event, _end_batch(store, event), [])


def _user_prompt(store: Store, event: Event) -> Decision:
    if event.text is None:
        raise ValueError("a user_prompt event needs the prompt text")
    if event.ends_batch:
        _end_batch(store, event)
    parts = []
    match = APPROVE_RE.search(event.text)
    if match is not None:
        plan = match.group(1)
        try:
            wo = workorder.activate(store, plan, event.text)
        except workorder.UnknownPlan:
            parts.append(UNKNOWN_PLAN_TEXT.format(plan=plan))
        else:
            parts.append(ACTIVATED_TEXT.format(plan=plan, ref=wo.ref))
    return _respond(store, event, event.frame, parts)


def _stop(store: Store, event: Event) -> Decision:
    if event.ends_batch:
        _end_batch(store, event)
    _check_citations(store, event.frame, event.text)
    return _respond(store, event, event.frame, [])


def _compact(store: Store, event: Event) -> Decision:
    gate.new_epoch(store, event.frame)
    with store.lock():
        rec = store.read(workorder.FRAMES, {}).get(event.frame)
        wo = (workorder.governing_work_order(store, rec) if rec is not None
              else workorder.active(store))
    parts = [] if wo is None else [COMPACT_TEXT.format(ref=wo.ref, text=wo.text)]
    return _respond(store, event, event.frame, parts)


def _subagent_start(store: Store, event: Event) -> Decision:
    return _respond(store, event, event.frame, [SUBAGENT_TEXT])


_HANDLERS = {PRE_TOOL: _pre_tool, POST_TOOL: _post_tool, BATCH_END: _batch_end,
             USER_PROMPT: _user_prompt, STOP: _stop, COMPACT: _compact,
             SUBAGENT_START: _subagent_start}


def handle(store: Store, event: Event) -> Decision:
    """The engine's decision for EVENT."""
    return _HANDLERS[event.kind](store, event)
