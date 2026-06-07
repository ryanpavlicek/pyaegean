"""Hybrid translation: lexicon/morphology grounding → LLM.

Builds grounding evidence from the package's own tooling (Greek baseline
lemmatizer, Linear A sign→sound transliteration), then hands the text plus that
evidence to :func:`aegean.ai.translate`. The grounding step is deterministic and
local; the translation itself is generative and returned as an exploratory,
provenanced :class:`~aegean.ai.ExploratoryResult`.
"""

from __future__ import annotations

from ..ai import translate as _ai_translate
from ..ai.client import ExploratoryResult, LLMClient

_SOURCE_NAMES = {"greek": "Ancient Greek", "lineara": "Linear A"}


def _greek_grounding(text: str) -> list[str]:
    from ..greek import lemmatize_verbose, tokenize_words

    out: list[str] = []
    for w in tokenize_words(text):
        lemma, known = lemmatize_verbose(w)
        if known:
            out.append(f"{w} → lemma {lemma}")
    return out


def _lineara_grounding(text: str) -> list[str]:
    from ..scripts.lineara.phonetic import word_to_phonetic

    return [
        f"{w} → /{word_to_phonetic(w)}/"
        for w in text.split()
        if "-" in w
    ]


def grounding_for(text: str, script: str) -> list[str]:
    """Local, deterministic grounding evidence for ``text`` in ``script``."""
    if script == "greek":
        return _greek_grounding(text)
    if script == "lineara":
        return _lineara_grounding(text)
    return []


def translate(
    text: str,
    *,
    script: str = "greek",
    target: str = "English",
    client: LLMClient | None = None,
) -> ExploratoryResult:
    """Translate ``text`` (a ``greek`` or ``lineara`` string) into ``target``,
    grounded in locally-derived lexicon/transliteration evidence.

    Exploratory: the grounding is real, the translation is a model hypothesis —
    especially for undeciphered Linear A.
    """
    source = _SOURCE_NAMES.get(script, script)
    return _ai_translate(
        text,
        source=source,
        target=target,
        grounding=grounding_for(text, script),
        client=client,
    )


__all__ = ["translate", "grounding_for"]
