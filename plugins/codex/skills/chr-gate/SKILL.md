---
name: chr-gate
description: Working rules for a project governed by the chr-gate plugin. Use before any action that changes files, runs a mutating command, spawns a subagent that will write or gives consequential testimony, and whenever a chr-gate tool refuses.
---

# Working under the chr-gate

This project is governed by the chr-gate MCP server (the gate protocol of C33
Appendix A). Every action with an external effect goes through it; reads and
normal replies never need it. The built-in shell is switched off, the sandbox
is read-only, and the chr-gate hook denies every built-in tool except
`collaborationspawn_agent` and `collaborationwait_agent`, `apply_patch` and
any built-in shell call included. In Codex the server's tools are named
`mcp__chr_gate__<tool>`, for example `mcp__chr_gate__write_file`; you call
them from your code cells.
Codex must run with code mode on: the server refuses a call that carries no
code-cell id.

The tools:

- `status` (alias `read_work_order`): read your active work order: its
  reference `wo:ID.vN`, its full text and your witness for `open_gate`.
- `open_gate`: open the action gate with that witness.
- `cite`: report the context nonces you rely on (fallback channel, see below).
- `propose_plan`: propose a work order for the user to approve.
- `research_shell`: run a read-only shell command in the project (no network).
- `write_file`, `edit_file`, `mutate_shell`: change the project (consequential).
- `delegate`: hand a work order to a subagent that will write (consequential).
- `testify`: record consequential testimony (consequential).

## Cite the context you rely on

Every chr-gate result ends with a line `chr-gate context nonce: ctx:...`.
After thinking and before acting, write the nonces you rely on in a cite tag in
your assistant text, exactly in this form (lowercase tag, no attributes,
nonces separated by spaces):

    <cite>ctx:... ctx:...</cite>

Codex hooks read your text before each tool call, so writing the tag before the
code cell that acts is enough. Only invalid citations produce output (a
chr-citation-warning on a later hook); when every citation is valid you hear
nothing. `cite` is only a fallback: it returns a fresh nonce when all the
nonces you pass are valid, else a warning naming the invalid ones. Never
invent or alter a nonce.

## No work order yet

If `status` says there is no active work order, write the full plan and call
`propose_plan` with it. It returns a plan id and the exact phrase
`approve P-xxxxxxxx`. Stop and ask the user to read the plan text in your
`propose_plan` tool call (approval activates exactly that stored text, not
your summary of it) and then to reply with exactly that phrase and nothing
else; a message that only mentions the phrase activates nothing. Do not act
until the user's own prompt approves it; the approved plan becomes your work
order `wo:ID.vN`. The user ends it with `revoke wo:ID.vN`; after that `status`
says there is no active work order.

## The gate sequence

In Codex the gate counts code cells: one exec cell is one step.

1. Read the work order with `status` (or `read_work_order`). Repeat reads in
   the same context return the same witness. A read cancels any pending open
   gate.
2. Call `open_gate` with the witness in a LATER code cell than the read; in
   the same cell it is refused. A failure returns "read your work order": go
   back to step 1. A pass returns the full work order: read it again.
3. Research may follow (reads, `research_shell`, `cite`) without using up the
   gate. Do not call `status` again before acting; it cancels the gate.
4. Act in ONE later code cell, never the cell that called `open_gate`. That
   cell uses the gate and the gate covers that cell only, so put every
   consequential call of this step into it (parallel or awaited in turn). Each
   call carries its own `claim` as its FIRST argument, written before the other
   arguments: a statement of how this action follows from the work order,
   citing `wo:ID.vN`. The server checks that a claim is present and cites your
   active work order; it does not check that the claim is true, so make it
   true.
5. For more consequential work, start again at step 1. A gate you used ends
   with its cell: the next cell, the end of your turn and the user's next
   prompt all need a new `open_gate`. A gate you opened but did not use lasts
   until it expires (`gate_lifetime_seconds`, default 900, or
   `max_intervening_turns` research cells, default 3), until you call `status`
   again or until compaction. `open_gate` in a cell that already made a
   consequential call is refused; call it in the next cell.

## Consequential tools

- `write_file(claim, path, content)` and `edit_file(claim, path, old, new)`:
  files inside the project, never .git/, .claude/, .codex/ or .mcp.json.
- `mutate_shell(claim, command)`: a command that may change the project
  (network allowed). The .git tree is read-only; the user runs git.
- `delegate(claim, work_order)`: see Subagents.
- `testify(claim, text)`: when your response itself is consequential (a
  statement someone will act on as fact), record it as testimony under an open
  gate.

Read-only work needs no gate: use `research_shell(command)` for shell reads
(the project is read-only and there is no network) and the host's read-only
web tools for web research.

## Subagents

- Before spawning a subagent that will write, call `delegate(claim,
  work_order)` under your open gate. You are its assigner: the `work_order`
  you write is its task, nobody can change it once issued, and it must stay
  inside your own work order, which the child receives verbatim above its
  task. Put the returned delegation id into the subagent's message and tell
  it to pass that id as `delegation_id` in its first `status` call. A changed
  task is a new delegation to a new subagent. Authority runs child -> you ->
  the user.
- A read-only subagent needs no delegation.
- As a subagent, pass the delegation id from your spawn message in your first
  `status` call. Your work order shows every inherited work order verbatim,
  the user-approved one first, then the rule that they govern, then your task
  under `--- work order text (your task, written by your assigner) ---`. The
  inherited orders win over your task. If your task is wrong or conflicts
  with an inherited order, do not act on it: stop and report to your
  assigner. If a result says your delegation ended, stop and report back to
  your assigner.

## When a tool refuses

- `write_file`, `edit_file` and `mutate_shell` refuse while a protected
  host-config path (such as .claude/, .codex/ or .mcp.json) is missing in the
  project. You cannot create those paths yourself: ask the user to run
  `chrgate-setup` in the project root (in their own shell, outside Codex),
  then retry. A missing .git/config needs a git repair; `chrgate-setup` never
  creates it.
- "read your work order" or another gate refusal: go back to step 1 of the gate
  sequence.
- A refusal that the call carries no code-cell id: Codex is running with code
  mode off. Tell the user; do not retry.
- A refusal that the chr-gate PreToolUse hook did not ticket this Codex call
  (`codex-no-ticket`): the plugin's hooks are not running (Codex skips plugin
  hooks until the user trusts them), so every chr-gate tool, `status`
  included, is refused. Tell the user to trust the chr-gate hooks in Codex's
  hook review (`/hooks`) or to run Codex with them enabled; do not retry until
  the user says the hooks run.
