"""EpiDoc builder conformance battery.

One parametrized suite that runs EVERY epigraphy corpus builder's extraction configuration
against a shared battery of hostile / edge TEI fixtures and asserts the project's extraction
conventions PER BUILDER. The point is drift-resistance: the TEI-``<choice>`` fusion bug shipped
for about a year (fixed in 0.39.0) because no battery ran the same fixtures through every sibling
builder. If a convention change lands on one builder but misses a sibling, or if a fixed regression
returns, a case here fails in the same commit.

What is under test
------------------
Six builders, whose extraction entry points are imported straight from ``scripts/`` (the shipped
release assets are never re-downloaded; this exercises the code paths):

* ``build_isicily_corpus`` / ``build_iip_corpus`` / ``build_iospe_corpus`` / ``build_igcyr_corpus``
  all resolve ``<choice>`` through the ONE shared extractor ``_epidoc.edition_tokens(...,
  choice_prefer=True)`` (expansion > regularization > correction), grouped here as
  ``epidoc_choice``.
* ``build_edh_corpus`` uses the same shared extractor and then additionally resolves EDH's
  ``#``-joined parallel word-forms into one reading plus alternates (``resolve_inline_variants``),
  grouped as ``edh`` (identical to ``epidoc_choice`` on every fixture that has no ``#``).
* ``build_ddbdp_corpus`` has its OWN walker with the papyrological apparatus policy
  (``<reg>``/``<lem>``/``<add>`` preferred), grouped as ``ddbdp``.

The parametrization documents the sharing explicitly: ``test_shared_extractor_identity`` asserts the
five inscription builders reference the SAME function object, so a future inline-fork of
``edition_tokens`` into one builder breaks the identity assertion and forces whoever forked it to add
a new parametrization group with its own expected outputs.

Two divergences the battery pins are CURRENT-behavior gaps, reported to the humans (see the
``test_gap_*`` cases): the shared inscription extractor drops the ``<abbr>`` letters inside
``<expan>`` (keeping only ``<ex>``) where DDbDP keeps the whole expansion, and it has no ``<subst>``
handling so it FUSES ``<add>``+``<del>`` (the same fuse-class the ``<choice>`` fix removed). These are
pinned as-is so that a later fix turns the pin red on purpose.
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

# The builders need only aegean.core (zero-dep); skip cleanly if the package is unavailable.
pytest.importorskip("aegean")

_REPO = Path(__file__).resolve().parent.parent
for _p in (_REPO / "scripts", _REPO / "src"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import _epidoc  # noqa: E402
import build_ddbdp_corpus as _ddbdp  # noqa: E402
import build_edh_corpus as _edh  # noqa: E402
import build_igcyr_corpus as _igcyr  # noqa: E402
import build_iip_corpus as _iip  # noqa: E402
import build_iospe_corpus as _iospe  # noqa: E402
import build_isicily_corpus as _isicily  # noqa: E402

_FIX_DIR = Path(__file__).resolve().parent / "fixtures" / "epidoc_conformance"

# ReadingStatus.value strings, for terse expected tables.
C, U, R, L = "certain", "unclear", "restored", "lost"


def _edition(name: str) -> ET.Element:
    """Parse a fixture file and return its ``<div type="edition">`` root element."""
    return ET.parse(str(_FIX_DIR / f"{name}.xml")).getroot()


# ── the six builder extraction configs ───────────────────────────────────────────
# Each extract fn returns list[list[tuple[text, status_value]]] so a builder's output is
# compared token-for-token, status included. The inscription builders reference their OWN
# module's ``edition_tokens`` symbol (which is the shared _epidoc function) so an inline-fork
# would change the callable this parametrization actually exercises.


def _shared_extract(module: object):
    def extract(edition: ET.Element) -> list[list[tuple[str, str]]]:
        return [
            [(w, s.value) for w, s in line]
            for line in module.edition_tokens(edition, choice_prefer=True)  # type: ignore[attr-defined]
        ]

    return extract


def _edh_extract(edition: ET.Element) -> list[list[tuple[str, str]]]:
    # EDH: the shared choice-aware tokens, then '#'-variant resolution to the primary reading
    # (the alternates go to Token.alt, checked separately in the focused edh test below).
    out: list[list[tuple[str, str]]] = []
    for line in _edh.edition_tokens(edition, choice_prefer=True):
        out.append([(_edh.resolve_inline_variants(w)[0], s.value) for w, s in line])
    return out


def _ddbdp_extract(edition: ET.Element) -> list[list[tuple[str, str]]]:
    return [[(w, s.value) for w, s in line] for line in _ddbdp.edition_tokens(edition)]


# (builder_id, expected-group, extract_fn)
_BUILDERS = [
    ("isicily", "epidoc_choice", _shared_extract(_isicily)),
    ("iip", "epidoc_choice", _shared_extract(_iip)),
    ("iospe", "epidoc_choice", _shared_extract(_iospe)),
    ("igcyr", "epidoc_choice", _shared_extract(_igcyr)),
    ("edh", "edh", _edh_extract),
    ("ddbdp", "ddbdp", _ddbdp_extract),
]

# A group with no explicit expected for a fixture falls back to this group's expected.
_GROUP_FALLBACK = {"edh": "epidoc_choice"}


# ── the fixture battery ──────────────────────────────────────────────────────────
# Expected token sequences (text, status) per group. Every value was verified against the live
# extractors. ``forbidden`` lists readings that must NEVER appear in ANY builder's output for that
# fixture (discarded apparatus members and fused concatenations): the never-fuse invariant.
_FIXTURES: dict[str, dict] = {
    # (1) choice corr/sic -> the corrected member; the sic is dropped, never fused.
    "choice_corr_sic": {
        "epidoc_choice": [[("ὁ", C), ("δῆμος", C), ("ἔδωκε", C)]],
        "ddbdp": [[("ὁ", C), ("δῆμος", C), ("ἔδωκε", C)]],
        "forbidden": ["δημος", "δῆμοςδημος", "δημοςδῆμος"],
    },
    # (2) choice reg/orig -> the regularized member.
    "choice_reg_orig": {
        "epidoc_choice": [[("ἐν", C), ("πόλει", C), ("ἦν", C)]],
        "ddbdp": [[("ἐν", C), ("πόλει", C), ("ἦν", C)]],
        "forbidden": ["πολει", "πόλειπολει", "πολειπόλει"],
    },
    # (3) choice expan/abbr -> the expansion member (plain text: both paths agree).
    "choice_expan_abbr": {
        "epidoc_choice": [[("Λούκιος", C), ("ἦλθε", C)]],
        "ddbdp": [[("Λούκιος", C), ("ἦλθε", C)]],
        "forbidden": ["ΛούκιοςΛ", "ΛΛούκιος"],
    },
    # (4) choice under supplied (RESTORED) and under unclear (UNCLEAR): status inherits into the
    # chosen member (the 0.39.0 behavior).
    "status_inheritance": {
        "epidoc_choice": [[("δήμου", R), ("βουλή", U)]],
        "ddbdp": [[("δήμου", R), ("βουλή", U)]],
        "forbidden": ["δημου", "βουλη", "δήμουδημου", "βουλήβουλη"],
    },
    # (5) supplied reason="undefined" -> LOST.
    "supplied_undefined_lost": {
        "epidoc_choice": [[("ὁ", C), ("σοφός", L), ("ἀνήρ", C)]],
        "ddbdp": [[("ὁ", C), ("σοφός", L), ("ἀνήρ", C)]],
    },
    # (6) unclear -> UNCLEAR.
    "unclear": {
        "epidoc_choice": [[("τὸ", C), ("ἔργον", U)]],
        "ddbdp": [[("τὸ", C), ("ἔργον", U)]],
    },
    # (7) lb break="no": a word split across a line rejoins to ONE token on ONE line.
    "lb_break_no_join": {
        "epidoc_choice": [[("Ἀλεξάνδρου", C)]],
        "ddbdp": [[("Ἀλεξάνδρου", C)]],
    },
    # (8) plain lb: a new physical line.
    "plain_lb_newline": {
        "epidoc_choice": [[("πρῶτος", C)], [("δεύτερος", C)]],
        "ddbdp": [[("πρῶτος", C)], [("δεύτερος", C)]],
    },
    # (9) gap + g (with its symbol) + space are skipped from the reading text.
    "skip_symbols": {
        "epidoc_choice": [[("ἀγαθὸς", C), ("τύχη", C)]],
        "ddbdp": [[("ἀγαθὸς", C), ("τύχη", C)]],
        "forbidden": ["☙"],
    },
    # (10) app with lem+rdg and a rdg-only app. DIVERGENCE: the inscription extractor drops the
    # whole <app>; the DDbDP walker keeps the <lem>. A <rdg> reading appears in neither.
    "app_lem_rdg": {
        "epidoc_choice": [[("μὲν", C), ("δέ", C), ("καί", C)]],
        "ddbdp": [[("μὲν", C), ("οὖν", C), ("δέ", C), ("καί", C)]],
        "forbidden": ["γάρ", "τε", "οὖνγάρ", "γάροὖν"],
    },
    # (11) the fuse canary: only the corrected member survives; the sic and any concatenation must
    # never appear (the regression that shipped for a year and must never return).
    "no_fuse_canary": {
        "epidoc_choice": [[("δῆμος", C)]],
        "ddbdp": [[("δῆμος", C)]],
        "forbidden": ["τυπος", "δῆμοςτυπος", "τυποςδῆμος"],
    },
    # (12) <head> (the EDH "Text" heading) is skipped, not emitted as a stray token.
    "head_skipped": {
        "epidoc_choice": [[("Διονύσιος", C)]],
        "ddbdp": [[("Διονύσιος", C)]],
        "forbidden": ["Text"],
    },
    # DIVERGENCE / GAP: <expan><abbr>..</abbr><ex>..</ex></expan>. The inscription extractor drops
    # the <abbr> letters on the stone and keeps only <ex> ("μὰς"); DDbDP keeps the whole
    # expansion ("δραχμὰς"). See test_gap_shared_extractor_drops_abbr_inside_expan.
    "expan_ex_inner": {
        "epidoc_choice": [[("μὰς", C), ("τρεῖς", C)]],
        "ddbdp": [[("δραχμὰς", C), ("τρεῖς", C)]],
    },
    # DIVERGENCE / GAP: <subst><add>..</add><del>..</del></subst>. The inscription extractor has no
    # <subst> handling and FUSES add+del ("ταῦτατουτο"); DDbDP picks <add> ("ταῦτα"). Pinned as
    # current behavior. See test_gap_shared_extractor_fuses_subst_add_del.
    "subst_add_del": {
        "epidoc_choice": [[("ταῦτατουτο", C), ("ἔστω", C)]],
        "ddbdp": [[("ταῦτα", C), ("ἔστω", C)]],
    },
    # DIVERGENCE: EDH '#'-joined parallel forms. Only the EDH build resolves them to one reading;
    # the other builders leave the '#' literal in the token text.
    "edh_hash_variants": {
        "epidoc_choice": [[("πέμπτης#πέμπτης#πέΝπτης", C), ("καλός", C)]],
        "edh": [[("πέμπτης", C), ("καλός", C)]],
        "ddbdp": [[("πέμπτης#πέμπτης#πέΝπτης", C), ("καλός", C)]],
    },
}


def _expected_for(fixture: dict, group: str):
    if group in fixture:
        return fixture[group]
    fallback = _GROUP_FALLBACK.get(group)
    return fixture.get(fallback) if fallback else None


@pytest.mark.parametrize("builder", _BUILDERS, ids=[b[0] for b in _BUILDERS])
@pytest.mark.parametrize("fixture_name", list(_FIXTURES), ids=list(_FIXTURES))
def test_builder_conformance(fixture_name: str, builder: tuple) -> None:
    """Every builder extraction config, on every fixture, produces the exact token/status sequence
    its group pins, and never emits a discarded apparatus member or a fused concatenation."""
    builder_id, group, extract = builder
    fixture = _FIXTURES[fixture_name]
    expected = _expected_for(fixture, group)
    assert expected is not None, (
        f"no expected output for group {group!r} on fixture {fixture_name!r}: a builder or fork "
        f"was added without pinning its behavior on this fixture"
    )

    actual = extract(_edition(fixture_name))
    assert actual == expected, f"{builder_id} / {fixture_name}: {actual!r} != {expected!r}"

    # The never-fuse invariant: discarded members and fused concatenations appear in no token.
    tokens = [t for line in actual for (t, _status) in line]
    for bad in fixture.get("forbidden", []):
        assert all(bad != t for t in tokens), (
            f"{builder_id} / {fixture_name}: discarded reading {bad!r} survived as a token"
        )
        assert all(bad not in t for t in tokens), (
            f"{builder_id} / {fixture_name}: fused reading {bad!r} appears inside a token"
        )


# ── the sharing / inline-fork tripwire ───────────────────────────────────────────


def test_shared_extractor_identity() -> None:
    """The four inscription builders and EDH all reference the ONE shared ``edition_tokens``.

    If a builder inline-forks its own copy (as the r33 wave did for the corpus DRIVERS, but NOT for
    the extractor itself), this identity breaks. Whoever forks must then add the fork as a new
    ``_BUILDERS`` group with its own expected outputs, which is exactly the drift this battery
    exists to force into the same commit."""
    assert _isicily.edition_tokens is _epidoc.edition_tokens
    assert _iip.edition_tokens is _epidoc.edition_tokens
    assert _iospe.edition_tokens is _epidoc.edition_tokens
    assert _igcyr.edition_tokens is _epidoc.edition_tokens
    assert _edh.edition_tokens is _epidoc.edition_tokens
    assert _edh.resolve_inline_variants is _epidoc.resolve_inline_variants


def test_ddbdp_has_its_own_extractor() -> None:
    """DDbDP deliberately does NOT share the inscription extractor (papyri carry a heavier
    apparatus), so it is its own group. If it ever collapses onto the shared one, its distinct
    apparatus expectations here would be silently wrong, so the divergence is asserted."""
    assert _ddbdp.edition_tokens is not _epidoc.edition_tokens


# ── the convention DOC pin ───────────────────────────────────────────────────────


def test_epidoc_docstring_states_choice_preference_policy() -> None:
    """The stated preference policy (expansion > regularization > correction) matches the observed
    behavior. If the policy constant changes, this and the fixtures move together."""
    assert _epidoc._CHOICE_PREFER == ("expan", "reg", "corr")
    pref_doc = _epidoc._preferred_choice.__doc__ or ""
    for keyword in ("expan", "reg", "corr"):
        assert keyword in pref_doc, f"{keyword!r} missing from _preferred_choice docstring"
    # the fuse rationale and the opt-in flag are documented on the extractor itself
    ext_doc = _epidoc.edition_tokens.__doc__ or ""
    assert "choice_prefer" in ext_doc


def test_ddbdp_docstring_states_apparatus_preference_policy() -> None:
    """The DDbDP walker's stated policy (reg>orig, corr>sic, lem>rdg, add>del) matches its
    ``_CHOICE_ORDER`` and module docstring."""
    assert _ddbdp._CHOICE_ORDER[:3] == ("reg", "corr", "expan")
    module_doc = _ddbdp.__doc__ or ""
    for keyword in ("reg", "orig", "corr", "sic", "lem", "rdg", "add", "del"):
        assert keyword in module_doc, f"{keyword!r} missing from build_ddbdp_corpus module docstring"


# ── focused edge cases the parametrized matrix leaves implicit ─────────────────────


def test_choice_prefer_false_still_fuses_documenting_the_bug() -> None:
    """The historical default (``choice_prefer=False``) STILL fuses both members. This pins that
    the flag every builder passes is what prevents the regression, so flipping the default or
    dropping the flag would surface here immediately."""
    edition = _edition("no_fuse_canary")
    fused = [w for line in _epidoc.edition_tokens(edition, choice_prefer=False) for w, _ in line]
    assert fused == ["δῆμοςτυπος"]
    resolved = [w for line in _epidoc.edition_tokens(edition, choice_prefer=True) for w, _ in line]
    assert resolved == ["δῆμος"]


def test_edh_hash_variant_resolution_yields_primary_and_alternate() -> None:
    """EDH resolves a '#'-joined form to one primary reading plus its distinct alternates, and the
    sibling inscription builders (which do not call resolve_inline_variants) leave the '#' literal
    (the divergence that makes EDH its own group)."""
    edition = _edition("edh_hash_variants")
    resolved = [
        _edh.resolve_inline_variants(w)
        for line in _edh.edition_tokens(edition, choice_prefer=True)
        for w, _ in line
    ]
    assert ("πέμπτης", ("πέΝπτης",)) in resolved
    assert ("καλός", ()) in resolved
    shared_words = [w for line in _epidoc.edition_tokens(edition, choice_prefer=True) for w, _ in line]
    assert "πέμπτης#πέμπτης#πέΝπτης" in shared_words


def test_gap_shared_extractor_drops_abbr_inside_expan() -> None:
    """GAP (reported in gaps_found): the shared inscription extractor drops the ``<abbr>`` letters
    inside ``<expan>`` and keeps only ``<ex>``, so ``<expan><abbr>δραχ</abbr><ex>μὰς</ex></expan>``
    reads ``μὰς`` (the letters actually on the stone are lost) while DDbDP keeps the whole
    expansion ``δραχμὰς``. Sibling builders disagree on the SAME construct. Pinned as CURRENT
    behavior; a fix that keeps the abbr will turn this red on purpose and force a corpus rebuild."""
    edition = _edition("expan_ex_inner")
    shared_first = _epidoc.edition_tokens(edition, choice_prefer=True)[0][0][0]
    ddbdp_first = _ddbdp.edition_tokens(edition)[0][0][0]
    assert shared_first == "μὰς"  # abbr "δραχ" dropped (the gap)
    assert ddbdp_first == "δραχμὰς"  # DDbDP keeps the whole expansion


def test_gap_shared_extractor_fuses_subst_add_del() -> None:
    """GAP (reported in gaps_found): the shared inscription extractor has no ``<subst>`` handling,
    so ``<subst><add>ταῦτα</add><del>τουτο</del></subst>`` FUSES to ``ταῦτατουτο``, the same
    fuse-class the 0.39.0 ``<choice>`` fix eliminated, still live for ``<subst>`` in
    isicily/iip/iospe/igcyr/edh. DDbDP picks ``<add>`` (``ταῦτα``). Pinned as CURRENT behavior."""
    edition = _edition("subst_add_del")
    shared_first = _epidoc.edition_tokens(edition, choice_prefer=True)[0][0][0]
    ddbdp_first = _ddbdp.edition_tokens(edition)[0][0][0]
    assert shared_first == "ταῦτατουτο"  # add+del fused (the gap)
    assert ddbdp_first == "ταῦτα"  # DDbDP picks <add>
