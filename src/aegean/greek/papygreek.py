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

import gzip
import hashlib
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .._atomic import atomic_path
from ..data import DataNotAvailableError, cache_dir, fetch

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = ["evaluate_on_papygreek", "papygreek_path"]

_ASSET = "papygreek-fold"
_CACHE_SUBDIR = "papygreek-grc"
_FOLD_NAME = "papygreek-test.conllu"
# The fold decompresses to ~1.3 MB. This cap is comfortably above that (documentary
# folds could grow) and far below what would OOM: it guards a decompression bomb served
# through a ``PYAEGEAN_PAPYGREEK_FOLD_URL`` override that disables the sha256 pin.
_MAX_FOLD_BYTES = 256 * 1024 * 1024


def _decompress_fold(gz: Path, *, max_bytes: int = _MAX_FOLD_BYTES) -> str:
    """Decompress the gzipped fold to text, capping the decompressed size.

    The asset is sha256-pinned when fetched from the project release, but a
    ``PYAEGEAN_PAPYGREEK_FOLD_URL`` override disables that check, so a swapped mirror could
    serve a tiny gzip that inflates to gigabytes. Decompress in chunks and stop with a clear
    error past ``max_bytes`` instead of reading the whole stream blindly (mirrors
    `aegean.data.load_gzip_json`)."""
    buf = bytearray()
    with gzip.open(gz, "rb") as fin:
        while True:
            chunk = fin.read(1 << 20)
            if not chunk:
                break
            buf += chunk
            if len(buf) > max_bytes:
                raise DataNotAvailableError(
                    f"{gz} decompresses to more than {max_bytes} bytes; refusing to load it "
                    "(a possible decompression bomb from an unverified mirror)"
                )
    return buf.decode("utf-8")


def papygreek_path(*, download: bool = True) -> Path:
    """The cached CoNLL-U path of the PapyGreek fold, fetched + decompressed on first use.

    The release asset is a gzipped CoNLL-U file (``papygreek-fold``); this fetches it (sha256
    pinned), decompresses it with a size cap, and writes it to a stable cache path. The write
    is atomic (temp file + ``os.replace``), so an interrupted decompress never leaves a
    truncated ``.conllu`` behind. A ``.sha256`` stamp sidecar records which archive the
    decompressed copy came from, so a re-pinned fold (a ``-v2`` asset) re-decompresses instead
    of serving the stale copy forever; a missing stamp re-decompresses too (the fold is ~1.3 MB,
    so unlike the heavy extract archives there is no legacy-trust carve-out). CC BY-SA 4.0 —
    cached for evaluation only, never bundled."""
    dest = cache_dir() / _CACHE_SUBDIR / _FOLD_NAME
    stamp = dest.with_name(dest.name + ".sha256")
    if not download:
        return dest
    gz = fetch(_ASSET)
    gz_sha = hashlib.sha256(gz.read_bytes()).hexdigest()
    if dest.exists() and stamp.exists():
        try:
            if stamp.read_text(encoding="ascii").strip() == gz_sha:
                return dest
        except (OSError, UnicodeDecodeError):
            pass  # unreadable stamp: fall through to a fresh decompress
    text = _decompress_fold(gz)
    with atomic_path(dest) as tmp:
        tmp.write_text(text, encoding="utf-8")
    # written after dest: an interruption between the two leaves a missing stamp, which
    # re-decompresses on the next call rather than trusting an unverified copy
    with atomic_path(stamp) as tmp:
        tmp.write_text(gz_sha, encoding="ascii")
    return dest


def evaluate_on_papygreek(
    *,
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

    Returns ``{"treebank", "split", "parsed", "upos", "xpos", "ufeats", "lemma", "uas", "las",
    "clas", "n_words", "n_sentences"}`` — accuracies in [0, 1]. The fold is leakage-clean for
    the shipped model (see the module docstring)."""
    from .ud import _eval_module, _score_conllu_text, load_conllu, pipeline_conllu

    gold_path = Path(source) if source is not None else papygreek_path()
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
        "treebank": "papygreek",
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
