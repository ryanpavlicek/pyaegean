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
