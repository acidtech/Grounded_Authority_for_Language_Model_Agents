"""Assistant text written since the last citation check (docs/spike-findings.md
item 4 and 'Mechanism choices').

Codex: transcript_path is the session rollout, one JSON record per line; the
assistant text is on response_item records whose payload is a message with role
assistant (output_text content parts). The rollout already holds that text at
PreToolUse. Claude Code: the assistant text is not in the transcript in time
(FALLBACK), so its adapter never reads the transcript and the agent uses the
cite(nonces) tool instead.

new_assistant_text(frame, path) returns the assistant text of the complete
lines added since the frame's last check and records the new line count in
hook_transcripts.json ({frame: {"path", "lines"}}). A changed path, or a file
shorter than the recorded count, starts again from line 1.
"""

import json
from typing import Any

from chrgate.core.store import Store

OFFSETS = "hook_transcripts.json"


def _assistant_texts(record: dict[str, Any]) -> list[str]:
    if record.get("type") != "response_item":
        return []
    payload = record["payload"]
    if payload.get("type") != "message" or payload.get("role") != "assistant":
        return []
    return [part["text"] for part in payload["content"] if part.get("type") == "output_text"]


def new_assistant_text(store: Store, frame_id: str, path: str) -> str:
    """Assistant text of FRAME_ID's transcript PATH written since the last call."""
    with open(path, encoding="utf-8") as fh:
        raw = fh.read()
    lines = raw.split("\n")[:-1]  # complete lines only; a partial last line waits
    with store.lock():
        offsets = store.read(OFFSETS, {})
        seen = offsets.get(frame_id)
        start = (seen["lines"] if seen is not None and seen["path"] == path
                 and seen["lines"] <= len(lines) else 0)
        offsets[frame_id] = {"path": path, "lines": len(lines)}
        store.write(OFFSETS, offsets)
    texts: list[str] = []
    for line in lines[start:]:
        if line.strip():
            texts += _assistant_texts(json.loads(line))
    return "\n".join(texts)
