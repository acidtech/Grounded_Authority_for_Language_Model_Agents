# Host measurement spike kit

> `scripts/spike/` is throwaway measurement tooling: a probe MCP server and a probe hook that record what Claude Code and Codex really send, so the chr-gate design rests on observed host behaviour.

## Key Files
- [README.md](../../scripts/spike/README.md): the six questions, the pieces, the commands and the output layout
- [run_claude_probe.sh](../../scripts/spike/run_claude_probe.sh) and [run_codex_probe.sh](../../scripts/spike/run_codex_probe.sh): the runners, batch or `compact`
- [render_kit_config.py](../../scripts/spike/render_kit_config.py): renders `@KIT@` and `@UV@` in the config templates
- [probe_hook.py](../../scripts/spike/probe_hook.py): one hook for every event; logs payloads, denies built-in writes, emits `SPIKE-CTX-n`
- [probe_mcp_server.py](../../scripts/spike/probe_mcp_server.py): `probe_write(claim, path, content)` and `probe_read(path)`; tees raw stdin
- [call_ids.py](../../scripts/spike/call_ids.py): per-call identity records of each Codex run
- [transcript_summary.py](../../scripts/spike/transcript_summary.py): marker hits only, never transcript text
- [claude/settings.json](../../scripts/spike/claude/settings.json) and [codex/probe.toml](../../scripts/spike/codex/probe.toml): hook and server templates
- [spike-findings.md](../../chr-gate/docs/spike-findings.md): the verdicts

## How It Works
A runner creates a scratch git project under `/tmp/chr-gate-spike/`, renders the templates into its output folder (hosts need absolute paths, and JSON and TOML never expand `$HOME`), records the host version and runs labelled measurements: `m1_parallel`, `m2_turns`, `m3_subagent` and `m4_builtin_write`; Codex adds `m6_one_cell`, two code-mode-off runs and the tool-disable candidates `m5_candidate_a` to `d`. Outputs: `hooks.jsonl`, `mcp.jsonl`, the streams and `transcripts-summary.jsonl`, plus `call-ids.jsonl` and `features-*.txt` for Codex.

Claude Code runs use `--setting-sources project` and `--strict-mcp-config`. Codex batch runs use `--ignore-user-config`, `--strict-config` and `--dangerously-bypass-hook-trust`, with the template passed as `-c` overrides, so your Codex config is never edited.

Results: argument order is preserved on both hosts; Claude Code marks a batch with PostToolBatch and Codex calls carry a per-cell `params._meta.itemId`; subagent identity reaches the hooks; Codex hooks see assistant text in time, Claude Code hooks only at Stop (FALLBACK: the `cite` tool); built-ins can be denied on both.

## Try it
- From the repository root, batch first: `bash scripts/spike/run_claude_probe.sh` and `bash scripts/spike/run_codex_probe.sh`, then each with `compact` (let it answer, type `/compact`, then exit).
- Offline: `scripts/spike/test_probe_kit.py` runs in `scripts/unit_suite.sh`; the README's Test section runs it alone.

## Cross-References
- [smoke kit](scripts-smoke.md), [chr-gate hooks](chr-gate-hooks.md), [chr-gate server](chr-gate-server.md), [Claude Code plugin](plugin-claude-code.md) and [Codex plugin](plugin-codex.md)

## Gotchas
- Not production code; it is kept for reproducibility.
- Batch mode moves an earlier output folder to `*.prev.STAMP`; `compact` appends, so run batch first.
- Interactive Codex (`compact`) has no `--ignore-user-config`, so your own Codex config loads there.
