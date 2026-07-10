"""Leakage-free held-out evaluation of Greek lemma/POS against the AGDT.

The treebank backend is a **lookup** — it memorizes attested forms, so any test set
drawn from its own training text is trivially aced and tells you nothing about
*generalization*. To measure real generalization, this module splits the AGDT into
train/dev **by sentence**, flags the dev forms that are **unseen** in train, and scores
any tagger on the disjoint unseen subset. Any callable — a pyaegean mode or a CLTK
pipeline — drops into the identical split.

**Load-bearing caveats:**
- The treebank lookup must NOT be active when scoring "pyaegean" here — it is built from
  the *whole* AGDT (dev included), so it would leak. Score the generalizer/baseline with
  `disable_treebank()`, or use the train-only lookup this module builds.
- stanza's grc models were trained on Perseus/PROIEL, which overlaps the AGDT, so an AGDT
  held-out split is genuinely held-out for pyaegean but likely **in-training for stanza** —
  raising stanza's score on *seen* forms. Separately, UD-vs-AGDT tagset differences (stanza
  emits PROPN/AUX/SCONJ, absent from the AGDT scheme) cut the other way on those same seen
  closed-class words. Both effects concentrate on seen forms and largely cancel there, so the
  **unseen-form column is the clean comparison** — it isolates generalization and is
  uncontaminated by the tagset convention. A fully neutral test still needs a hand-checked
  out-of-AGDT gold set.
- Gold lemmas from the treebank carry Perseus homonym digits (``μένω1``); they are cleaned
  (``_clean_lemma``) on both the gold and prediction side before scoring.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass

from . import syntax
from .treebank import _clean_lemma, _norm

__all__ = ["HeldoutSplit", "HeldoutToken", "compare", "isolated", "score", "split_tokens"]

_SKIP_POS = frozenset({"PUNCT", "NUM"})

# A whole-sentence tagger: given the sentence's forms, return (lemma, pos) per token.
TagSentence = Callable[[list[str]], list[tuple[str, str]]]


@dataclass(frozen=True, slots=True)
class HeldoutToken:
    form: str
    lemma: str       # cleaned gold lemma
    upos: str
    seen: bool       # form attested in the train split
    scored: bool     # counts toward the metric (not PUNCT/NUM)


@dataclass(frozen=True, slots=True)
class HeldoutSplit:
    sentences: tuple[tuple[HeldoutToken, ...], ...]
    train_forms: frozenset[str]
    train_lemma: dict[str, str]   # train-only lookup (token-stream granular)
    train_pos: dict[str, str]


def _ratio(correct: int, total: int) -> float:
    return correct / total if total else 0.0


def split_tokens(*, source_dir: str | None = None, holdout: float = 0.1) -> HeldoutSplit:
    """Split the AGDT by sentence into train/dev and flag dev forms unseen in train.

    The train-only lookup is built directly from the train **token stream** (never via
    ``build_lexicon``, which is file-granular and would leak across a sentence split)."""
    trees = syntax.load_gold_trees(source_dir=source_dir)
    cut = max(1, int(len(trees) * (1 - holdout)))
    train_trees, dev_trees = trees[:cut], trees[cut:]

    train_forms = frozenset(_norm(t.form) for tr in train_trees for t in tr.tokens)
    lemma_counts: dict[str, Counter[str]] = {}
    pos_counts: dict[str, Counter[str]] = {}
    for tr in train_trees:
        for t in tr.tokens:
            k = _norm(t.form)
            lemma_counts.setdefault(k, Counter())[_clean_lemma(t.lemma)] += 1
            pos_counts.setdefault(k, Counter())[t.upos] += 1

    sentences = tuple(
        tuple(
            HeldoutToken(
                form=t.form, lemma=_clean_lemma(t.lemma), upos=t.upos,
                seen=_norm(t.form) in train_forms, scored=t.upos not in _SKIP_POS,
            )
            for t in tr.tokens
        )
        for tr in dev_trees
        if tr.tokens
    )
    split = HeldoutSplit(
        sentences=sentences,
        train_forms=train_forms,
        train_lemma={k: c.most_common(1)[0][0] for k, c in lemma_counts.items()},
        train_pos={k: c.most_common(1)[0][0] for k, c in pos_counts.items()},
    )
    # Sanity cross-check: the ``seen`` flag is derived from ``train_forms``, so checking the
    # unseen set against ``train_forms`` would be a tautology. Check it instead against the
    # train lookup (``train_pos``), which is built from an *independent* counter pass — this
    # catches a divergence between the two train-side constructions (a real leakage guard).
    unseen = {_norm(t.form) for s in sentences for t in s if t.scored and not t.seen}
    assert not (unseen & split.train_pos.keys()), "held-out leakage: unseen dev form in train lookup"
    return split


def score(
    tag_sentence: TagSentence,
    *,
    source_dir: str | None = None,
    holdout: float = 0.1,
    split: HeldoutSplit | None = None,
    progress: Callable[[int, int], None] | None = None,
) -> dict[str, float]:
    """Score a whole-sentence tagger on the held-out split, overall and on the **unseen**
    subset. ``tag_sentence`` receives every form in a sentence (so context-aware systems
    get full context) and returns ``(lemma, pos)`` per token; only non-PUNCT/NUM tokens
    count. Lemmas are compared after ``_clean_lemma`` on both sides.

    ``progress`` (optional) is called as ``progress(done, total)`` after each scored
    sentence — the hook the long evaluations (the ~1 h whole-NT run) report through.
    It never changes the result; an exception it raises aborts the run."""
    sp = split if split is not None else split_tokens(source_dir=source_dir, holdout=holdout)
    total = len(sp.sentences)
    n_all = n_seen = n_unseen = 0
    lemma_ok = lemma_ok_unseen = pos_ok = pos_ok_unseen = 0
    for done, sent in enumerate(sp.sentences, start=1):
        preds = tag_sentence([t.form for t in sent])
        for tok, pred in zip(sent, preds):
            if not tok.scored:
                continue
            n_all += 1
            unseen = not tok.seen
            n_unseen += int(unseen)
            n_seen += int(not unseen)
            pred_lemma = _clean_lemma(pred[0]) if pred[0] else ""
            if pred_lemma == tok.lemma:
                lemma_ok += 1
                lemma_ok_unseen += int(unseen)
            if (pred[1] or "") == tok.upos:
                pos_ok += 1
                pos_ok_unseen += int(unseen)
        if progress is not None:
            progress(done, total)
    return {
        "lemma_all": _ratio(lemma_ok, n_all),
        "pos_all": _ratio(pos_ok, n_all),
        "lemma_unseen": _ratio(lemma_ok_unseen, n_unseen),
        "pos_unseen": _ratio(pos_ok_unseen, n_unseen),
        "n_all": n_all,
        "n_seen": n_seen,
        "n_unseen": n_unseen,
    }


def isolated(
    predict_lemma: Callable[[str], str], predict_pos: Callable[[str], str]
) -> TagSentence:
    """Adapt per-form predictors into a (context-free) ``tag_sentence`` — for tagging that
    doesn't use sentence context (e.g. pyaegean's lookup/heuristic, or per-word CLTK)."""
    def tag(forms: list[str]) -> list[tuple[str, str]]:
        return [(predict_lemma(f), predict_pos(f)) for f in forms]

    return tag


def compare(
    a: TagSentence,
    b: TagSentence,
    *,
    source_dir: str | None = None,
    holdout: float = 0.1,
    labels: tuple[str, str] = ("a", "b"),
) -> dict[str, dict[str, float]]:
    """Score two taggers on the **identical** split (e.g. a pyaegean mode vs CLTK)."""
    sp = split_tokens(source_dir=source_dir, holdout=holdout)
    return {labels[0]: score(a, split=sp), labels[1]: score(b, split=sp)}
