"""Render a 9-character AGDT-convention postag as a UD FEATS string.

The mapping is a pure function of the positional tag, validated at **100.00% agreement**
with the UD-Perseus conversion over all 159,895 aligned train-fold tokens (see
``docs/benchmarks.md``). Used by the neural pipeline (`aegean.greek.joint`) to render
its predicted XPOS as UD morphology, and by the training-side converters.

Positions: 0 pos, 1 person, 2 number, 3 tense, 4 mood, 5 voice, 6 gender, 7 case,
8 degree; ``-`` means not-applicable.
"""

from __future__ import annotations

__all__ = ["feats_from_xpos"]

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
    """The UD FEATS string for a 9-char AGDT postag (``"_"`` when no feature applies).

    Features are emitted in the CoNLL-U-required alphabetical order."""
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
