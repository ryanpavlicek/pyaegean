"""Baseline part-of-speech tagging for Greek (UD-style coarse tags).

High-precision **closed-class** tagging from a lexicon (article, prepositions,
conjunctions, particles, pronouns, and the εἰμί copula paradigm), with a light
suffix heuristic for open classes (a few unambiguous verb endings, else NOUN).

This is a **baseline**: closed classes are reliable; open-class precision is
limited until a real morphological analyzer / treebank-trained tagger lands. Tags
follow the Universal Dependencies inventory:
``DET ADP CCONJ SCONJ PART PRON ADV NUM NOUN VERB ADJ PUNCT X``.
"""

from __future__ import annotations

import re
import unicodedata

from .tokenize import tokenize

_GRAVE = "̀"
_ACUTE = "́"
_GREEK_LETTER = re.compile(r"[Ͱ-Ͽἀ-῿]")


def _norm(word: str) -> str:
    """Lowercase NFC with grave accents folded to acute, so running-text forms
    (καὶ, τὸν) match their lexical (καί, τόν) keys."""
    nfc = unicodedata.normalize("NFC", word).lower()
    nfd = unicodedata.normalize("NFD", nfc).replace(_GRAVE, _ACUTE)
    return unicodedata.normalize("NFC", nfd)


def _entries(tag: str, *forms: str) -> dict[str, str]:
    return {_norm(f): tag for f in forms}


# Closed-class lexicon (high precision). Built from acute-accented forms; the
# query is normalized the same way, so grave variants match.
_LEXICON: dict[str, str] = {
    **_entries(
        "DET",
        "ὁ", "ἡ", "τό", "οἱ", "αἱ", "τά",
        "τοῦ", "τῆς", "τῶν", "τῷ", "τῇ", "τοῖς", "ταῖς",
        "τόν", "τήν", "τούς", "τάς",
    ),
    **_entries(
        "ADP",
        "ἐν", "εἰς", "ἐκ", "ἐξ", "ἀπό", "πρός", "διά", "κατά", "μετά", "παρά",
        "περί", "ὑπό", "ἐπί", "ἀνά", "σύν", "πρό", "ὑπέρ", "ἀντί", "ἀμφί",
    ),
    **_entries("CCONJ", "καί", "τε", "δέ", "ἀλλά", "ἤ", "οὐδέ", "μηδέ"),
    **_entries("SCONJ", "ὅτι", "εἰ", "ἐάν", "ἵνα", "ὡς", "ὅπως", "ἐπεί", "γάρ", "οὖν"),
    **_entries("PART", "μέν", "δή", "γε", "ἄν", "οὐ", "οὐκ", "οὐχ", "μή", "ἄρα", "τοι"),
    **_entries(
        "PRON",
        "ἐγώ", "μου", "ἐμοῦ", "ἐμοί", "ἐμέ", "σύ", "σοῦ", "σοί", "σέ",
        "ἡμεῖς", "ὑμεῖς", "αὐτός", "αὐτή", "αὐτό", "αὐτοῦ", "αὐτῆς",
        "αὐτόν", "αὐτήν", "ὅς", "ἥ", "ὅ", "οὗτος", "αὕτη", "τοῦτο",
        "ὅδε", "ἥδε", "τόδε", "τίς", "τί", "ἐκεῖνος",
    ),
    # The copula is effectively a closed paradigm — tag it precisely.
    **_entries(
        "VERB",
        "εἰμί", "εἶ", "ἐστί", "ἐστίν", "ἐσμέν", "ἐστέ", "εἰσί", "εἰσίν",
        "ἦν", "ἦσαν", "ἔσται", "ὤν", "οὖσα", "ὄν",
    ),
}

# A few high-precision verb endings (after diacritic stripping).
_VERB_SUFFIXES = ("ω", "εις", "ομεν", "ετε", "ουσιν", "ουσι", "ειν")


def _strip(word: str) -> str:
    d = unicodedata.normalize("NFD", _norm(word))
    return "".join(c for c in d if not unicodedata.combining(c))


def pos_tag(word: str) -> str:
    """Tag a single token. Closed classes come from the lexicon; open-class words
    get a suffix heuristic (a few verb endings, else NOUN). Non-letter tokens are
    NUM (numeric) or PUNCT."""
    if not _GREEK_LETTER.search(word):
        if any(ch.isdigit() for ch in word):
            return "NUM"
        return "PUNCT" if word else "X"
    n = _norm(word)
    if n in _LEXICON:
        return _LEXICON[n]
    bare = _strip(word)
    if bare.endswith(_VERB_SUFFIXES):
        return "VERB"
    return "NOUN"


def pos_tags(text: str) -> list[tuple[str, str]]:
    """``(token, tag)`` pairs for a text, in order (punctuation tagged PUNCT)."""
    from ..core.model import TokenKind

    out: list[tuple[str, str]] = []
    for tok in tokenize(text):
        tag = "PUNCT" if tok.kind is TokenKind.PUNCT else pos_tag(tok.text)
        out.append((tok.text, tag))
    return out
