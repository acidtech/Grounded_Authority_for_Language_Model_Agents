"""Codex citation check against a real rollout (debt 101d2d): the fixture is
lines 95-131 of the 2026-10-29 smoke rollout, one whole turn from task_started
to task_complete, committed byte-for-byte."""

import json
from pathlib import Path

from chrgate.hooks.transcript import new_assistant_text

FIXTURE = Path(__file__).parent / "fixtures" / "transcripts" / "codex_rollout_cite_turn.jsonl"

ASSISTANT_TEXTS = [
    "I’m using the chr-gate skill, which requires reading its rules before writing files. "
    "Then I’ll make the two `write_file` calls in parallel, each with its own work-order claim.",
    "<cite>ctx:b495f30fc28b56f3 ctx:c2f7c2f4040c9078</cite>",
    "DONE.",
]
DEVELOPER_NONCES = ["ctx:60926b5fd4d2df81", "ctx:6beed60a09fe384e", "ctx:c87e80ee7e99d68c"]


def test_real_codex_rollout_assistant_text(store):
    text = new_assistant_text(store, "thread-real", str(FIXTURE))
    assert text == "\n".join(ASSISTANT_TEXTS)
    assert "ctx:b495f30fc28b56f3" in text
    assert "ctx:c2f7c2f4040c9078" in text
    for nonce in DEVELOPER_NONCES:
        assert nonce not in text
    assert "chr-gate smoke test, step 5" not in text


def test_real_codex_rollout_read_once(store):
    assert new_assistant_text(store, "thread-real", str(FIXTURE)) != ""
    assert new_assistant_text(store, "thread-real", str(FIXTURE)) == ""


def test_real_codex_rollout_record_mix():
    lines = [line for line in FIXTURE.read_text(encoding="utf-8").split("\n") if line.strip()]
    assert len(lines) == 37
    records = [json.loads(line) for line in lines]
    record_types = {r["type"] for r in records}
    assert {"response_item", "event_msg", "turn_context", "token_usage_record"} <= record_types
    payload_types = {r["payload"].get("type") for r in records}
    assert {"reasoning", "custom_tool_call"} <= payload_types
