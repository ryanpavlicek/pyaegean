"""Graphotactic sign-bigram surprisal (analysis.surprisal).

Ported 1:1 from the Linear A Research Workbench's ``surprisal.test.ts``.
"""

from __future__ import annotations

import math

from aegean.analysis.surprisal import train_sign_bigram_model, word_surprisal

# One dominant pattern (KU-RO-like) plus assorted support, so common vs novel
# transitions separate cleanly.
VOCAB = [
    ("KU-RO", 30),
    ("KU-RA", 10),
    ("KU-RE", 5),
    ("SA-RO", 8),
    ("SA-RA", 6),
    ("DA-RO", 4),
    ("DA-KU-RO", 3),
    ("TI", 50),  # single-sign: ignored in training
]


class TestTrain:
    def test_counts_token_weighted_with_boundaries(self) -> None:
        m = train_sign_bigram_model(VOCAB)
        assert m.bigram["KU"]["RO"] == 33  # 30 + 3 via DA-KU-RO
        assert m.bigram["^"]["KU"] == 45
        assert m.bigram["RO"]["$"] == 45
        assert "TI" not in m.bigram.get("^", {})  # single-sign contributes nothing
        assert m.cont_types["KU"] == 3  # RO, RA, RE


class TestWordSurprisal:
    def test_common_vs_novel(self) -> None:
        m = train_sign_bigram_model(VOCAB)
        common = word_surprisal(m, "KU-RO")
        novel = word_surprisal(m, "ZU-PU")  # both signs unattested
        assert common.mean < 2
        assert novel.mean > 5
        assert novel.mean > common.mean * 2

    def test_steps_include_boundaries(self) -> None:
        m = train_sign_bigram_model(VOCAB)
        r = word_surprisal(m, "DA-KU-RO")
        assert [(s.from_, s.to) for s in r.steps] == [
            ("^", "DA"),
            ("DA", "KU"),
            ("KU", "RO"),
            ("RO", "$"),
        ]
        assert all(s.bits >= 0 for s in r.steps)

    def test_leave_one_out_removes_self_support(self) -> None:
        m = train_sign_bigram_model(VOCAB)
        with_self = word_surprisal(m, "DA-KU-RO", 0)
        loo = word_surprisal(m, "DA-KU-RO", 3)
        assert loo.mean > with_self.mean

        def da_ku(r: object) -> float:
            return next(s.bits for s in r.steps if s.from_ == "DA" and s.to == "KU")  # type: ignore[attr-defined]

        assert da_ku(loo) > da_ku(with_self) + 1
        # KU->RO keeps outside support (KU-RO's 30 tokens), so it stays cheap.
        ku_ro = next(s for s in loo.steps if s.from_ == "KU" and s.to == "RO")
        assert ku_ro.bits < 2

    def test_leave_one_out_is_per_occurrence(self) -> None:
        # A word whose only structure is a repeated bigram, and the sole corpus
        # source of it. Per-occurrence LOO must remove ALL its self-support.
        vocab = [("PI-RE-PI-RE", 4), ("KU-RO", 30), ("SA-RO", 8)]
        model = train_sign_bigram_model(vocab)
        assert model.bigram["PI"]["RE"] == 8  # 2 per word * 4 tokens
        loo = word_surprisal(model, "PI-RE-PI-RE", 4)
        pi_re = next(s for s in loo.steps if s.from_ == "PI" and s.to == "RE")
        # all self-support removed -> highly surprising
        assert pi_re.bits > 4

    def test_valid_under_heavy_exclusion(self) -> None:
        m = train_sign_bigram_model(VOCAB)
        r = word_surprisal(m, "KU-RO", 9999)
        for s in r.steps:
            assert math.isfinite(s.bits)
            assert s.bits >= 0

    def test_deterministic(self) -> None:
        m = train_sign_bigram_model(VOCAB)
        assert word_surprisal(m, "SA-RA", 6) == word_surprisal(m, "SA-RA", 6)
