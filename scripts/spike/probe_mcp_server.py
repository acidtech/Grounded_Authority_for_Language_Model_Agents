"""CHR gate spike: stdio MCP probe server (throwaway measurement tooling).

Run: uv run --no-project --with 'mcp>=2.3,<3' python probe_mcp_server.py

Exposes probe_write(claim, path, content) and probe_read(path). Both tools
only record; neither touches the filesystem beyond the log. Every raw stdin
line is teed to $CHR_SPIKE_OUT/mcp.jsonl BEFORE the SDK parses it; for
tools/call the raw text of params.arguments, its key order on the wire and
params._meta are recorded. The schema key order claim, path, content differs
from the sorted order claim, content, path, so host reordering is separable
from model ordering.
"""

import json
import os
import re
import sys
import time

import anyio
import mcp.types as types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

OUT_DIR = os.environ.get("CHR_SPIKE_OUT")
if not OUT_DIR:
    sys.exit("probe_mcp_server: CHR_SPIKE_OUT is not set")
os.makedirs(OUT_DIR, exist_ok=True)
LOG_PATH = os.path.join(OUT_DIR, "mcp.jsonl")
LABEL = os.environ.get("CHR_SPIKE_LABEL")

_ARGS_KEY = re.compile(r'"arguments"\s*:\s*')
_DECODER = json.JSONDecoder()


def _log(record: dict) -> None:
    record = {"ts": time.time(), "pid": os.getpid(), "label": LABEL, **record}
    with open(LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")


def _raw_arguments(line: str, parsed_arguments) -> str | None:
    """Return the exact substring of the wire line that encodes params.arguments."""
    for match in _ARGS_KEY.finditer(line):
        try:
            value, end = _DECODER.raw_decode(line, match.end())
        except json.JSONDecodeError:
            continue
        if value == parsed_arguments:
            return line[match.end():end]
    return None


def _record_raw_line(raw: bytes) -> None:
    text = raw.decode("utf-8", errors="replace")
    record: dict = {"kind": "rpc", "raw_line": text.rstrip("\n")}
    try:
        message = json.loads(text)
    except json.JSONDecodeError as exc:
        record["parse_error"] = str(exc)
        _log(record)
        return
    record["method"] = message.get("method") if isinstance(message, dict) else None
    record["id"] = message.get("id") if isinstance(message, dict) else None
    params = message.get("params") if isinstance(message, dict) else None
    if isinstance(params, dict):
        record["params_keys"] = list(params.keys())
        if "_meta" in params:
            record["meta"] = params["_meta"]
        if record["method"] == "tools/call":
            record["kind"] = "tools/call"
            record["tool"] = params.get("name")
            arguments = params.get("arguments")
            record["argument_keys"] = list(arguments.keys()) if isinstance(arguments, dict) else None
            record["raw_arguments"] = _raw_arguments(text, arguments)
    _log(record)


class _TeeReader:
    """Text line reader over the binary stdin that logs each raw line first."""

    def __init__(self, raw):
        self._raw = raw

    def readline(self, *_args) -> str:
        line = self._raw.readline()
        if line:
            _record_raw_line(line)
        return line.decode("utf-8", errors="replace")


TOOLS = [
    types.Tool(
        name="probe_write",
        description=(
            "Spike probe for a consequential write. The FIRST argument is a required claim: "
            "one sentence stating why this write is authorized. Records the call; writes nothing."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "claim": {"type": "string", "description": "Why this write is authorized."},
                "path": {"type": "string", "description": "Target path (recorded only)."},
                "content": {"type": "string", "description": "Content (recorded only)."},
            },
            "required": ["claim", "path", "content"],
        },
    ),
    types.Tool(
        name="probe_read",
        description="Spike probe for a read. Records the call and returns a fixed text.",
        input_schema={
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Path to read (recorded only)."}},
            "required": ["path"],
        },
    ),
]


async def _list_tools(_ctx, _params) -> types.ListToolsResult:
    return types.ListToolsResult(tools=TOOLS)


async def _call_tool(_ctx, params: types.CallToolRequestParams) -> types.CallToolResult:
    if params.name not in {tool.name for tool in TOOLS}:
        raise ValueError(f"unknown tool {params.name!r}")
    text = f"{params.name} recorded by the CHR spike probe (no file was touched)."
    return types.CallToolResult(content=[types.TextContent(type="text", text=text)])


async def main() -> None:
    _log({"kind": "start", "cwd": os.getcwd(), "argv": sys.argv, "env_names": sorted(os.environ)})
    server = Server("probe", on_list_tools=_list_tools, on_call_tool=_call_tool)
    stdin = anyio.wrap_file(_TeeReader(sys.stdin.buffer))
    async with stdio_server(stdin=stdin) as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    anyio.run(main)
