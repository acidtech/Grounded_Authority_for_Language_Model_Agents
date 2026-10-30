# chr-gate live smoke kit (T7a)

Scripted live sessions, one per host, plus a checker. They need an
authenticated `claude` / `codex`, so you run them from your own shell:

    ! uv tool install --editable chr-gate
    ! bash scripts/smoke/smoke_claude_code.sh
    ! bash scripts/smoke/smoke_codex.sh

Each script (HOST is `claude-code` or `codex`):

1. creates the scratch git project `/tmp/chr-gate-smoke/HOST-proj` and runs
   `chrgate-setup --project` on it right after `git init` (without it every
   write tool refuses), with `XDG_STATE_HOME=/tmp/chr-gate-smoke/HOST-state`
   and `CHR_GATE_PROJECT` set to the project; earlier outputs are moved to
   `*.prev.STAMP`;
2. records the host version in `/tmp/chr-gate-smoke/HOST-version.txt`;
3. runs six non-interactive turns in ONE resumed session, saving every stream
   in `/tmp/chr-gate-smoke/HOST-streams/` and every host session id
   (Claude Code `session_id`, Codex `thread_id`) in
   `/tmp/chr-gate-smoke/HOST-session.txt`: (1) propose_plan for a.txt and
   b.txt, (2) `approve P-...` with the plan id read from the state,
   (3) open_gate with a deliberately wrong witness, (4) status then open_gate
   with the received witness, (5) two parallel write_file calls, each with its
   own claim, (6) a built-in write of c.txt (Claude Code Write; Codex
   apply_patch or shell);
4. prints the checker table:
   `uv run --frozen --project chr-gate python -m chrgate.smoke_check --host HOST --state /tmp/chr-gate-smoke/HOST-state --project /tmp/chr-gate-smoke/HOST-proj`.

The checker finds the one `events.jsonl` under `--state` (so it also runs on
copied outputs), prints PASS or FAIL for the six steps and exits 0 only when
all pass. Its INFO lines (one per refused-claude-no-ticket, refused-not-mediated
or hook_error event, naming the tool, the reason and the frame; the frame ids
in the log next to the saved host session ids) are diagnostics and never
change the exit code.

Claude Code: `claude -p` with `--plugin-dir plugins/claude-code`,
`--settings plugins/claude-code/settings/chr-gate-settings.json` (built-in
writes denied), `--setting-sources project` (your user hooks and plugins stay
out) and `--allowedTools` set to the chr-gate tools, then `--resume SESSION`.

Codex: the script installs the plugin with
`codex plugin marketplace add plugins/codex` and
`codex plugin add chr-gate@chr-gate-local`, and prints the removal commands at
the end:

    codex plugin remove chr-gate@chr-gate-local
    codex plugin marketplace remove chr-gate-local

- Hook trust: Codex skips plugin hooks until you trust their current hash in
  the interactive `/hooks` review. The script passes
  `--dangerously-bypass-hook-trust` on every `codex exec` / `codex exec resume`
  instead, so no one-time step is needed.
- Config fragment: Codex loads a project `.codex/config.toml` only for a
  project trusted in your user config, and `-c` cannot grant that trust, so
  the script applies `plugins/codex/config/chr-gate.toml` as `-c` session
  overrides on every call.
- Pre-flight, before the first model turn: `codex app-server` must list a
  chr-gate MCP server with its tools (`mcpServerStatus/list`) and show every
  fragment value in effect (`config/read`); otherwise the script stops with
  `pre-flight FAILED` and runs no session. The check is
  `scripts/smoke/codex_preflight.py PROJECT KEY=VALUE...`: it starts the
  `codex` on PATH with one `-c` per fragment pair, refuses a pair argument
  that starts with `-` or has no `=`, and when the app-server's output ends
  before both replies it names the app-server's exit code and stderr; a
  JSON-RPC error reply is printed verbatim. Its tests drive a stub codex;
  `test_fragment_pairs.py` checks the pairs `scripts/smoke/fragment_pairs.py`
  reads from the fragment:
  `cd chr-gate && uv run --frozen --no-sync pytest -q -p no:cacheprovider ../scripts/smoke/test_codex_preflight.py ../scripts/smoke/test_fragment_pairs.py`.
- State root: `plugins/codex/.mcp.json` forwards `XDG_STATE_HOME` and
  `CHR_GATE_PROJECT` to chrgate-mcp (`env_vars`), because Codex starts MCP
  servers with a minimal environment; the hooks inherit the shell's.
- Tool approval: `plugins/codex/.mcp.json` also sets
  `default_tools_approval_mode` to `"approve"`, so Codex runs the chr-gate
  tools under the smoke's `approval_policy="never"` instead of refusing them
  (bug 24b8a8). This is safe because chr-gate's own gate (work order, open
  gate, claim) checks every write.

## Root frame probe (debt dcb46a)

chr-gate takes the root frame of a call with no frame identity from the MCP
server's environment `CLAUDE_CODE_SESSION_ID` (`tickets.root_frame()`); the
hooks see the payload `session_id`. The probe shows whether the two agree for
the same tool call, including after `/clear` and `--resume`. It needs an
interactive, authenticated `claude`, so you run it:

    ! bash scripts/smoke/probe_root_frame.sh setup

Then, in your own terminal (approve the `whoami` MCP server if asked):

    cd /tmp/chr-gate-smoke/root-frame-probe/proj && claude --setting-sources project
    > call the whoami tool
    /clear
    > call the whoami tool
    /exit
    cd /tmp/chr-gate-smoke/root-frame-probe/proj && claude --setting-sources project --resume
    (pick the most recent session, the one after /clear)
    > call the whoami tool
    /exit

Then run the check and paste its output:

    ! bash scripts/smoke/probe_root_frame.sh check

`setup` moves an earlier `/tmp/chr-gate-smoke/root-frame-probe` to
`*.prev.STAMP` and creates the scratch git project `proj/` with
`.mcp.json` (server `whoami`: `python3 scripts/smoke/root_frame_probe.py server`,
absolute path, logging to `../mcp.jsonl`) and `.claude/settings.json`
(`enableAllProjectMcpServers` and a PreToolUse hook on `mcp__whoami__whoami`
running `root_frame_probe.py hook`, logging to `../hook.jsonl`; it never blocks
a call). `--setting-sources project` keeps your user hooks and plugins out of
the session, as in `smoke_claude_code.sh`; the project's own `.mcp.json` and
settings still load. `check` pairs each server call record with the hook record
of the same tool use id (`claudecode/toolUseId` in the call's `_meta`,
`tool_use_id` in the hook payload) and prints one row per call:
`tool_use_id pid env_session_id hook_session_id verdict`.

How to read it:

- every row MATCH and `result: PASS` (exit 0): the server env id equals the
  hook session id in all three calls, before `/clear`, after it and after
  `--resume`; that closes dcb46a.
- any MISMATCH (for example after `/clear`, when the hook session id changes
  but the server keeps its env), or a different `pid` in the first two rows
  (one claude process, so the server was restarted on `/clear` and its env
  re-read): report the output; it goes to a separate design plan. The third
  row's `pid` always differs, because `--resume` starts a new claude process.
- UNPAIRED: a call without a hook record or a hook record without a call (the
  hook did not fire, or the tool use id did not reach one side); `check` exits 1
  when any row is not MATCH or when there is no pair at all.

Unit tests (offline: synthetic records plus a run of setup, the server, the
hook and check under a temporary `PROBE_ROOT`):
`cd chr-gate && uv run --frozen --no-sync pytest -q -p no:cacheprovider ../scripts/smoke/test_root_frame_probe.py`.
