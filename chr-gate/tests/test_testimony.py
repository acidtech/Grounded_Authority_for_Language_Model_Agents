import pytest

from chrgate.core import claims, gate, testimony

FRAME = "session-A"


def test_records_append_in_order_with_work_order_reference(store, issuer, active_wo):
    w = issuer.read_work_order(FRAME).witness
    opened = gate.open_gate(store, FRAME, w)
    claim = f"observed under {active_wo.ref}"
    first = testimony.record(store, FRAME, claim, "the suite passes")
    path = store.root / testimony.TESTIMONY
    after_first = path.read_bytes()
    second = testimony.record(store, FRAME, claim, "lint is clean")

    assert path.read_bytes().startswith(after_first)  # appended, never rewritten
    entries = testimony.read_all(store)
    assert entries == [first, second]
    assert [e["text"] for e in entries] == ["the suite passes", "lint is clean"]
    for e in entries:
        assert (e["frame"], e["work_order"], e["opening_id"], e["claim"]) == (
            FRAME, active_wo.ref, opened.opening_id, claim)

    assert gate.close_gate(store, FRAME)
    with pytest.raises(claims.Refused):
        testimony.record(store, FRAME, claim, "after the gate closed")
    assert testimony.read_all(store) == [first, second]
