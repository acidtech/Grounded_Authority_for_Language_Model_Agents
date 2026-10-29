from chrgate.core import citations, gate, nonces

FRAME = "session-A"
OTHER = "agent-B"


def test_all_valid_citations_give_no_warning(store):
    a, b = nonces.issue(store, FRAME), nonces.issue(store, FRAME)
    cited = citations.parse(f"Per <cite>{a} {b}</cite> the parser drops CR bytes.")
    assert cited == [a, b]
    invalid = citations.check(store, FRAME, cited)
    assert invalid == []
    assert citations.warning_text(invalid) is None
    # The cite(nonces) fallback hands check the same kind of list.
    assert citations.check(store, FRAME, [b, a]) == []


def test_one_invalid_among_valid_lists_only_it(store, issuer):
    issuer.read_work_order(FRAME)
    a, b = nonces.issue(store, FRAME), nonces.issue(store, FRAME)
    foreign = nonces.issue(store, OTHER)
    cited = citations.parse(f"<cite>{a} {foreign} {b}</cite>")
    assert citations.check(store, FRAME, cited) == [foreign]
    warning = citations.warning_text([foreign])
    assert warning.startswith("<chr-citation-warning>")
    assert warning.endswith("</chr-citation-warning>")
    assert foreign in warning
    assert a not in warning and b not in warning

    assert gate.new_epoch(store, FRAME) == 2  # a previous epoch's nonce is invalid too
    c = nonces.issue(store, FRAME)
    assert citations.check(store, FRAME, [a, c]) == [a]


def test_malformed_tags_reported_without_exception(store):
    good = nonces.issue(store, FRAME)
    text = (f"<cite>{good} ctx:XYZ</cite> <cite></cite> stray </cite> "
            f'<cite nonces="{good}">x</cite> <CITE>{good}</CITE> <cite>{good}')
    cited = citations.parse(text)
    assert cited == [good, "ctx:XYZ", "<cite></cite>", "</cite>", f'<cite nonces="{good}">',
                     "</cite>", "<CITE>", "</CITE>", f"<cite>{good}"]
    invalid = citations.check(store, FRAME, cited)
    assert invalid == cited[1:]
    warning = citations.warning_text(invalid)
    assert "&lt;cite&gt;&lt;/cite&gt;" in warning and "ctx:XYZ" in warning
    for broken in ("<cite", "<cite>", "</cite", "<cite><cite></cite>"):
        assert citations.check(store, FRAME, citations.parse(broken))  # never raises


def test_multiple_tags_merged_in_order(store):
    n = [nonces.issue(store, FRAME) for _ in range(4)]
    text = (f"First <cite>{n[2]}</cite> then\n<cite>\n{n[0]}\t{n[3]}\n</cite> "
            f"and last <cite>{n[1]}</cite>.")
    assert citations.parse(text) == [n[2], n[0], n[3], n[1]]
    assert citations.parse("no tags here") == []
    assert citations.check(store, FRAME, citations.parse(text)) == []
