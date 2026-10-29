"""chrgate-hook --host codex on the recorded Codex payloads
(tests/fixtures/payloads/codex, T0b), through the INSTALLED console script.
The spike's MCP server was named probe, so CHR_GATE_SERVER=probe. Codex writes
no ticket (the server takes the frame from _meta); its batch end is Stop."""

import json
import os
import subprocess
import sys
from pathlib import Path

from chrgate.core import gate, nonces
from chrgate.server.tools import NONCE_LABEL

HOOK = Path(sys.executable).parent / "chrgate-hook"
FIXTURES = Path(__file__).parent / "fixtures" / "payloads" / "codex"


def payload(name):
    return json.loads((FIXTURES / name).read_bytes())


def run_hook(name):
    assert HOOK.is_file(), f"console script missing: {HOOK} (run uv sync in chr-gate/)"
    r = subprocess.run([str(HOOK), "--host", "codex"], input=(FIXTURES / name).read_bytes(),
                       capture_output=True, timeout=60, env={**os.environ, "CHR_GATE_SERVER": "probe"})
    assert r.returncode == 0, r.stderr.decode()
    return r.stdout.decode()


def test_console_script_chrgate_hook():
    assert HOOK.is_file() and os.access(HOOK, os.X_OK)


def test_builtin_writes_denied(store):
    for name, tool in (("PreToolUse__builtin_apply_patch.json", "apply_patch"),
                       ("PreToolUse__builtin_bash.json", "Bash")):
        out = json.loads(run_hook(name))["hookSpecificOutput"]
        assert out["hookEventName"] == "PreToolUse" and out["permissionDecision"] == "deny"
        assert tool in out["permissionDecisionReason"]
        assert "chr-gate MCP tools" in out["permissionDecisionReason"]


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
