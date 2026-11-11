"""T4: the Claude Code plugin package (plugins/claude-code) agrees with the
server registry (chrgate.server.tools.TOOLS) and the T3 claude_code adapter.
Every expectation is derived from code or from the package's own manifests,
never from a hand list.

Tool-name rule (Claude Code docs, code.claude.com/docs/en/plugins/components,
'Server names, tool names, and reloads'): a tool of MCP server S declared by
plugin P is named mcp__plugin_<P>_<S>__<tool>. The hook's chr_gate_tool
recognises mcp__<CHR_GATE_SERVER>__<tool>, so hooks.json must set
CHR_GATE_SERVER to plugin_<P>_<S>.
"""

import json
import re
import shlex
from pathlib import Path

from chrgate.hooks.adapters import SERVER_ENV, builtin_write, chr_gate_tool, claude_code
from chrgate.server.tools import TOOLS

PLUGIN = Path(__file__).resolve().parents[2] / "plugins" / "claude-code"
PAYLOADS = Path(__file__).parent / "fixtures" / "payloads" / "claude_code"
JSON_FILES = (".claude-plugin/plugin.json", ".claude-plugin/marketplace.json", ".mcp.json",
              "hooks/hooks.json", "settings/chr-gate-settings.json")
INIT_STREAM = (Path(__file__).resolve().parents[1] / "docs" / "smoke-raw" / "claude-code"
               / "streams" / "1-propose.stream.jsonl")
# the deny list this package shipped before F2; the adapter must still deny each
ORIGINAL_DENY = ("Bash", "Write", "Edit", "MultiEdit", "NotebookEdit")
HOOK_ARGV = ["chrgate-hook", "--host", claude_code.HOST]
ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")


def load(rel):
    return json.loads((PLUGIN / rel).read_text())


def plugin_name():
    return load(".claude-plugin/plugin.json")["name"]


def server_name():
    servers = load(".mcp.json")["mcpServers"]
    assert len(servers) == 1, servers
    return next(iter(servers))


def plugin_server():
    """The server part of the documented plugin tool name."""
    return f"plugin_{plugin_name()}_{server_name()}"


def hook_commands():
    """(event, env assignments, argv) of every hook handler in hooks.json."""
    out = []
    for event, groups in load("hooks/hooks.json")["hooks"].items():
        for group in groups:
            for handler in group["hooks"]:
                assert handler["type"] == "command", handler
                words = shlex.split(handler["command"])
                env = {}
                while words and ASSIGNMENT.match(words[0]):
                    key, value = words.pop(0).split("=", 1)
                    env[key] = value
                out.append((event, env, words))
    assert out, "hooks.json has no hook handlers"
    return out


def adapter_events():
    """Events the adapter turns into an Event on at least one recorded payload."""
    handled = set()
    for path in sorted(PAYLOADS.glob("*.json")):
        payload = json.loads(path.read_bytes())
        if claude_code.parse(payload) is not None:
            handled.add(payload["hook_event_name"])
    assert claude_code.CONTEXT_EVENTS <= handled, "payload fixtures miss an adapter event"
    return handled


def test_every_json_file_parses():
    found = {p.relative_to(PLUGIN).as_posix() for p in PLUGIN.rglob("*.json")}
    assert set(JSON_FILES) <= found
    for rel in sorted(found):
        assert isinstance(load(rel), dict), rel
    entries = load(".claude-plugin/marketplace.json")["plugins"]
    assert [(e["name"], (PLUGIN / e["source"]).resolve()) for e in entries] == [
        (plugin_name(), PLUGIN.resolve())]


def test_hook_commands_and_events_match_adapter():
    commands = hook_commands()
    for event, env, argv in commands:
        assert argv == HOOK_ARGV, (event, argv)
        assert env == {SERVER_ENV: plugin_server()}, (event, env)
    assert {event for event, _, _ in commands} == adapter_events()


def test_server_name_matches_hook_tool_prefix(monkeypatch):
    server = load(".mcp.json")["mcpServers"][server_name()]
    assert server["command"] == "chrgate-mcp" and not server.get("args"), server
    names = {env[SERVER_ENV] for _, env, _ in hook_commands()}
    assert len(names) == 1, names
    monkeypatch.setenv(SERVER_ENV, names.pop())
    for tool in TOOLS:
        runtime = f"mcp__plugin_{plugin_name()}_{server_name()}__{tool.name}"
        assert chr_gate_tool(runtime) == tool.name, runtime
        assert chr_gate_tool(f"mcp__{server_name()}__{tool.name}") is None


def init_tools():
    """The tools list of the recorded Claude Code system init record."""
    for line in INIT_STREAM.read_text().splitlines():
        record = json.loads(line)
        if record.get("type") == "system" and record.get("subtype") == "init":
            return record["tools"]
    raise AssertionError(f"no system init record in {INIT_STREAM}")


def test_settings_deny_covers_adapter_builtin_writes():
    deny = set(load("settings/chr-gate-settings.json")["permissions"]["deny"])
    expected = {tool for tool in (*init_tools(), *ORIGINAL_DENY)
                if builtin_write(tool, claude_code.READ_ONLY_BUILTINS)}
    assert set(ORIGINAL_DENY) <= expected
    assert expected <= deny, sorted(expected - deny)


def test_skill_names_every_registry_tool_and_setup():
    text = (PLUGIN / "skills" / "chr-gate" / "SKILL.md").read_text()
    assert text.startswith("---\n") and "\ndescription: " in text.split("\n---\n", 1)[0]
    missing = [tool.name for tool in TOOLS if f"`{tool.name}`" not in text]
    assert not missing, f"SKILL.md does not document: {missing}"
    assert "chrgate-setup" in text
    assert f"mcp__{plugin_server()}__" in text
    assert "chr-gate context nonce: ctx:" in text
