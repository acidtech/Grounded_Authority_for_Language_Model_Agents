"""chrgate-hook --host claude-code on the recorded Claude Code payloads
(tests/fixtures/payloads/claude_code, T0b), through the INSTALLED console
script. The spike's MCP server was named probe, so CHR_GATE_SERVER=probe."""

import json
import os
import subprocess
import sys
from pathlib import Path

from chrgate.core import events, gate, nonces
from chrgate.hooks import engine
from chrgate.server import tickets
from chrgate.server.tools import NONCE_LABEL

HOOK = Path(sys.executable).parent / "chrgate-hook"
FIXTURES = Path(__file__).parent / "fixtures" / "payloads" / "claude_code"


def payload(name):
    return json.loads((FIXTURES / name).read_bytes())


def run_raw(raw, **env):
    assert HOOK.is_file(), f"console script missing: {HOOK} (run uv sync in chr-gate/)"
    r = subprocess.run([str(HOOK), "--host", "claude-code"], input=raw,
                       capture_output=True, timeout=60,
                       env={**os.environ, "CHR_GATE_SERVER": "probe", **env})
    assert r.returncode == 0, r.stderr.decode()
    return r.stdout.decode()


def run_hook(name, **env):
    return run_raw((FIXTURES / name).read_bytes(), **env)


def hook_output(name):
    return json.loads(run_hook(name))["hookSpecificOutput"]


def ticket(store, tool_use_id):
    with store.lock():
        return store.read(tickets.TICKETS, {})[tool_use_id]


def test_console_script_chrgate_hook():
    assert HOOK.is_file() and os.access(HOOK, os.X_OK)


def test_hook_denies_pre_tool_inside_own_source_tree(store):
    repo = Path(__file__).resolve().parents[2]
    out = run_hook("PreToolUse__mcp_probe_write.json", CHR_GATE_PROJECT=str(repo))
    assert out, "the hook made no decision for a project holding the chr-gate source"
    decision = json.loads(out)["hookSpecificOutput"]
    assert decision["hookEventName"] == "PreToolUse" and decision["permissionDecision"] == "deny"
    assert "cannot govern its own source tree" in decision["permissionDecisionReason"]


def test_builtin_write_denied(store):
    for name, tool in (("PreToolUse__builtin_write.json", "Write"),
                       ("PreToolUse__builtin_bash.json", "Bash")):
        out = hook_output(name)
        assert out["hookEventName"] == "PreToolUse" and out["permissionDecision"] == "deny"
        assert tool in out["permissionDecisionReason"]
        assert "chr-gate MCP tools" in out["permissionDecisionReason"]


def hook_errors(store):
    return [e for e in events.read_all(store) if e["kind"] == "hook_error"]


def test_unknown_builtin_denied(store):
    p = payload("PreToolUse__builtin_toolsearch.json")
    for tool in ("CronCreate", "InventedBuiltinTool"):
        out = run_raw(json.dumps({**p, "tool_name": tool}).encode())
        assert out, f"the hook allowed the built-in {tool}"
        decision = json.loads(out)["hookSpecificOutput"]
        assert decision["permissionDecision"] == "deny", tool
        assert tool in decision["permissionDecisionReason"]
        assert "chr-gate MCP tools" in decision["permissionDecisionReason"]


def test_read_only_builtins_allowed(store):
    for name in ("PreToolUse__builtin_toolsearch.json", "PreToolUse__agent_launch.json"):
        assert run_hook(name) == "", name
    assert hook_errors(store) == []


def test_other_mcp_server_tool_not_denied(store):
    # with the chr-gate server named chr-gate, mcp__probe__probe_write is another server's tool
    assert run_hook("PreToolUse__mcp_probe_write.json", CHR_GATE_SERVER="chr-gate") == ""
    assert hook_errors(store) == []
    with store.lock():
        assert store.read(tickets.TICKETS, {}) == {}


def test_mcp_chr_gate_tool_ticketed(store):
    p = payload("PreToolUse__mcp_probe_write.json")
    assert run_hook("PreToolUse__mcp_probe_write.json") == ""
    t = ticket(store, p["tool_use_id"])
    assert t["tool"] == "probe_write" and t["session_id"] == p["session_id"]
    assert t["agent_id"] is None and t["turn_key"].startswith(engine.BATCH_PREFIX)


def test_post_tool_carries_nonce(store):
    p = payload("PostToolUse__mcp_probe_write.json")
    out = hook_output("PostToolUse__mcp_probe_write.json")
    assert out["hookEventName"] == "PostToolUse"
    assert out["additionalContext"].startswith(NONCE_LABEL + "ctx:")
    with store.lock():
        assert nonces.is_current(store, p["session_id"], out["additionalContext"][len(NONCE_LABEL):])


def test_batch_end_closes_gate(store, issuer):
    p = payload("PreToolUse__mcp_probe_write.json")
    frame = p["session_id"]
    witness = issuer.read_work_order(frame).witness
    assert gate.open_gate(store, frame, witness, turn_key="B-opening").status == gate.OPEN
    # a research batch (the server consumed the ticket but took no gate) leaves it open
    assert run_hook("PreToolUse__mcp_probe_write.json") == ""
    assert tickets.take_ticket(store, p["tool_use_id"], "probe_write") is not None
    assert run_hook("PostToolBatch__two_parallel.json") == ""
    assert gate.gate_is_current(store, frame)
    # a batch whose call the server took the gate for ends with close_gate
    assert run_hook("PreToolUse__mcp_probe_write.json") == ""
    assert gate.take_gate(store, frame, ticket(store, p["tool_use_id"])["turn_key"]).ok
    assert run_hook("PostToolBatch__two_parallel.json") == ""
    assert not gate.gate_is_current(store, frame)


def test_ticket_keyed_by_tool_use_id_with_batch_key(store):
    p = payload("PreToolUse__child_mcp_probe_write.json")
    assert run_hook("PreToolUse__child_mcp_probe_write.json") == ""
    with store.lock():
        recorded = store.read(tickets.TICKETS, {})
        batch = store.read(engine.BATCHES, {})[p["agent_id"]]
    assert list(recorded) == [p["tool_use_id"]]
    assert recorded[p["tool_use_id"]]["agent_type"] == p["agent_type"]
    caller = tickets.attribute(store, "probe_write", {tickets.CLAUDE_TOOL_USE_ID: p["tool_use_id"]})
    assert caller.mediated and caller.subagent and caller.frame == p["agent_id"]
    assert caller.turn_key == batch["key"] and p["tool_use_id"] in batch["calls"]


def _prompt_ends_batch(store, issuer, ending):
    """No PostToolBatch arrives: the ENDING event (UserPromptSubmit or Stop)
    must end the open batch."""
    p = payload("PreToolUse__mcp_probe_write.json")
    frame = p["session_id"]
    witness = issuer.read_work_order(frame).witness
    assert gate.open_gate(store, frame, witness, turn_key="B-opening").status == gate.OPEN
    run_hook(ending)
    assert gate.gate_is_current(store, frame)  # control: an unused open gate survives
    assert run_hook("PreToolUse__mcp_probe_write.json") == ""
    first = tickets.take_ticket(store, p["tool_use_id"], "probe_write")["turn_key"]
    assert gate.take_gate(store, frame, first).ok
    run_hook(ending)
    assert run_hook("PreToolUse__mcp_probe_write.json") == ""
    second = ticket(store, p["tool_use_id"])["turn_key"]
    assert second != first, "the batch survived the prompt"
    assert not gate.take_gate(store, frame, second).ok


def test_user_prompt_ends_claude_batch(store, issuer):
    _prompt_ends_batch(store, issuer, "UserPromptSubmit__plain.json")


def test_stop_ends_claude_batch(store, issuer):
    _prompt_ends_batch(store, issuer, "Stop__plain.json")
