"""``aegean browse`` — launch the local Greek visual corpus browser.

Serves a self-contained, zero-dependency local web interface backed directly by
PyAegean's Greek NLP, Biblical, lexicon, commentary, scansion, search, and library
engines. Works offline out of the box and upgrades seamlessly when optional hosted
corpora, lexica, or the neural pipeline are installed.
"""

from __future__ import annotations

import typer

from ._common import fail

__all__ = ["browse", "register"]


def register(app: typer.Typer) -> None:
    """Attach the ``browse`` command to the root CLI app."""
    app.command()(browse)


def browse(
    target: str = typer.Argument(
        "John 1:1-18",
        help=(
            "Initial Greek text to open: corpus id (greek, isicily, apostolic-fathers, …), "
            "NT/LXX reference ('John 1:1-18', 'Gen 1:1-5', 'MT Ps 23'), collection work "
            "(ogc002058), Patrologia Graeca volume (PG073), or local file path."
        ),
    ),
    port: int = typer.Option(8765, "--port", "-p", help="Local HTTP port to serve on."),
    auto_port: bool = typer.Option(
        True,
        "--auto-port/--no-auto-port",
        help="Automatically pick the next free port if --port is in use.",
    ),
    no_browser: bool = typer.Option(
        False,
        "--no-browser",
        help="Print the URL without opening a system browser window.",
    ),
    neural: bool = typer.Option(
        False,
        "--neural",
        help="Pre-activate the neural joint Greek pipeline (grc-joint-v3) on startup.",
    ),
    offline: bool = typer.Option(
        False,
        "--offline",
        help="Serve only from bundled/cached data without fetching missing corpora.",
    ),
    edition: str = typer.Option(
        "nestle1904",
        "--edition",
        "-e",
        help="Default Greek NT edition (nestle1904, sblgnt, srgnt, byzantine, tr, …).",
    ),
    doc: int = typer.Option(
        0,
        "--doc",
        "-d",
        help="Initial document index when opening a multi-document corpus.",
    ),
    host: str = typer.Option(
        "127.0.0.1",
        "--host",
        help="Loopback address to bind (127.0.0.1, localhost, or ::1).",
    ),
) -> None:
    """Launch the local interactive Greek visual corpus browser."""
    from ..browser import create_server

    try:
        server = create_server(
            target,
            doc_index=doc,
            edition=edition,
            port=port,
            auto_port=auto_port,
            host=host,
            neural=neural,
            offline=offline,
            open_browser=not no_browser,
        )
    except Exception as exc:
        raise fail(f"could not start Greek visual browser: {exc}") from exc

    typer.echo(f"PyAegean Greek Visual Corpus Browser serving at {server.url}")
    typer.echo(f"  Initial text: {target}  (Ctrl-C to stop)")
    try:
        server._thread.join()
    except KeyboardInterrupt:
        typer.echo("\nStopping Greek visual browser…")
    finally:
        server.stop()
