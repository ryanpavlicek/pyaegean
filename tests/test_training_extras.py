"""Tests for the Stage D+ extra-treebank loader (training/extra_treebanks.py).

Offline: a toy AGDT-schema file exercises the artificial-node drop + head re-resolution,
and the overlap-key helpers from the builder are pinned."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_DIR = Path(__file__).parent.parent / "training"
sys.path.insert(0, str(_DIR))

spec = importlib.util.spec_from_file_location("extra_treebanks", _DIR / "extra_treebanks.py")
assert spec is not None and spec.loader is not None
xt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(xt)

_TOY = """<?xml version="1.0" encoding="UTF-8"?>
<treebank>
  <sentence id="1">
    <word id="1" form="λέγει" lemma="λέγω" postag="v3spia---" relation="PRED" head="0"/>
    <word id="2" form="[0]" lemma="" postag="" relation="PRED" head="1" artificial="elliptic"/>
    <word id="3" form="λόγον" lemma="λόγος" postag="n-s---ma-" relation="OBJ" head="2"/>
    <word id="4" form="καλόν" lemma="καλός" postag="a-s---ma-" relation="ATR" head="3"/>
  </sentence>
</treebank>
"""


def test_artificial_nodes_dropped_and_heads_reresolved(tmp_path: Path) -> None:
    fp = tmp_path / "toy.xml"
    fp.write_text(_TOY, encoding="utf-8")
    rows = xt.load_extra("gorman", paths=[fp])
    assert len(rows) == 1
    attrs = rows[0]["attrs"]
    assert [a["form"] for a in attrs] == ["λέγει", "λόγον", "καλόν"]  # [0] dropped
    by_id = {a["id"]: a for a in attrs}
    # λόγον's head pointed at the artificial node (2) → re-resolved to its head (1)
    assert by_id["3"]["head"] == "1"
    assert by_id["4"]["head"] == "3"  # untouched
    assert rows[0]["file"].startswith("gorman:")


def test_herodotus_files_are_excluded_at_source() -> None:
    assert len(xt.GORMAN_HERODOTUS_EXCLUDED) == 10
    assert all(n.lower().startswith("hdt") for n in xt.GORMAN_HERODOTUS_EXCLUDED)
    fetch_list = xt._SOURCES["gorman"][1]
    assert not set(xt.GORMAN_HERODOTUS_EXCLUDED) & set(fetch_list)  # never fetched


def test_punct_strip_key_matches_proiel_tokenization() -> None:
    spec2 = importlib.util.spec_from_file_location(
        "build_full_dataset", _DIR / "build_full_dataset.py"
    )
    assert spec2 is not None and spec2.loader is not None
    bfd = importlib.util.module_from_spec(spec2)
    spec2.loader.exec_module(bfd)
    forms = ("ἐν", "ἀρχῇ", ",", "ἦν", ".")
    stripped = tuple(f for f in forms if not bfd._haspunct(f))
    assert stripped == ("ἐν", "ἀρχῇ", "ἦν")  # PROIEL-style: no punctuation tokens
