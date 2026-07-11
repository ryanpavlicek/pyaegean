"""Temperature-scaled confidence for the joint neural pipeline — the ONLY calibrated
confidence surface, and the one place a probability may be attached to a prediction.

pyaegean deliberately refuses to expose a raw softmax number: an *un*calibrated
probability reads as a precise claim it has not earned, so it violates the
measured-claims-only rule. This module supplies the rule-compliant alternative —
**temperature scaling** (Guo et al., 2017) with a **measured** Expected Calibration
Error (ECE). A single scalar temperature ``T`` per model head rescales that head's
logits (``softmax(z / T)``); ``T`` is fitted on a held-out development fold and its
effect is reported as ECE-before/after, so the confidence surfaced downstream is an
honest estimate of the probability the prediction is correct — with a stated genre
caveat (it is fitted on literary prose).

What is calibrated, per head:

- **UPOS** — the top-1 (max) softmax probability of the predicted part-of-speech tag,
  against whether that tag matched gold.
- **lemma** — the top-1 softmax probability of the joint model's *lemma edit-script*
  head, against whether the **composed lemma** (script + train-only lookup, i.e. what
  the user actually sees) matched gold. The script-head confidence is a calibrated
  *proxy* for composed-lemma correctness; see ``training/calibrate_temperature.py`` for
  the precise target and its caveats.

Temperature only rescales confidence: because ``T > 0`` is a monotone transform of the
logits, it never changes which label is the argmax, so a loaded calibration cannot
alter a single prediction — only the number attached to it.

The math (``temperature_softmax`` / ``top1_confidence`` / ``ece`` / ``fit_temperature``)
is stdlib + numpy only (numpy imported lazily, so ``import aegean`` stays instant and
this module is free to import). The joint model consults ``active()`` when a caller asks
for probabilities; with no calibration loaded, that request **raises**
`UncalibratedConfidenceError` rather than returning a raw softmax.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # keep this module import-clean (numpy is imported lazily at call time)
    import numpy as _np_t

__all__ = [
    "HEADS",
    "Calibration",
    "UncalibratedConfidenceError",
    "active",
    "disable_calibration",
    "ece",
    "fit_temperature",
    "temperature_softmax",
    "top1_confidence",
    "use_calibration",
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
    number invites false confidence, which breaks the measured-claims-only rule. A
    temperature-scaled, ECE-measured calibration must be loaded (`use_calibration`) or
    fitted (`fit_temperature`) before any confidence is surfaced."""


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
        Path(path).write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=1), encoding="utf-8"
        )

    @classmethod
    def load(cls, path: str | Path) -> "Calibration":
        """Read a calibration written by `save` (or an equivalent JSON file)."""
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


_ACTIVE: Calibration | None = None


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


def use_calibration(source: "str | Path | Calibration | dict[str, Any] | None" = None) -> Calibration:
    """Load a calibration and make it the active one, so the joint model may surface
    calibrated confidence.

    ``source`` is a `Calibration`, a path to a JSON file (`save`'s format), a `to_dict`
    mapping, or ``None`` for the bundled default calibration (shipped in the wheel). The
    no-arg form raises `UncalibratedConfidenceError` only when that file cannot be loaded
    (a missing or corrupt install), never a raw softmax. Returns the loaded `Calibration`."""
    global _ACTIVE
    if source is None:
        cal = _load_bundled()
    elif isinstance(source, Calibration):
        cal = source
    elif isinstance(source, dict):
        cal = Calibration.from_dict(source)
    else:
        cal = Calibration.load(source)
    _ACTIVE = cal
    return cal


def disable_calibration() -> None:
    """Unload the active calibration; the joint model then refuses to surface confidence."""
    global _ACTIVE
    _ACTIVE = None


def active() -> Calibration | None:
    """The active `Calibration`, or ``None`` (the default — no confidence is exposed)."""
    return _ACTIVE
