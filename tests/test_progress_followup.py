"""Progress hooks on the two remaining silent long operations: token-level tabular
exports (`io.to_csv` / `io.to_parquet`, ~140 s at DDbDP scale) and `data.fetch`
(a ~206 MB download + archive extraction).

Three dimensions per hook (the 0.32.0 rule):
  * correctness — the ``progress(done, total)`` sequence is exact (per-DOCUMENT for the
    exports; absolute BYTES for a download, per-MEMBER for extraction), ending at
    ``(total, total)``;
  * byte-identity — the ``progress=None`` default and the progress path produce
    byte-identical output, proven with ``read_bytes`` on a fixture;
  * adversarial — a raising progress callback aborts loudly and leaves no corruption
    (the prior export intact; the download's resumable ``.part`` kept so the next fetch
    continues); plus the empty-input and unknown-Content-Length edges.

The fetch tests run end-to-end against a local in-process HTTP server (no network),
following test_data_resume.py's pattern.
"""

from __future__ import annotations

import hashlib
import http.server
import io
import re
import socket
import socketserver
import tarfile
import threading
from pathlib import Path

import pytest

from aegean import data
from aegean.core.corpus import Corpus
from aegean.core.model import Document, DocumentMeta, ReadingStatus, Token, TokenKind
from aegean.core.provenance import Provenance
from aegean.data import DataNotAvailableError, DataSpec, fetch
from aegean.io import to_csv, to_parquet

# ══════════════════════════════════════════════════════════════════════════════
# Tabular exports (io/tabular.py): progress counts DOCUMENTS through row generation
# ══════════════════════════════════════════════════════════════════════════════


def _corpus(n_docs: int) -> Corpus:
    """A small Greek corpus: each document has a WORD token (with a ``lemma``
    annotation, so the token-level ``**annotations`` spread is exercised) and a
    NUMERAL token, so token-level rows outnumber documents."""
    docs = []
    for i in range(n_docs):
        toks = [
            Token(f"λόγος{i}", TokenKind.WORD, line_no=0, position=0,
                  annotations={"lemma": "λόγος"}),
            Token("5", TokenKind.NUMERAL, ("5",), line_no=0, position=1,
                  status=ReadingStatus.UNCLEAR),
        ]
        docs.append(
            Document(id=f"D{i}", script_id="greek", tokens=toks, lines=[[0, 1]],
                     meta=DocumentMeta(site="Testville", period="LM I"))
        )
    prov = Provenance(source="Synthetic", license="CC0", citation="Synthetic (2026).")
    return Corpus(docs, provenance=prov, script_id="greek")


@pytest.mark.parametrize("level", ["document", "token", "word"])
def test_to_csv_progress_counts_documents_and_is_byte_identical(tmp_path: Path, level: str) -> None:
    c = _corpus(5)
    calls: list[tuple[int, int]] = []
    to_csv(c, tmp_path / "with.csv", level=level, progress=lambda d, t: calls.append((d, t)))
    to_csv(c, tmp_path / "without.csv", level=level)  # the default byte-identical path
    # per DOCUMENT (not per token/word), in order, ending at (total, total)
    assert calls == [(1, 5), (2, 5), (3, 5), (4, 5), (5, 5)]
    assert calls[-1] == (5, 5)
    # byte-identity proof: the hook never changes the CSV
    assert (tmp_path / "with.csv").read_bytes() == (tmp_path / "without.csv").read_bytes()


@pytest.mark.parametrize("level", ["document", "token"])
def test_to_parquet_progress_counts_documents_and_is_byte_identical(
    tmp_path: Path, level: str
) -> None:
    pytest.importorskip("pyarrow")
    c = _corpus(4)
    calls: list[tuple[int, int]] = []
    to_parquet(c, tmp_path / "with.parquet", level=level,
               progress=lambda d, t: calls.append((d, t)))
    to_parquet(c, tmp_path / "without.parquet", level=level)
    assert calls == [(1, 4), (2, 4), (3, 4), (4, 4)]  # per document, final (total, total)
    # Parquet buffers the whole frame before its single write, so the final progress
    # call lands before the write; byte-identity still holds (pyarrow is deterministic).
    assert (tmp_path / "with.parquet").read_bytes() == (tmp_path / "without.parquet").read_bytes()


def test_tabular_empty_corpus_makes_no_calls_and_stays_identical(tmp_path: Path) -> None:
    calls: list[tuple[int, int]] = []
    to_csv(_corpus(0), tmp_path / "with.csv", level="token",
           progress=lambda d, t: calls.append((d, t)))
    to_csv(_corpus(0), tmp_path / "without.csv", level="token")
    assert calls == []  # nothing to report on an empty corpus
    assert (tmp_path / "with.csv").read_bytes() == (tmp_path / "without.csv").read_bytes()


def test_to_csv_raising_progress_aborts_loudly_keeping_prior_export(tmp_path: Path) -> None:
    out = tmp_path / "export.csv"
    to_csv(_corpus(2), out)  # a good prior export
    before = out.read_bytes()

    def boom(done: int, total: int) -> None:
        raise RuntimeError("observer failed")

    with pytest.raises(RuntimeError, match="observer failed"):
        to_csv(_corpus(4), out, level="token", progress=boom)
    assert out.read_bytes() == before  # the prior export is untouched (row gen precedes the write)
    assert not list(tmp_path.glob("*.tmp"))  # and no atomic-write debris


def test_to_parquet_raising_progress_aborts_loudly_keeping_prior_export(tmp_path: Path) -> None:
    pytest.importorskip("pyarrow")
    out = tmp_path / "export.parquet"
    to_parquet(_corpus(2), out)
    before = out.read_bytes()

    def boom(done: int, total: int) -> None:
        raise RuntimeError("observer failed")

    with pytest.raises(RuntimeError, match="observer failed"):
        to_parquet(_corpus(4), out, level="token", progress=boom)
    assert out.read_bytes() == before
    assert not list(tmp_path.glob("*.tmp"))


def test_progress_dataframe_bad_level_raises_like_to_dataframe(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="level must be"):
        to_csv(_corpus(2), tmp_path / "x.csv", level="sentence", progress=lambda d, t: None)


# ══════════════════════════════════════════════════════════════════════════════
# data.fetch: progress reports BYTES on download, tar MEMBERS on extraction
# ══════════════════════════════════════════════════════════════════════════════

PAYLOAD = bytes(range(256)) * 10_000  # 2,560,000 bytes: several 1 MiB read chunks


@pytest.fixture(autouse=True)
def _isolated_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PYAEGEAN_CACHE", str(tmp_path / "cache"))


class _Server(socketserver.ThreadingTCPServer):
    """Serves one payload at any path, honoring a ``bytes=N-`` Range (206) and, when
    ``send_length`` is False, omitting Content-Length (the unknown-total path)."""

    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, payload: bytes, *, send_length: bool = True) -> None:
        super().__init__(("127.0.0.1", 0), _Handler)
        self.payload = payload
        self.send_length = send_length
        self.range_headers: list[str | None] = []
        self.statuses: list[int] = []

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.server_address[1]}/asset.bin"

    def handle_error(self, request: object, client_address: object) -> None:
        pass


class _Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a: object) -> None:
        pass

    def do_GET(self) -> None:
        srv = self.server
        assert isinstance(srv, _Server)
        srv.range_headers.append(self.headers.get("Range"))
        payload = srv.payload
        rng = self.headers.get("Range")
        start: int | None = None
        if rng is not None:
            m = re.fullmatch(r"bytes=(\d+)-", rng.strip())
            if m:
                start = int(m.group(1))
        if start is not None and start >= len(payload):
            srv.statuses.append(416)
            self.send_response(416)
            self.send_header("Content-Range", f"bytes */{len(payload)}")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if start is not None:
            status, body = 206, payload[start:]
        else:
            status, body = 200, payload
        srv.statuses.append(status)
        self.send_response(status)
        if status == 206:
            self.send_header("Content-Range", f"bytes {start}-{len(payload) - 1}/{len(payload)}")
        if srv.send_length:
            self.send_header("Content-Length", str(len(body)))
        else:
            # A chunked body has no Content-Length (the production callback must
            # report total=-1) but ends with a protocol-level terminator, avoiding
            # platform-specific FIN/RST behavior in the local test server.
            self.send_header("Transfer-Encoding", "chunked")
        self.send_header("Connection", "close")
        self.end_headers()
        if srv.send_length:
            self.wfile.write(body)
        else:
            self.wfile.write(f"{len(body):X}\r\n".encode("ascii"))
            self.wfile.write(body)
            self.wfile.write(b"\r\n0\r\n\r\n")
        self.wfile.flush()
        try:
            # Send a FIN after every flushed response body before the handler's
            # socket object is closed. On Windows this prevents unsent kernel-buffer
            # data from being discarded as an intermittent RST on multi-MiB bodies.
            self.connection.shutdown(socket.SHUT_WR)
        except OSError:
            pass
        # Python 3.14 on Windows can otherwise tear this local test socket down
        # with RST, turning the ordinary-progress tests into nondeterministic retry
        # tests. Reset handling is covered separately with explicit fault injection.
        self.close_connection = True


@pytest.fixture()
def server():  # type: ignore[no-untyped-def]
    srv = _Server(PAYLOAD)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    yield srv
    srv.shutdown()
    srv.server_close()
    thread.join(timeout=10)


def _register(monkeypatch: pytest.MonkeyPatch, url: str, payload: bytes = PAYLOAD, *,
              extract: bool = False) -> None:
    monkeypatch.setitem(
        data._REMOTE, "blob",
        DataSpec(name="blob", url=url, license="x",
                 sha256=hashlib.sha256(payload).hexdigest(), extract=extract),
    )


def _assert_byte_sequence(calls: list[tuple[int, int]], total: int) -> None:
    """A download byte sequence: non-empty, strictly increasing absolute bytes, every
    call's total consistent, ending exactly at ``(total, total)``."""
    assert calls, "expected at least one progress call"
    assert all(t == total for _, t in calls)
    dones = [d for d, _ in calls]
    assert dones == sorted(dones) and len(set(dones)) == len(dones)  # strictly increasing
    assert 0 < dones[0] <= total
    assert calls[-1] == (total, total)


def test_fetch_download_reports_absolute_bytes_ending_at_total(server, monkeypatch) -> None:
    _register(monkeypatch, server.url)
    calls: list[tuple[int, int]] = []
    p = fetch("blob", progress=lambda d, t: calls.append((d, t)))
    assert p.read_bytes() == PAYLOAD
    _assert_byte_sequence(calls, len(PAYLOAD))  # bytes, total = full size, final (total, total)


def test_fetch_download_is_byte_identical_with_and_without_progress(server, monkeypatch) -> None:
    _register(monkeypatch, server.url)
    with_p = fetch("blob", progress=lambda d, t: None)
    body_with = with_p.read_bytes()
    data.fetch("blob", force=True)  # re-fetch with no progress
    body_without = (data.cache_dir() / "blob").read_bytes()
    assert body_with == body_without == PAYLOAD  # the hook never changes the bytes


def test_fetch_already_cached_makes_no_progress_calls(server, monkeypatch) -> None:
    _register(monkeypatch, server.url)
    fetch("blob")  # populate the store
    calls: list[tuple[int, int]] = []
    fetch("blob", progress=lambda d, t: calls.append((d, t)))  # idempotent no-op
    assert calls == []


def test_fetch_unknown_content_length_reports_total_minus_one(monkeypatch) -> None:
    srv = _Server(PAYLOAD, send_length=False)  # no Content-Length header
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    try:
        _register(monkeypatch, srv.url)
        calls: list[tuple[int, int]] = []
        p = fetch("blob", progress=lambda d, t: calls.append((d, t)))
    finally:
        srv.shutdown()
        srv.server_close()
        thread.join(timeout=10)
    assert p.read_bytes() == PAYLOAD
    assert calls, "expected progress calls even without a known total"
    assert all(t == -1 for _, t in calls)  # the documented unknown-total convention
    assert calls[-1][0] == len(PAYLOAD)  # the last call still reports every byte


def test_fetch_resume_reports_bytes_continuing_from_the_part_offset(server, monkeypatch) -> None:
    _register(monkeypatch, server.url)
    # Leave less than one transfer chunk. Windows' in-process HTTPServer can reset
    # a closing socket between two client reads even after its handler flushed the
    # full body; multi-chunk retry behavior is fault-injected in test_data_resume.
    offset = 2_550_000
    part = data.cache_dir() / "blob.part"
    part.parent.mkdir(parents=True, exist_ok=True)
    part.write_bytes(PAYLOAD[:offset])  # a kept partial transfer

    calls: list[tuple[int, int]] = []
    p = fetch("blob", progress=lambda d, t: calls.append((d, t)))
    assert p.read_bytes() == PAYLOAD
    assert server.range_headers == [f"bytes={offset}-"]  # resumed, not restarted
    assert calls[0][0] > offset  # bytes_done starts AT the resumed offset, not at 0
    _assert_byte_sequence(calls, len(PAYLOAD))


def test_fetch_raising_progress_keeps_part_and_next_fetch_resumes(server, monkeypatch) -> None:
    _register(monkeypatch, server.url)
    state = {"n": 0}

    def boom(done: int, total: int) -> None:
        state["n"] += 1
        if state["n"] >= 2:  # let the first chunk land, then fail mid-transfer
            raise RuntimeError("observer failed")

    with pytest.raises(RuntimeError, match="observer failed"):  # aborts loudly, unwrapped
        fetch("blob", progress=boom)

    part = data.cache_dir() / "blob.part"
    kept = part.read_bytes()
    assert 0 < len(kept) < len(PAYLOAD)  # a partial transfer was kept
    assert kept == PAYLOAD[: len(kept)]  # ...and is an uncorrupted prefix (resumable)

    p = fetch("blob")  # the retry a caller would make; no raising observer this time
    assert p.read_bytes() == PAYLOAD
    assert server.range_headers[-1] == f"bytes={len(kept)}-"  # continued from the kept .part
    assert not part.exists()


def _tar_gz(members: list[tuple[str, bytes]]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for name, content in members:
            info = tarfile.TarInfo(name)
            info.size = len(content)
            tf.addfile(info, io.BytesIO(content))
    return buf.getvalue()


def test_fetch_extraction_reports_per_member_progress(monkeypatch) -> None:
    members = [("a.txt", b"A" * 500), ("b.txt", b"B" * 10), ("c.txt", b"C" * 10)]
    archive = _tar_gz(members)
    srv = _Server(archive)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    try:
        _register(monkeypatch, srv.url, payload=archive, extract=True)
        calls: list[tuple[int, int]] = []
        out = fetch("blob", progress=lambda d, t: calls.append((d, t)))
    finally:
        srv.shutdown()
        srv.server_close()
        thread.join(timeout=10)

    # the unpacked directory is correct
    assert (out / "a.txt").read_bytes() == b"A" * 500
    assert (out / "c.txt").read_bytes() == b"C" * 10
    # a download phase reported bytes (total == the archive size, distinct from 3 members)
    assert any(t == len(archive) for _, t in calls)
    # then per-member extraction, in order, ending at (3, 3)
    assert calls[-3:] == [(1, 3), (2, 3), (3, 3)]
    assert calls[-1] == (3, 3)


def test_fetch_extraction_bytes_and_members_stay_correct_without_progress(monkeypatch) -> None:
    # the default (progress=None) extract path is unchanged: files land correctly
    members = [("a.txt", b"hello"), ("b.txt", b"world")]
    archive = _tar_gz(members)
    srv = _Server(archive)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    try:
        _register(monkeypatch, srv.url, payload=archive, extract=True)
        out = fetch("blob")  # no progress
    finally:
        srv.shutdown()
        srv.server_close()
        thread.join(timeout=10)
    assert (out / "a.txt").read_bytes() == b"hello"
    assert (out / "b.txt").read_bytes() == b"world"


def test_fetch_unknown_dataset_still_raises_cleanly() -> None:
    with pytest.raises(DataNotAvailableError, match="unknown dataset"):
        fetch("nonesuch", progress=lambda d, t: None)


# ── the CLI live line ─────────────────────────────────────────────────────────


def test_cli_fetch_progress_paints_download_then_extraction_tty_only() -> None:
    """`_FetchProgress`: silent off a TTY; on a TTY, a repainted byte line for the
    download phase then a member line for extraction, each phase change closing the
    prior line."""
    import sys

    from aegean.cli._data import _FetchProgress

    class _Tty(io.StringIO):
        def isatty(self) -> bool:
            return True

    real = sys.stderr
    paint = _FetchProgress("blob")
    try:
        sys.stderr = _Tty()
        paint(1_000_000, 2_000_000)   # download, 50%
        paint(2_000_000, 2_000_000)   # download, 100% -> closes the line
        paint(1, 3)                    # extraction begins (total switches 2M -> 3)
        paint(3, 3)                    # extraction complete
        paint.close()
        out = sys.stderr.getvalue()
    finally:
        sys.stderr = real
    assert "fetching blob: 1.0/2.0 MB (50%)" in out
    assert "fetching blob: 2.0/2.0 MB (100%)" in out
    assert "extracting blob: 1/3 files (33%)" in out
    assert out.rstrip().endswith("extracting blob: 3/3 files (100%)")

    try:
        sys.stderr = io.StringIO()  # a plain StringIO is not a TTY
        _FetchProgress("blob")(1_000, 2_000)
        piped = sys.stderr.getvalue()
    finally:
        sys.stderr = real
    assert piped == ""  # piped / captured / --json runs stay clean
