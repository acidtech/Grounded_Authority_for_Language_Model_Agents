# Claude Code plugin

> `plugins/claude-code/` packages chr-gate for Claude Code: the `chr-gate` MCP server, one hook command on seven events, a deny list for the built-ins that write, and the working-rules skill.

## Key Files
- [plugin.json](../../plugins/claude-code/.claude-plugin/plugin.json): the plugin manifest, name `chr-gate`
- [marketplace.json](../../plugins/claude-code/.claude-plugin/marketplace.json): the local marketplace `chr-gate-local`, source `./`
- [.mcp.json](../../plugins/claude-code/.mcp.json): starts `chrgate-mcp` as the server `chr-gate`
- [hooks.json](../../plugins/claude-code/hooks/hooks.json): `chrgate-hook --host claude-code` with `CHR_GATE_SERVER=plugin_chr-gate_chr-gate`
- [chr-gate-settings.json](../../plugins/claude-code/settings/chr-gate-settings.json): the built-in deny list
- [SKILL.md](../../plugins/claude-code/skills/chr-gate/SKILL.md): the working rules the agent reads

## How It Works
The server's tools appear as `mcp__plugin_chr-gate_chr-gate__<tool>`, and every hook command sets `CHR_GATE_SERVER=plugin_chr-gate_chr-gate` so the hook recognises them. The hook runs on SessionStart, UserPromptSubmit, PreToolUse, PostToolUse, PostToolBatch, Stop and SubagentStart; PostToolBatch ends a batch of parallel calls.

Two layers keep built-ins out. `chr-gate-settings.json` denies Bash, Write, Edit, MultiEdit, NotebookEdit, CronCreate, CronDelete, EnterWorktree, ExitWorktree, RemoteTrigger, ScheduleWakeup, SendMessage and Workflow as host config. The hook denies every other built-in outside its allowlist: Read, Glob, Grep, ToolSearch, WebFetch, WebSearch, Skill, Task, Agent, ListAgents, TaskStop, ReportFindings and CronList.

The skill teaches the gate sequence: `status`, `open_gate` in its own turn, then one later turn of consequential calls, each with its `claim` as the first argument. Claude Code hooks see assistant text only at Stop, so before a consequential turn the agent also passes its context nonces to `cite`.

## Try it
1. `uv tool install --editable /path/to/repo/chr-gate`, then run `chrgate-setup` in a scratch git project (never this repository).
2. From that project: `claude --plugin-dir /path/to/repo/plugins/claude-code --settings /path/to/repo/plugins/claude-code/settings/chr-gate-settings.json`.
3. Ask for a file change, read the plan text in the `propose_plan` call, reply with exactly `approve P-xxxxxxxx`, and watch `status`, `open_gate` and `write_file`.
4. Scripted: `bash scripts/smoke/smoke_claude_code.sh` (see the [smoke kit](scripts-smoke.md)).

To keep it installed: `/plugin marketplace add /path/to/repo/plugins/claude-code`, then `/plugin install chr-gate@chr-gate-local`, and copy the deny list into your own settings.

## Cross-References
- [chr-gate hooks](chr-gate-hooks.md), [chr-gate server](chr-gate-server.md), [Codex plugin](plugin-codex.md) and the [chr-gate README](../../chr-gate/README.md)

## Gotchas
- A plugin cannot set permissions: without `--settings`, or the deny list copied into your settings, only the hook denies the built-ins.
- If the plugin hooks do not run, every chr-gate call is refused `claude-no-ticket`.
- The smoke run used `--plugin-dir`, not the marketplace install.
