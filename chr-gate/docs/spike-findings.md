# CHR gate spike findings (Unit 0, part b)

Source: the user's second run of the fixed spike kit (`scripts/spike/`, task
T0a2) on 2026-10-28: both batch runs plus both compact sessions. Every citation
below points at the repo copies, byte-identical to the run outputs:

- `spike-raw/` means `chr-gate/tests/fixtures/spike-raw/`.
- `FILE:N` is line N of that file (1-based). Hook and server records carry the
  run `label` (m1_parallel, m2_turns, m3_subagent, m4_builtin_write, codex also
  m6_one_cell, m1_parallel_nocode, m2_turns_nocode, m5_candidate_a..d; compact).
- Hook records hold the raw host stdin (`stdin_raw`), the parsed `payload`, what
  the probe hook `emitted`, and `transcripts[]` summaries taken at hook time
  (line count and marker hits with record kind, never transcript text).

## Pinned versions

| Component | Version | Source |
|-----------|---------|--------|
| Claude Code | `2.1.280 (Claude Code)` | `spike-raw/claude/claude-version.txt:1` |
| Codex | `codex-cli 0.162.1` | `spike-raw/codex/codex-version.txt:1` |
| bubblewrap | 0.9.0 | `bwrap --version` on the build host |
| uv | 0.7.21 | `uv --version` on the build host |
| Python | 3.14.5 | `python3 --version` on the build host |
| MCP SDK | mcp 2.3.0 (pin `mcp>=2.3,<3`) | only mcp wheel in the uv cache the probe server ran from; pin in `scripts/spike/codex/probe.toml:9` |

Host protocol: Claude Code sends MCP `protocolVersion` 2025-11-25 with
clientInfo `claude-code` 2.1.280 (`spike-raw/claude/mcp.jsonl:2`); Codex sends
clientInfo `codex-mcp-client` 0.162.1 (`spike-raw/codex/mcp.jsonl:2`).

Codex runs with code mode on (the default, `code_mode_host` true in
`spike-raw/codex/features-baseline.txt:22`): the model's tools are
`functions.exec` plus collaboration tools, and it reaches MCP and built-in tools
from inside a JavaScript exec cell. Every Codex `tool_use_id` for an MCP or
built-in call starts with `exec-`.

## Verdict summary

| # | Measurement | Claude Code | Codex |
|---|-------------|-------------|-------|
| 1 | Argument order | CONFIRMED | CONFIRMED |
| 2 | Turn / cell grouping | CONFIRMED (PostToolBatch) | CONFIRMED with same-cell refusals (`params._meta.itemId`) |
| 3 | Subagent identity, child binding, frame identity at server | CONFIRMED | CONFIRMED |
| 4 | Assistant text visible to hooks in time | FALLBACK (cite tool) | CONFIRMED |
| 5 | Disable or deny built-ins | CONFIRMED | CONFIRMED |

No item is BREAKS-DESIGN on either host.

## (1) Argument order

Question: does the MCP server receive `probe_write` arguments in schema order
(`claim, path, content`) rather than sorted (`claim, content, path`)?

- Claude Code: every `tools/call` has `argument_keys` `["claim", "path",
  "content"]`: `spike-raw/claude/mcp.jsonl:5`, `:6` (two parallel calls), `:12`,
  `:17` (child). Verdict: CONFIRMED.
- Codex: the same order on every `probe_write` call that reached the server
  (MCP approval now `approve`): `spike-raw/codex/mcp.jsonl:5`, `:6`, `:12`,
  `:21` (child), `:31` (one-cell run). Verdict: CONFIRMED.

## (2) Turn grouping (Codex cell grouping)

Question: how does each host group one turn's parallel calls, and does a
boundary reach the gate? Updated rule for Codex (user ruling): the server
refuses `open_gate` in the same code cell as the read that delivered the
witness, and refuses every consequential call in the same code cell as the
`open_gate` that opened the gate; this needs a per-cell identifier on each call.

- Claude Code: the two parallel `probe_write` calls are followed by ONE
  PostToolBatch (`spike-raw/claude/hooks.jsonl:6`-`:9`, batch at `:10`); the
  m2 read and write each close their own batch (`:17`-`:19` and `:20`-`:22`).
  Verdict: CONFIRMED.
- Codex: there is no PostToolBatch event, and `turn_id` is per user turn, not
  per cell: the m2 read and write share turn_id `...a57adf713e37`
  (`spike-raw/codex/hooks.jsonl:11`, `:13`). The per-cell identifier is MCP
  `params._meta.itemId` (a `ctc_...` id):
  - one cell, two sequential awaited calls (m6_one_cell): read and write share
    `ctc_09dba9e9...a02cfc` (`spike-raw/codex/mcp.jsonl:30`, `:31`;
    `spike-raw/codex/call-ids.jsonl:26`, `:27`);
  - one cell, two parallel calls (m1_parallel): both share
    `ctc_049189f6...6b9f7c` (`spike-raw/codex/mcp.jsonl:5`, `:6`;
    `spike-raw/codex/call-ids.jsonl:5`, `:6`);
  - two cells in ONE turn (m2_turns, write issued after the read result was
    seen): `ctc_064645ff...e81944...` versus `ctc_064645ff...eb5db0...`
    (`spike-raw/codex/mcp.jsonl:11`, `:12`; `spike-raw/codex/call-ids.jsonl:11`,
    `:12`) under the same turn_id;
  - an exec cell is a `custom_tool_call` record in the Codex rollout: the
    child's claim marker DELEG-123 is hit on a `response_item/custom_tool_call`
    line of its transcript (`spike-raw/codex/transcripts-summary.jsonl:4`),
    which matches the `ctc_` prefix.
  Hook payloads carry NO cell id: the hook fields are `cwd, hook_event_name,
  model, permission_mode, session_id, tool_name, tool_use_id, transcript_path,
  turn_id` (plus `agent_id, agent_type` in a child)
  (`spike-raw/codex/call-ids.jsonl:1`-`:4`, `:22`-`:25`). The hook
  `tool_use_id` equals MCP `_meta.callId` on every call (for example
  `exec-0e64155e-...-e1ba7e543aca` at `spike-raw/codex/call-ids.jsonl:1` and
  `:5`), so hook records join server records exactly.
  Code mode off does NOT work as a fallback: with
  `-c features.code_mode_host=false` (`spike-raw/codex/features-code_mode_host_off.txt:22`)
  no PreToolUse fires and no `tools/call` reaches the server in
  m1_parallel_nocode and m2_turns_nocode (`spike-raw/codex/hooks.jsonl:43`-`:50`,
  `spike-raw/codex/mcp.jsonl:32`-`:39` show only start/initialize/tools/list),
  and the model reports the tool host disabled (Stop `last_assistant_message`
  at `spike-raw/codex/hooks.jsonl:45`, `:49`); Codex fails closed.
  Verdict: CONFIRMED with same-cell refusals, cell id field
  `params._meta.itemId`.

## (3) Subagent identity, child-id binding, frame identity at the MCP server

Question: do hooks see which subagent made a call, can the child id be bound
to what its parent delegated (marker DELEG-123), and does any frame identity
reach the MCP server?

- Claude Code: the parent's `Agent` PreToolUse carries the delegated text with
  DELEG-123 in `tool_input` (`spike-raw/claude/hooks.jsonl:26`); SubagentStart
  carries `agent_id` `aaff7db4297726951` and `agent_type` (`:27`); every child
  hook record carries the same `agent_id` and its own `tool_use_id` (`:28`,
  `:31`); SubagentStop adds `agent_transcript_path` (`:34`); the parent's
  `Agent` PostToolUse `tool_response.agentId` equals the child id (`:35`).
  Parent, SubagentStart and child calls share `prompt_id` (`:26`, `:27`, `:31`).
  At the server, `_meta` holds only `claudecode/toolUseId` and
  `progressToken` (`spike-raw/claude/mcp.jsonl:17`); its `toolUseId`
  `toolu_0175i3Df...` equals the child PreToolUse `tool_use_id`
  (`spike-raw/claude/hooks.jsonl:31`), which carries the `agent_id`. Initialize
  carries no frame identity (`spike-raw/claude/mcp.jsonl:2`). Verdict:
  CONFIRMED (frame identity reaches the server through the hook record keyed by
  toolUseId).
- Codex: the parent's `collaborationspawn_agent` PreToolUse carries the
  delegated message ENCRYPTED (`tool_input.message` is an opaque `gAAAA...`
  token, `spike-raw/codex/hooks.jsonl:19`) and the PostToolUse response holds
  only `{"task_name":"/root/measurement"}` (`:20`), so hooks cannot read the
  delegated text; the child does receive it (DELEG-123 on a user-message line of
  the child transcript, `spike-raw/codex/transcripts-summary.jsonl:4`).
  SubagentStart carries `agent_id` = the child thread id
  `01a18423-a7a8-...16699ffa` and `agent_type` `default` (`:21`); child hook
  records carry it (`:23`, `:25`); the parent's `session_id` stays on child
  records. At the server, `_meta` carries `threadId` (child thread),
  `sessionId` (root session), `windowId`, `itemId`, `callId` and
  `x-codex-turn-metadata` with `thread_id`, `parent_thread_id` =
  `forked_from_thread_id` = the parent thread, `subagent_kind` `thread_spawn`
  and `turn_id` (`spike-raw/codex/mcp.jsonl:21`). Main-thread calls carry
  `threadId` = `sessionId` (`spike-raw/codex/mcp.jsonl:5`). Verdict: CONFIRMED
  (frame identity and the parent link arrive natively in `_meta`).

## (4) Assistant text visible to hooks in time

Question: is the assistant text written before a tool call (m1 writes
`CITE-NONCE-7` first) readable by PreToolUse, and on Stop?

- Claude Code: at PreToolUse of both writes and at the PostToolBatch after
  them, the transcript (32 lines) holds CITE-NONCE-7 only on non-assistant
  records (user prompt line 5 and kind-less bookkeeping lines 1, 18, 31); no
  `assistant` hit (`spike-raw/claude/hooks.jsonl:6`, `:8`, `:10`). The
  assistant hit appears only at Stop (line 33,
  `assistant/message/assistant`, `spike-raw/claude/hooks.jsonl:11`), and Stop
  is not an additionalContext event. Verdict: FALLBACK (pre-approved: Claude
  Code uses the `cite(nonces)` tool).
- Codex: at the first PreToolUse the transcript already holds the assistant
  record with CITE-NONCE-7 (line 14, `response_item/message/assistant`,
  `spike-raw/codex/hooks.jsonl:3`); it is still there at the second call (`:5`)
  and at Stop (`:7`). Verdict: CONFIRMED.

## (5) Disabling or denying built-ins

Question: can the gate stop built-in writes (Claude `Write`; Codex
`apply_patch` and the shell)?

- Claude Code: the probe's PreToolUse deny on `Write` is honoured: the record
  `emitted` `permissionDecision: "deny"` (`spike-raw/claude/hooks.jsonl:40`)
  and no PostToolUse follows, only the PostToolBatch (`:41`). Verdict:
  CONFIRMED (deny path).
- Codex: PreToolUse deny is honoured for both `apply_patch` and `Bash`
  (`spike-raw/codex/hooks.jsonl:31`, `:32`; the model quotes "Command blocked
  by PreToolUse hook" at `:33`). Disabling: `features.shell_tool=false`
  (candidates A-D, `scripts/spike/codex/candidate_*.toml`) turns `shell_tool`
  off (`spike-raw/codex/features-candidate_a_features.txt:126`) and no shell
  call is attempted in any m5 run. Candidates A-D also set
  `features.unified_exec = false` (`scripts/spike/codex/candidate_*.toml`), but
  `spike-raw/codex/features-candidate_a_features.txt:152` still lists
  `unified_exec` as `stable` `true`, so `unified_exec` cannot be disabled in
  0.162.1 and the PreToolUse hook denies the built-in shell calls.
  `apply_patch` has no working feature switch
  (`apply_patch_freeform` is `removed`, `spike-raw/codex/features-baseline.txt:5`)
  and is still offered under A, B and C, where the hook denies it
  (`spike-raw/codex/hooks.jsonl:53`, `:58`, `:63`); candidate D (a derived
  `model_catalog_json` without built-ins) removes both, with no PreToolUse at
  all (`spike-raw/codex/hooks.jsonl:66`-`:69`). Verdict: CONFIRMED (shell off
  by `features.shell_tool=false`, `apply_patch` denied by PreToolUse; full
  removal needs the derived model catalog).

## Layout notes (for T3, T4, T5)

- Plugin manifest paths: NOT measured. The kit loaded hooks and the server
  through `--settings`/`--mcp-config` (Claude, `scripts/spike/claude/`) and
  `-c` overrides from `scripts/spike/codex/probe.toml` (Codex), not through
  plugin manifests. T4/T5 must take manifest paths from host documentation and
  prove them in the live smoke run.
- MCP server launch: cwd is the project directory on both hosts
  (`spike-raw/claude/mcp.jsonl:1`, `spike-raw/codex/mcp.jsonl:1`). Claude Code
  passes its full environment, including `CLAUDE_PROJECT_DIR`, `CLAUDECODE`
  and `CLAUDE_CODE_SESSION_ID` (`spike-raw/claude/mcp.jsonl:1`). Codex passes a
  minimal environment: HOME, LANG, LOGNAME, PATH, SHELL, TERM, USER, uv's own
  variables and only the variables named in the server's `env`/`env_vars`
  (`spike-raw/codex/mcp.jsonl:1`); the plugin must list every variable it needs.
- Hook launch: cwd is the project directory on both hosts
  (`spike-raw/claude/hooks.jsonl:1`, `spike-raw/codex/hooks.jsonl:1`). Claude
  hooks get `CLAUDE_PROJECT_DIR`, `CLAUDE_ENV_FILE`, `CLAUDE_PID`
  (`spike-raw/claude/hooks.jsonl:1`); Codex hooks inherit the launching shell's
  environment and get no Codex project variable (`spike-raw/codex/hooks.jsonl:1`;
  its CLAUDE_* names come from the user's shell, not from Codex).
- Events whose additionalContext reaches the model (the emitted
  `SPIKE-CTX-n` number is found in the transcript summaries):
  Claude Code: SessionStart (startup and compact), UserPromptSubmit,
  PreToolUse, PostToolUse, PostToolBatch, SubagentStart, all as `attachment`
  records (`spike-raw/claude/transcripts-summary.jsonl:1`-`:6`; for example
  SPIKE-CTX-1 emitted at `spike-raw/claude/hooks.jsonl:1`). Codex:
  SessionStart, UserPromptSubmit, PreToolUse, PostToolUse, SubagentStart, as
  `response_item/message/developer` records
  (`spike-raw/codex/transcripts-summary.jsonl:1`-`:13`); output emitted on
  Stop, SubagentStop, PreCompact and PostCompact was never found
  (`spike-raw/codex/hooks.jsonl:7`, `:25`, `:75`, `:76`).
- Compact: Claude fires PreCompact, a SubagentStop for the summarizer,
  SessionStart `source: compact` and PostCompact
  (`spike-raw/claude/hooks.jsonl:67`-`:70`). Codex fires PreCompact and
  PostCompact with `trigger: manual` and a new turn_id, and no SessionStart
  after compaction (`spike-raw/codex/hooks.jsonl:75`-`:77`).
- PreToolUse deny, both hosts: stdout JSON
  `{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision":
  "deny", "permissionDecisionReason": "<text>"}}`
  (`spike-raw/claude/hooks.jsonl:40`, `spike-raw/codex/hooks.jsonl:31`). Codex
  shows the model "Command blocked by PreToolUse hook: <reason>"
  (`spike-raw/codex/hooks.jsonl:33`).
- Codex hook tool names: MCP tools arrive as `mcp__<server>__<tool>`
  (`spike-raw/codex/hooks.jsonl:3`), collaboration tools as
  `collaborationspawn_agent` / `collaborationwait_agent` (`:19`, `:22`), built-ins
  as `apply_patch` and `Bash` (`:31`, `:32`).

## Mechanism choices for later tasks

- Gate turn boundary, Claude Code (T3): the gate consumed by a consequential
  batch closes at that batch's PostToolBatch hook.
- Gate cell boundary, Codex (T2b server, T3 hooks): the cell id is MCP
  `params._meta.itemId`. The server refuses `open_gate` when its itemId equals
  the itemId of the read_work_order/status call that delivered the witness, and
  refuses every consequential call whose itemId equals the itemId of the
  `open_gate` that opened the gate. The first consequential call after
  `open_gate` binds the gate to its itemId; later consequential calls with that
  itemId (parallel calls in the same cell) pass; the first call with any other
  itemId after that closes the gate. Backstops: Codex Stop and the next
  UserPromptSubmit (new `turn_id`). A Codex call without `_meta.itemId` is
  refused (fail closed); code mode off is not an option, Codex fails closed
  there.
- Call attribution: Claude Code `_meta["claudecode/toolUseId"]` equals the
  PreToolUse `tool_use_id`; Codex `_meta.callId` equals the PreToolUse
  `tool_use_id`, and Codex also sends `_meta.itemId`, `threadId`, `sessionId`
  and `x-codex-turn-metadata` (`parent_thread_id`, `turn_id`). The default
  ticket keyed by a hash of tool name plus arguments is no longer needed on
  either host. Claude Code still needs a ticket for frame identity, keyed by
  `tool_use_id`: PreToolUse writes `{session_id, agent_id, agent_type,
  transcript_path}` under the tool_use_id and the server consumes it by
  `claudecode/toolUseId`. Codex needs no ticket: the server takes the frame
  from `_meta` (`threadId`, `parent_thread_id`, `itemId`).
- Assistant text for citations: Claude Code uses the `cite(nonces)` tool
  (FALLBACK, item 4). Codex reads `transcript_path` at PreToolUse and takes the
  `response_item/message/assistant` records of the current turn.
- Child binding: `delegate(claim, work_order)` registers the work order on the
  server under the caller's frame and returns a delegation id that the parent
  puts into the child's launch prompt; the child's first read of its work order
  presents that id, and the server binds it to the child's frame id. Claude
  Code: child frame = `agent_id` from the PreToolUse ticket of that call
  (`SubagentStart.agent_id`, `Agent` PostToolUse `tool_response.agentId`
  confirms it later). Codex: child frame = `_meta.threadId`, and the server
  checks that `x-codex-turn-metadata.parent_thread_id` equals the delegating
  frame. Hooks cannot see the Codex delegated text (encrypted spawn message),
  so no Codex binding may rely on reading the spawn input.

## Payload fixtures

`chr-gate/tests/fixtures/payloads/<host>/EVENT__case.json` holds the host's raw
hook stdin (`stdin_raw`, which parses equal to `payload`) of the named
`spike-raw/<host>/hooks.jsonl` line, byte for byte.

| Claude Code fixture | Source line |
|---------------------|-------------|
| SessionStart__startup.json | `spike-raw/claude/hooks.jsonl:1` |
| UserPromptSubmit__plain.json | `:2` |
| PreToolUse__builtin_toolsearch.json | `:3` |
| PreToolUse__mcp_probe_write.json | `:6` |
| PostToolUse__mcp_probe_write.json | `:7` |
| PostToolBatch__two_parallel.json | `:10` |
| Stop__plain.json | `:11` |
| PreToolUse__mcp_probe_read.json | `:17` |
| PreToolUse__agent_launch.json | `:26` |
| SubagentStart__child.json | `:27` |
| PreToolUse__child_mcp_probe_write.json | `:31` |
| SubagentStop__child.json | `:34` |
| PostToolUse__agent_launch.json | `:35` |
| PreToolUse__builtin_write.json | `:40` |
| PostToolBatch__after_denied_write.json | `:41` |
| PreToolUse__builtin_bash.json | `:45` |
| PreCompact__manual.json | `:67` |
| SubagentStop__compact_summarizer.json | `:68` |
| SessionStart__compact.json | `:69` |
| PostCompact__manual.json | `:70` |

| Codex fixture | Source line |
|---------------|-------------|
| SessionStart__startup.json | `spike-raw/codex/hooks.jsonl:1` |
| UserPromptSubmit__plain.json | `:2` |
| PreToolUse__mcp_probe_write.json | `:3` |
| PostToolUse__mcp_probe_write.json | `:4` |
| Stop__plain.json | `:7` |
| SessionEnd__plain.json | `:8` |
| PreToolUse__mcp_probe_read.json | `:11` |
| PreToolUse__spawn_agent.json | `:19` |
| PostToolUse__spawn_agent.json | `:20` |
| SubagentStart__child.json | `:21` |
| PreToolUse__child_mcp_probe_write.json | `:23` |
| SubagentStop__child.json | `:25` |
| PreToolUse__builtin_apply_patch.json | `:31` |
| PreToolUse__builtin_bash.json | `:32` |
| PreToolUse__one_cell_probe_read.json | `:37` |
| PreToolUse__one_cell_probe_write.json | `:39` |
| Stop__code_mode_off.json | `:45` |
| PreCompact__manual.json | `:75` |
| PostCompact__manual.json | `:76` |
