"""Baseline Greek lemmatization (open-data seed + a generalizing rule layer).

Two zero-dependency tiers, tried in order:

1. a small bundled form→lemma table (seeded from the sample corpus), for irregular
   and high-frequency forms whose lemma is not derivable from the ending;
2. a **generalizing ending-stripping rule layer** (`rule_lemma_verbose`) that recovers
   the citation form of the *regular* second-declension and thematic-verb paradigms by
   accent-preserving ending substitution: the ``-ου/-ῳ/-ον/-οι/-οις/-ους`` oblique endings back
   to the nominative ``-ος`` (plus the first-declension ``-αν`` accusative ``→ -α``) and the
   regular thematic *active* endings back to the ``-ω`` citation form
   (``-εις/-ει/-ομεν/-ετε/-ουσι(ν)``, plus the present infinitive ``-ειν``). It keeps the surface
   stem (with its breathing and accent) intact and only synthesises the ending, so an unseen
   ``νόμου`` lemmatizes to ``νόμος`` without any lookup. Conservative guards, measured on the full
   New Testament (where a blind stripper regressed ~1,000 tokens), skip the forms it would wreck: a
   circumflex on the ending marks a contracted nominative (``Ἰησοῦς``), adverb (``ἐκεῖ``), or
   contracted verb (``ζῇ``), and a curated list covers the common neuter ``-ον`` nouns (``ἔργον``,
   whose lemma *is* the ``-ον`` form) and the indeclinables/reflexives.

This is the seed/rule tier of the cascade: the treebank, neural, and edit-tree backends
(opt-in) handle the heavier, ambiguous, and irregular work and take precedence when active.
Forms outside this scope (the ambiguous first-declension ``-η`` series, third-declension stems,
indeclinables, suppletives) are returned normalized (NFC) unchanged, flagged via
`lemmatize_verbose`. The rule layer also cannot restore an accent that *recedes* between the
inflected form and the lemma (``κυρίῳ`` → ``κύριος``, ``δούλοις`` → ``δοῦλος``): it preserves the
surface stem accent, so those need the opt-in backends.
"""

from __future__ import annotations

import unicodedata
from functools import lru_cache

from ..data import load_bundled_json

_ACUTE = "́"
_GRAVE = "̀"
_CIRCUMFLEX = "͂"
_IOTA_SUBSCRIPT = "ͅ"
_ACCENT_MARKS = frozenset({_ACUTE, _GRAVE, _CIRCUMFLEX})
_VOWELS = frozenset("αεηιουω")


@lru_cache(maxsize=1)
def _lemma_table() -> dict[str, str]:
    raw = load_bundled_json("greek", "lemmata.json")
    # Normalize keys to lowercase NFC so lookup is robust to input form.
    return {
        unicodedata.normalize("NFC", k.lower()): unicodedata.normalize("NFC", v)
        for k, v in raw.items()
    }


def seed_lemma_verbose(word: str) -> tuple[str, bool]:
    """The **seed-tier only** lookup: ``(lemma, known)`` from the bundled table, or the
    NFC-normalized form unchanged with ``known=False``. Never consults the trained
    backends — the rule-based morphology engine depends on that (its features must not
    change with backend state, and the backends themselves call back into it)."""
    key = unicodedata.normalize("NFC", word.lower())
    table = _lemma_table()
    if key in table:
        return table[key], True
    return unicodedata.normalize("NFC", word), False


# --- generalizing ending-stripping rule layer --------------------------------
# These rules recover the citation form of the *regular* second-declension
# nominal and thematic-verbal paradigms by accent-preserving ending substitution.
# Endings are matched against the bare (lowercased, diacritic-stripped, final-ς→σ)
# form; the citation ending replaces the matched ending while the surface stem (its
# breathing and accent untouched) is kept verbatim. Oxytones (the accent sits on the
# inflectional ending) keep an acute on the synthesised citation ending; otherwise the
# stem already carries the accent and the citation ending is unaccented.


def _bare(word: str) -> str:
    """Lowercase, diacritic-stripped form (final ς folded to σ) for ending match."""
    nfd = unicodedata.normalize("NFD", word).lower()
    stripped = "".join(c for c in nfd if not unicodedata.combining(c))
    return stripped.replace("ς", "σ")


def _last_n_have(word: str, n: int, marks: frozenset[str]) -> bool:
    """Whether any of ``marks`` sits on one of the last ``n`` base letters of ``word``."""
    bases = 0
    for ch in reversed(unicodedata.normalize("NFD", word)):
        if unicodedata.combining(ch):
            if ch in marks and bases < n:
                return True
            continue
        bases += 1
        if bases >= n:
            break
    return False


def _surface_stem(word: str, n: int) -> str:
    """The original-form prefix after dropping the last ``n`` base letters (with their
    combining marks); breathing and accent on the stem are preserved verbatim."""
    nfd = list(unicodedata.normalize("NFD", word))
    bases = 0
    cut = 0
    for i in range(len(nfd) - 1, -1, -1):
        if unicodedata.combining(nfd[i]):
            continue
        bases += 1
        if bases == n:
            cut = i
            break
    return unicodedata.normalize("NFC", "".join(nfd[:cut]))


def _acute_on_last_vowel(segment: str) -> str:
    """Place an acute on the last vowel of ``segment`` (the oxytone citation ending)."""
    nfd = list(unicodedata.normalize("NFD", segment))
    vowel_idx = [
        i for i, ch in enumerate(nfd) if not unicodedata.combining(ch) and ch.lower() in _VOWELS
    ]
    if not vowel_idx:
        return unicodedata.normalize("NFC", "".join(nfd))
    insert = vowel_idx[-1] + 1
    while insert < len(nfd) and unicodedata.combining(nfd[insert]):
        insert += 1  # after any breathing/dieresis already on the vowel
    nfd.insert(insert, _ACUTE)
    return unicodedata.normalize("NFC", "".join(nfd))


# Bare oblique ending → bare citation ending, for endings that take NO iota subscript.
# Second declension (-ος), then the first-declension -η and -α feminine series. The
# nominative -ος/-ης/-ας masculine endings are deliberately absent: they ARE citation
# forms, and the genitive -ης/-ας collide with them, so those are left to the seed table.
_NOMINAL_PLAIN: tuple[tuple[str, str], ...] = (
    ("ουσ", "ος"), ("οισ", "ος"), ("ου", "ος"), ("ον", "ος"), ("οι", "ος"),
    ("αν", "α"),
)
# The first-declension feminine -η *plural/accusative* endings (-αις/-ην/-αι) are deliberately
# absent: on the New Testament gold they recover almost nothing (the high-frequency feminines are
# in the seed table) yet collide with the 3rd-declension nominative -ης (παῖς) and the -μαι middle
# (ἔρχομαι), so they were net-harmful. The feminine dat.-sg. -ῃ/-ᾳ are out too: -ῃ collides with the
# contracted verb (ζῇ → ζάω) and both are feminine, out of this -ος/verb scope.
# Only the masculine/neuter dative singular -ῳ → -ος (no contracted verb ends in -ῳ, so the
# perispomenon ἀγαθῷ is safe to strip).
_NOMINAL_SUBSCRIPT: tuple[tuple[str, str], ...] = (
    ("ω", "ος"),
)
# Regular thematic active endings (present/future indicative, present infinitive) → -ω.
# Only the *active* series is mapped: the mediopassive endings (-ομαι/-εται/-ονται/…) are
# left out because a deponent's citation form is the -ομαι middle, not an active -ω, which a
# flat ending swap cannot tell apart. Past-tense (augmented) and sigmatic-aorist endings are
# also out (stripping the augment needs the morphology engine), as is the participle (its
# lemma depends on voice and contraction).
_VERBAL: tuple[tuple[str, str], ...] = (
    ("ομεν", "ω"), ("ουσιν", "ω"), ("ουσι", "ω"), ("ετε", "ω"), ("εισ", "ω"),
    ("ειν", "ω"), ("ει", "ω"),
)
# Genuinely indeclinable high-frequency forms that an ending rule would otherwise mis-fire on
# (μᾶλλον is an adverb, not the accusative of a noun μᾶλλος; πλήν is a preposition/conjunction,
# not a 1st-declension accusative). Kept deliberately tiny and only for forms that are NOT also
# a real inflected paradigm cell, so the guard never suppresses a correct lemmatization.
_INDECLINABLE = frozenset({
    "μᾶλλον", "πλήν",
    # High-frequency indeclinables whose -ου / -αν / -οῦ ending an oblique rule would otherwise
    # strip to a spurious -ος / -α (ὅπου → ὅπος, ὅταν → ὅτα, ὁμοῦ → ὁμός). Adverbs, conjunctions,
    # particles, and the reflexive pronouns (which have no nominative): closed classes, never an
    # inflected noun cell, so the guard only ever blocks a wrong lemmatization.
    "ὅπου", "ποῦ", "οὗ", "ὅταν", "ἄν", "ἐάν", "ἤτοι",
    "ἑαυτοῦ", "ἐμαυτοῦ", "σεαυτοῦ", "ὁμοῦ", "πανταχοῦ", "ἀλλαχοῦ",
})

# Common second-declension NEUTER nouns, whose nominative/accusative is -ον (the citation form):
# a gender-blind ending rule would wrongly strip -ον to a masculine -ος (ἔργον → ἔργος). This is a
# general list of textbook-frequency neuters (the rule has no way to know the gender), kept separate
# from the seed table; the oblique cases of rarer neuters can still be mis-stemmed (use a backend).
_NEUTER_2ND = frozenset({
    "ἔργον", "τέκνον", "δῶρον", "πλοῖον", "σημεῖον", "παιδίον", "βιβλίον", "ἱμάτιον", "εὐαγγέλιον",
    "δαιμόνιον", "ποτήριον", "πρόβατον", "σάββατον", "δεῖπνον", "ἔλαιον", "μνημεῖον", "ζῷον",
    "εἴδωλον", "ἄστρον", "θηρίον", "δένδρον", "μέτρον", "ὅπλον", "ἱερόν", "πρόσωπον", "μυστήριον",
    "βραβεῖον", "ταμεῖον", "ἄροτρον", "ἄκρον", "ἔριον",
})


def _rule_lemma(word: str) -> str | None:
    """The citation form recovered by ending substitution, or ``None`` when no regular
    rule applies. Operates on the surface form; the longest matching ending wins."""
    nfc = unicodedata.normalize("NFC", word)
    if nfc in _INDECLINABLE or nfc in _NEUTER_2ND:
        return None  # the surface form is already the lemma; no ending rule applies
    bare = _bare(word)
    best: tuple[int, str] | None = None  # (ending length, citation ending base)
    for ending, citation in _NOMINAL_SUBSCRIPT:
        if (
            bare.endswith(ending)
            and len(bare) > len(ending)
            and _last_n_have(word, len(ending), frozenset({_IOTA_SUBSCRIPT}))
            and (best is None or len(ending) > best[0])
        ):
            best = (len(ending), citation)
    for ending, citation in _NOMINAL_PLAIN:
        if (
            bare.endswith(ending)
            and len(bare) > len(ending)
            and not _last_n_have(word, len(ending), frozenset({_IOTA_SUBSCRIPT}))
            # A circumflex on -ους marks a contracted nominative (Ἰησοῦς, νοῦς), not the
            # accusative plural; do not strip it. The acc. pl. -ους is never perispomenon.
            and not (ending == "ουσ" and _last_n_have(word, len(ending), frozenset({_CIRCUMFLEX})))
            and (best is None or len(ending) > best[0])
        ):
            best = (len(ending), citation)
    for ending, citation in _VERBAL:
        if (
            bare.endswith(ending)
            and len(bare) > len(ending)
            and not _last_n_have(word, len(ending), frozenset({_IOTA_SUBSCRIPT}))
            # A circumflex on a verbal ending is a *contracted* verb (ποιεῖ) the flat swap
            # cannot resolve, or a perispomenon adverb (ἐκεῖ); skip rather than mis-stem it.
            and not _last_n_have(word, len(ending), frozenset({_CIRCUMFLEX}))
            and (best is None or len(ending) > best[0])
        ):
            best = (len(ending), citation)
    if best is None:
        return None
    length, citation = best
    stem = _surface_stem(word, length)
    if _last_n_have(word, length, _ACCENT_MARKS):  # oxytone: accent was on the ending
        citation = _acute_on_last_vowel(citation)
    return unicodedata.normalize("NFC", stem + citation)


def rule_lemma_verbose(word: str) -> tuple[str, bool]:
    """The generalizing rule layer: ``(lemma, recovered)``. ``recovered`` is True when a
    regular ending rule produced a citation form different from the (normalized) input;
    otherwise the NFC form is returned unchanged with ``recovered=False``.

    Consults only the deterministic ending rules — never the seed table or any trained
    backend, so it composes cleanly as the generalizing step between them."""
    out = _rule_lemma(word)
    norm = unicodedata.normalize("NFC", word)
    if out is not None and out != norm:
        return out, True
    return norm, False


def lemmatize_verbose(word: str) -> tuple[str, bool]:
    """Return ``(lemma, known)``. ``known`` is False when neither the seed table nor the
    generalizing rule layer found a lemma and the (normalized) input is returned unchanged.

    When the AGDT treebank backend is active (see `aegean.greek.use_treebank`),
    its attested, correctly-accented lemma is preferred; next, when the neural backend is
    active (see `aegean.greek.use_neural_lemmatizer`), its GreTa seq2seq prediction is
    used — it generalizes well to unseen forms (76.3%); next the trained edit-tree lemmatizer
    (see `aegean.greek.use_lemmatizer`); otherwise the bundled seed table is consulted, then
    the generalizing ending-stripping rule layer (`rule_lemma_verbose`) for regular forms not
    in the table."""
    from . import joint

    if joint.active() is not None:  # the neural pipeline: contextual scripts + big lookup
        pred = joint.analyze_sentence([word]).lemma[0]
        return pred, pred != unicodedata.normalize("NFC", word)
    from . import treebank

    lex = treebank.active()
    if lex is not None:
        hit = lex.lemmatize(word)
        if hit is not None:
            return hit, True
    from . import neural_lemmatizer

    if neural_lemmatizer.active() is not None:  # GreTa seq2seq — strong on unseen forms
        pred = neural_lemmatizer.predict(word)
        return pred, pred != unicodedata.normalize("NFC", word)
    from . import lemmatizer

    if lemmatizer.active() is not None:  # trained generalizer for unseen forms
        pred = lemmatizer.predict(word)
        # A prediction identical to the (normalized) form is an identity fall-through, so
        # mirror the seed-table contract: known=False when the form is returned unchanged.
        return pred, pred != unicodedata.normalize("NFC", word)
    lemma, known = seed_lemma_verbose(word)
    if known:
        return lemma, True
    return rule_lemma_verbose(word)  # generalize over the regular paradigms before giving up


def lemmatize(word: str) -> str:
    """The lemma for a form via the seed table then the generalizing rule layer, or the
    normalized form itself when neither applies."""
    return lemmatize_verbose(word)[0]
