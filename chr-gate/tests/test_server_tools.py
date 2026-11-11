import errno
import itertools
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from chrgate.core import config, delegation, events, gate, nonces, testimony, workorder
from chrgate.server import sandbox, tickets
from chrgate.server.tools import (DELEGATION_ENDED_TEXT, NONCE_LABEL, TOOLS, GateServer)

SESSION = "session-A"
CHILD = "agent-child"
CHILD_TEXT = "Write the parser tests only."
REPO = Path(__file__).resolve().parents[2]
_ids = itertools.count()


@pytest.fixture
def project(isolated_env, monkeypatch):
    monkeypatch.delenv(tickets.ROOT_FRAME_ENV, raising=False)
    root = isolated_env / "project"
    sandbox.ensure_protected(root, GateServer(root).state_root)
    return root


@pytest.fixture
def server(project):
    return GateServer(project)


class Claude:
    """Claude Code calls: a PreToolUse ticket per call, matched by toolUseId."""

    def __init__(self, server, agent=None, session=SESSION):
        self.server, self.agent, self.session = server, agent, session

    def __call__(self, tool, args, turn="batch-1", ticket=True):
        tool_use_id = f"toolu_{next(_ids)}"
        if ticket:
            tickets.put_ticket(self.server.store, tool_use_id, tool=tool, session_id=self.session,
                               turn_key=turn, agent_id=self.agent)
        return self.server.call(tool, args, {tickets.CLAUDE_TOOL_USE_ID: tool_use_id})


def codex(server, tool, args, cell, thread="thread-main", parent=None, ticket=True):
    """Codex calls: a PreToolUse ticket per call under its own callId (the hook
    tool_use_id); frame and cell come from _meta."""
    call_id = f"exec-{next(_ids)}"
    if ticket:
        tickets.put_ticket(server.store, call_id, tool=tool, session_id=parent or thread,
                           turn_key=f"turn-{cell}", agent_id=thread if parent else None)
    meta = {"threadId": thread, "itemId": cell, "callId": call_id}
    if parent is not None:
        meta[tickets.CODEX_TURN_METADATA] = {"parent_thread_id": parent}
    return server.call(tool, args, meta, "codex-mcp-client")


def body(outcome):
    return outcome.text.rsplit("\n\n" + NONCE_LABEL, 1)[0]


def witness_of(outcome):
    assert not outcome.is_error, outcome.text
    return re.search(r"witness: (wit:[0-9a-f]{32})", outcome.text).group(1)


def opened(call, read_turn="t-read", open_turn="t-open"):
    witness = witness_of(call("status", {}, turn=read_turn))
    result = call("open_gate", {"witness": witness}, turn=open_turn)
    assert not result.is_error, result.text
    return witness


def claim(ref):
    return f"Fixing the parser under {ref}"


def test_missing_claim_refused(server, active_wo, project):
    call = Claude(server)
    opened(call)
    out = call("write_file", {"path": "a.txt", "content": "x"})
    assert out.is_error and "a claim argument is required" in out.text
    assert not (project / "a.txt").exists()


def test_first_key_not_claim_refused(server, active_wo, project):
    call = Claude(server)
    opened(call)
    out = call("write_file", {"path": "a.txt", "claim": claim(active_wo.ref), "content": "x"})
    assert out.is_error and "claim must be the first argument" in out.text
    assert not (project / "a.txt").exists()


def test_claim_without_work_order_reference_refused(server, active_wo, project):
    call = Claude(server)
    opened(call)
    out = call("write_file", {"claim": "because it helps", "path": "a.txt", "content": "x"})
    assert out.is_error and "must cite your work order reference" in out.text
    assert not (project / "a.txt").exists()


def test_no_open_gate_refused(server, active_wo, project):
    call = Claude(server)
    args = {"claim": claim(active_wo.ref), "path": "a.txt", "content": "x"}
    out = call("write_file", args)
    assert out.is_error and body(out) == gate.DENIED_TEXT
    witness_of(call("status", {}, turn="t-read"))
    out = call("write_file", args)
    assert out.is_error and body(out) == gate.DENIED_TEXT
    assert not (project / "a.txt").exists()


def test_wrong_witness_says_read_work_order(server, active_wo):
    call = Claude(server)
    witness_of(call("status", {}, turn="t-read"))
    out = call("open_gate", {"witness": "wit:" + "0" * 32}, turn="t-open")
    assert out.is_error and body(out) == "read your work order"
    assert not gate.gate_is_current(server.store, SESSION)


def test_correct_witness_resurfaces_full_text(server, active_wo, wo_text):
    call = Claude(server)
    witness = witness_of(call("status", {}, turn="t-read"))
    out = call("open_gate", {"witness": witness}, turn="t-open")
    assert not out.is_error
    assert body(out).endswith("--- work order text ---\n" + wo_text)
    assert gate.gate_is_current(server.store, SESSION)


def test_status_same_witness_and_cancels_gate(server, active_wo, project):
    call = Claude(server)
    first = witness_of(call("status", {}, turn="t-read"))
    assert witness_of(call("read_work_order", {}, turn="t-read-2")) == first
    assert not call("open_gate", {"witness": first}, turn="t-open").is_error
    assert witness_of(call("status", {}, turn="t-read-3")) == first
    args = {"claim": claim(active_wo.ref), "path": "a.txt", "content": "x"}
    out = call("write_file", args)
    assert out.is_error and body(out) == gate.DENIED_TEXT
    assert not call("open_gate", {"witness": first}, turn="t-open-2").is_error
    assert not call("write_file", args).is_error
    assert (project / "a.txt").read_text() == "x"


def test_two_writes_same_gate_both_succeed(server, active_wo, project):
    call = Claude(server)
    opened(call)
    for name in ("a.txt", "b.txt"):
        out = call("write_file", {"claim": claim(active_wo.ref), "path": name, "content": name})
        assert not out.is_error, out.text
        assert (project / name).read_text() == name
    assert gate.close_gate(server.store, SESSION)
    out = call("write_file", {"claim": claim(active_wo.ref), "path": "c.txt", "content": "c"})
    assert out.is_error and body(out) == gate.DENIED_TEXT
    assert not (project / "c.txt").exists()


def test_second_batch_refused_consumed(server, active_wo, project):
    call = Claude(server)
    opened(call)
    args = {"claim": claim(active_wo.ref), "path": "a.txt", "content": "x"}
    assert not call("write_file", args, turn="batch-1").is_error
    out = call("write_file", {**args, "path": "b.txt"}, turn="batch-2")
    assert out.is_error and body(out) == gate.CONSUMED_TEXT
    assert not (project / "b.txt").exists()


def test_unticketed_consequential_call_refused(server, active_wo, project):
    call = Claude(server)
    opened(call)
    args = {"claim": claim(active_wo.ref), "path": "a.txt", "content": "x"}
    out = call("write_file", args, ticket=False)
    assert out.is_error and "did not ticket this Claude Code call" in out.text
    last = [e for e in events.read_all(server.store) if e["kind"].startswith("tool:")][-1]
    assert last["outcome"] == "refused-" + tickets.CLAUDE_NO_TICKET
    out = server.call("write_file", args)
    assert out.is_error and "not mediated" in out.text
    assert not (project / "a.txt").exists()


def test_write_outside_project_or_into_dot_claude_refused(server, active_wo, project,
                                                           isolated_env):
    call = Claude(server)
    opened(call)
    os.symlink(isolated_env / "home", project / "link")
    for path in ("../outside.txt", str(isolated_env / "outside.txt"), "link/x.txt",
                 ".claude/settings.json", ".codex/config.toml", ".mcp.json", ".git/config",
                 "sub/.git/hooks/pre-commit", "."):
        out = call("edit_file" if path == ".mcp.json" else "write_file",
                   {"claim": claim(active_wo.ref), "path": path, "content": "x"}
                   if path != ".mcp.json" else
                   {"claim": claim(active_wo.ref), "path": path, "old": "{", "new": "["})
        assert out.is_error, path
        assert "outside the project root" in out.text or "is protected" in out.text, out.text
    assert not (isolated_env / "outside.txt").exists()
    assert not (isolated_env / "home" / "x.txt").exists()
    assert not (project / ".claude" / "settings.json").exists()
    assert json.loads((project / ".mcp.json").read_text()) == sandbox.EMPTY_MCP_JSON
    assert not (project / "sub").exists()
    assert not call("write_file", {"claim": claim(active_wo.ref), "path": "ok/in.txt",
                                   "content": "x"}).is_error


def test_file_tools_refuse_mutate_protected_paths(server, active_wo, project):
    subprocess.run(["git", "-C", str(project), "init", "-q"], check=True)
    (project / ".git" / "hooks").mkdir(exist_ok=True)
    subprocess.run(["git", "-C", str(project), "config", "core.hooksPath", ".husky/_"], check=True)
    call = Claude(server)
    opened(call)
    c = claim(active_wo.ref)
    targets = (".gitmodules", ".vscode/settings.json", ".husky/_/pre-commit")
    for path in targets:
        out = call("write_file", {"claim": c, "path": path, "content": "pwned"})
        assert out.is_error and "is protected" in out.text, out.text
    assert not any(os.path.lexists(project / name) for name in (".gitmodules", ".vscode", ".husky"))
    for path in targets:
        (project / path).parent.mkdir(parents=True, exist_ok=True)
        (project / path).write_text("orig\n")
    for path in targets:
        out = call("edit_file", {"claim": c, "path": path, "old": "orig", "new": "pwned"})
        assert out.is_error and "is protected" in out.text, out.text
        assert (project / path).read_text() == "orig\n"
    out = call("write_file", {"claim": c, "path": ".husky/ok.txt", "content": "x"})
    assert not out.is_error, out.text
    assert (project / ".husky" / "ok.txt").read_text() == "x"


def test_effect_tools_refuse_when_protected_path_absent(server, active_wo, project):
    (project / ".codex").rmdir()
    (project / "e.txt").write_text("old")
    call = Claude(server)
    opened(call)
    c = claim(active_wo.ref)
    for tool, args in (("write_file", {"claim": c, "path": "w.txt", "content": "x"}),
                       ("edit_file", {"claim": c, "path": "e.txt", "old": "old", "new": "new"}),
                       ("mutate_shell", {"claim": c, "command": "touch m.txt; mkdir .codex"})):
        out = call(tool, args)
        assert out.is_error, tool
        assert ".codex" in out.text and "chrgate-setup" in out.text, out.text
        assert not (project / ".codex").exists()
    assert not (project / "w.txt").exists() and not (project / "m.txt").exists()
    assert (project / "e.txt").read_text() == "old"
    assert sandbox.ensure_protected(project, server.state_root) == [project / ".codex"]
    assert not call("write_file", {"claim": c, "path": "w.txt", "content": "x"}).is_error
    assert (project / "w.txt").read_text() == "x"


def test_tools_registry_claim_first():
    consequential = {t.name for t in TOOLS if t.consequential}
    assert consequential == {"write_file", "edit_file", "mutate_shell", "delegate", "testify"}
    for t in TOOLS:
        schema = t.input_schema
        if t.consequential:
            assert list(schema["properties"])[0] == "claim", t.name
            assert schema["required"][0] == "claim", t.name
        else:
            assert "claim" not in schema["properties"], t.name
    assert len({t.name for t in TOOLS}) == len(TOOLS)


def test_bad_arguments_list_accepted_arguments(server, active_wo, project):
    call = Claude(server)
    out = call("propose_plan", {"plan": "Create a.txt."}, turn="t-p")
    assert out.is_error
    assert body(out) == "propose_plan: unknown argument(s) ['plan']; accepted: text (required)"
    out = call("status", {"bogus": "x"}, turn="t-s")
    assert out.is_error
    assert body(out) == "status: unknown argument(s) ['bogus']; accepted: delegation_id"
    out = call("write_file", {"claim": claim(active_wo.ref), "path": "a.txt"})
    assert out.is_error
    assert body(out) == ("write_file: missing argument 'content'; accepted: claim (required), "
                         "path (required), content (required)")
    assert not (project / "a.txt").exists()


def test_take_gate_guards_every_consequential_tool(server, active_wo, project):
    (project / "e.txt").write_text("old")
    call = Claude(server)
    c = claim(active_wo.ref)
    cases = {"write_file": {"claim": c, "path": "w.txt", "content": "x"},
             "edit_file": {"claim": c, "path": "e.txt", "old": "old", "new": "new"},
             "mutate_shell": {"claim": c, "command": "touch m.txt"},
             "delegate": {"claim": c, "work_order": CHILD_TEXT},
             "testify": {"claim": c, "text": "I saw it."}}
    for n, (tool, args) in enumerate(cases.items()):
        opened(call, read_turn=f"r-{n}", open_turn=f"o-{n}")
        assert not call("write_file", {"claim": c, "path": f"consume-{n}.txt", "content": "x"},
                        turn=f"consume-{n}").is_error
        out = call(tool, args, turn=f"other-{n}")
        assert out.is_error and body(out) == gate.CONSUMED_TEXT, (tool, out.text)
        opened(call, read_turn=f"r2-{n}", open_turn=f"o2-{n}")
        for k in range(4):
            gate.note_turn(server.store, SESSION, f"research-{n}-{k}")
        out = call(tool, args, turn=f"late-{n}")
        assert out.is_error and body(out) == gate.EXPIRED_TEXT, (tool, out.text)
    assert not (project / "w.txt").exists() and not (project / "m.txt").exists()
    assert (project / "e.txt").read_text() == "old"
    assert testimony.read_all(server.store) == []
    with server.store.lock():
        assert server.store.read(workorder.DELEGATIONS, {}) == {}


def test_codex_open_gate_in_witness_cell_refused(server, active_wo, project):
    witness = witness_of(codex(server, "status", {}, "c1"))
    out = codex(server, "open_gate", {"witness": witness}, "c1")
    assert out.is_error and body(out).startswith(gate.DENIED_TEXT)
    assert not gate.gate_is_current(server.store, "thread-main")
    assert not codex(server, "open_gate", {"witness": witness}, "c2").is_error
    args = {"claim": claim(active_wo.ref), "path": "a.txt", "content": "x"}
    out = codex(server, "write_file", args, "c2")
    assert out.is_error and body(out) == gate.OPENING_TURN_TEXT
    assert not codex(server, "write_file", args, "c3").is_error
    assert (project / "a.txt").exists()


def test_codex_call_without_item_id_refused(server, active_wo, project):
    out = server.call("status", {}, {"threadId": "thread-main"}, "codex-mcp-client")
    assert out.is_error and "itemId" in out.text
    out = server.call("status", {}, {}, "codex-mcp-client")
    assert out.is_error and "itemId" in out.text
    out = server.call("write_file", {"claim": claim(active_wo.ref), "path": "a.txt",
                                     "content": "x"}, {"threadId": "thread-main"})
    assert out.is_error and "itemId" in out.text
    assert not (project / "a.txt").exists()
    with server.store.lock():
        assert server.store.read(workorder.FRAMES, {}) == {}


def test_codex_call_without_ticket_refused(server, active_wo, project):
    out = codex(server, "status", {}, "c1", ticket=False)
    assert out.is_error and "witness:" not in out.text, out.text
    assert "did not ticket this Codex call" in out.text and "/hooks" in out.text, out.text
    args = {"claim": claim(active_wo.ref), "path": "a.txt", "content": "x"}
    out = codex(server, "write_file", args, "c2", ticket=False)
    assert out.is_error and "did not ticket this Codex call" in out.text, out.text
    refusal = "refused-codex-no-ticket"
    assert [(e["kind"], e["frame"], e["outcome"]) for e in events.read_all(server.store)
            if e["kind"].startswith("tool:")] == [("tool:status", "thread-main", refusal),
                                                  ("tool:write_file", "thread-main", refusal)]
    assert not (project / "a.txt").exists()
    with server.store.lock():
        assert server.store.read(workorder.FRAMES, {}) == {}


def test_codex_call_with_ticket_attributed(store):
    meta = {"threadId": "thread-child", "itemId": "ctc_1", "callId": "exec-A",
            tickets.CODEX_TURN_METADATA: {"parent_thread_id": "thread-main"}}
    tickets.put_ticket(store, "exec-A", tool="status", session_id="thread-main",
                       turn_key="turn-1", agent_id="thread-child")
    caller = tickets.attribute(store, "status", meta, "codex-mcp-client")
    assert caller == tickets.Caller(tickets.CODEX, "thread-child", "ctc_1", mediated=True,
                                    subagent=True, parent_frame="thread-main")
    with store.lock():
        assert "exec-A" not in store.read(tickets.TICKETS, {})  # consumed
    with pytest.raises(tickets.AttributionRefused) as e:
        tickets.attribute(store, "status", meta, "codex-mcp-client")
    assert e.value.code == tickets.CODEX_NO_TICKET and e.value.frame == "thread-child"
    tickets.put_ticket(store, "exec-B", tool="open_gate", session_id="thread-main",
                       turn_key="turn-1")
    with pytest.raises(tickets.AttributionRefused) as e:  # a ticket for another tool
        tickets.attribute(store, "status", {**meta, "callId": "exec-B"}, "codex-mcp-client")
    assert e.value.code == tickets.CODEX_NO_TICKET
    with store.lock():
        assert "exec-B" in store.read(tickets.TICKETS, {})


def test_codex_research_cells_count_turns(server, active_wo, project):
    args = {"claim": claim(active_wo.ref), "path": "a.txt", "content": "x"}
    witness = witness_of(codex(server, "status", {}, "c-read"))
    assert not codex(server, "open_gate", {"witness": witness}, "c-open").is_error
    for k in range(3):
        assert not codex(server, "research_shell", {"command": "true"}, f"r{k}").is_error
    assert not codex(server, "write_file", args, "c-act").is_error
    assert not codex(server, "open_gate", {"witness": witness}, "c-open-2").is_error
    for k in range(4):
        assert not codex(server, "research_shell", {"command": "true"}, f"s{k}").is_error
    out = codex(server, "write_file", {**args, "path": "b.txt"}, "c-act-2")
    assert out.is_error and body(out) == "pending gate expired; reopen with the same witness"
    assert not (project / "b.txt").exists()


def test_claude_ticket_matched_by_tool_use_id(server, active_wo, project):
    opened(Claude(server))
    args = {"claim": claim(active_wo.ref), "path": "a.txt", "content": "x"}
    tickets.put_ticket(server.store, "toolu_X", tool="write_file", session_id=SESSION,
                       turn_key="batch-1")
    meta = {tickets.CLAUDE_TOOL_USE_ID: "toolu_X"}
    assert not server.call("write_file", args, meta).is_error
    out = server.call("write_file", {**args, "path": "b.txt"}, meta)  # ticket consumed
    assert out.is_error and "did not ticket this Claude Code call" in out.text
    tickets.put_ticket(server.store, "toolu_Y", tool="status", session_id=SESSION,
                       turn_key="batch-1")
    out = server.call("write_file", {**args, "path": "b.txt"}, {tickets.CLAUDE_TOOL_USE_ID: "toolu_Y"})
    assert out.is_error and "did not ticket this Claude Code call" in out.text
    assert not (project / "b.txt").exists()
    with server.store.lock():
        assert list(server.store.read(workorder.FRAMES, {})) == [SESSION]


def test_attribute_refuses_claude_call_without_matching_ticket(store, monkeypatch):
    monkeypatch.setenv(tickets.ROOT_FRAME_ENV, "stale-session")
    with pytest.raises(tickets.AttributionRefused) as e:
        tickets.attribute(store, "status", {tickets.CLAUDE_TOOL_USE_ID: "toolu_none"})
    assert e.value.code == tickets.CLAUDE_NO_TICKET and e.value.frame == "stale-session"
    assert "status refused" in e.value.message
    tickets.put_ticket(store, "toolu_other", tool="open_gate", session_id=SESSION,
                       turn_key="batch-1")
    with pytest.raises(tickets.AttributionRefused) as e:
        tickets.attribute(store, "status", {tickets.CLAUDE_TOOL_USE_ID: "toolu_other"})
    assert e.value.code == tickets.CLAUDE_NO_TICKET
    with store.lock():
        assert "toolu_other" in store.read(tickets.TICKETS, {})
    caller = tickets.attribute(store, "status", {})
    assert (caller.host, caller.frame, caller.mediated) == (tickets.NO_HOST, "stale-session", False)


def test_unticketed_claude_status_refused_without_side_effect(server, active_wo, monkeypatch):
    monkeypatch.setenv(tickets.ROOT_FRAME_ENV, "stale-session")
    refusal = ("tool:status", "stale-session", "refused-" + tickets.CLAUDE_NO_TICKET)

    def tool_events():
        return [(e["kind"], e["frame"], e["outcome"]) for e in events.read_all(server.store)
                if e["kind"].startswith("tool:")]

    out = Claude(server)("status", {}, ticket=False)
    assert out.is_error and "witness:" not in out.text, out.text
    assert tool_events()[-1] == refusal
    tickets.put_ticket(server.store, "toolu_other", tool="open_gate", session_id=SESSION,
                       turn_key="batch-1")
    out = server.call("status", {}, {tickets.CLAUDE_TOOL_USE_ID: "toolu_other"})
    assert out.is_error and "witness:" not in out.text, out.text
    assert tool_events()[-1] == refusal
    with server.store.lock():
        assert server.store.read(workorder.FRAMES, {}) == {}
    assert tool_events() == [refusal, refusal]


def _delegated(server, active_wo):
    parent = Claude(server)
    opened(parent)
    out = parent("delegate", {"claim": claim(active_wo.ref), "work_order": CHILD_TEXT})
    assert not out.is_error, out.text
    return re.search(r"delegation id: (D-[0-9a-f]+)", out.text).group(1)


def test_subagent_work_order_read_requires_delegation_id(server, active_wo, wo_text):
    delegation_id = _delegated(server, active_wo)
    child = Claude(server, agent=CHILD)
    out = child("status", {}, turn="c-read")
    assert out.is_error and "delegation id" in out.text
    with server.store.lock():
        assert CHILD not in server.store.read(workorder.FRAMES, {})
    out = child("status", {"delegation_id": delegation_id}, turn="c-read-2")
    assert not out.is_error, out.text
    assert "work order wo:DW-" in out.text and body(out).endswith(CHILD_TEXT)
    assert f"(approved by the user) ---\n{wo_text}\n" in out.text
    assert not child("status", {}, turn="c-read-3").is_error  # registered now
    out = codex(server, "status", {}, "x1", thread="thread-child", parent="thread-main")
    assert out.is_error and "delegation id" in out.text


def test_lapsed_delegation_message(server, active_wo, store):
    delegation_id = _delegated(server, active_wo)
    child = Claude(server, agent=CHILD)
    out = child("status", {"delegation_id": delegation_id}, turn="c-read")
    ref = re.search(r"work order (wo:DW-[0-9a-f]+\.v1)", out.text).group(1)
    assert not child("open_gate", {"witness": witness_of(out)}, turn="c-open").is_error
    plan_id = workorder.propose(store, "revised")
    workorder.activate(store, plan_id, f"approve {plan_id}")
    out = child("write_file", {"claim": f"under {ref}", "path": "a.txt", "content": "x"},
                turn="c-act")
    assert out.is_error and body(out) == DELEGATION_ENDED_TEXT
    out = child("status", {}, turn="c-read-2")
    assert out.is_error and body(out) == DELEGATION_ENDED_TEXT


def test_status_delegation_lapsed_between_read_and_render(server, active_wo, store, monkeypatch):
    delegation_id = _delegated(server, active_wo)
    read = server.issuer.read_work_order

    def lapsing(frame):  # the principal is revised after the read, before the render
        result = read(frame)
        plan_id = workorder.propose(store, "revised")
        workorder.activate(store, plan_id, f"approve {plan_id}")
        return result

    monkeypatch.setattr(server.issuer, "read_work_order", lapsing)
    out = Claude(server, agent=CHILD)("status", {"delegation_id": delegation_id}, turn="c-read")
    assert out.is_error and body(out) == DELEGATION_ENDED_TEXT, out.text
    last = [e for e in events.read_all(server.store) if e["kind"].startswith("tool:")][-1]
    assert last["outcome"] == "refused-delegation-ended"


def test_revoke_clears_gates_and_ends_delegated_children(server, active_wo, store, project):
    delegation_id = _delegated(server, active_wo)
    parent, child = Claude(server), Claude(server, agent=CHILD)
    opened(parent, read_turn="t-read-2", open_turn="t-open-2")
    out = child("status", {"delegation_id": delegation_id}, turn="c-read")
    ref = re.search(r"work order (wo:DW-[0-9a-f]+\.v1)", out.text).group(1)
    assert not child("open_gate", {"witness": witness_of(out)}, turn="c-open").is_error
    assert gate.gate_is_current(store, SESSION) and gate.gate_is_current(store, CHILD)

    workorder.revoke(store, active_wo.ref, f"revoke {active_wo.ref}")

    with store.lock():
        recs = store.read(workorder.FRAMES, {})
    for frame in (SESSION, CHILD):
        assert recs[frame]["gate"] is None and recs[frame]["witness_sha256"] is None, frame
        assert not gate.gate_is_current(store, frame), frame
    out = parent("write_file", {"claim": claim(active_wo.ref), "path": "a.txt", "content": "x"},
                 turn="t-act")
    assert out.is_error, out.text
    out = child("write_file", {"claim": f"under {ref}", "path": "b.txt", "content": "x"},
                turn="c-act")
    assert out.is_error and body(out) == DELEGATION_ENDED_TEXT
    assert not (project / "a.txt").exists() and not (project / "b.txt").exists()
    out = child("status", {}, turn="c-read-2")
    assert out.is_error and body(out) == DELEGATION_ENDED_TEXT


BOUNDS_RULE = ("Your task is limited by every inherited work order above. Where they disagree, "
               "the inherited order governs: stop and report to your assigner.")
PROHIBITION = "Never touch the deploy keys under secrets/."


def _status_head(ref, witness):
    return (f"work order {ref}\nwitness: {witness}\nCall open_gate with this witness, then cite "
            f"{ref} in the claim of each consequential call.\n")


def test_child_status_and_open_gate_carry_principal_text_before_task(server, store):
    principal_text = f"Fix the parser in src/parser.py. {PROHIBITION}"
    plan_id = workorder.propose(store, principal_text)
    principal = workorder.activate(store, plan_id, f"approve {plan_id}")
    assert PROHIBITION not in CHILD_TEXT
    delegation_id = _delegated(server, principal)
    child = Claude(server, agent=CHILD)
    status = child("status", {"delegation_id": delegation_id}, turn="c-read")
    assert not status.is_error, status.text
    ref = re.search(r"work order (wo:DW-[0-9a-f]+\.v1)", status.text).group(1)
    witness = witness_of(status)
    section = (f"--- inherited bounds: {principal.ref} (approved by the user) ---\n"
               f"{principal_text}\n{BOUNDS_RULE}\n"
               f"--- work order text (your task, written by your assigner) ---\n{CHILD_TEXT}")
    assert body(status) == _status_head(ref, witness) + section
    gate_out = child("open_gate", {"witness": witness}, turn="c-open")
    assert not gate_out.is_error, gate_out.text
    assert body(gate_out) == f"gate open under {ref}\n" + section
    for text in (body(status), body(gate_out)):
        assert text.index(principal_text) < text.index(CHILD_TEXT)


def test_principal_status_text_unchanged(server, active_wo, wo_text):
    call = Claude(server)
    status = call("status", {}, turn="t-read")
    witness = witness_of(status)
    assert body(status) == (_status_head(active_wo.ref, witness)
                            + f"--- work order text ---\n{wo_text}")
    out = call("open_gate", {"witness": witness}, turn="t-open")
    assert body(out) == f"gate open under {active_wo.ref}\n--- work order text ---\n{wo_text}"


def test_tool_results_carry_fresh_nonce(server, active_wo):
    call = Claude(server)
    results = [call("status", {}, turn="t-read"),
               call("open_gate", {"witness": "wit:" + "1" * 32}, turn="t-open"),
               call("propose_plan", {"text": "next"}, turn="t-p"),
               call("write_file", {"claim": "x", "path": "a.txt", "content": "x"}),
               server.call("status", {})]
    found = [re.fullmatch(r"(?s).*" + re.escape(NONCE_LABEL) + r"(ctx:[0-9a-f]{16})",
                          r.text).group(1) for r in results]
    assert len(set(found)) == len(found)
    with server.store.lock():
        assert all(nonces.is_current(server.store, SESSION, n) for n in found[:4])
    out = call("cite", {"nonces": found[:4]}, turn="t-cite")
    assert not out.is_error and out.text.startswith(NONCE_LABEL)
    out = call("cite", {"nonces": ["ctx:" + "0" * 16]}, turn="t-cite-2")
    assert "chr-citation-warning" in out.text
    kinds = [e["kind"] for e in events.read_all(server.store) if e["kind"].startswith("tool:")]
    assert len(kinds) == len(results) + 2


def test_bad_config_reported_as_configuration_error(server, active_wo):
    call = Claude(server)
    witness = opened(call)
    path = server.store.root / config.CONFIG
    path.write_text(json.dumps({"max_intervening_turns": "3"}))
    for out in (call("write_file", {"claim": claim(active_wo.ref), "path": "a.txt",
                                    "content": "x"}),
                call("open_gate", {"witness": witness}, turn="t-open-2")):
        assert out.is_error
        assert "configuration error" in out.text and str(path) in out.text
        assert gate.DENIED_TEXT not in out.text


@pytest.mark.parametrize("site", ["note_turn", "take_gate", "status", "read_work_order"])
def test_missing_turn_key_refused(server, active_wo, project, monkeypatch, site):
    caller = tickets.Caller(tickets.CODEX, "thread-main", None, mediated=True, subagent=False)
    monkeypatch.setattr(tickets, "attribute", lambda *_: caller)
    tool, args = {"note_turn": ("cite", {"nonces": []}),
                  "take_gate": ("write_file", {"claim": claim(active_wo.ref), "path": "a.txt",
                                               "content": "x"}),
                  "status": ("status", {}),
                  "read_work_order": ("read_work_order", {})}[site]
    out = server.call(tool, args)
    assert out.is_error, out.text
    assert out.text.startswith(f"{tool} refused"), out.text
    last = [e for e in events.read_all(server.store) if e["kind"].startswith("tool:")][-1]
    assert last["outcome"] == "refused-no-turn-key"
    if site == "take_gate":
        assert not (project / "a.txt").exists()
    if site in ("status", "read_work_order"):
        assert "thread-main" not in server._witness_cell


def test_delegated_status_without_turn_key_refused_before_binding(server, active_wo, monkeypatch):
    delegation_id = _delegated(server, active_wo)
    with server.store.lock():
        delegations = server.store.read(workorder.DELEGATIONS, {})
        frames = server.store.read(workorder.FRAMES, {})
    record = delegation.find(delegations, delegation_id)
    assert record["caller_frame"] == SESSION  # the parent check would pass: bind_child is reachable
    assert "thread-child" not in frames
    caller = tickets.Caller(tickets.CODEX, "thread-child", None, mediated=True, subagent=True,
                            parent_frame=SESSION)
    monkeypatch.setattr(tickets, "attribute", lambda *_: caller)
    out = server.call("status", {"delegation_id": delegation_id})
    assert out.is_error, out.text
    assert out.text.startswith("status refused"), out.text
    log = events.read_all(server.store)
    last = [e for e in log if e["kind"].startswith("tool:")][-1]
    assert last["outcome"] == "refused-no-turn-key"
    with server.store.lock():
        assert "thread-child" not in server.store.read(workorder.FRAMES, {})
        after = server.store.read(workorder.DELEGATIONS, {})
    assert after == delegations
    record = delegation.find(after, delegation_id)
    assert record["child_frame"] is None and record["bound_at"] is None
    assert "thread-child" not in server._witness_cell
    assert not [e for e in log if e["kind"] == "bind_child" and e["frame"] == "thread-child"]


def test_oserror_becomes_internal_error_refusal(server, monkeypatch):
    def broken(self, caller, args):
        raise OSError(5, "Input/output error")

    monkeypatch.setattr(GateServer, "_status", broken)
    out = Claude(server)("status", {})
    assert out.is_error and re.search(NONCE_LABEL + r"ctx:[0-9a-f]{16}$", out.text), out.text
    last = events.read_all(server.store)[-1]
    assert (last["kind"], last["outcome"]) == ("tool:status", "refused-internal-error")


def _swap_after_take_gate(monkeypatch, server, sub):
    """After the first path check (take_gate runs after it), replace the project
    directory SUB with a symlink to the state root."""
    take = gate.take_gate

    def swapping(*args, **kwargs):
        result = take(*args, **kwargs)
        shutil.rmtree(sub)
        os.symlink(server.state_root, sub)
        return result

    monkeypatch.setattr(gate, "take_gate", swapping)


def _fresh_dir(sub):
    if sub.is_symlink():
        sub.unlink()
    sub.mkdir()


def test_write_file_rechecks_path_under_project_lock(server, active_wo, project, monkeypatch):
    call = Claude(server)
    opened(call)
    sub = project / "sub"
    _swap_after_take_gate(monkeypatch, server, sub)
    for n in range(20):
        _fresh_dir(sub)
        out = call("write_file", {"claim": claim(active_wo.ref), "path": "sub/x.txt",
                                  "content": "x"})
        assert out.is_error and "outside the project root" in out.text, (n, out.text)
        assert not (server.state_root / "x.txt").exists(), n


def test_edit_file_rechecks_path_under_project_lock(server, active_wo, project, monkeypatch):
    call = Claude(server)
    opened(call)
    sub = project / "sub"
    decoy = server.state_root / "e.txt"
    decoy.write_text("old")
    _swap_after_take_gate(monkeypatch, server, sub)
    for n in range(20):
        _fresh_dir(sub)
        (sub / "e.txt").write_text("old")
        out = call("edit_file", {"claim": claim(active_wo.ref), "path": "sub/e.txt",
                                 "old": "old", "new": "new"})
        assert out.is_error and "outside the project root" in out.text, (n, out.text)
        assert decoy.read_text() == "old", n


def test_write_file_refuses_symlinked_final_component(server, active_wo, project, isolated_env,
                                                      monkeypatch):
    call = Claude(server)
    opened(call)
    sub = project / "sub"
    sub.mkdir()
    resolved = Path(os.path.realpath(sub))
    decoy = isolated_env / "decoy.txt"
    decoy.write_text("orig")
    mkdir = Path.mkdir

    def planting(self, *args, **kwargs):  # the parent mkdir runs after every path check
        mkdir(self, *args, **kwargs)
        if self == resolved and not os.path.lexists(resolved / "a.txt"):
            os.symlink(decoy, resolved / "a.txt")

    monkeypatch.setattr(Path, "mkdir", planting)
    out = call("write_file", {"claim": claim(active_wo.ref), "path": "sub/a.txt",
                              "content": "pwned"})
    monkeypatch.undo()
    assert out.is_error and body(out).startswith("write_file: "), out.text
    assert decoy.read_text() == "orig"
    last = [e for e in events.read_all(server.store) if e["kind"].startswith("tool:")][-1]
    assert last["outcome"] == "refused-write-failed"


def test_edit_file_refuses_symlink_at_open(server, active_wo, project, isolated_env, monkeypatch):
    call = Claude(server)
    opened(call)
    outside = isolated_env / "outside.txt"
    outside.write_text("old outside")
    (project / "e.txt").write_text("old")
    real_target = GateServer._target
    cached = []

    def planting(self, tool, path):  # both path checks pass; the open meets the symlink
        if not cached:
            target = real_target(self, tool, path)
            link = target.with_name("e.txt.link")
            os.symlink(outside, link)
            os.replace(link, target)
            cached.append(target)
        return cached[0]

    monkeypatch.setattr(GateServer, "_target", planting)
    out = call("edit_file", {"claim": claim(active_wo.ref), "path": "e.txt", "old": "old",
                             "new": "new"})
    assert out.is_error and body(out).startswith("edit_file: "), out.text
    assert os.strerror(errno.ELOOP) in out.text and "outside the project" not in out.text
    assert outside.read_text() == "old outside"
    last = [e for e in events.read_all(server.store) if e["kind"].startswith("tool:")][-1]
    assert last["outcome"] == "refused-edit-failed"


def test_server_refuses_inside_own_source_tree():
    server = GateServer(REPO)
    probe = REPO / "chrgate-self-hosting-probe.txt"
    out = server.call("status", {})
    assert out.is_error and "cannot govern its own source tree" in out.text, out.text
    out = Claude(server)("write_file", {"claim": "under wo:W-0.v1", "path": probe.name,
                                        "content": "x"})
    assert out.is_error and "cannot govern its own source tree" in out.text, out.text
    assert not probe.exists()
    last = [e for e in events.read_all(server.store) if e["kind"].startswith("tool:")][-1]
    assert last["outcome"] == "refused-self-hosting"


def test_claude_child_from_other_session_refused(server, active_wo):
    delegation_id = _delegated(server, active_wo)
    out = Claude(server, agent=CHILD, session="session-B")(
        "status", {"delegation_id": delegation_id}, turn="c-read")
    assert out.is_error and "made in another session" in out.text, out.text
    with server.store.lock():
        assert CHILD not in server.store.read(workorder.FRAMES, {})
    out = Claude(server, agent=CHILD)("status", {"delegation_id": delegation_id}, turn="c-read-2")
    assert not out.is_error, out.text  # the same-session control binds
    assert body(out).endswith(CHILD_TEXT)
