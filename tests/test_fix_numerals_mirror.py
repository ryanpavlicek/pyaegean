"""Aegean-numerals fixes mirrored from the Linear A Workbench, pinned on the
shared bundled corpus:

1. **KU-RA is a total marker.** KU-RA (ZA20, ARKH2) is read as a variant of
   KU-RO and closes a list the same way, so its lines now yield balance checks.
   Matching is exact per lexeme: HT117a's KU-RA-MU is a different word and must
   not be swallowed.
2. **Approximate readings parse at the editor's value.** An "≈ ¹⁄₆"-style token
   is the editor's estimated reading of a damaged or unclear quantity; the ≈ is
   editorial apparatus and is not propagated, so the value sums at face value.
   Previously all 29 such tokens in the bundled corpus classified UNKNOWN and
   silently dropped out of every accounting sum they feed. A bare "≈" (nothing
   legible after it) is still not a value.
3. **Corpus-wide accounting figures** (the numbers README / wiki publish):
   35 -> 37 tablets with a checkable total, 39 -> 41 total lines, 8 still
   balance exactly.
"""

import collections

import pytest

import aegean
from aegean.analysis import balance_check
from aegean.analysis.accounting import checkable_accounts
from aegean.core.corpus import Corpus
from aegean.core.model import ReadingStatus, TokenKind
from aegean.core.numerals import (
    is_value_token,
    line_value,
    markers_for,
    parse_value,
)
from aegean.scripts.lineara.loader import classify


@pytest.fixture(scope="module")
def corpus() -> Corpus:
    return aegean.load("lineara")


# ── 1. approximate (≈) readings parse at the editor's value ──────────────────


def test_parse_value_approximate_readings() -> None:
    assert parse_value("≈ ¹⁄₆") == pytest.approx(1 / 6)
    assert parse_value("≈ ¹⁄₄") == pytest.approx(0.25)
    assert parse_value("≈5") == 5  # no space after the qualifier
    assert is_value_token("≈ ¹⁄₆")
    # a bare ≈ (nothing legible after it) is still not a value
    assert parse_value("≈") is None
    assert parse_value("≈ ") is None
    assert not is_value_token("≈")
    # the qualifier is a prefix convention: ≈ elsewhere is not a numeral form
    assert parse_value("5≈") is None
    # a non-numeral reading stays non-numeral even when ≈-prefixed
    assert parse_value("≈ KU-RO") is None


def test_classify_approximate_fraction_is_numeral() -> None:
    tok = classify("≈ ¹⁄₆", 0, 0)
    assert tok.kind is TokenKind.NUMERAL
    assert tok.status is ReadingStatus.CERTAIN
    # bare ≈ carries no reading to classify
    assert classify("≈", 0, 0).kind is TokenKind.UNKNOWN


def test_corpus_fraction_tokens_all_classify_numeral(corpus: Corpus) -> None:
    """All 320 built-up-fraction tokens (U+2044) classify NUMERAL; the 29
    ≈-prefixed ones no longer fall out as UNKNOWN."""
    frac = [t for d in corpus for t in d.tokens if "⁄" in t.text]
    assert len(frac) == 320
    assert all(t.kind is TokenKind.NUMERAL for t in frac)
    approx_readings = [
        t for d in corpus for t in d.tokens
        if t.text.startswith("≈") and t.text.strip() != "≈"
    ]
    assert len(approx_readings) == 29
    assert all(t.kind is TokenKind.NUMERAL for t in approx_readings)
    # the 8 bare-≈ tokens stay valueless apparatus
    bare = [t for d in corpus for t in d.tokens if t.text.strip() == "≈"]
    assert len(bare) == 8
    assert all(t.kind is TokenKind.UNKNOWN for t in bare)


def test_ht93b_approximate_fraction_joins_line_sum(corpus: Corpus) -> None:
    """HT93b line 1 reads "165 ≈ ¹⁄₆": the estimated sixth used to be silently
    dropped, understating the quantity to a flat 165."""
    doc = corpus.get("HT93b")
    first = [doc.tokens[i].text for i in doc.lines[0]]
    assert first == ["165", "≈ ¹⁄₆"]
    assert line_value(first) == pytest.approx(165 + 1 / 6)


def test_ht123_124a_approximate_quantities_feed_accounting(corpus: Corpus) -> None:
    """HT123+124a carries ≈-fractions on both an item line and a stated total."""
    doc = corpus.get("HT123+124a")
    item = [doc.tokens[i].text for i in doc.lines[7]]
    assert item == ["*308", "4", "≈ ¹⁄₆"]
    assert line_value(item) == pytest.approx(4 + 1 / 6)
    checks = balance_check(doc)
    assert len(checks) == 2
    # first KU-RO (line 12): eight items sum to 31 + 8¼ + 31½ + 8¾ + 16 + 4⅙
    # + 15 + 4¼ = 118 + 11/12 (KI-RO deficit lines excluded)
    assert checks[0].total_line_index == 12
    assert checks[0].stated_total == pytest.approx(93.5)
    assert checks[0].item_count == 8
    assert checks[0].computed_sum == pytest.approx(118 + 11 / 12)
    # second KU-RO (line 14) states "25 ≈ ¹⁄₆" = 25⅙
    assert checks[1].total_line_index == 14
    assert checks[1].stated_total == pytest.approx(25 + 1 / 6)


def test_ht123_124b_approximate_only_line_becomes_an_item(corpus: Corpus) -> None:
    """HT123+124b line 9 ("SI-DU ≈ ¹⁄₆") had no countable numeral before; the
    estimated sixth now makes it an item line."""
    doc = corpus.get("HT123+124b")
    assert [doc.tokens[i].text for i in doc.lines[8]] == ["SI-DU", "≈ ¹⁄₆"]
    (check,) = balance_check(doc)
    assert check.item_count == 8  # was 7 without the ≈-only line
    # 11 + 1¾ + 4 + 1 + 10 + 13/20 + ⅙ + ⅜
    assert check.computed_sum == pytest.approx(28.775 + 1 / 6)
    assert not check.balances


# ── 2. KU-RA joins the total markers ─────────────────────────────────────────


def test_kura_is_a_lineara_total_marker() -> None:
    markers = markers_for("lineara")
    assert markers.total == frozenset({"KU-RO", "KU-RA"})
    assert markers.is_total("KU-RA")
    assert markers.is_total("ku-ra")  # case-insensitive like the rest
    # exact lexeme match only: HT117a's KU-RA-MU is a different word
    assert not markers.is_total("KU-RA-MU")


def test_za20_kura_line_yields_a_balance_check(corpus: Corpus) -> None:
    """ZA20 closes with "KU-RA 130"; the surviving items sum to
    4 + 1 + 6 + 12 + 3 = 26 (the tablet is broken at both ends)."""
    (check,) = balance_check(corpus.get("ZA20"))
    assert check.marker == "KU-RA"
    assert check.stated_total == 130
    assert check.computed_sum == 26
    assert check.item_count == 5
    assert not check.balances


def test_arkh2_leading_kura_yields_an_empty_section_check(corpus: Corpus) -> None:
    """ARKH2's KU-RA heads its list, so nothing precedes it: under this
    module's sectioning convention (every stated total yields a check, like the
    six pre-existing zero-item KU-RO checks) it reports an unverifiable
    zero-item section rather than balancing."""
    (check,) = balance_check(corpus.get("ARKH2"))
    assert check.marker == "KU-RA"
    assert check.stated_total == 5
    assert check.item_count == 0
    assert check.computed_sum == 0
    assert not check.balances


def test_ht117a_kura_mu_not_swallowed_by_kura(corpus: Corpus) -> None:
    """HT117a contains the word KU-RA-MU; its accounting must be untouched by
    the KU-RA marker (its one KU-RO check still balances 10 = 10)."""
    (check,) = balance_check(corpus.get("HT117a"))
    assert check.marker == "KU-RO"
    assert check.stated_total == check.computed_sum == 10
    assert check.balances


# ── 3. the corpus-wide figures the docs publish ───────────────────────────────


def test_corpus_wide_balance_figures(corpus: Corpus) -> None:
    """The recount behind README / wiki: 37 tablets carry a checkable total
    (41 total lines); 8 lines balance exactly; KU-RA adds exactly the ZA20 and
    ARKH2 checks and flips no other tablet."""
    tablets = checks_n = balanced = 0
    markers_seen: collections.Counter[str] = collections.Counter()
    kura_docs = []
    for doc in corpus:
        checks = balance_check(doc)
        if checks:
            tablets += 1
        checks_n += len(checks)
        for check in checks:
            markers_seen[check.marker] += 1
            if check.balances:
                balanced += 1
            if check.marker == "KU-RA":
                kura_docs.append(doc.id)
    assert tablets == 37
    assert checks_n == 41
    assert balanced == 8
    assert markers_seen == {"KU-RO": 37, "PO-TO-KU-RO": 2, "KU-RA": 2}
    assert sorted(kura_docs) == ["ARKH2", "ZA20"]


def test_checkable_accounts_membership_unchanged(corpus: Corpus) -> None:
    """The intact-and-balancing filter (the wiki's "7") is unaffected: neither
    KU-RA tablet balances and no ≈-bearing tablet flips within tolerance."""
    assert [d.id for d in checkable_accounts(corpus)] == [
        "HT9a", "HT9b", "HT11b", "HT13", "HT89", "HT94b", "HT117a",
    ]
