"""Codex config fragment as bare -c pairs (T5b): fragment_pairs.py FRAGMENT.TOML

Prints every setting of the TOML fragment (plugins/codex/config/chr-gate.toml)
as a bare key=value pair with a TOML inline value, each followed by a NUL byte.
smoke_codex.sh reads the list into an array.
"""
import json
import sys
import tomllib


def flat(prefix, value):
    if isinstance(value, dict):
        for key, sub in value.items():
            yield from flat(f"{prefix}.{key}" if prefix else key, sub)
    else:
        yield prefix, value


def inline(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, str)):
        return json.dumps(value)
    raise TypeError(f"unsupported fragment value {value!r}")


def main(argv):
    if len(argv) != 1:
        sys.exit("usage: fragment_pairs.py FRAGMENT.TOML")
    with open(argv[0], "rb") as fh:
        for key, value in flat("", tomllib.load(fh)):
            sys.stdout.write(f"{key}={inline(value)}\0")


if __name__ == "__main__":
    main(sys.argv[1:])
