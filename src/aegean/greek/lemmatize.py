"""Baseline Greek lemmatization (open-data seed + a generalizing rule layer).

Two zero-dependency tiers, tried in order:

1. a small form→lemma table: the bundled seed (from the sample corpus) plus the
   closed-class function words (article, pronouns, particles, prepositions), for
   irregular and high-frequency forms whose lemma is not derivable from the ending.
   Lookup keys fold a grave accent to the acute (the grave is only the running-text
   notation of a final acute; the citation form never carries one), so δὲ finds δέ;
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
   contracted verb (``ζῇ``); a curated list covers the common neuter ``-ον`` nouns (``ἔργον``,
   whose lemma *is* the ``-ον`` form) and the indeclinables/reflexives; and the closed-class
   function words are skipped outright (their lemmas are suppletive: an ending swap would
   turn ``τοῦ`` into a non-word ``τός`` instead of ``ὁ``), as is any match whose stem would
   be vowel-less (``μου``). The thematic ``-ει/-εις`` strip is further held back from the two
   look-alike classes it cannot otherwise tell from a present verb: the sigmatic future/aorist
   (a single ``σ`` before the ending: ``δώσει`` is not stripped to a non-word ``*δώσω``, while the
   genuine double-``σ`` present ``πράσσει → πράσσω`` still is) and the aorist-passive participle /
   ``-εί`` adverb whose accent sits on the diphthong (``ἀποκριθείς``). The frequent third-declension
   i-stem/s-stem datives and plurals whose ending collides with that verb rule (``πόλει``, ``πίστει``,
   ``δυνάμει``) are seeded to their attested noun lemma, so they resolve correctly rather than
   fabricating ``*πόλω``.

This is the seed/rule tier of the cascade: the treebank, neural, and edit-tree backends
(opt-in) handle the heavier, ambiguous, and irregular work and take precedence when active.
Forms outside this scope (the ambiguous first-declension ``-η`` series, most third-declension
stems, augmented past tenses, indeclinables, suppletives) are returned normalized (NFC)
unchanged, flagged via `lemmatize_verbose`. The rule layer also cannot restore an accent that
*recedes* between the inflected form and the lemma (``κυρίῳ`` → ``κύριος``, ``δούλοις`` → ``δοῦλος``):
it preserves the surface stem accent, so those need the opt-in backends.
"""

from __future__ import annotations

import unicodedata
from enum import Enum
from functools import lru_cache

from ..data import load_bundled_json


class LemmaSource(str, Enum):
    """Where a lemma came from — the evidence class for one token's lemma.

    A ``str`` Enum (not ``StrEnum``: the floor is Python 3.10), so members are plain
    strings under ``json.dumps`` and comparisons; emit ``.value`` where a bare string
    is wanted. Ordered from most to least trustworthy:

    - ``ATTESTED``   — a treebank-lexicon hit (an attested, correctly accented lemma).
    - ``NEURAL``     — a real prediction from the joint pipeline / seq2seq / edit-tree model.
    - ``RULE``       — the ending-stripping rule layer recovered a regular citation form.
    - ``SEED``       — the bundled seed table / a closed-class function word.
    - ``IDENTITY``   — a backend/model was consulted but returned the surface form unchanged
      (no real analysis), so the "lemma" is just the input.
    - ``UNRESOLVED`` — the baseline cascade was exhausted; the normalized form is returned.
    - ``PUNCT``      — a non-word token (punctuation / numeral): trivially its own lemma.

    ``IDENTITY`` and ``UNRESOLVED`` are the classes a human should verify (see
    `needs_review`); the rest are grounded analyses."""

    ATTESTED = "attested"
    NEURAL = "neural"
    RULE = "rule"
    SEED = "seed"
    IDENTITY = "identity"
    UNRESOLVED = "unresolved"
    PUNCT = "punct"


def needs_review(source: LemmaSource) -> bool:
    """Whether a lemma with this source should be verified by a human: an ``IDENTITY``
    fall-through or an ``UNRESOLVED`` baseline miss. ``ATTESTED``/``NEURAL``/``RULE``/
    ``SEED``/``PUNCT`` are grounded and do not need review."""
    return source in (LemmaSource.IDENTITY, LemmaSource.UNRESOLVED)

_ACUTE = "́"
_GRAVE = "̀"
_CIRCUMFLEX = "͂"
_IOTA_SUBSCRIPT = "ͅ"
_ACCENT_MARKS = frozenset({_ACUTE, _GRAVE, _CIRCUMFLEX})
_VOWELS = frozenset("αεηιουω")


def _fold_key(word: str) -> str:
    """Lowercase NFC lookup key with any grave folded to the acute: the grave is the
    running-text notation of a final acute (Smyth §155), never part of a citation form,
    so δὲ must find the δέ entry. Matches the closed-class key normalization in
    `.morphology`."""
    nfd = unicodedata.normalize("NFD", word.lower())
    return unicodedata.normalize("NFC", nfd.replace(_GRAVE, _ACUTE))


# Closed-class function words: the article, the personal/demonstrative/relative/
# reflexive/reciprocal pronouns, the negations, the accented particles and
# prepositions, plus the suppletive copula εἰμί and the two textbook irregular
# adjectives (πολύς, μέγας). These are suppletive or irregular (τοῦ's lemma is ὁ,
# μου's is ἐγώ): no ending rule can recover them, and a blind ending swap fabricates
# non-words (τοῦ → τός, πολλοί → πολλός), so they live in the seed table and are
# guarded from the rule layer. Keys are written in citation accentuation
# (`_fold_key` maps running-text graves onto them).
_FUNCTION_WORDS: dict[str, str] = {
    # the article (Smyth §332)
    "ὁ": "ὁ", "ἡ": "ὁ", "τό": "ὁ",
    "τοῦ": "ὁ", "τῆς": "ὁ", "τῷ": "ὁ", "τῇ": "ὁ", "τόν": "ὁ", "τήν": "ὁ",
    "οἱ": "ὁ", "αἱ": "ὁ", "τά": "ὁ",
    "τῶν": "ὁ", "τοῖς": "ὁ", "ταῖς": "ὁ", "τούς": "ὁ", "τάς": "ὁ",
    # personal pronouns (Smyth §325)
    "ἐγώ": "ἐγώ", "ἐμοῦ": "ἐγώ", "ἐμοί": "ἐγώ", "ἐμέ": "ἐγώ",
    "μου": "ἐγώ", "μοι": "ἐγώ", "με": "ἐγώ",
    "ἡμεῖς": "ἐγώ", "ἡμῶν": "ἐγώ", "ἡμῖν": "ἐγώ", "ἡμᾶς": "ἐγώ",
    "σύ": "σύ", "σοῦ": "σύ", "σοί": "σύ", "σέ": "σύ",
    "σου": "σύ", "σοι": "σύ", "σε": "σύ",
    "ὑμεῖς": "σύ", "ὑμῶν": "σύ", "ὑμῖν": "σύ", "ὑμᾶς": "σύ",
    # possessives ἐμός and σός, only the cells that do not collide with the personal
    # pronoun (ἐμοῦ/ἐμοί/ἐμέ and σοῦ/σοί/σέ keep their far more frequent personal reading)
    "ἐμός": "ἐμός", "ἐμή": "ἐμός", "ἐμόν": "ἐμός", "ἐμῷ": "ἐμός", "ἐμῇ": "ἐμός",
    "ἐμήν": "ἐμός", "ἐμοῖς": "ἐμός", "ἐμαῖς": "ἐμός", "ἐμούς": "ἐμός", "ἐμάς": "ἐμός",
    "ἐμά": "ἐμός",
    "σός": "σός", "σή": "σός", "σόν": "σός", "σῷ": "σός", "σῇ": "σός", "σήν": "σός",
    "σοῖς": "σός", "σαῖς": "σός", "σούς": "σός", "σάς": "σός", "σά": "σός",
    # αὐτός (the oblique masculine cells are also rule-recoverable; kept here so the
    # whole paradigm is table-validated, feminine/neuter/genitive-plural included)
    "αὐτός": "αὐτός", "αὐτή": "αὐτός", "αὐτό": "αὐτός",
    "αὐτοῦ": "αὐτός", "αὐτῆς": "αὐτός", "αὐτῷ": "αὐτός", "αὐτῇ": "αὐτός",
    "αὐτόν": "αὐτός", "αὐτήν": "αὐτός",
    "αὐτοί": "αὐτός", "αὐταί": "αὐτός", "αὐτά": "αὐτός",
    "αὐτῶν": "αὐτός", "αὐτοῖς": "αὐτός", "αὐταῖς": "αὐτός",
    "αὐτούς": "αὐτός", "αὐτάς": "αὐτός",
    # demonstratives οὗτος and ἐκεῖνος (Smyth §333)
    "οὗτος": "οὗτος", "αὕτη": "οὗτος", "τοῦτο": "οὗτος",
    "τούτου": "οὗτος", "ταύτης": "οὗτος", "τούτῳ": "οὗτος", "ταύτῃ": "οὗτος",
    "τοῦτον": "οὗτος", "ταύτην": "οὗτος",
    "οὗτοι": "οὗτος", "αὗται": "οὗτος", "ταῦτα": "οὗτος",
    "τούτων": "οὗτος", "τούτοις": "οὗτος", "ταύταις": "οὗτος",
    "τούτους": "οὗτος", "ταύτας": "οὗτος",
    "ἐκεῖνος": "ἐκεῖνος", "ἐκείνη": "ἐκεῖνος", "ἐκεῖνο": "ἐκεῖνος",
    "ἐκείνου": "ἐκεῖνος", "ἐκείνης": "ἐκεῖνος", "ἐκείνῳ": "ἐκεῖνος", "ἐκείνῃ": "ἐκεῖνος",
    "ἐκεῖνον": "ἐκεῖνος", "ἐκείνην": "ἐκεῖνος",
    "ἐκεῖνοι": "ἐκεῖνος", "ἐκεῖναι": "ἐκεῖνος", "ἐκεῖνα": "ἐκεῖνος",
    "ἐκείνων": "ἐκεῖνος", "ἐκείνοις": "ἐκεῖνος", "ἐκείναις": "ἐκεῖνος",
    "ἐκείνους": "ἐκεῖνος", "ἐκείνας": "ἐκεῖνος",
    # relative ὅς (Smyth §339; genitive οὗ omitted — it collides with the adverb οὗ
    # "where", kept an unresolved indeclinable) and the frequent ὅστις cells
    "ὅς": "ὅς", "ἥ": "ὅς", "ὅ": "ὅς",
    "ἧς": "ὅς", "ᾧ": "ὅς", "ᾗ": "ὅς", "ὅν": "ὅς", "ἥν": "ὅς",
    "οἵ": "ὅς", "αἵ": "ὅς", "ἅ": "ὅς",
    "ὧν": "ὅς", "οἷς": "ὅς", "αἷς": "ὅς", "οὕς": "ὅς", "ἅς": "ὅς",
    "ὅστις": "ὅστις", "ἥτις": "ὅστις", "οἵτινες": "ὅστις", "αἵτινες": "ὅστις",
    # reflexives (genitive-lemma convention: they have no nominative) and the reciprocal
    "ἑαυτοῦ": "ἑαυτοῦ", "ἑαυτῆς": "ἑαυτοῦ", "ἑαυτῷ": "ἑαυτοῦ", "ἑαυτῇ": "ἑαυτοῦ",
    "ἑαυτόν": "ἑαυτοῦ", "ἑαυτήν": "ἑαυτοῦ", "ἑαυτό": "ἑαυτοῦ",
    "ἑαυτῶν": "ἑαυτοῦ", "ἑαυτοῖς": "ἑαυτοῦ", "ἑαυταῖς": "ἑαυτοῦ",
    "ἑαυτούς": "ἑαυτοῦ", "ἑαυτάς": "ἑαυτοῦ",
    "ἐμαυτοῦ": "ἐμαυτοῦ", "ἐμαυτῷ": "ἐμαυτοῦ", "ἐμαυτόν": "ἐμαυτοῦ",
    "σεαυτοῦ": "σεαυτοῦ", "σεαυτῷ": "σεαυτοῦ", "σεαυτόν": "σεαυτοῦ",
    "ἀλλήλων": "ἀλλήλων", "ἀλλήλοις": "ἀλλήλων", "ἀλλήλαις": "ἀλλήλων",
    "ἀλλήλους": "ἀλλήλων", "ἀλλήλας": "ἀλλήλων",
    # negative pronouns οὐδείς and μηδείς
    "οὐδείς": "οὐδείς", "οὐδεμία": "οὐδείς", "οὐδέν": "οὐδείς",
    "οὐδενός": "οὐδείς", "οὐδεμιᾶς": "οὐδείς", "οὐδενί": "οὐδείς",
    "οὐδεμιᾷ": "οὐδείς", "οὐδένα": "οὐδείς", "οὐδεμίαν": "οὐδείς",
    "μηδείς": "μηδείς", "μηδεμία": "μηδείς", "μηδέν": "μηδείς",
    "μηδενός": "μηδείς", "μηδενί": "μηδείς", "μηδένα": "μηδείς", "μηδεμίαν": "μηδείς",
    # the copula εἰμί (suppletive throughout; present and imperfect indicative, the
    # infinitive, and the frequent future cells — the participle is left to morphology)
    "εἰμί": "εἰμί", "εἶ": "εἰμί", "ἐστίν": "εἰμί", "ἔστιν": "εἰμί", "ἐστιν": "εἰμί",
    "ἐστί": "εἰμί", "ἐσμέν": "εἰμί", "ἐστέ": "εἰμί", "εἰσίν": "εἰμί", "εἰσί": "εἰμί",
    "ἤμην": "εἰμί", "ἦς": "εἰμί", "ἦν": "εἰμί", "ἦμεν": "εἰμί", "ἦτε": "εἰμί",
    "ἦσαν": "εἰμί", "ἔσομαι": "εἰμί", "ἔσται": "εἰμί", "ἔσονται": "εἰμί",
    "εἶναι": "εἰμί",
    # the textbook irregular adjectives πολύς and μέγας (Smyth §311): their oblique
    # stems (πολλ-, μεγαλ-) would ending-swap to the non-words πολλός / μεγάλος
    "πολύς": "πολύς", "πολλή": "πολύς", "πολύ": "πολύς",
    "πολλοῦ": "πολύς", "πολλῆς": "πολύς", "πολλῷ": "πολύς", "πολλῇ": "πολύς",
    "πολύν": "πολύς", "πολλήν": "πολύς",
    "πολλοί": "πολύς", "πολλαί": "πολύς", "πολλά": "πολύς",
    "πολλῶν": "πολύς", "πολλοῖς": "πολύς", "πολλαῖς": "πολύς",
    "πολλούς": "πολύς", "πολλάς": "πολύς",
    "μέγας": "μέγας", "μεγάλη": "μέγας", "μέγα": "μέγας",
    "μεγάλου": "μέγας", "μεγάλης": "μέγας", "μεγάλῳ": "μέγας", "μεγάλῃ": "μέγας",
    "μέγαν": "μέγας", "μεγάλην": "μέγας",
    "μεγάλοι": "μέγας", "μεγάλαι": "μέγας", "μεγάλα": "μέγας",
    "μεγάλων": "μέγας", "μεγάλοις": "μέγας", "μεγάλαις": "μέγας",
    "μεγάλους": "μέγας", "μεγάλας": "μέγας",
    # negations and the high-frequency accented particles/conjunctions (the enclitics
    # τε/γε and convention-split lemmas like οὕτως/οὕτω are deliberately left out)
    "οὐ": "οὐ", "οὐκ": "οὐ", "οὐχ": "οὐ", "μή": "μή",
    "δέ": "δέ", "γάρ": "γάρ", "ἀλλά": "ἀλλά", "ἤ": "ἤ", "μέν": "μέν",
    "οὐδέ": "οὐδέ", "μηδέ": "μηδέ", "ἐάν": "ἐάν", "ἄν": "ἄν", "καθώς": "καθώς",
    # oxytone prepositions (the atonic proclitics εἰς/ἐν/ἐκ are already citation forms;
    # ἐξ is ἐκ's pre-vowel allomorph)
    "ἐπί": "ἐπί", "διά": "διά", "ἀπό": "ἀπό", "κατά": "κατά", "μετά": "μετά",
    "περί": "περί", "παρά": "παρά", "ὑπό": "ὑπό", "ὑπέρ": "ὑπέρ", "ἀντί": "ἀντί",
    "ἀνά": "ἀνά", "πρό": "πρό", "πρός": "πρός", "σύν": "σύν", "ἐξ": "ἐκ",
}

# The rule layer skips these forms outright (see `_rule_lemma`): a closed-class form
# that happens to match an oblique ending must not be ending-stripped.
_FUNCTION_KEYS = frozenset(_fold_key(k) for k in _FUNCTION_WORDS)

# Third-declension i-stem / s-stem datives (-ει) and nom/acc plurals (-εις): their bare
# ending collides with the thematic 2sg/3sg verb rule, which alone fabricates a non-word
# -ω (πόλει → *πόλω). Seeded to the attested noun lemma so these resolve correctly (and
# known=True) instead. Textbook/NT-frequency forms; the stem is unambiguous (no verb
# shares the surface), so the seed only ever replaces a wrong answer with the right one.
_THIRD_DECL: dict[str, str] = {
    "πίστει": "πίστις", "πόλει": "πόλις", "πόλεις": "πόλις",
    "δυνάμει": "δύναμις", "δυνάμεις": "δύναμις",
    "ὄρει": "ὄρος", "θλίψει": "θλῖψις", "ἔθνει": "ἔθνος",
    "ἀποκαλύψει": "ἀποκάλυψις", "μέρει": "μέρος", "σκότει": "σκότος",
    "τάχει": "τάχος", "ἔτει": "ἔτος", "εἴδει": "εἶδος",
    "πράξει": "πρᾶξις", "πράξεις": "πρᾶξις", "τάξει": "τάξις",
    "πλήρεις": "πλήρης", "ὄφεις": "ὄφις", "σκεύει": "σκεῦος",
    "νήστεις": "νῆστις", "πελάγει": "πέλαγος",
}


@lru_cache(maxsize=1)
def _lemma_table() -> dict[str, str]:
    raw = load_bundled_json("greek", "lemmata.json")
    # Keys are normalized with `_fold_key` (lowercase NFC, grave→acute) so lookup is
    # robust to input form; the bundled seed extends the closed-class function words.
    table = {_fold_key(k): unicodedata.normalize("NFC", v) for k, v in _FUNCTION_WORDS.items()}
    table.update((_fold_key(k), unicodedata.normalize("NFC", v)) for k, v in _THIRD_DECL.items())
    table.update((_fold_key(k), unicodedata.normalize("NFC", v)) for k, v in raw.items())
    return table


def seed_lemma_verbose(word: str) -> tuple[str, bool]:
    """The **seed-tier only** lookup: ``(lemma, known)`` from the bundled table plus the
    closed-class function words, or the NFC-normalized form unchanged with
    ``known=False``. The lookup key folds a grave to the acute (δὲ finds δέ). Never
    consults the trained backends — the rule-based morphology engine depends on that
    (its features must not change with backend state, and the backends themselves call
    back into it)."""
    key = _fold_key(word)
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


_TONOS = (_ACUTE, _GRAVE, _CIRCUMFLEX)


def _final_ei_accented(word: str) -> bool:
    """Whether a tonos sits on the terminal ``-ει`` (or ``-εις``) diphthong.

    Marks an aorist-passive participle (``-θείς``/``-είς``: ἀποκριθείς, στραφείς) or an
    ``-εί`` adverb, where the accent falls on the diphthong itself, as opposed to a
    thematic 2sg/3sg present (λέγεις, λύει) whose accent sits earlier. Used to keep the
    verbal ``-ει/-εις → -ω`` strip from fabricating a non-word ``-ω`` on those forms."""
    groups: list[tuple[str, str]] = []
    for ch in unicodedata.normalize("NFD", word):
        if unicodedata.combining(ch):
            if groups:
                base, marks = groups[-1]
                groups[-1] = (base, marks + ch)
        else:
            groups.append((ch, ""))
    if groups and groups[-1][0] in ("ς", "σ"):
        groups = groups[:-1]
    if len(groups) < 2:
        return False
    (e_base, e_marks), (i_base, i_marks) = groups[-2], groups[-1]
    if e_base.lower() != "ε" or i_base.lower() != "ι":
        return False
    return any(m in _TONOS for m in e_marks + i_marks)


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
    "μᾶλλον", "πλήν", "ἐνώπιον", "σήμερον",
    # High-frequency indeclinables whose -ου / -αν / -οῦ ending an oblique rule would otherwise
    # strip to a spurious -ος / -α (ὅπου → ὅπος, ὅταν → ὅτα, ὁμοῦ → ὁμός, ἰδού → ἰδός). Adverbs,
    # conjunctions, particles, and the reflexive pronouns (which have no nominative): closed
    # classes, never an inflected noun cell, so the guard only ever blocks a wrong lemmatization.
    "ὅπου", "ποῦ", "οὗ", "ὅταν", "ἄν", "ἐάν", "ἤτοι", "ἰδού",
    "ἑαυτοῦ", "ἐμαυτοῦ", "σεαυτοῦ", "ὁμοῦ", "πανταχοῦ", "ἀλλαχοῦ",
    # -ει conjunctions/adverbs an ending rule would strip to a spurious -ω verb
    # (ἐπεί → ἐπώ, ὡσεί → ὡσώ): indeclinable, never a thematic present.
    "ἐπεί", "ὡσεί", "ἐπειδή",
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


# Common thematic second-aorist / imperfect forms in -ον (1sg = 3pl). Their -ον is a verb
# ending, not a 2nd-declension accusative, so the -ον→-ος noun rule would fabricate a non-word
# (εἶπον → *εἶπος). These lemmas are suppletive/irregular (εἶπον → λέγω), not rule-derivable, so
# the guard blocks the strip and the layer returns an honest miss. Matched accent/breathing-blind.
_AORIST_2ND_ON = frozenset(
    _bare(w)
    for w in {
        "εἶπον", "ἦλθον", "ἔλαβον", "ἔβαλον", "ἔφαγον", "ἔπεσον", "ἔλιπον", "ἔτεκον", "ἤγαγον",
        "ἔμαθον", "εὗρον", "ἔπαθον", "ἔλαχον", "ἔτυχον", "ἔθανον", "ἔφυγον", "ἔκαμον", "ἤνεγκον",
        "εἶδον", "ἔσχον", "ἔλεγον", "εἶχον", "ἔφερον", "ἔγραφον", "ἔβλεπον", "ἦγον", "ἔμενον",
        "ἔπινον", "ἔτρεχον", "εἰσῆλθον", "ἐξῆλθον", "ἀπῆλθον", "προσῆλθον", "παρῆλθον", "ἀνῆλθον",
    }
)
# The accent-stripped stems of the common neuters (the -ον dropped), so a genitive/dative like
# ἔργου/δώρου is recognized as an oblique neuter (accent-blind: δῶρον vs δώρου) and not stripped
# to a masculine *ἔργος/*δώρος.
_NEUTER_2ND_STEMS = frozenset(_bare(w)[:-2] for w in _NEUTER_2ND)
# The common neuters keyed by their accent-blind bare form, so an enclitic/oblique variant maps
# back to the dictionary nominative: δῶρόν, carrying the acute an enclitic throws onto its ultima
# (δῶρόν ἐστιν, Smyth §183), is the neuter δῶρον, NOT a fabricated *δῶρός — and the -ον→-ος strip
# must not fire on it. (Matched accent-blind, mirroring the sibling aorist guard.)
_NEUTER_2ND_BY_BARE = {_bare(w): w for w in _NEUTER_2ND}

# Common first-declension MASCULINE nouns in -ης. Their genitive singular is -ου (προφήτου,
# Ἰωάνου), homographic with the 2nd-declension -ος genitive (λόγου → λόγος) but yielding the -ης
# nominative as the lemma (προφήτου → προφήτης, NOT a fabricated *προφήτος; Smyth §227, §230). The
# -ου ending alone cannot tell the two declensions apart, so for these curated stems the -ου→-ος
# strip is suppressed and the layer returns an honest miss rather than a confident non-word. Stems
# are accent/breathing-blind (the -ης dropped); NT-text spelling variants are listed explicitly
# (Ἰωάνης for the gold's Ἰωάννης, Ἅιδης for ᾅδης).
_MASC_1ST_ES = frozenset({
    "προφήτης", "ψευδοπροφήτης", "μαθητής", "στρατιώτης", "πολίτης", "τελώνης", "δεσπότης",
    "οἰκοδεσπότης", "ἰδιώτης", "ὑποκριτής", "βαπτιστής", "κριτής", "ναύτης", "πρεσβύτης",
    "ἐργάτης", "χάρτης", "κλέπτης", "λῃστής", "οἰκέτης", "δικαστής", "προδότης", "πλανήτης",
    "ἑκατοντάρχης", "πατριάρχης", "τετραάρχης", "χιλίαρχης", "πολιτάρχης",
    "Ἰωάννης", "Ἰωάνης", "Ἡρῴδης", "ᾅδης", "Ἅιδης", "Ἰορδάνης", "Ἰσκαριώτης",
})
_MASC_1ST_ES_STEMS = frozenset(_bare(w)[:-2] for w in _MASC_1ST_ES)


def _ei_strip_unsafe(word: str, bare: str) -> bool:
    """Whether the thematic ``-ει/-εις → -ω`` strip must NOT fire on this form.

    The flat swap correctly recovers thematic 2sg/3sg presents (λέγει → λέγω) but
    fabricates a non-word ``-ω`` on two look-alike classes it cannot otherwise tell
    apart: the sigmatic future/aorist (δώσει → *δώσω, its lemma is the present δίδωμι;
    a *single* σ before -ει, not the genuine double-σ present πράσσει → πράσσω), and
    the aorist-passive participle / -εί adverb whose accent sits on the diphthong
    (ἀποκριθείς → *ἀποκριθώ). Both are left to the seed table or a backend."""
    if (bare.endswith("σει") and not bare.endswith("σσει")) or (
        bare.endswith("σεισ") and not bare.endswith("σσεισ")
    ):
        return True
    # ψ (=πσ/βσ/φσ) and ξ (=κσ/γσ/χσ) are contracted sigmatic futures too (γράψει, διώξει,
    # πέμψει): the lemma is the present (γράφω, διώκω, πέμπω), not the fabricated -ω future.
    if bare.endswith(("ψει", "ξει", "ψεισ", "ξεισ")):
        return True
    return _final_ei_accented(word)


def _sigmatic_before(bare: str, ending: str) -> bool:
    """Whether a *single* σ sits immediately before a thematic personal ending.

    That marks a sigmatic future/aorist (δώσομεν, δώσετε, δώσουσιν), whose lemma is
    the present (δίδωμι), NOT the fabricated ``-ω`` the flat swap would invent. A genuine
    thematic present has no σ (λέγομεν) or a double σ (πράσσομεν) before the ending, so it
    is left to strip normally. This generalizes the ``-ει/-εις`` guard to the other
    thematic endings (``-ομεν``/``-ετε``/``-ουσι(ν)``), which had no such guard."""
    stem = bare[: -len(ending)]
    return stem.endswith("σ") and not stem.endswith("σσ")


def _rule_lemma(word: str) -> str | None:
    """The citation form recovered by ending substitution, or ``None`` when no regular
    rule applies. Operates on the surface form; the longest matching ending wins."""
    key = _fold_key(word)
    if key in _INDECLINABLE:
        return None  # the surface form is already the lemma; no ending rule applies
    if key in _FUNCTION_KEYS:
        return None  # closed-class: the lemma is suppletive (τοῦ → ὁ), not rule-derivable
    bare = _bare(word)
    neuter = _NEUTER_2ND_BY_BARE.get(bare)
    if neuter is not None:
        # a common 2nd-declension neuter: its dictionary nominative is the lemma. This blocks the
        # -ον→-ος strip and normalises an enclitic-throwback acute (δῶρόν → δῶρον), so the layer
        # never fabricates *δῶρός; the plain nominative δῶρον maps to itself unchanged.
        return neuter
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
            # A circumflex on -οῖ is a contract verb 3sg (δηλοῖ = δηλόω), never a nom. pl.
            # -οι (which is short and never circumflexed, Smyth §169): do not strip to -ος.
            and not (ending == "οι" and _last_n_have(word, len(ending), frozenset({_CIRCUMFLEX})))
            # -ον is also the augmented thematic aorist/imperfect (εἶπον, ἦλθον): a verb, not
            # an accusative noun. Do not fabricate a -ος noun for the common such forms.
            and not (ending == "ον" and _bare(word) in _AORIST_2ND_ON)
            # The genitive/dative of a common 2nd-declension neuter (ἔργου, δώρου) is not a
            # masculine -ος: block the strip rather than fabricate ἔργος/δώρος.
            and not (ending in ("ου", "οισ") and _bare(word)[: -len(ending)] in _NEUTER_2ND_STEMS)
            # A first-declension MASCULINE -ης genitive (προφήτου, Ἰωάνου) is homographic with the
            # 2nd-decl -ος genitive but its lemma is the -ης nominative: block the strip (honest
            # miss) rather than fabricate *προφήτος (Smyth §227). Curated stems only, so a genuine
            # 2nd-decl -ος genitive on the same shape (πλούτου → πλοῦτος) is untouched.
            and not (ending == "ου" and _bare(word)[:-2] in _MASC_1ST_ES_STEMS)
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
            and not (ending in ("ει", "εισ") and _ei_strip_unsafe(word, bare))
            # the same sigmatic-future look-alike on the other thematic endings
            and not (ending in ("ομεν", "ετε", "ουσι", "ουσιν") and _sigmatic_before(bare, ending))
            and (best is None or len(ending) > best[0])
        ):
            best = (len(ending), citation)
    if best is None:
        return None
    length, citation = best
    if not any(c in _VOWELS for c in bare[:-length]):
        # A vowel-less stem is no Greek stem: the match is a monosyllabic function word
        # (τοῦ, μου, πᾶν) whose lemma is suppletive; synthesising τ-ός or μ-ος would
        # fabricate a non-word.
        return None
    stem = _surface_stem(word, length)
    if _last_n_have(word, length, _ACCENT_MARKS):  # oxytone: accent was on the ending
        citation = _acute_on_last_vowel(citation)
    return unicodedata.normalize("NFC", stem + citation)


def rule_lemma_verbose(word: str) -> tuple[str, bool]:
    """The generalizing rule layer: ``(lemma, recovered)``. ``recovered`` is True when a
    regular ending rule produced a citation form different from the (normalized) input;
    otherwise the NFC form is returned unchanged with ``recovered=False``.

    Consults only the deterministic ending rules and the curated guard lists (the
    indeclinables, the common neuters, the closed-class function words) — never the
    corpus-seeded table or any trained backend, so it composes cleanly as the
    generalizing step between them."""
    out = _rule_lemma(word)
    norm = unicodedata.normalize("NFC", word)
    if out is not None and out != norm:
        return out, True
    return norm, False


def lemmatize_sourced(word: str) -> tuple[str, LemmaSource]:
    """Return ``(lemma, source)``: the lemma plus the evidence class it came from (see
    `LemmaSource`). This is the authoritative cascade; `lemmatize` and `lemmatize_verbose`
    are expressed on top of it, so the lemma and its known/verbose flag can never drift
    from the source.

    Tier order (identical to the historical cascade): the neural joint pipeline
    (`use_neural_pipeline`) → the AGDT treebank (`use_treebank`, an attested lemma) → the
    GreTa seq2seq backend (`use_neural_lemmatizer`) → the trained edit-tree lemmatizer
    (`use_lemmatizer`) → the bundled seed table → the generalizing ending-stripping rule
    layer. A backend that returns the surface form unchanged is reported ``IDENTITY`` (not
    a real analysis); an exhausted baseline is ``UNRESOLVED``.

    The joint pipeline's ``IDENTITY`` is decided by *which branch composed the lemma*
    (`joint._compose_lemma`), not by a surface-string compare, so a nominative singular
    whose lemma equals the form is correctly ``NEURAL``. The auxiliary seq2seq/edit-tree
    backends have no such signal, so there a lemma equal to the surface reads ``IDENTITY``
    (preserving their historical ``known`` semantics)."""
    from . import joint

    if joint.active() is not None:  # the neural pipeline: contextual scripts + big lookup
        ana = joint.analyze_sentence([word])
        resolved = ana.lemma_resolved[0] if ana.lemma_resolved else ana.lemma[0] != word
        return ana.lemma[0], LemmaSource.NEURAL if resolved else LemmaSource.IDENTITY
    from . import treebank

    lex = treebank.active()
    if lex is not None:
        hit = lex.lemmatize(word)
        if hit is not None:
            return hit, LemmaSource.ATTESTED
    from . import neural_lemmatizer

    if neural_lemmatizer.active() is not None:  # GreTa seq2seq — strong on unseen forms
        pred = neural_lemmatizer.predict(word)
        changed = pred != unicodedata.normalize("NFC", word)
        return pred, LemmaSource.NEURAL if changed else LemmaSource.IDENTITY
    from . import lemmatizer

    if lemmatizer.active() is not None:  # trained generalizer for unseen forms
        pred = lemmatizer.predict(word)
        changed = pred != unicodedata.normalize("NFC", word)
        return pred, LemmaSource.NEURAL if changed else LemmaSource.IDENTITY
    lemma, known = seed_lemma_verbose(word)
    if known:
        return lemma, LemmaSource.SEED
    lemma, recovered = rule_lemma_verbose(word)  # generalize over the regular paradigms
    return lemma, LemmaSource.RULE if recovered else LemmaSource.UNRESOLVED


def lemmatize_verbose(word: str) -> tuple[str, bool]:
    """Return ``(lemma, known)``. ``known`` is False when the lemma is not a real analysis:
    an identity fall-through from a backend, or an exhausted baseline that returns the
    (normalized) input unchanged. Delegates to `lemmatize_sourced` (the tier order is
    documented there) so the flag tracks the evidence class exactly."""
    lemma, source = lemmatize_sourced(word)
    return lemma, not needs_review(source)


def lemmatize(word: str) -> str:
    """The lemma for a form via the active backend cascade, then the seed table and the
    generalizing rule layer, or the normalized form itself when nothing applies (see
    `lemmatize_sourced` for the tier order and the evidence class)."""
    return lemmatize_sourced(word)[0]
