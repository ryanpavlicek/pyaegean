"""Batched joint inference: `analyze_batch` / `analyze_sentences` parity with the
sequential path, and the ``batch_size`` wiring through the evaluators.

Offline correctness runs through a batch-aware stub (no ONNX): ONE deterministic
logits function backs both a per-sentence ``_run`` and a padded fake batch session,
so comparing `analyze_batch` against sequential `analyze` exercises the real padding /
slicing / fallback logic in ``_run_batch`` — including empty sentences, a simulated
subword-budget truncation, and a sentence with no decodable word positions. A gated
spot check repeats the comparison on the cached real model (in a subprocess, so
onnxruntime never leaks into this process's ``sys.modules``). Batching is a throughput
convenience: the recorded benchmark protocol stays the sequential default everywhere."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import types
from pathlib import Path

import pytest

np = pytest.importorskip("numpy")

from aegean.greek import joint  # noqa: E402

CONLLU = Path(__file__).parent / "fixtures" / "ud" / "sample-ud-test.conllu"

_EMPTY = joint.SentenceAnalysis((), (), (), (), (), (), (), ())

# form → (upos label id, x0 char id); anything else falls back to ("X", "-")
_BY_FORM = {"ὁ": (0, 1), "λόγος": (1, 2), "ἐστί": (2, 3)}
_NAMES = ["upos"] + [f"x{i}" for i in range(9)] + ["arc", "rel", "lemma"]
_TRUNCATE = 5   # sentences longer than this lose word coverage for the tail
_NO_POS = "∅"   # a token the fake tokenizer yields no word positions for


def _logits_for(words: list[str]) -> dict[str, "np.ndarray"]:
    """The one deterministic logits function (mirrors test_joint's stub): DET/NOUN/VERB
    for the known forms, a head chain w → w+1 with the last word on ROOT."""
    n = len(words)
    seq = n + 2

    def tag(labels: list[int], n_labels: int) -> "np.ndarray":
        a = np.full((seq, n_labels), -9.0)
        for w, lab in enumerate(labels):
            a[w + 1, lab] = 9.0
        return a

    out = {
        "upos": tag([_BY_FORM.get(w, (3, 0))[0] for w in words], 4),
        "x0": tag([_BY_FORM.get(w, (3, 0))[1] for w in words], 4),
    }
    for i in range(1, 9):
        out[f"x{i}"] = tag([0] * n, 4)
    arc = np.full((n, n + 1), -9.0)
    rel = np.full((4, n, n + 1), -9.0)
    for w in range(n):
        h = w + 2 if w < n - 1 else 0
        arc[w, h] = 9.0
        rel[min(w, 2) if w < n - 1 else 2, w, h] = 9.0
    out["arc"] = arc
    out["rel"] = rel
    out["lemma"] = np.zeros((n, 1))  # script 0 for everyone
    return out


def _batch_stub_model() -> joint._JointModel:
    """A _JointModel whose single (`_run`) and batched (`_sess.run`) passes are backed by
    the SAME logits function, so any sequential-vs-batched divergence is a padding or
    slicing defect in the production ``_run_batch`` / ``analyze_batch`` code."""
    m = object.__new__(joint._JointModel)  # skip __init__ (no artifact on disk)
    m._np = np
    m.inv = {
        "upos": dict(enumerate(["DET", "NOUN", "VERB", "X"])),
        "deprel": dict(enumerate(["det", "nsubj", "root", "dep"])),
    }
    for i in range(9):
        m.inv[f"x{i}"] = {0: "-", 1: "l", 2: "n", 3: "v"}
    m.trees = [["sub", "λόγος"]]          # script 0 rewrites anything to λόγος
    m.lookup_form = {"ὁ": "ὁ"}
    m.lookup_form_upos = {"ἐστί|VERB": "εἰμί"}
    m.lookup_lower = {}

    vocab: dict[str, int] = {}
    rev: dict[int, str] = {}

    def _word_id(w: str) -> int:
        if w not in vocab:
            vocab[w] = 100 + len(vocab)
            rev[vocab[w]] = w
        return vocab[w]

    def encode(words: list[str]) -> tuple[list[int], list[int], list[int]]:
        if words == [_NO_POS]:
            return [0, 2], [], []          # tokenized, but no decodable word positions
        kept_words = words[:_TRUNCATE]     # simulated subword-budget truncation
        ids = [0] + [_word_id(w) for w in kept_words] + [2]
        return ids, list(range(1, len(kept_words) + 1)), list(range(len(kept_words)))

    def fake_run(words: list[str]) -> dict:
        ids, word_pos, kept = encode(words)
        out = {name: arr[None, ...] for name, arr in _logits_for([words[k] for k in kept]).items()}
        out["_word_pos"] = word_pos
        out["_kept"] = kept
        return out

    class _FakeSess:
        calls = 0

        def get_outputs(self) -> list[types.SimpleNamespace]:
            return [types.SimpleNamespace(name=n) for n in _NAMES]

        def run(self, _none: None, feed: dict) -> list["np.ndarray"]:
            type(self).calls += 1
            rows = []
            for input_row, mask_row in zip(feed["input_ids"], feed["attention_mask"]):
                real = [int(t) for t, keep in zip(input_row, mask_row) if keep]
                rows.append(_logits_for([rev[t] for t in real if t in rev]))
            out = []
            for name in _NAMES:
                arrs = [r[name] for r in rows]
                shape = tuple(max(a.shape[d] for a in arrs) for d in range(arrs[0].ndim))
                stacked = np.full((len(rows), *shape), -9.0)
                for b, a in enumerate(arrs):
                    stacked[(b, *(slice(0, s) for s in a.shape))] = a
                out.append(stacked)
            return out

    m._sess = _FakeSess()  # type: ignore[assignment]
    m._encode = encode  # type: ignore[method-assign]
    m._run = fake_run  # type: ignore[method-assign]
    return m


# a mixed batch: known forms, empty, single token, truncation, no word positions, OOV
BATCH = [
    ["ὁ", "λόγος", "ἐστί"],
    [],
    ["λόγος"],
    ["ὁ", "λόγος", "ἐστί", "ὁ", "λόγος", "ἐστί", "λόγος"],  # 7 words → tail truncated
    [_NO_POS],
    ["ξένος"],
]


# --- analyze_batch parity ----------------------------------------------------------


def test_analyze_batch_equals_sequential_field_for_field() -> None:
    m = _batch_stub_model()
    seq = [m.analyze(list(s)) for s in BATCH]
    bat = m.analyze_batch([list(s) for s in BATCH])
    assert bat == seq  # SentenceAnalysis is frozen — this compares every field
    # and the shared values are RIGHT, not merely mutually consistent:
    assert bat[0].upos == ("DET", "NOUN", "VERB")
    assert bat[0].head == (2, 3, 0)
    assert bat[0].deprel == ("det", "nsubj", "root")
    assert bat[0].lemma == ("ὁ", "λόγος", "εἰμί")
    assert bat[0].lemma_resolved == (True, False, True)
    assert bat[1] == _EMPTY
    assert bat[2].upos == ("NOUN",) and bat[2].head == (0,) and bat[2].deprel == ("root",)
    # the truncated tail keeps the honest fallback: X, identity lemma, unresolved
    assert bat[3].upos[_TRUNCATE:] == ("X", "X")
    assert bat[3].lemma[_TRUNCATE:] == ("ἐστί", "λόγος")
    assert bat[3].lemma_resolved[_TRUNCATE:] == (False, False)
    # no decodable word positions → the whole-sentence fallback, single root
    assert bat[4].upos == ("X",) and bat[4].head == (0,) and bat[4].deprel == ("root",)
    assert bat[5].upos == ("X",)  # out-of-vocabulary form


def test_analyze_batch_runs_one_padded_session_call() -> None:
    m = _batch_stub_model()
    sess = m._sess
    m.analyze_batch([list(s) for s in BATCH])
    assert type(sess).calls == 1  # the whole mixed batch = one ONNX run


def test_analyze_batch_empty_inputs_never_touch_the_session() -> None:
    m = _batch_stub_model()
    sess = m._sess
    assert m.analyze_batch([]) == []
    assert m.analyze_batch([[], []]) == [_EMPTY, _EMPTY]
    assert type(sess).calls == 0


# --- the analyze_sentences wrapper ---------------------------------------------------


def test_analyze_sentences_matches_sequential_across_chunk_sizes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    m = _batch_stub_model()
    monkeypatch.setattr(joint, "_ACTIVE", m)
    expected = [m.analyze(list(s)) for s in BATCH]
    assert joint.analyze_sentences([list(s) for s in BATCH]) == expected  # None = sequential
    for size in (1, 2, 4, 100):  # chunk boundaries must not change anything
        assert joint.analyze_sentences([list(s) for s in BATCH], batch_size=size) == expected


def test_analyze_sentences_requires_activation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(joint, "_ACTIVE", None)
    with pytest.raises(joint.NeuralPipelineNotLoadedError):
        joint.analyze_sentences([["λόγος"]], batch_size=2)


@pytest.mark.parametrize("bad", [0, -1])
def test_analyze_sentences_rejects_a_non_positive_batch_size(
    monkeypatch: pytest.MonkeyPatch, bad: int
) -> None:
    monkeypatch.setattr(joint, "_ACTIVE", _batch_stub_model())
    with pytest.raises(ValueError, match="batch_size"):
        joint.analyze_sentences([["λόγος"]], batch_size=bad)


# --- evaluator wiring: identical results with and without batch_size -----------------


def test_pipeline_conllu_batch_size_output_and_progress_identical(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from aegean.greek.ud import load_conllu, pipeline_conllu

    sentences = load_conllu(CONLLU)  # the 2-sentence offline UD fixture
    m = _batch_stub_model()
    monkeypatch.setattr(joint, "_ACTIVE", m)
    base = pipeline_conllu(sentences, parse=True)
    calls: list[tuple[int, int]] = []
    batched = pipeline_conllu(
        sentences, parse=True, batch_size=2, progress=lambda d, t: calls.append((d, t))
    )
    assert batched == base                # byte-identical CoNLL-U
    assert calls == [(1, 2), (2, 2)]      # the progress contract is unchanged
    with pytest.raises(ValueError, match="batch_size"):
        pipeline_conllu(sentences, batch_size=0)


def test_pipeline_conllu_batch_size_is_inert_without_the_joint_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from aegean.greek.ud import load_conllu, pipeline_conllu

    monkeypatch.setattr(joint, "_ACTIVE", None)  # the offline cascade has no batched loop
    sentences = load_conllu(CONLLU)
    assert pipeline_conllu(sentences, batch_size=4) == pipeline_conllu(sentences)


def test_evaluate_on_ud_batch_size_scores_identically(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from aegean.greek import ud

    m = _batch_stub_model()
    monkeypatch.setattr(joint, "_ACTIVE", m)
    try:
        base = ud.evaluate_on_ud(source=CONLLU, parse=True)
    except Exception as exc:
        pytest.skip(f"official evaluator unavailable offline: {exc}")
    batched = ud.evaluate_on_ud(source=CONLLU, parse=True, batch_size=2)
    assert batched == base
    assert base["n_sentences"] == 2  # the fixture really was scored


def test_evaluate_by_genre_batch_size_scores_identically(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from aegean.greek.ud import evaluate_by_genre

    m = _batch_stub_model()
    monkeypatch.setattr(joint, "_ACTIVE", m)
    try:
        base = evaluate_by_genre(
            source=CONLLU, parse=True, bootstrap=False, min_sentences=1
        )
    except Exception as exc:
        pytest.skip(f"official evaluator unavailable offline: {exc}")
    batched = evaluate_by_genre(
        source=CONLLU, parse=True, bootstrap=False, min_sentences=1, batch_size=2
    )
    assert batched == base


def test_score_batch_path_matches_sequential_with_exact_progress() -> None:
    from aegean.greek.heldout import HeldoutSplit, HeldoutToken, score

    sents = tuple(
        (HeldoutToken(form=f"λόγος{i}", lemma=f"λόγος{i}", upos="NOUN", seen=False, scored=True),)
        for i in range(5)
    )
    split = HeldoutSplit(sentences=sents, train_forms=frozenset(), train_lemma={}, train_pos={})

    def tag(forms: list[str]) -> list[tuple[str, str]]:
        return [(f, "NOUN") for f in forms]

    calls: list[tuple[int, int]] = []
    batched = score(
        tag, split=split, batch_size=2,
        tag_batch=lambda batch: [tag(f) for f in batch],
        progress=lambda d, t: calls.append((d, t)),
    )
    assert batched == score(tag, split=split)                       # identical scores
    assert calls == [(1, 5), (2, 5), (3, 5), (4, 5), (5, 5)]        # identical progress
    # batch_size without a tag_batch has no effect (documented degradation)
    assert score(tag, split=split, batch_size=2) == batched


def test_score_batch_taggers_wrong_count_aborts_loudly() -> None:
    from aegean.greek.heldout import HeldoutSplit, HeldoutToken, score

    sents = tuple(
        (HeldoutToken(form="λόγος", lemma="λόγος", upos="NOUN", seen=False, scored=True),)
        for _ in range(4)
    )
    split = HeldoutSplit(sentences=sents, train_forms=frozenset(), train_lemma={}, train_pos={})

    def tag(forms: list[str]) -> list[tuple[str, str]]:
        return [(f, "NOUN") for f in forms]

    def short_batch(batch: list[list[str]]) -> list[list[tuple[str, str]]]:
        return [tag(f) for f in batch[:-1]]  # silently drops a sentence

    with pytest.raises(ValueError):  # never a silently truncated score
        score(tag, split=split, batch_size=2, tag_batch=short_batch)
    with pytest.raises(ValueError, match="batch_size"):
        score(tag, split=split, batch_size=0)


def test_evaluate_on_nt_batch_size_uses_batched_inference_and_scores_identically(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from aegean.core.corpus import Corpus
    from aegean.core.model import Document, Token, TokenKind
    from aegean.greek.nt_eval import evaluate_on_nt

    m = _batch_stub_model()
    monkeypatch.setattr(joint, "_ACTIVE", m)
    batches: list[int] = []
    real_batch = m.analyze_batch

    def spy(batch: list[list[str]]) -> list[joint.SentenceAnalysis]:
        batches.append(len(batch))
        return real_batch(batch)

    m.analyze_batch = spy  # type: ignore[method-assign]

    def tok(text: str, verse: int, pos: int) -> Token:
        return Token(
            text=text, kind=TokenKind.WORD, line_no=verse, position=pos,
            annotations={"lemma": text, "upos": "NOUN"},
        )

    doc = Document(
        id="TestB", script_id="greek",
        tokens=[tok("λόγος", 1, 0), tok("ὁ", 2, 1), tok("ἐστί", 3, 2)],
        lines=[[0], [1], [2]],
    )
    corpus = Corpus([doc], script_id="greek")
    base = evaluate_on_nt(corpus=corpus)                 # default neural tagger, sequential
    batched = evaluate_on_nt(corpus=corpus, batch_size=2)
    assert batched == base and base["n"] == 3
    assert batches == [2, 1]                             # 3 verses → chunks of 2 + 1


def test_evaluate_on_nt_batch_size_is_inert_with_a_custom_tagger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from aegean.core.corpus import Corpus
    from aegean.core.model import Document, Token, TokenKind
    from aegean.greek.nt_eval import evaluate_on_nt

    monkeypatch.setattr(joint, "_ACTIVE", None)  # no pipeline: the custom tagger is used as-is
    doc = Document(
        id="TestB", script_id="greek",
        tokens=[Token(text="λόγος", kind=TokenKind.WORD, line_no=1, position=0,
                      annotations={"lemma": "λόγος", "upos": "NOUN"})],
        lines=[[0]],
    )
    corpus = Corpus([doc], script_id="greek")

    def echo(forms: list[str]) -> list[tuple[str, str]]:
        return [(f, "NOUN") for f in forms]

    assert evaluate_on_nt(echo, corpus=corpus, batch_size=8) == evaluate_on_nt(echo, corpus=corpus)


# --- the real shipped model: a gated exact-parity spot check -------------------------

_PROBE = '''
import json, sys
from pathlib import Path
from aegean.greek.joint import _JointModel

SENTS = [
    ["Ἐν", "ἀρχῇ", "ἦν", "ὁ", "λόγος", ",", "καὶ", "ὁ", "λόγος", "ἦν", "πρὸς", "τὸν", "θεόν", "."],
    ["μῆνιν", "ἄειδε", "θεὰ", "Πηληϊάδεω", "Ἀχιλῆος"],
    ["ἄνδρα", "μοι", "ἔννεπε", ",", "Μοῦσα", ",", "πολύτροπον"],
    ["γνῶθι", "σαυτόν"],
    ["πάντες", "ἄνθρωποι", "τοῦ", "εἰδέναι", "ὀρέγονται", "φύσει"],
    ["ὁ", "δὲ", "ἀνεξέταστος", "βίος", "οὐ", "βιωτὸς", "ἀνθρώπῳ"],
    ["ἐγὼ", "εἰμι", "ἡ", "ὁδὸς", "καὶ", "ἡ", "ἀλήθεια", "καὶ", "ἡ", "ζωή"],
    ["θάλαττα", ",", "θάλαττα"],
    ["ἓν", "οἶδα", "ὅτι", "οὐδὲν", "οἶδα"],
    ["Κῦρος", "ὁ", "βασιλεὺς", "ἐπορεύετο", "σὺν", "τῷ", "στρατεύματι"],
    [],
    ["λόγος"],
]
FIELDS = ("tokens", "upos", "xpos", "feats", "head", "deprel", "lemma", "lemma_resolved")

m = _JointModel(Path(sys.argv[1]))
seq = [m.analyze(list(s)) for s in SENTS]
bat = m.analyze_batch([list(s) for s in SENTS])
diffs = [
    {"i": i, "fields": [f for f in FIELDS if getattr(a, f) != getattr(b, f)]}
    for i, (a, b) in enumerate(zip(seq, bat)) if a != b
]
print(json.dumps({"identical": not diffs, "diffs": diffs, "n": len(SENTS),
                  "providers": m._sess.get_providers()}))
'''


def _cached_joint_dir() -> Path | None:
    from aegean.data import cache_dir

    d = cache_dir() / "grc-joint"
    if (d / "model.onnx").exists():
        return d
    nested = [p for p in d.iterdir() if p.is_dir()] if d.exists() else []
    if len(nested) == 1 and (nested[0] / "model.onnx").exists():
        return d
    return None


def test_real_model_batch_parity_is_exact() -> None:
    """analyze_batch == sequential analyze on the shipped grc-joint model, EXACT equality
    over a mixed 12-sentence batch (CPU provider — the recorded protocol's configuration).

    Runs in a subprocess so onnxruntime never enters this process's sys.modules, and only
    when the model is already cached (never fetches). Exact decoded-field parity is the
    gate for ever using batching near the benchmark protocol; if this fails, batching
    stays a throughput convenience only."""
    for dep in ("onnxruntime", "tokenizers"):
        if importlib.util.find_spec(dep) is None:
            pytest.skip(f"{dep} not installed (the [neural] extra)")
    model_dir = _cached_joint_dir()
    if model_dir is None:
        pytest.skip("grc-joint model not cached; fetching it is not done in a committed test")
    env = {**os.environ, "PYTHONUTF8": "1", "PYAEGEAN_ORT_PROVIDERS": "CPUExecutionProvider"}
    proc = subprocess.run(
        [sys.executable, "-c", _PROBE, str(model_dir)],
        capture_output=True, text=True, encoding="utf-8", env=env, timeout=600,
    )
    assert proc.returncode == 0, proc.stderr
    verdict = json.loads(proc.stdout.strip().splitlines()[-1])
    assert verdict["providers"] == ["CPUExecutionProvider"]
    assert verdict["identical"], f"batched != sequential on the real model: {verdict['diffs']}"
