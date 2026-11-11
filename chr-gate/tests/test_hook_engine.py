"""chrgate-hook engine behaviour on neutral events (T3). The tests act as the
MCP server where the server's part is needed (open_gate, take_gate)."""

import itertools
import json

import pytest

from chrgate.core import citations, delegation, events, gate, nonces, workorder
from chrgate.core.witness import WitnessIssuer
from chrgate.hooks import engine
from chrgate.hooks.adapters import render
from chrgate.hooks.engine import Decision, Event
from chrgate.server import tickets

S = "sess-engine-1"
CHILD = "agent-child-1"
GRANDCHILD = "agent-grandchild-1"
_ids = itertools.count(1)
HOOK_EVENT = {"pre_tool": "PreToolUse", "post_tool": "PostToolUse", "batch_end": "PostToolBatch",
              "user_prompt": "UserPromptSubmit", "stop": "Stop", "compact": "SessionStart",
              "subagent_start": "SubagentStart"}


def claude(kind, frame=S, **kw):
    return Event(kind=kind, host="claude-code", hook_event=HOOK_EVENT[kind], frame=frame,
                 session_id=S, agent_id=None if frame == S else frame,
                 accepts_context=kind != "stop", writes_tickets=True, reports_turns=True, **kw)


def codex(kind, transcript, batch_key="turn-1", **kw):
    return Event(kind=kind, host="codex", hook_event=HOOK_EVENT[kind], frame=S, session_id=S,
                 accepts_context=kind != "stop", transcript_path=str(transcript),
                 reads_transcript=kind == "pre_tool", writes_tickets=kind == "pre_tool",
                 batch_key=batch_key, **kw)


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


def _tickets(store):
    with store.lock():
        return store.read(tickets.TICKETS, {})


def test_batch_end_drops_leftover_tickets(store, issuer, tmp_path):
    open_gate_batch(store, issuer)
    ev, d = pre(store, "write_file")
    assert d.deny is None and ev.tool_use_id in _tickets(store)
    batch_end(store, ev)  # the host refused the call: the server never took its ticket
    assert ev.tool_use_id not in _tickets(store)
    path = transcript_with(tmp_path, "no citations here")
    cev = codex_tool("pre_tool", path)
    assert engine.handle(store, cev).deny is None and cev.tool_use_id in _tickets(store)
    engine.handle(store, codex("stop", path, text="done", ends_batch=True))
    assert _tickets(store) == {}


def test_research_batch_leaves_gate_open(store, issuer):
    open_gate_batch(store, issuer)
    research_batch(store)
    assert gate.gate_is_current(store, S)


def codex_pre(store, path, tool, batch_key, tool_use_id):
    return engine.handle(store, codex("pre_tool", path, batch_key=batch_key, tool=tool,
                                      host_tool="mcp__chr-gate__" + tool, tool_use_id=tool_use_id))


def test_codex_new_turn_ends_replaced_consequential_batch(store, issuer, tmp_path):
    witness = issuer.read_work_order(S).witness
    assert gate.open_gate(store, S, witness, turn_key="turn-0").status == gate.OPEN
    path = transcript_with(tmp_path, "no citations here")
    assert codex_pre(store, path, "write_file", "turn-1", "c-1").deny is None
    assert gate.take_gate(store, S, "turn-1").ok
    d = codex_pre(store, path, "write_file", "turn-2", "c-2")  # no Stop between the turns
    assert d.deny is not None and "call open_gate first" in d.deny
    assert "c-1" not in _tickets(store)
    assert not gate.gate_is_current(store, S)


def test_codex_new_turn_after_nonconsequential_turn_keeps_gate(store, issuer, tmp_path):
    witness = issuer.read_work_order(S).witness
    assert gate.open_gate(store, S, witness, turn_key="turn-0").status == gate.OPEN
    path = transcript_with(tmp_path, "no citations here")
    assert codex_pre(store, path, "research_shell", "turn-1", "c-1").deny is None
    assert codex_pre(store, path, "write_file", "turn-2", "c-2").deny is None
    left = _tickets(store)
    assert "c-1" not in left and "c-2" in left
    assert gate.gate_is_current(store, S)


def test_codex_new_turn_ignores_pre_tool_batch_fields(store, issuer, tmp_path):
    witness = issuer.read_work_order(S).witness
    assert gate.open_gate(store, S, witness, turn_key="turn-0").status == gate.OPEN
    path = transcript_with(tmp_path, "no citations here")
    assert codex_pre(store, path, "research_shell", "turn-1", "c-1").deny is None
    tickets.put_ticket(store, "c-3", tool="research_shell", session_id=S, turn_key="turn-2")
    ev = codex("pre_tool", path, batch_key="turn-2", tool="write_file",
               host_tool="mcp__chr-gate__write_file", tool_use_id="c-2",
               batch_tool_use_ids=("c-2", "c-3"), batch_tools=("write_file",))
    assert engine.handle(store, ev).deny is None
    left = _tickets(store)
    assert "c-1" not in left and "c-2" in left and "c-3" in left
    assert gate.gate_is_current(store, S)


def test_codex_new_turn_after_consumed_gate_closes_gate(store, issuer, tmp_path):
    witness = issuer.read_work_order(S).witness
    assert gate.open_gate(store, S, witness, turn_key="turn-0").status == gate.OPEN
    path = transcript_with(tmp_path, "no citations here")
    assert codex_pre(store, path, "research_shell", "turn-1", "c-1").deny is None
    assert gate.take_gate(store, S, "turn-1").ok
    d = codex_pre(store, path, "write_file", "turn-2", "c-2")
    assert d.deny is not None and "call open_gate first" in d.deny
    assert "c-1" not in _tickets(store)
    assert not gate.gate_is_current(store, S)


def _batch(store):
    with store.lock():
        return store.read(engine.BATCHES, {})[S]


def test_record_call_refuses_differing_open_batch_key(store, tmp_path):
    with store.lock():
        store.write(engine.BATCHES, {S: {"key": "turn-1", "calls": {
            "c-1": {"tool": "research_shell", "consequential": False}}}})
    ev = codex("pre_tool", tmp_path / "rollout.jsonl", batch_key="turn-2", tool="research_shell",
               host_tool="mcp__chr-gate__research_shell", tool_use_id="c-2")
    with pytest.raises(ValueError, match="turn-1"):
        engine._record_call(store, ev)
    batch = _batch(store)
    assert batch["key"] == "turn-1" and set(batch["calls"]) == {"c-1"}  # raised before any write
    same = codex("pre_tool", tmp_path / "rollout.jsonl", batch_key="turn-1", tool="research_shell",
                 host_tool="mcp__chr-gate__research_shell", tool_use_id="c-3")
    assert engine._record_call(store, same) == "turn-1"
    assert set(_batch(store)["calls"]) == {"c-1", "c-3"}


def test_approve_activates_exact_proposed_text(store, wo_text):
    workorder.propose(store, "another proposal")
    plan = workorder.propose(store, wo_text)
    d = engine.handle(store, claude("user_prompt", text=f"approve {plan}"))
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


def _work_order_record(store):
    with store.lock():
        return store.read(workorder.WORK_ORDER, None)


def test_approval_needs_whole_prompt(store, wo_text):
    plan = workorder.propose(store, wo_text)
    for text in (f"do not approve {plan} yet",
                 f'2026-11-11T12:00:01Z hook user_prompt text="approve {plan}" outcome=ok',
                 f"Looks right. approve {plan}"):
        d = engine.handle(store, claude("user_prompt", text=text))
        assert _work_order_record(store) is None, text
        assert d.context is not None and "nothing was activated" in d.context, text
        assert f'mentions "approve {plan}" but is not exactly that phrase' in d.context
        assert d.context.endswith(f"To approve, reply with exactly: approve {plan}"), d.context
    d = engine.handle(store, claude("user_prompt", text=f"  approve {plan}\n"))
    record = _work_order_record(store)
    assert record["plan_id"] == plan and record["text"] == wo_text
    assert plan in d.context and "is now active" in d.context


def test_approval_ignored_from_subagent(store, wo_text):
    plan = workorder.propose(store, wo_text)
    d = engine.handle(store, claude("user_prompt", frame=CHILD, text=f"approve {plan}"))
    assert _work_order_record(store) is None
    assert d == Decision()


def test_revoke_needs_whole_prompt_and_active_ref(store, active_wo):
    plan = workorder.propose(store, "second text")
    wo2 = workorder.activate(store, plan, f"approve {plan}")
    issuer = WitnessIssuer(store)
    open_gate_batch(store, issuer)
    ref = wo2.ref

    def unrevoked():
        with store.lock():
            assert workorder.active(store) == wo2
        assert gate.gate_is_current(store, S)

    for text in (f"do not revoke {ref} yet", f"The plan is wrong. revoke {ref}"):
        d = engine.handle(store, claude("user_prompt", text=text))
        unrevoked()
        assert f'mentions "revoke {ref}" but is not exactly that phrase' in d.context, text
        assert "nothing was revoked" in d.context
        assert d.context.endswith(f"To revoke, reply with exactly: revoke {ref}"), d.context
    for other in (active_wo.ref, "wo:WO-00000000.v2", "wo:DW-0123abcd.v1"):
        d = engine.handle(store, claude("user_prompt", text=f"revoke {other}"))
        unrevoked()
        assert "nothing was revoked" in d.context and f"the active work order is {ref}" in d.context
    d = engine.handle(store, claude("user_prompt", text=f"  revoke {ref}\n"))
    assert d.context == (f"chr-gate: the user revoked {ref}; no work order is active. "
                         "Propose a new plan with propose_plan.")
    with store.lock():
        assert workorder.active(store) is None
    assert not gate.gate_is_current(store, S)


def test_revoke_ignored_from_subagent(store, active_wo):
    d = engine.handle(store, claude("user_prompt", frame=CHILD, text=f"revoke {active_wo.ref}"))
    assert d == Decision()
    with store.lock():
        assert workorder.active(store) == active_wo
    engine.handle(store, claude("user_prompt", text=f"revoke {active_wo.ref}"))
    with store.lock():
        assert workorder.active(store) is None  # the same prompt from the principal revokes


def test_builtin_denial_logged(store):
    for host_tool, denied in (("CronCreate", True), ("Read", False), ("Write", True)):
        ev = claude("pre_tool", host_tool=host_tool, tool_use_id=f"toolu_{next(_ids)}",
                    builtin_write=denied)
        assert (engine.handle(store, ev).deny is not None) == denied, host_tool
    logged = [(e["frame"], e["outcome"], e["ref"]) for e in events.read_all(store)
              if e["kind"] == "builtin_denied"]
    assert logged == [(S, "denied", "CronCreate"), (S, "denied", "Write")]


BOUNDS_RULE = ("Your task is limited by every inherited work order above. Where they disagree, "
               "the inherited order governs: stop and report to your assigner.")


def test_compaction_resurfaces_inherited_bounds_for_child(store, issuer, active_wo, wo_text):
    child_text, grandchild_text = "Only the parser tests.", "Only the CRLF test."
    assert gate.open_gate(store, S, issuer.read_work_order(S).witness).status == gate.OPEN
    d = delegation.delegate(store, S, f"under {active_wo.ref}", child_text)
    delegation.bind_child(store, CHILD, d.delegation_id)
    assert gate.open_gate(store, CHILD, issuer.read_work_order(CHILD).witness).status == gate.OPEN
    g = delegation.delegate(store, CHILD, f"under {d.ref}", grandchild_text)
    delegation.bind_child(store, GRANDCHILD, g.delegation_id)
    context = engine.handle(store, claude("compact", frame=GRANDCHILD)).context
    assert context == (
        "chr-gate: your context was compacted, which ended your witness and any open gate. "
        f"Your active work order is {g.ref}:\n"
        f"--- inherited bounds: {active_wo.ref} (approved by the user) ---\n{wo_text}\n"
        f"--- inherited bounds: {d.ref} (written by its assigner) ---\n{child_text}\n"
        f"{BOUNDS_RULE}\n"
        f"--- work order text (your task, written by your assigner) ---\n{grandchild_text}\n"
        "--- end of work order ---\nCall read_work_order (status) on the chr-gate server "
        "for a new witness before open_gate.")
