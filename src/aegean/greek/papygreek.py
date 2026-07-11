"""Documentary-Koine dependency evaluation against the PapyGreek Treebanks.

A complement to `aegean.greek.ud` (literary UD-Perseus/PROIEL) and `aegean.greek.nt_eval`
(Koine NT lemma/UPOS): this scores the active pipeline on **Greek documentary papyri**
(ca. 300 BCE-700 CE) — a register the other folds do not cover — with the *same* official
CoNLL 2018 evaluator, over gold tokens, reporting the full UD metric set (UPOS, XPOS,
UFeats, lemma, UAS, LAS, CLAS).

Data: a UD CoNLL-U fold converted from the **PapyGreek Treebanks**
(github.com/ezhenrik/papygreek-treebanks, **CC BY-SA 4.0**; Vierros et al., JOHD
10.5334/johd.55), which annotate documentary papyri in the Ancient Greek Dependency
Treebank Guidelines 2.0 scheme. ``scripts/build_papygreek_fold.py`` selects the
syntactically-annotated Greek trees (no artificial nodes, fully annotated, editorial
apparatus stripped to the reading text) and runs pyaegean's own AGDT->UD converter — the
code that built the training labels — so the fold is scored by exactly the machinery every
other UD fold uses. The fold is fetched to the cache for **evaluation only**, never bundled.

**Leakage.** Every fold sentence whose NFC form tuple appears in the shipped model's
training data (AGDT + Gorman + Pedalion, including Pedalion's documentary ``papyri.xml``
subset) is excluded at build time (the same form-tuple exclusion `agdt_ud_overlap` uses), so
the fold is leakage-clean for the shipped ``grc-joint`` model — a genuine out-of-domain
documentary-Koine generalization number.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..data import cache_dir

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

__all__ = [
    "PapyGreekConventionReport",
    "evaluate_on_papygreek",
    "evaluate_on_papygreek_dev",
    "papygreek_convention_report",
    "papygreek_dev_path",
    "papygreek_orig_path",
    "papygreek_path",
]

_ASSET = "papygreek-fold"
_CACHE_SUBDIR = "papygreek-grc"
_FOLD_NAME = "papygreek-test.conllu"

# The ORIG (diplomatic) surface variant of the test fold: the SAME 1,696 sentences and the
# SAME gold columns as the reg fold, with the emitted FORM swapped to the raw documentary
# orthography. Built by ``scripts/build_papygreek_fold.py --layer orig``; a distinct pinned
# asset, measured once by the integrator, never fitted against. See `papygreek_orig_path`.
_ORIG_ASSET = "papygreek-fold-orig"
_ORIG_FOLD_NAME = "papygreek-test-orig.conllu"

# The document-disjoint DEV fold (experiment/lever-ranking only, never a published number and
# never touching the pinned test fold): two tracks, one per fetchable asset. See
# ``scripts/build_papygreek_dev.py``. ``track -> (asset name, cache file name)``.
_DEV_ASSETS: dict[str, tuple[str, str]] = {
    "tagging": ("papygreek-dev-tagging", "papygreek-dev-tagging.conllu"),
    "parse": ("papygreek-dev-parse", "papygreek-dev-parse.conllu"),
}
# The fold decompresses to ~1.3 MB. This cap is comfortably above that (documentary
# folds could grow) and far below what would OOM: it guards a decompression bomb served
# through a ``PYAEGEAN_PAPYGREEK_FOLD_URL`` override that disables the sha256 pin.
_MAX_FOLD_BYTES = 256 * 1024 * 1024


def _fetch_conllu(asset: str, dest: Path, *, download: bool) -> Path:
    """Fetch a gzipped CoNLL-U asset and materialize it at ``dest``, via the shared
    `aegean.data.fetch_text` (capped decompress, atomic write, and the ``.sha256`` stamp
    sidecar that makes a re-pinned asset re-extract instead of serving a stale copy).
    Shared by the test fold and both dev tracks. CC BY-SA 4.0 — cached for evaluation
    only, never bundled."""
    from ..data import fetch_text

    # expect_gzip=True: every fold asset is a gzip archive, so a non-gzip body is a
    # corrupt or swapped download and must refuse, never materialize as the fold.
    return fetch_text(asset, dest, max_bytes=_MAX_FOLD_BYTES, download=download, expect_gzip=True)


def papygreek_path(*, download: bool = True) -> Path:
    """The cached CoNLL-U path of the PapyGreek test fold, fetched + decompressed on first use.

    The release asset is a gzipped CoNLL-U file (``papygreek-fold``). See `_fetch_conllu` for
    the fetch/decompress/stamp mechanics. CC BY-SA 4.0 — cached for evaluation only, never
    bundled."""
    return _fetch_conllu(_ASSET, cache_dir() / _CACHE_SUBDIR / _FOLD_NAME, download=download)


def papygreek_orig_path(*, download: bool = True) -> Path:
    """The cached CoNLL-U path of the PapyGreek ORIG (diplomatic) test fold, fetched +
    decompressed on first use.

    The diplomatic-surface variant of `papygreek_path`: the **same** 1,696 sentences and the
    **same** gold columns (UPOS/XPOS/UFeats/lemma/head/deprel), with the emitted FORM swapped
    to the raw documentary orthography (itacism, phonetic spelling, non-standard breathing) that
    the ``orig`` layer preserves. The two folds are token-aligned line-for-line and differ only
    in the surface form, so the orig row isolates the effect of the harder orthography. Built by
    ``scripts/build_papygreek_fold.py --layer orig``. See `_fetch_conllu` for the
    fetch/decompress/stamp mechanics. CC BY-SA 4.0 — cached for evaluation only, never
    bundled."""
    return _fetch_conllu(_ORIG_ASSET, cache_dir() / _CACHE_SUBDIR / _ORIG_FOLD_NAME, download=download)


def papygreek_dev_path(track: str = "tagging", *, download: bool = True) -> Path:
    """The cached CoNLL-U path of a PapyGreek DEV track, fetched + decompressed on first use.

    ``track`` is ``"tagging"`` (UPOS/XPOS/UFeats/lemma over annotated surface tokens) or
    ``"parse"`` (UAS/LAS over the reattached artificial-node sentences). The dev fold is
    document-disjoint from the pinned test fold and is for experiment/lever ranking only — it
    yields no published number and is never fitted against the test fold. CC BY-SA 4.0 — cached
    for evaluation only, never bundled."""
    if track not in _DEV_ASSETS:
        raise ValueError(f"track must be one of {sorted(_DEV_ASSETS)}; got {track!r}")
    asset, name = _DEV_ASSETS[track]
    return _fetch_conllu(asset, cache_dir() / _CACHE_SUBDIR / name, download=download)


def _score_fold(
    gold_path: Path,
    *,
    treebank: str,
    split: str,
    parse: bool | None,
    progress: Callable[[int, int], None] | None,
    batch_size: int | None,
) -> dict[str, Any]:
    """Score the active pipeline on a CoNLL-U fold with the official evaluator.

    The shared core of `evaluate_on_papygreek` and `evaluate_on_papygreek_dev`: it reuses
    `aegean.greek.ud`'s machinery wholesale (`ud.load_conllu`, `ud.pipeline_conllu`, the
    fetched official ``conll18_ud_eval`` and its scorer) so every fold is measured byte-for-byte
    the same way as UD-Perseus/PROIEL; only the gold data and the ``treebank``/``split`` labels
    differ."""
    from .ud import _eval_module, _score_conllu_text, load_conllu, pipeline_conllu

    sentences = load_conllu(gold_path)
    if parse is None:
        from . import joint, syntax

        parse = joint.active() is not None or syntax.active() is not None
    system_text = pipeline_conllu(sentences, parse=parse, progress=progress, batch_size=batch_size)
    gold_text = gold_path.read_text(encoding="utf-8")
    metrics = (
        ("upos", "xpos", "ufeats", "lemma", "uas", "las", "clas")
        if parse
        else ("upos", "xpos", "ufeats", "lemma")
    )
    ev = _eval_module()
    scores = _score_conllu_text(ev, gold_text, system_text, metrics)
    return {
        "treebank": treebank,
        "split": split,
        "parsed": parse,
        "upos": scores["upos"],
        "xpos": scores["xpos"],
        "ufeats": scores["ufeats"],
        "lemma": scores["lemma"],
        "uas": scores["uas"] if parse else None,
        "las": scores["las"] if parse else None,
        "clas": scores["clas"] if parse else None,
        "n_words": sum(len(s.tokens) for s in sentences),
        "n_sentences": len(sentences),
    }


def evaluate_on_papygreek(
    *,
    layer: str = "reg",
    source: Path | str | None = None,
    parse: bool | None = None,
    progress: Callable[[int, int], None] | None = None,
    batch_size: int | None = None,
) -> dict[str, Any]:
    """Score the active pipeline on the PapyGreek documentary-Koine fold (official evaluator).

    Reuses `aegean.greek.ud`'s machinery wholesale — `ud.load_conllu`, `ud.pipeline_conllu`
    (gold tokenization, the neural encoder pass, optional batching), the fetched official
    ``conll18_ud_eval`` (`ud._eval_module`), and its scorer (`ud._score_conllu_text`) — so
    this fold is measured byte-for-byte the same way as UD-Perseus/PROIEL; only the gold data
    and the ``"treebank"`` label differ. Activate the backends you want measured first
    (`use_neural_pipeline` for the shipped model). ``parse`` defaults to whether a parser/joint
    model is active; with ``parse=False`` UAS/LAS/CLAS are ``None``. ``progress`` is called as
    ``progress(done, total)`` per analyzed sentence; ``batch_size`` batches the neural
    encoder's passes (a throughput convenience — the recorded protocol is the sequential
    default). ``source`` overrides the fold path (tests pass a local CoNLL-U).

    ``layer`` selects which fold is fetched when ``source`` is not given: ``"reg"`` (the
    default, the editorially regularized reading behind the published PapyGreek numbers) or
    ``"orig"`` (the diplomatic-surface variant — the same sentences and gold, the raw
    documentary orthography as the FORM; see `papygreek_orig_path`). The orig fold measures the
    same model against a harder input and is directly comparable to the reg row.

    Returns ``{"treebank", "split", "layer", "parsed", "upos", "xpos", "ufeats", "lemma",
    "uas", "las", "clas", "n_words", "n_sentences"}`` — accuracies in [0, 1]. The fold is
    leakage-clean for the shipped model (see the module docstring)."""
    if layer not in ("reg", "orig"):
        raise ValueError(f"layer must be 'reg' or 'orig'; got {layer!r}")
    if source is not None:
        gold_path = Path(source)
    elif layer == "orig":
        gold_path = papygreek_orig_path()
    else:
        gold_path = papygreek_path()
    result = _score_fold(
        gold_path, treebank="papygreek", split="test",
        parse=parse, progress=progress, batch_size=batch_size,
    )
    result["layer"] = layer
    return result


def evaluate_on_papygreek_dev(
    track: str = "tagging",
    *,
    source: Path | str | None = None,
    parse: bool | None = None,
    progress: Callable[[int, int], None] | None = None,
    batch_size: int | None = None,
) -> dict[str, Any]:
    """Score the active pipeline on a PapyGreek documentary-Koine DEV track (official evaluator).

    The dev fold is **document-disjoint** from the pinned ``papygreek`` test fold and exists to
    rank levers and catch regressions **without touching the test fold** — it yields no
    published number and nothing is fitted against the test fold. Reuses the exact `_score_fold`
    machinery `evaluate_on_papygreek` uses; only the gold data (a dev track) differs.

    ``track`` is ``"tagging"`` — annotated surface tokens of the non-fold artificial/partial
    sentences, scored for UPOS/XPOS/UFeats/lemma (``parse`` forced ``False``; its trees are
    placeholders, UAS/LAS meaningless) — or ``"parse"`` — the reattached single-artificial-node
    sentences, scored for UAS/LAS (``parse`` defaults to whether a parser/joint model is active;
    the track is thin, treat its parse numbers as directional). ``source`` overrides the track
    path (tests pass a local CoNLL-U for an offline run). ``progress`` and ``batch_size`` are as
    for `evaluate_on_papygreek`.

    Returns the same key set as `evaluate_on_papygreek`, with ``"split"`` set to the track
    name."""
    if track not in _DEV_ASSETS:
        raise ValueError(f"track must be one of {sorted(_DEV_ASSETS)}; got {track!r}")
    gold_path = Path(source) if source is not None else papygreek_dev_path(track)
    # The tagging track's trees are placeholders (its sentences lack gold head/relation), so
    # UAS/LAS carry no meaning there — force gold-token tagging scoring only.
    if track == "tagging":
        parse = False
    return _score_fold(
        gold_path, treebank="papygreek-dev", split=track,
        parse=parse, progress=progress, batch_size=batch_size,
    )


# ── UPOS + XPOS convention decomposition ──────────────────────────────────────────
#
# The published PapyGreek UPOS (91.05) and XPOS (76.76) are capped by annotation /
# encoding CONVENTION, not just model quality — the documentary register writes the same
# Greek the AGDT-trained model learned under a *different* set of habits, and the merged
# training labels themselves tag the coordinators/particles under three incompatible
# conventions. This decomposition, in the pattern of `proiel_convention_report`, reproduces
# the official UPOS/XPOS from the model's own outputs and then partitions each gap into the
# convention parts (which the AGDT-trained model structurally cannot close on this fold) and
# the residual real error. Measurement only: it changes no published number and fits nothing
# to the fold.
#
# Findings this decomposition quantifies (matching the phase-1 error anatomy framing):
#  - UPOS: the coordinator class (gold CCONJ — καί/δέ/τε…) carries ~57% of all UPOS errors,
#    because the merged training set tags those words under three conventions (c/CCONJ vs the
#    non-AGDT b/X pos-code vs d/ADV) and the model drifts to the b/X and d readings.
#  - XPOS (9-position postag, exact match): the same coordinator pos-code drift (gold c → b/d),
#    the model's common-gender habit (predicting gender c where gold is a specific m/f/n or
#    none), and the fold's literal ``_`` gold slots (an encoding artifact the fold build does
#    not normalize to ``-``) are convention/encoding; the residue is real morphology error
#    (dominated by specific-gender confusion + case).

# A gold or system token reduced to the two fields this decomposition compares.
_PapyToken = tuple[str, str]  # (upos, xpos)

_COORD_POSCODE_DRIFT = frozenset({"b", "d"})  # gold pos-code 'c' predicted as b (→X) or d (→ADV)


def _pad9(x: str) -> str:
    """A 9-position AGDT postag, padded/truncated to 9 (for per-position bucketing). The
    exact-match accuracy itself is computed on the raw strings the evaluator compares."""
    return (x or "").ljust(9, "-")[:9]


def _classify_xpos_error(gx: str, px: str) -> str:
    """The convention/encoding bucket for one XPOS-error token (gold ``gx`` != pred ``px``).

    Priority-ordered so the buckets are mutually exclusive and partition every XPOS error:
      1. ``coordinator_poscode`` — gold pos-code 'c' predicted as 'b'/'d' (the coordinator
         convention: the whole tag is wrong because the closed-class label is unstable);
      2. ``common_gender`` — the model predicts gender 'c' (common) where gold is a specific
         gender or none (the model's over-applied common-gender habit);
      3. ``underscore_encoding`` — every differing position is a gold ``_`` vs predicted ``-``
         (the fold's un-normalized ``_`` slots; the model never emits ``_``);
      4. ``residual_real`` — everything else (real morphology error: specific gender, case…)."""
    g, p = _pad9(gx), _pad9(px)
    if g[0] == "c" and p[0] in _COORD_POSCODE_DRIFT:
        return "coordinator_poscode"
    if g[6] != "c" and p[6] == "c":
        return "common_gender"
    diffs = [i for i in range(9) if g[i] != p[i]]
    if diffs and all(g[i] == "_" and p[i] == "-" for i in diffs):
        return "underscore_encoding"
    return "residual_real"


class NeuralPipelineRequiredError(RuntimeError):
    """Raised when `papygreek_convention_report` is called with no neural pipeline active and no
    injected ``predictions``."""


@dataclass(frozen=True, slots=True)
class PapyGreekConventionReport:
    """Where the PapyGreek UPOS and XPOS gaps come from — annotation/encoding convention (the
    AGDT-trained model structurally cannot close it on this fold) told apart from real error.

    Measurement only: it reproduces the official UPOS/XPOS from the model's own outputs and
    partitions them; it does not replace any published number and nothing is fitted to the fold.
    Every count is over the fold's scored words (the evaluator scores every aligned syntactic
    word for UPOS/XPOS under gold tokenization)."""

    n_words: int
    # --- UPOS decomposition ---
    upos_correct: int
    upos_coordinator_errors: int   # gold CCONJ, mispredicted (the καί/δέ/τε collapse)
    upos_other_errors: int         # every other UPOS error
    upos_confusions: tuple[tuple[str, str, int], ...]   # (gold, predicted, count), most first
    # --- XPOS decomposition (9-position exact match) ---
    xpos_correct: int
    xpos_coordinator_poscode: int  # gold pos-code 'c' → 'b'/'d'
    xpos_common_gender: int        # predicted gender 'c' where gold is specific/none
    xpos_underscore_encoding: int  # pure gold '_' vs pred '-' (encoding artifact)
    xpos_residual_real: int        # real morphology error
    n_gold_xpos_underscore: int    # gold words whose postag carries a literal '_' in any slot
    xpos_position_errors: tuple[int, ...]   # per-position (0..8) error counts

    # -- UPOS --
    @property
    def upos(self) -> float:
        """Per-word UPOS accuracy (reproduces the official UPOS F1 under gold tokenization)."""
        return self.upos_correct / self.n_words if self.n_words else 0.0

    @property
    def upos_gap(self) -> float:
        return 1.0 - self.upos

    @property
    def upos_errors(self) -> int:
        return self.n_words - self.upos_correct

    @property
    def coordinator_share(self) -> float:
        """Fraction of ALL UPOS errors that fall on the coordinator class (gold CCONJ) — the
        single-phenomenon concentration signal (phase-1: ~57%)."""
        return self.upos_coordinator_errors / self.upos_errors if self.upos_errors else 0.0

    @property
    def upos_coordinator_pts(self) -> float:
        """Share of ALL words lost to coordinator-class UPOS errors (one additive part of the
        UPOS gap; ``upos_coordinator_pts + upos_other_pts == upos_gap``)."""
        return self.upos_coordinator_errors / self.n_words if self.n_words else 0.0

    @property
    def upos_other_pts(self) -> float:
        return self.upos_other_errors / self.n_words if self.n_words else 0.0

    # -- XPOS --
    @property
    def xpos(self) -> float:
        """Per-word XPOS (9-position exact) accuracy (reproduces the official XPOS F1)."""
        return self.xpos_correct / self.n_words if self.n_words else 0.0

    @property
    def xpos_gap(self) -> float:
        return 1.0 - self.xpos

    @property
    def xpos_errors(self) -> int:
        return self.n_words - self.xpos_correct

    def _pts(self, count: int) -> float:
        return count / self.n_words if self.n_words else 0.0

    @property
    def xpos_coordinator_pts(self) -> float:
        return self._pts(self.xpos_coordinator_poscode)

    @property
    def xpos_common_gender_pts(self) -> float:
        return self._pts(self.xpos_common_gender)

    @property
    def xpos_underscore_pts(self) -> float:
        return self._pts(self.xpos_underscore_encoding)

    @property
    def xpos_residual_pts(self) -> float:
        return self._pts(self.xpos_residual_real)

    @property
    def xpos_convention_pts(self) -> float:
        """The three convention/encoding parts of the XPOS gap, together (coordinator +
        common-gender + ``_``-encoding). ``xpos_convention_pts + xpos_residual_pts ==
        xpos_gap``."""
        return self._pts(
            self.xpos_coordinator_poscode + self.xpos_common_gender + self.xpos_underscore_encoding
        )

    @property
    def xpos_forgiving_convention(self) -> float:
        """XPOS accuracy if the three convention/encoding buckets are forgiven — the model's
        morphology quality with the convention cap removed."""
        forgiven = (
            self.xpos_correct + self.xpos_coordinator_poscode
            + self.xpos_common_gender + self.xpos_underscore_encoding
        )
        return forgiven / self.n_words if self.n_words else 0.0

    def summary(self, *, top: int = 8) -> str:
        """A short, readable account of both decompositions."""
        if not self.n_words:
            return "PapyGreek convention decomposition: no words"
        out = [
            f"PapyGreek convention decomposition over {self.n_words} words",
            f"  UPOS {self.upos:.1%} (gap {self.upos_gap:.1%}): coordinator class (gold CCONJ) "
            f"{self.upos_coordinator_pts:.1%} = {self.coordinator_share:.0%} of all UPOS errors "
            f"({self.upos_coordinator_errors} tokens) + {self.upos_other_pts:.1%} other",
        ]
        if self.upos_confusions:
            out.append("    top UPOS confusions (gold → predicted):")
            out += [
                f"      {g} → {p}: {c}"
                + (f" ({c / self.upos_errors:.0%} of UPOS errors)" if self.upos_errors else "")
                for g, p, c in self.upos_confusions[:top]
            ]
        out += [
            f"  XPOS {self.xpos:.1%} (gap {self.xpos_gap:.1%}): "
            f"{self.xpos_coordinator_pts:.1%} coordinator pos-code + "
            f"{self.xpos_common_gender_pts:.1%} common-gender + "
            f"{self.xpos_underscore_pts:.1%} '_'-encoding "
            f"= {self.xpos_convention_pts:.1%} convention/encoding, "
            f"+ {self.xpos_residual_pts:.1%} real morphology error",
            f"    forgiving those three, XPOS would be {self.xpos_forgiving_convention:.1%} "
            f"({self.n_gold_xpos_underscore} gold words carry a literal '_' slot)",
        ]
        return "\n".join(out)

    def as_dict(self) -> dict[str, Any]:
        """A JSON-serializable view (for ``--json`` / ``--drift`` and receipts)."""
        return {
            "n_words": self.n_words,
            "upos": self.upos,
            "upos_gap": self.upos_gap,
            "upos_errors": self.upos_errors,
            "upos_coordinator_errors": self.upos_coordinator_errors,
            "upos_coordinator_share_of_errors": self.coordinator_share,
            "upos_coordinator_pts": self.upos_coordinator_pts,
            "upos_other_pts": self.upos_other_pts,
            "upos_confusions": [[g, p, c] for g, p, c in self.upos_confusions],
            "xpos": self.xpos,
            "xpos_gap": self.xpos_gap,
            "xpos_errors": self.xpos_errors,
            "xpos_coordinator_poscode": self.xpos_coordinator_poscode,
            "xpos_common_gender": self.xpos_common_gender,
            "xpos_underscore_encoding": self.xpos_underscore_encoding,
            "xpos_residual_real": self.xpos_residual_real,
            "xpos_coordinator_pts": self.xpos_coordinator_pts,
            "xpos_common_gender_pts": self.xpos_common_gender_pts,
            "xpos_underscore_pts": self.xpos_underscore_pts,
            "xpos_residual_pts": self.xpos_residual_pts,
            "xpos_convention_pts": self.xpos_convention_pts,
            "xpos_forgiving_convention": self.xpos_forgiving_convention,
            "n_gold_xpos_underscore": self.n_gold_xpos_underscore,
            "xpos_position_errors": list(self.xpos_position_errors),
        }


def _decompose_papygreek(
    gold: Sequence[Sequence[_PapyToken]],
    system: Sequence[Sequence[_PapyToken]],
) -> PapyGreekConventionReport:
    """The pure decomposition core: align gold and system word-for-word (gold tokenization →
    identical token sequences) and tabulate the UPOS and XPOS convention splits.

    Each token is ``(upos, xpos)``. Every word counts. Injected directly by the tests so the
    split can be checked against numbers known by construction; `papygreek_convention_report`
    builds the two arguments from the fold gold and the model's outputs."""
    n_words = upos_correct = xpos_correct = 0
    upos_coord_err = upos_other_err = 0
    xb: Counter[str] = Counter()
    upos_conf: Counter[tuple[str, str]] = Counter()
    pos_err = [0] * 9
    n_gold_us = 0

    for g_sent, s_sent in zip(gold, system, strict=True):
        for (g_upos, g_xpos), (s_upos, s_xpos) in zip(g_sent, s_sent, strict=True):
            n_words += 1
            if "_" in _pad9(g_xpos):
                n_gold_us += 1
            # UPOS
            if g_upos == s_upos:
                upos_correct += 1
            else:
                upos_conf[(g_upos, s_upos)] += 1
                if g_upos == "CCONJ":
                    upos_coord_err += 1
                else:
                    upos_other_err += 1
            # XPOS (exact match on the raw evaluator strings)
            if g_xpos == s_xpos:
                xpos_correct += 1
            else:
                xb[_classify_xpos_error(g_xpos, s_xpos)] += 1
                gp, pp = _pad9(g_xpos), _pad9(s_xpos)
                for i in range(9):
                    if gp[i] != pp[i]:
                        pos_err[i] += 1

    return PapyGreekConventionReport(
        n_words=n_words,
        upos_correct=upos_correct,
        upos_coordinator_errors=upos_coord_err,
        upos_other_errors=upos_other_err,
        upos_confusions=tuple((g, p, c) for (g, p), c in upos_conf.most_common()),
        xpos_correct=xpos_correct,
        xpos_coordinator_poscode=xb["coordinator_poscode"],
        xpos_common_gender=xb["common_gender"],
        xpos_underscore_encoding=xb["underscore_encoding"],
        xpos_residual_real=xb["residual_real"],
        n_gold_xpos_underscore=n_gold_us,
        xpos_position_errors=tuple(pos_err),
    )


def papygreek_convention_report(
    *,
    source: Path | str | None = None,
    batch_size: int | None = None,
    progress: Callable[[int, int], None] | None = None,
    predictions: Sequence[Sequence[_PapyToken]] | None = None,
) -> PapyGreekConventionReport:
    """Decompose the PapyGreek UPOS and XPOS gaps into annotation/encoding convention versus
    real error, on the neural pipeline's own outputs.

    Runs the active neural pipeline (`aegean.greek.use_neural_pipeline` — the model behind the
    published PapyGreek numbers) over the fold's gold tokens and compares its UPOS/XPOS to gold.
    Returns a `PapyGreekConventionReport` whose ``upos``/``xpos`` reproduce the official metrics
    from the model's outputs, split into the coordinator / common-gender / ``_``-encoding
    convention parts and the residual real error. This is a measurement DECOMPOSITION: it
    changes no published number and fits nothing to the fold.

    ``batch_size`` defaults to ``None`` (**sequential**, unlike `proiel_convention_report`): the
    published PapyGreek numbers are the sequential run and batch-32 is not prediction-identical
    on this fold, so a sequential pass is needed to reproduce them exactly. ``source`` overrides
    the fold path (tests pass a local CoNLL-U fixture); ``progress`` is called ``progress(done,
    total)`` per sentence. ``predictions`` injects the system outputs directly (one
    ``(upos, xpos)`` per gold token, sentence-aligned) so the decomposition can be exercised
    without the model; with it, no pipeline is required."""
    from .ud import load_conllu

    gold_path = Path(source) if source is not None else papygreek_path()
    sentences = load_conllu(gold_path)
    gold: list[list[_PapyToken]] = [[(t.upos, t.xpos) for t in s.tokens] for s in sentences]

    if predictions is not None:
        system: Sequence[Sequence[_PapyToken]] = predictions
    else:
        from . import joint

        model = joint.active()
        if model is None:
            raise NeuralPipelineRequiredError(
                "papygreek_convention_report needs the neural pipeline active (it decomposes the "
                "neural model's UPOS/XPOS): call aegean.greek.use_neural_pipeline() first, or "
                "pass predictions= to inject system outputs."
            )
        system = _model_upos_xpos(
            model, [[t.form for t in s.tokens] for s in sentences],
            batch_size=batch_size, progress=progress,
        )
    return _decompose_papygreek(gold, system)


def _model_upos_xpos(
    model: Any,
    forms: Sequence[Sequence[str]],
    *,
    batch_size: int | None,
    progress: Callable[[int, int], None] | None,
) -> list[list[_PapyToken]]:
    """Run the joint model over each sentence's gold forms → ``(upos, xpos)`` per token.
    Sequential by default (the published numbers' protocol); batched when ``batch_size`` is set
    (a throughput convenience — not prediction-identical on this fold, see the caller)."""
    forms_list = [list(f) for f in forms]
    total = len(forms_list)
    out: list[list[_PapyToken]] = []
    done = 0
    if batch_size is not None and batch_size >= 1:
        for start in range(0, total, batch_size):
            chunk = forms_list[start : start + batch_size]
            for ana in model.analyze_batch(chunk):
                out.append(list(zip(ana.upos, ana.xpos)))
                done += 1
                if progress is not None:
                    progress(done, total)
    else:
        for sent in forms_list:
            ana = model.analyze(sent)
            out.append(list(zip(ana.upos, ana.xpos)))
            done += 1
            if progress is not None:
                progress(done, total)
    return out
