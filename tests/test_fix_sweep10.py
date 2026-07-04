"""Regression tests for the tenth sweep (security / hostile-input), 0.19.12.

Each pins a hardening fix against an untrusted-input weakness the security sweep found:
unsafe deserialization, an algorithmic-complexity DoS, a decompression bomb, a graceless
crash on a malformed corpus, a private-path leak, and a path-injection/SSRF.
"""

from __future__ import annotations

import gzip
import os
import time

import pytest

import aegean


# ── F6: load_work rejects a path-traversal work id (SSRF guard) ────────────────
def test_work_id_rejects_path_traversal():
    from aegean.scripts.greek.perseus import _work_dir

    for bad in [
        "g.p/../../../../ATTACKER/EVILREPO/main",
        "tlg0012.tlg001/../../x",
        "a.b\\c",
        "tlg0012.tlg001/..",
    ]:
        with pytest.raises(ValueError):
            _work_dir(bad)
    assert _work_dir("tlg0012.tlg001") == "data/tlg0012/tlg001"  # legit id still works


# ── F4: from_dict validates line indices instead of crashing later ─────────────
def test_from_dict_rejects_out_of_range_line_index():
    bad = {"documents": [{
        "id": "HT13", "script_id": "lineara",
        "tokens": [{"text": "a", "kind": "word"}],
        "lines": [[0, 7]],  # index 7 with a single token
    }]}
    with pytest.raises(ValueError) as exc:
        aegean.Corpus.from_dict(bad)
    assert "HT13" in str(exc.value) and "token" in str(exc.value)  # names the malformed source
    # a valid document still loads
    good = {"documents": [{
        "id": "HT13", "script_id": "lineara",
        "tokens": [{"text": "a", "kind": "word"}], "lines": [[0]],
    }]}
    assert len(aegean.Corpus.from_dict(good)) == 1


# ── F5: EpiDoc import provenance carries only the basename (no path leak) ───────
def test_epidoc_provenance_is_basename_only(tmp_path):
    from aegean.io.epidoc import from_epidoc

    xml = ('<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body><div type="edition">'
           "<ab><w>a</w></ab></div></body></text></TEI>")
    sub = tmp_path / "private_dissertation"
    sub.mkdir()
    f = sub / "inscr.xml"
    f.write_text(xml, encoding="utf-8")
    corpus = from_epidoc(f)
    assert corpus.provenance.source == "EpiDoc TEI import: inscr.xml"
    assert str(tmp_path) not in corpus.provenance.source  # no directory leak


# ── F3: the gzip index loader caps decompression (bomb guard) ──────────────────
def test_load_gzip_json_caps_decompression(tmp_path):
    from aegean.data import DataNotAvailableError, load_gzip_json

    p = tmp_path / "index.json.gz"
    with gzip.open(p, "wt", encoding="utf-8") as f:
        f.write('{"ok": [1, 2, 3]}')
    assert load_gzip_json(p) == {"ok": [1, 2, 3]}          # normal load

    with gzip.open(p, "wt", encoding="utf-8") as f:
        f.write('{"x": "' + "A" * 200_000 + '"}')          # inflates past a tiny cap
    with pytest.raises(DataNotAvailableError):
        load_gzip_json(p, max_bytes=1000)


# ── F2: EpiDoc import is linear, not quadratic (DoS guard) ─────────────────────
def _nested_tei(depth: int, ntok: int) -> str:
    body = "<seg>" * depth + "".join("<w>a</w>" for _ in range(ntok)) + "</seg>" * depth
    return ('<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body><div type="edition">'
            f"<ab>{body}</ab></div></body></text></TEI>")


def test_epidoc_deeply_nested_parses_quickly(tmp_path):
    """A deeply-nested TEI made the importer O(tokens x depth) = quadratic; a hostile
    ~100 KB file hung for many seconds. It is now linear, so a large nesting parses fast.
    The bound is generous (real time is a fraction of a second) so it does not flake."""
    from aegean.io.epidoc import from_epidoc

    f = tmp_path / "nested.xml"
    f.write_text(_nested_tei(depth=10_000, ntok=300), encoding="utf-8")
    start = time.perf_counter()
    corpus = from_epidoc(f)
    elapsed = time.perf_counter() - start
    assert len(corpus) == 1
    assert elapsed < 10.0, f"parse took {elapsed:.1f}s — the quadratic blowup is back"


def test_epidoc_reading_status_unchanged_by_the_linear_rewrite(tmp_path):
    """The O(n) status precompute must produce the same ReadingStatus as the old per-token
    subtree scan: supplied(undefined)/gap -> LOST, other supplied -> RESTORED, unclear ->
    UNCLEAR, else CERTAIN, with the first supplied in document order winning."""
    from aegean.core.model import ReadingStatus
    from aegean.io.epidoc import from_epidoc

    xml = (
        '<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body><div type="edition"><ab>'
        "<w>plain</w>"
        '<w><supplied reason="lost">restored</supplied></w>'
        '<w><supplied reason="undefined">conj</supplied></w>'
        "<w>dam<unclear>aged</unclear></w>"
        "<w>lac<gap/></w>"
        "</ab></div></body></text></TEI>"
    )
    f = tmp_path / "s.xml"
    f.write_text(xml, encoding="utf-8")
    docs = from_epidoc(f)
    statuses = [t.status for t in docs.get(next(iter(docs)).id).tokens]
    assert statuses == [
        ReadingStatus.CERTAIN, ReadingStatus.RESTORED, ReadingStatus.LOST,
        ReadingStatus.UNCLEAR, ReadingStatus.LOST,
    ]


# ── F1: the analysis cache hardens its file + warns on a shared dir ────────────
def test_analysis_cache_file_is_owner_only_on_posix(tmp_path):
    from aegean import cache

    path = tmp_path / "analysis-cache.sqlite"
    cache.enable(path)
    try:
        assert path.exists()  # created without error on every platform
        if os.name == "posix":
            assert (path.stat().st_mode & 0o077) == 0  # no group/other access
    finally:
        cache.disable()


@pytest.mark.skipif(os.name != "posix", reason="POSIX mode bits only")
def test_analysis_cache_warns_on_a_world_writable_dir(tmp_path):
    from aegean import cache

    shared = tmp_path / "shared"
    shared.mkdir()
    os.chmod(shared, 0o777)  # group/other writable
    cache._warned_dirs.discard(str(shared))
    with pytest.warns(UserWarning, match="writable by other users"):
        cache.enable(shared / "analysis-cache.sqlite")
    cache.disable()
