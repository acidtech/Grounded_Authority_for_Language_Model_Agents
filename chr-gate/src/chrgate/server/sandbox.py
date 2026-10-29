"""Bubblewrap profiles for research_shell and mutate_shell.

bwrap applies mounts in argv order and a later bind over the same path wins,
so every read-only bind comes AFTER the writable binds it must override. That
keeps the project (research) and the state root (both profiles) read-only
even when they live under the writable /tmp.

Protected paths are ro-bound in mutate_shell. A bound path is a mount point,
so inside the sandbox it can be neither written, removed nor renamed. A .git
directory is ro-bound as a whole, so nothing under it can be written, removed
or renamed: agents cannot stage, commit or branch, and the user runs git. A
project whose .git is a file (linked worktree or submodule checkout) is not
supported. When .git exists, .git/hooks and .git/config are required too.
run_mutate fails closed while a required protected path is missing, because
the agent could create it, and while one is a symlink. ensure_protected
is the per-project setup step (chrgate-setup) that creates the missing ones
(never .git/config); nothing in the server calls it.

The masked names (MASKED_DIRS and MASKED_FILES, at the project root) are
read-only in mutate_shell too: a present one is ro-bound onto itself, a
missing one gets a read-only placeholder (an empty directory or empty file
kept under the state root), so none can be created there and git init at the
project root fails. A masked name that is a symlink is refused. bwrap creates
each placeholder's mount point as an empty directory or file in the real
project; run_mutate records them in a manifest under the state root before
the sandbox starts and removes the ones still empty after it exits. A
manifest left by a crash is processed at the start of the next run_mutate
and of ensure_protected. Both hold a per-project lock under the state root
for their whole run. Both shells see the empty placeholder file, read-only, at
both lock files' paths, the project lock's and the Store lock's
(chrgate.core.store.LOCK_NAME), so no command inside a shell can take or
contend for either lock; both lock files are created before either argv is
built, because bwrap cannot create a mount point on the read-only state root.
run_mutate is the mutate_shell entry point; _mutate_argv only builds the argv
and removes no placeholder.

When .git is a directory, the project paths its effective git configuration
names are read-only in mutate_shell too: every config file in the project (an
origin of the listing, or an include.path or includeIf.<condition>.path
target, which git silently skips while it is missing or empty), the
core.hooksPath directory and a core.fsmonitor program. run_mutate lists the
configuration with the host's git before any sandbox starts and refuses
(GitConfigUnreadable) when it cannot. A present one is ro-bound onto itself, a
missing one gets a placeholder like a missing masked name, at its first missing
path component (an empty directory when that is a missing parent folder), so
no writable parent folder is created. One with a symlinked component is
refused. Every .git entry up to NESTED_GIT_SCAN_DEPTH directory levels below
the project root (a nested repository or submodule) is ro-bound as a whole and
refused when it is a symlink; after the run, run_mutate warns in stderr about
each .git entry the command created.

Every folder strictly between the project root and the target of one of these
binds (a nested .git entry, a git-config-named path or its placeholder) that no
read-only bind covers is bound onto itself, writable, before the read-only
binds. A mount point cannot be renamed or removed, so the folder cannot be
swapped out from above the protected path, while files in it stay writable.
read_only_paths lists every path mutate_shell holds read-only; write_file and
edit_file refuse the same paths. A folder within the nested scan depth that
cannot be read is refused (FolderUnreadable) before a run; after the run,
run_mutate warns in stderr about each one instead.

Both profiles start from a cleared environment holding only ENV_ALLOWLIST.

state_root is the caller's chrgate.core.paths.state_root(project); it is
created (0700, like Store) before the sandbox starts if it does not exist.
"""

import errno
import fcntl
import json
import os
import shutil
import stat
import subprocess
import threading
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import IO, NamedTuple

from chrgate.core.store import LOCK_NAME as STORE_LOCK_NAME

REQUIRED_DIRS = (".claude", ".codex")
REQUIRED_FILES = (".mcp.json",)
REQUIRED_PROTECTED = REQUIRED_DIRS + REQUIRED_FILES
GIT_PROTECTED = (".git/hooks", ".git/config")
ENV_ALLOWLIST = ("PATH", "HOME", "LANG", "TERM", "USER")
EMPTY_MCP_JSON = {"mcpServers": {}}
MASKED_DIRS = (".git", ".vscode", ".idea", ".agents", ".aws")
MASKED_FILES = (".gitmodules", ".gitconfig", ".ripgreprc", ".bashrc", ".bash_profile",
                ".zshrc", ".zprofile", ".profile")
MASKED = MASKED_DIRS + MASKED_FILES
MANIFEST_NAME = "placeholders.json"
LOCK_NAME = "mutate.lock"
PLACEHOLDER_DIR = "placeholder-dir"
PLACEHOLDER_FILE = "placeholder-file"
NESTED_GIT_SCAN_DEPTH = 3
GIT_BOOLEANS = frozenset({"true", "false", "yes", "no", "on", "off", "1", "0"})

type PathArg = str | os.PathLike[str]


class ProtectedPathMissing(Exception):
    """mutate_shell refused: a required protected path is absent."""

    def __init__(self, missing: Sequence[Path]):
        self.missing = list(missing)
        names = ", ".join(str(p) for p in self.missing)
        configs = [p for p in self.missing if p.parts[-2:] == (".git", "config")]
        creatable = [p for p in self.missing if p not in configs]
        message = f"mutate_shell refused: required protected path(s) missing: {names}."
        if creatable:
            message += (" Run chrgate-setup in the project to create "
                        + ", ".join(str(p) for p in creatable) + ".")
        for config in configs:
            message += (f" {config} is missing: repair the git repository; "
                        "chrgate-setup never creates it.")
        super().__init__(message)


class ProtectedPathSymlink(Exception):
    """mutate_shell refused: a protected path is a symlink."""

    def __init__(self, symlinked: Sequence[Path]):
        self.symlinked = list(symlinked)
        names = ", ".join(str(p) for p in self.symlinked)
        super().__init__(
            f"mutate_shell refused: protected path(s) are symlinks: {names}. "
            "Replace each with a real directory or file in the project.")


class GitFileUnsupported(Exception):
    """mutate_shell refused: the project's .git is a file, not a directory."""

    def __init__(self, git_file: Path):
        self.git_file = git_file
        super().__init__(
            f"mutate_shell refused: {git_file} is a file (a linked worktree or "
            "submodule checkout); projects whose .git is a file are not supported.")


class GitConfigUnreadable(Exception):
    """chr-gate refused: git cannot list the project's configuration, so
    chr-gate cannot protect the paths it names (mutate_shell holds them
    read-only; write_file and edit_file refuse them)."""

    def __init__(self, config: Path, stderr: str):
        self.config = config
        self.stderr = stderr
        super().__init__(
            f"chr-gate refused: cannot read the git configuration {config}: "
            f"{stderr.strip()}. Repair it; chr-gate protects the paths it names "
            "(mutate_shell holds them read-only; write_file and edit_file refuse them).")


class FolderUnreadable(Exception):
    """chr-gate refused: a folder within the nested .git scan depth cannot be read."""

    def __init__(self, folders: Sequence[Path]):
        self.folders = list(folders)
        names = ", ".join(str(p) for p in self.folders)
        super().__init__(
            f"chr-gate refused: cannot read folder(s) {names} while scanning for nested "
            ".git entries, so a repository under them could not be protected. Make each "
            "readable or remove it.")


class BwrapNotFound(RuntimeError):
    """bubblewrap is not installed; chr-gate shells need Linux with bwrap."""


class RunResult(NamedTuple):
    rc: int
    stdout: str
    stderr: str


def protected_paths(project: PathArg) -> list[Path]:
    """The required protected paths, plus .git/hooks and .git/config whenever
    .git exists."""
    root = Path(project)
    names = REQUIRED_PROTECTED + (GIT_PROTECTED if (root / ".git").exists() else ())
    return [root / name for name in names]


def missing_protected(project: PathArg) -> list[Path]:
    """The required protected paths that are absent."""
    return [path for path in protected_paths(project) if not path.exists()]


def ensure_protected(project: PathArg, state_root: PathArg) -> list[Path]:
    """Create only the missing required protected paths; return those created.

    An existing path is never modified. Holds the project lock and first
    removes the placeholders a crashed run_mutate left behind."""
    root = Path(project)
    state = _state(state_root)
    with _project_lock(state):
        _remove_placeholders(root, state)
        created = []
        for name in REQUIRED_DIRS:
            path = root / name
            if not os.path.lexists(path):
                path.mkdir()
                created.append(path)
        for name in REQUIRED_FILES:
            path = root / name
            if not os.path.lexists(path):
                with open(path, "x", encoding="utf-8") as f:
                    f.write(json.dumps(EMPTY_MCP_JSON) + "\n")
                created.append(path)
        hooks = root / ".git" / "hooks"
        if (root / ".git").is_dir() and not os.path.lexists(hooks):
            hooks.mkdir()
            created.append(hooks)
        return created


def _bwrap() -> str:
    path = shutil.which("bwrap")
    if path is None:
        raise BwrapNotFound("bubblewrap (bwrap) not found on PATH; chr-gate shells "
                            "need Linux with bubblewrap installed")
    return path


def _state(state_root: PathArg) -> Path:
    state = Path(state_root)
    state.mkdir(mode=0o700, parents=True, exist_ok=True)
    return state.resolve(strict=True)


def _placeholder_sources(state: Path) -> tuple[Path, Path]:
    """The empty directory and empty file ro-bound at missing masked names."""
    empty_dir, empty_file = state / PLACEHOLDER_DIR, state / PLACEHOLDER_FILE
    empty_dir.mkdir(mode=0o700, exist_ok=True)
    empty_file.touch(mode=0o600, exist_ok=True)
    return empty_dir, empty_file


def _lock_masks(state: Path, empty_file: Path) -> list[str]:
    """The ro-binds of EMPTY_FILE over the project's lock file and the Store
    lock file, each created if missing (never truncated or locked), because
    bwrap cannot create those mount points on the read-only state root."""
    binds: list[str] = []
    for name in (LOCK_NAME, STORE_LOCK_NAME):
        lock = state / name
        os.close(os.open(lock, os.O_RDWR | os.O_CREAT, 0o600))
        binds += ["--ro-bind", str(empty_file), str(lock)]
    return binds


@contextmanager
def _project_lock(state: Path) -> Iterator[None]:
    """Exclusive flock on the project's lock file for the whole block."""
    fd = os.open(state / LOCK_NAME, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)


def _record_placeholders(state: Path, names: Sequence[str]) -> None:
    """Write the placeholder manifest atomically, before the sandbox starts."""
    tmp = state / (MANIFEST_NAME + ".tmp")
    tmp.write_text(json.dumps(list(names)) + "\n", encoding="utf-8")
    os.replace(tmp, state / MANIFEST_NAME)


def _remove_placeholders(root: Path, state: Path) -> None:
    """Remove each manifest path that is still an empty regular file or an
    empty directory (lstat: a symlink is never followed or removed; nothing
    non-empty is removed), then the manifest. No manifest: nothing to do."""
    manifest = state / MANIFEST_NAME
    try:
        names = json.loads(manifest.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return
    for name in sorted(names, key=lambda n: -len(Path(n).parts)):
        path = root / name
        if _symlinked_components(root, path):
            continue
        try:
            st = os.lstat(path)
        except FileNotFoundError:
            continue
        if stat.S_ISREG(st.st_mode) and st.st_size == 0:
            path.unlink()
        elif stat.S_ISDIR(st.st_mode):
            try:
                path.rmdir()
            except OSError as e:
                if e.errno != errno.ENOTEMPTY:
                    raise
    manifest.unlink()


def _symlinked_components(root: Path, path: Path) -> list[Path]:
    """The components of PATH (ROOT itself excluded) that are symlinks."""
    parts = path.relative_to(root).parts
    return [link for i in range(1, len(parts) + 1)
            if (link := root.joinpath(*parts[:i])).is_symlink()]


def _nested_git(root: Path) -> tuple[list[Path], list[Path]]:
    """Every entry named .git in a directory 1 to NESTED_GIT_SCAN_DEPTH levels
    below ROOT, and the directories within that depth that could not be read
    (PermissionError). Symlinked directories and .git directories are never
    entered."""
    found: list[Path] = []
    unreadable: list[Path] = []

    def walk(directory: Path, level: int) -> None:
        try:
            with os.scandir(directory) as it:
                entries = sorted(it, key=lambda e: e.name)
        except PermissionError:
            unreadable.append(directory)
            return
        for entry in entries:
            path = directory / entry.name
            if entry.name == ".git":
                if level:
                    found.append(path)
            elif level < NESTED_GIT_SCAN_DEPTH and entry.is_dir(follow_symlinks=False):
                walk(path, level + 1)

    walk(root, 0)
    return found, unreadable


def _git_config_paths(root: Path) -> list[tuple[Path, bool]]:
    """The paths the effective configuration of ROOT/.git names, each with
    whether it is a directory: every config file origin, every include.path and
    includeIf.<condition>.path target (relative to the including file), the
    last core.hooksPath and the last non-boolean core.fsmonitor (relative to
    ROOT); ~ expanded, normalized, not yet filtered to the project. Raises
    GitConfigUnreadable when git is not on PATH or the listing fails."""
    git_dir = root / ".git"
    git = shutil.which("git")
    if git is None:
        raise GitConfigUnreadable(git_dir / "config", "git not found on PATH")
    proc = subprocess.run([git, f"--git-dir={git_dir}", "config", "--includes",
                           "--show-origin", "--null", "--list"],
                          cwd=root, stdin=subprocess.DEVNULL, capture_output=True)
    if proc.returncode != 0:
        raise GitConfigUnreadable(git_dir / "config",
                                  proc.stderr.decode("utf-8", errors="replace"))
    named: list[tuple[Path, bool]] = []
    hooks_path = fsmonitor = None
    fields = os.fsdecode(proc.stdout).split("\0")[:-1]
    for origin, entry in zip(fields[::2], fields[1::2], strict=True):
        key, has_value, value = entry.partition("\n")
        source = root / origin.removeprefix("file:") if origin.startswith("file:") else None
        if source is not None:
            named.append((source, False))
        if key == "core.fsmonitor":
            fsmonitor = value if has_value and value.lower() not in GIT_BOOLEANS else None
        elif not has_value:
            continue
        elif key == "core.hookspath":
            hooks_path = value
        elif key == "include.path" or (key.startswith("includeif.") and key.endswith(".path")):
            base = source.parent if source is not None else root
            named.append((base / os.path.expanduser(value), False))
    if hooks_path is not None:
        named.append((root / os.path.expanduser(hooks_path), True))
    if fsmonitor is not None:
        named.append((root / os.path.expanduser(fsmonitor), False))
    return [(Path(os.path.normpath(path)), is_dir) for path, is_dir in named]


def read_only_paths(project: PathArg) -> list[Path]:
    """Every path mutate_shell holds read-only in PROJECT, in bind order: the
    masked names, the protected paths, the nested .git entries and the
    git-config-named paths (read now). write_file and edit_file refuse a target
    equal to or under any of them. Raises FolderUnreadable and
    GitConfigUnreadable as run_mutate does."""
    return list(_read_only(Path(project).resolve(strict=True))[0])


def _read_only(root: Path) -> tuple[dict[Path, bool], list[Path]]:
    """read_only_paths, each with whether its placeholder is a directory, and
    the nested .git entries among them. The git-config-named paths are those in
    the project and not equal to or under an earlier listed path."""
    nested, unreadable = _nested_git(root)
    if unreadable:
        raise FolderUnreadable(unreadable)
    listed = {root / name: name in MASKED_DIRS for name in MASKED}
    for path in [*protected_paths(root), *nested]:
        listed.setdefault(path, path.is_dir())
    whole = set(listed)
    for path, is_dir in (_git_config_paths(root) if (root / ".git").is_dir() else []):
        if (path.is_relative_to(root) and path != root
                and not any(p in whole for p in (path, *path.parents))):
            listed.setdefault(path, is_dir)
    return listed, nested


def _first_missing(root: Path, path: Path) -> Path:
    """The shallowest component of PATH below ROOT that does not exist."""
    parts = path.relative_to(root).parts
    return next(p for i in range(1, len(parts) + 1)
                if not os.path.lexists(p := root.joinpath(*parts[:i])))


def _ancestor_pins(root: Path, listed: dict[Path, bool], targets: list[Path]) -> list[Path]:
    """The folders strictly between ROOT and each bind target that no listed
    path covers, shallowest first. Each is bound onto itself, writable, before
    the read-only binds; as a mount point it cannot be renamed or removed."""
    pins = {folder for target in targets for folder in target.parents
            if folder != root and folder.is_relative_to(root)
            and not any(p in listed for p in (folder, *folder.parents))}
    return sorted(pins, key=lambda p: (len(p.parts), str(p)))


def _base(bwrap: str) -> list[str]:
    return [bwrap, "--ro-bind", "/", "/", "--dev", "/dev", "--proc", "/proc",
            "--bind", "/tmp", "/tmp"]


def _bind(flag: str, path: Path) -> list[str]:
    return [flag, str(path), str(path)]


def _env() -> list[str]:
    argv = ["--clearenv"]
    for name in ENV_ALLOWLIST:
        if name in os.environ:
            argv += ["--setenv", name, os.environ[name]]
    return argv


def research_argv(project: PathArg, state_root: PathArg, command: str) -> list[str]:
    """Project and state root read-only, /tmp otherwise writable, no network."""
    root = Path(project).resolve(strict=True)
    bwrap = _bwrap()
    state = _state(state_root)
    _, empty_file = _placeholder_sources(state)
    return (_base(bwrap)
            + _bind("--ro-bind", root)
            + _bind("--ro-bind", state)
            + _lock_masks(state, empty_file)
            + _env()
            + ["--unshare-net", "--unshare-pid", "--die-with-parent", "--new-session",
               "--chdir", str(root), "--", "bash", "-c", command])


def _mutate_argv(project: PathArg, state_root: PathArg,
                 command: str) -> tuple[list[str], list[str], list[Path]]:
    """The mutate_shell argv, the project-relative paths bwrap creates for the
    placeholders (each at its path's first missing component) and the nested
    .git entries found. The argv: project writable except its protected paths
    and masked names; state root read-only; .git directory read-only; network
    shared. Raises ProtectedPathSymlink while a masked name or protected path
    is a symlink, GitFileUnsupported while .git is a file and
    ProtectedPathMissing while a required protected path is absent; in each
    case no sandbox starts. Also raises ProtectedPathSymlink while a nested
    .git entry or a component of a git-config-named path is a symlink, and
    GitConfigUnreadable while git cannot list the configuration of a .git
    directory, and FolderUnreadable while a folder within the nested scan
    depth cannot be read. Running the argv leaves the placeholders' mount
    points in the project; run_mutate removes them."""
    root = Path(project).resolve(strict=True)
    git_dir = root / ".git"
    symlinked = [path for path in [*(root / name for name in MASKED), *protected_paths(root)]
                 if path.is_symlink()]
    if symlinked:
        raise ProtectedPathSymlink(symlinked)
    if git_dir.is_file():
        raise GitFileUnsupported(git_dir)
    missing = missing_protected(root)
    if missing:
        raise ProtectedPathMissing(missing)
    listed, nested = _read_only(root)
    symlinked = [*(path for path in nested if path.is_symlink()),
                 *(link for path in listed if path not in nested
                   for link in _symlinked_components(root, path))]
    if symlinked:
        raise ProtectedPathSymlink(list(dict.fromkeys(symlinked)))
    bwrap = _bwrap()
    state = _state(state_root)
    empty_dir, empty_file = _placeholder_sources(state)
    binds: list[str] = []
    targets: list[Path] = []
    placeholders: list[str] = []
    for path, is_dir in listed.items():
        if os.path.lexists(path):
            binds += _bind("--ro-bind", path)
            targets.append(path)
            continue
        first = _first_missing(root, path)
        rel = str(first.relative_to(root))
        if rel not in placeholders:
            source = empty_dir if is_dir or first != path else empty_file
            binds += ["--ro-bind", str(source), str(first)]
            targets.append(first)
            placeholders.append(rel)
    argv = _base(bwrap) + _bind("--bind", root)
    for pin in _ancestor_pins(root, listed, targets):
        argv += _bind("--bind", pin)
    argv += _bind("--ro-bind", state) + _lock_masks(state, empty_file)
    argv += binds
    return argv + _env() + ["--unshare-pid", "--die-with-parent", "--new-session",
                   "--chdir", str(root), "--", "bash", "-c", command], placeholders, nested


def _drain(stream: IO[bytes], limit: int, sink: list[tuple[bytes, int]]) -> None:
    """Keep the first LIMIT bytes of STREAM, count the rest, never buffer it."""
    kept = bytearray()
    total = 0
    while chunk := stream.read1(65536):  # type: ignore[attr-defined]
        total += len(chunk)
        room = limit - len(kept)
        if room > 0:
            kept += chunk[:room]
    stream.close()
    sink.append((bytes(kept), total))


def _render(kept: bytes, total: int) -> str:
    text = kept.decode("utf-8", errors="replace")
    if total > len(kept):
        text += f"\n[chr-gate: output truncated: {total} bytes, first {len(kept)} shown]"
    return text


def run(argv: Sequence[str], timeout: float, max_output_bytes: int) -> RunResult:
    """Run ARGV; stdout and stderr are each capped at MAX_OUTPUT_BYTES with a
    truncation note. On timeout the sandbox is killed and stderr says so."""
    proc = subprocess.Popen(list(argv), stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out: list[tuple[bytes, int]] = []
    err: list[tuple[bytes, int]] = []
    readers = [threading.Thread(target=_drain, args=(proc.stdout, max_output_bytes, out)),
               threading.Thread(target=_drain, args=(proc.stderr, max_output_bytes, err))]
    for reader in readers:
        reader.start()
    timed_out = False
    try:
        rc = proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        proc.kill()
        rc = proc.wait()
    for reader in readers:
        reader.join()
    stderr = _render(*err[0])
    if timed_out:
        stderr += f"\n[chr-gate: command timed out after {timeout}s and was killed]"
    return RunResult(rc, _render(*out[0]), stderr)


def run_mutate(project: PathArg, state_root: PathArg, command: str, timeout: float,
               max_output_bytes: int) -> RunResult:
    """The mutate_shell entry point. Under the project lock: remove a crashed
    run's placeholders, build the argv (raising as _mutate_argv does, before
    any sandbox starts), record this run's placeholders, run, and remove them
    however the run ends. Then rescan for nested .git entries and append one
    warning line to stderr for each the command created and for each folder the
    rescan cannot read."""
    root = Path(project).resolve(strict=True)
    state = _state(state_root)
    with _project_lock(state):
        _remove_placeholders(root, state)
        argv, placeholders, nested = _mutate_argv(root, state, command)
        _record_placeholders(state, placeholders)
        try:
            result = run(argv, timeout, max_output_bytes)
        finally:
            _remove_placeholders(root, state)
        after, unreadable = _nested_git(root)
        warnings = "".join(
            f"\n[chr-gate: warning: the command created git metadata at "
            f"{path.relative_to(root)}; do not run git there before checking its "
            "config and hooks]" for path in after if path not in nested)
        warnings += "".join(
            f"\n[chr-gate: warning: cannot read {path.relative_to(root)} after the "
            "command; git metadata the command created under it was not checked]"
            for path in unreadable)
        return result._replace(stderr=result.stderr + warnings)
