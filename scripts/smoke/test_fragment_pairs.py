"""Regression test for fragment_pairs.py (T5b): it prints the bare -c pairs
smoke_codex.sh passes for plugins/codex/config/chr-gate.toml, and smoke_codex.sh
passes those bare pairs (not the -c expanded C_ARGS) to codex_preflight.py.

Run as: cd chr-gate && uv run --frozen --no-sync pytest -q -p no:cacheprovider \
../scripts/smoke/test_codex_preflight.py ../scripts/smoke/test_fragment_pairs.py
"""
import subprocess
import sys
from pathlib import Path

SMOKE_DIR = Path(__file__).resolve().parent
PLUGIN = SMOKE_DIR.parents[1] / "plugins" / "codex"
FRAGMENT_PAIRS = SMOKE_DIR / "fragment_pairs.py"
# What the pairs code embedded in smoke_codex.sh printed for
# plugins/codex/config/chr-gate.toml before the move (pinned base
# refs/pins/chr-gate-plugins-T5b-codex-plugin-mcp).
SMOKE_PAIRS = b'sandbox_mode="read-only"\0features.shell_tool=false\0'


def test_fragment_pairs_matches_smoke():
    proc = subprocess.run([sys.executable, str(FRAGMENT_PAIRS), str(PLUGIN / "config" / "chr-gate.toml")],
                          capture_output=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == SMOKE_PAIRS
    call = '"${PY[@]}" "$REPO/scripts/smoke/fragment_pairs.py" "$PLUGIN/config/chr-gate.toml"'
    text = (SMOKE_DIR / "smoke_codex.sh").read_text()
    assert call in text
    assert "tomllib" not in text


PREFLIGHT_CALL = '"$REPO/scripts/smoke/codex_preflight.py" "$PROJ" "${PAIRS[@]}"'


def _preflight_call_problems(text):
    """Problems with smoke_codex.sh's codex_preflight.py call; empty when good."""
    calls = [line for line in text.splitlines()
             if "codex_preflight.py" in line and not line.lstrip().startswith("#")]
    if len(calls) != 1:
        return [f"expected 1 codex_preflight.py call line, found {len(calls)}: {calls}"]
    problems = []
    if PREFLIGHT_CALL not in calls[0]:
        problems.append(f"call line lacks {PREFLIGHT_CALL}: {calls[0]}")
    if "C_ARGS" in calls[0]:
        problems.append(f"call line passes C_ARGS: {calls[0]}")
    return problems


def test_preflight_call_passes_bare_pairs():
    text = (SMOKE_DIR / "smoke_codex.sh").read_text()
    assert _preflight_call_problems(text) == []
    # Self-check: the helper flags a call switched to C_ARGS and a deleted call.
    c_args = text.replace(PREFLIGHT_CALL, PREFLIGHT_CALL.replace('"${PAIRS[@]}"', '"${C_ARGS[@]}"'))
    assert c_args != text
    assert _preflight_call_problems(c_args)
    deleted = "\n".join(line for line in text.splitlines() if PREFLIGHT_CALL not in line)
    assert deleted != text
    assert _preflight_call_problems(deleted)
