import hashlib
import re

import pytest

from chrgate.core import claims, delegation, gate, workorder
from chrgate.core.claims import Refused
from chrgate.core.witness import NoActiveWorkOrder

FRAME = "session-A"
CHILD = "agent-child"
GRANDCHILD = "agent-grandchild"
CHILD_TEXT = "Write the parser tests only; touch nothing else."


def _open(store, issuer, frame):
    read = issuer.read_work_order(frame)
    result = gate.open_gate(store, frame, read.witness)
    assert result.status == gate.OPEN
    return read.witness, result


def test_delegate_without_open_gate_refused(store, issuer, active_wo, state_snapshot):
    issuer.read_work_order(FRAME)  # witness issued, no gate opened
    before = state_snapshot(store.root)
    with pytest.raises(Refused) as refused:
        delegation.delegate(store, FRAME, f"under {active_wo.ref}", CHILD_TEXT)
    assert refused.value.code == claims.GATE_NOT_CURRENT
    assert state_snapshot(store.root) == before

    _open(store, issuer, FRAME)
    assert gate.close_gate(store, FRAME)
    with pytest.raises(Refused) as refused:
        delegation.delegate(store, FRAME, f"under {active_wo.ref}", CHILD_TEXT)
    assert refused.value.code == claims.GATE_NOT_CURRENT

    _open(store, issuer, FRAME)
    with pytest.raises(Refused) as refused:  # an open gate still needs a valid claim
        delegation.delegate(store, FRAME, "no reference here", CHILD_TEXT)
    assert refused.value.code == claims.REFERENCE_MISSING
    with store.lock():
        assert store.read(workorder.DELEGATIONS, None) is None


def test_chain_child_caller_principal(store, issuer, active_wo):
    _, opened = _open(store, issuer, FRAME)
    d = delegation.delegate(store, FRAME, f"narrowing {active_wo.ref} to tests", CHILD_TEXT)
    links = delegation.chain(store, d.ref)
    assert [link.kind for link in links] == ["delegated", "principal", "approval"]
    assert [link.ref for link in links] == [d.ref, active_wo.ref, active_wo.ref]
    assert (links[0].text, links[0].caller_frame, links[0].opening_id) == (
        CHILD_TEXT, FRAME, opened.opening_id)
    with store.lock():
        record = store.read(workorder.WORK_ORDER, None)
    assert links[2].approval == {"plan_id": record["plan_id"], **record["approval"]}

    delegation.bind_child(store, CHILD, d.delegation_id)
    _open(store, issuer, CHILD)
    g = delegation.delegate(store, CHILD, f"under {d.ref}", "Only the CRLF test.")
    links = delegation.chain(store, g.ref)
    assert [link.kind for link in links] == ["delegated", "delegated", "principal", "approval"]
    assert [link.ref for link in links] == [g.ref, d.ref, active_wo.ref, active_wo.ref]
    assert links[0].caller_frame == CHILD


def test_bound_child_reads_its_own_work_order_and_witness(store, issuer, active_wo, wo_text):
    parent_witness, _ = _open(store, issuer, FRAME)
    d = delegation.delegate(store, FRAME, f"under {active_wo.ref}", CHILD_TEXT)
    assert delegation.bind_child(store, CHILD, d.delegation_id) == d.ref

    read = issuer.read_work_order(CHILD)
    assert (read.ref, read.text) == (d.ref, CHILD_TEXT)
    assert read.witness != parent_witness
    opened = gate.open_gate(store, CHILD, read.witness)
    assert (opened.status, opened.ref, opened.text) == (gate.OPEN, d.ref, CHILD_TEXT)
    parent = issuer.read_work_order(FRAME)
    assert (parent.ref, parent.text) == (active_wo.ref, wo_text)


def test_parent_witness_does_not_open_child_gate(store, issuer, active_wo):
    parent_witness, _ = _open(store, issuer, FRAME)
    d = delegation.delegate(store, FRAME, f"under {active_wo.ref}", CHILD_TEXT)
    delegation.bind_child(store, CHILD, d.delegation_id)
    child_witness = issuer.read_work_order(CHILD).witness

    assert gate.open_gate(store, CHILD, parent_witness).status == gate.DENIED
    assert not gate.gate_is_current(store, CHILD)
    assert gate.open_gate(store, FRAME, child_witness).status == gate.DENIED


def test_principal_revision_ends_delegated_authority(store, issuer, active_wo):
    _open(store, issuer, FRAME)
    d = delegation.delegate(store, FRAME, f"under {active_wo.ref}", CHILD_TEXT)
    delegation.bind_child(store, CHILD, d.delegation_id)
    child_witness, _ = _open(store, issuer, CHILD)

    plan_id = workorder.propose(store, "revised")
    workorder.activate(store, plan_id, f"approve {plan_id}")
    assert not gate.gate_is_current(store, CHILD)
    assert gate.open_gate(store, CHILD, child_witness).status == gate.DENIED
    with pytest.raises(NoActiveWorkOrder):
        issuer.read_work_order(CHILD)
    assert claims.check_claim(store, CHILD, "write_file",
                              {"claim": f"under {d.ref}"}).code == claims.NO_WORK_ORDER


def test_delegation_rebind_second_frame_refused(store, issuer, active_wo):
    _open(store, issuer, FRAME)
    d = delegation.delegate(store, FRAME, f"under {active_wo.ref}", CHILD_TEXT)
    assert delegation.bind_child(store, CHILD, d.delegation_id) == d.ref
    with pytest.raises(Refused) as refused:
        delegation.bind_child(store, GRANDCHILD, d.delegation_id)
    assert refused.value.code == delegation.BOUND_ELSEWHERE


def test_chain_unknown_reference(store, active_wo):
    for ref in ("wo:DW-unknown.v1", "not a reference"):
        with pytest.raises(LookupError):
            delegation.chain(store, ref)


def test_delegation_id_stored_as_hash_only(store, issuer, active_wo):
    _open(store, issuer, FRAME)
    d = delegation.delegate(store, FRAME, f"under {active_wo.ref}", CHILD_TEXT)
    raw = (store.root / workorder.DELEGATIONS).read_bytes()
    assert d.delegation_id.encode() not in raw
    assert re.search(rb"D-[0-9a-f]{16}", raw) is None, raw
    with store.lock():
        (record,) = store.read(workorder.DELEGATIONS, {}).values()
    assert record["delegation_sha256"] == hashlib.sha256(d.delegation_id.encode()).hexdigest()
    assert delegation.bind_child(store, CHILD, d.delegation_id) == d.ref


def test_record_without_hash_never_binds(store, issuer, active_wo):
    _open(store, issuer, FRAME)
    d = delegation.delegate(store, FRAME, f"under {active_wo.ref}", CHILD_TEXT)
    with store.lock():
        delegated = store.read(workorder.DELEGATIONS, {})
        for record in delegated.values():  # the record as stored before hashing
            record.pop("delegation_sha256", None)
            record["delegation_id"] = d.delegation_id
        store.write(workorder.DELEGATIONS, delegated)
    with pytest.raises(Refused) as refused:
        delegation.bind_child(store, CHILD, d.delegation_id)
    assert refused.value.code == delegation.UNKNOWN_DELEGATION


def test_inherited_walks_to_principal_root_first(store, issuer, active_wo):
    _open(store, issuer, FRAME)
    d = delegation.delegate(store, FRAME, f"under {active_wo.ref}", CHILD_TEXT)
    delegation.bind_child(store, CHILD, d.delegation_id)
    _open(store, issuer, CHILD)
    g = delegation.delegate(store, CHILD, f"under {d.ref}", "Only the CRLF test.")
    d_id, g_id = (claims.REF_RE.fullmatch(x.ref).group(1) for x in (d, g))
    with store.lock():
        assert delegation.inherited(store, active_wo.id) == []
        assert delegation.inherited(store, d_id) == [active_wo]
        assert delegation.inherited(store, g_id) == [
            active_wo, workorder.WorkOrder(id=d_id, version=1, text=CHILD_TEXT)]


def test_inherited_raises_when_parent_not_live(store, issuer, active_wo):
    _open(store, issuer, FRAME)
    d = delegation.delegate(store, FRAME, f"under {active_wo.ref}", CHILD_TEXT)
    delegation.bind_child(store, CHILD, d.delegation_id)
    _open(store, issuer, CHILD)
    g = delegation.delegate(store, CHILD, f"under {d.ref}", "Only the CRLF test.")
    d_id, g_id = (claims.REF_RE.fullmatch(x.ref).group(1) for x in (d, g))
    # (b) first, while the principal is live: g's delegated parent d is not at
    # g's parent_version, so the walk stops at d and never reaches the principal
    with store.lock():
        delegated = store.read(workorder.DELEGATIONS, {})
        delegated[d_id]["version"] = 2
        store.write(workorder.DELEGATIONS, delegated)
        with pytest.raises(RuntimeError, match="is not live"):
            delegation.inherited(store, g_id)
    # (a) the principal d descends from was revised
    plan_id = workorder.propose(store, "revised")
    workorder.activate(store, plan_id, f"approve {plan_id}")
    with store.lock():
        with pytest.raises(RuntimeError, match="is not live"):
            delegation.inherited(store, d_id)


def test_inherited_raises_when_parent_record_absent(store, issuer, active_wo):
    _open(store, issuer, FRAME)
    d = delegation.delegate(store, FRAME, f"under {active_wo.ref}", CHILD_TEXT)
    delegation.bind_child(store, CHILD, d.delegation_id)
    _open(store, issuer, CHILD)
    g = delegation.delegate(store, CHILD, f"under {d.ref}", "Only the CRLF test.")
    d_id, g_id = (claims.REF_RE.fullmatch(x.ref).group(1) for x in (d, g))
    with store.lock():
        delegated = store.read(workorder.DELEGATIONS, {})
        del delegated[d_id]
        store.write(workorder.DELEGATIONS, delegated)
        with pytest.raises(RuntimeError, match="is not live"):
            delegation.inherited(store, g_id)
