"""Error analysis for the Greek tagger/lemmatizer: not just *how accurate*, but *what kinds
of mistakes*.

Aggregate accuracy (`evaluate_on_ud`, `evaluate_on_proiel`, `evaluate_on_nt`) tells a
scholar a single number; it hides which parts of speech are confused, which lemmas are
missed, and whether the model is systematically drifting from an annotation convention or
scattering random errors. This module turns any gold set into an `ErrorAnalysis`: a
gold-to-predicted POS confusion matrix, per-POS accuracy, the most common lemma confusions,
a seen-vs-unseen split, and optional per-frequency-band accuracy.

It generalizes the PROIEL-only drift report (`proiel.proiel_drift`, now a thin adapter over
`analyze_errors`) to every gold source pyaegean can score against: UD-Perseus, the PROIEL
treebank, the Nestle-1904 New Testament, and the leakage-free AGDT held-out split. All the
adapters reconcile POS to pyaegean's tagset on both sides (PROPN->NOUN, SCONJ->CCONJ,
AUX->VERB), so a per-POS number reflects a real disagreement, not a convention gap. Note
that the UD adapter therefore reconciles where `evaluate_on_ud` deliberately does not (it
scores raw UPOS with the official evaluator): the drift view is a diagnostic, not the
headline metric.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from .heldout import HeldoutToken, TagSentence
from .treebank import _clean_lemma

__all__ = [
    "PosStat",
    "ErrorAnalysis",
    "analyze_errors",
    "proiel_error_analysis",
    "nt_error_analysis",
    "ud_error_analysis",
    "heldout_error_analysis",
]


@dataclass(frozen=True, slots=True)
class PosStat:
    """Per-gold-POS accuracy over the scored tokens."""

    pos: str
    n: int
    pos_correct: int
    lemma_correct: int

    @property
    def pos_accuracy(self) -> float:
        return self.pos_correct / self.n if self.n else 0.0

    @property
    def lemma_accuracy(self) -> float:
        return self.lemma_correct / self.n if self.n else 0.0


@dataclass(frozen=True, slots=True)
class ErrorAnalysis:
    """A breakdown of a tagger's errors against a gold set.

    ``pos_confusions`` / ``lemma_confusions`` are (gold, predicted, count) triples,
    most-frequent first; ``lemma_mismatches`` samples (form, gold lemma, predicted lemma)
    for reading. ``per_pos`` is per-gold-POS accuracy (most-frequent POS first). The
    seen/unseen counts are substantive only for the AGDT held-out split, where forms carry a
    real ``seen`` flag; for out-of-domain sets (PROIEL, NT, UD) every token is unseen by
    construction, so the unseen figures equal the overall ones."""

    pos_confusions: tuple[tuple[str, str, int], ...]     # (gold, predicted, count)
    lemma_mismatches: tuple[tuple[str, str, str], ...]   # (form, gold lemma, predicted lemma) sample
    lemma_confusions: tuple[tuple[str, str, int], ...]   # (gold lemma, predicted lemma, count)
    per_pos: tuple[PosStat, ...]
    freq_bands: tuple[tuple[str, int, int, int], ...]    # (band, n, pos_correct, lemma_correct)
    pos_scored: int
    pos_errors: int
    lemma_errors: int
    n_seen: int
    n_unseen: int
    pos_ok_seen: int
    pos_ok_unseen: int
    lemma_ok_seen: int
    lemma_ok_unseen: int

    @property
    def pos_accuracy(self) -> float:
        return (self.pos_scored - self.pos_errors) / self.pos_scored if self.pos_scored else 0.0

    @property
    def lemma_accuracy(self) -> float:
        return (self.pos_scored - self.lemma_errors) / self.pos_scored if self.pos_scored else 0.0

    @property
    def top_share(self) -> float:
        """Fraction of POS errors in the single most common confusion pair (higher = more
        systematic/convention-like, lower = more scattered)."""
        if not self.pos_errors or not self.pos_confusions:
            return 0.0
        return self.pos_confusions[0][2] / self.pos_errors

    @property
    def pos_accuracy_seen(self) -> float:
        return self.pos_ok_seen / self.n_seen if self.n_seen else 0.0

    @property
    def pos_accuracy_unseen(self) -> float:
        return self.pos_ok_unseen / self.n_unseen if self.n_unseen else 0.0

    @property
    def lemma_accuracy_seen(self) -> float:
        return self.lemma_ok_seen / self.n_seen if self.n_seen else 0.0

    @property
    def lemma_accuracy_unseen(self) -> float:
        return self.lemma_ok_unseen / self.n_unseen if self.n_unseen else 0.0

    def summary(self, *, top: int = 8) -> str:
        """A short, readable breakdown: overall accuracy, top POS confusions, the weakest
        parts of speech, and (when meaningful) the unseen-form accuracy."""
        if not self.pos_scored:
            return "error analysis: no scored tokens"
        out = [
            f"error analysis over {self.pos_scored} scored tokens: "
            f"POS {self.pos_accuracy:.1%} ({self.pos_errors} wrong), "
            f"lemma {self.lemma_accuracy:.1%} ({self.lemma_errors} wrong)",
        ]
        if self.pos_confusions:
            out.append("  top POS confusions (gold -> predicted):")
            out += [
                f"    {g} -> {p}: {c}"
                + (f" ({c / self.pos_errors:.0%} of POS errors)" if self.pos_errors else "")
                for g, p, c in self.pos_confusions[:top]
            ]
        weak = sorted((s for s in self.per_pos if s.n >= 5), key=lambda s: s.pos_accuracy)[:5]
        if weak:
            out.append("  weakest parts of speech (POS accuracy):")
            out += [f"    {s.pos}: {s.pos_accuracy:.1%} of {s.n}" for s in weak]
        if self.n_seen and self.n_unseen:  # a real seen/unseen split (held-out only)
            out.append(
                f"  seen forms: POS {self.pos_accuracy_seen:.1%} / lemma {self.lemma_accuracy_seen:.1%}"
                f" ({self.n_seen}); unseen: POS {self.pos_accuracy_unseen:.1%} / "
                f"lemma {self.lemma_accuracy_unseen:.1%} ({self.n_unseen})"
            )
        return "\n".join(out)

    def as_dict(self) -> dict[str, Any]:
        """A JSON-serializable view (for ``--json`` and receipts)."""
        return {
            "pos_scored": self.pos_scored,
            "pos_errors": self.pos_errors,
            "lemma_errors": self.lemma_errors,
            "pos_accuracy": self.pos_accuracy,
            "lemma_accuracy": self.lemma_accuracy,
            "top_share": self.top_share,
            "pos_confusions": [[g, p, c] for g, p, c in self.pos_confusions],
            "lemma_confusions": [[g, p, c] for g, p, c in self.lemma_confusions],
            "lemma_mismatches": [[f, g, p] for f, g, p in self.lemma_mismatches],
            "per_pos": [
                {"pos": s.pos, "n": s.n, "pos_accuracy": s.pos_accuracy,
                 "lemma_accuracy": s.lemma_accuracy}
                for s in self.per_pos
            ],
            "freq_bands": [
                {"band": b, "n": n, "pos_correct": pc, "lemma_correct": lc}
                for b, n, pc, lc in self.freq_bands
            ],
            "n_seen": self.n_seen,
            "n_unseen": self.n_unseen,
            "pos_accuracy_seen": self.pos_accuracy_seen,
            "pos_accuracy_unseen": self.pos_accuracy_unseen,
            "lemma_accuracy_seen": self.lemma_accuracy_seen,
            "lemma_accuracy_unseen": self.lemma_accuracy_unseen,
        }


_BANDS: tuple[tuple[str, int], ...] = (("1", 1), ("2-5", 5), ("6-50", 50))


def _band(count: int) -> str:
    for label, hi in _BANDS:
        if count <= hi:
            return label
    return "51+"


def analyze_errors(
    tag_sentence: TagSentence,
    sentences: Sequence[Sequence[HeldoutToken]],
    *,
    samples: int = 40,
    freq: Callable[[str], int] | None = None,
) -> ErrorAnalysis:
    """Run ``tag_sentence`` over gold ``sentences`` and tabulate the errors.

    Only tokens flagged ``scored`` count (PUNCT/NUM excluded, as everywhere). The predicted
    lemma is cleaned (`_clean_lemma`) before comparison, matching the aggregate scorers, and
    the gold lemma is already cleaned by the gold builder. ``tag_sentence`` and the gold are
    expected to already agree on POS convention (the adapters reconcile both sides). ``freq``,
    when given, maps a form to a corpus frequency for per-band accuracy."""
    confus: Counter[tuple[str, str]] = Counter()
    lemma_confus: Counter[tuple[str, str]] = Counter()
    lemma_mis: list[tuple[str, str, str]] = []
    pp_n: dict[str, int] = defaultdict(int)
    pp_pos: dict[str, int] = defaultdict(int)
    pp_lemma: dict[str, int] = defaultdict(int)
    band_n: dict[str, int] = defaultdict(int)
    band_pos: dict[str, int] = defaultdict(int)
    band_lemma: dict[str, int] = defaultdict(int)
    n = pos_ok = lemma_err = 0
    n_seen = n_unseen = pos_ok_seen = pos_ok_unseen = lemma_ok_seen = lemma_ok_unseen = 0

    for sent in sentences:
        preds = tag_sentence([t.form for t in sent])
        for tok, pred in zip(sent, preds):
            if not tok.scored:
                continue
            n += 1
            unseen = not tok.seen
            n_unseen += unseen
            n_seen += not unseen
            g_pos = tok.upos
            p_pos = pred[1] or ""
            p_lemma = _clean_lemma(pred[0]) if pred[0] else ""
            pp_n[g_pos] += 1
            pos_hit = p_pos == g_pos
            lem_hit = p_lemma == tok.lemma
            if pos_hit:
                pos_ok += 1
                pp_pos[g_pos] += 1
                pos_ok_seen += not unseen
                pos_ok_unseen += unseen
            else:
                confus[(g_pos, p_pos)] += 1
            if lem_hit:
                pp_lemma[g_pos] += 1
                lemma_ok_seen += not unseen
                lemma_ok_unseen += unseen
            else:
                lemma_err += 1
                lemma_confus[(tok.lemma, p_lemma)] += 1
                if len(lemma_mis) < samples:
                    lemma_mis.append((tok.form, tok.lemma, p_lemma))
            if freq is not None:
                b = _band(freq(tok.form))
                band_n[b] += 1
                band_pos[b] += pos_hit
                band_lemma[b] += lem_hit

    per_pos = tuple(
        PosStat(pos=p, n=pp_n[p], pos_correct=pp_pos[p], lemma_correct=pp_lemma[p])
        for p in sorted(pp_n, key=lambda p: -pp_n[p])
    )
    band_order = {label: i for i, (label, _hi) in enumerate((*_BANDS, ("51+", 0)))}
    freq_bands = tuple(
        (b, band_n[b], band_pos[b], band_lemma[b])
        for b in sorted(band_n, key=lambda b: band_order.get(b, 99))
    )
    return ErrorAnalysis(
        pos_confusions=tuple((g, p, c) for (g, p), c in confus.most_common()),
        lemma_mismatches=tuple(lemma_mis),
        lemma_confusions=tuple((g, p, c) for (g, p), c in lemma_confus.most_common()),
        per_pos=per_pos,
        freq_bands=freq_bands,
        pos_scored=n,
        pos_errors=n - pos_ok,
        lemma_errors=lemma_err,
        n_seen=n_seen,
        n_unseen=n_unseen,
        pos_ok_seen=pos_ok_seen,
        pos_ok_unseen=pos_ok_unseen,
        lemma_ok_seen=lemma_ok_seen,
        lemma_ok_unseen=lemma_ok_unseen,
    )


# --- per-source adapters (each builds reconciled gold, wraps the tagger, analyzes) ----------


def proiel_error_analysis(
    tag_sentence: TagSentence | None = None, *, source_dir: Any = None,
    files: tuple[str, ...] | None = None, samples: int = 40,
) -> ErrorAnalysis:
    """Error analysis on the PROIEL Greek treebank (out-of-AGDT). Same tagger/reconciliation
    as `evaluate_on_proiel`."""
    from . import proiel

    kw = {"files": files} if files is not None else {}
    gold = proiel.load_proiel_gold(source_dir=source_dir, **kw)  # type: ignore[arg-type]
    return analyze_errors(proiel._reconciled(tag_sentence), gold, samples=samples)


def nt_error_analysis(
    tag_sentence: TagSentence | None = None, *, corpus: Any = None,
    book: str | None = None, samples: int = 40,
) -> ErrorAnalysis:
    """Error analysis on the Nestle-1904 NT gold (out-of-domain Koine). Defaults to the neural
    joint pipeline, exactly like `evaluate_on_nt`."""
    from . import nt_eval
    from .proiel import _canon_pos

    if corpus is None:
        from ..scripts.greek.nt import load_nt

        corpus = load_nt(book)
    gold = nt_eval._gold_sentences(corpus)
    base = tag_sentence if tag_sentence is not None else nt_eval._neural_tagger()

    def reconciled(forms: list[str]) -> list[tuple[str, str]]:
        return [(lemma, _canon_pos(pos)) for lemma, pos in base(forms)]

    return analyze_errors(reconciled, gold, samples=samples)


def _active_tagger() -> TagSentence:
    """The current pipeline as a TagSentence: the neural joint model when active, else the
    zero-dependency lemmatize + POS baseline."""
    from . import joint

    if joint.active() is not None:
        from .joint import analyze_sentence

        def tag(forms: list[str]) -> list[tuple[str, str]]:
            a = analyze_sentence(forms)
            return list(zip(a.lemma, a.upos))

        return tag
    from .heldout import isolated
    from .lemmatize import lemmatize
    from .pos import pos_tag

    return isolated(lemmatize, pos_tag)


def ud_error_analysis(
    tag_sentence: TagSentence | None = None, *, treebank: str = "perseus",
    split: str = "test", source: Any = None, samples: int = 40,
) -> ErrorAnalysis:
    """Error analysis on a UD Ancient Greek fold (default UD-Perseus test). Unlike
    `evaluate_on_ud` (which scores raw UPOS with the official evaluator), this reconciles POS
    on both sides so per-POS reads as real disagreement; treat it as a diagnostic, not the
    headline number. Defaults to the active pipeline (neural if loaded, else baseline)."""
    from .proiel import _SKIP_POS, _canon_pos
    from .ud import load_conllu, ud_path

    path = source if source is not None else ud_path(treebank, split)
    gold: list[tuple[HeldoutToken, ...]] = []
    for sent in load_conllu(path):
        toks = tuple(
            HeldoutToken(
                form=t.form, lemma=_clean_lemma(t.lemma), upos=_canon_pos(t.upos),
                seen=False, scored=_canon_pos(t.upos) not in _SKIP_POS,
            )
            for t in sent.tokens
        )
        if toks:
            gold.append(toks)
    base = tag_sentence if tag_sentence is not None else _active_tagger()

    def reconciled(forms: list[str]) -> list[tuple[str, str]]:
        return [(lemma, _canon_pos(pos)) for lemma, pos in base(forms)]

    return analyze_errors(reconciled, tuple(gold), samples=samples)


def heldout_error_analysis(
    tag_sentence: TagSentence | None = None, *, holdout: float = 0.1,
    source_dir: str | None = None, samples: int = 40,
) -> ErrorAnalysis:
    """Error analysis on the leakage-free AGDT held-out split — the one source with a real
    seen/unseen contrast (so the seen/unseen figures are substantive here). Defaults to the
    active pipeline; disable the treebank backend first to avoid leakage (see
    `aegean.greek.heldout`)."""
    from .heldout import split_tokens

    sp = split_tokens(source_dir=source_dir, holdout=holdout)
    tagger = tag_sentence if tag_sentence is not None else _active_tagger()
    return analyze_errors(tagger, sp.sentences, samples=samples)
