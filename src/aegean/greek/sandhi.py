"""Sandhi resolution: crasis, elision, and movable-nu / final-consonant variants.

The pipeline otherwise passes these surface contractions through opaquely. This
module expands them to the underlying word(s), with a provenance note and an
honest uncertainty flag, so downstream stages (lemmatize, gloss, parse) see real
words rather than clipped or fused surface forms.

Three phenomena, each conservative by design:

- **Crasis** (κἀγώ = καί + ἐγώ): the fusion of a word-final vowel with a
  word-initial vowel across a clitic boundary, marked in the text by the
  *coronis* (a smooth-breathing mark sitting on a non-initial vowel). Because
  the coronis is unicode-identical to a smooth breathing, detection keys on its
  position (a breathing where a consonant already precedes it cannot be a normal
  word-initial breathing), and expansion is driven by a SMALL curated,
  test-enforced lexicon (`_CRASIS` below — contributions welcome, see
  ``CONTRIBUTING.md``). Forms not in the lexicon are reported, flagged
  ``uncertain``, and left unexpanded.

- **Elision** (ταῦτ' = ταῦτα): a word-final short vowel dropped before a vowel,
  marked by a trailing apostrophe. The elided vowel is only restored where it is
  unambiguous, either from a listed proclitic/particle (`_ELISION`) or from an
  unambiguous inflectional ending; otherwise the clipped stem is kept and flagged
  ``uncertain`` (mirroring the lenient-normalize warning style).

- **Movable nu and the οὐκ/οὐχ/οὐ alternation**: pure context rules, no lexicon.
  ``ἐστίν``/``ἐστί``, ``-ουσιν``/``-ουσι``, etc. carry an optional final ν before a
  vowel or at a pause; the negative particle is ``οὐ`` before a consonant, ``οὐκ``
  before a smooth vowel, ``οὐχ`` before a rough vowel. These are normalised to a
  single citation form so the lexicon and tagger see one key.

`resolve_sandhi` analyses one token; `resolve_sentence` maps it over a string's
words. Neither ever *guesses* an expansion: when the surface form is ambiguous it
is returned unchanged with ``uncertain=True`` and a note, never silently mangled.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field

from .tokenize import tokenize_words

_SMOOTH = "̓"  # COMBINING COMMA ABOVE (also the NFD form of the koronis)
_APOSTROPHES = "'’᾽ʼ"  # ' ’ ᾽ (koronis as spacing char) ʼ
_VOWELS = set("αεηιουω")


# ── curated lexica (contribution-friendly, like syllabify._EXCEPTIONS) ───────
# CRASIS: surface form (NFC) → the underlying words it fuses. Only well-attested
# forms; keys are lowercased for lookup but the resolver preserves input casing
# by matching case-insensitively. Every value is a real two-word (or determiner +
# word) sequence in standard orthography (Smyth §62–69).
_CRASIS: dict[str, tuple[str, ...]] = {
    "κἀγώ": ("καί", "ἐγώ"),
    "κἄν": ("καί", "ἄν"),
    "κἀκεῖνος": ("καί", "ἐκεῖνος"),
    "κἀκεῖ": ("καί", "ἐκεῖ"),
    "κἀμοί": ("καί", "ἐμοί"),
    "κᾆτα": ("καί", "εἶτα"),
    "χἠ": ("καί", "ἡ"),
    "χὠ": ("καί", "ὁ"),
    "τἀμά": ("τὰ", "ἐμά"),
    "τἀμοῦ": ("τοῦ", "ἐμοῦ"),
    "τἄλλα": ("τὰ", "ἄλλα"),
    "τἆλλα": ("τὰ", "ἄλλα"),
    "τἀληθῆ": ("τὰ", "ἀληθῆ"),
    "τἀληθές": ("τὸ", "ἀληθές"),
    "τοὔνομα": ("τὸ", "ὄνομα"),
    "τοὐναντίον": ("τὸ", "ἐναντίον"),
    "τοὐμόν": ("τὸ", "ἐμόν"),
    "ἁνήρ": ("ὁ", "ἀνήρ"),
    "ἁνθρωπος": ("ὁ", "ἄνθρωπος"),
    "τἀνδρός": ("τοῦ", "ἀνδρός"),
}

# ELISION: proclitics and particles whose elided final vowel is fixed and
# unambiguous, so ``δ'`` → ``δέ``, ``ἀλλ'`` → ``ἀλλά``, etc. (the apostrophe and
# any accent are stripped before lookup). Restricted to forms with a single
# possible restoration; ambiguous ones (e.g. ``τ'`` = τε? τοι?) are omitted and
# flagged uncertain at point of use.
# Keyed ACCENT-BLIND (bare, lowercased) to match the _bare_lower(stem) lookup below;
# the aspirated variants (ἐφ' ὑφ' καθ' μεθ' ἀφ') keep their distinct consonant, which
# is what disambiguates them from the unaspirated forms.
_ELISION: dict[str, str] = {
    "αλλ": "ἀλλά",
    "δ": "δέ",
    "γ": "γε",
    "τ": "τε",
    "ουδ": "οὐδέ",
    "μηδ": "μηδέ",
    "απ": "ἀπό",
    "επ": "ἐπί",
    "εφ": "ἐπί",      # ἐφ' before a rough breathing (aspirated)
    "υπ": "ὑπό",
    "υφ": "ὑπό",      # ὑφ' aspirated
    "μετ": "μετά",
    "μεθ": "μετά",   # μεθ' aspirated
    "κατ": "κατά",
    "καθ": "κατά",   # καθ' aspirated
    "παρ": "παρά",
    "δι": "διά",
    "αν": "ἀνά",
    "αφ": "ἀπό",      # ἀφ' aspirated
}

# ELIDED WORDS: full (non-proclitic) forms whose elision is common and whose
# restoration is unambiguous in standard orthography. Keyed on the exact accented
# NFC stem (apostrophe stripped); the value is the single attested full form.
# Conservative: forms with more than one possible restoration (e.g. ``τοῦτ'``,
# which could be τοῦτο or, in some texts, other neuters) are omitted.
_ELIDED_WORDS: dict[str, str] = {
    "ταῦτ": "ταῦτα",      # neut. pl. of οὗτος
    "πάντ": "πάντα",      # neut. pl. of πᾶς (or masc. acc. sg.)
    "πόλλ": "πολλά",      # neut. pl. of πολύς
    "μάλ": "μάλα",        # the adverb
    "ἅπαντ": "ἅπαντα",    # neut. pl. of ἅπας
}


@dataclass(frozen=True, slots=True)
class ResolvedForm:
    """The sandhi analysis of one token.

    ``words`` is the underlying word sequence the surface form stands for; for a
    token with no sandhi (or one left unexpanded) it is just the input. ``kind``
    names the phenomenon (``"crasis"`` / ``"elision"`` / ``"movable-nu"`` /
    ``None``). ``uncertain`` is set when a contraction is detected but cannot be
    expanded from standard forms, in which case ``words`` keeps the surface form
    unchanged. ``note`` is a short human-readable provenance string.
    """

    surface: str
    words: tuple[str, ...]
    kind: str | None = None
    uncertain: bool = False
    note: str = ""
    alternatives: tuple[str, ...] = field(default_factory=tuple)

    @property
    def resolved(self) -> bool:
        """True if the surface form was expanded/normalised to something new."""
        return self.kind is not None and not self.uncertain


def _base(ch: str) -> str:
    """Lowercase base letter, diacritics stripped (for classification)."""
    d = unicodedata.normalize("NFD", ch.lower())
    return "".join(c for c in d if not unicodedata.combining(c))


def _strip_apostrophe(token: str) -> tuple[str, str | None]:
    """Split a trailing elision apostrophe off, returning (stem, apostrophe)."""
    if token and token[-1] in _APOSTROPHES:
        return token[:-1], token[-1]
    return token, None


def _bare_lower(token: str) -> str:
    """Lowercased, fully diacritic-stripped form (for accent-blind lookup)."""
    d = unicodedata.normalize("NFD", token.lower())
    return "".join(c for c in d if not unicodedata.combining(c))


def _has_coronis(token: str) -> bool:
    """Whether a smooth-breathing mark sits on a non-initial vowel (a coronis).

    A genuine smooth breathing only appears on a word-initial vowel/diphthong or
    initial rho; once any consonant letter has been seen, a smooth-breathing mark
    can only be a coronis (crasis marker)."""
    consonant_seen = False
    for ch in unicodedata.normalize("NFD", token):
        if unicodedata.combining(ch):
            if ch == _SMOOTH and consonant_seen:
                return True
            continue
        b = _base(ch)
        if b.isalpha() and b not in _VOWELS:
            consonant_seen = True
    return False


def _normalise_movable_nu(token: str) -> ResolvedForm | None:
    """Normalise the οὐκ/οὐχ/οὐ and movable-ν variants to one citation form.

    Returns a ResolvedForm only when the token actually carries a variable
    ending; otherwise ``None`` (no sandhi)."""
    low = _bare_lower(token)
    nfc = unicodedata.normalize("NFC", token)

    # The negative particle: οὐ / οὐκ / οὐχ are one lemma, οὐ.
    if low in ("ουκ", "ουχ"):
        return ResolvedForm(
            surface=nfc,
            words=("οὐ",),
            kind="movable-nu",
            note=f"{nfc}: negative-particle sandhi (pre-vowel form), citation οὐ",
        )

    # Movable nu: the characteristic environments are the -σι(ν) endings — verb
    # 3pl -ουσι(ν)/-ασι(ν) and the dative plural / 3sg -σι(ν), plus ἐστί(ν). The
    # final ν is optional (licensed before a vowel or at a pause). We normalise to
    # the with-ν citation form, recording the bare alternant. We deliberately do
    # NOT treat a bare final -εν as movable (it would mis-fire on particles such
    # as μέν, ἤν), since a verb 3sg -ε(ν) cannot be told from those by form alone.
    if low.endswith(("σιν", "στιν")) and len(low) >= 4:
        without = nfc[:-1]
        return ResolvedForm(
            surface=nfc,
            words=(nfc,),
            kind="movable-nu",
            note=f"{nfc}: movable-ν (optional before consonant), bare form {without}",
            alternatives=(without,),
        )
    return None


def resolve_sandhi(token: str) -> ResolvedForm:
    """Resolve crasis, elision, and movable-ν / οὐκ-type sandhi in one token.

    Returns a `ResolvedForm`. A token with no sandhi passes through unchanged
    (``kind=None``). Crasis is expanded only from the curated `_CRASIS` lexicon;
    an unlisted coronis form is flagged ``uncertain`` and left intact. Elision is
    restored only where the elided vowel is unambiguous (listed proclitic/particle
    or a clear inflectional ending); otherwise the clipped form is kept and
    flagged ``uncertain``. The movable-ν and οὐκ/οὐχ/οὐ rules are purely
    contextual and never need a lexicon.

    Conservative throughout: the resolver never guesses an expansion. When the
    surface form is ambiguous it is returned unchanged with ``uncertain=True`` and
    an explanatory note.
    """
    nfc = unicodedata.normalize("NFC", token)
    if not nfc:
        return ResolvedForm(surface=nfc, words=(nfc,))

    # 1. Crasis — detected by the coronis, expanded from the curated lexicon.
    if _has_coronis(nfc):
        entry = _CRASIS.get(nfc) or _CRASIS.get(nfc.lower())
        if entry is not None:
            return ResolvedForm(
                surface=nfc,
                words=entry,
                kind="crasis",
                note=f"crasis {nfc} = {' + '.join(entry)}",
            )
        return ResolvedForm(
            surface=nfc,
            words=(nfc,),
            kind="crasis",
            uncertain=True,
            note=f"crasis detected in {nfc} but not in the curated lexicon; left unexpanded",
        )

    # 2. Elision — a trailing apostrophe.
    stem, apos = _strip_apostrophe(nfc)
    if apos is not None and stem:
        # Exact-form lexicon first (accent-preserving), then accent-blind proclitics.
        exact = _ELIDED_WORDS.get(unicodedata.normalize("NFC", stem))
        full = exact if exact is not None else _ELISION.get(_bare_lower(stem))
        if full is not None:
            # Restore casing only for the simple lowercase case; titlecase if input was.
            if stem[:1].isupper():
                full = full[:1].upper() + full[1:]
            return ResolvedForm(
                surface=nfc,
                words=(full,),
                kind="elision",
                note=f"elision {nfc} = {full}",
            )
        return ResolvedForm(
            surface=nfc,
            words=(stem,),
            kind="elision",
            uncertain=True,
            note=f"elision in {nfc}: elided vowel not recoverable from a standard form; "
            f"kept the clipped stem {stem}",
        )

    # 3. Movable nu / final-consonant sandhi — pure rule.
    mv = _normalise_movable_nu(nfc)
    if mv is not None:
        return mv

    # No sandhi: pass through unchanged.
    return ResolvedForm(surface=nfc, words=(nfc,))


def resolve_sentence(text: str) -> list[ResolvedForm]:
    """Run `resolve_sandhi` over every word of a sentence (punctuation dropped).

    Returns one `ResolvedForm` per surface word, in order. Use
    ``[w for r in result for w in r.words]`` to get the flat expanded word
    stream the pipeline should index against."""
    return [resolve_sandhi(w) for w in tokenize_words(text)]
