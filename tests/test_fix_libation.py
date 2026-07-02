"""Libation-word liveness regressions for the tablet-structure classifier.

Pins one fix: ``LIBATION_WORDS`` carries the a-di-ki-te family as the corpus
actually attests it. The old entry "A-DI-KI-TE-TE-DU" matched zero bundled
tokens (it is a fragment of Younger's restored reading of the damaged word on
PK Za 11, A-DI-KI-TE-TE-DU-PU-RE, not a word any inscription carries), so the
libation signal could never fire on it; PK Za 8/11/15 mis-classified as
text/list/other. The set's whole job is to match tokens of the real corpus,
so every entry is held to a liveness property here: a dead entry silently
blinds the classifier and cannot be caught by "it runs" tests. Mirrors the
workbench's shared libation list (1.6.0, src/data/libation.ts).
"""

from __future__ import annotations

from collections import Counter

import pytest

import aegean
from aegean.analysis.structure import LIBATION_WORDS, classify_structure
from aegean.core.corpus import Corpus


@pytest.fixture(scope="module")
def corpus() -> Corpus:
    return aegean.load("lineara")


@pytest.fixture(scope="module")
def token_counts(corpus: Corpus) -> Counter[str]:
    return Counter(t.text for d in corpus for t in d.tokens)


def test_every_libation_word_is_live(token_counts: Counter[str]) -> None:
    """Liveness property: every entry matches at least one bundled-corpus
    token by exact text, so no entry can silently never fire."""
    dead = {w for w in LIBATION_WORDS if token_counts[w] == 0}
    assert dead == set()


def test_attested_adikite_family_present_and_restoration_fragment_gone(
    token_counts: Counter[str],
) -> None:
    """The set carries the four attested a-di-ki-te family forms (exactly as
    the corpus writes them, subscript ₂ included) and no longer the
    unattested restoration fragment."""
    for w in (
        "A-DI-KI-TE",
        "A-DI-KI-TE-TE",
        "JA-DI-KI-TE-TE-DU-PU₂-RE",
        "JA-DI-KI-TE-TE-*307-PU₂-RE",
    ):
        assert w in LIBATION_WORDS
        assert token_counts[w] >= 1
    assert "A-DI-KI-TE-TE-DU" not in LIBATION_WORDS
    assert token_counts["A-DI-KI-TE-TE-DU"] == 0


def test_adikite_family_on_the_right_vessels(corpus: Corpus) -> None:
    """Known-answer: each family form appears on exactly the PK Za vessel
    Younger reads it on (same gold ids as the workbench test)."""
    gold = {
        "A-DI-KI-TE": ["PKZa12"],
        "A-DI-KI-TE-TE": ["PKZa11"],
        "JA-DI-KI-TE-TE-DU-PU₂-RE": ["PKZa15"],
        "JA-DI-KI-TE-TE-*307-PU₂-RE": ["PKZa8"],
    }
    for word, want_ids in gold.items():
        ids = [d.id for d in corpus if any(t.text == word for t in d.tokens)]
        assert ids == want_ids


def test_pk_za_vessels_now_classify_as_libation(corpus: Corpus) -> None:
    """Known-answer classification: the PK Za libation vessels carrying only
    an a-di-ki-te form (no A-TA-I-*301-WA-JA / JA-SA-SA-RA-ME token) signal
    libation. Before the fix: PKZa8 -> text, PKZa11 -> list,
    PKZa15 -> other."""
    for doc_id in ("PKZa8", "PKZa11", "PKZa15"):
        doc = next(d for d in corpus if d.id == doc_id)
        assert classify_structure(doc) == "libation"


def test_pkza12_still_libation(corpus: Corpus) -> None:
    """PKZa12 signalled libation before the fix too (via A-TA-I-*301-WA-JA);
    it must keep doing so now that A-DI-KI-TE also matches it."""
    doc = next(d for d in corpus if d.id == "PKZa12")
    assert classify_structure(doc) == "libation"
