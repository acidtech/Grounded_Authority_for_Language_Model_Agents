# chr-gate hooks

> `chrgate-hook --host claude-code|codex` is one shared hook: it denies unlisted built-ins, writes the frame tickets the server needs, ends tool batches, handles approval prompts, checks citations and resurfaces the work order after compaction.

## Key Files
- [engine.py](../../chr-gate/src/chrgate/hooks/engine.py): all hook behaviour on neutral `Event`s
- [cli.py](../../chr-gate/src/chrgate/hooks/cli.py): the entry point; payload on stdin, decision on stdout, fail-closed errors
- [transcript.py](../../chr-gate/src/chrgate/hooks/transcript.py): new assistant text from a Codex rollout
- [adapters/\_\_init\_\_.py](../../chr-gate/src/chrgate/hooks/adapters/__init__.py): `builtin_write`, `chr_gate_tool`, `render`
- [adapters/claude_code.py](../../chr-gate/src/chrgate/hooks/adapters/claude_code.py) and [adapters/codex.py](../../chr-gate/src/chrgate/hooks/adapters/codex.py): payload parsing and `READ_ONLY_BUILTINS`

## How It Works
The adapter turns a payload into an `Event` (frame: the subagent `agent_id`, else `session_id`); `engine.handle` returns a deny or additionalContext, printed as `hookSpecificOutput`, or nothing.

`PreToolUse` denies every built-in (a name not starting `mcp__`) that the allowlist does not name and logs a `builtin_denied` event. A consequential chr-gate call is denied early when a subagent has no delegation or no gate is current; the hook never consumes the gate. Otherwise the call joins the frame's open batch and gets a ticket under its `tool_use_id`. `PostToolUse` adds `chr-gate context nonce: ctx:...` to the result.

A batch ends at `PostToolBatch` (Claude Code), at a new `turn_id` (Codex), and at `Stop` or `UserPromptSubmit`. A batch that held a consequential call or used the gate closes it; any other Claude Code batch counts one turn. A whole prompt of `approve P-xxxxxxxx` activates that plan and `revoke wo:ID.vN` revokes the active order; a mere mention gets a notice, and a subagent never approves. Compaction starts a new epoch and resurfaces the work order text, never a witness. Citation warnings are queued for the next event that takes additionalContext; Claude Code text is checked only at `Stop`, so `cite(nonces)` is its in-turn channel.

## Try it
Run `scripts/unit_suite.sh`. Live: run `chrgate-setup` in a test project, then `claude --plugin-dir /path/to/repo/plugins/claude-code --settings /path/to/repo/plugins/claude-code/settings/chr-gate-settings.json`, or `codex plugin marketplace add /path/to/repo/plugins/codex` and `codex plugin add chr-gate@chr-gate-local`, then trust the hooks in `/hooks`. Wiring: [Claude Code hooks.json](../../plugins/claude-code/hooks/hooks.json), [Codex hooks.json](../../plugins/codex/hooks/hooks.json).

## Cross-References
- [chr-gate core](chr-gate-core.md), [chr-gate server](chr-gate-server.md) and the [chr-gate README](../../chr-gate/README.md)

## Gotchas
- Hook errors fail closed for consequential tools and unlisted built-ins, open otherwise.
- Without the hooks every chr-gate call is refused `claude-no-ticket` or `codex-no-ticket`.
- `CHR_GATE_SERVER` must match the tool prefix: `plugin_chr-gate_chr-gate` (Claude Code) or `chr_gate` (Codex).
- In the chrgate source tree itself every `PreToolUse` is denied.
