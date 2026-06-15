"""``aegean workbench`` — fetch and serve the Linear A Research Workbench locally.

The workbench (the browser UI at linearaworkbench.xyz) is published as a small static-build
release asset; this command fetches it to the cache (sha256-pinned, ~3 MB, the established
fetch-to-cache pattern) and serves it on ``http://localhost:<port>/``. If the Linear A
facsimile imagery has already been fetched (``aegean.data.fetch("lineara-images")``), it is
mounted at ``/upstream/images/`` so the imagery browser works too; otherwise the app runs
fine without it (image-heavy views just show no picture).
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

    d = cache_dir() / "lineara-images"
    return d if d.is_dir() else None


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
) -> None:
    """Serve the Linear A Research Workbench from a local web server.

    Fetches the sha256-pinned ``workbench-app`` build to the cache on first use, then serves
    it at ``http://localhost:<port>/`` until interrupted (Ctrl+C). Cached Linear A imagery,
    if present, is mounted so the picture browser works."""
    import socketserver
    import webbrowser

    from ._common import fail

    try:
        static_dir = _workbench_dir(force=force)
    except Exception as exc:  # network/checksum errors surface as one clean CLI line
        raise fail(f"could not fetch the workbench build: {exc}") from exc

    handler = _make_handler(static_dir, _images_dir())
    url = f"http://localhost:{port}/"
    try:
        server = socketserver.ThreadingTCPServer(("127.0.0.1", port), handler)
    except OSError as exc:
        raise fail(f"could not bind port {port} ({exc}); try --port <n>") from exc
    with server:
        print(f"Serving the Linear A Research Workbench at {url}  (Ctrl+C to stop)")
        if not no_browser:
            webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nstopped.")
