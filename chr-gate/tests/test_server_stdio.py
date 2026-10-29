import json
import os
import select
import subprocess
import sys
from pathlib import Path

import pytest

from chrgate.core import workorder
from chrgate.core.store import Store
from chrgate.server import sandbox, tickets
from chrgate.server.tools import TOOLS

SESSION = "session-A"
INIT = (b'{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":'
        b'"2025-11-25","capabilities":{},"clientInfo":{"name":"chrgate-test","version":"0"}}}')
INITIALIZED = b'{"jsonrpc":"2.0","method":"notifications/initialized"}'


class Stdio:
    """A chr-gate server subprocess spoken to in literal JSON-RPC lines."""

    def __init__(self, argv, cwd):
        env = {k: v for k, v in os.environ.items() if k != tickets.ROOT_FRAME_ENV}
        self.proc = subprocess.Popen(argv, cwd=cwd, env=env, bufsize=0, stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.buf = b""
        self.send(INIT)
        assert "result" in self.answer(1)
        self.send(INITIALIZED)

    def send(self, line):
        self.proc.stdin.write(line + b"\n")

    def answer(self, request_id, timeout=30):
        fd = self.proc.stdout.fileno()
        while True:
            while b"\n" not in self.buf:
                if not select.select([fd], [], [], timeout)[0]:
                    raise AssertionError("server did not answer")
                chunk = os.read(fd, 65536)
                if not chunk:
                    raise AssertionError("server exited: " + self.proc.stderr.read().decode())
                self.buf += chunk
            line, self.buf = self.buf.split(b"\n", 1)
            message = json.loads(line)
            if message.get("id") == request_id:
                return message

    def close(self):
        self.proc.stdin.close()
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait()


@pytest.fixture
def project(isolated_env):
    root = isolated_env / "project"
    sandbox.ensure_protected(root, Store.for_project(root).root)
    return root


def _call(server, request_id, raw_params):
    server.send(b'{"jsonrpc":"2.0","id":%d,"method":"tools/call","params":%s}'
                % (request_id, raw_params))
    result = server.answer(request_id)["result"]
    return result["isError"], result["content"][0]["text"]


def _ticketed(store, tool_use_id, tool):
    tickets.put_ticket(store, tool_use_id, tool=tool, session_id=SESSION, turn_key="batch-1"
                       if tool == "write_file" else f"turn-{tool_use_id}")
    return b'"_meta":{"claudecode/toolUseId":"%s"}' % tool_use_id.encode()


def test_raw_argument_order_over_stdio(project):
    store = Store.for_project(project)
    plan_id = workorder.propose(store, "Write a.txt.")
    ref = workorder.activate(store, plan_id, f"approve {plan_id}").ref.encode()
    server = Stdio([sys.executable, "-m", "chrgate.server.app"], project)
    try:
        error, text = _call(server, 2, b'{"name":"status","arguments":{},%s}'
                            % _ticketed(store, "toolu_1", "status"))
        assert not error, text
        witness = text.split("witness: ", 1)[1].split("\n", 1)[0].encode()
        error, text = _call(server, 3, b'{"name":"open_gate","arguments":{"witness":"%s"},%s}'
                            % (witness, _ticketed(store, "toolu_2", "open_gate")))
        assert not error, text
        error, text = _call(server, 4, b'{"name":"write_file","arguments":{"content":"hi",'
                            b'"claim":"under %s","path":"a.txt"},%s}'
                            % (ref, _ticketed(store, "toolu_3", "write_file")))
        assert error and "claim must be the first argument" in text
        assert not (project / "a.txt").exists()
        error, text = _call(server, 5, b'{"name":"write_file","arguments":{"claim":"under %s",'
                            b'"path":"a.txt","content":"hi"},%s}'
                            % (ref, _ticketed(store, "toolu_4", "write_file")))
        assert not error, text
        assert (project / "a.txt").read_text() == "hi"
    finally:
        server.close()


def test_console_script_chrgate_mcp(project):
    script = Path(sys.executable).parent / "chrgate-mcp"
    assert script.is_file(), f"{script} missing: run uv sync in chr-gate/"
    server = Stdio([str(script)], project)
    try:
        server.send(b'{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}')
        listed = [t["name"] for t in server.answer(2)["result"]["tools"]]
        assert listed == [t.name for t in TOOLS]
    finally:
        server.close()
