# chr-gate live smoke results

Date: 2026-10-29. Both hosts pass all six smoke steps (6/6 PASS each).

The smoke kit is `scripts/smoke/` (T7a). The user ran each host's smoke
script in their own shell against an authenticated host CLI; the outputs
were copied verbatim into `docs/smoke-raw/` and every result below was
produced from those repo copies, not from `/tmp`.

## Host versions

Pinned from the copied version files:

| Host        | Version (copied file)                                   | Run (UTC)        |
|-------------|---------------------------------------------------------|------------------|
| Claude Code | `2.1.280 (Claude Code)` (`smoke-raw/claude-code/claude-code-version.txt`) | 2026-10-29 13:02 |
| Codex       | `codex-cli 0.162.1` (`smoke-raw/codex/codex-version.txt`) | 2026-10-29 14:09 |

## Raw copies

`docs/smoke-raw/HOST/` for HOST in `claude-code` and `codex` holds:

- `state/` - the whole smoke `XDG_STATE_HOME` tree (`chr-gate/<project id>/`
  with `events.jsonl`, `workorder.json`, `proposals.json`, `nonces.json`,
  `frames.json`, hook state files and lock files).
- `project/` - the scratch project files (`.mcp.json`, `a.txt`, `b.txt`,
  empty `.claude/` and `.codex/` directories), without its `.git`. Git does
  not track the empty directories.
- `streams/` - per turn `N-name.stream.jsonl` and `N-name.stderr.txt`, plus
  `exit-codes.txt` (all six turns exit 0 on both hosts).
- `HOST-version.txt`, `HOST-session.txt` (the host session id; the checker
  reads it beside `state/`) and `HOST-run.log` (the smoke script's own log,
  ending in its checker output against the original `/tmp` outputs).

Only the current run's outputs were copied, never the `*.prev.*` outputs of
earlier runs. Every copied file matches its `/tmp/chr-gate-smoke` source by
sha256 (28 files per host).

## Checker tables

Command, run from the repo root (read-only), once per host:

```
PYTHONDONTWRITEBYTECODE=1 uv run --frozen --no-sync --project chr-gate python -m chrgate.smoke_check --host HOST --state chr-gate/docs/smoke-raw/HOST/state --project chr-gate/docs/smoke-raw/HOST/project
```

### Claude Code (`--host claude-code`)

| Step | Result | Check | Detail |
|------|--------|-------|--------|
| 1 | PASS | proposal recorded | P-7fcda509 stored; its text names a.txt, b.txt |
| 2 | PASS | activation of exactly the proposed text | P-7fcda509 activated as wo:WO-9a382bf7.v1 with exactly the proposed text |
| 3 | PASS | wrong witness refused with 'read your work order' | open_gate refused for frame fbf48d06-09ce-4619-b4c1-bd398be0e595; the server returns 'read your work order' for this outcome |
| 4 | PASS | correct witness passed and the full text returned | status then open_gate passed for frame fbf48d06-09ce-4619-b4c1-bd398be0e595 (G-f817110ef9d5ab44); open_gate returns the full text of wo:WO-9a382bf7.v1 |
| 5 | PASS | two write_file calls in one batch, both with claims, both files right | one batch under G-f817110ef9d5ab44 took 2 calls; 2 claims accepted, 2 write_file calls; a.txt, b.txt hold the expected content |
| 6 | PASS | built-in write denied and c.txt absent | c.txt absent: the built-in write (Write) was denied by host config or the hook (the step 6 stream shows which) |

INFO lines: no refused-not-mediated or hook_error events; frame ids in
events.jsonl: fbf48d06-09ce-4619-b4c1-bd398be0e595; host session id
fbf48d06-09ce-4619-b4c1-bd398be0e595 is a frame id in events.jsonl.
RESULT: 6/6 PASS (exit 0).

Step 6 mechanism (from `streams/6-builtin-write.stream.jsonl`): host config.
The model reported that no built-in Write tool existed in the session, so it
made no tool call; the hook was not needed.

Provenance: this run predates T5b, T5c and T5d. Those tasks changed only
`plugins/codex`, the Codex smoke script and the wording of the server's
bad-argument refusal, none of which a passing Claude Code run touches, so
the run stands for the current tree.

### Codex (`--host codex`)

| Step | Result | Check | Detail |
|------|--------|-------|--------|
| 1 | PASS | proposal recorded | P-e9e94ac4 stored; its text names a.txt, b.txt |
| 2 | PASS | activation of exactly the proposed text | P-e9e94ac4 activated as wo:WO-552f0308.v1 with exactly the proposed text |
| 3 | PASS | wrong witness refused with 'read your work order' | open_gate refused for frame 01a187fd-b758-7211-acb3-e4eca75e54b4; the server returns 'read your work order' for this outcome |
| 4 | PASS | correct witness passed and the full text returned | status then open_gate passed for frame 01a187fd-b758-7211-acb3-e4eca75e54b4 (G-89981cd044164701); open_gate returns the full text of wo:WO-552f0308.v1 |
| 5 | PASS | two write_file calls in one batch, both with claims, both files right | one batch under G-89981cd044164701 took 2 calls; 2 claims accepted, 2 write_file calls; a.txt, b.txt hold the expected content |
| 6 | PASS | built-in write denied and c.txt absent | c.txt absent: the built-in write (apply_patch or shell) was denied by host config or the hook (the step 6 stream shows which) |

INFO lines: no refused-not-mediated or hook_error events; frame ids in
events.jsonl: 01a187fd-b758-7211-acb3-e4eca75e54b4; host session id
01a187fd-b758-7211-acb3-e4eca75e54b4 is a frame id in events.jsonl.
RESULT: 6/6 PASS (exit 0).

Step 6 mechanism (from `streams/6-builtin-write.stream.jsonl`): the
chr-gate PreToolUse hook denied `apply_patch` ("chr-gate: the built-in tool
apply_patch is disabled in this project; make changes through the chr-gate
MCP tools ...").

Provenance: run on the current tree, after T5b, T5c and T5d. Earlier Codex
runs failed; three fixes led to this pass. Bug fd67c7: the plugin's MCP
entry used the Agent Plugins format without `"type": "stdio"` and with
`env_vars`, so Codex failed to parse it and never listed the server; T5b
moved `plugins/codex` to the Codex-native layout. Bug 24b8a8: Codex refused
every chr-gate tool call with "MCP tool call requires approval, but approval
policy is never"; T5c set `"default_tools_approval_mode": "approve"` on the
server entry (solution f98735). Bug 5b484c: Codex code mode hides MCP tool
schemas, so the model guessed `propose_plan({plan})` and was refused; T5d
named the `text` argument in the turn 1 prompt and made the server's
bad-argument refusals list the accepted arguments (solution 73de05).

## Failures

None. No step failed on either host, so no stream excerpt is quoted.
