# chr-gate: an example CHR gate for Claude Code and Codex

chr-gate puts the gate protocol of
[Grounded Authority for Language-Model Agents](../Grounded_Authority_for_Language_Model_Agents_C32.md)
(C32 Appendix A) in front of two coding-agent hosts, Claude Code and Codex.
Every action with an external effect goes through one MCP server,
`chrgate-mcp`, and needs an approved work order, an open gate and a written
claim. The host hooks (`chrgate-hook`) deny the hosts' built-in write tools,
carry frame identity to the server, check citations and resurface the work
order after compaction.

## What this is and is not

This is an example with stated limits (see "Stated limits" below). It shows
how C32's gate can sit in front of hosts that already exist, using only their
plugin systems, their hooks and an MCP server, and it is checked against those
hosts: the host behaviour it relies on is measured in
[docs/spike-findings.md](docs/spike-findings.md), and the live runs are
recorded in [docs/smoke-results.md](docs/smoke-results.md).

It is not a hardened product. The hooks are not a full boundary, the shell
protections need Linux with bubblewrap, and several C32 mechanisms are reduced
here (each reduction is listed under "Stated limits"). It is not a remake of
any other harness: it is built from C32 and the implementation guide
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
  (the built-in write denials).
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
working-rules skill. `--settings` denies the built-in `Bash`, `Write`, `Edit`,
`MultiEdit` and `NotebookEdit` tools. The server's tools appear as
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
  the hooks no work order can be approved (approval runs in the
  `UserPromptSubmit` hook), chr-gate denies no built-in write and compaction
  starts no new epoch.
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
   `approve P-xxxxxxxx`.
2. Reply with exactly that phrase. The `UserPromptSubmit` hook activates
   exactly that proposal's text as the work order `wo:ID.v1`; only your own
   prompt can approve it.
3. The agent reads its work order with `status`, calls
   `open_gate(witness)` in a later turn (Codex: a later code cell), then acts
   in a later turn with `write_file(claim, path, content)`, `edit_file`,
   `mutate_shell`, `delegate` or `testify`, each call carrying its own claim
   that cites `wo:ID.v1`.

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

chr-gate follows C32's default witness lifecycle. The MCP server is the only
witness issuer; the hooks never mint, hold or see a plaintext witness.
`status` returns the frame's witness (`wit:` plus 128 random bits). Repeat
work-order reads in one frame epoch return the same witness (Invariant 2,
C32 3.2): the witness is bound to the work order id, its version, the frame
and the epoch; the server keeps the plaintext in its process memory for that
binding, and the state on disk holds only its sha256 and the binding.

`open_gate` neither rotates nor consumes the witness, so the same witness
opens each separately opened gate in its epoch. A trusted work-order re-read
(`status` or `read_work_order`) cancels a pending open gate (C32 Appendix A),
while other research (`research_shell`, `cite`, the hosts' read-only tools)
keeps the gate open.

The witness ends when the epoch ends: a new work-order version or another
authority change, or compaction (C32 2.4). After compaction the hook
resurfaces only the work-order text, with the instruction to read the work
order again, and the agent reads its new witness from the server. Per-action
rotation (C32 Appendix F) is not used.

### The gate

`open_gate(witness)` returns "read your work order" on any failure and changes
no state; a pass returns the full work order text. Research may follow
without using the gate up. The next consequential turn uses it: the first
consequential call takes the gate for its turn, parallel calls of that same
turn share it (each with its own claim), and a later turn needs a new
`open_gate`. A consequential call in the turn that opened the gate is refused.

The turn boundary differs per host (spike-findings item 2). Claude Code:
one tool batch, closed by the `PostToolBatch` hook. Codex: one code cell,
identified by the MCP `_meta.itemId`; `open_gate` must run in a later cell
than the read that delivered the witness, and consequential calls in a later
cell than `open_gate`. Codex `Stop` and the next user prompt are backstops.

A pending gate expires after `gate_lifetime_seconds` (default 900) or
`max_intervening_turns` completed research turns (default 3). Both live in
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

### Mechanism map

| Mechanism | chr-gate | C32 | Guide stage |
|-----------|----------|-----|-------------|
| Witnesses and nonces | `wit:` witness from `status`; `ctx:` nonce on every result | C32 2.3 Identifiers; C32 Appendix D | Stage 1 (nonces), Stage 2 (the bound witness) |
| Epochs and compaction | compaction starts a new epoch for the frame and ends witness and gate | C32 2.4 Context epochs; C32 B.1 | Stage 2 (start_new_epoch) |
| Consequential tools | the five tools above; built-in writes denied | C32 2.5 Consequential actions; C32 3.7 Effect policy | Above the gate: Effect policy |
| Citation warning | `<cite>` tags checked, warnings only on invalid ones | C32 3.0 The shared context-provenance validator | Stage 1: Shared context-provenance validator and minimal warning profile |
| `open_gate` and work-order binding | witness bound to work order version, frame and epoch | C32 3.2 The four invariants; C32 3.3 The gate; C32 Appendix A | Stage 2: Authority gate with `plan_auth` and the bound witness |
| Resurfacing | `open_gate` pass and post-compaction hook return the work-order text | C32 3.4 Resurfacing | Stage 3: Resurfacing |
| Claims | required first argument citing `wo:ID.vN` | C32 3.5 Claims | Stage 4: Action-specific claims (without the generation receipt) |
| Parallel turns | one gate covers one turn's parallel calls | C32 3.8 Parallel batches | Above the gate: Parallel batches |
| Propose and approve | `propose_plan`, then the user's `approve P-...` | C32 3.9 Approval and change requests | Above the gate: Approval and change requests |
| Delegation | `delegate(claim, work_order)`; child -> caller -> user | frame model of C32 Appendix B | none (the guide's stages do not cover delegation) |

Delegation: a subagent that will write gets its work order through
`delegate(claim, work_order)` under the caller's open gate and authority. The
returned delegation id goes into the subagent's launch prompt, and the child
presents it on its first `status` call, which binds it to the child's frame.
Authority runs child -> caller -> user. A read-only subagent needs no
delegation.

### Protected paths and git

`research_shell` runs in bubblewrap with the project and the state root
read-only and no network. `mutate_shell` runs with the project writable
except the paths below and with the network shared; the state root is
read-only in both.

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
  read-only.
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
  `shell`), as it denies `apply_patch`, which has no working switch either.
- Codex ignores a project's `.codex/config.toml` unless that project is
  trusted in the user's Codex config, so users merge
  `plugins/codex/config/chr-gate.toml` into `~/.codex/config.toml` or trust
  the project.
- `--dangerously-bypass-hook-trust` is used only by the smoke script; normal
  use trusts the plugin hooks through Codex's hook review.

## Smoke results

Both hosts passed all six live smoke steps (6/6 PASS each) on 2026-10-29:
Claude Code 2.1.280 and codex-cli 0.162.1. The steps: (1) the proposal is
recorded; (2) `approve P-...` activates exactly the proposed text; (3) a wrong
witness is refused with "read your work order"; (4) the correct witness opens
the gate and returns the full text; (5) two `write_file` calls in one batch,
each with its own claim, write both files correctly; (6) a built-in write of
`c.txt` is denied and `c.txt` is absent.

- Claude Code: 6/6 PASS. Step 6 was blocked by host config: the model
  reported that no built-in Write tool existed in the session, so it made no
  tool call and the hook was not needed.
- Codex: 6/6 PASS. Step 6 was blocked by the chr-gate PreToolUse hook
  denying `apply_patch`.

The checker tables, versions and provenance are in
[docs/smoke-results.md](docs/smoke-results.md); the raw copies of both runs
are in [docs/smoke-raw/](docs/smoke-raw/).

## Stated limits

Hooks are not a full boundary. A hook only sees what the host routes through
it, and a host update can change that. The backstop is host config: the
Claude Code deny list of built-in write tools, and on Codex the read-only
sandbox (`sandbox_mode = "read-only"`) with the built-in shell switched off.

`research_shell` has no network, but web research uses the hosts' read-only
web tools, and a GET query string can still carry data out. `mutate_shell`
shares the network.

The C32 F.3 hosted-history variant is out of scope. Both hosts own their
conversation history; chr-gate makes no claim about admission validity under
history changes it does not see, beyond starting a new epoch on the
compaction events the hosts report.

Claims are checked for presence and work-order citation, never truth. The
server checks that the first argument is a non-empty claim containing the
caller's active `wo:ID.vN`; whether the claim is true is not checked.

Generation order is enforced only through the first-argument rule: a
consequential call whose first argument is not `claim` is refused. There is
no generation receipt (guide Stage 4).

The plaintext witness lives only in the MCP server's memory and disk holds
hashes, so a server restart issues a new witness and the agent must read its
work order again.

Frame attribution relies on the hook ticket on Claude Code (PreToolUse writes
the frame under the `tool_use_id`, which the server matches against
`_meta["claudecode/toolUseId"]`; a Claude Code call whose `toolUseId` has no
ticket naming its tool is refused (`claude-no-ticket`), whatever the tool, and
a consequential call with no host identity at all is refused as not mediated)
and, on Codex, on the `_meta` fields the host sends
(`threadId`, `parent_thread_id`, `itemId`), which the server takes as sent
(spike-findings item 3).

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
C32 section it cites is a heading of the C32 paper, and every FALLBACK or
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
