"""T4: repository hygiene.

- scratch output (tmp/) and Python bytecode (__pycache__/) are git-ignored;
- scripts/unit_suite.sh collects the tests of scripts/smoke and scripts/spike,
  read from the script's own pytest command line, never from a hand list.
"""

import shlex
import subprocess
from pathlib import Path

import pytest

CHR_GATE = Path(__file__).resolve().parents[1]
REPO = CHR_GATE.parent
UNIT_SUITE = REPO / "scripts" / "unit_suite.sh"

IGNORED = ("tmp/x", "scripts/smoke/__pycache__/m.cpython-312.pyc")
SCRIPT_TEST_DIRS = ("scripts/smoke", "scripts/spike")
# pytest options in unit_suite.sh whose value is the next token, not a path.
OPTIONS_WITH_VALUE = {"-p", "-k", "-m", "-c", "-o", "--basetemp", "--rootdir", "--ignore", "--deselect"}


def _git(*args: str) -> int:
    return subprocess.run(["git", "-C", str(REPO), *args], capture_output=True).returncode


def _suite_paths() -> list[Path]:
    commands = []
    for line in UNIT_SUITE.read_text().splitlines():
        tokens = shlex.split(line, comments=True)
        if "pytest" in tokens:
            commands.append(tokens[tokens.index("pytest") + 1 :])
    assert len(commands) == 1, f"expected one pytest command line in {UNIT_SUITE}, found {len(commands)}"
    paths, skip_next = [], False
    for token in commands[0]:
        if skip_next:
            skip_next = False
        elif token.startswith("-"):
            skip_next = token in OPTIONS_WITH_VALUE
        else:
            paths.append((CHR_GATE / token).resolve())
    return paths


def test_scratch_and_bytecode_ignored():
    if _git("rev-parse", "--is-inside-work-tree") != 0:
        pytest.skip(f"{REPO} is not a git work tree")
    not_ignored = [p for p in IGNORED if _git("check-ignore", "-q", "--no-index", p) != 0]
    assert not not_ignored, f"not ignored by {REPO / '.gitignore'}: {not_ignored}"


def test_unit_suite_collects_script_tests():
    paths = _suite_paths()
    for rel in SCRIPT_TEST_DIRS:
        files = sorted((REPO / rel).glob("test_*.py"))
        assert files, f"no test_*.py under {rel}"
        missed = [f.name for f in files if not any(f.resolve().is_relative_to(p) for p in paths)]
        assert not missed, f"{UNIT_SUITE} paths {[str(p) for p in paths]} miss {rel}: {missed}"
