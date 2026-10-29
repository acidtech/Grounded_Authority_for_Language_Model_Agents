"""Claim checks for consequential tools (design point 3).

Every consequential tool's FIRST argument is a required claim. check_claim
checks presence and citation, never truth: the claim must be a non-empty
string that contains the reference wo:ID.vN of the work order governing the
calling frame (the delegated work order for a child frame). Each refusal has
its own code. authorize() is the in-lock entry for consequential core
operations (delegate, testify): a current gate, then a valid claim.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from chrgate.core import events, gate, workorder
from chrgate.core.store import Store
from chrgate.core.witness import check_frame_id

CLAIM_KEY = "claim"
ACCEPTED = "accepted"
FIRST_KEY_NOT_CLAIM = "first-key-not-claim"
CLAIM_MISSING = "claim-missing"
CLAIM_EMPTY = "claim-empty-or-not-string"
NO_WORK_ORDER = "no-work-order"
REFERENCE_MISSING = "reference-missing"
STALE_VERSION = "stale-version"
GATE_NOT_CURRENT = "gate-not-current"
REF_RE = re.compile(r"(?<![A-Za-z0-9])wo:([A-Za-z0-9-]+)\.v([0-9]+)(?![0-9])")


class Refused(PermissionError):
    """A consequential core operation was refused; nothing changed."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


@dataclass(frozen=True)
class ClaimResult:
    ok: bool
    code: str
    message: str
    ref: str | None = None  # the governing reference, for the audit log only


def _governing(store: Store, frames: dict[str, Any], frame_id: str
               ) -> workorder.WorkOrder | None:
    rec = frames.get(frame_id)
    return workorder.active(store) if rec is None else workorder.governing_work_order(store, rec)


def _check(store: Store, frames: dict[str, Any], frame_id: str, tool: str,
           raw_arguments: Mapping[str, Any]) -> ClaimResult:
    if not isinstance(tool, str) or not tool:
        raise ValueError(f"tool must be a non-empty string, got {tool!r}")
    if not isinstance(raw_arguments, Mapping):
        raise TypeError("raw_arguments must be the argument mapping in received order")
    if CLAIM_KEY not in raw_arguments:
        return ClaimResult(False, CLAIM_MISSING, f"{tool}: a claim argument is required")
    if next(iter(raw_arguments)) != CLAIM_KEY:
        return ClaimResult(False, FIRST_KEY_NOT_CLAIM,
                           f"{tool}: claim must be the first argument")
    claim = raw_arguments[CLAIM_KEY]
    if not isinstance(claim, str) or not claim.strip():
        return ClaimResult(False, CLAIM_EMPTY, f"{tool}: claim must be non-empty text")
    wo = _governing(store, frames, frame_id)
    if wo is None:
        return ClaimResult(False, NO_WORK_ORDER,
                           f"{tool}: no approved work order governs this frame")
    cited = {(wo_id, int(version)) for wo_id, version in REF_RE.findall(claim)}
    if (wo.id, wo.version) in cited:
        return ClaimResult(True, ACCEPTED, f"{tool}: claim accepted", wo.ref)
    if any(wo_id == wo.id for wo_id, _ in cited):
        return ClaimResult(False, STALE_VERSION, f"{tool}: the claim cites another version "
                           "of your work order; read your work order", wo.ref)
    return ClaimResult(False, REFERENCE_MISSING, f"{tool}: the claim must cite your work "
                       "order reference; read your work order", wo.ref)


def check_claim(store: Store, frame_id: str, tool: str,
                raw_arguments: Mapping[str, Any]) -> ClaimResult:
    """Check the claim in RAW_ARGUMENTS (received order) of TOOL for FRAME_ID."""
    check_frame_id(frame_id)
    with store.lock():
        result = _check(store, store.read(workorder.FRAMES, {}), frame_id, tool, raw_arguments)
        events.append(store, frame=frame_id, kind="claim", outcome=result.code, ref=result.ref)
    return result


def authorize(store: Store, frames: dict[str, Any], frame_id: str, tool: str,
              raw_arguments: Mapping[str, Any]
              ) -> tuple[workorder.WorkOrder, dict[str, Any]]:
    """A current gate and a valid claim for TOOL, else Refused; the caller
    holds store.lock(). Returns the governing work order and the gate."""
    current, wo = gate.current_gate(store, frames, frame_id)
    if current is None or wo is None:
        events.append(store, frame=frame_id, kind=tool, outcome=f"refused-{GATE_NOT_CURRENT}")
        raise Refused(GATE_NOT_CURRENT, f"{tool}: no current gate for this frame; read "
                      "your work order and call open_gate")
    result = _check(store, frames, frame_id, tool, raw_arguments)
    if not result.ok:
        events.append(store, frame=frame_id, kind=tool, outcome=f"refused-{result.code}")
        raise Refused(result.code, result.message)
    return wo, current
