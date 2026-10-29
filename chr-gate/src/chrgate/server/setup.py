"""chrgate-setup [--project PATH]: the user-run per-project setup step.

Creates the missing required protected paths (sandbox.ensure_protected: .claude/,
.codex/, .mcp.json, and .git/hooks when .git is a directory), prints each
created path or 'nothing to create', then re-checks sandbox.missing_protected
and exits non-zero while anything required is still missing (notably
.git/config, which setup never creates). A project path that is not a
directory exits non-zero.
"""

import argparse
import os
import sys
from pathlib import Path

from chrgate.core.paths import state_root
from chrgate.server import sandbox


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="chrgate-setup", description="Create the protected paths chr-gate needs in a project.")
    parser.add_argument("--project", default=None, help="project root (default: the cwd)")
    args = parser.parse_args(argv)
    project = Path(args.project) if args.project is not None else Path.cwd()
    if not project.is_dir():
        print(f"chrgate-setup: {project} is not a directory", file=sys.stderr)
        return 2
    project = Path(os.path.realpath(project))
    created = sandbox.ensure_protected(project, state_root(project))
    for path in created:
        print(f"created {path}")
    if not created:
        print("nothing to create")
    missing = sandbox.missing_protected(project)
    if missing:
        print("chrgate-setup: still missing: " + ", ".join(str(p) for p in missing)
              + " (a missing .git/config needs a git repair; setup never creates it)",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
