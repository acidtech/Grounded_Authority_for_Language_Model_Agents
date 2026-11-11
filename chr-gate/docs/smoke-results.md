# chr-gate live smoke results

Date: 2026-11-11. Both hosts pass all six smoke steps (6/6 PASS each).

The smoke kit is `scripts/smoke/` (T7a). The user ran each host's smoke
script in their own shell against an authenticated host CLI; the outputs
were copied verbatim into `docs/smoke-raw/` and every result below was
produced from those repo copies, not from `/tmp`.

## Host versions

Pinned from the copied version files:

| Host        | Version (copied file)                                   | Run (UTC)        |
|-------------|---------------------------------------------------------|------------------|
| Claude Code | `2.1.280 (Claude Code)` (`smoke-raw/claude-code/claude-code-version.txt`) | 2026-11-11 16:39-16:40 |
| Codex       | `codex-cli 0.162.1` (`smoke-raw/codex/codex-version.txt`) | 2026-11-11 16:40-16:42 |

## Raw copies

`docs/smoke-raw/HOST/` for HOST in `claude-code` and `codex` holds:

- `state/` - the whole smoke `XDG_STATE_HOME` tree (`chr-gate/<project id>/`
  with `events.jsonl`, `workorder.json`, `proposals.json`, `nonces.json`,
  `frames.json`, `tickets.json`, hook state files and lock files; Codex also
  `hook_transcripts.json` and the sandbox's empty `placeholder-file` and
  `placeholder-dir/`).
- `project/` - the scratch project files (`.mcp.json`, `a.txt`, `b.txt`,
  empty `.claude/` and `.codex/` directories), without its `.git`. Git does
  not track the empty directories.
- `streams/` - per turn `N-name.stream.jsonl` and `N-name.stderr.txt`, plus
  `exit-codes.txt` (all six turns exit 0 on both hosts).
- `HOST-version.txt` and `HOST-session.txt` (the host session id; the checker
  reads it beside `state/`).

No `HOST-run.log` is recorded for this run: the smoke script prints its log
to the terminal and writes no log file, and the user's terminal output was
not saved. The 2026-10-29 run logs were moved out of the tree with the rest
of that run's copies replaced. The checker tables below come from the repo
copies.

Only the current run's outputs were copied, never the `*.prev.*` outputs of
the earlier run of the same day (see Failures). Every copied file and
directory matches its `/tmp/chr-gate-smoke` source (`diff -r`, `.git`
excluded).

## Checker tables

Command, run from `chr-gate/` (read-only), for both hosts:

```
for h in claude-code codex; do uv run --frozen --no-sync python -m chrgate.smoke_check --host $h --state docs/smoke-raw/$h/state --project docs/smoke-raw/$h/project; echo "exit=$?"; done
```

### Claude Code (`--host claude-code`)

| Step | Result | Check | Detail |
|------|--------|-------|--------|
| 1 | PASS | proposal recorded | P-66a07961 stored; its text names a.txt, b.txt |
| 2 | PASS | activation of exactly the proposed text | P-66a07961 activated as wo:WO-1e371406.v1 with exactly the proposed text |
| 3 | PASS | wrong witness refused with 'read your work order' | open_gate refused for frame 9602edd5-4633-49f8-81f0-3aa9d4f83e4d; the server returns 'read your work order' for this outcome |
| 4 | PASS | correct witness passed and the full text returned | status then open_gate passed for frame 9602edd5-4633-49f8-81f0-3aa9d4f83e4d (G-08a0dcfc221b5b37); open_gate returns the full text of wo:WO-1e371406.v1 |
| 5 | PASS | two write_file calls in one batch, both with claims, both files right | one batch under G-08a0dcfc221b5b37 took 2 calls; 2 claims accepted, 2 write_file calls; a.txt, b.txt hold the expected content |
| 6 | PASS | built-in write denied and c.txt absent | c.txt absent: the built-in write (Write) was denied by host config or the hook (the step 6 stream shows which) |

INFO lines: no refused-claude-no-ticket, refused-not-mediated or hook_error
events; frame ids in events.jsonl: 9602edd5-4633-49f8-81f0-3aa9d4f83e4d; host
session id 9602edd5-4633-49f8-81f0-3aa9d4f83e4d is a frame id in
events.jsonl. RESULT: 6/6 PASS (exit 0).

Step 6 mechanism (from `streams/6-builtin-write.stream.jsonl`): host config.
The model reported that the built-in Write tool was neither loaded nor in the
deferred-tool list, so it made no tool call; the hook was not needed.

Other observations: in turns 1, 3, 4 and 5 the model first called the
built-in `ToolSearch` to load the chr-gate tool schemas (a read-only lookup
the settings allow); turn 2 made no tool call and replied `OK`.
`tickets.json` is empty (`{}`).

### Codex (`--host codex`)

| Step | Result | Check | Detail |
|------|--------|-------|--------|
| 1 | PASS | proposal recorded | P-b3fc1b6e stored; its text names a.txt, b.txt |
| 2 | PASS | activation of exactly the proposed text | P-b3fc1b6e activated as wo:WO-65283601.v1 with exactly the proposed text |
| 3 | PASS | wrong witness refused with 'read your work order' | open_gate refused for frame 01a1cb7b-b1cb-7183-a761-141d1f6efcbd; the server returns 'read your work order' for this outcome |
| 4 | PASS | correct witness passed and the full text returned | status then open_gate passed for frame 01a1cb7b-b1cb-7183-a761-141d1f6efcbd (G-9032f6c40643058c); open_gate returns the full text of wo:WO-65283601.v1 |
| 5 | PASS | two write_file calls in one batch, both with claims, both files right | one batch under G-9032f6c40643058c took 2 calls; 2 claims accepted, 2 write_file calls; a.txt, b.txt hold the expected content |
| 6 | PASS | built-in write denied and c.txt absent | c.txt absent: the built-in write (apply_patch or shell) was denied by host config or the hook (the step 6 stream shows which) |

INFO lines: no refused-claude-no-ticket, refused-not-mediated or hook_error
events; one builtin_denied line:
`2026-11-11T16:42:05.852811+00:00 built-in apply_patch denied by the chr-gate hook (builtin_denied); frame=01a1cb7b-b1cb-7183-a761-141d1f6efcbd`;
frame ids in events.jsonl: 01a1cb7b-b1cb-7183-a761-141d1f6efcbd; host
session id 01a1cb7b-b1cb-7183-a761-141d1f6efcbd is a frame id in
events.jsonl. RESULT: 6/6 PASS (exit 0).

Step 6 mechanism (from `streams/6-builtin-write.stream.jsonl` and
`6-builtin-write.stderr.txt`): the chr-gate PreToolUse hook denied
`apply_patch` ("chr-gate: the built-in tool apply_patch is disabled in this
project; make changes through the chr-gate MCP tools ...").

Built-ins the Codex hooks denied in this run (from the builtin_denied events
and the Codex streams):

| Built-in | Denials | Verdict |
|----------|---------|---------|
| `apply_patch` | 1 (step 6) | stays denied: it writes files |

No other built-in was denied; every other tool call in the Codex streams is
a chr-gate MCP tool (`propose_plan`, `read_work_order`, `open_gate`,
`research_shell`, `status`, `write_file`), so the Codex allowlist is
unchanged.

Other observations: in turn 2 the model called the chr-gate
`read_work_order` tool (prompted by the hook's activation notice) before
replying `OK`, despite the turn 1 request to make no tool call in that turn;
the call is read-only and step 3 still passed. In turn 3 it called
`research_shell` to read the chr-gate skill after the refusal. The events
hold no refused-codex-no-ticket outcome, and `tickets.json` is empty (`{}`).

## Provenance

Both runs were made on the tree after T9 (commit 8a800b3,
2026-11-11 16:38:31 UTC); every copied stream and version file is dated
after it.

Turn 2 is exactly the approval phrase `approve P-...` on both hosts (T1's F1
fix, commit 828be52). The stored approval proves it: `workorder.json`
records `prompt_sha256` 9b131cfc...a9eb211f for Claude Code and
84860dcc...2687f691 for Codex, the sha256 of exactly `approve P-66a07961`
and `approve P-b3fc1b6e`, and the Claude Code step 2 stream shows the hook's
reply "chr-gate: the user approved P-66a07961; work order wo:WO-1e371406.v1
is now active."

F1 also dropped the step 2 line "make no tool call in this turn". Turn 1's
prompt now ends "My next message will be the approval phrase alone; that is
smoke step 2: make no tool call in that turn, reply OK."
(`scripts/smoke/smoke_claude_code.sh`, `scripts/smoke/smoke_codex.sh`).

## Failures

None in the recorded run.

The first run of the same day (outputs `*.prev.20261111T163929Z` for Claude
Code and `*.prev.20261111T164041Z` for Codex, not copied) failed step 3 on
both hosts (5/6 PASS): with turn 2 reduced to the bare approval phrase and
no instruction against tool calls, both models executed the work order
inside turn 2. With the user's
approval the no-tool-call instruction moved into turn 1's prompt, as quoted
above, and the re-run recorded here passed.
