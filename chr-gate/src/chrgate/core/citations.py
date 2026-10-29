"""Citation tags and the Stage 1 citation warning.

The agent cites the context nonces it relies on in assistant text, canonical
form: <cite>ctx:... ctx:...</cite> (whitespace-separated nonces). The cite()
tool is the fallback source of the same nonce list (Claude Code); check() takes
a nonce list and does not care which source produced it.

parse(text) returns every cited token in order across all tags. A malformed
tag never raises: it yields its raw text as a token, which check() then
reports as invalid (an empty tag, an unclosed tag, a stray closing tag, a
non-canonical tag such as <cite x="1"> or <CITE>). check(frame, nonces)
returns ONLY the invalid tokens; warning_text(invalid) renders them as a
chr-citation-warning block, and is None when nothing is invalid, so all-valid
citations produce no output at all.
"""

import re
from collections.abc import Iterable
from xml.sax.saxutils import escape

from chrgate.core import events, nonces
from chrgate.core.store import Store
from chrgate.core.witness import check_frame_id

OPEN_TAG = "<cite>"
CLOSE_TAG = "</cite>"
WARNING_TAG = "chr-citation-warning"
# Anything that looks like an opening or closing cite tag, canonical or not.
_TAG_RE = re.compile(r"<\s*/?\s*cite\b[^<>]*>?", re.IGNORECASE)


def parse(text: str) -> list[str]:
    """Cited tokens of TEXT in order; malformed tags yield their raw text."""
    if not isinstance(text, str):
        raise TypeError(f"text must be a string, got {type(text).__name__}")
    cited: list[str] = []
    pending: re.Match[str] | None = None  # an open canonical tag awaiting </cite>

    def unclosed(opening: re.Match[str], end: int) -> None:
        body = text[opening.end():end].split()
        cited.append(OPEN_TAG + (body[0] if body else ""))

    for m in _TAG_RE.finditer(text):
        tag = m.group(0)
        if tag == CLOSE_TAG and pending is not None:
            body = text[pending.end():m.start()].split()
            cited.extend(body if body else [OPEN_TAG + CLOSE_TAG])
            pending = None
            continue
        if pending is not None:
            unclosed(pending, m.start())
            pending = None
        if tag == OPEN_TAG:
            pending = m
        else:
            cited.append(tag)
    if pending is not None:
        unclosed(pending, len(text))
    return cited


def check(store: Store, frame_id: str, cited: Iterable[str]) -> list[str]:
    """The invalid tokens of CITED, in order: malformed, unknown, issued to
    another frame or issued in an earlier epoch of FRAME_ID."""
    check_frame_id(frame_id)
    if isinstance(cited, str):
        raise TypeError("cited must be a list of nonces, not one string")
    tokens = list(cited)
    for token in tokens:
        if not isinstance(token, str):
            raise TypeError(f"cited nonces must be strings, got {type(token).__name__}")
    with store.lock():
        invalid = [t for t in tokens if not nonces.is_current(store, frame_id, t)]
        events.append(store, frame=frame_id, kind="citation_check",
                      outcome=f"invalid-{len(invalid)}" if invalid else "valid")
    return invalid


def warning_text(invalid: list[str]) -> str | None:
    """The chr-citation-warning block for INVALID, or None when it is empty."""
    if not invalid:
        return None
    lines = [f"<{WARNING_TAG}>",
             "These citations are not context nonces issued to you in this context; "
             "cite only ctx: nonces from tool results you received since your last "
             "compaction:"]
    lines += [f"<invalid>{escape(token)}</invalid>" for token in invalid]
    lines.append(f"</{WARNING_TAG}>")
    return "\n".join(lines)
