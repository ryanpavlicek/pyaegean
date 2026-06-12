"""Tests for the Stage D lemma machinery (edit-script inventory + composition).

The edit trees themselves are aegean.greek.lemmatizer's (already covered by its own
tests); these pin the Stage D usage: keys round-trip through JSON, scripts generalize
across same-pattern forms, and the LemmaComposer's fallback orders behave."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

from aegean.greek.lemmatizer import _key, apply_tree, build_tree

_DIR = Path(__file__).parent.parent / "training"
sys.path.insert(0, str(_DIR))


def test_edit_script_roundtrip_and_generalization() -> None:
    tree = build_tree("λόγου", "λόγος")
    assert apply_tree(tree, "λόγου") == "λόγος"
    # the same script generalizes to another 2nd-declension genitive
    assert apply_tree(json.loads(_key(tree)), "νόμου") == "νόμος"
    # accent-shift pair round-trips through its own (more specific) tree
    t2 = build_tree("ἀνθρώπου", "ἄνθρωπος")
    assert apply_tree(t2, "ἀνθρώπου") == "ἄνθρωπος"


def test_lemma_composer_fallback_orders() -> None:
    spec = importlib.util.spec_from_file_location("train_full", _DIR / "train_full.py")
    assert spec is not None and spec.loader is not None
    tf = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(tf)
    except ModuleNotFoundError as exc:  # torch/transformers absent in some envs
        import pytest

        pytest.skip(f"training deps unavailable: {exc}")

    scripts = [_key(build_tree("λόγου", "λόγος"))]
    lookup = {"form": {"λόγου": "λόγος-LOOKUP"},
              "form_upos": {"λόγου|NOUN": "λόγος-UPOS"},
              "form_lower": {"λόγου": "λόγος-LOWER"}}
    c = tf.LemmaComposer(scripts, lookup)
    # lookup-first prefers the (form|UPOS) key; neural-only applies the script
    assert c.resolve("lookup-first", "λόγου", "NOUN", 0) == "λόγος-UPOS"
    assert c.resolve("neural-only", "λόγου", "NOUN", 0) == "λόγος"
    assert c.resolve("neural-first", "λόγου", "NOUN", 0) == "λόγος"
    # unseen-neural: lookup wins for seen forms; the script covers unseen ones
    assert c.resolve("unseen-neural", "λόγου", "NOUN", 0) == "λόγος-UPOS"
    assert c.resolve("unseen-neural", "νόμου", "NOUN", 0) == "νόμος"
    # no script, nothing in the lookup → identity
    assert c.resolve("neural-first", "ξένον", "NOUN", -100) == "ξένον"
