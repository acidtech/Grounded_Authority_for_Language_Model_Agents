"""Shared fixtures. Every test runs against a tmp XDG_STATE_HOME, HOME and
project root, never the real ~/.local/state, ~/.claude or ~/.codex."""

from pathlib import Path

import pytest

from chrgate.core import workorder
from chrgate.core.store import Store
from chrgate.core.witness import WitnessIssuer

# CRLF, tabs, trailing spaces and non-ASCII: activation must keep every byte.
WORK_ORDER_TEXT = "Fix the parser.\r\n\tKeep tabs and trailing spaces   \nUnicode: é 中 \U0001f600\n"


@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch):
    for name in ("state", "home", "project"):
        (tmp_path / name).mkdir()
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CHR_GATE_PROJECT", str(tmp_path / "project"))
    return tmp_path


@pytest.fixture
def store(isolated_env):
    s = Store.for_project()
    assert s.root.is_relative_to(isolated_env / "state")
    return s


@pytest.fixture
def wo_text():
    return WORK_ORDER_TEXT


@pytest.fixture
def active_wo(store, wo_text):
    plan_id = workorder.propose(store, wo_text)
    return workorder.activate(store, plan_id, f"approve {plan_id}")


@pytest.fixture
def issuer(store, active_wo):
    return WitnessIssuer(store)


def _snapshot(root: Path) -> dict[str, bytes]:
    """Bytes of every state file under ROOT; events.jsonl is the audit log."""
    return {str(p.relative_to(root)): p.read_bytes()
            for p in sorted(root.rglob("*")) if p.is_file() and p.name != "events.jsonl"}


@pytest.fixture
def state_snapshot():
    return _snapshot
