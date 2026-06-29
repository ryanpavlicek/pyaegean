"""``aegean workbench`` — fetch and serve the Linear A Research Workbench locally.

The workbench (the browser UI at linearaworkbench.xyz) is published as a small static-build
release asset; this command fetches it to the cache (sha256-pinned, ~3 MB, the established
fetch-to-cache pattern) and serves it on ``http://localhost:<port>/``. The Linear A facsimile
imagery is a separate ~116 MB asset: ``aegean workbench --fetch-images`` (or
``aegean data fetch lineara-images``) downloads it, after which it is mounted at
``/upstream/images/`` so the imagery browser works too. Without it the app runs fine (image-heavy
views just show no picture).
"""

from __future__ import annotations

import os
import posixpath
from pathlib import Path
from typing import Any

import typer


def register(app: typer.Typer) -> None:
    app.command()(workbench)


def _workbench_dir(*, force: bool = False) -> Path:
    """Fetch + extract the workbench static build to the cache; return its directory."""
    from ..data import fetch

    return fetch("workbench-app", force=force)


def _images_dir() -> Path | None:
    """The cached Linear A imagery directory, if the user has fetched it; else None."""
    from ..data import cache_dir

    base = cache_dir() / "lineara-images"
    # The asset unpacks to lineara-images/images/<file>, so serve from that inner
    # directory; fall back to the base for any flat layout.
    inner = base / "images"
    if inner.is_dir():
        return inner
    return base if base.is_dir() else None


def _prepare_images(*, fetch_images: bool) -> Path | None:
    """Optionally download the ~116 MB Linear A imagery asset, then return the cached images
    directory (or ``None`` if it was never fetched)."""
    if fetch_images:
        from ..data import fetch

        print("Fetching Linear A imagery (~116 MB, first time only)...")
        fetch("lineara-images")
    return _images_dir()


def _resolve_path(path: str, static_dir: Path, images_dir: Path | None) -> str | None:
    """Map a request path to a file under the imagery cache, or ``None`` to use the default
    static-build handling. Guards against directory traversal out of the imagery dir."""
    if images_dir is None:
        return None
    p = path.split("?", 1)[0].split("#", 1)[0]
    prefix = "/upstream/images/"
    if not p.startswith(prefix):
        return None
    rel = posixpath.normpath(p[len(prefix):]).lstrip("/")
    if rel.startswith("..") or os.path.isabs(rel):
        return None
    return os.path.join(str(images_dir), *rel.split("/"))


def _make_handler(static_dir: Path, images_dir: Path | None) -> Any:
    import http.server

    class _Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, directory=str(static_dir), **kwargs)

        def translate_path(self, path: str) -> str:
            mapped = _resolve_path(path, static_dir, images_dir)
            return mapped if mapped is not None else super().translate_path(path)

        def log_message(self, *args: Any) -> None:  # quiet: no per-request stderr spam
            pass

    return _Handler


def workbench(
    port: int = typer.Option(8000, "--port", "-p", help="Port to serve on."),
    no_browser: bool = typer.Option(False, "--no-browser", help="Don't open a web browser."),
    force: bool = typer.Option(False, "--force", help="Re-download the app build."),
    fetch_images: bool = typer.Option(
        False,
        "--fetch-images",
        help="Download the Linear A facsimile imagery (~116 MB, once) so the picture browser works.",
    ),
) -> None:
    """Serve the Linear A Research Workbench from a local web server.

    Fetches the sha256-pinned ``workbench-app`` build to the cache on first use, then serves it
    at ``http://localhost:<port>/`` until interrupted (Ctrl+C). The facsimile imagery is a
    separate ~116 MB asset: pass ``--fetch-images`` (or run ``aegean data fetch lineara-images``)
    to download it; once cached it is mounted at ``/upstream/images/`` so the picture browser works."""
    import socketserver
    import webbrowser

    from ._common import fail

    try:
        static_dir = _workbench_dir(force=force)
    except Exception as exc:  # network/checksum errors surface as one clean CLI line
        raise fail(f"could not fetch the workbench build: {exc}") from exc

    try:
        images_dir = _prepare_images(fetch_images=fetch_images)
    except Exception as exc:  # network/checksum errors surface as one clean CLI line
        raise fail(f"could not fetch the imagery: {exc}") from exc

    handler = _make_handler(static_dir, images_dir)
    url = f"http://localhost:{port}/"
    try:
        server = socketserver.ThreadingTCPServer(("127.0.0.1", port), handler)
    except OSError as exc:
        raise fail(f"could not bind port {port} ({exc}); try --port <n>") from exc
    with server:
        print(f"Serving the Linear A Research Workbench at {url}  (Ctrl+C to stop)")
        if images_dir is None:
            print("  facsimile images not cached — re-run with --fetch-images to show them.")
        if not no_browser:
            webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nstopped.")
