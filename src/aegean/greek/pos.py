"""Baseline part-of-speech tagging for Greek (UD-style coarse tags).

High-precision **closed-class** tagging from a lexicon (article, prepositions,
conjunctions, particles, pronouns, and the εἰμί copula paradigm), with a light
suffix heuristic for open classes (a few unambiguous verb endings, else NOUN).

Closed classes are reliable; open-class precision is limited by the suffix
heuristic — but activating the **opt-in treebank backend**
(`aegean.greek.use_treebank`) yields gold, attested tags for known forms,
covering the open-class words this baseline would mislabel. Tags follow the
Universal Dependencies inventory:
``DET ADP CCONJ SCONJ PART PRON ADV NUM NOUN VERB ADJ PUNCT X`` (the treebank
backend may additionally emit ``INTJ``).
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
    **_entries(
        "PART",
        "μέν", "δή", "γε", "ἄν", "οὐ", "οὐκ", "οὐχ", "μή", "ἄρα", "τοι",
        # remaining common particles (Smyth §§2769ff.; the indefinite adverbs
        # που/ποτε/πως are enclitic and distinct from interrogative ποῦ/πότε/πῶς)
        "μέντοι", "καίτοι", "δῆτα", "γοῦν", "τοίνυν", "που", "ποτε", "πως",
    ),
    **_entries(
        "PRON",
        "ἐγώ", "μου", "ἐμοῦ", "ἐμοί", "ἐμέ", "σύ", "σοῦ", "σοί", "σέ",
        "ἡμεῖς", "ὑμεῖς", "αὐτός", "αὐτή", "αὐτό", "αὐτοῦ", "αὐτῆς",
        "αὐτόν", "αὐτήν", "οὗτος", "αὕτη", "τοῦτο",
        "ὅδε", "ἥδε", "τόδε", "ἐκεῖνος",
        # relative ὅς, ἥ, ὅ (Smyth §339)
        "ὅς", "ἥ", "ὅ", "οὗ", "ἧς", "ᾧ", "ᾗ", "ὅν", "ἥν",
        "οἵ", "αἵ", "ἅ", "ὧν", "οἷς", "αἷς", "οὕς", "ἅς",
        # interrogative τίς, τί (Smyth §333; persistent acute)
        "τίς", "τί", "τίνος", "τίνι", "τίνα", "τίνες", "τίνων", "τίσι", "τίσιν", "τίνας",
        # indefinite τις, τι (Smyth §334; enclitic — the accent tells them apart)
        "τις", "τι", "τινός", "τινί", "τινά", "τινές", "τινῶν", "τισί", "τισίν", "τινάς",
    ),
    # determiners (Smyth §§337, 340): adjectival quantifiers, citation forms
    **_entries("DET", "ἄλλος", "ἕκαστος", "πᾶς"),
    # low cardinals (Smyth §§347-349): tagged NUM, following UD.
    **_entries(
        "NUM",
        "εἷς", "μία", "ἕν", "ἑνός", "μιᾶς", "ἑνί", "μιᾷ", "ἕνα",
        "δύο", "δυοῖν", "τρεῖς", "τρία", "τριῶν", "τρισί", "τρισίν",
        "τέσσαρες", "τέτταρες", "τέσσαρα", "τέτταρα", "τεσσάρων", "τεττάρων",
    ),
    # low ordinals: UD tags ordinals ADJ (NumType=Ord), not NUM. Only the
    # masc-nom citation form is keyed; the full -ος paradigm is handled by the
    # nominal ending rules.
    **_entries("ADJ", "πρῶτος", "δεύτερος", "τρίτος"),
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
    """Tag a single token. Closed classes come from the lexicon; when the treebank
    backend is active (see `aegean.greek.use_treebank`), an attested form's
    gold tag is used next; otherwise open-class words get a suffix heuristic (a few
    verb endings, else NOUN). Non-letter tokens are NUM (numeric) or PUNCT."""
    if not _GREEK_LETTER.search(word):
        if any(ch.isdigit() for ch in word):
            return "NUM"
        return "PUNCT" if word else "X"
    from . import joint

    if joint.active() is not None:  # the neural pipeline, when active, answers everything
        return joint.analyze_sentence([word]).upos[0]
    n = _norm(word)
    if n in _LEXICON:
        return _LEXICON[n]
    from . import treebank

    lex = treebank.active()
    if lex is not None:
        attested = lex.pos(word)
        if attested is not None:
            return attested
    from . import tagger

    if tagger.active() is not None:  # trained generalizer for unseen forms
        return tagger.tag_pos([word])[0]
    bare = _strip(word)
    if bare.endswith(_VERB_SUFFIXES):
        return "VERB"
    return "NOUN"


def pos_tags(text: str) -> list[tuple[str, str]]:
    """``(token, tag)`` pairs for a text, in order (punctuation tagged PUNCT). When the
    trained tagger is active it tags the whole sentence **in context**, with the
    closed-class lexicon and the treebank lookup still taking precedence per token."""
    from ..core.model import TokenKind
    from . import joint, tagger, treebank

    toks = list(tokenize(text))
    if joint.active() is not None:  # one encoder pass tags the whole sentence in context
        ana = joint.analyze_sentence([t.text for t in toks])
        return [(t.text, u) for t, u in zip(toks, ana.upos)]
    if tagger.active() is None:
        return [
            (t.text, "PUNCT" if t.kind is TokenKind.PUNCT else pos_tag(t.text))
            for t in toks
        ]

    context_tags = tagger.tag_pos([t.text for t in toks])
    lex = treebank.active()
    out: list[tuple[str, str]] = []
    for tok, ctx in zip(toks, context_tags):
        looked_up = lex.pos(tok.text) if lex is not None else None
        if tok.kind is TokenKind.PUNCT:
            tag = "PUNCT"
        elif _norm(tok.text) in _LEXICON:
            tag = _LEXICON[_norm(tok.text)]
        elif looked_up is not None:
            tag = looked_up
        else:
            tag = ctx
        out.append((tok.text, tag))
    return out
