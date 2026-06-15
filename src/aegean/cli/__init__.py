"""The `aegean` command-line interface — the whole toolkit without writing Python.

Installed by the ``[cli]`` extra (``pip install "pyaegean[cli]"``; typer + rich).
The command tree mirrors the public API:

- corpus commands at the top level: ``info``, ``load``, ``show``, ``search``,
  ``query``, ``stats``, ``dispersion``, ``keyness``, ``balance``, ``cite``,
  ``export``, ``geo``, ``sign``, ``bridge``, ``plot``;
- ``aegean greek …`` — the full Greek NLP pipeline (normalize → … → parse,
  plus ``pipeline`` and the ``eval`` reproductions), with ``--neural`` /
  ``--treebank`` / … flags standing in for the ``use_*()`` activations;
- ``aegean analyze …`` — distance, alignment, cross-script comparison,
  association statistics, morphological clusters, structure census;
- ``aegean data …`` — the fetch-to-cache layer;
- ``aegean ai …`` — the generative layer (exploratory-labeled, key-gated).

Conventions: ``--json`` on every command for machine-readable output; a TEXT
argument of ``-`` reads stdin; errors are one line on stderr with exit code 1.
This module is imported only by the console script — ``import aegean`` never
pulls typer/rich, so the zero-dependency core stays clean.
"""

from __future__ import annotations

import sys
from typing import Any

__all__ = ["main"]


def main() -> None:
    """Console-script entry point (the ``aegean`` command)."""
    try:
        import typer  # noqa: F401
        import rich  # noqa: F401
    except ModuleNotFoundError:
        print(
            "aegean: the CLI needs the [cli] extra — pip install 'pyaegean[cli]'",
            file=sys.stderr,
        )
        raise SystemExit(1) from None
    _build_app()()


def _build_app() -> Any:
    import typer

    import aegean

    from . import _corpus, _viz, _workbench
    from ._ai import ai_app
    from ._analyze import analyze_app
    from ._data import data_app
    from ._db import db_app
    from ._greek import greek_app

    app = typer.Typer(
        pretty_exceptions_show_locals=False,
        help=(
            "pyaegean from the shell: corpora, Greek NLP, analysis, data, and the "
            "(exploratory) AI layer. Every command takes --json."
        ),
        no_args_is_help=True,
        context_settings={"help_option_names": ["-h", "--help"]},
    )

    def _version(value: bool) -> None:
        if value:
            print(f"pyaegean {aegean.__version__}")
            raise typer.Exit()

    @app.callback()
    def _root(
        version: bool = typer.Option(
            False, "--version", callback=_version, is_eager=True, help="Print the version and exit."
        ),
    ) -> None:
        """pyaegean — Ancient Greek + Aegean scripts, from the command line."""

    _corpus.register(app)
    _viz.register(app)
    _workbench.register(app)
    app.add_typer(greek_app, name="greek")
    app.add_typer(analyze_app, name="analyze")
    app.add_typer(data_app, name="data")
    app.add_typer(db_app, name="db")
    app.add_typer(ai_app, name="ai")
    return app
