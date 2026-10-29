"""Locked, atomic JSON state under one state root.

Every core operation runs inside Store.lock(), an exclusive fcntl lock on the
state root's .lock file (C32 Appendix A serialized_frame_state), so the MCP
server, hooks and tests serialize across processes and threads. JSON files are
replaced atomically (temp file in the same directory, fsync, os.replace), so no
reader ever sees a partial file. Core operations make every check before their
first write, so a failed check changes no state. events.jsonl (events.py) is
the append-only audit log, not state.
"""

import contextlib
import fcntl
import json
import os
import tempfile
import threading
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from chrgate.core.paths import state_root

LOCK_NAME = ".lock"


class LockNotHeld(RuntimeError):
    """A state file was touched outside Store.lock()."""


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


class Store:
    """JSON state files under ROOT; read and write only inside lock()."""

    def __init__(self, root: str | os.PathLike[str]) -> None:
        self.root = Path(root)
        self._local = threading.local()

    @classmethod
    def for_project(cls, project: str | os.PathLike[str] | None = None) -> "Store":
        return cls(state_root(project))

    def _is_held(self) -> bool:
        return getattr(self._local, "held", False)

    @contextlib.contextmanager
    def lock(self) -> Iterator["Store"]:
        """Exclusive lock on the state root; not reentrant."""
        if self._is_held():
            raise RuntimeError("Store.lock() is not reentrant; this thread already holds it")
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        fd = os.open(self.root / LOCK_NAME, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            self._local.held = True
            try:
                yield self
            finally:
                self._local.held = False
        finally:
            os.close(fd)  # closing the descriptor releases the flock

    def _path(self, name: str) -> Path:
        if not self._is_held():
            raise LockNotHeld(f"state file {name!r} touched outside Store.lock()")
        if not name or "/" in name or name.startswith("."):
            raise ValueError(f"invalid state file name {name!r}")
        return self.root / name

    def read(self, name: str, default: Any) -> Any:
        """Parsed JSON of NAME, or DEFAULT when the file does not exist yet."""
        path = self._path(name)
        try:
            raw = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return default
        return json.loads(raw)

    def write(self, name: str, data: Any) -> None:
        """Replace NAME atomically with DATA as JSON."""
        path = self._path(name)
        fd, tmp = tempfile.mkstemp(prefix=f".{name}.", suffix=".tmp", dir=self.root)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2, sort_keys=True)
                fh.write("\n")
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, path)
        except BaseException:
            with contextlib.suppress(FileNotFoundError):
                os.unlink(tmp)
            raise

    def append_line(self, name: str, record: Any) -> None:
        """Append RECORD to NAME as one JSON line."""
        path = self._path(name)
        line = json.dumps(record, sort_keys=True) + "\n"
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(line)
            fh.flush()
            os.fsync(fh.fileno())

    def read_lines(self, name: str) -> list[Any]:
        """Parsed JSON lines of NAME, [] when the file does not exist yet."""
        path = self._path(name)
        try:
            raw = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return []
        return [json.loads(line) for line in raw.splitlines()]
