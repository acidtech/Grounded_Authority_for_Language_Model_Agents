"""The action gate (C32 Appendix A open_gate, consequential_batch and
gate_is_current).

open_gate(frame, witness, turn_key) checks the witness against the frame's
stored hash and binding for the governing work order version and the frame's
epoch. Any mismatch returns DENIED with 'read your work order' and changes no
state; a pass records a gate (opening_id, work order id, version, frame,
epoch, opened_at, expires_at = opened_at + config gate_lifetime_seconds,
opening_turn_key, intervening_turns, seen_turn_keys, consumed_by) and returns
OPEN with the full work order text. open_gate neither rotates nor consumes the
witness.

note_turn(frame, turn_key) counts one completed nonconsequential worker turn
against an open, unconsumed gate (never the opening turn, never a key twice).
take_gate(frame, turn_key) is the single dispatch check for a consequential
call: the gate is current (authority), now < expires_at, intervening_turns <=
config max_intervening_turns, the call is not in the opening turn (C32
'Opening first': the turn key differs from opening_turn_key), and the gate is
unconsumed or consumed by this same turn key. The first passing call consumes the gate for its turn key, so
the parallel calls of one batch share it and a later batch needs a new
open_gate. A refusal changes no state. Expiry and consumption end the gate,
never the witness. gate_is_current is the authority check alone. close_gate
ends the gate only. new_epoch starts a new context epoch for the frame
(compaction), which ends both the witness and the gate.
"""

import hmac
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from chrgate.core import events, workorder
from chrgate.core.config import load_config
from chrgate.core.store import Store
from chrgate.core.witness import binding, check_frame_id, witness_sha256

OPEN = "OPEN"
DENIED = "DENIED"
DENIED_TEXT = "read your work order"

# take_gate result codes
TAKEN = "taken"
NO_GATE = "no-gate"
EXPIRED_LIFETIME = "expired-lifetime"
EXPIRED_TURNS = "expired-turns"
CONSUMED = "consumed"
OPENING_TURN = "opening-turn"
EXPIRED_TEXT = "pending gate expired; reopen with the same witness"
CONSUMED_TEXT = "gate already used by an earlier batch; call open_gate again"
OPENING_TURN_TEXT = ("a consequential call cannot run in the turn that opened the gate; "
                     "make it in your next turn")
TAKE_TEXT = {NO_GATE: DENIED_TEXT, EXPIRED_LIFETIME: EXPIRED_TEXT,
             EXPIRED_TURNS: EXPIRED_TEXT, CONSUMED: CONSUMED_TEXT,
             OPENING_TURN: OPENING_TURN_TEXT}


@dataclass(frozen=True)
class GateResult:
    status: str
    message: str
    ref: str | None = None
    text: str | None = None
    opening_id: str | None = None


@dataclass(frozen=True)
class TakeResult:
    ok: bool
    code: str
    message: str
    opening_id: str | None = None


def _clock(now: datetime | None) -> datetime:
    """NOW (injectable for tests), else the current UTC time; timezone-aware."""
    if now is None:
        return datetime.now(UTC)
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise ValueError(f"now must be a timezone-aware datetime, got {now!r}")
    return now


def _check_turn_key(turn_key: str) -> None:
    if not isinstance(turn_key, str) or not turn_key:
        raise ValueError(f"turn key must be a non-empty string, got {turn_key!r}")


def _frame(store: Store, frames: dict[str, Any], frame_id: str
           ) -> tuple[dict[str, Any] | None, workorder.WorkOrder | None]:
    rec = frames.get(frame_id)
    if rec is None:
        return None, None
    return rec, workorder.governing_work_order(store, rec)


def open_gate(store: Store, frame_id: str, witness: str, turn_key: str | None = None,
              now: datetime | None = None) -> GateResult:
    """Open the frame's gate when WITNESS is its current witness. TURN_KEY is
    the host turn/batch key of the open_gate call itself (never counted as an
    intervening turn)."""
    check_frame_id(frame_id)
    if turn_key is not None:
        _check_turn_key(turn_key)
    opened = _clock(now)
    with store.lock():
        config = load_config(store)
        frames = store.read(workorder.FRAMES, {})
        rec, wo = _frame(store, frames, frame_id)
        valid = (rec is not None and wo is not None
                 and isinstance(witness, str)
                 and rec["witness_sha256"] is not None
                 and rec["witness_binding"] == binding(wo, frame_id, rec["epoch"])
                 and hmac.compare_digest(rec["witness_sha256"], witness_sha256(witness)))
        if not valid:
            events.append(store, frame=frame_id, kind="open_gate", outcome="denied")
            return GateResult(status=DENIED, message=DENIED_TEXT)
        gate = {"opening_id": "G-" + secrets.token_hex(8), "work_order": wo.id,
                "version": wo.version, "frame": frame_id, "epoch": rec["epoch"],
                "opened_at": opened.isoformat(),
                "expires_at": (opened + timedelta(seconds=config.gate_lifetime_seconds)).isoformat(),
                "opening_turn_key": turn_key, "intervening_turns": 0, "seen_turn_keys": [],
                "consumed_by": None}
        rec["gate"] = gate
        store.write(workorder.FRAMES, frames)
        events.append(store, frame=frame_id, kind="open_gate", outcome="open",
                      ref=gate["opening_id"])
    return GateResult(status=OPEN, message=f"gate open under {wo.ref}", ref=wo.ref,
                      text=wo.text, opening_id=gate["opening_id"])


def current_gate(store: Store, frames: dict[str, Any], frame_id: str
                 ) -> tuple[dict[str, Any] | None, workorder.WorkOrder | None]:
    """Appendix A gate_is_current inside the caller's store.lock(): the
    frame's gate when it is bound to the governing work order version, this
    frame and its current epoch (else None), and the governing work order."""
    rec, wo = _frame(store, frames, frame_id)
    if rec is None or wo is None or rec["gate"] is None:
        return None, wo
    gate = rec["gate"]
    if (gate["work_order"] == wo.id and gate["version"] == wo.version
            and gate["frame"] == frame_id and gate["epoch"] == rec["epoch"]):
        return gate, wo
    return None, wo


def gate_is_current(store: Store, frame_id: str) -> bool:
    """Appendix A gate_is_current for FRAME_ID (takes the lock)."""
    check_frame_id(frame_id)
    with store.lock():
        frames = store.read(workorder.FRAMES, {})
        return current_gate(store, frames, frame_id)[0] is not None


def note_turn(store: Store, frame_id: str, turn_key: str) -> bool:
    """Record one completed nonconsequential worker turn TURN_KEY. It counts
    only against a current, unconsumed gate, when it is not the opening turn
    and was not seen before; True when it counted. Never raises for a closed
    or absent gate."""
    check_frame_id(frame_id)
    _check_turn_key(turn_key)
    with store.lock():
        frames = store.read(workorder.FRAMES, {})
        current, _ = current_gate(store, frames, frame_id)
        if current is None:
            outcome = NO_GATE
        elif current["consumed_by"] is not None:
            outcome = CONSUMED
        elif turn_key == current["opening_turn_key"]:
            outcome = OPENING_TURN
        elif turn_key in current["seen_turn_keys"]:
            outcome = "duplicate"
        else:
            current["intervening_turns"] += 1
            current["seen_turn_keys"].append(turn_key)
            store.write(workorder.FRAMES, frames)
            outcome = "counted"
        events.append(store, frame=frame_id, kind="note_turn", outcome=outcome,
                      ref=None if current is None else current["opening_id"])
    return outcome == "counted"


def take_gate(store: Store, frame_id: str, turn_key: str,
              now: datetime | None = None) -> TakeResult:
    """The dispatch check for a consequential call in host turn/batch
    TURN_KEY. The first passing call consumes the gate for TURN_KEY; a refusal
    changes no state."""
    check_frame_id(frame_id)
    _check_turn_key(turn_key)
    at = _clock(now)
    with store.lock():
        config = load_config(store)
        frames = store.read(workorder.FRAMES, {})
        current, _ = current_gate(store, frames, frame_id)
        if current is None:
            code = NO_GATE
        elif turn_key == current["opening_turn_key"]:
            code = OPENING_TURN
        elif not at < datetime.fromisoformat(current["expires_at"]):
            code = EXPIRED_LIFETIME
        elif current["intervening_turns"] > config.max_intervening_turns:
            code = EXPIRED_TURNS
        elif current["consumed_by"] not in (None, turn_key):
            code = CONSUMED
        else:
            code = TAKEN
        opening_id = None if current is None else current["opening_id"]
        if code != TAKEN:
            events.append(store, frame=frame_id, kind="take_gate", outcome=f"refused-{code}",
                          ref=opening_id)
            return TakeResult(ok=False, code=code, message=TAKE_TEXT[code], opening_id=opening_id)
        assert current is not None
        if current["consumed_by"] is None:
            current["consumed_by"] = turn_key
            store.write(workorder.FRAMES, frames)
            outcome = TAKEN
        else:
            outcome = "taken-same-batch"
        events.append(store, frame=frame_id, kind="take_gate", outcome=outcome, ref=opening_id)
    return TakeResult(ok=True, code=TAKEN, message=f"gate taken by turn {turn_key}",
                      opening_id=opening_id)


def close_gate(store: Store, frame_id: str) -> bool:
    """End the frame's gate (never the witness); True when a gate was open."""
    check_frame_id(frame_id)
    with store.lock():
        frames = store.read(workorder.FRAMES, {})
        rec = frames.get(frame_id)
        if rec is None or rec["gate"] is None:
            events.append(store, frame=frame_id, kind="close_gate", outcome="no-gate")
            return False
        opening_id = rec["gate"]["opening_id"]
        rec["gate"] = None
        store.write(workorder.FRAMES, frames)
        events.append(store, frame=frame_id, kind="close_gate", outcome="closed", ref=opening_id)
    return True


def new_epoch(store: Store, frame_id: str) -> int | None:
    """Start a new context epoch (Appendix A new_worker_epoch): the witness
    and gate end. Returns the new epoch, or None for an unknown frame."""
    check_frame_id(frame_id)
    with store.lock():
        frames = store.read(workorder.FRAMES, {})
        rec = frames.get(frame_id)
        if rec is None:
            events.append(store, frame=frame_id, kind="new_epoch", outcome="no-frame")
            return None
        rec["epoch"] += 1
        workorder.clear_witness(rec)
        store.write(workorder.FRAMES, frames)
        events.append(store, frame=frame_id, kind="new_epoch", outcome=f"epoch-{rec['epoch']}")
    return rec["epoch"]
