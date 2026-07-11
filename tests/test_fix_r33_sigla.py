"""R33: SigLA homophone syllabograms keep their (base, option) subscript.

The SigLA build decoded field[2]'s ``(base, option)`` transliteration pair with
``_first_string``, which returned only the base and dropped the homophone index,
collapsing the distinct signs AB76 RA₂ / AB29 PU₂ / AB66 TA₂ onto plain RA / PU /
TA. AB76 = ``('ra', Some '2')`` must read ``ra₂`` (Unicode subscript, matching
the bundled GORILA lineara convention), while AB60 = ``('ra', None)`` stays plain
``ra``. These pin the build extractor (known-answer, hand-built Marshal blocks),
the loader end-to-end (synthetic v2 asset), the distinctness of the emitted label
in the shared inventory, and the real fetched asset when it carries the fix.
"""

from __future__ import annotations

import importlib.util
import json
from collections import Counter
from pathlib import Path

import pytest

import aegean.data as data
from aegean.core.model import ReadingStatus, TokenKind
from aegean.scripts.lineara import sigla
from aegean.scripts.lineara.sigla import Block


def _build_module():
    """Load scripts/build_sigla_corpus.py by path (scripts/ is not a package)."""
    path = Path(__file__).resolve().parents[1] / "scripts" / "build_sigla_corpus.py"
    spec = importlib.util.spec_from_file_location("_build_sigla_corpus_r33", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _field2(base: str, option: str | None) -> Block:
    """Reproduce SigLA's field[2] = ``Some (base, option)`` heap shape:
    ``B0[ B0[base, option] ]`` where option is ``0`` (None) or ``B0[digit]``."""
    opt: object = 0 if option is None else Block(0, [option])
    return Block(0, [Block(0, [base, opt])])


def _sign_record(series: str, number: int, base: str, option: str | None, ref: str) -> Block:
    """A minimal 9-field sign record (fields[0] series, [2] transliteration pair,
    [3] representative drawing ref) as `_triple`/`_find_sign_record` read it."""
    fields: list[object] = [series, number, _field2(base, option), ref, 0, 0, 0, 0, 0]
    return Block(0, fields)


# ── the build extractor: (base, option) → base + subscript option ────────────


def test_transliteration_appends_subscript_option():
    m = _build_module()
    # AB76 ('ra', Some '2') → ra₂ ; AB60 ('ra', None) → ra (no index)
    assert m._transliteration(_field2("ra", "2")) == "ra₂"
    assert m._transliteration(_field2("pu", "2")) == "pu₂"
    assert m._transliteration(_field2("ta", "2")) == "ta₂"
    assert m._transliteration(_field2("ra", None)) == "ra"
    assert m._transliteration(_field2("pu", None)) == "pu"
    assert m._transliteration(_field2("ta", None)) == "ta"


def test_subscript_is_unicode_not_ascii():
    m = _build_module()
    ra2 = m._transliteration(_field2("ra", "2"))
    assert ra2 == "ra₂"          # U+2082 SUBSCRIPT TWO
    assert ra2 != "ra2"               # not the ASCII digit
    assert ord(ra2[-1]) == 0x2082
    # matches exactly how the bundled GORILA lineara corpus writes the label
    assert ra2.upper() == "RA₂"


def test_option_string_none_vs_some():
    m = _build_module()
    assert m._option_string(0) == ""                       # OCaml None
    assert m._option_string(Block(0, ["2"])) == "2"        # OCaml Some '2'


def test_triple_keeps_homophone_index_but_ref_is_plain():
    m = _build_module()
    rec_ra2 = _sign_record("AB", 76, "ra", "2", "KH 5/5")
    rec_ra = _sign_record("AB", 60, "ra", None, "HT 1/1")
    assert m._triple(rec_ra2) == ("AB", "ra₂", "KH 5/5")
    assert m._triple(rec_ra) == ("AB", "ra", "HT 1/1")
    # display uppercases the transliteration, *NNN untouched for A-signs
    assert m._display("AB", 76, "ra₂") == "RA₂"
    assert m._display("A", 301, "") == "*301"


# ── the loader: RA₂ flows through as a distinct, CERTAIN sign ─────────────────


def _load_synthetic(tmp_path, monkeypatch, atts):
    payload = {
        "_meta": {"version": 2, "cite": "Fake.", "source_sha256": "ab" * 32},
        "documents": [{"id": "HT 1", "typology": "Tablet", "site": "S",
                       "period": "LM I", "attestations": atts}],
        "signs": [],
    }
    p = tmp_path / "sigla-corpus.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(data, "fetch", lambda name, **k: p)
    return sigla.load_sigla()


def test_loader_reads_qe_ra2_u(tmp_path, monkeypatch):
    atts = [
        {"sign": "QE", "kind": "syllable", "word": 0},
        {"sign": "RA₂", "kind": "syllable", "word": 0},
        {"sign": "U", "kind": "syllable", "word": 0},
    ]
    doc = _load_synthetic(tmp_path, monkeypatch, atts).get("HT 1")
    assert [t.text for t in doc.tokens] == ["QE-RA₂-U"]
    assert doc.tokens[0].signs == ("QE", "RA₂", "U")
    assert doc.tokens[0].kind is TokenKind.WORD
    # the homophone carries no editorial apparatus → the word stays CERTAIN
    assert doc.tokens[0].status is ReadingStatus.CERTAIN


def test_loader_keeps_ra2_distinct_from_ra(tmp_path, monkeypatch):
    atts = [
        {"sign": "SA", "kind": "syllable", "word": 0},
        {"sign": "RA₂", "kind": "syllable", "word": 0},   # SA-RA₂
        {"sign": "SA", "kind": "syllable", "word": 1},
        {"sign": "RA", "kind": "syllable", "word": 1},         # SA-RA
    ]
    doc = _load_synthetic(tmp_path, monkeypatch, atts).get("HT 1")
    texts = [t.text for t in doc.tokens]
    assert texts == ["SA-RA₂", "SA-RA"]
    assert doc.tokens[0].signs == ("SA", "RA₂")
    assert doc.tokens[1].signs == ("SA", "RA")
    assert doc.tokens[0].signs != doc.tokens[1].signs


def test_emitted_label_resolves_as_a_distinct_inventory_sign():
    """The RA₂/PU₂/TA₂ labels the corpus now emits are real, distinct signs in the
    shared Linear A inventory (so word-contains-sign queries keep working), never
    aliases of plain RA/PU/TA."""
    from aegean.scripts.lineara.inventory import linear_a_inventory

    inv = linear_a_inventory()
    for sub, plain in (("RA₂", "RA"), ("PU₂", "PU"), ("TA₂", "TA")):
        assert inv.by_label(sub) is not None, sub
        assert inv.by_label(sub) is not inv.by_label(plain), sub


# ── the real fetched asset: pin the homophone tally when the fix is present ──


_SIGLA_CACHED = data.is_downloaded(data._REMOTE["sigla-corpus"], data.cache_dir())


@pytest.mark.skipif(not _SIGLA_CACHED, reason="sigla-corpus not cached (no network in CI)")
def test_real_asset_homophone_counts_when_present():
    """On a fetched asset that carries the fix the homophone syllabograms tally
    RA₂ 43 / PU₂ 7 / TA₂ 14 and HT 1 reads QE-RA₂-U, while the corpus size stays
    781 documents / 2,578 tokens (the apparatus decoding is untouched). Skips on a
    cached asset that predates the fix (RA₂ absent), so it never fails backward."""
    import aegean

    c = aegean.load("sigla")
    cnt: Counter[str] = Counter()
    for d in c:
        for t in d.tokens:
            for s in t.signs:
                if s in ("RA₂", "PU₂", "TA₂"):
                    cnt[s] += 1
    if sum(cnt.values()) == 0:
        pytest.skip("cached sigla asset predates the homophone fix")
    assert cnt["RA₂"] == 43
    assert cnt["PU₂"] == 7
    assert cnt["TA₂"] == 14
    assert c.get("HT 1").tokens[0].text == "QE-RA₂-U"
    ntok = sum(len(d.tokens) for d in c)
    assert (len(c), ntok) == (781, 2578)
    # no plain-RA sign leaks a subscript, and no marker leaks anywhere
    assert not any(m in s for d in c for t in d.tokens for s in t.signs for m in "?[]")
