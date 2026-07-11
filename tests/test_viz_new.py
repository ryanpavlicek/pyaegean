"""The new aegean.viz plots: find-sites, date timeline, sign/word network, plotly backend.

Offline; headless Agg; matplotlib-gated. Plotly tests skip without the [viz-interactive] extra.
"""

from __future__ import annotations

import pytest

matplotlib = pytest.importorskip("matplotlib")
matplotlib.use("Agg")

from aegean import viz  # noqa: E402
from aegean.core.model import Document, DocumentMeta, Token, TokenKind  # noqa: E402


def _wdoc(doc_id: str, words: list[str], site: str = "", period: str = "") -> Document:
    tokens = [
        Token(w, TokenKind.WORD, tuple(w.split("-")), None, 0, i) for i, w in enumerate(words)
    ]
    return Document(
        id=doc_id, script_id="lineara", tokens=tokens,
        lines=[list(range(len(tokens)))] if tokens else [],
        meta=DocumentMeta(site=site, period=period),
    )


@pytest.fixture(autouse=True)
def _close_figures():
    yield
    import matplotlib.pyplot as plt

    plt.close("all")


# ── parse_period (best-effort date reader) ───────────────────────────────────


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("", None),
        ("Hellenistic", None),                         # named period, no number/era
        ("(?)", None),
        ("Third century BC", (-300, -201)),            # word ordinal + BC
        ("3rd century BC", (-300, -201)),              # digit ordinal
        ("1st century BCE", (-100, -1)),
        ("II century C.E", (101, 200)),                # Roman numeral + CE
        ("IVth century C.E", (301, 400)),
        ("Fourth or third century BC", (-400, -201)),  # century span
        ("4th — 5th century CE", (301, 500)),
        ("480—450 BCE", (-480, -450)),                 # explicit BCE year range
        ("201 AD – 300 AD", (201, 300)),               # explicit CE year range
        ("Ca. 500 BC", (-500, -500)),                  # single year
        ("Late C3 AD - C4 AD", (201, 400)),            # isicily "C3" abbreviation
        ("Second half of fourth century BC", (-400, -301)),  # fraction qualifier ignored
    ],
)
def test_parse_period(text, expected):
    assert viz.parse_period(text) == expected


# ── timeline (bins + honest unparsed handling) ───────────────────────────────


def _dated(doc_id: str, period: str) -> Document:
    return Document(
        id=doc_id, script_id="x", tokens=[Token("a", TokenKind.WORD, position=0)],
        lines=[[0]], meta=DocumentMeta(period=period),
    )


TIMELINE_DOCS = [
    _dated("d1", "Third century BC"),   # (-300,-201) mid -250.5 -> bin -300
    _dated("d2", "2nd century BC"),     # (-200,-101) mid -150.5 -> bin -200
    _dated("d3", "480—450 BCE"),        # (-480,-450) mid -465   -> bin -500
    _dated("d4", "201 AD – 300 AD"),    # (201,300)   mid  250.5 -> bin  200
    _dated("d5", "Hellenistic"),        # unparsed
    _dated("d6", ""),                   # unparsed
]


def test_timeline_bins_counts_and_unparsed():
    tl = viz.timeline_bins(TIMELINE_DOCS, bin_width=100)
    assert tl.total == 6 and tl.parsed == 4 and tl.unparsed == 2
    assert tl.unparsed_fraction == pytest.approx(2 / 6)
    assert [(b.start, b.count) for b in tl.bins] == [
        (-500, 1), (-300, 1), (-200, 1), (200, 1)
    ]


def test_timeline_bin_width_widens_buckets():
    tl = viz.timeline_bins(TIMELINE_DOCS, bin_width=500)
    # -465, -250.5, -150.5 all land in [-500,0); 250.5 in [0,500)
    counts = {b.start: b.count for b in tl.bins}
    assert counts == {-500: 3, 0: 1}


def test_timeline_bins_rejects_bad_width():
    with pytest.raises(ValueError, match="bin_width"):
        viz.timeline_bins(TIMELINE_DOCS, bin_width=0)


def test_plot_timeline_states_unparsed_fraction(tmp_path):
    ax = viz.plot_timeline(TIMELINE_DOCS, bin_width=100)
    assert len(ax.patches) == 4  # one bar per non-empty bin
    notes = [t.get_text() for t in ax.texts]
    assert "unparsed dates: 2 of 6 (33%)" in notes
    ax.figure.savefig(tmp_path / "timeline.png")


def test_plot_timeline_all_unparsed_still_reports(tmp_path):
    docs = [_dated("a", "Hellenistic"), _dated("b", "")]
    ax = viz.plot_timeline(docs)
    notes = [t.get_text() for t in ax.texts]
    assert "unparsed dates: 2 of 2 (100%)" in notes  # never silently dropped


def test_plot_timeline_empty_corpus_raises():
    with pytest.raises(ValueError, match="no documents"):
        viz.plot_timeline([])


# ── find-sites map ───────────────────────────────────────────────────────────


def test_plot_findspots_points_and_labels(tmp_path):
    import aegean
    from aegean.geo import site_coordinates

    c = aegean.load("lineara")
    coords = site_coordinates()
    expected_sites = {d.meta.site for d in c if d.meta.site in coords}
    ax = viz.plot_findspots(c)
    # one scatter collection whose point count == number of mapped sites
    assert len(ax.collections) == 1
    assert ax.collections[0].get_offsets().shape[0] == len(expected_sites)
    assert "find-sites" in ax.get_title()
    # labels carry the per-site inscription count "(N)"
    assert any(t.get_text().endswith(")") for t in ax.texts)
    ax.figure.savefig(tmp_path / "findspots.png")


def test_plot_findspots_no_sites_degrades_cleanly():
    docs = [_wdoc("d1", ["ku-ro"], site="Nowhere-XYZ")]
    with pytest.raises(ValueError, match="no find-sites"):
        viz.plot_findspots(docs)


# ── sign / word co-occurrence network ────────────────────────────────────────


NETWORK_DOCS = [
    _wdoc("D1", ["ku-ro", "pa-i-to"]),
    _wdoc("D2", ["ku-ro", "pa-i-to"]),
    _wdoc("D3", ["ku-ro", "di-na"]),
]


def test_plot_sign_network_nodes_and_title(tmp_path):
    ax = viz.plot_sign_network(NETWORK_DOCS, level="word", min_count=1)
    # one scatter per node; three distinct words co-occur
    assert len(ax.collections) == 3
    assert "exploratory" in ax.get_title()
    assert "co-occurrence" in ax.get_title()
    ax.figure.savefig(tmp_path / "signnet.png")


def test_plot_sign_network_caps_nodes():
    ax = viz.plot_sign_network(NETWORK_DOCS, level="sign", min_count=1, max_nodes=3)
    assert len(ax.collections) == 3  # capped to the 3 most frequent signs


def test_plot_sign_network_empty_degrades():
    with pytest.raises(ValueError, match="no co-occurring"):
        viz.plot_sign_network(NETWORK_DOCS, min_count=999)


def test_new_plots_reject_unknown_backend():
    with pytest.raises(ValueError, match="backend"):
        viz.plot_findspots(NETWORK_DOCS, backend="ggplot")
    with pytest.raises(ValueError, match="backend"):
        viz.plot_timeline(TIMELINE_DOCS, backend="ggplot")
    with pytest.raises(ValueError, match="backend"):
        viz.plot_sign_network(NETWORK_DOCS, backend="ggplot")


# ── plotly backend (skips without the extra) ─────────────────────────────────


def test_plotly_backend_returns_figures():
    pytest.importorskip("plotly")
    import aegean

    fig_f = viz.plot_findspots(aegean.load("lineara"), backend="plotly")
    assert type(fig_f).__name__ == "Figure" and len(fig_f.data) == 1

    fig_t = viz.plot_timeline(TIMELINE_DOCS, backend="plotly")
    assert type(fig_t).__name__ == "Figure"
    assert "unparsed dates: 2 of 6" in fig_t.layout.title.text  # stated on the plot

    fig_n = viz.plot_sign_network(NETWORK_DOCS, level="word", backend="plotly")
    assert len(fig_n.data) == 2  # one edge trace + one node trace


# ── CLI new kinds ────────────────────────────────────────────────────────────


def test_cli_plot_new_kinds(tmp_path):
    from typer.testing import CliRunner

    from aegean.cli import _build_app

    app = _build_app()
    runner = CliRunner()

    for kind, extra in (
        ("findspots", []),
        ("timeline", ["--bin-width", "50"]),
        ("signnet", ["--signs", "--scope", "line", "--min-count", "2"]),
    ):
        out = tmp_path / f"{kind}.png"
        r = runner.invoke(app, ["plot", kind, "lineara", "-o", str(out), *extra])
        assert r.exit_code == 0, r.output
        assert out.stat().st_size > 0

    # signnet with an impossible threshold: a clean one-line error, not a traceback
    r = runner.invoke(
        app, ["plot", "signnet", "lineara", "-o", str(tmp_path / "x.png"), "--min-count", "99999"]
    )
    assert r.exit_code == 1
    assert "no co-occurring" in r.output
