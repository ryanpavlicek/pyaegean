"""Byzantine book-epigram POS/lemma tagging evaluation against the DBBE gold standard.

A register neither the literary UD folds (`aegean.greek.ud`), the Koine NT
(`aegean.greek.nt_eval`), nor the documentary-Koine PapyGreek fold (`aegean.greek.papygreek`)
cover: **medieval (Byzantine) Greek verse**, the 7th-15th c. of DBBE's documented scope. This
scores the active pipeline's
tagging (UPOS, XPOS, UFeats, lemma) on the DBBE linguistic-annotation gold standard with the
*same* official CoNLL 2018 evaluator, over gold tokens.

Data: a UD CoNLL-U fold converted from the **DBBE gold standard**
(github.com/coswaele/ByzantineGreekDatasets, ``lingAnn_GS_medievalGreek.tsv`` — Swaelens, De
Vos & Lefever / DBBE, Ghent University; **CC BY 4.0**). ``scripts/build_dbbe_fold.py`` selects
the clean, fully-tagged tokens and runs pyaegean's OWN AGDT->UD converter — the code that built
the training labels — so the fold is scored by exactly the machinery every other UD fold uses.
The fold is fetched to the cache for **evaluation only**, never bundled.

**Tagging only.** The DBBE gold standard annotates POS + morphology + lemma but **no dependency
trees**, so this fold reports only the tagging metrics (UPOS/XPOS/UFeats/lemma); ``parse`` is
forced ``False`` and UAS/LAS/CLAS are ``None``. It is a small, single-register datapoint (825
sentences / 9,191 tokens), reported as such and never a headline number.

**Two documented systematic caps** the AGDT-trained model structurally cannot close on this
fold, so the row reads low by construction, not by model quality:

* *Attic-lemma normalization.* DBBE standardizes lemmas to Attic dictionary headwords; a
  Byzantine surface form whose lemma the model composes to a non-Attic (medieval) headword
  scores as a lemma miss even when the analysis is right.
* *Mapped tagset + copular ``εἰμί``.* The AGDT 9-position postag is mapped to UD UPOS by
  pyaegean's converter; the ``c`` pos-code splits to CCONJ/SCONJ and ``l`` to DET, and because
  the tagging-only source carries no tree context the copular ``εἰμί`` scores VERB (no PNOM
  dependent to mark it AUX) — the same systematic convention cap the PapyGreek decomposition
  quantifies.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..data import cache_dir

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = [
    "dbbe_path",
    "evaluate_on_dbbe",
]

_ASSET = "dbbe-lingann-fold"
_CACHE_SUBDIR = "dbbe-grc"
_FOLD_NAME = "dbbe-lingann-test.conllu"
# The fold decompresses to ~0.6 MB. This cap sits far above that (a register fold could grow)
# and far below what would OOM: it guards a decompression bomb served through a
# ``PYAEGEAN_DBBE_LINGANN_FOLD_URL`` override that disables the sha256 pin.
_MAX_FOLD_BYTES = 256 * 1024 * 1024


def dbbe_path(*, download: bool = True) -> Path:
    """The cached CoNLL-U path of the DBBE Byzantine book-epigram tagging fold, fetched +
    decompressed on first use.

    The release asset is a gzipped CoNLL-U file (``dbbe-lingann-fold``). Fetched via the shared
    `aegean.data.fetch_text` (capped decompress, atomic write, and the ``.sha256`` stamp sidecar
    that makes a re-pinned asset re-extract instead of serving a stale copy). ``expect_gzip=True``
    so a non-gzip body (a corrupt or swapped download) refuses rather than materializing as the
    fold. CC BY 4.0 — cached for evaluation only, never bundled."""
    from ..data import fetch_text

    return fetch_text(
        _ASSET,
        cache_dir() / _CACHE_SUBDIR / _FOLD_NAME,
        max_bytes=_MAX_FOLD_BYTES,
        download=download,
        expect_gzip=True,
    )


def evaluate_on_dbbe(
    *,
    source: Path | str | None = None,
    progress: Callable[[int, int], None] | None = None,
    batch_size: int | None = None,
) -> dict[str, Any]:
    """Score the active pipeline's tagging on the DBBE Byzantine book-epigram fold (official
    evaluator).

    Reuses `aegean.greek.papygreek._score_fold` wholesale — which in turn reuses
    `aegean.greek.ud`'s machinery (`ud.load_conllu`, `ud.pipeline_conllu`, the fetched official
    ``conll18_ud_eval`` and its scorer) — so this fold is measured byte-for-byte the same way as
    UD-Perseus/PROIEL and PapyGreek; only the gold data and the ``"treebank"`` label differ.
    Activate the backends you want measured first (`use_neural_pipeline` for the shipped model).

    **Tagging only.** The DBBE gold standard carries no dependency trees, so ``parse`` is forced
    ``False``: the result reports UPOS/XPOS/UFeats/lemma and UAS/LAS/CLAS are ``None``. ``progress``
    is called as ``progress(done, total)`` per analyzed sentence; ``batch_size`` batches the neural
    encoder's passes (a throughput convenience — the recorded protocol is the sequential default).
    ``source`` overrides the fold path (tests pass a local CoNLL-U).

    The score reads low by construction (see the module docstring: Attic-lemma normalization,
    the mapped tagset, copular ``εἰμί`` without tree context), and it is a small, single-register
    datapoint — a Byzantine-verse row, never a headline number.

    Returns ``{"treebank", "split", "parsed", "upos", "xpos", "ufeats", "lemma", "uas", "las",
    "clas", "n_words", "n_sentences"}`` — the tagging accuracies in [0, 1], the parse metrics
    ``None``."""
    from .papygreek import _score_fold

    gold_path = Path(source) if source is not None else dbbe_path()
    return _score_fold(
        gold_path,
        treebank="dbbe",
        split="test",
        parse=False,
        progress=progress,
        batch_size=batch_size,
    )
