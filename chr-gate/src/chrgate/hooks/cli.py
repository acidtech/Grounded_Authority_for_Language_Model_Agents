"""chrgate-hook --host claude-code|codex: one hook payload on stdin, the
host-format decision on stdout (nothing when there is nothing to say), exit 0.

A hook error is logged to events.jsonl (kind hook_error) and stderr; it fails
closed for consequential chr-gate tools and built-in writes (deny) and open for
everything else. A payload that cannot be parsed at all is denied when it is
not known to be a non-PreToolUse event.
"""

import argparse
import json
import sys
from types import ModuleType

from chrgate.core import events
from chrgate.core.store import Store
from chrgate.hooks import engine
from chrgate.hooks.adapters import PRE_TOOL_EVENT, claude_code, codex, deny_json, render

ADAPTERS: dict[str, ModuleType] = {claude_code.HOST: claude_code, codex.HOST: codex}


def _log_error(store: Store, frame: str | None, error: BaseException) -> None:
    print(f"chrgate-hook error: {type(error).__name__}: {error}", file=sys.stderr)
    with store.lock():
        events.append(store, frame=frame, kind="hook_error",
                      outcome=f"error-{type(error).__name__}")


def _hook_event(raw: str) -> str | None:
    try:
        payload = json.loads(raw)
    except ValueError:
        return None
    name = payload.get("hook_event_name") if isinstance(payload, dict) else None
    return name if isinstance(name, str) else None


def run(host: str, raw: str, store: Store) -> str:
    """The stdout text for one payload RAW from HOST."""
    adapter = ADAPTERS[host]
    try:
        event = adapter.parse(json.loads(raw))
    except Exception as e:  # unparseable payload: logged, then fail closed
        _log_error(store, None, e)
        name = _hook_event(raw)
        if name is None or name == PRE_TOOL_EVENT:
            return deny_json(PRE_TOOL_EVENT, engine.FAIL_CLOSED_TEXT.format(
                error=type(e).__name__, tool="this call"))
        return ""
    if event is None:
        return ""
    try:
        decision = engine.handle(store, event)
    except Exception as e:  # logged, then fail closed or open by event
        _log_error(store, event.frame, e)
        decision = engine.failure_decision(event, e)
    return render(event, decision)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="chrgate-hook", description=__doc__)
    parser.add_argument("--host", required=True, choices=sorted(ADAPTERS))
    args = parser.parse_args(argv)
    out = run(args.host, sys.stdin.read(), Store.for_project())
    if out:
        sys.stdout.write(out + "\n")
    return 0
