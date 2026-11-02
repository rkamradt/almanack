"""
Unit tests for corpus/parse.py.
"""

from corpus.parse import modernize, parse_sayings, strip_gutenberg

# ---------------------------------------------------------------------------
# Fixture: minimal Gutenberg-format text with known sayings
# ---------------------------------------------------------------------------

FIXTURE = """\
The Project Gutenberg EBook of Test

*** START OF THE PROJECT GUTENBERG EBOOK TEST ***

THE WAY TO WEALTH.

"Early to bed, and early to rise, makes a man healthy, wealthy, and wise,"
as Poor Richard says.

Also, "Lost time is never found again; and what we call time enough, always
proves little enough." He continued.

[Illustration: Published by W. Darton.]

"Diligence is the mother of good luck," said Father Abraham.

Some text without quotes that should not become a saying.

*** END OF THE PROJECT GUTENBERG EBOOK TEST ***

End of Project Gutenberg
"""


def test_extracts_expected_sayings():
    sayings = parse_sayings(FIXTURE, source="test")
    texts = [s["text"] for s in sayings]
    assert any("early to bed" in t.lower() for t in texts), texts
    assert any("Lost time" in t for t in texts), texts
    assert any("Diligence" in t for t in texts), texts


def test_no_gutenberg_boilerplate_in_sayings():
    sayings = parse_sayings(FIXTURE, source="test")
    for s in sayings:
        assert "PROJECT GUTENBERG" not in s["text"]
        assert "EBook" not in s["text"]


def test_no_illustration_text():
    sayings = parse_sayings(FIXTURE, source="test")
    for s in sayings:
        assert "Darton" not in s["text"]
        assert "Illustration" not in s["text"]


def test_deduplication():
    # Duplicate fixture: same saying twice
    dup = FIXTURE + '\n"Early to bed, and early to rise, makes a man healthy, wealthy, and wise," repeated.\n'
    sayings = parse_sayings(dup, source="test")
    early_bed = [s for s in sayings if "early to bed" in s["text"].lower()]
    assert len(early_bed) == 1, "Duplicate saying should be merged"


def test_each_record_has_required_fields():
    sayings = parse_sayings(FIXTURE, source="test")
    assert len(sayings) > 0
    for s in sayings:
        assert "text" in s
        assert "modern" in s
        assert "source" in s
        assert "line_ref" in s
        assert s["source"] == "test"
        assert s["line_ref"].startswith("q")


def test_source_set_correctly():
    sayings = parse_sayings(FIXTURE, source="my-source")
    for s in sayings:
        assert s["source"] == "my-source"


def test_strip_gutenberg_header():
    body = strip_gutenberg(FIXTURE)
    assert "PROJECT GUTENBERG EBOOK" not in body
    assert "early to bed" in body.lower()


# ---------------------------------------------------------------------------
# Moderniser unit tests
# ---------------------------------------------------------------------------

def test_modernize_thou():
    assert modernize("thou art wise") == "you are wise"


def test_modernize_thy():
    assert modernize("Know thy trade") == "Know your trade"


def test_modernize_hath():
    assert modernize("He that hath a trade hath an estate") == \
           "He that has a trade has an estate"


def test_modernize_tis():
    assert modernize("'Tis the stone") == "It is the stone"


def test_modernize_dost():
    assert modernize("dost thou love life") == "do you love life"


def test_modernize_past_apostrophe():
    result = modernize("labour'd")
    assert result == "laboured"


def test_modernize_preserves_unchanged_words():
    s = "Experience keeps a dear school"
    assert modernize(s) == s
