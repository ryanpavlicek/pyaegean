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


def test_load_sigla_builds_a_corpus(tmp_path, monkeypatch):
    """Offline: a synthetic dataset file in the release-asset schema (no SigLA data)."""
    import json

    from aegean.core.model import TokenKind
    from aegean.scripts.lineara import sigla

    synthetic = {
        "_meta": {"cite": "Fake cite.", "source_sha256": "ab" * 32},
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
    assert len(c) == 1
    doc = c.get("XX 1")
    assert [t.text for t in doc.tokens] == ["KA", "*301"]  # the blank attestation is skipped
    assert all(t.kind is TokenKind.UNKNOWN for t in doc.tokens)  # sign-level granularity
    assert doc.meta.site == "Nowhere" and "1×2×0.5 cm" in doc.meta.name
    assert c.provenance.license.startswith("CC BY-NC-SA")
    assert c.provenance.data_version.startswith("sigla-corpus-v1@abab")
