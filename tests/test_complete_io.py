"""Completion-pass correctness tests for aegean.io / aegean.db / aegean.geo / aegean.data.

Most of this module group already has strong correctness coverage (see test_io.py,
test_db.py, test_db_append.py, test_geo.py, test_data.py, test_file_import.py,
test_io_workbench.py). This file backfills the public functions that were UNTESTED there:

  * aegean.data.load_bundled_json / cache_dir / bundled_data_version / versions /
    download_file / fetch_prebuilt
  * aegean.io.read_epidoc (the list[Document] entry point; previously exercised only
    indirectly through from_epidoc)
  * aegean.analysis.normalize_sign_label (named in the coverage task; subscript folding)

Everything here is pure stdlib + bundled data; no network. The one download path uses a
``file://`` URL so it is deterministic and offline.
"""

from __future__ import annotations

import hashlib
import json
from importlib.resources import files
from pathlib import Path

import pytest

from aegean import data
from aegean.analysis import normalize_sign_label
from aegean.core.model import Document, DocumentMeta, ReadingStatus, Token, TokenKind
from aegean.data import (
    DataNotAvailableError,
    DataSpec,
    bundled_data_version,
    cache_dir,
    download_file,
    fetch_prebuilt,
    load_bundled_json,
    sha256_file,
    versions,
)
from aegean.io import read_epidoc, write_epidoc


@pytest.fixture(autouse=True)
def _isolated_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point the cache at a temp dir so nothing touches the user's real ~/.cache."""
    monkeypatch.setenv("PYAEGEAN_CACHE", str(tmp_path / "cache"))


# ── aegean.data.load_bundled_json ────────────────────────────────────────────────


def test_load_bundled_json_equals_raw_bytes_parse() -> None:
    """load_bundled_json must return exactly json.loads of the file's on-disk bytes.

    Expected value is derived by reading the same bundled file via importlib.resources
    and parsing it independently — an identity invariant, not a snapshot of behavior."""
    raw = files("aegean.data").joinpath("bundled", "geo", "site_coordinates.json").read_bytes()
    expected = json.loads(raw.decode("utf-8"))
    assert load_bundled_json("geo", "site_coordinates.json") == expected


def test_load_bundled_json_returns_structured_data() -> None:
    """The Linear B sign list is a non-empty JSON array (known shape of the bundled file)."""
    signs = load_bundled_json("linearb", "signs.json")
    assert isinstance(signs, list)
    assert len(signs) > 0


def test_load_bundled_json_missing_file_raises() -> None:
    """A non-existent bundled resource raises (it cannot be read), not return empty."""
    with pytest.raises(Exception):  # noqa: B017 - FileNotFoundError on the resource path
        load_bundled_json("nope", "does-not-exist.json")


# ── aegean.data.cache_dir ────────────────────────────────────────────────────────


def test_cache_dir_honors_env_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """With PYAEGEAN_CACHE set, cache_dir is exactly <override>/pyaegean and is created.

    Hand-derived: cache_dir joins the override base with the literal 'pyaegean' subdir."""
    base = tmp_path / "mycache"
    monkeypatch.setenv("PYAEGEAN_CACHE", str(base))
    d = cache_dir()
    assert d == base / "pyaegean"
    assert d.is_dir()  # cache_dir creates it (mkdir parents=True, exist_ok=True)


def test_cache_dir_prefers_pyaegean_over_xdg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """PYAEGEAN_CACHE wins over XDG_CACHE_HOME (documented precedence)."""
    pae = tmp_path / "pae"
    monkeypatch.setenv("PYAEGEAN_CACHE", str(pae))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg"))
    assert cache_dir() == pae / "pyaegean"


# ── aegean.data.bundled_data_version ─────────────────────────────────────────────


def test_bundled_data_version_matches_package_version() -> None:
    """Bundled data is immutable per release, so its version IS the installed package
    version. Derived independently from importlib.metadata (or the uninstalled-tree
    sentinel the function documents)."""
    from importlib.metadata import PackageNotFoundError, version

    try:
        expected = version("pyaegean")
    except PackageNotFoundError:  # pragma: no cover - matches the function's own fallback
        expected = "0.0.0+unknown"
    assert bundled_data_version() == expected


# ── aegean.data.versions (the reproducibility manifest) ───────────────────────────


def test_versions_manifest_shape_and_keys() -> None:
    """The manifest has the three documented top-level keys, and package == data version."""
    v = versions()
    assert set(v.keys()) == {"package", "bundled", "fetched"}
    assert v["package"] == bundled_data_version()
    assert isinstance(v["bundled"], dict) and v["bundled"]
    assert isinstance(v["fetched"], dict) and v["fetched"]


def test_versions_bundled_sha256_and_bytes_are_correct() -> None:
    """Each bundled entry's sha256 + byte count must match an independent hash of the file.

    Expected values are recomputed from the file's own bytes via importlib.resources +
    hashlib — the manifest's whole purpose is byte-level reproducibility, so this asserts
    that promise rather than echoing the function's output."""
    v = versions()
    key = "geo/site_coordinates.json"
    sub, name = key.split("/")
    blob = files("aegean.data").joinpath("bundled", sub, name).read_bytes()
    assert v["bundled"][key]["sha256"] == hashlib.sha256(blob).hexdigest()
    assert v["bundled"][key]["bytes"] == len(blob)


def test_versions_fetched_entries_carry_pinned_metadata() -> None:
    """A pinned fetchable asset surfaces its 64-hex sha256, url, license, and a bool cached
    flag; with our isolated empty cache it must be uncached."""
    v = versions()
    li = v["fetched"]["lineara-images"]
    assert set(li.keys()) == {"url", "sha256", "license", "cached"}
    assert len(li["sha256"]) == 64
    assert li["url"].endswith("lineara-images-v1/lineara-images.tar.gz")
    assert li["cached"] is False  # isolated tmp cache holds nothing yet


def test_versions_cached_flag_flips_after_fetch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """cached starts False and becomes True once an asset is present in the cache.

    Uses a registered-but-overridden dataset fetched from a file:// URL (no network)."""
    src = tmp_path / "payload.bin"
    src.write_bytes(b"abc")
    monkeypatch.setitem(data._REMOTE, "tmpasset",
                        DataSpec(name="tmpasset", url=src.as_uri(), license="x"))
    assert versions()["fetched"]["tmpasset"]["cached"] is False
    data.fetch("tmpasset")
    assert versions()["fetched"]["tmpasset"]["cached"] is True


# ── aegean.data.download_file (shared atomic downloader) ──────────────────────────


def test_download_file_writes_bytes_and_verifies_checksum(tmp_path: Path) -> None:
    """download_file copies the source bytes to dest and accepts a correct sha256.

    Expected sha256 is computed from the source bytes with sha256_file (cross-checked
    below against hashlib)."""
    src = tmp_path / "src.bin"
    payload = b"facsimile-bytes-123"
    src.write_bytes(payload)
    good = sha256_file(src)
    assert good == hashlib.sha256(payload).hexdigest()  # sha256_file == hashlib over the bytes

    dest = tmp_path / "out" / "dest.bin"
    returned = download_file(src.as_uri(), dest, sha256=good)
    assert returned == dest
    assert dest.read_bytes() == payload
    assert not dest.with_name(dest.name + ".part").exists()  # temp removed after rename


def test_download_file_rejects_bad_checksum_and_cleans_up(tmp_path: Path) -> None:
    """A wrong sha256 raises DataNotAvailableError and leaves no dest/.part file behind."""
    src = tmp_path / "src.bin"
    src.write_bytes(b"data")
    dest = tmp_path / "dest.bin"
    with pytest.raises(DataNotAvailableError, match="checksum mismatch"):
        download_file(src.as_uri(), dest, sha256="0" * 64)
    assert not dest.exists()
    assert not dest.with_name(dest.name + ".part").exists()


# ── aegean.data.fetch_prebuilt (build-from-source fallback gate) ──────────────────


def test_fetch_prebuilt_places_single_file_artifact(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """fetch_prebuilt returns True and copies a hosted single-file artifact to dest."""
    src = tmp_path / "index.json.gz"
    src.write_bytes(b"prebuilt-index")
    monkeypatch.setitem(data._REMOTE, "pbasset",
                        DataSpec(name="pbasset", url=src.as_uri(), license="x"))
    dest = tmp_path / "placed" / "index.json.gz"
    assert fetch_prebuilt("pbasset", dest) is True
    assert dest.read_bytes() == b"prebuilt-index"


def test_fetch_prebuilt_extracts_named_member(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """For an extract dataset, ``member`` selects a file inside the unpacked dir."""
    import tarfile

    payload = tmp_path / "tree"
    (payload / "sub").mkdir(parents=True)
    (payload / "sub" / "model.onnx").write_bytes(b"weights")
    archive = tmp_path / "bundle.tar.gz"
    with tarfile.open(archive, "w:gz") as tf:
        tf.add(payload, arcname="pkg")
    monkeypatch.setitem(
        data._REMOTE, "pbtar",
        DataSpec(name="pbtar", url=archive.as_uri(), license="x",
                 sha256=sha256_file(archive), extract=True),
    )
    dest = tmp_path / "out.onnx"
    assert fetch_prebuilt("pbtar", dest, member="pkg/sub/model.onnx") is True
    assert dest.read_bytes() == b"weights"


def test_fetch_prebuilt_returns_false_when_unavailable() -> None:
    """An unpinned dataset (no URL) makes fetch_prebuilt return False (so the caller
    falls back to building), never raises. 'linearb-corpus' ships with an empty URL."""
    assert "linearb-corpus" in data._REMOTE
    assert data._REMOTE["linearb-corpus"].url == ""
    dest = cache_dir() / "wont-be-written.bin"
    assert fetch_prebuilt("linearb-corpus", dest) is False
    assert not dest.exists()


def test_fetch_prebuilt_returns_false_for_missing_member(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A member that isn't in the unpacked archive yields False, not a crash."""
    import tarfile

    payload = tmp_path / "tree"
    payload.mkdir()
    (payload / "a.txt").write_bytes(b"a")
    archive = tmp_path / "b.tar.gz"
    with tarfile.open(archive, "w:gz") as tf:
        tf.add(payload, arcname="pkg")
    monkeypatch.setitem(
        data._REMOTE, "pbtar2",
        DataSpec(name="pbtar2", url=archive.as_uri(), license="x",
                 sha256=sha256_file(archive), extract=True),
    )
    assert fetch_prebuilt("pbtar2", tmp_path / "x", member="pkg/missing.txt") is False


# ── aegean.io.read_epidoc (the list[Document] reader, direct) ─────────────────────


def _epidoc_doc() -> Document:
    """A hand-built Document with one CERTAIN, one RESTORED, and one LOST token across
    two physical lines — covers the LOST-vs-RESTORED distinction the writer encodes via
    @reason on <supplied>."""
    toks = [
        Token("KU-RO", TokenKind.WORD, ("KU", "RO"), line_no=0, position=0),
        Token("OVIS", TokenKind.LOGOGRAM, ("OVIS",), line_no=0, position=1),
        Token("DA-RO", TokenKind.WORD, ("DA", "RO"), line_no=1, position=2,
              status=ReadingStatus.RESTORED),
        Token("PA-RO", TokenKind.WORD, ("PA", "RO"), line_no=1, position=3,
              status=ReadingStatus.LOST),
    ]
    return Document(
        id="KN X 7", script_id="linearb", tokens=toks, lines=[[0, 1], [2, 3]],
        meta=DocumentMeta(site="Knossos", name="KN X 7"),
    )


def test_read_epidoc_single_file_recovers_tokens_lines_and_status(tmp_path: Path) -> None:
    """read_epidoc returns a one-element list whose Document matches the source's id,
    site, token texts/kinds, line grouping, and editorial status (incl. LOST≠RESTORED).

    Expected values are the hand-built source document's own fields — this is a
    write→read round-trip identity on the stdlib reader/writer pair."""
    src = _epidoc_doc()
    p = tmp_path / "kn_x_7.xml"
    write_epidoc(src, p)

    docs = read_epidoc(p, script_id="linearb")
    assert isinstance(docs, list) and len(docs) == 1
    back = docs[0]
    assert back.id == "KN X 7"
    assert back.meta.site == "Knossos"
    assert [t.text for t in back.tokens] == ["KU-RO", "OVIS", "DA-RO", "PA-RO"]
    assert [t.kind for t in back.tokens] == [
        TokenKind.WORD, TokenKind.LOGOGRAM, TokenKind.WORD, TokenKind.WORD,
    ]
    assert back.lines == [[0, 1], [2, 3]]
    by_text = {t.text: t.status for t in back.tokens}
    assert by_text == {
        "KU-RO": ReadingStatus.CERTAIN,
        "OVIS": ReadingStatus.CERTAIN,
        "DA-RO": ReadingStatus.RESTORED,
        "PA-RO": ReadingStatus.LOST,  # distinct from RESTORED via @reason="undefined"
    }


def test_read_epidoc_directory_reads_all_files_sorted(tmp_path: Path) -> None:
    """Given a directory, read_epidoc reads every *.xml (in sorted order) into Documents."""
    d = tmp_path / "edition"
    d.mkdir()
    write_epidoc(_epidoc_doc(), d / "b.xml")
    second = Document(
        id="KN X 1", script_id="linearb",
        tokens=[Token("A-DU", TokenKind.WORD, ("A", "DU"), line_no=0, position=0)],
        lines=[[0]], meta=DocumentMeta(site="Knossos"),
    )
    write_epidoc(second, d / "a.xml")

    docs = read_epidoc(d, script_id="linearb")
    assert len(docs) == 2
    # a.xml sorts before b.xml; ids come from the <idno> in each file, not the filename
    assert [doc.id for doc in docs] == ["KN X 1", "KN X 7"]


# ── aegean.analysis.normalize_sign_label (task-named; subscript folding) ──────────


def test_normalize_sign_label_folds_unicode_subscripts() -> None:
    """Subscript digits ₂/₃/₄ fold to ASCII 2/3/4; everything else is unchanged.

    Hand-derived from the documented contract (RA₂ → RA2). The case is preserved
    (this function does not upper-case)."""
    assert normalize_sign_label("RA₂") == "RA2"   # RA₂
    assert normalize_sign_label("PA₃") == "PA3"   # PA₃
    assert normalize_sign_label("ZA₄") == "ZA4"   # ZA₄
    assert normalize_sign_label("RA2") == "RA2"        # already ASCII → identity
    assert normalize_sign_label("A-DU") == "A-DU"      # no subscripts → unchanged
    assert normalize_sign_label("") == ""              # empty in, empty out


def test_normalize_sign_label_only_touches_known_subscripts() -> None:
    """A subscript-one (₁) is NOT in the fold map, so it is left as-is — the function
    only folds ₂/₃/₄ (the homophone disambiguators that appear in Aegean sign labels)."""
    assert normalize_sign_label("DA₁") == "DA₁"  # ₁ untouched
