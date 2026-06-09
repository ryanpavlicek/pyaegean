"""The :class:`Corpus` — the package's center of gravity.

Clean, typed, pandas-friendly access to a collection of documents. A loader
registry lets each script provide its bundled corpus without the core
importing the script (no cycles).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterator
from typing import Any

from .model import Document, SignInventory, TokenKind
from .provenance import SCHEMA_VERSION, Provenance

_LOADERS: dict[str, Callable[[], "Corpus"]] = {}


def register_loader(script_id: str, fn: Callable[[], "Corpus"]) -> None:
    _LOADERS[script_id] = fn


class Corpus:
    """A collection of :class:`Document` s plus shared inventory + provenance."""

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
        (AND-combination), e.g. ``corpus.filter(site="HT", period="LMIB")``."""

        def ok(d: Document) -> bool:
            return all(getattr(d.meta, k, None) == v for k, v in meta.items())

        return Corpus(
            [d for d in self.documents if ok(d)],
            self.sign_inventory,
            self.provenance,
            self.script_id,
        )

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
        """The canonical versioned export (``_meta`` + documents)."""
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
