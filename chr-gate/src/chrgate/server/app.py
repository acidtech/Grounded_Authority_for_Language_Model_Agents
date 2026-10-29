"""chrgate-mcp: the chr-gate MCP server over stdio.

Built on the low-level mcp.server.lowlevel.Server, not MCPServer: its
on_call_tool handler receives CallToolRequestParams.arguments exactly as parsed
from the JSON-RPC request (a dict in received key order), and on stdio nothing
validates them against the input schema first, so GateServer.call (tools.py)
sees the RAW arguments and checks that claim is the first key. MCPServer
would validate the arguments into a model before any tool code ran.

The project is CHR_GATE_PROJECT, else the working directory (both hosts start
the server in the project directory).
"""

import os

import anyio
import anyio.to_thread
import mcp.types as types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

from chrgate.core import paths
from chrgate.server.tools import TOOLS, GateServer

SERVER_NAME = "chr-gate"


def build(project: str | os.PathLike[str] | None = None) -> Server:
    """The low-level Server for PROJECT (default: paths.project_root())."""
    gate_server = GateServer(paths.project_root() if project is None else project)
    listed = [types.Tool(name=t.name, description=t.description, input_schema=t.input_schema)
              for t in TOOLS]

    async def list_tools(_ctx, _params) -> types.ListToolsResult:
        return types.ListToolsResult(tools=listed)

    async def call_tool(ctx, params: types.CallToolRequestParams) -> types.CallToolResult:
        client = ctx.session.client_params
        client_name = client.client_info.name if client is not None else None
        outcome = await anyio.to_thread.run_sync(
            gate_server.call, params.name, params.arguments, params.meta, client_name)
        return types.CallToolResult(content=[types.TextContent(type="text", text=outcome.text)],
                                    is_error=outcome.is_error)

    return Server(SERVER_NAME, on_list_tools=list_tools, on_call_tool=call_tool)


def main() -> None:
    server = build()

    async def serve() -> None:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())

    anyio.run(serve)


if __name__ == "__main__":
    main()
