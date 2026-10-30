"""Regression tests for the root frame probe kit (debt dcb46a).

Run as: cd chr-gate && uv run --frozen --no-sync pytest -q -p no:cacheprovider \
../scripts/smoke/test_root_frame_probe.py
"""
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import root_frame_probe  # noqa: E402

DRIVER = HERE / "probe_root_frame.sh"
PROBE = HERE / "root_frame_probe.py"


def _call(use_id, env_id, pid=101):
    return {"kind": "call", "ts": 1.0, "pid": pid, "env_session_id": env_id, "tool_use_id": use_id}


def _hook(use_id, session_id):
    return {"kind": "hook", "ts": 1.0, "session_id": session_id, "tool_use_id": use_id,
            "tool_name": "mcp__whoami__whoami"}


def _check(tmp_path, mcp_records, hook_records):
    mcp_log, hook_log = tmp_path / "mcp.jsonl", tmp_path / "hook.jsonl"
    mcp_log.write_text("".join(json.dumps(r) + "\n" for r in mcp_records), encoding="utf-8")
    hook_log.write_text("".join(json.dumps(r) + "\n" for r in hook_records), encoding="utf-8")
    return root_frame_probe.main(["check", "--mcp-log", str(mcp_log), "--hook-log", str(hook_log)])


def _verdicts(mcp_records, hook_records):
    return [(row.tool_use_id, row.verdict) for row in root_frame_probe.pair(mcp_records, hook_records)]


def test_pair_all_match(tmp_path):
    start = {"kind": "start", "ts": 0.5, "pid": 101, "env_session_id": "sess-A"}
    mcp = [start, _call("toolu_1", "sess-A"), _call("toolu_2", "sess-A")]
    hooks = [_hook("toolu_2", "sess-A"), _hook("toolu_1", "sess-A")]
    assert _verdicts(mcp, hooks) == [("toolu_1", "MATCH"), ("toolu_2", "MATCH")]
    assert _check(tmp_path, mcp, hooks) == 0


def test_pair_mismatch_after_clear(tmp_path):
    # /clear starts a new hook session id while the MCP server keeps its env value.
    mcp = [_call("toolu_1", "sess-A"), _call("toolu_2", "sess-A")]
    hooks = [_hook("toolu_1", "sess-A"), _hook("toolu_2", "sess-B")]
    rows = root_frame_probe.pair(mcp, hooks)
    assert [(r.tool_use_id, r.env_session_id, r.hook_session_id, r.verdict) for r in rows] == [
        ("toolu_1", "sess-A", "sess-A", "MATCH"), ("toolu_2", "sess-A", "sess-B", "MISMATCH")]
    assert _check(tmp_path, mcp, hooks) == 1


def test_pair_unpaired_and_missing_env(tmp_path, capsys):
    mcp = [_call("toolu_1", None)]
    hooks = [_hook("toolu_1", None), _hook("toolu_9", "sess-A")]
    assert _verdicts(mcp, hooks) == [("toolu_1", "MISMATCH"), ("toolu_9", "UNPAIRED")]
    assert _check(tmp_path, mcp, hooks) == 1
    assert "UNPAIRED" in capsys.readouterr().out
    assert _verdicts([], []) == []
    empty = tmp_path / "empty"
    empty.mkdir()
    assert _check(empty, [], []) == 1  # no pair is not a pass


def test_probe_end_to_end_offline(tmp_path):
    root = tmp_path / "probe"
    env = {**os.environ, "PROBE_ROOT": str(root)}
    setup = subprocess.run(["bash", str(DRIVER), "setup"], env=env, capture_output=True, text=True)
    assert setup.returncode == 0, setup.stderr
    server = json.loads((root / "proj" / ".mcp.json").read_text())["mcpServers"]["whoami"]
    assert server["command"] == "python3"
    assert server["args"] == [str(PROBE), "server", "--log", str(root / "mcp.jsonl")]
    settings = json.loads((root / "proj" / ".claude" / "settings.json").read_text())
    assert settings["enableAllProjectMcpServers"] is True
    [entry] = settings["hooks"]["PreToolUse"]
    assert entry["matcher"] == "mcp__whoami__whoami"
    hook_command = entry["hooks"][0]["command"]
    assert str(PROBE) in hook_command and str(root / "hook.jsonl") in hook_command

    requests = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                    "clientInfo": {"name": "test", "version": "0"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
         "params": {"name": "whoami", "arguments": {}, "_meta": {"claudecode/toolUseId": "toolu_1"}}},
    ]
    served = subprocess.run([server["command"], *server["args"]], cwd=root / "proj",
                            env={**os.environ, "CLAUDE_CODE_SESSION_ID": "sess-X"},
                            input="".join(json.dumps(r) + "\n" for r in requests),
                            capture_output=True, text=True, timeout=30)
    assert served.returncode == 0, served.stderr
    replies = [json.loads(line) for line in served.stdout.splitlines()]
    assert [r["id"] for r in replies] == [1, 2, 3]  # the notification got no reply
    assert replies[0]["result"]["protocolVersion"] == "2025-06-18"
    assert [t["name"] for t in replies[1]["result"]["tools"]] == ["whoami"]
    assert "sess-X" in replies[2]["result"]["content"][0]["text"]

    payload = {"session_id": "sess-X", "tool_use_id": "toolu_1", "tool_name": "mcp__whoami__whoami",
               "hook_event_name": "PreToolUse", "tool_input": {}}
    hooked = subprocess.run(hook_command, shell=True, input=json.dumps(payload),
                            capture_output=True, text=True, timeout=30)
    assert (hooked.returncode, hooked.stdout) == (0, ""), hooked.stderr

    check = subprocess.run(["bash", str(DRIVER), "check"], env=env, capture_output=True, text=True)
    assert check.returncode == 0, check.stdout + check.stderr
    rows = [line.split("\t") for line in check.stdout.splitlines() if "\t" in line]
    assert rows[1:] == [["toolu_1", str(json.loads((root / "mcp.jsonl").read_text().splitlines()[1])["pid"]),
                         "sess-X", "sess-X", "MATCH"]]
