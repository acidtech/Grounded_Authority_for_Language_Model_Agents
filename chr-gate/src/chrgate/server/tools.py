"""The chr-gate MCP tool set: ONE registry, TOOLS, and GateServer, the only
effect path and the only witness issuer (one WitnessIssuer per process).

GateServer.call(name, arguments, meta, client_name) takes the RAW tools/call
arguments in received order. Every call is attributed to a frame first
(tickets.py). A consequential call (write_file, edit_file, mutate_shell,
delegate, testify) is refused unless it is mediated; then check_claim (T1b)
runs on the raw arguments, so the first key must be claim; write_file,
edit_file and mutate_shell refuse while a required protected path is missing
(fail closed: the user runs chrgate-setup); paths are checked; then
gate.take_gate is the single gate check, and only then does the effect run. A
refusal before take_gate changes no gate state. On Codex every
non-consequential call reports its itemId with gate.note_turn (Claude Code
turns are reported by the T3 hooks at PostToolBatch).

status (alias read_work_order) delivers the frame's work order and witness and
cancels its pending gate. A subagent frame (Claude Code agent_id in the
ticket, Codex parent_thread_id) that is not registered yet must present the
delegation id from its launch prompt; the server binds it (delegation.
bind_child) before the read, so the child is governed by the delegated work
order. On Codex, open_gate in the same itemId as the read that delivered the
witness is refused.

Every result carries a fresh context nonce (nonces.issue) and appends one
events.jsonl entry. Sandbox refusals pass their message through unchanged; an
invalid config.json is reported as a configuration error naming the file.
"""

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from chrgate.core import (citations, claims, delegation, events, gate, nonces, paths,
                          testimony, workorder)
from chrgate.core.claims import Refused
from chrgate.core.config import ConfigError
from chrgate.core.store import Store
from chrgate.core.witness import NoActiveWorkOrder, WitnessIssuer
from chrgate.server import sandbox, tickets

SHELL_TIMEOUT_SECONDS = 120
MAX_OUTPUT_BYTES = 64 * 1024
NONCE_LABEL = "chr-gate context nonce: "
NO_WORK_ORDER_TEXT = ("no active work order: propose one with propose_plan and ask the user "
                      "to approve it")
DELEGATION_ENDED_TEXT = ("your delegation ended: the work order that delegated to you was "
                         "revised, so your delegated work order no longer holds; stop and "
                         "report back to your caller")
SAME_CELL_TEXT = (gate.DENIED_TEXT + ": open_gate must run in a later code cell than the "
                  "status/read_work_order call that delivered the witness")
EFFECT_TOOLS = ("write_file", "edit_file", "mutate_shell")
NO_TURN_KEY_CODE = "no-turn-key"
SANDBOX_ERRORS = (sandbox.ProtectedPathMissing, sandbox.ProtectedPathSymlink,
                  sandbox.GitFileUnsupported, sandbox.GitConfigUnreadable,
                  sandbox.FolderUnreadable, sandbox.BwrapNotFound)

_CLAIM = {"type": "string", "description": "Why this call is authorized; must cite your work "
          "order reference wo:ID.vN. Must be the FIRST argument."}
_FILE_NOTE = ("a path mutate_shell holds read-only: .git/, .claude/, .codex/, "
              ".mcp.json, the masked names such as .vscode/ or .gitmodules, and the paths "
              "the git configuration names")
_SHELL_NOTE = ("The project's .git tree is read-only inside the sandbox: you cannot stage, "
               "commit or branch; the user runs git.")


def _str(description: str) -> dict[str, Any]:
    return {"type": "string", "description": description}


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    properties: dict[str, dict[str, Any]]
    required: tuple[str, ...]
    consequential: bool
    handler: str

    @property
    def input_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": dict(self.properties),
                "required": list(self.required), "additionalProperties": False}


_STATUS_DESC = ("Read your active work order: returns its reference, full text and your "
                "witness for open_gate (the same witness on every read in this context), and "
                "cancels any pending open gate. A subagent's first read must pass the "
                "delegation id from its launch prompt.")
_STATUS_PROPS = {"delegation_id": _str("Delegation id from your launch prompt (subagents).")}

TOOLS: tuple[Tool, ...] = (
    Tool("status", _STATUS_DESC, _STATUS_PROPS, (), False, "status"),
    Tool("read_work_order", "Alias of status. " + _STATUS_DESC, _STATUS_PROPS, (), False,
         "status"),
    Tool("open_gate", "Open the action gate with the witness from status. A pass returns "
         "your full work order; any failure returns 'read your work order'. Make "
         "consequential calls in a later turn.",
         {"witness": _str("The witness returned by status.")}, ("witness",), False,
         "open_gate"),
    Tool("cite", "Report the context nonces (ctx:...) you rely on. Returns nothing but a "
         "fresh nonce when all are valid, else a warning naming the invalid ones.",
         {"nonces": {"type": "array", "items": {"type": "string"},
                     "description": "The ctx: nonces you cite."}}, ("nonces",), False, "cite"),
    Tool("propose_plan", "Propose a work order; returns its plan id and the exact phrase "
         "'approve P-xxxxxxxx' the user replies with to approve it.",
         {"text": _str("Full work order text.")}, ("text",), False, "propose_plan"),
    Tool("research_shell", "Run a read-only shell command in the project: no network, the "
         "project and state are read-only. " + _SHELL_NOTE,
         {"command": _str("bash command.")}, ("command",), False, "research_shell"),
    Tool("write_file", f"Write a file inside the project (never {_FILE_NOTE}). Needs an open gate.",
         {"claim": _CLAIM, "path": _str("Path relative to the project root."),
          "content": _str("Full new file content.")}, ("claim", "path", "content"), True,
         "write_file"),
    Tool("edit_file", "Replace the one occurrence of old with new in a project file "
         f"(never {_FILE_NOTE}). Needs an open gate.",
         {"claim": _CLAIM, "path": _str("Path relative to the project root."),
          "old": _str("Text that occurs exactly once."), "new": _str("Replacement text.")},
         ("claim", "path", "old", "new"), True, "edit_file"),
    Tool("mutate_shell", "Run a shell command that may change the project (network allowed). "
         "Needs an open gate. " + _SHELL_NOTE + " Empty placeholder files or folders (such "
         "as .vscode or .gitmodules) may appear in the project while a mutate_shell run is "
         "in progress; they are removed afterwards.",
         {"claim": _CLAIM, "command": _str("bash command.")}, ("claim", "command"), True,
         "mutate_shell"),
    Tool("delegate", "Delegate a work order to a consequential subagent under your open gate; "
         "returns a delegation id to put in the subagent's launch prompt.",
         {"claim": _CLAIM, "work_order": _str("The delegated work order text.")},
         ("claim", "work_order"), True, "delegate"),
    Tool("testify", "Record testimony under your open gate.",
         {"claim": _CLAIM, "text": _str("Testimony text.")}, ("claim", "text"), True,
         "testify"),
)
TOOLS_BY_NAME = {tool.name: tool for tool in TOOLS}


class ToolError(Exception):
    """A tool call was refused or failed; the message goes to the caller."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _turn_key(tool_name: str, caller: tickets.Caller) -> str:
    """The caller's turn key; a call without one is refused, fail closed."""
    if isinstance(caller.turn_key, str):
        return caller.turn_key
    raise ToolError(NO_TURN_KEY_CODE, f"{tool_name} refused: the call carries no turn key "
                    "(internal attribution error); refused, fail closed")


@dataclass(frozen=True)
class Outcome:
    text: str
    is_error: bool


def _accepted(tool: Tool) -> str:
    """The tool's accepted arguments in schema order, required ones marked."""
    return "accepted: " + ", ".join(f"{key} (required)" if key in tool.required else key
                                    for key in tool.properties)


def _args(tool: Tool, raw: Mapping[str, Any]) -> dict[str, Any]:
    unknown = [key for key in raw if key not in tool.properties]
    if unknown:
        raise ToolError("bad-arguments",
                        f"{tool.name}: unknown argument(s) {unknown}; {_accepted(tool)}")
    for key in tool.required:
        if key not in raw:
            raise ToolError("bad-arguments",
                            f"{tool.name}: missing argument {key!r}; {_accepted(tool)}")
    for key, value in raw.items():
        if tool.properties[key]["type"] == "array":
            ok = isinstance(value, list) and all(isinstance(v, str) for v in value)
        else:
            ok = isinstance(value, str)
        if not ok:
            raise ToolError("bad-arguments", f"{tool.name}: {key} must be "
                            f"{tool.properties[key]['type']}")
    return dict(raw)


def _shell_text(result: sandbox.RunResult) -> str:
    return f"exit code: {result.rc}\n[stdout]\n{result.stdout}\n[stderr]\n{result.stderr}"


class GateServer:
    """The server state for one project: its Store and its single witness issuer."""

    def __init__(self, project: str | os.PathLike[str]) -> None:
        self.project = Path(os.path.realpath(project))
        self.state_root = paths.state_root(self.project)
        self.store = Store(self.state_root)
        self.issuer = WitnessIssuer(self.store)
        self._witness_cell: dict[str, str] = {}  # Codex frame -> itemId of its last read

    def call(self, name: str, arguments: Mapping[str, Any] | None,
             meta: Mapping[str, Any] | None = None, client_name: str | None = None) -> Outcome:
        tool = TOOLS_BY_NAME.get(name)
        frame = tickets.root_frame()
        kind = f"tool:{name}" if tool is not None else "tool:unknown"
        raw = {} if arguments is None else arguments
        try:
            if tool is None:
                raise ToolError("unknown-tool", f"unknown tool {name!r}")
            caller = tickets.attribute(self.store, name, dict(meta or {}), client_name)
            frame = caller.frame
            if tool.consequential:
                text = self._consequential(tool, caller, raw)
            else:
                turn_key = _turn_key(name, caller) if caller.host == tickets.CODEX else None
                text = getattr(self, "_" + tool.handler)(caller, _args(tool, raw))
                if turn_key is not None:
                    gate.note_turn(self.store, caller.frame, turn_key)
            code, is_error = "ok", False
        except tickets.AttributionRefused as e:
            frame, code, text, is_error = e.frame, e.code, e.message, True
        except (ToolError, Refused) as e:
            code, text, is_error = e.code, e.message, True
        except ConfigError as e:
            code, text, is_error = "configuration-error", f"chr-gate configuration error: {e}", True
        except SANDBOX_ERRORS as e:
            code, text, is_error = "sandbox-refused", str(e), True
        except ValueError as e:
            code, text, is_error = "invalid-argument", f"{name}: {e}", True
        nonce = nonces.issue(self.store, frame)
        with self.store.lock():
            events.append(self.store, frame=frame, kind=kind,
                          outcome=f"refused-{code}" if is_error else code)
        return Outcome(f"{text}\n\n{NONCE_LABEL}{nonce}" if text else NONCE_LABEL + nonce,
                       is_error)

    # consequential dispatch

    def _consequential(self, tool: Tool, caller: tickets.Caller,
                       raw: Mapping[str, Any]) -> str:
        if not caller.mediated:
            raise ToolError("not-mediated", f"{tool.name} refused: the call is not mediated "
                            "(no PreToolUse ticket names it); consequential tools run only "
                            "through the chr-gate hooks")
        result = claims.check_claim(self.store, caller.frame, tool.name, raw)
        if not result.ok:
            if result.code == claims.NO_WORK_ORDER and self._lapsed(caller.frame):
                raise ToolError("delegation-ended", DELEGATION_ENDED_TEXT)
            raise ToolError(result.code, result.message)
        args = _args(tool, raw)
        if tool.name in EFFECT_TOOLS:
            self._require_protected(tool.name)
        target = self._target(tool.name, args["path"]) if "path" in args else None
        taken = gate.take_gate(self.store, caller.frame, _turn_key(tool.name, caller))
        if not taken.ok:
            raise ToolError(taken.code, taken.message)
        return getattr(self, "_" + tool.handler)(caller, args, target)

    def _require_protected(self, tool: str) -> None:
        missing = sandbox.missing_protected(self.project)
        if not missing:
            return
        names = ", ".join(str(p.relative_to(self.project)) for p in missing)
        message = (f"{tool} refused: required protected path(s) missing: {names}. Ask the user "
                   f"to run chrgate-setup in the project root ({self.project}); chr-gate tools "
                   "never create them.")
        if any(p.parts[-2:] == (".git", "config") for p in missing):
            message += " A missing .git/config needs a git repair; chrgate-setup never creates it."
        raise ToolError("protected-path-missing", message)

    def _target(self, tool: str, path: str) -> Path:
        if not path:
            raise ToolError("bad-path", f"{tool}: path must be non-empty")
        target = Path(os.path.realpath(self.project / path))
        if not target.is_relative_to(self.project) or target == self.project:
            raise ToolError("path-outside-project", f"{tool}: {path!r} resolves outside the "
                            f"project root {self.project}")
        rel = target.relative_to(self.project)
        protected = [q for p in sandbox.read_only_paths(self.project)
                     for q in (p, Path(os.path.realpath(p)))]
        if ".git" in rel.parts or any(target.is_relative_to(p) for p in protected):
            raise ToolError("path-protected", f"{tool}: {path!r} is protected; write_file and "
                            f"edit_file never touch {_FILE_NOTE}")
        return target

    def _lapsed(self, frame: str) -> bool:
        """FRAME is governed by a delegated work order that no longer holds."""
        with self.store.lock():
            rec = self.store.read(workorder.FRAMES, {}).get(frame)
            return (rec is not None and rec["governs"].startswith(delegation.DELEGATED_PREFIX)
                    and workorder.resolve(self.store, rec["governs"]) is None)

    # non-consequential handlers

    def _status(self, caller: tickets.Caller, args: dict[str, Any]) -> str:
        delegation_id = args.get("delegation_id")
        if caller.subagent and delegation_id is None:
            with self.store.lock():
                registered = caller.frame in self.store.read(workorder.FRAMES, {})
            if not registered:
                raise ToolError("delegation-id-required", "a subagent's first work order read "
                                "must present the delegation id from its launch prompt: "
                                "status(delegation_id=...)")
        if delegation_id is not None:
            if caller.host == tickets.CODEX:
                self._check_codex_parent(caller, delegation_id)
            delegation.bind_child(self.store, caller.frame, delegation_id)
        try:
            read = self.issuer.read_work_order(caller.frame)
        except NoActiveWorkOrder:
            if self._lapsed(caller.frame):
                raise ToolError("delegation-ended", DELEGATION_ENDED_TEXT) from None
            return NO_WORK_ORDER_TEXT
        if caller.host == tickets.CODEX:
            self._witness_cell[caller.frame] = caller.turn_key
        return (f"work order {read.ref}\nwitness: {read.witness}\nCall open_gate with this "
                f"witness, then cite {read.ref} in the claim of each consequential call.\n"
                f"--- work order text ---\n{read.text}")

    def _check_codex_parent(self, caller: tickets.Caller, delegation_id: str) -> None:
        with self.store.lock():
            records = self.store.read(workorder.DELEGATIONS, {}).values()
            record = next((r for r in records if r["delegation_id"] == delegation_id), None)
        if record is not None and record["caller_frame"] != caller.parent_frame:
            raise ToolError("delegation-parent-mismatch", "this delegation was made by another "
                            "thread than your parent thread")

    def _open_gate(self, caller: tickets.Caller, args: dict[str, Any]) -> str:
        if (caller.host == tickets.CODEX
                and self._witness_cell.get(caller.frame) == caller.turn_key):
            raise ToolError("same-cell", SAME_CELL_TEXT)
        result = gate.open_gate(self.store, caller.frame, args["witness"],
                                turn_key=caller.turn_key)
        if result.status != gate.OPEN:
            raise ToolError("denied", result.message)
        return f"{result.message}\n--- work order text ---\n{result.text}"

    def _cite(self, caller: tickets.Caller, args: dict[str, Any]) -> str:
        warning = citations.warning_text(citations.check(self.store, caller.frame,
                                                         args["nonces"]))
        return warning or ""

    def _propose_plan(self, caller: tickets.Caller, args: dict[str, Any]) -> str:
        plan_id = workorder.propose(self.store, args["text"])
        return (f"proposed plan {plan_id}. Ask the user to approve it by replying exactly:\n"
                f"approve {plan_id}")

    def _research_shell(self, caller: tickets.Caller, args: dict[str, Any]) -> str:
        argv = sandbox.research_argv(self.project, self.state_root, args["command"])
        return _shell_text(sandbox.run(argv, SHELL_TIMEOUT_SECONDS, MAX_OUTPUT_BYTES))

    # consequential handlers (gate taken)

    def _write_file(self, caller: tickets.Caller, args: dict[str, Any], target: Path) -> str:
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            with open(target, "w", encoding="utf-8", newline="") as fh:
                fh.write(args["content"])
        except OSError as e:
            raise ToolError("write-failed", f"write_file: {e}") from e
        return f"wrote {target.relative_to(self.project)}"

    def _edit_file(self, caller: tickets.Caller, args: dict[str, Any], target: Path) -> str:
        old = args["old"]
        if not old:
            raise ToolError("bad-arguments", "edit_file: old must be non-empty")
        try:
            with open(target, encoding="utf-8", newline="") as fh:
                text = fh.read()
            count = text.count(old)
            if count != 1:
                raise ToolError("old-not-unique", f"edit_file: old occurs {count} times in "
                                f"{target.relative_to(self.project)}; it must occur exactly once")
            with open(target, "w", encoding="utf-8", newline="") as fh:
                fh.write(text.replace(old, args["new"], 1))
        except OSError as e:
            raise ToolError("edit-failed", f"edit_file: {e}") from e
        return f"edited {target.relative_to(self.project)}"

    def _mutate_shell(self, caller: tickets.Caller, args: dict[str, Any], target: None) -> str:
        return _shell_text(sandbox.run_mutate(self.project, self.state_root, args["command"],
                                              SHELL_TIMEOUT_SECONDS, MAX_OUTPUT_BYTES))

    def _delegate(self, caller: tickets.Caller, args: dict[str, Any], target: None) -> str:
        d = delegation.delegate(self.store, caller.frame, args["claim"], args["work_order"])
        return (f"delegated work order {d.ref}\ndelegation id: {d.delegation_id}\nPut this "
                "delegation id in the subagent's launch prompt; its first status call must "
                "pass it as delegation_id.")

    def _testify(self, caller: tickets.Caller, args: dict[str, Any], target: None) -> str:
        entry = testimony.record(self.store, caller.frame, args["claim"], args["text"])
        return f"testimony recorded under {entry['work_order']}"
