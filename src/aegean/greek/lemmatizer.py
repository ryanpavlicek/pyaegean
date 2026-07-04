"""Generalizing Greek lemmatizer — **edit-trees** + an averaged-perceptron reranker,
trained on the AGDT (pure Python, no heavy deps).

**Opt-in, and the lemma counterpart to the POS tagger.** The treebank backend lemmatizes
by *lookup* (attested forms only) and the seed table is tiny; neither lemmatizes an
*unseen* form. This model learns, for each (form, lemma) pair, a Chrupała-style **edit
tree** — a recursive transform (keep the shared stem, rewrite the differing prefix/suffix)
that captures Greek inflection *and* accent shifts and generalizes to forms it has never
seen (e.g. learning ``-ου → -ος`` applies it to an unseen ``νόμου → νόμος``).

Decoding uses a reranker rather than a flat classifier over the thousands of distinct edit
trees: the form's suffixes propose a handful of candidate trees and an **averaged perceptron**
(`aegean.greek.syntax`) reranks just those — fast, learned, and still generalizing. The
reranker conditions on **POS** (from the trained tagger when active) — the key signal for
which inflectional rule applies (a noun ``-ων`` vs a participle ``-ων`` lemmatize differently).

Trained on the AGDT we already fetch (CC BY-SA 3.0), built in the cache on first use, never
bundled. Default behaviour without `use_lemmatizer` is unchanged.
"""

from __future__ import annotations

import gzip
import json
import unicodedata
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Any

from ..data import cache_dir, load_gzip_json
from . import syntax
from .morphology import _bare
from .treebank import _clean_lemma

__all__ = [
    "LemmatizerNotLoadedError",
    "disable_lemmatizer",
    "evaluate_lemmatizer",
    "lemmatize_one",
    "predict",
    "train_lemmatizer",
    "use_lemmatizer",
]

_MODEL_NAME = "agdt-lemmatizer.json.gz"
_MAX_SUFFIX = 6
_TOPN = 15
_MIN_TREE_COUNT = 2  # an edit tree must occur at least this often to be a candidate
_BUCKET_CAP = 32     # max trees stored per suffix bucket (pre-sorted by count, bounds cache)


class LemmatizerNotLoadedError(RuntimeError):
    """Raised when the trained lemmatizer is used before `use_lemmatizer`."""


# --- normalization -----------------------------------------------------------


@lru_cache(maxsize=200_000)
def _norm(form: str) -> str:
    """NFC-normalize, **preserving case** — so capitalized lemmas (proper nouns, ethnonyms)
    are modeled; the edit tree learns any case change (e.g. sentence-initial Ὁ → ὁ) itself."""
    return unicodedata.normalize("NFC", form)


# --- edit trees (Chrupała-style) ---------------------------------------------
# A tree is a JSON-native nested list: ["keep"] (emit the segment unchanged),
# ["sub", s] (replace the whole segment with s), or
# ["node", prefix_len, suffix_len, left_tree, right_tree] (keep the shared middle,
# recursively edit the prefix and suffix). Storing *lengths* (not the stem text) is
# what makes a tree reusable across different forms.

EditTree = Any


def _lcs(a: str, b: str) -> tuple[int, int, int]:
    """Longest common (contiguous) substring: ``(start_in_a, start_in_b, length)``."""
    if not a or not b:
        return (0, 0, 0)
    best = end_a = end_b = 0
    prev = [0] * (len(b) + 1)
    for i in range(1, len(a) + 1):
        cur = [0] * (len(b) + 1)
        ai = a[i - 1]
        for j in range(1, len(b) + 1):
            if ai == b[j - 1]:
                cur[j] = prev[j - 1] + 1
                if cur[j] > best:
                    best, end_a, end_b = cur[j], i, j
        prev = cur
    if best == 0:
        return (0, 0, 0)
    return (end_a - best, end_b - best, best)


def build_tree(w: str, lemma: str) -> EditTree:
    """The edit tree transforming form segment ``w`` into lemma segment ``lemma``."""
    if w == lemma:
        return ["keep"]
    sa, sb, ln = _lcs(w, lemma)
    if ln == 0:
        return ["sub", lemma]
    left = build_tree(w[:sa], lemma[:sb])
    right = build_tree(w[sa + ln :], lemma[sb + ln :])
    return ["node", sa, len(w) - (sa + ln), left, right]


def apply_tree(tree: EditTree, w: str) -> str | None:
    """Apply an edit tree to a form; ``None`` if it structurally doesn't fit ``w``."""
    kind = tree[0]
    if kind == "keep":
        return w
    if kind == "sub":
        return tree[1]  # type: ignore[no-any-return]
    _, plen, slen, left, right = tree
    if plen + slen > len(w):
        return None
    pref = apply_tree(left, w[:plen])
    suf = apply_tree(right, w[len(w) - slen :] if slen else "")
    if pref is None or suf is None:
        return None
    mid = w[plen : len(w) - slen] if slen else w[plen:]
    return pref + mid + suf


def _key(tree: EditTree) -> str:
    return json.dumps(tree, ensure_ascii=False, separators=(",", ":"))


_IDENTITY = ["keep"]
_IDENTITY_KEY = _key(_IDENTITY)


# --- features ----------------------------------------------------------------


@lru_cache(maxsize=400_000)
def _features(form: str, pos: str) -> tuple[str, ...]:
    f = _norm(form)
    b = _bare(form)
    feats = [
        f"as1={f[-1:]}", f"as2={f[-2:]}", f"as3={f[-3:]}", f"as4={f[-4:]}",
        f"bs1={b[-1:]}", f"bs2={b[-2:]}", f"bs3={b[-3:]}", f"bs4={b[-4:]}", f"bs5={b[-5:]}",
        f"bp1={b[:1]}", f"bp2={b[:2]}", f"bp3={b[:3]}",
        f"len={min(len(b), 8)}",
    ]
    if form[:1].isupper():  # signals proper-noun / sentence-initial case handling
        feats.append("cap=1")
    if pos:  # POS is the key disambiguator for lemma rules (noun -ων vs participle -ων)
        feats += [
            f"pos={pos}", f"pos={pos}|bs2={b[-2:]}", f"pos={pos}|bs3={b[-3:]}",
            f"pos={pos}|as3={f[-3:]}",
        ]
    if any(ch.isdigit() for ch in form):
        feats.append("shape=digit")
    if not any(ch.isalpha() for ch in form):
        feats.append("shape=nonletter")
    return tuple(feats)


# --- candidates --------------------------------------------------------------


def _candidates(
    form: str, suffix_trees: dict[str, list[str]], tree_map: dict[str, EditTree]
) -> list[str]:
    """Candidate edit-tree keys for a form: trees seen for its bare suffixes (longest first,
    most-frequent first — buckets are pre-sorted at train time) that actually apply to it,
    plus identity as a backstop."""
    b = _bare(form)
    nf = _norm(form)
    seen: set[str] = set()
    cands: list[str] = []
    for length in range(min(_MAX_SUFFIX, len(b)), 0, -1):
        bucket = suffix_trees.get(b[-length:])
        if not bucket:
            continue
        for tk in bucket:
            if tk in seen:
                continue
            seen.add(tk)
            tree = tree_map.get(tk)
            if tree is not None and apply_tree(tree, nf) is not None:
                cands.append(tk)
            if len(cands) >= _TOPN:
                break
        if len(cands) >= _TOPN:
            break
    if _IDENTITY_KEY not in seen:
        cands.append(_IDENTITY_KEY)
    return cands


# --- train / decode ----------------------------------------------------------


def _triples(source_dir: str | None) -> list[tuple[str, str, str]]:
    trees = syntax.load_gold_trees(source_dir=source_dir)
    return [(t.form, _clean_lemma(t.lemma), t.upos) for tr in trees for t in tr.tokens]


def _train(data: list[tuple[str, str, str]], epochs: int) -> dict[str, Any]:
    tree_map: dict[str, EditTree] = {_IDENTITY_KEY: _IDENTITY}
    tree_count: Counter[str] = Counter()
    suffix_trees: dict[str, Counter[str]] = defaultdict(Counter)
    examples: list[tuple[str, str, str, str]] = []
    for form, lemma, pos in data:
        tree = build_tree(_norm(form), _norm(lemma))
        tk = _key(tree)
        tree_map[tk] = tree
        tree_count[tk] += 1
        b = _bare(form)
        for length in range(1, min(_MAX_SUFFIX, len(b)) + 1):
            suffix_trees[b[-length:]][tk] += 1
        examples.append((form, lemma, pos, tk))

    # Keep only trees attested >= _MIN_TREE_COUNT (drop idiosyncratic hapaxes); store each
    # bucket as a list pre-sorted by count and capped at _BUCKET_CAP (bounds cache size and
    # removes the per-call sort). Prune tree_map to the reachable trees (+ identity).
    pruned: dict[str, list[str]] = {}
    kept_keys: set[str] = {_IDENTITY_KEY}
    for suffix, bucket in suffix_trees.items():
        ranked = [tk for tk, _c in bucket.most_common() if tree_count[tk] >= _MIN_TREE_COUNT]
        if ranked:
            ranked = ranked[:_BUCKET_CAP]
            pruned[suffix] = ranked
            kept_keys.update(ranked)
    kept_map = {tk: tree_map[tk] for tk in kept_keys}

    # Precompute (features, candidates, target) per example once — invariant across epochs.
    # When the gold tree was pruned/unreachable, retarget to a reachable candidate that
    # reproduces the gold lemma so train candidates == decode candidates (no dead labels);
    # skip the token if none can (it is unlearnable through the candidate set).
    prepared: list[tuple[list[str], list[str], str]] = []
    for form, lemma, pos, gold in examples:
        cands = _candidates(form, pruned, kept_map)
        if gold not in cands:
            nlem, nf = _norm(lemma), _norm(form)
            target = next((c for c in cands if apply_tree(kept_map[c], nf) == nlem), None)
            if target is None:
                continue
            gold = target
        prepared.append((list(_features(form, pos)), cands, gold))

    perc = syntax._Perceptron()
    for _epoch in range(epochs):
        for feats, cands, gold in prepared:
            pred = syntax._predict(perc.w, cands, feats)
            perc.update(gold, pred, feats)
    return {"weights": perc.averaged(), "suffix_trees": pruned, "tree_map": kept_map}


def lemmatize_one(form: str, model: dict[str, Any], pos: str = "") -> str:
    """Predict the lemma of a single form using a trained model dict. ``pos`` (a UD tag, if
    known) sharpens the rule choice; pass "" when it is unknown."""
    cands = _candidates(form, model["suffix_trees"], model["tree_map"])
    tk = syntax._predict(model["weights"], cands, list(_features(form, pos)))
    out = apply_tree(model["tree_map"][tk], _norm(form))
    return out if out is not None else _norm(form)


# --- model persistence + activation ------------------------------------------


def train_lemmatizer(
    *, source_dir: str | None = None, epochs: int = 8, force: bool = False
) -> Path:
    """Train (and cache, gzipped) the lemmatizer, returning the model path.

    Prefers the hosted **prebuilt model** (skipping the AGDT download + training);
    falls back to training from the AGDT (downloaded on first use). ``source_dir``
    trains from local fixture XML (tests; no network, no prebuilt fetch)."""
    out = cache_dir() / _MODEL_NAME
    if out.exists() and not force and source_dir is None:
        return out
    if source_dir is None:
        from ..data import fetch_prebuilt

        if fetch_prebuilt("agdt-derived", out, member=_MODEL_NAME):
            return out
    model = _train(_triples(source_dir), epochs)
    with gzip.open(out, "wt", encoding="utf-8") as f:
        json.dump(model, f, ensure_ascii=False)
    return out


def _load_model(path: Path | str | None = None) -> dict[str, Any]:
    p = Path(path) if path is not None else cache_dir() / _MODEL_NAME
    if not p.exists():
        raise LemmatizerNotLoadedError(f"no lemmatizer model at {p}; call use_lemmatizer() first")
    model: dict[str, Any] = load_gzip_json(p)
    return model


_ACTIVE: dict[str, Any] | None = None


def use_lemmatizer(*, train: bool = True, force: bool = False) -> None:
    """Activate the generalizing lemmatizer. With ``train=True`` (default) it trains on
    first use — from the cached AGDT, a few minutes — then caches the model; later calls
    load the cache. ``train=False`` loads an existing cached model (raises
    `LemmatizerNotLoadedError` if none exists). ``force=True`` retrains even if cached."""
    global _ACTIVE
    if train and (force or not (cache_dir() / _MODEL_NAME).exists()):
        train_lemmatizer(force=force)
    _ACTIVE = _load_model()


def disable_lemmatizer() -> None:
    """Deactivate the lemmatizer; restore the lookup/seed/identity behaviour."""
    global _ACTIVE
    _ACTIVE = None


def active() -> dict[str, Any] | None:
    """The active lemmatizer model, or ``None`` (the default)."""
    return _ACTIVE


def _pos_for(form: str) -> str:
    """Best available POS for a form, via `aegean.greek.pos.pos_tag` — which itself
    cascades closed-class lexicon → treebank lookup → trained tagger → suffix heuristic, and
    crucially never calls back into the lemmatizer (avoiding recursion)."""
    from .pos import pos_tag

    return pos_tag(form)


def predict(form: str) -> str:
    """Lemmatize a form with the active model (raises if none is active). Conditions on POS
    from the trained tagger when active (see `aegean.greek.use_tagger`) — best
    results come from activating both; otherwise a rule-based POS guess is used."""
    if _ACTIVE is None:
        raise LemmatizerNotLoadedError("lemmatizer not loaded — call aegean.greek.use_lemmatizer() first")
    return lemmatize_one(form, _ACTIVE, _pos_for(form))


def evaluate_lemmatizer(
    *, source_dir: str | None = None, holdout: float = 0.1, epochs: int = 8
) -> dict[str, float]:
    """Train on the train split and score lemma accuracy on the held-out split (overall +
    unseen), via `aegean.greek.heldout` — the honest generalization number. A POS
    tagger is trained on the same split so the dev set is scored with *predicted* POS (the
    realistic pipeline), not gold. Returns ``lemma_all``/``lemma_unseen`` plus token counts
    (POS metrics are omitted)."""
    from . import heldout, tagger

    trees = syntax.load_gold_trees(source_dir=source_dir)
    cut = max(1, int(len(trees) * (1 - holdout)))
    train_triples = [
        (t.form, _clean_lemma(t.lemma), t.upos) for tr in trees[:cut] for t in tr.tokens
    ]
    model = _train(train_triples, epochs)

    tagger_data = [([t.form for t in tr.tokens], [t.upos for t in tr.tokens]) for tr in trees[:cut]]
    tw, tlabels = tagger._train(tagger_data, epochs)

    def tag_sentence(forms: list[str]) -> list[tuple[str, str]]:
        ptags = tagger._decode(forms, tw, tlabels)
        return [(lemmatize_one(f, model, p), "") for f, p in zip(forms, ptags)]

    split = heldout.split_tokens(source_dir=source_dir, holdout=holdout)
    result = heldout.score(tag_sentence, split=split)
    return {k: v for k, v in result.items() if not k.startswith("pos_")}
