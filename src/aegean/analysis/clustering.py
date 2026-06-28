"""Sign-class induction by Brown clustering, EXPLORATORY.

Greedy agglomerative Brown clustering (Brown et al. 1992) of a script's signs
from their *distribution* alone. Every sign starts in its own class; the pair
whose merge costs the least average mutual information of the sign-bigram model
is merged, repeatedly, until a target number of classes remains. The result
groups signs that occur in the **same contexts**: signs that tend to be preceded
and followed by the same neighbours.

Aimed at **Cypro-Minoan**, the least-served Aegean script, where every sign
currently carries the same (single) class. It is the natural unsupervised first
question one can ask of an undeciphered signary: do the signs fall into
distributional classes (a candidate vowel/consonant or open/closed split, a
positional grammar) at all?

**EXPLORATORY.** The classes reflect *distribution, not phonetic value*: two
signs in one class share contexts, which is evidence of a shared grammatical or
phonotactic role, never a reading. On a small corpus the induced classes overfit
badly (most sign bigrams are seen once or never), so :func:`induce_classes`
reports the corpus size alongside its quality numbers, and a class boundary is a
lead to inspect, not a decipherment. Pure stdlib; ties broken deterministically
with the shared ``mulberry32`` PRNG so a run is reproducible.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from ..core.model import Document, TokenKind
from .stats import mulberry32

__all__ = [
    "SignClasses",
    "ClusterReport",
    "induce_classes",
]

# Sequence boundary markers, kept distinct from any real sign label. Bigrams
# spanning a word/document boundary carry no information about sign context, so
# the stream is broken at each token: a sign's neighbours are its in-word
# neighbours only.
_START = "\x02"
_END = "\x03"


def _documents(corpus: Any) -> list[Document]:
    """Coerce a Corpus / QueryResults / iterable of Documents to a list."""
    docs = getattr(corpus, "documents", corpus)
    out = list(docs)
    if out and not isinstance(out[0], Document):
        raise TypeError(f"expected a corpus or documents, got {type(out[0]).__name__}")
    return out


def _signs_of(token: Any) -> list[str]:
    """The sign labels of one token (same convention as ``stats`` ``kind='signs'``)."""
    if token.signs:
        return list(token.signs)
    return token.text.split("-") if "-" in token.text else [token.text]


def _sign_sequences(docs: Sequence[Document]) -> list[list[str]]:
    """One bounded sign sequence per multi-sign token across the corpus.

    Only WORD/LOGOGRAM/UNKNOWN tokens contribute signs; numerals, separators,
    and punctuation are skipped. Each token becomes its own ``^ … $`` sequence so
    bigrams never cross a token boundary."""
    keep = {TokenKind.WORD, TokenKind.LOGOGRAM, TokenKind.UNKNOWN}
    seqs: list[list[str]] = []
    for d in docs:
        for t in d.tokens:
            if t.kind not in keep:
                continue
            signs = _signs_of(t)
            if signs:
                seqs.append([_START, *signs, _END])
    return seqs


def _bigram_counts(
    seqs: Sequence[Sequence[str]],
) -> tuple[dict[tuple[str, str], int], list[str]]:
    """Adjacent sign-bigram token counts and the sign vocabulary (boundaries excluded)."""
    bigrams: dict[tuple[str, str], int] = defaultdict(int)
    vocab: dict[str, None] = {}
    for seq in seqs:
        for a, b in zip(seq, seq[1:], strict=False):
            bigrams[(a, b)] += 1
            if a not in (_START, _END):
                vocab[a] = None
            if b not in (_START, _END):
                vocab[b] = None
    return dict(bigrams), list(vocab)


def _xlogx(value: float) -> float:
    """``value · log2 value`` with the limit ``0·log0 = 0``."""
    return value * math.log2(value) if value > 0 else 0.0


@dataclass(frozen=True)
class ClusterReport:
    """Quality of an induced sign-classing, for honest reporting.

    ``n_classes`` is how many classes remain; ``n_signs`` the signs that were
    clustered. ``corpus_signs`` is the number of sign tokens the bigram model saw
    and ``corpus_bigrams`` the number of distinct adjacent pairs: both small on
    Aegean material, which is why the classes overfit (read them as leads).
    ``mutual_information`` is the average MI (bits) of the class-bigram model that
    the merges maximised, ``perplexity`` its ``2^H`` branching factor over the
    class-bigram distribution. ``mi_loss`` is the total MI given up to reach this
    classing from one-sign-per-class (0 when no merge happened)."""

    n_classes: int
    n_signs: int
    corpus_signs: int
    corpus_bigrams: int
    mutual_information: float
    perplexity: float
    mi_loss: float

    def __str__(self) -> str:
        return (
            f"{self.n_classes} classes over {self.n_signs} signs "
            f"(corpus: {self.corpus_signs} sign tokens, {self.corpus_bigrams} bigram types); "
            f"MI={self.mutual_information:.4f} bits, perplexity={self.perplexity:.2f}, "
            f"MI lost={self.mi_loss:.4f}"
        )


@dataclass(frozen=True)
class SignClasses:
    """An induced distributional classing of a script's signs (EXPLORATORY).

    ``class_of`` maps a sign label to its integer class id (``-1`` for a sign the
    corpus never attested). ``classes`` lists the members of each class. The
    ``report`` carries the quality numbers and the corpus size they rest on.

    The classes reflect distribution, not phonetic value: two signs share a class
    because they occur in the same contexts, which is a candidate grammatical or
    phonotactic role, never a reading."""

    _class_of: dict[str, int]
    _members: list[list[str]]
    report: ClusterReport

    def class_of(self, sign: str) -> int:
        """The class id of ``sign`` (``-1`` if the corpus never attested it)."""
        return self._class_of.get(sign, -1)

    def classes(self) -> list[list[str]]:
        """The classes as lists of sign labels, sign-sorted within each class."""
        return [list(members) for members in self._members]

    def __len__(self) -> int:
        return len(self._members)


def _average_mutual_information(
    left: dict[int, int],
    right: dict[int, int],
    pair: dict[tuple[int, int], int],
    total: int,
) -> float:
    """Average MI (bits) of a class-bigram distribution from its integer counts.

    ``left[c]`` / ``right[c]`` are class ``c``'s predecessor / successor token
    totals, ``pair[(c, d)]`` the count of class ``c`` immediately followed by
    class ``d``, and ``total`` the bigram-token grand total."""
    if total <= 0:
        return 0.0
    mi = 0.0
    for (c, d), n in pair.items():
        if n <= 0:
            continue
        p = n / total
        mi += p * math.log2(p * total * total / (left[c] * right[d]))
    return mi


def induce_classes(corpus: Any, *, n_classes: int) -> SignClasses:
    """Induce ``n_classes`` distributional sign classes by Brown clustering.

    EXPLORATORY. Builds the adjacent sign-bigram model of ``corpus`` (a Corpus,
    QueryResults, or document list; numerals/separators/punctuation skipped, with
    each token bounded so bigrams never cross a token edge), seeds one class per
    sign, then greedily merges the class pair whose merge gives up the least
    average mutual information of the class-bigram model, until ``n_classes``
    classes remain (Brown et al. 1992). Ties in MI loss are broken by the lower
    pre-sorted class index, jittered with the shared ``mulberry32`` PRNG, so a run
    is reproducible.

    The result is a :class:`SignClasses`: signs in one class occur in the same
    contexts, which is a candidate shared role (a vowel/consonant or open/closed
    split, a positional pattern), **not** a phonetic reading. On the small Aegean
    corpora (especially undeciphered Cypro-Minoan and Linear A) most sign bigrams
    are seen once or never, so the classing overfits: the attached ``report``
    carries the corpus size so the classes are read as leads, not facts.

    Raises ``ValueError`` for ``n_classes < 1`` or a corpus with no multi-sign
    sequences to learn from.
    """
    if n_classes < 1:
        raise ValueError("n_classes must be at least 1")
    docs = _documents(corpus)
    seqs = _sign_sequences(docs)
    bigrams, vocab = _bigram_counts(seqs)
    if not vocab:
        raise ValueError("corpus has no signs to cluster")

    vocab.sort()
    index = {sign: i for i, sign in enumerate(vocab)}
    n = len(vocab)
    target = min(n_classes, n)

    # Boundary markers get their own fixed class ids past the sign range so the
    # model knows where sequences start and end, but they are never merged and
    # never reported as a sign class.
    start_id = n
    end_id = n + 1
    total = sum(bigrams.values())

    # Class-bigram counts keyed by integer class id. Signs map to their own id;
    # boundaries map to the two reserved ids.
    def cid(sym: str) -> int:
        if sym == _START:
            return start_id
        if sym == _END:
            return end_id
        return index[sym]

    pair: dict[tuple[int, int], int] = defaultdict(int)
    left: dict[int, int] = defaultdict(int)
    right: dict[int, int] = defaultdict(int)
    for (sa, sb), c in bigrams.items():
        ca, cb = cid(sa), cid(sb)
        pair[(ca, cb)] += c
        left[ca] += c
        right[cb] += c

    members: dict[int, list[str]] = {i: [vocab[i]] for i in range(n)}
    succ: dict[int, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    pred: dict[int, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    for (ca, cb), c in pair.items():
        succ[ca][cb] += c
        pred[cb][ca] += c

    base_mi = _average_mutual_information(dict(left), dict(right), dict(pair), total)

    rng = mulberry32(0)
    active = list(range(n))  # mergeable class ids (signs only), in sorted order

    def merge_loss(a: int, b: int) -> float:
        """MI given up by merging classes ``a`` and ``b`` (lower is cheaper)."""
        before = (
            _xlogx_terms(a, succ, pred, left, right, total)
            + _xlogx_terms(b, succ, pred, left, right, total)
            - _shared_term(a, b, pair, left, right, total)
        )
        # Merged class: pool the marginals and the directed counts, then the
        # self-loop folds the four a/b interactions into one.
        ml = left[a] + left[b]
        mr = right[a] + right[b]
        out_counts: dict[int, int] = defaultdict(int)
        for d, c in succ.get(a, {}).items():
            out_counts[d if d not in (a, b) else -1] += c
        for d, c in succ.get(b, {}).items():
            out_counts[d if d not in (a, b) else -1] += c
        in_counts: dict[int, int] = defaultdict(int)
        for d, c in pred.get(a, {}).items():
            in_counts[d if d not in (a, b) else -1] += c
        for d, c in pred.get(b, {}).items():
            in_counts[d if d not in (a, b) else -1] += c
        after = 0.0
        for d, c in out_counts.items():
            if d == -1:
                after += _term(c, ml, mr, total)  # self-loop of the merged class
            else:
                after += _term(c, ml, right[d], total)
        for d, c in in_counts.items():
            if d == -1:
                continue  # already counted as the self-loop above
            after += _term(c, left[d], mr, total)
        return before - after

    # Greedy agglomeration: until the target class count, find the pair whose
    # merge loses the least MI and merge it.
    while len(active) > target:
        best: tuple[float, float, int, int] | None = None
        for i in range(len(active)):
            a = active[i]
            for j in range(i + 1, len(active)):
                b = active[j]
                loss = merge_loss(a, b)
                jitter = rng() * 1e-12
                key = (loss, jitter, a, b)
                if best is None or key < best:
                    best = key
        assert best is not None
        _, _, a, b = best
        _apply_merge(a, b, members, succ, pred, pair, left, right)
        active.remove(b)

    final_mi = _average_mutual_information(dict(left), dict(right), dict(pair), total)
    perplexity = 2.0 ** _conditional_entropy(succ, left, right, total)

    # Renumber the surviving classes 0..k-1 by their smallest member (stable),
    # and emit the sign→class map and the sorted member lists.
    survivors = sorted(active, key=lambda c: min(members[c]))
    class_of: dict[str, int] = {}
    member_lists: list[list[str]] = []
    for new_id, old in enumerate(survivors):
        ms = sorted(members[old])
        member_lists.append(ms)
        for sign in ms:
            class_of[sign] = new_id

    report = ClusterReport(
        n_classes=len(survivors),
        n_signs=n,
        corpus_signs=sum(1 for seq in seqs for s in seq if s not in (_START, _END)),
        corpus_bigrams=len(bigrams),
        mutual_information=final_mi,
        perplexity=perplexity,
        mi_loss=base_mi - final_mi,
    )
    return SignClasses(_class_of=class_of, _members=member_lists, report=report)


def _term(count: int, lmass: int, rmass: int, total: int) -> float:
    """One ``p·log2(p / (pl·pr))`` MI term, in bits, from integer counts."""
    if count <= 0 or lmass <= 0 or rmass <= 0:
        return 0.0
    p = count / total
    return p * math.log2(p * total * total / (lmass * rmass))


def _xlogx_terms(
    c: int,
    succ: dict[int, dict[int, int]],
    pred: dict[int, dict[int, int]],
    left: dict[int, int],
    right: dict[int, int],
    total: int,
) -> float:
    """The MI mass touching class ``c`` (its outgoing and incoming bigram terms)."""
    s = 0.0
    for d, n in succ.get(c, {}).items():
        s += _term(n, left[c], right[d], total)
    for d, n in pred.get(c, {}).items():
        if d == c:
            continue  # the self-loop is already in the outgoing sum
        s += _term(n, left[d], right[c], total)
    return s


def _shared_term(
    a: int,
    b: int,
    pair: dict[tuple[int, int], int],
    left: dict[int, int],
    right: dict[int, int],
    total: int,
) -> float:
    """The a↔b cross terms double-counted when ``_xlogx_terms(a)`` and
    ``_xlogx_terms(b)`` are summed (a→b counted in both, b→a likewise)."""
    s = 0.0
    s += _term(pair.get((a, b), 0), left[a], right[b], total)
    s += _term(pair.get((b, a), 0), left[b], right[a], total)
    return s


def _apply_merge(
    a: int,
    b: int,
    members: dict[int, list[str]],
    succ: dict[int, dict[int, int]],
    pred: dict[int, dict[int, int]],
    pair: dict[tuple[int, int], int],
    left: dict[int, int],
    right: dict[int, int],
) -> None:
    """Fold class ``b`` into class ``a`` in place across every count table."""
    members[a] = members[a] + members[b]
    left[a] += left[b]
    right[a] += right[b]

    # Redirect every bigram touching b onto a, then drop b's rows/columns.
    out_b = dict(succ.get(b, {}))
    in_b = dict(pred.get(b, {}))

    for d, c in out_b.items():
        dd = a if d == b else d
        pair[(b, d)] = 0
        del pair[(b, d)]
        pair[(a, dd)] = pair.get((a, dd), 0) + c
        succ[b].pop(d, None)
        if d in pred:
            pred[d].pop(b, None)
        succ[a][dd] = succ[a].get(dd, 0) + c
        pred[dd][a] = pred[dd].get(a, 0) + c
    for d, c in in_b.items():
        if d == b:
            continue  # the b→b self-loop was handled in out_b
        dd = a if d == b else d
        pair[(d, b)] = 0
        del pair[(d, b)]
        pair[(dd, a)] = pair.get((dd, a), 0) + c
        pred[b].pop(d, None)
        if d in succ:
            succ[d].pop(b, None)
        succ[dd][a] = succ[dd].get(a, 0) + c
        pred[a][dd] = pred[a].get(dd, 0) + c

    succ.pop(b, None)
    pred.pop(b, None)
    left.pop(b, None)
    right.pop(b, None)
    members.pop(b, None)


def _conditional_entropy(
    succ: dict[int, dict[int, int]],
    left: dict[int, int],
    right: dict[int, int],
    total: int,
) -> float:
    """``H(next | current)`` in bits over the class-bigram distribution.

    The perplexity ``2^H`` is the effective branching factor of the class model:
    how many successor classes a class predicts, on average."""
    if total <= 0:
        return 0.0
    h = 0.0
    for c, outs in succ.items():
        for d, n in outs.items():
            if n <= 0:
                continue
            p_joint = n / total
            p_cond = n / left[c]
            h -= p_joint * math.log2(p_cond)
    return h
