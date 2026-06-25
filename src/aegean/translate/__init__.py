"""Hybrid translation: lexicon/morphology grounding → LLM.

Builds grounding evidence from the package's own tooling (Greek lemmatizer plus
gated, content-word LSJ glosses; Linear A sign→sound transliteration), then hands
the text plus that evidence to `aegean.ai.translate`. The grounding step is
deterministic and local; the translation itself is generative and returned as an
exploratory, provenanced `ExploratoryResult`.

The Greek gloss grounding is deliberately selective (see `ai.grounding.content_glosses`):
it glosses only low-polysemy content words, where the dominant-sense gloss is reliable,
and leaves highly polysemous words to the model — an ungated first-sense gloss for a
word like στάσις or κρίσις is often the wrong contextual sense and degrades a capable
model. Most useful for weaker models and obscure, dominant-sense vocabulary.
"""

from __future__ import annotations

import warnings

from ..ai import translate as _ai_translate
from ..ai.client import ExploratoryResult, LLMClient
from ..ai.grounding import GroundingItem, content_glosses

_SOURCE_NAMES = {"greek": "Ancient Greek", "lineara": "Linear A"}


def _rich_lemmatizer_active() -> bool:
    """Whether a lemmatizer better than the bundled seed table is loaded — the
    treebank, neural pipeline, GreTa, or edit-tree backend. Lexical grounding on rare
    or inflected forms depends on one of these being active."""
    from ..greek import joint, lemmatizer, neural_lemmatizer, treebank

    return any(m.active() is not None for m in (joint, treebank, neural_lemmatizer, lemmatizer))


def _greek_grounding(text: str, *, glosses: bool = True) -> list[GroundingItem]:
    from ..greek import lemmatize_verbose, tokenize_words

    out: list[GroundingItem] = []
    for w in tokenize_words(text):
        lemma, known = lemmatize_verbose(w)
        if known:
            out.append(GroundingItem(f"{w} → lemma {lemma}", source="lemmatizer", ref=w))
    if glosses:
        # Gated LSJ glosses for content words — best-effort, empty without greek.use_lsj().
        out.extend(content_glosses(text))
    return out


def _lineara_grounding(text: str) -> list[GroundingItem]:
    from ..scripts.lineara.phonetic import word_to_phonetic

    return [
        GroundingItem(f"{w} → /{word_to_phonetic(w)}/", source="transliteration", ref=w)
        for w in text.split()
        if "-" in w
    ]


def grounding_for(text: str, script: str, *, glosses: bool = True) -> list[GroundingItem]:
    """Local, deterministic grounding evidence for ``text`` in ``script`` — each
    item tagged with its source (``lemmatizer`` / ``transliteration``) so the
    result's `trace()` shows where the grounding came from. For ``greek``, ``glosses``
    controls whether gated LSJ glosses are added on top of the lemma grounding."""
    if script == "greek":
        return _greek_grounding(text, glosses=glosses)
    if script == "lineara":
        return _lineara_grounding(text)
    return []


def translate(
    text: str,
    *,
    script: str = "greek",
    target: str = "English",
    glosses: bool = True,
    client: LLMClient | None = None,
) -> ExploratoryResult:
    """Translate ``text`` (a ``greek`` or ``lineara`` string) into ``target``,
    grounded in locally-derived lexicon/transliteration evidence.

    Exploratory: the grounding is real, the translation is a model hypothesis —
    especially for undeciphered Linear A.

    For ``greek``, ``glosses`` (default ``True``) adds gated, content-word LSJ glosses to
    the lemma grounding. These help most on **rare or documentary vocabulary the model
    would otherwise misread** — their value is proportional to that headroom. On text a
    capable model already handles well they are neutral to mildly counterproductive (an
    unnecessary gloss can nudge a correct reading), and a richer lemmatizer that glosses
    more words amplifies both effects. Pass ``glosses=False`` for lemma-only grounding on
    familiar text. Coverage of rare/inflected forms depends on the active lemmatizer, so a
    warning is raised when only the baseline seed table is loaded (call
    ``aegean.greek.use_treebank()`` or ``use_neural_lemmatizer()`` first).
    """
    if script == "greek" and glosses and not _rich_lemmatizer_active():
        warnings.warn(
            "Grounded Greek translation is using the baseline lemmatizer; lexical "
            "grounding will miss many rare or inflected forms. Call "
            "aegean.greek.use_treebank() (or aegean.greek.use_neural_lemmatizer() for the "
            "fullest coverage on oblique/documentary forms) first for fuller grounding.",
            stacklevel=2,
        )
    source = _SOURCE_NAMES.get(script, script)
    return _ai_translate(
        text,
        source=source,
        target=target,
        grounding=grounding_for(text, script, glosses=glosses),
        client=client,
    )


__all__ = ["translate", "grounding_for"]
