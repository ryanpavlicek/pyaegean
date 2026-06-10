"""AGDT → UD label conversion for Stage B training labels (UD-Perseus conventions).

Authored rules + a closed-class lexicon, **validated against** (never extracted from
wholesale) the UD-Perseus train fold via validate_agdt_ud.py — the UD folds are
CC BY-NC-SA and are used for evaluation/validation only. The facts encoded here are
closed-class grammar (which conjunctions subordinate; how a 9-char positional tag spells
out) under the UD-Perseus conversion's conventions:

- UPOS is the AGDT postag's first character, except two real splits:
  * ``c`` → CCONJ vs **SCONJ** — form-deterministic (a 67-form subordinator lexicon;
    note the convention keeps e.g. ἐπεί and μή under CCONJ).
  * ``v`` → VERB vs **AUX** — *contextual*: copular εἰμί is AUX. AGDT trees mark the
    copular construction (a PNOM dependent), so the label derives from the tree.
- FEATS is a pure function of the 9-char postag (validated: 810/810 distinct tags in the
  UD train fold map to exactly one FEATS string).

Training-side only: the trained tagger predicts UD UPOS directly (it learns the lexical
and contextual splits), so inference needs no UPOS converter; ``feats_from_xpos`` moves
into the package at Stage E to render predicted tags as UD FEATS.
"""

from __future__ import annotations

import unicodedata

__all__ = ["copular_flags", "feats_from_xpos", "upos_from_xpos"]


def _strip(form: str) -> str:
    """Accent/breathing-insensitive lowercase key for closed-class lookup."""
    nfd = unicodedata.normalize("NFD", form.lower())
    return "".join(c for c in nfd if not unicodedata.combining(c))


_FIRST = {
    "n": "NOUN", "v": "VERB", "a": "ADJ", "d": "ADV", "l": "DET", "g": "PART",
    "c": "CCONJ", "r": "ADP", "p": "PRON", "m": "NUM", "i": "INTJ", "e": "INTJ",
    "u": "PUNCT", "x": "X", "-": "X",
}

# Subordinating conjunctions under the UD-Perseus convention (stripped forms; includes
# epic/elided/crasis variants). Everything else tagged ``c`` is CCONJ.
_SCONJ = frozenset({
    "αι", "αν", "ατε", "διοπερ", "διοτι", "εαν", "ει", "ειος", "ειπερ", "ενθα",
    "επαν", "επεαν", "επειδαν", "επειπερ", "επην", "εστ", "ευτ", "ευτε", "εως",
    "ημεν", "ημος", "ην", "ηνικ", "ηος", "ηυτε", "ιν", "ινα", "καθαπερ", "καθοτι",
    "κατα", "κει", "μεχρι", "μηποτε", "μητοι", "ο", "οθ", "οθουνεκ", "οθουνεκα",
    "οθουνεχ", "οια", "οκως", "ομως", "οποτ", "οποτε", "οπποτ", "οπποτε", "οππως",
    "οπως", "οπωσπερ", "οσακις", "οτ", "οταν", "οτε", "οτι", "οττι", "ουνεκ",
    "ουνεκα", "ουνεχ", "οφρ", "οφρα", "παρος", "πριν", "χωπως", "χωταν", "ως",
    "ωσθ", "ωστ", "ωστε",
})

# Copular/auxiliary lemmas the UD-Perseus conversion demotes to AUX when the AGDT tree
# shows the construction (a PNOM dependent, or the verb's own relation is AuxV).
_COPULA_LEMMAS = frozenset({"ειμι"})
_AUX_LEMMAS = frozenset({"ειμι", "εχω"})  # AuxV-relation auxiliaries (periphrastics)


def copular_flags(words: list[dict]) -> list[bool]:
    """Per-token copular/auxiliary context from an AGDT sentence's tree.

    ``words``: dicts with at least ``id``, ``head``, ``relation`` (AGDT attributes, as
    strings). True where the token has a ``PNOM*`` dependent — directly, or through one
    ``COORD``/``APOS`` level (coordinated predicates attach to the coordinator, not the
    copula). The AuxV case is handled separately via ``own_relation``."""
    pnom_heads = {w.get("head") for w in words if (w.get("relation") or "").startswith("PNOM")}
    # one level of indirection: a COORD/APOS node with PNOM children marks ITS head too
    for w in words:
        rel = w.get("relation") or ""
        if (rel.startswith("COORD") or rel.startswith("APOS")) and w.get("id") in pnom_heads:
            pnom_heads.add(w.get("head"))
    return [w.get("id") in pnom_heads for w in words]


def upos_from_xpos(
    form: str,
    xpos: str,
    *,
    lemma: str = "",
    has_pnom_child: bool = False,
    own_relation: str = "",
) -> str:
    """The UD-Perseus UPOS for an AGDT token.

    ``has_pnom_child`` is the copular tree signal (compute it with `copular_flags` when
    converting whole sentences); ``own_relation`` is the token's AGDT relation, used for
    the ``AuxV`` auxiliary case. Without tree context every ``v`` stays VERB."""
    first = xpos[:1] if xpos else "-"
    if first == "c":
        return "SCONJ" if _strip(form) in _SCONJ else "CCONJ"
    if first == "v":
        key = _strip(lemma)
        if has_pnom_child and key in _COPULA_LEMMAS:
            return "AUX"
        if own_relation.startswith("AuxV") and key in _AUX_LEMMAS:
            return "AUX"
    return _FIRST.get(first, "X")


# --- FEATS: a pure function of the 9-char positional tag --------------------------
# Positions: 0 pos, 1 person, 2 number, 3 tense, 4 mood, 5 voice, 6 gender, 7 case, 8 degree.

_NUMBER = {"s": "Sing", "p": "Plur", "d": "Dual"}
_TENSE = {  # (Tense, Aspect or None) under the UD-Perseus convention
    "p": ("Pres", None), "i": ("Past", "Imp"), "a": ("Past", None), "r": ("Past", "Perf"),
    "l": ("Pqp", None), "f": ("Fut", None), "t": ("Fut", "Perf"),
}
_MOOD = {"i": "Ind", "s": "Sub", "o": "Opt", "m": "Imp"}  # finite moods
_VOICE = {"a": "Act", "m": "Mid", "p": "Pass", "e": "Mid"}
_GENDER = {"m": "Masc", "f": "Fem", "n": "Neut"}
_CASE = {"n": "Nom", "g": "Gen", "d": "Dat", "a": "Acc", "v": "Voc", "l": "Loc"}
_DEGREE = {"c": "Cmp", "s": "Sup"}


def feats_from_xpos(xpos: str) -> str:
    """The UD-Perseus FEATS string for a 9-char AGDT postag (``"_"`` when empty).

    Validated as a pure function on the UD train fold; features are emitted in the
    CoNLL-U-required alphabetical order."""
    x = (xpos or "").ljust(9, "-")
    feats: dict[str, str] = {}
    if x[1] in "123":
        feats["Person"] = x[1]
    if x[2] in _NUMBER:
        feats["Number"] = _NUMBER[x[2]]
    if x[3] in _TENSE:
        tense, aspect = _TENSE[x[3]]
        feats["Tense"] = tense
        if aspect:
            feats["Aspect"] = aspect
    mood = x[4]
    if mood in _MOOD:
        feats["Mood"] = _MOOD[mood]
        feats["VerbForm"] = "Fin"
    elif mood == "n":
        feats["VerbForm"] = "Inf"
    elif mood == "p":
        feats["VerbForm"] = "Part"
    if x[5] in _VOICE:
        feats["Voice"] = _VOICE[x[5]]
    if x[6] in _GENDER:
        feats["Gender"] = _GENDER[x[6]]
    if x[7] in _CASE:
        feats["Case"] = _CASE[x[7]]
    if x[8] in _DEGREE:
        feats["Degree"] = _DEGREE[x[8]]
    if not feats:
        return "_"
    return "|".join(f"{k}={v}" for k, v in sorted(feats.items()))
