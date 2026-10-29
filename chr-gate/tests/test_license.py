"""T5: the release ships the official license texts and matching metadata.

- both LICENSES/ files are the verbatim official texts (pinned sha256);
- chr-gate/LICENSE.md carries the Required Notice and the PolyForm text byte for byte;
- chr-gate/pyproject.toml declares the PolyForm SPDX expression, existing license-files and the author;
- the root notices never call the release open source.
"""

import hashlib
import re
import tomllib
from pathlib import Path

CHR_GATE = Path(__file__).resolve().parents[1]
REPO = CHR_GATE.parent
POLYFORM = REPO / "LICENSES" / "PolyForm-Noncommercial-1.0.0.md"
CC = REPO / "LICENSES" / "CC-BY-NC-ND-4.0.txt"
PACKAGE_LICENSE = CHR_GATE / "LICENSE.md"

OFFICIAL_SHA256 = {
    POLYFORM: "c0ea4a896d2c8c394b29f9427589996db826cd501c512279ff0ed3ef48fabbe5",
    CC: "38762e3777f4ec00a6f769062a7c3f704fb78ce08303ecff88558da4c49cf9ea",
}


def test_license_texts_are_official():
    for path, expected in OFFICIAL_SHA256.items():
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected, f"{path.name} is not the official text"


def test_package_license_copy():
    data = PACKAGE_LICENSE.read_bytes()
    notices = [line for line in data.decode("utf-8").splitlines() if line.startswith("Required Notice:")]
    assert notices and "Nathan Scherdin" in notices[0], "chr-gate/LICENSE.md has no Required Notice naming Nathan Scherdin"
    assert data.endswith(POLYFORM.read_bytes()), "chr-gate/LICENSE.md does not end with the PolyForm text"


def test_package_license_metadata():
    project = tomllib.loads((CHR_GATE / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert project["license"] == "PolyForm-Noncommercial-1.0.0"
    assert project["license-files"], "license-files is empty"
    for entry in project["license-files"]:
        assert (CHR_GATE / entry).is_file(), f"license-files entry {entry} does not exist under chr-gate/"
    assert any(author.get("name") == "Nathan Scherdin" for author in project["authors"])


def test_license_files_not_called_open_source():
    for name in ("LICENSE.md", "COMMERCIAL-LICENSE.md"):
        text = (REPO / name).read_text(encoding="utf-8")
        assert not re.search(r"open[ -]source", text, re.IGNORECASE), f"{name} calls the release open source"
