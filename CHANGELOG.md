# Changelog

## 0.2.0 - 2026-11-11

### Added

- Revocation: the user's exact prompt `revoke wo:ID.vN` revokes the active
  principal work order. Every frame's witness and gate are cleared and every
  delegation under it ends; the next `approve P-...` continues at the revoked
  version plus one. A reference that is not the active one revokes nothing
  and the notice names the active reference.
- Self-hosting refusal (C33 3.10): when the `chrgate` package lies inside the
  governed project, the server refuses every call with code `self-hosting`
  before attribution, and the hook denies every PreToolUse.
- `open_gate` in a turn whose consequential call already used the gate is
  refused (`open_gate` outcome `denied-acted-turn`) and changes no state.
- `docs/wiki/`: one page per subsystem plus an index, for people testing the
  example harnesses, linked from `README.md`. `chr-gate/tests/test_wiki.py`
  tests the pages.
- `scripts/spike/render_kit_config.py`, which renders the spike kit config
  templates.

### Changed

- The paper revision is now C33
  (`Grounded_Authority_for_Language_Model_Agents_C33.md`): Appendix F.5 gains
  a paragraph on the recursive assigner model of task sub-authorities. Every
  citation in the repository names C33; the C32 file moved to the git-ignored
  `old/` and stays in git history.
- Approval must be the whole prompt: the stripped prompt must be exactly
  `approve P-xxxxxxxx`. A prompt that only mentions the phrase activates
  nothing and gets a notice saying so, and a prompt in a subagent never
  approves.
- Built-in tools are denied by default. The hook denies every host built-in
  (a name not starting with `mcp__`) that the adapter's read-only allowlist
  does not name: on Claude Code `Read`, `Glob`, `Grep`, `ToolSearch`,
  `WebFetch`, `WebSearch`, `Skill`, `Task`, `Agent`, `ListAgents`,
  `TaskStop`, `ReportFindings` and `CronList`; on Codex
  `collaborationspawn_agent` and `collaborationwait_agent`. Read-only-looking
  tools outside the lists (for example `LSP`, `AskUserQuestion`,
  `TodoWrite`, `Monitor`, `PowerShell`) are now denied too. Each denial is a
  `builtin_denied` event (outcome `denied`, ref the tool, with the frame),
  and `smoke_check` prints one INFO line per event. The Claude Code settings
  deny list adds `CronCreate`, `CronDelete`, `EnterWorktree`,
  `ExitWorktree`, `RemoteTrigger`, `ScheduleWakeup`, `SendMessage` and
  `Workflow`.
- Claude Code `UserPromptSubmit` and `Stop` now end the open batch, as
  backstops for a missing `PostToolBatch`; an unused open gate survives them.
- A Codex call to a chr-gate tool needs a PreToolUse hook ticket, keyed by the
  hook `tool_use_id` (equal to `_meta.callId`); without one every call,
  `status` included, is refused (`codex-no-ticket`). The frame and cell still
  come from `_meta`.
- Delegation ids are stored only as their sha256 in `delegations.json`, and a
  Claude Code child must run in its assigner's session
  (`delegation-parent-mismatch` otherwise). A stored record from before this
  change (no hash) never binds: such delegations fail closed and must be made
  again.
- A delegated frame's `status`, `open_gate` and compaction text deliver every
  inherited work order verbatim before the task, the user-approved one first,
  with the rule that the inherited orders govern. The delegation-ended
  refusal now says the parent order was "revised or revoked".
- `research_shell` runs with a private `/tmp` (a tmpfs discarded after each
  call) and an empty `/run`; `mutate_shell` is unchanged.
- `sandbox._project_lock(state)` is now the public
  `sandbox.project_lock(state_root)`, a non-reentrant exclusive per-project
  lock.
- A Claude Code call to a chr-gate tool that the chr-gate PreToolUse hook did
  not ticket is now refused (`claude-no-ticket`), fail closed, whatever the
  tool. Before, it ran on the server's `CLAUDE_CODE_SESSION_ID` frame, which
  is not the session's frame after `/clear` or `--resume`. The chr-gate hooks
  are required: a session where they do not run gets every chr-gate call
  refused, including `status`.
- The captured fixtures and smoke logs use `/home/user` as the home directory
  and the neutral `user user` as the file owner.
- The spike kit configs are templates: the runners render `@KIT@` and `@UV@`
  into them, so the kit runs from any clone, and the commands in
  `scripts/spike/README.md` are relative to the repository.
- `scripts/unit_suite.sh` collects every test under `scripts/`.
- Comments, docstrings and docs no longer cite internal tracker records, and
  an internal pin reference was removed from a test comment.

### Fixed

- `write_file` and `edit_file` resolve their target again under the project
  lock and open the final component with `O_NOFOLLOW`, so a directory swapped
  for a symlink, or a symlink at the final component, is refused.
- On Codex the cell that acts is no longer counted as an intervening turn of
  its own gate (C33 Appendix A).
- Compaction clears the frame's context nonces for every frame, also one with
  no frame record yet.
- The project scan skips a directory that vanishes during the scan, and an
  `OSError` in a tool call becomes an `internal-error` refusal instead of an
  SDK error.
- Tickets left by calls the host or the user refused are deleted when their
  batch ends (ticket cleanup).

## 0.1.0 - 2026-10-29

The first public release of chr-gate, the example CHR gate for Claude Code
and Codex.

### Added

- The MCP server `chrgate-mcp`: work orders, propose and approve, the gate
  with its bound witness, claims, citations and context nonces, delegation,
  testimony, and the bubblewrap shells `research_shell` and `mutate_shell`.
- The shared host hook `chrgate-hook`, with one adapter per host, and
  `chrgate-setup`, which creates the protected host-config paths a project
  needs.
- The Claude Code plugin (`plugins/claude-code/`) and the Codex plugin
  (`plugins/codex/`).
- The live smoke kit (`scripts/smoke/`) and the host measurement kit
  (`scripts/spike/`).
- A GitHub Actions workflow (`.github/workflows/ci.yml`) that runs
  `scripts/unit_suite.sh` under bubblewrap on Python 3.12 and 3.14.

### Fixed

- The Store lock file is masked in both shells, as the project lock already
  was, so no command inside `research_shell` or `mutate_shell` can take or
  contend for it.
- Refusal texts name the tool that was invoked, and the refusals the sandbox
  raises for any tool start with "chr-gate refused".

### Changed

- `mutate_argv` is no longer public in `chrgate.server.sandbox`. The public
  functions are `protected_paths`, `missing_protected`, `ensure_protected`,
  `read_only_paths`, `research_argv`, `run` and `run_mutate`.
- `scripts/unit_suite.sh` also runs the `scripts/smoke` and `scripts/spike`
  tests.
- chr-gate requires Python 3.12 or newer; the suite was run on CPython 3.12
  and 3.14.
- Licensing: the repository is source-available and non-commercial. The code
  is licensed under the PolyForm Noncommercial License 1.0.0 and the three
  documents under CC BY-NC-ND 4.0 with an additional permission for
  non-commercial translations; see `LICENSE.md`. Commercial use needs a
  separately negotiated license; see `COMMERCIAL-LICENSE.md`. Patent
  applications are pending.
