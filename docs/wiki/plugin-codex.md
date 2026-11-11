# Codex plugin

> `plugins/codex/` packages chr-gate for Codex: the `chr-gate` MCP server with its environment and approval settings, one hook command on six events, a config fragment you merge yourself, and the working-rules skill.

## Key Files
- [plugin.json](../../plugins/codex/.codex-plugin/plugin.json): the plugin manifest, name `chr-gate`
- [marketplace.json](../../plugins/codex/.agents/plugins/marketplace.json): the local marketplace `chr-gate-local`, local source `./`
- [.mcp.json](../../plugins/codex/.mcp.json): `chrgate-mcp` with `env_vars` `XDG_STATE_HOME` and `CHR_GATE_PROJECT` and `default_tools_approval_mode` `approve`
- [chr-gate.toml](../../plugins/codex/config/chr-gate.toml): `sandbox_mode = "read-only"` and `features.shell_tool = false`
- [hooks.json](../../plugins/codex/hooks/hooks.json): `env CHR_GATE_SERVER=chr_gate chrgate-hook --host codex`
- [SKILL.md](../../plugins/codex/skills/chr-gate/SKILL.md): the working rules, counted in code cells

## How It Works
The tools appear as `mcp__chr_gate__<tool>`. The hook runs on UserPromptSubmit, PreToolUse, PostToolUse, Stop, SubagentStart and PostCompact; Codex has no batch event, so a batch ends at a new `turn_id`. The gate counts code cells: `open_gate` goes in a later cell than the witness read, and the consequential calls in one later cell. Codex must run with code mode on: the server refuses a call that carries no code-cell id.

Codex starts MCP servers with a minimal environment, so `.mcp.json` forwards the two state variables; the hooks inherit your shell's, so set both or neither. The `approve` mode lets the chr-gate tools run without Codex's own approval prompt; chr-gate's gate still checks every write.

Built-ins: the read-only sandbox is the backstop and `features.shell_tool = false` turns the shell off. `apply_patch` has no working switch, so the hook denies it and every other built-in except `collaborationspawn_agent` and `collaborationwait_agent`. Codex hooks read the assistant text before each tool call, so a `<cite>` tag written before the acting cell is enough.

## Try it
1. `uv tool install --editable /path/to/repo/chr-gate`, then run `chrgate-setup` in a scratch git project (never this repository).
2. `codex plugin marketplace add /path/to/repo/plugins/codex`, then `codex plugin add chr-gate@chr-gate-local`.
3. Merge `config/chr-gate.toml` into `~/.codex/config.toml`, or trust the project and put it in its `.codex/config.toml`.
4. Start `codex` in the project, trust the chr-gate hooks in `/hooks`, ask for a file change and approve the plan with exactly `approve P-xxxxxxxx`.
5. Scripted: `bash scripts/smoke/smoke_codex.sh` (see the [smoke kit](scripts-smoke.md)).

Remove it with `codex plugin remove chr-gate@chr-gate-local` and `codex plugin marketplace remove chr-gate-local`.

## Cross-References
- [chr-gate hooks](chr-gate-hooks.md), [chr-gate server](chr-gate-server.md), [Claude Code plugin](plugin-claude-code.md) and the [chr-gate README](../../chr-gate/README.md)

## Gotchas
- Codex skips plugin hooks until you trust them; until then every chr-gate call, `status` included, is refused `codex-no-ticket`.
- Codex ignores a project's `.codex/config.toml` unless that project is trusted in your user config.
- `features.unified_exec = false` is accepted but has no effect; the hook denies that tool too.
