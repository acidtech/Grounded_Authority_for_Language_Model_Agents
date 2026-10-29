"""T7a: chrgate.smoke_check. The synthetic session is made by the real core
calls (propose, activate, read_work_order, open_gate, check_claim, take_gate),
so the log is the one the server writes; the state lands in the nested
XDG_STATE_HOME/chr-gate/PROJECTKEY folder under --state. Each step's failure
case turns exactly that step FAIL with a non-zero exit."""

import json

import pytest

from chrgate import smoke_check
from chrgate.core import claims, events, gate, workorder
from chrgate.core.store import Store
from chrgate.core.witness import WitnessIssuer
from chrgate.hooks.adapters import claude_code

FRAME = "smoke-session-1"
NAMES = [name for name, _ in smoke_check.STEPS]


def session(tmp_path, monkeypatch, *, wrong_witness_accepted=False, second_write=True):
    state, project = tmp_path / "smoke-state", tmp_path / "proj"
    project.mkdir()
    monkeypatch.setenv("XDG_STATE_HOME", str(state))
    store = Store.for_project(project)
    text = "Create " + " and ".join(f"{n} containing {t!r}"
                                    for n, t in smoke_check.EXPECTED_FILES.items())
    plan = workorder.propose(store, text)
    wo = workorder.activate(store, plan, f"approve {plan}")
    issuer = WitnessIssuer(store)
    if wrong_witness_accepted:  # the step 3 attempt passes instead of being refused
        witness = issuer.read_work_order(FRAME).witness
        assert gate.open_gate(store, FRAME, witness, turn_key="t3").status == gate.OPEN
    else:
        assert gate.open_gate(store, FRAME, "wit:" + "0" * 32, turn_key="t3").status == gate.DENIED
    witness = issuer.read_work_order(FRAME).witness
    assert gate.open_gate(store, FRAME, witness, turn_key="t4").status == gate.OPEN
    files = list(smoke_check.EXPECTED_FILES.items())[:2 if second_write else 1]
    for name, content in files:
        args = {"claim": f"creating {name} under {wo.ref}", "path": name, "content": content}
        assert claims.check_claim(store, FRAME, "write_file", args).ok
        assert gate.take_gate(store, FRAME, "t5").ok
        (project / name).write_text(content + "\n")
        with store.lock():
            events.append(store, frame=FRAME, kind=smoke_check.WRITE_OK[0],
                          outcome=smoke_check.WRITE_OK[1])
    return state, project, store


def check(capsys, state, project):
    rc = smoke_check.main(["--host", claude_code.HOST, "--state", str(state),
                           "--project", str(project)])
    out = capsys.readouterr().out
    results = {}
    for line in out.splitlines():
        number, _, rest = line.partition(". ")
        if number.isdigit():
            results[NAMES[int(number) - 1]] = rest.split()[0]
    assert len(results) == len(NAMES), out
    return rc, results, out


def drop_events(store, kind, outcome):
    path = store.root / events.EVENTS
    kept = [line for line in path.read_text().splitlines()
            if (json.loads(line)["kind"], json.loads(line)["outcome"]) != (kind, outcome)]
    path.write_text("".join(line + "\n" for line in kept))


def retext_work_order(store):
    path = store.root / workorder.WORK_ORDER
    record = json.loads(path.read_text())
    record["text"] += " Also create d.txt."
    path.write_text(json.dumps(record))


def test_passing_session_all_pass(tmp_path, monkeypatch, capsys):
    state, project, store = session(tmp_path, monkeypatch)
    assert store.root.parent.parent == state  # nested: STATE/chr-gate/KEY/
    rc, results, out = check(capsys, state, project)
    assert rc == 0, out
    assert set(results.values()) == {"PASS"}, out
    assert "RESULT: 6/6 PASS" in out


CASES = [
    (0, {}, lambda project, store: drop_events(store, "propose", "stored")),
    (1, {}, lambda project, store: retext_work_order(store)),
    (2, {"wrong_witness_accepted": True}, None),
    (3, {}, lambda project, store: drop_events(store, "open_gate", "open")),
    (4, {"second_write": False}, None),
    (5, {}, lambda project, store: (project / smoke_check.BUILTIN_FILE).write_text("charlie\n")),
]


@pytest.mark.parametrize("step, kwargs, damage", CASES, ids=[NAMES[c[0]] for c in CASES])
def test_each_failure_fails_exactly_its_step(tmp_path, monkeypatch, capsys, step, kwargs, damage):
    state, project, store = session(tmp_path, monkeypatch, **kwargs)
    if damage is not None:
        damage(project, store)
    rc, results, out = check(capsys, state, project)
    assert rc != 0, out
    assert {name for name, verdict in results.items() if verdict == "FAIL"} == {NAMES[step]}, out


def test_info_lines_never_change_the_exit_code(tmp_path, monkeypatch, capsys):
    state, project, store = session(tmp_path, monkeypatch)
    with store.lock():
        events.append(store, frame=FRAME, kind=smoke_check.HOOK_ERROR, outcome="error-KeyError")
        events.append(store, frame=FRAME, kind="tool:write_file",
                      outcome=smoke_check.NOT_MEDIATED)
    (state.parent / smoke_check.SESSION_FILE.format(host=claude_code.HOST)).write_text(
        f"{FRAME}\nother-session\n")
    rc, results, out = check(capsys, state, project)
    assert rc == 0 and set(results.values()) == {"PASS"}, out
    assert f"kind={smoke_check.HOOK_ERROR}" in out and f"outcome={smoke_check.NOT_MEDIATED}" in out
    assert f"INFO: host session id {FRAME}: is a frame id" in out
    assert "INFO: host session id other-session: is not a frame id" in out
