"""The `aegean plot` command — the aegean.viz one-liners as image files."""

from __future__ import annotations

import sys
from pathlib import Path

import typer

from ._common import apply_meta_filters, fail, load_corpus, read_text, writing
from ._corpus import PERIOD_OPT, SCRIBE_OPT, SITE_OPT, SUPPORT_OPT

_KINDS = ("freq", "dispersion", "keyness", "network", "balance", "scansion")

# Kept word-for-word in step with `aegean greek scan --meter`: plot's scansion meter is
# passed straight to greek.scan_line, so the two helps must name the same meters.
_METER_HELP = (
    "Scansion: hexameter, pentameter, trimeter, or an aeolic line "
    "(glyconic, pherecratean, sapphic_hendecasyllable, adonean, "
    "alcaic_hendecasyllable, alcaic_enneasyllable, alcaic_decasyllable)."
)


def register(app: typer.Typer) -> None:
    app.command()(plot)


def plot(
    kind: str = typer.Argument(..., help="One of: " + " | ".join(_KINDS)),
    subject: str = typer.Argument(
        ..., help="Corpus name — or, for `scansion`, the Greek line ('-' reads stdin)."
    ),
    output: Path = typer.Option(..., "--output", "-o", help="Image file (.png/.svg/.pdf)."),
    signs: bool = typer.Option(False, "--signs", help="Sign-level (freq/dispersion/keyness)."),
    top: int = typer.Option(20, "--top", help="How many items (freq/dispersion/keyness)."),
    site: str | None = SITE_OPT,
    period: str | None = PERIOD_OPT,
    scribe: str | None = SCRIBE_OPT,
    support: str | None = SUPPORT_OPT,
    reference: str | None = typer.Option(
        None, "--reference", help="Keyness: reference corpus (else filters split subset vs rest)."
    ),
    word: str | None = typer.Option(None, "--word", help="Network: this word's ego network."),
    min_count: int = typer.Option(2, "--min-count", help="Network: minimum shared documents."),
    meter: str = typer.Option("hexameter", "--meter", help=_METER_HELP),
    dpi: int = typer.Option(150, "--dpi", help="Raster resolution for .png output."),
) -> None:
    """Draw one figure (frequencies, dispersion, keyness, co-occurrence network,
    accounting balance, or a scansion grid) and write it to --output.

    Needs the viz extra: pip install 'pyaegean\\[viz]'.
    """
    if kind not in _KINDS:
        raise fail(f"unknown plot kind {kind!r}; one of: {', '.join(_KINDS)}")
    try:
        import matplotlib

        matplotlib.use("Agg")  # headless: the CLI always writes a file
    except ImportError:
        raise fail(
            "matplotlib is required — install the viz extra: pip install 'pyaegean[viz]'"
        ) from None

    from aegean import viz

    item_kind = "signs" if signs else "words"
    try:
        if kind == "scansion":
            ax = viz.plot_scansion(read_text(subject), meter=meter)
        else:
            c = load_corpus(subject)
            filtered = apply_meta_filters(c, site, period, scribe, support)
            if kind == "freq":
                ax = viz.plot_sign_frequencies(filtered, top=top, kind=item_kind)
            elif kind == "dispersion":
                ax = viz.plot_dispersion(filtered, kind=item_kind, annotate=top)
            elif kind == "keyness":
                if reference is not None:
                    target, ref = filtered, load_corpus(reference)
                elif filtered is not c:
                    subset_ids = {d.id for d in filtered.documents}
                    target = filtered
                    ref = [d for d in c.documents if d.id not in subset_ids]
                else:
                    raise fail(
                        "keyness needs --reference CORPUS or a filter (--site/--period/…)"
                    )
                ax = viz.plot_keyness(target, ref, kind=item_kind, top=top)
            elif kind == "network":
                ax = viz.plot_collocation_network(filtered, word, min_count=min_count)
            else:  # balance
                ax = viz.plot_balance(filtered)
        with writing(output):  # parent dirs + one-line OSError failures
            ax.figure.savefig(output, dpi=dpi, bbox_inches="tight")
    except typer.Exit:  # an inner fail() already printed its one line — pass it through
        raise
    except ValueError as e:  # bad meter/dpi/format — matplotlib's message is readable
        raise fail(str(e)) from None
    except Exception as e:  # ScansionError etc. — one readable line, not a traceback
        raise fail(f"{type(e).__name__}: {e}") from None
    print(f"wrote {output}", file=sys.stderr)
