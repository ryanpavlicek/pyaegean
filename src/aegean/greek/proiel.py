"""Neutral, out-of-AGDT evaluation against the PROIEL treebank (Ancient Greek).

`aegean.greek.heldout` measures generalization *within* the AGDT — the treebank
pyaegean's lemmatizer/tagger backends are built from. This module measures it against a
*different*, independently annotated source: the PROIEL treebank's Greek New Testament
and Herodotus, which none of pyaegean's models have ever seen. That is the genuinely
neutral check the heldout module's docstring calls for.

PROIEL is in-training for some other tools (e.g. stanza's ``grc_proiel`` model), so this
is a clean test for *pyaegean specifically* — not a level field for cross-tool comparison.

Data: ``github.com/proiel/proiel-treebank`` ``greek-nt.xml`` + ``hdt.xml``, pinned to a
commit, licensed **CC BY-NC-SA 3.0**. Fetched to the cache for evaluation only and
**never bundled** (NonCommercial + ShareAlike), exactly like the AGDT backend. Token
schema: ``<token form="…" lemma="…" part-of-speech="…"/>``; punctuation is not tokenized
(it lives in ``presentation-*`` attributes) and empty tokens carry no form/lemma.
"""

from __future__ import annotations

import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path

from ..data import cache_dir, download_file
from .heldout import HeldoutSplit, HeldoutToken, TagSentence, isolated, score
from .treebank import _clean_lemma

__all__ = ["evaluate_on_proiel", "load_proiel_gold", "proiel_dir"]

# PROIEL treebank, pinned for reproducibility (github.com/proiel/proiel-treebank).
_COMMIT = "8e388967a1335ed12335ddc655fe46993ee7d57a"
_BASE_URL = f"https://raw.githubusercontent.com/proiel/proiel-treebank/{_COMMIT}/"
_CACHE_SUBDIR = "proiel-greek"
_GREEK_FILES: tuple[str, ...] = ("greek-nt.xml", "hdt.xml")

# PROIEL part-of-speech tag → universal POS (the tagset is declared in each file header).
_POS_MAP: dict[str, str] = {
    "A-": "ADJ", "Df": "ADV", "S-": "DET", "Ma": "NUM", "Nb": "NOUN", "C-": "CCONJ",
    "Pd": "PRON", "F-": "X", "Px": "PRON", "N-": "PART", "I-": "INTJ", "Du": "ADV",
    "Pi": "PRON", "Mo": "ADJ", "Pp": "PRON", "Pk": "PRON", "Ps": "PRON", "Pt": "PRON",
    "R-": "ADP", "Ne": "PROPN", "Py": "DET", "Pc": "PRON", "Dq": "ADV", "Pr": "PRON",
    "G-": "SCONJ", "V-": "VERB", "X-": "X",
}

# pyaegean's POS comes from the AGDT scheme, which has no PROPN/SCONJ/AUX. Collapse those
# UD-only distinctions on *both* gold and prediction, so the POS number measures real
# disagreements rather than tagset-convention gaps (see aegean.greek.heldout for why).
_POS_CANON: dict[str, str] = {"PROPN": "NOUN", "SCONJ": "CCONJ", "AUX": "VERB"}

_SKIP_POS = frozenset({"PUNCT", "NUM"})  # not scored (matches the AGDT held-out eval)


def _canon_pos(pos: str) -> str:
    return _POS_CANON.get(pos, pos)


def _clean_gold_lemma(lemma: str) -> str:
    """A PROIEL lemma made comparable: drop the ``#N`` homograph suffix (``εἰμί#1`` →
    ``εἰμί``), then apply the treebank lemma cleanup (NFC + strip trailing homonym digits)
    that scoring also applies to predictions."""
    return _clean_lemma(lemma.split("#", 1)[0])


def proiel_dir(*, download: bool = True, files: tuple[str, ...] = _GREEK_FILES) -> Path:
    """The cache directory of PROIEL Greek XML files, fetching any missing on first use.
    The data is CC BY-NC-SA 3.0 — kept in the cache for evaluation only, never bundled."""
    d = cache_dir() / _CACHE_SUBDIR
    if download:
        for name in files:
            dest = d / name
            if not dest.exists():
                download_file(_BASE_URL + name, dest)
    return d


def _parse_file(path: Path) -> list[tuple[HeldoutToken, ...]]:
    """Parse one PROIEL XML file into gold sentences, skipping empty/null tokens."""
    sentences: list[tuple[HeldoutToken, ...]] = []
    cur: list[HeldoutToken] = []
    for _event, elem in ET.iterparse(str(path), events=("end",)):
        if elem.tag == "token":
            form = elem.get("form")
            lemma = elem.get("lemma")
            pos = elem.get("part-of-speech")
            if form and lemma and pos:  # empty tokens carry no form/lemma/POS
                upos = _canon_pos(_POS_MAP.get(pos, "X"))
                cur.append(
                    HeldoutToken(
                        form=unicodedata.normalize("NFC", form),
                        lemma=_clean_gold_lemma(lemma),
                        upos=upos,
                        seen=False,  # pyaegean never trained on PROIEL
                        scored=upos not in _SKIP_POS,
                    )
                )
        elif elem.tag == "sentence":
            if cur:
                sentences.append(tuple(cur))
            cur = []
            elem.clear()
    return sentences


def load_proiel_gold(
    *, source_dir: Path | str | None = None, files: tuple[str, ...] = _GREEK_FILES
) -> tuple[tuple[HeldoutToken, ...], ...]:
    """Parse the PROIEL Greek treebank into gold sentences of (form, lemma, POS) tokens.

    Fetches the pinned PROIEL files into the cache unless ``source_dir`` is given (tests
    pass a local fixture for an offline run). Empty tokens are dropped, lemmas cleaned
    (``#N`` homograph suffix removed), and POS mapped to pyaegean's tagset convention.
    Every token is flagged ``seen=False`` — PROIEL is wholly outside pyaegean's training."""
    if source_dir is not None:
        paths = sorted(Path(source_dir).glob("*.xml"))
    else:
        d = proiel_dir(download=True, files=files)
        paths = [d / name for name in files]
    sentences: list[tuple[HeldoutToken, ...]] = []
    for p in paths:
        if p.exists():
            sentences.extend(_parse_file(p))
    return tuple(sentences)


def _gold_split(
    *, source_dir: Path | str | None = None, files: tuple[str, ...] = _GREEK_FILES
) -> HeldoutSplit:
    """A HeldoutSplit of PROIEL gold with empty train lookups and all tokens unseen — so
    the heldout scorer's overall and unseen accuracies coincide by construction."""
    return HeldoutSplit(
        sentences=load_proiel_gold(source_dir=source_dir, files=files),
        train_forms=frozenset(),
        train_lemma={},
        train_pos={},
    )


def evaluate_on_proiel(
    tag_sentence: TagSentence | None = None,
    *,
    source_dir: Path | str | None = None,
    files: tuple[str, ...] = _GREEK_FILES,
) -> dict[str, float]:
    """Score a tagger on PROIEL gold — the neutral, out-of-AGDT generalization number.

    ``tag_sentence`` maps a sentence's forms to ``(lemma, pos)`` per token; it defaults to
    pyaegean's current pipeline (``lemmatize`` + ``pos_tag``, honouring whichever backends
    are active — enable ``use_treebank``/``use_neural_lemmatizer`` first to measure them).
    Returns ``{"lemma", "pos", "n"}``: lemma and POS accuracy over the scored tokens. Lemma
    is the clean metric; POS is compared under a reconciled tagset (PROPN→NOUN, SCONJ→CCONJ).
    The PROIEL files are fetched on first use unless ``source_dir`` points at local XML."""
    if tag_sentence is None:
        from .lemmatize import lemmatize
        from .pos import pos_tag

        tag_sentence = isolated(lemmatize, pos_tag)
    base = tag_sentence  # non-None; named so the closure's type is clean

    def reconciled(forms: list[str]) -> list[tuple[str, str]]:
        return [(lemma, _canon_pos(pos)) for lemma, pos in base(forms)]

    result = score(reconciled, split=_gold_split(source_dir=source_dir, files=files))
    return {"lemma": result["lemma_all"], "pos": result["pos_all"], "n": result["n_all"]}
