"""Regression: the CoNLL-U interop sidecar must survive Unicode line separators.

``to_conllu`` embeds the sidecar as one comment line joined with an ASCII
newline, but the reader used to peel it back off with ``str.splitlines``, which
also breaks on U+2028/U+2029/U+0085 (and U+000B/U+000C/U+001C-U+001E).  Any such
character in ``source_text`` (arbitrary user text: PDF/JS extraction, XML 1.1
NEL, latin-1 0x85) split the sidecar JSON mid-string, so the writer produced a
file its own reader refused.  The reader now splits on ASCII newlines only.
"""

from __future__ import annotations

import pytest

from aegean.greek.ud import UDDocument, UDSentence, UDToken
from aegean.io._interop_bundle import bundle_from_document
from aegean.io.interop import (
    SIDECAR_COMMENT_PREFIX,
    InteropSchemaError,
    from_conllu,
    from_ud_document,
    to_conllu,
)

# Every separator ``str.splitlines`` treats as a line boundary but CoNLL-U does not.
_LINE_SEPARATORS = [
    ("U+2028", " "),
    ("U+2029", " "),
    ("U+0085", ""),
    ("U+000B", ""),
    ("U+000C", ""),
    ("U+001C", ""),
    ("U+001D", ""),
    ("U+001E", ""),
]


def _document(source_text: str):
    ud = UDDocument(
        (
            UDSentence(
                "s1",
                "de x",
                (
                    UDToken(1, "de", "de", "ADP", "_", "_", 0, "root"),
                    UDToken(2, "x", "x", "NOUN", "_", "_", 1, "dep"),
                ),
            ),
        )
    )
    return from_ud_document(ud, source_text=source_text)


@pytest.mark.parametrize("name,separator", _LINE_SEPARATORS, ids=[n for n, _ in _LINE_SEPARATORS])
def test_conllu_sidecar_round_trips_through_unicode_line_separator(name: str, separator: str) -> None:
    source = "de" + separator + "x"
    doc = _document(source)
    exported = to_conllu(doc)
    assert exported.sidecar is not None  # richer metadata -> a sidecar is emitted

    restored = from_conllu(exported.value)  # previously raised InteropSchemaError

    # The exact source text, separator included, must survive the round trip.
    assert restored.value.source_text == source
    # And re-exporting is byte-identical: no metadata was lost or fabricated.
    assert to_conllu(restored.value).value == exported.value


@pytest.mark.parametrize("name,separator", _LINE_SEPARATORS, ids=[n for n, _ in _LINE_SEPARATORS])
def test_conllu_bundle_builds_over_unicode_line_separator(name: str, separator: str) -> None:
    doc = _document("de" + separator + "x")
    bundle = bundle_from_document(doc, target="conllu")  # previously raised on hash mismatch
    assert bundle.report.lossless


def test_ordinary_text_still_round_trips() -> None:
    # Control: a plain source (and a genuine, JSON-escaped newline) is unaffected.
    for source in ("de x", "line one\nline two"):
        doc = _document(source)
        restored = from_conllu(to_conllu(doc).value)
        assert restored.value.source_text == source


def test_duplicate_sidecar_comment_is_still_rejected() -> None:
    doc = _document("de x")
    exported = to_conllu(doc).value
    # Two sidecar comment lines is malformed input and must still be caught.
    doubled = SIDECAR_COMMENT_PREFIX + "{}\n" + exported
    with pytest.raises(InteropSchemaError, match="duplicate"):
        from_conllu(doubled)
