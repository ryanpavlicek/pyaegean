"""Regression tests for the security fixes.

* the workbench image server's traversal guard: backslash, mixed-separator, and
  percent-encoded payloads (the old guard only caught forward-slash ``..``, so on
  Windows ``a\\..\\..\\secret`` escaped the imagery dir), plus absolute and
  drive-letter forms;
* the ``workbench-app`` asset pin: at least 1.5.2, the sanitizer-fixed build;
* ``_download``: a timeout on the connection (a stall raises instead of hanging
  ``fetch()`` forever) with the file written chunked;
* ``_safe_extract_tar``: symlink/hardlink members whose *targets* escape the
  extraction root are refused before anything is unpacked.
"""

from __future__ import annotations

import http.client
import io
import os
import re
import tarfile
import threading
from pathlib import Path

import pytest

from aegean import data
from aegean.cli._workbench import _make_handler, _resolve_path
from aegean.data import DataNotAvailableError

# ---------------------------------------------------------------------------
# _resolve_path: the imagery traversal guard
# ---------------------------------------------------------------------------

# Every payload aims at <imgroot>/secret.txt from an images root at <imgroot>/images.
_TRAVERSAL_PAYLOADS = [
    "/upstream/images/../secret.txt",                     # plain forward-slash
    "/upstream/images/..\\secret.txt",                    # plain backslash
    "/upstream/images/a\\..\\..\\secret.txt",             # backslash, no leading ".."
    "/upstream/images/a/..\\..\\secret.txt",              # mixed separators
    "/upstream/images/a\\../..\\secret.txt",              # mixed separators
    "/upstream/images/%2e%2e/secret.txt",                 # encoded dots
    "/upstream/images/%2e%2e%5csecret.txt",               # encoded dots + backslash
    "/upstream/images/..%5C..%5Csecret.txt",              # encoded backslashes
    "/upstream/images/a%5C..%5C..%5Csecret.txt",          # encoded, no leading ".."
    "/upstream/images//etc/passwd",                       # absolute
    "/upstream/images/%2F%2Fserver%2Fshare",              # encoded UNC form
    "/upstream/images/C:/Windows/win.ini",                # drive letter
    "/upstream/images/C:\\Windows\\win.ini",              # drive letter, backslashes
    "/upstream/images/C:secret.txt",                      # drive-relative
]


def _layout(tmp_path: Path) -> tuple[Path, Path, Path]:
    """<imgroot>/images (the served root), a file inside it, and a secret one level up."""
    images = tmp_path / "imgroot" / "images"
    images.mkdir(parents=True)
    (images / "pic.jpg").write_bytes(b"jpeg-bytes")
    secret = tmp_path / "imgroot" / "secret.txt"
    secret.write_bytes(b"top-secret")
    return tmp_path / "app", images, secret


def test_resolve_path_rejects_all_traversal_forms(tmp_path: Path) -> None:
    static, images, _ = _layout(tmp_path)
    for payload in _TRAVERSAL_PAYLOADS:
        assert _resolve_path(payload, static, images) is None, payload


def test_resolve_path_never_escapes_the_images_root(tmp_path: Path) -> None:
    # Property invariant: whatever the request, a mapped path stays inside the root.
    static, images, _ = _layout(tmp_path)
    root = os.path.realpath(images)
    for payload in _TRAVERSAL_PAYLOADS + ["/upstream/images/pic.jpg", "/upstream/images/a/./b"]:
        mapped = _resolve_path(payload, static, images)
        if mapped is not None:
            real = os.path.realpath(mapped)
            assert os.path.commonpath([root, real]) == root, payload


def test_resolve_path_still_serves_cached_images(tmp_path: Path) -> None:
    static, images, _ = _layout(tmp_path)
    (images / "sub").mkdir()
    (images / "sub" / "b.png").write_bytes(b"png-bytes")
    (images / "HT 1.jpg").write_bytes(b"spaced-name")

    mapped = _resolve_path("/upstream/images/pic.jpg", static, images)
    assert mapped == os.path.join(str(images), "pic.jpg")
    assert Path(mapped).read_bytes() == b"jpeg-bytes"
    assert _resolve_path("/upstream/images/sub/b.png", static, images) == os.path.join(
        str(images), "sub", "b.png"
    )
    # percent-encoded names decode, matching SimpleHTTPRequestHandler.translate_path
    spaced = _resolve_path("/upstream/images/HT%201.jpg", static, images)
    assert spaced is not None and Path(spaced).read_bytes() == b"spaced-name"


def test_server_never_serves_outside_the_images_root(tmp_path: Path) -> None:
    # End-to-end over HTTP: the secret sits one level above the served images root.
    static, images, secret = _layout(tmp_path)
    static.mkdir()
    (static / "index.html").write_text("<html>ok</html>", encoding="utf-8")

    import socketserver

    handler = _make_handler(static, images)
    with socketserver.ThreadingTCPServer(("127.0.0.1", 0), handler) as server:
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            def get(path: str) -> tuple[int, bytes]:
                conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
                try:
                    conn.request("GET", path)
                    resp = conn.getresponse()
                    return resp.status, resp.read()
                finally:
                    conn.close()

            status, body = get("/upstream/images/pic.jpg")
            assert status == 200 and body == b"jpeg-bytes"  # legit images still serve
            for payload in _TRAVERSAL_PAYLOADS:
                status, body = get(payload)
                assert status != 200, payload
                assert b"top-secret" not in body, payload
        finally:
            server.shutdown()
            thread.join(timeout=10)


# ---------------------------------------------------------------------------
# the workbench-app pin
# ---------------------------------------------------------------------------

def test_workbench_app_pin_is_at_least_the_sanitizer_fixed_build() -> None:
    spec = data._REMOTE["workbench-app"]
    m = re.search(r"workbench-app-v(\d+)\.(\d+)\.(\d+)/", spec.url)
    assert m is not None, spec.url
    version = tuple(int(g) for g in m.groups())
    assert version >= (1, 5, 4)  # 1.5.2 fixed the HTML sanitizer; 1.5.4 is current
    assert len(spec.sha256) == 64
    # the 1.5.1 digest must be gone with the tag (guards a tag-only bump)
    assert spec.sha256 != "22d05fd641c6419793b81adea4a658f8961d2916a0c06e357e141f6419dfec8c"


# ---------------------------------------------------------------------------
# _download: timeout + chunked copy
# ---------------------------------------------------------------------------

def test_download_passes_a_timeout_and_writes_the_payload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import urllib.request

    captured: dict[str, object] = {}

    class _Resp(io.BytesIO):
        def __enter__(self) -> _Resp:
            return self

        def __exit__(self, *args: object) -> None:
            self.close()

    def fake_urlopen(url: str, *args: object, **kwargs: object) -> _Resp:
        captured["timeout"] = kwargs.get("timeout")
        return _Resp(b"asset-bytes")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    dest = tmp_path / "asset.part"
    data._download("https://example.invalid/asset", dest, "asset")
    assert dest.read_bytes() == b"asset-bytes"
    timeout = captured["timeout"]
    assert isinstance(timeout, (int, float)) and timeout > 0  # a stall can't hang forever


def test_download_still_handles_file_urls(tmp_path: Path) -> None:
    # file:// URLs are the env-override / offline-test path; they must keep working.
    src = tmp_path / "src.bin"
    src.write_bytes(b"local-copy")
    dest = tmp_path / "out.part"
    data._download(src.as_uri(), dest, "local")
    assert dest.read_bytes() == b"local-copy"


# ---------------------------------------------------------------------------
# _safe_extract_tar: link-target validation
# ---------------------------------------------------------------------------

def _make_archive(tmp_path: Path, links: list[tuple[str, str, bytes]]) -> Path:
    """A tar.gz with one regular file plus the given (name, linkname, tar-type) links."""
    archive = tmp_path / "bundle.tar.gz"
    with tarfile.open(archive, "w:gz") as tf:
        blob = b"img-a"
        info = tarfile.TarInfo("images/a.jpg")
        info.size = len(blob)
        tf.addfile(info, io.BytesIO(blob))
        for name, linkname, typ in links:
            link = tarfile.TarInfo(name)
            link.type = typ
            link.linkname = linkname
            tf.addfile(link)
    return archive


@pytest.mark.parametrize(
    ("name", "linkname", "typ"),
    [
        ("images/evil", "../../../outside.txt", tarfile.SYMTYPE),   # relative escape
        ("evil", "../outside.txt", tarfile.SYMTYPE),                # one level up
        ("images/evil", "/etc/passwd", tarfile.SYMTYPE),            # absolute
        ("images/evil", "../../outside.txt", tarfile.LNKTYPE),      # hard link escape
    ],
)
def test_extract_rejects_escaping_link_targets(
    tmp_path: Path, name: str, linkname: str, typ: bytes
) -> None:
    archive = _make_archive(tmp_path, [(name, linkname, typ)])
    dest = tmp_path / "unpack"
    dest.mkdir()
    with pytest.raises(DataNotAvailableError, match="unsafe link target"):
        data._safe_extract_tar(archive, dest)
    assert list(dest.iterdir()) == []  # refused before anything was unpacked


def test_extract_keeps_benign_relative_links(tmp_path: Path) -> None:
    # A sibling-relative symlink stays inside the root and must not be refused.
    # (Where symlinks can't be created, tarfile falls back to copying the target.)
    archive = _make_archive(tmp_path, [("images/link.jpg", "a.jpg", tarfile.SYMTYPE)])
    dest = tmp_path / "unpack"
    dest.mkdir()
    data._safe_extract_tar(archive, dest)
    assert (dest / "images" / "a.jpg").read_bytes() == b"img-a"
    assert (dest / "images" / "link.jpg").read_bytes() == b"img-a"
