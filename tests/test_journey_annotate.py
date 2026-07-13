"""Journey tests for the annotate → review loop and its joint-pipeline seams (offline).

Covers the `annotate_corpus` joint branch (stubbed model, no download — the
test_pipeline_convenience idiom), the explicit ``tag_sentence`` override, the
`joint._compose_lemma` honesty contract, the `evaluate_by_genre` singleton-bucket
bootstrap fallback, and the full TEI work → annotate → review table → correct →
apply → token DataFrame journey on the bundled fixture."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

import aegean
from aegean.core.model import Document, Token, TokenKind
from aegean.greek import joint
from aegean.greek import LemmaSource
from aegean.greek.annotate import annotate_corpus
from aegean.greek.joint import SentenceAnalysis
from aegean.io.review import from_review_table, needs_review_flag, to_review_table

FIXTURE = Path(__file__).parent / "fixtures" / "greeklit" / "sample.xml"


def _two_word_corpus() -> aegean.Corpus:
    doc = Document(
        id="d1",
        script_id="greek",
        tokens=[
            Token("λόγον", TokenKind.WORD, line_no=0, position=0),
            Token("χψω", TokenKind.WORD, line_no=0, position=1),
        ],
        lines=[[0, 1]],
    )
    return aegean.Corpus([doc], script_id="greek")


# --- 1. the joint branch of annotate_corpus ---------------------------------------


class _StubJoint:
    """Stands in for joint._JointModel: analyze() returns a fixed SentenceAnalysis."""

    def analyze(self, words: list[str]) -> SentenceAnalysis:
        assert words == ["λόγον", "χψω"]  # the corpus's word forms, grouped by line
        return SentenceAnalysis(
            tokens=("λόγον", "χψω"),
            upos=("NOUN", "X"),
            xpos=("n-s---ma-", "---------"),
            feats=("Case=Acc|Gender=Masc|Number=Sing", ""),
            head=(0, 1),
            deprel=("root", "dep"),
            lemma=("λόγος", "χψω"),
            lemma_resolved=(True, False),
            lemma_source=(LemmaSource.NEURAL_EDIT, LemmaSource.IDENTITY),
            lemma_verified=(False, False),
            analyzed=(True, True),
        )


def test_annotate_corpus_joint_branch_writes_neural_and_identity_sources(monkeypatch):
    corpus = _two_word_corpus()
    monkeypatch.setattr(joint, "_ACTIVE", _StubJoint())
    out = annotate_corpus(corpus)
    t0, t1 = out.documents[0].tokens

    # token 0: a real analysis (lemma_resolved=True) → NEURAL evidence class
    assert t0.annotations["lemma"] == "λόγος"
    assert t0.annotations["upos"] == "NOUN"
    assert t0.annotations["lemma_source"] == "neural_edit"
    assert t0.annotations["lemma_resolved"] == "true"
    assert t0.annotations["lemma_verified"] == "false"
    assert t0.annotations["review_recommended"] == "false"
    assert t0.annotations["lemma_known"] == "true"

    # token 1: the identity fall-through (lemma_resolved=False) → IDENTITY class
    assert t1.annotations["lemma"] == "χψω"
    assert t1.annotations["upos"] == "X"
    assert t1.annotations["lemma_source"] == "identity"
    assert t1.annotations["review_recommended"] == "true"
    assert t1.annotations["lemma_known"] == "false"

    # the review triage predicate agrees with the evidence classes
    assert needs_review_flag(t1.annotations) is True
    assert needs_review_flag(t0.annotations) is False

    # the input corpus is not mutated
    assert corpus.documents[0].tokens[0].annotations == {}
    assert corpus.documents[0].tokens[1].annotations == {}


# --- 2. the explicit tag_sentence override -----------------------------------------


class _ExplodingJoint:
    def analyze(self, words: list[str]) -> SentenceAnalysis:
        raise AssertionError("joint model consulted despite an explicit tag_sentence")


def test_annotate_corpus_tag_sentence_override_lands_verbatim(monkeypatch):
    corpus = _two_word_corpus()
    # even with the joint pipeline "active", the override must win
    monkeypatch.setattr(joint, "_ACTIVE", _ExplodingJoint())

    def tag(forms: list[str]) -> list[tuple[str, str]]:
        return [(f + "-LEM", "PART") for f in forms]

    out = annotate_corpus(corpus, tag_sentence=tag)
    t0, t1 = out.documents[0].tokens
    assert t0.annotations["lemma"] == "λόγον-LEM" and t0.annotations["upos"] == "PART"
    assert t1.annotations["lemma"] == "χψω-LEM" and t1.annotations["upos"] == "PART"
    # the override carries no evidence class: no lemma_source / lemma_known written
    assert "lemma_source" not in t0.annotations and "lemma_known" not in t0.annotations
    assert "lemma_source" not in t1.annotations and "lemma_known" not in t1.annotations


# --- 3. _compose_lemma honesty (the D1 regression surface) --------------------------


class _StubComposeModel:
    """The four attributes _compose_lemma reads, nothing else."""

    def __init__(self, **lookups: dict[str, str]) -> None:
        self.lookup_form_upos: dict[str, str] = lookups.get("form_upos", {})
        self.lookup_form: dict[str, str] = lookups.get("form", {})
        self.lookup_lower: dict[str, str] = lookups.get("lower", {})
        # tree 0 = the identity edit script (["keep"] emits the segment unchanged);
        # tree 1 = a whole-segment substitution to the CoNLL-U "_" placeholder
        self.trees: list[list] = [["keep"], ["sub", "_"]]


def test_compose_lemma_placeholder_script_is_never_the_literal_underscore():
    # sanity: the tree encoding really produces "_" (matches lemmatizer.apply_tree)
    from aegean.greek.lemmatizer import apply_tree

    model = _StubComposeModel()
    assert apply_tree(model.trees[1], "ἀγορά") == "_"

    lemma, resolved, source = joint._compose_lemma("ἀγορά", "NOUN", 1, model)
    assert lemma == "ἀγορά"  # the surface form, never the "_" placeholder
    assert resolved is False
    assert source is joint.LemmaSource.IDENTITY


def test_compose_lemma_identity_script_on_unknown_form_is_unresolved():
    model = _StubComposeModel()
    lemma, resolved, source = joint._compose_lemma("χψω", "X", 0, model)
    assert (lemma, resolved, source) == (
        "χψω", False, joint.LemmaSource.IDENTITY,
    )  # identity fall-through, honestly flagged


def test_compose_lemma_lookup_hit_equal_to_the_form_stays_resolved():
    # the D1 nominative case: a lookup lemma that EQUALS the surface form is a real
    # analysis; resolved must come from the branch, not a string compare
    model = _StubComposeModel(form={"λόγος": "λόγος"})
    lemma, resolved, source = joint._compose_lemma("λόγος", "NOUN", 0, model)
    assert (lemma, resolved, source) == (
        "λόγος", True, joint.LemmaSource.NEURAL_LOOKUP,
    )


# --- 4. evaluate_by_genre: singleton buckets under bootstrap=True -------------------

_EPIC = (
    "# sent_id = tlg0012.tlg001.tb.xml@1\n"
    "# text = μῆνιν ἄειδε θεά\n"
    "1\tμῆνιν\tμῆνις\tNOUN\t_\t_\t2\tobj\t_\t_\n"
    "2\tἄειδε\tἀείδω\tVERB\t_\t_\t0\troot\t_\t_\n"
    "3\tθεά\tθεά\tNOUN\t_\t_\t2\tvocative\t_\t_\n\n"
)
_PROSE = (
    "# sent_id = tlg0008.tlg001.tb.xml@1\n"
    "# text = ὁ λόγος ἦν\n"
    "1\tὁ\tὁ\tDET\t_\t_\t2\tdet\t_\t_\n"
    "2\tλόγος\tλόγος\tNOUN\t_\t_\t3\tnsubj\t_\t_\n"
    "3\tἦν\tεἰμί\tVERB\t_\t_\t0\troot\t_\t_\n\n"
)


def test_evaluate_by_genre_singleton_buckets_fall_back_to_point_scores(tmp_path: Path):
    """bootstrap=True on 1-sentence buckets must not raise: each bucket falls back to
    plain point scores (a 1-sentence bucket cannot be resampled) and is flagged thin."""
    from aegean.data import cache_dir
    from aegean.greek.ud import _CACHE_SUBDIR, evaluate_by_genre

    if not (cache_dir() / _CACHE_SUBDIR / "conll18_ud_eval.py").exists():
        try:
            from aegean.greek.ud import _eval_module

            _eval_module()
        except Exception as exc:
            pytest.skip(f"official evaluator unavailable offline: {exc}")

    fold = tmp_path / "mixed.conllu"
    fold.write_text(_EPIC + _PROSE, encoding="utf-8")
    res = evaluate_by_genre(
        "perseus", "test", source=fold, parse=False,
        bootstrap=True, min_sentences=2, n_resamples=50,
    )

    assert set(res) == {"epic", "prose", "_unmapped"}
    for g in ("epic", "prose"):
        assert res[g]["n_sentences"] == 1
        assert res[g]["thin"] is True  # 1 sentence < min_sentences=2
        # the bootstrap fallback fired: plain float scores, no CI object
        assert isinstance(res[g]["upos"], float) and 0.0 <= res[g]["upos"] <= 1.0
        assert isinstance(res[g]["lemma"], float) and 0.0 <= res[g]["lemma"] <= 1.0
        assert "uas" not in res[g] and "las" not in res[g]  # parse=False drops syntax


# --- 5. the journey: TEI work → annotate → review table → correct → apply → CSV -----


def test_tei_work_annotate_review_correct_apply_journey(tmp_path: Path):
    from aegean.scripts.greek.perseus import parse_tei_work

    _title, _author, docs = parse_tei_work(FIXTURE.read_bytes(), "w")
    corpus = aegean.Corpus(docs, script_id="greek")
    n_words = sum(len(d.words) for d in corpus.documents)
    assert n_words == 19  # the fixture's word tokens (punctuation excluded)

    # annotate with the offline baseline (joint inactive by default)
    assert joint.active() is None
    annotated = annotate_corpus(corpus)
    for d in annotated.documents:
        for t in d.words:
            assert t.annotations["lemma"]  # every word got a lemma annotation
            assert t.annotations["lemma_source"]
            assert t.annotations["lemma_resolved"] in ("true", "false")
            assert t.annotations["lemma_verified"] == "false"
            assert t.annotations["review_recommended"] in ("true", "false")

    # export: one row per word token, positions are digit strings
    table = tmp_path / "review.csv"
    n_rows = to_review_table(annotated, table)
    assert n_rows == n_words
    with open(table, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == n_words
    assert all(r["position"].isdigit() for r in rows)
    assert rows[0]["token"] == "μῆνιν" and rows[0]["doc_id"] == "w:1"

    # the reviewer corrects the first row's lemma
    machine_lemma = rows[0]["pred_lemma"]
    assert machine_lemma != "δοκιμή"  # the correction must differ from the prediction
    with open(table, encoding="utf-8-sig", newline="") as f:
        raw = list(csv.reader(f))
    header = raw[0]
    raw[1][header.index("correct_lemma")] = "δοκιμή"
    with open(table, "w", encoding="utf-8-sig", newline="") as f:
        csv.writer(f).writerows(raw)

    # apply: the correction lands, the machine value is preserved under lemma__pred
    corrected = from_review_table(table, annotated, reviewer="tester")
    tok = corrected.documents[0].tokens[0]
    assert tok.text == "μῆνιν"
    assert tok.annotations["lemma"] == "δοκιμή"
    assert tok.annotations["lemma__pred"] == machine_lemma
    assert tok.annotations["lemma_source"] == "user"
    assert tok.annotations["lemma_source__pred"]
    assert tok.annotations["lemma_resolved"] == "true"
    assert tok.annotations["lemma_verified"] == "true"
    assert tok.annotations["review_recommended"] == "false"
    assert tok.annotations["review_status"] == "corrected"
    assert tok.annotations["reviewed_by"] == "tester"
    # the pre-apply corpus is untouched
    assert annotated.documents[0].tokens[0].annotations.get("review_status") is None

    # The explicit epistemic fields survive the corpus's persistent JSON format.
    saved = tmp_path / "corrected.json"
    corrected.to_json(saved)
    reloaded = aegean.Corpus.from_json(saved)
    persisted = reloaded.documents[0].tokens[0].annotations
    assert persisted["lemma_source"] == "user"
    assert persisted["lemma_verified"] == "true"
    assert persisted["lemma_source__pred"] == tok.annotations["lemma_source__pred"]

    # token-level DataFrame carries the annotations as columns
    pytest.importorskip("pandas")
    df = corrected.to_dataframe(level="token")
    assert "lemma" in df.columns and "text" in df.columns
    hit = df[(df["doc_id"] == "w:1") & (df["position"] == 0)]
    assert len(hit) == 1 and hit["lemma"].iloc[0] == "δοκιμή"
    words = df[df["kind"] == "word"]
    assert len(words) == n_words and words["lemma"].notna().all()
