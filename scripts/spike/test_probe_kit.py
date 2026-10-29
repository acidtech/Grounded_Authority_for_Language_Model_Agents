"""Regression tests for the CHR gate spike kit.

Run: PYTHONDONTWRITEBYTECODE=1 uv run --no-project --with pytest --with 'mcp>=2.3,<3' \
         pytest -p no:cacheprovider scripts/spike/test_probe_kit.py
"""

import json
import os
import queue
import subprocess
import sys
import threading
from pathlib import Path

KIT = Path(__file__).resolve().parent
TIMEOUT = 30


def _env(out_dir: Path) -> dict:
    env = dict(os.environ)
    env["CHR_SPIKE_OUT"] = str(out_dir)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_probe_server_logs_raw_argument_order(tmp_path):
    proc = subprocess.Popen(
        [sys.executable, str(KIT / "probe_mcp_server.py")],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=_env(tmp_path),
        cwd=tmp_path,
    )
    lines: queue.Queue = queue.Queue()
    threading.Thread(target=lambda: [lines.put(line) for line in proc.stdout], daemon=True).start()

    def send(raw: str) -> None:
        proc.stdin.write(raw.encode("utf-8") + b"\n")
        proc.stdin.flush()

    def response(request_id: int) -> dict:
        while True:
            message = json.loads(lines.get(timeout=TIMEOUT))
            if message.get("id") == request_id:
                return message

    try:
        send('{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18",'
             '"capabilities":{},"clientInfo":{"name":"test","version":"0"}}}')
        assert "result" in response(1)
        send('{"jsonrpc":"2.0","method":"notifications/initialized"}')
        send('{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}')
        tools = {tool["name"]: tool for tool in response(2)["result"]["tools"]}
        schema = tools["probe_write"]["inputSchema"]
        assert list(schema["properties"]) == ["claim", "path", "content"]
        assert "claim" in schema["required"]
        assert list(tools["probe_read"]["inputSchema"]["properties"]) == ["path"]

        raw_arguments = '{"content":"body","claim":"why","path":"x.txt"}'
        send('{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"probe_write",'
             f'"arguments":{raw_arguments},"_meta":{{"probe":"meta-1"}}}}}}')
        assert response(3)["result"]["isError"] is False
    finally:
        proc.stdin.close()
        proc.wait(timeout=TIMEOUT)

    records = _read_jsonl(tmp_path / "mcp.jsonl")
    start = records[0]
    assert start["kind"] == "start" and start["cwd"] == str(tmp_path)
    assert "CHR_SPIKE_OUT" in start["env_names"] and str(tmp_path) not in json.dumps(start["env_names"])
    calls = [r for r in records if r["kind"] == "tools/call"]
    assert len(calls) == 1
    call = calls[0]
    assert call["tool"] == "probe_write"
    assert call["argument_keys"] == ["content", "claim", "path"]  # neither schema nor sorted order
    assert call["raw_arguments"] == raw_arguments
    assert call["meta"] == {"probe": "meta-1"}


def test_probe_hook_logs_and_denies(tmp_path):
    payload = {
        "session_id": "s-1",
        "transcript_path": str(tmp_path / "missing-transcript.jsonl"),
        "cwd": str(tmp_path),
        "hook_event_name": "PreToolUse",
        "tool_name": "Write",
        "tool_input": {"file_path": str(tmp_path / "x.txt"), "content": "x"},
    }
    result = subprocess.run(
        [sys.executable, str(KIT / "probe_hook.py"), "--host", "claude", "--event", "PreToolUse"],
        input=json.dumps(payload).encode("utf-8"),
        capture_output=True,
        env=_env(tmp_path),
        timeout=TIMEOUT,
    )
    assert result.returncode == 0, result.stderr.decode()
    decision = json.loads(result.stdout)
    assert decision["hookSpecificOutput"]["hookEventName"] == "PreToolUse"
    assert decision["hookSpecificOutput"]["permissionDecision"] == "deny"

    records = _read_jsonl(tmp_path / "hooks.jsonl")
    assert len(records) == 1
    record = records[0]
    assert record["event"] == "PreToolUse" and record["host"] == "claude"
    assert record["payload"] == payload
    assert json.loads(record["stdin_raw"]) == payload
    assert "CHR_SPIKE_OUT" in record["env_names"]
    assert record["emitted"] == decision
    assert record["transcripts"] == [{"path": payload["transcript_path"], "exists": False}]


def test_probe_hook_never_stores_transcript_text(tmp_path):
    secret = "SECRET-TRANSCRIPT-LINE user@example.invalid do-not-store"
    transcript = tmp_path / "transcript.jsonl"
    transcript_lines = [
        {"type": "user", "message": {"role": "user", "content": secret}},
        {"type": "assistant", "message": {"role": "assistant", "content": "CITE-NONCE-7 I rely on the work order."}},
        {"type": "user", "message": {"role": "user", "content": "hook context SPIKE-CTX-3"}},
    ]
    transcript.write_text("".join(json.dumps(line) + "\n" for line in transcript_lines), encoding="utf-8")
    payload = {
        "session_id": "s-2",
        "transcript_path": str(transcript),
        "cwd": str(tmp_path),
        "hook_event_name": "Stop",
    }
    env = _env(tmp_path)
    env["CHR_SPIKE_LABEL"] = "privacy"
    result = subprocess.run(
        [sys.executable, str(KIT / "probe_hook.py"), "--host", "claude", "--event", "Stop"],
        input=json.dumps(payload).encode("utf-8"),
        capture_output=True,
        env=env,
        timeout=TIMEOUT,
    )
    assert result.returncode == 0, result.stderr.decode()

    hit = {"line": 2, "kind": "assistant/assistant"}
    expected = {
        "path": str(transcript),
        "exists": True,
        "size": transcript.stat().st_size,
        "line_count": 3,
        "markers": {"DELEG-123": [], "CITE-NONCE-7": [hit]},
        "spike_ctx": {"3": [{"line": 3, "kind": "user/user"}]},
    }
    hooks_text = (tmp_path / "hooks.jsonl").read_text(encoding="utf-8")
    assert "SECRET-TRANSCRIPT-LINE" not in hooks_text and "user@example.invalid" not in hooks_text
    assert _read_jsonl(tmp_path / "hooks.jsonl")[0]["transcripts"] == [expected]

    # The runners' shared entry point summarizes the same way into transcripts-summary.jsonl.
    result = subprocess.run(
        [sys.executable, str(KIT / "transcript_summary.py"), str(tmp_path)],
        capture_output=True,
        env=env,
        timeout=TIMEOUT,
    )
    assert result.returncode == 0, result.stderr.decode()
    summary_text = (tmp_path / "transcripts-summary.jsonl").read_text(encoding="utf-8")
    assert "SECRET-TRANSCRIPT-LINE" not in summary_text and "user@example.invalid" not in summary_text
    assert _read_jsonl(tmp_path / "transcripts-summary.jsonl") == [{"labels": ["privacy"], **expected}]
    assert not (tmp_path / "transcripts").exists()
