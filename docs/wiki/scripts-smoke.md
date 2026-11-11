# Live smoke kit

> `scripts/smoke/` runs one scripted six-turn session per host against a scratch project and checks the recorded state with `chrgate.smoke_check`; a separate probe tests where the root frame comes from.

## Key Files
- [README.md](../../scripts/smoke/README.md): what each script does and how to read its output
- [smoke_claude_code.sh](../../scripts/smoke/smoke_claude_code.sh) and [smoke_codex.sh](../../scripts/smoke/smoke_codex.sh): the session scripts
- [codex_preflight.py](../../scripts/smoke/codex_preflight.py): `codex app-server` must list the chr-gate tools and show the fragment in effect
- [fragment_pairs.py](../../scripts/smoke/fragment_pairs.py): the Codex config fragment as bare `key=value` pairs for `-c`
- [probe_root_frame.sh](../../scripts/smoke/probe_root_frame.sh) and [root_frame_probe.py](../../scripts/smoke/root_frame_probe.py): the interactive root-frame probe
- [smoke_check.py](../../chr-gate/src/chrgate/smoke_check.py): the checker
- [smoke-results.md](../../chr-gate/docs/smoke-results.md): the recorded run, 6/6 PASS on both hosts

## How It Works
Each script creates `/tmp/chr-gate-smoke/HOST-proj` (`git init`, then `chrgate-setup --project`), sets `XDG_STATE_HOME` and `CHR_GATE_PROJECT`, moves earlier outputs to `*.prev.STAMP` and runs six turns in one resumed session: (1) `propose_plan`, (2) `approve P-...` with the id read from the state, (3) `open_gate` with a wrong witness, (4) `status`, then `open_gate` with the real witness, (5) two parallel `write_file` calls, each with its own claim, (6) a built-in write of `c.txt`, which must be denied.

Claude Code runs `claude -p` with `--plugin-dir`, the plugin's `--settings`, `--setting-sources project` (your user hooks and plugins stay out) and `--allowedTools` set to the chr-gate tools. The Codex script installs the plugin from its marketplace, passes the fragment as `-c` overrides and `--dangerously-bypass-hook-trust` on every call, and stops with `pre-flight FAILED` before any model turn when the pre-flight fails.

`smoke_check` finds the one `events.jsonl` under `--state`, so it also runs on copied outputs. It prints PASS or FAIL per step and exits 0 only when all six pass (1 on a failure, 2 when the inputs cannot be checked); INFO lines are diagnostics only.

## Try it
- `uv tool install --editable chr-gate`, then from the repository root `bash scripts/smoke/smoke_claude_code.sh` or `bash scripts/smoke/smoke_codex.sh` (needs an authenticated host).
- Re-check the recorded run offline, from `chr-gate/`: `uv run --frozen --no-sync python -m chrgate.smoke_check --host codex --state docs/smoke-raw/codex/state --project docs/smoke-raw/codex/project` (or `--host claude-code` with the `claude-code` folders).
- Root frame: `bash scripts/smoke/probe_root_frame.sh setup`, the README's interactive steps, then `bash scripts/smoke/probe_root_frame.sh check`.
- The kit's offline tests run in `scripts/unit_suite.sh`.

## Cross-References
- [Claude Code plugin](plugin-claude-code.md), [Codex plugin](plugin-codex.md), [spike kit](scripts-spike.md) and [chr-gate hooks](chr-gate-hooks.md)

## Gotchas
- `smoke_codex.sh` installs the plugin into your Codex home and prints the removal commands at exit.
- Turn 1 tells the model to make no tool call in turn 2; without that the models acted inside the approval turn and step 3 failed.
- The checker needs exactly one `events.jsonl` under `--state`; a state folder holding two runs fails with exit 2.
