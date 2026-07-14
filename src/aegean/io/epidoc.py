"""Read and write the corpus model as EpiDoc TEI XML, both on the stdlib XML parser.

**Writing** (`to_epidoc` / `write_epidoc`): a `Document` becomes a TEI document — the header
carries the id and find-place, the body carries the transliteration as
``<w>``/``<num>``/``<g>``/``<seg>`` tokens with ``<lb/>`` line breaks and ``<unclear>``/``<supplied>``
apparatus for non-certain readings.

**Reading** (`from_epidoc` / `read_epidoc`): the inverse, and script-agnostic. It ingests pyaegean
output and other token-carrier EpiDoc editions (a single file or a directory) into a `Corpus`,
taking the id and find-place from the header and the token/line stream plus editorial certainty
from the ``<div type="edition">``. Tokens must be carried by ``<w>``/``<num>``/``<g>``/``<seg>``;
free-text editions need a source-specific extractor. Token kinds come from the carrier element
(``<w>``→word, ``<num>``→numeral, ``<g>``→logogram); a logogram
that had to be carried in ``<seg>`` to hold apparatus markup reloads as a word. Both directions use
**only the stdlib XML parser**, so neither needs an extra dependency. (The Linear B-specific
`aegean.scripts.linearb.parse_epidoc` keeps its own lxml reader for DAMOS-style files, where it
re-derives Aegean token kinds from the transliteration text.)
"""

from __future__ import annotations

import warnings
import re
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from .._atomic import atomic_path
from ..core.model import (
    Document,
    DocumentMeta,
    FormSegment,
    ReadingStatus,
    SourceMarkupRef,
    Token,
    TokenFormState,
    TokenKind,
)

# Characters XML 1.0 forbids in text: control chars other than tab/newline/CR, plus the
# non-character code points. Emitting them raw yields output that cannot be re-parsed.
_XML_OK_WS = frozenset((0x09, 0x0A, 0x0D))  # tab, newline, carriage return
_XML_ATTR_NAME = re.compile(
    r"^(?:\{[^{}]+\})?[A-Za-z_][A-Za-z0-9._:-]*$"
)


def _xml_clean(text: str) -> str:
    """Drop XML-1.0-invalid characters so the serialized document stays well-formed."""
    return "".join(
        c
        for c in text
        if ord(c) in _XML_OK_WS
        or 0x20 <= ord(c) <= 0xD7FF
        or 0xE000 <= ord(c) <= 0xFFFD
        or ord(c) >= 0x10000
    )

if TYPE_CHECKING:
    import xml.etree.ElementTree as ET

    from ..core.corpus import Corpus

_TEI = "http://www.tei-c.org/ns/1.0"
_XML = "http://www.w3.org/XML/1998/namespace"  # for xml:lang on the edition div

# pyaegean token kind → EpiDoc element. The reader re-classifies by text, so this is for semantic
# fidelity and interop with other EpiDoc tools; w/num/g/seg all reload to the right kind.
_TAG = {TokenKind.WORD: "w", TokenKind.NUMERAL: "num", TokenKind.LOGOGRAM: "g"}

# script id → BCP 47 xml:lang for the edition div ("und" = undetermined, for the undeciphered scripts).
_LANG = {"lineara": "und", "linearb": "gmy", "cypriot": "grc", "cyprominoan": "und", "greek": "grc"}

# non-CERTAIN reading → the EpiDoc apparatus element that wraps the token text.
# RESTORED and LOST both use <supplied> (which, unlike the empty <gap>, can carry the token
# text so it survives the round trip) and are kept distinct by @reason: an editor-supplied
# reading is reason="lost"; a non-preserved/conjectural reading is reason="undefined". Both
# @reason values are EpiDoc-recommended, so the output stays schema-valid.
_STATUS_EL = {
    ReadingStatus.UNCLEAR: ("unclear", {}),
    ReadingStatus.RESTORED: ("supplied", {"reason": "lost"}),
    ReadingStatus.LOST: ("supplied", {"reason": "undefined"}),
}


def to_epidoc(document: Document) -> str:
    """Serialize a single `Document` to an EpiDoc TEI XML string.

    The transliteration lives in a TEI ``<div type="edition">`` (EpiDoc's required edition
    division), as ``<lb/>``-delimited lines of ``<w>``/``<num>``/``<g>`` tokens. A token whose
    `aegean.ReadingStatus` is not ``CERTAIN`` is wrapped in the matching EpiDoc apparatus
    element (``<unclear>`` or ``<supplied>``), so editorial certainty survives the round trip
    through `aegean.scripts.linearb.parse_epidoc`. The output validates against the EpiDoc
    RelaxNG schema (see ``tests/test_io.py``).

    Token *text* round-trips subject to standard XML text normalization: a carriage
    return becomes a line feed, leading/trailing whitespace on a token is trimmed, and a
    token (or alternate reading) whose text is only whitespace does not survive the parse.
    Real transliteration tokens are never whitespace-only, so this affects only synthetic
    input; the transliteration content itself is preserved.

    ``Token.annotations`` (lemma, morphology, evidence class, review stamps) are NOT
    serialized to EpiDoc: the format carries edition text and apparatus, not an
    analysis layer. A typed state projects its diplomatic form, one selected editorial
    form (regularized before normalized), and apparatus segments. ``model_input``, its
    operations, and a second normalized form are not edition markup and are not serialized.
    Use `Corpus.to_json`, `aegean.db.to_sqlite`, or CoNLL-U for the full typed record."""
    import xml.etree.ElementTree as ET  # lazy: keep `import aegean` free of the XML parser

    def q(tag: str) -> str:
        return f"{{{_TEI}}}{tag}"

    def sub(parent: ET.Element, tag: str, text: str | None = None) -> ET.Element:
        el = ET.SubElement(parent, q(tag))
        if text is not None:
            el.text = _xml_clean(text)
        return el

    def apply_source_attrs(el: ET.Element, ref: SourceMarkupRef | None) -> None:
        """Restore safe semantic source attributes with their namespace names intact."""
        if ref is None:
            return
        for key, value in ref.attrs:
            if not _XML_ATTR_NAME.fullmatch(key):
                raise ValueError(
                    f"invalid XML attribute name {key!r} in source markup reference"
                )
            if ":" in key and not key.startswith("{") and not key.startswith("xml:"):
                raise ValueError(
                    f"unbound XML attribute prefix in {key!r}; use Clark notation"
                )
            el.set(key, _xml_clean(value))

    def emit_segment(parent: ET.Element, segment: FormSegment) -> None:
        if not segment.text:
            # An empty segment is a real lacuna, not an omitted token.  Keep its semantic
            # reference attributes where they are representable, while remaining valid TEI.
            gap = sub(parent, "gap")
            apply_source_attrs(gap, segment.source_ref)
            if "reason" not in gap.attrib:
                gap.set("reason", "lost")
            return
        wrapper = _STATUS_EL.get(segment.status)
        if wrapper is None:
            value = _xml_clean(segment.text)
            if len(parent):
                parent[-1].tail = (parent[-1].tail or "") + value
            else:
                parent.text = (parent.text or "") + value
            return
        tag, attrs = wrapper
        inner = sub(parent, tag, segment.text)
        apply_source_attrs(inner, segment.source_ref)
        for key, value in attrs.items():
            existing = inner.get(key)
            if existing is not None and existing != value:
                raise ValueError(
                    "source markup attributes conflict with the typed editorial "
                    f"status: {key}={existing!r}, expected {value!r}"
                )
            inner.set(key, value)

    def emit_form(parent: ET.Element, tok: Token, carrier: str) -> None:
        state = tok.form_state
        if state is None:
            wrap = _STATUS_EL.get(tok.status)
            if wrap is None:
                parent.text = _xml_clean(tok.text)
            else:
                tag, attrs = wrap
                inner = sub(parent, tag, tok.text)
                for key, value in attrs.items():
                    inner.set(key, value)
            return

        segments = state.segments
        selected_form = (
            state.regularized
            if state.regularized is not None
            else state.normalized
            if state.normalized is not None
            else state.diplomatic
        )
        if segments and "".join(segment.text for segment in segments) != selected_form:
            raise ValueError(
                "token form-state segments do not compose the selected EpiDoc form"
            )
        # EpiDoc's choice is the semantic carrier for a diplomatic/original vs selected form.
        # Keep the selected text in the preferred branch and retain the original branch without
        # pretending that this is a byte-identical XML round trip.
        edited = state.regularized if state.regularized is not None else state.normalized
        if edited is not None and state.diplomatic != edited:
            choice = sub(parent, "choice")
            selected_tag = next(
                (
                    segment.source_ref.tag
                    for segment in segments
                    if segment.source_ref is not None
                    and segment.source_ref.tag in _CHOICE_PREFERENCE
                ),
                "reg",
            )
            counterpart_tag = {"reg": "orig", "corr": "sic", "expan": "abbr"}[
                selected_tag
            ]
            edited_el = sub(choice, selected_tag)
            selected_ref = next(
                (
                    segment.source_ref
                    for segment in segments
                    if segment.source_ref is not None
                    and segment.source_ref.tag == selected_tag
                ),
                None,
            )
            apply_source_attrs(edited_el, selected_ref)
            if segments:
                for segment in segments:
                    emit_segment(edited_el, segment)
            else:
                edited_el.text = _xml_clean(edited)
            sub(choice, counterpart_tag, state.diplomatic)
            return
        if segments:
            for segment in segments:
                emit_segment(parent, segment)
            # A constructed state may carry a token-level status without per-segment markup.
            if not any(segment.status is not ReadingStatus.CERTAIN for segment in segments):
                if tok.status is not ReadingStatus.CERTAIN and parent.text:
                    value = parent.text
                    parent.text = None
                    tag, attrs = _STATUS_EL[tok.status]
                    inner = sub(parent, tag, value)
                    for key, attr_value in attrs.items():
                        inner.set(key, attr_value)
            return
        wrap = _STATUS_EL.get(tok.status)
        if wrap is None:
            parent.text = _xml_clean(selected_form)
        else:
            tag, attrs = wrap
            inner = sub(parent, tag, selected_form)
            for key, value in attrs.items():
                inner.set(key, value)

    ET.register_namespace("", _TEI)  # emit the TEI namespace as the default (xmlns="…")
    root = ET.Element(q("TEI"))
    # fileDesc requires titleStmt, publicationStmt, sourceDesc — in that order — to be TEI-valid.
    file_desc = sub(sub(root, "teiHeader"), "fileDesc")
    sub(sub(file_desc, "titleStmt"), "title", document.meta.name or document.id)
    sub(sub(file_desc, "publicationStmt"), "p", "Exported by pyaegean; redistribute under the source's terms.")
    ms = sub(sub(file_desc, "sourceDesc"), "msDesc")
    sub(sub(ms, "msIdentifier"), "idno", document.id)
    if document.meta.site:
        sub(sub(sub(ms, "history"), "origin"), "origPlace", document.meta.site)

    body = sub(sub(root, "text"), "body")
    edition = sub(body, "div")
    edition.set("type", "edition")
    edition.set(f"{{{_XML}}}lang", _LANG.get(document.script_id, "und"))
    ab = sub(edition, "ab")
    lines = document.line_tokens if document.lines else [document.tokens]
    for i, line in enumerate(lines, start=1):
        sub(ab, "lb").set("n", str(i))
        for tok in line:
            carrier = _TAG.get(tok.kind, "seg")
            # TEI's <g> (glyph) has a restricted content model and can't hold <unclear>/<supplied>
            # (and an <app> can't carry it inside <lem>/<rdg> meaningfully); carry the token in
            # <seg> instead (the reader re-derives its kind by text).
            if (tok.status is not ReadingStatus.CERTAIN or tok.alt or tok.form_state) and carrier == "g":
                carrier = "seg"
            if tok.alt:
                # alternate readings: <app><lem><w>text</w></lem><rdg><w>alt</w></rdg>…</app>
                app = sub(ab, "app")
                el = sub(sub(app, "lem"), carrier)
                emit_form(el, tok, carrier)
                for a in tok.alt:
                    sub(sub(app, "rdg"), carrier, _xml_clean(a))
            else:
                el = sub(ab, carrier)
                emit_form(el, tok, carrier)

    ET.indent(root)
    return "<?xml version='1.0' encoding='UTF-8'?>\n" + ET.tostring(root, encoding="unicode") + "\n"


def _safe_name(doc_id: str) -> str:
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in doc_id) or "document"


def write_epidoc(obj: Corpus | Document, path: str | Path) -> None:
    """Write EpiDoc TEI XML to disk.

    A single `Document` is written to the file ``path``; a
    `Corpus` is written as one ``{id}.xml`` file per document into the
    directory ``path`` (created if needed) — the layout
    `aegean.scripts.linearb.parse_epidoc` reads back. Ids are sanitized for
    the filesystem (anything outside ``[A-Za-z0-9-_.]`` becomes ``_``), which
    can conflate distinct ids: when two ids sanitize to the same filename, the
    later ones (in id order) get a ``-2``, ``-3``, ... suffix and a warning
    names the colliding ids, so no document silently overwrites another.
    ``Token.annotations`` are not serialized (see `to_epidoc`)."""
    if isinstance(obj, Document):
        with atomic_path(path) as tmp:  # temp+replace: a failed write keeps the prior file
            tmp.write_text(to_epidoc(obj), encoding="utf-8")
        return
    out = Path(path)
    out.mkdir(parents=True, exist_ok=True)
    # Sanitizing can map distinct ids to the same filename ("KN X 1" and "KN,X;1" both become
    # "KN_X_1"); group by sanitized name and disambiguate deterministically in id order.
    by_name: dict[str, list[Document]] = {}
    for doc in obj:
        by_name.setdefault(_safe_name(doc.id), []).append(doc)
    used = set(by_name)
    for name, group in by_name.items():
        group.sort(key=lambda d: d.id)
        if len(group) > 1:
            ids = ", ".join(repr(d.id) for d in group)
            warnings.warn(
                f"write_epidoc: document ids {ids} all sanitize to the filename {name!r}.xml; "
                f"keeping the first (in id order) and suffixing the rest with -2, -3, ...",
                stacklevel=2,
            )
        for i, doc in enumerate(group):
            fname = name
            if i:
                n = i + 1
                fname = f"{name}-{n}"
                while fname in used:  # a suffixed name can itself be another document's id
                    n += 1
                    fname = f"{name}-{n}"
                used.add(fname)
            with atomic_path(out / f"{fname}.xml") as tmp:
                tmp.write_text(to_epidoc(doc), encoding="utf-8")


# ── reading EpiDoc TEI back into the corpus model ────────────────────────────────

_TOKEN_TAGS = frozenset({"w", "num", "g", "seg"})
_KIND_BY_TAG = {"w": TokenKind.WORD, "num": TokenKind.NUMERAL, "g": TokenKind.LOGOGRAM}


def _local(tag: object) -> str:
    """Local name of a (possibly namespaced) ElementTree tag."""
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def _node_text(el: ET.Element) -> str:
    return "".join(el.itertext()).strip()


def _first_text(root: ET.Element, *tags: str) -> str:
    """First non-empty text among the named TEI elements, searched anywhere."""
    for tag in tags:
        el = root.find(f".//{{{_TEI}}}{tag}")
        if el is not None and _node_text(el):
            return _node_text(el)
    return ""


def _status_index(region: ET.Element) -> "Callable[[ET.Element], ReadingStatus]":
    """Build an O(1) reading-status lookup for every element under ``region``, in one pass.

    Editorial certainty comes from any EpiDoc apparatus element a token contains:
    ``<supplied reason="undefined">`` (non-preserved / conjectural) and a bare ``<gap>`` are
    ``LOST``; any other ``<supplied>`` (editor-supplied, ``reason="lost"``) is ``RESTORED``;
    ``<unclear>`` is ``UNCLEAR``. Computing this per token by rescanning the token's subtree
    was O(subtree) each, hence O(n^2) on a deeply-nested document; folding the subtree flags
    bottom-up once makes it linear. The result matches the old per-token scan: the first
    ``<supplied>`` in document order (parent before children) sets the supplied reason."""
    order = list(region.iter())
    supplied_reason: dict[ET.Element, str | None] = {}
    has_gap: dict[ET.Element, bool] = {}
    has_unclear: dict[ET.Element, bool] = {}
    for el in reversed(order):  # children precede parents, so a fold sees them first
        loc = _local(el.tag)
        reason = el.get("reason", "") if loc == "supplied" else None
        gap = loc == "gap"
        unclear = loc == "unclear"
        for child in el:  # children in document order: the first supplied wins
            if reason is None:
                reason = supplied_reason.get(child)
            gap = gap or has_gap.get(child, False)
            unclear = unclear or has_unclear.get(child, False)
        supplied_reason[el] = reason
        has_gap[el] = gap
        has_unclear[el] = unclear

    def status_of(el: ET.Element) -> ReadingStatus:
        reason = supplied_reason.get(el)
        if reason is not None:
            return ReadingStatus.LOST if reason == "undefined" else ReadingStatus.RESTORED
        if has_gap.get(el, False):
            return ReadingStatus.LOST
        if has_unclear.get(el, False):
            return ReadingStatus.UNCLEAR
        return ReadingStatus.CERTAIN

    return status_of


def _kind_of(carrier: str, text: str) -> TokenKind:
    kind = _KIND_BY_TAG.get(carrier)
    if kind is not None:
        return kind
    # <seg> is the writer's fallback carrier (e.g. a logogram that had to hold apparatus
    # markup); re-derive the obvious numeral case, otherwise treat it as a word.
    return TokenKind.NUMERAL if text and all(c.isdigit() for c in text) else TokenKind.WORD


_SEVERITY = {
    ReadingStatus.CERTAIN: 0,
    ReadingStatus.UNCLEAR: 1,
    ReadingStatus.RESTORED: 2,
    ReadingStatus.LOST: 3,
}
_SKIP_TEXT = frozenset({"g", "space", "milestone", "note", "certainty", "head"})
_CHOICE_PREFERENCE = ("expan", "reg", "corr")


def _status_for_element(el: ET.Element, inherited: ReadingStatus) -> ReadingStatus:
    """Apply one EpiDoc apparatus marker, retaining the most severe status."""
    tag = _local(el.tag)
    if tag == "supplied":
        status = ReadingStatus.LOST if el.get("reason") == "undefined" else ReadingStatus.RESTORED
    elif tag == "unclear":
        status = ReadingStatus.UNCLEAR
    else:
        status = inherited
    return status if _SEVERITY[status] >= _SEVERITY[inherited] else inherited


def _markup_ref(
    source_id: str, el: ET.Element, paths: dict[ET.Element, str] | None = None,
) -> SourceMarkupRef:
    """Build semantic markup provenance, never a byte offset or raw-XML claim."""
    attrs = tuple((key, value) for key, value in el.attrib.items())
    tag = _local(el.tag)
    return SourceMarkupRef(source_id, paths.get(el, tag) if paths is not None else tag, tag, attrs)


def _choice_member(choice: ET.Element, preferred: bool = True) -> ET.Element | None:
    children = list(choice)
    if preferred:
        for wanted in _CHOICE_PREFERENCE:
            for child in children:
                if _local(child.tag) == wanted:
                    return child
    for child in children:
        if _local(child.tag) not in {"abbr", "orig", "sic"}:
            return child
    return children[0] if children else None


def _plain_text(root: ET.Element) -> str:
    """Extract one selected EpiDoc branch without recursive Python calls.

    The explicit stack is important: user-supplied TEI can be deeply nested and must remain
    linear and bounded by the input size rather than Python's recursion limit.
    """
    return _plain_form(root, "selected")


def _plain_form(root: ET.Element, mode: str) -> str:
    """Extract one structural choice view (selected or diplomatic) iteratively."""
    chunks: list[str] = []
    stack: list[tuple[str, ET.Element | None, str | None]] = [("node", root, None)]
    while stack:
        event, el, text = stack.pop()
        if event == "text":
            if text:
                chunks.append(text)
            continue
        if el is None:
            continue
        tag = _local(el.tag)
        if (tag in _SKIP_TEXT and el is not root) or tag in {"gap", "lb"}:
            continue
        if tag == "choice":
            selected = _choice_member(el)
            if mode == "diplomatic" and selected is not None:
                counterpart_tag = {"reg": "orig", "corr": "sic", "expan": "abbr"}.get(
                    _local(selected.tag)
                )
                selected = next(
                    (child for child in el if _local(child.tag) == counterpart_tag), selected
                )
            if el.text:
                chunks.append(el.text)
            if selected is not None:
                stack.append(("text", None, selected.tail))
                stack.append(("node", selected, None))
            continue
        if tag == "app":
            lem = next((child for child in el if _local(child.tag) == "lem"), None)
            if lem is not None:
                stack.append(("node", lem, None))
            continue
        if tag == "expan":
            # ``<abbr>`` may be a prefix inside a full expansion (``<abbr>dr</abbr><ex>ach</ex>``);
            # retain it here.  A sibling <abbr> branch of <choice> is handled separately as the
            # diplomatic counterpart.
            children = list(el)
        else:
            children = [child for child in el if _local(child.tag) != "abbr"]
        for child in reversed(children):
            stack.append(("text", None, child.tail))
            stack.append(("node", child, None))
        if el.text:
            stack.append(("text", None, el.text))
    return "".join(chunks).strip()


def _segments(
    root: ET.Element, source_id: str, paths: dict[ET.Element, str] | None = None,
    initial_status: ReadingStatus = ReadingStatus.CERTAIN,
    initial_ref: SourceMarkupRef | None = None,
) -> tuple[FormSegment, ...]:
    """Read selected text into ordered, status-bearing segments without recursion."""
    out: list[FormSegment] = []
    stack: list[tuple[str, ET.Element | None, ReadingStatus, SourceMarkupRef | None]] = [
        ("node", root, initial_status, initial_ref)
    ]

    def add_text(value: str | None, status: ReadingStatus, ref: SourceMarkupRef | None) -> None:
        if not value or not value.strip():
            return
        value = value.strip() if not out else value
        if not value:
            return
        if out and out[-1].status is status and out[-1].source_ref == ref and out[-1].text:
            out[-1] = FormSegment(out[-1].text + value, status, ref)
        else:
            out.append(FormSegment(value, status, ref))

    while stack:
        event, el, inherited, ref = stack.pop()
        if event == "text":
            add_text(el.text if el is not None else None, inherited, ref)
            continue
        if event == "tail":
            add_text(el.tail if el is not None else None, inherited, ref)
            continue
        if el is None:
            continue
        tag = _local(el.tag)
        if (tag in _SKIP_TEXT and el is not root) or tag == "lb":
            continue
        if tag == "gap":
            gap_ref = _markup_ref(source_id, el, paths)
            out.append(FormSegment("", ReadingStatus.LOST, gap_ref))
            continue
        if tag == "choice":
            selected = _choice_member(el)
            if selected is not None:
                selected_ref = ref or _markup_ref(source_id, selected, paths)
                if selected.tail:
                    stack.append(("tail", selected, inherited, ref))
                stack.append(("node", selected, inherited, selected_ref))
            if el.text:
                stack.append(("text", el, inherited, ref))
            continue
        if tag == "app":
            lem = next((child for child in el if _local(child.tag) == "lem"), None)
            if lem is not None:
                stack.append(("node", lem, inherited, ref))
            continue
        status = _status_for_element(el, inherited)
        marker_ref = ref
        if tag in {"supplied", "unclear"}:
            marker_status = (
                ReadingStatus.LOST
                if tag == "supplied" and el.get("reason") == "undefined"
                else ReadingStatus.RESTORED
                if tag == "supplied"
                else ReadingStatus.UNCLEAR
            )
            if _SEVERITY[marker_status] >= _SEVERITY[inherited]:
                marker_ref = _markup_ref(source_id, el, paths)
        if tag == "expan":
            children = list(el)
        else:
            children = [child for child in el if _local(child.tag) != "abbr"]
        for child in reversed(children):
            if child.tail:
                stack.append(("tail", child, status, marker_ref))
            stack.append(("node", child, status, marker_ref))
        if el.text:
            stack.append(("text", el, status, marker_ref))
    return tuple(out)


def _variant_state(carrier: ET.Element, selected: str, segments: tuple[FormSegment, ...]) -> TokenFormState | None:
    """Return an A6 state for choices/apparatus, or ``None`` for plain legacy tokens."""
    choices = [el for el in carrier.iter() if _local(el.tag) == "choice"]
    pairs: list[tuple[str, str, str]] = []
    for choice in choices:
        selected_el = _choice_member(choice)
        if selected_el is None:
            continue
        selected_tag = _local(selected_el.tag)
        counterpart_tag = {
            "reg": "orig", "corr": "sic", "expan": "abbr",
        }.get(selected_tag)
        counterpart = next((child for child in choice if _local(child.tag) == counterpart_tag), None)
        if counterpart is None:
            continue
        selected_text = _plain_text(selected_el)
        diplomatic_text = _plain_text(counterpart)
        if selected_text or diplomatic_text:
            pairs.append((selected_tag, selected_text, diplomatic_text))
    diplomatic = _plain_form(carrier, "diplomatic") if pairs else selected
    regularized: str | None = None
    for selected_tag, _selected_text, _diplomatic_text in pairs:
        if selected_tag in {"reg", "corr", "expan"}:
            regularized = selected
    has_markup = any(
        segment.source_ref is not None or segment.status is not ReadingStatus.CERTAIN
        or not segment.text
        for segment in segments
    )
    if not pairs and not has_markup:
        return None
    return TokenFormState(
        diplomatic=diplomatic,
        regularized=regularized,
        model_input=None,
        segments=segments,
        model_input_source=None,
    )


def _token_form(
    carrier: ET.Element, source_id: str, paths: dict[ET.Element, str] | None = None,
    initial_status: ReadingStatus = ReadingStatus.CERTAIN,
    initial_ref: SourceMarkupRef | None = None,
) -> tuple[str, ReadingStatus, TokenFormState | None]:
    segments = _segments(carrier, source_id, paths, initial_status, initial_ref)
    text = "".join(segment.text for segment in segments)
    status = max((segment.status for segment in segments), key=lambda value: _SEVERITY[value], default=ReadingStatus.CERTAIN)
    state = _variant_state(carrier, text, segments)
    return text, status, state


def _read_document(root: ET.Element, script_id: str, fallback_id: str) -> Document | None:
    edition = next(
        (d for d in root.iter(f"{{{_TEI}}}div") if d.get("type") == "edition"), None
    )
    region = edition if edition is not None else root.find(f".//{{{_TEI}}}body")
    if region is None:
        return None

    doc_id = _first_text(root, "idno", "title") or root.get(f"{{{_XML}}}id") or fallback_id
    name = _first_text(root, "title")
    site = _first_text(root, "origPlace", "settlement", "provenance")
    notes = tuple(
        _node_text(n) for n in root.iter()
        if _local(n.tag) in ("note", "bibl") and _node_text(n)
    )
    # Stable semantic paths are ordinal labels, not offsets into XML bytes.  Building them from
    # one document-order pass keeps deeply nested hostile input linear while distinguishing
    # repeated <supplied>/<gap> markers.
    paths = {
        element: f"{_local(element.tag)}[{ordinal}]"
        for ordinal, element in enumerate(region.iter(), start=1)
        if _local(element.tag)
        in {
            "supplied",
            "unclear",
            "gap",
            "choice",
            "expan",
            "reg",
            "corr",
            "abbr",
            "orig",
            "sic",
        }
    }
    contexts: dict[ET.Element, tuple[ReadingStatus, SourceMarkupRef | None]] = {}
    context_stack: list[tuple[ET.Element, ReadingStatus, SourceMarkupRef | None]] = [
        (region, ReadingStatus.CERTAIN, None)
    ]
    while context_stack:
        element, inherited, inherited_ref = context_stack.pop()
        status = _status_for_element(element, inherited)
        ref = inherited_ref
        if _local(element.tag) in {"supplied", "unclear"}:
            marker_status = (
                ReadingStatus.LOST
                if _local(element.tag) == "supplied" and element.get("reason") == "undefined"
                else ReadingStatus.RESTORED
                if _local(element.tag) == "supplied"
                else ReadingStatus.UNCLEAR
            )
            if _SEVERITY[marker_status] >= _SEVERITY[inherited]:
                ref = _markup_ref(doc_id, element, paths)
        contexts[element] = (status, ref)
        for child in reversed(list(element)):
            context_stack.append((child, status, ref))

    # Set of elements nested inside an <app> (consumed at the <app> itself, so skipped
    # as standalone tokens), and a per-element reading-status, both precomputed in single
    # passes. A per-token ancestor walk (inside_app) and a per-token subtree rescan
    # (_reading_status) were each O(tokens x depth) = quadratic, so a deeply-nested hostile
    # TEI hung the importer; these lookups make the parse linear.
    in_app: set[ET.Element] = set()
    for app in region.iter(f"{{{_TEI}}}app"):
        for desc in app:
            stack = [desc]
            while stack:
                e = stack.pop()
                in_app.add(e)
                stack.extend(e)
    tokens: list[Token] = []
    lines: list[list[int]] = []
    cur: list[int] = []
    pos = 0
    # A carrier is a token root.  Nested carriers occur in hostile/decorative TEI (and in
    # ``<seg>`` wrappers); consuming each nested carrier independently would turn a 10,000-deep
    # document into quadratic work and duplicate the same reading many times.
    token_roots: list[ET.Element] = []
    covered: set[ET.Element] = set()
    covered_apps: set[ET.Element] = set()
    for candidate in region.iter():
        if _local(candidate.tag) not in _TOKEN_TAGS or candidate in in_app or candidate in covered:
            continue
        token_roots.append(candidate)
        stack = list(candidate)
        while stack:
            child = stack.pop()
            covered.add(child)
            if _local(child.tag) == "app":
                covered_apps.add(child)
            stack.extend(child)
    token_root_set = set(token_roots)
    for el in region.iter():
        tag = _local(el.tag)
        if tag == "lb":
            if el.get("break") != "no" and cur:
                lines.append(cur)
                cur = []
        elif tag == "app":
            if el in covered_apps:
                continue
            lem = el.find(f"{{{_TEI}}}lem")
            if lem is None:
                continue
            carrier_el = next((c for c in lem.iter() if _local(c.tag) in _TOKEN_TAGS), lem)
            carrier = _local(carrier_el.tag) if carrier_el is not lem else "seg"
            initial_status, initial_ref = contexts.get(
                carrier_el, (ReadingStatus.CERTAIN, None)
            )
            text, status, state = _token_form(
                carrier_el, doc_id, paths, initial_status, initial_ref
            )
            alts = tuple(
                value for rdg in el.findall(f"{{{_TEI}}}rdg")
                if (value := _plain_text(rdg))
            )
            if not text and state is None:
                continue
            tokens.append(Token(
                text=text, kind=_kind_of(carrier, text),
                status=status, alt=alts, line_no=len(lines), position=pos,
                form_state=state,
            ))
            cur.append(pos)
            pos += 1
        elif tag in _TOKEN_TAGS:
            if el not in token_root_set:
                continue
            initial_status, initial_ref = contexts.get(el, (ReadingStatus.CERTAIN, None))
            text, status, state = _token_form(el, doc_id, paths, initial_status, initial_ref)
            if not text and state is None:
                continue
            tokens.append(Token(
                text=text, kind=_kind_of(tag, text), status=status,
                line_no=len(lines), position=pos, form_state=state,
            ))
            cur.append(pos)
            pos += 1
    if cur:
        lines.append(cur)

    meta = DocumentMeta(site=site, name=name or doc_id, notes=notes)
    return Document(id=doc_id, script_id=script_id, tokens=tokens, lines=lines, meta=meta)


def read_epidoc(source: str | Path, *, script_id: str = "greek") -> list[Document]:
    """Parse token-carrier EpiDoc TEI into Documents.

    A file, or every ``*.xml`` file in a directory, must represent tokens with
    ``<w>``, ``<num>``, ``<g>``, or ``<seg>`` carriers. This is the inverse of
    :func:`write_epidoc`; arbitrary free-text TEI needs a source-specific extractor.

    ``script_id`` labels the result: EpiDoc's ``xml:lang`` can't disambiguate (say) Linear A
    from Cypro-Minoan, so the caller names the script. Uses the stdlib XML parser only.

    Raises `FileNotFoundError` if ``source`` does not exist (or a directory holds no
    ``*.xml`` files), and `ValueError` if nothing in it is EpiDoc (no ``<div type="edition">``
    or ``<body>`` in the TEI namespace) — rather than silently returning an empty list. A
    malformed file inside a directory raises an `xml.etree.ElementTree.ParseError` whose
    message names the offending file, so a single bad inscription in a large corpus folder
    is identifiable (a directory has no line/column of its own)."""
    import xml.etree.ElementTree as ET

    path = Path(source)
    if not path.exists():
        # Match the friendly not-found message the sibling importers give (from_text_file
        # "no such text file", from_csv "no such CSV file") instead of leaking a raw
        # OSError "[Errno 2] No such file or directory" out of ET.parse.
        raise FileNotFoundError(f"no such EpiDoc file: {path}")
    is_dir = path.is_dir()
    files = sorted(path.glob("*.xml")) if is_dir else [path]
    if is_dir and not files:
        # Mirror from_text_dir's empty-match error rather than reporting "wrote 0" success.
        raise FileNotFoundError(f"no *.xml files in {path}")
    out: list[Document] = []
    for f in files:
        try:
            root = ET.parse(str(f)).getroot()
        except ET.ParseError as exc:
            # Name the offending FILE, not just a line/column. In a directory import the
            # caller (and the CLI) only knows the folder, and a folder has no "line 4"; a
            # single bad inscription in a large corpus would otherwise be unfindable. Keep
            # the parser's position and re-raise as a ParseError so the CLI adds its own
            # "not well-formed EpiDoc/TEI XML" frame exactly once (don't repeat it here).
            if is_dir:
                named = ET.ParseError(f"{f.name}: {exc}")
                named.code = exc.code
                named.position = exc.position
                raise named from None
            raise
        doc = _read_document(root, script_id, f.stem)
        if doc is not None:
            out.append(doc)
    if not out:
        # The source existed and parsed, but held no recognizable EpiDoc edition — say WHY
        # and where to look, rather than returning an empty corpus that reads as success.
        raise ValueError(
            f"no EpiDoc editions found in {path.name} — expected a "
            '<div type="edition"> or <body> in the TEI namespace '
            "(see the Using-Critical-Editions wiki page)"
        )
    return out


def from_epidoc(source: str | Path, *, script_id: str = "greek") -> Corpus:
    """Load token-carrier EpiDoc TEI into a `Corpus`.

    The inverse of `write_epidoc`: round-trips the id, find-place, token/line stream,
    editorial certainty, alternate readings, and typed form state. Other input must
    carry tokens in ``<w>``/``<num>``/``<g>``/``<seg>`` elements; free-text editions
    need a source-specific extractor. ``script_id`` labels the corpus (default
    ``"greek"``). pyaegean parses your files locally and never re-hosts them."""
    from ..core.corpus import Corpus
    from ..core.provenance import Provenance

    docs = read_epidoc(source, script_id=script_id)
    provenance = Provenance(
        # basename only (like from_text_file/from_csv): the full path would leak the user's
        # directory layout and username into the shared to_json archive and every citation.
        source=f"EpiDoc TEI import: {Path(source).name}",
        license="Parsed locally from your EpiDoc; redistribute under the source's terms.",
    )
    return Corpus(docs, provenance=provenance, script_id=script_id)
