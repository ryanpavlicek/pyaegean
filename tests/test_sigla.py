"""The OCaml Marshal reader behind the SigLA integration (offline: hand-built bytes)."""

from __future__ import annotations

import struct

import pytest

from aegean.scripts.lineara.sigla import (
    Block,
    MarshalError,
    parse_database_js,
    unmarshal,
)


def wrap(payload: bytes, num_objects: int) -> bytes:
    """A valid small-format Marshal envelope around hand-built opcodes."""
    return struct.pack(">IIIII", 0x8495A6BE, len(payload), num_objects, 0, 0) + payload


def test_small_int_and_small_block():
    # Block tag 0 size 2: [int 5, int 63]
    payload = bytes([0x80 | (2 << 4) | 0, 0x40 | 5, 0x40 | 63])
    v = unmarshal(wrap(payload, 1))
    assert isinstance(v, Block) and v.tag == 0 and v.fields == [5, 63]


def test_small_string_and_sharing():
    # Block(tag 0, size 2): ["ka", shared ref to "ka"]
    payload = bytes([0x80 | (2 << 4), 0x20 | 2]) + b"ka" + bytes([0x04, 1])
    v = unmarshal(wrap(payload, 2))  # the block + the string register
    assert v.fields == ["ka", "ka"]
    assert v.fields[0] is v.fields[1]  # genuinely shared


def test_boxed_ints_and_atom():
    # Block: [INT16 -300, atom block (size 0, not registered)]
    payload = bytes([0x80 | (2 << 4), 0x01]) + struct.pack(">h", -300) + bytes([0x80 | 0 | 1])
    v = unmarshal(wrap(payload, 1))
    assert v.fields[0] == -300
    assert isinstance(v.fields[1], Block) and v.fields[1].tag == 1 and v.fields[1].fields == []


def test_cycle_via_back_reference():
    # Block A(size 1) whose field is a shared ref to A itself (distance 1)
    payload = bytes([0x80 | (1 << 4), 0x04, 1])
    v = unmarshal(wrap(payload, 1))
    assert v.fields[0] is v


def test_header_checks():
    payload = bytes([0x40 | 1])
    with pytest.raises(MarshalError, match="magic"):
        unmarshal(b"\x00" * 20 + payload)
    with pytest.raises(MarshalError, match="objects"):
        unmarshal(wrap(payload, 7))  # an int registers nothing
    good = unmarshal(wrap(payload, 0))
    assert good == 1


def test_parse_database_js_two_escape_layers():
    # the on-disk form: a JS literal of a quoted OCaml literal with decimal escapes
    inner = wrap(bytes([0x20 | 2]) + b"ok", 1)
    ocaml = '"' + "".join(f"\\{b:03d}" for b in inner) + '"'
    js = ocaml.replace("\\", "\\\\")
    db = parse_database_js(f"/* X */\nvar x = '{js}';\n")
    assert db == {"x": "ok"}


def test_load_sigla_v1_asset_back_compat(tmp_path, monkeypatch):
    """A v1-shaped asset (no word/kind keys) still loads as the sign stream."""
    import json

    from aegean.core.model import TokenKind
    from aegean.scripts.lineara import sigla

    synthetic = {
        "_meta": {"cite": "Fake cite.", "source_sha256": "ab" * 32},  # no version → v1
        "documents": [
            {
                "id": "XX 1", "typology": "Tablet", "site": "Nowhere",
                "dimensions_cm": [1.0, 2.0, 0.5], "period": "LM I",
                "attestations": [
                    {"sign": "KA", "series": "AB", "number": 77, "raw_flags": [0]},
                    {"sign": "*301", "series": "A", "number": 301, "raw_flags": [1]},
                    {"sign": "", "series": "", "number": None, "raw_flags": [9]},
                ],
            }
        ],
        "signs": [],
    }
    f = tmp_path / "sigla-corpus.json"
    f.write_text(json.dumps(synthetic), encoding="utf-8")
    import aegean.data

    monkeypatch.setattr(aegean.data, "fetch", lambda name, **k: f)
    c = sigla.load_sigla()
    doc = c.get("XX 1")
    assert [t.text for t in doc.tokens] == ["KA", "*301"]  # blank skipped
    assert all(t.kind is TokenKind.UNKNOWN for t in doc.tokens)  # v1 sign-level
    assert c.provenance.data_version.startswith("sigla-corpus-v1@abab")


def test_load_sigla_v2_words_and_logograms(tmp_path, monkeypatch):
    """v2: attestations carry word/kind → multi-sign WORD + LOGOGRAM tokens."""
    import json

    from aegean.scripts.lineara import sigla

    # KA-U-DE-TA  VIN(logogram)  KU-*?-NI (internal gap kept as *?)
    atts = [
        {"sign": "KA", "kind": "syllable", "word": 0},
        {"sign": "U", "kind": "syllable", "word": 0},
        {"sign": "DE", "kind": "syllable", "word": 0},
        {"sign": "TA", "kind": "syllable", "word": 0},
        {"sign": "VIN", "kind": "logogram", "word": None},
        {"sign": "KU", "kind": "syllable", "word": 1},
        {"sign": "", "kind": "blank", "word": 1},          # unresolved internal sign
        {"sign": "NI", "kind": "syllable", "word": 1},
        {"sign": "", "kind": "fraction", "word": None},    # no value → skipped
    ]
    synthetic = {
        "_meta": {"version": 2, "cite": "Fake.", "source_sha256": "cd" * 32},
        "documents": [{"id": "XX 1", "typology": "Tablet", "site": "S",
                       "period": "LM I", "attestations": atts}],
        "signs": [],
    }
    f = tmp_path / "sigla-corpus.json"
    f.write_text(json.dumps(synthetic), encoding="utf-8")
    import aegean.data

    monkeypatch.setattr(aegean.data, "fetch", lambda name, **k: f)
    doc = sigla.load_sigla().get("XX 1")
    by_kind = [(t.text, t.kind.name) for t in doc.tokens]
    assert by_kind == [
        ("KA-U-DE-TA", "WORD"),
        ("VIN", "LOGOGRAM"),
        ("KU-*?-NI", "WORD"),   # internal gap preserved, word contiguous
    ]
    assert doc.tokens[0].signs == ("KA", "U", "DE", "TA")
    # one line per word/standalone item
    assert len(doc.lines) == 3
    assert sigla.load_sigla().provenance.data_version.startswith("sigla-corpus-v2@cdcd")
