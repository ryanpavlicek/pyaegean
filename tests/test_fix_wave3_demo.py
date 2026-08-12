"""The browser demo's Linear A seriation, against both libraries it can run on.

The page installs pyaegean from PyPI, so the card meets two shapes of ``SeriationResult``:
one that reports the similarity graph's connected blocks and one that reports the ordering
alone. Tablets that share no sign are joined by no similarity evidence, so reading a flat
ordering as one sequence turns unrelated fragments into an apparent run: Khania is 21 blocks,
and its 111-tablet block sits next to 20 others it shares nothing with. Where the blocks are
reported the card must show them; where they are not it must claim none.

These tests pin the demo function's block reporting against a direct seriation of the same
documents, the partition invariant the per-block rendering relies on, the largest-block marker
(which is withheld when blocks tie for largest, a tie eight Linear A sites have), the
degraded shape when the installed library reports no blocks, the disclosure text, the
site-input error path on both Linear A cards, and the card wiring: blocks rather than one
chain, a suggestion list the browser can actually run, and a label cap that leaves the card's
default site complete.
"""

from __future__ import annotations

import importlib.util
import json
import re
import warnings
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

import aegean
from aegean.analysis import seriation as seriation_module
from aegean.analysis.seriation import SeriationResult, seriate

_DEMO_DIR = Path(__file__).resolve().parents[1] / "docs" / "demo"


@lru_cache(maxsize=1)
def _load_demo() -> ModuleType:
    spec = importlib.util.spec_from_file_location("_pyaegean_web_demo_wave3", _DEMO_DIR / "demo.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@lru_cache(maxsize=None)
def _seriate_site(site: str) -> str:
    """The demo's JSON for one site (cached: a large site's seriation is not cheap)."""
    return str(_load_demo().seriate_site(site))


def _demo(site: str) -> dict[str, Any]:
    out = json.loads(_seriate_site(site))
    assert isinstance(out, dict)
    return out


@lru_cache(maxsize=None)
def _direct(site: str) -> SeriationResult:
    """Seriate the site's documents through the library, with the ambiguity warnings muted."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return seriate(aegean.load("lineara").filter(site=site))


@lru_cache(maxsize=1)
def _page() -> str:
    return (_DEMO_DIR / "index.html").read_text(encoding="utf-8")


def _handler_source() -> str:
    """The `ser:` arrow function out of the demo page's handler table."""
    html = _page()
    start = html.index("  ser: () => {")
    return html[start : html.index("\n  },", start)]


def _seriation_card() -> str:
    """The seriation card's markup, its source line breaks collapsed to single spaces so a
    sentence reads the same here as it does on the page."""
    html = _page()
    card = html[html.index("<h2>Linear A seriation") : html.index("<h2>Sign-variant")]
    return re.sub(r"\s+", " ", card)


@dataclass(frozen=True)
class _OrderingOnlyResult:
    """A ``SeriationResult`` carrying only the fields pyaegean 0.58.0 defines.

    The demo page installs pyaegean from PyPI, so this is the result the card actually
    receives until a release carries the blocks: an ordering, the similarity it came from,
    the solver's pass count, and the row labels. There is no ``components`` and no
    ``ambiguous`` to read."""

    order: tuple[int, ...]
    similarity: tuple[tuple[float, ...], ...]
    iterations: int
    labels: tuple[str, ...] | None

    def ordered_labels(self) -> tuple[str, ...] | None:
        if self.labels is None:
            return None
        return tuple(self.labels[i] for i in self.order)


# --------------------------------------------------------------------------- #
# the blocks, measured against a direct seriation
# --------------------------------------------------------------------------- #


def test_seriate_site_reports_the_blocks_a_direct_seriation_finds() -> None:
    """blocks / largest_block / ambiguous / the per-block sequences all come from the
    similarity graph, not from a single flattened ordering."""
    for site in ("Zakros", "Khania", "Petras"):
        got, ref = _demo(site), _direct(site)
        labels = ref.labels or ()
        expected = [[labels[i] for i in block] for block in ref.components]
        assert got["blocks"] == len(expected), site
        assert [g["size"] for g in got["groups"]] == [len(b) for b in expected], site
        assert [g["order"] for g in got["groups"]] == expected, site
        assert got["largest_block"] == max(len(b) for b in expected), site
        assert got["ambiguous"] is ref.ambiguous, site
        assert got["seriated"] == len(ref.order), site


def test_seriate_site_splits_khania_into_its_twenty_one_blocks() -> None:
    """The site the card suggests: 208 of 226 documents seriate, and they are 21 blocks that
    share no sign with one another, not one 208-tablet sequence."""
    r = _demo("Khania")
    assert r["site"] == "Khania" and r["documents"] == 226 and r["seriated"] == 208
    assert r["blocks"] == 21
    assert [g["size"] for g in r["groups"]] == [
        111, 25, 13, 11, 9, 8, 6, 5, 3, 2, 2, 2, 2, 2, 1, 1, 1, 1, 1, 1, 1
    ]
    assert r["largest_block"] == 111
    # the largest block is a minority of the site: 97 tablets sit outside it
    assert sum(g["size"] for g in r["groups"] if not g["largest"]) == 97


def test_seriate_site_keeps_a_connected_site_whole() -> None:
    """Zakros shares signs throughout, so it is one block and its sequence runs end to end."""
    r = _demo("Zakros")
    assert r["blocks"] == 1 and r["ambiguous"] is False
    assert r["groups"][0]["size"] == r["seriated"] == 47
    assert r["groups"][0]["largest"] is True
    assert r["groups"][0]["order"] == r["order"]
    assert r["order"][0] == "ZAWa38"  # the deterministic, input-order-invariant ordering


def test_seriate_site_groups_partition_the_ordering() -> None:
    """The rendering slices the flat ordering into blocks, so the blocks must tile it exactly:
    same labels, same sequence, no repeat, nothing dropped."""
    for site in ("Zakros", "Phaistos", "Khania", "Petras", "Kea"):
        r = _demo(site)
        flat = [label for g in r["groups"] for label in g["order"]]
        assert flat == r["order"], site
        assert sum(g["size"] for g in r["groups"]) == r["seriated"], site
        assert len(set(flat)) == len(flat), site
        assert all(g["size"] == len(g["order"]) for g in r["groups"]), site


def test_seriate_site_marks_the_one_largest_block_wherever_it_sits() -> None:
    """The global direction flip that makes the ordering reproducible can reverse the block
    layout, so the largest block sits at one END, not necessarily first. Petras lays its
    9-tablet block after a 2-tablet one; exactly one block carries the marker either way."""
    petras = _demo("Petras")
    assert [g["size"] for g in petras["groups"]] == [2, 9]
    assert [g["largest"] for g in petras["groups"]] == [False, True]
    for site in ("Zakros", "Khania", "Petras", "Phaistos", "Vrysinas"):
        r = _demo(site)
        sizes = [g["size"] for g in r["groups"]]
        assert sizes.count(max(sizes)) == 1, site  # these sites have one biggest block
        flagged = [g for g in r["groups"] if g["largest"]]
        assert len(flagged) == 1, site
        assert flagged[0]["size"] == r["largest_block"] == max(sizes)


def test_seriate_site_marks_no_block_when_the_blocks_tie_for_largest() -> None:
    """"Largest" is a distinction the sizes have to carry. On the eight Linear A sites whose
    blocks are all the same size there is no largest, so no block is marked: flagging the
    first of several equals would print "(largest)" above blocks of identical size."""
    tied = {
        "Kea": [1, 1, 1, 1, 1, 1],
        "Kythera": [1, 1],
        "Larani": [1, 1],
        "Milos": [1, 1, 1],
        "Mycenae": [1, 1],
        "Poros Herakleiou": [1, 1],
        "Psykhro": [1, 1],
        "Samothrace": [1, 1],
    }
    for site, sizes in tied.items():
        r = _demo(site)
        assert [g["size"] for g in r["groups"]] == sizes, site
        assert [g["largest"] for g in r["groups"]] == [False] * len(sizes), site
        assert r["largest_block"] == max(sizes), site  # the size is still reported


# --------------------------------------------------------------------------- #
# the library the page installs may report no blocks at all
# --------------------------------------------------------------------------- #


def test_seriate_site_claims_no_blocks_when_the_installed_library_reports_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Against a ``SeriationResult`` with only the released fields, the card reports the one
    sequence that result carries and asserts no block, no largest, and no ambiguity: reading
    those off a result that does not have them is an error string on a deployed page, and
    inventing them would be a claim the library never made."""
    ref = _direct("Khania")
    released = _OrderingOnlyResult(ref.order, ref.similarity, ref.iterations, ref.labels)
    assert not hasattr(released, "components") and not hasattr(released, "ambiguous")
    monkeypatch.setattr(seriation_module, "seriate", lambda *a, **k: released)

    r = json.loads(_load_demo().seriate_site("Khania"))
    assert "error" not in r
    assert r["blocks"] is None
    for invented in ("groups", "largest_block", "ambiguous"):
        assert invented not in r, invented
    assert r["sequence"] == list(ref.ordered_labels() or ())
    assert r["site"] == "Khania" and r["documents"] == 226 and r["seriated"] == 208
    assert "EXPLORATORY" in r["note"]
    assert "without the similarity graph's blocks" in r["note"]
    assert "not by itself evidence" in r["note"]


def test_demo_card_renders_a_blockless_result_without_touching_the_block_fields() -> None:
    """The page reaches the ordering-only branch before it maps over the blocks, so a library
    that reports none renders its sequence instead of failing on a missing field."""
    src = _handler_source()
    assert "if (!r.groups) {" in src
    assert src.index("if (!r.groups) {") < src.index("r.groups.map")
    assert "r.sequence" in src
    fallback = "\n".join(
        line
        for line in src[src.index("if (!r.groups) {") : src.index("const head")].splitlines()
        if not line.lstrip().startswith("//")  # what it renders, not what it explains
    )
    # nothing on that branch renders a block count, a block heading, or a largest marker
    for claim in ("similarity block", "block ${", "g.largest", "r.blocks", "r.ambiguous"):
        assert claim not in fallback, claim
    assert "sharing no sign can stand" in fallback


# --------------------------------------------------------------------------- #
# what the result says about itself
# --------------------------------------------------------------------------- #


def test_seriate_site_note_discloses_the_split_and_the_ambiguity() -> None:
    """A multi-block result states the count and that the between-block order is a convention,
    a single connected block claims neither, an undetermined axis is named as such, and the
    exploratory caveat travels with every one of them."""
    for site in ("Zakros", "Khania", "Petras", "Phaistos"):
        note, blocks, ref = _demo(site)["note"], _demo(site)["blocks"], _direct(site)
        assert "EXPLORATORY" in note, site
        if blocks > 1:
            assert f"{blocks} blocks" in note, site
            assert "only within a block" in note and "convention" in note, site
        else:
            assert "block" not in note, site
        assert ("ambiguous" in note) is ref.ambiguous, site
    assert _demo("Khania")["blocks"] == 21 and _demo("Zakros")["blocks"] == 1


# --------------------------------------------------------------------------- #
# input handling, on both Linear A site cards
# --------------------------------------------------------------------------- #


def test_seriate_site_answers_unusable_site_input_with_an_error() -> None:
    """Blank, unknown, oversized, and non-string input each return the JSON error plus the
    site list to choose from, never a traceback and never a silent stand-in result."""
    for bad in ("", "   ", "\t\n", "Atlantis", "zakros", "x" * 5000, None, 7, ["Zakros"]):
        r = json.loads(_load_demo().seriate_site(bad))  # type: ignore[arg-type]
        assert "error" in r, repr(bad)
        assert "Zakros" in r["sites"] and "Khania" in r["sites"], repr(bad)
        assert "order" not in r and "groups" not in r and "sequence" not in r, repr(bad)
    # the three documents whose recorded site is empty are not what a blank box asks for
    assert sum(1 for d in aegean.load("lineara").documents if not d.meta.site) == 3
    assert "no Linear A documents" in json.loads(_load_demo().seriate_site(""))["error"]


def test_lineara_stats_answers_unusable_site_input_with_an_error() -> None:
    """The statistics card takes a site the same way. Keyness measures one site against the
    rest, so a blank box has no site to measure: it returns the list to choose from, not a
    table computed over the documents that record no find-site at all."""
    demo = _load_demo()
    for bad in ("", "   ", "\t\n", "Atlantis", "khania", "x" * 5000, None, 7, ["Khania"]):
        r = json.loads(demo.lineara_stats(bad))
        assert "error" in r, repr(bad)
        assert "Zakros" in r["sites"] and "Khania" in r["sites"], repr(bad)
        assert "keyness" not in r and "dispersion" not in r, repr(bad)
    assert sum(1 for d in aegean.load("lineara").documents if not d.meta.site) == 3
    named = json.loads(demo.lineara_stats("Khania"))
    assert named["site"] == "Khania" and named["keyness"] and named["dispersion"]


# --------------------------------------------------------------------------- #
# the card
# --------------------------------------------------------------------------- #


def test_demo_card_renders_the_blocks_rather_than_one_chain() -> None:
    """The page's seriation handler builds its output from the blocks and never joins the flat
    ordering into a single sequence."""
    src = _handler_source()
    assert "r.groups.map" in src
    assert "r.blocks" in src and "g.size" in src and "g.largest" in src
    assert "r.order" not in src  # the flat ordering is exactly what misreads as one sequence
    assert "block" in src


def test_demo_card_prints_its_default_site_in_full() -> None:
    """The label cap is above the card's out-of-the-box result, so the view a first-time
    reader gets is the whole sequence, and still below the largest block of a large site,
    so a 111-tablet block does not run off the card."""
    src = _handler_source()
    cap = int(re.search(r"const cap = (\d+);", src).group(1))  # type: ignore[union-attr]
    default = re.search(r'id="ser" value="([^"]+)"', _page()).group(1)  # type: ignore[union-attr]
    shown = _demo(default)
    assert max(g["size"] for g in shown["groups"]) <= cap, default
    assert max(g["size"] for g in _demo("Khania")["groups"]) > cap  # the cap still caps


def test_demo_card_prose_describes_a_blocked_result() -> None:
    """The card's own text tells the reader what comes back: blocks, each its own sequence,
    with the between-block order a convention."""
    card = _seriation_card()
    assert "blocks" in card and "each its own sequence" in card
    assert "only within a block" in card and "stated convention" in card
    assert "a deterministic sequence that puts compositionally similar tablets" not in card


def test_demo_card_suggests_only_sites_the_browser_can_seriate() -> None:
    """Every site the card offers is one the page can actually run. Haghia Triada is a
    thousand tablets and is named as too large rather than offered, with the count it is
    named by matching the corpus."""
    card = _seriation_card()
    suggested = set(re.findall(r"<code>([^<]+)</code>", card))
    assert suggested == {"Zakros", "Khania", "Phaistos"}
    for site in sorted(suggested):
        assert len(aegean.load("lineara").filter(site=site).documents) <= 226, site
    haghia = len(aegean.load("lineara").filter(site="Haghia Triada").documents)
    assert haghia > 1000  # the site the browser is told to leave alone
    assert f"{haghia:,} tablets are more than the browser" in card
