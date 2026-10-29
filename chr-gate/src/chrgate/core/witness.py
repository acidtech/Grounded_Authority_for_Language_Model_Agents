"""The witness issuer (C32 Invariant 2; Appendix A read_active_authority).

WitnessIssuer lives in the MCP server process and is the ONLY witness issuer.
read_work_order(frame) returns the governing work order's full text and the
frame's witness: 'wit:' plus 32 hex characters (128 random bits, never a record
id). Within one binding (work order id, version, frame id, epoch) every read
returns the SAME witness: the plaintext stays in this object's memory, and disk
holds only sha256(witness) and the binding. An issuer holding no plaintext for
the current binding (first read, or a new issuer after a server restart) mints
a new witness and replaces the stored hash, which invalidates the earlier one.
A read also cancels any pending open gate of that frame (Appendix A line 1036).
"""

import hashlib
import secrets
from dataclasses import dataclass
from typing import Any

from chrgate.core import events, workorder
from chrgate.core.store import Store

WITNESS_PREFIX = "wit:"


class NoActiveWorkOrder(LookupError):
    """No approved work order is active for the frame."""


@dataclass(frozen=True)
class WorkOrderRead:
    ref: str
    text: str
    witness: str


def new_witness() -> str:
    return WITNESS_PREFIX + secrets.token_hex(16)


def witness_sha256(witness: str) -> str:
    return hashlib.sha256(witness.encode("utf-8", "surrogatepass")).hexdigest()


def binding(wo: workorder.WorkOrder, frame_id: str, epoch: int) -> dict[str, Any]:
    """Appendix A binding: (work order id, version, frame id, epoch)."""
    return {"work_order": wo.id, "version": wo.version, "frame": frame_id, "epoch": epoch}


def check_frame_id(frame_id: str) -> None:
    if not isinstance(frame_id, str) or not frame_id:
        raise ValueError(f"frame id must be a non-empty string, got {frame_id!r}")


class WitnessIssuer:
    """Issues and remembers one witness per frame binding (in memory only)."""

    def __init__(self, store: Store) -> None:
        self.store = store
        self._plaintext: dict[str, tuple[dict[str, Any], str]] = {}

    def read_work_order(self, frame_id: str) -> WorkOrderRead:
        """Deliver the frame's work order text and witness; cancel its gate."""
        check_frame_id(frame_id)
        with self.store.lock():
            frames = self.store.read(workorder.FRAMES, {})
            rec = frames.get(frame_id)
            if rec is None:
                wo = workorder.active(self.store)
            else:
                wo = workorder.governing_work_order(self.store, rec)
            if wo is None:
                events.append(self.store, frame=frame_id, kind="read_work_order",
                              outcome="refused-no-work-order")
                raise NoActiveWorkOrder("no approved work order is active; propose one "
                                        "and ask the principal to approve it")
            if rec is None:
                rec = frames[frame_id] = workorder.new_frame(wo.id)
            current = binding(wo, frame_id, rec["epoch"])
            held = self._plaintext.get(frame_id)
            if (held is not None and held[0] == current
                    and rec["witness_binding"] == current
                    and rec["witness_sha256"] == witness_sha256(held[1])):
                witness, outcome = held[1], "reused"
            else:
                witness, outcome = new_witness(), "issued"
                rec["witness_sha256"] = witness_sha256(witness)
                rec["witness_binding"] = current
            rec["gate"] = None
            self.store.write(workorder.FRAMES, frames)
            self._plaintext[frame_id] = (current, witness)
            events.append(self.store, frame=frame_id, kind="read_work_order",
                          outcome=outcome, ref=wo.ref)
        return WorkOrderRead(ref=wo.ref, text=wo.text, witness=witness)
