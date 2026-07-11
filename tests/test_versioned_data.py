"""The versioned-corpora surface: kept historical release pins, `fetch(name,
version=...)` into a version-suffixed cache entry, and `aegean.load(id,
version=...)` for reproducing an earlier analysis.

Offline: every download is a file:// URL into an isolated PYAEGEAN_CACHE (the
tests/test_data.py idiom); historical pins are injected by monkeypatching
`_REMOTE_HISTORY`, exactly as the existing tests monkeypatch `_REMOTE`."""

from __future__ import annotations

import json
import tarfile
from pathlib import Path

import pytest

import aegean
from aegean import data
from aegean.core.corpus import Corpus
from aegean.data import (
    DataNotAvailableError,
    DataSpec,
    HistoricalPin,
    fetch,
    sha256_file,
)


@pytest.fixture(autouse=True)
def _isolated_cache(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.setenv("PYAEGEAN_CACHE", str(tmp_path / "cache"))


# The six 0.29.0-superseded epigraphy assets, whose -v1 releases the project still hosts.
# The sha256 of each is the REAL value the v1 pin carried at publish time, recovered from
# the git history of data/__init__.py (commit 013fa15, the state just before the -v2 re-host).
_RECOVERED_V1 = {
    "isicily-corpus": "c0242f4b52df05ae7295b17a0c786dd7b474c4ef47520be88795c8117aa8d4d1",
    "iip-corpus": "2fec633b5e6ea38621bc8e0b3c62f959317e4cdd84af5c348b650a479a02dc74",
    "iospe-corpus": "bd2143d408d13f96d2e087e54c1508da6bfdb6a096fec6d82feeeb4523e33d7e",
    "igcyr-corpus": "673481ce3041ad268d26fb1d5490987b187ad86fb29af50ef7390f919f77e28b",
    "edh-corpus": "4828a9760fb64a397a510d3ac239a3df600ef23b7bd7d146c6ad911dc33f6541",
    "ddbdp-corpus": "7ae265384543cabc7554e543c3f3a1cccbfa1e3ca531b4cbd8755124f58845e2",
}


# ── (A) registry integrity: the recovered pins are real and distinct ────────────
@pytest.mark.parametrize(("name", "sha"), sorted(_RECOVERED_V1.items()))
def test_shipped_history_carries_the_real_recovered_v1_sha(name: str, sha: str) -> None:
    pins = data.historical_versions(name)
    v1 = next(p for p in pins if p.version == "v1")
    assert v1.sha256 == sha  # the actual published v1 checksum, not invented
    assert len(v1.sha256) == 64 and v1.superseded == "v2"
    assert v1.url.endswith(f"{name}-v1/{name}.json") or v1.url.endswith(f"{name}-v1/{name}.tar.gz")
    # every kept pin must differ from the current pin, and versions are newest-first
    for pin in pins:
        assert pin.sha256 != data._REMOTE[name].sha256
    assert [p.version for p in pins] == sorted(
        (p.version for p in pins), key=lambda v: int(v[1:]), reverse=True
    )


# Datasets whose superseded releases stay hosted: the six 0.29.0-era epigraphy corpora
# (v1 recovered) plus the assets rebuilt in the 0.39.0 fidelity pass.
_KEPT_HISTORY = set(_RECOVERED_V1) | {
    "sigla-corpus",
    "papygreek-fold",
    "autenrieth-index",
    "grc-paradigms",
}


def test_exactly_the_superseded_assets_have_kept_history() -> None:
    assert set(data._REMOTE_HISTORY) == _KEPT_HISTORY
    # a dataset without history reports an empty list, and available_versions is current-only
    assert data.historical_versions("nt-corpus") == []
    avail = data.available_versions("nt-corpus")
    assert len(avail) == 1 and avail[0]["current"] is True


def test_ddbdp_history_is_an_extract_archive_the_others_json() -> None:
    assert data.historical_versions("ddbdp-corpus")[0].extract is True
    assert all(p.extract is False for p in data.historical_versions("isicily-corpus"))


def test_available_versions_lists_current_first_then_history_newest_first() -> None:
    versions = data.available_versions("isicily-corpus")
    assert [v["version"] for v in versions] == ["v3", "v2", "v1"]
    assert versions[0]["current"] is True
    assert all(v["current"] is False for v in versions[1:])
    assert versions[1]["superseded"] == "v3" and versions[2]["superseded"] == "v2"


# ── (B) version resolution + fetch mechanics (file:// mocks) ─────────────────────
def _pin_history(monkeypatch, name, source: Path, *, extract=False):  # type: ignore[no-untyped-def]
    """Register `name` (current) + a v1 historical pin, both at file:// sources."""
    sha = sha256_file(source)
    monkeypatch.setitem(
        data._REMOTE_HISTORY,
        name,
        [HistoricalPin(version="v1", url=source.as_uri(), sha256=sha, superseded="v2", extract=extract)],
    )
    return sha


def test_version_selects_the_historical_url_and_sha(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    src = tmp_path / "v1.json"
    src.write_bytes(b"historical-v1-bytes")
    monkeypatch.setitem(
        data._REMOTE,
        "epi",
        DataSpec(
            name="epi",
            url="https://github.com/x/y/releases/download/epi-v2/epi.json",
            license="x",
            sha256="0" * 64,
        ),
    )
    sha = _pin_history(monkeypatch, "epi", src)
    url, resolved_sha, extract, ver = data._resolve_version("epi", "v1")
    assert url == src.as_uri() and resolved_sha == sha and ver == "v1" and extract is False


def test_versioned_fetch_lands_in_a_version_suffixed_entry(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    src = tmp_path / "v1.json"
    src.write_bytes(b"v1-content")
    monkeypatch.setitem(data._REMOTE, "epi", DataSpec(name="epi", url="", license="x"))
    _pin_history(monkeypatch, "epi", src)
    path = fetch("epi", version="v1")
    assert path == data.cache_dir() / "epi@v1"
    assert path.read_bytes() == b"v1-content"


def test_default_path_is_untouched_by_a_versioned_fetch(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    """The default (no version=) download is byte-identical to before and never
    collides with a versioned one — they are separate cache entries."""
    current = tmp_path / "current.json"
    current.write_bytes(b"CURRENT-v2")
    historical = tmp_path / "v1.json"
    historical.write_bytes(b"OLD-v1")
    monkeypatch.setitem(data._REMOTE, "epi", DataSpec(name="epi", url=current.as_uri(), license="x"))
    _pin_history(monkeypatch, "epi", historical)

    default = fetch("epi")  # the unchanged default path
    assert default == data.cache_dir() / "epi"
    assert default.read_bytes() == b"CURRENT-v2"
    mtime = default.stat().st_mtime_ns

    versioned = fetch("epi", version="v1")
    assert versioned != default
    assert versioned.read_bytes() == b"OLD-v1"
    # the default entry is completely unaffected by the versioned fetch
    assert default.read_bytes() == b"CURRENT-v2"
    assert default.stat().st_mtime_ns == mtime


def test_versioned_fetch_is_idempotent(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    src = tmp_path / "v1.json"
    src.write_bytes(b"v1")
    monkeypatch.setitem(data._REMOTE, "epi", DataSpec(name="epi", url="", license="x"))
    _pin_history(monkeypatch, "epi", src)
    first = fetch("epi", version="v1")
    mtime = first.stat().st_mtime_ns
    assert fetch("epi", version="v1") == first
    assert first.stat().st_mtime_ns == mtime  # no re-download


def test_versioned_fetch_rejects_a_bad_historical_sha(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    src = tmp_path / "v1.json"
    src.write_bytes(b"v1")
    monkeypatch.setitem(data._REMOTE, "epi", DataSpec(name="epi", url="", license="x"))
    monkeypatch.setitem(
        data._REMOTE_HISTORY,
        "epi",
        [HistoricalPin(version="v1", url=src.as_uri(), sha256="0" * 64, superseded="v2")],
    )
    with pytest.raises(DataNotAvailableError, match="checksum mismatch"):
        fetch("epi", version="v1")


def test_recovered_sha_entry_loads_when_it_matches(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    """A historical pin whose sha256 matches the served bytes fetches and verifies —
    the mechanism the real recovered-sha v1 pins rely on."""
    src = tmp_path / "v1.json"
    src.write_bytes(b"reproducible-historical-corpus")
    real_sha = sha256_file(src)
    monkeypatch.setitem(data._REMOTE, "epi", DataSpec(name="epi", url="", license="x"))
    monkeypatch.setitem(
        data._REMOTE_HISTORY,
        "epi",
        [HistoricalPin(version="v1", url=src.as_uri(), sha256=real_sha, superseded="v2")],
    )
    path = fetch("epi", version="v1")
    assert sha256_file(path) == real_sha


def test_unknown_version_raises_listing_available(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.setitem(
        data._REMOTE,
        "epi",
        DataSpec(
            name="epi",
            url="https://github.com/x/y/releases/download/epi-v2/epi.json",
            license="x",
            sha256="0" * 64,
        ),
    )
    monkeypatch.setitem(
        data._REMOTE_HISTORY,
        "epi",
        [HistoricalPin(version="v1", url="http://x/epi.json", sha256="0" * 64, superseded="v2")],
    )
    with pytest.raises(DataNotAvailableError, match="no version 'v9'.*v2.*v1"):
        fetch("epi", version="v9")


def test_current_version_string_resolves_to_the_current_pin(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    """Passing the current version tag fetches the current asset (into its own
    version-suffixed entry), not a historical one."""
    current = tmp_path / "current.json"
    current.write_bytes(b"the-current-asset")
    monkeypatch.setitem(
        data._REMOTE,
        "epi",
        DataSpec(
            name="epi",
            url="https://github.com/x/y/releases/download/epi-v2/epi.json",
            license="x",
        ),
    )
    monkeypatch.setenv(data._env_url_var("epi"), current.as_uri())
    path = fetch("epi", version="v2")
    assert path == data.cache_dir() / "epi@v2"
    assert path.read_bytes() == b"the-current-asset"


def test_per_version_env_override(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    """PYAEGEAN_<NAME>_<VERSION>_URL points a historical fetch at a user's mirror
    (sha not enforced against the mirror, like the current-URL override)."""
    mirror = tmp_path / "mirror-v1.json"
    mirror.write_bytes(b"from-my-own-mirror")
    monkeypatch.setitem(data._REMOTE, "epi", DataSpec(name="epi", url="", license="x"))
    monkeypatch.setitem(
        data._REMOTE_HISTORY,
        "epi",
        [HistoricalPin(version="v1", url="http://unreachable/epi.json", sha256="0" * 64, superseded="v2")],
    )
    monkeypatch.setenv(data._version_env_url_var("epi", "v1"), mirror.as_uri())
    path = fetch("epi", version="v1")
    assert path.read_bytes() == b"from-my-own-mirror"


# ── (C) aegean.load(id, version=...) end-to-end journey ─────────────────────────
def _json_corpus(words: list[str]) -> Corpus:
    return Corpus.from_records(
        [{"id": "ISic000001", "words": words, "meta": {"site": "Syracusae"}}],
        script_id="greek",
    )


def test_load_version_returns_the_historical_content(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    """Journey: pin a v1 and v2 isicily asset with DIFFERENT content, then confirm
    aegean.load('isicily') gives v2 and aegean.load('isicily', version='v1') gives v1."""
    v1_file = tmp_path / "isicily-v1.json"
    _json_corpus(["ΑΛΦΑ", "ΒΗΤΑ"]).to_json(v1_file)
    v2_file = tmp_path / "isicily-v2.json"
    _json_corpus(["ΑΛΦΑ", "ΒΗΤΑ", "ΓΑΜΜΑ"]).to_json(v2_file)
    monkeypatch.setitem(
        data._REMOTE,
        "isicily-corpus",
        DataSpec(name="isicily-corpus", url=v2_file.as_uri(), license="x", sha256=sha256_file(v2_file)),
    )
    _pin_history(monkeypatch, "isicily-corpus", v1_file)

    current = aegean.load("isicily")
    historical = aegean.load("isicily", version="v1")
    assert list(current.iter_words()) == ["ΑΛΦΑ", "ΒΗΤΑ", "ΓΑΜΜΑ"]
    assert list(historical.iter_words()) == ["ΑΛΦΑ", "ΒΗΤΑ"]
    # the two live in separate cache entries; loading one never disturbs the other
    root = data.cache_dir()
    assert (root / "isicily-corpus").exists() and (root / "isicily-corpus@v1").exists()


def test_load_version_reaches_a_sqlite_extract_corpus(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    """The ddbdp historical path: a SQLite-in-tar v1 archive materialises via db."""
    dbfile = tmp_path / "ddbdp.sqlite"
    _json_corpus(["βασιλεως", "δωρον"]).to_sql(dbfile)
    archive = tmp_path / "ddbdp-v1.tar.gz"
    with tarfile.open(archive, "w:gz") as tf:
        tf.add(dbfile, arcname="ddbdp.sqlite")
    monkeypatch.setitem(
        data._REMOTE_HISTORY,
        "ddbdp-corpus",
        [HistoricalPin(
            version="v1", url=archive.as_uri(), sha256=sha256_file(archive),
            superseded="v2", extract=True,
        )],
    )
    corpus = aegean.load("ddbdp", version="v1")
    assert list(corpus.iter_words()) == ["βασιλεως", "δωρον"]
    assert (data.cache_dir() / "ddbdp-corpus@v1").is_dir()


def test_load_version_on_a_corpus_without_history_is_a_clean_error() -> None:
    with pytest.raises(DataNotAvailableError, match="kept historical pins"):
        aegean.load("lineara", version="v1")


def test_default_load_ignores_version_none(monkeypatch):  # type: ignore[no-untyped-def]
    # version=None must be exactly the ordinary bundled path (no fetch attempted)
    corpus = aegean.load("lineara")
    assert len(corpus) > 0 and corpus.script_id == "lineara"


# ── (D) versions() manifest carries the history ─────────────────────────────────
def test_versions_manifest_includes_history_with_cached_flags(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    src = tmp_path / "v1.json"
    src.write_bytes(b"v1")
    monkeypatch.setitem(
        data._REMOTE,
        "isicily-corpus",
        DataSpec(name="isicily-corpus", url="", license="x"),
    )
    _pin_history(monkeypatch, "isicily-corpus", src)
    manifest = data.versions()
    hist = manifest["fetched"]["isicily-corpus"]["history"]
    assert len(hist) == 1 and hist[0]["version"] == "v1"
    assert hist[0]["cached"] is False
    fetch("isicily-corpus", version="v1")
    assert data.versions()["fetched"]["isicily-corpus"]["history"][0]["cached"] is True


# ── (E) CLI surface: `data versions` lists history, `data fetch --version` works ─
def _runner():  # type: ignore[no-untyped-def]
    pytest.importorskip("typer")
    from typer.testing import CliRunner

    from aegean.cli import _build_app

    return CliRunner(), _build_app()


def test_cli_data_versions_lists_the_historical_pin_json() -> None:
    runner, app = _runner()
    res = runner.invoke(app, ["data", "versions", "--json"])
    assert res.exit_code == 0, res.output
    manifest = json.loads(res.output)
    hist = manifest["fetched"]["isicily-corpus"]["history"]
    assert [h["version"] for h in hist] == ["v2", "v1"]
    assert hist[-1]["sha256"] == _RECOVERED_V1["isicily-corpus"]


def test_cli_data_versions_table_shows_a_versioned_row() -> None:
    runner, app = _runner()
    res = runner.invoke(app, ["data", "versions"])
    assert res.exit_code == 0, res.output
    assert "isicily-corpus@v1" in res.output


def test_cli_data_fetch_version(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.setenv("PYAEGEAN_CACHE", str(tmp_path / "cache"))
    src = tmp_path / "v1.json"
    src.write_bytes(b"v1-cli")
    monkeypatch.setitem(data._REMOTE, "isicily-corpus", DataSpec(name="isicily-corpus", url="", license="x"))
    _pin_history(monkeypatch, "isicily-corpus", src)
    runner, app = _runner()
    res = runner.invoke(app, ["data", "fetch", "isicily", "--version", "v1", "--json"])
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    assert payload["version"] == "v1"
    assert Path(payload["path"]) == tmp_path / "cache" / "pyaegean" / "isicily-corpus@v1"
    assert Path(payload["path"]).read_bytes() == b"v1-cli"


def test_cli_data_fetch_unknown_version_exits_nonzero(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.setenv("PYAEGEAN_CACHE", str(tmp_path / "cache"))
    runner, app = _runner()
    res = runner.invoke(app, ["data", "fetch", "isicily", "--version", "v999"])
    assert res.exit_code != 0
    assert "no version" in (res.output + (res.stderr if hasattr(res, "stderr") else ""))
