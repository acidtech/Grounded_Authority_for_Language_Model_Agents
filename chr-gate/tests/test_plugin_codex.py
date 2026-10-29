"""T5: the Codex plugin package (plugins/codex) agrees with the server
registry (chrgate.server.tools.TOOLS), the T3 codex adapter and the spike's
built-in measurements. Every expectation is derived from code, the recorded
payload fixtures, the spike candidate configs or the package's own manifests,
never from a hand list.

Tool-name rule (openai/codex rust-v0.162.1): a plugin's MCP servers keep the
key they have under mcpServers (codex-mcp/src/plugin_config.rs), and the
model-visible name, which hooks receive as tool_name, is 'mcp__' +
sanitize(server) + '__' + sanitize(tool) (codex-mcp/src/tools.rs), where
sanitize_responses_api_tool_name (codex-mcp/src/mcp/mod.rs) maps every
character that is not ASCII alphanumeric or '_' to '_'. The hook's
chr_gate_tool recognises mcp__<CHR_GATE_SERVER>__<tool>, so hooks.json must set
CHR_GATE_SERVER to sanitize(server).
"""

import json
import re
import shlex
import tomllib
from pathlib import Path

from chrgate.core.paths import PROJECT_ENV
from chrgate.hooks.adapters import SERVER_ENV, chr_gate_tool, codex
from chrgate.server.tools import TOOLS

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "plugins" / "codex"
PAYLOADS = Path(__file__).parent / "fixtures" / "payloads" / "codex"
CANDIDATES = ROOT / "scripts" / "spike" / "codex"
SPIKE_RAW = Path(__file__).parent / "fixtures" / "spike-raw" / "codex"
MANIFEST = ".codex-plugin/plugin.json"
MCP_CONFIG = ".mcp.json"
JSON_FILES = (MANIFEST, MCP_CONFIG, "hooks/hooks.json", ".agents/plugins/marketplace.json")
FRAGMENT = "config/chr-gate.toml"
HOOK_ARGV = ["chrgate-hook", "--host", codex.HOST]
ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")


def load(rel):
    return json.loads((PLUGIN / rel).read_text())


def sanitize(name):
    """codex sanitize_responses_api_tool_name."""
    return re.sub(r"[^A-Za-z0-9_]", "_", name) or "_"


def plugin_name():
    return load(MANIFEST)["name"]


def server_name():
    servers = load(MCP_CONFIG)["mcpServers"]
    assert len(servers) == 1, servers
    return next(iter(servers))


def hook_commands():
    """(event, env assignments, argv) of every hook handler in hooks.json."""
    out = []
    for event, groups in load("hooks/hooks.json")["hooks"].items():
        for group in groups:
            assert "matcher" not in group, (event, group)
            for handler in group["hooks"]:
                assert handler["type"] == "command", handler
                words = shlex.split(handler["command"])
                assert words[0] == "env", handler
                words.pop(0)
                env = {}
                while words and ASSIGNMENT.match(words[0]):
                    key, value = words.pop(0).split("=", 1)
                    env[key] = value
                out.append((event, env, words))
    assert out, "hooks.json has no hook handlers"
    return out


def adapter_events():
    """Events the adapter turns into an Event on at least one recorded payload."""
    handled, parsed = set(), []
    for path in sorted(PAYLOADS.glob("*.json")):
        payload = json.loads(path.read_bytes())
        event = codex.parse(payload)
        if event is not None:
            handled.add(payload["hook_event_name"])
            parsed.append(event)
    assert any(e.ends_batch for e in parsed), "no batch-end backstop among the fixtures"
    assert any(e.builtin_write for e in parsed), "no built-in write among the fixtures"
    return handled


def recorded_features(candidate):
    """name -> value of `codex features list` recorded under CANDIDATE."""
    path = SPIKE_RAW / f"features-{candidate.stem}.txt"
    rows = [line.split() for line in path.read_text().splitlines() if line.strip()]
    return {row[0]: row[-1] for row in rows}


def spike_disable_settings():
    """sandbox_mode and the [features] switches findings item 5 established:
    the sandbox_mode the read-only candidate sets, and every feature switch that
    all candidates (scripts/spike/codex/candidate_*.toml) set to false AND that
    the recorded feature list of every candidate shows in effect."""
    paths = sorted(CANDIDATES.glob("candidate_*.toml"))
    docs = [tomllib.loads(p.read_text()) for p in paths]
    assert len(docs) >= 2, paths
    shared = set.intersection(*(set(doc["features"].items()) for doc in docs))
    assert all(value is False for _, value in shared), shared
    effective = {key: value for key, value in shared
                 if all(recorded_features(p)[key] == "false" for p in paths)}
    assert effective, shared
    modes = {doc["sandbox_mode"] for doc in docs if "sandbox_mode" in doc}
    assert len(modes) == 1, modes
    return modes.pop(), effective


def test_every_manifest_parses():
    found = {p.relative_to(PLUGIN).as_posix() for p in PLUGIN.rglob("*.json")}
    assert set(JSON_FILES) <= found
    for rel in sorted(found):
        assert isinstance(load(rel), dict), rel
    assert isinstance(tomllib.loads((PLUGIN / FRAGMENT).read_text()), dict)
    entries = load(".agents/plugins/marketplace.json")["plugins"]
    assert [(e["name"], e["source"]["source"], (PLUGIN / e["source"]["path"]).resolve())
            for e in entries] == [(plugin_name(), "local", PLUGIN.resolve())]


def test_codex_plugin_mcp_layout():
    """Codex-native layout (T5b, bug fd67c7). In codex-cli 0.162.1 a root
    plugin.json with the Agent Plugins $schema makes Codex parse the MCP file in
    that format, which skips our entry (no "type", has env_vars) and forwards no
    parent environment; .codex-plugin/plugin.json selects the legacy parser
    (McpServerConfig, env_vars accepted), with .mcp.json as its default file."""
    assert (PLUGIN / MANIFEST).is_file() and (PLUGIN / MCP_CONFIG).is_file()
    assert not (PLUGIN / "plugin.json").exists() and not (PLUGIN / "mcp.json").exists()
    for rel in (MANIFEST, MCP_CONFIG):
        assert "$schema" not in load(rel), rel
    assert load(MCP_CONFIG)["mcpServers"][server_name()]["env_vars"], server_name()


def test_hook_commands_and_events_match_adapter():
    commands = hook_commands()
    for event, env, argv in commands:
        assert argv == HOOK_ARGV, (event, argv)
        assert env == {SERVER_ENV: sanitize(server_name())}, (event, env)
    assert {event for event, _, _ in commands} == adapter_events()


def test_server_name_matches_hook_tool_prefix(monkeypatch):
    server = load(MCP_CONFIG)["mcpServers"][server_name()]
    assert server["command"] == "chrgate-mcp" and not server.get("args"), server
    assert server["env_vars"] == ["XDG_STATE_HOME", PROJECT_ENV], server
    names = {env[SERVER_ENV] for _, env, _ in hook_commands()}
    assert len(names) == 1, names
    monkeypatch.setenv(SERVER_ENV, names.pop())
    for tool in TOOLS:
        runtime = f"mcp__{sanitize(server_name())}__{sanitize(tool.name)}"
        assert chr_gate_tool(runtime) == tool.name, runtime
        if sanitize(server_name()) != server_name():
            assert chr_gate_tool(f"mcp__{server_name()}__{tool.name}") is None
        assert chr_gate_tool(f"mcp__plugin_{plugin_name()}_{server_name()}__{tool.name}") is None


def test_codex_mcp_tools_preapproved():
    """Codex runs chr-gate tools under approval_policy never (bug 24b8a8)."""
    server = load(MCP_CONFIG)["mcpServers"][server_name()]
    assert server.get("default_tools_approval_mode") == "approve", server


def test_config_fragment_sets_read_only_and_disables_builtins():
    fragment = tomllib.loads((PLUGIN / FRAGMENT).read_text())
    mode, features = spike_disable_settings()
    assert fragment["sandbox_mode"] == mode == "read-only"
    for key, value in features.items():
        assert fragment["features"][key] is value, key


def test_skill_names_every_registry_tool_and_setup():
    text = (PLUGIN / "skills" / "chr-gate" / "SKILL.md").read_text()
    assert text.startswith("---\n") and "\ndescription: " in text.split("\n---\n", 1)[0]
    missing = [tool.name for tool in TOOLS if f"`{tool.name}`" not in text]
    assert not missing, f"SKILL.md does not document: {missing}"
    assert "chrgate-setup" in text
    assert f"mcp__{sanitize(server_name())}__" in text
    assert "chr-gate context nonce: ctx:" in text
