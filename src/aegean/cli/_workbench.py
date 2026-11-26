"""``aegean workbench`` — fetch and serve the Linear A Research Workbench locally.

The workbench (the browser UI at linearaworkbench.xyz) is published as a small static-build
release asset; this command fetches it to the cache (sha256-pinned, ~3 MB, the established
fetch-to-cache pattern) and serves it on ``http://localhost:<port>/``.

Optional bridge capabilities:

- ``--fetch-images`` downloads the ~116 MB Linear A facsimile imagery asset and mounts it
  at ``/upstream/images/``.
- ``--corpus <id-or-path>`` loads any pyaegean corpus (by dataset id or local JSON file),
  serializes it with `to_workbench`, and serves it at ``/api/local/corpus.json``.
- ``--site`` / ``--period`` / ``--scribe`` / ``--support`` / ``--module`` / ``--doc`` open
  the browser straight to a scoped view, specific module, or inscription detail.
- ``--damos`` mounts the cached DAMOS Linear B corpus at ``/api/local/damos-corpus.json``
  so Sign Inventory's Linear A vs. Linear B frequency divergence loads automatically.
- ``--state <workspace.json>`` enables bidirectional loopback persistence at
  ``/api/local/backup``: annotations, notes, collections, findings, and hypotheses hydrate
  on launch and auto-save back to the local file (compatible with `load_workbench_backup`).
- ``--dir <path>`` serves a local workbench ``dist/`` build instead of fetching the release.
"""

from __future__ import annotations

import json
import os
import posixpath
import urllib.parse
from pathlib import Path
from typing import Any

import typer

_MAX_BACKUP_BYTES = 25 * 1024 * 1024  # 25 MiB guard for PUT /api/local/backup
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


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


def _damos_file(*, fetch_if_missing: bool = False) -> Path | None:
    """Return the cached ``damos-corpus.json`` path, optionally fetching it first."""
    from ..data import cache_dir, fetch

    candidate = cache_dir() / "damos-corpus.json"
    if candidate.is_file():
        return candidate
    if fetch_if_missing:
        print("Fetching DAMOS Linear B corpus (~3 MB, first time only)...")
        return fetch("damos")
    return None


def _load_corpus_bytes(corpus_arg: str) -> bytes:
    """Load a pyaegean corpus id or local JSON file and serialize to workbench JSON bytes."""
    from .. import load
    from ..io.workbench import from_workbench_export, to_workbench

    path = Path(corpus_arg)
    if path.is_file():
        raw_text = path.read_text(encoding="utf-8-sig")
        parsed = json.loads(raw_text)
        # Accept either a workbench array/schema-v1 export directly or a pyaegean Corpus JSON.
        if isinstance(parsed, list) or (
            isinstance(parsed, dict) and "inscriptions" in parsed
        ):
            corpus = from_workbench_export(parsed)
        else:
            from ..core.corpus import Corpus

            corpus = Corpus.from_json(path)
    else:
        corpus = load(corpus_arg)
    records = to_workbench(corpus)
    return json.dumps(records, ensure_ascii=False).encode("utf-8")


def _build_launch_url(
    port: int,
    *,
    has_corpus: bool = False,
    has_damos: bool = False,
    has_state: bool = False,
    module: str | None = None,
    doc: str | None = None,
    site: str | None = None,
    period: str | None = None,
    scribe: str | None = None,
    support: str | None = None,
) -> str:
    """Build the local launch URL with query parameters and hash permalink."""
    query: list[tuple[str, str]] = []
    if has_corpus:
        query.append(("corpus", "/api/local/corpus.json"))
    if has_damos:
        query.append(("damos", "/api/local/damos-corpus.json"))
    if has_state:
        query.append(("localState", "1"))
    qs = f"?{urllib.parse.urlencode(query)}" if query else ""

    scope: list[tuple[str, str]] = []
    if doc and module:
        scope.append(("m", module))
    for key, val in (
        ("site", site),
        ("period", period),
        ("scribe", scribe),
        ("support", support),
    ):
        if val:
            scope.append((key, val))

    hash_part = ""
    if doc:
        frag_qs = f"?{urllib.parse.urlencode(scope)}" if scope else ""
        hash_part = f"#/i/{urllib.parse.quote(doc, safe='')}{frag_qs}"
    elif module or scope:
        target_mod = module or "home"
        frag_qs = f"?{urllib.parse.urlencode(scope)}" if scope else ""
        hash_part = f"#/m/{urllib.parse.quote(target_mod, safe='')}{frag_qs}"

    return f"http://localhost:{port}/{qs}{hash_part}"


def _is_loopback_origin(origin: str | None) -> bool:
    """Return True if ``Origin`` is absent (non-CORS same-origin/curl) or a loopback origin."""
    if not origin:
        return True
    try:
        parsed = urllib.parse.urlparse(origin)
    except ValueError:
        return False
    return parsed.scheme in ("http", "https") and (parsed.hostname or "").lower() in _LOOPBACK_HOSTS


def _resolve_path(path: str, static_dir: Path, images_dir: Path | None) -> str | None:
    """Map a request path to a file under the imagery cache, or ``None`` to use the default
    static-build handling. Guards against directory traversal out of the imagery dir: the
    request is percent-decoded (matching the static handler), backslashes count as
    separators (they are on Windows), absolute and drive-letter forms are refused, and the
    mapped file must resolve inside the imagery dir."""
    if images_dir is None:
        return None
    p = path.split("?", 1)[0].split("#", 1)[0]
    prefix = "/upstream/images/"
    if not p.startswith(prefix):
        return None
    # Percent-decode like SimpleHTTPRequestHandler.translate_path does, then fold
    # backslashes into forward slashes so a ..\ payload can't sidestep the guard. An
    # invalid-UTF-8 percent byte (e.g. %FF) must not crash the handler: fall back to
    # errors="replace" (CPython's translate_path default) so it resolves to a clean 404.
    encoded = p[len(prefix):]
    try:
        rel = urllib.parse.unquote(encoded, errors="surrogatepass").replace("\\", "/")
    except UnicodeDecodeError:
        rel = urllib.parse.unquote(encoded, errors="replace").replace("\\", "/")
    if rel.startswith("/") or ":" in rel:  # absolute, UNC, or drive-letter form
        return None
    rel = posixpath.normpath(rel)
    if rel.startswith(".."):
        return None
    mapped = os.path.join(str(images_dir), *rel.split("/"))
    # The authoritative check: the real (symlink-resolved) target must stay inside the
    # imagery dir, whatever the request looked like.
    try:
        if not Path(mapped).resolve().is_relative_to(images_dir.resolve()):
            return None
    except (OSError, ValueError):  # unresolvable path (e.g. an embedded NUL)
        return None
    return mapped


def _make_handler(
    static_dir: Path,
    images_dir: Path | None,
    *,
    corpus_bytes: bytes | None = None,
    damos_path: Path | None = None,
    state_path: Path | None = None,
) -> Any:
    import http.server

    from ..io.workbench import load_workbench_backup, save_workbench_backup

    class _Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, directory=str(static_dir), **kwargs)

        def translate_path(self, path: str) -> str:
            mapped = _resolve_path(path, static_dir, images_dir)
            return mapped if mapped is not None else super().translate_path(path)

        def _send_bytes(
            self,
            status: int,
            payload: bytes,
            content_type: str = "application/json; charset=utf-8",
        ) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            if payload:
                self.wfile.write(payload)

        def do_GET(self) -> None:  # noqa: N802
            route = self.path.split("?", 1)[0]
            if route == "/api/local/corpus.json":
                if corpus_bytes is None:
                    self._send_bytes(404, b'{"error":"no custom corpus mounted"}')
                else:
                    self._send_bytes(200, corpus_bytes)
                return
            if route == "/api/local/damos-corpus.json":
                if damos_path is None or not damos_path.is_file():
                    self._send_bytes(404, b'{"error":"DAMOS corpus not mounted"}')
                else:
                    self._send_bytes(200, damos_path.read_bytes())
                return
            if route == "/api/local/backup":
                if state_path is None:
                    self._send_bytes(404, b'{"error":"local state not enabled"}')
                elif not state_path.is_file():
                    self.send_response(204)
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                else:
                    try:
                        data = state_path.read_bytes()
                    except OSError:
                        self._send_bytes(500, b'{"error":"could not read state file"}')
                    else:
                        self._send_bytes(200, data)
                return
            super().do_GET()

        def do_PUT(self) -> None:  # noqa: N802
            route = self.path.split("?", 1)[0]
            if route != "/api/local/backup" or state_path is None:
                self._send_bytes(404, b'{"error":"endpoint not enabled"}')
                return
            if not _is_loopback_origin(self.headers.get("Origin")):
                self._send_bytes(403, b'{"error":"forbidden origin"}')
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                self._send_bytes(400, b'{"error":"invalid Content-Length"}')
                return
            if length <= 0 or length > _MAX_BACKUP_BYTES:
                self._send_bytes(413, b'{"error":"payload too large or empty"}')
                return
            raw = self.rfile.read(length)
            try:
                parsed = json.loads(raw.decode("utf-8"))
                backup = load_workbench_backup(parsed)
                save_workbench_backup(backup, state_path)
            except (UnicodeDecodeError, ValueError) as exc:
                msg = json.dumps({"error": str(exc)}).encode("utf-8")
                self._send_bytes(400, msg)
                return
            except OSError as exc:
                msg = json.dumps({"error": str(exc)}).encode("utf-8")
                self._send_bytes(500, msg)
                return
            self._send_bytes(200, b'{"ok":true}')

        def log_message(self, *args: Any) -> None:  # quiet: no per-request stderr spam
            pass

    return _Handler


def workbench(
    port: int = typer.Option(
        8000,
        "--port",
        "-p",
        help="Port to serve on (1-65535).",
    ),
    auto_port: bool = typer.Option(
        False,
        "--auto-port",
        help="Let the OS pick any available loopback port (ignores --port).",
    ),
    no_browser: bool = typer.Option(False, "--no-browser", help="Don't open a web browser."),
    force: bool = typer.Option(False, "--force", help="Re-download the app build."),
    fetch_images: bool = typer.Option(
        False,
        "--fetch-images",
        help="Download the Linear A facsimile imagery (~116 MB, once) so the picture browser works.",
    ),
    corpus: str | None = typer.Option(
        None,
        "--corpus",
        help="Mount a pyaegean corpus id (e.g. 'damos', 'cypro-minoan') or local JSON export.",
    ),
    site: str | None = typer.Option(None, "--site", help="Open pre-scoped to a find-site."),
    period: str | None = typer.Option(None, "--period", help="Open pre-scoped to a dating period."),
    scribe: str | None = typer.Option(None, "--scribe", help="Open pre-scoped to a scribal hand."),
    support: str | None = typer.Option(None, "--support", help="Open pre-scoped to a support type."),
    module: str | None = typer.Option(
        None, "--module", "-m", help="Open directly to a workbench module id (e.g. 'arith', 'signref')."
    ),
    doc: str | None = typer.Option(
        None, "--doc", help="Open directly to an inscription detail view (e.g. 'HT13')."
    ),
    damos: bool = typer.Option(
        False,
        "--damos",
        help="Mount cached DAMOS Linear B corpus (fetches if missing) for automatic Linear A/B comparison.",
    ),
    state: Path | None = typer.Option(
        None,
        "--state",
        help="Auto-load and persist workbench backup JSON (annotations, notes, collections) to this file.",
    ),
    app_dir: Path | None = typer.Option(
        None,
        "--dir",
        help="Serve a local linearaworkbench build directory (e.g. ./dist) instead of the cached release.",
    ),
) -> None:
    """Serve the Linear A Research Workbench from a local web server.

    Fetches the sha256-pinned ``workbench-app`` build to the cache on first use, then serves it
    at ``http://localhost:<port>/`` until interrupted (Ctrl+C). Use ``--corpus``, ``--site``,
    ``--module``, ``--doc``, ``--damos``, and ``--state`` to bridge Python corpora and local
    workspace files directly into the browser UI."""
    import socketserver
    import webbrowser

    from ._common import fail

    if not auto_port and not 1 <= port <= 65535:
        raise fail(f"--port must be between 1 and 65535, got {port}")
    bind_port = 0 if auto_port else port

    if app_dir is not None:
        static_dir = app_dir.expanduser().resolve()
        if not (static_dir / "index.html").is_file():
            raise fail(f"--dir must contain an index.html build: {static_dir}")
    else:
        try:
            static_dir = _workbench_dir(force=force)
        except Exception as exc:  # network/checksum errors surface as one clean CLI line
            raise fail(f"could not fetch the workbench build: {exc}") from exc

    try:
        images_dir = _prepare_images(fetch_images=fetch_images)
    except Exception as exc:  # network/checksum errors surface as one clean CLI line
        raise fail(f"could not fetch the imagery: {exc}") from exc

    corpus_bytes: bytes | None = None
    if corpus is not None:
        try:
            corpus_bytes = _load_corpus_bytes(corpus)
        except Exception as exc:
            raise fail(f"could not load --corpus {corpus!r}: {exc}") from exc

    damos_path: Path | None = None
    if damos:
        try:
            damos_path = _damos_file(fetch_if_missing=True)
        except Exception as exc:
            raise fail(f"could not fetch DAMOS corpus: {exc}") from exc

    state_path: Path | None = state.expanduser().resolve() if state is not None else None

    handler = _make_handler(
        static_dir,
        images_dir,
        corpus_bytes=corpus_bytes,
        damos_path=damos_path,
        state_path=state_path,
    )
    try:
        server = socketserver.ThreadingTCPServer(("127.0.0.1", bind_port), handler)
        # Ctrl+C must stop the server even when a client holds an in-flight request it
        # has stopped reading (a handler blocked in sendall would otherwise be joined
        # forever by server_close): handler threads are daemons, shutdown never waits.
        server.daemon_threads = True
    except OSError as exc:
        raise fail(f"could not bind port {bind_port} ({exc}); try --port <n> or --auto-port") from exc

    actual_port = int(server.server_address[1])
    url = _build_launch_url(
        actual_port,
        has_corpus=corpus_bytes is not None,
        has_damos=damos_path is not None,
        has_state=state_path is not None,
        module=module,
        doc=doc,
        site=site,
        period=period,
        scribe=scribe,
        support=support,
    )
    with server:
        print(f"Serving the Linear A Research Workbench at {url}  (Ctrl+C to stop)")
        if images_dir is None:
            print("  facsimile images not cached — re-run with --fetch-images to show them.")
        if corpus is not None:
            print(f"  custom corpus mounted: {corpus}")
        if damos_path is not None:
            print("  DAMOS Linear B corpus mounted at /api/local/damos-corpus.json")
        if state_path is not None:
            print(f"  workspace state file: {state_path}")
        if not no_browser:
            webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nstopped.")
