import hashlib
import re

from chrgate.core import citations, events, nonces, workorder
from chrgate.core.gate import (DENIED, DENIED_TEXT, OPEN, close_gate, gate_is_current,
                               new_epoch, open_gate)
from chrgate.core.store import Store
from chrgate.core.witness import WitnessIssuer

FRAME = "session-A"
OTHER = "agent-B"
WRONG = "wit:" + "0" * 32


def test_wrong_witness_denied(store, issuer, state_snapshot):
    issuer.read_work_order(FRAME)
    before = state_snapshot(store.root)
    for wrong in (WRONG, "", None):
        result = open_gate(store, FRAME, wrong)
        assert result.status == DENIED
        assert result.message == DENIED_TEXT == "read your work order"
        assert result.text is None
    assert state_snapshot(store.root) == before
    assert not gate_is_current(store, FRAME)


def test_correct_witness_opens_and_resurfaces(store, issuer, active_wo, wo_text):
    read = issuer.read_work_order(FRAME)
    result = open_gate(store, FRAME, read.witness)
    assert result.status == OPEN
    assert result.text == wo_text
    assert result.ref == active_wo.ref
    assert result.opening_id
    assert gate_is_current(store, FRAME)


def test_plaintext_witness_never_on_disk(store, issuer, isolated_env):
    w_a = issuer.read_work_order(FRAME).witness
    open_gate(store, FRAME, w_a)
    issuer.read_work_order(FRAME)
    open_gate(store, FRAME, w_a)
    close_gate(store, FRAME)
    w_b = issuer.read_work_order(OTHER).witness
    open_gate(store, OTHER, WRONG)
    new_epoch(store, FRAME)
    w_a2 = issuer.read_work_order(FRAME).witness

    files = [p for p in (isolated_env / "state").rglob("*") if p.is_file()]
    assert {"frames.json", "events.jsonl", "workorder.json"} <= {p.name for p in files}
    for w in (w_a, w_b, w_a2):
        for p in files:
            data = p.read_bytes()
            assert w.encode() not in data, p
            assert w.removeprefix("wit:").encode() not in data, p
    with store.lock():
        recs = store.read(workorder.FRAMES, None)
    assert recs[FRAME]["witness_sha256"] == hashlib.sha256(w_a2.encode()).hexdigest()


def test_reread_returns_same_witness(issuer):
    first = issuer.read_work_order(FRAME)
    second = issuer.read_work_order(FRAME)
    assert second.witness == first.witness
    assert (second.ref, second.text) == (first.ref, first.text)


def test_reread_cancels_open_gate(store, issuer):
    w = issuer.read_work_order(FRAME).witness
    assert open_gate(store, FRAME, w).status == OPEN
    assert gate_is_current(store, FRAME)

    again = issuer.read_work_order(FRAME)
    assert not gate_is_current(store, FRAME)
    assert again.witness == w
    assert open_gate(store, FRAME, w).status == OPEN
    assert gate_is_current(store, FRAME)


def test_gate_survives_other_research(store, issuer):
    w = issuer.read_work_order(FRAME).witness
    assert open_gate(store, FRAME, w).status == OPEN

    # Research that is not a work-order read of this frame leaves the gate open.
    issuer.read_work_order(OTHER)
    workorder.propose(store, "draft for a later approval")
    with store.lock():
        workorder.active(store)
    events.read_all(store)
    nonce = nonces.issue(store, FRAME)
    assert citations.check(store, FRAME, [nonce]) == []
    assert open_gate(store, OTHER, WRONG).status == DENIED
    assert open_gate(store, FRAME, WRONG).status == DENIED  # a failed opening changes nothing
    assert gate_is_current(store, FRAME)
    assert gate_is_current(store, FRAME)

    assert close_gate(store, FRAME) is True
    assert not gate_is_current(store, FRAME)


def test_witness_reused_across_gates(store, issuer):
    w = issuer.read_work_order(FRAME).witness
    first = open_gate(store, FRAME, w)
    assert first.status == OPEN
    assert close_gate(store, FRAME) is True
    assert not gate_is_current(store, FRAME)

    second = open_gate(store, FRAME, w)
    assert second.status == OPEN
    assert second.opening_id != first.opening_id
    assert gate_is_current(store, FRAME)


def test_open_gate_does_not_consume_witness(store, issuer):
    w = issuer.read_work_order(FRAME).witness
    assert open_gate(store, FRAME, w).status == OPEN
    assert open_gate(store, FRAME, w).status == OPEN
    assert issuer.read_work_order(FRAME).witness == w
    assert open_gate(store, FRAME, w).status == OPEN


def test_new_version_issues_new_witness(store, issuer, active_wo):
    old = issuer.read_work_order(FRAME).witness
    assert open_gate(store, FRAME, old).status == OPEN

    plan_id = workorder.propose(store, "revised text")
    workorder.activate(store, plan_id, f"approve {plan_id}")
    assert not gate_is_current(store, FRAME)
    assert open_gate(store, FRAME, old).status == DENIED

    new = issuer.read_work_order(FRAME)
    assert new.witness != old
    assert (new.ref, new.text) == (f"wo:{active_wo.id}.v2", "revised text")
    assert open_gate(store, FRAME, new.witness).status == OPEN
    assert open_gate(store, FRAME, old).status == DENIED


def test_new_epoch_issues_new_witness(store, issuer):
    old = issuer.read_work_order(FRAME).witness
    assert open_gate(store, FRAME, old).status == OPEN

    assert new_epoch(store, FRAME) == 2
    assert not gate_is_current(store, FRAME)
    assert open_gate(store, FRAME, old).status == DENIED

    new = issuer.read_work_order(FRAME).witness
    assert new != old
    assert open_gate(store, FRAME, new).status == OPEN
    assert open_gate(store, FRAME, old).status == DENIED


def test_restart_issues_new_witness(store, issuer):
    old = issuer.read_work_order(FRAME).witness

    restarted = WitnessIssuer(Store.for_project())  # a new server process
    new = restarted.read_work_order(FRAME).witness
    assert new != old
    assert open_gate(store, FRAME, old).status == DENIED
    assert open_gate(store, FRAME, new).status == OPEN
    assert restarted.read_work_order(FRAME).witness == new


def test_witness_bound_to_frame(store, issuer):
    w_a = issuer.read_work_order(FRAME).witness
    w_b = issuer.read_work_order(OTHER).witness
    assert w_a != w_b
    assert open_gate(store, OTHER, w_a).status == DENIED
    assert open_gate(store, FRAME, w_b).status == DENIED
    assert open_gate(store, "never-read", w_a).status == DENIED
    assert open_gate(store, FRAME, w_a).status == OPEN
    assert open_gate(store, OTHER, w_b).status == OPEN


def test_witness_format(issuer, active_wo):
    read = issuer.read_work_order(FRAME)
    m = re.fullmatch(r"wit:([0-9a-f]+)", read.witness)
    assert m
    assert len(m.group(1)) * 4 >= 64
    assert len(m.group(1)) == 32
    assert m.group(1) not in active_wo.ref
