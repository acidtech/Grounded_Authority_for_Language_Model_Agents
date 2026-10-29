"""Codex smoke pre-flight (T7a2): codex_preflight.py PROJECT KEY=VALUE...

Run by smoke_codex.sh before the first model turn. Starts the `codex` found on
PATH as `codex app-server` with exactly one -c per bare KEY=VALUE pair, then
checks that mcpServerStatus/list lists a chr-gate server with its tools and
that config/read shows every pair in effect. Otherwise no session can pass, so
it exits non-zero. When the app-server's stdout ends before both replies, the
failure names its exit code and stderr; a JSON-RPC error reply is printed
verbatim.
"""
import json
import signal
import subprocess
import sys
import tempfile
import tomllib


def main(argv):
    if len(argv) < 2:
        sys.exit("usage: codex_preflight.py PROJECT KEY=VALUE...")
    proj, pairs = argv[0], argv[1:]
    for pair in pairs:
        if pair.startswith("-") or "=" not in pair:
            sys.exit(f"smoke: pre-flight: argument {pair!r} is not a bare key=value pair")
    signal.alarm(120)
    requests = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"clientInfo": {"name": "chr-gate-smoke", "version": "0"}}},
        {"jsonrpc": "2.0", "method": "initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "mcpServerStatus/list", "params": {}},
        {"jsonrpc": "2.0", "id": 3, "method": "config/read", "params": {"cwd": proj}},
    ]
    cmd = ["codex", "app-server"] + [a for pair in pairs for a in ("-c", pair)]
    with tempfile.TemporaryFile("w+") as err:
        p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=err, text=True)
        try:
            p.stdin.write("".join(json.dumps(request) + "\n" for request in requests))
            p.stdin.flush()
        except BrokenPipeError:
            # The app-server already exited; its stdout ends at once and the
            # exit code and stderr are reported below.
            try:
                p.stdin.close()
            except BrokenPipeError:
                pass
        results = {}  # request id -> (message, raw line)
        for line in p.stdout:
            if line.startswith("{"):
                message = json.loads(line)
                if message.get("id") in (2, 3):
                    results[message["id"]] = (message, line.rstrip("\n"))
            if len(results) == 2:
                break
        if len(results) < 2:
            rc = p.wait()
            err.seek(0)
            received = [raw for _, raw in results.values()]
            sys.exit(f"smoke: pre-flight FAILED: codex app-server ({' '.join(cmd)}) exited with code "
                     f"{rc} before replying to requests 2 and 3 (replies received: {received}); "
                     f"its stderr:\n{err.read()}")
        p.terminate()
        p.wait()
    for rid in (2, 3):
        message, raw = results[rid]
        if "result" not in message:
            sys.exit(f"smoke: pre-flight: app-server gave no result for request {rid}: {raw}")
    servers = results[2][0]["result"]["data"]
    gate = [s for s in servers if "propose_plan" in (s["tools"] or {})]
    if not gate:
        sys.exit("smoke: pre-flight FAILED: Codex lists no chr-gate MCP server (mcpServerStatus/list: "
                 f"{[s['name'] for s in servers]}). The plugin's chr-gate server is not configured "
                 "and enabled, so no smoke session can pass; nothing was run.")
    print(f"pre-flight: MCP server {gate[0]['name']!r} (pluginId {gate[0]['pluginId']}) lists "
          f"{len(gate[0]['tools'])} tools")
    config = results[3][0]["result"]["config"]
    for pair in pairs:
        key, raw = pair.split("=", 1)
        want = tomllib.loads(f"v = {raw}")["v"]
        have = config
        for part in key.split("."):
            have = have.get(part) if isinstance(have, dict) else None
        if have != want:
            sys.exit(f"smoke: pre-flight FAILED: effective {key} is {have!r}, the fragment sets {want!r}")
        print(f"pre-flight: {key} = {have!r}")


if __name__ == "__main__":
    main(sys.argv[1:])
