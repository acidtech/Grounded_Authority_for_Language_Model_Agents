"""Proposed and active work orders, and the frames they govern.

propose(text) stores a proposal under a plan id (P- plus 8 hex). activate() is
the trusted principal path (UserPromptSubmit, T3): it makes exactly the
proposed text the principal work order with the next version, records the
approval, and clears the witness and gate of every frame that work order
governs (C32 Invariant 3; Appendix A activate_plan_auth). WorkOrder.ref is the
reference string wo:ID.vN that claims cite.

The frame registry (frames.json) lives here because activation must invalidate
governed frames, and the witness and gate layers build on this module. Frame
record: governs (work order id), epoch (int), witness_sha256, witness_binding
and gate. A frame is governed either by the principal work order or by a
delegated work order (delegation.py, stored in delegations.json); resolve()
and governing_work_order() serve both.
"""

import hashlib
import secrets
from dataclasses import dataclass
from typing import Any

from chrgate.core import events
from chrgate.core.store import Store, utc_now

PROPOSALS = "proposals.json"
WORK_ORDER = "workorder.json"
FRAMES = "frames.json"
DELEGATIONS = "delegations.json"


class UnknownPlan(LookupError):
    """activate() got a plan id that was never proposed."""


@dataclass(frozen=True)
class WorkOrder:
    id: str
    version: int
    text: str

    @property
    def ref(self) -> str:
        return f"wo:{self.id}.v{self.version}"


def _new_id(prefix: str, taken: dict[str, Any]) -> str:
    while True:
        candidate = prefix + secrets.token_hex(4)
        if candidate not in taken:
            return candidate


def propose(store: Store, text: str) -> str:
    """Store TEXT as a proposal and return its plan id."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("a work order proposal must be non-empty text")
    with store.lock():
        proposals = store.read(PROPOSALS, {})
        plan_id = _new_id("P-", proposals)
        proposals[plan_id] = {"text": text, "proposed_at": utc_now()}
        store.write(PROPOSALS, proposals)
        events.append(store, frame=None, kind="propose", outcome="stored", ref=plan_id)
    return plan_id


def activate(store: Store, plan_id: str, approval_prompt_text: str) -> WorkOrder:
    """Activate exactly the text proposed under PLAN_ID as the next version of
    the principal work order. Trusted principal path only."""
    if not isinstance(approval_prompt_text, str):
        raise TypeError("approval_prompt_text must be the principal's prompt text")
    with store.lock():
        proposals = store.read(PROPOSALS, {})
        if plan_id not in proposals:
            events.append(store, frame=None, kind="activate", outcome="refused-unknown-plan")
            raise UnknownPlan(f"unknown plan id {plan_id!r}; nothing activated")
        text = proposals[plan_id]["text"]
        current = store.read(WORK_ORDER, None)
        if current is None:
            wo = WorkOrder(id="WO-" + secrets.token_hex(4), version=1, text=text)
        else:
            wo = WorkOrder(id=current["id"], version=current["version"] + 1, text=text)
        now = utc_now()
        prompt_hash = hashlib.sha256(approval_prompt_text.encode("utf-8", "surrogatepass")).hexdigest()
        record = {"id": wo.id, "version": wo.version, "text": wo.text, "plan_id": plan_id,
                  "activated_at": now,
                  "approval": {"prompt_sha256": prompt_hash, "approved_at": now}}
        frames = store.read(FRAMES, {})
        for rec in frames.values():
            if rec["governs"] == wo.id:
                clear_witness(rec)
        store.write(WORK_ORDER, record)
        store.write(FRAMES, frames)
        events.append(store, frame=None, kind="activate", outcome="activated", ref=wo.ref)
    return wo


def active(store: Store) -> WorkOrder | None:
    """The active principal work order; the caller holds store.lock()."""
    record = store.read(WORK_ORDER, None)
    if record is None:
        return None
    return WorkOrder(id=record["id"], version=record["version"], text=record["text"])


def new_frame(governs: str) -> dict[str, Any]:
    """A fresh frame record governed by work order GOVERNS, epoch 1."""
    return {"governs": governs, "epoch": 1, "witness_sha256": None,
            "witness_binding": None, "gate": None}


def clear_witness(rec: dict[str, Any]) -> None:
    """Appendix A clear_witness: end the frame's witness and any open gate."""
    rec["witness_sha256"] = None
    rec["witness_binding"] = None
    rec["gate"] = None


def resolve(store: Store, wo_id: str) -> WorkOrder | None:
    """The live work order WO_ID: the active principal work order, or a
    delegated work order whose parent (by id and version) is itself live. None
    when no work order is active or a parent version was superseded, so a
    principal revision ends every delegation made under the earlier version
    (C32 Invariant 3). The caller holds store.lock()."""
    principal = active(store)
    if principal is None:
        return None
    if wo_id == principal.id:
        return principal
    record = store.read(DELEGATIONS, {}).get(wo_id)
    if record is None:
        raise RuntimeError(f"frame is governed by unknown work order {wo_id!r}")
    parent = resolve(store, record["parent_id"])
    if parent is None or parent.version != record["parent_version"]:
        return None
    return WorkOrder(id=record["id"], version=record["version"], text=record["text"])


def governing_work_order(store: Store, rec: dict[str, Any]) -> WorkOrder | None:
    """The live work order governing frame record REC (principal or
    delegated), or None (see resolve); the caller holds store.lock()."""
    return resolve(store, rec["governs"])
