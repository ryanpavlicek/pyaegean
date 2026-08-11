"""Regressions for defects found by using the public surfaces as a researcher would.

Each test pins the observable behaviour a user meets, not an internal detail:

* ``import aegean.viz`` failed outright in a fresh interpreter (import cycle).
* ``seriate`` silently dropped the first document of a generator, so the natural
  filtering idiom seriated one assemblage fewer than it was given.
* the sign-pattern matcher branched exponentially on ``**``, turning a documented
  wildcard search over a bundled corpus into a 70-second hang with no bound.
* the CLI let Windows expand ``KU-*`` against the working directory, so a search
  returned different results depending on which files sat next to the user.
* ``to_conllu`` wrote HEAD 0 with DEPREL ``_`` for unparsed text, which claims every
  word is the sentence root and which pyaegean's own strict reader refuses.
* the sentence projection removed the last terminal mark found ANYWHERE in the span,
  deleting a period from inside a citation and fusing two source tokens.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time

import pytest


@pytest.fixture(autouse=True, scope="module")
def _restore_backends():
    """Leave the process as this module found it.

    Backend activation is global session state, so a module that turns one on and walks
    away changes what unrelated tests see -- which under ``pytest -n`` means a different
    worker, and a failure with no visible cause. Everything this file activates is turned
    off again here."""
    yield
    from aegean import greek

    for name in (
        "disable_neural_pipeline",
        "disable_treebank",
        "disable_lsj",
        "disable_lexicon",
        "disable_paradigms",
        "disable_tagger",
        "disable_parser",
        "disable_lemmatizer",
        "disable_neural_lemmatizer",
        "disable_calibration",
    ):
        try:
            getattr(greek, name)()
        except Exception:  # pragma: no cover - a backend that was never active
            pass




def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args], capture_output=True, text=True, encoding="utf-8"
    )


# --- aegean.viz is importable on its own ------------------------------------- #


def test_viz_imports_in_a_fresh_interpreter() -> None:
    for statement in (
        "import aegean.viz; aegean.viz.parse_period('III century BC')",
        "from aegean.viz import plot_findspots, parse_period; parse_period('III century BC')",
        "import aegean; aegean.viz.parse_period('III century BC')",
        "import aegean; aegean.analysis.seriate",
    ):
        done = _run("-c", statement)
        assert done.returncode == 0, f"{statement!r} failed:\n{done.stderr}"


# --- seriate over a one-shot iterator ---------------------------------------- #


def test_seriate_keeps_every_document_from_a_generator() -> None:
    import aegean
    from aegean.analysis import seriate

    docs = list(aegean.load("lineara").documents)[:20]
    from_list = seriate(list(docs))
    from_generator = seriate(d for d in docs)
    assert len(from_generator.order) == len(docs)
    assert from_generator.labels == from_list.labels
    assert from_generator.order == from_list.order


# --- sign-pattern matching is polynomial ------------------------------------- #


def test_sign_pattern_matching_is_bounded() -> None:
    from aegean.analysis.patterns import compile_sign_pattern, match_sign_pattern

    word = "KU RO SA RA2 TI NA PA QE WE DI MO NO SO TO WA JA KE ME NE".split()
    compiled = compile_sign_pattern("-".join(["**"] * 14) + "-ZZZ")
    assert compiled is not None
    started = time.perf_counter()
    assert match_sign_pattern(word, compiled) is False
    assert time.perf_counter() - started < 1.0


def test_sign_pattern_semantics_are_unchanged() -> None:
    from aegean.analysis.patterns import compile_sign_pattern, match_sign_pattern

    def matches(pattern: str, word: str) -> bool:
        compiled = compile_sign_pattern(pattern)
        assert compiled is not None
        return match_sign_pattern(word.split("-"), compiled)

    assert matches("KU-RO", "KU-RO")
    assert matches("KU-*", "KU-RO")
    assert not matches("KU-*", "KU-RO-SA")
    assert matches("KU-**", "KU-RO-SA")
    assert matches("**", "KU-RO-SA")
    assert matches("**-RO", "KU-RO")
    assert matches("**-RO-**", "KU-RO-SA")
    assert not matches("**-ZZ", "KU-RO")
    assert matches("KU-**-SA", "KU-SA")
    assert not matches("KU-*-SA", "KU-SA")
    # subscript folding still applies on both sides
    assert matches("SA-RA2", "SA-RA₂")


def test_very_long_pattern_does_not_exhaust_the_stack() -> None:
    from aegean.analysis.patterns import compile_sign_pattern, match_sign_pattern

    compiled = compile_sign_pattern("-".join(["*"] * 3000))
    assert compiled is not None
    assert match_sign_pattern(["KU", "RO"], compiled) is False


# --- the CLI does not glob its own arguments --------------------------------- #


def test_cli_pattern_argument_is_not_expanded_against_the_working_directory(
    tmp_path,
) -> None:
    pytest.importorskip("typer")
    (tmp_path / "KU-RO").write_text("decoy", encoding="utf-8")
    done = subprocess.run(
        [sys.executable, "-m", "aegean.cli", "search", "lineara", "KU-*"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=tmp_path,
        env={**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"},
    )
    assert done.returncode == 0, done.stderr[:500]
    # The header echoes the pattern the command actually received.
    assert "'KU-*'" in done.stdout, done.stdout[:400]
    assert "'KU-RO':" not in done.stdout


# --- CoNLL-U: a writer must obey its own strict reader ----------------------- #


def _pipeline_conllu(text: str) -> str:
    from aegean import greek
    from aegean.io import from_token_records, to_conllu

    document = from_token_records(
        greek.pipeline(text), source_text=text, document_id="input"
    )
    return to_conllu(document).value


def test_unparsed_conllu_does_not_claim_every_word_is_the_root() -> None:
    rows = [
        line
        for line in _pipeline_conllu("ἐν ἀρχῇ ἦν ὁ λόγος.").split("\n")
        if line and not line.startswith("#")
    ]
    assert rows
    for row in rows:
        columns = row.split("\t")
        assert columns[6] == "_", row
        assert columns[7] == "_", row


def test_strict_reader_accepts_what_the_writer_emits(tmp_path) -> None:
    from aegean.io.interop import load_conllu_document

    text = _pipeline_conllu("ἐν ἀρχῇ ἦν ὁ λόγος.")
    body = "\n".join(
        line for line in text.split("\n") if not line.startswith("# aegean.interop")
    )
    path = tmp_path / "unparsed.conllu"
    path.write_text(body, encoding="utf-8", newline="")
    load_conllu_document(path, strict=True)  # must not raise


def test_head_and_deprel_must_be_annotated_together(tmp_path) -> None:
    from aegean.greek.ud import load_conllu

    path = tmp_path / "mixed.conllu"
    path.write_text(
        "# sent_id = s1\n# text = α β\n"
        "1\tα\tα\tNOUN\t_\t_\t0\t_\t_\t_\n"
        "2\tβ\tβ\tNOUN\t_\t_\t_\t_\t_\t_\n\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="HEAD and DEPREL"):
        load_conllu(path, strict=True)


def test_a_parsed_sentence_is_unaffected(tmp_path) -> None:
    from aegean.greek.ud import dump_conllu, load_conllu

    source = (
        "# sent_id = s1\n# text = α β\n"
        "1\tα\tα\tNOUN\t_\t_\t2\tnsubj\t_\t_\n"
        "2\tβ\tβ\tVERB\t_\t_\t0\troot\t_\t_\n\n"
    )
    path = tmp_path / "parsed.conllu"
    path.write_text(source, encoding="utf-8", newline="")
    sentences = load_conllu(path, strict=True)
    assert [t.head for t in sentences[0].tokens] == [2, 0]
    assert dump_conllu(sentences, canonical=True) == source


# --- the sentence projection never fabricates a word ------------------------- #

FUSION_CASES = [
    ("εἴρηται ἐν Choer.489,12 καὶ ἀλλαχοῦ.", ["εἴρηται ἐν Choer.489,12", "καὶ ἀλλαχοῦ"]),
    ("τοῖς ἄλλοις m.1Vc Ba 22", ["τοῖς ἄλλοις m.1Vc", "Ba 22"]),
    ("ὅρα Vat.221, καὶ τέλος.", ["ὅρα Vat.221,", "καὶ τέλος"]),
]


@pytest.mark.parametrize("source,expected", FUSION_CASES)
def test_projection_does_not_delete_an_interior_mark(source, expected) -> None:
    from aegean import greek

    assert greek.sentences(source) == expected


def test_projection_still_drops_a_genuine_trailing_mark() -> None:
    from aegean import greek

    assert greek.sentences("ἐν ἀρχῇ ἦν ὁ λόγος. καὶ ὁ λόγος ἦν.") == [
        "ἐν ἀρχῇ ἦν ὁ λόγος",
        "καὶ ὁ λόγος ἦν",
    ]
    # a closing quote, bracket or dash after the mark is re-attached, as before
    assert greek.sentences("λόγος.” καί") == ["λόγος”", "καί"]
    assert greek.sentences("λόγος.— καί") == ["λόγος—", "καί"]


def test_no_projected_sentence_invents_a_word_on_a_shipped_corpus() -> None:
    """The property that makes the class impossible, checked on real text."""
    import re

    import aegean
    from aegean.greek import sentence_segmentation as seg

    word = re.compile(r"[^\W_]+", re.UNICODE)
    for corpus_id in ("nt", "isicily"):
        corpus = aegean.load(corpus_id)
        for document in list(corpus.documents)[:60]:
            text = " ".join(token.text for token in document.tokens)
            if not text.strip():
                continue
            for policy in ("default", "prose", "verse", "inscription", "papyrus"):
                result = seg.segment_text(text, policy=policy)
                for boundary, sentence in zip(result.boundaries, result.sentences):
                    source_words = {m.group(0) for m in word.finditer(boundary.text(result.source))}
                    invented = [
                        m.group(0) for m in word.finditer(sentence) if m.group(0) not in source_words
                    ]
                    assert not invented, (policy, invented[:3])
