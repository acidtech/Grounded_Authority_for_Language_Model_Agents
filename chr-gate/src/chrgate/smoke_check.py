"""python -m chrgate.smoke_check --host HOST --state STATE --project PROJECT

The checker of one live smoke session (scripts/smoke, T7a). It finds the one
events.jsonl under STATE by searching (it never recomputes the project key, so
it also runs against copied outputs), reads the state files beside it
(proposals.json, workorder.json, frames.json) and the PROJECT folder, and
prints PASS or FAIL for each of the six smoke steps. Exit 0 only when all six
pass, 1 when any fails, 2 when the inputs cannot be checked at all.

INFO lines are diagnostics and never change the exit code: one line per event
with outcome refused-claude-no-ticket or refused-not-mediated or kind
hook_error, naming the attempted tool (or the hook error), the code and its
meaning, and the frame; and the frame ids seen in events.jsonl next to the
host session ids the smoke script saved in HOST-session.txt beside STATE.
"""

import argparse
import json
import sys
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from chrgate.core import claims, events, gate, workorder
from chrgate.hooks.adapters import claude_code, codex
from chrgate.server import tickets

HOSTS = (claude_code.HOST, codex.HOST)
EXPECTED_FILES = {"a.txt": "chr-gate smoke alpha", "b.txt": "chr-gate smoke bravo"}
BUILTIN_FILE = "c.txt"
BUILTIN_TOOL = {claude_code.HOST: "Write", codex.HOST: "apply_patch or shell"}
SAME_BATCH = "taken-same-batch"     # gate.take_gate outcome for the later calls of one batch
WRITE_OK = ("tool:write_file", "ok")  # GateServer.call event of an effective write_file
READ_OUTCOMES = ("issued", "reused")  # WitnessIssuer.read_work_order outcomes
NO_TICKET = "refused-" + tickets.CLAUDE_NO_TICKET
NOT_MEDIATED = "refused-not-mediated"
HOOK_ERROR = "hook_error"
REFUSAL_MEANING = {
    NO_TICKET.removeprefix("refused-"):
        "no PreToolUse ticket for this call, the chr-gate hook did not run for it",
    NOT_MEDIATED.removeprefix("refused-"):
        "no PreToolUse ticket names this call, which carried no Claude Code or Codex identity",
}
SESSION_FILE = "{host}-session.txt"


class CheckError(Exception):
    """The inputs cannot be checked at all (exit 2)."""


@dataclass(frozen=True)
class Run:
    events: list[dict[str, Any]]
    proposals: dict[str, Any]
    work_order: dict[str, Any] | None
    frames: dict[str, Any]
    project: Path

    @property
    def ref(self) -> str | None:
        wo = self.work_order
        return None if wo is None else workorder.WorkOrder(wo["id"], wo["version"], wo["text"]).ref


def find_state_root(state: Path) -> Path:
    """The folder of the one events.jsonl under STATE."""
    found = sorted(state.rglob(events.EVENTS)) if state.is_dir() else []
    if len(found) != 1:
        listed = "".join(f"\n  {p}" for p in found)
        raise CheckError(f"expected exactly one {events.EVENTS} under {state}, found "
                         f"{len(found)}{listed}")
    return found[0].parent


def _json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def load(state: Path, project: Path) -> Run:
    if not project.is_dir():
        raise CheckError(f"project {project} is not a directory")
    root = find_state_root(state)
    lines = (root / events.EVENTS).read_text(encoding="utf-8").splitlines()
    return Run(events=[json.loads(line) for line in lines if line],
               proposals=_json(root / workorder.PROPOSALS, {}),
               work_order=_json(root / workorder.WORK_ORDER, None),
               frames=_json(root / workorder.FRAMES, {}), project=project)


def _is(event: dict[str, Any], kind: str, outcome: str) -> bool:
    return event["kind"] == kind and event["outcome"] == outcome


def _activation(run: Run) -> int | None:
    """Index of the activation event of the active work order."""
    return next((i for i, e in enumerate(run.events)
                 if _is(e, "activate", "activated") and e["ref"] == run.ref), None)


def _content(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8").rstrip("\n")
    except FileNotFoundError:
        return None


Result = tuple[bool, str]


def step_proposal(run: Run, host: str) -> Result:
    stored = [e["ref"] for e in run.events if _is(e, "propose", "stored")]
    if not stored:
        return False, "no propose_plan event (kind propose, outcome stored) in events.jsonl"
    for plan in stored:
        record = run.proposals.get(plan)
        if record is not None and all(name in record["text"] for name in EXPECTED_FILES):
            return True, f"{plan} stored; its text names {', '.join(EXPECTED_FILES)}"
    return False, (f"proposal(s) {', '.join(stored)} missing from proposals.json or not naming "
                   f"{', '.join(EXPECTED_FILES)}")


def step_activation(run: Run, host: str) -> Result:
    wo = run.work_order
    if wo is None:
        return False, "no workorder.json: nothing was activated"
    plan = wo["plan_id"]
    if plan not in run.proposals:
        return False, f"active {run.ref} names plan {plan}, which is not in proposals.json"
    if wo["text"] != run.proposals[plan]["text"]:
        return False, f"active {run.ref} text differs from the text proposed under {plan}"
    if _activation(run) is None:
        return False, f"no activate event (outcome activated) for {run.ref}"
    return True, f"{plan} activated as {run.ref} with exactly the proposed text"


def step_wrong_witness(run: Run, host: str) -> Result:
    start = _activation(run)
    if start is None:
        return False, "no activation event, so no gate attempt under the work order"
    after = run.events[start:]
    first_open = next((i for i, e in enumerate(after) if _is(e, "open_gate", "open")), len(after))
    denied = next((e for e in after[:first_open] if _is(e, "open_gate", "denied")), None)
    if denied is None:
        return False, ("no refused open_gate (outcome denied) between the activation and the "
                       "first passing open_gate: the wrong witness was not refused")
    return True, (f"open_gate refused for frame {denied['frame']}; the server returns "
                  f"{gate.DENIED_TEXT!r} for this outcome")


def step_correct_witness(run: Run, host: str) -> Result:
    start = _activation(run)
    if start is None or run.work_order is None:
        return False, "no activation event"
    for i in range(start, len(run.events)):
        event = run.events[i]
        if not _is(event, "open_gate", "open"):
            continue
        frame = event["frame"]
        read = any(e["kind"] == "read_work_order" and e["outcome"] in READ_OUTCOMES
                   and e["ref"] == run.ref and e["frame"] == frame
                   for e in run.events[start:i])
        rec = run.frames.get(frame)
        if read and rec is not None and rec["governs"] == run.work_order["id"]:
            return True, (f"status then open_gate passed for frame {frame} ({event['ref']}); "
                          f"open_gate returns the full text of {run.ref}")
    return False, ("no passing open_gate after a status read of the active work order in the "
                   "same frame")


def step_parallel_writes(run: Run, host: str) -> Result:
    start = _activation(run)
    if start is None:
        return False, "no activation event"
    after = run.events[start:]
    takes = Counter(e["ref"] for e in after
                    if e["kind"] == "take_gate" and e["outcome"] in (gate.TAKEN, SAME_BATCH))
    batches = [e["ref"] for e in after if _is(e, "take_gate", gate.TAKEN) and takes[e["ref"]] >= 2]
    if not batches:
        return False, ("no gate opening taken by two calls of one batch (take_gate taken plus "
                       f"{SAME_BATCH})")
    accepted = sum(1 for e in after if _is(e, "claim", claims.ACCEPTED) and e["ref"] == run.ref)
    writes = sum(1 for e in after if _is(e, *WRITE_OK))
    if accepted < 2 or writes < 2:
        return False, (f"{accepted} accepted claim(s) citing {run.ref} and {writes} effective "
                       "write_file call(s); two of each are needed")
    wrong = [name for name, text in EXPECTED_FILES.items() if _content(run.project / name) != text]
    if wrong:
        return False, "missing or with other content: " + ", ".join(wrong)
    return True, (f"one batch under {batches[0]} took {takes[batches[0]]} calls; {accepted} claims "
                  f"accepted, {writes} write_file calls; {', '.join(EXPECTED_FILES)} hold the "
                  "expected content")


def step_builtin(run: Run, host: str) -> Result:
    tool = BUILTIN_TOOL[host]
    if (run.project / BUILTIN_FILE).exists():
        return False, f"{BUILTIN_FILE} exists: the built-in write ({tool}) was not denied"
    return True, (f"{BUILTIN_FILE} absent: the built-in write ({tool}) was denied by host config "
                  "or the hook (the step 6 stream shows which)")


STEPS: tuple[tuple[str, Callable[[Run, str], Result]], ...] = (
    ("proposal recorded", step_proposal),
    ("activation of exactly the proposed text", step_activation),
    (f"wrong witness refused with {gate.DENIED_TEXT!r}", step_wrong_witness),
    ("correct witness passed and the full text returned", step_correct_witness),
    ("two write_file calls in one batch, both with claims, both files right", step_parallel_writes),
    (f"built-in write denied and {BUILTIN_FILE} absent", step_builtin),
)


def info_lines(run: Run, state: Path, host: str) -> list[str]:
    """Diagnostics only; they never change the exit code."""
    out = []
    odd = [e for e in run.events
           if e["outcome"] in (NO_TICKET, NOT_MEDIATED) or e["kind"] == HOOK_ERROR]
    if odd:
        out.append(f"INFO: {len(odd)} refused or failed hook event(s):")
    else:
        out.append(f"INFO: no {NO_TICKET}, {NOT_MEDIATED} or {HOOK_ERROR} events")
    for e in odd:
        if e["kind"] == HOOK_ERROR:
            error = e["outcome"].removeprefix("error-")
            out.append(f"INFO:   {e['time']} hook failed ({HOOK_ERROR}, {e['outcome']}): the "
                       f"chr-gate hook raised {error}, it denies consequential chr-gate tools and "
                       f"built-in writes on an error and allows the rest; frame={e['frame']}")
        else:
            tool, code = e["kind"].removeprefix("tool:"), e["outcome"].removeprefix("refused-")
            out.append(f"INFO:   {e['time']} {tool} call refused ({code}): "
                       f"{REFUSAL_MEANING[code]}; frame={e['frame']}")
    frames = sorted({e["frame"] for e in run.events if e["frame"] is not None})
    out.append("INFO: frame ids in events.jsonl: " + (", ".join(frames) or "none"))
    session = state.parent / SESSION_FILE.format(host=host)
    if not session.is_file():
        out.append(f"INFO: no host session file {session}")
        return out
    for sid in (line.strip() for line in session.read_text(encoding="utf-8").splitlines()):
        if sid:
            verdict = "is" if sid in frames else "is not"
            out.append(f"INFO: host session id {sid}: {verdict} a frame id in events.jsonl")
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m chrgate.smoke_check",
                                     description="PASS/FAIL table of one chr-gate smoke session.")
    parser.add_argument("--host", required=True, choices=HOSTS)
    parser.add_argument("--state", required=True, type=Path, help="the smoke XDG_STATE_HOME")
    parser.add_argument("--project", required=True, type=Path, help="the scratch project")
    args = parser.parse_args(argv)
    try:
        run = load(args.state, args.project)
    except CheckError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    passed = 0
    for number, (name, step) in enumerate(STEPS, 1):
        ok, detail = step(run, args.host)
        passed += ok
        print(f"{number}. {'PASS' if ok else 'FAIL'}  {name}: {detail}")
    for line in info_lines(run, args.state, args.host):
        print(line)
    print(f"RESULT: {passed}/{len(STEPS)} PASS")
    return 0 if passed == len(STEPS) else 1


if __name__ == "__main__":
    sys.exit(main())
