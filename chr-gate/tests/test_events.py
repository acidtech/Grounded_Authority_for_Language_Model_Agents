from datetime import datetime

from chrgate.core import events, gate, workorder
from chrgate.core.witness import WitnessIssuer

FRAME = "session-A"


def _run_sequence(store):
    plan_id = workorder.propose(store, "work order text")
    wo = workorder.activate(store, plan_id, f"approve {plan_id}")
    issuer = WitnessIssuer(store)
    w = issuer.read_work_order(FRAME).witness
    gate.open_gate(store, FRAME, "wit:" + "0" * 32)
    opened = gate.open_gate(store, FRAME, w)
    gate.close_gate(store, FRAME)
    issuer.read_work_order(FRAME)
    gate.new_epoch(store, FRAME)
    return plan_id, wo, w, opened


def test_events_append_in_order(store):
    plan_id, wo, _, opened = _run_sequence(store)
    got = events.read_all(store)
    assert [(e["kind"], e["outcome"], e["frame"], e["ref"]) for e in got] == [
        ("propose", "stored", None, plan_id),
        ("activate", "activated", None, wo.ref),
        ("read_work_order", "issued", FRAME, wo.ref),
        ("open_gate", "denied", FRAME, None),
        ("open_gate", "open", FRAME, opened.opening_id),
        ("close_gate", "closed", FRAME, opened.opening_id),
        ("read_work_order", "reused", FRAME, wo.ref),
        ("new_epoch", "epoch-2", FRAME, None),
    ]
    times = [datetime.fromisoformat(e["time"]) for e in got]
    assert times == sorted(times)
    lines = (store.root / events.EVENTS).read_text().splitlines()
    assert len(lines) == len(got)


def test_events_never_contain_witness(store):
    _, _, w, _ = _run_sequence(store)
    raw = (store.root / events.EVENTS).read_text()
    assert w not in raw
    assert w.removeprefix("wit:") not in raw
    for e in events.read_all(store):
        assert set(e) == {"time", "frame", "kind", "outcome", "ref"}
