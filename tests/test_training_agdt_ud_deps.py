"""Contract tests for the AGDT→UD dependency converter (training/agdt_ud_deps.py).

Toy Prague-style trees exercising each structural transform; the corpus-level numbers
(96.5% head / 94.5% head+label agreement vs the UD-Perseus train fold) are measured by
training/validate_agdt_ud_deps.py (network-dependent, not in CI)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_DIR = Path(__file__).parent.parent / "training"
sys.path.insert(0, str(_DIR))
spec = importlib.util.spec_from_file_location("agdt_ud_deps", _DIR / "agdt_ud_deps.py")
assert spec is not None and spec.loader is not None
deps = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deps)


def w(i, head, rel, form="x", lemma="x", xpos="n-s---ma-"):
    return {"id": str(i), "head": str(head), "relation": rel,
            "form": form, "lemma": lemma, "xpos": xpos}


def test_plain_labels_and_root() -> None:
    #  ὁ λόγος ἐστί: PRED root; SBJ → nsubj; ATR(article) → det
    words = [
        w(1, 2, "ATR", "ὁ", "ὁ", "l-s---mn-"),
        w(2, 3, "SBJ", "λόγος", "λόγος", "n-s---mn-"),
        w(3, 0, "PRED", "λέγει", "λέγω", "v3spia---"),
    ]
    assert deps.convert_tree(words) == [(2, "det"), (3, "nsubj"), (0, "root")]


def test_coordination_promotes_first_conjunct() -> None:
    # Prague: COORD(3) heads PRED_CO(1) and PRED_CO(4); UD: 1 is root, 4 conj of 1, cc on 1
    words = [
        w(1, 3, "PRED_CO", xpos="v3spia---"),
        w(2, 1, "OBJ", xpos="n-s---ma-"),
        w(3, 0, "COORD", "καί", "καί", "c--------"),
        w(4, 3, "PRED_CO", xpos="v3spia---"),
    ]
    out = deps.convert_tree(words)
    assert out[0] == (0, "root")
    assert out[1] == (1, "obj")
    assert out[2] == (1, "cc")
    assert out[3] == (1, "conj")


def test_aux_p_demotes_preposition() -> None:
    # Prague: ἐν(AuxP) heads ἀρχῇ(ADV); UD: ἀρχῇ takes AuxP's head as obl, ἐν → case
    words = [
        w(1, 3, "AuxP", "ἐν", "ἐν", "r--------"),
        w(2, 1, "ADV", "ἀρχῇ", "ἀρχή", "n-s---fd-"),
        w(3, 0, "PRED", "ἦν", "εἰμί", "v3siia---"),
    ]
    assert deps.convert_tree(words) == [(2, "case"), (3, "obl"), (0, "root")]


def test_aux_c_demotes_subordinator() -> None:
    # Prague: ὅτι(AuxC) heads the verb(ADV); UD: verb takes AuxC's head as advcl, ὅτι → mark
    words = [
        w(1, 0, "PRED", xpos="v3spia---"),
        w(2, 1, "AuxC", "ὅτι", "ὅτι", "c--------"),
        w(3, 2, "ADV", xpos="v3spia---"),
    ]
    assert deps.convert_tree(words) == [(0, "root"), (3, "mark"), (1, "advcl")]


def test_copula_promotes_predicate() -> None:
    # Prague: ἐστί(PRED) heads PNOM + SBJ; UD: predicate is root, copula → cop, subject re-attaches
    words = [
        w(1, 2, "SBJ", "λόγος", "λόγος", "n-s---mn-"),
        w(2, 0, "PRED", "ἐστί", "εἰμί", "v3spia---"),
        w(3, 2, "PNOM", "καλός", "καλός", "a-s---mn-"),
    ]
    out = deps.convert_tree(words)
    assert out[2] == (0, "root")     # the predicate nominal promoted
    assert out[1] == (3, "cop")      # the copula demoted under it
    assert out[0] == (3, "nsubj")    # the subject follows the promotion


def test_aux_k_attaches_to_root() -> None:
    words = [
        w(1, 0, "PRED", xpos="v3spia---"),
        w(2, 1, "OBJ", xpos="n-s---ma-"),
        w(3, 0, "AuxK", ".", ".", "u--------"),
    ]
    assert deps.convert_tree(words) == [(0, "root"), (1, "obj"), (1, "punct")]


def test_dative_iobj_requires_direct_object() -> None:
    base = [
        w(1, 0, "PRED", xpos="v3spia---"),
        w(2, 1, "OBJ", xpos="n-s---md-"),   # dative object
    ]
    assert deps.convert_tree(base)[1] == (1, "obj")  # alone: plain obj
    both = base + [w(3, 1, "OBJ", xpos="n-s---ma-")]  # + accusative sibling
    out = deps.convert_tree(both)
    assert out[1] == (1, "iobj") and out[2] == (1, "obj")
