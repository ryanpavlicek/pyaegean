"""Resumable downloads: a mid-transfer network failure keeps the ``.part`` file
and later attempts continue it with an HTTP Range request, so one transient
stall no longer costs a whole multi-hundred-MB asset. Exercised end to end
through ``fetch()`` against a local in-process HTTP server (no external
network), following the PYAEGEAN_CACHE / DataSpec-registration pattern of
test_data.py. The payload is position-dependent (every offset has distinct
bytes), so any misassembly (wrong offset, appended garbage, mixed remotes)
fails the byte-for-byte comparison and the pinned sha256.
"""

from __future__ import annotations

import hashlib
import http.server
import json
import re
import socketserver
import threading

import pytest

from aegean import data
from aegean.data import DataNotAvailableError, DataSpec, fetch

PAYLOAD = bytes(range(256)) * 64  # 16 KiB
DROP_AFTER = 4096  # body bytes a "dropping" server sends before cutting the connection


@pytest.fixture(autouse=True)
def _isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("PYAEGEAN_CACHE", str(tmp_path / "cache"))


class _RangeServer(socketserver.ThreadingTCPServer):
    """Serves one payload at any path, honoring Range and If-Range, with
    switchable failure injection: cut the connection mid-body, ignore Range,
    or answer a fixed error status."""

    allow_reuse_address = True
    daemon_threads = True

    def __init__(self) -> None:
        super().__init__(("127.0.0.1", 0), _Handler)
        self.payload = PAYLOAD
        self.etag: str | None = None
        self.honor_range = True
        self.drops_remaining = 0  # how many requests get cut off mid-body
        self.always_status: int | None = None  # e.g. 404 for the HTTP-error test
        self.range_headers: list[str | None] = []  # the Range header of every request
        self.sent_statuses: list[int] = []

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.server_address[1]}/asset.bin"

    def handle_error(self, request, client_address):
        pass  # a client abandoning a stale 206 mid-flight is expected, not noise


class _Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def do_GET(self) -> None:
        srv = self.server
        assert isinstance(srv, _RangeServer)
        srv.range_headers.append(self.headers.get("Range"))
        if srv.always_status is not None:
            srv.sent_statuses.append(srv.always_status)
            self.send_response(srv.always_status)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        payload = srv.payload
        rng = self.headers.get("Range")
        if_range = self.headers.get("If-Range")
        start: int | None = None
        if rng is not None and srv.honor_range and (if_range is None or if_range == srv.etag):
            m = re.fullmatch(r"bytes=(\d+)-", rng.strip())
            if m:
                start = int(m.group(1))
        if start is not None and start >= len(payload):
            srv.sent_statuses.append(416)
            self.send_response(416)
            self.send_header("Content-Range", f"bytes */{len(payload)}")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if start is not None:
            status, body = 206, payload[start:]
        else:
            status, body = 200, payload
        srv.sent_statuses.append(status)
        self.send_response(status)
        if status == 206:
            self.send_header("Content-Range", f"bytes {start}-{len(payload) - 1}/{len(payload)}")
        if srv.etag is not None:
            self.send_header("ETag", srv.etag)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if srv.drops_remaining > 0:
            srv.drops_remaining -= 1
            self.wfile.write(body[:DROP_AFTER])
            self.wfile.flush()
            return  # the connection closes with the body short of Content-Length
        self.wfile.write(body)


@pytest.fixture()
def server():
    srv = _RangeServer()
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    yield srv
    srv.shutdown()
    srv.server_close()
    thread.join(timeout=10)


def _register(monkeypatch, url: str, payload: bytes = PAYLOAD) -> None:
    monkeypatch.setitem(
        data._REMOTE,
        "blob",
        DataSpec(
            name="blob", url=url, license="x", sha256=hashlib.sha256(payload).hexdigest()
        ),
    )


def test_drop_mid_body_is_resumed_within_one_fetch(server, monkeypatch):
    # (a) The observed real-world failure: the connection dies partway through.
    # A single fetch() call must recover by resuming, without the caller retrying.
    _register(monkeypatch, server.url)
    server.drops_remaining = 1
    p = fetch("blob")
    assert p.read_bytes() == PAYLOAD  # byte-exact assembly; the pinned sha256 also passed
    assert server.range_headers == [None, f"bytes={DROP_AFTER}-"]  # resumed, not restarted
    assert server.sent_statuses == [200, 206]
    assert not (data.cache_dir() / "blob.part").exists()
    assert not (data.cache_dir() / "blob.part.info").exists()  # resume sidecar cleaned up


def test_exhausted_retries_keep_the_part_and_a_later_fetch_resumes(server, monkeypatch):
    # (a) continued: when every in-call attempt fails, the progress survives the
    # raised error, and the caller's next fetch() picks the transfer back up.
    _register(monkeypatch, server.url)
    server.drops_remaining = 3  # all three in-call attempts get cut off
    with pytest.raises(DataNotAvailableError, match=r"could not fetch 'blob'.*resume"):
        fetch("blob")
    part = data.cache_dir() / "blob.part"
    assert part.read_bytes() == PAYLOAD[: 3 * DROP_AFTER]  # 3 attempts of progress, kept
    p = fetch("blob")  # the retry a caller would naturally make
    assert p.read_bytes() == PAYLOAD
    assert server.range_headers[-1] == f"bytes={3 * DROP_AFTER}-"  # continued from the .part
    assert not part.exists()


def test_server_ignoring_range_restarts_from_zero(server, monkeypatch):
    # (b) A server that answers a Range request with a plain 200 sends the whole
    # file; the .part must be rewritten from byte zero, never appended to.
    _register(monkeypatch, server.url)
    server.honor_range = False
    part = data.cache_dir() / "blob.part"
    part.write_bytes(b"\xff" * 5000)  # garbage: appending to it could never verify
    p = fetch("blob")
    assert p.read_bytes() == PAYLOAD
    assert server.range_headers == ["bytes=5000-"]  # a resume was attempted
    assert server.sent_statuses == [200]  # the server sent the full body instead


def test_stale_part_with_wrong_recorded_total_restarts(server, monkeypatch):
    # (c) The recorded total disagrees with the 206's Content-Range total (the
    # remote was republished at a different size): clean restart from zero.
    _register(monkeypatch, server.url)
    part = data.cache_dir() / "blob.part"
    part.write_bytes(b"\xff" * 5000)  # leftover bytes from the old remote
    data._part_info_path(part).write_text(
        json.dumps({"length": len(PAYLOAD) + 777, "etag": None, "last_modified": None}),
        encoding="utf-8",
    )
    p = fetch("blob")
    assert p.read_bytes() == PAYLOAD
    assert server.range_headers == ["bytes=5000-", None]  # 206 rejected, then full fetch
    assert server.sent_statuses == [206, 200]


def test_part_longer_than_the_remote_hits_416_and_restarts(server, monkeypatch):
    # (c) continued: a .part larger than the remote total is unsatisfiable (416
    # with "bytes */total"); the total does not match our offset, so restart.
    _register(monkeypatch, server.url)
    part = data.cache_dir() / "blob.part"
    part.write_bytes(PAYLOAD + b"overshoot")
    p = fetch("blob")
    assert p.read_bytes() == PAYLOAD
    assert server.sent_statuses == [416, 200]
    assert server.range_headers == [f"bytes={len(PAYLOAD) + 9}-", None]


def test_complete_part_is_finished_without_refetching_the_body(server, monkeypatch):
    # (c) continued: a 416 whose total equals the .part size means the download
    # already finished; verification and the rename proceed with no body refetch.
    _register(monkeypatch, server.url)
    part = data.cache_dir() / "blob.part"
    part.write_bytes(PAYLOAD)
    p = fetch("blob")
    assert p.read_bytes() == PAYLOAD
    assert server.sent_statuses == [416]  # the only request; no bytes re-downloaded
    assert server.range_headers == [f"bytes={len(PAYLOAD)}-"]


def test_changed_remote_is_detected_via_if_range(server, monkeypatch):
    # (c) continued, the hard case: the remote is republished with different
    # bytes but the SAME length, so no size check can catch it. The resume
    # carries If-Range with the recorded validator; the server answers 200 with
    # the full new body and the file is rebuilt from zero.
    server.etag = '"v1"'
    _register(monkeypatch, server.url)
    server.drops_remaining = 3
    with pytest.raises(DataNotAvailableError):
        fetch("blob")
    part = data.cache_dir() / "blob.part"
    info = json.loads(data._part_info_path(part).read_text(encoding="utf-8"))
    assert info["etag"] == '"v1"' and info["length"] == len(PAYLOAD)  # sidecar recorded

    new_payload = bytes(reversed(PAYLOAD))  # same length, different bytes
    server.payload = new_payload
    server.etag = '"v2"'
    _register(monkeypatch, server.url, payload=new_payload)
    p = fetch("blob")
    assert p.read_bytes() == new_payload
    assert server.range_headers[-1] == f"bytes={3 * DROP_AFTER}-"  # a resume was attempted
    assert server.sent_statuses[-1] == 200  # If-Range mismatch: full body, restart
    assert not part.exists()


def test_wrong_bytes_at_full_size_fail_verification_and_are_discarded(server, monkeypatch):
    # Corruption-class: a completed assembly that fails its sha256 is discarded
    # (never kept for resume), and the next fetch recovers with a clean download.
    _register(monkeypatch, server.url)
    part = data.cache_dir() / "blob.part"
    part.write_bytes(b"\xff" * len(PAYLOAD))  # right size, wrong bytes
    with pytest.raises(DataNotAvailableError, match="checksum mismatch"):
        fetch("blob")
    assert not part.exists()
    assert not data._part_info_path(part).exists()
    p = fetch("blob")
    assert p.read_bytes() == PAYLOAD


def test_http_error_discards_the_part(server, monkeypatch):
    # Corruption-class: an HTTP status error means the resource is wrong or
    # gone; the .part is removed and no in-call retries are burned on it.
    _register(monkeypatch, server.url)
    part = data.cache_dir() / "blob.part"
    part.write_bytes(PAYLOAD[:100])
    server.always_status = 404
    with pytest.raises(DataNotAvailableError, match="could not fetch"):
        fetch("blob")
    assert not part.exists()
    assert not data._part_info_path(part).exists()
    assert len(server.range_headers) == 1  # failed once, no pointless retries


def test_file_url_with_leftover_part_restarts_cleanly(tmp_path, monkeypatch):
    # (d) file:// URLs (the env-override / offline-test path) never use Range:
    # a leftover .part is simply overwritten by a full local copy.
    src = tmp_path / "src.bin"
    src.write_bytes(PAYLOAD)
    monkeypatch.setitem(data._REMOTE, "blob", DataSpec(name="blob", url="", license="x"))
    monkeypatch.setenv("PYAEGEAN_BLOB_URL", src.as_uri())
    part = data.cache_dir() / "blob.part"
    part.write_bytes(b"\xff" * 100)  # leftover from an interrupted transfer
    p = fetch("blob")
    assert p.read_bytes() == PAYLOAD  # restarted from zero: no garbage prefix survived
    assert not part.exists()
