import json
from datetime import UTC, datetime, timedelta

import pytest

from chrgate.core import events, gate, workorder
from chrgate.core.config import CONFIG, Config, ConfigError, load_config
from chrgate.core.witness import witness_sha256

FRAME = "session-A"
EXPIRED = "pending gate expired; reopen with the same witness"
CONSUMED = "gate already used by an earlier batch; call open_gate again"


def _config(store, values):
    store.root.mkdir(parents=True, exist_ok=True)
    (store.root / CONFIG).write_text(json.dumps(values), encoding="utf-8")


def _read(issuer):
    return issuer.read_work_order(FRAME).witness


def _open(store, witness, turn_key="t-open", now=None):
    opened = gate.open_gate(store, FRAME, witness, turn_key=turn_key, now=now)
    assert opened.status == gate.OPEN
    return opened


def _frame(store):
    with store.lock():
        return store.read(workorder.FRAMES, {})[FRAME]


def test_defaults_without_config(store, issuer):
    with store.lock():
        assert load_config(store) == Config(max_intervening_turns=3, gate_lifetime_seconds=900)
    assert not (store.root / CONFIG).exists()
    t0 = datetime(2026, 1, 1, tzinfo=UTC)
    _open(store, _read(issuer), now=t0)
    g = _frame(store)["gate"]
    assert g["opened_at"] == t0.isoformat()
    assert g["expires_at"] == (t0 + timedelta(seconds=900)).isoformat()
    assert (g["opening_turn_key"], g["intervening_turns"], g["seen_turn_keys"],
            g["consumed_by"]) == ("t-open", 0, [], None)


def test_invalid_config_raises(store, issuer):
    w = _read(issuer)
    bad = [{"max_intervening_turns": "3"}, {"max_intervening_turns": True},
           {"gate_lifetime_seconds": 1.5}, {"max_intervening_turns": -1},
           {"gate_lifetime_seconds": 0}, {"gate_lifetime_seconds": -5},
           {"gate_lifetime": 900}, [3, 900]]
    for values in bad:
        _config(store, values)
        with store.lock(), pytest.raises(ConfigError):
            load_config(store)
        with pytest.raises(ConfigError):
            gate.open_gate(store, FRAME, w, turn_key="t-open")
        with pytest.raises(ConfigError):
            gate.take_gate(store, FRAME, "t-act")
    _config(store, {"max_intervening_turns": 0, "gate_lifetime_seconds": 1})
    with store.lock():
        assert load_config(store) == Config(max_intervening_turns=0, gate_lifetime_seconds=1)


def test_research_turns_within_limit_keep_gate(store, issuer):
    _open(store, _read(issuer))
    for key in ("r1", "r2", "r3"):
        assert gate.note_turn(store, FRAME, key)
    assert _frame(store)["gate"]["intervening_turns"] == 3
    result = gate.take_gate(store, FRAME, "t-act")
    assert (result.ok, result.code) == (True, gate.TAKEN)


def test_turns_over_limit_expire(store, issuer):
    w = _read(issuer)
    _open(store, w)
    for key in ("r1", "r2", "r3", "r4"):
        assert gate.note_turn(store, FRAME, key)
    result = gate.take_gate(store, FRAME, "t-act")
    assert (result.ok, result.code, result.message) == (False, gate.EXPIRED_TURNS, EXPIRED)
    rec = _frame(store)
    assert rec["witness_sha256"] == witness_sha256(w)
    assert gate.gate_is_current(store, FRAME)  # authority meaning unchanged
    _open(store, w, turn_key="t-reopen")
    assert gate.take_gate(store, FRAME, "t-act").ok


def test_lifetime_expiry(store, issuer):
    _config(store, {"gate_lifetime_seconds": 60})
    w = _read(issuer)
    t0 = datetime(2026, 1, 1, tzinfo=UTC)
    _open(store, w, now=t0)
    for at in (t0 + timedelta(seconds=60), t0 + timedelta(hours=1)):
        result = gate.take_gate(store, FRAME, "t-act", now=at)
        assert (result.ok, result.code, result.message) == (False, gate.EXPIRED_LIFETIME,
                                                            EXPIRED)
    assert _frame(store)["witness_sha256"] == witness_sha256(w)
    t1 = t0 + timedelta(hours=1)
    _open(store, w, turn_key="t-reopen", now=t1)
    assert gate.take_gate(store, FRAME, "t-act", now=t1 + timedelta(seconds=59)).ok


def test_opening_turn_not_counted(store, issuer):
    _config(store, {"max_intervening_turns": 0})
    _open(store, _read(issuer), turn_key="t-open")
    assert not gate.note_turn(store, FRAME, "t-open")
    g = _frame(store)["gate"]
    assert (g["intervening_turns"], g["seen_turn_keys"]) == (0, [])
    assert gate.take_gate(store, FRAME, "t-act").ok


def test_duplicate_turn_key_counted_once(store, issuer):
    _config(store, {"max_intervening_turns": 1})
    _open(store, _read(issuer))
    assert gate.note_turn(store, FRAME, "r1")
    assert not gate.note_turn(store, FRAME, "r1")
    g = _frame(store)["gate"]
    assert (g["intervening_turns"], g["seen_turn_keys"]) == (1, ["r1"])
    assert gate.take_gate(store, FRAME, "t-act").ok


def test_first_batch_consumes_gate(store, issuer):
    w = _read(issuer)
    _open(store, w)
    first = gate.take_gate(store, FRAME, "batch-1")
    second = gate.take_gate(store, FRAME, "batch-1")
    assert first.ok and second.ok
    assert first.opening_id == second.opening_id
    other = gate.take_gate(store, FRAME, "batch-2")
    assert (other.ok, other.code, other.message) == (False, gate.CONSUMED, CONSUMED)
    assert _frame(store)["gate"]["consumed_by"] == "batch-1"
    assert not gate.note_turn(store, FRAME, "r1")  # a consumed gate counts no turns
    assert _frame(store)["witness_sha256"] == witness_sha256(w)
    _open(store, w, turn_key="t-reopen")
    assert gate.take_gate(store, FRAME, "batch-2").ok


def test_zero_turns_allows_only_next_turn(store, issuer):
    _config(store, {"max_intervening_turns": 0})
    w = _read(issuer)
    _open(store, w, turn_key="t-open")
    assert gate.take_gate(store, FRAME, "t-next").ok
    _open(store, w, turn_key="t-open-2")
    assert gate.note_turn(store, FRAME, "r1")
    result = gate.take_gate(store, FRAME, "t-later")
    assert (result.ok, result.code, result.message) == (False, gate.EXPIRED_TURNS, EXPIRED)


def test_refusal_changes_no_state(store, issuer, state_snapshot):
    w = _read(issuer)

    def refused(code, **kwargs):
        before = state_snapshot(store.root)
        result = gate.take_gate(store, FRAME, "t-refused", **kwargs)
        assert (result.ok, result.code) == (False, code)
        assert state_snapshot(store.root) == before

    refused(gate.NO_GATE)
    _open(store, w)
    refused(gate.EXPIRED_LIFETIME, now=datetime.now(UTC) + timedelta(days=1))
    for key in ("r1", "r2", "r3", "r4"):
        gate.note_turn(store, FRAME, key)
    refused(gate.EXPIRED_TURNS)
    _open(store, w, turn_key="t-reopen")
    assert gate.take_gate(store, FRAME, "batch-1").ok
    refused(gate.CONSUMED)
    assert gate.take_gate(store, FRAME, "t-refused", now=None).code == gate.CONSUMED
    assert gate.TAKE_TEXT[gate.NO_GATE] == gate.DENIED_TEXT == "read your work order"


def test_events_record_outcomes_without_witness(store, issuer):
    _config(store, {"max_intervening_turns": 0})
    w = _read(issuer)
    g1 = _open(store, w, turn_key="t-open").opening_id
    gate.note_turn(store, FRAME, "t-open")
    gate.take_gate(store, FRAME, "b1")
    gate.take_gate(store, FRAME, "b1")
    gate.take_gate(store, FRAME, "b2")
    gate.note_turn(store, FRAME, "r1")
    g2 = _open(store, w, turn_key="t-open-2").opening_id
    gate.note_turn(store, FRAME, "r2")
    gate.note_turn(store, FRAME, "r2")
    gate.take_gate(store, FRAME, "b3")
    g3 = _open(store, w, turn_key="t-open-3").opening_id
    gate.take_gate(store, FRAME, "b4", now=datetime.now(UTC) + timedelta(days=1))
    assert gate.close_gate(store, FRAME)
    gate.note_turn(store, FRAME, "r3")
    gate.take_gate(store, FRAME, "b5")
    got = [(e["kind"], e["outcome"], e["ref"]) for e in events.read_all(store)
           if e["kind"] in ("note_turn", "take_gate")]
    assert got == [
        ("note_turn", "opening-turn", g1),
        ("take_gate", "taken", g1),
        ("take_gate", "taken-same-batch", g1),
        ("take_gate", "refused-consumed", g1),
        ("note_turn", "consumed", g1),
        ("note_turn", "counted", g2),
        ("note_turn", "duplicate", g2),
        ("take_gate", "refused-expired-turns", g2),
        ("take_gate", "refused-expired-lifetime", g3),
        ("note_turn", "no-gate", None),
        ("take_gate", "refused-no-gate", None),
    ]
    assert all(e["frame"] == FRAME for e in events.read_all(store) if e["frame"] is not None)
    assert w not in (store.root / events.EVENTS).read_text(encoding="utf-8")


def test_consequential_call_in_opening_turn_refused(store, issuer, state_snapshot):
    _open(store, _read(issuer), turn_key="t-open")
    before = state_snapshot(store.root)
    result = gate.take_gate(store, FRAME, "t-open")
    assert (result.ok, result.code, result.message) == (False, gate.OPENING_TURN,
                                                        gate.OPENING_TURN_TEXT)
    assert state_snapshot(store.root) == before
    assert _frame(store)["gate"]["consumed_by"] is None
    assert gate.take_gate(store, FRAME, "t-next").ok
