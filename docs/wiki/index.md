# chr-gate wiki

> Subsystem pages for people testing the example harnesses: the chr-gate gate for Claude Code and Codex, its two host plugins and its test kits.

## Pages
- [chr-gate core](chr-gate-core.md): work orders, witnesses, the action gate, claims, citations, delegation and testimony
- [chr-gate server](chr-gate-server.md): `chrgate-mcp`, the only effect path, and `chrgate-setup`
- [chr-gate hooks](chr-gate-hooks.md): `chrgate-hook`, the one hook both hosts run
- [Claude Code plugin](plugin-claude-code.md): `plugins/claude-code/`
- [Codex plugin](plugin-codex.md): `plugins/codex/`
- [Live smoke kit](scripts-smoke.md): scripted six-turn sessions and their checker
- [Host measurement spike kit](scripts-spike.md): the probes behind the design

The project overview is the [repository README](../../README.md); install steps and stated limits are in the [chr-gate README](../../chr-gate/README.md).

## Requirements
Linux or WSL2 with bubblewrap, git, uv and Python 3.12 or newer. Live sessions also need an authenticated `claude` or `codex`.

## Run the suite
From the repository root: `bash scripts/unit_suite.sh`. It runs `chr-gate/tests` and the offline tests of the smoke and spike kits; no host is needed.

## Where a tester starts
- Claude Code: `uv tool install --editable /path/to/repo/chr-gate`, `chrgate-setup` in a scratch git project, then Try it on the [Claude Code plugin](plugin-claude-code.md) page.
- Codex: the same install and setup, then Try it on the [Codex plugin](plugin-codex.md) page (merge the config fragment, trust the hooks).
- Both hosts, scripted: the [live smoke kit](scripts-smoke.md).
- How the gate decides: [core](chr-gate-core.md), then [server](chr-gate-server.md), then [hooks](chr-gate-hooks.md).

## Gotchas
- Never govern this repository itself: chr-gate refuses its own source tree.
- Every write goes through a user-approved work order: reply with exactly `approve P-xxxxxxxx` to activate one.
