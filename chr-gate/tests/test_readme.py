"""T6: chr-gate/README.md agrees with the documents it cites.

Every expectation is parsed from the sources, never from a hand list:
- every relative markdown link in the README resolves to an existing path;
- every C33 section the README cites ('C33 2.3', 'C33 F.3', 'C33 Appendix A',
  or any 'Appendix X') is a heading of Grounded_Authority_for_Language_Model_Agents_C33.md;
- every verdict marked FALLBACK or LIMIT in docs/spike-findings.md (the
  Verdict summary table and the per-item 'Verdict:' lines) has a limit
  paragraph in the README's 'Stated limits' section naming 'spike item N',
  the host and the verdict;
- each limit label of the 2026-11 review (L1-L8, L11, L12) leads exactly one
  'Stated limits' paragraph, and the labels the review drops because their
  fixes shipped (L9, L10) appear nowhere in the README. These labels are a
  hand list: they name sections of an external review, not of a tracked file.
The release documents are checked too:
- every relative markdown link in the repository root README.md resolves;
- the release documents exist and none calls the release open source.
"""

import re
from pathlib import Path

CHR_GATE = Path(__file__).resolve().parents[1]
REPO = CHR_GATE.parent
README = CHR_GATE / "README.md"
C33 = REPO / "Grounded_Authority_for_Language_Model_Agents_C33.md"
SPIKE = CHR_GATE / "docs" / "spike-findings.md"
ROOT_README = REPO / "README.md"
RELEASE_DOCS = ("README.md", "chr-gate/README.md", "CHANGELOG.md", "CONTRIBUTING.md",
                "LICENSE.md", "COMMERCIAL-LICENSE.md")

LIMIT_VERDICTS = ("FALLBACK", "LIMIT")
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
CITED_SECTION_RE = re.compile(r"C33 (\d+(?:\.\d+)*|[A-Z]\.\d+(?:\.\d+)*)(?![\w.]*\w)")
CITED_APPENDIX_RE = re.compile(r"\bAppendix ([A-Z])\b")
HEADING_RE = re.compile(r"#{1,6}\s+(.*)")
VERDICT_WORD_RE = re.compile(r"\b(" + "|".join(LIMIT_VERDICTS) + r")\b")
OPEN_SOURCE_RE = re.compile(r"open[\s-]source", re.IGNORECASE)
REVIEW_LABELS = ("L1", "L2", "L3", "L4", "L5", "L6", "L7", "L8", "L11", "L12")
DROPPED_LABELS = ("L9", "L10")
LABEL_LEAD_RE = re.compile(r"\**(L\d+)\.")


def _outside_fences(text: str) -> list[str]:
    lines, fenced = [], False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if not fenced:
            lines.append(line)
    return lines


def c33_section_ids() -> set[str]:
    """Section ids from the C33 headings: '2.3', '3', 'F.3', 'Appendix A'."""
    ids = set()
    for line in _outside_fences(C33.read_text(encoding="utf-8")):
        m = HEADING_RE.fullmatch(line)
        if m is None:
            continue
        title = m[1]
        if a := re.match(r"Appendix ([A-Z])\.", title):
            ids.add(f"Appendix {a[1]}")
        elif n := re.match(r"(\d+(?:\.\d+)*)\.?\s", title):
            ids.add(n[1])
        elif s := re.match(r"([A-Z]\.\d+(?:\.\d+)*)\s", title):
            ids.add(s[1])
    return ids


def readme_cited_sections(text: str) -> set[str]:
    body = "\n".join(_outside_fences(text))
    cited = {m[1] for m in CITED_SECTION_RE.finditer(body)}
    cited |= {f"Appendix {m[1]}" for m in CITED_APPENDIX_RE.finditer(body)}
    return cited


def relative_links(text: str) -> list[str]:
    body = "\n".join(_outside_fences(text))
    return [t for t in (m[1] for m in LINK_RE.finditer(body))
            if not SCHEME_RE.match(t) and not t.startswith("#")]


def spike_limit_verdicts() -> tuple[set[tuple[str, str, str]], int]:
    """(item, host, verdict) for every FALLBACK/LIMIT verdict in spike-findings.md,
    from the Verdict summary table and the per-item 'Verdict:' bullets, plus the
    number of verdicts parsed in total (a parse guard)."""
    lines = SPIKE.read_text(encoding="utf-8").splitlines()
    found: set[tuple[str, str, str]] = set()
    parsed = 0
    # Verdict summary table: | # | Measurement | HOST... |
    start = lines.index("## Verdict summary")
    rows = []
    for line in lines[start + 1:]:
        if line.startswith("## "):
            break
        if line.startswith("|"):
            rows.append([c.strip() for c in line.strip().strip("|").split("|")])
    header, data = rows[0], [r for r in rows[2:]]
    hosts = header[2:]
    for row in data:
        for host, cell in zip(hosts, row[2:], strict=True):
            parsed += 1
            if v := VERDICT_WORD_RE.search(cell):
                found.add((row[0], host, v[1]))
    # Per-item sections: '## (N) ...' with '- Host: ... Verdict: X' bullets.
    item = bullet = None
    bullets: list[tuple[str, str]] = []
    for line in lines:
        if m := re.match(r"## \((\d+)\)", line):
            item = m[1]
            continue
        if line.startswith("## "):
            item = None
            continue
        if item is None:
            continue
        if line.startswith("- "):
            bullet = [item, line[2:]]
            bullets.append(bullet)  # type: ignore[arg-type]
        elif bullet is not None and line.startswith(" "):
            bullet[1] += " " + line.strip()
    for n, text in bullets:
        host, _, rest = text.partition(":")
        for v in re.finditer(r"Verdict:\s*([A-Z][A-Z-]*)", rest):
            parsed += 1
            if v[1] in LIMIT_VERDICTS:
                found.add((n, host.strip(), v[1]))
    return found, parsed


def stated_limit_paragraphs(text: str) -> list[str]:
    section = text.split("\n## Stated limits\n", 1)
    assert len(section) == 2, "README has no '## Stated limits' section"
    body = section[1].split("\n## ", 1)[0]
    return [" ".join(p.split()) for p in re.split(r"\n\s*\n", body) if p.strip()]


def test_relative_links_resolve():
    links = relative_links(README.read_text(encoding="utf-8"))
    assert links, "no relative links parsed from the README"
    broken = [t for t in links if not (README.parent / t.split("#", 1)[0]).exists()]
    assert not broken, f"README links to missing paths: {broken}"


def test_cited_c33_sections_exist():
    headings = c33_section_ids()
    assert {"2.3", "Appendix A"} <= headings, "C33 heading parse found no sections"
    cited = readme_cited_sections(README.read_text(encoding="utf-8"))
    assert cited, "the README cites no C33 section"
    missing = sorted(cited - headings)
    assert not missing, f"README cites C33 sections that are not headings of {C33.name}: {missing}"


def test_spike_fallback_and_limit_verdicts_have_limit_paragraphs():
    verdicts, parsed = spike_limit_verdicts()
    assert parsed, "no verdicts parsed from spike-findings.md"
    paragraphs = stated_limit_paragraphs(README.read_text(encoding="utf-8"))
    missing = [(n, host, v) for n, host, v in sorted(verdicts)
               if not any(f"spike item {n}".lower() in p.lower() and host in p and v in p
                          for p in paragraphs)]
    assert not missing, ("FALLBACK/LIMIT verdicts with no 'Stated limits' paragraph naming "
                         f"'spike item N', the host and the verdict: {missing}")


def test_stated_limits_cover_review_labels():
    text = README.read_text(encoding="utf-8")
    leads = [m[1] for p in stated_limit_paragraphs(text) if (m := LABEL_LEAD_RE.match(p))]
    wrong = {label: leads.count(label) for label in REVIEW_LABELS if leads.count(label) != 1}
    assert not wrong, f"review labels not leading exactly one 'Stated limits' paragraph: {wrong}"
    dropped = [label for label in DROPPED_LABELS if re.search(rf"\b{label}\b", text)]
    assert not dropped, f"README names review labels whose fixes shipped: {dropped}"


def test_root_readme_links_resolve():
    links = relative_links(ROOT_README.read_text(encoding="utf-8"))
    assert links, "no relative links parsed from the root README"
    broken = [t for t in links if not (REPO / t.split("#", 1)[0]).exists()]
    assert not broken, f"root README links to missing paths: {broken}"


def test_release_docs_not_called_open_source():
    missing = [d for d in RELEASE_DOCS if not (REPO / d).is_file()]
    assert not missing, f"release documents missing: {missing}"
    called = [d for d in RELEASE_DOCS
              if OPEN_SOURCE_RE.search((REPO / d).read_text(encoding="utf-8"))]
    assert not called, f"release documents that say 'open source': {called}"
