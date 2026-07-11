"""R33 regression tests: viz.parse_period cross-era / abbreviated / Roman-range parsing,
viz.plot_findspots normalized site resolution, analysis.seriation permutation invariance.

Each test verifies the actual output against a known-answer or a property invariant (a range
straddling the epoch, a permutation recovering the same band up to reversal), never merely that
the call runs. Corpus-backed and matplotlib/geopandas-backed checks skip when the dependency or
the cached corpus is unavailable.
"""

from __future__ import annotations

import random
import re

import pytest

from aegean import viz
from aegean.analysis.seriation import seriate
from aegean.core.model import Document, DocumentMeta, Token, TokenKind


# --------------------------------------------------------------------------- #
# parse_period: the verified panel cases (findings 1-3)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # (1) cross-era ranges keep both signs (each side read on its own era)
        ("27 BC - 14 AD", (-27, 14)),
        ("100 BC - 200 AD", (-100, 200)),
        ("1st century BCE - 1st century CE", (-100, 100)),
        ("30 BC-AD 323", (-30, 323)),  # papyri shorthand: hyphen, era before the year
        ("30 BC-14 AD", (-30, 14)),
        ("21 BC-5 AD", (-21, 5)),
        ("50 BC – 50 AD", (-50, 50)),  # en dash
        # (2) abbreviated centuries -> full century span, never a stray single year
        ("First half of the 5th cent. BCE", (-500, -401)),
        ("2nd half of III cent B.C.E", (-300, -201)),
        ("not before I cent C.E", (1, 100)),
        # (3) Roman-numeral century ranges span both centuries
        ("II-III century C.E", (101, 300)),
        ("late IV - early III century B.C.E.", (-400, -201)),
        ("VI-V century B.C.E.", (-600, -401)),
        ("XIV–XVth centuries C.E", (1301, 1500)),
        ("I-II century C.E", (1, 200)),
    ],
)
def test_parse_period_panel(text, expected):
    assert viz.parse_period(text) == expected


# --------------------------------------------------------------------------- #
# parse_period: curated REAL strings from igcyr / iospe / edh / ddbdp (CI-safe)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # bilingual iospe range: the far century (IV) is no longer dropped
        ("кон. IV – нач. III в. до н.э. late IV - early III century B.C.Е.", (-400, -201)),
        # the "1-я"/"2-я" ordinal-suffix hyphen must NOT be read as a range delimiter,
        # and the "2" of "2nd half" must NOT be read as a century
        ("2-я пол. IV в. до н.э. 2nd half of IV century B.C.Е.", (-400, -301)),
        ("1-я пол. III в. до н.э. 1st half of III century B.C.Е.", (-300, -201)),
        ("III в. до н.э. III century B.C.Е.", (-300, -201)),  # bilingual, purely BCE
        ("late VI - early V century B.C.E.", (-600, -401)),
        ("early V century B.C.E.", (-500, -401)),
        ("ca. 500 B.C.E.", (-500, -500)),
        ("c. 101-88 BC", (-101, -88)),  # circa year range: "c." is not a century here
        ("15/14 BC-AD 14", (-15, 14)),  # slash within a side, hyphen the range
    ],
)
def test_parse_period_real_strings(text, expected):
    assert viz.parse_period(text) == expected


# --------------------------------------------------------------------------- #
# parse_period: single-era / non-range strings stay exactly as before
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("", None),
        ("Hellenistic", None),
        ("(?)", None),
        ("Third century BC", (-300, -201)),
        ("1st century BCE", (-100, -1)),
        ("II century C.E", (101, 200)),
        ("IVth century C.E", (301, 400)),
        ("Fourth or third century BC", (-400, -201)),
        ("4th — 5th century CE", (301, 500)),
        ("480—450 BCE", (-480, -450)),
        ("201 AD – 300 AD", (201, 300)),
        ("Ca. 500 BC", (-500, -500)),
        ("Late C3 AD - C4 AD", (201, 400)),
        ("Second half of fourth century BC", (-400, -301)),
    ],
)
def test_parse_period_single_era_unchanged(text, expected):
    assert viz.parse_period(text) == expected


def test_parse_period_crossera_straddles_epoch():
    # A genuine BCE->CE span must start negative and end positive (the core of finding 1).
    for s in ("27 BC - 14 AD", "100 BC - 200 AD", "30 BC-AD 323", "1st century BCE - 1st century CE"):
        rng = viz.parse_period(s)
        assert rng is not None, s
        lo, hi = rng
        assert lo < 0 < hi, (s, rng)
        assert lo <= hi


def test_parse_period_abbrev_century_never_stray_year():
    # Century intent must not collapse to a small year (finding 2 regression guard).
    for s in ("First half of the 5th cent. BCE", "2nd half of III cent B.C.E"):
        lo, hi = viz.parse_period(s)
        assert lo <= -201 and hi <= -1  # a real century span, not (-5,-5)/(-2,-2)
        assert hi - lo == 99


# --------------------------------------------------------------------------- #
# parse_period: property checks across the real corpora (skip if not cached)
# --------------------------------------------------------------------------- #


def _opposite_era_sides(period: str) -> bool:
    """True when the string splits into two sides whose eras are opposite (a genuine
    BCE->CE span), using the module's own side/era logic so the 'B.C.E.' spelling is
    correctly read as BCE, not as a stray 'C.E.'."""
    sides = viz._split_sides(period.lower())
    if len(sides) != 2:
        return False
    eras = {viz._era(sides[0]), viz._era(sides[1])}
    return eras == {-1, 1}


def test_no_crossera_misparse_across_corpora():
    aegean = pytest.importorskip("aegean")
    checked = 0
    loaded = 0
    for cid in ("igcyr", "iospe", "edh", "ddbdp"):
        try:
            corpus = aegean.load(cid)
        except Exception:  # noqa: BLE001 - corpus not cached offline
            continue
        loaded += 1
        for d in corpus:
            period = d.meta.period or ""
            if not _opposite_era_sides(period):
                continue
            rng = viz.parse_period(period)
            assert rng is not None, period  # a cross-era string is never unreadable here
            lo, hi = rng
            assert lo < 0 < hi, (period, rng)  # every cross-era span straddles the epoch
            assert lo <= hi
            checked += 1
    if loaded == 0:
        pytest.skip("no epigraphy corpora available offline")
    assert checked > 0  # the corpora do contain cross-era strings


def test_every_parsed_period_has_start_le_end():
    aegean = pytest.importorskip("aegean")
    loaded = 0
    for cid in ("igcyr", "iospe", "edh"):
        try:
            corpus = aegean.load(cid)
        except Exception:  # noqa: BLE001
            continue
        loaded += 1
        for d in corpus:
            rng = viz.parse_period(d.meta.period or "")
            if rng is not None:
                assert rng[0] <= rng[1], (d.meta.period, rng)
    if loaded == 0:
        pytest.skip("no epigraphy corpora available offline")


# --------------------------------------------------------------------------- #
# plot_findspots: resolve through the normalized gazetteer index
# --------------------------------------------------------------------------- #


def _sdoc(doc_id: str, site: str) -> Document:
    tok = Token("ku-ro", TokenKind.WORD, ("ku", "ro"), None, 0, 0)
    return Document(
        id=doc_id, script_id="lineara", tokens=[tok], lines=[[0]],
        meta=DocumentMeta(site=site),
    )


def test_plot_findspots_aggregates_whitespace_variants():
    matplotlib = pytest.importorskip("matplotlib")
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # noqa: F401 - forces the Agg backend load

    from aegean.geo import _normalize_site, site_coordinates

    coords = site_coordinates()
    key = next(iter(coords))  # a real gazetteer label
    noisy = "  " + "\n  ".join(key.split(" ")) + "  "  # same site, whitespace mangled
    assert _normalize_site(noisy) == _normalize_site(key)

    docs = [_sdoc("d1", key), _sdoc("d2", noisy), _sdoc("d3", key)]
    ax = viz.plot_findspots(docs)
    try:
        # all three inscriptions land on ONE resolved site, not two raw labels
        assert ax.collections[0].get_offsets().shape[0] == 1
        assert "1 sites" in ax.get_title()
        assert "3 inscriptions" in ax.get_title()
    finally:
        matplotlib.pyplot.close("all")


def test_plot_findspots_counts_agree_with_geo():
    matplotlib = pytest.importorskip("matplotlib")
    matplotlib.use("Agg")
    pytest.importorskip("geopandas")
    aegean = pytest.importorskip("aegean")
    try:
        corpus = aegean.load("iip")
    except Exception:  # noqa: BLE001
        pytest.skip("iip corpus not available offline")

    from aegean.geo import site_coordinates, to_geodataframe

    gdf = to_geodataframe(corpus, level="inscription")
    coords = site_coordinates()
    old_raw = sum(1 for d in corpus if d.meta.site in coords)  # pre-fix raw-label count

    ax = viz.plot_findspots(corpus)
    try:
        m = re.search(r"(\d+) inscriptions", ax.get_title())
        assert m is not None
        plotted = int(m.group(1))
        assert plotted == len(gdf)  # the plot now agrees with geo.to_geodataframe
        assert plotted > old_raw  # normalization recovers inscriptions the raw match dropped
    finally:
        matplotlib.pyplot.close("all")


# --------------------------------------------------------------------------- #
# seriate: permutation invariance (finding 5)
# --------------------------------------------------------------------------- #


def _battleship(n: int, m: int, spread: float = 2.2) -> list[list[float]]:
    """A planted seriation: each type's unimodal peak marches along the assemblage sequence,
    so row order 0..n-1 is the true seriation (a Robinson band matrix after BR similarity)."""
    peaks = [t * (n - 1) / (m - 1) for t in range(m)]
    return [
        [max(0.0, 10.0 - spread * abs(a - peaks[t])) for t in range(m)] for a in range(n)
    ]


def test_seriate_canonical_band_and_finding_permutation():
    planted = _battleship(6, 5)
    truth = list(range(6))
    base = list(seriate(planted).order)
    assert base == truth or base == truth[::-1]
    # the exact permutation from the finding: the old code returned a scrambled order
    perm = [5, 1, 2, 0, 4, 3]
    recovered = [perm[i] for i in seriate([planted[p] for p in perm]).order]
    assert recovered == truth or recovered == truth[::-1]


def test_seriate_permutation_invariant_20_shuffles():
    planted = _battleship(6, 5)
    truth = list(range(6))
    for s in range(20):
        rng = random.Random(s)
        perm = truth[:]
        rng.shuffle(perm)
        recovered = [perm[i] for i in seriate([planted[p] for p in perm]).order]
        assert recovered == truth or recovered == truth[::-1], (s, recovered)


def test_seriate_permutation_invariant_larger_matrix():
    planted = _battleship(12, 7)
    truth = list(range(12))
    for s in range(20):
        rng = random.Random(1000 + s)
        perm = truth[:]
        rng.shuffle(perm)
        recovered = [perm[i] for i in seriate([planted[p] for p in perm]).order]
        assert recovered == truth or recovered == truth[::-1], (s, recovered)


def test_seriate_direction_is_canonicalized():
    planted = _battleship(8, 5)
    a = seriate(planted).order
    b = seriate(planted).order
    assert a == b  # deterministic
    assert a[0] < a[-1]  # canonical direction: smaller input index at the low end
    # the reverse input yields the reverse ordering (documented reversal)
    rev = seriate(list(reversed(planted))).order
    mapped = [len(planted) - 1 - i for i in rev]
    assert mapped == list(a) or mapped == list(a)[::-1]


def test_seriate_order_is_valid_permutation_on_random_matrix():
    rng = random.Random(7)
    mat = [[rng.randint(0, 15) for _ in range(6)] for _ in range(9)]
    result = seriate(mat)
    assert sorted(result.order) == list(range(9))
    assert result.iterations >= 0
