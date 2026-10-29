---
name: chr-gate
description: Working rules for a project governed by the chr-gate plugin. Use before any action that changes files, runs a mutating command, launches a subagent that will write or gives consequential testimony, and whenever a chr-gate tool refuses.
---

# Working under the chr-gate

This project is governed by the chr-gate MCP server (the gate protocol of C32
Appendix A). Every action with an external effect goes through it; reads and
normal replies never need it. The built-in Bash, Write, Edit, MultiEdit and
NotebookEdit tools are denied. In Claude Code the server's tools are named
`mcp__plugin_chr-gate_chr-gate__<tool>`, for example
`mcp__plugin_chr-gate_chr-gate__write_file`.

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

Only invalid citations produce output (a chr-citation-warning on a later
hook); when every citation is valid you hear nothing. Claude Code hooks see
your text only when the turn ends, so before a consequential turn also pass the
same nonces to `cite`; it returns a fresh nonce when all are valid, else a
warning naming the invalid ones. Never invent or alter a nonce.

## No work order yet

If `status` says there is no active work order, write the full plan and call
`propose_plan` with it. It returns a plan id and the exact phrase
`approve P-xxxxxxxx`. Stop and ask the user to reply with that phrase. Do not
act until the user's own prompt approves it; the approved plan becomes your
work order `wo:ID.vN`.

## The gate sequence

1. Read the work order with `status` (or `read_work_order`). Repeat reads in
   the same context return the same witness. A read cancels any pending open
   gate.
2. Call `open_gate` with the witness, in its own turn. A failure returns "read
   your work order": go back to step 1. A pass returns the full work order:
   read it again.
3. Research may follow (reads, `research_shell`, `cite`) without using up the
   gate. Do not call `status` again before acting; it cancels the gate.
4. Act in ONE later turn. The next turn that holds consequential calls uses the
   gate, and the gate covers that turn only, so put every consequential call of
   this step into that turn as parallel calls. Each call carries its own
   `claim` as its FIRST argument, written before the other arguments: a
   statement of how this action follows from the work order, citing
   `wo:ID.vN`. The server checks that a claim is present and cites your active
   work order; it does not check that the claim is true, so make it true.
5. For more consequential work, start again at step 1.

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

- Before launching a subagent that will write, call `delegate(claim,
  work_order)` under your open gate. Put the returned delegation id into the
  subagent's prompt and tell it to pass that id as `delegation_id` in its first
  `status` call. Authority runs child -> you -> the user.
- A read-only subagent needs no delegation.
- As a subagent, pass the delegation id from your launch prompt in your first
  `status` call. If a result says your delegation ended, stop and report back
  to your caller.

## When a tool refuses

- `write_file`, `edit_file` and `mutate_shell` refuse while a protected
  host-config path (such as .claude/, .codex/ or .mcp.json) is missing in the
  project. You cannot create those paths yourself: ask the user to run
  `chrgate-setup` in the project root (in their own shell, for example
  `! chrgate-setup`), then retry. A missing .git/config needs a git repair;
  `chrgate-setup` never creates it.
- "read your work order" or another gate refusal: go back to step 1 of the gate
  sequence.
- "not mediated": the call did not pass the chr-gate hook, so the plugin's
  hooks are not running. Tell the user; do not retry.
