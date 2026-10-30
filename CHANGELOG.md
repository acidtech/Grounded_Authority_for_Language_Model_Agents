# Changelog

## Unreleased

### Changed

- A Claude Code call to a chr-gate tool that the chr-gate PreToolUse hook did
  not ticket is now refused (`claude-no-ticket`), fail closed, whatever the
  tool. Before, it ran on the server's `CLAUDE_CODE_SESSION_ID` frame, which
  is not the session's frame after `/clear` or `--resume`. The chr-gate hooks
  are required: a session where they do not run gets every chr-gate call
  refused, including `status`.

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
