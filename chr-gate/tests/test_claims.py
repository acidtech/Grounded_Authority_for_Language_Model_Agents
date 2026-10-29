from chrgate.core import claims, delegation, gate, workorder

FRAME = "session-A"
CHILD = "agent-child"


def _check(store, args, frame=FRAME):
    return claims.check_claim(store, frame, "write_file", args)


def test_each_refusal_code_fires_on_its_own_case(store, wo_text):
    seen = set()

    def refused(args, code):
        result = _check(store, args)
        assert (result.ok, result.code) == (False, code), (args, result)
        seen.add(code)

    refused({"claim": "anything"}, claims.NO_WORK_ORDER)
    plan_id = workorder.propose(store, wo_text)
    v1 = workorder.activate(store, plan_id, f"approve {plan_id}")
    ref = v1.ref

    refused({"path": "a.txt", "content": "x"}, claims.CLAIM_MISSING)
    refused({}, claims.CLAIM_MISSING)
    refused({"path": "a.txt", "claim": f"under {ref}", "content": "x"}, claims.FIRST_KEY_NOT_CLAIM)
    for bad in ("", "   \n", 7, None, [ref]):
        refused({"claim": bad, "path": "a.txt"}, claims.CLAIM_EMPTY)
    refused({"claim": "fix the parser", "path": "a.txt"}, claims.REFERENCE_MISSING)
    refused({"claim": "under wo:WO-00000000.v1"}, claims.REFERENCE_MISSING)
    refused({"claim": f"under x{ref}"}, claims.REFERENCE_MISSING)

    plan_id = workorder.propose(store, "revised")
    v2 = workorder.activate(store, plan_id, f"approve {plan_id}")
    refused({"claim": f"under {ref}"}, claims.STALE_VERSION)
    refused({"claim": f"under {v2.ref}1"}, claims.STALE_VERSION)  # v21 is not v2
    assert _check(store, {"claim": f"under {v2.ref}", "path": "a.txt"}).ok

    assert seen == {claims.NO_WORK_ORDER, claims.CLAIM_MISSING, claims.FIRST_KEY_NOT_CLAIM,
                    claims.CLAIM_EMPTY, claims.REFERENCE_MISSING, claims.STALE_VERSION}


def test_false_claim_with_right_reference_passes(store, active_wo):
    claim = (f"Under {active_wo.ref}: the moon is made of cheese, and this write "
             "deletes every file in the project.")
    result = _check(store, {"claim": claim, "path": "a.txt", "content": "x"})
    assert (result.ok, result.code) == (True, claims.ACCEPTED)


def test_child_frame_citing_parent_reference_refused(store, issuer, active_wo):
    w = issuer.read_work_order(FRAME).witness
    assert gate.open_gate(store, FRAME, w).status == gate.OPEN
    d = delegation.delegate(store, FRAME, f"narrowing {active_wo.ref} to tests", "write tests only")
    delegation.bind_child(store, CHILD, d.delegation_id)

    result = _check(store, {"claim": f"under {active_wo.ref}"}, frame=CHILD)
    assert (result.ok, result.code) == (False, claims.REFERENCE_MISSING)
    assert _check(store, {"claim": f"under {d.ref}"}, frame=CHILD).ok
    assert _check(store, {"claim": f"under {d.ref}"}, frame=FRAME).code == claims.REFERENCE_MISSING
