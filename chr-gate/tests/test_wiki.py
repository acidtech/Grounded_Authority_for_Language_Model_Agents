"""docs/wiki agrees with itself and with the root README.

The pages are generated; each starts with HTML comment header lines, which
these checks skip. Only the top-level pages are read:
- index.md exists and links every other page;
- every relative markdown link in a page body resolves from docs/wiki/;
- no page body holds a wiki: tag or calls the release open source;
- some relative link in the root README.md resolves to docs/wiki/index.md.
"""

import re
from pathlib import Path

from test_readme import OPEN_SOURCE_RE, REPO, ROOT_README, relative_links

WIKI = REPO / "docs" / "wiki"
INDEX = WIKI / "index.md"
WIKI_TAG_RE = re.compile(r"\bwiki:")


def _pages() -> list[Path]:
    pages = sorted(WIKI.glob("*.md"))
    assert pages, f"no pages in {WIKI}"
    return pages


def _body(page: Path) -> str:
    lines = page.read_text(encoding="utf-8").splitlines()
    while lines and lines[0].startswith("<!--"):
        lines.pop(0)
    return "\n".join(lines)


def _target(base: Path, link: str) -> Path:
    return base / link.split("#", 1)[0]


def test_wiki_index_links_every_page():
    assert INDEX.is_file(), f"{INDEX} is missing"
    linked = {_target(WIKI, t).resolve() for t in relative_links(_body(INDEX))}
    others = [p for p in _pages() if p.name != INDEX.name]
    assert others, "the wiki has no page besides index.md"
    missing = [p.name for p in others if p.resolve() not in linked]
    assert not missing, f"index.md does not link: {missing}"


def test_wiki_relative_links_resolve():
    links = {p.name: relative_links(_body(p)) for p in _pages()}
    assert any(links.values()), "no relative links parsed from the wiki pages"
    broken = [(name, t) for name, ts in links.items() for t in ts
              if not _target(WIKI, t).exists()]
    assert not broken, f"wiki links to missing paths: {broken}"


def test_wiki_body_has_no_wiki_tags_or_open_source():
    tagged = [p.name for p in _pages() if WIKI_TAG_RE.search(_body(p))]
    assert not tagged, f"wiki pages with a wiki: tag in the body: {tagged}"
    called = [p.name for p in _pages() if OPEN_SOURCE_RE.search(_body(p))]
    assert not called, f"wiki pages that say 'open source': {called}"


def test_root_readme_links_wiki_index():
    links = relative_links(ROOT_README.read_text(encoding="utf-8"))
    assert any(_target(REPO, t).resolve() == INDEX.resolve() for t in links), \
        "the root README does not link docs/wiki/index.md"
