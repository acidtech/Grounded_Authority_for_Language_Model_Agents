# chr-gate server

> `chrgate-mcp` is the stdio MCP server, the only effect path and the only witness issuer; `chrgate-setup` prepares a project for it.

## Key Files
- [app.py](../../chr-gate/src/chrgate/server/app.py): a low-level MCP `Server`, so tool code sees the raw arguments in order
- [tools.py](../../chr-gate/src/chrgate/server/tools.py): the `TOOLS` registry, `GateServer.call` and the handlers
- [tickets.py](../../chr-gate/src/chrgate/server/tickets.py): frame attribution from hook tickets and `_meta`
- [sandbox.py](../../chr-gate/src/chrgate/server/sandbox.py): the bubblewrap profiles and protected paths
- [setup.py](../../chr-gate/src/chrgate/server/setup.py): `chrgate-setup [--project PATH]`
- [pyproject.toml](../../chr-gate/pyproject.toml): the console scripts `chrgate-mcp`, `chrgate-setup` and `chrgate-hook`

## How It Works
Not consequential: `status` (alias `read_work_order`), `open_gate`, `cite`, `propose_plan`, `research_shell`. Consequential: `write_file`, `edit_file`, `mutate_shell`, `delegate`, `testify`, each with `claim` first. Each call is attributed first: Claude Code by the ticket under `_meta["claudecode/toolUseId"]`, Codex by the ticket under `_meta.callId` with frame `threadId` and turn key `itemId`. In the chrgate source tree every call is refused `self-hosting`.

A consequential call must be mediated (ticketed), carry a valid claim, find the protected paths present and its target inside the project and unprotected, then pass `take_gate`; only then does the effect run. Every result ends with a fresh `ctx:` nonce and adds one `events.jsonl` line.

`status` returns the reference, the witness and the work order text; a subagent's first `status` passes `delegation_id`. On Codex `open_gate` in the read's own cell is refused. `research_shell`: project and state root read-only, private `/tmp`, no network. `mutate_shell`: network and host `/tmp`, but `.git`, `.claude/`, `.codex/`, `.mcp.json`, the masked root names and git-config paths read-only. Both shells keep only `PATH`, `HOME`, `LANG`, `TERM` and `USER` and stop after 120 s.

## Try it
Install with `uv tool install --editable /path/to/repo/chr-gate`, then run `chrgate-setup` in a test project (it prints what it created or `nothing to create`). The plugins start the server from [Claude Code .mcp.json](../../plugins/claude-code/.mcp.json) and [Codex .mcp.json](../../plugins/codex/.mcp.json); tools appear as `mcp__plugin_chr-gate_chr-gate__<tool>` and `mcp__chr_gate__<tool>`. `scripts/unit_suite.sh` runs the tests (it needs `bwrap`).

## Cross-References
- [chr-gate core](chr-gate-core.md), [chr-gate hooks](chr-gate-hooks.md) and the [chr-gate README](../../chr-gate/README.md)

## Gotchas
- Before `chrgate-setup`, the write tools refuse `protected-path-missing`; setup never creates `.git/config`.
- Codex must run in code mode, else `codex-no-item-id`.
- A restart forgets the witness, so the agent calls `status` again.
- Linux with bubblewrap only. Agents never stage or commit; the user runs git.
