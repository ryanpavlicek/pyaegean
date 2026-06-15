"""The headline data-layer contract for Linear A."""

import hashlib
import json

import aegean
from aegean.core.model import ReadingStatus, TokenKind
from aegean.data import load_bundled_json

# The upstream's erased/illegible-sign placeholder (see lineara/loader.py).
_ERASED = "\U0001076B"


def test_recovered_apparatus_counts():
    """The apparatus signal the bundled data carries, now interpreted. These
    counts pin the recovery — change them only with a corresponding data/loader
    change."""
    c = aegean.load("lineara")
    lost = [t for d in c for t in d.tokens if t.status is ReadingStatus.LOST]
    unclear = [t for d in c for t in d.tokens if t.status is ReadingStatus.UNCLEAR]
    assert len(lost) == 552      # standalone erased-sign runs → text not preserved
    assert len(unclear) == 120   # damaged-at-break words + bracketed uncertain readings
    assert all(t.kind is TokenKind.UNKNOWN for t in lost)
    docs_with_apparatus = sum(
        1 for d in c if any(t.status is not ReadingStatus.CERTAIN for t in d.tokens)
    )
    assert docs_with_apparatus == 366


def test_apparatus_token_semantics():
    c = aegean.load("lineara")
    # a bracketed uncertain ligature reads UNCLEAR but keeps its kind
    vir = next(t for t in c.get("HT7a").tokens if "[" in t.text)
    assert vir.text == "VIR+[?]"
    assert vir.kind is TokenKind.LOGOGRAM and vir.status is ReadingStatus.UNCLEAR
    # a standalone erased-sign token is LOST
    erased = next(t for d in c for t in d.tokens if t.text == _ERASED)
    assert erased.status is ReadingStatus.LOST
    # a word damaged at a break is UNCLEAR, and the marker is not a sign label
    damaged = next(
        t for d in c for t in d.tokens
        if _ERASED in t.text and t.text.replace(_ERASED, "")
    )
    assert damaged.status is ReadingStatus.UNCLEAR
    assert all(_ERASED not in s for s in damaged.signs)
    # a tablet ruling dash is a separator, not an unknown word
    dash = next(t for d in c for t in d.tokens if t.text == "—")
    assert dash.kind is TokenKind.SEPARATOR and dash.status is ReadingStatus.CERTAIN


def test_load_count_and_inventory():
    c = aegean.load("lineara")
    assert len(c) == 1721
    assert c.script_id == "lineara"
    inv = c.sign_inventory
    assert inv is not None
    # The inventory covers the full Unicode Linear A repertoire (~340 signs); 84 of them are
    # transliteration-aligned (source != "ucd"), of which 47 carry an assigned sound value;
    # the rest are UCD-derived.
    assert len(inv) > 300
    assert sum(1 for s in inv if s.attrs.get("source") != "ucd") == 84
    assert all(s.phonetic is None for s in inv if s.attrs.get("source") == "ucd")


def test_filter_and_word_frequencies():
    c = aegean.load("lineara")
    ht = c.filter(site="Haghia Triada")
    assert 0 < len(ht) < len(c)
    assert all(d.meta.site == "Haghia Triada" for d in ht)

    freqs = c.word_frequencies()
    assert freqs
    assert freqs[0][1] >= freqs[-1][1]  # sorted descending
    assert freqs[0][1] > 1              # the top word recurs


def test_registered_and_provenance_and_export():
    assert "lineara" in aegean.registered_scripts()
    c = aegean.load("lineara")
    assert "GORILA" in c.provenance.source
    assert c.provenance.cite()  # non-empty formatted citation

    d = c.to_dict()
    assert d["_meta"]["documentCount"] == 1721
    assert d["_meta"]["scriptId"] == "lineara"
    assert len(d["documents"]) == 1721


def test_tokenize_classifies_kinds():
    la = aegean.get_script("lineara")
    toks = la.tokenize("KU-RO 5 GRA")
    kinds = [t.kind.value for t in toks]
    assert kinds == ["word", "numeral", "logogram"]
    assert toks[0].signs == ("KU", "RO")


def test_manifest_parity_with_workbench():
    """The bundled corpus matches the manifest stamped by the linearaworkbench
    corpus build: same record count, same sha256 over the canonical projection
    of the shared fields. The workbench verifies the identical checksum on its
    side, so the two projects' copies of this corpus cannot drift apart
    silently — whichever side drifts fails its own CI."""
    manifest = load_bundled_json("lineara", "manifest.json")
    recs = load_bundled_json("lineara", "inscriptions.json")
    assert len(recs) == manifest["inscriptionCount"]
    projection = [{k: r.get(k) for k in manifest["parityFields"]} for r in recs]
    canonical = json.dumps(projection, ensure_ascii=False, separators=(",", ":"))
    sha = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    assert sha == manifest["paritySha256"]


def test_image_references_drive_has_image():
    """Every bundled inscription carries its facsimile/photograph references
    (paths only, never binaries), so the `has-image` query field behaves
    exactly as it does in the workbench over the same corpus."""
    from aegean.analysis import FilterRow

    c = aegean.load("lineara")
    assert all(d.meta.images for d in c)
    assert all(isinstance(p, str) and p for d in c for p in d.meta.images)
    results = c.query([FilterRow("has-image", True)])
    assert len(results.inscriptions) == len(c)
