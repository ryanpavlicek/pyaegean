"""Ancient Greek VERSE dependency evaluation (tragedy: Euripides, Bacchae 1-169).

A companion to `aegean.greek.ud` (literary UD-Perseus/PROIEL), `aegean.greek.nt_eval`
(Koine NT), and `aegean.greek.papygreek` (documentary Koine): this scores the active
pipeline on **poetic** Ancient Greek — a register the other folds do not cover — with the
*same* official CoNLL 2018 evaluator, over gold tokens, reporting the full UD metric set
(UPOS, XPOS, UFeats, lemma, UAS, LAS, CLAS).

The fold is **tragedy-only**: **Euripides, Bacchae 1-169** (spoken trimeter + the lyric
parodos), carried under the ``verse:tragedy:...`` ``sent_id`` prefix — a leakage-clean
tragedy dependency evaluation for the shipped model (no prior one is known to us). A former
``verse:hexameter:...`` sliver (Maximus, Peri katarchon 1.4) was removed: on inspection it
was the Maximus PROSE paraphrase (the sentences do not scan), so it was dropped rather than
mislabeled as hexameter (see docs/benchmarks.md). ``track="tragedy"`` (or ``"all"``/``None``,
which apply no filter and score whatever the fetched fold holds) selects the tragedy fold; the
``"hexameter"`` filter value is rejected.

Data: a UD CoNLL-U fold converted from the **unesp-trees** treebanks
(github.com/perseids-publications/unesp-trees, **CC BY-SA 4.0**; the Perseids/Arethusa
manual gold annotation of Prof. Anise D'Orange Ferreira's UNESP project) by
``scripts/build_verse_fold.py``, which selects the fully-annotated, artificial-node-free,
cleanly-readable sentences and runs pyaegean's own AGDT->UD converter — the code that built
the training labels — so the fold is scored by exactly the machinery every other UD fold
uses. Fetched to the cache for **evaluation only**, never bundled, never trained on.

**Leakage.** Every fold sentence whose NFC form tuple appears in the shipped model's
training data (AGDT + Gorman + Pedalion) is excluded at build time (the same form-tuple
exclusion `agdt_ud_overlap` uses), and the build additionally asserts work-level
disjointness (Bacchae / Maximus are absent from the training documents; the only trained
Euripides is Medea). So the fold is leakage-clean for the shipped ``grc-joint`` model.

**Read this before quoting any number.** This is a **SMALL-SAMPLE genre-conditioned
datapoint** (tens of sentences) whose accuracy carries **wide bootstrap confidence
intervals**; the tragedy fold is a leakage-clean tragedy evaluation (no prior one is
known to us). It is **never a headline number** — report it with the sample size and CI,
alongside the leakage-clean literary/documentary folds, not on its own.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..data import cache_dir

if TYPE_CHECKING:
    from collections.abc import Callable

    from .ud import UDSentence

__all__ = [
    "evaluate_on_verse",
    "verse_path",
]

_ASSET = "verse-fold"
_CACHE_SUBDIR = "verse-grc"
_FOLD_NAME = "verse-test.conllu"

# The selectable ``track`` filter values. The fold is tragedy-only: the former ``hexameter``
# sliver was the Maximus PROSE paraphrase (the sentences do not scan) and has been removed
# (see docs/benchmarks.md). ``"all"`` (and ``None``) apply no filter and score whatever the
# fetched fold holds; the ``"hexameter"`` filter value is rejected explicitly.
_TRACKS: tuple[str, ...] = ("tragedy", "all")

# The fold decompresses to well under 1 MB. This cap is far above that and far below what
# would OOM: it guards a decompression bomb served through a ``PYAEGEAN_VERSE_FOLD_URL``
# override that disables the sha256 pin.
_MAX_FOLD_BYTES = 256 * 1024 * 1024


def _fetch_conllu(dest: Path, *, download: bool) -> Path:
    """Fetch the gzipped verse fold and materialize it at ``dest``, via the shared
    `aegean.data.fetch_text` (capped decompress, atomic write, the ``.sha256`` stamp sidecar
    that makes a re-pinned asset re-extract instead of serving a stale copy). CC BY-SA 4.0 —
    cached for evaluation only, never bundled."""
    from ..data import fetch_text

    # expect_gzip=True: the fold asset is always a gzip archive, so a non-gzip body is a
    # corrupt or swapped download and must refuse, never materialize as the fold.
    return fetch_text(_ASSET, dest, max_bytes=_MAX_FOLD_BYTES, download=download, expect_gzip=True)


def verse_path(*, download: bool = True) -> Path:
    """The cached CoNLL-U path of the verse fold, fetched + decompressed on first use.

    The release asset is a gzipped CoNLL-U file (``verse-fold``) holding both tracks
    (``verse:tragedy:...`` + ``verse:hexameter:...``). See `_fetch_conllu` for the fetch/
    decompress/stamp mechanics. This fold is a **small-sample genre-conditioned datapoint
    with wide bootstrap CIs, never a headline number** — CC BY-SA 4.0, cached for evaluation
    only, never bundled."""
    return _fetch_conllu(cache_dir() / _CACHE_SUBDIR / _FOLD_NAME, download=download)


def _read_track(gold_path: Path, track: str | None) -> tuple[list[UDSentence], str]:
    """Load the fold and (optionally) restrict it to one track's sentences.

    Returns ``(sentences, gold_text)`` where the two are byte-aligned: the CoNLL-U blocks in
    ``gold_text`` correspond one-to-one, in order, to ``sentences`` (both derived from the
    same file in the same order, then filtered by the ``verse:<track>:`` ``sent_id``
    prefix). ``track=None`` keeps every sentence."""
    from .ud import _split_conllu_sentences, load_conllu

    sentences = load_conllu(gold_path)
    blocks = _split_conllu_sentences(gold_path.read_text(encoding="utf-8"))
    if len(blocks) != len(sentences):
        raise ValueError(
            f"fold sentence/block count mismatch: {len(sentences)} vs {len(blocks)}"
        )
    if track is None:
        return sentences, "".join(blocks)
    prefix = f"verse:{track}:"
    pairs = [(s, b) for s, b in zip(sentences, blocks) if s.sent_id.startswith(prefix)]
    return [s for s, _ in pairs], "".join(b for _, b in pairs)


def evaluate_on_verse(
    track: str | None = None,
    *,
    source: Path | str | None = None,
    parse: bool | None = None,
    progress: Callable[[int, int], None] | None = None,
    batch_size: int | None = None,
) -> dict[str, Any]:
    """Score the active pipeline on the Ancient Greek verse fold (official evaluator).

    Reuses `aegean.greek.ud`'s machinery wholesale — `ud.load_conllu`, `ud.pipeline_conllu`
    (gold tokenization, the neural encoder pass, optional batching), the fetched official
    ``conll18_ud_eval`` (`ud._eval_module`), and its scorer (`ud._score_conllu_text`) — so
    this fold is measured byte-for-byte the same way as UD-Perseus/PROIEL and PapyGreek;
    only the gold data and the labels differ. Activate the backends you want measured first
    (`use_neural_pipeline` for the shipped model).

    ``track`` selects ``"tragedy"`` (Euripides, Bacchae 1-169) or ``"all"``/``None`` for the
    whole fetched fold (no filter). The fold is tragedy-only, so the former ``"hexameter"``
    filter value is rejected with guidance (see the module docstring). ``parse`` defaults to
    whether a parser/joint model is active; with ``parse=False`` UAS/LAS/CLAS are ``None``.
    ``progress`` is called as ``progress(done, total)`` per analyzed sentence; ``batch_size``
    batches the neural
    encoder's passes (a throughput convenience — the recorded protocol is the sequential
    default). ``source`` overrides the fold path (tests pass a local CoNLL-U).

    Returns ``{"treebank", "track", "split", "parsed", "upos", "xpos", "ufeats", "lemma",
    "uas", "las", "clas", "n_words", "n_sentences"}`` — accuracies in [0, 1].

    This is a **SMALL-SAMPLE genre-conditioned datapoint with wide bootstrap confidence
    intervals** (tens of sentences); the tragedy fold is a leakage-clean tragedy evaluation
    (no prior one is known to us). **It is never a headline number** — report it with the
    sample size and CI, not on its own."""
    if track == "hexameter":
        raise ValueError(
            "track 'hexameter' was removed: the hexameter sliver was identified as the Maximus "
            "prose paraphrase (the sentences do not scan) and the verse fold is tragedy-only; "
            "use track='tragedy' or 'all' (see docs/benchmarks.md)"
        )
    if track is not None and track not in _TRACKS:
        raise ValueError(f"track must be one of {list(_TRACKS)} or None; got {track!r}")
    from .ud import _eval_module, _score_conllu_text, pipeline_conllu

    gold_path = Path(source) if source is not None else verse_path()
    # 'all' (and None) apply no filter; only 'tragedy' filters by the sent_id prefix.
    filter_track = None if track in (None, "all") else track
    sentences, gold_text = _read_track(gold_path, filter_track)
    # Zero sentences after filtering would emit a lone "\n" that the official evaluator
    # misparses into a misleading "multiple roots" UDError; refuse cleanly, naming track+source.
    if not sentences:
        scope = f"track {track!r}" if filter_track is not None else "the fold"
        raise ValueError(
            f"verse {scope} matched zero sentences in {gold_path}: nothing to score"
        )
    if parse is None:
        from . import joint, syntax

        parse = joint.active() is not None or syntax.active() is not None
    system_text = pipeline_conllu(sentences, parse=parse, progress=progress, batch_size=batch_size)
    metrics = (
        ("upos", "xpos", "ufeats", "lemma", "uas", "las", "clas")
        if parse
        else ("upos", "xpos", "ufeats", "lemma")
    )
    ev = _eval_module()
    scores = _score_conllu_text(ev, gold_text, system_text, metrics)
    return {
        "treebank": "verse",
        "track": track or "all",
        "split": "test",
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
