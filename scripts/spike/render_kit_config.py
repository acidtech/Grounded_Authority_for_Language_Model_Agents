#!/usr/bin/env python3
"""Render a spike kit config template.

Usage: python3 render_kit_config.py --kit DIR --uv PATH SRC DEST

Replaces @KIT@ with DIR (the spike kit directory) and @UV@ with PATH (the uv
binary) in SRC and writes the result to DEST. The hosts need absolute paths
in their hook and MCP commands, and JSON and TOML never expand $HOME, so the
runners render the templates from their own location before starting a host.

Exit 2 and nothing written when DIR or PATH is not absolute or contains
whitespace, a double quote or a backslash, or when any @[A-Z_]+@ token
remains after rendering.
"""
import argparse
import os
import re
import sys

_TOKEN = re.compile(r"@[A-Z_]+@")
_UNSAFE = re.compile(r'[\s"\\]')


def _refuse(message: str) -> int:
    print(f"render_kit_config: {message}; nothing written", file=sys.stderr)
    return 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--kit", required=True)
    parser.add_argument("--uv", required=True)
    parser.add_argument("src")
    parser.add_argument("dest")
    args = parser.parse_args(argv)
    for name, value in (("--kit", args.kit), ("--uv", args.uv)):
        if not os.path.isabs(value):
            return _refuse(f"{name} {value!r} is not an absolute path")
        if _UNSAFE.search(value):
            return _refuse(f"{name} {value!r} contains whitespace, a double quote or a backslash")
    with open(args.src, encoding="utf-8") as fh:
        text = fh.read()
    text = text.replace("@KIT@", args.kit).replace("@UV@", args.uv)
    left = sorted(set(_TOKEN.findall(text)))
    if left:
        return _refuse(f"{args.src} still holds {', '.join(left)} after rendering")
    with open(args.dest, "w", encoding="utf-8") as fh:
        fh.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
