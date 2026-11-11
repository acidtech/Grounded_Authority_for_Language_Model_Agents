"""chrgate-hook --host codex on the recorded Codex payloads
(tests/fixtures/payloads/codex, T0b), through the INSTALLED console script.
The spike's MCP server was named probe, so CHR_GATE_SERVER=probe. PreToolUse
writes a ticket under the hook tool_use_id (the server's _meta.callId); the
batch end is Stop."""

import json
import os
import subprocess
import sys
from pathlib import Path

from chrgate.core import events, gate, nonces
from chrgate.server import tickets
from chrgate.server.tools import NONCE_LABEL

HOOK = Path(sys.executable).parent / "chrgate-hook"
FIXTURES = Path(__file__).parent / "fixtures" / "payloads" / "codex"
SPIKE_MCP = Path(__file__).parent / "fixtures" / "spike-raw" / "codex" / "mcp.jsonl"


def payload(name):
    return json.loads((FIXTURES / name).read_bytes())


def run_raw(raw, server="probe"):
    assert HOOK.is_file(), f"console script missing: {HOOK} (run uv sync in chr-gate/)"
    r = subprocess.run([str(HOOK), "--host", "codex"], input=raw,
                       capture_output=True, timeout=60, env={**os.environ, "CHR_GATE_SERVER": server})
    assert r.returncode == 0, r.stderr.decode()
    return r.stdout.decode()


def run_hook(name):
    return run_raw((FIXTURES / name).read_bytes())


def with_rollout(name, tmp_path, **changes):
    """Payload NAME with CHANGES, its transcript_path moved to an empty rollout
    under TMP_PATH (the recorded path exists only on the recording machine)."""
    rollout = tmp_path / "rollout.jsonl"
    rollout.write_text("", encoding="utf-8")
    return json.dumps({**payload(name), "transcript_path": str(rollout), **changes}).encode()


def hook_errors(store):
    return [e for e in events.read_all(store) if e["kind"] == "hook_error"]


def test_console_script_chrgate_hook():
    assert HOOK.is_file() and os.access(HOOK, os.X_OK)


def test_builtin_writes_denied(store):
    for name, tool in (("PreToolUse__builtin_apply_patch.json", "apply_patch"),
                       ("PreToolUse__builtin_bash.json", "Bash")):
        out = json.loads(run_hook(name))["hookSpecificOutput"]
        assert out["hookEventName"] == "PreToolUse" and out["permissionDecision"] == "deny"
        assert tool in out["permissionDecisionReason"]
        assert "chr-gate MCP tools" in out["permissionDecisionReason"]


def test_unknown_builtin_denied(store, tmp_path):
    raw = with_rollout("PreToolUse__spawn_agent.json", tmp_path, tool_name="invented_builtin_tool")
    text = run_raw(raw)
    assert text, "the hook allowed the built-in invented_builtin_tool"
    out = json.loads(text)["hookSpecificOutput"]
    assert out["permissionDecision"] == "deny"
    assert "invented_builtin_tool" in out["permissionDecisionReason"]
    assert "chr-gate MCP tools" in out["permissionDecisionReason"]


def test_read_only_builtins_allowed(store, tmp_path):
    assert run_raw(with_rollout("PreToolUse__spawn_agent.json", tmp_path)) == ""
    assert hook_errors(store) == []


def test_other_mcp_server_tool_not_denied(store, tmp_path):
    # with the chr-gate server named chr_gate, mcp__probe__probe_write is another server's tool
    raw = with_rollout("PreToolUse__mcp_probe_write.json", tmp_path)
    assert run_raw(raw, server="chr_gate") == ""
    assert hook_errors(store) == []


def test_codex_pre_tool_writes_ticket_keyed_by_tool_use_id(store, tmp_path):
    p = payload("PreToolUse__mcp_probe_write.json")
    assert run_raw(with_rollout("PreToolUse__mcp_probe_write.json", tmp_path)) == ""
    with store.lock():
        ticket = store.read(tickets.TICKETS, {}).get(p["tool_use_id"])
    assert ticket is not None, "PreToolUse wrote no ticket under the hook tool_use_id"
    assert (ticket["tool"], ticket["session_id"], ticket["turn_key"], ticket["agent_id"]) == (
        "probe_write", p["session_id"], p["turn_id"], None)
    # the recorded MCP call of this hook call carries the tool_use_id as _meta.callId
    calls = [json.loads(line) for line in SPIKE_MCP.read_text(encoding="utf-8").splitlines()]
    meta = next(c["meta"] for c in calls
                if c["kind"] == "tools/call" and c["meta"].get("callId") == p["tool_use_id"])
    caller = tickets.attribute(store, "probe_write", meta, "codex-mcp-client")
    assert (caller.host, caller.frame, caller.turn_key) == (tickets.CODEX, meta["threadId"],
                                                            meta["itemId"])
    with store.lock():
        assert p["tool_use_id"] not in store.read(tickets.TICKETS, {})


def test_post_tool_carries_nonce(store):
    p = payload("PostToolUse__mcp_probe_write.json")
    out = json.loads(run_hook("PostToolUse__mcp_probe_write.json"))["hookSpecificOutput"]
    assert out["hookEventName"] == "PostToolUse"
    assert out["additionalContext"].startswith(NONCE_LABEL + "ctx:")
    with store.lock():
        assert nonces.is_current(store, p["session_id"], out["additionalContext"][len(NONCE_LABEL):])


def test_stop_closes_gate_after_consequential_call(store, issuer):
    frame = payload("Stop__plain.json")["session_id"]
    witness = issuer.read_work_order(frame).witness
    assert gate.open_gate(store, frame, witness, turn_key="ctc_opening").status == gate.OPEN
    assert run_hook("Stop__plain.json") == ""
    assert gate.gate_is_current(store, frame)  # research only: the gate stays open
    assert gate.take_gate(store, frame, "ctc_consequential").ok  # the server took the gate
    assert run_hook("Stop__plain.json") == ""
    assert not gate.gate_is_current(store, frame)
