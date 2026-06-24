"""Terminology rarity: a corpus-relative vocabulary-rarity score for Greek text.

How rare is a text's vocabulary, measured against a reference corpus? Rare, technical, or
documentary terms are where a translator (human or model) is most likely to stumble, so this
is a cheap, offline, deterministic *translation-difficulty* estimator and a guide for when
lexical grounding is worth applying.

Rarity is always **relative to the corpus you pass** — score against the Greek NT and a word's
rarity reflects how unusual it is in Koine; score against a tragedy and it reflects that
register. Each content word is scored by its lemma's frequency in the reference corpus on a
log scale (0 = as common as the corpus's most frequent lemma, 1 = absent from it); the overall
score is the mean over the text's words. Lemmas come from a token's gold annotation when the
corpus carries one (e.g. the NT), otherwise from the active lemmatizer.

Heuristic and exploratory: a rarity score is a difficulty *signal*, not a measured accuracy.
"""

from __future__ import annotations

import math
import unicodedata
from collections import Counter
from dataclasses import dataclass

from ..core.model import TokenKind

__all__ = ["RarityResult", "WordRarity", "terminology_rarity"]


@dataclass(frozen=True, slots=True)
class WordRarity:
    """One word's rarity against the reference corpus."""

    word: str
    lemma: str
    count: int      # the lemma's frequency in the reference corpus
    rarity: float   # 0 (common) .. 1 (absent)
    label: str      # absent / hapax / rare / uncommon / common


@dataclass(frozen=True, slots=True)
class RarityResult:
    """A text's terminology rarity against a reference corpus."""

    overall: float            # mean word rarity, 0 (easy) .. 1 (all-rare)
    words: tuple[WordRarity, ...]
    corpus_lemmas: int        # distinct lemmas in the reference corpus
    corpus_tokens: int        # total word tokens in the reference corpus

    def hardest(self, n: int = 5) -> tuple[WordRarity, ...]:
        """The ``n`` rarest words, most rare first."""
        return tuple(sorted(self.words, key=lambda w: -w.rarity)[:n])


def _norm(s: str) -> str:
    return unicodedata.normalize("NFC", s).strip().lower()


def _label(count: int) -> str:
    if count == 0:
        return "absent"
    if count == 1:
        return "hapax"
    if count <= 5:
        return "rare"
    if count <= 20:
        return "uncommon"
    return "common"


def _corpus_lemma_freqs(corpus: object) -> Counter[str]:
    """Lemma frequencies of a reference corpus: gold lemma from a token's annotation when
    present, else the active lemmatizer."""
    from .lemmatize import lemmatize

    docs = getattr(corpus, "documents", None)
    if docs is None:
        raise TypeError("corpus must expose .documents (an aegean.Corpus or QueryResults)")
    freqs: Counter[str] = Counter()
    for doc in docs:
        for tok in doc.tokens:
            if tok.kind is not TokenKind.WORD:
                continue
            ann = getattr(tok, "annotations", None) or {}
            lemma = ann.get("lemma") or lemmatize(tok.text)
            if lemma:
                freqs[_norm(lemma)] += 1
    return freqs


def terminology_rarity(text: str, corpus: object) -> RarityResult:
    """Score the terminology rarity of ``text`` against a reference ``corpus``.

    ``corpus`` is any `aegean.Corpus` (or `QueryResults`); its word tokens define the
    frequency basis, so the score is relative to that corpus's register. Returns the overall
    score plus a per-word breakdown (use ``.hardest()`` to surface the rare terms).
    """
    from .lemmatize import lemmatize
    from .tokenize import tokenize_words

    freqs = _corpus_lemma_freqs(corpus)
    total = sum(freqs.values())
    max_count = max(freqs.values(), default=0)
    denom = math.log1p(max_count) or 1.0

    out: list[WordRarity] = []
    for w in tokenize_words(text):
        lemma = lemmatize(w) or w
        count = freqs.get(_norm(lemma), 0)
        rarity = 1.0 - math.log1p(count) / denom  # count==0 -> 1.0, max_count -> 0.0
        out.append(WordRarity(word=w, lemma=lemma, count=count, rarity=rarity, label=_label(count)))

    overall = sum(w.rarity for w in out) / len(out) if out else 0.0
    return RarityResult(
        overall=overall, words=tuple(out), corpus_lemmas=len(freqs), corpus_tokens=total
    )
