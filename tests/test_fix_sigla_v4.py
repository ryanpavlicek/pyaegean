"""SigLA v4 refresh: the upstream database.js now serves 802 documents (21 new
vs the v3 781; THE 7-12, KH 101-105, GO 2a/2b, KN 49/54, KE 6a/6b, KH 93a/93b,
PH 54 among them), rebuilt with the current build script (homophone subscripts
included). The rebuild is data-only: the loader logic and the v2 JSON schema are
unchanged, so the carried-over 781 documents are byte-identical except a single
upstream word re-division on PE 2 (``TO-*49-RE`` → ``TO-*49`` + ``RE``).

The offline tests pin the loader behaviour the new documents exercise (the
standalone-logogram homograph, complex-sign apparatus, plain syllable words)
with synthetic v2 fixtures, mirroring ``tests/test_sigla_apparatus.py``. The
cache-gated tests pin the v4 corpus-wide counts and a spread of new-document
readings on the real fetched asset, and skip cleanly when it is not cached (CI,
or a machine still holding the v3 asset)."""

from __future__ import annotations

import json

import pytest

import aegean.data as data
from aegean.core.model import ReadingStatus, TokenKind
from aegean.scripts.lineara import sigla


def _load_synthetic(tmp_path, monkeypatch, atts, doc_id="THE 8"):
    payload = {
        "_meta": {"version": 2, "cite": "Fake.", "source_sha256": "cc" * 32},
        "documents": [{"id": doc_id, "typology": "Tablet", "site": "Thera",
                       "period": "LM IA", "attestations": atts}],
        "signs": [],
    }
    p = tmp_path / "sigla-corpus.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(data, "fetch", lambda name, **k: p)
    return sigla.load_sigla()


# ── the loader reads the shapes the 21 new documents introduce ────────────────


def test_the8_complex_signs_read_ro_plus_starred(tmp_path, monkeypatch):
    """THE 8 = a plain syllable then two Linear-A-only complex signs, one of which
    carries a lost component ([?]) → UNCLEAR, marker kept in text, dropped from
    signs (RO stays a clean CERTAIN standalone syllable)."""
    atts = [
        {"sign": "RO", "kind": "syllable", "word": None},
        {"sign": "*80+*26", "kind": "logogram", "word": None},
        {"sign": "*51+[?]", "kind": "logogram", "word": None},
    ]
    doc = _load_synthetic(tmp_path, monkeypatch, atts).get("THE 8")
    by_text = {t.text: t for t in doc.tokens}
    assert [t.text for t in doc.tokens] == ["RO", "*80+*26", "*51+[?]"]
    assert by_text["RO"].status is ReadingStatus.CERTAIN
    assert by_text["*80+*26"].status is ReadingStatus.CERTAIN      # composition only
    assert by_text["*51+[?]"].status is ReadingStatus.UNCLEAR      # lost component
    assert by_text["*51+[?]"].signs == ("*51",)                    # [?] + orphan '+' gone
    assert not any(m in s for t in doc.tokens for s in t.signs for m in "?[]")


def test_the7a_standalone_homograph_reads_as_logogram(tmp_path, monkeypatch):
    """THE 7a's occurrence carries both a syllabogram value (AB21 = qi) and a
    logogram name (OVIS); a STANDALONE such sign reads as the OVIS ideogram, not
    the syllable (the build's documented word-internal/standalone homograph
    rule)."""
    atts = [{"sign": "OVIS", "kind": "logogram", "word": None}]
    doc = _load_synthetic(tmp_path, monkeypatch, atts, doc_id="THE 7a").get("THE 7a")
    assert [t.text for t in doc.tokens] == ["OVIS"]
    assert doc.tokens[0].kind is TokenKind.LOGOGRAM
    assert doc.tokens[0].status is ReadingStatus.CERTAIN


def test_ph54_words_i_sa_ri_ke_and_du_ti(tmp_path, monkeypatch):
    """PH 54 = the well-attested word I-SA-RI-KE plus DU-TI (two syllabic words)."""
    atts = [
        {"sign": "I", "kind": "syllable", "word": 0},
        {"sign": "SA", "kind": "syllable", "word": 0},
        {"sign": "RI", "kind": "syllable", "word": 0},
        {"sign": "KE", "kind": "syllable", "word": 0},
        {"sign": "DU", "kind": "syllable", "word": 1},
        {"sign": "TI", "kind": "syllable", "word": 1},
    ]
    doc = _load_synthetic(tmp_path, monkeypatch, atts, doc_id="PH 54").get("PH 54")
    assert [t.text for t in doc.tokens] == ["I-SA-RI-KE", "DU-TI"]
    assert doc.tokens[0].signs == ("I", "SA", "RI", "KE")
    assert all(t.status is ReadingStatus.CERTAIN for t in doc.tokens)


# ── the real fetched v4 asset: pin the corpus-wide counts and new readings ─────

_SIGLA_CACHED = data.is_downloaded(data._REMOTE["sigla-corpus"], data.cache_dir())

_NEW_IN_V4 = {
    "GO 2a", "GO 2b", "KE 6a", "KE 6b", "KH 93a", "KH 93b",
    "KH 101", "KH 102", "KH 103", "KH 104", "KH 105", "KN 49", "KN 54",
    "PH 54", "THE 7a", "THE 7b", "THE 8", "THE 9", "THE 10", "THE 11", "THE 12",
}


def _is_v4(c) -> bool:
    """True only when the cached asset is the v4 refresh (has the 21 new docs)."""
    return len(c) == 802 and _NEW_IN_V4 <= {d.id for d in c}


@pytest.mark.skipif(not _SIGLA_CACHED, reason="sigla-corpus not cached (no network in CI)")
def test_v4_corpus_wide_counts():
    """The v4 asset is 802 documents / 2,616 tokens / 1,895 WORD tokens, with the
    apparatus decoding yielding 2,296 CERTAIN, 320 UNCLEAR (across 215 documents),
    and no RESTORED/LOST. Skips on a pre-v4 cached asset so it never fails backward."""
    import aegean

    c = aegean.load("sigla")
    if not _is_v4(c):
        pytest.skip("cached sigla asset predates the v4 refresh")
    counts = {s: 0 for s in ReadingStatus}
    docs_app = ntok = nwords = 0
    for d in c:
        app = False
        nwords += len(d.words)
        for t in d.tokens:
            ntok += 1
            counts[t.status] += 1
            if t.status is not ReadingStatus.CERTAIN:
                app = True
            assert not any(m in s for s in t.signs for m in "?[]")
        if app:
            docs_app += 1
    assert (len(c), ntok, nwords) == (802, 2616, 1895)
    assert counts[ReadingStatus.CERTAIN] == 2296
    assert counts[ReadingStatus.UNCLEAR] == 320
    assert counts[ReadingStatus.RESTORED] == 0 and counts[ReadingStatus.LOST] == 0
    assert docs_app == 215


@pytest.mark.skipif(not _SIGLA_CACHED, reason="sigla-corpus not cached (no network in CI)")
def test_v4_new_documents_present_and_read():
    """All 21 new documents load, none of the v3 781 were dropped, and a spread of
    new readings (THE 8 / THE 9 / KH 105 / PH 54) decode as expected."""
    import aegean

    c = aegean.load("sigla")
    if not _is_v4(c):
        pytest.skip("cached sigla asset predates the v4 refresh")
    by_id = {d.id: d for d in c}
    assert _NEW_IN_V4 <= set(by_id)

    def signs(doc_id):
        return [s for t in by_id[doc_id].tokens for s in t.signs]

    assert [t.text for t in by_id["THE 9"].tokens] == ["TE-MU-SA-SE"]
    assert "RO" in signs("THE 8")                       # RO + Linear-A-only complex signs
    # KH 105: the lost DE-position (GORILA's DE-KI-TI) reads as an in-word *? gap
    assert [t.text for t in by_id["KH 105"].tokens] == ["*?-KI-TI"]
    assert "I-SA-RI-KE" in [t.text for t in by_id["PH 54"].tokens]


@pytest.mark.skipif(not _SIGLA_CACHED, reason="sigla-corpus not cached (no network in CI)")
def test_v4_carried_over_pe2_word_redivision():
    """The one carried-over document whose reading changed upstream: PE 2's final
    word ``TO-*49-RE`` (v3) is re-divided into ``TO-*49`` + ``RE`` (v4)."""
    import aegean

    c = aegean.load("sigla")
    if not _is_v4(c):
        pytest.skip("cached sigla asset predates the v4 refresh")
    texts = [t.text for t in c.get("PE 2").tokens]
    assert texts[-2:] == ["TO-*49", "RE"]
    assert "TO-*49-RE" not in texts
