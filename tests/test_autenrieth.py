"""Tests for the Autenrieth Homeric-dictionary backend.

Covers the build (``scripts/build_autenrieth_index.py``): Beta Code → Unicode with the
digamma / vowel-length / homograph-digit conventions, the ``{lemma: {"hw","def"}}`` index
shape, and homograph merging; and the registry wiring in ``aegean.greek.lexicons``: the
hosted registration, loading a present index, the graceful not-hosted error, and a
corrupt index file.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from aegean import greek
from aegean.data import DataNotAvailableError
from aegean.greek import lexicons as lexmod
from aegean.greek.lexindex import IndexLexicon, load_index

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import build_autenrieth_index as bx  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures" / "autenrieth" / "sample.xml"
INDEX_NAME = "autenrieth-index.json.gz"


@pytest.fixture(autouse=True)
def _reset_active():
    """Never let a use_lexicon in one test leak an active Autenrieth into the next."""
    yield
    lexmod._ACTIVE.pop("autenrieth", None)


def _fixture_index() -> dict[str, dict[str, str]]:
    return bx.index_from_tei(FIXTURE)


# ── Beta Code / headword-convention normalization ────────────────────────────

def test_beta_to_unicode_digamma_and_length_marks():
    # Perseus writes the Homeric digamma as ``v`` / ``*v`` (the project's 24-letter
    # converter does not); the build maps it to ϝ / Ϝ.
    assert bx.beta_to_unicode("va/nac") == "ϝάναξ"
    assert bx.beta_to_unicode("*ve/rgon") == "Ϝέργον"
    # Macron ``_`` and breve ``^`` (vowel-quantity notation) are dropped.
    assert bx.beta_to_unicode("a_") == "α"
    assert bx.beta_to_unicode("boulu_to/nde") == "βουλυτόνδε"
    assert bx.beta_to_unicode("") == ""


@pytest.mark.parametrize(
    ("beta_key", "lemma", "hw"),
    [
        ("mh=nis", "μῆνις", "μῆνις"),          # Iliad's first word
        ("a)ei/dw", "ἀείδω", "ἀείδω"),          # "sing", Il. 1.1
        ("a)/nac", "ἄναξ", "ἄναξ"),             # digamma-initial: headword is the bare form
        ("h)e/lios", "ἠέλιος", "ἠέλιος"),       # epic-only form of ἥλιος
        ("*)axaioi/", "ἀχαιοί", "Ἀχαιοί"),      # capital preserved in hw, folded in the key
        ("qea/", "θεά", "θεά"),
        ("krh/demnon", "κρήδεμνον", "κρήδεμνον"),
        ("e)/rgon", "ἔργον", "ἔργον"),          # digamma survives in the body (ϝέργον)
    ],
)
def test_headword_normalization(beta_key, lemma, hw):
    assert bx.lemma_key(beta_key) == lemma
    assert bx.headword(beta_key) == hw


def test_homograph_digit_stripped():
    # A trailing Perseus homograph digit is dropped so the lemma is the bare headword;
    # ``s2`` is a homograph marker here, not a sigma variant, and the accent stays right.
    assert bx.lemma_key("ai)no/s2") == "αἰνός"
    assert bx.lemma_key("a)i/w1") == bx.lemma_key("a)i/w2") == "ἀίω"


# ── index shape / content ────────────────────────────────────────────────────

def test_index_shape_and_content():
    idx = _fixture_index()
    # same {lemma: {"hw", "def"}} shape as the sibling lexica
    assert all(set(rec) == {"hw", "def"} for rec in idx.values())
    assert {"μῆνις", "ἀείδω", "ἄναξ", "ἠέλιος", "ἀχαιοί", "θεά", "κρήδεμνον", "ἔργον"} <= set(idx)
    assert "wrath" in idx["μῆνις"]["def"]
    assert idx["ἀχαιοί"]["hw"] == "Ἀχαιοί"  # proper-noun capital kept in the display headword


def test_digamma_only_in_body_not_headword():
    idx = _fixture_index()
    # ἄναξ is reachable under the bare vowel, NOT under a ϝ-initial lemma...
    assert "ϝάναξ" not in idx
    # ...but the etymological digamma is preserved where Autenrieth prints it (the body).
    assert "ϝάναξ" in idx["ἄναξ"]["def"]
    assert "ϝέργον" in idx["ἔργον"]["def"]


def test_length_marks_dropped_in_body():
    idx = _fixture_index()
    body = idx["ἠέλιος"]["def"]
    assert "_" not in body and "βουλυτόνδε" in body


def test_entry_without_key_skipped():
    idx = _fixture_index()
    assert "ἄκεψ" not in idx and all("skipped" not in rec["def"] for rec in idx.values())


def test_homographs_merged_not_lost():
    idx = _fixture_index()
    # a)i/w1 (hear) and a)i/w2 (breathe out) collapse to one lemma; both senses survive.
    body = idx["ἀίω"]["def"]
    assert " | " in body
    assert "hear" in body and "breathe out" in body


# ── round-trip through the shared index machinery ────────────────────────────

def test_index_roundtrip_and_serves(tmp_path):
    idx = _fixture_index()
    out = tmp_path / INDEX_NAME
    bx.write_index_deterministic(out, idx)
    assert load_index(out) == idx  # gzip round-trip is lossless

    lex = IndexLexicon(lexmod._AUTENRIETH_INFO, load_index(out))
    e = lex.lookup("μῆνις")
    assert e is not None and e.lexicon == "autenrieth" and "wrath" in e.body
    assert lex.gloss("θεά").startswith("θεά:")
    # lemmatize-on-miss: an inflected form resolves to its headword
    assert lex.lookup("μῆνιν").headword == "μῆνις"


def test_deterministic_build_is_reproducible(tmp_path):
    idx = _fixture_index()
    a, b = tmp_path / "a.json.gz", tmp_path / "b.json.gz"
    bx.write_index_deterministic(a, idx)
    bx.write_index_deterministic(b, idx)
    assert a.read_bytes() == b.read_bytes()  # fixed mtime → pinnable sha256


# ── registry wiring ──────────────────────────────────────────────────────────

def test_registered_hosted_homeric():
    infos = {i.id: i for i in greek.lexica()}
    a = infos["autenrieth"]
    assert a.hosted is True and a.scope == "Homeric"
    assert "autenrieth" in lexmod._DEFAULT_ORDER


def test_use_lexicon_loads_present_index(tmp_path, monkeypatch):
    out = tmp_path / INDEX_NAME
    bx.write_index_deterministic(out, _fixture_index())
    monkeypatch.setattr("aegean.data.cache_dir", lambda: tmp_path)

    lex = greek.use_lexicon("autenrieth")
    assert lex.info.id == "autenrieth"
    assert "wrath" in (greek.gloss("μῆνις", dictionary="autenrieth") or "")
    assert "autenrieth" in greek.active_lexica()


def test_not_hosted_raises_clean_error(tmp_path, monkeypatch):
    # empty cache + a prebuilt fetch that reports "not hosted" → a clean, typed error
    monkeypatch.setattr("aegean.data.cache_dir", lambda: tmp_path)
    monkeypatch.setattr("aegean.data.fetch_prebuilt", lambda *a, **k: False)
    with pytest.raises(DataNotAvailableError, match="not hosted yet"):
        greek.use_lexicon("autenrieth")


def test_corrupt_index_file_errors(tmp_path, monkeypatch):
    # adversarial: a truncated / non-gzip index must fail loudly, never serve garbage
    (tmp_path / INDEX_NAME).write_bytes(b"this is not a gzip file")
    monkeypatch.setattr("aegean.data.cache_dir", lambda: tmp_path)
    with pytest.raises((OSError, ValueError)):
        greek.use_lexicon("autenrieth")
