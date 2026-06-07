"""Benchmark harness for the Greek pipeline.

Scores each stage (tokenize, syllabify, accent classification, lemmatization)
against a small hand-authored gold set, and compares any candidate lemmatizer —
notably **CLTK** — on the same gold. This operationalizes the project's goal
("match-or-beat CLTK on Greek") as a measured metric, while keeping CLTK a
*benchmark target, never a dependency*: the comparison takes an injected
lemmatize callable, so nothing here imports CLTK.

```python
from aegean.greek import benchmark
scores = benchmark.run_benchmark()
for stage, s in scores.items():
    print(stage, f"{s.accuracy:.0%}", f"({s.correct}/{s.total})")

# Compare against CLTK (only when it's installed):
from cltk import NLP
nlp = NLP(language="grc", suppress_banner=True)
def cltk_lemma(w): return nlp.analyze(w).lemmata[0]
benchmark.compare_lemmatizers(cltk_lemma)   # {'pyaegean': Score, 'candidate': Score}
```
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ..data import load_bundled_json
from .accent import accentuation
from .lemmatize import lemmatize
from .syllabify import syllabify
from .tokenize import tokenize_words


@dataclass(frozen=True, slots=True)
class Score:
    """A stage's accuracy on the gold set."""

    stage: str
    total: int
    correct: int

    @property
    def accuracy(self) -> float:
        return self.correct / self.total if self.total else 0.0

    def __str__(self) -> str:
        return f"{self.stage}: {self.accuracy:.0%} ({self.correct}/{self.total})"


def load_gold() -> dict[str, list[dict[str, Any]]]:
    """The bundled gold set (override by passing your own to the scorers)."""
    gold = load_bundled_json("greek", "benchmark_gold.json")
    return {k: v for k, v in gold.items() if not k.startswith("_")}


def _count(items: list[dict[str, Any]], ok: Callable[[dict[str, Any]], bool]) -> int:
    return sum(1 for it in items if ok(it))


def run_benchmark(gold: dict[str, list[dict[str, Any]]] | None = None) -> dict[str, Score]:
    """Score the pyaegean pipeline against ``gold`` (defaults to the bundled set)."""
    g = gold or load_gold()
    tok = g.get("tokenize", [])
    syl = g.get("syllabify", [])
    acc = g.get("accent", [])
    lem = g.get("lemma", [])
    return {
        "tokenize": Score(
            "tokenize", len(tok),
            _count(tok, lambda it: tokenize_words(it["text"]) == it["tokens"]),
        ),
        "syllabify": Score(
            "syllabify", len(syl),
            _count(syl, lambda it: syllabify(it["word"]) == it["syllables"]),
        ),
        "accent": Score(
            "accent", len(acc),
            _count(acc, lambda it: accentuation(it["word"]).classification == it["classification"]),
        ),
        "lemma": Score(
            "lemma", len(lem),
            _count(lem, lambda it: lemmatize(it["word"]) == it["lemma"]),
        ),
    }


def score_lemmatizer(
    predict: Callable[[str], str],
    gold: dict[str, list[dict[str, Any]]] | None = None,
) -> Score:
    """Score an arbitrary lemmatize callable on the lemma gold."""
    lem = (gold or load_gold()).get("lemma", [])
    return Score("lemma", len(lem), _count(lem, lambda it: predict(it["word"]) == it["lemma"]))


def compare_lemmatizers(
    candidate: Callable[[str], str],
    gold: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, Score]:
    """Compare pyaegean's lemmatizer against a ``candidate`` (e.g. CLTK's) on the
    same lemma gold. Returns ``{"pyaegean": Score, "candidate": Score}``."""
    g = gold or load_gold()
    return {
        "pyaegean": score_lemmatizer(lemmatize, g),
        "candidate": score_lemmatizer(candidate, g),
    }
