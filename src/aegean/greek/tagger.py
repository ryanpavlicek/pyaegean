"""Generalizing Greek POS tagger — a greedy **averaged-perceptron** sequence tagger
trained on the AGDT (pure Python, no heavy deps).

**Opt-in, and the piece that generalizes.** The treebank backend is a *lookup* (attested
forms only) and the rule baseline only knows regular paradigms; neither tags an *unseen*
form well. This tagger predicts POS for any form from suffix/shape/accent + context
features, reaching ~84% on unseen forms. It reuses the averaged-perceptron machinery from
the dependency parser (:mod:`aegean.greek.syntax`).

Trained on the AGDT we already fetch (CC BY-SA 3.0), built in the cache on first use,
never bundled. POS only; lemma (edit-trees) and full morphology are separate steps.
Default behaviour without :func:`use_tagger` is unchanged.
"""

from __future__ import annotations

import gzip
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from ..data import cache_dir
from . import syntax
from .accent import accentuation
from .morphology import _bare, best_pos
from .pos import _LEXICON
from .pos import _norm as _pos_norm

__all__ = [
    "TaggerNotLoadedError",
    "disable_tagger",
    "evaluate_tagger",
    "tag_pos",
    "train_tagger",
    "use_tagger",
]

_MODEL_NAME = "agdt-postagger.json.gz"
_BOS, _EOS = "<s>", "</s>"


class TaggerNotLoadedError(RuntimeError):
    """Raised when :func:`tag_pos` is used before :func:`use_tagger`."""


# --- features ----------------------------------------------------------------


@lru_cache(maxsize=200_000)
def _form_features(form: str, bare: str) -> tuple[str, ...]:
    """Context-free features of a single token (cached across epochs)."""
    # Suffix/prefix n-grams are the generalizing signal (Greek inflection is suffixal,
    # endings run to ~6 chars: -μενος, -σθαι). There is deliberately no lexicalized
    # whole-form feature: it would only memorize seen forms (which the treebank lookup
    # already covers) and never fire on the unseen forms this tagger handles.
    feats = [
        f"suf1={bare[-1:]}", f"suf2={bare[-2:]}", f"suf3={bare[-3:]}",
        f"suf4={bare[-4:]}", f"suf5={bare[-5:]}", f"suf6={bare[-6:]}",
        f"pre1={bare[:1]}", f"pre2={bare[:2]}", f"pre3={bare[:3]}",
        f"len={min(len(bare), 8)}",
    ]
    if any(ch.isdigit() for ch in form):
        feats.append("shape=hasdigit")
    if not any(ch.isalpha() for ch in form):
        feats.append("shape=nonletter")
    try:
        feats.append(f"acc={accentuation(form).classification}")
    except Exception:  # pragma: no cover - accent analysis is best-effort
        pass
    closed = _LEXICON.get(_pos_norm(form))
    if closed is not None:
        feats.append(f"closed={closed}")
    rule = best_pos(form)
    if rule is not None:
        feats.append(f"rule={rule}")
    return tuple(feats)


def _features(forms: list[str], bares: list[str], i: int, hist: list[str]) -> list[str]:
    feats = list(_form_features(forms[i], bares[i]))
    prev1 = hist[i - 1] if i >= 1 else _BOS
    prev2 = hist[i - 2] if i >= 2 else _BOS
    nxt = bares[i + 1][-3:] if i + 1 < len(bares) else _EOS
    prv = bares[i - 1][-3:] if i >= 1 else _BOS
    feats += [
        f"p1={prev1}", f"p2={prev2}", f"p12={prev2}|{prev1}",
        f"nsuf={nxt}", f"psuf={prv}",
        f"suf2p1={bares[i][-2:]}|{prev1}",       # the dominant suffix × prev-tag combo
    ]
    return feats


# --- train / decode ----------------------------------------------------------


def _sentences(source_dir: str | None) -> list[tuple[list[str], list[str]]]:
    trees = syntax.load_gold_trees(source_dir=source_dir)
    return [([t.form for t in tr.tokens], [t.upos for t in tr.tokens]) for tr in trees]


def _train(
    data: list[tuple[list[str], list[str]]], epochs: int
) -> tuple[dict[str, dict[str, float]], list[str]]:
    labels = sorted({u for _forms, ups in data for u in ups})
    # Precompute bare forms once — they are invariant across epochs, so recomputing them in
    # the inner loop would cost (epochs-1)×N redundant _bare() calls.
    prepared = [(forms, [_bare(f) for f in forms], ups) for forms, ups in data]
    perc = syntax._Perceptron()
    for _epoch in range(epochs):
        for forms, bares, ups in prepared:
            for i in range(len(forms)):
                feats = _features(forms, bares, i, ups)  # gold-history (teacher forcing)
                pred = syntax._predict(perc.w, labels, feats)
                perc.update(ups[i], pred, feats)
    return perc.averaged(), labels


def _decode(forms: list[str], weights: dict[str, dict[str, float]], labels: list[str]) -> list[str]:
    bares = [_bare(f) for f in forms]
    hist: list[str] = []
    for i in range(len(forms)):
        hist.append(syntax._predict(weights, labels, _features(forms, bares, i, hist)))
    return hist


# --- model persistence + activation ------------------------------------------


def train_tagger(*, source_dir: str | None = None, epochs: int = 8, force: bool = False) -> Path:
    """Train (and cache, gzipped) the POS tagger, returning the model path. Trains from
    the AGDT (downloaded on first use) unless ``source_dir`` is given (tests)."""
    out = cache_dir() / _MODEL_NAME
    if out.exists() and not force and source_dir is None:
        return out
    weights, labels = _train(_sentences(source_dir), epochs)
    with gzip.open(out, "wt", encoding="utf-8") as f:
        json.dump({"weights": weights, "labels": labels}, f, ensure_ascii=False)
    return out


def _load_model(path: Path | str | None = None) -> dict[str, Any]:
    p = Path(path) if path is not None else cache_dir() / _MODEL_NAME
    if not p.exists():
        raise TaggerNotLoadedError(f"no POS-tagger model at {p}; call use_tagger() first")
    with gzip.open(p, "rt", encoding="utf-8") as f:
        model: dict[str, Any] = json.load(f)
    return model


_ACTIVE: dict[str, Any] | None = None


def use_tagger(*, train: bool = True, force: bool = False) -> None:
    """Activate the generalizing POS tagger. With ``train=True`` (default) it trains on
    first use — from the cached AGDT, a few minutes — then caches the model; later calls
    load the cache. ``train=False`` loads an existing cached model without training (raises
    :class:`TaggerNotLoadedError` if none exists). ``force=True`` retrains even if cached."""
    global _ACTIVE
    if train and (force or not (cache_dir() / _MODEL_NAME).exists()):
        train_tagger(force=force)
    _ACTIVE = _load_model()


def disable_tagger() -> None:
    """Deactivate the POS tagger; restore the lookup/rule behaviour."""
    global _ACTIVE
    _ACTIVE = None


def active() -> dict[str, Any] | None:
    """The active tagger model, or ``None`` (the default)."""
    return _ACTIVE


def tag_pos(forms: list[str]) -> list[str]:
    """Tag a whole sentence's forms with POS (uses left-to-right context). Requires an
    active model (see :func:`use_tagger`)."""
    if _ACTIVE is None:
        raise TaggerNotLoadedError("POS tagger not loaded — call aegean.greek.use_tagger() first")
    return _decode(forms, _ACTIVE["weights"], _ACTIVE["labels"])


def evaluate_tagger(
    *, source_dir: str | None = None, holdout: float = 0.1, epochs: int = 8
) -> dict[str, float]:
    """Train on the train split and score POS on the held-out split (overall + unseen),
    via :mod:`aegean.greek.heldout` — the honest generalization number. Returns
    ``pos_all``/``pos_unseen`` plus the token counts (this tagger predicts POS only, so the
    lemma metrics are omitted)."""
    from . import heldout

    trees = syntax.load_gold_trees(source_dir=source_dir)
    cut = max(1, int(len(trees) * (1 - holdout)))
    train_data = [([t.form for t in tr.tokens], [t.upos for t in tr.tokens]) for tr in trees[:cut]]
    weights, labels = _train(train_data, epochs)

    def tag_sentence(forms: list[str]) -> list[tuple[str, str]]:
        return [("", p) for p in _decode(forms, weights, labels)]

    split = heldout.split_tokens(source_dir=source_dir, holdout=holdout)
    result = heldout.score(tag_sentence, split=split)
    # POS-only tagger: the lemma metrics would be an artifactual 0% — drop them.
    return {k: v for k, v in result.items() if not k.startswith("lemma_")}
