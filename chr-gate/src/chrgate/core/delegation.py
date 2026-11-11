"""Delegated work orders for consequential subagents (design point 5).

delegate(caller, claim, text) runs under the caller's current gate and a
valid claim; it records a child work order in delegations.json (keyed by its
id: text, parent reference, caller frame, caller session, opening_id, time,
claim, the principal approval it descends from, and delegation_sha256) and
returns a delegation id and the child reference. Only the sha256 of the
delegation id is stored, as for the witness; find() compares hashes, and a
record without delegation_sha256 never matches. The parent puts the
delegation id in the child's launch prompt; the child presents it on its
first work-order read, and the server
calls bind_child(child_frame, delegation_id) before read_work_order, so the
child gets its own witness for its own work order. chain(ref) walks child ->
caller work order -> principal approval. inherited(wo_id) lists the work
orders a delegated order inherits its bounds from, root first, and
work_order_section renders them verbatim before the child's own task text
(F12). Narrowing is claimed, not checked.
A delegated work order lives only while its parent version is current
(workorder.resolve).
"""

import hashlib
import hmac
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
INHERITED_RULE = ("Your task is limited by every inherited work order above. Where they "
                  "disagree, the inherited order governs: stop and report to your assigner.")


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


def delegation_sha256(delegation_id: str) -> str:
    return hashlib.sha256(delegation_id.encode("utf-8", "surrogatepass")).hexdigest()


def find(delegated: dict[str, Any], delegation_id: str) -> dict[str, Any] | None:
    """The record of DELEGATION_ID in DELEGATED, matched by delegation_sha256; a
    record without one (state from before hashing) never matches, fail closed."""
    digest = delegation_sha256(delegation_id)
    return next((r for r in delegated.values() if "delegation_sha256" in r
                 and hmac.compare_digest(r["delegation_sha256"], digest)), None)


def delegate(store: Store, caller_frame: str, claim: str, work_order_text: str,
             caller_session: str | None = None) -> Delegation:
    """Record a child work order under CALLER_FRAME's current gate and claim.
    CALLER_SESSION is the Claude Code session of the caller (None on Codex)."""
    check_frame_id(caller_frame)
    if not isinstance(work_order_text, str) or not work_order_text.strip():
        raise ValueError("a delegated work order must be non-empty text")
    with store.lock():
        frames = store.read(workorder.FRAMES, {})
        parent, current = claims.authorize(store, frames, caller_frame, "delegate",
                                           {"claim": claim, "work_order": work_order_text})
        delegated = store.read(workorder.DELEGATIONS, {})
        wo_id = workorder._new_id(DELEGATED_PREFIX, delegated)
        delegation_id = DELEGATION_PREFIX + secrets.token_hex(8)
        while find(delegated, delegation_id) is not None:
            delegation_id = DELEGATION_PREFIX + secrets.token_hex(8)
        principal = store.read(workorder.WORK_ORDER, None)
        delegated[wo_id] = {
            "id": wo_id, "version": 1, "text": work_order_text,
            "parent_id": parent.id, "parent_version": parent.version, "parent_ref": parent.ref,
            "caller_frame": caller_frame, "caller_session": caller_session,
            "opening_id": current["opening_id"], "created_at": utc_now(), "claim": claim,
            "delegation_sha256": delegation_sha256(delegation_id),
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
        record = find(delegated, delegation_id)

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


def inherited(store: Store, wo_id: str) -> list[workorder.WorkOrder]:
    """The work orders WO_ID inherits its bounds from, root first: the principal
    (user-approved) order, then each delegated order down to WO_ID's own
    assigner; [] for the principal itself. Root first because hosts truncate a
    long result from its end, so the root bound is the last to go. The caller
    holds store.lock() and has seen WO_ID resolve (workorder.resolve), so every
    parent is live at its recorded parent_version; RuntimeError otherwise."""
    if not wo_id.startswith(DELEGATED_PREFIX):
        return []
    delegated = store.read(workorder.DELEGATIONS, {})
    record = delegated.get(wo_id)
    if record is None:
        raise RuntimeError(f"unknown delegated work order {wo_id!r}")
    bounds: list[workorder.WorkOrder] = []
    while record["parent_id"].startswith(DELEGATED_PREFIX):
        parent = delegated.get(record["parent_id"])
        if parent is None or parent["version"] != record["parent_version"]:
            raise RuntimeError(f"{_ref(record['parent_id'], record['parent_version'])} "
                               "is not live")
        record = parent
        bounds.append(workorder.WorkOrder(id=record["id"], version=record["version"],
                                          text=record["text"]))
    principal = workorder.active(store)
    if principal is None or principal.ref != _ref(record["parent_id"], record["parent_version"]):
        raise RuntimeError(f"{_ref(record['parent_id'], record['parent_version'])} is not live")
    bounds.append(principal)
    return bounds[::-1]


def work_order_section(store: Store, wo_id: str, text: str) -> str:
    """The work order block that status, open_gate and compaction deliver for
    WO_ID with its TEXT: for the principal '--- work order text ---' and TEXT;
    for a delegated order every inherited bound verbatim, the rule that they
    govern, then TEXT. The caller holds store.lock() (see inherited)."""
    bounds = inherited(store, wo_id)
    if not bounds:
        return f"--- work order text ---\n{text}"
    parts = [f"--- inherited bounds: {wo.ref} "
             f"({'approved by the user' if i == 0 else 'written by its assigner'}) ---\n{wo.text}"
             for i, wo in enumerate(bounds)]
    return "\n".join([*parts, INHERITED_RULE,
                      f"--- work order text (your task, written by your assigner) ---\n{text}"])
