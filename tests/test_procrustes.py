"""Cross-script Procrustes alignment: the MEASURED NULL it ships, plus its calibration invariants.

The module is EXPLORATORY and, more to the point, it is the honest instrument that MEASURED a
null: distributional embedding alignment recovers no Linear A -> Linear B sign correspondence at
this corpus scale (leave-one-out top-1 = 0.000 on the 53 known chart-shared pairs). These tests
pin that null two ways:

- fast, always-on: a scrambled-target construction shows the leave-one-out recovery collapses to
  chance when there is no cross-space signal, and the shipped evidence file's null numbers are
  checked for internal consistency (the benchmark-guard pattern: a doc/evidence edit that claims
  signal fails here, per-PR, offline);
- heavy, when the data is present: the real leave-one-out is re-run on the bundled Linear A vs the
  syllabogram-restricted DAMOS Linear B and asserted at chance (top-1 = 0.000). This is the guard
  that fires if a future change ever "finds signal" on the real corpora, demanding scrutiny.

The remaining tests assert the calibration mathematics the honesty architecture rests on: aligning
a space to itself (or to a known rotation of itself) recovers the identity above the stated floor.
The fast tests use deterministic stub embeddings so they need no corpus and run under bare pytest.
"""

import json
import math
from pathlib import Path

import pytest

import aegean.data as data
from aegean.analysis.embeddings import SignEmbeddings
from aegean.analysis.procrustes import (
    Correspondence,
    IdentityCheck,
    ProcrustesAlignment,
    RankReport,
    align_embeddings,
    align_scripts,
    rank_known_pairs,
    recover_identity,
    shared_label_anchors,
)
from aegean.analysis.stats import mulberry32
from aegean.core.model import Document, Token, TokenKind

ROOT = Path(__file__).resolve().parents[1]
_EVIDENCE = ROOT / "training" / "results" / "procrustes-null-2026-07-11.json"


# --------------------------------------------------------------------------- #
# stub embeddings
# --------------------------------------------------------------------------- #


def _unit(v: list[float]) -> tuple[float, ...]:
    n = math.sqrt(sum(x * x for x in v))
    return tuple(x / n for x in v) if n else tuple(v)


def _low_rank_stub(n: int = 10) -> SignEmbeddings:
    """n signs living on a 3-D structure, well spread, so a subset of anchors constrains
    the whole rotation (held-out signs can genuinely generalize)."""
    vocab = tuple(chr(ord("A") + i) for i in range(n))
    vecs = []
    for i in range(n):
        a = 2 * math.pi * i / n
        vecs.append(_unit([math.cos(a), math.sin(a), 0.3 * math.cos(3 * a)]))
    return SignEmbeddings(vocab=vocab, vectors=tuple(vecs), dim=3, window=1)


def _rotate3(v: tuple[float, ...]) -> tuple[float, ...]:
    x, y, z = v
    th = math.radians(35)
    c, s = math.cos(th), math.sin(th)
    x, y = c * x - s * y, s * x + c * y
    ph = math.radians(20)
    c2, s2 = math.cos(ph), math.sin(ph)
    y, z = c2 * y - s2 * z, s2 * y + c2 * z
    return _unit([x, y, z])


def _rotated_copy(emb: SignEmbeddings) -> SignEmbeddings:
    return SignEmbeddings(
        vocab=emb.vocab,
        vectors=tuple(_rotate3(v) for v in emb.vectors),
        dim=emb.dim,
        window=emb.window,
    )


def _scrambled_copy(emb: SignEmbeddings, seed: int = 7) -> SignEmbeddings:
    """Same labels, but each label carries a DIFFERENT sign's vector: the label<->vector
    correspondence is destroyed, so no rotation can recover the identity. This is the
    controlled 'no cross-space signal' case."""
    rand = mulberry32(seed)
    order = list(range(len(emb.vocab)))
    for i in range(len(order) - 1, 0, -1):
        j = int(rand() * (i + 1))
        order[i], order[j] = order[j], order[i]
    return SignEmbeddings(
        vocab=emb.vocab,
        vectors=tuple(emb.vectors[order[i]] for i in range(len(emb.vocab))),
        dim=emb.dim,
        window=emb.window,
    )


# --------------------------------------------------------------------------- #
# THE MEASURED NULL, fast pins (always on, offline)
# --------------------------------------------------------------------------- #


def test_no_signal_collapses_leave_one_out_to_chance():
    # When the target carries no consistent mapping of the source (labels scrambled onto
    # other signs' vectors), leave-one-out recovery must collapse to chance: top-1 = 0 and
    # the median rank at or below chance quality (no better than guessing). This is the
    # functional shape of the module's headline result, checked fast without a corpus.
    src = _low_rank_stub(12)
    tgt = _scrambled_copy(src)
    rep = rank_known_pairs(src, tgt, [(s, s) for s in src.vocab], leave_one_out=True)
    assert rep.top1 == 0.0
    # median rank is no better than chance (>= chance - 1): no recovered signal.
    assert rep.median_rank >= rep.chance_median - 1.0


def test_shipped_null_evidence_file_is_internally_consistent():
    # The benchmark-guard pattern: the shipped evidence file's NULL numbers are pinned so an
    # edit that quietly claims cross-script signal (a non-zero top-1, a tiny median) fails
    # here, per-PR and offline, without needing the heavy re-measure.
    ev = json.loads(_EVIDENCE.read_text(encoding="utf-8"))
    loo = ev["leave_one_out_null"]
    assert loo["n_pairs"] == 53
    assert loo["n_targets"] == 73
    assert loo["top1"] == 0.0  # the decisive null: no pair recovered at rank 1
    assert loo["top5"] <= 0.15  # at chance (chance is 5/73 = 0.068)
    assert loo["chance_median"] == (loo["n_targets"] + 1) / 2 == 37.0
    ranks = loo["ranks"]
    assert len(ranks) == loo["n_pairs"]
    srt = sorted(ranks)
    n = len(srt)
    median = srt[n // 2] if n % 2 else (srt[n // 2 - 1] + srt[n // 2]) / 2
    assert median == loo["median_rank"]
    # median is short of recovery (buried) yet not worse than chance.
    assert 15.0 <= loo["median_rank"] <= loo["chance_median"]
    # the self-alignment sanity floor is HIGH (machinery works) but not a clean 1.0 on the
    # real, twin-bearing Linear A embedding.
    ident = ev["identity_sanity_floor"]
    assert 0.85 <= ident["top1_recovery"] < 1.0


# --------------------------------------------------------------------------- #
# THE MEASURED NULL, heavy re-run on the bundled corpora (skipped without DAMOS)
# --------------------------------------------------------------------------- #

_DAMOS_CACHED = data.is_downloaded(data._REMOTE["damos-corpus"], data.cache_dir())


def _syllabogram_damos(damos) -> list[Document]:
    """DAMOS restricted to the 74 canonical Linear B syllabograms.

    Full-vocab DAMOS embeddings are intractable for the pure-Python SVD, so each sign is
    cleaned with the Linear B Leiden normalizer and kept only if a canonical syllabogram;
    the token count is preserved (document lines stay valid) and the embeddings builder
    then drops any word left with fewer than two signs."""
    from aegean.core.script import get_script
    from aegean.scripts.linearb.lexicon import _norm

    syllabograms = {
        s.label for s in get_script("linearb").sign_inventory
        if s.attrs.get("signClass") == "syllabogram"
    }
    out: list[Document] = []
    for d in damos:
        toks: list[Token] = []
        for t in d.tokens:
            if t.kind is not TokenKind.WORD:
                toks.append(t)
                continue
            raw = list(t.signs) or (t.text.split("-") if "-" in t.text else [t.text])
            kept = [s for s in (_norm(x) for x in raw) if s in syllabograms]
            toks.append(Token(text="-".join(kept), kind=TokenKind.WORD, signs=tuple(kept)))
        out.append(Document(id=d.id, script_id=d.script_id, tokens=toks, lines=d.lines))
    return out


@pytest.mark.skipif(not _DAMOS_CACHED, reason="damos-corpus not cached (no network in CI)")
def test_leave_one_out_null_on_the_bundled_corpora():
    # THE headline guard, re-measured live: aligning the bundled Linear A embedding to the
    # syllabogram-restricted DAMOS Linear B embedding recovers NONE of the 53 known
    # chart-shared pairs at rank 1. If a future change ever produces cross-script signal
    # (a non-zero top-1, a tiny median), this fails loudly and demands scrutiny. Bounds
    # match training/results/procrustes-null-2026-07-11.json. Heavy (~5 min); gated on the
    # fetched DAMOS corpus being present.
    import aegean
    from aegean.analysis import sign_embeddings

    la = sign_embeddings(aegean.load("lineara"), dim=50, window=1)
    lb = sign_embeddings(_syllabogram_damos(list(aegean.load("damos"))), dim=50, window=1)

    # self-alignment sanity floor: the machinery recovers a space aligned to itself well
    # (high, though not a clean 1.0 because of distributional twins), in stark contrast to
    # the cross-script null below. Cheap; also checked twice for determinism.
    ident = recover_identity(la, anchor_fraction=1.0, seed=1)
    assert ident.top1_recovery >= 0.85
    assert recover_identity(la, anchor_fraction=1.0, seed=1).top1_recovery == ident.top1_recovery

    pairs = shared_label_anchors(la, lb)
    assert len(pairs) == 53
    rep = rank_known_pairs(la, lb, pairs, leave_one_out=True)
    assert rep.n == 53
    assert rep.n_targets == 73
    assert rep.chance_median == 37.0
    assert rep.top1 == 0.0  # the null: no known pair recovered at rank 1
    assert rep.top5 <= 0.15  # at chance
    assert 20.0 <= rep.median_rank <= 34.0  # buried; below chance yet far from recovery
    # the self-alignment floor is dramatically above the cross-script recovery.
    assert ident.top1_recovery > rep.top1 + 0.5


# --------------------------------------------------------------------------- #
# THE KEY CORRECTNESS INVARIANT: self-alignment recovers the identity
# --------------------------------------------------------------------------- #


def test_identity_recovery_full_anchor_is_exact():
    # Aligning a CLEAN, twin-free space to itself with every sign anchored MUST recover the
    # identity: each sign's rank-1 correspondence is itself. This is the calibration sanity
    # floor in the ideal case (on a real corpus it falls short only on distributional twins).
    stub = _low_rank_stub()
    check = recover_identity(stub, anchor_fraction=1.0, seed=1)
    assert isinstance(check, IdentityCheck)
    assert check.n == len(stub.vocab)
    assert check.top1_recovery == 1.0
    assert check.top5_recovery == 1.0


def test_identity_recovery_generalizes_from_a_subset():
    # A 50% anchor subset of a low-rank space still recovers held-out signs (the rotation
    # is fully determined by well-spread anchors). Stated floor: perfect here.
    stub = _low_rank_stub(12)
    check = recover_identity(stub, anchor_fraction=0.5, seed=2)
    assert check.top1_recovery >= 0.8


def test_alignment_recovers_a_known_rotation():
    # Target = source rotated by a known 3-D rotation. With all signs anchored, alignment
    # must map each source sign nearest to its own (rotated) image: top-1 recovery = 1.0.
    src = _low_rank_stub()
    tgt = _rotated_copy(src)
    anchors = [(s, s) for s in src.vocab]
    al = align_embeddings(src, tgt, anchors)
    assert al.anchor_fit == pytest.approx(1.0, abs=1e-6)
    recovered = sum(
        1 for s in src.vocab if al.correspondences(s, k=1)[0].target_sign == s
    )
    assert recovered == len(src.vocab)


def test_alignment_generalizes_to_held_out_signs():
    # Learn the rotation from a subset of anchors; held-out source signs still map to their
    # own rotated images. This is the honest generalization the calibration measures.
    src = _low_rank_stub(10)
    tgt = _rotated_copy(src)
    anchors = [(s, s) for s in src.vocab[:6]]
    al = align_embeddings(src, tgt, anchors)
    held = src.vocab[6:]
    recovered = sum(
        1 for s in held if al.correspondences(s, k=1)[0].target_sign == s
    )
    assert recovered / len(held) >= 0.5


# --------------------------------------------------------------------------- #
# rank_known_pairs: recovers a known mapping, and behaves at chance on noise
# --------------------------------------------------------------------------- #


def test_rank_known_pairs_recovers_a_clean_mapping_leave_one_out():
    src = _low_rank_stub(10)
    tgt = _rotated_copy(src)
    pairs = [(s, s) for s in src.vocab]
    rep = rank_known_pairs(src, tgt, pairs, leave_one_out=True)
    assert isinstance(rep, RankReport)
    assert rep.leave_one_out
    assert rep.n == len(pairs)
    assert rep.n_targets == len(tgt.vocab)
    # A clean, well-determined mapping is recovered even holding each pair out.
    assert rep.top1 >= 0.8
    assert rep.median_rank <= 2


def test_rank_known_pairs_chance_median_property():
    src = _low_rank_stub(8)
    tgt = _rotated_copy(src)
    pairs = [(s, s) for s in src.vocab]
    rep = rank_known_pairs(src, tgt, pairs, leave_one_out=False)
    # chance_median is (n_targets + 1) / 2 -- the yardstick a real result is read against.
    assert rep.chance_median == pytest.approx((len(tgt.vocab) + 1) / 2)
    assert all(1 <= r <= rep.n_targets for r in rep.ranks)


# --------------------------------------------------------------------------- #
# shared_label_anchors: value-based pairing with subscript folding
# --------------------------------------------------------------------------- #


def test_shared_label_anchors_folds_subscripts():
    src = SignEmbeddings(
        vocab=("RA₂", "PA₃", "QQQ"),
        vectors=(_unit([1, 0]), _unit([0, 1]), _unit([1, 1])),
        dim=2,
        window=1,
    )
    tgt = SignEmbeddings(
        vocab=("RA2", "PA3", "ZZZ"),
        vectors=(_unit([1, 0]), _unit([0, 1]), _unit([1, 1])),
        dim=2,
        window=1,
    )
    pairs = shared_label_anchors(src, tgt)
    # RA₂/RA2 and PA₃/PA3 pair by folded value; QQQ/ZZZ do not.
    assert ("RA₂", "RA2") in pairs
    assert ("PA₃", "PA3") in pairs
    assert all(s not in ("QQQ",) for s, _ in pairs)
    assert pairs == sorted(pairs)


# --------------------------------------------------------------------------- #
# correspondences / hypotheses ordering
# --------------------------------------------------------------------------- #


def test_correspondences_are_rank_ordered_and_capped():
    src = _low_rank_stub()
    tgt = _rotated_copy(src)
    al = align_embeddings(src, tgt, [(s, s) for s in src.vocab])
    corr = al.correspondences("A", k=3)
    assert len(corr) == 3
    assert [c.rank for c in corr] == [1, 2, 3]
    # Scores are non-increasing.
    assert corr[0].score >= corr[1].score >= corr[2].score
    assert all(isinstance(c, Correspondence) for c in corr)
    assert al.correspondences("A", k=0) == []


def test_hypotheses_global_list_sorted_by_score():
    src = _low_rank_stub()
    tgt = _rotated_copy(src)
    al = align_embeddings(src, tgt, [(s, s) for s in src.vocab])
    hyps = al.hypotheses(k=1, top=5)
    assert len(hyps) == 5
    scores = [c.score for c in hyps]
    assert scores == sorted(scores, reverse=True)


def test_alignment_is_a_frozen_dataclass():
    src = _low_rank_stub()
    al = align_embeddings(src, _rotated_copy(src), [(s, s) for s in src.vocab])
    assert isinstance(al, ProcrustesAlignment)
    assert al.dim == 3
    assert al.n_anchors == len(src.vocab)


# --------------------------------------------------------------------------- #
# adversarial / bad input
# --------------------------------------------------------------------------- #


def test_align_rejects_empty_vocab():
    empty = SignEmbeddings(vocab=(), vectors=(), dim=3, window=1)
    good = _low_rank_stub()
    with pytest.raises(ValueError):
        align_embeddings(empty, good, [])


def test_align_rejects_anchors_absent_from_vocab():
    src = _low_rank_stub()
    tgt = _rotated_copy(src)
    with pytest.raises(ValueError):
        align_embeddings(src, tgt, [("NOPE", "ALSO-NOPE")])


def test_correspondences_unknown_source_sign_raises():
    src = _low_rank_stub()
    al = align_embeddings(src, _rotated_copy(src), [(s, s) for s in src.vocab])
    with pytest.raises(KeyError):
        al.correspondences("ZZZ")


def test_recover_identity_rejects_bad_fraction():
    stub = _low_rank_stub()
    with pytest.raises(ValueError):
        recover_identity(stub, anchor_fraction=0.0)
    with pytest.raises(ValueError):
        recover_identity(stub, anchor_fraction=1.5)


def test_recover_identity_rejects_empty_vocab():
    empty = SignEmbeddings(vocab=(), vectors=(), dim=3, window=1)
    with pytest.raises(ValueError):
        recover_identity(empty)


def test_rank_known_pairs_rejects_no_valid_pairs():
    src = _low_rank_stub()
    tgt = _rotated_copy(src)
    with pytest.raises(ValueError):
        rank_known_pairs(src, tgt, [("NOPE", "NOPE")])


def test_align_scripts_builds_embeddings_and_auto_anchors():
    # Two toy corpora sharing sign labels: align_scripts learns embeddings for both and,
    # with anchors=None, auto-derives the shared-value anchors and aligns.
    def _corpus(cid: str) -> list[Document]:
        words = [["A", "B", "C"], ["B", "C", "D"], ["A", "C", "D"], ["A", "B", "D"]]
        toks = [Token(text="-".join(w), kind=TokenKind.WORD, signs=tuple(w)) for w in words]
        return [Document(id=cid, script_id="toy", tokens=toks, lines=[list(range(len(toks)))])]

    al = align_scripts(
        _corpus("s"),
        _corpus("t"),
        source_script="src",
        target_script="tgt",
        dim=5,
        window=1,
    )
    assert isinstance(al, ProcrustesAlignment)
    assert al.source_script == "src" and al.target_script == "tgt"
    # The shared signs A/B/C/D were auto-derived as anchors.
    assert al.n_anchors >= 4
    # Identical corpora -> the rotation is near-identity: each sign maps to itself.
    assert al.correspondences("A", k=1)[0].target_sign == "A"


def test_determinism_of_alignment():
    src = _low_rank_stub()
    tgt = _rotated_copy(src)
    anchors = [(s, s) for s in src.vocab]
    a = align_embeddings(src, tgt, anchors)
    b = align_embeddings(src, tgt, anchors)
    assert a.rotation == b.rotation
    assert a.hypotheses() == b.hypotheses()
