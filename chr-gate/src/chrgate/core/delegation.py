"""Delegated work orders for consequential subagents (design point 5).

delegate(caller, claim, text) runs under the caller's current gate and a
valid claim; it records a child work order in delegations.json (keyed by its
id: text, parent reference, caller frame, opening_id, time, claim, the
principal approval it descends from) and returns a delegation id and the
child reference. The parent puts the delegation id in the child's launch
prompt; the child presents it on its first work-order read, and the server
calls bind_child(child_frame, delegation_id) before read_work_order, so the
child gets its own witness for its own work order. chain(ref) walks child ->
caller work order -> principal approval. Narrowing is claimed, not checked.
A delegated work order lives only while its parent version is current
(workorder.resolve).
"""

import secrets
from dataclasses import dataclass
from typing import Any

from chrgate.core import claims, events, workorder
from chrgate.core.claims import Refused
from chrgate.core.store import Store, utc_now
from chrgate.core.witness import check_frame_id

DELEGATED_PREFIX = "DW-"
DELEGATION_PREFIX = "D-"
UNKNOWN_DELEGATION = "unknown-delegation"
BOUND_ELSEWHERE = "delegation-bound-elsewhere"
FRAME_GOVERNED_ELSEWHERE = "frame-governed-elsewhere"
NOT_LIVE = "work-order-not-live"


@dataclass(frozen=True)
class Delegation:
    delegation_id: str
    ref: str


@dataclass(frozen=True)
class Link:
    kind: str  # "delegated", "principal" or "approval"
    ref: str
    text: str | None = None
    caller_frame: str | None = None
    opening_id: str | None = None
    created_at: str | None = None
    claim: str | None = None
    approval: dict[str, Any] | None = None


def _ref(wo_id: str, version: int) -> str:
    return f"wo:{wo_id}.v{version}"


def delegate(store: Store, caller_frame: str, claim: str, work_order_text: str) -> Delegation:
    """Record a child work order under CALLER_FRAME's current gate and claim."""
    check_frame_id(caller_frame)
    if not isinstance(work_order_text, str) or not work_order_text.strip():
        raise ValueError("a delegated work order must be non-empty text")
    with store.lock():
        frames = store.read(workorder.FRAMES, {})
        parent, current = claims.authorize(store, frames, caller_frame, "delegate",
                                           {"claim": claim, "work_order": work_order_text})
        delegated = store.read(workorder.DELEGATIONS, {})
        wo_id = workorder._new_id(DELEGATED_PREFIX, delegated)
        taken = {r["delegation_id"] for r in delegated.values()}
        delegation_id = DELEGATION_PREFIX + secrets.token_hex(8)
        while delegation_id in taken:
            delegation_id = DELEGATION_PREFIX + secrets.token_hex(8)
        principal = store.read(workorder.WORK_ORDER, None)
        delegated[wo_id] = {
            "id": wo_id, "version": 1, "text": work_order_text,
            "parent_id": parent.id, "parent_version": parent.version, "parent_ref": parent.ref,
            "caller_frame": caller_frame, "opening_id": current["opening_id"],
            "created_at": utc_now(), "claim": claim, "delegation_id": delegation_id,
            "child_frame": None, "bound_at": None,
            "principal": {"ref": _ref(principal["id"], principal["version"]),
                          "plan_id": principal["plan_id"], "approval": principal["approval"]}}
        store.write(workorder.DELEGATIONS, delegated)
        ref = _ref(wo_id, 1)
        events.append(store, frame=caller_frame, kind="delegate", outcome="delegated", ref=ref)
    return Delegation(delegation_id=delegation_id, ref=ref)


def bind_child(store: Store, child_frame_id: str, delegation_id: str) -> str:
    """Make the work order of DELEGATION_ID govern CHILD_FRAME_ID; returns its
    reference. Binding is one frame per delegation and idempotent for it."""
    check_frame_id(child_frame_id)
    with store.lock():
        delegated = store.read(workorder.DELEGATIONS, {})
        record = next((r for r in delegated.values()
                       if r["delegation_id"] == delegation_id), None)

        def refuse(code: str, message: str) -> Refused:
            events.append(store, frame=child_frame_id, kind="bind_child", outcome=f"refused-{code}")
            return Refused(code, message)

        if record is None:
            raise refuse(UNKNOWN_DELEGATION, "unknown delegation id")
        if record["child_frame"] not in (None, child_frame_id):
            raise refuse(BOUND_ELSEWHERE, "this delegation is bound to another frame")
        frames = store.read(workorder.FRAMES, {})
        rec = frames.get(child_frame_id)
        if rec is not None and rec["governs"] != record["id"]:
            raise refuse(FRAME_GOVERNED_ELSEWHERE, "this frame is governed by another work order")
        wo = workorder.resolve(store, record["id"])
        if wo is None:
            raise refuse(NOT_LIVE, "the delegating work order version is no longer current")
        if rec is None:
            frames[child_frame_id] = workorder.new_frame(record["id"])
            store.write(workorder.FRAMES, frames)
        if record["child_frame"] is None:
            record["child_frame"] = child_frame_id
            record["bound_at"] = utc_now()
            store.write(workorder.DELEGATIONS, delegated)
        events.append(store, frame=child_frame_id, kind="bind_child", outcome="bound", ref=wo.ref)
    return wo.ref


def chain(store: Store, ref: str) -> list[Link]:
    """Authority chain of REF: delegated links child first, then the principal
    work order and its approval. LookupError for an unknown reference."""
    m = claims.REF_RE.fullmatch(ref) if isinstance(ref, str) else None
    if m is None:
        raise LookupError(f"not a work order reference: {ref!r}")
    wo_id, version = m.group(1), int(m.group(2))
    with store.lock():
        delegated = store.read(workorder.DELEGATIONS, {})
        current_principal = store.read(workorder.WORK_ORDER, None)
    links: list[Link] = []
    principal = None
    while wo_id in delegated:
        r = delegated[wo_id]
        if r["version"] != version:
            raise LookupError(f"unknown work order reference {_ref(wo_id, version)!r}")
        links.append(Link(kind="delegated", ref=_ref(wo_id, version), text=r["text"],
                          caller_frame=r["caller_frame"], opening_id=r["opening_id"],
                          created_at=r["created_at"], claim=r["claim"]))
        principal = r["principal"]
        wo_id, version = r["parent_id"], r["parent_version"]
    if principal is None and current_principal is not None:
        principal = {"ref": _ref(current_principal["id"], current_principal["version"]),
                     "plan_id": current_principal["plan_id"],
                     "approval": current_principal["approval"]}
    if principal is None or principal["ref"] != _ref(wo_id, version):
        raise LookupError(f"unknown work order reference {_ref(wo_id, version)!r}")
    links.append(Link(kind="principal", ref=principal["ref"]))
    links.append(Link(kind="approval", ref=principal["ref"],
                      approval={"plan_id": principal["plan_id"], **principal["approval"]}))
    return links
