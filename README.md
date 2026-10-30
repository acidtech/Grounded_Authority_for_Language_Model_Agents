# Grounded Authority for Language-Model Agents

Context provenance, warning feedback and enforced action gates for
language-model workers. This repository holds the design, an implementation
guide, the essay that argues for the approach, and an example gate for two
coding-agent hosts.

Video overview: [The Wrong Defendant: AI Agents, Authority Drift, and the Work
Order Nobody Signed](https://youtu.be/ObYBY2l19e4)

## Contents

- [Grounded_Authority_for_Language_Model_Agents_C32.md](Grounded_Authority_for_Language_Model_Agents_C32.md)
  (C32): the engineering reference. It defines the mechanisms and the gate
  protocol (C32 Appendix A).
- [Implementing_a_Grounded_Authority_Harness.md](Implementing_a_Grounded_Authority_Harness.md):
  the implementation guide. It builds a harness from C32 in stages.
- [The_Wrong_Defendant_AI_Governance_Failure_v2_2.md](The_Wrong_Defendant_AI_Governance_Failure_v2_2.md):
  the rationale essay (working paper, version 2.2).
- [chr-gate/](chr-gate/README.md): the example CHR gate for Claude Code and
  Codex, built from C32 Appendix A and the guide: an MCP server
  (`chrgate-mcp`), the host hooks (`chrgate-hook`) and `chrgate-setup`.
  - [plugins/claude-code/](plugins/claude-code/) and
    [plugins/codex/](plugins/codex/): the two host plugins.
  - [scripts/unit_suite.sh](scripts/unit_suite.sh): the test suite,
    [scripts/smoke/](scripts/smoke/README.md): the live smoke kit, and
    [scripts/spike/](scripts/spike/README.md): the host measurement kit.

The documents are the source; chr-gate is one example of them in front of
hosts that already exist, with its limits stated in its README.

## Quick start

Requirements: Linux with bubblewrap, git, Python 3.12 or newer, and uv.

Follow [Install and try](chr-gate/README.md#install-and-try) in
chr-gate's README. To run the tests, from the repository root:

    scripts/unit_suite.sh

Changes are listed in [CHANGELOG.md](CHANGELOG.md); see
[CONTRIBUTING.md](CONTRIBUTING.md) before opening an issue.

## License

This repository is source-available and non-commercial.

- The code (`chr-gate/`, `plugins/` and `scripts/`) is licensed under the
  PolyForm Noncommercial License 1.0.0.
- The three documents above are licensed under CC BY-NC-ND 4.0, with an
  additional permission for non-commercial translations.
- Any commercial use requires a separately negotiated license; see
  [COMMERCIAL-LICENSE.md](COMMERCIAL-LICENSE.md).
- Patent applications are pending.

The terms are in [LICENSE.md](LICENSE.md), with the full license texts in
[LICENSES/](LICENSES/).
