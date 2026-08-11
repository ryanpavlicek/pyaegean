"""`aegean.TokenKind` survives the EpiDoc round trip.

The writer used to have an element for only three kinds (``<w>``/``<num>``/``<g>``) and sent every
other kind to a bare ``<seg>``; the reader mapped a bare ``<seg>`` back to NUMERAL when its text was
all digits and WORD otherwise. So a separator, an unknown sign, and any logogram that had to leave
``<g>`` to carry apparatus markup all came back as words: on the bundled Linear A corpus the WORD
count rose 1,381 to 2,637 across a write/read cycle, making the word-divider the most frequent
"word" in every count, query, and statistic computed off a re-imported edition.

Each kind now names itself in the file: ``<w>`` word, ``<num>`` numeral, ``<g>`` logogram, ``<pc>``
punct, and ``<seg type="...">`` for the rest. An untyped ``<seg>`` keeps the old reading, so EpiDoc
written before the attribute existed still imports exactly as it did.
"""

from __future__ import annotations

import tempfile
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

import aegean
from aegean.core.model import (
    Document,
    DocumentMeta,
    FormSegment,
    ReadingStatus,
    Token,
    TokenFormState,
    TokenKind,
)
from aegean.io import epidoc as epidoc_io
from aegean.io import from_epidoc, to_epidoc

_EPIDOC_RNG_URL = "https://epidoc.stoa.org/schema/9.4/tei-epidoc.rng"
_TEI_NS = "http://www.tei-c.org/ns/1.0"


# ── helpers ──────────────────────────────────────────────────────────────────────


def _doc(tokens: list[Token], doc_id: str = "TEST 1", script_id: str = "lineara") -> Document:
    return Document(
        id=doc_id,
        script_id=script_id,
        tokens=tokens,
        lines=[[t.position for t in tokens if t.position is not None]],
        meta=DocumentMeta(site="Haghia Triada"),
    )


def _roundtrip(doc: Document, tmp_path: Path, script_id: str = "lineara") -> Document:
    p = tmp_path / f"{doc.id.replace(' ', '_')}.xml"
    p.write_text(to_epidoc(doc), encoding="utf-8")
    return from_epidoc(p, script_id=script_id).documents[0]


def _kinds(doc: Document) -> list[str]:
    return [t.kind.value for t in doc.tokens]


def _records(doc: Document) -> list[tuple[str, str, str, tuple[str, ...]]]:
    return [(t.text, t.kind.value, t.status.value, t.alt) for t in doc.tokens]


def _tag(el: ET.Element) -> str:
    return str(el.tag).rsplit("}", 1)[-1]


def _apparatus_carriers(xml: str) -> tuple[list[tuple[str, str | None]], list[tuple[str, str | None]]]:
    """The (element, @type) of every carrier inside ``<lem>`` and inside ``<rdg>``, in order."""
    root = ET.fromstring(xml)
    lem: list[tuple[str, str | None]] = []
    rdg: list[tuple[str, str | None]] = []
    for app in root.iter(f"{{{_TEI_NS}}}app"):
        for branch in app:
            carriers = [(_tag(c), c.get("type")) for c in branch]
            (lem if _tag(branch) == "lem" else rdg).extend(carriers)
    return lem, rdg


def _read_xml(xml: str, tmp_path: Path, name: str = "hand.xml") -> Document:
    p = tmp_path / name
    p.write_text(xml, encoding="utf-8")
    return from_epidoc(p, script_id="lineara").documents[0]


def _edition(body: str, doc_id: str = "HAND 1") -> str:
    """A minimal EpiDoc file whose edition division holds ``body``."""
    return (
        "<?xml version='1.0' encoding='UTF-8'?>\n"
        f'<TEI xmlns="{_TEI_NS}"><teiHeader><fileDesc>'
        f"<titleStmt><title>{doc_id}</title></titleStmt>"
        "<publicationStmt><p>test</p></publicationStmt>"
        f"<sourceDesc><msDesc><msIdentifier><idno>{doc_id}</idno></msIdentifier>"
        "</msDesc></sourceDesc></fileDesc></teiHeader>"
        '<text><body><div type="edition" xml:lang="und"><ab>'
        f'<lb n="1"/>{body}'
        "</ab></div></body></text></TEI>"
    )


_ALL_KINDS = [
    Token("KA-U-DE-TA", TokenKind.WORD, line_no=0, position=0),
    Token("VIN", TokenKind.LOGOGRAM, line_no=0, position=1),
    Token("56", TokenKind.NUMERAL, line_no=0, position=2),
    Token("\U00010101", TokenKind.SEPARATOR, line_no=0, position=3),
    Token(".", TokenKind.PUNCT, line_no=0, position=4),
    Token("*34", TokenKind.UNKNOWN, line_no=0, position=5),
]


# ── the round trip preserves every kind ──────────────────────────────────────────


def test_every_token_kind_survives_the_round_trip(tmp_path: Path) -> None:
    """All six `aegean.TokenKind` members come back as themselves, text and order intact."""
    doc = _doc(list(_ALL_KINDS))
    back = _roundtrip(doc, tmp_path)

    assert _kinds(back) == [
        "word", "logogram", "numeral", "separator", "punct", "unknown",
    ]
    assert _records(back) == _records(doc)


@pytest.mark.parametrize("kind", list(TokenKind), ids=[k.value for k in TokenKind])
def test_each_declared_kind_round_trips(kind: TokenKind, tmp_path: Path) -> None:
    """Enumerated live from `aegean.TokenKind`, so a kind added later cannot quietly land in an
    untyped ``<seg>`` and reload as a word: it fails here until it has a carrier."""
    doc = _doc([Token("SA-MPLE", kind, line_no=0, position=0)], doc_id=f"K {kind.value}")
    assert _roundtrip(doc, tmp_path).tokens[0].kind is kind


def test_writer_and_reader_seg_type_tables_are_inverses() -> None:
    """The ``@type`` the writer emits is exactly the one the reader maps back, for every kind.

    The two tables live on opposite sides of the module; pinning the inversion here means a value
    edited on one side alone turns this red rather than silently degrading to the text heuristic.
    """
    assert set(epidoc_io._SEG_TYPE) == set(TokenKind)
    assert epidoc_io._KIND_BY_SEG_TYPE == {
        value: kind for kind, value in epidoc_io._SEG_TYPE.items()
    }
    for kind, seg_type in epidoc_io._SEG_TYPE.items():
        assert seg_type == seg_type.casefold(), "written @type must match the reader's casefold"
        assert epidoc_io._kind_of("seg", "", seg_type) is kind


def test_separator_does_not_return_as_a_word(tmp_path: Path) -> None:
    """The headline symptom: the Linear A word-divider reloaded as a WORD.

    A separator between two words must stay a separator, or every word count taken off a
    re-imported edition is inflated by the dividers.
    """
    doc = _doc([
        Token("KA-U-DE-TA", TokenKind.WORD, line_no=0, position=0),
        Token("\U00010101", TokenKind.SEPARATOR, line_no=0, position=1),
        Token("RE-ZA", TokenKind.WORD, line_no=0, position=2),
    ])
    back = _roundtrip(doc, tmp_path)

    assert _kinds(back) == ["word", "separator", "word"]
    assert sum(t.kind is TokenKind.WORD for t in back.tokens) == 2


@pytest.mark.parametrize(
    ("kind", "text", "expected_carrier"),
    [
        (TokenKind.WORD, "KA-U", "<w>KA-U</w>"),
        (TokenKind.NUMERAL, "56", "<num>56</num>"),
        (TokenKind.LOGOGRAM, "VIN", "<g>VIN</g>"),
        (TokenKind.PUNCT, ".", "<pc>.</pc>"),
        (TokenKind.SEPARATOR, "\U00010101", '<seg type="separator">\U00010101</seg>'),
        (TokenKind.UNKNOWN, "*34", '<seg type="unknown">*34</seg>'),
    ],
)
def test_each_kind_writes_its_own_carrier(
    kind: TokenKind, text: str, expected_carrier: str
) -> None:
    """The emitted element names the kind: a dedicated TEI element, or ``<seg>`` plus ``@type``."""
    xml = to_epidoc(_doc([Token(text, kind, line_no=0, position=0)]))
    assert expected_carrier in xml


def test_logogram_needing_apparatus_uses_a_typed_seg(tmp_path: Path) -> None:
    """A non-CERTAIN logogram leaves ``<g>`` (whose TEI content model excludes ``<unclear>``)
    for ``<seg type="logogram">``, and reloads as a logogram rather than a word."""
    doc = _doc([
        Token("OVIS", TokenKind.LOGOGRAM, line_no=0, position=0, status=ReadingStatus.UNCLEAR),
    ])
    xml = to_epidoc(doc)

    assert '<seg type="logogram">' in xml
    assert "<unclear>OVIS</unclear>" in xml
    back = _roundtrip(doc, tmp_path)
    assert _records(back) == [("OVIS", "logogram", "unclear", ())]


@pytest.mark.parametrize(
    "status",
    [ReadingStatus.CERTAIN, ReadingStatus.UNCLEAR, ReadingStatus.RESTORED, ReadingStatus.LOST],
)
def test_kinds_and_status_survive_together(status: ReadingStatus, tmp_path: Path) -> None:
    """Editorial certainty and kind are independent: neither is lost when the other is set."""
    tokens = [
        Token(t.text, t.kind, line_no=0, position=i, status=status)
        for i, t in enumerate(_ALL_KINDS)
    ]
    back = _roundtrip(_doc(tokens), tmp_path)

    assert _kinds(back) == ["word", "logogram", "numeral", "separator", "punct", "unknown"]
    assert [t.status for t in back.tokens] == [status] * 6


def test_kinds_survive_alongside_alternate_readings(tmp_path: Path) -> None:
    """The ``<app><lem>/<rdg>`` path carries the kind on its own carrier elements too."""
    tokens = [
        Token(t.text, t.kind, line_no=0, position=i, alt=(f"alt{i}",))
        for i, t in enumerate(_ALL_KINDS)
    ]
    xml = to_epidoc(_doc(tokens))
    # both branches of the apparatus carry the kind, not just the lemma
    lem_carriers, rdg_carriers = _apparatus_carriers(xml)
    assert lem_carriers == rdg_carriers == [
        ("w", None), ("seg", "logogram"), ("num", None),
        ("seg", "separator"), ("pc", None), ("seg", "unknown"),
    ]

    back = _roundtrip(_doc(tokens), tmp_path)
    assert _kinds(back) == ["word", "logogram", "numeral", "separator", "punct", "unknown"]
    assert [t.alt for t in back.tokens] == [(f"alt{i}",) for i in range(6)]


def test_kinds_survive_a_typed_form_state(tmp_path: Path) -> None:
    """A seg-carried kind keeps its kind when the token also carries a diplomatic/regularized
    ``<choice>``; the selected and diplomatic forms still round-trip."""
    doc = _doc(
        [
            Token(
                "b",
                TokenKind.SEPARATOR,
                line_no=0,
                position=0,
                form_state=TokenFormState(diplomatic="a", regularized="b"),
            ),
            Token(
                "d",
                TokenKind.UNKNOWN,
                line_no=0,
                position=1,
                form_state=TokenFormState(diplomatic="c", regularized="d"),
            ),
        ],
    )
    back = _roundtrip(doc, tmp_path)

    assert _kinds(back) == ["separator", "unknown"]
    assert [t.text for t in back.tokens] == ["b", "d"]
    assert [t.form_state.diplomatic for t in back.tokens if t.form_state] == ["a", "c"]


def test_punct_token_survives_with_apparatus(tmp_path: Path) -> None:
    """``<pc>`` can hold apparatus markup, so a restored punctuation mark needs no fallback."""
    doc = _doc(
        [
            Token(
                ".",
                TokenKind.PUNCT,
                line_no=0,
                position=0,
                status=ReadingStatus.RESTORED,
                form_state=TokenFormState(
                    diplomatic=".",
                    segments=(FormSegment(".", ReadingStatus.RESTORED, None),),
                ),
            )
        ],
        script_id="greek",
    )
    xml = to_epidoc(doc)
    pc = ET.fromstring(xml).find(f".//{{{_TEI_NS}}}pc")
    assert pc is not None
    supplied = list(pc)
    assert [(_tag(el), el.get("reason"), el.text) for el in supplied] == [
        ("supplied", "lost", ".")
    ]

    back = _roundtrip(doc, tmp_path, script_id="greek")
    assert _records(back) == [(".", "punct", "restored", ())]


# ── the real corpora ─────────────────────────────────────────────────────────────


def test_bundled_linear_a_tablet_keeps_its_kind_census(tmp_path: Path) -> None:
    """HT 13, the reported case: 8 words / 10 numerals / 2 logograms / 2 separators, unchanged
    by a write/read cycle. Before, its two separators returned as words (10 words / 0 separators)."""
    doc = aegean.load("lineara").get("HT13")
    counts = {k: sum(t.kind.value == k for t in doc.tokens) for k in
              ("word", "numeral", "logogram", "separator")}
    assert counts == {"word": 8, "numeral": 10, "logogram": 2, "separator": 2}

    back = _roundtrip(doc, tmp_path)
    assert _records(back) == _records(doc)


@pytest.mark.parametrize("corpus_id", ["lineara", "cypriot"])
def test_whole_corpus_kind_census_is_preserved(corpus_id: str, tmp_path: Path) -> None:
    """Over every bundled document of a corpus, the total per-kind census is identical before
    and after the round trip, and no individual document's kind sequence changes.

    Linear A is the demanding case: it is the only bundled corpus carrying all of words,
    numerals, logograms, separators and unknown signs.
    """
    corpus = aegean.load(corpus_id)
    before: dict[str, int] = {}
    after: dict[str, int] = {}
    changed: list[str] = []
    target = tmp_path / "doc.xml"
    for doc in corpus:
        target.write_text(to_epidoc(doc), encoding="utf-8")
        back = from_epidoc(target, script_id=corpus_id).documents[0]
        for kind in _kinds(doc):
            before[kind] = before.get(kind, 0) + 1
        for kind in _kinds(back):
            after[kind] = after.get(kind, 0) + 1
        if _kinds(doc) != _kinds(back):
            changed.append(doc.id)

    assert not changed, f"{len(changed)} documents changed kinds, e.g. {changed[:5]}"
    assert after == before
    # guard the census itself, so a corpus rebuild that silently drops a kind is visible here
    if corpus_id == "lineara":
        assert before == {
            "logogram": 2211, "numeral": 1621, "separator": 524, "unknown": 669, "word": 1381,
        }
    else:
        assert before == {"numeral": 1, "unknown": 179, "word": 448}


# ── EpiDoc written before @type carried the kind ─────────────────────────────────


def test_untyped_seg_still_reads_as_word_or_numeral(tmp_path: Path) -> None:
    """A bare ``<seg>`` (a foreign edition, or EpiDoc pyaegean wrote before this attribute) keeps
    the historical reading: all-digit text is a numeral, anything else a word."""
    doc = _read_xml(
        _edition(
            "<w>KA-U-DE-TA</w><g>VIN</g>"
            "<seg>\U00010101</seg><seg>17</seg><num>5</num>"
            "<seg><unclear>TE</unclear></seg>"
        ),
        tmp_path,
    )
    assert _records(doc) == [
        ("KA-U-DE-TA", "word", "certain", ()),
        ("VIN", "logogram", "certain", ()),
        ("\U00010101", "word", "certain", ()),      # historical reading, deliberately unchanged
        ("17", "numeral", "certain", ()),
        ("5", "numeral", "certain", ()),
        ("TE", "word", "unclear", ()),
    ]


def test_untyped_seg_inside_an_app_keeps_the_historical_reading(tmp_path: Path) -> None:
    """The apparatus path has the same legacy behaviour: an untyped ``<seg>`` in a ``<lem>``, and
    a ``<lem>`` with no carrier at all, both read as before."""
    doc = _read_xml(
        _edition(
            "<app><lem><seg>\U00010101</seg></lem><rdg><seg>|</seg></rdg></app>"
            "<app><lem>PLAIN</lem><rdg>OTHER</rdg></app>"
        ),
        tmp_path,
    )
    assert _records(doc) == [
        ("\U00010101", "word", "certain", ("|",)),
        ("PLAIN", "word", "certain", ("OTHER",)),
    ]


# ── hostile / wrong-but-plausible @type values ───────────────────────────────────


@pytest.mark.parametrize(
    ("type_attr", "text", "expected"),
    [
        ("separator", "\U00010101", "separator"),   # what pyaegean writes
        ("SEPARATOR", "\U00010101", "separator"),   # a hand-written edition shouting
        ("  Unknown  ", "*34", "unknown"),          # padded and mixed case
        ("separator", "17", "separator"),           # @type outranks the all-digits heuristic
        ("", "KA-U", "word"),                       # empty @type: fall back
        ("   ", "KA-U", "word"),                    # whitespace-only @type: fall back
        ("line", "KA-U", "word"),                   # a foreign edition's own vocabulary
        ("word/separator", "\U00010101", "word"),   # not a kind name: fall back
        ("nonsense", "17", "numeral"),              # fall back, digits still read as a numeral
    ],
)
def test_seg_type_values_are_read_defensively(
    type_attr: str, text: str, expected: str, tmp_path: Path
) -> None:
    """An unrecognized, empty, or foreign ``<seg>/@type`` falls back to the historical text-based
    reading instead of raising or inventing a kind; a recognized one wins over the heuristic."""
    doc = _read_xml(_edition(f'<seg type="{type_attr}">{text}</seg>'), tmp_path)
    assert _kinds(doc) == [expected]


def test_pathologically_long_seg_type_is_rejected_cleanly(tmp_path: Path) -> None:
    """A megabyte-long ``@type`` is not a kind: the token still loads, by the fallback reading."""
    doc = _read_xml(_edition(f'<seg type="{"x" * 1_000_000}">KA-U</seg>'), tmp_path)
    assert _records(doc) == [("KA-U", "word", "certain", ())]


def test_kind_attribute_on_a_dedicated_carrier_is_ignored(tmp_path: Path) -> None:
    """``@type`` only names the kind on ``<seg>``. A ``<w type="numeral">`` is still a word: the
    element is the stronger statement, and foreign editions type ``<w>`` for their own purposes."""
    doc = _read_xml(
        _edition('<w type="numeral">KA-U</w><num type="word">5</num><pc type="unknown">.</pc>'),
        tmp_path,
    )
    assert _kinds(doc) == ["word", "numeral", "punct"]


def test_foreign_punctuation_element_is_read_as_a_token(tmp_path: Path) -> None:
    """``<pc>`` is now a recognized carrier, so punctuation in a third-party edition is imported
    as a PUNCT token rather than dropped from the text stream."""
    doc = _read_xml(_edition("<w>λόγος</w><pc>.</pc><w>ἦν</w>"), tmp_path)
    assert _records(doc) == [
        ("λόγος", "word", "certain", ()),
        (".", "punct", "certain", ()),
        ("ἦν", "word", "certain", ()),
    ]


# ── the output is still EpiDoc ───────────────────────────────────────────────────


@pytest.fixture(scope="module")
def epidoc_rng():  # type: ignore[no-untyped-def]
    """The official EpiDoc RelaxNG validator, cached in the temp dir; skips if unreachable."""
    etree = pytest.importorskip("lxml.etree")
    cache = Path(tempfile.gettempdir()) / "pyaegean-tei-epidoc-9.4.rng"
    if not cache.exists():
        try:
            with urllib.request.urlopen(_EPIDOC_RNG_URL, timeout=30) as resp:
                cache.write_bytes(resp.read())
        except Exception as exc:  # offline / CI without network — skip, don't fail
            pytest.skip(f"EpiDoc schema unavailable: {exc}")
    try:
        return etree.RelaxNG(etree.parse(str(cache)))
    except Exception as exc:  # pragma: no cover - corrupt cache
        cache.unlink(missing_ok=True)
        pytest.skip(f"EpiDoc schema unusable: {exc}")


def test_every_carrier_shape_validates_against_the_epidoc_schema(epidoc_rng) -> None:  # type: ignore[no-untyped-def]
    """``<pc>`` and the typed ``<seg>`` are real EpiDoc: every kind, on its own and combined with
    apparatus markup, alternate readings, and a typed form state, validates against the official
    EpiDoc RelaxNG schema."""
    from lxml import etree

    samples = [to_epidoc(_doc(list(_ALL_KINDS)))]
    for status in (ReadingStatus.UNCLEAR, ReadingStatus.RESTORED, ReadingStatus.LOST):
        samples.append(
            to_epidoc(_doc([
                Token(t.text, t.kind, line_no=0, position=i, status=status)
                for i, t in enumerate(_ALL_KINDS)
            ]))
        )
    samples.append(
        to_epidoc(_doc([
            Token(t.text, t.kind, line_no=0, position=i, alt=(f"alt{i}",))
            for i, t in enumerate(_ALL_KINDS)
        ]))
    )
    samples.append(
        to_epidoc(_doc(
            [
                Token(
                    "b", TokenKind.SEPARATOR, line_no=0, position=0,
                    form_state=TokenFormState(diplomatic="a", regularized="b"),
                ),
                Token(
                    "d", TokenKind.PUNCT, line_no=0, position=1,
                    form_state=TokenFormState(diplomatic="c", regularized="d"),
                ),
            ],
            script_id="greek",
        ))
    )
    samples.append(to_epidoc(aegean.load("lineara").get("HT13")))

    for xml in samples:
        tree = etree.fromstring(xml.encode("utf-8"))
        assert epidoc_rng.validate(tree), epidoc_rng.error_log
