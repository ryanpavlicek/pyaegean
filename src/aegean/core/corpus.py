"""The `Corpus` — the package's center of gravity.

Clean, typed, pandas-friendly access to a collection of documents. A loader
registry lets each script provide its bundled corpus without the core
importing the script (no cycles).
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .._log import get_logger
from .model import (
    Document,
    DocumentMeta,
    ReadingStatus,
    Sign,
    SignInventory,
    SourceAlignment,
    Token,
    TokenFormState,
    TokenKind,
)
from .provenance import SCHEMA_VERSION, Provenance

if TYPE_CHECKING:  # type-only: keep the L1 core free of an import-time dependency on L3 analysis
    from ..analysis.query import FilterRow, Output, QueryResults
    from .diagnose import DiagnoseReport

_LOG = get_logger("core")
_LOADERS: dict[str, Callable[[], "Corpus"]] = {}


def register_loader(script_id: str, fn: Callable[[], "Corpus"]) -> None:
    """Register a corpus loader so ``Corpus.load(script_id)`` / ``aegean.load(script_id)`` works."""
    _LOADERS[script_id] = fn


def _merged_provenance(corpora: "list[Corpus]", n_docs: int) -> Provenance:
    """A fresh provenance for a merged corpus that names every input, so `cite` stays truthful."""
    sources = [
        (c.provenance.citation or c.provenance.source)
        if c.provenance is not None
        else (c.script_id or "unnamed corpus")
        for c in corpora
    ]
    licenses = sorted(
        {c.provenance.license for c in corpora if c.provenance and c.provenance.license}
    )
    # edition_fidelity survives a merge only when every input agrees on one non-empty
    # value; a mixed or partly-unknown merge honestly reports "" (unknown), never a
    # single corpus's flag stretched over the others' text.
    fidelities = {
        c.provenance.edition_fidelity if c.provenance is not None else "" for c in corpora
    }
    fidelity = fidelities.pop() if len(fidelities) == 1 else ""
    return Provenance(
        source="Merged corpus (aegean.combine)",
        license="; ".join(licenses) or "mixed",
        citation="Merged corpus of: " + "; ".join(sources),
        notes=(f"merged: {len(corpora)} corpora → {n_docs} documents",),
        edition_fidelity=fidelity,
    )


class Corpus:
    """A collection of `Document` s plus shared inventory + provenance."""

    def __init__(
        self,
        documents: list[Document],
        sign_inventory: SignInventory | None = None,
        provenance: Provenance | None = None,
        script_id: str = "",
    ) -> None:
        docs = list(documents)
        by_id = {d.id: d for d in docs}
        if len(by_id) != len(docs):
            # Duplicate document ids: collapse to one per id (keeping the last — what `.get()`
            # already returned) so .documents, len(), iteration, fingerprint, and the id lookup
            # all agree. A corpus can't hold two documents with the same id. Warn rather than
            # drop silently: a duplicate id is a data problem worth surfacing.
            import warnings

            seen: set[str] = set()
            dupes: list[str] = []
            for d in docs:
                if d.id in seen:
                    dupes.append(d.id)
                else:
                    seen.add(d.id)
            uniq = sorted(set(dupes))
            shown = ", ".join(uniq[:5]) + (f" (+{len(uniq) - 5} more)" if len(uniq) > 5 else "")
            warnings.warn(
                f"Corpus: collapsed {len(docs) - len(by_id)} duplicate document id(s), "
                f"keeping the last of each: {shown}",
                stacklevel=2,
            )
            docs = list(by_id.values())
        self.documents = docs
        self.sign_inventory = sign_inventory
        self.provenance = provenance
        self.script_id = script_id
        self._by_id = by_id

    # ── construction ────────────────────────────────────────────────────
    @classmethod
    def load(cls, script_id: str, *, version: str | None = None) -> "Corpus":
        """Load a registered corpus by name, e.g. ``Corpus.load("lineara")`` (bundled)
        or ``Corpus.load("damos")`` (fetched to the local data store on first use).

        Loaders may cache one built instance per process (the bundled corpora do),
        so the result is returned as a `copy`: mutate it freely, and documents
        added, dropped, or edited never leak into later ``load`` calls.

        ``version`` (optional) loads a kept **historical** release of a fetched corpus
        that the project still hosts, for reproducing an earlier analysis byte-for-byte
        (e.g. ``version="v1"`` for a pre-0.29.0 epigraphy corpus). It applies only to
        the corpora with kept historical pins (``isicily``, ``iip``, ``iospe``,
        ``igcyr``, ``edh``, ``ddbdp``; see `aegean.data.historical_versions`) and
        fetches into a separate version-suffixed cache entry, leaving the current data
        untouched. The default (``version=None``) is unchanged."""
        if version is not None:
            from ..data import load_corpus_version

            _LOG.info("loading corpus %r version %s", script_id, version)
            return load_corpus_version(script_id, version)
        fn = _LOADERS.get(script_id)
        if fn is None:
            # Forgive case as a last resort, so ``load("LINEARA")`` finds ``lineara`` —
            # mirroring read_corpus, so the primary Python entry point behaves like its
            # flexible sibling rather than raising a bare KeyError.
            by_fold = {k.casefold(): k for k in _LOADERS}
            hit = by_fold.get(script_id.casefold())
            if hit is not None:
                fn = _LOADERS[hit]
                script_id = hit
            else:
                from .resolve import suggest

                close = suggest(script_id, sorted(_LOADERS), n=2)
                lead = f"no registered corpus {script_id!r}"
                if close:
                    lead += f" — did you mean {' or '.join(repr(m) for m in close)}?"
                    lead += " available"
                else:
                    lead += "; available"
                raise KeyError(f"{lead}: {sorted(_LOADERS)}") from None
        _LOG.info("loading corpus %r", script_id)
        corpus = fn().copy()
        _LOG.info("loaded corpus %r (%d documents)", script_id, len(corpus))
        return corpus

    # ── access ──────────────────────────────────────────────────────────
    def __len__(self) -> int:
        return len(self.documents)

    def __iter__(self) -> Iterator[Document]:
        return iter(self.documents)

    def get(self, doc_id: str) -> Document | None:
        """The document with id ``doc_id``, or ``None`` if there is no such document."""
        return self._by_id.get(doc_id)

    def fingerprint(self) -> str:
        """A stable content hash of this corpus, covering everything a token-level
        analysis can see: the script id, the provenance ``data_version``, each
        document's id, every token's text, `TokenKind`, `ReadingStatus`, decomposed
        ``signs``, Unicode ``glyphs``, alternate readings (``alt``), and annotations
        (hashed as sorted key/value pairs), and any ``subset:`` / ``merged:`` /
        ``appended:`` provenance note. Document metadata (site, period, ...) is
        deliberately excluded. Cheap relative to the analyses it keys: one pass over
        the tokens, no model build. Two corpora with the same fingerprint have the
        same analysable content, so it's the cache key for `aegean.cache`-memoised
        analyses (including the sign-level dispersion/keyness that read ``signs``)."""
        h = hashlib.sha256()

        def field(value: str) -> None:
            # Length-prefix every variable-length field so the serialization is injective:
            # a separator-byte scheme collides if the data itself contains the separator
            # (a control char in a doc id, sign label, or annotation value).
            b = value.encode("utf-8")
            h.update(len(b).to_bytes(8, "big"))
            h.update(b)

        def count(n: int) -> None:
            h.update(n.to_bytes(8, "big"))

        field(self.script_id or "")
        field(
            self.provenance.data_version
            if self.provenance is not None and self.provenance.data_version
            else ""
        )
        count(len(self.documents))
        for d in self.documents:
            field(d.id)
            count(len(d.tokens))
            for t in d.tokens:
                field(t.text)
                field(t.kind.value)
                field(t.status.value)
                # signs / glyphs / alt are independent stored fields an analysis reads
                # (sign-level dispersion & keyness key on `signs`), so they vary the hash.
                field(t.glyphs or "")
                count(len(t.signs))
                for s in t.signs:
                    field(s)
                count(len(t.alt))
                for alt_value in t.alt:
                    field(alt_value)
                count(len(t.annotations))
                for k in sorted(t.annotations):
                    field(k)
                    field(str(t.annotations[k]))
            # Keep the pre-A4 fingerprint byte-for-byte identical for corpora with
            # no alignment.  Once a source snapshot or token mapping is present,
            # append a clearly framed block so cache keys distinguish source edits,
            # normalization changes, and token identity changes.
            if d.source_text is not None or any(t.alignment is not None for t in d.tokens):
                field("A4-source-alignment")
                field("present" if d.source_text is not None else "absent")
                field(d.source_text or "")
                count(len(d.tokens))
                for t in d.tokens:
                    alignment = t.alignment
                    field("aligned" if alignment is not None else "unaligned")
                    if alignment is None:
                        continue
                    field(alignment.document_id)
                    field(alignment.sentence_id or "")
                    field(alignment.source_token_id)
                    field(alignment.original_text)
                    field(str(alignment.start_char))
                    field(str(alignment.end_char))
                    field(alignment.whitespace_before)
                    field(alignment.normalized_text)
                    count(len(alignment.normalization_ops))
                    for op in alignment.normalization_ops:
                        field(op)
        # A6 form state is additive: leave the byte stream exactly as it was for
        # legacy corpora with no state, but frame a deterministic block whenever at
        # least one token carries one so state cannot collide with an unannotated cache.
        if any(t.form_state is not None for d in self.documents for t in d.tokens):
            field("A6-token-form-state")
            for d in self.documents:
                for t in d.tokens:
                    state = t.form_state
                    field("present" if state is not None else "absent")
                    if state is None:
                        continue
                    field(state.diplomatic)
                    field("present" if state.regularized is not None else "absent")
                    field(state.regularized or "")
                    field("present" if state.normalized is not None else "absent")
                    field(state.normalized or "")
                    field("present" if state.model_input is not None else "absent")
                    field(state.model_input or "")
                    field(state.model_input_source or "")
                    count(len(state.model_input_ops))
                    for op in state.model_input_ops:
                        field(op)
                    count(len(state.segments))
                    for segment in state.segments:
                        field(segment.text)
                        field(segment.status.value)
                        ref = segment.source_ref
                        field("present" if ref is not None else "absent")
                        if ref is None:
                            continue
                        field(ref.source_id)
                        field(ref.path)
                        field(ref.tag)
                        count(len(ref.attrs))
                        for key, value in ref.attrs:
                            field(key)
                            field(value)
        notes = [
            n
            for n in (self.provenance.notes if self.provenance is not None else ())
            if n.startswith(("subset:", "merged:", "appended:"))
        ]
        count(len(notes))
        for n in notes:
            field(n)
        return h.hexdigest()

    def cache_key(self) -> str:
        """Alias for `fingerprint`, the protocol `aegean.cache` keys on."""
        return self.fingerprint()

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

    def copy(self) -> "Corpus":
        """A structurally independent copy: a fresh document list and, per document,
        fresh token/line/translation containers, so mutating the copy (or the
        original) never affects the other. `Token` and `Sign` are frozen value
        objects but each carries a mutable per-element dict (`annotations` /
        `attrs`) for user analysis, so the copy rebuilds those with independent
        dicts, keeping a per-token annotation edit (or a per-sign attr edit) from
        leaking into the original, a sibling copy, or a later `load` of the same
        cached corpus. The remaining fields (`DocumentMeta`, `Provenance`, the
        immutable Token/Sign scalars) are shared. One pass over the tokens — a
        fraction of a second even for the largest corpora (the annotation-rich NT
        is the slowest); the copy fingerprints identically to the original."""
        docs = [
            Document(
                id=d.id, script_id=d.script_id,
                tokens=[replace(t, annotations=dict(t.annotations)) for t in d.tokens],
                lines=[list(line) for line in d.lines],
                glyphs=d.glyphs, transcription=d.transcription,
                translations=list(d.translations),
                meta=d.meta,
                source_text=d.source_text,
            )
            for d in self.documents
        ]
        inv = self.sign_inventory
        if inv is not None:
            signs = [replace(s, attrs=dict(s.attrs)) for s in inv.signs]
            inv = SignInventory(signs, inv.script_id)
        return Corpus(docs, inv, self.provenance, self.script_id)

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

    def subset(self, ids: Iterable[str]) -> "Corpus":
        """A new Corpus of just the documents whose id is in ``ids`` (original order kept).

        The id-based counterpart to `filter`; records a ``subset:`` provenance note so `cite`
        on the result names the slice."""
        wanted = set(ids)
        docs = [d for d in self.documents if d.id in wanted]
        prov = self.provenance
        if prov is not None:
            note = f"subset: {len(docs)} of {len(self.documents)} documents by id"
            prov = replace(prov, notes=prov.notes + (note,))
        return Corpus(docs, self.sign_inventory, prov, self.script_id)

    def merge(self, *others: "Corpus", dedupe: str = "error") -> "Corpus":
        """Merge this corpus with ``others`` into one (documents concatenated in order).

        ``dedupe`` controls duplicate document ids across the inputs: ``"error"`` (raise,
        listing the collisions — the safe default), ``"first"`` / ``"last"`` (keep that
        occurrence), or ``"suffix"`` (rename later collisions ``id#2``, ``id#3``, …). The
        merged ``script_id`` is the common value, or ``"mixed"`` when the inputs differ; the
        sign inventory is the first input's when scripts agree, else ``None``. A fresh
        provenance names every source, so `cite` on the result stays truthful.

        See also `aegean.combine`, the module-level form that takes a list."""
        if dedupe not in ("error", "first", "last", "suffix"):
            raise ValueError("dedupe must be 'error', 'first', 'last', or 'suffix'")
        corpora = [self, *others]
        out: list[Document] = []
        at: dict[str, int] = {}
        seen_count: dict[str, int] = {}
        collisions: list[str] = []
        for c in corpora:
            for d in c.documents:
                if d.id not in at:
                    at[d.id] = len(out)
                    seen_count[d.id] = 1
                    out.append(d)
                    continue
                collisions.append(d.id)
                if dedupe == "first":
                    continue
                if dedupe == "last":
                    out[at[d.id]] = d
                elif dedupe == "suffix":
                    seen_count[d.id] += 1
                    renamed = replace(d, id=f"{d.id}#{seen_count[d.id]}")
                    at[renamed.id] = len(out)
                    out.append(renamed)
        if dedupe == "error" and collisions:
            uniq = sorted(set(collisions))
            shown = ", ".join(uniq[:10]) + (f" (+{len(uniq) - 10} more)" if len(uniq) > 10 else "")
            raise ValueError(
                f"duplicate document ids across corpora: {shown}; "
                "pass dedupe='first', 'last', or 'suffix'"
            )
        scripts = {c.script_id for c in corpora}
        script_id = next(iter(scripts)) if len(scripts) == 1 else "mixed"
        inventory = (
            next((c.sign_inventory for c in corpora if c.sign_inventory is not None), None)
            if script_id != "mixed"
            else None
        )
        return Corpus(out, inventory, _merged_provenance(corpora, len(out)), script_id)

    def cite(self, style: str = "plain") -> str:
        """Cite this corpus — or the exact filtered subset — in one call.

        ``style``: ``"plain"`` (one line), ``"bibtex"`` (a ``@misc`` entry), or
        ``"apa"``. Filtered subsets (see `filter`) carry a ``subset:`` note that
        all three styles include, so the citation states exactly what was used."""
        if self.provenance is None:
            raise ValueError("this corpus carries no provenance to cite")
        p = self.provenance
        if style == "plain":
            notes = [n for n in p.notes if n.startswith(("subset:", "merged:", "appended:"))]
            return p.cite() + (f" [{'; '.join(notes)}]" if notes else "")
        if style == "bibtex":
            return p.bibtex(key=f"{self.script_id or 'aegean'}-corpus")
        if style == "apa":
            return p.apa()
        raise ValueError(f"style must be 'plain', 'bibtex', or 'apa'; got {style!r}")

    # ── streaming views (memory-friendly over large corpora) ────────────
    def iter_documents(self) -> Iterator[Document]:
        """Iterate documents (the explicit-name form of ``iter(corpus)``)."""
        return iter(self.documents)

    def iter_tokens(self) -> Iterator[Token]:
        """Every `Token`, in document then in-document order — a memory-friendly
        stream that never builds an all-tokens list (useful on a large corpus)."""
        for doc in self.documents:
            yield from doc.tokens

    def iter_words(self) -> Iterator[str]:
        """Every lexical (`WORD`) token's text, in order, lazily. The unit
        `word_frequencies` counts — stream it to feed your own ``Counter`` or a
        running statistic without materialising a list."""
        for doc in self.documents:
            for tok in doc.tokens:
                if tok.kind is TokenKind.WORD:
                    yield tok.text

    # ── analysis-friendly views ─────────────────────────────────────────
    def word_frequencies(self) -> list[tuple[str, int]]:
        """(word, count) for every lexical word, sorted by descending count."""
        counter: Counter[str] = Counter(self.iter_words())
        return sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))

    # ── health report ────────────────────────────────────────────────────
    def diagnose(self, level: str = "quick") -> "DiagnoseReport":
        """A descriptive corpus-health report: reading-status profile, provenance /
        citation completeness, Aegean accounting reconciliation, numeral anomalies,
        annotation review state, and (``level="full"``) sign-frequency outliers.

        Composes existing public machinery into one `aegean.core.diagnose.DiagnoseReport`
        (``.print()`` / ``.to_markdown()`` / ``.to_dataframe()``); every check degrades
        gracefully on a corpus it does not apply to. Descriptive, not a verdict."""
        from .diagnose import diagnose

        return diagnose(self, level)

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
            token_rows: list[dict[str, Any]] = [
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
                    "source_text": d.source_text,
                }
                for d in self.documents
            ]
            return pd.DataFrame(token_rows)

        if level in ("token", "word"):
            want_word = level == "word"
            rows = [
                {
                    # token annotations (lemma/morph/strongs/gloss for the Greek NT, etc.)
                    # spread first so the canonical columns below always win on a name clash.
                    **tok.annotations,
                    # A6 canonical form-state columns.  These are written after arbitrary
                    # annotations deliberately: user metadata cannot spoof the typed values.
                    "form_diplomatic": (
                        tok.form_state.diplomatic if tok.form_state is not None else None
                    ),
                    "form_regularized": (
                        tok.form_state.regularized if tok.form_state is not None else None
                    ),
                    "form_normalized": (
                        tok.form_state.normalized if tok.form_state is not None else None
                    ),
                    "form_model_input": (
                        tok.form_state.model_input if tok.form_state is not None else None
                    ),
                    "form_model_input_ops": (
                        tok.form_state.model_input_ops if tok.form_state is not None else None
                    ),
                    "form_model_input_source": (
                        tok.form_state.model_input_source if tok.form_state is not None else None
                    ),
                    "form_segments": (
                        json.dumps(
                            [segment.to_dict() for segment in tok.form_state.segments],
                            ensure_ascii=False,
                            separators=(",", ":"),
                        )
                        if tok.form_state is not None
                        else None
                    ),
                    "form_editorial_status": (
                        tok.form_state.editorial_status.value
                        if tok.form_state is not None
                        else None
                    ),
                    "form_supplied_text": (
                        tok.form_state.supplied_text if tok.form_state is not None else None
                    ),
                    "form_unclear_text": (
                        tok.form_state.unclear_text if tok.form_state is not None else None
                    ),
                    "form_lost_text": (
                        tok.form_state.lost_text if tok.form_state is not None else None
                    ),
                    "form_supplied": (
                        tok.form_state.supplied if tok.form_state is not None else None
                    ),
                    "form_unclear": (
                        tok.form_state.unclear if tok.form_state is not None else None
                    ),
                    "form_lost": (
                        tok.form_state.lost if tok.form_state is not None else None
                    ),
                    "form_has_damage": (
                        tok.form_state.has_damage if tok.form_state is not None else None
                    ),
                    "form_has_uncertainty": (
                        tok.form_state.has_uncertainty if tok.form_state is not None else None
                    ),
                    "doc_id": d.id,
                    "line_no": tok.line_no,
                    "position": tok.position,
                    "text": tok.text,
                    "kind": tok.kind.value,
                    # the editorial reading status (CERTAIN/UNCLEAR/RESTORED/LOST): without
                    # it, a spreadsheet of an epigraphic corpus could not tell a restored
                    # reading from a securely-read one
                    "status": tok.status.value,
                    "site": d.meta.site,
                    "period": d.meta.period,
                    "alignment_document_id": (
                        tok.alignment.document_id if tok.alignment is not None else None
                    ),
                    "alignment_sentence_id": (
                        tok.alignment.sentence_id if tok.alignment is not None else None
                    ),
                    "alignment_source_token_id": (
                        tok.alignment.source_token_id if tok.alignment is not None else None
                    ),
                    "alignment_original_text": (
                        tok.alignment.original_text if tok.alignment is not None else None
                    ),
                    "alignment_start_char": (
                        tok.alignment.start_char if tok.alignment is not None else None
                    ),
                    "alignment_end_char": (
                        tok.alignment.end_char if tok.alignment is not None else None
                    ),
                    "alignment_whitespace_before": (
                        tok.alignment.whitespace_before if tok.alignment is not None else None
                    ),
                    "alignment_normalized_text": (
                        tok.alignment.normalized_text if tok.alignment is not None else None
                    ),
                    "alignment_normalization_ops": (
                        tok.alignment.normalization_ops if tok.alignment is not None else None
                    ),
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
        from .._atomic import atomic_path  # temp+replace: a failed write keeps the prior export

        with atomic_path(path) as tmp:
            tmp.write_text(text, encoding="utf-8")
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
    def from_records(
        cls,
        records: Sequence[dict[str, Any]],
        *,
        script_id: str = "custom",
        provenance: Provenance | None = None,
        sign_inventory: SignInventory | None = None,
    ) -> "Corpus":
        """Build a corpus from plain dict records — your own inscriptions get the
        full API (filter, query, DataFrames, citation, export).

        Each record needs an ``"id"`` and its text as one of:

        - ``"lines"``: a list of physical lines, each a list of tokens;
        - ``"words"``: a flat token list (treated as one line);
        - ``"text"``: a whitespace-tokenized string (one line).

        A token is a string, or a dict ``{"text": …}`` with optional ``"kind"``
        (a `TokenKind` value; inferred when omitted — numerals by parseability,
        the rest words), ``"status"`` (a `ReadingStatus` value), and ``"alt"``
        (alternate readings). Hyphenated tokens get their ``signs`` split.
        Optional record keys: ``"meta"`` (site/period/scribe/support/findspot/
        name), ``"translations"``. Example::

            corpus = Corpus.from_records([
                {"id": "X1", "text": "KU-RO 10", "meta": {"site": "My site"}},
                {"id": "X2", "lines": [["A-DU", {"text": "5", "status": "unclear"}]]},
            ], script_id="lineara")

        To make it loadable by name, register a loader:
        ``aegean.core.corpus.register_loader("myfind", lambda: corpus)``."""
        from .numerals import parse_value

        docs: list[Document] = []
        for rec in records:
            if "id" not in rec:
                raise ValueError(f"record missing 'id': {rec!r}")
            if "lines" in rec:
                raw_lines = [list(line) for line in rec["lines"]]
            elif "words" in rec:
                raw_lines = [list(rec["words"])]
            elif "text" in rec:
                raw_lines = [str(rec["text"]).split()]
            else:
                raise ValueError(f"record {rec['id']!r} needs 'lines', 'words', or 'text'")
            tokens: list[Token] = []
            lines: list[list[int]] = []
            pos = 0
            for line_no, raw in enumerate(raw_lines):
                idxs: list[int] = []
                for item in raw:
                    spec = item if isinstance(item, dict) else {"text": item}
                    text = str(spec["text"])
                    kind = (
                        TokenKind(spec["kind"])
                        if "kind" in spec
                        else (TokenKind.NUMERAL if parse_value(text) is not None else TokenKind.WORD)
                    )
                    tokens.append(
                        Token(
                            text=text, kind=kind,
                            signs=tuple(text.split("-")) if "-" in text else (),
                            line_no=line_no, position=pos,
                            status=ReadingStatus(spec.get("status", "certain")),
                            alt=tuple(spec.get("alt") or ()),
                        )
                    )
                    idxs.append(pos)
                    pos += 1
                lines.append(idxs)
            m = rec.get("meta") or {}
            docs.append(
                Document(
                    id=str(rec["id"]), script_id=script_id, tokens=tokens, lines=lines,
                    translations=list(rec.get("translations") or []),
                    meta=DocumentMeta(
                        site=m.get("site", ""), support=m.get("support", ""),
                        scribe=m.get("scribe", ""), findspot=m.get("findspot", ""),
                        period=m.get("period", ""), name=m.get("name", ""),
                    ),
                )
            )
        prov = provenance or Provenance(
            source="User-supplied corpus (Corpus.from_records)",
            license="user-supplied",
        )
        return cls(docs, sign_inventory, prov, script_id)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Corpus":
        """Reconstruct a Corpus from the dict `to_json` serializes (its ``json.loads``).

        Raises ``ValueError`` when the file records a schema version newer than this
        release understands (a file from a future pyaegean), naming the fix; a missing
        or older version loads normally."""
        meta = data.get("_meta") or {}
        stored = meta.get("schemaVersion")
        if isinstance(stored, int) and stored > SCHEMA_VERSION:
            raise ValueError(
                f"this corpus file uses schema version {stored}, but this pyaegean "
                f"understands up to {SCHEMA_VERSION} — upgrade pyaegean to read it"
            )
        # Form state was introduced in schema 3.  A schema-1/2 artifact may carry
        # unrelated future-looking keys, but an older writer cannot establish the
        # A6 contract, so those values are intentionally ignored.
        allow_form_state = isinstance(stored, int) and stored >= 3
        return cls(
            [_document_from_dict(d, allow_form_state=allow_form_state) for d in data.get("documents", [])],
            sign_inventory=_inventory_from_dict(data.get("signInventory")),
            provenance=_provenance_from_dict(data.get("provenance")),
            script_id=meta.get("scriptId", ""),
        )

    # ── SQLite persistence ───────────────────────────────────────────────
    def to_sql(self, path: str | Path, *, fts: bool = True, append: bool = False) -> None:
        """Write this corpus to a SQLite database (stdlib only). Documents and tokens
        become queryable rows with an optional FTS5 text index; provenance round-trips.
        With ``append=True`` the documents are upserted into an existing database (by id)
        instead of overwriting it. Reload with `Corpus.from_sql`; search with `aegean.db.search`."""
        from ..db import to_sqlite

        to_sqlite(self, path, fts=fts, append=append)

    @classmethod
    def from_sql(cls, path: str | Path) -> "Corpus":
        """Reconstruct a Corpus from a SQLite database written by `to_sql` — the lossless
        counterpart to `from_json`. For huge databases, `aegean.db.stream` yields documents
        one at a time instead of loading them all."""
        from ..db import from_sqlite

        return from_sqlite(path)

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
        so ``results.cite()`` cites the exact result set. In ``.words`` each count is
        the word's **document frequency** (how many distinct inscriptions it occurs
        in), not its token frequency; for token counts use `word_frequencies`. The
        available fields are
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
        "data_version": p.data_version, "edition_fidelity": p.edition_fidelity,
    }


def _provenance_from_dict(d: dict[str, Any] | None) -> Provenance | None:
    if not d:
        return None
    return Provenance(
        source=d.get("source", ""), license=d.get("license", ""),
        citation=d.get("citation", ""), url=d.get("url", ""),
        schema_version=d.get("schema_version", SCHEMA_VERSION),
        notes=tuple(d.get("notes") or ()),
        data_version=d.get("data_version", ""),
        edition_fidelity=d.get("edition_fidelity", ""),
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
    if t.alt:
        d["alt"] = list(t.alt)
    if t.annotations:
        d["annotations"] = dict(t.annotations)
    if t.alignment is not None:
        d["alignment"] = _alignment_to_dict(t.alignment)
    if t.form_state is not None:
        if not isinstance(t.form_state, TokenFormState):
            raise TypeError("token form_state must be a TokenFormState or None")
        d["form_state"] = t.form_state.to_dict()
    return d


def _token_from_dict(
    d: dict[str, Any], *, allow_form_state: bool = True, context: str = "token"
) -> Token:
    raw_alignment = d.get("alignment")
    if raw_alignment is None:
        alignment = None
    elif isinstance(raw_alignment, SourceAlignment):
        # SQLite reconstruction already has a validated typed value.  Reusing it
        # keeps this central decoder the single validation seam.
        alignment = raw_alignment
    elif isinstance(raw_alignment, dict):
        alignment = _alignment_from_dict(raw_alignment)
    else:
        raise TypeError("token alignment must be an object or SourceAlignment")
    raw_form_state = d.get("form_state") if allow_form_state else None
    if raw_form_state is None:
        form_state = None
    elif isinstance(raw_form_state, TokenFormState):
        form_state = raw_form_state
    elif isinstance(raw_form_state, dict):
        try:
            form_state = TokenFormState.from_dict(raw_form_state)
        except (TypeError, ValueError, KeyError) as exc:
            raise ValueError(f"malformed token form_state in {context}: {exc}") from exc
    else:
        raise TypeError(f"malformed token form_state in {context}: expected an object")
    return Token(
        text=d["text"], kind=TokenKind(d["kind"]), signs=tuple(d.get("signs") or ()),
        glyphs=d.get("glyphs"), line_no=d.get("line_no"), position=d.get("position"),
        status=ReadingStatus(d["status"]) if d.get("status") else ReadingStatus.CERTAIN,
        alt=tuple(d.get("alt") or ()),
        annotations=dict(d.get("annotations") or {}),
        alignment=alignment,
        form_state=form_state,
    )


def _alignment_to_dict(a: SourceAlignment) -> dict[str, Any]:
    """Serialize a typed alignment value without exposing dataclass internals."""
    return {
        "document_id": a.document_id,
        "sentence_id": a.sentence_id,
        "source_token_id": a.source_token_id,
        "original_text": a.original_text,
        "start_char": a.start_char,
        "end_char": a.end_char,
        "whitespace_before": a.whitespace_before,
        "normalized_text": a.normalized_text,
        "normalization_ops": list(a.normalization_ops),
    }


def _alignment_from_dict(d: dict[str, Any]) -> SourceAlignment:
    """Deserialize one alignment object, retaining strict constructor checks."""
    if not isinstance(d, dict):
        raise TypeError("token alignment must be an object")
    raw_ops = d.get("normalization_ops")
    if raw_ops is not None and not isinstance(raw_ops, (list, tuple)):
        raise TypeError("normalization_ops must be a JSON array")
    start_char = d.get("start_char")
    end_char = d.get("end_char")
    if not isinstance(start_char, int) or isinstance(start_char, bool):
        raise TypeError("start_char must be an integer")
    if not isinstance(end_char, int) or isinstance(end_char, bool):
        raise TypeError("end_char must be an integer")
    return SourceAlignment(
        document_id=d.get("document_id", ""),
        sentence_id=d.get("sentence_id"),
        source_token_id=d.get("source_token_id", ""),
        original_text=d.get("original_text", ""),
        start_char=start_char,
        end_char=end_char,
        whitespace_before=d.get("whitespace_before", ""),
        normalized_text=d.get("normalized_text", ""),
        normalization_ops=tuple(raw_ops or ()),
    )


def _document_to_dict(d: Document) -> dict[str, Any]:
    # Persistence is a trust boundary: never serialize a source snapshot whose
    # token spans, gaps, or identities are internally inconsistent.
    d.validate_source_alignment()
    return {
        "id": d.id, "script_id": d.script_id, "glyphs": d.glyphs,
        "transcription": d.transcription, "translations": list(d.translations),
        "meta": {
            "site": d.meta.site, "support": d.meta.support, "scribe": d.meta.scribe,
            "findspot": d.meta.findspot, "period": d.meta.period, "name": d.meta.name,
            "images": list(d.meta.images), "notes": list(d.meta.notes),
        },
        "tokens": [_token_to_dict(t) for t in d.tokens],
        "lines": [list(line) for line in d.lines],
        "source_text": d.source_text,
    }


def _document_from_dict(d: dict[str, Any], *, allow_form_state: bool = True) -> Document:
    m = d.get("meta") or {}
    meta = DocumentMeta(
        site=m.get("site", ""), support=m.get("support", ""), scribe=m.get("scribe", ""),
        findspot=m.get("findspot", ""), period=m.get("period", ""), name=m.get("name", ""),
        images=tuple(m.get("images") or ()), notes=tuple(m.get("notes") or ()),
    )
    document_id = d.get("id", "?")
    tokens = [
        _token_from_dict(
            t,
            allow_form_state=allow_form_state,
            context=f"document {document_id!r}, token {i}",
        )
        for i, t in enumerate(d.get("tokens", []))
    ]
    source_text = d.get("source_text")
    if source_text is not None and not isinstance(source_text, str):
        raise TypeError("document source_text must be a string or None")
    document_id = d["id"]
    for token in tokens:
        if token.alignment is None:
            continue
        if token.alignment.document_id != document_id:
            raise ValueError(
                f"document {document_id!r}: token alignment belongs to "
                f"document {token.alignment.document_id!r}"
            )
        if source_text is not None:
            token.alignment.validate_source(source_text, document_id=document_id)
    lines = [list(line) for line in d.get("lines", [])]
    # Validate the line index lists against the token count up front: an out-of-range index
    # (a corpus file whose lines got out of sync with tokens) otherwise loads fine and then
    # crashes with a bare IndexError at a much later, unrelated call (line_tokens, _repr_html_,
    # an EpiDoc/workbench export). Fail here with a message that names the malformed source.
    n = len(tokens)
    for li, line in enumerate(lines):
        for i in line:
            if not isinstance(i, int) or isinstance(i, bool) or i < 0 or i >= n:
                raise ValueError(
                    f"document {d.get('id', '?')!r}: line {li} references token index {i!r}, "
                    f"but the document has {n} token(s); the source is malformed"
                )
    document = Document(
        id=d["id"], script_id=d.get("script_id", ""),
        tokens=tokens, lines=lines,
        glyphs=d.get("glyphs", ""), transcription=d.get("transcription", ""),
        translations=list(d.get("translations") or []), meta=meta,
        source_text=source_text,
    )
    document.validate_source_alignment()
    return document
