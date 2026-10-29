"""Regression test for fragment_pairs.py (T5b): it prints the bare -c pairs
smoke_codex.sh passes for plugins/codex/config/chr-gate.toml.

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
