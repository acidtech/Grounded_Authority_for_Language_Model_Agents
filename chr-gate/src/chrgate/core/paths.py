"""Where the gate keeps its trusted state for one project.

State root: ${XDG_STATE_HOME:-~/.local/state}/chr-gate/PROJECTKEY/, where
PROJECTKEY is the first 16 hex characters of sha256 of the realpath of the
project root. The project root is CHR_GATE_PROJECT when set, else the process
working directory. The state root lives outside the project tree.
"""

import hashlib
import os
from pathlib import Path

PROJECT_ENV = "CHR_GATE_PROJECT"
STATE_DIR_NAME = "chr-gate"


def project_root() -> Path:
    """Realpath of the governed project: CHR_GATE_PROJECT, else the cwd."""
    configured = os.environ.get(PROJECT_ENV)
    return Path(os.path.realpath(configured if configured else os.getcwd()))


def project_key(root: str | os.PathLike[str]) -> str:
    """First 16 hex of sha256 of the realpath of ROOT."""
    return hashlib.sha256(os.fsencode(os.path.realpath(root))).hexdigest()[:16]


def state_base() -> Path:
    """${XDG_STATE_HOME:-~/.local/state}"""
    xdg = os.environ.get("XDG_STATE_HOME")
    return Path(xdg) if xdg else Path.home() / ".local" / "state"


def state_root(root: str | os.PathLike[str] | None = None) -> Path:
    """State root of project ROOT (default: project_root())."""
    project = project_root() if root is None else Path(root)
    return state_base() / STATE_DIR_NAME / project_key(project)
