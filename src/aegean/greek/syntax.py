"""Greek dependency parsing — a transition-based **arc-eager** parser with an
**averaged-perceptron** classifier (pure Python; no heavy ML deps), trained on the
Perseus AGDT.

Opt-in. Call `use_parser` to train (on first use, from the AGDT we already fetch
for the treebank) or load the cached model, then `parse` turns a Greek sentence
into a `DepTree` with the gold **AGDT/Prague** labels (SBJ, OBJ, ATR, ADV, PRED,
COORD, Aux*…). On a free-word-order, partly non-projective language it reaches about
0.67 UAS / 0.57 LAS on projective AGDT; `evaluate` reports UAS/LAS on a held-out
split. Default behaviour (without `use_parser`) does nothing and needs no network.

Data: the same AGDT v2.1 Greek files used by `aegean.greek.treebank` (CC BY-SA
3.0; fetched to cache, never bundled). The trained model is built in the cache.
"""

from __future__ import annotations

import gzip
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from ..data import cache_dir, load_gzip_json
from . import treebank

__all__ = [
    "DepToken",
    "DepTree",
    "ParserNotLoadedError",
    "disable_parser",
    "evaluate",
    "load_gold_trees",
    "parse",
    "train_parser",
    "use_parser",
]

_MODEL_NAME = "agdt-parser-model.json.gz"
_ROOT = 0  # the artificial root token id


class ParserNotLoadedError(RuntimeError):
    """Raised when `parse` is called before `use_parser`."""


# --- data model --------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DepToken:
    """One token in a dependency tree (1-based ``id``; ``head=0`` is the root)."""

    id: int
    form: str
    lemma: str
    upos: str
    head: int
    relation: str
    postag: str = ""  # raw Perseus 9-char tag (morphology features via treebank.decode_postag)


@dataclass(frozen=True, slots=True)
class DepTree:
    """A dependency tree over a sentence's tokens (AGDT/Prague relation labels)."""

    tokens: tuple[DepToken, ...]

    def root(self) -> DepToken | None:
        """The token whose head is the artificial root (0)."""
        return next((t for t in self.tokens if t.head == _ROOT), None)

    def head_of(self, token_id: int) -> DepToken | None:
        head = next((t.head for t in self.tokens if t.id == token_id), None)
        if head is None or head == _ROOT:
            return None
        return next((t for t in self.tokens if t.id == head), None)

    def children(self, token_id: int) -> list[DepToken]:
        return [t for t in self.tokens if t.head == token_id]

    def is_projective(self) -> bool:
        """Whether the tree has no crossing arcs (arc-eager can only build these)."""
        arcs = [(min(t.id, t.head), max(t.id, t.head)) for t in self.tokens if t.head != _ROOT]
        for i, (a1, a2) in enumerate(arcs):
            for a3, a4 in arcs[i + 1:]:
                if a1 < a3 < a2 < a4 or a3 < a1 < a4 < a2:  # arcs cross
                    return False
        return True

    def __str__(self) -> str:
        by_id = {t.id: t for t in self.tokens}
        lines = []
        for t in self.tokens:
            head_form = "ROOT" if t.head == _ROOT else by_id[t.head].form
            lines.append(f"{t.id}\t{t.form}\t{t.upos}\t{t.relation}\t->{t.head}({head_form})")
        return "\n".join(lines)

    def _repr_html_(self) -> str:
        import html

        rows = "".join(
            f"<tr><td>{t.id}</td><td><b>{html.escape(t.form)}</b></td>"
            f"<td>{t.upos}</td><td>{html.escape(t.relation)}</td>"
            f"<td>{'ROOT' if t.head == _ROOT else t.head}</td></tr>"
            for t in self.tokens
        )
        return (
            "<table><tr><th>#</th><th>form</th><th>pos</th><th>rel</th><th>head</th></tr>"
            f"{rows}</table>"
        )


# --- AGDT gold-tree loading --------------------------------------------------


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def load_gold_trees(*, source_dir: Path | str | None = None) -> list[DepTree]:
    """Load AGDT sentences as gold `DepTree` objects (fetching the treebank on
    first use, unless ``source_dir`` is given)."""
    if source_dir is not None:
        files = sorted(Path(source_dir).glob("*.xml"))
    else:
        files = sorted(treebank.agdt_dir(download=True).glob("*.tb.xml"))

    trees: list[DepTree] = []
    for fp in files:
        if not fp.exists():
            continue
        for _event, elem in ET.iterparse(str(fp), events=("end",)):
            if _local(elem.tag) != "sentence":
                continue
            toks: list[DepToken] = []
            ok = True
            for w in elem:
                if _local(w.tag) != "word":
                    continue
                form, rel = w.get("form"), w.get("relation")
                if form is None or rel is None:
                    ok = False
                    break
                try:  # ids/heads are ints; AGDT has occasional empty/artificial nodes
                    tid, thead = int(w.get("id") or ""), int(w.get("head") or "")
                except ValueError:
                    ok = False
                    break
                feats = treebank.decode_postag(w.get("postag") or "")
                toks.append(
                    DepToken(
                        id=tid, form=form, lemma=w.get("lemma") or form,
                        upos=feats.get("pos", "X"), head=thead, relation=rel,
                        postag=w.get("postag") or "",
                    )
                )
            elem.clear()
            # Keep clean, contiguously-numbered sentences (drop elliptical/odd ids).
            if ok and toks and [t.id for t in toks] == list(range(1, len(toks) + 1)):
                if all(0 <= t.head <= len(toks) for t in toks):
                    trees.append(DepTree(tokens=tuple(toks)))
    return trees


# --- arc-eager transition system ---------------------------------------------

SHIFT, REDUCE, LEFT, RIGHT = "SHIFT", "REDUCE", "LEFT", "RIGHT"


def _encode(action: str, rel: str = "") -> str:
    return f"{action}:{rel}" if rel else action


def _legal(stack: list[int], beta: int, n: int, head: dict[int, int]) -> list[str]:
    """Legal action *types* (LEFT/RIGHT carry a relation, added by the caller)."""
    out: list[str] = []
    s0 = stack[-1]
    buffer_nonempty = beta <= n
    if buffer_nonempty:
        out.append(SHIFT)
    if buffer_nonempty:  # RIGHT may attach b0 to ROOT (the sentence root)
        out.append(RIGHT)
    if buffer_nonempty and s0 != _ROOT and s0 not in head:
        out.append(LEFT)
    if s0 != _ROOT and s0 in head:
        out.append(REDUCE)
    return out


def _oracle(tree: DepTree) -> list[tuple[str, str]] | None:
    """The arc-eager static-oracle action sequence reproducing ``tree`` (forms an
    exact match for projective trees); ``None`` if it cannot (non-projective)."""
    n = len(tree.tokens)
    gold_head = {t.id: t.head for t in tree.tokens}
    gold_rel = {t.id: t.relation for t in tree.tokens}
    stack, beta = [_ROOT], 1
    head: dict[int, int] = {}
    actions: list[tuple[str, str]] = []
    steps = 0
    while beta <= n or len(stack) > 1:
        if beta > n and len(stack) > 1:
            # buffer empty but stack has unreduced tokens — only REDUCE remains
            if stack[-1] in head:
                stack.pop()
                actions.append((REDUCE, ""))
                continue
            return None
        s0 = stack[-1]
        if s0 != _ROOT and s0 not in head and gold_head[s0] == beta:
            head[s0] = beta
            stack.pop()
            actions.append((LEFT, gold_rel[s0]))
        elif gold_head.get(beta) == s0:  # s0 may be ROOT — attaches the sentence root
            head[beta] = s0
            stack.append(beta)
            beta += 1
            actions.append((RIGHT, gold_rel[beta - 1]))
        elif s0 in head and any(
            gold_head.get(beta) == k or gold_head.get(k) == beta
            for k in stack[:-1]
        ):
            stack.pop()
            actions.append((REDUCE, ""))
        elif beta <= n:
            stack.append(beta)
            beta += 1
            actions.append((SHIFT, ""))
        else:
            return None
        steps += 1
        if steps > 4 * n + 5:  # safety
            return None
    # Verify the oracle reproduced the gold arcs exactly (projective check).
    if any(head.get(t.id, _ROOT) != t.head for t in tree.tokens):
        return None
    return actions


# --- features ----------------------------------------------------------------


def _attr(seq: list[str], i: int) -> str:
    return seq[i] if 0 <= i < len(seq) else "_"


def _features(
    stack: list[int], beta: int, n: int,
    form: list[str], lemma: list[str], pos: list[str],
    lrel: dict[int, str], rrel: dict[int, str],
) -> list[str]:
    s0 = stack[-1]
    s1 = stack[-2] if len(stack) >= 2 else -1
    b0 = beta if beta <= n else -1
    b1 = beta + 1 if beta + 1 <= n else -1
    s0p, s0f, s0l = _attr(pos, s0), _attr(form, s0), _attr(lemma, s0)
    b0p, b0f, b0l = _attr(pos, b0), _attr(form, b0), _attr(lemma, b0)
    b1p, s1p = _attr(pos, b1), _attr(pos, s1)
    dist = "d:" + (str(min(b0 - s0, 8)) if b0 > 0 and s0 > 0 else "_")
    return [
        f"1:{s0p}", f"2:{s0f}", f"3:{s0l}",
        f"4:{b0p}", f"5:{b0f}", f"6:{b0l}",
        f"7:{b1p}", f"8:{s1p}",
        f"9:{s0p}|{b0p}", f"10:{s0f}|{b0p}", f"11:{s0p}|{b0f}",
        f"12:{s0l}|{b0l}", f"13:{b0p}|{b1p}", f"14:{s1p}|{s0p}|{b0p}",
        f"15:{s0p}|{b0p}|{b1p}", f"16:{dist}", f"17:{s0p}|{dist}|{b0p}",
        f"18:lr:{lrel.get(s0, '_')}", f"19:rr:{rrel.get(s0, '_')}",
        f"20:blr:{lrel.get(b0, '_')}",
        f"21:{s0p}|lr:{lrel.get(s0, '_')}|rr:{rrel.get(s0, '_')}",
    ]


# --- averaged perceptron -----------------------------------------------------


class _Perceptron:
    def __init__(self) -> None:
        self.w: dict[str, dict[str, float]] = {}
        self._tot: dict[str, dict[str, float]] = {}
        self._t: dict[str, dict[str, int]] = {}
        self.i = 0

    def score(self, action: str, feats: list[str]) -> float:
        wa = self.w.get(action)
        if not wa:
            return 0.0
        return sum(wa.get(f, 0.0) for f in feats)

    def _bump(self, action: str, feats: list[str], delta: float) -> None:
        wa = self.w.setdefault(action, {})
        ta = self._tot.setdefault(action, {})
        sa = self._t.setdefault(action, {})
        for f in feats:
            ta[f] = ta.get(f, 0.0) + (self.i - sa.get(f, 0)) * wa.get(f, 0.0)
            wa[f] = wa.get(f, 0.0) + delta
            sa[f] = self.i

    def update(self, gold: str, pred: str, feats: list[str]) -> None:
        self.i += 1
        if gold != pred:
            self._bump(gold, feats, 1.0)
            self._bump(pred, feats, -1.0)

    def averaged(self) -> dict[str, dict[str, float]]:
        out: dict[str, dict[str, float]] = {}
        denom = self.i or 1
        for action, wa in self.w.items():
            ta, sa = self._tot.get(action, {}), self._t.get(action, {})
            avg: dict[str, float] = {}
            for f, weight in wa.items():
                total = ta.get(f, 0.0) + (self.i - sa.get(f, 0)) * weight
                if total:
                    avg[f] = total / denom
            if avg:
                out[action] = avg
        return out


def _predict(weights: dict[str, dict[str, float]], legal: list[str], feats: list[str]) -> str:
    best, best_score = legal[0], float("-inf")
    for action in legal:
        wa = weights.get(action)
        s = sum(wa.get(f, 0.0) for f in feats) if wa else 0.0
        if s > best_score:
            best, best_score = action, s
    return best


def _candidate_actions(legal_types: list[str], rels: list[str]) -> list[str]:
    out: list[str] = []
    for t in legal_types:
        if t in (LEFT, RIGHT):
            out.extend(_encode(t, r) for r in rels)
        else:
            out.append(_encode(t))
    return out


# --- train / parse / evaluate ------------------------------------------------


def _relations(trees: list[DepTree]) -> list[str]:
    return sorted({t.relation for tree in trees for t in tree.tokens})


def _train(trees: list[DepTree], epochs: int) -> tuple[dict[str, dict[str, float]], list[str], int]:
    rels = _relations(trees)
    seqs: list[tuple[DepTree, list[tuple[str, str]]]] = []
    for tree in trees:
        actions = _oracle(tree)  # None for non-projective trees → skipped
        if actions is not None:
            seqs.append((tree, actions))
    perc = _Perceptron()
    for _epoch in range(epochs):
        for tree, actions in seqs:
            _replay_train(tree, actions, perc, rels)
    return perc.averaged(), rels, len(seqs)


def _sent_arrays(tree: DepTree) -> tuple[list[str], list[str], list[str], int]:
    n = len(tree.tokens)
    form = ["<root>"] + [t.form for t in tree.tokens]
    lemma = ["<root>"] + [t.lemma for t in tree.tokens]
    pos = ["ROOT"] + [t.upos for t in tree.tokens]
    return form, lemma, pos, n


def _replay_train(tree: DepTree, actions: list[tuple[str, str]], perc: _Perceptron, rels: list[str]) -> None:
    form, lemma, pos, n = _sent_arrays(tree)
    stack, beta = [_ROOT], 1
    head: dict[int, int] = {}
    lrel: dict[int, str] = {}
    rrel: dict[int, str] = {}
    for act_type, rel in actions:
        feats = _features(stack, beta, n, form, lemma, pos, lrel, rrel)
        legal = _candidate_actions(_legal(stack, beta, n, head), rels)
        gold = _encode(act_type, rel)
        pred = _predict(perc.w, legal, feats) if legal else gold
        perc.update(gold, pred, feats)
        _apply(act_type, rel, stack, head, lrel, rrel, beta)
        beta = _advance_beta(act_type, beta)


def _advance_beta(act_type: str, beta: int) -> int:
    return beta + 1 if act_type in (SHIFT, RIGHT) else beta


def _apply(
    act_type: str, rel: str, stack: list[int], head: dict[int, int],
    lrel: dict[int, str], rrel: dict[int, str], beta: int,
) -> None:
    s0 = stack[-1]
    if act_type == SHIFT:
        stack.append(beta)
    elif act_type == RIGHT:
        head[beta] = s0
        rrel[s0] = rel
        stack.append(beta)
    elif act_type == LEFT:
        head[s0] = beta
        lrel[beta] = rel
        stack.pop()
    elif act_type == REDUCE:
        stack.pop()


def _parse_arrays(
    form: list[str], lemma: list[str], pos: list[str], n: int,
    weights: dict[str, dict[str, float]], rels: list[str],
) -> tuple[dict[int, int], dict[int, str]]:
    stack, beta = [_ROOT], 1
    head: dict[int, int] = {}
    rel_of: dict[int, str] = {}
    lrel: dict[int, str] = {}
    rrel: dict[int, str] = {}
    steps = 0
    while beta <= n or len(stack) > 1:
        legal = _candidate_actions(_legal(stack, beta, n, head), rels)
        if not legal:
            break
        feats = _features(stack, beta, n, form, lemma, pos, lrel, rrel)
        choice = _predict(weights, legal, feats)
        act_type, _, rel = choice.partition(":")
        s0 = stack[-1]
        if act_type == RIGHT:
            rel_of[beta] = rel
        elif act_type == LEFT:
            rel_of[s0] = rel
        _apply(act_type, rel, stack, head, lrel, rrel, beta)
        beta = _advance_beta(act_type, beta)
        steps += 1
        if steps > 6 * n + 10:  # safety against pathological loops
            break
    return head, rel_of


def _build_tree(
    form: list[str], lemma: list[str], pos: list[str], n: int,
    head: dict[int, int], rel_of: dict[int, str],
) -> DepTree:
    toks = tuple(
        DepToken(
            id=i, form=form[i], lemma=lemma[i], upos=pos[i],
            head=head.get(i, _ROOT), relation=rel_of.get(i, "ROOT"),
        )
        for i in range(1, n + 1)
    )
    return DepTree(tokens=toks)


# --- model persistence + activation ------------------------------------------


def train_parser(
    *, source_dir: Path | str | None = None, epochs: int = 5, force: bool = False
) -> Path:
    """Train (and cache, gzipped) the parser model, returning its path.

    Prefers the hosted **prebuilt model** (skipping the AGDT download + training);
    falls back to training from the AGDT (downloaded on first use). ``source_dir``
    trains from local fixture XML (tests; no network, no prebuilt fetch)."""
    out = cache_dir() / _MODEL_NAME
    # A present artifact is trusted as-is (a deliberate local build must never be
    # trampled); rebuilt hosted content ships under a new asset name, never in place.
    if out.exists() and not force and source_dir is None:
        return out
    if source_dir is None:
        from ..data import fetch_prebuilt

        if fetch_prebuilt("agdt-derived", out, member=_MODEL_NAME):
            return out
    trees = load_gold_trees(source_dir=source_dir)
    weights, rels, n_proj = _train(trees, epochs)
    model = {"weights": weights, "relations": rels, "sentences": len(trees), "projective": n_proj}
    from .._atomic import atomic_path

    with atomic_path(out) as tmp:
        with gzip.open(tmp, "wt", encoding="utf-8") as f:
            json.dump(model, f, ensure_ascii=False)
    return out


def _load_model(path: Path | str | None = None) -> dict[str, Any]:
    p = Path(path) if path is not None else cache_dir() / _MODEL_NAME
    if not p.exists():
        raise ParserNotLoadedError(f"no parser model at {p}; call use_parser() first")
    model: dict[str, Any] = load_gzip_json(p)
    return model


_ACTIVE: dict[str, Any] | None = None


def use_parser(*, train: bool = True, force: bool = False) -> None:
    """Activate the dependency parser for this session — training the model on first
    use (``train=True``; from the cached AGDT, a few minutes) or loading the cache."""
    global _ACTIVE
    if train and (force or not (cache_dir() / _MODEL_NAME).exists()):
        train_parser(force=force)
    _ACTIVE = _load_model()


def disable_parser() -> None:
    """Deactivate the dependency parser."""
    global _ACTIVE
    _ACTIVE = None


def active() -> dict[str, Any] | None:
    return _ACTIVE


def parse(sentence: str | list[str]) -> DepTree:
    """Parse a Greek sentence (a string or a list of tokens) into a `DepTree`.

    Uses the neural pipeline when it is active (`aegean.greek.use_neural_pipeline`) —
    relations are then **UD** (nsubj, obj, advcl, …) and ``postag`` carries the predicted
    9-char tag. Otherwise requires `use_parser` (the arc-eager baseline, AGDT/Prague
    relations), with POS/lemma from the (treebank-aware) pipeline."""
    from . import joint
    from .tokenize import tokenize_words

    if joint.active() is not None:
        words = tokenize_words(sentence) if isinstance(sentence, str) else list(sentence)
        ana = joint.analyze_sentence(words)
        return DepTree(tuple(
            DepToken(id=i + 1, form=f, lemma=ana.lemma[i], upos=ana.upos[i],
                     head=ana.head[i], relation=ana.deprel[i], postag=ana.xpos[i])
            for i, f in enumerate(ana.tokens)
        ))
    if _ACTIVE is None:
        raise ParserNotLoadedError("parser not loaded — call aegean.greek.use_parser() first")
    from .lemmatize import lemmatize
    from .pos import pos_tag

    words = tokenize_words(sentence) if isinstance(sentence, str) else list(sentence)
    form = ["<root>"] + words
    lemma = ["<root>"] + [lemmatize(w) for w in words]
    pos = ["ROOT"] + [pos_tag(w) for w in words]
    weights = _ACTIVE["weights"]
    rels = _ACTIVE["relations"]
    head, rel_of = _parse_arrays(form, lemma, pos, len(words), weights, rels)
    return _build_tree(form, lemma, pos, len(words), head, rel_of)


def evaluate(
    *, source_dir: Path | str | None = None, holdout: float = 0.1, epochs: int = 5
) -> dict[str, Any]:
    """Train on a split and score the held-out trees → ``{"uas","las","tokens","sentences"}``
    (gold POS/lemma; measures parsing in isolation). Exposed as ``greek.evaluate_parser``."""
    trees = load_gold_trees(source_dir=source_dir)
    cut = max(1, int(len(trees) * (1 - holdout)))
    train_trees, dev_trees = trees[:cut], trees[cut:]
    weights, rels, _ = _train(train_trees, epochs)

    total = correct_u = correct_l = 0
    for tree in dev_trees:
        form, lemma, pos, n = _sent_arrays(tree)
        head, rel_of = _parse_arrays(form, lemma, pos, n, weights, rels)
        for t in tree.tokens:
            total += 1
            if head.get(t.id, _ROOT) == t.head:
                correct_u += 1
                if rel_of.get(t.id, "ROOT") == t.relation:
                    correct_l += 1
    return {
        "uas": correct_u / total if total else 0.0,
        "las": correct_l / total if total else 0.0,
        "tokens": total,
        "sentences": len(dev_trees),
    }
