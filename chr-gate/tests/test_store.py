import hashlib
import os
import threading
import time

import pytest

from chrgate.core import paths
from chrgate.core.store import Store


def test_atomic_write_leaves_no_partial_file(store, monkeypatch):
    with store.lock():
        store.write("x.json", {"a": 1})
    before = (store.root / "x.json").read_bytes()

    # Serialisation fails after part of the JSON reached the temp file.
    with store.lock(), pytest.raises(TypeError):
        store.write("x.json", {"a": 2, "z": object()})

    # The process "crashes" just before the rename.
    def refuse(src, dst):
        raise OSError("simulated crash before rename")

    with store.lock(), monkeypatch.context() as m:
        m.setattr(os, "replace", refuse)
        with pytest.raises(OSError, match="simulated"):
            store.write("x.json", {"a": 3})

    assert (store.root / "x.json").read_bytes() == before
    assert sorted(p.name for p in store.root.iterdir()) == [".lock", "x.json"]
    with store.lock():
        assert store.read("x.json", None) == {"a": 1}


def test_lock_serializes_two_writers(store):
    rounds = 40

    def writer():
        own = Store(store.root)  # its own lock descriptor, like a second process
        for _ in range(rounds):
            with own.lock():
                n = own.read("counter.json", {"n": 0})["n"]
                time.sleep(0.001)  # widen the read-modify-write window
                own.write("counter.json", {"n": n + 1})

    threads = [threading.Thread(target=writer) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    with store.lock():
        assert store.read("counter.json", None) == {"n": 2 * rounds}


def test_project_key_stable_for_same_realpath(isolated_env, monkeypatch):
    project = isolated_env / "project"
    link = isolated_env / "link"
    link.symlink_to(project, target_is_directory=True)

    key = paths.project_key(project)
    assert key == hashlib.sha256(os.fsencode(os.path.realpath(project))).hexdigest()[:16]
    assert paths.project_key(link) == key
    assert paths.project_key(f"{project}/.") == key
    assert paths.project_key(isolated_env / "home") != key

    from_env = paths.state_root()  # CHR_GATE_PROJECT=project
    assert from_env == isolated_env / "state" / "chr-gate" / key
    monkeypatch.setenv("CHR_GATE_PROJECT", str(link))
    assert paths.state_root() == from_env
    monkeypatch.delenv("CHR_GATE_PROJECT")
    monkeypatch.chdir(link)
    assert paths.state_root() == from_env
