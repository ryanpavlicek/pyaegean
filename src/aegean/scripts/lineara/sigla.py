"""SigLA — the Linear A paleographical database, decoded (opt-in, fetched).

SigLA (https://sigla.phis.me, Salgarella & Castellan) publishes its dataset and
drawings under **CC BY-NC-SA 4.0**, and its paper invites reuse "outside the
interface". The database ships inside the web app (``database.js``) as quoted
OCaml string literals holding **OCaml Marshal** payloads; this module fetches
that file to the cache (never bundled — NonCommercial data stays out of the
Apache-2.0 wheel), peels the two escape layers, decodes the Marshal streams
with a pure-Python reader, and exposes the result through the standard corpus
model. The NonCommercial + ShareAlike obligations pass through to you; cite
SigLA in academic work (see ``NOTICE``).

The Marshal reader implements the documented subset of OCaml's serialization
format (see ``intern.c`` in the OCaml runtime): small/boxed ints, strings,
blocks, shared back-references, doubles, and fixed-size customs. The header's
declared object count is verified after decoding — a structural self-check
that the stream was read exactly as written.
"""

from __future__ import annotations

import re
import struct
from dataclasses import dataclass
from typing import Any

_MAGIC_SMALL = 0x8495A6BE

# opcode constants (intern.c)
_PREFIX_SMALL_BLOCK = 0x80
_PREFIX_SMALL_INT = 0x40
_PREFIX_SMALL_STRING = 0x20
_CODE_INT8 = 0x00
_CODE_INT16 = 0x01
_CODE_INT32 = 0x02
_CODE_INT64 = 0x03
_CODE_SHARED8 = 0x04
_CODE_SHARED16 = 0x05
_CODE_SHARED32 = 0x06
_CODE_BLOCK32 = 0x08
_CODE_STRING8 = 0x09
_CODE_STRING32 = 0x0A
_CODE_DOUBLE_BIG = 0x0B
_CODE_DOUBLE_LITTLE = 0x0C
_CODE_DOUBLE_ARRAY8_BIG = 0x0D
_CODE_DOUBLE_ARRAY8_LITTLE = 0x0E
_CODE_DOUBLE_ARRAY32_BIG = 0x0F
_CODE_DOUBLE_ARRAY32_LITTLE = 0x07
_CODE_CUSTOM = 0x12
_CODE_BLOCK64 = 0x13
_CODE_CUSTOM_LEN = 0x18
_CODE_CUSTOM_FIXED = 0x19


@dataclass
class Block:
    """One OCaml heap block: a constructor/tuple/record with a tag and fields."""

    tag: int
    fields: list[Any]

    def __repr__(self) -> str:  # compact, for exploration
        return f"B{self.tag}({', '.join(map(_short, self.fields))})"


def _short(v: Any) -> str:
    s = repr(v)
    return s if len(s) <= 28 else s[:25] + "…"


class MarshalError(ValueError):
    """The byte stream is not the OCaml Marshal subset this reader supports."""


class _Reader:
    def __init__(self, buf: bytes) -> None:
        self.buf = buf
        self.pos = 0
        self.table: list[Any] = []  # shared-object table, in registration order

    def _take(self, n: int) -> bytes:
        b = self.buf[self.pos : self.pos + n]
        if len(b) != n:
            raise MarshalError("truncated stream")
        self.pos += n
        return b

    def _u8(self) -> int:
        return self._take(1)[0]

    def _u16(self) -> int:
        return int(struct.unpack(">H", self._take(2))[0])

    def _u32(self) -> int:
        return int(struct.unpack(">I", self._take(4))[0])

    def _register(self, v: Any) -> Any:
        self.table.append(v)
        return v

    def value(self) -> Any:
        code = self._u8()
        if code >= _PREFIX_SMALL_BLOCK:
            tag = code & 0x0F
            size = (code >> 4) & 0x07
            return self._block(tag, size)
        if code >= _PREFIX_SMALL_INT:
            return code & 0x3F
        if code >= _PREFIX_SMALL_STRING:
            return self._string(code & 0x1F)
        if code == _CODE_INT8:
            return struct.unpack(">b", self._take(1))[0]
        if code == _CODE_INT16:
            return struct.unpack(">h", self._take(2))[0]
        if code == _CODE_INT32:
            return struct.unpack(">i", self._take(4))[0]
        if code == _CODE_INT64:
            return struct.unpack(">q", self._take(8))[0]
        if code == _CODE_SHARED8:
            return self._shared(self._u8())
        if code == _CODE_SHARED16:
            return self._shared(self._u16())
        if code == _CODE_SHARED32:
            return self._shared(self._u32())
        if code == _CODE_BLOCK32:
            header = self._u32()
            return self._block(header & 0xFF, header >> 10)
        if code == _CODE_STRING8:
            return self._string(self._u8())
        if code == _CODE_STRING32:
            return self._string(self._u32())
        if code == _CODE_DOUBLE_LITTLE:
            return self._register(struct.unpack("<d", self._take(8))[0])
        if code == _CODE_DOUBLE_BIG:
            return self._register(struct.unpack(">d", self._take(8))[0])
        if code in (_CODE_DOUBLE_ARRAY8_LITTLE, _CODE_DOUBLE_ARRAY8_BIG):
            n = self._u8()
            fmt = "<d" if code == _CODE_DOUBLE_ARRAY8_LITTLE else ">d"
            return self._register([struct.unpack(fmt, self._take(8))[0] for _ in range(n)])
        if code in (_CODE_DOUBLE_ARRAY32_LITTLE, _CODE_DOUBLE_ARRAY32_BIG):
            n = self._u32()
            fmt = "<d" if code == _CODE_DOUBLE_ARRAY32_LITTLE else ">d"
            return self._register([struct.unpack(fmt, self._take(8))[0] for _ in range(n)])
        if code in (_CODE_CUSTOM, _CODE_CUSTOM_FIXED, _CODE_CUSTOM_LEN):
            return self._custom(code)
        if code == _CODE_BLOCK64:
            raise MarshalError("64-bit blocks not supported")
        raise MarshalError(f"unknown opcode {code:#x} at {self.pos - 1}")

    def _block(self, tag: int, size: int) -> Any:
        if size == 0:
            return Block(tag, [])  # an atom — not registered (intern.c)
        b = Block(tag, [])
        self._register(b)  # register BEFORE fields: they may back-reference it
        b.fields = [self.value() for _ in range(size)]
        return b

    def _string(self, n: int) -> str:
        raw = self._take(n)
        s = raw.decode("utf-8", errors="replace")
        self._register(s)
        return s

    def _shared(self, distance: int) -> Any:
        idx = len(self.table) - distance
        if not 0 <= idx < len(self.table):
            raise MarshalError(f"bad shared distance {distance}")
        return self.table[idx]

    def _custom(self, code: int) -> Any:
        # identifier is a NUL-terminated string
        ident = bytearray()
        while (c := self._u8()) != 0:
            ident.append(c)
        name = ident.decode("ascii", errors="replace")
        if code == _CODE_CUSTOM_LEN:
            self._take(8 + 8)  # explicit 32/64 lengths precede the payload
        sizes = {"_j": 8, "_i": 4, "_n": 8}
        if name not in sizes:
            raise MarshalError(f"unsupported custom block {name!r}")
        raw = self._take(sizes[name])
        val = int.from_bytes(raw, "big", signed=True)
        return self._register(val)


def unmarshal(buf: bytes) -> Any:
    """Decode one OCaml Marshal value; verifies the header and the object count."""
    if len(buf) < 20:
        raise MarshalError("too short for a Marshal header")
    magic, data_len, num_objects, _sz32, _sz64 = struct.unpack(">IIIII", buf[:20])
    if magic != _MAGIC_SMALL:
        raise MarshalError(f"bad magic {magic:#x}")
    if data_len != len(buf) - 20:
        raise MarshalError(f"declared {data_len} data bytes, have {len(buf) - 20}")
    r = _Reader(buf[20:])
    v = r.value()
    if r.pos != data_len:
        raise MarshalError(f"decoded {r.pos} of {data_len} bytes")
    if len(r.table) != num_objects:
        raise MarshalError(f"registered {len(r.table)} objects, header says {num_objects}")
    return v


# ── the database.js container: two escape layers around the Marshal bytes ───

_VAR_RE = re.compile(r"var (\w+) = '(.*?)';", re.S)


def _ocaml_literal_bytes(literal: str) -> bytes:
    """Decode a quoted OCaml string literal (decimal ``\\DDD`` escapes)."""
    if not (literal.startswith('"') and literal.endswith('"')):
        raise MarshalError("expected a quoted OCaml string literal")
    body = literal[1:-1]
    out = bytearray()
    i = 0
    while i < len(body):
        c = body[i]
        if c == "\\":
            nxt = body[i + 1]
            if nxt.isdigit():
                out.append(int(body[i + 1 : i + 4]))
                i += 4
            elif nxt == "x":
                out.append(int(body[i + 2 : i + 4], 16))
                i += 4
            elif nxt == "n":
                out.append(10)
                i += 2
            elif nxt == "t":
                out.append(9)
                i += 2
            else:  # \" \\ \' …
                out.append(ord(nxt))
                i += 2
        else:
            out.append(ord(c))
            i += 1
    return bytes(out)


def parse_database_js(text: str) -> dict[str, Any]:
    """Decode every ``var NAME = '…'`` Marshal payload in a SigLA database.js."""
    out: dict[str, Any] = {}
    for name, js_literal in _VAR_RE.findall(text):
        ocaml_literal = js_literal.replace("\\\\", "\\")  # JS string layer
        out[name] = unmarshal(_ocaml_literal_bytes(ocaml_literal))
    return out


# ── the corpus loader (fetches the decoded, versioned release asset) ─────────


def _sigla_tokens(attestations: list[dict[str, Any]]) -> tuple[list[Any], list[list[int]]]:
    """Build tokens + lines from v2 attestations, grouping signs into words.

    Each attestation carries a ``kind`` (syllable / logogram / fraction / blank)
    and a ``word`` index (None = standalone). Consecutive ``syllable``
    attestations sharing a word index become one multi-sign `WORD` token
    (``KA-U-DE-TA``); ``logogram`` attestations become `LOGOGRAM` tokens;
    fraction/blank attestations carry no resolved value and are skipped (SigLA
    records no cardinal-number values). Each word/standalone item is its own
    line. Falls back to one `UNKNOWN` token per sign for a v1 asset (no
    ``word``/``kind`` keys)."""
    from ...core.model import Token, TokenKind

    tokens: list[Any] = []
    lines: list[list[int]] = []
    pending: list[str] = []          # signs accumulating into the current word
    pending_word: int | None = None  # the current word index

    def flush() -> None:
        nonlocal pending, pending_word
        if not pending:
            return
        text = "-".join(pending)
        idx = len(tokens)
        tokens.append(Token(text, TokenKind.WORD, tuple(pending), None, len(lines), idx))
        lines.append([idx])
        pending = []
        pending_word = None

    for att in attestations:
        sign = att.get("sign") or ""
        kind = att.get("kind")
        word = att.get("word")
        if kind is None:  # v1 asset — preserve the old sign-stream behaviour
            if sign:
                idx = len(tokens)
                tokens.append(Token(sign, TokenKind.UNKNOWN, (sign,), None, 0, idx))
                lines.append([idx])
            continue
        if word is not None and kind in ("syllable", "blank"):
            # part of a multi-sign word; an unresolved sign is kept as ``*?`` so
            # the word stays contiguous (KU-ZU-NI with an unread ZU → KU-*?-NI).
            if pending_word is not None and word != pending_word:
                flush()
            pending_word = word
            pending.append(sign or "*?")
            continue
        flush()
        if kind == "logogram" and sign:
            idx = len(tokens)
            tokens.append(Token(sign, TokenKind.LOGOGRAM, (sign,), None, len(lines), idx))
            lines.append([idx])
        elif kind == "syllable" and sign:  # a standalone single syllabogram (its own word)
            idx = len(tokens)
            tokens.append(Token(sign, TokenKind.WORD, (sign,), None, len(lines), idx))
            lines.append([idx])
        # fraction / blank: no resolved value in SigLA — skipped
    flush()
    return tokens, lines


def load_sigla() -> Any:
    """Load the SigLA-derived Linear A dataset as a `Corpus` (opt-in, fetched).

    Fetches the ``sigla-corpus`` release asset (~1 MB JSON; sha256-pinned;
    **CC BY-NC-SA 4.0** — the NonCommercial obligation passes to you) on first
    use, then loads offline from the cache. One `Document` per SigLA document,
    with typology/site/period metadata and the physical dimensions in the
    document name. Since the **v2** asset, signs are grouped into **words** using
    SigLA's own word division: a multi-sign word like ``KA-U-DE-TA`` is one
    `WORD` token (signs in ``Token.signs``), commodity ideograms are `LOGOGRAM`
    tokens, and Linear-A-only signs read ``*NNN``. SigLA is a *palaeographic*
    database — it records sign occurrences and word division, **not** the
    cardinal-number quantities of the accounts — so fraction/unvalued signs carry
    no number and are skipped, and word division differs editorially from GORILA.
    Cite SigLA in academic work (see ``NOTICE``)."""
    import json as _json

    from ...core.corpus import Corpus
    from ...core.model import Document, DocumentMeta
    from ...core.provenance import Provenance
    from ...data import fetch

    path = fetch("sigla-corpus")
    payload = _json.loads(path.read_text(encoding="utf-8"))
    meta = payload.get("_meta", {})
    version = meta.get("version", 1)
    docs: list[Document] = []
    for rec in payload["documents"]:
        tokens, lines = _sigla_tokens(rec.get("attestations", []))
        dims = rec.get("dimensions_cm")
        name = str(rec["id"]) + (
            f" ({'×'.join(f'{d:g}' for d in dims)} cm)" if dims else ""
        )
        docs.append(
            Document(
                id=str(rec["id"]), script_id="lineara", tokens=tokens, lines=lines,
                meta=DocumentMeta(
                    site=rec.get("site") or "",
                    support=rec.get("typology") or "",
                    period=rec.get("period") or "",
                    name=name,
                ),
            )
        )
    provenance = Provenance(
        source="SigLA — The Signs of Linear A (Salgarella & Castellan), decoded dataset",
        license="CC BY-NC-SA 4.0 (as published by SigLA; NonCommercial — fetched, never bundled)",
        citation=str(
            meta.get(
                "cite",
                "Salgarella, E. & Castellan, S. (2020). SigLA. https://sigla.phis.me",
            )
        ),
        url="https://sigla.phis.me",
        data_version=f"sigla-corpus-v{version}@{str(meta.get('source_sha256', ''))[:12]}",
        notes=(
            "palaeographical corpus with SigLA's own word division (WORD tokens) "
            "and commodity ideograms (LOGOGRAM tokens); no cardinal-number values "
            "(SigLA records sign occurrences, not quantities). Word division and "
            "complex-sign notation differ editorially from GORILA."
            if version >= 2 else
            "sign-level paleographical corpus: one token per sign attestation, in "
            "tablet order; word boundaries are not encoded in this dataset version",
        ),
    )
    return Corpus(docs, None, provenance, "lineara")


# loadable by name: aegean.load("sigla") — fetches ~1 MB to the cache on first use
from ...core.corpus import register_loader  # noqa: E402

register_loader("sigla", load_sigla)
