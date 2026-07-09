"""Genre-sliced UD evaluation (aegean.greek.ud.evaluate_by_genre) and the author→genre map.

The map + sentence-id parsing are pure/offline; the end-to-end slice runs the official evaluator
on a synthetic two-genre fold (skips offline, the same pattern as test_evaluate_on_ud_against_fixture).
The real leakage-clean Perseus test fold is a single prose author (Athenaeus, tlg0008) — a documented
finding, not an assertion here; this test only proves the bucketing/scoring machinery is correct."""

from __future__ import annotations

from pathlib import Path

import pytest

from aegean.greek.ud import _sent_genre, evaluate_by_genre


def test_author_genre_map_and_sent_id_parsing() -> None:
    assert _sent_genre("tlg0012.tlg001.perseus-grc1.tb.xml@197") == ("tlg0012", "epic")   # Homer
    assert _sent_genre("tlg0011.tlg004.perseus-grc1.tb.xml@5") == ("tlg0011", "tragedy")  # Sophocles
    assert _sent_genre("tlg0008.tlg001.perseus-grc1.tb.xml@1") == ("tlg0008", "prose")    # Athenaeus
    assert _sent_genre("tlg9999.tlg001.tb.xml@1") == ("tlg9999", "other")                 # unmapped
    assert _sent_genre("bare-id-no-at") == ("bare-id-no-at", "other")


_EPIC = (
    "# sent_id = tlg0012.tlg001.tb.xml@1\n"
    "# text = μῆνιν ἄειδε θεά\n"
    "1\tμῆνιν\tμῆνις\tNOUN\t_\t_\t2\tobj\t_\t_\n"
    "2\tἄειδε\tἀείδω\tVERB\t_\t_\t0\troot\t_\t_\n"
    "3\tθεά\tθεά\tNOUN\t_\t_\t2\tvocative\t_\t_\n\n"
)
_PROSE = (
    "# sent_id = tlg0008.tlg001.tb.xml@1\n"
    "# text = ὁ λόγος ἦν\n"
    "1\tὁ\tὁ\tDET\t_\t_\t2\tdet\t_\t_\n"
    "2\tλόγος\tλόγος\tNOUN\t_\t_\t3\tnsubj\t_\t_\n"
    "3\tἦν\tεἰμί\tVERB\t_\t_\t0\troot\t_\t_\n\n"
)


def test_evaluate_by_genre_buckets_and_scores(tmp_path: Path) -> None:
    """End-to-end through the official evaluator on a two-genre fold (skips offline)."""
    from aegean.data import cache_dir
    from aegean.greek.ud import _CACHE_SUBDIR

    if not (cache_dir() / _CACHE_SUBDIR / "conll18_ud_eval.py").exists():
        try:
            from aegean.greek.ud import _eval_module

            _eval_module()
        except Exception as exc:
            pytest.skip(f"official evaluator unavailable offline: {exc}")

    fold = tmp_path / "mixed.conllu"
    fold.write_text(_EPIC + _PROSE, encoding="utf-8")
    res = evaluate_by_genre("perseus", "test", source=fold, parse=False, bootstrap=False, min_sentences=1)

    assert set(res) == {"epic", "prose", "_unmapped"}
    assert res["_unmapped"]["authors"] == []          # both authors are mapped
    assert res["epic"]["n_sentences"] == 1 and res["epic"]["n_words"] == 3
    assert res["prose"]["authors"] == ["tlg0008"]
    assert res["epic"]["thin"] is False               # min_sentences=1
    for g in ("epic", "prose"):
        assert 0.0 <= res[g]["upos"] <= 1.0 and 0.0 <= res[g]["lemma"] <= 1.0
        assert "uas" not in res[g] and "las" not in res[g]   # parse=False drops syntax metrics


def test_evaluate_by_genre_flags_thin_buckets(tmp_path: Path) -> None:
    from aegean.data import cache_dir
    from aegean.greek.ud import _CACHE_SUBDIR

    if not (cache_dir() / _CACHE_SUBDIR / "conll18_ud_eval.py").exists():
        try:
            from aegean.greek.ud import _eval_module

            _eval_module()
        except Exception as exc:
            pytest.skip(f"official evaluator unavailable offline: {exc}")

    fold = tmp_path / "one.conllu"
    fold.write_text(_PROSE, encoding="utf-8")
    res = evaluate_by_genre("perseus", "test", source=fold, parse=False, bootstrap=False, min_sentences=20)
    assert res["prose"]["thin"] is True   # 1 sentence < min_sentences → flagged thin (wide/unreliable)
