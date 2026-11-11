# chr-gate: an example CHR gate for Claude Code and Codex

chr-gate puts the gate protocol of
[Grounded Authority for Language-Model Agents](../Grounded_Authority_for_Language_Model_Agents_C33.md)
(C33 Appendix A) in front of two coding-agent hosts, Claude Code and Codex.
Every action with an external effect goes through one MCP server,
`chrgate-mcp`, and needs an approved work order, an open gate and a written
claim. The host hooks (`chrgate-hook`) deny every host built-in tool that is
not on a short read-only allowlist, carry frame identity to the server, check
citations and resurface the work order after compaction.

## What this is and is not

This is an example with stated limits (see "Stated limits" below). It shows
how C33's gate can sit in front of hosts that already exist, using only their
plugin systems, their hooks and an MCP server, and it is checked against those
hosts: the host behaviour it relies on is measured in
[docs/spike-findings.md](docs/spike-findings.md), and the live runs are
recorded in [docs/smoke-results.md](docs/smoke-results.md).

It is not a hardened product. The hooks are not a full boundary, the shell
protections need Linux with bubblewrap, and several C33 mechanisms are reduced
here (each reduction is listed under "Stated limits"; the C33 mechanisms not
built at all are listed there under L11). It is not a remake of
any other harness: it is built from C33 and the implementation guide
[Implementing a Grounded Authority Harness](../Implementing_a_Grounded_Authority_Harness.md)
only.

## Layout

- `chr-gate/` (this folder): the shared core, one uv Python project with the
  package `chrgate` in src layout.
  - `src/chrgate/core/`: the library: work orders and proposals, the witness
    issuer, the gate, claims, citations and context nonces, delegation,
    testimony, the event log, the state store and the gate timing config.
  - `src/chrgate/server/`: the MCP server (`chrgate-mcp`), its tool registry,
    frame attribution tickets, the bubblewrap profiles
    ([sandbox.py](src/chrgate/server/sandbox.py)) and `chrgate-setup`.
  - `src/chrgate/hooks/`: the shared hook (`chrgate-hook`) and one adapter per
    host.
  - `src/chrgate/smoke_check.py`: the checker of the live smoke runs.
  - `tests/`: the pytest suite, with host hook payload fixtures and the raw
    spike copies under `tests/fixtures/`.
  - `docs/`: [spike-findings.md](docs/spike-findings.md),
    [smoke-results.md](docs/smoke-results.md) and the raw smoke copies in
    [smoke-raw/](docs/smoke-raw/).
- [`plugins/claude-code/`](../plugins/claude-code/): the Claude Code plugin:
  `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`,
  `.mcp.json`, `hooks/hooks.json`, `skills/chr-gate/SKILL.md` and
  [settings/chr-gate-settings.json](../plugins/claude-code/settings/chr-gate-settings.json)
  (the host-config denials of built-in tools).
- [`plugins/codex/`](../plugins/codex/): the Codex plugin in the Codex-native
  layout: [.codex-plugin/plugin.json](../plugins/codex/.codex-plugin/plugin.json),
  [.mcp.json](../plugins/codex/.mcp.json), `hooks/hooks.json`,
  `skills/chr-gate/SKILL.md`, `.agents/plugins/marketplace.json` and the
  config fragment [config/chr-gate.toml](../plugins/codex/config/chr-gate.toml).
- `scripts/`: [unit_suite.sh](../scripts/unit_suite.sh) (the test suite
  wrapper), [spike/](../scripts/spike/README.md) (the host measurement kit)
  and [smoke/](../scripts/smoke/README.md) (the live smoke kit).

The plugins call the console scripts `chrgate-mcp` and `chrgate-hook` by
name. You install the core once, so a host's plugin cache copy never needs a
path back into this repository.

## Requirements

Linux with bubblewrap (`bwrap`, built and tested with 0.9.0), git, Python 3.12
or newer (tested on 3.12 and 3.14) and uv (0.7.21). The MCP SDK is pinned
`mcp>=2.3,<3`. The measured hosts are Claude Code 2.1.280 and codex-cli
0.162.1; other host versions are untested.

## Install and try

### 1. The core, once

    uv tool install --editable /path/to/repo/chr-gate

This puts `chrgate-mcp`, `chrgate-hook` and `chrgate-setup` on your PATH.

chr-gate refuses to govern its own source tree (C33 3.10). When the `chrgate`
package that the server or the hook runs from lies inside the governed
project, the server refuses every call with code `self-hosting`, before any
frame attribution and so `status` included, and the hook denies every
`PreToolUse`, both with "chr-gate cannot govern its own source tree (C33
3.10); install a non-editable copy or use another project". With the
`--editable` install above, never use this repository itself as the governed
project.

### 2. Each project: chrgate-setup

Run it from your own shell in the project root (or pass `--project PATH`):

    cd /path/to/project
    chrgate-setup

Why it exists: `mutate_shell` holds the hosts' configuration paths in the
project read-only (`.claude/`, `.codex/`, `.mcp.json` and, when `.git` is a
directory, `.git/hooks` and `.git/config`) by binding each one read-only in
the sandbox. A path that does not exist cannot be bound, and the agent could
create it, for example a `.mcp.json` the host loads in the next session. So
the protected host-config paths must exist to be held read-only, and the
write tools fail closed until setup has run: `write_file`, `edit_file` and
`mutate_shell` refuse, name the missing paths and ask you to run
`chrgate-setup`. The chr-gate tools never create these paths themselves.

`chrgate-setup` creates only the missing paths (empty `.claude/` and
`.codex/` folders, a `.mcp.json` holding `{"mcpServers": {}}`, and
`.git/hooks` when `.git` is a directory), never changes an existing one,
prints what it created (or `nothing to create`) and exits non-zero while a
required path is still missing. It never creates `.git/config`: a missing one
needs a git repair.

### 3a. Claude Code

To try it for one session (the route the live smoke run used):

    cd /path/to/project
    claude --plugin-dir /path/to/repo/plugins/claude-code \
           --settings /path/to/repo/plugins/claude-code/settings/chr-gate-settings.json

`--plugin-dir` loads the plugin: the `chr-gate` MCP server, the hooks and the
working-rules skill. `--settings` denies the built-in tools that write, act
later or send (`Bash`, `Write`, `Edit`, `MultiEdit`, `NotebookEdit`,
`CronCreate`, `CronDelete`, `EnterWorktree`, `ExitWorktree`, `RemoteTrigger`,
`ScheduleWakeup`, `SendMessage` and `Workflow`) as host config, and the
chr-gate hook denies every other built-in outside its allowlist (see
"Built-in tools" below). The server's tools appear as
`mcp__plugin_chr-gate_chr-gate__<tool>`.

To keep it installed, the plugin folder is also a local marketplace
(`chr-gate-local`): `/plugin marketplace add /path/to/repo/plugins/claude-code`,
then `/plugin install chr-gate@chr-gate-local`. The smoke run did not use this
route. A plugin cannot set permissions, so copy the deny list of
`chr-gate-settings.json` into your own settings (for example
`~/.claude/settings.json`, or the project's `.claude/settings.json` edited
from your own shell).

### 3b. Codex

Install the plugin from its local marketplace:

    codex plugin marketplace add /path/to/repo/plugins/codex
    codex plugin add chr-gate@chr-gate-local

and remove it with:

    codex plugin remove chr-gate@chr-gate-local
    codex plugin marketplace remove chr-gate-local

Then, from your own shell:

- Config fragment. A plugin cannot set the keys in
  [config/chr-gate.toml](../plugins/codex/config/chr-gate.toml)
  (`sandbox_mode = "read-only"`, `features.shell_tool = false`). Codex ignores
  a project's `.codex/config.toml` unless that project is trusted in your user
  Codex config, so merge `plugins/codex/config/chr-gate.toml` into
  `~/.codex/config.toml`, or trust the project and put the fragment in its
  `.codex/config.toml`.
- Hook trust. Codex skips plugin hooks until you trust their current hash.
  Start `codex` interactively and trust the chr-gate hooks in Codex's hook
  review (`/hooks`). Normal use trusts the plugin hooks this way;
  `--dangerously-bypass-hook-trust` is used only by the smoke script. Without
  the hooks every chr-gate tool call, `status` included, is refused
  `codex-no-ticket`: the chr-gate `PreToolUse` hook writes the ticket the
  server needs under the call's `_meta.callId`. Trust the hooks (`/hooks`) or
  run Codex with them enabled. Claude Code fails the same way when its plugin
  hooks do not run: every chr-gate call is refused `claude-no-ticket`.
- State root. Codex starts MCP servers with a minimal environment, so
  [.mcp.json](../plugins/codex/.mcp.json) forwards `XDG_STATE_HOME` and
  `CHR_GATE_PROJECT` to `chrgate-mcp` (`env_vars`); the hooks inherit your
  shell's environment. Set both or neither, so server and hooks share one
  state root.

The server's tools appear in Codex as `mcp__chr_gate__<tool>`. See "Codex
0.162.1 notes" below for the layout, approval and code-mode details.

### 4. A first session

1. Ask for a change. The agent calls `status`, finds no work order, writes a
   plan and calls `propose_plan(text)`, which returns a plan id and the phrase
   `approve P-xxxxxxxx`. Before you approve, read the plan text in the
   `propose_plan` tool call itself (its `text` argument in the host's view of
   the call): approval activates exactly that stored text, and the agent's
   summary in chat is not it (L5).
2. Reply with exactly that phrase and nothing else. The `UserPromptSubmit`
   hook activates the proposal only when your whole prompt, stripped of
   surrounding whitespace, is `approve P-xxxxxxxx`; a prompt that only
   mentions the phrase activates nothing and gets a notice saying so. The
   hook activates exactly that proposal's text as the work order `wo:ID.v1`;
   only your own prompt can approve it, and a subagent never approves.
3. The agent reads its work order with `status`, calls
   `open_gate(witness)` in a later turn (Codex: a later code cell), then acts
   in a later turn with `write_file(claim, path, content)`, `edit_file`,
   `mutate_shell`, `delegate` or `testify`, each call carrying its own claim
   that cites `wo:ID.v1`.

To end the active work order, reply with exactly `revoke wo:ID.vN`, naming
its active version (the same whole-prompt rule; a prompt that only mentions
the phrase revokes nothing). Revocation clears the witness and gate of every
frame and ends every delegation under it; no work order is active until the
next `approve P-...`, which continues at the revoked version plus one. A
reference that is not the active one revokes nothing, and the notice names
the active reference.

The live smoke kit ([scripts/smoke/](../scripts/smoke/README.md)) runs this
sequence on each host.

## How the gate works here

### Tools

| Tool | Consequential | Purpose |
|------|---------------|---------|
| `status` (alias `read_work_order`) | no | the work order reference `wo:ID.vN`, its full text and the frame's witness |
| `open_gate(witness)` | no | open the gate; a pass returns the full work order text |
| `cite(nonces)` | no | fallback channel for citations |
| `propose_plan(text)` | no | propose a work order for the user to approve |
| `research_shell(command)` | no | read-only shell in the project, no network |
| `write_file(claim, path, content)` | yes | write a project file |
| `edit_file(claim, path, old, new)` | yes | replace one occurrence in a project file |
| `mutate_shell(claim, command)` | yes | shell that may change the project, network allowed |
| `delegate(claim, work_order)` | yes | hand a work order to a subagent that will write |
| `testify(claim, text)` | yes | record consequential testimony |

Consequential means an external effect. Reads and normal replies never need
the gate.

### Witness lifecycle

chr-gate follows C33's default witness lifecycle. The MCP server is the only
witness issuer; the hooks never mint, hold or see a plaintext witness.
`status` returns the frame's witness (`wit:` plus 128 random bits). Repeat
work-order reads in one frame epoch return the same witness (Invariant 2,
C33 3.2): the witness is bound to the work order id, its version, the frame
and the epoch; the server keeps the plaintext in its process memory for that
binding, and the state on disk holds only its sha256 and the binding.

`open_gate` neither rotates nor consumes the witness, so the same witness
opens each separately opened gate in its epoch. A trusted work-order re-read
(`status` or `read_work_order`) cancels a pending open gate (C33 Appendix A),
while other research (`research_shell`, `cite`, the hosts' read-only tools)
keeps the gate open.

The witness ends when the epoch ends: a new work-order version or another
authority change, or compaction (C33 2.4). After compaction the hook
resurfaces only the work-order text, with the instruction to read the work
order again, and the agent reads its new witness from the server. Per-action
rotation (C33 Appendix F) is not used.

### The gate

`open_gate(witness)` returns "read your work order" on any failure and changes
no state; a pass returns the full work order text. Research may follow
without using the gate up. The next consequential turn uses it: the first
consequential call takes the gate for its turn, parallel calls of that same
turn share it (each with its own claim), and a later turn needs a new
`open_gate`. A consequential call in the turn that opened the gate is refused,
and so is `open_gate` in a turn that already made a consequential call
(`denied-acted-turn`): call it in the next turn.

The turn boundary differs per host (spike-findings item 2). Claude Code:
one tool batch, closed by the `PostToolBatch` hook. Codex: one code cell,
identified by the MCP `_meta.itemId`; `open_gate` must run in a later cell
than the read that delivered the witness, and consequential calls in a later
cell than `open_gate`. On both hosts `Stop` and the next user prompt
(`UserPromptSubmit`) end an open batch as backstops. On Claude Code they
matter when `PostToolBatch` does not arrive; whether Claude Code fires
`PostToolBatch` when the user interrupts a batch or a tool call errors is not
measured (M1). A batch end closes the gate only when the batch held a
consequential call or used the gate, so an unused open gate survives the
user's next prompt.

A pending gate expires after `gate_lifetime_seconds` (default 900) or
`max_intervening_turns` completed research turns (default 3; the opening turn
and the acting turn are not counted). Both live in
`config.json` in the state root (`$XDG_STATE_HOME/chr-gate/<project key>/`,
default `~/.local/state`), which the agent's sandboxes hold read-only. Expiry
ends the gate, never the witness.

### Citations

Every chr-gate result ends with `chr-gate context nonce: ctx:...`. The agent
writes the nonces it relies on in a `<cite>ctx:... ctx:...</cite>` tag in its
assistant text. Only invalid citations produce output, a
`chr-citation-warning` that rides the next hook event that accepts
additionalContext; when every citation is valid there is no output at all.
The `cite(nonces)` tool is only a fallback, and on Claude Code it is the
in-turn channel (spike item 4, see "Stated limits").

### Built-in tools

The chr-gate `PreToolUse` hook denies every host built-in tool (a tool whose
name does not start with `mcp__`) unless the host adapter's read-only
allowlist names it, so a built-in nobody has classified, or one a host update
adds, is denied too.

- Claude Code allowlist (`claude_code.READ_ONLY_BUILTINS`): `Read`, `Glob`,
  `Grep`, `ToolSearch`, `WebFetch`, `WebSearch`, `Skill`, `Task`, `Agent`,
  `ListAgents`, `TaskStop`, `ReportFindings` and `CronList`.
- Codex allowlist (`codex.READ_ONLY_BUILTINS`): `collaborationspawn_agent`
  and `collaborationwait_agent`.

Read-only-looking tools outside these lists are denied as well, for example
`LSP`, `AskUserQuestion`, `EnterPlanMode` and `ExitPlanMode`, `TaskCreate`,
`TaskList` and `TodoWrite`, `ListMcpResourcesTool`, `Monitor` and
`PowerShell`. Each denial is logged to `events.jsonl` as a `builtin_denied`
event (outcome `denied`, ref the host tool, with the frame), and the smoke
checker prints one INFO line per such event. Tools of other MCP servers are
not built-ins and are not denied (L1).

### Mechanism map

| Mechanism | chr-gate | C33 | Guide stage |
|-----------|----------|-----|-------------|
| Witnesses and nonces | `wit:` witness from `status`; `ctx:` nonce on every result | C33 2.3 Identifiers; C33 Appendix D | Stage 1 (nonces), Stage 2 (the bound witness) |
| Epochs and compaction | compaction starts a new epoch for the frame and ends witness and gate | C33 2.4 Context epochs; C33 B.1 | Stage 2 (start_new_epoch) |
| Consequential tools | the five tools above; built-ins denied unless allowlisted | C33 2.5 Consequential actions; C33 3.7 Effect policy | Above the gate: Effect policy |
| Citation warning | `<cite>` tags checked, warnings only on invalid ones | C33 3.0 The shared context-provenance validator | Stage 1: Shared context-provenance validator and minimal warning profile |
| `open_gate` and work-order binding | witness bound to work order version, frame and epoch | C33 3.2 The four invariants; C33 3.3 The gate; C33 Appendix A | Stage 2: Authority gate with `plan_auth` and the bound witness |
| Resurfacing | `open_gate` pass and post-compaction hook return the work-order text | C33 3.4 Resurfacing | Stage 3: Resurfacing |
| Claims | required first argument citing `wo:ID.vN` | C33 3.5 Claims | Stage 4: Action-specific claims (without the generation receipt) |
| Parallel turns | one gate covers one turn's parallel calls | C33 3.8 Parallel batches | Above the gate: Parallel batches |
| Propose and approve | `propose_plan`, then the user's `approve P-...` | C33 3.9 Approval and change requests | Above the gate: Approval and change requests |
| Delegation | `delegate(claim, work_order)`; child -> caller -> user | frame model of C33 Appendix B | none (the guide's stages do not cover delegation) |

Delegation follows a recursive assigner model. A subagent that will write gets
its task through `delegate(claim, work_order)` under the caller's open gate
and authority: the caller is its assigner and writes the task, and nobody
else can change it once issued (the delegation record is written once, and
the state root is read-only in both shells). The returned delegation id goes
into the subagent's launch prompt, and the child presents it on its first
`status` call, which binds it to the child's frame. The server stores only
the id's sha256, and the child must run in its assigner's session (Claude
Code) or under its assigner's thread (Codex). Every `status`, `open_gate` and
compaction text of a delegated frame delivers each inherited work order
verbatim before the task, the user-approved order first, then the rule that
they govern, then the task:

    --- inherited bounds: wo:WO-xxxxxxxx.v2 (approved by the user) ---
    <its exact text>
    Your task is limited by every inherited work order above. Where they
    disagree, the inherited order governs: stop and report to your assigner.
    --- work order text (your task, written by your assigner) ---
    <the task>

An inherited order written by an intermediate assigner is labelled
`(written by its assigner)`. The inherited orders win over the task. A child
whose task is wrong, or conflicts with an inherited order, stops and reports
to its assigner; it cannot change its task, and a changed task is a new
delegation to a new subagent. A revision or revocation of a work order above
ends the delegation. Authority runs child -> assigner -> user. A read-only
subagent needs no delegation.

### Protected paths and git

`research_shell` runs in bubblewrap with the project and the state root
read-only, no network, a private `/tmp` (a tmpfs discarded after each call)
and an empty `/run`; a project or state root under `/tmp` stays visible.
`mutate_shell` runs with the project writable except the paths below, with
the network shared, the host's `/tmp` writable and the host's `/run` visible;
the state root is read-only in both.

- Inside `mutate_shell` agents cannot stage, commit or branch, because the
  whole `.git` is read-only; the user runs git.
- The masked names at the project root (`.git`, `.vscode`, `.idea`,
  `.agents`, `.aws`, `.gitmodules`, `.gitconfig`, `.ripgreprc` and the shell
  startup files `.bashrc`, `.bash_profile`, `.zshrc`, `.zprofile`,
  `.profile`) are read-only. A missing one is a read-only placeholder during
  a run, so none can be created there and `git init` at the project root
  fails. The empty placeholders exist on the host only during a run and are
  removed after it.
- When `.git` is a directory, the project files named by `core.hooksPath`, a
  `core.fsmonitor` program path or an included git config file (and every
  git config file in the project) are read-only to agents.
- Nested repositories up to 3 levels down are read-only, and a run that
  creates git metadata reports it with a warning.
- During a `mutate_shell` run an agent cannot rename or delete a folder that
  holds a protected path, while files in those folders stay writable.
- `write_file` and `edit_file` refuse the same paths `mutate_shell` holds
  read-only. They resolve their target again under the project lock (which
  `mutate_shell` holds for its whole run) and open the final component
  without following a symlink, so a symlink there is refused (the residual
  is in L3).
- A protected path that is a symlink is refused. Projects whose `.git` is a
  file or a symlink are unsupported.

### Codex 0.162.1 notes

- The plugin uses the Codex-native layout (`.codex-plugin/plugin.json` and
  `.mcp.json`), because a root `plugin.json` with the Agent Plugins `$schema`
  makes Codex skip the server entry and forward no environment.
- The chr-gate server entry in `.mcp.json` sets
  `default_tools_approval_mode` to `"approve"`, so Codex runs chr-gate tools
  without its own approval prompt. This is safe because chr-gate's gate checks
  every write (work order, open gate, claim).
- Codex must run in code mode, its default; turning it off stops all MCP tool
  calls (spike-findings item 2). In code mode the model calls tools from a
  script without seeing their schemas, so the server's unknown or missing
  argument refusals list the accepted arguments, for example
  `propose_plan: unknown argument(s) ['plan']; accepted: text (required)`.
- `features.unified_exec` cannot be disabled (spike-findings item 5: the
  candidate that sets it false still lists it true in
  [features-candidate_a_features.txt](tests/fixtures/spike-raw/codex/features-candidate_a_features.txt)),
  so the chr-gate PreToolUse hook denies the built-in shell calls (`Bash`,
  `shell`) and `apply_patch`, which has no working switch either, as it
  denies every built-in outside the Codex allowlist.
- Codex ignores a project's `.codex/config.toml` unless that project is
  trusted in the user's Codex config, so users merge
  `plugins/codex/config/chr-gate.toml` into `~/.codex/config.toml` or trust
  the project.
- `--dangerously-bypass-hook-trust` is used only by the smoke script; normal
  use trusts the plugin hooks through Codex's hook review.

## Smoke results

Both hosts passed all six live smoke steps (6/6 PASS each) on 2026-11-11:
Claude Code 2.1.280 and codex-cli 0.162.1. The steps: (1) the proposal is
recorded; (2) a turn that is exactly `approve P-...` activates exactly the
proposed text; (3) a wrong
witness is refused with "read your work order"; (4) the correct witness opens
the gate and returns the full text; (5) two `write_file` calls in one batch,
each with its own claim, write both files correctly; (6) a built-in write of
`c.txt` is denied and `c.txt` is absent.

- Claude Code: 6/6 PASS. Step 6 was blocked by host config: the model
  reported that no built-in Write tool existed in the session, so it made no
  tool call and the hook was not needed.
- Codex: 6/6 PASS. Step 6 was blocked by the chr-gate PreToolUse hook
  denying `apply_patch`, the only built-in the Codex hooks denied in the run;
  it writes files, so it stays denied.

The checker tables, versions and provenance are in
[docs/smoke-results.md](docs/smoke-results.md); the raw copies of both runs
are in [docs/smoke-raw/](docs/smoke-raw/).

## Stated limits

Hooks are not a full boundary. A hook only sees what the host routes through
it, and a host update can change that. The backstop is host config: the
Claude Code deny list in `chr-gate-settings.json`, and on Codex the read-only
sandbox (`sandbox_mode = "read-only"`) with the built-in shell switched off.

`research_shell` has no network, but web research uses the hosts' read-only
web tools, and a GET query string can still carry data out. `mutate_shell`
shares the network.

L1. Other MCP servers. chr-gate gates its own tools and denies the hosts'
built-in tools outside the read-only allowlists (see "Built-in tools"). A
tool of another MCP server or connector (`mcp__<other>__...`) is neither
gated nor denied. Run the example with no other server that can write, or
accept that those calls are outside the gate.

L2. Context changes the hosts do not report. The example is the limited
variant of C33 Appendix F.3: both hosts own their conversation history, and
only the compaction events they report (Claude Code `SessionStart` with
source `compact`, Codex `PostCompact`) start a new epoch. Rewind, silent
pruning of tool results and any other edit of the history are not seen;
chr-gate makes no claim about admission validity under history changes the
hosts do not report.

L3. The shells confine file writes, not processes. Bubblewrap holds the
project read-only in `research_shell` and the protected paths read-only in
`mutate_shell`. `research_shell` has a private `/tmp` and an empty `/run`,
but `mutate_shell` shares the network, binds the host's `/tmp` writable and
sees the host's `/run`, so a command there can reach Unix sockets the user
can reach (tmux, the D-Bus user bus, Docker, ssh-agent) and through them
services that act outside the sandbox. `write_file` and `edit_file` re-check
their target under the project lock and do not follow a symlink at the final
component, but an outside process that swaps an ancestor directory of the
target between that check and the open is not prevented. The shells are
sized for a worker acting in good faith, not a hostile one (C33 3.7).

L4. What counts as a turn. Claude Code: one tool batch. Codex: one code cell
that calls a chr-gate tool. A turn of text only, and a Codex cell that calls
only host tools, are not counted against `max_intervening_turns`, so a policy
of zero intervening turns is approximate.

L5. Approval is by plan id. `approve P-...` activates exactly the text stored
under that id, and the hook cannot show that text to the user: read it in the
`propose_plan` tool call before you approve; the agent's summary in chat is
not the stored text. Approval must be the user's whole prompt, and a
subagent's prompt never approves; whether either host fires
`UserPromptSubmit` for a message one agent sends to another (Codex
collaboration messages, Claude Code `SendMessage`) is not measured (M4).

L6. Delegation. A task is free text written by its assigner. The child
receives every inherited work order verbatim before its task, but the server
does not check that the task is narrower than those bounds. There is no tool
for a child to request a change and no way to revise an issued task: the
child stops and reports to its assigner, and the assigner delegates again to
a new subagent.

L7. Subagent compaction. Compaction of a subagent's own context was not
measured on either host: which events each host fires then, and with which
`agent_id`, is not measured (M2). If a host reports none, a child's witness
outlives the compaction of its context.

L8. Witness in Codex code mode. C33 3.0 requires the model to generate the
witness. Whether a Codex code cell keeps script variables from an earlier
cell is not measured (M3). If it does, a script can carry the witness from
the cell that read it to the `open_gate` cell without the model writing it
again; chr-gate refuses `open_gate` only in the same cell as the read.

L11. C33 mechanisms not built. The failed-opening cap and the
`authority_unavailable` value (C33 B.2); confirmed delivery before a witness
is set (C33 Appendix A); evidence admission and evidence ids at `open_gate`;
turn commits and post-commit verification (C33 B.4); the harness-performed
bootstrap (after compaction the hook resurfaces the work-order text only, and
the worker reads its new witness itself); per-action witness rotation (C33
Appendix F); the generation receipt (see below). A refused claim uses the
gate up on Claude Code, because the batch that held the consequential call
closes it, but on Codex a later cell of the same turn can still use it.

L12. Large work orders. Both hosts can truncate a long tool result. The
witness comes before the work-order text in the `status` result, and a
delegated frame's result also carries every inherited order, so a truncated
read can deliver the witness without the full text. Keep work orders short
enough for the host's tool-result limit.

Claims are checked for presence and work-order citation, never truth. The
server checks that the first argument is a non-empty claim containing the
caller's active `wo:ID.vN`; whether the claim is true is not checked.

Generation order is enforced only through the first-argument rule: a
consequential call whose first argument is not `claim` is refused. There is
no generation receipt (guide Stage 4).

The plaintext witness lives only in the MCP server's memory and disk holds
hashes, so a server restart issues a new witness and the agent must read its
work order again.

Frame attribution relies on the hook ticket on both hosts. Claude Code:
PreToolUse writes the frame under the `tool_use_id`, which the server matches
against `_meta["claudecode/toolUseId"]`; a Claude Code call whose `toolUseId`
has no ticket naming its tool is refused (`claude-no-ticket`), whatever the
tool, and a consequential call with no host identity at all is refused as not
mediated. Codex: PreToolUse also writes a ticket, keyed by the hook
`tool_use_id`, which equals the MCP `_meta.callId`; a Codex call without one
is refused (`codex-no-ticket`), whatever the tool. The frame and cell still
come from the `_meta` fields Codex sends (`threadId`, `parent_thread_id`,
`itemId`), which the server takes as sent (spike-findings item 3). Tickets
left by calls the host or the user refused are dropped when their batch ends.

A repository an agent creates during a run, or one deeper than 3 levels, is
unprotected: its hooks and config are the agent's. Never run git in
agent-created directories, or run it there with hooks and fsmonitor off:

    git -c core.fsmonitor=false -c core.hooksPath=/dev/null <command>

Git settings whose value is a command (pager, editor, filters, aliases, diff
and merge drivers, credential helpers) that names a project file can run
agent-edited code, as can settings passed with `-c` or `GIT_CONFIG_*` that
chr-gate cannot see.

Agent-edited Makefiles and scripts run when the user runs them.

Spike item 4, Claude Code: FALLBACK. The assistant text written before a tool
call is not in the Claude Code transcript at PreToolUse or PostToolBatch; it
appears only at Stop, which takes no additionalContext. So Claude Code
citations in text are checked only on the final assistant text at Stop, and
their warnings arrive with the next event; the `cite(nonces)` tool is the
in-turn channel there. Codex hooks read the text in time (CONFIRMED).

Linux with bubblewrap only. The shells need `bwrap`; without it they refuse,
and the tests fail rather than skip.

## Tests

From the repository root:

    scripts/unit_suite.sh

It runs the pytest suite in `tests/` and also the tests of the smoke and spike
kits in [scripts/smoke/](../scripts/smoke/) and
[scripts/spike/](../scripts/spike/).

`tests/test_readme.py` checks this file: every relative link resolves, every
C33 section it cites is a heading of the C33 paper, and every FALLBACK or
LIMIT verdict in [docs/spike-findings.md](docs/spike-findings.md) has a limit
paragraph above. The expectations are parsed from those documents.
`tests/test_readme.py` also checks the release documents: every relative link
in the root `README.md` resolves, and the root README, this README,
`CHANGELOG.md`, `CONTRIBUTING.md`, `LICENSE.md` and `COMMERCIAL-LICENSE.md`
all exist and none of them describes the source-available release with the
term the test forbids.

## License

chr-gate is source-available and non-commercial. The code in `chr-gate/`,
`plugins/` and `scripts/` is licensed under the PolyForm Noncommercial License
1.0.0; see [LICENSE.md](../LICENSE.md). Any commercial use requires a
separately negotiated license; see
[COMMERCIAL-LICENSE.md](../COMMERCIAL-LICENSE.md). Patent applications are
pending.
