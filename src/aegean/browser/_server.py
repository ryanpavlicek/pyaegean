"""Stdlib loopback HTTP server for the local PyAegean Greek visual corpus browser."""

from __future__ import annotations

import http.server
import json
import socket
import threading
import urllib.parse
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import _service

__all__ = ["BrowserServer", "create_server", "serve"]

_LOOPBACK_HOSTS: frozenset[str] = frozenset({"localhost", "127.0.0.1", "::1"})
_STATIC_DIR = Path(__file__).resolve().parent / "static"
_STATIC_FILES: dict[str, tuple[str, str]] = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "application/javascript; charset=utf-8"),
}
_MAX_POST_BYTES = 2 * 1024 * 1024


def _is_loopback_origin(origin: str | None) -> bool:
    """Return True if ``Origin`` is absent (same-origin/CLI) or a loopback origin."""
    if not origin:
        return True
    try:
        parsed = urllib.parse.urlparse(origin)
    except ValueError:
        return False
    return parsed.scheme in ("http", "https") and (parsed.hostname or "").lower() in _LOOPBACK_HOSTS


def _pick_port(host: str, port: int, *, auto_port: bool) -> int:
    """Return ``port`` if bindable, or the next free loopback port when ``auto_port=True``."""
    if port == 0:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((host, 0))
            return int(s.getsockname()[1])
    candidates = [port] + (list(range(port + 1, port + 40)) if auto_port else [])
    last_err: OSError | None = None
    for cand in candidates:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind((host, cand))
                return cand
            except OSError as exc:
                last_err = exc
    raise OSError(f"no free loopback port starting at {port}: {last_err}")


@dataclass
class BrowserServer:
    """Handle for a running local Greek Visual Corpus Browser HTTP server."""

    host: str
    port: int
    url: str
    _httpd: http.server.ThreadingHTTPServer
    _thread: threading.Thread

    def stop(self) -> None:
        """Shut down the HTTP server and join its background thread."""
        try:
            self._httpd.shutdown()
        finally:
            self._httpd.server_close()
            if self._thread.is_alive() and threading.current_thread() is not self._thread:
                self._thread.join(timeout=3.0)

    def __enter__(self) -> BrowserServer:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.stop()


def _make_handler(
    *,
    initial_target: str,
    initial_doc_index: int,
    initial_edition: str,
    offline: bool,
) -> type[http.server.BaseHTTPRequestHandler]:
    class _Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:  # noqa: A002
            # Stay silent by default so CLI / TUI / notebook output stays clean.
            return

        def _send_bytes(
            self,
            status: int,
            payload: bytes,
            content_type: str = "application/json; charset=utf-8",
            extra_headers: dict[str, str] | None = None,
        ) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            if extra_headers:
                for k, v in extra_headers.items():
                    self.send_header(k, v)
            self.end_headers()
            if payload:
                self.wfile.write(payload)

        def _send_json(self, status: int, data: Any) -> None:
            raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self._send_bytes(status, raw, "application/json; charset=utf-8")

        def _send_error_json(self, status: int, message: str, *, kind: str = "Error") -> None:
            self._send_json(status, {"error": message, "type": kind})

        def _read_json_body(self) -> dict[str, Any]:
            raw_len = self.headers.get("Content-Length", "0")
            try:
                length = int(raw_len)
            except ValueError as exc:
                raise ValueError("invalid Content-Length header") from exc
            if length < 0 or length > _MAX_POST_BYTES:
                raise OverflowError(f"request body exceeds {_MAX_POST_BYTES} bytes")
            raw = self.rfile.read(length) if length > 0 else b"{}"
            parsed = json.loads(raw.decode("utf-8"))
            if not isinstance(parsed, dict):
                raise ValueError("JSON request body must be an object")
            return parsed

        def _qs_first(self, qs: dict[str, list[str]], key: str, default: str = "") -> str:
            vals = qs.get(key)
            return vals[0] if vals else default

        def _qs_int(self, qs: dict[str, list[str]], key: str, default: int) -> int:
            raw = self._qs_first(qs, key, "")
            if not raw:
                return default
            return int(raw)

        def _qs_bool(self, qs: dict[str, list[str]], key: str, default: bool) -> bool:
            raw = self._qs_first(qs, key, "").strip().lower()
            if not raw:
                return default
            return raw in ("1", "true", "yes", "on")

        def do_GET(self) -> None:  # noqa: N802
            parsed = urllib.parse.urlparse(self.path)
            route = parsed.path
            qs = urllib.parse.parse_qs(parsed.query, keep_blank_values=False)

            if route in _STATIC_FILES:
                fname, ctype = _STATIC_FILES[route]
                fpath = _STATIC_DIR / fname
                if not fpath.is_file():
                    self._send_error_json(404, f"static asset {fname!r} missing")
                    return
                self._send_bytes(200, fpath.read_bytes(), ctype)
                return

            try:
                if route == "/api/health":
                    import aegean

                    self._send_json(200, {"ok": True, "version": aegean.__version__})
                    return

                if route == "/api/config":
                    self._send_json(
                        200,
                        {
                            "initial_target": initial_target,
                            "initial_doc_index": initial_doc_index,
                            "initial_edition": initial_edition,
                            "offline": offline,
                        },
                    )
                    return

                if route == "/api/catalog":
                    self._send_json(200, _service.catalog_payload())
                    return

                if route == "/api/collections":
                    self._send_json(
                        200,
                        _service.collections_payload(
                            collection=self._qs_first(qs, "collection") or None,
                            query=self._qs_first(qs, "q") or None,
                            period=self._qs_first(qs, "period") or None,
                            limit=self._qs_int(qs, "limit", 60),
                            offset=self._qs_int(qs, "offset", 0),
                        ),
                    )
                    return

                if route == "/api/open":
                    target = self._qs_first(qs, "target", initial_target)
                    self._send_json(
                        200,
                        _service.document_payload(
                            target,
                            doc_index=self._qs_int(qs, "doc", 0),
                            ref=self._qs_first(qs, "ref") or None,
                            edition=self._qs_first(qs, "edition", initial_edition),
                            numbering=self._qs_first(qs, "numbering", "lxx"),
                            max_tokens=self._qs_int(qs, "limit", 500),
                            offset=self._qs_int(qs, "offset", 0),
                            offline=self._qs_bool(qs, "offline", offline),
                        ),
                    )
                    return

                if route == "/api/word":
                    self._send_json(
                        200,
                        _service.analyze_word_payload(
                            self._qs_first(qs, "surface"),
                            lemma=self._qs_first(qs, "lemma") or None,
                            upos=self._qs_first(qs, "upos") or None,
                            xpos=self._qs_first(qs, "xpos") or None,
                            feats=self._qs_first(qs, "feats") or None,
                            robinson=self._qs_first(qs, "robinson") or None,
                            strongs=self._qs_first(qs, "strongs") or None,
                            sentence_text=self._qs_first(qs, "sentence") or None,
                            book=self._qs_first(qs, "book") or None,
                        ),
                    )
                    return

                if route == "/api/search":
                    self._send_json(
                        200,
                        _service.search_payload(
                            self._qs_first(qs, "q"),
                            target=self._qs_first(qs, "target", "bible"),
                            limit=self._qs_int(qs, "limit", 30),
                            offline=self._qs_bool(qs, "offline", True),
                        ),
                    )
                    return

                if route == "/api/word-study":
                    self._send_json(
                        200,
                        _service.word_study_payload(
                            self._qs_first(qs, "q"),
                            offline=self._qs_bool(qs, "offline", True),
                        ),
                    )
                    return

                if route == "/api/bible/editions":
                    self._send_json(
                        200,
                        _service.bible_editions_payload(
                            self._qs_first(qs, "book", "John"),
                            self._qs_first(qs, "ref", "1.1-5"),
                            offline=self._qs_bool(qs, "offline", offline),
                        ),
                    )
                    return

                if route == "/api/bible/witnesses":
                    self._send_json(
                        200,
                        _service.bible_witnesses_payload(
                            self._qs_first(qs, "book", "John"),
                            self._qs_first(qs, "ref", "1.1-5"),
                            offline=self._qs_bool(qs, "offline", offline),
                        ),
                    )
                    return

                if route == "/api/bible/commentaries":
                    self._send_json(
                        200,
                        _service.bible_commentaries_payload(
                            book=self._qs_first(qs, "book") or None,
                            kind=self._qs_first(qs, "kind") or None,
                        ),
                    )
                    return

                if route == "/api/bible/commentary-excerpt":
                    self._send_json(
                        200,
                        _service.bible_commentary_excerpt_payload(
                            self._qs_first(qs, "book", "John"),
                            work_id=self._qs_first(qs, "work_id") or None,
                            query=self._qs_first(qs, "q") or None,
                            ref=self._qs_first(qs, "ref") or None,
                            limit=self._qs_int(qs, "limit", 5),
                        ),
                    )
                    return

                if route == "/api/bible/psalm":
                    self._send_json(
                        200,
                        _service.bible_psalm_payload(
                            self._qs_int(qs, "number", 23),
                            direction=self._qs_first(qs, "direction", "mt_to_lxx"),
                        ),
                    )
                    return

                if route == "/api/engine":
                    self._send_json(200, _service.engine_status_payload())
                    return

                if route == "/api/library":
                    self._send_json(200, _service.library_payload())
                    return

                self._send_error_json(404, f"unknown route: {route}")
            except (ValueError, KeyError) as exc:
                self._send_error_json(400, str(exc), kind=type(exc).__name__)
            except Exception as exc:
                self._send_error_json(500, str(exc), kind=type(exc).__name__)

        def do_POST(self) -> None:  # noqa: N802
            if not _is_loopback_origin(self.headers.get("Origin")):
                self._send_error_json(403, "cross-origin POST requests are forbidden on the loopback server")
                return

            route = urllib.parse.urlparse(self.path).path
            try:
                body = self._read_json_body()
            except OverflowError as exc:
                self._send_error_json(413, str(exc), kind="PayloadTooLarge")
                return
            except (ValueError, json.JSONDecodeError) as exc:
                self._send_error_json(400, str(exc), kind=type(exc).__name__)
                return

            try:
                if route == "/api/analyze-text":
                    self._send_json(
                        200,
                        _service.analyze_text_payload(
                            str(body.get("text") or ""),
                            betacode=bool(body.get("betacode", False)),
                            translation=str(body.get("translation") or "") or None,
                            title=str(body.get("title") or "Custom Greek Passage"),
                        ),
                    )
                    return

                if route == "/api/scan":
                    raw_lines = body.get("lines")
                    if isinstance(raw_lines, str):
                        lines = raw_lines.splitlines()
                    elif isinstance(raw_lines, list):
                        lines = [str(x) for x in raw_lines]
                    else:
                        lines = []
                    self._send_json(
                        200,
                        _service.scan_lines_payload(
                            lines,
                            meter=str(body.get("meter") or "hexameter"),
                        ),
                    )
                    return

                if route == "/api/engine":
                    self._send_json(200, _service.configure_engine_payload(body))
                    return

                if route == "/api/lexicon/activate":
                    self._send_json(200, _service.activate_lexicon_payload(str(body.get("id") or "")))
                    return

                if route == "/api/library/fetch":
                    self._send_json(200, _service.library_fetch_payload(str(body.get("dataset") or "")))
                    return

                if route == "/api/export":
                    content, ctype, filename = _service.export_payload(
                        fmt=str(body.get("format") or "json"),
                        title=str(body.get("title") or "passage"),
                        sentences=list(body.get("sentences") or []),
                        blocks=list(body.get("blocks") or []),
                    )
                    self._send_bytes(
                        200,
                        content.encode("utf-8"),
                        ctype,
                        extra_headers={"Content-Disposition": f'attachment; filename="{filename}"'},
                    )
                    return

                self._send_error_json(404, f"unknown route: {route}")
            except (ValueError, KeyError) as exc:
                self._send_error_json(400, str(exc), kind=type(exc).__name__)
            except Exception as exc:
                self._send_error_json(500, str(exc), kind=type(exc).__name__)

    return _Handler


def create_server(
    target: str | None = None,
    *,
    doc_index: int = 0,
    edition: str = "nestle1904",
    port: int = 8765,
    auto_port: bool = True,
    host: str = "127.0.0.1",
    neural: bool = False,
    offline: bool = False,
    open_browser: bool = False,
) -> BrowserServer:
    """Start the local Greek visual corpus browser in a background thread and return its handle."""
    if host.lower() not in _LOOPBACK_HOSTS:
        raise ValueError(
            f"Greek visual browser binds strictly to loopback ({', '.join(sorted(_LOOPBACK_HOSTS))}), got {host!r}"
        )
    if neural:
        from ..greek import use_neural_pipeline

        use_neural_pipeline()

    chosen_port = _pick_port(host, port, auto_port=auto_port)
    handler_cls = _make_handler(
        initial_target=(target or "John 1:1-18").strip(),
        initial_doc_index=max(0, int(doc_index)),
        initial_edition=(edition or "nestle1904").strip(),
        offline=bool(offline),
    )
    httpd = http.server.ThreadingHTTPServer((host, chosen_port), handler_cls)
    httpd.daemon_threads = True
    actual_port = int(httpd.server_address[1])
    url = f"http://localhost:{actual_port}/"

    thread = threading.Thread(target=httpd.serve_forever, name="aegean-browser-http", daemon=True)
    thread.start()

    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass

    return BrowserServer(
        host=host,
        port=actual_port,
        url=url,
        _httpd=httpd,
        _thread=thread,
    )


def serve(
    target: str | None = None,
    *,
    doc_index: int = 0,
    edition: str = "nestle1904",
    port: int = 8765,
    auto_port: bool = True,
    host: str = "127.0.0.1",
    neural: bool = False,
    offline: bool = False,
    open_browser: bool = True,
    background: bool = False,
) -> BrowserServer | None:
    """Launch the local Greek visual corpus browser.

    By default, starts the server, opens the URL in your system browser, and blocks until
    ``Ctrl-C`` (mirroring ``aegean workbench``). Pass ``background=True`` to return a
    :class:`BrowserServer` handle immediately (useful in scripts, notebooks, and tests).
    """
    server = create_server(
        target,
        doc_index=doc_index,
        edition=edition,
        port=port,
        auto_port=auto_port,
        host=host,
        neural=neural,
        offline=offline,
        open_browser=open_browser,
    )
    if background:
        return server
    try:
        server._thread.join()
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()
    return None
