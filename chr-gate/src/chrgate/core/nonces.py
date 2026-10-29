"""Context nonces that citations name (Stage 1 citation warnings).

issue(frame) returns 'ctx:' plus 16 hex characters (64 random bits) for one
tool result. The registry (nonces.json) keeps only sha256 of each nonce, per
frame and epoch: {frame: {"epoch": N, "sha256": [...]}}. A nonce is current
only in the frame it was issued to and only while that frame is in the epoch
it was issued in, so a new epoch (gate.new_epoch) clears the frame's set: the
old hashes stop counting at once, and the first issue of the new epoch
replaces them on disk.
"""

import hashlib
import re
import secrets

from chrgate.core import workorder
from chrgate.core.store import Store
from chrgate.core.witness import check_frame_id

NONCES = "nonces.json"
NONCE_PREFIX = "ctx:"
NONCE_RE = re.compile(r"ctx:[0-9a-f]{16}")
FIRST_EPOCH = 1  # a frame with no record yet starts here (workorder.new_frame)


def nonce_sha256(nonce: str) -> str:
    return hashlib.sha256(nonce.encode("utf-8", "surrogatepass")).hexdigest()


def _epoch(store: Store, frame_id: str) -> int:
    rec = store.read(workorder.FRAMES, {}).get(frame_id)
    return FIRST_EPOCH if rec is None else rec["epoch"]


def issue(store: Store, frame_id: str) -> str:
    """A fresh nonce for one tool result delivered to FRAME_ID."""
    check_frame_id(frame_id)
    nonce = NONCE_PREFIX + secrets.token_hex(8)
    with store.lock():
        registry = store.read(NONCES, {})
        epoch = _epoch(store, frame_id)
        entry = registry.get(frame_id)
        if entry is None or entry["epoch"] != epoch:
            entry = registry[frame_id] = {"epoch": epoch, "sha256": []}
        entry["sha256"].append(nonce_sha256(nonce))
        store.write(NONCES, registry)
    return nonce


def is_current(store: Store, frame_id: str, nonce: object) -> bool:
    """NONCE is well formed and was issued to FRAME_ID in its current epoch;
    the caller holds store.lock()."""
    if not isinstance(nonce, str) or NONCE_RE.fullmatch(nonce) is None:
        return False
    entry = store.read(NONCES, {}).get(frame_id)
    return (entry is not None and entry["epoch"] == _epoch(store, frame_id)
            and nonce_sha256(nonce) in entry["sha256"])
