# CHR gate spike kit (Unit 0, part a)

Throwaway measurement tooling. It measures six design-critical host behaviours
on Claude Code and Codex so the chr-gate core is built on observed facts. Nothing
here is production code; it is kept for reproducibility.

## The six questions

| # | Question | Measured by |
|---|----------|-------------|
| 1 | Is MCP argument order preserved end to end (schema order `claim, path, content` vs sorted `claim, content, path`)? | m1, m2, m3 (codex also m6 and the `_nocode` runs): `mcp.jsonl` `argument_keys` and `raw_arguments` |
| 2 | How does each host group one turn's parallel calls (payload fields or events marking a turn or batch boundary)? Claude Code PostToolBatch is the comparison. | m1 (two parallel `probe_write`), m2 (`probe_read` then `probe_write` in separate turns): `hooks.jsonl` (`turn_id`, `tool_use_id`, PostToolBatch), streams |
| 3 | Subagent identity in hook payloads (`agent_id`/`agent_type`), whether a child id can be bound to what its parent delegated (marker `DELEG-123` in the parent's launch-tool input), and whether any frame identity reaches the MCP server (`_meta`, initialize `clientInfo`) | m3: `hooks.jsonl` SubagentStart/PreToolUse records, `mcp.jsonl` `meta` and initialize `raw_line` |
| 4 | Is the assistant text written before a tool call visible to PreToolUse in time for a citation check, and on Stop? | m1 writes `CITE-NONCE-7` before its tool calls: `hooks.jsonl` `transcripts[].markers["CITE-NONCE-7"]` hits (line number and record kind, for example `assistant/assistant`; the user prompt also holds the marker, so look for an assistant-kind hit) in summaries taken at hook time, Stop `last_assistant_message` |
| 5 | How to disable Codex built-in tools (shell, apply_patch)? | m4 (deny path, tool list) and codex m5 candidates A-D: model's tool list, PreToolUse records, `features-*.txt` |
| 6 | Codex only: does each tool call carry a per-code-cell identifier (hook payload field or MCP `params._meta` key), so the gate server can refuse `open_gate` in the same code cell as the witness read and any consequential call in the same cell as `open_gate`? If not, does `-c features.code_mode_host=false` (code mode off, the fallback) keep m1 and m2 working? | m6_one_cell (`probe_read` then `probe_write` awaited in ONE exec cell), m1_parallel_nocode, m2_turns_nocode: `call-ids.jsonl` (per call: every hook payload field except `tool_input`/`tool_response`, and the full `_meta`; a per-cell id is a field shared by the two m6 calls that would differ across cells), streams, `features-code_mode_host_off.txt` |

Supporting layout notes (not design points): `mcp.jsonl` start records give the
server cwd and env var names; `hooks.jsonl` records give each hook's cwd and env
var names (for example `CLAUDE_PROJECT_DIR`); the `emitted` field plus the stream
show which events accept `additionalContext` (look for `SPIKE-CTX-n` numbers in
the transcript summaries' `spike_ctx` and in the streams).

No transcript text is stored anywhere: hook records and
`transcripts-summary.jsonl` hold only path, exists, size, line_count and marker
hits. The raw hook stdin and parsed payload are kept as they are.

## Pieces

- `probe_mcp_server.py`: stdio MCP server on `mcp>=2.3,<3` exposing
  `probe_write(claim, path, content)` (all required) and `probe_read(path)`. It
  tees every raw stdin line to `$CHR_SPIKE_OUT/mcp.jsonl` before the SDK parses
  it; `tools/call` records carry `raw_arguments`, `argument_keys` (wire order) and
  `meta` (`params._meta`). The tools record only; they never touch files.
- `probe_hook.py`: one hook for every event on both hosts. Appends raw stdin,
  parsed payload, event, env var names and a transcript summary per transcript
  path in the payload (`transcripts[]`, from `transcript_summary.summarize()`)
  to `$CHR_SPIKE_OUT/hooks.jsonl`. Denies PreToolUse for Claude `Write` and Codex
  `apply_patch`/`Bash`/`shell`/`exec_command`/`Edit`/`Write`; emits
  `SPIKE-CTX-n` additionalContext on the events each host documents as
  accepting it (Claude Code: PreToolUse, PostToolUse, PostToolBatch,
  UserPromptSubmit, SessionStart, SubagentStart; Codex: SessionStart,
  PreToolUse, PostToolUse, UserPromptSubmit, SubagentStart, SubagentStop, Stop,
  PreCompact, PostCompact).
- `transcript_summary.py`: the one transcript summary implementation.
  `summarize(path)` returns `path`, `exists`, `size`, `line_count`, `markers`
  (hits for `DELEG-123` and `CITE-NONCE-7`) and `spike_ctx` (hits per
  `SPIKE-CTX-n` number); a hit is `{"line": n, "kind": "<type/role labels>"}`,
  never line text. Its CLI (`python3 transcript_summary.py OUT_DIR`), called by
  both runners, writes `transcripts-summary.jsonl`: one summary per distinct
  transcript path named in `hooks.jsonl`, with the run `labels` that named it.
- `call_ids.py`: called by the codex runner after every run with the line
  counts of `hooks.jsonl` and `mcp.jsonl` taken before it; appends that run's
  tool calls to `call-ids.jsonl`. Each record has `label` (the runner's run
  label), `record_label` (the label in the raw record) and `source`: `hook`
  records (PreToolUse, PermissionRequest, PostToolUse) carry `event`,
  `tool_name` and `fields` (every payload field and value except `tool_input`
  and `tool_response`); `mcp` records carry `tool_name`, `rpc_id`,
  `params_keys` and `meta` (the full `params._meta`, null when absent).
- `claude/settings.json`, `claude/mcp.json`: hooks for PreToolUse, PostToolUse,
  PostToolBatch, UserPromptSubmit, Stop, SubagentStart, SubagentStop,
  PreCompact, PostCompact, SessionStart; the probe server as `probe`.
- `codex/probe.toml`: the equivalent hooks (plus PermissionRequest and
  SessionEnd) and `mcp_servers.probe` for codex 0.162.1, with
  `default_tools_approval_mode = "approve"` (see below) and
  `env_vars = ["CHR_SPIKE_LABEL"]` so the server's records carry the run label
  (the first run's `mcp.jsonl` had `label: null` throughout). The runner turns each
  second-level table into one `-c key=<inline TOML>` override; `~/.codex` is
  never edited. `codex/candidate_*.toml`: tool-disable candidates for
  measurement 5 (A: `features.shell_tool/unified_exec=false`; B: A plus
  `experimental_use_unified_exec_tool=false`, `features.apply_patch_freeform=false`;
  C: A plus `sandbox_mode="read-only"`; D: A plus a `model_catalog_json` the
  runner derives from `codex debug models` with `shell_type="disabled"` and no
  `apply_patch_tool_type`).
- `run_claude_probe.sh`, `run_codex_probe.sh`: create the scratch git project,
  record the host version, run the measurements, summarize the transcripts named
  in hook payloads with `transcript_summary.py` (no copies), and print where the
  outputs went. The codex runner adds m6_one_cell and the code-mode-off runs
  m1_parallel_nocode and m2_turns_nocode (`-c features.code_mode_host=false`,
  with `codex features list` under that override saved to
  `features-code_mode_host_off.txt`), and runs `call_ids.py` after every run.

## Codex MCP tool approval

The first run denied every probe call with "MCP tool call requires approval, but
approval policy is never". `codex/probe.toml` now sets
`mcp_servers.probe.default_tools_approval_mode = "approve"`. Verified on
2026-10-28 for the installed codex-cli 0.162.1:

- Installed binary: `codex -c 'mcp_servers.probe={command="true",
  default_tools_approval_mode="approve"}' mcp list` loads; the value `"bogus"`
  fails with "unknown variant `bogus`, expected one of `auto`, `prompt`,
  `writes`, `approve` in `mcp_servers.probe.default_tools_approval_mode`". The
  kit's generated `-c mcp_servers.probe={...}` override also loads
  (`codex mcp get probe --json`). The binary contains the denial string.
- Official docs (developers.openai.com/codex/config-reference, now served from
  learn.chatgpt.com/docs/config-file/config-reference):
  `mcp_servers.<id>.default_tools_approval_mode` and
  `mcp_servers.<id>.tools.<tool>.approval_mode`, values
  `auto | prompt | writes | approve`.
- Codex source (openai/codex main, `codex-rs/core/src/mcp_tool_call.rs`,
  `requires_mcp_tool_approval_for_mode`): `Approve => false` (no approval
  needed); `Auto` defers to the tool annotations; under `approval_policy =
  never` a call that needs approval is denied with the message above.

T0b confirms it in the stream: codex `tools/call` records appear in `mcp.jsonl`
and no stream item carries the denial message.

## Exact user commands

The sandbox has no authenticated hosts, so the user runs these in their own `!`
shell, batch mode first:

    ! bash /home/acidtech/Ground_Authority_for_Language_Model_Agents/scripts/spike/run_claude_probe.sh
    ! bash /home/acidtech/Ground_Authority_for_Language_Model_Agents/scripts/spike/run_codex_probe.sh
    ! bash /home/acidtech/Ground_Authority_for_Language_Model_Agents/scripts/spike/run_claude_probe.sh compact
    ! bash /home/acidtech/Ground_Authority_for_Language_Model_Agents/scripts/spike/run_codex_probe.sh compact

The `compact` mode starts an interactive session with the same configuration:
let it answer its one-line prompt, type `/compact`, wait, then exit (`/exit` in
Claude Code, `/quit` in Codex). That captures PreCompact, PostCompact and
SessionStart(compact). Batch mode moves an existing output folder aside to
`<folder>.prev.<UTC stamp>`; compact mode appends to it, so run batch first.

## Output layout

- `/tmp/chr-gate-spike/claude/` and `/tmp/chr-gate-spike/codex/`:
  `<host>-version.txt`, `exit-codes.txt`, `<label>.stream.jsonl`,
  `<label>.stderr.txt` (codex also `<label>.last-message.txt`), `hooks.jsonl`,
  `mcp.jsonl`, `ctx_counter`, `transcripts-summary.jsonl` (no `transcripts/`
  copy any more). Codex adds `call-ids.jsonl`, `features-*.txt` (including
  `features-code_mode_host_off.txt`), `overrides-*.txt` (the exact `-c`
  overrides used), `catalog-original.json` and `catalog-no-builtins.json`.
- Labels: `m1_parallel`, `m2_turns`, `m3_subagent`, `m4_builtin_write`; codex
  adds `m6_one_cell`, `m1_parallel_nocode`, `m2_turns_nocode`,
  `m5_candidate_a_features`, `m5_candidate_b_legacy_keys`,
  `m5_candidate_c_readonly`, `m5_candidate_d_catalog` (in that order);
  interactive runs use `compact`. Every hook and server record carries `label`
  (from `CHR_SPIKE_LABEL`) when the host passes the runner's environment
  through; `call-ids.jsonl` records always carry the runner's label.
- Older output folders (`<folder>.prev.<stamp>`) from runs before this change
  may still hold transcript text in `hooks.jsonl` and full copies under
  `transcripts/`; delete them once they are no longer needed.
- Scratch projects: `/tmp/chr-gate-spike/claude-proj`, `/tmp/chr-gate-spike/codex-proj`.

## Isolation from the user's own configuration

- Claude Code runs use `--setting-sources project` (the scratch project has no
  `.claude/`), so user and local settings, including global hooks from other
  harnesses and enabled plugins, do not load; the login is not a setting and
  stays. `--strict-mcp-config` loads only the probe server. Residual risk: the
  user's `~/.claude/CLAUDE.md` memory still loads, and managed settings would
  still apply.
- Codex batch runs use `codex exec --ignore-user-config` (auth still comes from
  `CODEX_HOME`) with `--strict-config`, so unknown override keys fail loudly, and
  `--dangerously-bypass-hook-trust` so the kit's hooks run without a persisted
  trust entry. Residual risk: interactive `codex` (compact mode) has no
  `--ignore-user-config`, so `~/.codex/config.toml` also loads there (it held no
  hooks when the kit was written), and `~/.codex/AGENTS.md` loads in every run.

## Test

    PYTHONDONTWRITEBYTECODE=1 uv run --no-project --with pytest --with 'mcp>=2.3,<3' pytest -p no:cacheprovider scripts/spike/test_probe_kit.py
