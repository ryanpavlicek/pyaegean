"""Opt-in OOV-gated lemma candidate generation and reranking for Ancient/Koine Greek.

Builds train-only orthographic, documentary-phonetic, and preverb indices strictly
from a joint model's own training lookup tables (zero external lexicon leakage) and
exposes two reversible, OOV-gated decoders:

1. ``rerank_oov_unique`` — zero-parameter deterministic rescue for out-of-vocabulary
   forms when strict orthographic folding or Koine documentary phonetic folding
   (itacism, vowel length, lunate sigma, gemination, optional final ``-ν``) yields
   a unique train-only lemma.
2. ``rerank_candidates`` / ``fit_oov_reranker`` — conditional log-linear reranker
   over top-K neural edit scripts (with equivalent-edit probability marginalization),
   train-only strict/phonetic folds, preverb-stripped simplex candidates, and
   identity fallback, serializable as a SHA-256-verified ``LemmaRerankerConfig``.

By default (``oov_only=True``), tokens already resolved by exact training lookup
(``neural_lookup``) are never overridden.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
import hashlib
import json
import math
import re
from threading import RLock
from typing import TYPE_CHECKING, Any
import unicodedata

from .lemmatize import LemmaSource
from .neural_preprocessing import _strip_editorial_apparatus

if TYPE_CHECKING:
    from .joint import SentenceAnalysis

__all__ = [
    "FEATURE_NAMES",
    "LemmaCandidate",
    "LemmaRerankerConfig",
    "RerankDecision",
    "TrainOnlyLemmaIndex",
    "disable_oov_lemma_reranker",
    "documentary_phonetic_fold",
    "extract_oov_candidates",
    "fit_oov_reranker",
    "oov_lemma_reranker_active",
    "preverb_candidates",
    "rerank_analysis",
    "rerank_candidates",
    "rerank_oov_unique",
    "score_candidates",
    "strict_fold",
    "use_oov_lemma_reranker",
]

FEATURE_NAMES: tuple[str, ...] = (
    "is_baseline_top1",
    "is_lookup_exact",
    "edit_logp",
    "edit_prob_sum",
    "edit_rank_inv",
    "in_strict_fold",
    "strict_unique",
    "strict_upos_match",
    "in_phonetic_fold",
    "phonetic_unique",
    "phonetic_upos_match",
    "in_preverb",
    "train_log_freq",
    "is_identity",
    "oov_x_strict_uniq",
    "oov_x_phon_uniq",
    "oov_x_preverb",
    "oov_x_edit_logp",
)

_PREVERBS: tuple[tuple[str, str], ...] = (
    ("κατα", "κατα"), ("κατ", "κατα"), ("καθ", "κατα"),
    ("μετα", "μετα"), ("μετ", "μετα"), ("μεθ", "μετα"),
    ("παρα", "παρα"), ("παρ", "παρα"),
    ("περι", "περι"),
    ("προσ", "προσ"), ("προ", "προ"),
    ("αντι", "αντι"), ("αντ", "αντι"), ("ανθ", "αντι"),
    ("αμφι", "αμφι"), ("αμφ", "αμφι"),
    ("υπερ", "υπερ"),
    ("υπο", "υπο"), ("υπ", "υπο"), ("υφ", "υπο"),
    ("απο", "απο"), ("απ", "απο"), ("αφ", "απο"),
    ("ανα", "ανα"), ("αν", "ανα"),
    ("δια", "δια"), ("δι", "δια"),
    ("επι", "επι"), ("επ", "επι"), ("εφ", "επι"),
    ("εισ", "εισ"), ("εσ", "εισ"),
    ("συν", "συν"), ("συγ", "συν"), ("συμ", "συν"), ("συλ", "συν"), ("συρ", "συν"), ("συ", "συν"),
    ("εν", "εν"), ("εμ", "εν"), ("εγ", "εν"), ("ελ", "εν"),
    ("εκ", "εκ"), ("εξ", "εκ"),
)
_DOC_SPAN_RE = re.compile(r"ου|ει|οι|υι|αι|[ηυω]")
_CONFIG_FORMAT = "pyaegean-oov-lemma-reranker/1"


def _nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def _canonical_sha256(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def strict_fold(form: str) -> str:
    """Accent-, breathing-, case-, and underdot-folded Greek key preserving adscript iota."""
    if not form:
        return ""
    cleaned = _strip_editorial_apparatus(form)
    if not cleaned:
        return ""
    decomposed = unicodedata.normalize("NFD", cleaned.replace("ϲ", "σ").replace("Ϲ", "Σ").lower())
    out: list[str] = []
    for ch in decomposed:
        if ch == "\u0345":  # combining Greek ypogegrammeni (iota subscript)
            out.append("ι")
            continue
        if unicodedata.combining(ch):
            continue
        out.append("σ" if ch == "ς" else ch)
    return "".join(out)


def documentary_phonetic_fold(form: str) -> str:
    """Koine/documentary phonetic fold: itacism, αι→ε, ω→ο, degemination, optional final -ν."""
    base = strict_fold(form)
    if not base:
        return ""

    def _repl(match: re.Match[str]) -> str:
        tok = match.group(0)
        if tok == "ου":
            return "ου"
        if tok in ("ει", "οι", "υι", "η", "υ"):
            return "ι"
        if tok == "αι":
            return "ε"
        if tok == "ω":
            return "ο"
        return tok

    folded = _DOC_SPAN_RE.sub(_repl, base)
    dedup: list[str] = []
    for ch in folded:
        if not dedup or dedup[-1] != ch:
            dedup.append(ch)
    out = "".join(dedup)
    if len(out) > 3 and out.endswith("ν"):
        out = out[:-1]
    return out


class TrainOnlyLemmaIndex:
    """Orthographic, phonetic, and preverb indices derived strictly from training lookups."""

    def __init__(
        self,
        *,
        strict: dict[str, Counter[str]],
        strict_upos: dict[tuple[str, str], Counter[str]],
        phon: dict[str, Counter[str]],
        phon_upos: dict[tuple[str, str], Counter[str]],
        lemma_freq: Counter[str],
        lemma_by_strict: dict[str, Counter[str]],
    ) -> None:
        self.strict = strict
        self.strict_upos = strict_upos
        self.phon = phon
        self.phon_upos = phon_upos
        self.lemma_freq = lemma_freq
        self.lemma_by_strict = lemma_by_strict

    @classmethod
    def from_lookup_tables(
        cls,
        lookup_form_upos: Mapping[str, str],
        lookup_form: Mapping[str, str] | None = None,
        lookup_lower: Mapping[str, str] | None = None,
    ) -> "TrainOnlyLemmaIndex":
        strict: dict[str, Counter[str]] = defaultdict(Counter)
        strict_upos: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
        phon: dict[str, Counter[str]] = defaultdict(Counter)
        phon_upos: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
        lemma_freq: Counter[str] = Counter()
        lemma_by_strict: dict[str, Counter[str]] = defaultdict(Counter)

        for key, raw_lemma in lookup_form_upos.items():
            if "\t" in key:
                form, upos = key.split("\t", 1)
            elif "|" in key:
                form, upos = key.rsplit("|", 1)
            else:
                form, upos = key, ""
            lem = _nfc(raw_lemma)
            if not lem:
                continue
            lemma_freq[lem] += 1
            lsf = strict_fold(lem)
            if lsf:
                lemma_by_strict[lsf][lem] += 1
            sf = strict_fold(form)
            if sf:
                strict[sf][lem] += 1
                if upos:
                    strict_upos[(sf, upos)][lem] += 1
            pf = documentary_phonetic_fold(form)
            if pf:
                phon[pf][lem] += 1
                if upos:
                    phon_upos[(pf, upos)][lem] += 1

        for table in (lookup_form or {}, lookup_lower or {}):
            for form, raw_lemma in table.items():
                lem = _nfc(raw_lemma)
                if not lem:
                    continue
                lemma_freq[lem] += 1
                lsf = strict_fold(lem)
                if lsf:
                    lemma_by_strict[lsf][lem] += 1
                sf = strict_fold(form)
                if sf:
                    strict[sf][lem] += 1
                pf = documentary_phonetic_fold(form)
                if pf:
                    phon[pf][lem] += 1

        return cls(
            strict=dict(strict),
            strict_upos=dict(strict_upos),
            phon=dict(phon),
            phon_upos=dict(phon_upos),
            lemma_freq=lemma_freq,
            lemma_by_strict=dict(lemma_by_strict),
        )

    @classmethod
    def from_model(cls, model: Any) -> "TrainOnlyLemmaIndex":
        return cls.from_lookup_tables(
            getattr(model, "lookup_form_upos", {}),
            getattr(model, "lookup_form", {}),
            getattr(model, "lookup_lower", {}),
        )


def preverb_candidates(form: str, upos: str, index: TrainOnlyLemmaIndex) -> list[str]:
    """Recover compound verb/deverbal lemmas by stripping a Greek preverb + optional augment."""
    sf = strict_fold(form)
    if len(sf) < 5:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for pref, canon_pref in _PREVERBS:
        if not sf.startswith(pref) or len(sf) - len(pref) < 3:
            continue
        rem = sf[len(pref) :]
        variants = [rem]
        if rem.startswith("ε") and len(rem) >= 4:
            variants.append(rem[1:])
        for stem_form in variants:
            simplex = index.strict_upos.get((stem_form, upos)) or index.strict.get(stem_form)
            if not simplex:
                continue
            for slem, _cnt in simplex.most_common(3):
                cand_strict = canon_pref + strict_fold(slem)
                for clem, _ in index.lemma_by_strict.get(cand_strict, Counter()).most_common(2):
                    if clem not in seen:
                        seen.add(clem)
                        out.append(clem)
    return out


@dataclass(frozen=True, slots=True)
class LemmaCandidate:
    """One deduplicated candidate lemma with marginalized neural mass and feature vector."""

    lemma: str
    routes: tuple[str, ...]
    edit_prob_sum: float
    best_edit_rank: int
    features: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class LemmaRerankerConfig:
    """Versioned, SHA-256-verified linear weight configuration for OOV lemma reranking."""

    weights: tuple[float, ...]
    feature_names: tuple[str, ...] = FEATURE_NAMES
    oov_only: bool = True
    sha256: str = ""

    def __post_init__(self) -> None:
        if len(self.weights) != len(self.feature_names):
            raise ValueError(
                f"weights length ({len(self.weights)}) != feature_names length "
                f"({len(self.feature_names)})"
            )
        if tuple(self.feature_names) != FEATURE_NAMES:
            raise ValueError("feature_names must match canonical FEATURE_NAMES order")
        for w in self.weights:
            if not math.isfinite(w):
                raise ValueError(f"non-finite reranker weight: {w!r}")
        canonical_weights = tuple(round(float(w), 12) for w in self.weights)
        object.__setattr__(self, "weights", canonical_weights)
        digest = _canonical_sha256(self._core_dict())
        if not self.sha256:
            object.__setattr__(self, "sha256", digest)
        elif self.sha256 != digest:
            raise ValueError(
                f"reranker config sha256 mismatch: expected {digest}, got {self.sha256}"
            )

    def _core_dict(self) -> dict[str, Any]:
        return {
            "format": _CONFIG_FORMAT,
            "feature_names": list(self.feature_names),
            "oov_only": bool(self.oov_only),
            "weights": list(self.weights),
        }

    def to_dict(self) -> dict[str, Any]:
        out = self._core_dict()
        out["sha256"] = self.sha256
        return out

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "LemmaRerankerConfig":
        if payload.get("format") != _CONFIG_FORMAT:
            raise ValueError(f"unsupported reranker config format: {payload.get('format')!r}")
        names = tuple(str(x) for x in payload.get("feature_names", ()))
        weights = tuple(float(x) for x in payload.get("weights", ()))
        oov_only = bool(payload.get("oov_only", True))
        sha = str(payload.get("sha256", ""))
        if not sha:
            raise ValueError("reranker config missing required sha256")
        return cls(weights=weights, feature_names=names, oov_only=oov_only, sha256=sha)

    @classmethod
    def bundled(cls) -> "LemmaRerankerConfig":
        """Load the bundled qualified weighted OOV reranker preset shipped in the wheel."""
        from ..data import load_bundled_json

        raw = load_bundled_json("greek", "oov_lemma_reranker_v1.json")
        return cls.from_dict(raw)


@dataclass(frozen=True, slots=True)
class RerankDecision:
    """Result of applying an OOV-gated reranker or deterministic fold rescue to one token."""

    lemma: str
    changed: bool
    route: str
    posterior: float | None
    candidates: tuple[LemmaCandidate, ...] = ()


def extract_oov_candidates(
    *,
    form: str,
    upos: str,
    baseline_lemma: str,
    baseline_source: str,
    index: TrainOnlyLemmaIndex,
    top_edit_predictions: Sequence[tuple[str, float]] = (),
    apply_normalizer: Callable[[str], str] | None = None,
) -> tuple[LemmaCandidate, ...]:
    """Build deduplicated candidate analyses for one token.

    ``top_edit_predictions`` is a ranked sequence of ``(predicted_lemma, probability)``
    pairs from the model's top-K edit scripts; equivalent predictions mapping to the
    same normalized lemma have their probability masses summed cleanly.
    """
    norm = apply_normalizer or _nfc
    base_lem = norm(baseline_lemma)
    is_oov = baseline_source != "neural_lookup"
    oov_flag = 1.0 if is_oov else 0.0

    cands: dict[str, dict[str, Any]] = {}

    def _ensure(lem: str) -> dict[str, Any]:
        if lem not in cands:
            cands[lem] = {
                "lemma": lem,
                "is_baseline_top1": 0.0,
                "is_lookup_exact": 0.0,
                "edit_prob_sum": 0.0,
                "best_edit_rank": 999,
                "in_strict_fold": 0.0,
                "strict_unique": 0.0,
                "strict_upos_match": 0.0,
                "in_phonetic_fold": 0.0,
                "phonetic_unique": 0.0,
                "phonetic_upos_match": 0.0,
                "in_preverb": 0.0,
                "is_identity": 0.0,
                "routes": set(),
            }
        return cands[lem]

    c_top = _ensure(base_lem)
    c_top["is_baseline_top1"] = 1.0
    if not is_oov:
        c_top["is_lookup_exact"] = 1.0
        c_top["routes"].add("exact_lookup")
    else:
        c_top["routes"].add(baseline_source)

    for rank, (raw_pred, prob) in enumerate(top_edit_predictions, start=1):
        if not raw_pred or raw_pred == "_":
            continue
        lem = norm(raw_pred)
        rec = _ensure(lem)
        rec["edit_prob_sum"] += max(0.0, float(prob))
        rec["best_edit_rank"] = min(rec["best_edit_rank"], rank)
        rec["routes"].add("neural_edit")

    probe = _strip_editorial_apparatus(_nfc(form))
    id_lem = norm(probe or form)
    rec_id = _ensure(id_lem)
    rec_id["is_identity"] = 1.0
    rec_id["routes"].add("identity")

    sf = strict_fold(form)
    s_hits = index.strict.get(sf, Counter()) if sf else Counter()
    su_hits = index.strict_upos.get((sf, upos), Counter()) if sf else Counter()
    s_top = [lem for lem, _ in s_hits.most_common(5)]
    strict_uniq = s_top[0] if len(s_hits) == 1 else None
    for lem in s_top:
        rec = _ensure(lem)
        rec["in_strict_fold"] = 1.0
        rec["routes"].add("strict_fold")
        if lem == strict_uniq:
            rec["strict_unique"] = 1.0
        if lem in su_hits:
            rec["strict_upos_match"] = 1.0

    pf = documentary_phonetic_fold(form)
    p_hits = index.phon.get(pf, Counter()) if pf else Counter()
    pu_hits = index.phon_upos.get((pf, upos), Counter()) if pf else Counter()
    p_top = [lem for lem, _ in p_hits.most_common(5)]
    phon_uniq = p_top[0] if len(p_hits) == 1 else None
    for lem in p_top:
        rec = _ensure(lem)
        rec["in_phonetic_fold"] = 1.0
        rec["routes"].add("phonetic_fold")
        if lem == phon_uniq:
            rec["phonetic_unique"] = 1.0
        if lem in pu_hits:
            rec["phonetic_upos_match"] = 1.0

    for lem in preverb_candidates(form, upos, index):
        rec = _ensure(lem)
        rec["in_preverb"] = 1.0
        rec["routes"].add("preverb")

    out: list[LemmaCandidate] = []
    for lem in sorted(cands):
        rec = cands[lem]
        p_sum = float(rec["edit_prob_sum"])
        edit_logp = math.log(max(p_sum, 1e-6))
        rank_inv = 1.0 / rec["best_edit_rank"] if rec["best_edit_rank"] < 999 else 0.0
        train_log_freq = math.log1p(index.lemma_freq.get(lem, 0))
        feats = (
            float(rec["is_baseline_top1"]),
            float(rec["is_lookup_exact"]),
            edit_logp,
            p_sum,
            rank_inv,
            float(rec["in_strict_fold"]),
            float(rec["strict_unique"]),
            float(rec["strict_upos_match"]),
            float(rec["in_phonetic_fold"]),
            float(rec["phonetic_unique"]),
            float(rec["phonetic_upos_match"]),
            float(rec["in_preverb"]),
            train_log_freq,
            float(rec["is_identity"]),
            oov_flag * float(rec["strict_unique"]),
            oov_flag * float(rec["phonetic_unique"]),
            oov_flag * float(rec["in_preverb"]),
            oov_flag * edit_logp,
        )
        out.append(
            LemmaCandidate(
                lemma=lem,
                routes=tuple(sorted(rec["routes"])),
                edit_prob_sum=p_sum,
                best_edit_rank=int(rec["best_edit_rank"]),
                features=feats,
            )
        )
    return tuple(out)


def rerank_oov_unique(
    *,
    form: str,
    upos: str,
    baseline_lemma: str,
    baseline_source: str,
    index: TrainOnlyLemmaIndex,
) -> RerankDecision:
    """Zero-parameter OOV-gated deterministic rescue (strict fold → phonetic fold → baseline).

    Never overrides exact ``neural_lookup`` resolutions.
    """
    base_lem = _nfc(baseline_lemma)
    if baseline_source == "neural_lookup":
        return RerankDecision(lemma=base_lem, changed=False, route="exact_lookup", posterior=None)

    sf = strict_fold(form)
    if sf:
        su = index.strict_upos.get((sf, upos))
        if su and len(su) == 1:
            pick = next(iter(su))
            return RerankDecision(
                lemma=pick, changed=(pick != base_lem), route="strict_fold_unique_upos", posterior=None
            )
        sh = index.strict.get(sf)
        if sh and len(sh) == 1:
            pick = next(iter(sh))
            return RerankDecision(
                lemma=pick, changed=(pick != base_lem), route="strict_fold_unique", posterior=None
            )

    pf = documentary_phonetic_fold(form)
    if pf:
        pu = index.phon_upos.get((pf, upos))
        if pu and len(pu) == 1:
            pick = next(iter(pu))
            return RerankDecision(
                lemma=pick, changed=(pick != base_lem), route="phonetic_fold_unique_upos", posterior=None
            )
        ph = index.phon.get(pf)
        if ph and len(ph) == 1:
            pick = next(iter(ph))
            return RerankDecision(
                lemma=pick, changed=(pick != base_lem), route="phonetic_fold_unique", posterior=None
            )

    return RerankDecision(lemma=base_lem, changed=False, route=baseline_source, posterior=None)


def score_candidates(
    candidates: Sequence[LemmaCandidate],
    config: LemmaRerankerConfig,
) -> list[tuple[LemmaCandidate, float]]:
    """Return candidates ranked by descending conditional softmax probability."""
    if not candidates:
        return []
    weights = config.weights
    logits = [
        sum(w * f for w, f in zip(weights, c.features, strict=True))
        for c in candidates
    ]
    max_logit = max(logits)
    exps = [math.exp(z - max_logit) for z in logits]
    total = sum(exps)
    scored = [(c, e / total) for c, e in zip(candidates, exps, strict=True)]
    scored.sort(key=lambda item: (-item[1], item[0].lemma))
    return scored


def rerank_candidates(
    *,
    candidates: Sequence[LemmaCandidate],
    baseline_lemma: str,
    baseline_source: str,
    config: LemmaRerankerConfig,
) -> RerankDecision:
    """Apply a verified ``LemmaRerankerConfig`` to candidate analyses (OOV-gated by default)."""
    base_lem = _nfc(baseline_lemma)
    if config.oov_only and baseline_source == "neural_lookup":
        return RerankDecision(
            lemma=base_lem,
            changed=False,
            route="exact_lookup",
            posterior=None,
            candidates=tuple(candidates),
        )
    ranked = score_candidates(candidates, config)
    if not ranked:
        return RerankDecision(
            lemma=base_lem,
            changed=False,
            route=baseline_source,
            posterior=None,
            candidates=(),
        )
    best, prob = ranked[0]
    route = "+".join(best.routes) if best.routes else baseline_source
    return RerankDecision(
        lemma=best.lemma,
        changed=(best.lemma != base_lem),
        route=route,
        posterior=prob,
        candidates=tuple(c for c, _ in ranked),
    )


def fit_oov_reranker(
    examples: Sequence[tuple[Sequence[LemmaCandidate], str]],
    *,
    l2: float = 1.0,
    max_iter: int = 150,
    oov_only: bool = True,
) -> LemmaRerankerConfig:
    """Fit an L2-regularized conditional log-linear reranker over ``(candidates, gold_lemma)``.

    Examples whose gold lemma is unreachable in the candidate set are automatically
    masked out of the NLL objective so unreachable tokens never distort weights.
    """
    import numpy as np

    usable: list[tuple[np.ndarray, int]] = []
    for cands, gold in examples:
        gold_norm = _nfc(gold)
        gold_idx = next((i for i, c in enumerate(cands) if c.lemma == gold_norm), None)
        if gold_idx is None or len(cands) < 2:
            continue
        usable.append((np.asarray([c.features for c in cands], dtype=np.float64), gold_idx))

    dim = len(FEATURE_NAMES)
    if not usable:
        return LemmaRerankerConfig(weights=(0.0,) * dim, oov_only=oov_only)

    n_ex = len(usable)
    c_max = max(mat.shape[0] for mat, _ in usable)
    x_pad = np.zeros((n_ex, c_max, dim), dtype=np.float64)
    mask = np.zeros((n_ex, c_max), dtype=np.bool_)
    gold_vec = np.zeros((n_ex, dim), dtype=np.float64)
    for i, (mat, g_idx) in enumerate(usable):
        m = mat.shape[0]
        x_pad[i, :m, :] = mat
        mask[i, :m] = True
        gold_vec[i] = mat[g_idx]

    w = np.zeros(dim, dtype=np.float64)

    def _loss_and_grad(vec: np.ndarray) -> tuple[float, np.ndarray]:
        logits = np.einsum("ncd,d->nc", x_pad, vec)
        logits = np.where(mask, logits, -1e30)
        row_max = np.max(logits, axis=1, keepdims=True)
        exps = np.where(mask, np.exp(logits - row_max), 0.0)
        denom = np.sum(exps, axis=1, keepdims=True)
        probs = exps / denom
        log_z = row_max.squeeze(1) + np.log(denom.squeeze(1))
        gold_logits = np.einsum("nd,d->n", gold_vec, vec)
        nll = float(np.sum(log_z - gold_logits)) + 0.5 * l2 * float(np.dot(vec, vec))
        exp_feats = np.einsum("nc,ncd->nd", probs, x_pad)
        grad = np.sum(exp_feats - gold_vec, axis=0) + l2 * vec
        return nll, grad

    lr = 0.05
    for _ in range(max_iter):
        loss0, grad = _loss_and_grad(w)
        grad_norm = float(np.linalg.norm(grad))
        if grad_norm < 1e-6:
            break
        step = lr
        accepted = False
        while step >= 1e-6:
            cand_w = w - step * grad
            loss1, _ = _loss_and_grad(cand_w)
            if loss1 <= loss0 - 1e-4 * step * (grad_norm**2):
                w = cand_w
                lr = min(0.5, step * 1.25)
                accepted = True
                break
            step *= 0.5
        if not accepted:
            break

    return LemmaRerankerConfig(weights=tuple(float(v) for v in w), oov_only=oov_only)


# ── SentenceAnalysis post-processing & opt-in neural pipeline toggle ───────────


_STATE_LOCK = RLock()
_ACTIVE_ENABLED: bool = False
_ACTIVE_CONFIG: LemmaRerankerConfig | None = None


def _reranker_receipt(
    receipt: Any,
    *,
    config: LemmaRerankerConfig | None,
    top_k_edits: int = 0,
) -> Any:
    """Attach an explicit PostprocessingStep for the active OOV reranker mode."""
    from .annotation_profiles import PostprocessingStep, canonical_analysis_profile

    params: list[tuple[str, str]] = [
        ("mode", "weighted_reranker" if config is not None else "unique_fold"),
        ("oov_only", "true" if (config is None or config.oov_only) else "false"),
    ]
    if config is not None and top_k_edits > 0:
        params.append(("top_k_edits", str(top_k_edits)))
    step_kwargs: dict[str, Any] = {
        "step_id": "pyaegean-oov-lemma-reranker-v1",
        "parameters": tuple(params),
    }
    if config is not None:
        step_kwargs["resource_id"] = "pyaegean-oov-lemma-reranker-config-v1"
        step_kwargs["resource_sha256"] = config.sha256
    step = PostprocessingStep(**step_kwargs)

    existing_profile = getattr(receipt, "analysis_profile", None)
    base = existing_profile if existing_profile is not None else canonical_analysis_profile()
    existing_steps = tuple(getattr(base, "postprocessing", ()))
    profile = replace(
        base,
        postprocessing=(*existing_steps, step),
    )
    return receipt.with_analysis_profile(profile)


def rerank_analysis(
    ana: "SentenceAnalysis",
    index: TrainOnlyLemmaIndex,
    *,
    config: LemmaRerankerConfig | None = None,
    top_edit_predictions: Sequence[Sequence[tuple[str, float]]] | None = None,
) -> "SentenceAnalysis":
    """Apply OOV-gated lemma reranking to a ``SentenceAnalysis`` (pure, reversible).

    When ``config`` is ``None``, applies zero-parameter deterministic strict→phonetic
    unique-fold rescue (``rerank_oov_unique``). When ``config`` is supplied, scores
    OOV candidate sets with ``rerank_candidates`` (optionally incorporating per-token
    ``top_edit_predictions`` from the neural edit-script head). Exact ``neural_lookup``
    tokens are preserved unchanged whenever ``config is None`` or ``config.oov_only``
    is True.
    """
    n = len(ana.tokens)
    if n == 0:
        return ana

    lemmas = list(ana.lemma)
    resolved = list(ana.lemma_resolved) if len(ana.lemma_resolved) == n else [True] * n
    sources = (
        list(ana.lemma_source)
        if len(ana.lemma_source) == n
        else [
            LemmaSource.NEURAL_LOOKUP if r else LemmaSource.IDENTITY
            for r in resolved
        ]
    )
    paths = (
        list(ana.lemma_source_path)
        if len(ana.lemma_source_path) == n
        else [s.value for s in sources]
    )
    verified = list(ana.lemma_verified) if len(ana.lemma_verified) == n else [False] * n
    changed_any = False
    use_top_edits = top_edit_predictions is not None and len(top_edit_predictions) == n

    for i in range(n):
        src_val = sources[i].value
        if config is None:
            decision = rerank_oov_unique(
                form=ana.tokens[i],
                upos=ana.upos[i],
                baseline_lemma=lemmas[i],
                baseline_source=src_val,
                index=index,
            )
        else:
            tok_edits = top_edit_predictions[i] if use_top_edits and top_edit_predictions is not None else ()
            cands = extract_oov_candidates(
                form=ana.tokens[i],
                upos=ana.upos[i],
                baseline_lemma=lemmas[i],
                baseline_source=src_val,
                index=index,
                top_edit_predictions=tok_edits,
            )
            decision = rerank_candidates(
                candidates=cands,
                baseline_lemma=lemmas[i],
                baseline_source=src_val,
                config=config,
            )
        if decision.changed:
            lemmas[i] = decision.lemma
            resolved[i] = True
            sources[i] = LemmaSource.NEURAL_LOOKUP
            paths[i] = f"oov_rerank:{decision.route}"
            verified[i] = False
            changed_any = True

    receipt = ana.receipt
    if receipt is not None:
        receipt = _reranker_receipt(
            receipt,
            config=config,
            top_k_edits=10 if (config is not None and use_top_edits) else 0,
        )

    if not changed_any and receipt is ana.receipt:
        return ana
    return replace(
        ana,
        lemma=tuple(lemmas),
        lemma_resolved=tuple(resolved),
        lemma_source=tuple(sources),
        lemma_source_path=tuple(paths),
        lemma_verified=tuple(verified),
        receipt=receipt,
    )


_DEFAULT_TOP_K_EDITS = 10


class _OovRerankModel:
    """Wraps an active joint model, applying opt-in OOV-gated lemma reranking."""

    def __init__(
        self,
        inner: Any,
        *,
        _frozen_state: tuple[bool, LemmaRerankerConfig | None] | None = None,
        _index: TrainOnlyLemmaIndex | None = None,
    ) -> None:
        self.inner = inner
        self._frozen_state = _frozen_state
        self._index = _index

    def _state(self) -> tuple[bool, LemmaRerankerConfig | None]:
        with _STATE_LOCK:
            if self._frozen_state is not None:
                return self._frozen_state
            return _ACTIVE_ENABLED, _ACTIVE_CONFIG

    def _get_index(self) -> TrainOnlyLemmaIndex:
        if self._index is None:
            self._index = TrainOnlyLemmaIndex.from_model(self.inner)
        return self._index

    def _snapshot_for_stream(self) -> "_OovRerankModel":
        inner_snap = (
            self.inner._snapshot_for_stream()
            if hasattr(self.inner, "_snapshot_for_stream")
            else self.inner
        )
        return _OovRerankModel(
            inner_snap,
            _frozen_state=self._state(),
            _index=self._get_index(),
        )

    def _apply(
        self,
        ana: "SentenceAnalysis",
        *,
        top_edit_predictions: Sequence[Sequence[tuple[str, float]]] | None = None,
    ) -> "SentenceAnalysis":
        enabled, cfg = self._state()
        if not enabled:
            return ana
        return rerank_analysis(
            ana,
            self._get_index(),
            config=cfg,
            top_edit_predictions=top_edit_predictions,
        )

    def analyze(
        self,
        words: list[str],
        *,
        with_probs: bool = False,
        long_input: str = "strict",
        domain: str | None = None,
        policy: Any = None,
    ) -> "SentenceAnalysis":
        enabled, cfg = self._state()
        kwargs: dict[str, Any] = {}
        if with_probs or long_input != "strict" or domain is not None or policy is not None:
            kwargs = {
                "with_probs": with_probs,
                "long_input": long_input,
            }
            if domain is not None:
                kwargs["domain"] = domain
            if policy is not None:
                kwargs["policy"] = policy
        if enabled and cfg is not None:
            from . import joint

            with joint._capture_top_lemma_edits(_DEFAULT_TOP_K_EDITS) as captured:
                ana = self.inner.analyze(words, **kwargs) if kwargs else self.inner.analyze(words)
            sent_edits = (
                captured[0]
                if len(captured) == 1 and len(captured[0]) == len(ana.tokens)
                else None
            )
            return self._apply(ana, top_edit_predictions=sent_edits)
        ana = self.inner.analyze(words, **kwargs) if kwargs else self.inner.analyze(words)
        return self._apply(ana)

    def analyze_batch(
        self,
        sentences: list[list[str]],
        *,
        with_probs: bool = False,
        long_input: str = "strict",
        domain: str | None = None,
        policy: Any = None,
    ) -> list["SentenceAnalysis"]:
        enabled, cfg = self._state()
        kwargs: dict[str, Any] = {}
        if with_probs or long_input != "strict" or domain is not None or policy is not None:
            kwargs = {
                "with_probs": with_probs,
                "long_input": long_input,
            }
            if domain is not None:
                kwargs["domain"] = domain
            if policy is not None:
                kwargs["policy"] = policy
        if enabled and cfg is not None:
            from . import joint

            with joint._capture_top_lemma_edits(_DEFAULT_TOP_K_EDITS) as captured:
                analyses = (
                    self.inner.analyze_batch(sentences, **kwargs)
                    if kwargs
                    else self.inner.analyze_batch(sentences)
                )
            if len(captured) == len(analyses):
                return [
                    self._apply(
                        a,
                        top_edit_predictions=(e if len(e) == len(a.tokens) else None),
                    )
                    for a, e in zip(analyses, captured)
                ]
            return [self._apply(a) for a in analyses]
        analyses = (
            self.inner.analyze_batch(sentences, **kwargs)
            if kwargs
            else self.inner.analyze_batch(sentences)
        )
        return [self._apply(a) for a in analyses]

    def __getattr__(self, name: str) -> Any:
        return getattr(self.inner, name)


def _has_rerank_wrapper(backend: Any) -> bool:
    cur = backend
    seen: set[int] = set()
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        if isinstance(cur, _OovRerankModel):
            return True
        cur = getattr(cur, "inner", None)
    return False


def _strip_rerank_wrapper(backend: Any) -> Any:
    """Remove any ``_OovRerankModel`` layer anywhere in a wrapper chain."""
    if isinstance(backend, _OovRerankModel):
        return _strip_rerank_wrapper(backend.inner)
    inner = getattr(backend, "inner", None)
    if inner is not None and _has_rerank_wrapper(inner):
        cleaned = _strip_rerank_wrapper(inner)
        backend.inner = cleaned
    return backend


def _sync() -> None:
    """Install or remove ``_OovRerankModel`` so ``joint.active()`` matches the toggle."""
    from . import joint

    with _STATE_LOCK:
        active: Any = joint.active()
        if active is None:
            return
        wrapped = _has_rerank_wrapper(active)
        if _ACTIVE_ENABLED and not wrapped:
            joint._replace_active_backend(_OovRerankModel(active))
        elif not _ACTIVE_ENABLED and wrapped:
            joint._replace_active_backend(_strip_rerank_wrapper(active))


def _resolve_reranker_config(
    config: LemmaRerankerConfig | str | None,
) -> LemmaRerankerConfig | None:
    """Resolve a reranker preset name or config object."""
    if config is None or config == "unique":
        return None
    if config == "weighted":
        return LemmaRerankerConfig.bundled()
    if isinstance(config, LemmaRerankerConfig):
        return config
    if isinstance(config, str):
        raise ValueError(
            f"unknown OOV lemma reranker preset {config!r}; expected 'unique', 'weighted', "
            "a LemmaRerankerConfig, or None"
        )
    raise TypeError(
        "config must be a LemmaRerankerConfig, preset name ('unique'|'weighted'), or None"
    )


def use_oov_lemma_reranker(
    *,
    config: LemmaRerankerConfig | str | None = None,
) -> None:
    """Activate opt-in OOV-gated lemma reranking on top of the active neural pipeline.

    Requires the neural pipeline to be active (raises ``NeuralPipelineNotLoadedError``
    otherwise).

    ``config`` accepts:

    - ``None`` or ``"unique"`` (default) — zero-parameter deterministic strict→phonetic
      unique-fold lookup derived strictly from the active model's own training tables.
    - ``"weighted"`` — the bundled, locked-test-qualified weighted OOV reranker
      (``LemmaRerankerConfig.bundled()``), automatically combining top-10 neural
      edit-script candidates with train-only orthographic, Koine phonetic, and preverb
      indices.
    - a SHA-256-verified ``LemmaRerankerConfig`` — custom weighted reranker config.

    Off by default and reversible via ``disable_oov_lemma_reranker()``.
    """
    global _ACTIVE_ENABLED, _ACTIVE_CONFIG
    from . import joint

    if joint.active() is None:
        raise joint.NeuralPipelineNotLoadedError(
            "the OOV lemma reranker post-processes the neural pipeline; activate it first "
            "with aegean.greek.use_neural_pipeline()."
        )
    resolved_config = _resolve_reranker_config(config)
    with _STATE_LOCK:
        _ACTIVE_ENABLED = True
        _ACTIVE_CONFIG = resolved_config
        _sync()


def disable_oov_lemma_reranker() -> None:
    """Deactivate opt-in OOV-gated lemma reranking and restore plain pipeline behavior."""
    global _ACTIVE_ENABLED, _ACTIVE_CONFIG
    with _STATE_LOCK:
        _ACTIVE_ENABLED = False
        _ACTIVE_CONFIG = None
        _sync()


def oov_lemma_reranker_active() -> bool:
    """Whether opt-in OOV-gated lemma reranking is currently active."""
    with _STATE_LOCK:
        return _ACTIVE_ENABLED
