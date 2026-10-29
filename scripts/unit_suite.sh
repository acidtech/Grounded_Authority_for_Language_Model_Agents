#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../chr-gate"
export PYTHONDONTWRITEBYTECODE=1
base="$(mktemp -d /tmp/chrgate-suite.XXXXXX)"
trap 'rm -rf "$base"' EXIT
uv run --frozen --no-sync pytest -q -p no:cacheprovider --basetemp="$base/t" tests ../scripts/smoke ../scripts/spike
