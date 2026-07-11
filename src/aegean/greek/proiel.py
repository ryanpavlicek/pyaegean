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
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..data import cache_dir, download_file
from .heldout import HeldoutSplit, HeldoutToken, TagSentence, isolated, score
from .treebank import _clean_lemma
from .udfeats import feats_from_xpos

__all__ = [
    "ConventionReport",
    "DeprelConfusion",
    "DriftReport",
    "FeatureConventionStat",
    "NeuralPipelineRequiredError",
    "evaluate_on_proiel",
    "load_proiel_gold",
    "proiel_convention_report",
    "proiel_dir",
    "proiel_drift",
]

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


@dataclass(frozen=True, slots=True)
class DriftReport:
    """Where the PROIEL gap comes from — so systematic annotation-convention divergence can be
    told apart from scattered real error.

    The shipped model is trained on the AGDT convention; scoring it on the differently-annotated
    PROIEL conflates real mistakes with convention differences. ``pos_confusions`` lists the
    (gold POS → predicted POS) disagreements most-frequent first: a few pairs carrying most of
    the POS errors points to a convention difference, a long flat tail to genuine error.
    ``lemma_mismatches`` samples the lemma disagreements (often homograph or normalization
    convention). POS here is already reconciled (PROPN→NOUN, SCONJ→CCONJ, AUX→VERB), so what
    remains is *other* convention drift plus real error."""

    pos_confusions: tuple[tuple[str, str, int], ...]     # (gold, predicted, count)
    lemma_mismatches: tuple[tuple[str, str, str], ...]   # (form, gold lemma, predicted lemma)
    pos_scored: int
    pos_errors: int
    lemma_errors: int

    @property
    def pos_accuracy(self) -> float:
        """POS accuracy over the scored tokens (the same number `evaluate_on_proiel` reports)."""
        return (self.pos_scored - self.pos_errors) / self.pos_scored if self.pos_scored else 0.0

    @property
    def lemma_accuracy(self) -> float:
        """Lemma accuracy over the scored tokens."""
        return (self.pos_scored - self.lemma_errors) / self.pos_scored if self.pos_scored else 0.0

    @property
    def top_share(self) -> float:
        """Fraction of POS errors in the single most common confusion pair — a rough
        systematic-vs-scattered signal (higher → more convention-like)."""
        if not self.pos_errors or not self.pos_confusions:
            return 0.0
        return self.pos_confusions[0][2] / self.pos_errors

    def summary(self, *, top: int = 8) -> str:
        """A short, readable breakdown of the top POS confusions."""
        if not self.pos_scored:
            return "PROIEL drift: no scored tokens"
        out = [
            f"PROIEL drift over {self.pos_scored} scored tokens: {self.pos_errors} POS "
            f"disagreements ({self.pos_errors / self.pos_scored:.1%}), {self.lemma_errors} lemma",
            "  top POS confusions (gold → predicted):",
        ]
        out += [
            f"    {g} → {p}: {c}" + (f" ({c / self.pos_errors:.0%} of POS errors)" if self.pos_errors else "")
            for g, p, c in self.pos_confusions[:top]
        ]
        return "\n".join(out)


def _reconciled(tag_sentence: TagSentence | None) -> TagSentence:
    """The default pipeline tagger if none is given, wrapped to reconcile predicted POS to
    pyaegean's tagset (PROPN→NOUN, SCONJ→CCONJ, AUX→VERB) — matching the gold side."""
    if tag_sentence is None:
        from .lemmatize import lemmatize
        from .pos import pos_tag

        tag_sentence = isolated(lemmatize, pos_tag)
    base = tag_sentence

    def reconciled(forms: list[str]) -> list[tuple[str, str]]:
        return [(lemma, _canon_pos(pos)) for lemma, pos in base(forms)]

    return reconciled


def evaluate_on_proiel(
    tag_sentence: TagSentence | None = None,
    *,
    source_dir: Path | str | None = None,
    files: tuple[str, ...] = _GREEK_FILES,
    progress: Callable[[int, int], None] | None = None,
) -> dict[str, float]:
    """Score a tagger on PROIEL gold — the neutral, out-of-AGDT generalization number.

    ``tag_sentence`` maps a sentence's forms to ``(lemma, pos)`` per token; it defaults to
    pyaegean's current pipeline (``lemmatize`` + ``pos_tag``, honouring whichever backends
    are active — enable ``use_treebank``/``use_neural_lemmatizer`` first to measure them).
    ``progress`` (optional) is called as ``progress(done, total)`` per scored sentence.
    Returns ``{"lemma", "pos", "n"}``: lemma and POS accuracy over the scored tokens. Lemma
    is the clean metric; POS is compared under a reconciled tagset (PROPN→NOUN, SCONJ→CCONJ).
    See `proiel_drift` for *where* the gap comes from. The PROIEL files are fetched on first
    use unless ``source_dir`` points at local XML."""
    result = score(
        _reconciled(tag_sentence),
        split=_gold_split(source_dir=source_dir, files=files),
        progress=progress,
    )
    return {"lemma": result["lemma_all"], "pos": result["pos_all"], "n": result["n_all"]}


def proiel_drift(
    tag_sentence: TagSentence | None = None,
    *,
    source_dir: Path | str | None = None,
    files: tuple[str, ...] = _GREEK_FILES,
    samples: int = 40,
) -> DriftReport:
    """Quantify *where* the PROIEL gap comes from, so systematic annotation-convention
    divergence can be separated from scattered real error.

    Re-tags the PROIEL gold with the same (reconciled) tagger `evaluate_on_proiel` uses and
    returns a `DriftReport`: the gold→predicted POS confusion matrix (most-frequent first), a
    sample of lemma mismatches, and the scored counts. A few confusion pairs carrying most of
    the POS errors (high ``top_share``) suggests a convention difference rather than real
    error. ``tag_sentence`` and ``source_dir`` are as for `evaluate_on_proiel`.

    This is now a thin PROIEL view of the shared `aegean.greek.erroranalysis` engine (which
    also serves UD-Perseus, the NT, and the AGDT held-out split, and carries richer per-POS /
    seen-unseen breakdowns): see `erroranalysis.proiel_error_analysis` for the full report."""
    from .erroranalysis import analyze_errors

    ea = analyze_errors(
        _reconciled(tag_sentence),
        load_proiel_gold(source_dir=source_dir, files=files),
        samples=samples,
    )
    return DriftReport(
        pos_confusions=ea.pos_confusions,
        lemma_mismatches=ea.lemma_mismatches,
        pos_scored=ea.pos_scored,
        pos_errors=ea.pos_errors,
        lemma_errors=ea.lemma_errors,
    )


# ── UD-fold convention decomposition (UFeats + LAS) ───────────────────────────────
#
# The published PROIEL UD-fold numbers — UFeats, UAS, LAS — come from
# ``evaluate_on_ud("proiel", "test")`` with the neural pipeline, a DIFFERENT path from the
# raw-XML ``evaluate_on_proiel`` above (which scores only lemma/POS). Those numbers are
# capped by annotation-convention divergence: PROIEL and UD-Perseus (the AGDT convention the
# model is trained on) render the same Greek under different feature and relation schemes.
# The two decompositions below MEASURE that cap — how much of each gap is convention the
# AGDT-trained model structurally cannot close, versus real disagreement on the shared
# scheme. This is measurement only: nothing is re-scored into the published rows and nothing
# is fitted to the fold. The strict official UFeats/UAS/LAS are unchanged; the decomposition
# accounts for them.

# The universal feature types the official CoNLL-18 evaluator scores for UFeats (it drops
# every language-specific feature before comparing, ``conll18_ud_eval.UNIVERSAL_FEATURES``).
# Mirrored here so the decomposition partitions exactly the mass UFeats is computed over.
_UNIVERSAL_FEATURES = frozenset({
    "PronType", "NumType", "Poss", "Reflex", "Foreign", "Abbr", "Gender", "Animacy",
    "Number", "Case", "Definite", "Degree", "VerbForm", "Mood", "Tense", "Aspect",
    "Voice", "Evident", "Polarity", "Person", "Polite",
})


def _model_feature_types() -> frozenset[str]:
    """The UD feature types the AGDT→UD morphology renderer (`udfeats.feats_from_xpos`) can
    ever emit, probed exhaustively over each of the 9 postag positions so the set can never
    silently drift from the renderer. A gold universal feature type outside this set is one
    the AGDT/UD-Perseus scheme never produces — the model structurally cannot match a word
    that carries it (its rendered feature bundle will always lack that key)."""
    keys: set[str] = set()
    for pos in range(9):
        for ch in "-0123456789abcdefghijklmnopqrstuvwxyz":
            x = ["-"] * 9
            x[pos] = ch
            rendered = feats_from_xpos("".join(x))
            if rendered != "_":
                keys.update(item.split("=", 1)[0] for item in rendered.split("|"))
    return frozenset(keys)


# The model's emittable feature-type inventory (computed once from the renderer):
# {Case, Gender, Number, Person, Tense, Aspect, Mood, VerbForm, Voice, Degree}.
_MODEL_FEATURE_TYPES = _model_feature_types()


def _parse_feats(feats: str) -> dict[str, str]:
    """A CoNLL-U FEATS string → ``{type: value}``, restricted to the universal feature types
    the evaluator scores (so ``_``/empty → ``{}`` and language-specific features are dropped,
    exactly as ``conll18_ud_eval`` does before the UFeats comparison)."""
    if not feats or feats == "_":
        return {}
    out: dict[str, str] = {}
    for item in feats.split("|"):
        key, _, value = item.partition("=")
        if value and key in _UNIVERSAL_FEATURES:
            out[key] = value
    return out


def _base_deprel(deprel: str) -> str:
    """The universal relation without its language-specific subtype (``obl:arg`` → ``obl``),
    matching the evaluator's LAS, which ignores subtypes (``columns[DEPREL].split(':')[0]``)."""
    return deprel.split(":", 1)[0]


class NeuralPipelineRequiredError(RuntimeError):
    """Raised when `proiel_convention_report` is called with no neural pipeline active and no
    injected ``predictions``."""


@dataclass(frozen=True, slots=True)
class FeatureConventionStat:
    """One UD feature type's contribution to the UFeats gap.

    ``gold_count`` is how many scored gold words carry this (universal) feature.
    ``emitted_by_model_scheme`` is whether the AGDT→UD renderer can produce it at all — when
    False the feature is *scheme-absent* and every gold word carrying it is an unavoidable
    UFeats miss. ``shared_agree`` counts, among those gold words, how many the model labels
    with the SAME value (0 for a scheme-absent feature)."""

    feature: str
    gold_count: int
    emitted_by_model_scheme: bool
    shared_agree: int

    @property
    def agreement_on_shared(self) -> float:
        """Fraction of gold words carrying this feature that the model labels with the same
        value. 0.0 for a scheme-absent feature (the model never emits it)."""
        return self.shared_agree / self.gold_count if self.gold_count else 0.0


@dataclass(frozen=True, slots=True)
class DeprelConfusion:
    """A (gold relation → predicted relation) pair among the attachment-correct/label-wrong
    tokens — the label-only errors that separate UAS from LAS. Subtypes are stripped (the
    evaluator's LAS convention)."""

    gold: str
    predicted: str
    count: int


@dataclass(frozen=True, slots=True)
class ConventionReport:
    """Where the PROIEL UD-fold UFeats and LAS gaps come from, told apart into
    annotation-convention divergence (the AGDT-trained model structurally cannot close it)
    and real disagreement on the shared scheme.

    Measurement only — it reproduces the official UFeats/UAS/LAS from the model's own outputs
    and partitions them; it does not replace any published number and nothing is fitted to the
    fold. Every count is over the fold's scored words (the evaluator scores every aligned
    syntactic word for these metrics; unlike the POS/lemma drift view it does not skip
    PUNCT/NUM)."""

    n_words: int
    # --- UFeats decomposition ---
    ufeats_correct: int          # words whose full universal-feature bundle matches gold
    n_scheme_blocked_words: int  # gold word carries ≥1 universal feature the model can't emit
    n_shared_only_words: int     # gold word's universal features are all model-emittable
    shared_only_correct: int     # full-bundle matches among the shared-only words
    feature_stats: tuple[FeatureConventionStat, ...]   # most-frequent gold feature first
    # --- LAS / deprel decomposition ---
    uas_correct: int
    las_correct: int
    label_only_errors: int       # head correct, base relation wrong (the UAS↔LAS gap mass)
    deprel_confusions: tuple[DeprelConfusion, ...]     # among label-only errors, most first

    # -- UFeats --
    @property
    def ufeats(self) -> float:
        """Per-word UFeats accuracy (reproduces the official UFeats F1 under gold
        tokenization, where precision = recall = accuracy)."""
        return self.ufeats_correct / self.n_words if self.n_words else 0.0

    @property
    def ufeats_gap(self) -> float:
        return 1.0 - self.ufeats

    @property
    def gap_scheme_absent(self) -> float:
        """The share of ALL words lost purely to scheme-absent features (words carrying a
        universal feature the model can never emit — an unavoidable UFeats miss). One of the
        two additive parts of the UFeats gap."""
        return self.n_scheme_blocked_words / self.n_words if self.n_words else 0.0

    @property
    def gap_shared_disagreement(self) -> float:
        """The share of ALL words lost to disagreement WITHIN the shared scheme (the other
        additive part; ``gap_scheme_absent + gap_shared_disagreement == ufeats_gap``)."""
        wrong_shared = self.n_shared_only_words - self.shared_only_correct
        return wrong_shared / self.n_words if self.n_words else 0.0

    @property
    def shared_subset_ufeats(self) -> float:
        """UFeats accuracy on the subset of words whose gold features are all scheme-shared —
        the model's morphology quality with the convention gap removed."""
        return self.shared_only_correct / self.n_shared_only_words if self.n_shared_only_words else 0.0

    @property
    def scheme_absent_features(self) -> tuple[FeatureConventionStat, ...]:
        """The universal feature types PROIEL uses that the AGDT scheme never emits, by count."""
        return tuple(s for s in self.feature_stats if not s.emitted_by_model_scheme and s.gold_count)

    # -- LAS --
    @property
    def uas(self) -> float:
        return self.uas_correct / self.n_words if self.n_words else 0.0

    @property
    def las(self) -> float:
        return self.las_correct / self.n_words if self.n_words else 0.0

    @property
    def label_only_share(self) -> float:
        """The share of ALL words that are attachment-correct but label-wrong — the part of
        the LAS gap that is pure relabelling (``uas - las == label_only_share``)."""
        return self.label_only_errors / self.n_words if self.n_words else 0.0

    @property
    def deprel_top_share(self) -> float:
        """Fraction of the label-only-error mass in the single most common relation confusion
        (higher → more systematic/convention-like, lower → more scattered)."""
        if not self.label_only_errors or not self.deprel_confusions:
            return 0.0
        return self.deprel_confusions[0].count / self.label_only_errors

    def deprel_concentration(self, top: int = 5) -> float:
        """Fraction of the label-only-error mass in the top-``top`` relation confusions."""
        if not self.label_only_errors:
            return 0.0
        return sum(c.count for c in self.deprel_confusions[:top]) / self.label_only_errors

    def summary(self, *, top: int = 8) -> str:
        """A short, readable account of both decompositions."""
        if not self.n_words:
            return "PROIEL convention decomposition: no words"
        out = [
            f"PROIEL UD-fold convention decomposition over {self.n_words} words",
            f"  UFeats {self.ufeats:.1%} (gap {self.ufeats_gap:.1%}): "
            f"{self.gap_scheme_absent:.1%} scheme-absent features + "
            f"{self.gap_shared_disagreement:.1%} shared-scheme disagreement",
            f"    on the shared-only subset ({self.n_shared_only_words} words) the model "
            f"scores UFeats {self.shared_subset_ufeats:.1%}",
        ]
        absent = self.scheme_absent_features
        if absent:
            out.append("    scheme-absent universal features (PROIEL uses, AGDT scheme never emits):")
            out += [f"      {s.feature}: {s.gold_count} gold words" for s in absent[:top]]
        shared = [s for s in self.feature_stats if s.emitted_by_model_scheme and s.gold_count]
        if shared:
            out.append("    shared-feature agreement (gold words carrying it → same value):")
            out += [
                f"      {s.feature}: {s.agreement_on_shared:.1%} of {s.gold_count}"
                for s in shared[:top]
            ]
        out.append(
            f"  LAS {self.las:.1%} vs UAS {self.uas:.1%}: {self.label_only_share:.1%} of words "
            f"are attachment-correct but label-wrong ({self.label_only_errors} tokens)"
        )
        if self.deprel_confusions:
            out.append("    top gold → predicted relation confusions (share of label-only mass):")
            out += [
                f"      {c.gold} → {c.predicted}: {c.count}"
                + (f" ({c.count / self.label_only_errors:.0%})" if self.label_only_errors else "")
                for c in self.deprel_confusions[:top]
            ]
        return "\n".join(out)

    def as_dict(self) -> dict[str, Any]:
        """A JSON-serializable view (for ``--json`` and receipts)."""
        return {
            "n_words": self.n_words,
            "ufeats": self.ufeats,
            "ufeats_gap": self.ufeats_gap,
            "gap_scheme_absent": self.gap_scheme_absent,
            "gap_shared_disagreement": self.gap_shared_disagreement,
            "shared_subset_ufeats": self.shared_subset_ufeats,
            "n_scheme_blocked_words": self.n_scheme_blocked_words,
            "n_shared_only_words": self.n_shared_only_words,
            "feature_stats": [
                {
                    "feature": s.feature,
                    "gold_count": s.gold_count,
                    "emitted_by_model_scheme": s.emitted_by_model_scheme,
                    "agreement_on_shared": s.agreement_on_shared,
                }
                for s in self.feature_stats
            ],
            "uas": self.uas,
            "las": self.las,
            "label_only_errors": self.label_only_errors,
            "label_only_share": self.label_only_share,
            "deprel_top_share": self.deprel_top_share,
            "deprel_confusions": [[c.gold, c.predicted, c.count] for c in self.deprel_confusions],
        }


# A gold or system token reduced to the three fields the decomposition compares.
_ConvToken = tuple[str, int, str]  # (feats, head, deprel)


def _decompose_conventions(
    gold: Sequence[Sequence[_ConvToken]],
    system: Sequence[Sequence[_ConvToken]],
) -> ConventionReport:
    """The pure decomposition core: align gold and system word-for-word (gold tokenization →
    identical token sequences) and tabulate the UFeats and LAS convention splits.

    Each token is ``(feats, head, deprel)``. Every word counts (the evaluator scores all
    aligned syntactic words for UFeats/UAS/LAS). Injected directly by the tests so the split
    can be checked against numbers known by construction; `proiel_convention_report` builds
    the two arguments from the fold gold and the model's outputs."""
    n_words = ufeats_correct = 0
    n_scheme_blocked = n_shared_only = shared_only_correct = 0
    uas_correct = las_correct = label_only_errors = 0
    gold_count: Counter[str] = Counter()
    shared_agree: Counter[str] = Counter()
    deprel_confus: Counter[tuple[str, str]] = Counter()

    for g_sent, s_sent in zip(gold, system, strict=True):
        for (g_feats, g_head, g_deprel), (s_feats, s_head, s_deprel) in zip(
            g_sent, s_sent, strict=True
        ):
            n_words += 1
            gf = _parse_feats(g_feats)
            sf = _parse_feats(s_feats)
            # UFeats: the whole universal-feature bundle must match (the evaluator's rule).
            if gf == sf:
                ufeats_correct += 1
            # Convention split: a gold word carrying a feature the model can never emit is an
            # unavoidable miss; otherwise it is a shared-only word scored on real agreement.
            blocked = any(k not in _MODEL_FEATURE_TYPES for k in gf)
            if blocked:
                n_scheme_blocked += 1
            else:
                n_shared_only += 1
                if gf == sf:
                    shared_only_correct += 1
            for k, v in gf.items():
                gold_count[k] += 1
                if sf.get(k) == v:
                    shared_agree[k] += 1
            # LAS vs UAS: head is 1-based (0 = root); the relation is compared subtype-free.
            head_ok = g_head == s_head
            label_ok = _base_deprel(g_deprel) == _base_deprel(s_deprel)
            if head_ok:
                uas_correct += 1
                if label_ok:
                    las_correct += 1
                else:
                    label_only_errors += 1
                    deprel_confus[(_base_deprel(g_deprel), _base_deprel(s_deprel))] += 1

    feature_stats = tuple(
        FeatureConventionStat(
            feature=feat,
            gold_count=cnt,
            emitted_by_model_scheme=feat in _MODEL_FEATURE_TYPES,
            shared_agree=shared_agree[feat],
        )
        for feat, cnt in gold_count.most_common()
    )
    deprel_confusions = tuple(
        DeprelConfusion(gold=g, predicted=p, count=c)
        for (g, p), c in deprel_confus.most_common()
    )
    return ConventionReport(
        n_words=n_words,
        ufeats_correct=ufeats_correct,
        n_scheme_blocked_words=n_scheme_blocked,
        n_shared_only_words=n_shared_only,
        shared_only_correct=shared_only_correct,
        feature_stats=feature_stats,
        uas_correct=uas_correct,
        las_correct=las_correct,
        label_only_errors=label_only_errors,
        deprel_confusions=deprel_confusions,
    )


def proiel_convention_report(
    *,
    split: str = "test",
    source: Path | str | None = None,
    batch_size: int | None = 32,
    progress: Callable[[int, int], None] | None = None,
    predictions: Sequence[Sequence[_ConvToken]] | None = None,
) -> ConventionReport:
    """Decompose the PROIEL UD-fold UFeats and LAS gaps into annotation-convention divergence
    versus real disagreement, on the neural pipeline's own outputs.

    Runs the active neural pipeline (`aegean.greek.use_neural_pipeline` — the model behind the
    published UD-PROIEL numbers) over the fold's gold tokens and compares its FEATS/HEAD/DEPREL
    to gold. Returns a `ConventionReport` whose ``ufeats``/``uas``/``las`` reproduce the
    official metrics from the model's outputs, split into: the UFeats gap's scheme-absent vs
    shared-disagreement parts (with a per-feature-type table), and the LAS gap's
    attachment-correct/label-wrong mass (with the gold→predicted relation confusions). This is
    a measurement DECOMPOSITION: it changes no published number and fits nothing to the fold.

    ``source`` overrides the UD-PROIEL fold path (tests pass a local CoNLL-U fixture);
    ``batch_size`` batches the encoder passes (a throughput convenience — the diagnostic does
    not feed the recorded sequential protocol); ``progress`` is called ``progress(done,
    total)`` per sentence. ``predictions`` injects the system outputs directly (one
    ``(feats, head, deprel)`` per gold token, sentence-aligned) so the decomposition can be
    exercised without the model; with it, no pipeline is required."""
    from .ud import load_conllu, ud_path

    gold_path = Path(source) if source is not None else ud_path("proiel", split)
    sentences = load_conllu(gold_path)
    gold: list[list[_ConvToken]] = [
        [(t.feats, t.head, t.deprel) for t in s.tokens] for s in sentences
    ]

    if predictions is not None:
        system: Sequence[Sequence[_ConvToken]] = predictions
    else:
        from . import joint

        model = joint.active()
        if model is None:
            raise NeuralPipelineRequiredError(
                "proiel_convention_report needs the neural pipeline active (it decomposes the "
                "neural model's UFeats/LAS): call aegean.greek.use_neural_pipeline() first, or "
                "pass predictions= to inject system outputs."
            )
        system = _model_predictions(
            model, [[t.form for t in s.tokens] for s in sentences],
            batch_size=batch_size, progress=progress,
        )
    return _decompose_conventions(gold, system)


def _model_predictions(
    model: Any,
    forms: Sequence[Sequence[str]],
    *,
    batch_size: int | None,
    progress: Callable[[int, int], None] | None,
) -> list[list[_ConvToken]]:
    """Run the joint model over each sentence's gold forms → ``(feats, head, deprel)`` per
    token. Batched when ``batch_size`` is set (the fold is ~1k sentences); the analyses are
    the same fields either way."""
    forms_list = [list(f) for f in forms]
    total = len(forms_list)
    out: list[list[_ConvToken]] = []
    done = 0
    if batch_size is not None and batch_size >= 1:
        for start in range(0, total, batch_size):
            chunk = forms_list[start : start + batch_size]
            for ana in model.analyze_batch(chunk):
                out.append(list(zip(ana.feats, ana.head, ana.deprel)))
                done += 1
                if progress is not None:
                    progress(done, total)
    else:
        for sent in forms_list:
            ana = model.analyze(sent)
            out.append(list(zip(ana.feats, ana.head, ana.deprel)))
            done += 1
            if progress is not None:
                progress(done, total)
    return out
