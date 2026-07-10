"""End-to-end journeys through the REAL fetch -> registered-loader -> analyze -> export
seam that the per-loader tests monkeypatch away. Offline: every download is a file:// URL
into an isolated PYAEGEAN_CACHE (the tests/test_data.py idiom)."""

from __future__ import annotations

import tarfile

import pytest

import aegean
from aegean import Provenance, ReadingStatus, data, db
from aegean.core.corpus import Corpus
from aegean.data import DataSpec, fetch, sha256_file


@pytest.fixture(autouse=True)
def _isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("PYAEGEAN_CACHE", str(tmp_path / "cache"))


def _greek_corpus(extra: bool = False) -> Corpus:
    """A 2-doc Greek corpus with one RESTORED token and apparatus-aware provenance,
    the same shape the shipped isicily-corpus asset carries."""
    doc2_line = ["ΞΕΝΟΔΟΚΟΣ", "ΑΝΕΘΗΚΕ"] + (["ΘΕΟΙΣ"] if extra else [])
    records = [
        {
            "id": "TEST001",
            "lines": [["ΔΙΟΣ", {"text": "ΣΩΤΗΡΟΣ", "status": "restored"}]],
            "meta": {"site": "Syracusae", "period": "Hellenistic"},
        },
        {"id": "TEST002", "lines": [doc2_line], "meta": {"site": "Katane"}},
    ]
    prov = Provenance(
        source="I.Sicily journey-test asset",
        license="CC-BY-4.0",
        edition_fidelity="apparatus-preserved,normalized",
    )
    return Corpus.from_records(records, script_id="greek", provenance=prov)


def _pin_isicily(tmp_path, monkeypatch, corpus: Corpus, filename: str) -> str:
    """Write ``corpus`` as a file:// asset and re-pin the REAL 'isicily-corpus' remote
    entry at it, so aegean.load('isicily') exercises the real fetch + registered loader."""
    asset = tmp_path / filename
    corpus.to_json(asset)
    sha = sha256_file(asset)
    monkeypatch.setitem(
        data._REMOTE,
        "isicily-corpus",
        DataSpec(
            name="isicily-corpus",
            url=asset.as_uri(),
            license="CC-BY-4.0",
            sha256=sha,
            extract=False,
        ),
    )
    return sha


def _targz(tmp_path, name: str, files: dict[str, bytes]):
    """A small tar.gz whose members live under 'payload/' (test_data.py's _make_targz)."""
    src = tmp_path / (name + "-payload")
    src.mkdir()
    for rel, content in files.items():
        p = src / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(content)
    archive = tmp_path / (name + ".tar.gz")
    with tarfile.open(archive, "w:gz") as tf:
        tf.add(src, arcname="payload")
    return archive, sha256_file(archive)


# ── journey 1: real fetch → registered loader → analyze → export → re-read ──
def test_fetch_feeds_registered_isicily_loader_end_to_end(tmp_path, monkeypatch):
    built = _greek_corpus()
    _pin_isicily(tmp_path, monkeypatch, built, "asset.json")

    c = aegean.load("isicily")  # the REAL data.fetch() feeding the REAL registered loader

    # fetch stored the sha-verified asset in the isolated cache under the dataset name
    assert (data.cache_dir() / "isicily-corpus").exists()

    # everything built in Python survived the JSON asset + download + loader
    assert [d.id for d in c.documents] == ["TEST001", "TEST002"]
    assert [t.text for t in c.get("TEST001").tokens] == ["ΔΙΟΣ", "ΣΩΤΗΡΟΣ"]
    assert [t.text for t in c.get("TEST002").tokens] == ["ΞΕΝΟΔΟΚΟΣ", "ΑΝΕΘΗΚΕ"]
    assert c.get("TEST001").tokens[0].status is ReadingStatus.CERTAIN
    assert c.get("TEST001").tokens[1].status is ReadingStatus.RESTORED  # apparatus survived
    assert c.provenance is not None
    assert c.provenance.license == "CC-BY-4.0"
    assert c.provenance.edition_fidelity == "apparatus-preserved,normalized"

    # analyze (metadata subset) → SQLite export → re-read: nothing decays in the chain
    sub = c.filter(site="Syracusae")
    assert [d.id for d in sub.documents] == ["TEST001"]
    db_path = tmp_path / "out.db"
    db.to_sqlite(sub, db_path, fts=True)
    back = db.from_sqlite(db_path)
    assert [d.id for d in back.documents] == ["TEST001"]
    assert [t.text for t in back.documents[0].tokens] == ["ΔΙΟΣ", "ΣΩΤΗΡΟΣ"]
    assert back.documents[0].tokens[1].status is ReadingStatus.RESTORED
    assert back.provenance is not None
    assert back.provenance.edition_fidelity == "apparatus-preserved,normalized"

    # full-text search over the exported DB finds the planted token exactly
    assert db.search(db_path, "ΣΩΤΗΡΟΣ") == [("TEST001", 1, "ΣΩΤΗΡΟΣ")]


# ── journey 2: a re-pinned asset propagates through the loader, no manual remove ──
def test_repin_propagates_through_registered_loader(tmp_path, monkeypatch):
    _pin_isicily(tmp_path, monkeypatch, _greek_corpus(), "asset.json")
    c1 = aegean.load("isicily")
    assert [t.text for t in c1.get("TEST002").tokens] == ["ΞΕΝΟΔΟΚΟΣ", "ΑΝΕΘΗΚΕ"]

    # rebuild the asset with one extra token and re-pin the SAME dataset entry (new url+sha)
    sha2 = _pin_isicily(tmp_path, monkeypatch, _greek_corpus(extra=True), "asset-v2.json")
    c2 = aegean.load("isicily")  # no `data remove` in between
    assert [t.text for t in c2.get("TEST002").tokens] == ["ΞΕΝΟΔΟΚΟΣ", "ΑΝΕΘΗΚΕ", "ΘΕΟΙΣ"]
    # fetch's sha re-validation replaced the stale cached copy with the v2 bytes
    assert sha256_file(data.cache_dir() / "isicily-corpus") == sha2


# ── journey 3: an env-mirror extract fetch stamps the ACTUAL archive sha ──
def test_env_mirror_fetch_writes_sha_stamp_then_repin_redownloads(tmp_path, monkeypatch):
    v1, sha1 = _targz(tmp_path, "v1", {"corpus.txt": b"v1-content"})
    monkeypatch.setitem(
        data._REMOTE, "mirrds", DataSpec(name="mirrds", url="", license="x", extract=True)
    )
    monkeypatch.setenv("PYAEGEAN_MIRRDS_URL", v1.as_uri())
    out = fetch("mirrds")  # sha unenforced (env override), but the extraction must be stamped
    assert (out / "payload" / "corpus.txt").read_bytes() == b"v1-content"
    stamp = data.cache_dir() / "mirrds.sha256"
    assert stamp.exists()  # NOT absent: the mirror fetch records what it actually extracted
    assert stamp.read_text(encoding="utf-8").strip() == sha1  # the real archive sha256

    # clear the mirror, re-pin the spec at a DIFFERENT archive: the stamped mirror sha
    # mismatches the pin, so fetch() re-downloads instead of serving the mirror's content
    monkeypatch.delenv("PYAEGEAN_MIRRDS_URL")
    v2, sha2 = _targz(tmp_path, "v2", {"corpus.txt": b"v2-content"})
    monkeypatch.setitem(
        data._REMOTE,
        "mirrds",
        DataSpec(name="mirrds", url=v2.as_uri(), license="x", sha256=sha2, extract=True),
    )
    out2 = fetch("mirrds")
    assert (out2 / "payload" / "corpus.txt").read_bytes() == b"v2-content"  # re-extracted
    assert stamp.read_text(encoding="utf-8").strip() == sha2


# ── journey 4: doctor reports a stranded .old extraction directory ──
def test_doctor_sees_stranded_old_extraction():
    from aegean import _doctor

    root = data.cache_dir()
    old = root / "someds.old"  # a re-pin swap's rename-aside dir, stranded by an interruption
    old.mkdir()
    (old / "stale.txt").write_text("stale", encoding="utf-8")

    report = _doctor.build_report()
    orphans = report["data_store"]["orphans"]
    mine = [o for o in orphans if o["file"] == "someds.old"]
    assert mine, f"doctor did not report the .old dir; orphans: {orphans}"
    assert mine[0]["dataset"] == "someds"
    assert str(old) in mine[0]["fix"]  # unregistered dataset → 'delete <path>'
    assert any(
        i["section"] == "data store" and "someds.old" in i["message"] for i in report["issues"]
    )
    assert report["ok"] is False
