"""Tests for the AGDT→UD label converter (training/agdt_ud.py, Stage B).

The converter is authored and these are its contract tests; its corpus-level agreement
(99.94% UPOS / 100% FEATS vs the UD-Perseus train fold) is measured separately by
training/validate_agdt_ud.py (network-dependent, not run in CI)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_MOD = Path(__file__).parent.parent / "training" / "agdt_ud.py"
spec = importlib.util.spec_from_file_location("agdt_ud", _MOD)
assert spec is not None and spec.loader is not None
agdt_ud = importlib.util.module_from_spec(spec)
spec.loader.exec_module(agdt_ud)

upos = agdt_ud.upos_from_xpos
feats = agdt_ud.feats_from_xpos


def test_upos_first_char_map() -> None:
    assert upos("λόγος", "n-s---mn-") == "NOUN"
    assert upos("ὁ", "l-s---mn-") == "DET"
    assert upos("ἐν", "r--------") == "ADP"
    assert upos(",", "u--------") == "PUNCT"


def test_conjunction_split_is_lexical() -> None:
    assert upos("καί", "c--------") == "CCONJ"
    assert upos("ὅτι", "c--------") == "SCONJ"
    assert upos("Εἰ", "c--------") == "SCONJ"      # case/accents fold away
    assert upos("ἐπεί", "c--------") == "CCONJ"    # the UD-Perseus convention
    assert upos("ὥστε", "c--------") == "SCONJ"


def test_copular_aux_needs_tree_context() -> None:
    x = "v3spia---"
    assert upos("ἐστί", x, lemma="εἰμί") == "VERB"  # no context → VERB
    assert upos("ἐστί", x, lemma="εἰμί", has_pnom_child=True) == "AUX"
    assert upos("λύει", x, lemma="λύω", has_pnom_child=True) == "VERB"  # not a copula
    assert upos("ἔχει", x, lemma="ἔχω", own_relation="AuxV") == "AUX"  # periphrastic


def test_copular_flags_direct_and_coordinated() -> None:
    # 1 is the copula with a direct PNOM child (2); 3 heads a COORD (4) whose child (5) is PNOM_CO
    words = [
        {"id": "1", "head": "0", "relation": "PRED"},
        {"id": "2", "head": "1", "relation": "PNOM"},
        {"id": "3", "head": "0", "relation": "PRED"},
        {"id": "4", "head": "3", "relation": "COORD"},
        {"id": "5", "head": "4", "relation": "PNOM_CO"},
    ]
    assert agdt_ud.copular_flags(words) == [True, False, True, True, False]


def test_feats_rendering_matches_the_validated_convention() -> None:
    assert feats("v3ppia---") == "Mood=Ind|Number=Plur|Person=3|Tense=Pres|VerbForm=Fin|Voice=Act"
    assert feats("v-papmmd-") == "Case=Dat|Gender=Masc|Number=Plur|Tense=Past|VerbForm=Part|Voice=Mid"
    assert feats("v3siie---") == "Aspect=Imp|Mood=Ind|Number=Sing|Person=3|Tense=Past|VerbForm=Fin|Voice=Mid"
    assert feats("v1sria---") == "Aspect=Perf|Mood=Ind|Number=Sing|Person=1|Tense=Past|VerbForm=Fin|Voice=Act"
    assert feats("v3plia---") == "Mood=Ind|Number=Plur|Person=3|Tense=Pqp|VerbForm=Fin|Voice=Act"
    assert feats("a-s---mac") == "Case=Acc|Degree=Cmp|Gender=Masc|Number=Sing"
    assert feats("v--pne---") == "Tense=Pres|VerbForm=Inf|Voice=Mid"
    assert feats("d--------") == "_"
    assert feats("") == "_"
