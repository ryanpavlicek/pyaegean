"""Heuristic morphological clustering for an undeciphered syllabic script.

A faithful port of ``findMorphologicalClusters`` from the workbench
``src/lib/algorithms.ts``: find suffixes that are *productive* (end many
distinct words), then group words where one is a stem of another via a
productive suffix (union-find over the corpus vocabulary).

**Exploratory.** With no known grammar, "suffix" here means a recurring final
sign-string, not a confirmed morpheme. Clusters are leads for morphological
analysis, not established paradigms.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ClusterMember:
    """A word in a cluster, with the signs it appends beyond the cluster stem
    (``""`` for the stem itself; ``"≠"`` flags a member that doesn't actually
    extend the stem)."""

    word: str
    count: int
    suffix: str


@dataclass(frozen=True, slots=True)
class MorphCluster:
    """A stem and its productive-suffix derivations."""

    stem: str
    members: tuple[ClusterMember, ...]
    total_count: int
    suffixes: tuple[str, ...]


def find_morphological_clusters(
    words: Iterable[Mapping[str, object] | tuple[str, int]],
    min_suffix_productivity: int = 5,
    min_cluster_size: int = 2,
    max_suffix_len: int = 2,
) -> list[MorphCluster]:
    """Cluster stems with their productive-suffix derivations.

    ``words`` is an iterable of ``{"word": str, "count": int}`` mappings or
    ``(word, count)`` pairs (e.g. straight from :meth:`Corpus.word_frequencies`).
    A suffix is *productive* when it ends at least ``min_suffix_productivity``
    distinct words; clusters smaller than ``min_cluster_size`` are dropped;
    suffixes are considered up to ``max_suffix_len`` signs long.
    """
    # Normalize input to (word, count) and keep multi-sign words only — a
    # single-sign token carries no morphological signal.
    norm: list[tuple[str, int]] = []
    for w in words:
        if isinstance(w, Mapping):
            word, count = str(w["word"]), int(w["count"])  # type: ignore[call-overload]
        else:
            word, count = str(w[0]), int(w[1])
        if "-" in word:
            norm.append((word, count))

    by_word = dict(norm)
    word_set = set(by_word)

    # Tally suffix productivity (distinct-word counts) at sign granularity.
    suffix_prod: dict[str, set[str]] = {}
    for word, _ in norm:
        parts = word.split("-")
        for length in range(1, min(max_suffix_len, len(parts) - 1) + 1):
            suf = "-".join(parts[-length:])
            suffix_prod.setdefault(suf, set()).add(word)
    productive = {suf for suf, s in suffix_prod.items() if len(s) >= min_suffix_productivity}

    # Union-Find over words: link word ↔ (word − productive suffix) when both
    # are corpus-attested. The shorter word becomes the root (likely stem).
    parent = {word: word for word, _ in norm}

    def find(x: str) -> str:
        cur = x
        while parent[cur] != cur:
            cur = parent[cur]
        p = x
        while parent[p] != cur:  # path compression
            parent[p], p = cur, parent[p]
        return cur

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra == rb:
            return
        if len(ra.split("-")) <= len(rb.split("-")):
            parent[rb] = ra
        else:
            parent[ra] = rb

    for word, _ in norm:
        parts = word.split("-")
        for length in range(1, min(max_suffix_len, len(parts) - 1) + 1):
            suf = "-".join(parts[-length:])
            if suf not in productive:
                continue
            stem = "-".join(parts[: len(parts) - length])
            if stem in word_set:
                union(word, stem)

    # Collect connected components (insertion-ordered to match the TS Map).
    groups: dict[str, list[str]] = {}
    for word, _ in norm:
        groups.setdefault(find(word), []).append(word)

    clusters: list[MorphCluster] = []
    for members in groups.values():
        if len(members) < min_cluster_size:
            continue
        # Cluster stem = shortest (fewest signs) member; ties broken by count.
        stem = sorted(
            members,
            key=lambda w: (len(w.split("-")), -(by_word.get(w, 0))),
        )[0]
        stem_parts = stem.split("-")
        shared_len = len(stem_parts)
        member_list: list[ClusterMember] = []
        for member in members:
            parts = member.split("-")
            if member == stem:
                suffix = ""
            elif len(parts) > shared_len and all(
                stem_parts[i] == parts[i] for i in range(shared_len)
            ):
                suffix = "-".join(parts[shared_len:])
            else:
                suffix = "≠"  # member doesn't actually extend the stem
            member_list.append(ClusterMember(member, by_word.get(member, 0), suffix))
        member_list.sort(key=lambda m: -m.count)
        total_count = sum(m.count for m in member_list)
        suffixes = tuple(
            dict.fromkeys(m.suffix for m in member_list if m.suffix and m.suffix != "≠")
        )
        clusters.append(
            MorphCluster(stem, tuple(member_list), total_count, suffixes)
        )
    clusters.sort(key=lambda c: -len(c.members))
    return clusters
