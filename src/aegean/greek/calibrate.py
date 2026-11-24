"""Calibrated confidence for the joint neural pipeline — the ONLY calibrated
confidence surface, and the one place a probability may be attached to a prediction.

pyaegean deliberately refuses to expose a raw softmax number: an *un*calibrated
probability reads as a precise claim it has not earned, so it violates the
measured-claims-only rule. This module supplies two rule-compliant, ECE-measured
calibration layers:

- **Schema-2 `CalibrationRegistry` (recommended, `use_calibration_registry()`)** —
  a bundled per-task, per-source, per-domain logit-affine calibrator
  (``calibration_registry_v2.json``) covering all six neural tasks (**UPOS**, **XPOS**,
  **FEATS**, **lemma** by decision route, **head**, and **relation**) across both
  ``literary`` and ``documentary_native`` domains. Each resolved `ConfidenceResult`
  carries its scope, calibration hash, sample count, and measured ECE / Brier score,
  or an explicit unavailable reason when a domain/task is uncalibrated. Pairs with
  caller-owned `AbstentionPolicy` thresholds and calibrated-risk review queues.
- **Legacy Schema-1 scalar temperature scaling (`use_calibration()`)** —
  single-temperature rescaling (Guo et al., 2017; ``softmax(z / T)``) for the **UPOS**
  and **lemma** (composed-lemma proxy) heads fitted on literary prose, retained for
  compatibility with published Schema-1 receipts and flat confidence fields.

Calibration only rescales confidence: monotone logit transforms never change which
label is the argmax, so a loaded calibration cannot alter a single prediction — only
the probability attached to it.

The math (``temperature_softmax`` / ``top1_confidence`` / ``ece`` / ``brier_score`` /
``fit_temperature`` / ``fit_logit_affine``) is stdlib + numpy only (numpy imported
lazily, so ``import aegean`` stays instant and this module is free to import). When a
caller requests probabilities with no calibration loaded, the joint model **raises**
`UncalibratedConfidenceError` rather than returning a raw softmax.
"""

from __future__ import annotations

import json
import math
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path
from threading import RLock
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # keep this module import-clean (numpy is imported lazily at call time)
    import numpy as _np_t

__all__ = [
    "HEADS",
    "Calibration",
    "UncalibratedConfidenceError",
    "AbstentionPolicy",
    "CalibrationEntry",
    "CalibrationRegistry",
    "CalibrationResolution",
    "ConfidenceResult",
    "TokenConfidence",
    "SentenceConfidence",
    "CoverageRiskPoint",
    "PolicyDecision",
    "brier_score",
    "active",
    "canonical_json",
    "canonical_sha256",
    "coverage_risk_curve",
    "disable_calibration",
    "ece",
    "fit_logit_affine",
    "fit_temperature",
    "temperature_softmax",
    "top1_confidence",
    "use_calibration",
    "use_calibration_registry",
    "active_registry",
]

# The two model heads pyaegean calibrates and surfaces a confidence for.
HEADS = ("upos", "lemma")

# The bundled default calibration, shipped in the wheel alongside the other small JSON
# data (code + JSON wheel rule): src/aegean/data/bundled/greek/calibration.json.
# `use_calibration()` with no argument loads it; `UncalibratedConfidenceError` fires only
# when confidence is requested and this file cannot be loaded (a missing/corrupt install).
_BUNDLED_PARTS = ("greek", "calibration.json")


class UncalibratedConfidenceError(RuntimeError):
    """Raised when calibrated confidence is requested but none is loaded.

    pyaegean never exposes a raw (uncalibrated) softmax probability: an uncalibrated
    number invites false confidence, which breaks the measured-claims-only rule. Load a
    measured calibration registry (`use_calibration_registry`), load a legacy scalar
    calibration (`use_calibration`), or fit one (`fit_logit_affine` / `fit_temperature`)
    before surfacing any confidence."""


def _numpy() -> Any:
    try:
        import numpy as np
    except ModuleNotFoundError as e:  # pragma: no cover - import guard
        raise RuntimeError(
            "temperature calibration needs numpy (the [neural] extra): "
            "pip install 'pyaegean[neural]'"
        ) from e
    return np


# --- the temperature-scaled softmax and its top-1 confidence -----------------------


def temperature_softmax(
    logits: Any, temperature: float, *, np: "_np_t | None" = None
) -> Any:
    """Numerically-stable softmax over the last axis after dividing by ``temperature``.

    ``temperature`` must be strictly positive; it only rescales the distribution's
    sharpness and never moves the argmax. ``logits`` may be 1-D (a single row) or 2-D
    ``[n_items, n_classes]``; the returned probabilities have the same shape and sum to
    1 along the last axis. Pass ``np`` to reuse an already-imported numpy module (the
    joint model does this in its decode loop)."""
    if not (isinstance(temperature, (int, float)) and math.isfinite(temperature)):
        raise ValueError(f"temperature must be a finite number, got {temperature!r}")
    if temperature <= 0:
        raise ValueError(f"temperature must be > 0, got {temperature!r}")
    if np is None:
        np = _numpy()
    z = np.asarray(logits, dtype=np.float64) / float(temperature)
    if z.ndim == 0:
        raise ValueError("logits must have at least one dimension")
    if not np.isfinite(z).all():
        raise ValueError("logits contain non-finite values (NaN/inf)")
    z = z - z.max(axis=-1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=-1, keepdims=True)


def top1_confidence(
    logits: Any, temperature: float, *, np: "_np_t | None" = None
) -> Any:
    """The top-1 (max) softmax probability per row, temperature-scaled.

    This is the single number pyaegean surfaces as a prediction's confidence: once the
    temperature is calibrated, it estimates the probability the argmax prediction is
    correct. 1-D ``logits`` return a scalar; 2-D ``[n_items, n_classes]`` return a length-
    ``n_items`` array. The argmax is unchanged by ``temperature`` (see
    `temperature_softmax`), so this only rescales the *confidence*, never the label."""
    if np is None:
        np = _numpy()
    p = temperature_softmax(logits, temperature, np=np)
    return p.max(axis=-1)


# --- Expected Calibration Error ----------------------------------------------------


def ece(
    probs: Any, correct: Any, *, n_bins: int = 15, np: "_np_t | None" = None
) -> float:
    """Expected Calibration Error via equal-width binning (Guo et al., 2017).

    ``probs`` are per-item top-1 confidences in ``[0, 1]``; ``correct`` are the matching
    0/1 outcomes (whether the surfaced prediction was right). Each item is placed in one
    of ``n_bins`` equal-width bins over ``[0, 1]`` (a confidence of exactly 1.0 falls in
    the last bin); the ECE is the sample-weighted mean absolute gap between each bin's
    mean confidence and its empirical accuracy. 0 means perfectly calibrated. An empty
    input is defined as 0.0."""
    if n_bins < 1:
        raise ValueError(f"n_bins must be >= 1, got {n_bins!r}")
    if np is None:
        np = _numpy()
    p = np.asarray(probs, dtype=np.float64).ravel()
    y = np.asarray(correct, dtype=np.float64).ravel()
    if p.shape != y.shape:
        raise ValueError(
            f"probs and correct must have the same length: {p.shape} vs {y.shape}"
        )
    if p.size == 0:
        return 0.0
    if not np.isfinite(p).all():
        raise ValueError("probs contain non-finite values (NaN/inf)")
    if (p < 0).any() or (p > 1).any():
        raise ValueError("probs must be in [0, 1]")
    if not np.isfinite(y).all() or ((y != 0) & (y != 1)).any():
        raise ValueError("correct must contain only 0/1 values")
    n = int(p.size)
    bins = np.clip((p * n_bins).astype(int), 0, n_bins - 1)
    total = 0.0
    for b in range(n_bins):
        m = bins == b
        cnt = int(m.sum())
        if cnt:
            conf = float(p[m].mean())
            acc = float(y[m].mean())
            total += (cnt / n) * abs(acc - conf)
    return total


# --- fitting the scalar temperature ------------------------------------------------


def _binary_nll(conf: Any, correct: Any, np: Any) -> float:
    """Mean binary negative log-likelihood of the top-1 confidence against correctness."""
    eps = 1e-12
    c = np.clip(conf, eps, 1.0 - eps)
    y = correct
    return float(-(y * np.log(c) + (1.0 - y) * np.log(1.0 - c)).mean())


_INV_PHI = (5.0**0.5 - 1.0) / 2.0  # 1/φ ≈ 0.618


def _golden_section(f: Any, a: float, b: float, *, tol: float = 1e-4, max_iter: int = 200) -> float:
    """Minimize a smooth 1-D ``f`` on ``[a, b]`` by golden-section search."""
    c = b - _INV_PHI * (b - a)
    d = a + _INV_PHI * (b - a)
    fc, fd = f(c), f(d)
    for _ in range(max_iter):
        if b - a < tol:
            break
        if fc < fd:
            b, d, fd = d, c, fc
            c = b - _INV_PHI * (b - a)
            fc = f(c)
        else:
            a, c, fc = c, d, fd
            d = a + _INV_PHI * (b - a)
            fd = f(d)
    return (a + b) / 2.0


def fit_temperature(
    logits: Any,
    correct: Any,
    *,
    bracket: tuple[float, float] = (0.05, 20.0),
    np: "_np_t | None" = None,
) -> float:
    """Fit the scalar temperature ``T`` that best calibrates a head's top-1 confidence.

    ``logits`` is a 2-D ``[n_items, n_classes]`` array of a head's raw logits; ``correct``
    is a length-``n_items`` 0/1 array of whether the surfaced (argmax) prediction was
    right. ``T`` is chosen to minimize the **binary negative log-likelihood** of the
    top-1 confidence ``softmax(z / T).max()`` against ``correct`` — i.e. it directly
    calibrates the one number pyaegean surfaces. Overconfident heads (the usual case) fit
    ``T > 1`` (flattening the distribution lowers confidence toward the observed
    accuracy); a well-calibrated head fits ``T ≈ 1``.

    The optimization is a coarse geometric grid over ``bracket`` (robust to a
    non-unimodal objective) followed by a golden-section refine around the grid minimum —
    no scipy. Returns a strictly-positive float.

    Raises ``ValueError`` on an empty fold, a shape mismatch, non-finite logits, or an
    invalid ``bracket``."""
    if np is None:
        np = _numpy()
    z = np.asarray(logits, dtype=np.float64)
    if z.ndim != 2:
        raise ValueError(f"logits must be a 2-D [n_items, n_classes] array, got ndim={z.ndim}")
    y = np.asarray(correct, dtype=np.float64).ravel()
    if y.shape[0] != z.shape[0]:
        raise ValueError(
            f"logits and correct must have the same number of items: {z.shape[0]} vs {y.shape[0]}"
        )
    if not np.isfinite(y).all() or ((y != 0) & (y != 1)).any():
        raise ValueError("correct must contain only 0/1 values")
    if z.shape[0] == 0:
        raise ValueError("cannot fit a temperature on an empty fold")
    if not np.isfinite(z).all():
        raise ValueError("logits contain non-finite values (NaN/inf)")
    lo, hi = bracket
    if not (0 < lo < hi):
        raise ValueError(f"bracket must satisfy 0 < lo < hi, got {bracket!r}")

    # Subtract the per-row max once (numerical stability) so the objective only exps a
    # shifted, non-positive array at each candidate temperature.
    zc = z - z.max(axis=-1, keepdims=True)

    def nll(t: float) -> float:
        e = np.exp(zc / t)
        conf = e.max(axis=-1) / e.sum(axis=-1)
        return _binary_nll(conf, y, np)

    grid = np.geomspace(lo, hi, 40)
    vals = [nll(float(t)) for t in grid]
    k = int(np.argmin(vals))
    a = float(grid[max(k - 1, 0)])
    b = float(grid[min(k + 1, len(grid) - 1)])
    if a == b:  # grid minimum at an endpoint
        return a
    return _golden_section(nll, a, b)


def fit_logit_affine(
    probs: Any,
    correct: Any,
    *,
    slope_bracket: tuple[float, float] = (1e-3, 1e3),
    intercept_bracket: tuple[float, float] = (-30.0, 30.0),
    np: "_np_t | None" = None,
) -> tuple[float, float]:
    """Fit a monotone logit-affine calibrator to raw confidence/correctness pairs.

    The returned ``(slope, intercept)`` parameters define
    ``sigmoid(slope * logit(p) + intercept)``.  A strictly positive slope preserves
    confidence ordering, so calibration cannot make a less-confident prediction rank
    above a more-confident one.  The fit minimizes binary negative log-likelihood by a
    deterministic nested grid/golden-section search and needs only NumPy.

    ``probs`` must be a non-constant one-dimensional sequence in ``[0, 1]`` and
    ``correct`` must contain both binary outcomes.  Exact endpoint probabilities are
    clipped only while fitting so their logits remain finite; applying the fitted
    :class:`CalibrationEntry` still maps exact 0 and 1 to themselves.
    """
    if np is None:
        np = _numpy()
    p = np.asarray(probs, dtype=np.float64).ravel()
    y = np.asarray(correct, dtype=np.float64).ravel()
    if p.shape != y.shape:
        raise ValueError(
            f"probs and correct must have the same length: {p.shape} vs {y.shape}"
        )
    if p.size == 0:
        raise ValueError("cannot fit a logit-affine calibrator on an empty fold")
    if not np.isfinite(p).all() or (p < 0).any() or (p > 1).any():
        raise ValueError("probs must contain only finite values in [0, 1]")
    if not np.isfinite(y).all() or ((y != 0) & (y != 1)).any():
        raise ValueError("correct must contain only 0/1 values")
    if not bool((y == 0).any()) or not bool((y == 1).any()):
        raise ValueError("correct must contain both 0 and 1 to fit an affine calibrator")
    slope_lo, slope_hi = slope_bracket
    intercept_lo, intercept_hi = intercept_bracket
    if not (0 < slope_lo < slope_hi):
        raise ValueError(
            "slope_bracket must satisfy 0 < lo < hi, "
            f"got {slope_bracket!r}"
        )
    if not (intercept_lo < intercept_hi):
        raise ValueError(
            "intercept_bracket must satisfy lo < hi, "
            f"got {intercept_bracket!r}"
        )

    clipped = np.clip(p, 1e-12, 1.0 - 1e-12)
    logits = np.log(clipped / (1.0 - clipped))
    if float(logits.max() - logits.min()) == 0.0:
        raise ValueError("probs must not be constant")

    def sigmoid(values: Any) -> Any:
        out = np.empty_like(values)
        nonnegative = values >= 0
        out[nonnegative] = 1.0 / (1.0 + np.exp(-values[nonnegative]))
        exp_values = np.exp(values[~nonnegative])
        out[~nonnegative] = exp_values / (1.0 + exp_values)
        return out

    def best_intercept(slope: float) -> tuple[float, float]:
        def objective(intercept: float) -> float:
            return _binary_nll(sigmoid(slope * logits + intercept), y, np)

        grid = np.linspace(intercept_lo, intercept_hi, 61)
        values = [objective(float(value)) for value in grid]
        index = int(np.argmin(values))
        left = float(grid[max(index - 1, 0)])
        right = float(grid[min(index + 1, len(grid) - 1)])
        intercept = (
            left
            if left == right
            else _golden_section(objective, left, right, tol=1e-6)
        )
        return intercept, objective(intercept)

    slope_grid = np.geomspace(slope_lo, slope_hi, 50)
    profile = [best_intercept(float(slope))[1] for slope in slope_grid]
    index = int(np.argmin(profile))
    left = float(slope_grid[max(index - 1, 0)])
    right = float(slope_grid[min(index + 1, len(slope_grid) - 1)])

    def profiled_objective(slope: float) -> float:
        return best_intercept(slope)[1]

    slope = (
        left
        if left == right
        else _golden_section(profiled_objective, left, right, tol=1e-6)
    )
    intercept, _ = best_intercept(slope)
    return float(slope), float(intercept)


# --- the Calibration record + module state -----------------------------------------


@dataclass(frozen=True, slots=True)
class Calibration:
    """A fitted temperature calibration for the joint model's heads.

    ``temperature`` maps each head name (``"upos"``, ``"lemma"``) to its fitted scalar
    ``T`` (strictly positive). ``fitted_on`` describes the fold and model it was measured
    on, ``date`` when, and ``ece_before`` / ``ece_after`` / ``n`` record the measured
    Expected Calibration Error (before and after scaling) and the token count per head —
    the honesty evidence that travels with the number. Round-trips to JSON via
    `to_dict` / `from_dict` (and `save` / `load`)."""

    temperature: dict[str, float]
    fitted_on: str = ""
    date: str = ""
    ece_before: dict[str, float] = field(default_factory=dict)
    ece_after: dict[str, float] = field(default_factory=dict)
    n: dict[str, int] = field(default_factory=dict)
    notes: str = ""

    def __post_init__(self) -> None:
        missing = [h for h in HEADS if h not in self.temperature]
        if missing:
            raise ValueError(f"calibration is missing a temperature for head(s): {missing}")
        for head, t in self.temperature.items():
            if not (isinstance(t, (int, float)) and math.isfinite(t) and t > 0):
                raise ValueError(
                    f"calibration temperature for {head!r} must be a finite positive number, got {t!r}"
                )

    def to_dict(self) -> dict[str, Any]:
        """A JSON-ready dict of this calibration (the shape `from_dict` reads)."""
        return {
            "temperature": {k: float(v) for k, v in self.temperature.items()},
            "fitted_on": self.fitted_on,
            "date": self.date,
            "ece_before": {k: float(v) for k, v in self.ece_before.items()},
            "ece_after": {k: float(v) for k, v in self.ece_after.items()},
            "n": {k: int(v) for k, v in self.n.items()},
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Calibration":
        """Rebuild a `Calibration` from a `to_dict` mapping (validated on construction)."""
        return cls(
            temperature={k: float(v) for k, v in d["temperature"].items()},
            fitted_on=str(d.get("fitted_on", "")),
            date=str(d.get("date", "")),
            ece_before={k: float(v) for k, v in d.get("ece_before", {}).items()},
            ece_after={k: float(v) for k, v in d.get("ece_after", {}).items()},
            n={k: int(v) for k, v in d.get("n", {}).items()},
            notes=str(d.get("notes", "")),
        )

    def save(self, path: str | Path) -> None:
        """Write this calibration to ``path`` as JSON."""
        from .._atomic import atomic_path

        with atomic_path(path) as tmp:
            tmp.write_text(
                json.dumps(self.to_dict(), ensure_ascii=False, indent=1), encoding="utf-8"
            )

    @classmethod
    def load(cls, path: str | Path) -> "Calibration":
        """Read a calibration written by `save` (or an equivalent JSON file)."""
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


_ACTIVE: Calibration | None = None
_ACTIVE_REGISTRY: "CalibrationRegistry | None" = None
_STATE_LOCK = RLock()
_CALIBRATION_OVERRIDE: ContextVar[
    tuple[Calibration | None, "CalibrationRegistry | None"] | None
] = ContextVar("pyaegean_calibration_override", default=None)


@contextmanager
def _bind_calibration(
    legacy: Calibration | None,
    registry: "CalibrationRegistry | None",
) -> Iterator[None]:
    """Temporarily bind instance-scoped calibration state for one pipeline call."""
    token = _CALIBRATION_OVERRIDE.set((legacy, registry))
    try:
        yield
    finally:
        _CALIBRATION_OVERRIDE.reset(token)


def _active_state() -> tuple[Calibration | None, "CalibrationRegistry | None"]:
    """Return one coherent legacy/registry calibration snapshot."""
    override = _CALIBRATION_OVERRIDE.get()
    if override is not None:
        return override
    with _STATE_LOCK:
        return _ACTIVE, _ACTIVE_REGISTRY


def _load_bundled() -> Calibration:
    from ..data import load_bundled_json

    # The bundled calibration ships (see _BUNDLED_PARTS). A missing file (a broken
    # install) OR a present-but-corrupt/partial one (truncated JSON, a temperature head
    # dropped) must fail loudly with actionable guidance, never leak a raw
    # JSONDecodeError/ValueError, and never fall back to an uncalibrated softmax.
    try:
        d = load_bundled_json(*_BUNDLED_PARTS)
        return Calibration.from_dict(d)
    except (FileNotFoundError, json.JSONDecodeError, ValueError, KeyError) as e:
        raise UncalibratedConfidenceError(
            "the bundled calibration could not be loaded "
            f"({type(e).__name__}: {e}); reinstall pyaegean, or fit one with "
            "training/calibrate_temperature.py and pass its JSON to "
            "use_calibration(path) (or pass a Calibration object). The project will not "
            "surface an uncalibrated softmax."
        ) from e


def _resolve_calibration_source(
    source: "str | Path | Calibration | dict[str, Any] | None",
) -> tuple[Calibration, "CalibrationRegistry"]:
    """Load a Schema-1 Calibration and its v2 registry adapter without mutating globals."""
    if source is None:
        cal = _load_bundled()
    elif isinstance(source, Calibration):
        cal = source
    elif isinstance(source, dict):
        cal = Calibration.from_dict(source)
    else:
        cal = Calibration.load(source)
    from .confidence import CalibrationRegistry

    registry = CalibrationRegistry.from_legacy(cal.to_dict())
    return cal, registry


def use_calibration(source: "str | Path | Calibration | dict[str, Any] | None" = None) -> Calibration:
    """Load a calibration and make it the active one, so the joint model may surface
    calibrated confidence.

    ``source`` is a `Calibration`, a path to a JSON file (`save`'s format), a `to_dict`
    mapping, or ``None`` for the bundled default calibration (shipped in the wheel). The
    no-arg form raises `UncalibratedConfidenceError` only when that file cannot be loaded
    (a missing or corrupt install), never a raw softmax. Returns the loaded `Calibration`."""
    global _ACTIVE, _ACTIVE_REGISTRY
    # Keep a separate v2 scope registry for callers that request typed confidence.
    # Legacy construction/JSON/active() remain unchanged; schema-1 aggregate entries
    # are explicitly marked as unscoped fallbacks by the registry adapter.
    cal, registry = _resolve_calibration_source(source)
    with _STATE_LOCK:
        _ACTIVE = cal
        _ACTIVE_REGISTRY = registry
    return cal


def _load_bundled_registry() -> "CalibrationRegistry":
    from .confidence import CalibrationRegistry

    try:
        return CalibrationRegistry.bundled()
    except (FileNotFoundError, json.JSONDecodeError, ValueError, KeyError, TypeError) as e:
        raise UncalibratedConfidenceError(
            "the bundled Schema-2 calibration registry could not be loaded "
            f"({type(e).__name__}: {e}); reinstall pyaegean or pass a CalibrationRegistry "
            "JSON path to use_calibration_registry(path). The project will not surface "
            "an uncalibrated softmax."
        ) from e


def _resolve_registry_source(
    source: "str | Path | CalibrationRegistry | dict[str, Any] | None",
) -> "CalibrationRegistry":
    """Load a Schema-2 CalibrationRegistry without mutating globals."""
    from .confidence import CalibrationRegistry

    if source is None:
        return _load_bundled_registry()
    if isinstance(source, CalibrationRegistry):
        return source
    if isinstance(source, dict):
        return CalibrationRegistry.from_dict(source)
    return CalibrationRegistry.load(source)


def use_calibration_registry(
    source: "str | Path | CalibrationRegistry | dict[str, Any] | None" = None,
) -> "CalibrationRegistry":
    """Load and activate a version-2 task/source/domain calibration registry.

    With ``source=None`` (the default), loads the bundled qualified Schema-2 registry
    shipped in the wheel (``calibration_registry_v2.json``), covering ``literary`` and
    ``documentary_native`` domains across UPOS, XPOS, FEATS, lemma routes, head, and
    non-root dependency relations.
    """
    registry = _resolve_registry_source(source)
    global _ACTIVE, _ACTIVE_REGISTRY
    with _STATE_LOCK:
        _ACTIVE = None
        _ACTIVE_REGISTRY = registry
    return registry


def active_registry() -> "CalibrationRegistry | None":
    """Return the active v2 registry, or ``None`` when no calibration is active."""
    override = _CALIBRATION_OVERRIDE.get()
    if override is not None:
        return override[1]
    with _STATE_LOCK:
        return _ACTIVE_REGISTRY


def disable_calibration() -> None:
    """Unload the active calibration; the joint model then refuses to surface confidence."""
    global _ACTIVE, _ACTIVE_REGISTRY
    with _STATE_LOCK:
        _ACTIVE = None
        _ACTIVE_REGISTRY = None


def active() -> Calibration | None:
    """The active `Calibration`, or ``None`` (the default — no confidence is exposed)."""
    override = _CALIBRATION_OVERRIDE.get()
    if override is not None:
        return override[0]
    with _STATE_LOCK:
        return _ACTIVE


# Additive confidence-policy and evidence helpers.  This import is stdlib-only and
# intentionally does not pull NumPy into the import path; the legacy record above
# remains unchanged.  Re-exporting here keeps ``aegean.greek.calibrate`` a convenient
# compatibility surface while the implementation lives in its own module.
from .confidence import (  # noqa: E402  (placed after Calibration to keep legacy state first)
    AbstentionPolicy,
    CalibrationEntry,
    CalibrationRegistry,
    CalibrationResolution,
    ConfidenceResult,
    TokenConfidence,
    SentenceConfidence,
    CoverageRiskPoint,
    PolicyDecision,
    brier_score,
    canonical_json,
    canonical_sha256,
    coverage_risk_curve,
)
