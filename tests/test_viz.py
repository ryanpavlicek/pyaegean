"""The aegean.viz one-liners (offline; headless Agg; skipped without matplotlib)."""

from __future__ import annotations

import pytest

matplotlib = pytest.importorskip("matplotlib")
matplotlib.use("Agg")

from aegean import viz  # noqa: E402
from aegean.core.model import Document, DocumentMeta, Token, TokenKind  # noqa: E402


def _doc(doc_id: str, words: list[str], site: str = "") -> Document:
    tokens = [Token(w, TokenKind.WORD, tuple(w.split("-")), None, 0, i) for i, w in enumerate(words)]
    return Document(
        id=doc_id, script_id="lineara", tokens=tokens,
        lines=[list(range(len(tokens)))] if tokens else [],
        meta=DocumentMeta(site=site),
    )


DOCS = [
    _doc("HT1", ["ku-ro", "pa-i-to", "ka-u-de-ta"], site="A"),
    _doc("HT2", ["ku-ro", "pa-i-to", "di-na-u"], site="A"),
    _doc("HT3", ["ku-ro", "ka-u-de-ta", "di-na-u"], site="B"),
    _doc("HT4", ["pa-i-to", "ka-u-de-ta", "sa-ro"], site="B"),
]


@pytest.fixture(autouse=True)
def _close_figures():
    yield
    import matplotlib.pyplot as plt

    plt.close("all")


def test_plot_sign_frequencies_words_and_signs(tmp_path):
    ax = viz.plot_sign_frequencies(DOCS, top=5, kind="words")
    assert len(ax.patches) == 5
    assert ax.get_title() == "top 5 words"
    out = tmp_path / "freq.png"
    ax.figure.savefig(out)
    assert out.stat().st_size > 0

    ax2 = viz.plot_sign_frequencies(DOCS, top=3, kind="signs")
    assert len(ax2.patches) == 3


def test_plot_dispersion_annotates(tmp_path):
    ax = viz.plot_dispersion(DOCS, min_frequency=2, annotate=2)
    assert ax.get_ylabel() == "DP (normalized)"
    texts = [t.get_text() for t in ax.texts]
    assert len(texts) == 2
    ax.figure.savefig(tmp_path / "dp.png")


def test_plot_keyness_diverging(tmp_path):
    target = DOCS[:2]
    reference = DOCS[2:]
    ax = viz.plot_keyness(target, reference, min_target=1, top=6)
    assert ax.patches  # bars drawn
    ax.figure.savefig(tmp_path / "key.png")


def test_plot_collocation_network_full_and_ego(tmp_path):
    ax = viz.plot_collocation_network(DOCS, min_count=2)
    assert "exploratory" in ax.get_title()
    ax.figure.savefig(tmp_path / "net.png")
    ax2 = viz.plot_collocation_network(DOCS, "ku-ro", min_count=1)
    assert "ku-ro" in ax2.get_title()
    with pytest.raises(ValueError, match="no co-occurring"):
        viz.plot_collocation_network(DOCS, min_count=99)


def test_plot_scansion_from_text(tmp_path):
    line = "ἄνδρα μοι ἔννεπε, Μοῦσα, πολύτροπον, ὃς μάλα πολλὰ"
    ax = viz.plot_scansion(line)
    assert "hexameter" in ax.get_title()
    assert ax.patches  # one rectangle per syllable
    ax.figure.savefig(tmp_path / "scan.png")


def test_plot_scansion_accepts_scansion_object():
    from aegean.greek.meter import scan_line

    s = scan_line("ἄνδρα μοι ἔννεπε, Μοῦσα, πολύτροπον, ὃς μάλα πολλὰ")
    ax = viz.plot_scansion(s)
    assert len(ax.patches) == len(s.syllables)


def test_plot_balance_on_lineara(tmp_path):
    import aegean

    c = aegean.load("lineara")
    ax = viz.plot_balance(c)
    assert ax.get_xlabel() == "computed sum of items"
    assert ax.collections  # scatter layers present
    ax.figure.savefig(tmp_path / "balance.png")


def test_cli_plot_writes_files(tmp_path):
    from typer.testing import CliRunner

    from aegean.cli import _build_app

    app = _build_app()
    runner = CliRunner()
    out = tmp_path / "freq.png"
    r = runner.invoke(app, ["plot", "freq", "lineara", "-o", str(out), "--top", "5"])
    assert r.exit_code == 0, r.output
    assert out.stat().st_size > 0

    out2 = tmp_path / "scan.svg"
    r2 = runner.invoke(
        app,
        ["plot", "scansion", "ἄνδρα μοι ἔννεπε, Μοῦσα, πολύτροπον, ὃς μάλα πολλὰ", "-o", str(out2)],
    )
    assert r2.exit_code == 0, r2.output
    assert out2.stat().st_size > 0

    r3 = runner.invoke(app, ["plot", "nope", "lineara", "-o", str(tmp_path / "x.png")])
    assert r3.exit_code == 1
    r4 = runner.invoke(app, ["plot", "keyness", "lineara", "-o", str(tmp_path / "k.png")])
    assert r4.exit_code == 1  # needs --reference or a filter
