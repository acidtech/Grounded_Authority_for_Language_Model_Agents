import hashlib
import re

from chrgate.core import gate, nonces

FRAME = "session-A"
OTHER = "agent-B"


def _current(store, frame, nonce):
    with store.lock():
        return nonces.is_current(store, frame, nonce)


def test_nonce_valid_only_in_its_frame_and_epoch(store, issuer):
    issuer.read_work_order(FRAME)
    n = nonces.issue(store, FRAME)
    assert re.fullmatch(r"ctx:[0-9a-f]{16}", n)
    assert _current(store, FRAME, n)
    assert not _current(store, OTHER, n)
    other = nonces.issue(store, OTHER)
    assert not _current(store, FRAME, other)

    assert gate.new_epoch(store, FRAME) == 2
    assert not _current(store, FRAME, n)
    fresh = nonces.issue(store, FRAME)
    assert _current(store, FRAME, fresh)
    assert not _current(store, FRAME, n)
    assert _current(store, OTHER, other)  # another frame's epoch is untouched


def test_plaintext_nonce_absent_from_disk(store, isolated_env):
    issued = [nonces.issue(store, FRAME) for _ in range(3)] + [nonces.issue(store, OTHER)]
    files = [p for p in (isolated_env / "state").rglob("*") if p.is_file()]
    assert "nonces.json" in {p.name for p in files}
    for n in issued:
        for p in files:
            data = p.read_bytes()
            assert n.encode() not in data, p
            assert n.removeprefix("ctx:").encode() not in data, p
    with store.lock():
        registry = store.read(nonces.NONCES, None)
    assert registry[FRAME]["sha256"] == [hashlib.sha256(n.encode()).hexdigest()
                                         for n in issued[:3]]
