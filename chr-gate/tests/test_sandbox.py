"""The research and mutate bwrap profiles. The project and the state root
live under the suite's /tmp basetemp, the case where a read-only bind only
holds because it comes after --bind /tmp /tmp. These tests need bwrap and
fail (never skip) without it."""

import inspect
import json
import os
import shlex
import shutil
import stat
import subprocess
import threading
import time
from pathlib import Path

import pytest

from chrgate.core import paths
from chrgate.core.store import LOCK_NAME as STORE_LOCK_NAME
from chrgate.core.store import Store
from chrgate.server import sandbox
from chrgate.server.sandbox import (LOCK_NAME, MANIFEST_NAME, MASKED, MASKED_DIRS, MASKED_FILES,
                                    FolderUnreadable, GitConfigUnreadable, GitFileUnsupported,
                                    ProtectedPathMissing, ProtectedPathSymlink, _mutate_argv,
                                    _project_lock, ensure_protected, protected_paths,
                                    read_only_paths, research_argv, run, run_mutate)
from chrgate.server.tools import SANDBOX_ERRORS

TIMEOUT = 60
MAX_OUTPUT = 1 << 16


def _git(project: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(project), "-c", "user.name=t", "-c", "user.email=t@example.invalid",
         *args], check=True, capture_output=True, text=True).stdout


def _git_init(project: Path) -> None:
    _git(project, "init", "-q")
    (project / ".git" / "hooks").mkdir(exist_ok=True)
    (project / "README").write_text("hello\n")
    _git(project, "add", "README")
    _git(project, "commit", "-q", "-m", "init")


@pytest.fixture
def project(isolated_env):
    root = (isolated_env / "project").resolve()
    assert str(root).startswith("/tmp/")
    _git_init(root)
    ensure_protected(root, paths.state_root(root))
    return root


@pytest.fixture
def state(project):
    root = paths.state_root(project)
    assert str(root).startswith("/tmp/")
    return root


def _sh(argv):
    return run(argv, TIMEOUT, MAX_OUTPUT)


def _at(argv, flag, path) -> int:
    triple = [flag, str(path), str(path)]
    for i in range(len(argv) - 2):
        if argv[i:i + 3] == triple:
            return i
    raise AssertionError(f"{triple} not in {argv}")


def _snap(targets):
    out = {}
    for p in targets:
        if p.is_dir():
            out[str(p)] = sorted((str(f.relative_to(p)), f.read_bytes() if f.is_file() else None)
                                 for f in p.rglob("*"))
        else:
            out[str(p)] = p.read_bytes()
    return out


def test_research_cannot_write_project(project, state):
    r = _sh(research_argv(project, state, "echo ran; echo x > new.txt"))
    assert "ran" in r.stdout, r.stderr
    assert r.rc != 0
    assert "Read-only file system" in r.stderr
    assert not (project / "new.txt").exists()


def test_research_can_write_tmp(isolated_env, project, state):
    other = isolated_env / "elsewhere"
    other.mkdir()
    target = other / "f.txt"
    r = _sh(research_argv(project, state, f"echo hi > {shlex.quote(str(target))}"))
    assert r.rc == 0, r.stderr
    assert target.read_text() == "hi\n"


def test_research_has_no_network(project, state):
    r = _sh(research_argv(project, state, "cat /proc/net/dev"))
    assert r.rc == 0, r.stderr
    names = [line.split(":")[0].strip() for line in r.stdout.splitlines()[2:] if ":" in line]
    assert names == ["lo"]
    start = time.monotonic()
    r = _sh(research_argv(project, state, "echo ran; exec 3<>/dev/tcp/192.0.2.1/9"))
    assert time.monotonic() - start < 5
    assert "ran" in r.stdout, r.stderr
    assert r.rc != 0
    assert "unreachable" in r.stderr.lower()


def test_research_cannot_write_state_root(project, state):
    planted = state / "planted"
    r = _sh(research_argv(project, state, f"echo ran; echo x > {shlex.quote(str(planted))}"))
    assert "ran" in r.stdout, r.stderr
    assert r.rc != 0
    assert not planted.exists()


def test_mutate_can_write_project(project, state):
    r = _mutate(project, state, "echo x > new.txt")
    assert r.rc == 0, r.stderr
    assert (project / "new.txt").read_text() == "x\n"


def test_every_protected_path_read_only_in_mutate_shell(project, state):
    prot = protected_paths(project)
    rels = {p.relative_to(project).as_posix() for p in prot}
    assert {".claude", ".codex", ".mcp.json", ".git/hooks", ".git/config"} <= rels
    before = _snap(prot)
    attempts = []
    for p in prot:
        q = shlex.quote(str(p))
        if p.is_dir():
            attempts += [f"touch {q}/planted", f"rm -rf {q}", f"mv {q} {q}.moved"]
        else:
            attempts += [f"echo x >> {q}", f"rm -f {q}", f"mv {q} {q}.moved"]
    attempts.append(f"touch {shlex.quote(str(state / 'planted'))}")
    script = "echo ran > control.txt\n" + "".join(
        f"if {a} 2>/dev/null; then echo {shlex.quote('OK: ' + a)}; fi\n" for a in attempts)
    r = _mutate(project, state, script)
    assert r.rc == 0, r.stderr
    assert (project / "control.txt").read_text() == "ran\n"
    assert "OK:" not in r.stdout, r.stdout
    assert _snap(prot) == before
    assert not (state / "planted").exists()


@pytest.mark.parametrize("name", [".claude", ".codex", ".mcp.json"])
def test_mutate_refuses_when_protected_path_absent(project, state, name):
    target = project / name
    if target.is_dir():
        shutil.rmtree(target)
    else:
        target.unlink()
    marker = project / "ran-marker"
    with pytest.raises(ProtectedPathMissing) as exc:
        _mutate(project, state, f"touch ran-marker; mkdir -p {name}")
    assert exc.value.missing == [target]
    assert str(target) in str(exc.value)
    assert not marker.exists()
    assert not target.exists()


def test_mutate_cannot_rename_git_dir(project, state):
    head = _git(project, "rev-parse", "HEAD")
    script = ("echo ran; mkdir -p sub\n"
              "if mv .git .git-aside 2>/dev/null; then echo OK-aside; fi\n"
              "if mv .git sub/ 2>/dev/null; then echo OK-subdir; fi\n")
    r = _mutate(project, state, script)
    assert r.rc == 0, r.stderr
    assert "ran" in r.stdout
    assert "OK-" not in r.stdout, r.stdout
    assert (project / ".git").is_dir()
    assert not (project / ".git-aside").exists()
    assert not (project / "sub" / ".git").exists()
    assert _git(project, "rev-parse", "HEAD") == head


def test_git_commit_refused_in_mutate_shell(project, state):
    head = _git(project, "rev-parse", "HEAD")
    script = ("echo change > file2 && git add file2 && "
              "git -c user.name=t -c user.email=t@example.invalid commit -q -m inside-sandbox")
    r = _mutate(project, state, script)
    assert r.rc != 0
    assert "Read-only file system" in r.stderr, r.stderr
    assert (project / "file2").read_text() == "change\n"
    assert _git(project, "log", "--format=%s").splitlines() == ["init"]
    assert _git(project, "rev-parse", "HEAD") == head


def test_git_dir_read_only_in_mutate_shell(project, state):
    git = project / ".git"
    head = _git(project, "rev-parse", "HEAD")
    index = (git / "index").read_bytes()
    before = _snap([git])
    attempts = [
        "echo /tmp > .git/commondir",
        "mkdir -p .git/modules/x/hooks && echo 'touch /tmp/pwned' > .git/modules/x/hooks/pre-commit",
        "mkdir -p .git/worktrees/x",
        "git add file2",
        "git -c user.name=t -c user.email=t@example.invalid commit -q --allow-empty -m inside",
    ]
    script = "echo change > file2\n" + "".join(
        f"if ({a}) 2>/dev/null; then echo {shlex.quote('OK: ' + a)}; fi\n" for a in attempts)
    r = _mutate(project, state, script)
    assert r.rc == 0, r.stderr
    assert (project / "file2").read_text() == "change\n"
    assert "OK:" not in r.stdout, r.stdout
    assert _git(project, "rev-parse", "HEAD") == head
    assert (git / "index").read_bytes() == index
    assert _snap([git]) == before


def test_mutate_can_write_project_with_git_present(project, state):
    assert (project / ".git").is_dir()
    r = _mutate(project, state, "echo changed > README && mkdir -p sub && echo y > sub/f")
    assert r.rc == 0, r.stderr
    assert (project / "README").read_text() == "changed\n"
    assert (project / "sub" / "f").read_text() == "y\n"


def test_git_paths_bound_only_when_present(isolated_env):
    root = (isolated_env / "project").resolve()
    ensure_protected(root, paths.state_root(root))
    state = paths.state_root(root)
    argv = _mutate_argv(root, state, "true")[0]
    i = argv.index(str(root / ".git"))
    assert argv[i - 2] == "--ro-bind" and Path(argv[i - 1]).parent == state.resolve(), argv
    assert not any("/.git/" in a for a in argv), argv
    _git_init(root)
    argv = _mutate_argv(root, state, "true")[0]
    git_ro = _at(argv, "--ro-bind", root / ".git")
    assert _at(argv, "--bind", root) < git_ro
    assert git_ro < _at(argv, "--ro-bind", root / ".git" / "hooks")
    assert git_ro < _at(argv, "--ro-bind", root / ".git" / "config")
    assert not any(argv[i] == "--bind" and ".git" in argv[i + 1]
                   for i in range(len(argv) - 1)), argv


def test_mutate_refuses_when_git_is_a_file(isolated_env):
    root = (isolated_env / "project").resolve()
    other = isolated_env / "other"
    other.mkdir()
    _git(other, "init", "-q")
    git_file = root / ".git"
    git_file.write_text(f"gitdir: {other / '.git'}\n")
    ensure_protected(root, paths.state_root(root))
    with pytest.raises(GitFileUnsupported) as exc:
        _mutate(root, paths.state_root(root), "touch ran-marker")
    message = str(exc.value)
    assert str(git_file) in message
    assert "not supported" in message
    assert "chrgate-setup" not in message
    assert not (root / "ran-marker").exists()


def test_ensure_protected_skips_git_file_project(isolated_env):
    root = isolated_env / "project"
    git_file = root / ".git"
    content = "gitdir: /nonexistent/repo/.git\n"
    git_file.write_text(content)
    created = ensure_protected(root, paths.state_root(root))
    assert sorted(created) == sorted([root / ".claude", root / ".codex", root / ".mcp.json"])
    assert git_file.is_file()
    assert git_file.read_text() == content
    assert ensure_protected(root, paths.state_root(root)) == []


def test_ensure_protected_creates_missing_only(isolated_env):
    root = isolated_env / "project"
    created = ensure_protected(root, paths.state_root(root))
    assert sorted(created) == sorted([root / ".claude", root / ".codex", root / ".mcp.json"])
    assert list((root / ".claude").iterdir()) == []
    assert list((root / ".codex").iterdir()) == []
    assert json.loads((root / ".mcp.json").read_text()) == {"mcpServers": {}}
    assert ensure_protected(root, paths.state_root(root)) == []

    other = isolated_env / "other"
    other.mkdir()
    existing = b'{"mcpServers": {"x": {"command": "y"}}}\n'
    (other / ".mcp.json").write_bytes(existing)
    assert sorted(ensure_protected(other, paths.state_root(other))) == sorted([other / ".claude", other / ".codex"])
    assert (other / ".mcp.json").read_bytes() == existing
    assert ensure_protected(other, paths.state_root(other)) == []


def test_argv_builders(project, state):
    argv = research_argv(project, state, "true")
    tmp = _at(argv, "--bind", "/tmp")
    assert _at(argv, "--ro-bind", project) > tmp
    assert _at(argv, "--ro-bind", state) > tmp
    assert "--unshare-net" in argv
    assert argv[-4:] == ["--", "bash", "-c", "true"]

    argv = _mutate_argv(project, state, "true")[0]
    writable = max(_at(argv, "--bind", "/tmp"), _at(argv, "--bind", project))
    for path in [state, *protected_paths(project)]:
        assert _at(argv, "--ro-bind", path) > writable
    assert "--unshare-net" not in argv
    assert argv[-4:] == ["--", "bash", "-c", "true"]


def test_mutate_refuses_when_git_hooks_absent(project, state):
    hooks = project / ".git" / "hooks"
    shutil.rmtree(hooks)
    with pytest.raises(ProtectedPathMissing) as exc:
        _mutate(project, state, "touch ran-marker; mkdir -p .git/hooks")
    assert exc.value.missing == [hooks]
    assert str(hooks) in str(exc.value)
    assert not (project / "ran-marker").exists()
    assert not hooks.exists()


def test_mutate_refuses_when_git_config_absent(project, state):
    config = project / ".git" / "config"
    config.unlink()
    with pytest.raises(ProtectedPathMissing) as exc:
        _mutate(project, state, "touch ran-marker; touch .git/config")
    assert exc.value.missing == [config]
    assert str(config) in str(exc.value)
    assert "repair the git repository" in str(exc.value)
    assert not (project / "ran-marker").exists()
    assert not config.exists()


def test_ensure_protected_creates_git_hooks(isolated_env):
    root = isolated_env / "project"
    assert sorted(ensure_protected(root, paths.state_root(root))) == sorted(
        [root / ".claude", root / ".codex", root / ".mcp.json"])
    assert not (root / ".git").exists()
    _git(root, "init", "-q")
    hooks, config = root / ".git" / "hooks", root / ".git" / "config"
    shutil.rmtree(hooks, ignore_errors=True)
    config.unlink()
    assert ensure_protected(root, paths.state_root(root)) == [hooks]
    assert hooks.is_dir()
    assert list(hooks.iterdir()) == []
    assert not config.exists()
    assert ensure_protected(root, paths.state_root(root)) == []
    assert not config.exists()


def test_git_hooks_read_only_after_setup(isolated_env):
    root = (isolated_env / "project").resolve()
    _git(root, "init", "-q")
    hooks = root / ".git" / "hooks"
    shutil.rmtree(hooks, ignore_errors=True)
    assert hooks in ensure_protected(root, paths.state_root(root))
    script = ("echo ran\n"
              "if (echo x > .git/hooks/pre-commit) 2>/dev/null; then echo OK-write; fi\n"
              "if touch .git/hooks/pre-commit 2>/dev/null; then echo OK-touch; fi\n")
    r = _mutate(root, paths.state_root(root), script)
    assert r.rc == 0, r.stderr
    assert "ran" in r.stdout
    assert "OK-" not in r.stdout, r.stdout
    assert list(hooks.iterdir()) == []


@pytest.mark.parametrize("name", [".claude", ".codex", ".mcp.json"])
def test_mutate_refuses_symlinked_protected_path(isolated_env, project, state, name):
    target = project / name
    real = isolated_env / f"real{name}"
    target.rename(real)
    target.symlink_to(real)
    with pytest.raises(ProtectedPathSymlink) as exc:
        _mutate(project, state, "touch ran-marker")
    assert exc.value.symlinked == [target]
    assert str(target) in str(exc.value)
    assert not (project / "ran-marker").exists()
    assert ensure_protected(project, state) == []
    assert target.is_symlink()
    assert target.readlink() == real


def test_env_cleared_in_both_shells(project, state, monkeypatch):
    monkeypatch.setenv("CHRGATE_TEST_SECRET", "chrgate-secret-value")
    for r in (_sh(research_argv(project, state, "env")), _mutate(project, state, "env")):
        assert r.rc == 0, r.stderr
        names = {line.split("=", 1)[0] for line in r.stdout.splitlines() if "=" in line}
        assert "CHRGATE_TEST_SECRET" not in names
        assert "chrgate-secret-value" not in r.stdout
        assert "PATH" in names


def test_run_truncates_output(project, state):
    r = run(research_argv(project, state, "head -c 5000 /dev/zero | tr '\\0' x"), TIMEOUT, 100)
    assert r.rc == 0, r.stderr
    assert r.stdout == "x" * 100 + "\n[chr-gate: output truncated: 5000 bytes, first 100 shown]"


def test_run_timeout_kills(project, state):
    start = time.monotonic()
    r = run(research_argv(project, state, "echo started; sleep 30"), 2, MAX_OUTPUT)
    assert time.monotonic() - start < 10
    assert r.rc < 0
    assert "started" in r.stdout
    assert r.stderr.endswith("[chr-gate: command timed out after 2s and was killed]")


def _bare_project(isolated_env):
    """A project with the required protected paths and no masked name."""
    root = (isolated_env / "project").resolve()
    state = paths.state_root(root)
    ensure_protected(root, state)
    assert _masked_present(root) == []
    return root, state


def _masked_present(root):
    return [name for name in MASKED if os.path.lexists(root / name)]


def _mutate(root, state, command, timeout=TIMEOUT):
    return run_mutate(root, state, command, timeout, MAX_OUTPUT)


def _attempts(attempts):
    return "echo ran\n" + "".join(
        f"if ({a}) 2>/dev/null; then echo {shlex.quote('OK: ' + a)}; fi\n" for a in attempts)


def test_git_init_refused_without_git_dir(isolated_env):
    root, state = _bare_project(isolated_env)
    r = _mutate(root, state, _attempts(["git init -q", "mkdir .git"]))
    assert r.rc == 0, r.stderr
    assert "ran" in r.stdout
    assert "OK:" not in r.stdout, r.stdout
    assert not os.path.lexists(root / ".git")


def test_masked_names_read_only_in_mutate_shell(isolated_env):
    root, state = _bare_project(isolated_env)
    absent = []
    for name in MASKED_DIRS:
        absent += [f"mkdir {name}", f"mkdir -p {name}/sub",
                   f"mkdir {name}.new && mv -T {name}.new {name}"]
    for name in MASKED_FILES:
        absent += [f"echo x > {name}", f"rm -f {name} && echo x > {name}",
                   f"echo x > {name}.new && mv -T {name}.new {name}"]
    r = _mutate(root, state, _attempts(absent))
    assert r.rc == 0, r.stderr
    assert "ran" in r.stdout
    assert "OK:" not in r.stdout, r.stdout
    assert _masked_present(root) == []

    _git_init(root)
    for name in MASKED_DIRS:
        (root / name).mkdir(exist_ok=True)
        (root / name / "content").write_text("orig\n")
    for name in MASKED_FILES:
        (root / name).write_text("orig\n")
    present = []
    for name in MASKED_DIRS:
        present += [f"echo x > {name}/content", f"touch {name}/planted", f"rm -rf {name}",
                    f"mv {name} {name}.moved"]
    for name in MASKED_FILES:
        present += [f"echo x >> {name}", f"echo x > {name}", f"rm -f {name}",
                    f"mv {name} {name}.moved"]
    masked = [root / name for name in MASKED]
    before = _snap(masked)
    r = _mutate(root, state, _attempts(present))
    assert r.rc == 0, r.stderr
    assert "ran" in r.stdout
    assert "OK:" not in r.stdout, r.stdout
    assert _snap(masked) == before
    assert not any(os.path.lexists(root / f"{name}.moved") for name in MASKED)


def test_placeholders_removed_after_run(isolated_env):
    root, state = _bare_project(isolated_env)
    placed = " && ".join([*(f"test -d {name}" for name in MASKED_DIRS),
                          *(f"test -f {name}" for name in MASKED_FILES)]) + " && echo placed"
    manifest = state / MANIFEST_NAME
    runs = [(placed, TIMEOUT), (placed + " && exit 3", TIMEOUT), (placed + " && sleep 30", 2)]
    rcs = []
    for command, timeout in runs:
        r = _mutate(root, state, command, timeout)
        assert "placed" in r.stdout, r.stderr
        assert _masked_present(root) == []
        assert not manifest.exists()
        rcs.append(r.rc)
    assert rcs[:2] == [0, 3]
    assert rcs[2] < 0


def _plant_leftovers(root, state):
    (root / ".git").mkdir()
    (root / ".gitmodules").touch()
    (root / ".vscode").mkdir(exist_ok=True)
    (root / ".vscode" / "settings.json").write_text("{}\n")
    (state / MANIFEST_NAME).write_text(json.dumps([".git", ".gitmodules", ".vscode"]) + "\n")


def _assert_leftovers_cleaned(root, state):
    assert not os.path.lexists(root / ".git")
    assert not os.path.lexists(root / ".gitmodules")
    assert [p.name for p in (root / ".vscode").iterdir()] == ["settings.json"]
    assert (root / ".vscode" / "settings.json").read_text() == "{}\n"
    assert not (state / MANIFEST_NAME).exists()


def test_crash_leftover_placeholders_cleaned(isolated_env):
    root, state = _bare_project(isolated_env)
    _plant_leftovers(root, state)
    r = _mutate(root, state, "echo ran")
    assert r.rc == 0, r.stderr
    assert "ran" in r.stdout
    _assert_leftovers_cleaned(root, state)

    _plant_leftovers(root, state)
    assert ensure_protected(root, state) == []
    _assert_leftovers_cleaned(root, state)


def test_mutate_runs_serialized_per_project(isolated_env):
    root, state = _bare_project(isolated_env)
    barrier = threading.Barrier(2)
    results = {}

    def go(tag):
        barrier.wait()
        results[tag] = _mutate(root, state,
                               f"date +%s%N > {tag}.start; sleep 1; date +%s%N > {tag}.end")

    threads = [threading.Thread(target=go, args=(tag,)) for tag in ("a", "b")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(results) == ["a", "b"]
    assert all(r.rc == 0 for r in results.values()), results
    (a0, a1), (b0, b1) = [(int((root / f"{tag}.start").read_text()),
                           int((root / f"{tag}.end").read_text())) for tag in ("a", "b")]
    assert a1 <= b0 or b1 <= a0, (a0, a1, b0, b1)


def test_mutate_refuses_symlinked_git(isolated_env):
    root, state = _bare_project(isolated_env)
    other = isolated_env / "other"
    other.mkdir()
    _git_init(other)
    real_vscode = isolated_env / "real.vscode"
    real_vscode.mkdir()
    for name, target in ((".git", other / ".git"), (".vscode", real_vscode)):
        link = root / name
        link.symlink_to(target)
        with pytest.raises(ProtectedPathSymlink) as exc:
            _mutate(root, state, "touch ran-marker")
        assert exc.value.symlinked == [link]
        assert str(link) in str(exc.value)
        assert not (root / "ran-marker").exists()
        link.unlink()


def test_hooks_path_in_project_read_only(project, state):
    husky = project / ".husky"
    husky.mkdir()
    (husky / "pre-commit").write_text("orig\n")
    _git(project, "config", "core.hooksPath", ".husky")
    before = _snap([husky])
    r = _mutate(project, state, _attempts([
        "echo x > .husky/pre-commit", "echo x >> .husky/pre-commit",
        "touch .husky/post-checkout", "mv .husky .husky.moved", "rm -rf .husky"]))
    assert r.rc == 0, r.stderr
    assert "ran" in r.stdout
    assert "OK:" not in r.stdout, r.stdout
    assert _snap([husky]) == before
    assert not os.path.lexists(project / ".husky.moved")

    shutil.rmtree(husky)
    listing = sorted(os.listdir(project))
    for hooks in (".husky", ".husky/_"):
        _git(project, "config", "core.hooksPath", hooks)
        r = _mutate(project, state, _attempts([
            f"mkdir {hooks}", f"mkdir -p {hooks} && echo x > {hooks}/pre-commit",
            "rm -rf .husky", "mv .husky moved-hooks"]) + "test -d .husky && echo placed\n")
        assert r.rc == 0, r.stderr
        assert "placed" in r.stdout, r.stdout
        assert "OK:" not in r.stdout, r.stdout
        assert sorted(os.listdir(project)) == listing
        assert not (state / MANIFEST_NAME).exists()


def test_fsmonitor_path_in_project_read_only(project, state):
    plain = _mutate_argv(project, state, "true")[0]
    fsmon = project / "tools" / "fsmon.sh"
    fsmon.parent.mkdir()
    fsmon.write_text("#!/bin/sh\n")
    _git(project, "config", "core.fsmonitor", "tools/fsmon.sh")
    assert _at(_mutate_argv(project, state, "true")[0], "--ro-bind", fsmon) > _at(plain, "--bind", project)
    r = _mutate(project, state, _attempts([
        "echo x >> tools/fsmon.sh", "echo x > tools/fsmon.sh", "rm -f tools/fsmon.sh",
        "mv tools/fsmon.sh tools/moved"]))
    assert r.rc == 0, r.stderr
    assert "ran" in r.stdout
    assert "OK:" not in r.stdout, r.stdout
    assert fsmon.read_text() == "#!/bin/sh\n"
    assert sorted(os.listdir(fsmon.parent)) == ["fsmon.sh"]
    for value in ("true", "On", "0"):
        _git(project, "config", "core.fsmonitor", value)
        assert _mutate_argv(project, state, "true")[0] == plain


def test_included_config_file_read_only(project, state, monkeypatch):
    conf = project / "conf"
    conf.mkdir()
    files = {"git.inc": "[core]\n\tfsmonitor = false\n", "empty.inc": "",
             "global.cfg": "[user]\n\tname = t\n"}
    for name, text in files.items():
        (conf / name).write_text(text)
    _git(project, "config", "include.path", "../conf/git.inc")
    _git(project, "config", "--add", "include.path", "../conf/empty.inc")
    _git(project, "config", "includeIf.onbranch:topic.path", "../conf/missing.inc")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(conf / "global.cfg"))
    before = _snap([conf / name for name in files])
    attempts = ["echo x > conf/missing.inc"]
    for name in files:
        attempts += [f"echo x >> conf/{name}", f"echo x > conf/{name}", f"rm -f conf/{name}",
                     f"mv conf/{name} conf/{name}.moved"]
    r = _mutate(project, state, _attempts(attempts))
    assert r.rc == 0, r.stderr
    assert "ran" in r.stdout
    assert "OK:" not in r.stdout, r.stdout
    assert _snap([conf / name for name in files]) == before
    assert sorted(os.listdir(conf)) == sorted(files)


def test_git_config_unreadable_refused(isolated_env, project, state, monkeypatch):
    config = project / ".git" / "config"
    config.write_text("[core\n\tbare = false\n")
    with pytest.raises(GitConfigUnreadable) as exc:
        _mutate(project, state, "touch ran-marker")
    assert str(exc.value).startswith("chr-gate refused:"), str(exc.value)
    assert str(config) in str(exc.value)
    assert "bad config" in str(exc.value)
    assert not (project / "ran-marker").exists()
    config.write_text("[core]\n\tbare = false\n")
    empty = isolated_env / "empty-path"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))
    with pytest.raises(GitConfigUnreadable) as exc:
        _mutate(project, state, "touch ran-marker")
    assert str(exc.value).startswith("chr-gate refused:"), str(exc.value)
    assert str(config) in str(exc.value)
    assert "git not found on PATH" in str(exc.value)


def test_git_config_unreadable_names_chr_gate_for_file_tools(project):
    config = project / ".git" / "config"
    config.write_text("[core\n\tbare = false\n")
    with pytest.raises(GitConfigUnreadable) as exc:
        read_only_paths(project)
    assert str(exc.value).startswith("chr-gate refused:"), str(exc.value)
    assert str(config) in str(exc.value)


def test_nested_repo_read_only(project, state):
    for rel in ("sub", "a/b/c", "a/b/c/d"):
        (project / rel).mkdir(parents=True)
        _git(project / rel, "init", "-q")
    sub, abc, deep = (project / rel / ".git" for rel in ("sub", "a/b/c", "a/b/c/d"))
    argv = _mutate_argv(project, state, "true")[0]
    assert _at(argv, "--ro-bind", sub) > _at(argv, "--bind", project)
    assert _at(argv, "--ro-bind", abc) > _at(argv, "--bind", project)
    assert str(deep) not in argv
    before = _snap([sub, abc])
    r = _mutate(project, state, _attempts([
        "echo x >> sub/.git/config", "touch sub/.git/hooks/pre-commit",
        "echo x > sub/.git/hooks/pre-commit", "rm -rf sub/.git", "mv sub/.git sub/moved",
        "echo x >> a/b/c/.git/config", "touch a/b/c/.git/hooks/pre-commit"])
        + "echo x >> a/b/c/d/.git/config && echo deep-writable\n")
    assert r.rc == 0, r.stderr
    assert "ran" in r.stdout
    assert "OK:" not in r.stdout, r.stdout
    assert "deep-writable" in r.stdout, r.stderr
    assert _snap([sub, abc]) == before

    gitfile = project / "wt" / ".git"
    gitfile.parent.mkdir()
    gitfile.write_text("gitdir: ../sub/.git\n")
    _at(_mutate_argv(project, state, "true")[0], "--ro-bind", gitfile)
    r = _mutate(project, state, _attempts(["echo x >> wt/.git", "rm -f wt/.git",
                                           "mv wt/.git wt/moved"]))
    assert r.rc == 0, r.stderr
    assert "OK:" not in r.stdout, r.stdout
    assert gitfile.read_text() == "gitdir: ../sub/.git\n"

    link = project / "l" / ".git"
    link.parent.mkdir()
    link.symlink_to(sub)
    with pytest.raises(ProtectedPathSymlink) as exc:
        _mutate(project, state, "touch ran-marker")
    assert exc.value.symlinked == [link]
    assert str(link) in str(exc.value)
    assert not (project / "ran-marker").exists()


def test_new_nested_repo_reported(project, state):
    warning = ("[chr-gate: warning: the command created git metadata at sub/.git; "
               "do not run git there before checking its config and hooks]")
    r = _mutate(project, state, "mkdir sub && git init -q sub")
    assert r.rc == 0, r.stderr
    assert (project / "sub" / ".git").is_dir()
    assert warning in r.stderr.splitlines(), r.stderr
    assert r.stderr.count("chr-gate: warning") == 1, r.stderr
    for command in ("mkdir other && echo x > other/f", "echo x > sub/f"):
        r = _mutate(project, state, command)
        assert r.rc == 0, r.stderr
        assert "chr-gate: warning" not in r.stderr, r.stderr


def test_mutate_cannot_rename_protected_ancestor(project, state):
    hooks = project / ".husky" / "_"
    hooks.mkdir(parents=True)
    (hooks / "pre-commit").write_text("orig\n")
    _git(project, "config", "core.hooksPath", ".husky/_")
    before = _snap([hooks])
    r = _mutate(project, state, _attempts([
        "mv .husky .husky.moved", "rmdir .husky", "rm -rf .husky",
        "mkdir -p evil/_ && mv -T evil .husky"]) + "echo y > .husky/ordinary && echo wrote\n")
    assert r.rc == 0, r.stderr
    assert "wrote" in r.stdout, r.stdout + r.stderr
    assert "OK:" not in r.stdout, r.stdout
    assert _snap([hooks]) == before
    assert (project / ".husky" / "ordinary").read_text() == "y\n"
    assert not os.path.lexists(project / ".husky.moved")
    argv = _mutate_argv(project, state, "true")[0]
    assert (_at(argv, "--bind", project) < _at(argv, "--bind", hooks.parent)
            < _at(argv, "--ro-bind", hooks))


def test_mutate_cannot_replace_nested_git_parent(project, state):
    for rel in ("sub", "a/b/c"):
        (project / rel).mkdir(parents=True)
        _git(project / rel, "init", "-q")
    gits = [project / "sub" / ".git", project / "a" / "b" / "c" / ".git"]
    before = _snap(gits)
    r = _mutate(project, state, _attempts([
        "mv sub sub.old", "rm -rf sub", "mkdir -p evil/.git && mv -T evil sub",
        "mv a a.old", "mv a/b a/b.old", "mv a/b/c a/b/c.old", "rm -rf a"])
        + "echo y > sub/ordinary && echo y > a/b/ordinary && echo wrote\n")
    assert r.rc == 0, r.stderr
    assert "wrote" in r.stdout, r.stdout + r.stderr
    assert "OK:" not in r.stdout, r.stdout
    assert _snap(gits) == before
    assert (project / "sub" / "ordinary").read_text() == "y\n"
    assert (project / "a" / "b" / "ordinary").read_text() == "y\n"
    assert not any(os.path.lexists(project / name)
                   for name in ("sub.old", "a.old", "a/b.old", "a/b/c.old"))
    argv = _mutate_argv(project, state, "true")[0]
    for pin, git in (("sub", gits[0]), ("a", gits[1]), ("a/b", gits[1]), ("a/b/c", gits[1])):
        assert (_at(argv, "--bind", project) < _at(argv, "--bind", project / pin)
                < _at(argv, "--ro-bind", git))


def test_included_config_parent_pinned(project, state):
    conf = project / "conf"
    conf.mkdir()
    inc = conf / "git.inc"
    inc.write_text("[core]\n\tfsmonitor = false\n")
    _git(project, "config", "include.path", "../conf/git.inc")
    r = _mutate(project, state, _attempts([
        "mv conf conf.moved", "rmdir conf", "rm -rf conf",
        "mkdir evil && echo '[core]' > evil/git.inc && mv -T evil conf"])
        + "echo y > conf/ordinary && echo wrote\n")
    assert r.rc == 0, r.stderr
    assert "wrote" in r.stdout, r.stdout + r.stderr
    assert "OK:" not in r.stdout, r.stdout
    assert inc.read_text() == "[core]\n\tfsmonitor = false\n"
    assert sorted(os.listdir(conf)) == ["git.inc", "ordinary"]
    assert not os.path.lexists(project / "conf.moved")
    argv = _mutate_argv(project, state, "true")[0]
    assert _at(argv, "--bind", project) < _at(argv, "--bind", conf) < _at(argv, "--ro-bind", inc)


def test_missing_hooks_path_placeholder_at_first_missing_component(project, state):
    _git(project, "config", "core.hooksPath", ".husky/_")
    husky = project / ".husky"
    listing = sorted(os.listdir(project))
    argv = _mutate_argv(project, state, "true")[0]
    i = argv.index(str(husky))
    assert argv[i - 2] == "--ro-bind" and Path(argv[i - 1]).parent == state.resolve(), argv
    assert str(husky / "_") not in argv
    manifest = state / MANIFEST_NAME
    r = _mutate(project, state, _attempts([
        "mkdir .husky/_", "mkdir -p .husky/_ && echo x > .husky/_/pre-commit",
        "touch .husky/pre-commit", "rm -rf .husky", "mv .husky moved"])
        + 'test -d .husky && test -z "$(ls -A .husky)" && echo placed\n'
        + f"cat {shlex.quote(str(manifest))}\n")
    assert r.rc == 0, r.stderr
    assert "placed" in r.stdout, r.stdout
    assert "OK:" not in r.stdout, r.stdout
    names = json.loads(r.stdout.splitlines()[-1])
    assert ".husky" in names and ".husky/_" not in names, names
    assert sorted(os.listdir(project)) == listing
    assert not manifest.exists()


def test_config_named_symlink_refused(isolated_env, project, state):
    outside = isolated_env / "outside"
    (outside / "_").mkdir(parents=True)
    link = project / ".husky"
    for target, hooks in ((outside / "_", ".husky"), (outside, ".husky/_")):
        link.symlink_to(target)
        _git(project, "config", "core.hooksPath", hooks)
        with pytest.raises(ProtectedPathSymlink) as exc:
            _mutate(project, state, "touch ran-marker")
        assert exc.value.symlinked == [link]
        assert str(link) in str(exc.value)
        assert not (project / "ran-marker").exists()
        link.unlink()


def test_cleanup_skips_symlinked_ancestor(isolated_env):
    root, state = _bare_project(isolated_env)
    outside = isolated_env / "outside"
    (outside / "empty-dir").mkdir(parents=True)
    (outside / "empty-file").touch()
    (root / "link").symlink_to(outside)
    (state / MANIFEST_NAME).write_text(
        json.dumps(["link/empty-dir", "link/empty-file", "link"]) + "\n")
    r = _mutate(root, state, "echo ran")
    assert r.rc == 0, r.stderr
    assert "ran" in r.stdout
    assert (outside / "empty-dir").is_dir()
    assert (outside / "empty-file").is_file()
    assert (root / "link").is_symlink()
    assert not (state / MANIFEST_NAME).exists()


def test_unreadable_dir_refused_before_run(project, state):
    locked = project / "a" / "locked"
    locked.mkdir(parents=True)
    locked.chmod(0)
    try:
        with pytest.raises(FolderUnreadable) as exc:
            _mutate(project, state, "touch ran-marker")
        assert exc.value.folders == [locked]
        assert str(locked) in str(exc.value)
        assert isinstance(exc.value, SANDBOX_ERRORS)
        assert not (project / "ran-marker").exists()
    finally:
        locked.chmod(0o700)


def test_unreadable_dir_after_run_warns(project, state):
    warning = ("[chr-gate: warning: cannot read locked after the command; git metadata the "
               "command created under it was not checked]")
    try:
        r = _mutate(project, state, "mkdir locked && echo out && chmod 000 locked")
        assert r.rc == 0, r.stderr
        assert "out" in r.stdout
        assert warning in r.stderr.splitlines(), r.stderr
        assert r.stderr.count("chr-gate: warning") == 1, r.stderr
    finally:
        (project / "locked").chmod(0o700)


def test_lock_file_masked_in_both_shells(project, state):
    lock = state.resolve() / LOCK_NAME
    command = f"flock -n -x {shlex.quote(str(lock))} true; echo rc=$?"
    with _project_lock(state.resolve()):
        r = _sh(research_argv(project, state, command))
    assert "rc=0" in r.stdout, (r.stdout, r.stderr)
    r = _mutate(project, state, command)
    assert "rc=0" in r.stdout, (r.stdout, r.stderr)


def test_store_lock_masked_in_both_shells(project, state):
    lock = state.resolve() / STORE_LOCK_NAME
    command = f"flock -n -x {shlex.quote(str(lock))} true; echo rc=$?"
    with Store(state.resolve()).lock():
        r = _sh(research_argv(project, state, command))
        assert "rc=0" in r.stdout, (r.stdout, r.stderr)
        r = _mutate(project, state, command)
        assert "rc=0" in r.stdout, (r.stdout, r.stderr)


def test_research_runs_without_lock_file(isolated_env):
    root = (isolated_env / "project").resolve()
    state = isolated_env / "fresh-state"
    assert not (state / LOCK_NAME).exists()
    r = _sh(research_argv(root, state, "echo ran"))
    assert r.rc == 0, r.stderr
    assert r.stdout == "ran\n"


def test_research_runs_without_store_lock_file(isolated_env):
    root = (isolated_env / "project").resolve()
    state = isolated_env / "fresh-state"
    assert not (state / STORE_LOCK_NAME).exists()
    r = _sh(research_argv(root, state, "echo ran"))
    assert r.rc == 0, r.stderr
    assert r.stdout == "ran\n"
    with Store(state).lock():
        pass
    st = os.lstat(state / STORE_LOCK_NAME)
    assert stat.S_ISREG(st.st_mode)
    assert stat.S_IMODE(st.st_mode) == 0o600


def test_sandbox_public_surface():
    public = {name for name, fn in inspect.getmembers(sandbox, inspect.isfunction)
              if fn.__module__ == sandbox.__name__ and not name.startswith("_")}
    assert public == {"protected_paths", "missing_protected", "ensure_protected",
                      "read_only_paths", "research_argv", "run", "run_mutate"}
