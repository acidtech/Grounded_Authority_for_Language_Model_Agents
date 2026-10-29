"""Append-only event log: events.jsonl in the state root.

One JSON line per core decision: time, frame, kind, outcome and an optional
ref (a work-order ref, plan id or gate opening id). The schema has no
free-form field, so no caller can write a plaintext witness into the log. The
smoke checker (T7a) reads it.
"""

from typing import Any

from chrgate.core.store import Store, utc_now

EVENTS = "events.jsonl"


def append(store: Store, *, frame: str | None, kind: str, outcome: str,
           ref: str | None = None) -> None:
    """Append one event; the caller holds store.lock()."""
    store.append_line(EVENTS, {"time": utc_now(), "frame": frame, "kind": kind,
                               "outcome": outcome, "ref": ref})


def read_all(store: Store) -> list[dict[str, Any]]:
    """Every event in append order."""
    with store.lock():
        return store.read_lines(EVENTS)
