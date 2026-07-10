"""Koine / New Testament evaluation against the Nestle 1904 gold (lemma + UPOS).

A complement to `aegean.greek.proiel`: that scores pyaegean against the PROIEL
treebank's Greek NT (a *different* project's annotation layer); this scores it against
the **Nestle1904 corpus's own gold** lemmas and morphology (``greek.load_nt``). Neither
source is in pyaegean's training data (the models train on AGDT + Gorman + Pedalion), so
both are genuine out-of-domain Koine checks.

The default predictor is the **neural joint pipeline** (``greek.use_neural_pipeline``) —
this fold is meant to report the number a user gets from the shipped model. Following the
same honesty rule as ``proiel`` and ``heldout``: lemma is the clean metric; UPOS is
compared under a reconciled tagset (PROPN→NOUN, SCONJ→CCONJ, AUX→VERB) so the score
measures real disagreement, not Robinson-vs-UD convention gaps. Finer morphological
features are deliberately *not* scored — the Robinson tagset and pyaegean's UD FEATS do
not align feature-for-feature, so a UFeats number here would be a convention artefact, not
an accuracy (see the PROIEL UFeats note in docs/benchmarks.md).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .heldout import HeldoutSplit, HeldoutToken, TagBatch, TagSentence, score
from .proiel import _SKIP_POS, _canon_pos
from .treebank import _clean_lemma

if TYPE_CHECKING:
    from collections.abc import Callable

    from ..core.corpus import Corpus

__all__ = ["evaluate_on_nt"]


def _gold_sentences(corpus: Corpus) -> tuple[tuple[HeldoutToken, ...], ...]:
    """Group an NT corpus's word tokens into per-verse gold sentences (form, lemma, UPOS).

    The form is the normalized (punctuation-stripped) surface, the lemma is the Nestle1904
    gold lemma, and the UPOS is the reconciled Robinson→UD tag already on each token."""
    from ..core.model import TokenKind

    out: list[tuple[HeldoutToken, ...]] = []
    for doc in corpus.documents:
        by_verse: dict[int, list[HeldoutToken]] = {}
        for tok in doc.tokens:
            if tok.kind is not TokenKind.WORD:
                continue
            a = tok.annotations
            form = a.get("normalized") or tok.text
            upos = _canon_pos(a.get("upos", "X"))
            ht = HeldoutToken(
                form=form,
                lemma=_clean_lemma(a.get("lemma", "")),
                upos=upos,
                seen=False,                       # the NT is out-of-domain for the models
                scored=upos not in _SKIP_POS,
            )
            by_verse.setdefault(tok.line_no or 0, []).append(ht)
        for _verse in sorted(by_verse):
            sent = tuple(by_verse[_verse])
            if sent:
                out.append(sent)
    return tuple(out)


def _neural_tagger() -> TagSentence:
    """A TagSentence backed by the neural joint pipeline (one analyze pass per sentence)."""
    from .joint import NeuralPipelineNotLoadedError, active, analyze_sentence

    if active() is None:
        raise NeuralPipelineNotLoadedError(
            "the NT eval defaults to the neural pipeline — call "
            "aegean.greek.use_neural_pipeline() first, or pass your own tag_sentence"
        )

    def tag(forms: list[str]) -> list[tuple[str, str]]:
        a = analyze_sentence(forms)
        return list(zip(a.lemma, a.upos))

    return tag


def _neural_batch_tagger() -> TagBatch:
    """The batched counterpart of `_neural_tagger`: one padded encoder pass per chunk.

    Must produce exactly the per-sentence tagger's predictions — batching is a
    throughput convenience; the published NT numbers use the sequential default."""
    from .joint import analyze_sentences

    def tag(batch: list[list[str]]) -> list[list[tuple[str, str]]]:
        analyses = analyze_sentences(batch, batch_size=max(len(batch), 1))
        return [list(zip(a.lemma, a.upos)) for a in analyses]

    return tag


def evaluate_on_nt(
    tag_sentence: TagSentence | None = None,
    *,
    corpus: Corpus | None = None,
    book: str | None = None,
    progress: Callable[[int, int], None] | None = None,
    batch_size: int | None = None,
) -> dict[str, float]:
    """Score a tagger on the Nestle1904 Greek NT gold — lemma + reconciled UPOS accuracy.

    ``tag_sentence`` maps a sentence's forms to ``(lemma, upos)`` per token; it defaults to
    the **neural joint pipeline** (enable ``greek.use_neural_pipeline()`` first), so the
    number reflects the shipped model. ``corpus`` supplies the gold (defaults to
    ``greek.load_nt(book)`` — the whole NT, or one ``book``). ``progress`` (optional) is
    called as ``progress(done, total)`` per scored verse — the whole-NT run is ~1 h on
    plain CPU, so this is how the CLI shows it moving. ``batch_size`` (optional) runs the
    default neural tagger's encoder over that many verses at a time (one ONNX call per
    chunk) — a throughput convenience; the recorded protocol (the published numbers) is
    the sequential default, and with a caller-supplied ``tag_sentence`` the value has no
    effect. Returns ``{"lemma", "upos", "n"}``: accuracy over the scored tokens. Lemma is
    the clean metric; UPOS is compared under a reconciled tagset, mirroring
    ``evaluate_on_proiel``."""
    if corpus is None:
        from ..scripts.greek.nt import load_nt

        corpus = load_nt(book)
    split = HeldoutSplit(
        sentences=_gold_sentences(corpus),
        train_forms=frozenset(),
        train_lemma={},
        train_pos={},
    )
    base: TagSentence = tag_sentence if tag_sentence is not None else _neural_tagger()

    def reconciled(forms: list[str]) -> list[tuple[str, str]]:
        return [(lemma, _canon_pos(pos)) for lemma, pos in base(forms)]

    tag_batch: TagBatch | None = None
    if batch_size is not None and tag_sentence is None:
        raw_batch = _neural_batch_tagger()

        def _reconciled_batch(batch: list[list[str]]) -> list[list[tuple[str, str]]]:
            return [
                [(lemma, _canon_pos(pos)) for lemma, pos in sent] for sent in raw_batch(batch)
            ]

        tag_batch = _reconciled_batch

    result = score(
        reconciled, split=split, progress=progress, batch_size=batch_size, tag_batch=tag_batch
    )
    return {"lemma": result["lemma_all"], "upos": result["pos_all"], "n": result["n_all"]}
