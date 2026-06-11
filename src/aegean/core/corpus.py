"""The `Corpus` — the package's center of gravity.

Clean, typed, pandas-friendly access to a collection of documents. A loader
registry lets each script provide its bundled corpus without the core
importing the script (no cycles).
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Callable, Iterator, Sequence
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .model import Document, DocumentMeta, ReadingStatus, Sign, SignInventory, Token, TokenKind
from .provenance import SCHEMA_VERSION, Provenance

if TYPE_CHECKING:  # type-only: keep the L1 core free of an import-time dependency on L3 analysis
    from ..analysis.query import FilterRow, Output, QueryResults

_LOADERS: dict[str, Callable[[], "Corpus"]] = {}


def register_loader(script_id: str, fn: Callable[[], "Corpus"]) -> None:
    """Register a corpus loader so ``Corpus.load(script_id)`` / ``aegean.load(script_id)`` works."""
    _LOADERS[script_id] = fn


class Corpus:
    """A collection of `Document` s plus shared inventory + provenance."""

    def __init__(
        self,
        documents: list[Document],
        sign_inventory: SignInventory | None = None,
        provenance: Provenance | None = None,
        script_id: str = "",
    ) -> None:
        self.documents = list(documents)
        self.sign_inventory = sign_inventory
        self.provenance = provenance
        self.script_id = script_id
        self._by_id = {d.id: d for d in self.documents}

    # ── construction ────────────────────────────────────────────────────
    @classmethod
    def load(cls, script_id: str) -> "Corpus":
        """Load a bundled corpus by script id, e.g. ``Corpus.load("lineara")``."""
        try:
            fn = _LOADERS[script_id]
        except KeyError:
            raise KeyError(
                f"no bundled corpus for {script_id!r}; available: {sorted(_LOADERS)}"
            ) from None
        return fn()

    # ── access ──────────────────────────────────────────────────────────
    def __len__(self) -> int:
        return len(self.documents)

    def __iter__(self) -> Iterator[Document]:
        return iter(self.documents)

    def get(self, doc_id: str) -> Document | None:
        """The document with id ``doc_id``, or ``None`` if there is no such document."""
        return self._by_id.get(doc_id)

    def _repr_html_(self) -> str:
        """Rich rendering in Jupyter/Colab (plain ``repr`` everywhere else)."""
        from ._html import card, esc, table

        title = (
            "Corpus <span style='color:#888;font-weight:400'>· "
            f"{esc(self.script_id or '?')} · {len(self.documents)} documents</span>"
        )
        body = ""
        if self.provenance is not None:
            body += (
                "<div style='color:#666;font-size:0.85em;margin-bottom:6px'>"
                f"{esc(self.provenance.source)}</div>"
            )
        preview = self.documents[:8]
        rows = [(d.id, d.meta.site, d.meta.period, len(d.words)) for d in preview]
        body += table(["id", "site", "period", "words"], rows)
        if len(self.documents) > len(preview):
            body += (
                "<div style='color:#888;font-size:0.8em'>… "
                f"{len(self.documents) - len(preview)} more documents</div>"
            )
        return card(title, body)

    def filter(self, **meta: Any) -> "Corpus":
        """Return a new Corpus whose documents match all given metadata fields
        (AND-combination), e.g. ``corpus.filter(site="HT", period="LMIB")``.

        The subset's provenance records what was filtered (a ``subset:`` note),
        so `cite` on the result cites the exact subset used."""

        def ok(d: Document) -> bool:
            return all(getattr(d.meta, k, None) == v for k, v in meta.items())

        docs = [d for d in self.documents if ok(d)]
        prov = self.provenance
        if prov is not None and meta:
            desc = ", ".join(f"{k}={v!r}" for k, v in sorted(meta.items()))
            note = f"subset: filter({desc}) → {len(docs)} of {len(self.documents)} documents"
            prov = replace(prov, notes=prov.notes + (note,))
        return Corpus(docs, self.sign_inventory, prov, self.script_id)

    def cite(self, style: str = "plain") -> str:
        """Cite this corpus — or the exact filtered subset — in one call.

        ``style``: ``"plain"`` (one line), ``"bibtex"`` (a ``@misc`` entry), or
        ``"apa"``. Filtered subsets (see `filter`) carry a ``subset:`` note that
        all three styles include, so the citation states exactly what was used."""
        if self.provenance is None:
            raise ValueError("this corpus carries no provenance to cite")
        p = self.provenance
        if style == "plain":
            subset = [n for n in p.notes if n.startswith("subset:")]
            return p.cite() + (f" [{'; '.join(subset)}]" if subset else "")
        if style == "bibtex":
            return p.bibtex(key=f"{self.script_id or 'aegean'}-corpus")
        if style == "apa":
            return p.apa()
        raise ValueError(f"style must be 'plain', 'bibtex', or 'apa'; got {style!r}")

    # ── analysis-friendly views ─────────────────────────────────────────
    def word_frequencies(self) -> list[tuple[str, int]]:
        """(word, count) for every lexical word, sorted by descending count."""
        counter: Counter[str] = Counter()
        for doc in self.documents:
            for tok in doc.tokens:
                if tok.kind is TokenKind.WORD:
                    counter[tok.text] += 1
        return sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))

    # ── interop ─────────────────────────────────────────────────────────
    def to_dataframe(self, level: str = "document"):  # type: ignore[no-untyped-def]
        """A pandas DataFrame at ``document``, ``token``, or ``word`` level.

        pandas is an optional dependency — install with ``pip install 'pyaegean[data]'``."""
        try:
            import pandas as pd  # lazy, optional [data] extra
        except ModuleNotFoundError as exc:
            raise ModuleNotFoundError(
                "to_dataframe() needs pandas; install it with: pip install 'pyaegean[data]'"
            ) from exc

        if level == "document":
            rows = [
                {
                    "id": d.id,
                    "script_id": d.script_id,
                    "site": d.meta.site,
                    "support": d.meta.support,
                    "scribe": d.meta.scribe,
                    "findspot": d.meta.findspot,
                    "period": d.meta.period,
                    "name": d.meta.name,
                    "n_tokens": len(d.tokens),
                    "n_words": len(d.words),
                }
                for d in self.documents
            ]
            return pd.DataFrame(rows)

        if level in ("token", "word"):
            want_word = level == "word"
            rows = [
                {
                    "doc_id": d.id,
                    "line_no": tok.line_no,
                    "position": tok.position,
                    "text": tok.text,
                    "kind": tok.kind.value,
                    "site": d.meta.site,
                    "period": d.meta.period,
                }
                for d in self.documents
                for tok in d.tokens
                if not want_word or tok.kind is TokenKind.WORD
            ]
            return pd.DataFrame(rows)

        raise ValueError(f"level must be 'document', 'token', or 'word'; got {level!r}")

    def to_dict(self) -> dict[str, Any]:
        """A compact, *lossy* export (``_meta`` + per-document words/metadata) for quick
        interop. For a complete, reversible serialization use `to_json`/`from_json`."""
        prov = self.provenance
        return {
            "_meta": {
                "tool": "pyaegean",
                "schemaVersion": SCHEMA_VERSION,
                "scriptId": self.script_id,
                "documentCount": len(self.documents),
                "source": prov.source if prov else "",
                "license": prov.license if prov else "",
                "citation": prov.cite() if prov else "",
            },
            "documents": [
                {
                    "id": d.id,
                    "script_id": d.script_id,
                    "words": [t.text for t in d.words],
                    "glyphs": d.glyphs,
                    "transcription": d.transcription,
                    "translations": d.translations,
                    "meta": {
                        "site": d.meta.site,
                        "support": d.meta.support,
                        "scribe": d.meta.scribe,
                        "findspot": d.meta.findspot,
                        "period": d.meta.period,
                        "name": d.meta.name,
                    },
                }
                for d in self.documents
            ],
        }

    # ── lossless round-trip ──────────────────────────────────────────────
    def to_json(self, path: str | Path | None = None, *, indent: int | None = 2) -> str | None:
        """Serialize the whole corpus to JSON **losslessly** — every token (with its kind,
        signs, glyphs, line/position), the physical lines, full document metadata, the sign
        inventory, and provenance all survive. `from_json` reverses it exactly.

        Returns the JSON string, or writes it to ``path`` and returns ``None`` when ``path``
        is given. (Unlike `to_dict`, which is a compact lossy summary.)"""
        data: dict[str, Any] = {
            "_meta": {"tool": "pyaegean", "schemaVersion": SCHEMA_VERSION, "scriptId": self.script_id},
            "provenance": _provenance_to_dict(self.provenance),
            "signInventory": _inventory_to_dict(self.sign_inventory),
            "documents": [_document_to_dict(d) for d in self.documents],
        }
        text = json.dumps(data, ensure_ascii=False, indent=indent)
        if path is None:
            return text
        Path(path).write_text(text, encoding="utf-8")
        return None

    @classmethod
    def from_json(cls, source: str | Path) -> "Corpus":
        """Reconstruct a Corpus from `to_json` output: a JSON string, a ``Path`` to a
        ``.json`` file, or a path-like string (anything not beginning with ``{``)."""
        if isinstance(source, Path):
            text = source.read_text(encoding="utf-8")
        elif source.lstrip().startswith("{"):
            text = source
        else:
            text = Path(source).read_text(encoding="utf-8")
        return cls.from_dict(json.loads(text))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Corpus":
        """Reconstruct a Corpus from the dict `to_json` serializes (its ``json.loads``)."""
        meta = data.get("_meta") or {}
        return cls(
            [_document_from_dict(d) for d in data.get("documents", [])],
            sign_inventory=_inventory_from_dict(data.get("signInventory")),
            provenance=_provenance_from_dict(data.get("provenance")),
            script_id=meta.get("scriptId", ""),
        )

    # ── compound query ───────────────────────────────────────────────────
    def query(
        self,
        filters: Sequence[FilterRow],
        output: Output = "inscriptions",
        *,
        annotated_ids: set[str] | None = None,
    ) -> QueryResults:
        """Run the compound-query predicate engine over this corpus.

        ``filters`` is a sequence of `aegean.analysis.FilterRow` rows (a field id, a
        value, and optional ``connector``/``negate``); ``output`` selects ``"inscriptions"``
        or ``"words"``. Returns `aegean.analysis.QueryResults` (``.inscriptions`` and
        ``.words``) carrying this corpus's provenance and a summary of the filters,
        so ``results.cite()`` cites the exact result set. The available fields are
        in `aegean.analysis.FIELDS`. Unlike `filter` (exact metadata match), this
        supports text/prefix/sign-pattern/co-occurrence predicates with AND/OR/NOT."""
        from ..analysis.query import run_query  # lazy: no import-time core→analysis edge

        return run_query(self, list(filters), output, annotated_ids)


# ── (de)serialization helpers for the lossless round-trip ──────────────────
def _provenance_to_dict(p: Provenance | None) -> dict[str, Any] | None:
    if p is None:
        return None
    return {
        "source": p.source, "license": p.license, "citation": p.citation,
        "url": p.url, "schema_version": p.schema_version, "notes": list(p.notes),
    }


def _provenance_from_dict(d: dict[str, Any] | None) -> Provenance | None:
    if not d:
        return None
    return Provenance(
        source=d.get("source", ""), license=d.get("license", ""),
        citation=d.get("citation", ""), url=d.get("url", ""),
        schema_version=d.get("schema_version", SCHEMA_VERSION),
        notes=tuple(d.get("notes") or ()),
    )


def _inventory_to_dict(inv: SignInventory | None) -> dict[str, Any] | None:
    if inv is None:
        return None
    return {
        "script_id": inv.script_id,
        "signs": [
            {
                "label": s.label, "glyph": s.glyph, "codepoint": s.codepoint,
                "phonetic": s.phonetic, "script_id": s.script_id, "attrs": s.attrs,
            }
            for s in inv.signs
        ],
    }


def _inventory_from_dict(d: dict[str, Any] | None) -> SignInventory | None:
    if not d:
        return None
    signs = [
        Sign(
            label=s["label"], glyph=s.get("glyph"), codepoint=s.get("codepoint"),
            phonetic=s.get("phonetic"), script_id=s.get("script_id", ""),
            attrs=dict(s.get("attrs") or {}),
        )
        for s in d.get("signs", [])
    ]
    return SignInventory(signs, d.get("script_id", ""))


def _token_to_dict(t: Token) -> dict[str, Any]:
    d: dict[str, Any] = {
        "text": t.text, "kind": t.kind.value, "signs": list(t.signs),
        "glyphs": t.glyphs, "line_no": t.line_no, "position": t.position,
    }
    if t.status is not ReadingStatus.CERTAIN:  # omit the default to keep JSON compact + back-compatible
        d["status"] = t.status.value
    return d


def _token_from_dict(d: dict[str, Any]) -> Token:
    return Token(
        text=d["text"], kind=TokenKind(d["kind"]), signs=tuple(d.get("signs") or ()),
        glyphs=d.get("glyphs"), line_no=d.get("line_no"), position=d.get("position"),
        status=ReadingStatus(d["status"]) if d.get("status") else ReadingStatus.CERTAIN,
    )


def _document_to_dict(d: Document) -> dict[str, Any]:
    return {
        "id": d.id, "script_id": d.script_id, "glyphs": d.glyphs,
        "transcription": d.transcription, "translations": list(d.translations),
        "meta": {
            "site": d.meta.site, "support": d.meta.support, "scribe": d.meta.scribe,
            "findspot": d.meta.findspot, "period": d.meta.period, "name": d.meta.name,
            "images": list(d.meta.images),
        },
        "tokens": [_token_to_dict(t) for t in d.tokens],
        "lines": [list(line) for line in d.lines],
    }


def _document_from_dict(d: dict[str, Any]) -> Document:
    m = d.get("meta") or {}
    meta = DocumentMeta(
        site=m.get("site", ""), support=m.get("support", ""), scribe=m.get("scribe", ""),
        findspot=m.get("findspot", ""), period=m.get("period", ""), name=m.get("name", ""),
        images=tuple(m.get("images") or ()),
    )
    return Document(
        id=d["id"], script_id=d.get("script_id", ""),
        tokens=[_token_from_dict(t) for t in d.get("tokens", [])],
        lines=[list(line) for line in d.get("lines", [])],
        glyphs=d.get("glyphs", ""), transcription=d.get("transcription", ""),
        translations=list(d.get("translations") or []), meta=meta,
    )
