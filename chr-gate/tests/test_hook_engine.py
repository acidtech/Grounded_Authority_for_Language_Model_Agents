"""chrgate-hook engine behaviour on neutral events (T3). The tests act as the
MCP server where the server's part is needed (open_gate, take_gate)."""

import itertools
import json

from chrgate.core import citations, events, gate, nonces, workorder
from chrgate.hooks import engine
from chrgate.hooks.adapters import render
from chrgate.hooks.engine import Decision, Event
from chrgate.server import tickets

S = "sess-engine-1"
CHILD = "agent-child-1"
_ids = itertools.count(1)
HOOK_EVENT = {"pre_tool": "PreToolUse", "post_tool": "PostToolUse", "batch_end": "PostToolBatch",
              "user_prompt": "UserPromptSubmit", "stop": "Stop", "compact": "SessionStart",
              "subagent_start": "SubagentStart"}


def claude(kind, frame=S, **kw):
    return Event(kind=kind, host="claude-code", hook_event=HOOK_EVENT[kind], frame=frame,
                 session_id=S, agent_id=None if frame == S else frame,
                 accepts_context=kind != "stop", writes_tickets=True, reports_turns=True, **kw)


def codex(kind, transcript, **kw):
    return Event(kind=kind, host="codex", hook_event=HOOK_EVENT[kind], frame=S, session_id=S,
                 accepts_context=kind != "stop", transcript_path=str(transcript),
                 reads_transcript=kind == "pre_tool", batch_key="turn-1", **kw)


def codex_tool(kind, transcript):
    return codex(kind, transcript, tool="research_shell", host_tool="mcp__chr-gate__research_shell",
                 tool_use_id="exec-1")


def pre(store, tool, frame=S):
    ev = claude("pre_tool", frame=frame, tool=tool, host_tool="mcp__chr-gate__" + tool,
                tool_use_id=f"toolu_{next(_ids)}")
    return ev, engine.handle(store, ev)


def batch_end(store, *evs):
    return engine.handle(store, claude("batch_end",
                                       batch_tool_use_ids=tuple(e.tool_use_id for e in evs)))


def ticket_key(store, ev):
    with store.lock():
        return store.read(tickets.TICKETS, {})[ev.tool_use_id]["turn_key"]


def gate_record(store, frame=S):
    with store.lock():
        return store.read(workorder.FRAMES, {})[frame]["gate"]


def open_gate_batch(store, issuer, frame=S):
    """The opening batch: open_gate goes through the hook, then the server
    opens the gate under the ticket's batch key."""
    ev, d = pre(store, "open_gate", frame)
    assert d.deny is None
    witness = issuer.read_work_order(frame).witness
    assert gate.open_gate(store, frame, witness, turn_key=ticket_key(store, ev)).status == gate.OPEN
    batch_end(store, ev)


def research_batch(store, frame=S):
    ev, d = pre(store, "research_shell", frame)
    assert d.deny is None
    batch_end(store, ev)


def transcript_with(tmp_path, text):
    path = tmp_path / "rollout.jsonl"
    rec = {"type": "response_item", "payload": {"type": "message", "role": "assistant",
                                                "content": [{"type": "output_text", "text": text}]}}
    path.write_text(json.dumps({"type": "session_meta", "payload": {}}) + "\n" + json.dumps(rec)
                    + "\n", encoding="utf-8")
    return path


def test_all_valid_citations_print_nothing(store, tmp_path):
    nonce = nonces.issue(store, S)
    path = transcript_with(tmp_path, f"I rely on <cite>{nonce}</cite>.")
    ev = codex_tool("pre_tool", path)
    d = engine.handle(store, ev)
    assert d == Decision() and render(ev, d) == ""
    stop = codex("stop", path, text=f"Done, see <cite>{nonce}</cite>")
    d = engine.handle(store, stop)
    assert d == Decision() and render(stop, d) == ""
    post = engine.handle(store, codex_tool("post_tool", path))
    assert citations.WARNING_TAG not in post.context


def test_invalid_citation_warning_arrives_in_next_context_event(store, tmp_path):
    bad = "ctx:0123456789abcdef"
    path = transcript_with(tmp_path, f"Based on <cite>{bad}</cite>")
    d = engine.handle(store, codex_tool("pre_tool", path))
    assert d == Decision()  # not before
    post = engine.handle(store, codex_tool("post_tool", path))
    assert citations.WARNING_TAG in post.context and bad in post.context
    again = engine.handle(store, codex_tool("post_tool", path))
    assert citations.WARNING_TAG not in again.context


def test_batch_end_with_consequential_call_closes_gate(store, issuer):
    open_gate_batch(store, issuer)
    ev, d = pre(store, "write_file")
    assert d.deny is None
    assert gate.take_gate(store, S, ticket_key(store, ev)).ok
    batch_end(store, ev)
    assert not gate.gate_is_current(store, S)


def test_research_batch_leaves_gate_open(store, issuer):
    open_gate_batch(store, issuer)
    research_batch(store)
    assert gate.gate_is_current(store, S)


def test_approve_activates_exact_proposed_text(store, wo_text):
    workorder.propose(store, "another proposal")
    plan = workorder.propose(store, wo_text)
    d = engine.handle(store, claude("user_prompt", text=f"Looks right. approve {plan}"))
    with store.lock():
        record = store.read(workorder.WORK_ORDER, None)
    assert record["text"] == wo_text and record["plan_id"] == plan
    assert plan in d.context and "read_work_order" in d.context


def test_compact_resurfaces_work_order_without_witness(store, issuer, wo_text):
    witness = issuer.read_work_order(S).witness
    ev = claude("compact")
    d = engine.handle(store, ev)
    out = render(ev, d)
    assert wo_text in d.context and "read_work_order" in d.context
    assert "wit:" not in out and witness not in out and "wit:" not in d.context
    assert gate.open_gate(store, S, witness).status == gate.DENIED


def test_consequential_call_without_gate_denied(store, active_wo):
    ev, d = pre(store, "write_file")
    assert "call open_gate first" in d.deny
    assert json.loads(render(ev, d))["hookSpecificOutput"]["permissionDecision"] == "deny"
    with store.lock():
        assert ev.tool_use_id not in store.read(tickets.TICKETS, {})


def test_child_without_delegation_denied(store, active_wo):
    assert "delegation_id" in engine.handle(store, claude("subagent_start", frame=CHILD)).context
    _, d = pre(store, "write_file", frame=CHILD)
    assert d.deny is not None and "read-only" in d.deny


def test_research_batch_counts_turn(store, issuer):
    open_gate_batch(store, issuer)  # the opening batch is not counted
    for _ in range(4):
        research_batch(store)
    assert gate_record(store)["intervening_turns"] == 4
    ev, d = pre(store, "write_file")
    assert d.deny is None
    taken = gate.take_gate(store, S, ticket_key(store, ev))
    assert not taken.ok and taken.message == gate.EXPIRED_TEXT


def test_consequential_batch_not_counted(store, issuer):
    open_gate_batch(store, issuer)
    ev, d = pre(store, "write_file")
    assert d.deny is None

    def turns():
        return [e for e in events.read_all(store) if e["kind"] == "note_turn"]

    before = turns()
    batch_end(store, ev)  # the server refused the call (no take_gate): close_gate is the backstop
    assert turns() == before
    assert not gate.gate_is_current(store, S)


def test_pre_tool_early_deny_does_not_consume_gate(store, issuer):
    open_gate_batch(store, issuer)
    first, d1 = pre(store, "write_file")
    second, d2 = pre(store, "edit_file")
    assert d1.deny is None and d2.deny is None
    assert gate_record(store)["consumed_by"] is None
    key = ticket_key(store, first)
    assert ticket_key(store, second) == key
    assert gate.take_gate(store, S, key).ok
