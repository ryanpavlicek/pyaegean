"""Correctness coverage for aegean.core + the Greek backend toggles.

Backfills output-verifying tests for the public surface in the audit group:

- ``Corpus`` access/transform/interop/citation: ``query`` / ``filter`` / ``subset`` /
  ``merge`` / ``combine`` / ``word_frequencies`` / ``to_dataframe`` / ``to_json`` /
  ``from_json`` / ``to_dict`` / ``cite`` / ``fingerprint`` / ``cache_key`` / streaming views;
- ``Document`` / ``Token`` / ``Sign`` / ``SignInventory`` accessors;
- ``Provenance.bibtex`` / ``apa`` / ``cite`` (assert parseable, correct fields);
- ``register_loader`` / ``read_corpus`` resolution;
- the script registry (``register`` / ``get_script`` / ``registered_scripts``);
- the Greek backend toggles (``use_*`` / ``disable_*``): contract tests that ``active()``
  flips. The ``use_*`` activations need a fetched/built index or model, so each is gated on
  the cache already existing (and the disable path, which is pure local state, is always
  tested). Every expected value below is hand-derived or a stated invariant, never a snapshot
  of current output.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys

import pytest

import aegean
from aegean.core.corpus import Corpus, register_loader
from aegean.core.model import (
    Document,
    DocumentMeta,
    ReadingStatus,
    Sign,
    SignInventory,
    Token,
    TokenKind,
)
from aegean.core.provenance import Provenance
from aegean.core.resolve import CorpusNotFound, read_corpus

PROV = Provenance(
    source="Example corpus via example.org",
    license="CC BY 4.0",
    citation="Editor, B. (2018). A Small Edition.",
    url="https://example.org/ed",
)


def test_analysis_and_viz_namespaces_are_lazy_and_discoverable() -> None:
    code = (
        "import sys, aegean\n"
        "assert {'analysis', 'viz'} <= set(dir(aegean))\n"
        "assert 'aegean.analysis' not in sys.modules\n"
        "assert 'aegean.viz' not in sys.modules\n"
        "assert aegean.analysis.__name__ == 'aegean.analysis'\n"
        "assert 'aegean.analysis' in sys.modules\n"
        "assert aegean.viz.__name__ == 'aegean.viz'\n"
        "assert 'aegean.viz' in sys.modules\n"
    )
    subprocess.run([sys.executable, "-c", code], check=True)


def _doc(doc_id: str, site: str, words: list[str], *, line_breaks: list[int] | None = None) -> Document:
    """A WORD-only document; ``line_breaks`` lists token indices that start a new line."""
    tokens = [Token(w, TokenKind.WORD, position=i) for i, w in enumerate(words)]
    breaks = set(line_breaks or [])
    lines: list[list[int]] = []
    cur: list[int] = []
    for i in range(len(tokens)):
        if i in breaks and cur:
            lines.append(cur)
            cur = []
        cur.append(i)
    if cur:
        lines.append(cur)
    return Document(
        id=doc_id, script_id="lineara", tokens=tokens,
        lines=lines or [list(range(len(tokens)))], meta=DocumentMeta(site=site),
    )


def _corpus() -> Corpus:
    return Corpus(
        [
            _doc("X1", "Alpha", ["KU-RO", "KI-RO"]),
            _doc("X2", "Alpha", ["KU-RO"]),
            _doc("X3", "Beta", ["SA-RA"]),
        ],
        None, PROV, "lineara",
    )


# ── Corpus.word_frequencies ───────────────────────────────────────────────────
def test_word_frequencies_counts_and_orders_words_only() -> None:
    """Counts WORD tokens only; sorted by descending count, ties broken alphabetically.
    Hand count over the fixture: KU-RO appears in X1 and X2 -> 2; KI-RO -> 1; SA-RA -> 1.
    Numerals/logograms must be excluded."""
    c = Corpus(
        [
            _doc("d1", "S", ["KU-RO", "KI-RO"]),
            _doc("d2", "S", ["KU-RO"]),
            Document(
                id="d3", script_id="lineara",
                tokens=[
                    Token("SA-RA", TokenKind.WORD, position=0),
                    Token("5", TokenKind.NUMERAL, position=1),     # excluded
                    Token("GRA", TokenKind.LOGOGRAM, position=2),  # excluded
                ],
                lines=[[0, 1, 2]],
            ),
        ],
        script_id="lineara",
    )
    assert c.word_frequencies() == [("KU-RO", 2), ("KI-RO", 1), ("SA-RA", 1)]


def test_word_frequencies_tie_breaks_alphabetically() -> None:
    """Two words at the same count -> the lower string sorts first (key is (-count, word))."""
    c = Corpus([_doc("d", "S", ["Zeta", "Alpha"])], script_id="lineara")
    assert c.word_frequencies() == [("Alpha", 1), ("Zeta", 1)]


# ── streaming views ────────────────────────────────────────────────────────────
def test_iter_words_matches_word_frequencies_multiset() -> None:
    """iter_words is exactly the multiset word_frequencies aggregates, and excludes
    non-WORD tokens. Independent check via collections.Counter."""
    from collections import Counter

    c = Corpus(
        [
            _doc("d1", "S", ["a", "b", "a"]),
            Document(
                id="d2", script_id="lineara",
                tokens=[Token("9", TokenKind.NUMERAL, position=0)], lines=[[0]],
            ),
        ],
        script_id="lineara",
    )
    assert Counter(c.iter_words()) == Counter({"a": 2, "b": 1})
    assert Counter(c.iter_words()) == Counter(dict(c.word_frequencies()))


def test_iter_tokens_is_lazy_and_in_document_order() -> None:
    """iter_tokens yields every token (all kinds) in document then in-document order, and is a
    one-shot generator (a second pass is empty), so it never materializes a list."""
    c = Corpus(
        [_doc("d1", "S", ["a", "b"]), _doc("d2", "S", ["c"])],
        script_id="lineara",
    )
    it = c.iter_tokens()
    assert [t.text for t in it] == ["a", "b", "c"]
    assert list(it) == []  # exhausted -> it was a generator, not a stored list


# ── Corpus.filter / subset ──────────────────────────────────────────────────────
def test_filter_matches_all_fields_and_records_subset_note() -> None:
    """filter is an AND over metadata equality. Two docs have site='Alpha'; the result keeps
    exactly those two, in order, and appends a subset note naming the predicate and the count."""
    sub = _corpus().filter(site="Alpha")
    assert [d.id for d in sub] == ["X1", "X2"]
    assert sub.provenance.notes[-1] == "subset: filter(site='Alpha') → 2 of 3 documents"
    # an over-constrained AND yields nothing
    assert len(_corpus().filter(site="Alpha", scribe="nobody")) == 0


def test_subset_keeps_requested_ids_in_original_order() -> None:
    """subset selects by id and preserves the corpus's order (not the argument order)."""
    sub = _corpus().subset({"X3", "X1"})
    assert [d.id for d in sub] == ["X1", "X3"]  # original order, not {X3, X1}
    assert sub.provenance.notes[-1] == "subset: 2 of 3 documents by id"


# ── Corpus.merge / combine ──────────────────────────────────────────────────────
def test_merge_concatenates_and_dedupe_modes() -> None:
    """Disjoint merge concatenates in order. On a full id collision: 'error' raises,
    'first'/'last' keep one copy, 'suffix' renames the later one to id#2."""
    a = Corpus([_doc("d1", "S", ["a"])], None, Provenance(source="A"), "lineara")
    b = Corpus([_doc("d2", "S", ["b"])], None, Provenance(source="B"), "lineara")
    assert [d.id for d in a.merge(b)] == ["d1", "d2"]

    with pytest.raises(ValueError, match="duplicate document ids"):
        a.merge(a)
    assert [d.id for d in a.merge(a, dedupe="first")] == ["d1"]
    assert [d.id for d in a.merge(a, dedupe="last")] == ["d1"]
    assert [d.id for d in a.merge(a, dedupe="suffix")] == ["d1", "d1#2"]


def test_merge_mixed_scripts_drops_inventory_and_names_sources() -> None:
    """Merging different script_ids yields script_id='mixed', a None inventory, and a fresh
    provenance naming each input source."""
    a = Corpus([_doc("d1", "S", ["a"])], SignInventory([], "lineara"),
               Provenance(source="Src-A"), "lineara")
    b = Corpus([_doc("d2", "S", ["b"])], SignInventory([], "greek"),
               Provenance(source="Src-B"), "greek")
    m = a.merge(b)
    assert m.script_id == "mixed"
    assert m.sign_inventory is None
    cite = m.cite()
    assert "Src-A" in cite and "Src-B" in cite


def test_combine_equals_merge_and_rejects_empty() -> None:
    """aegean.combine([a, b]) is a.merge(b); combine([]) raises."""
    a = Corpus([_doc("d1", "S", ["a"])], None, Provenance(source="A"), "lineara")
    b = Corpus([_doc("d2", "S", ["b"])], None, Provenance(source="B"), "lineara")
    assert [d.id for d in aegean.combine([a, b])] == [d.id for d in a.merge(b)]
    with pytest.raises(ValueError, match="at least one corpus"):
        aegean.combine([])


def test_merge_bad_dedupe_rejected() -> None:
    a = Corpus([_doc("d1", "S", ["a"])], None, None, "lineara")
    with pytest.raises(ValueError, match="dedupe"):
        a.merge(a, dedupe="bogus")


# ── Corpus.fingerprint / cache_key ──────────────────────────────────────────────
def test_fingerprint_is_sha256_hex_and_alias_of_cache_key() -> None:
    """fingerprint is a 64-char lowercase hex sha256, and cache_key returns the same value."""
    c = _corpus()
    fp = c.fingerprint()
    assert re.fullmatch(r"[0-9a-f]{64}", fp)
    assert c.cache_key() == fp


def test_fingerprint_keys_on_token_text_not_metadata() -> None:
    """The fingerprint hashes script_id + doc ids + token text. Changing only document
    metadata leaves it unchanged; changing a token's text changes it."""
    base = Corpus([_doc("d1", "Alpha", ["a", "b"])], script_id="lineara")
    meta_only = Corpus([_doc("d1", "Beta", ["a", "b"])], script_id="lineara")  # site differs
    text_diff = Corpus([_doc("d1", "Alpha", ["a", "c"])], script_id="lineara")  # token differs
    assert base.fingerprint() == meta_only.fingerprint()
    assert base.fingerprint() != text_diff.fingerprint()


# ── Corpus.to_dict (lossy) ───────────────────────────────────────────────────────
def test_to_dict_is_lossy_word_only_with_meta_header() -> None:
    """to_dict keeps only WORD token text per document and a provenance header; numerals and
    logograms are dropped. Hand-derived: the doc has one WORD ('W'), so words == ['W']."""
    doc = Document(
        id="dd", script_id="lineara",
        tokens=[
            Token("W", TokenKind.WORD, position=0),
            Token("5", TokenKind.NUMERAL, position=1),
            Token("GRA", TokenKind.LOGOGRAM, position=2),
        ],
        lines=[[0, 1, 2]],
    )
    c = Corpus([doc], None, PROV, "lineara")
    out = c.to_dict()
    assert out["documents"][0]["words"] == ["W"]
    assert out["_meta"]["scriptId"] == "lineara"
    assert out["_meta"]["citation"] == PROV.cite()
    assert out["_meta"]["documentCount"] == 1


# ── Corpus.to_json / from_json (lossless round-trip) ─────────────────────────────
def test_json_roundtrip_preserves_every_field() -> None:
    """to_json/from_json is lossless: a corpus exercising every token kind, statuses, alt
    readings, annotations, sign attrs, and provenance notes reconstructs to an equal object
    (dataclass __eq__ over the whole tree). This is the round-trip identity invariant."""
    toks = [
        Token("KU-RO", TokenKind.WORD, ("KU", "RO"), glyphs="𐀓𐀫", line_no=0, position=0,
              status=ReadingStatus.UNCLEAR, alt=("KI-RO",), annotations={"lemma": "kuro"}),
        Token("5", TokenKind.NUMERAL, ("5",), line_no=0, position=1),
        Token("GRA", TokenKind.LOGOGRAM, ("GRA",), line_no=1, position=2),
    ]
    doc = Document(
        id="HT1", script_id="lineara", tokens=toks, lines=[[0, 1], [2]],
        glyphs="𐀓𐀫", transcription="KU-RO 5 GRA", translations=["total (illustrative)"],
        meta=DocumentMeta(site="HT", support="tablet", scribe="s1", findspot="villa",
                          period="LMIB", name="HT 1", images=("a.jpg",), notes=("bibl",)),
    )
    inv = SignInventory(
        [Sign("KU", glyph="𐀓", codepoint=0x10053, phonetic="ku", script_id="lineara",
              attrs={"sharedWithLinearB": True})],
        "lineara",
    )
    prov = Provenance(source="Synthetic", license="CC0", citation="Test (2026).",
                      url="https://example.org", notes=("subset: 1 of 1 documents by id",))
    c = Corpus([doc], inv, prov, "lineara")

    c2 = Corpus.from_json(c.to_json())
    assert c2.script_id == "lineara"
    assert c2.documents == c.documents          # full tree equality (tokens/lines/meta/anno)
    assert c2.provenance == c.provenance
    assert c2.sign_inventory.signs == c.sign_inventory.signs


def test_json_empty_annotations_and_default_status_omitted() -> None:
    """Compact + back-compatible serialization: a CERTAIN token with no alt/annotations emits
    neither 'status' nor 'alt' nor 'annotations' keys, yet still round-trips to an equal token."""
    doc = Document(
        id="d", script_id="lineara",
        tokens=[Token("A-DU", TokenKind.WORD, position=0)], lines=[[0]],
    )
    c = Corpus([doc], script_id="lineara")
    raw = json.loads(c.to_json())["documents"][0]["tokens"][0]
    assert "status" not in raw and "alt" not in raw and "annotations" not in raw
    assert Corpus.from_json(c.to_json()).documents == c.documents


def test_json_file_path_and_string_sources(tmp_path) -> None:
    """from_json accepts a Path, a path-like string, and an inline JSON string; writing to a
    path returns None and produces a file whose reload matches the original documents."""
    c = _corpus()
    p = tmp_path / "c.json"
    assert c.to_json(p) is None and p.exists()
    assert Corpus.from_json(p).documents == c.documents              # Path
    assert Corpus.from_json(str(p)).documents == c.documents          # path-like str
    assert Corpus.from_json(c.to_json()).documents == c.documents     # inline JSON string


# ── Corpus.to_dataframe ──────────────────────────────────────────────────────────
def test_to_dataframe_levels_and_counts() -> None:
    """document level -> one row per document with n_words/n_tokens columns; word level ->
    only WORD tokens. Hand-derived: X1 has 2 words, X2 has 1, X3 has 1 -> 3 doc rows, 4 word
    rows; token level keeps all tokens including the lone numeral added below."""
    pytest.importorskip("pandas")
    c = Corpus(
        [
            _doc("X1", "Alpha", ["KU-RO", "KI-RO"]),
            _doc("X2", "Alpha", ["KU-RO"]),
            Document(
                id="X3", script_id="lineara",
                tokens=[
                    Token("SA-RA", TokenKind.WORD, position=0),
                    Token("5", TokenKind.NUMERAL, position=1),
                ],
                lines=[[0, 1]],
            ),
        ],
        script_id="lineara",
    )
    docdf = c.to_dataframe(level="document")
    assert list(docdf["id"]) == ["X1", "X2", "X3"]
    assert list(docdf["n_words"]) == [2, 1, 1]

    worddf = c.to_dataframe(level="word")
    assert len(worddf) == 4 and (worddf["kind"] == "word").all()

    tokdf = c.to_dataframe(level="token")
    assert len(tokdf) == 5  # 4 words + 1 numeral
    assert set(tokdf["kind"]) == {"word", "numeral"}


def test_to_dataframe_rejects_unknown_level() -> None:
    pytest.importorskip("pandas")
    with pytest.raises(ValueError, match="level"):
        _corpus().to_dataframe(level="paragraph")


# ── Corpus.cite (styles) ─────────────────────────────────────────────────────────
def test_corpus_cite_styles_and_subset_note() -> None:
    """'plain' == Provenance.cite(); a filtered subset appends its subset note in brackets;
    'bibtex' produces an @misc entry keyed by script; an unknown style raises."""
    c = _corpus()
    assert c.cite() == PROV.cite()
    sub = c.filter(site="Alpha")
    assert "subset: filter(site='Alpha') → 2 of 3 documents" in sub.cite()
    assert c.cite("bibtex").startswith("@misc{lineara-corpus,")
    assert c.cite("apa").startswith("Editor, B. (2018).")
    with pytest.raises(ValueError, match="style"):
        c.cite("chicago")


def test_corpus_without_provenance_cannot_cite() -> None:
    with pytest.raises(ValueError, match="no provenance"):
        Corpus([], None, None, "lineara").cite()


# ── Corpus.query ─────────────────────────────────────────────────────────────────
def test_query_inscription_scope_equals_filter() -> None:
    """An inscription-scope site-is query returns the same id set as the equivalent
    metadata filter; both select the two 'Alpha' docs."""
    from aegean.analysis import FilterRow

    c = _corpus()
    via_query = {d.id for d in c.query([FilterRow("site-is", "Alpha")]).inscriptions}
    via_filter = {d.id for d in c.filter(site="Alpha")}
    assert via_query == via_filter == {"X1", "X2"}


def test_query_word_output_counts_document_frequency() -> None:
    """output='words' counts distinct documents (document frequency), not tokens. Fixture:
    KU-RO written twice in one doc and once in another -> document frequency 2 (not 3)."""
    from aegean.analysis import FilterRow

    c = Corpus(
        [
            _doc("d1", "S", ["KU-RO", "KU-RO"]),  # twice in one document
            _doc("d2", "S", ["KU-RO"]),
        ],
        script_id="lineara",
    )
    counts = dict(c.query([FilterRow("word-prefix", "KU")], output="words").words)
    assert counts["KU-RO"] == 2  # documents d1, d2 — not the 3 token occurrences


# ── Document / Token accessors ───────────────────────────────────────────────────
def test_document_kind_accessors_partition_the_stream() -> None:
    """words/numerals/logograms select exactly their TokenKind, and len(doc) is the total
    token count. Hand-derived over a 4-token mixed stream."""
    doc = Document(
        id="d", script_id="lineara",
        tokens=[
            Token("W1", TokenKind.WORD, position=0),
            Token("5", TokenKind.NUMERAL, position=1),
            Token("GRA", TokenKind.LOGOGRAM, position=2),
            Token("W2", TokenKind.WORD, position=3),
        ],
        lines=[[0, 1], [2, 3]],
    )
    assert [t.text for t in doc.words] == ["W1", "W2"]
    assert [t.text for t in doc.numerals] == ["5"]
    assert [t.text for t in doc.logograms] == ["GRA"]
    assert len(doc) == 4


def test_document_line_tokens_regroups_by_physical_line() -> None:
    """line_tokens maps each line's index list back to its tokens, preserving the physical
    line structure. Lines [[0,1],[2,3]] -> [[W1,5],[GRA,W2]]."""
    doc = Document(
        id="d", script_id="lineara",
        tokens=[
            Token("W1", TokenKind.WORD, position=0),
            Token("5", TokenKind.NUMERAL, position=1),
            Token("GRA", TokenKind.LOGOGRAM, position=2),
            Token("W2", TokenKind.WORD, position=3),
        ],
        lines=[[0, 1], [2, 3]],
    )
    assert [[t.text for t in line] for line in doc.line_tokens] == [["W1", "5"], ["GRA", "W2"]]


# ── Sign / SignInventory accessors ───────────────────────────────────────────────
def test_sign_inventory_lookups_and_len() -> None:
    """by_label/by_glyph/by_codepoint resolve to the same Sign; misses return None; len is
    the sign count; iteration yields the signs in order."""
    s = Sign("KU", glyph="𐀓", codepoint=0x10053, phonetic="ku", script_id="lineara")
    inv = SignInventory([s], "lineara")
    assert inv.by_label("KU") is s
    assert inv.by_glyph("𐀓") is s
    assert inv.by_codepoint(0x10053) is s
    assert inv.by_label("ZZ") is None
    assert inv.by_glyph("?") is None
    assert inv.by_codepoint(999999) is None
    assert len(inv) == 1
    assert list(inv) == [s]


def test_bundled_greek_inventory_known_letter() -> None:
    """Against bundled gold: the Greek inventory resolves alpha by its glyph, an independently
    known fact (α is 'alpha'). Guards the accessor wiring on real data."""
    inv = aegean.load("greek").sign_inventory
    assert inv is not None
    assert inv.by_glyph("α").label == "alpha"


# ── Provenance.bibtex / apa / cite ───────────────────────────────────────────────
def test_provenance_cite_one_line_joins_url() -> None:
    """cite() is 'citation — url' when both present; just the citation otherwise."""
    assert PROV.cite() == "Editor, B. (2018). A Small Edition. — https://example.org/ed"
    assert Provenance(source="Only source").cite() == "Only source"


def test_provenance_bibtex_fields_parseable_and_correct() -> None:
    """A @misc entry with the expected key, a title from the citation, the year extracted from
    the citation text (2018), the url, and a note carrying the license. Braces balance and the
    field syntax 'k = {v}' parses for each emitted field."""
    bt = PROV.bibtex(key="ed18")
    assert bt.startswith("@misc{ed18,")
    assert "title = {Editor, B. (2018). A Small Edition.}" in bt
    assert "year = {2018}" in bt           # the only 4-digit year in the citation
    assert "url = {https://example.org/ed}" in bt
    assert "License: CC BY 4.0" in bt
    assert bt.count("{") == bt.count("}")  # balanced braces -> parseable
    # every field line matches the BibTeX 'key = {value}' shape
    field_lines = [ln.strip().rstrip(",") for ln in bt.splitlines()[1:-1]]
    assert field_lines and all(re.fullmatch(r"\w+ = \{.*\}", ln) for ln in field_lines)


def test_provenance_bibtex_omits_unknown_year_and_url() -> None:
    """No recoverable year and no url -> neither 'year' nor 'url' field is emitted; the title
    falls back to the source."""
    bt = Provenance(source="Field notes").bibtex()
    assert "year" not in bt and "url" not in bt
    assert "title = {Field notes}" in bt


def test_provenance_apa_line_and_nd_fallback() -> None:
    """APA: '<title>. (<year>). <url>'. With a recoverable year, that year is used; with none,
    '(n.d.)'. Notes (if any) trail in brackets."""
    assert PROV.apa() == "Editor, B. (2018). A Small Edition. (2018). https://example.org/ed"
    assert Provenance(source="Field notes").apa() == "Field notes. (n.d.)."
    with_note = Provenance(source="Src", notes=("subset: 1 of 2",))
    assert with_note.apa() == "Src. (n.d.). [subset: 1 of 2]"


# ── register_loader / read_corpus ────────────────────────────────────────────────
def test_register_loader_makes_corpus_loadable_by_id() -> None:
    """A registered loader is reachable via aegean.load(id) and returns an independent copy of the
    loader's corpus (isolated so a caller's mutation cannot corrupt a cached loader instance)."""
    c = Corpus.from_records([{"id": "R1", "text": "A-DU"}], script_id="myfind")
    register_loader("complete-core-test", lambda: c)
    loaded = aegean.load("complete-core-test")
    assert loaded is not c
    assert loaded.fingerprint() == c.fingerprint()
    assert [d.id for d in loaded] == [d.id for d in c]


def test_read_corpus_inline_json_and_registered_id() -> None:
    """read_corpus parses inline JSON (a string starting with '{') back to an equal corpus, and
    resolves a registered id to the loaded corpus."""
    c = Corpus.from_records([{"id": "Q1", "text": "KU-RO 5"}], script_id="lineara")
    rt = read_corpus(c.to_json(indent=None))
    assert [d.id for d in rt] == ["Q1"]
    assert rt.documents == c.documents

    register_loader("complete-core-read", lambda: c)
    assert [d.id for d in read_corpus("complete-core-read")] == ["Q1"]


def test_read_corpus_json_file(tmp_path) -> None:
    """read_corpus loads a .json file path via Corpus.from_json."""
    c = Corpus.from_records([{"id": "F1", "text": "A-DU"}], script_id="lineara")
    p = tmp_path / "saved.json"
    c.to_json(p)
    assert [d.id for d in read_corpus(str(p))] == ["F1"]


def test_read_corpus_unknown_spec_raises() -> None:
    """An unresolvable spec (not an id, work id, or readable file) raises CorpusNotFound, and a
    non-existent .json path raises with 'no such corpus file'."""
    with pytest.raises(CorpusNotFound, match="unknown corpus"):
        read_corpus("definitely-not-a-corpus-xyz")
    with pytest.raises(CorpusNotFound, match="no such corpus file"):
        read_corpus("/nonexistent/path/to/corpus.json")


# ── script registry: register / get_script / registered_scripts ──────────────────
def test_registered_scripts_includes_builtins_and_is_sorted() -> None:
    """Importing aegean registers all built-in scripts; the list is sorted and contains the
    five known ids."""
    ids = aegean.registered_scripts()
    assert ids == sorted(ids)
    assert {"cypriot", "cyprominoan", "greek", "lineara", "linearb"} <= set(ids)


def test_get_script_returns_plugin_and_unknown_raises() -> None:
    """get_script('lineara') returns a Script whose id matches and whose tokenizer classifies a
    known commodity logogram correctly; an unknown id raises KeyError."""
    la = aegean.get_script("lineara")
    assert la.id == "lineara"
    toks = la.tokenize("KU-RO 5 GRA")
    by_kind = {t.text: t.kind for t in toks}
    assert by_kind["KU-RO"] is TokenKind.WORD
    assert by_kind["5"] is TokenKind.NUMERAL
    assert by_kind["GRA"] is TokenKind.LOGOGRAM
    with pytest.raises(KeyError, match="no script"):
        aegean.get_script("no-such-script")


def test_register_custom_script_is_retrievable() -> None:
    """A custom Script subclass, once register()ed under its id, is returned by get_script with
    object identity."""
    from aegean.core import Script, register

    class _Dummy(Script):
        id = "complete-core-dummy"
        name = "Dummy"

        @property
        def sign_inventory(self) -> SignInventory:
            return SignInventory([], self.id)

        def tokenize(self, raw: str) -> list[Token]:
            return [Token(w, TokenKind.WORD, position=i) for i, w in enumerate(raw.split())]

    d = _Dummy()
    register(d)
    assert aegean.get_script("complete-core-dummy") is d
    assert d.id in aegean.registered_scripts()


# ── Greek backend toggles ─────────────────────────────────────────────────────────
# Each ``use_*`` activation needs a fetched/built index or model (network on first use), so the
# activation half is gated on the relevant cache already existing; the ``disable_*`` half is pure
# local state and is always tested. ``active()`` is the contract observed.


def test_disable_toggles_clear_active_state() -> None:
    """The disable_* toggles set their backend's active() to None — no network, pure local
    state. This is the always-true half of the toggle contract."""
    from aegean.greek import joint, lexicon, neural_lemmatizer, treebank

    joint.disable_neural_pipeline()
    assert joint.active() is None
    neural_lemmatizer.disable_neural_lemmatizer()
    assert neural_lemmatizer.active() is None
    treebank.disable_treebank()
    assert treebank.active() is None
    lexicon.disable_lsj()
    assert lexicon.active() is None


def test_use_treebank_activates_when_index_cached_then_disables() -> None:
    """Contract: use_treebank flips active() from None to a loaded lexicon, and disable_treebank
    flips it back. Gated on the AGDT index already being built in the cache (building it needs a
    network download), so we never fetch in a committed test."""
    from aegean.greek import treebank

    if not (treebank.cache_dir() / treebank._LEXICON_NAME).exists():
        pytest.skip("AGDT treebank index not cached; building it requires a network download")
    treebank.disable_treebank()
    assert treebank.active() is None
    lex = treebank.use_treebank(build=False)  # build=False: load only, never fetch
    assert treebank.active() is lex is not None
    treebank.disable_treebank()
    assert treebank.active() is None


def test_use_lsj_activates_when_index_cached_then_disables() -> None:
    """Contract: use_lsj flips active() from None to a loaded lexicon and disable_lsj reverts it.
    Gated on the LSJ index already being built in the cache (building it downloads ~270 MB), so
    no network in this committed test."""
    from aegean.greek import lexicon

    if not (lexicon.cache_dir() / lexicon._INDEX_NAME).exists():
        pytest.skip("LSJ index not cached; building it requires a ~270 MB network download")
    lexicon.disable_lsj()
    assert lexicon.active() is None
    lex = lexicon.use_lsj(build=False)  # build=False: load only, never fetch
    assert lexicon.active() is lex is not None
    lexicon.disable_lsj()
    assert lexicon.active() is None


def test_use_lexicon_unknown_id_raises_offline() -> None:
    """use_lexicon validates its id before any fetch, so an unknown lexicon raises KeyError with
    no network access — a meaningful offline contract test for the activation entry point."""
    from aegean.greek import lexicons

    with pytest.raises(KeyError, match="unknown lexicon"):
        lexicons.use_lexicon("definitely-not-a-lexicon")


def test_disable_lexicon_is_a_noop_for_inactive_id() -> None:
    """disable_lexicon on a lexicon that is not active is a harmless no-op (no error), and
    active_lexica reflects that lsj/dodson are off after disabling them."""
    from aegean.greek import koine, lexicon, lexicons

    lexicon.disable_lsj()
    koine.disable_dodson()
    lexicons.disable_lexicon("lsj")     # not active -> must not raise
    lexicons.disable_lexicon("dodson")  # not active -> must not raise
    assert "lsj" not in lexicons.active_lexica()
    assert "dodson" not in lexicons.active_lexica()


# The neural-pipeline *activation* contract (use_neural_pipeline flips joint.active() and pulls
# onnxruntime) is owned by test_joint.py / test_neural_lemmatizer.py, which order it after their
# import-cleanliness check. It is deliberately NOT re-tested here: importing onnxruntime would leak
# into sys.modules and break test_neural_lemmatizer::test_import_stays_clean. The always-offline
# disable half is covered in test_disable_toggles_clear_active_state above.
