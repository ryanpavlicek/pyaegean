"""data.fetch_prebuilt: the prefer-hosted-artifact-over-local-build helper (offline)."""

from __future__ import annotations

import pytest

from aegean import data


def test_fetch_prebuilt_copies_single_file(tmp_path, monkeypatch):
    src = tmp_path / "asset.bin"
    src.write_bytes(b"hello")
    monkeypatch.setattr(data, "fetch", lambda name, **k: src)
    dest = tmp_path / "out" / "index.json.gz"
    assert data.fetch_prebuilt("whatever", dest) is True
    assert dest.read_bytes() == b"hello"


def test_fetch_prebuilt_copies_member_from_extracted_dir(tmp_path, monkeypatch):
    extracted = tmp_path / "bundle"
    extracted.mkdir()
    (extracted / "model.json.gz").write_bytes(b"weights")
    monkeypatch.setattr(data, "fetch", lambda name, **k: extracted)
    dest = tmp_path / "model.json.gz"
    assert data.fetch_prebuilt("bundle", dest, member="model.json.gz") is True
    assert dest.read_bytes() == b"weights"


def test_fetch_prebuilt_false_when_unavailable(tmp_path, monkeypatch):
    def boom(name, **k):
        raise data.DataNotAvailableError("no url")

    monkeypatch.setattr(data, "fetch", boom)
    dest = tmp_path / "x"
    assert data.fetch_prebuilt("missing", dest) is False
    assert not dest.exists()


def test_fetch_prebuilt_false_when_member_absent(tmp_path, monkeypatch):
    extracted = tmp_path / "bundle"
    extracted.mkdir()
    monkeypatch.setattr(data, "fetch", lambda name, **k: extracted)
    assert data.fetch_prebuilt("bundle", tmp_path / "d", member="nope.gz") is False


def test_prebuilt_specs_registered():
    assert "lsj-index" in data._REMOTE
    assert data._REMOTE["lsj-index"].sha256  # pinned
    agdt = data._REMOTE["agdt-derived"]
    assert agdt.extract and agdt.sha256


def test_lexicon_build_uses_prebuilt_when_offered(tmp_path, monkeypatch):
    """build_index returns immediately when the prebuilt index is fetchable —
    no Perseus download, no parsing."""
    from aegean.greek import lexicon

    monkeypatch.setattr(lexicon, "cache_dir", lambda: tmp_path)

    def fake_prebuilt(name, dest, **k):
        assert name == "lsj-index"
        dest.write_bytes(b"\x1f\x8b")  # a stand-in gz; presence is what matters here
        return True

    monkeypatch.setattr("aegean.data.fetch_prebuilt", fake_prebuilt)
    # if it fell through to the real build it would hit the network; it must not
    monkeypatch.setattr(lexicon, "_lsj_dir", lambda **k: pytest.fail("built from source"))
    out = lexicon.build_index(force=True)
    assert out == tmp_path / lexicon._INDEX_NAME and out.exists()
