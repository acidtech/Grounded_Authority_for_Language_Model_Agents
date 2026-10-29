"""Testimony (design point 4: testify is consequential).

record(frame, claim, text) runs under the frame's current gate and a valid
claim, and appends one line to testimony.jsonl: time, frame, work order
reference, gate opening_id, claim and text. The file is append-only; nothing
in the core rewrites it.
"""

from typing import Any

from chrgate.core import claims, events, workorder
from chrgate.core.store import Store, utc_now
from chrgate.core.witness import check_frame_id

TESTIMONY = "testimony.jsonl"


def record(store: Store, frame_id: str, claim: str, text: str) -> dict[str, Any]:
    """Append FRAME_ID's testimony TEXT under its current gate; returns the entry."""
    check_frame_id(frame_id)
    if not isinstance(text, str) or not text.strip():
        raise ValueError("testimony must be non-empty text")
    with store.lock():
        frames = store.read(workorder.FRAMES, {})
        wo, current = claims.authorize(store, frames, frame_id, "testify",
                                       {"claim": claim, "text": text})
        entry = {"time": utc_now(), "frame": frame_id, "work_order": wo.ref,
                 "opening_id": current["opening_id"], "claim": claim, "text": text}
        store.append_line(TESTIMONY, entry)
        events.append(store, frame=frame_id, kind="testify", outcome="recorded",
                      ref=current["opening_id"])
    return entry


def read_all(store: Store) -> list[dict[str, Any]]:
    """Every testimony entry in append order."""
    with store.lock():
        return store.read_lines(TESTIMONY)
