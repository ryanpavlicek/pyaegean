"""One-line visualization helpers (the ``[viz]`` extra: matplotlib, imported lazily).

Convenience plots over the corpus model and the analysis layer — each function
draws one publication-ready-enough figure and returns the matplotlib ``Axes``
(pass ``ax=`` to compose subplots; call ``.figure.savefig(...)`` to write a
file). These are conveniences, not a plotting framework: for anything bespoke,
take the numbers from ``aegean.analysis`` and plot them yourself.

Most functions take ``backend="matplotlib"`` (the default) or
``backend="plotly"``. With ``"plotly"`` they return a Plotly ``Figure`` instead
of a matplotlib ``Axes`` (call ``.write_html(...)`` to save an interactive
page); Plotly is imported lazily and, if absent, raises a clear pointer to
``pip install 'pyaegean[viz-interactive]'``.

``import aegean`` stays dependency-free — matplotlib (and Plotly) are imported
only inside the plotting calls, and a missing matplotlib raises a clear pointer
to ``pip install 'pyaegean[viz]'``. From the shell: ``aegean plot …``.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from .analysis.multivariate import CAResult
from .analysis.stats import _documents, _items_of, dispersions, keyness

__all__ = [
    "plot_sign_frequencies",
    "plot_dispersion",
    "plot_keyness",
    "plot_collocation_network",
    "plot_scansion",
    "plot_balance",
    "correspondence_layout",
    "plot_correspondence_analysis",
    # find-site / timeline / co-occurrence-network plots (+ their data helpers)
    "plot_findspots",
    "plot_timeline",
    "plot_sign_network",
    "parse_period",
    "timeline_bins",
    "Timeline",
    "TimelineBin",
]


def _percentile_abs(values: Sequence[float], q: float) -> float:
    s = sorted(abs(v) for v in values)
    return s[min(len(s) - 1, int(len(s) * q))] if s else 0.0


def correspondence_layout(
    points: Sequence[tuple[float, float]],
    *,
    percentile: float = 0.9,
    pad_factor: float = 1.1,
    floor: float = 1e-9,
) -> list[tuple[float, float]]:
    """Scale CA coordinates into the box [-1, 1]² for legible plotting.

    A correspondence-analysis axis is usually dominated by one or two outlier
    points that, scaled by the global maximum, crush the rest of the cloud into a
    thin band. This scales **each axis independently** to its ``percentile``-th
    absolute coordinate (×``pad_factor``) and pins points beyond that at the box
    edge (±1). The picture then shows relative position along each axis, not
    literal CA distances — state that in any caption."""
    if not points:
        return []
    max_x = max(floor, _percentile_abs([x for x, _ in points], percentile) * pad_factor)
    max_y = max(floor, _percentile_abs([y for _, y in points], percentile) * pad_factor)

    def clamp(v: float) -> float:
        return -1.0 if v < -1.0 else 1.0 if v > 1.0 else v

    return [(clamp(x / max_x), clamp(y / max_y)) for x, y in points]


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


def _plotly_go() -> Any:
    try:
        import plotly.graph_objects as go
    except ImportError as e:  # pragma: no cover - exercised only without the extra
        raise ImportError(
            "plotly is required for backend='plotly' — install with: "
            "pip install 'pyaegean[viz-interactive]'"
        ) from e
    return go


def _check_backend(backend: str) -> None:
    if backend not in ("matplotlib", "plotly"):
        raise ValueError(f"backend must be 'matplotlib' or 'plotly', got {backend!r}")


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


def plot_correspondence_analysis(
    ca: CAResult, *, label_top: int = 12, ax: Any = None
) -> Any:
    """Correspondence-analysis biplot: rows (blue) and columns (amber) in one
    plane, with per-axis percentile scaling so a single outlier can't flatten the
    cloud (see :func:`correspondence_layout`). The heaviest ``label_top`` columns
    and all rows are labelled. Shows relative position along each axis, not
    literal CA distances."""
    n_rows = len(ca.rows)
    coords = correspondence_layout([(p.x, p.y) for p in ca.rows + ca.cols])
    row_xy = coords[:n_rows]
    col_xy = coords[n_rows:]
    ax = _axes(ax, figsize=(7, 6))
    ax.axhline(0, color="#ccc", linewidth=0.6, zorder=1)
    ax.axvline(0, color="#ccc", linewidth=0.6, zorder=1)
    ax.scatter(
        [x for x, _ in col_xy], [y for _, y in col_xy],
        s=20, color="#e7a33e", alpha=0.8, label="columns", zorder=2,
    )
    ax.scatter(
        [x for x, _ in row_xy], [y for _, y in row_xy],
        s=[8 + 120 * math.sqrt(p.mass) for p in ca.rows],
        color="#4a6fa5", alpha=0.4, label="rows", zorder=3,
    )
    for (x, y), p in zip(row_xy, ca.rows, strict=True):
        ax.annotate(p.label, (x, y), fontsize=8, fontweight="bold", zorder=4)
    heaviest = sorted(range(len(ca.cols)), key=lambda j: -ca.cols[j].mass)[:label_top]
    for j in heaviest:
        ax.annotate(ca.cols[j].label, col_xy[j], fontsize=7, color="#9c6a1e", zorder=4)
    pct = (ca.inertia[0] + ca.inertia[1]) * 100
    ax.set_title(f"correspondence analysis ({pct:.0f}% of inertia on axes 1–2)")
    ax.set_xlabel("axis 1")
    ax.set_ylabel("axis 2")
    ax.legend(loc="best", fontsize=8)
    ax.figure.tight_layout()
    return ax


# ── find-sites map ────────────────────────────────────────────────────────────


def plot_findspots(corpus: Any, *, backend: str = "matplotlib", ax: Any = None) -> Any:
    """A scatter of the corpus's find-sites: longitude (x) against latitude (y),
    marker size scaled by the number of inscriptions from each site, each point
    labelled with its site name and count.

    Coordinates come from the bundled site gazetteer (:func:`aegean.geo.site_coordinates`,
    stdlib — no ``[geo]`` extra needed to plot). Sites absent from the gazetteer are
    dropped; if *no* site maps, the corpus has nothing to place and a clear
    ``ValueError`` is raised (the CLI turns it into a one-line message)."""
    _check_backend(backend)
    from .geo import site_coordinates

    coords = site_coordinates()
    counts = Counter(d.meta.site for d in _documents(corpus) if d.meta.site in coords)
    if not counts:
        raise ValueError("no find-sites in this corpus map to the bundled gazetteer")
    rows = [(coords[s].name, coords[s].lon, coords[s].lat, n) for s, n in counts.most_common()]
    n_max = max(r[3] for r in rows)
    total = sum(r[3] for r in rows)
    title = f"find-sites ({len(rows)} sites, {total} inscriptions)"
    if backend == "plotly":
        return _findspots_plotly(rows, n_max, title)
    ax = _axes(ax, figsize=(8, 7))
    ax.scatter(
        [r[1] for r in rows], [r[2] for r in rows],
        s=[30 + 170 * (r[3] / n_max) for r in rows],
        color="#4a6fa5", alpha=0.7, edgecolors="#22344f", zorder=2,
    )
    for name, lon, lat, n in rows:
        ax.annotate(f"{name} ({n})", (lon, lat), fontsize=7, alpha=0.9,
                    xytext=(4, 4), textcoords="offset points", zorder=3)
    ax.set_xlabel("longitude")
    ax.set_ylabel("latitude")
    ax.set_title(title)
    ax.figure.tight_layout()
    return ax


def _findspots_plotly(rows: list[tuple[str, float, float, int]], n_max: int, title: str) -> Any:
    go = _plotly_go()
    fig = go.Figure(
        go.Scatter(
            x=[r[1] for r in rows], y=[r[2] for r in rows],
            mode="markers+text",
            text=[f"{r[0]} ({r[3]})" for r in rows],
            textposition="top center",
            marker={"size": [10 + 34 * (r[3] / n_max) for r in rows], "color": "#4a6fa5"},
        )
    )
    fig.update_layout(title=title, xaxis_title="longitude", yaxis_title="latitude")
    return fig


# ── timeline over parsed dates ────────────────────────────────────────────────
#
# origDate-style metadata (``meta.period``) is free text — "Third century BC", "480—450
# BCE", "II century C.E", "201 AD – 300 AD", "Hellenistic". parse_period() is a best-effort
# reader: explicit year ranges and centuries (English words, digit ordinals, Roman numerals,
# the isicily "C3" abbreviation), with BC/BCE/до-н.э → negative years and AD/CE → positive.
# What it can't read is never silently dropped — it is counted and surfaced as the unparsed
# fraction on the plot and in the returned Timeline.

_WORD_ORDINALS = {
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7,
    "eighth": 8, "ninth": 9, "tenth": 10, "eleventh": 11, "twelfth": 12, "thirteenth": 13,
    "fourteenth": 14, "fifteenth": 15, "sixteenth": 16, "seventeenth": 17, "eighteenth": 18,
    "nineteenth": 19, "twentieth": 20,
}
_ROMAN = {"i": 1, "v": 5, "x": 10, "l": 50, "c": 100, "d": 500, "m": 1000}


def _roman_to_int(s: str) -> int | None:
    s = s.lower()
    if not s or any(ch not in _ROMAN for ch in s):
        return None
    total = 0
    prev = 0
    for ch in reversed(s):
        v = _ROMAN[ch]
        total += -v if v < prev else v
        prev = max(prev, v)
    return total or None


def _era(t: str) -> int | None:
    """+1 = CE/AD, -1 = BCE/BC, None = no era marker (t is lowercased)."""
    if re.search(r"(?<![a-z])b\.?\s*c\.?", t) or "до н" in t:
        return -1
    if (
        re.search(r"(?<![a-z])a\.?\s*d(?![a-z])", t)
        or re.search(r"(?<![a-z])c\.?\s*e(?![a-z])", t)
        or "н.э" in t
    ):
        return 1
    return None


_FRACTION_RE = re.compile(
    r"\b(?:first|second|third|fourth|fifth|last|\d+(?:st|nd|rd|th))\s+(?:half|quarter|third)\b"
)


def _centuries(t: str) -> set[int]:
    # Drop "<ordinal> half/quarter/third" phrases so "second half of fourth century" reads as
    # the 4th century, not the 2nd–4th. The century is kept whole (best-effort binning).
    t = _FRACTION_RE.sub(" ", t)
    nums: set[int] = set()
    for word, n in _WORD_ORDINALS.items():
        if re.search(rf"\b{word}\b", t):
            nums.add(n)
    for m in re.finditer(r"\b(\d+)(?:st|nd|rd|th)\b", t):
        nums.add(int(m.group(1)))
    for m in re.finditer(r"\bc(\d+)\b", t):  # isicily "C3 AD" century abbreviation
        nums.add(int(m.group(1)))
    # Roman numeral immediately before "century" ("III century", "IVth century"). Capped to a
    # plausible century so an all-Roman-letter English word ("mid", "c" from a following "C.E")
    # can't inject a spurious value; era markers follow the century word, never precede it.
    for m in re.finditer(r"\b([ivxlcdm]+)(?:th)?\s+centur", t):
        r = _roman_to_int(m.group(1))
        if r is not None and 1 <= r <= 21:
            nums.add(r)
    return nums


def parse_period(text: str) -> tuple[int, int] | None:
    """Best-effort parse of an origDate-style date string to a ``(start, end)`` year range,
    BCE years negative and CE positive (e.g. ``"480—450 BCE"`` → ``(-480, -450)``,
    ``"Third century BC"`` → ``(-300, -201)``, ``"II century C.E"`` → ``(101, 200)``).

    Returns ``None`` when the string carries no readable century or era-qualified year
    (a bare "Hellenistic" or "" is honestly unparseable, not guessed). Half/quarter and
    hedge qualifiers ("Second half of", "Perhaps", "Ca.") are ignored — the whole century
    is returned. This is a heuristic for aggregate binning, not a dating authority."""
    if not text:
        return None
    t = text.lower()
    era = _era(t)
    is_century = ("centur" in t) or bool(re.search(r"\bc\d", t))
    if is_century:
        cents = _centuries(t)
        if not cents or era is None:
            return None
        n_lo, n_hi = min(cents), max(cents)
        if era < 0:  # BCE: the higher century number is the earlier (more negative) year
            return (-(n_hi * 100), -(n_lo * 100 - 99))
        return ((n_lo - 1) * 100 + 1, n_hi * 100)
    if era is None:
        return None
    years = [int(m) for m in re.findall(r"\d+", t)]
    if not years:
        return None
    lo_y, hi_y = min(years), max(years)
    if era < 0:
        return (-hi_y, -lo_y)
    return (lo_y, hi_y)


@dataclass(frozen=True)
class TimelineBin:
    """One time bucket: ``start`` is the bin's first year (negative = BCE); ``count`` is the
    number of documents whose parsed date midpoint falls in ``[start, start + bin_width)``."""

    start: int
    count: int


@dataclass(frozen=True)
class Timeline:
    """The result of bucketing a corpus's documents over parsed dates.

    ``bins`` are the non-empty buckets in chronological order; ``unparsed`` counts the
    documents whose ``meta.period`` :func:`parse_period` could not read (never dropped —
    always reported). ``unparsed_fraction`` is that count over ``total``."""

    bins: tuple[TimelineBin, ...]
    parsed: int
    unparsed: int
    total: int
    bin_width: int

    @property
    def unparsed_fraction(self) -> float:
        return self.unparsed / self.total if self.total else 0.0


def timeline_bins(corpus: Any, *, bin_width: int = 100) -> Timeline:
    """Bucket a corpus's documents into ``bin_width``-year bins by their parsed date.

    Each document is placed by the midpoint of its :func:`parse_period` range; documents
    with no readable date are counted in ``unparsed`` (never silently dropped). Default
    ``bin_width=100`` gives one bar per century."""
    if bin_width <= 0:
        raise ValueError(f"bin_width must be positive, got {bin_width}")
    docs = _documents(corpus)
    counts: Counter[int] = Counter()
    unparsed = 0
    for d in docs:
        parsed = parse_period(d.meta.period)
        if parsed is None:
            unparsed += 1
            continue
        lo, hi = parsed
        mid = (lo + hi) / 2
        counts[math.floor(mid / bin_width) * bin_width] += 1
    total = len(docs)
    bins = tuple(TimelineBin(start, counts[start]) for start in sorted(counts))
    return Timeline(bins, total - unparsed, unparsed, total, bin_width)


def plot_timeline(corpus: Any, *, bin_width: int = 100, backend: str = "matplotlib",
                  ax: Any = None) -> Any:
    """Document counts over ``bin_width``-year bins (default one bar per century), from the
    best-effort dates in ``meta.period`` (see :func:`parse_period`).

    The fraction of documents whose date could not be read is stated on the figure and
    available on :func:`timeline_bins` — dates are never silently dropped. Raises
    ``ValueError`` only for a corpus with no documents at all."""
    _check_backend(backend)
    tl = timeline_bins(corpus, bin_width=bin_width)
    if tl.total == 0:
        raise ValueError("no documents to place on a timeline")
    note = f"unparsed dates: {tl.unparsed} of {tl.total} ({tl.unparsed_fraction * 100:.0f}%)"
    title = f"documents over time (bin {bin_width} yr)"
    if backend == "plotly":
        return _timeline_plotly(tl, title, note)
    ax = _axes(ax, figsize=(8, 5))
    ax.bar(
        [b.start + bin_width / 2 for b in tl.bins], [b.count for b in tl.bins],
        width=bin_width * 0.9, color="#4a6fa5", align="center",
    )
    ax.set_xlabel("year (negative = BCE)")
    ax.set_ylabel("documents")
    ax.set_title(title)
    ax.annotate(note, xy=(0.99, 0.97), xycoords="axes fraction", ha="right", va="top",
                fontsize=8, color="#a54a4a")
    ax.figure.tight_layout()
    return ax


def _timeline_plotly(tl: Timeline, title: str, note: str) -> Any:
    go = _plotly_go()
    fig = go.Figure(
        go.Bar(
            x=[b.start + tl.bin_width / 2 for b in tl.bins],
            y=[b.count for b in tl.bins],
            marker_color="#4a6fa5",
        )
    )
    fig.update_layout(title=f"{title} — {note}", xaxis_title="year (negative = BCE)",
                      yaxis_title="documents")
    return fig


# ── sign / word co-occurrence network ─────────────────────────────────────────


def plot_sign_network(
    corpus: Any,
    *,
    level: str = "sign",
    scope: str = "document",
    min_count: int = 1,
    max_nodes: int = 30,
    backend: str = "matplotlib",
    ax: Any = None,
) -> Any:
    """Render the corpus's co-occurrence graph (:func:`aegean.analysis.graph.cooccurrence_graph`)
    with a deterministic, seedless frequency-ranked circular layout.

    ``level`` (``"sign"``/``"word"``), ``scope`` (``"document"``/``"line"``) and ``min_count``
    are passed straight to the graph builder; the ``max_nodes`` most frequent nodes are drawn.
    Node size scales with corpus frequency, edge width with the shared-unit weight. Raises
    ``ValueError`` when nothing co-occurs at the threshold. **Exploratory**: an edge is shared
    context on undeciphered material, never an asserted phrase or meaning."""
    _check_backend(backend)
    from .analysis.graph import cooccurrence_graph

    graph = cooccurrence_graph(corpus, level=level, scope=scope, min_count=min_count)
    if not graph.nodes:
        raise ValueError(f"no co-occurring {level}s at this threshold")
    nodes = graph.nodes[:max_nodes]
    keep = {n.id for n in nodes}
    edges = [e for e in graph.edges if e.source in keep and e.target in keep]
    n = len(nodes)
    pos = {
        nd.id: (math.cos(2 * math.pi * i / n), math.sin(2 * math.pi * i / n))
        for i, nd in enumerate(nodes)
    }
    title = f"{level} co-occurrence network (shared {scope}, ≥{min_count}; exploratory)"
    if backend == "plotly":
        return _sign_network_plotly(nodes, edges, pos, title)
    ax = _axes(ax, figsize=(7.5, 7.5))
    w_max = max((e.weight for e in edges), default=1)
    for e in sorted(edges, key=lambda e: e.weight):
        (x1, y1), (x2, y2) = pos[e.source], pos[e.target]
        ax.plot([x1, x2], [y1, y2], color="#4a6fa5",
                linewidth=0.6 + 2.4 * e.weight / w_max,
                alpha=0.25 + 0.6 * e.weight / w_max, zorder=1)
    f_max = max(nd.frequency for nd in nodes)
    for nd in nodes:
        x, y = pos[nd.id]
        ax.scatter([x], [y], s=40 + 160 * nd.frequency / f_max, color="#2d4a73", zorder=2)
        ax.annotate(nd.id, (x * 1.08, y * 1.08), fontsize=8, ha="center", va="center", zorder=3)
    ax.set_xlim(-1.3, 1.3)
    ax.set_ylim(-1.3, 1.3)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(title)
    ax.figure.tight_layout()
    return ax


def _sign_network_plotly(nodes: Any, edges: Any, pos: dict[str, tuple[float, float]],
                         title: str) -> Any:
    go = _plotly_go()
    edge_x: list[float | None] = []
    edge_y: list[float | None] = []
    for e in edges:
        (x1, y1), (x2, y2) = pos[e.source], pos[e.target]
        edge_x += [x1, x2, None]
        edge_y += [y1, y2, None]
    edge_trace = go.Scatter(x=edge_x, y=edge_y, mode="lines",
                            line={"color": "#9db5d4"}, hoverinfo="none")
    f_max = max(nd.frequency for nd in nodes)
    node_trace = go.Scatter(
        x=[pos[nd.id][0] for nd in nodes], y=[pos[nd.id][1] for nd in nodes],
        mode="markers+text", text=[nd.id for nd in nodes], textposition="top center",
        marker={"size": [12 + 28 * nd.frequency / f_max for nd in nodes], "color": "#2d4a73"},
    )
    fig = go.Figure([edge_trace, node_trace])
    fig.update_layout(title=title, showlegend=False)
    return fig
