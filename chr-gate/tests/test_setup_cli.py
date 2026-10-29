import json
import subprocess
import sys
from pathlib import Path


def _snapshot(root):
    return {str(p.relative_to(root)): (p.read_bytes() if p.is_file() else None)
            for p in sorted(root.rglob("*"))}


def test_console_script_chrgate_setup(isolated_env):
    script = Path(sys.executable).parent / "chrgate-setup"
    assert script.is_file(), f"{script} missing: run uv sync in chr-gate/"
    project = isolated_env / "project"
    first = subprocess.run([str(script), "--project", str(project)], capture_output=True,
                           text=True)
    assert first.returncode == 0, first.stderr
    for name in (".claude", ".codex"):
        assert (project / name).is_dir() and not any((project / name).iterdir())
        assert name in first.stdout
    assert json.loads((project / ".mcp.json").read_text()) == {"mcpServers": {}}
    before = _snapshot(project)
    second = subprocess.run([str(script), "--project", str(project)], capture_output=True,
                            text=True)
    assert second.returncode == 0, second.stderr
    assert second.stdout.strip() == "nothing to create"
    assert _snapshot(project) == before
    a_file = isolated_env / "a-file"
    a_file.write_text("x")
    third = subprocess.run([str(script), "--project", str(a_file)], capture_output=True,
                           text=True)
    assert third.returncode != 0
    assert a_file.read_text() == "x"
