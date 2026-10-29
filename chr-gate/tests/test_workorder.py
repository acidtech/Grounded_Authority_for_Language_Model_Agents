import hashlib
import re

import pytest

from chrgate.core import gate, workorder
from chrgate.core.witness import WitnessIssuer


def test_activate_stores_exact_proposed_text(store, wo_text):
    plan_id = workorder.propose(store, wo_text)
    assert re.fullmatch(r"P-[0-9a-f]{8}", plan_id)
    wo = workorder.activate(store, plan_id, f"approve {plan_id}")

    assert re.fullmatch(r"WO-[0-9a-f]+", wo.id)
    assert wo.ref == f"wo:{wo.id}.v1"
    assert wo.text.encode("utf-8") == wo_text.encode("utf-8")
    with store.lock():
        assert workorder.active(store).text.encode("utf-8") == wo_text.encode("utf-8")
        record = store.read(workorder.WORK_ORDER, None)
    assert record["approval"]["prompt_sha256"] == hashlib.sha256(
        f"approve {plan_id}".encode()).hexdigest()
    assert record["approval"]["approved_at"]
    assert WitnessIssuer(store).read_work_order("session-A").text == wo_text


def test_version_increments_on_second_activation(store, active_wo):
    assert active_wo.version == 1
    plan_id = workorder.propose(store, "second text")
    wo2 = workorder.activate(store, plan_id, f"approve {plan_id}")
    assert (wo2.id, wo2.version, wo2.text) == (active_wo.id, 2, "second text")
    assert wo2.ref == f"wo:{active_wo.id}.v2"
    with store.lock():
        assert workorder.active(store) == wo2


def test_activation_invalidates_every_frame_witness_and_gate(store, issuer):
    frames = ["session-A", "agent-B"]
    witnesses = {f: issuer.read_work_order(f).witness for f in frames}
    for f in frames:
        assert gate.open_gate(store, f, witnesses[f]).status == gate.OPEN

    plan_id = workorder.propose(store, "revised")
    workorder.activate(store, plan_id, f"approve {plan_id}")

    with store.lock():
        recs = store.read(workorder.FRAMES, None)
    for f in frames:
        assert recs[f]["witness_sha256"] is None
        assert recs[f]["witness_binding"] is None
        assert recs[f]["gate"] is None
        assert not gate.gate_is_current(store, f)
        assert gate.open_gate(store, f, witnesses[f]).status == gate.DENIED


def test_unknown_plan_id_refused_without_state_change(store, active_wo, state_snapshot):
    before = state_snapshot(store.root)
    with pytest.raises(workorder.UnknownPlan):
        workorder.activate(store, "P-00000000", "approve P-00000000")
    assert state_snapshot(store.root) == before
    with store.lock():
        assert workorder.active(store) == active_wo
