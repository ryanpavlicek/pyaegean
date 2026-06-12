"""One-line visualization helpers (the ``[viz]`` extra: matplotlib, imported lazily).

Convenience plots over the corpus model and the analysis layer — each function
draws one publication-ready-enough figure and returns the matplotlib ``Axes``
(pass ``ax=`` to compose subplots; call ``.figure.savefig(...)`` to write a
file). These are conveniences, not a plotting framework: for anything bespoke,
take the numbers from ``aegean.analysis`` and plot them yourself.

``import aegean`` stays dependency-free — matplotlib is imported only inside
the plotting calls and a missing install raises a clear pointer to
``pip install 'pyaegean[viz]'``. From the shell: ``aegean plot …``.
"""

from __future__ import annotations

import math
from collections import Counter
from typing import Any

from .analysis.stats import _documents, _items_of, dispersions, keyness

__all__ = [
    "plot_sign_frequencies",
    "plot_dispersion",
    "plot_keyness",
    "plot_collocation_network",
    "plot_scansion",
    "plot_balance",
]


def _plt() -> Any:
    try:
        import matplotlib.pyplot as plt
    except ImportError as e:  # pragma: no cover - exercised only without the extra
        raise ImportError(
            "matplotlib is required for aegean.viz — install with: pip install 'pyaegean[viz]'"
        ) from e
    return plt


def _axes(ax: Any, *, figsize: tuple[float, float]) -> Any:
    if ax is not None:
        return ax
    _, new_ax = _plt().subplots(figsize=figsize)
    return new_ax


def plot_sign_frequencies(
    corpus: Any, *, top: int = 20, kind: str = "signs", ax: Any = None
) -> Any:
    """Horizontal frequency bars — the ``aegean stats`` table as a figure.

    ``kind="signs"`` (default) counts individual signs; ``kind="words"`` whole
    words. Most frequent at the top."""
    counts: Counter[str] = Counter()
    for d in _documents(corpus):
        counts.update(_items_of(d, kind))
    pairs = counts.most_common(top)
    ax = _axes(ax, figsize=(7, max(2.5, 0.32 * len(pairs))))
    labels = [p[0] for p in pairs][::-1]
    values = [p[1] for p in pairs][::-1]
    ax.barh(labels, values, color="#4a6fa5")
    ax.set_xlabel("occurrences")
    ax.set_title(f"top {len(pairs)} {kind}")
    ax.figure.tight_layout()
    return ax


def plot_dispersion(
    corpus: Any,
    *,
    kind: str = "words",
    min_frequency: int = 2,
    annotate: int = 10,
    ax: Any = None,
) -> Any:
    """Frequency (log x) against Gries' normalized DP (y).

    The diagnostic read: bottom-right = frequent corpus-wide vocabulary;
    top-right = frequent but *concentrated* items (formulaic or site/genre-bound
    — on Aegean material usually the interesting quadrant). The ``annotate``
    most frequent items are labeled."""
    rows = dispersions(corpus, kind=kind, min_frequency=min_frequency)
    ax = _axes(ax, figsize=(7, 5))
    ax.scatter(
        [r.frequency for r in rows],
        [r.dp_norm for r in rows],
        s=18,
        alpha=0.55,
        color="#4a6fa5",
        edgecolors="none",
    )
    ax.set_xscale("log")
    ax.set_xlabel("frequency (log)")
    ax.set_ylabel("DP (normalized)")
    ax.set_ylim(-0.02, 1.02)
    ax.set_title(f"dispersion of {kind} (Gries' DP)")
    for r in sorted(rows, key=lambda r: -r.frequency)[:annotate]:
        ax.annotate(r.item, (r.frequency, r.dp_norm), fontsize=8, alpha=0.9,
                    xytext=(3, 3), textcoords="offset points")
    ax.figure.tight_layout()
    return ax


def plot_keyness(
    target: Any,
    reference: Any,
    *,
    kind: str = "words",
    top: int = 15,
    min_target: int = 2,
    ax: Any = None,
) -> Any:
    """Diverging bars of the ``top``-G² key items: log-ratio effect size,
    right = overused in the target, left = underused. Bar labels carry G²."""
    rows = keyness(target, reference, kind=kind, min_target=min_target)[:top]
    rows = sorted(rows, key=lambda r: r.log_ratio)
    ax = _axes(ax, figsize=(7, max(2.5, 0.34 * len(rows))))
    colors = ["#4a6fa5" if r.log_ratio >= 0 else "#a54a4a" for r in rows]
    ax.barh([r.item for r in rows], [r.log_ratio for r in rows], color=colors)
    ax.axvline(0, color="#444", linewidth=0.8)
    ax.set_xlabel("log₂ ratio (each point ≈ one doubling)")
    ax.set_title(f"keyness ({kind}): top {len(rows)} by G²")
    for i, r in enumerate(rows):
        ax.annotate(f"G²={r.log_likelihood:.0f}", (r.log_ratio, i), fontsize=7,
                    va="center", xytext=(4 if r.log_ratio >= 0 else -4, 0),
                    textcoords="offset points",
                    ha="left" if r.log_ratio >= 0 else "right", alpha=0.8)
    ax.figure.tight_layout()
    return ax


def plot_collocation_network(
    corpus: Any,
    word: str | None = None,
    *,
    max_nodes: int = 24,
    min_count: int = 2,
    ax: Any = None,
) -> Any:
    """A document-co-occurrence network of multi-sign words (circular layout).

    Edges join words attested together in ``min_count``+ documents; width and
    opacity scale with the count. ``word`` restricts to that word's ego
    network. **Exploratory** on undeciphered material: an edge is shared
    *context*, not an asserted phrase or meaning."""
    pair_counts: Counter[tuple[str, str]] = Counter()
    for d in _documents(corpus):
        words = sorted({t.text for t in d.tokens if "-" in t.text})
        for i, a in enumerate(words):
            for b in words[i + 1 :]:
                pair_counts[(a, b)] += 1
    edges = {p: n for p, n in pair_counts.items() if n >= min_count}
    if word is not None:
        edges = {p: n for p, n in edges.items() if word in p}
    if not edges:
        raise ValueError("no co-occurring word pairs at this threshold")
    weight: Counter[str] = Counter()
    for (a, b), n in edges.items():
        weight[a] += n
        weight[b] += n
    nodes = [w for w, _ in weight.most_common(max_nodes)]
    if word is not None and word not in nodes:
        nodes = [word, *nodes][:max_nodes]
    keep = set(nodes)
    edges = {p: n for p, n in edges.items() if p[0] in keep and p[1] in keep}

    pos = {
        w: (math.cos(2 * math.pi * i / len(nodes)), math.sin(2 * math.pi * i / len(nodes)))
        for i, w in enumerate(nodes)
    }
    ax = _axes(ax, figsize=(7.5, 7.5))
    n_max = max(edges.values())
    for (a, b), n in sorted(edges.items(), key=lambda kv: kv[1]):
        (x1, y1), (x2, y2) = pos[a], pos[b]
        ax.plot([x1, x2], [y1, y2], color="#4a6fa5",
                linewidth=0.6 + 2.4 * n / n_max, alpha=0.25 + 0.6 * n / n_max, zorder=1)
    for w, (x, y) in pos.items():
        ax.scatter([x], [y], s=120 if w == word else 60,
                   color="#a54a4a" if w == word else "#2d4a73", zorder=2)
        ax.annotate(w, (x * 1.08, y * 1.08), fontsize=8,
                    ha="center", va="center", zorder=3)
    ax.set_xlim(-1.3, 1.3)
    ax.set_ylim(-1.3, 1.3)
    ax.set_aspect("equal")
    ax.axis("off")
    title = f"co-occurrence network of {word}" if word else "co-occurrence network"
    ax.set_title(f"{title} (≥{min_count} shared documents; exploratory)")
    ax.figure.tight_layout()
    return ax


def plot_scansion(line: Any, *, meter: str = "hexameter", ax: Any = None) -> Any:
    """A scansion grid for one verse line: syllables in metrical position,
    long (—) and short (⏑) marks, foot boundaries, and the caesura (‖).

    ``line`` is Greek text (scanned via ``greek.scan_line``) or an existing
    ``LineScansion``. Raises ``ScansionError`` if the text does not fit the
    meter (synizesis is declined, never inferred)."""
    from .greek.meter import HEAVY, LIGHT, scan_line

    scansion = scan_line(line, meter) if isinstance(line, str) else line
    # "˘" (U+02D8) rather than the metrical "⏑" (U+23D1): the classical glyph is
    # missing from matplotlib's default fonts and renders as tofu.
    marks = {HEAVY: ("—", 0.55, "#4a6fa5"), LIGHT: ("˘", 0.28, "#9db5d4")}
    anceps = ("×", 0.42, "#7a93b8")
    ax = _axes(ax, figsize=(max(6.0, 0.62 * len(scansion.syllables)), 2.6))
    x = 0.0
    boundaries: list[float] = []
    syll_index = 0
    for foot in scansion.feet:
        for syll, quant in zip(foot.syllables, foot.quantities, strict=True):
            glyph, height, color = marks.get(quant, anceps)
            ax.add_patch(_plt().Rectangle((x, 1.0), 0.9, height, color=color))
            ax.annotate(glyph, (x + 0.45, 1.78), ha="center", fontsize=11)
            ax.annotate(syll, (x + 0.45, 0.55), ha="center", fontsize=9)
            if scansion.caesura_index is not None and syll_index == scansion.caesura_index:
                ax.annotate("‖", (x - 0.08, 1.25), ha="center",
                            fontsize=14, color="#a54a4a")
            syll_index += 1
            x += 1.0
        boundaries.append(x - 0.05)
    for b in boundaries[:-1]:
        ax.axvline(b, color="#999", linewidth=0.7, linestyle=":")
    ax.set_xlim(-0.3, x + 0.2)
    ax.set_ylim(0.2, 2.2)
    ax.axis("off")
    sub = f" · {scansion.caesura} caesura" if scansion.caesura else ""
    pattern = scansion.pattern.replace("⏑", "˘")  # same font caveat as the marks
    ax.set_title(f"{scansion.meter}: {pattern}{sub}", fontsize=10)
    ax.figure.tight_layout()
    return ax


def plot_balance(corpus: Any, *, ax: Any = None) -> Any:
    """Accounting reconciliation at a glance: each checked total (KU-RO /
    TO-SO) as computed sum (x) vs stated total (y). Points on the diagonal
    balance; red points do not — the discrepancies worth a closer look. The
    reconciliation inherits the heuristics of ``balance_check`` (section
    boundaries are inferred), so treat outliers as leads, not verdicts."""
    from .analysis import balance_check

    xs: list[float] = []
    ys: list[float] = []
    bad_xs: list[float] = []
    bad_ys: list[float] = []
    labels: list[tuple[float, float, str]] = []
    for d in _documents(corpus):
        for chk in balance_check(d):
            if chk.stated_total is None or chk.computed_sum is None:
                continue
            if chk.balances:
                xs.append(chk.computed_sum)
                ys.append(chk.stated_total)
            else:
                bad_xs.append(chk.computed_sum)
                bad_ys.append(chk.stated_total)
                labels.append((chk.computed_sum, chk.stated_total, d.id))
    if not xs and not bad_xs:
        raise ValueError("no checkable stated totals in this corpus")
    ax = _axes(ax, figsize=(6.5, 6.5))
    lim = max(xs + bad_xs + ys + bad_ys) * 1.08
    ax.plot([0, lim], [0, lim], color="#999", linewidth=0.8, zorder=1)
    if xs:
        ax.scatter(xs, ys, s=26, color="#4a6fa5", alpha=0.65,
                   label=f"balances ({len(xs)})", zorder=2)
    if bad_xs:
        ax.scatter(bad_xs, bad_ys, s=34, color="#a54a4a",
                   label=f"discrepant ({len(bad_xs)})", zorder=3)
        for bx, by, doc_id in labels:
            ax.annotate(doc_id, (bx, by), fontsize=7, alpha=0.9,
                        xytext=(4, 4), textcoords="offset points")
    ax.set_xlabel("computed sum of items")
    ax.set_ylabel("stated total")
    ax.set_title("accounting reconciliation (heuristic sections)")
    ax.legend(loc="lower right", fontsize=8)
    ax.figure.tight_layout()
    return ax
