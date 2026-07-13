"""Tests for the neural pipeline plumbing — MST, FEATS, joint post-processing, hooks.

All offline: the joint model's post-processing is exercised through a stubbed `_run`
(no ONNX), and the dispatch hooks through a fake active model. The real fetched
artifact is integration-tested separately once published."""

from __future__ import annotations

import pytest

np = pytest.importorskip("numpy")

from aegean.greek import joint  # noqa: E402
from aegean.greek.mst import decode_mst  # noqa: E402
from aegean.greek.udfeats import feats_from_xpos  # noqa: E402


# --- MST -------------------------------------------------------------------------


def test_mst_simple_chain() -> None:
    # 2 words; word1 wants ROOT, word2 wants word1
    scores = np.array([[5.0, -1.0, -1.0],     # dep 1: ROOT best
                       [-1.0, 5.0, -1.0]])    # dep 2: head 1 best
    assert decode_mst(scores) == [0, 1]


def test_mst_breaks_cycles() -> None:
    # greedy heads would be 1<->2 (a cycle); MST must break it via the root
    scores = np.array([[1.0, -9.0, 5.0],      # dep 1 prefers head 2
                       [-9.0, 5.0, -9.0]])    # dep 2 prefers head 1
    heads = decode_mst(scores)
    assert sorted(heads) != [1, 2] or 0 in heads  # no pure cycle survives
    assert heads.count(0) == 1                    # exactly one root
    # tree-ness: every node reaches the root
    for start in (1, 2):
        seen, h = set(), start
        while h != 0:
            assert h not in seen
            seen.add(h)
            h = heads[h - 1]


def test_mst_enforces_single_root() -> None:
    # both words prefer ROOT; only the better one may keep it
    scores = np.array([[9.0, -1.0, 0.0],
                       [8.0, 0.0, -1.0]])
    heads = decode_mst(scores)
    assert heads.count(0) == 1
    assert heads[0] == 0  # the higher-scoring root attachment wins


# --- FEATS (package-level contract; the converter re-exports this) -----------------


def test_feats_from_xpos_contract() -> None:
    assert feats_from_xpos("v3ppia---") == (
        "Mood=Ind|Number=Plur|Person=3|Tense=Pres|VerbForm=Fin|Voice=Act"
    )
    assert feats_from_xpos("v1sria---") == (
        "Aspect=Perf|Mood=Ind|Number=Sing|Person=1|Tense=Past|VerbForm=Fin|Voice=Act"
    )
    assert feats_from_xpos("a-s---mac") == "Case=Acc|Degree=Cmp|Gender=Masc|Number=Sing"
    assert feats_from_xpos("d--------") == "_"
    assert feats_from_xpos("") == "_"


# --- joint post-processing through a stubbed runner --------------------------------


def _stub_model() -> joint._JointModel:
    """A _JointModel whose _run returns deterministic logits, no ONNX involved.

    Sentence: ['ὁ', 'λόγος', 'ἐστί'] → DET(det,2) NOUN(nsubj,3) VERB(root,0)."""
    m = object.__new__(joint._JointModel)  # skip __init__ (no artifact on disk)
    m._np = np
    upos_labels = ["DET", "NOUN", "VERB", "X"]
    deprels = ["det", "nsubj", "root", "dep"]
    m.inv = {"upos": dict(enumerate(upos_labels)),
             "deprel": dict(enumerate(deprels))}
    for i in range(9):
        m.inv[f"x{i}"] = {0: "-", 1: "l", 2: "n", 3: "v"}
    m.trees = [["sub", "λόγος"]]          # script 0 rewrites anything to λόγος
    m.lookup_form = {"ὁ": "ὁ"}
    m.lookup_form_upos = {"ἐστί|VERB": "εἰμί"}
    m.lookup_lower = {}

    # form → (upos label id, x0 char id); the stub works for any sentence length
    by_form = {"ὁ": (0, 1), "λόγος": (1, 2), "ἐστί": (2, 3)}

    def fake_run(words: list[str]) -> dict:
        n = len(words)
        word_pos = list(range(1, n + 1))  # pretend 1 subword per word after <s>
        seq = n + 2
        def tag(labels: list[int], n_labels: int) -> np.ndarray:
            a = np.full((1, seq, n_labels), -9.0)
            for w, lab in enumerate(labels):
                a[0, word_pos[w], lab] = 9.0
            return a
        upos_ids = [by_form.get(w, (3, 0))[0] for w in words]
        x0_ids = [by_form.get(w, (3, 0))[1] for w in words]
        out = {"upos": tag(upos_ids, 4), "x0": tag(x0_ids, 4)}
        for i in range(1, 9):
            out[f"x{i}"] = tag([0] * n, 4)
        # a head chain: word i → word i+1; the last word → ROOT
        arc = np.full((1, n, n + 1), -9.0)
        rel = np.full((1, 4, n, n + 1), -9.0)
        rel_ids = [0, 1, 2, 3]  # det, nsubj, root, dep — cycled by position
        for w in range(n):
            h = w + 2 if w < n - 1 else 0
            arc[0, w, h] = 9.0
            rel[0, rel_ids[min(w, 2)] if w < n - 1 else 2, w, h] = 9.0
        out["arc"] = arc
        out["rel"] = rel
        out["lemma"] = np.full((1, n, 1), 0.0)   # script 0 for everyone
        out["_word_pos"] = word_pos
        out["_kept"] = list(range(n))
        return out

    m._run = fake_run  # type: ignore[method-assign]
    return m


def test_joint_analyze_end_to_end_logic() -> None:
    ana = _stub_model().analyze(["ὁ", "λόγος", "ἐστί"])
    assert ana.upos == ("DET", "NOUN", "VERB")
    assert ana.head == (2, 3, 0)
    assert ana.deprel == ("det", "nsubj", "root")
    assert ana.xpos[0].startswith("l") and ana.xpos[2].startswith("v")
    assert ana.feats == ("_", "_", "_")  # all positions '-' beyond pos0
    # lemma composition: form lookup beats the script; (form|UPOS) resolves the copula;
    # the script covers the rest
    assert ana.lemma == ("ὁ", "λόγος", "εἰμί")


def test_joint_analyze_empty_sentence() -> None:
    assert _stub_model().analyze([]) == joint.SentenceAnalysis((), (), (), (), (), (), (), ())


def test_joint_analyze_populates_lemma_resolved() -> None:
    # ὁ resolves via the form lookup and ἐστί via the (form|UPOS) lookup; λόγος goes
    # through the edit script, whose output equals the surface form — no lookup confirms
    # it, so it is honestly flagged unresolved (needs review), not counted as grounded
    ana = _stub_model().analyze(["ὁ", "λόγος", "ἐστί"])
    assert ana.lemma_resolved == (True, False, True)


def test_compose_lemma_reports_whether_it_resolved() -> None:
    """The D1 fix: `_compose_lemma` must report resolution by *which branch fired*, not by a
    surface-string compare. A lookup hit whose lemma equals the form (a nominative) is a real
    analysis (resolved=True); only the terminal fall-through is resolved=False."""
    from types import SimpleNamespace

    hit = SimpleNamespace(
        lookup_form_upos={}, lookup_form={"λόγος": "λόγος"}, lookup_lower={}, trees=[]
    )
    # lemma == form, yet it came from a lookup → resolved True (NOT an identity fall-through)
    assert joint._compose_lemma("λόγος", "NOUN", 0, hit) == (
        "λόγος", True, joint.LemmaSource.NEURAL_LOOKUP,
    )

    miss = SimpleNamespace(lookup_form_upos={}, lookup_form={}, lookup_lower={}, trees=[])
    # nothing matched: the surface form is returned, flagged as not resolved
    assert joint._compose_lemma("ζζζ", "NOUN", 0, miss) == (
        "ζζζ", False, joint.LemmaSource.IDENTITY,
    )


def test_pipeline_neural_identity_fallthrough_is_not_known(monkeypatch) -> None:
    """The end-to-end D1 regression: under an active joint model, a token the model cannot
    lemmatize (identity fall-through) must report `lemma_source == IDENTITY` and
    `lemma_known is False` — even though its lemma equals the surface form."""
    from aegean import greek
    from aegean.greek import LemmaSource

    model = _stub_model()
    model.lookup_form = {}          # clear every lemma source so all three fall through
    model.lookup_form_upos = {}
    model.lookup_lower = {}
    model.trees = []                # no edit-script applies → bare identity fall-through
    monkeypatch.setattr(joint, "_ACTIVE", model)
    recs = greek.pipeline("ὁ λόγος ἐστί")
    assert [r.lemma for r in recs] == ["ὁ", "λόγος", "ἐστί"]  # all identity (surface form)
    for r in recs:  # lemma == surface, but honestly flagged as an unresolved fall-through
        assert r.lemma_source is LemmaSource.IDENTITY
        assert r.lemma_resolved is False and r.review_recommended is True


# --- the dispatch hooks -------------------------------------------------------------


def test_hooks_dispatch_to_joint_when_active(monkeypatch) -> None:
    from aegean import greek

    model = _stub_model()
    monkeypatch.setattr(joint, "_ACTIVE", model)
    try:
        assert [u for _t, u in greek.pos_tags("ὁ λόγος ἐστί")] == ["DET", "NOUN", "VERB"]
        assert greek.pos_tag("ὁ") == "DET"
        assert greek.lemmatize("ἐστί") == "εἰμί"
        tree = greek.parse(["ὁ", "λόγος", "ἐστί"])
        assert [t.relation for t in tree.tokens] == ["det", "nsubj", "root"]  # UD labels
        assert tree.root() is not None and tree.root().form == "ἐστί"
        assert tree.tokens[0].postag.startswith("l")
    finally:
        monkeypatch.setattr(joint, "_ACTIVE", None)


def test_analyze_sentence_requires_activation() -> None:
    with pytest.raises(joint.NeuralPipelineNotLoadedError):
        joint.analyze_sentence(["λόγος"])
