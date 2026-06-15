"""Positional / edge keyness and morphological productivity.

Statistics over a corpus's multi-sign word vocabulary that flag candidate
affixes and positional regularities — ported from the Linear A Research
Workbench's Morphology and Positional-Grammar modules:

- **edge-bias G²** — is a fixed-length affix over-represented in the word *edge*
  slot (final for suffixes, initial for prefixes) versus interior windows?
- **positional-bias G²** — is a word over-represented in its dominant slot
  (initial / medial / final) versus the corpus-wide slot baseline?
- **Baayen's productivity P** — hapax types bearing an affix / its token total.
- **Harris successor variety** — how many distinct signs follow a prefix,
  scored against the mean branching factor at that sign-depth.

All are exploratory on a small, undeciphered corpus: a high score flags a
candidate worth inspecting, not a confirmed morpheme. The two G² statistics are
signed Dunning log-likelihood values (nats); the sign marks the direction of the
effect, the magnitude its strength on a χ²₁ scale.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from .collocation import log_likelihood_ratio_2x2

__all__ = [
    "edge_bias_g2",
    "EdgeBiasRow",
    "affix_edge_bias",
    "positional_bias_g2",
    "PositionalRow",
    "positional_bias",
    "Productivity",
    "baayen_productivity",
    "SuccessorRow",
    "SuccessorVariety",
    "successor_variety",
]


# ── edge-bias G² ─────────────────────────────────────────────────────────────


def edge_bias_g2(
    edge_count: int, edge_total: int, interior_count: int, interior_total: int
) -> float:
    """Signed Dunning G² of an affix's edge-slot rate vs its interior-window rate.

    ``edge_count`` of ``edge_total`` edge slots hold the affix; ``interior_count``
    of ``interior_total`` interior windows do. Positive = over-represented at the
    word edge (affix-like); negative = interior-leaning; an exact rate tie is
    positive. Returns 0 for an empty edge or interior population."""
    if edge_total <= 0 or interior_total <= 0:
        return 0.0
    g2 = log_likelihood_ratio_2x2(
        edge_count, edge_total, edge_count + interior_count, edge_total + interior_total
    )
    edge_rate = edge_count / edge_total
    interior_rate = interior_count / interior_total
    return g2 if edge_rate >= interior_rate else -g2


@dataclass(frozen=True)
class EdgeBiasRow:
    """One affix's edge-bias result: its edge-slot count, its interior-window
    count, and the signed G²."""

    affix: str
    edge_count: int
    interior: int
    g2: float


def affix_edge_bias(
    words: Iterable[tuple[str, int]],
    *,
    affix_len: int = 1,
    mode: str = "suffix",
) -> list[EdgeBiasRow]:
    """Edge-bias G² for every length-``affix_len`` affix over a multi-sign word
    vocabulary, strongest (most edge-biased) first.

    ``words`` is an iterable of ``(word, count)`` pairs — hyphen-joined signs and
    a token frequency; everything is token-weighted. ``mode`` is ``"suffix"``
    (final slot) or ``"prefix"`` (initial slot). Words with no remaining stem
    (``parts <= affix_len`` signs) are skipped. Interior occurrences are window
    matches of the affix that don't fall in the edge slot."""
    if mode not in ("suffix", "prefix"):
        raise ValueError(f"mode must be 'suffix' or 'prefix', got {mode!r}")
    edge_map: dict[str, int] = defaultdict(int)
    windows: dict[str, int] = defaultdict(int)
    edge_total = 0
    window_total = 0
    for word, count in words:
        parts = word.split("-")
        if len(parts) <= affix_len:
            continue
        if mode == "suffix":
            key = "-".join(parts[len(parts) - affix_len :])
        else:
            key = "-".join(parts[:affix_len])
        edge_map[key] += count
        edge_total += count
        for i in range(len(parts) - affix_len + 1):
            windows["-".join(parts[i : i + affix_len])] += count
            window_total += count
    interior_total = window_total - edge_total
    rows = [
        EdgeBiasRow(
            affix=affix,
            edge_count=edge_count,
            interior=max(0, windows.get(affix, 0) - edge_count),
            g2=edge_bias_g2(
                edge_count, edge_total, max(0, windows.get(affix, 0) - edge_count), interior_total
            ),
        )
        for affix, edge_count in edge_map.items()
    ]
    rows.sort(key=lambda r: (-r.g2, r.affix))
    return rows


# ── positional-bias G² ───────────────────────────────────────────────────────


def positional_bias_g2(in_pos: int, slots: int, slot_total: int, grand_total: int) -> float:
    """Signed Dunning G² of a word's share in its dominant slot vs the rest of
    the corpus's share in that slot.

    ``in_pos`` of the word's ``slots`` positional events fall in its dominant
    slot; ``slot_total`` of ``grand_total`` corpus-wide events fall in that same
    slot. Positive = the word concentrates in its dominant slot more than the
    rest of the corpus does (a tie is positive); negative = it leans there least
    of all despite it being its commonest slot. Returns 0 when degenerate."""
    if slots <= 0 or grand_total - slots <= 0:
        return 0.0
    g2 = log_likelihood_ratio_2x2(in_pos, slots, slot_total, grand_total)
    rate = in_pos / slots
    rest = grand_total - slots
    base_rate = (slot_total - in_pos) / rest if rest > 0 else 0.0
    return g2 if rate >= base_rate else -g2


@dataclass(frozen=True)
class PositionalRow:
    """A word's positional profile: token ``count``, its slot tallies
    (``initial`` / ``medial`` / ``final``), its ``dominant`` slot, and the signed
    positional-bias G²."""

    word: str
    count: int
    initial: int
    medial: int
    final: int
    dominant: str
    g2: float


_SLOT_LABEL = {"first": "initial", "mid": "medial", "last": "final"}


def _dominant(first: int, mid: int, last: int) -> str:
    if first >= mid and first >= last:
        return "first"
    if last >= mid and last >= first:
        return "last"
    return "mid"


def positional_bias(inscriptions: Iterable[Sequence[str]], *, min_count: int = 2) -> list[PositionalRow]:
    """Positional-bias G² for every word attested ``min_count`` times, over the
    word-position events of a corpus.

    ``inscriptions`` is an iterable of per-inscription word lists (any tokens
    without a hyphen are dropped, as in the workbench). Within an inscription a
    word's position is initial / medial / final among its hyphenated words; a
    lone hyphenated word counts in *both* edge slots (a deliberate workbench
    quirk that inflates the edge baselines). Baselines are summed over the whole
    vocabulary (hapaxes included); only words with ``count >= min_count`` are
    scored. Strongest positive bias first."""
    first: dict[str, int] = defaultdict(int)
    mid: dict[str, int] = defaultdict(int)
    last: dict[str, int] = defaultdict(int)
    count: dict[str, int] = defaultdict(int)
    for words in inscriptions:
        ws = [w for w in words if "-" in w]
        n = len(ws)
        for i, w in enumerate(ws):
            count[w] += 1
            if n == 1:
                first[w] += 1
                last[w] += 1
            elif i == 0:
                first[w] += 1
            elif i == n - 1:
                last[w] += 1
            else:
                mid[w] += 1
    pos_first = sum(first.values())
    pos_mid = sum(mid.values())
    pos_last = sum(last.values())
    grand = pos_first + pos_mid + pos_last
    pos_total = {"first": pos_first, "mid": pos_mid, "last": pos_last}

    rows: list[PositionalRow] = []
    for w, c in count.items():
        if c < min_count:
            continue
        d_first, d_mid, d_last = first[w], mid[w], last[w]
        slots = d_first + d_mid + d_last
        p = _dominant(d_first, d_mid, d_last)
        in_pos = {"first": d_first, "mid": d_mid, "last": d_last}[p]
        rows.append(
            PositionalRow(
                word=w,
                count=c,
                initial=d_first,
                medial=d_mid,
                final=d_last,
                dominant=_SLOT_LABEL[p],
                g2=positional_bias_g2(in_pos, slots, pos_total[p], grand),
            )
        )
    rows.sort(key=lambda r: (-r.g2, r.word))
    return rows


# ── Baayen's productivity ────────────────────────────────────────────────────


@dataclass(frozen=True)
class Productivity:
    """One affix's productivity: ``count`` (token sum of bearing words),
    ``distinct`` word types, ``hapax`` types (attested once), and Baayen's
    ``productivity`` P = hapax / count."""

    affix: str
    count: int
    distinct: int
    hapax: int
    productivity: float


def baayen_productivity(
    words: Iterable[tuple[str, int]],
    *,
    affix_len: int = 1,
    mode: str = "suffix",
) -> list[Productivity]:
    """Baayen's category-conditioned productivity P for every length-``affix_len``
    affix, most productive first.

    P = (number of hapax-legomena *types* bearing the affix) / (total *token*
    frequency of all words bearing it). ``words`` is an iterable of
    ``(word, count)`` pairs; words with no remaining stem are skipped.

    **Caveat.** On a corpus that is overwhelmingly hapax (most Linear A
    vocabulary) P runs high for nearly every affix, because almost every bearing
    type is itself a hapax. Read P as a *relative* ranking among affixes, never
    as an absolute productivity figure."""
    if mode not in ("suffix", "prefix"):
        raise ValueError(f"mode must be 'suffix' or 'prefix', got {mode!r}")
    counts: dict[str, int] = defaultdict(int)
    distinct: dict[str, int] = defaultdict(int)
    hapax: dict[str, int] = defaultdict(int)
    for word, count in words:
        parts = word.split("-")
        if len(parts) <= affix_len:
            continue
        if mode == "suffix":
            key = "-".join(parts[len(parts) - affix_len :])
        else:
            key = "-".join(parts[:affix_len])
        counts[key] += count
        distinct[key] += 1
        if count == 1:
            hapax[key] += 1
    rows = [
        Productivity(
            affix=affix,
            count=counts[affix],
            distinct=distinct[affix],
            hapax=hapax[affix],
            productivity=hapax[affix] / counts[affix] if counts[affix] > 0 else 0.0,
        )
        for affix in counts
    ]
    rows.sort(key=lambda r: (-r.productivity, -r.count, r.affix))
    return rows


# ── Harris successor variety ─────────────────────────────────────────────────


@dataclass(frozen=True)
class SuccessorRow:
    """A prefix's successor variety: ``variety`` distinct following signs, the
    ``parent_variety`` of the prefix one sign shorter, and ``ratio`` =
    variety / mean branching at this sign-depth."""

    stem: str
    variety: int
    parent_variety: int
    ratio: float


@dataclass(frozen=True)
class SuccessorVariety:
    """Successor-variety rows (passing the thresholds, strongest ``ratio`` first)
    and ``total`` = how many passed."""

    rows: list[SuccessorRow]
    total: int


def successor_variety(
    words: Iterable[str],
    *,
    min_prefix_signs: int = 2,
    min_variety: int = 3,
) -> SuccessorVariety:
    """Harris (1955) successor variety over a multi-sign word vocabulary, scored
    as a ratio against the per-depth mean branching factor.

    ``words`` is an iterable of distinct word *types* (token frequency is
    ignored — this is type-based). For each prefix of *k* signs, ``variety`` is
    the number of distinct signs that immediately follow it across the
    vocabulary; ``ratio`` divides that by the mean variety of all prefixes at
    depth *k*. Only prefixes of at least ``min_prefix_signs`` signs with variety
    at least ``min_variety`` are reported. A high ratio marks a candidate
    morpheme boundary — a heuristic, not a significance test."""
    succ: dict[str, set[str]] = defaultdict(set)
    for word in words:
        parts = word.split("-")
        if len(parts) < 2:
            continue
        for i in range(1, len(parts)):
            succ["-".join(parts[:i])].add(parts[i])
    depth_sum: dict[int, int] = defaultdict(int)
    depth_n: dict[int, int] = defaultdict(int)
    for pre, nexts in succ.items():
        d = len(pre.split("-"))
        depth_sum[d] += len(nexts)
        depth_n[d] += 1
    rows: list[SuccessorRow] = []
    for pre, nexts in succ.items():
        parts = pre.split("-")
        variety = len(nexts)
        if len(parts) < min_prefix_signs or variety < min_variety:
            continue
        d = len(parts)
        mean = depth_sum[d] / (depth_n[d] or 1)
        parent = "-".join(parts[:-1])
        rows.append(
            SuccessorRow(
                stem=pre,
                variety=variety,
                parent_variety=len(succ.get(parent, set())),
                ratio=variety / mean if mean > 0 else 0.0,
            )
        )
    rows.sort(key=lambda r: (-r.ratio, r.stem))
    return SuccessorVariety(rows=rows, total=len(rows))
