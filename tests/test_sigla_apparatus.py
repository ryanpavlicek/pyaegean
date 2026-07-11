"""SigLA editorial-apparatus decoding (loader-side, offline).

The loader now decodes SigLA's transcription apparatus into `ReadingStatus`:
a doubtful reading (``?``), an epigraphic break/lacuna bracket (``[`` ``]``), or an
unresolved in-word sign (``*?``) reads UNCLEAR, with the marker kept in the token
text but dropped from its sign labels; the complex-sign composition notation
(``+`` ``|`` ``(`` ``)`` ``{`` ``}``) is preserved, not read as apparatus.

The loader-logic tests use a synthetic v2 fixture with ``fetch`` monkeypatched
(no network), mirroring ``tests/test_sigla.py`` and ``tests/test_damos.py``. One
extra test pins the corpus-wide before/after counts on the real fetched asset,
but skips cleanly when it is not cached (so CI, which has no cache, does not
fetch)."""

from __future__ import annotations

import json

import pytest

import aegean.data as data
from aegean.core.model import ReadingStatus
from aegean.scripts.lineara import sigla


def _v2_fixture(tmp_path, atts, doc_id="AP 1", extra_docs=()):
    """A synthetic SigLA v2 asset carrying ``atts`` on one document."""
    docs = [{"id": doc_id, "typology": "Tablet", "site": "S", "period": "LM I",
             "attestations": atts}]
    docs.extend(extra_docs)
    payload = {
        "_meta": {"version": 2, "cite": "Fake.", "source_sha256": "ab" * 32},
        "documents": docs,
        "signs": [],
    }
    p = tmp_path / "sigla-corpus.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p


# The representative apparatus vocabulary found in the real SigLA corpus.
_ATTS = [
    {"sign": "KA", "kind": "syllable", "word": 0},          # clean word
    {"sign": "U", "kind": "syllable", "word": 0},
    {"sign": "KU", "kind": "syllable", "word": 1},          # word with an unresolved gap
    {"sign": "", "kind": "blank", "word": 1},               # → *? in text, dropped from signs
    {"sign": "NI", "kind": "syllable", "word": 1},
    {"sign": "*16+[?]+*50", "kind": "logogram", "word": None},   # lost middle component
    {"sign": "]*80+*26", "kind": "logogram", "word": None},      # left-break bracket
    {"sign": "*302+*10", "kind": "logogram", "word": None},      # composition only (no apparatus)
    {"sign": "(*73?+*57?) | *26", "kind": "logogram", "word": None},  # doubtful components
    {"sign": "*412VAS+{E}", "kind": "logogram", "word": None},   # inscribed sign (composition)
    {"sign": "*414VAS+{?}", "kind": "logogram", "word": None},   # inscribed sign uncertain
    {"sign": "QA?", "kind": "syllable", "word": None},           # standalone doubtful syllable
    {"sign": "NE", "kind": "syllable", "word": None},            # standalone clean syllable
    {"sign": "", "kind": "fraction", "word": None},              # skipped
    {"sign": "", "kind": "blank", "word": None},                 # standalone blank → skipped
]


def _load(tmp_path, monkeypatch, atts=_ATTS, **kw):
    p = _v2_fixture(tmp_path, atts, **kw)
    monkeypatch.setattr(data, "fetch", lambda name, **k: p)
    return sigla.load_sigla()


def test_status_decoded_from_apparatus(tmp_path, monkeypatch):
    doc = _load(tmp_path, monkeypatch).get("AP 1")
    got = {t.text: t.status for t in doc.tokens}
    # clean word / composition-only logogram / clean syllable stay CERTAIN
    assert got["KA-U"] is ReadingStatus.CERTAIN
    assert got["*302+*10"] is ReadingStatus.CERTAIN
    assert got["*412VAS+{E}"] is ReadingStatus.CERTAIN     # braces = composition, not apparatus
    assert got["NE"] is ReadingStatus.CERTAIN
    # every apparatus-bearing token is UNCLEAR (SigLA yields no RESTORED/LOST)
    for text in ("KU-*?-NI", "*16+[?]+*50", "]*80+*26", "(*73?+*57?) | *26",
                 "*414VAS+{?}", "QA?"):
        assert got[text] is ReadingStatus.UNCLEAR, text
    assert not any(t.status in (ReadingStatus.RESTORED, ReadingStatus.LOST) for t in doc.tokens)


def test_markers_kept_in_text_dropped_from_signs(tmp_path, monkeypatch):
    doc = _load(tmp_path, monkeypatch).get("AP 1")
    by_text = {t.text: t for t in doc.tokens}
    # the marker stays in the TEXT (marks the position) …
    assert by_text["KU-*?-NI"].text == "KU-*?-NI"
    assert by_text["*16+[?]+*50"].text == "*16+[?]+*50"
    # … but never appears in the sign labels, which are the preserved reading only
    assert by_text["KU-*?-NI"].signs == ("KU", "NI")             # *? dropped
    assert by_text["*16+[?]+*50"].signs == ("*16+*50",)          # lost component + orphan '+' gone
    assert by_text["]*80+*26"].signs == ("*80+*26",)             # break bracket stripped
    assert by_text["(*73?+*57?) | *26"].signs == ("(*73+*57) | *26",)  # '?' off each component
    assert by_text["*414VAS+{?}"].signs == ("*414VAS",)         # emptied brace tidied
    assert by_text["QA?"].signs == ("QA",)
    # composition notation is untouched in the signs of a clean logogram
    assert by_text["*302+*10"].signs == ("*302+*10",)
    assert by_text["*412VAS+{E}"].signs == ("*412VAS+{E}",)
    # no apparatus character survives in ANY sign label anywhere in the corpus
    assert all(not any(m in s for m in "?[]") for t in doc.tokens for s in t.signs)


def test_raw_marked_form_preserved_in_annotations(tmp_path, monkeypatch):
    """A cleaned logogram keeps its raw marked composite in annotations['sigla']
    (nothing is lost), mirroring the Cypriot loader's annotations['leiden']."""
    doc = _load(tmp_path, monkeypatch).get("AP 1")
    by_text = {t.text: t for t in doc.tokens}
    assert by_text["*16+[?]+*50"].annotations.get("sigla") == "*16+[?]+*50"
    assert by_text["*414VAS+{?}"].annotations.get("sigla") == "*414VAS+{?}"
    # a logogram with no apparatus carries no such annotation
    assert "sigla" not in by_text["*302+*10"].annotations


def test_kinds_and_lines_unchanged(tmp_path, monkeypatch):
    """Status/sign decoding does not disturb token kinds, text, or word grouping
    (the 0.19.x word/logogram contract from test_sigla.py still holds)."""
    doc = _load(tmp_path, monkeypatch).get("AP 1")
    assert [(t.text, t.kind.name) for t in doc.tokens][:3] == [
        ("KA-U", "WORD"), ("KU-*?-NI", "WORD"), ("*16+[?]+*50", "LOGOGRAM")
    ]
    # fraction + standalone blank skipped; one line per emitted token
    # (2 words + 6 logograms + 2 standalone syllables)
    assert len(doc.lines) == len(doc.tokens) == 10


def test_clean_label_helper_edges():
    """The label cleaner removes only apparatus, tidies orphaned operators, and
    terminates on hostile operator runs (never loops, never leaks a marker)."""
    assert sigla._clean_label("KA") == "KA"                    # plain sign untouched
    assert sigla._clean_label("*302+*10") == "*302+*10"        # composition preserved
    assert sigla._clean_label("*16+[?]+*50") == "*16+*50"      # middle component gone
    assert sigla._clean_label("]*80+*26[") == "*80+*26"        # both break edges
    assert sigla._clean_label("[?]") == ""                     # entirely apparatus
    assert sigla._clean_label("*1+++*2") == "*1+*2"            # collapsed operator run
    assert sigla._clean_label("{[?]}") == ""                   # emptied group removed
    assert sigla._clean_label("((*1))") == "((*1))"            # balanced groups kept


def test_adversarial_all_apparatus_logogram(tmp_path, monkeypatch):
    """A pathological standalone logogram that is entirely apparatus degrades
    cleanly: UNCLEAR, empty signs, marker kept in text — no crash, no CERTAIN."""
    atts = [{"sign": "[?]", "kind": "logogram", "word": None},
            {"sign": "?", "kind": "logogram", "word": None}]
    doc = _load(tmp_path, monkeypatch, atts=atts).get("AP 1")
    assert [t.text for t in doc.tokens] == ["[?]", "?"]
    assert all(t.status is ReadingStatus.UNCLEAR for t in doc.tokens)
    assert all(t.signs == () for t in doc.tokens)


def test_adversarial_empty_and_marker_only_document(tmp_path, monkeypatch):
    """An empty document and a document of only skipped items load without error."""
    empty = {"id": "EMPTY", "typology": "", "site": "", "period": "", "attestations": []}
    only_skipped = [{"sign": "", "kind": "fraction", "word": None},
                    {"sign": "", "kind": "blank", "word": None}]
    c = _load(tmp_path, monkeypatch, atts=only_skipped, doc_id="SKIP", extra_docs=[empty])
    assert c.get("EMPTY").tokens == []
    assert c.get("SKIP").tokens == []


def test_composition_markers_are_not_apparatus(tmp_path, monkeypatch):
    """+ | ( ) { } alone never make a token UNCLEAR (they are decomposition notation)."""
    atts = [{"sign": s, "kind": "logogram", "word": None}
            for s in ("*302+*67", "*303 || D", "(*80+*26) || *13", "*412VAS+{E}")]
    doc = _load(tmp_path, monkeypatch, atts=atts).get("AP 1")
    assert all(t.status is ReadingStatus.CERTAIN for t in doc.tokens)
    assert doc.tokens[1].signs == ("*303 || D",)  # spacing preserved, label intact


def test_provenance_note_documents_the_apparatus(tmp_path, monkeypatch):
    prov = _load(tmp_path, monkeypatch).provenance
    assert "ReadingStatus" in (prov.notes[0] if prov.notes else "")
    assert "UNCLEAR" in prov.notes[0]


# ── the real fetched asset: pin the corpus-wide before/after (cache-gated) ──────
_SIGLA_CACHED = data.is_downloaded(data._REMOTE["sigla-corpus"], data.cache_dir())


@pytest.mark.skipif(not _SIGLA_CACHED, reason="sigla-corpus not cached (no network in CI)")
def test_real_corpus_status_counts():
    """On the real SigLA asset the loader now decodes 309 UNCLEAR tokens across
    205 documents (before this decoding every token defaulted to CERTAIN); the
    2,578-token, 781-document corpus is otherwise unchanged. Recorded so the
    decoded counts cannot drift silently where the asset is present."""
    import aegean

    c = aegean.load("sigla")
    counts = {s: 0 for s in ReadingStatus}
    docs_app = 0
    ntok = 0
    for d in c:
        app = False
        for t in d.tokens:
            ntok += 1
            counts[t.status] += 1
            if t.status is not ReadingStatus.CERTAIN:
                app = True
            assert not any(m in s for s in t.signs for m in "?[]")  # no marker leaks
        if app:
            docs_app += 1
    assert (len(c), ntok) == (781, 2578)
    assert counts[ReadingStatus.CERTAIN] == 2269
    assert counts[ReadingStatus.UNCLEAR] == 309
    assert counts[ReadingStatus.RESTORED] == 0 and counts[ReadingStatus.LOST] == 0
    assert docs_app == 205
    # every unclear word/logogram is exactly one whose text carries ? [ or ]
    assert all(
        (any(m in t.text for m in "?[]")) == (t.status is ReadingStatus.UNCLEAR)
        for d in c for t in d.tokens
    )
