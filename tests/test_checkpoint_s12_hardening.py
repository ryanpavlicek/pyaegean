"""Regression tests for §12 public inputs, tar extraction, and clause-omission accounting."""

from __future__ import annotations

import io
import json
import pathlib
import tarfile

import pytest

from aegean import data
from aegean.ai._translation_fidelity import audit_clause_checks
from aegean.data import DataNotAvailableError
from aegean.scripts.greek import perseus


@pytest.mark.parametrize(
    "bad_work",
    [
        "tlg0012.tlg001?ref=evil",
        "tlg0012.tlg001#frag",
        "tlg0012.tlg001&x=1",
        "tlg0012.tlg 001",
        "tlg0012.tlg%2f001",
        "../evil.tlg001",
        "tlg0012/tlg001.tlg002",
    ],
)
def test_perseus_work_dir_rejects_url_and_path_injection(bad_work: str) -> None:
    with pytest.raises(ValueError):
        perseus._work_dir(bad_work)


def test_perseus_github_listing_writes_atomically_and_encodes_ref(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen_urls: list[str] = []

    class _Resp:
        def __enter__(self) -> _Resp:
            return self

        def __exit__(self, *_a: object) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps([{"name": "tlg0012.tlg001.perseus-grc2.xml"}]).encode("utf-8")

    def _fake_urlopen(req: object, timeout: int = 30) -> _Resp:
        seen_urls.append(getattr(req, "full_url"))
        return _Resp()

    monkeypatch.setenv("PYAEGEAN_CACHE", str(tmp_path))
    monkeypatch.setattr(perseus.urllib.request, "urlopen", _fake_urlopen)

    names = perseus._github_listing("o/r", "data/tlg0012/tlg001", "ref with space")
    assert names == ["tlg0012.tlg001.perseus-grc2.xml"]
    assert "ref=ref%20with%20space" in seen_urls[0]
    listing_dir = perseus.cache_dir() / "greek-works" / "listings"
    files = list(listing_dir.glob("*.json"))
    assert len(files) == 1
    assert json.loads(files[0].read_text(encoding="utf-8")) == names


def test_safe_extract_tar_rejects_absolute_and_unknown_member_types(tmp_path: pathlib.Path) -> None:
    abs_tar = tmp_path / "abs.tar.gz"
    with tarfile.open(abs_tar, "w:gz") as tf:
        info = tarfile.TarInfo("/etc/evil.txt")
        blob = b"x"
        info.size = len(blob)
        tf.addfile(info, io.BytesIO(blob))
    with pytest.raises(DataNotAvailableError, match="unsafe path"):
        data._safe_extract_tar(abs_tar, tmp_path / "out_abs")

    exotic_tar = tmp_path / "exotic.tar.gz"
    with tarfile.open(exotic_tar, "w:gz") as tf:
        info = tarfile.TarInfo("weird")
        info.type = tarfile.CHRTYPE
        tf.addfile(info)
    with pytest.raises(DataNotAvailableError, match="unsafe special file"):
        data._safe_extract_tar(exotic_tar, tmp_path / "out_exotic")


def test_clause_audit_distinguishes_explicit_omission_from_unaccounted_source() -> None:
    row_aligned = {
        "source": {"text": "λέγω", "occurrence": 1},
        "translation": {"text": "I speak", "occurrence": 1},
        "checks": {
            "roles": "preserved", "negation": "not_applicable",
            "qualifications": "preserved", "speech_act": "preserved",
        },
        "finding": "Main verb preserved.",
        "evidence_refs": [],
    }
    row_omitted = {
        "source": {"text": "· οὐ φεύγω", "occurrence": 1},
        "translation": None,
        "checks": {
            "roles": "concern", "negation": "concern",
            "qualifications": "not_applicable", "speech_act": "concern",
        },
        "finding": "Negated second clause is omitted from the translation.",
        "evidence_refs": [],
    }
    result = audit_clause_checks(
        [row_aligned, row_omitted],
        source="λέγω· οὐ φεύγω",
        translation="I speak",
        evidence_refs=(),
    )
    # Unresolved omission stays visible via status='incomplete' and explicit issue.
    assert result["clause_check_status"] == "incomplete"
    val = result["clause_check_validation"]
    assert any("explicit omission" in issue for issue in val["issues"])
    # Source is fully accounted for (aligned + explicitly omitted), while still uncovered in translation alignment.
    assert val["source_unaccounted_spans"] == []
    assert val["omitted_source_spans"] == [
        {"index": 1, "start": 4, "end": 14, "text": "· οὐ φεύγω"},
    ]
    assert val["source_uncovered_spans"] == [
        {"start": 4, "end": 14, "text": "· οὐ φεύγω"},
    ]
    assert val["translation_uncovered_spans"] == []
