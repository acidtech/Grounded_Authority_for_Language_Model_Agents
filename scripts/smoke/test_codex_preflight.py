"""Regression tests for codex_preflight.py (T7a2, bug aa2aea) against a stub codex.

Run as: cd chr-gate && uv run --frozen --no-sync pytest -q -p no:cacheprovider \
../scripts/smoke/test_codex_preflight.py
"""
import json
import os
import subprocess
import sys
from pathlib import Path

PREFLIGHT = Path(__file__).with_name("codex_preflight.py")
PAIRS = ['sandbox_mode="read-only"', "features.shell_tool=false"]
ERROR_REPLY = {"jsonrpc": "2.0", "id": 2,
               "error": {"code": -32603, "message": "stub: mcp server status unavailable"}}

# Behaves like codex-cli 0.162.1 `codex app-server` for the pre-flight exchange.
STUB = r'''#!@PYTHON@
import json, sys, tomllib
MODE = @MODE@
ERROR_REPLY = @ERROR@
open(@MARKER@, "a").write(json.dumps(sys.argv[1:]) + "\n")
args = sys.argv[1:]
if args[:1] != ["app-server"]:
    sys.exit(f"stub codex: unexpected arguments {args}")
pairs, rest, i = [], args[1:], 0
while i < len(rest):
    if rest[i] != "-c":
        sys.exit(f"stub codex: unexpected argument {rest[i]!r}")
    if i + 1 == len(rest) or rest[i + 1] == "-c":
        sys.stderr.write("error: a value is required for '--config <key=value>' but none was supplied\n")
        sys.exit(2)
    pairs.append(rest[i + 1])
    i += 2
if MODE == "exit3":
    sys.stderr.write("stub app-server: fatal: could not load the plugin marketplace\n")
    sys.exit(3)
config = {}
for pair in pairs:
    key, raw = pair.split("=", 1)
    *parents, leaf = key.split(".")
    node = config
    for part in parents:
        node = node.setdefault(part, {})
    node[leaf] = tomllib.loads(f"v = {raw}")["v"]

def send(message):
    sys.stdout.write(json.dumps(message) + "\n")
    sys.stdout.flush()

for line in iter(sys.stdin.readline, ""):
    rid = json.loads(line).get("id")
    if rid == 1:
        send({"jsonrpc": "2.0", "id": 1, "result": {"userAgent": "stub/0.162.1"}})
    elif rid == 2:
        send({"jsonrpc": "2.0", "method": "remoteControl/status/changed", "params": {}})
        if MODE == "error2":
            send(ERROR_REPLY)
        else:
            send({"jsonrpc": "2.0", "id": 2, "result": {"data": [
                {"name": "chr-gate", "pluginId": "chr-gate@chr-gate-local",
                 "tools": {"propose_plan": {}, "open_gate": {}, "status": {}}}]}})
    elif rid == 3:
        send({"jsonrpc": "2.0", "id": 3, "result": {"config": config}})
'''


def run_preflight(tmp_path, pairs, mode="ok"):
    bindir, proj = tmp_path / "bin", tmp_path / "proj"
    bindir.mkdir()
    proj.mkdir()
    marker = tmp_path / "stub-ran.jsonl"
    stub = bindir / "codex"
    stub.write_text(STUB.replace("@PYTHON@", sys.executable).replace("@MODE@", repr(mode))
                    .replace("@ERROR@", repr(ERROR_REPLY)).replace("@MARKER@", repr(str(marker))))
    stub.chmod(0o755)
    env = dict(os.environ, PATH=f"{bindir}{os.pathsep}{os.environ['PATH']}")
    proc = subprocess.run([sys.executable, str(PREFLIGHT), str(proj), *pairs], cwd=proj, env=env,
                          capture_output=True, text=True, timeout=60)
    return proc, marker


def test_preflight_passes_with_single_c_pairs(tmp_path):
    proc, marker = run_preflight(tmp_path, PAIRS)
    assert proc.returncode == 0, proc.stderr
    assert json.loads(marker.read_text()) == ["app-server", "-c", PAIRS[0], "-c", PAIRS[1]]
    assert proc.stdout.splitlines() == [
        "pre-flight: MCP server 'chr-gate' (pluginId chr-gate@chr-gate-local) lists 3 tools",
        "pre-flight: sandbox_mode = 'read-only'",
        "pre-flight: features.shell_tool = False",
    ]


def test_preflight_rejects_flag_arguments(tmp_path):
    proc, marker = run_preflight(tmp_path, ["-c", PAIRS[0]])
    assert proc.returncode != 0
    assert "argument '-c' is not a bare key=value pair" in proc.stderr
    assert not marker.exists()


def test_preflight_reports_app_server_exit(tmp_path):
    proc, marker = run_preflight(tmp_path, PAIRS, mode="exit3")
    assert proc.returncode != 0
    assert marker.exists()
    assert "exited with code 3" in proc.stderr
    assert "stub app-server: fatal: could not load the plugin marketplace" in proc.stderr


def test_preflight_reports_error_reply(tmp_path):
    proc, _ = run_preflight(tmp_path, PAIRS, mode="error2")
    assert proc.returncode != 0
    assert ("smoke: pre-flight: app-server gave no result for request 2: "
            + json.dumps(ERROR_REPLY)) in proc.stderr
