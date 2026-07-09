"""UD (CoNLL-U) evaluation harness — pyaegean on the field's standard benchmark.

`aegean.greek.heldout` measures generalization *within* the AGDT under pyaegean's own
protocol, and `aegean.greek.proiel` measures it on out-of-AGDT text. This module measures
the pipeline on the **Universal Dependencies** Ancient Greek test folds with the **official
CoNLL 2018 shared-task evaluator** — the protocol behind the published cross-tool numbers
(see ``docs/benchmarks.md``) — and builds the **leakage-exclusion manifest** that every
future trained model must honour.

Data: ``UD_Ancient_Greek-Perseus`` / ``UD_Ancient_Greek-PROIEL``, pinned to commits,
licensed **CC BY-NC-SA** (Perseus 2.5, PROIEL 3.0) — fetched to the cache for **evaluation
only**, never bundled and never trained on (the PROIEL handling). The evaluator (``conll18_ud_eval.py``, Mozilla
Public License 2.0) is fetched to the cache pinned by sha256 and imported from there.

Protocol (spelled out in ``docs/benchmarks.md``):

- **Gold tokenization.** The pipeline runs over each fold's gold FORM column, so scores
  measure tagging/lemma/parsing quality, not tokenizer agreement.
- **No tagset collapsing.** UPOS and lemmas are scored exactly as emitted (unlike
  `evaluate_on_proiel`, which reconciles tagsets) — convention gaps count against us.
- **DEPREL.** The shipped neural pipeline emits UD relations, so **LAS** is scored directly
  against UD gold. (The legacy pure-Python parser emits AGDT/Prague labels, for which only
  **UAS** is comparable; it is reported as a baseline, not as the accuracy claim.)
- **Leakage.** UD Perseus is converted *from* the AGDT, so its sentence ids point straight at
  AGDT files (``tlg0008….tb.xml@197``). The shipped neural model's training split removes every
  UD-Perseus dev+test sentence via the `agdt_ud_overlap` exclusion manifest, so its Perseus
  scores are leakage-clean. The legacy full-AGDT backends have *seen* those sentences, so their
  Perseus-fold scores are an in-training upper bound. The PROIEL fold is clean for every
  pyaegean model (none trains on PROIEL).
"""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unicodedata
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..data import cache_dir, download_file

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from ..analysis.stats import BootstrapCI

__all__ = [
    "UDSentence",
    "UDToken",
    "agdt_ud_overlap",
    "bootstrap_ud",
    "evaluate_on_ud",
    "evaluate_by_genre",
    "load_conllu",
    "ud_path",
]

_CACHE_SUBDIR = "ud-grc"

# UD Ancient Greek treebanks, pinned for reproducibility (CC BY-NC-SA: Perseus 2.5, PROIEL 3.0
# — per each treebank's README; eval only).
_UD_REPO: dict[str, tuple[str, str]] = {
    "perseus": ("UD_Ancient_Greek-Perseus", "331ddef91411d0e6549744ee889e05549e6da77d"),
    "proiel": ("UD_Ancient_Greek-PROIEL", "a4ab8d436de97d4598d410d91ea20b4127d04a5f"),
}
# The two UD folds carry DIFFERENT Creative-Commons versions (each treebank's own README at the
# pinned commit): UD-Perseus is 2.5, UD-PROIEL is 3.0. Both are NonCommercial + ShareAlike, so
# both are evaluation-only, never bundled, never trained on — but the version differs, so it is
# recorded per treebank rather than blanket-stated.
_UD_LICENSE: dict[str, str] = {
    "perseus": "CC BY-NC-SA 2.5",
    "proiel": "CC BY-NC-SA 3.0",
}
_SPLITS = ("train", "dev", "test")

# AGDT (Perseus) TLG author-group id -> literary genre, for genre-sliced evaluation. The
# UD-Perseus sentence ids begin with the AGDT source filename, which begins with the TLG author
# id (e.g. "tlg0012.tlg001…@197" -> Homer). Genre boundaries are editorial (Hesiod is grouped
# with epic as didactic hexameter). Only ids that actually occur in a fold matter; the rest fall
# to "other". `evaluate_by_genre` reports the unmapped ids so this table can be audited/extended.
_AUTHOR_GENRE: dict[str, str] = {
    "tlg0012": "epic",     # Homer
    "tlg0013": "epic",     # Homeric Hymns (hexameter)
    "tlg0020": "epic",     # Hesiod (didactic hexameter)
    "tlg0085": "tragedy",  # Aeschylus
    "tlg0011": "tragedy",  # Sophocles
    "tlg0006": "tragedy",  # Euripides
    "tlg0019": "comedy",   # Aristophanes
    "tlg0016": "prose",    # Herodotus
    "tlg0003": "prose",    # Thucydides
    "tlg0059": "prose",    # Plato
    "tlg0032": "prose",    # Xenophon
    "tlg0007": "prose",    # Plutarch
    "tlg0008": "prose",    # Athenaeus (Deipnosophistae)
    "tlg0060": "prose",    # Diodorus Siculus
}


def _sent_genre(sent_id: str) -> tuple[str, str]:
    """(author id, genre) for a UD sentence id like ``tlg0012.tlg001.perseus-grc1.tb.xml@197``."""
    head = sent_id.rpartition("@")[0] or sent_id  # drop the "@197" sentence index
    author = head.split(".", 1)[0]
    return author, _AUTHOR_GENRE.get(author, "other")

# The official CoNLL 2018 shared-task evaluator (MPL 2.0), pinned by content hash.
_EVAL_URL = "https://universaldependencies.org/conll18/conll18_ud_eval.py"
_EVAL_SHA256 = "1072e02af00b1a56205b5e8216d51dee9b8944a104d80744afaccc78859fcb16"

_EXCLUSION_NAME = "agdt-ud-exclusion.json"


@dataclass(frozen=True, slots=True)
class UDToken:
    """One syntactic word from a CoNLL-U sentence (multiword ranges and empty nodes skipped)."""

    id: int
    form: str
    lemma: str
    upos: str
    xpos: str
    feats: str
    head: int
    deprel: str


@dataclass(frozen=True, slots=True)
class UDSentence:
    """One CoNLL-U sentence: its ``# sent_id``, raw ``# text`` (when present), and tokens."""

    sent_id: str
    text: str
    tokens: tuple[UDToken, ...]


def ud_path(treebank: str = "perseus", split: str = "test", *, download: bool = True) -> Path:
    """The cached path of a UD Ancient Greek fold, fetching it on first use.

    ``treebank`` is ``"perseus"`` or ``"proiel"``; ``split`` is ``"train"``/``"dev"``/
    ``"test"``. The data is CC BY-NC-SA (Perseus 2.5, PROIEL 3.0) — cached for evaluation
    only, never bundled."""
    repo, commit = _UD_REPO[treebank]
    if split not in _SPLITS:
        raise ValueError(f"split must be one of {_SPLITS}; got {split!r}")
    name = f"grc_{treebank}-ud-{split}.conllu"
    dest = cache_dir() / _CACHE_SUBDIR / name
    if download and not dest.exists():
        download_file(f"https://raw.githubusercontent.com/UniversalDependencies/{repo}/{commit}/{name}", dest)
    return dest


def load_conllu(source: Path | str) -> list[UDSentence]:
    """Parse a CoNLL-U file into `UDSentence` objects.

    Multiword-token ranges (``3-4``) and empty nodes (``3.1``) are skipped, so each
    sentence holds exactly the syntactic words the evaluator scores."""
    sentences: list[UDSentence] = []
    sent_id = text = ""
    tokens: list[UDToken] = []
    for raw in Path(source).read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            if tokens:
                sentences.append(UDSentence(sent_id, text, tuple(tokens)))
            sent_id = text = ""
            tokens = []
            continue
        if line.startswith("#"):
            if line.startswith("# sent_id"):
                sent_id = line.split("=", 1)[1].strip() if "=" in line else ""
            elif line.startswith("# text"):
                text = line.split("=", 1)[1].strip() if "=" in line else ""
            continue
        cols = line.split("\t")
        if len(cols) < 8 or not cols[0].isdigit():  # skip MWT ranges + empty nodes
            continue
        tokens.append(
            UDToken(
                id=int(cols[0]), form=cols[1], lemma=cols[2], upos=cols[3], xpos=cols[4],
                feats=cols[5], head=int(cols[6]) if cols[6].isdigit() else 0, deprel=cols[7],
            )
        )
    if tokens:
        sentences.append(UDSentence(sent_id, text, tuple(tokens)))
    return sentences


# --- running the pipeline over gold tokens -------------------------------------


def _tag_forms(forms: list[str]) -> list[str]:
    """UPOS per gold token, mirroring `aegean.greek.pos_tags`'s cascade without
    re-tokenizing: closed-class lexicon → treebank lookup → context tagger → heuristic."""
    from . import tagger, treebank
    from .pos import _LEXICON, _norm, pos_tag

    context: list[str] | None = None
    if tagger.active() is not None:
        context = tagger.tag_pos(forms)
    lex = treebank.active()
    out: list[str] = []
    for i, form in enumerate(forms):
        if not any(ch.isalpha() for ch in form):
            out.append(pos_tag(form))  # PUNCT / NUM
        elif _norm(form) in _LEXICON:
            out.append(_LEXICON[_norm(form)])
        elif lex is not None and lex.pos(form) is not None:
            out.append(lex.pos(form) or "X")
        elif context is not None:
            out.append(context[i])
        else:
            out.append(pos_tag(form))
    return out


def pipeline_conllu(sentences: list[UDSentence], *, parse: bool = False) -> str:
    """Run the active pyaegean pipeline over gold-tokenized sentences, emitting CoNLL-U.

    FORM is the gold token (gold tokenization — see the module docstring); LEMMA and UPOS
    come from the active cascade (whatever backends are switched on); HEAD/DEPREL come
    from `aegean.greek.parse` when ``parse=True`` (requires `use_parser`), else a flat
    placeholder that makes UAS/LAS meaningless (the caller omits them). XPOS/FEATS are
    not emitted by the current stack (``_``)."""
    from . import joint
    from .lemmatize import lemmatize

    if parse:
        from .syntax import parse as parse_tree

    lines: list[str] = []
    for sent in sentences:
        forms = [t.form for t in sent.tokens]
        model = joint.active()
        if model is not None:  # the neural pipeline: one encoder pass fills every column
            ana = model.analyze(forms)
            if sent.sent_id:
                lines.append(f"# sent_id = {sent.sent_id}")
            if sent.text:
                lines.append(f"# text = {sent.text}")
            for i in range(len(forms)):
                lines.append("	".join((
                    str(i + 1), forms[i], ana.lemma[i], ana.upos[i], ana.xpos[i],
                    ana.feats[i], str(ana.head[i]), ana.deprel[i], "_", "_")))
            lines.append("")
            continue
        lemmas = [lemmatize(f) for f in forms]
        tags = _tag_forms(forms)
        # Placeholder when not parsing: a valid single-root flat tree (the evaluator
        # rejects multi-root sentences); UAS/LAS are meaningless and reported as None.
        heads = [0] + [1] * (len(forms) - 1)
        rels = ["root"] + ["dep"] * (len(forms) - 1)
        if parse:
            tree = parse_tree(forms)
            for tok in tree.tokens:
                heads[tok.id - 1] = tok.head
                rels[tok.id - 1] = tok.relation
            # The evaluator requires exactly one root per sentence; the baseline arc-eager
            # parser can leave several tokens on the root. Standard normalization: keep the
            # first root, re-attach the rest to it (counted as-is by UAS — no gold peeking).
            roots = [i for i, h in enumerate(heads) if h == 0]
            if not roots:
                heads[0] = 0
                rels[0] = "root"
            else:
                for i in roots[1:]:
                    heads[i] = roots[0] + 1
        if sent.sent_id:
            lines.append(f"# sent_id = {sent.sent_id}")
        if sent.text:
            lines.append(f"# text = {sent.text}")
        for i, form in enumerate(forms):
            lines.append(
                "\t".join(
                    (str(i + 1), form, lemmas[i] or form, tags[i], "_", "_",
                     str(heads[i]), rels[i], "_", "_")
                )
            )
        lines.append("")
    return "\n".join(lines) + "\n"


# --- the official evaluator -----------------------------------------------------


def _eval_module() -> Any:
    """Import the official ``conll18_ud_eval`` from the cache (fetched once, sha256-pinned)."""
    dest = cache_dir() / _CACHE_SUBDIR / "conll18_ud_eval.py"
    if not dest.exists():
        download_file(_EVAL_URL, dest, sha256=_EVAL_SHA256)
    spec = importlib.util.spec_from_file_location("conll18_ud_eval", dest)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def evaluate_on_ud(
    treebank: str = "perseus",
    split: str = "test",
    *,
    source: Path | str | None = None,
    parse: bool | None = None,
) -> dict[str, Any]:
    """Score the active pipeline on a UD Ancient Greek fold with the official evaluator.

    Runs over the fold's gold tokens (gold-tokenization protocol), emits CoNLL-U, and
    scores it against the gold file with ``conll18_ud_eval``. Activate the backends you
    want measured first (`use_treebank`, `use_tagger`, `use_lemmatizer`,
    `use_neural_lemmatizer`, `use_parser`). ``parse`` defaults to whether the parser
    is active; with ``parse=False`` UAS/LAS are returned as ``None``.

    Returns ``{"upos", "lemma", "uas", "las", "n_words", "n_sentences", "treebank",
    "split", "parsed"}`` — accuracies in [0, 1]. **Read the module docstring's leakage
    caveat before quoting the Perseus fold for an AGDT-trained model.**"""
    gold_path = Path(source) if source is not None else ud_path(treebank, split)
    sentences = load_conllu(gold_path)
    if parse is None:
        from . import joint, syntax

        parse = joint.active() is not None or syntax.active() is not None
    system = pipeline_conllu(sentences, parse=parse)

    ev = _eval_module()
    with tempfile.TemporaryDirectory() as td:
        sys_path = Path(td) / "system.conllu"
        sys_path.write_text(system, encoding="utf-8")
        with open(gold_path, encoding="utf-8") as gf:
            gold_ud = ev.load_conllu(gf)
        with open(sys_path, encoding="utf-8") as sf:
            system_ud = ev.load_conllu(sf)
    scores = ev.evaluate(gold_ud, system_ud)
    return {
        "treebank": treebank,
        "split": split,
        "parsed": parse,
        "upos": scores["UPOS"].f1,
        "xpos": scores["XPOS"].f1,
        "ufeats": scores["UFeats"].f1,
        "lemma": scores["Lemmas"].f1,
        "uas": scores["UAS"].f1 if parse else None,
        "las": scores["LAS"].f1 if parse else None,
        "clas": scores["CLAS"].f1 if parse else None,
        "n_words": len([t for s in sentences for t in s.tokens]),
        "n_sentences": len(sentences),
    }


# --- bootstrap confidence intervals over the fold's sentences --------------------

_METRIC_KEY = {
    "upos": "UPOS",
    "xpos": "XPOS",
    "ufeats": "UFeats",
    "lemma": "Lemmas",
    "uas": "UAS",
    "las": "LAS",
    "clas": "CLAS",
}


def _split_conllu_sentences(text: str) -> list[str]:
    """Split a CoNLL-U string into sentence blocks, each terminated by a blank line."""
    blocks: list[str] = []
    cur: list[str] = []
    for line in text.splitlines():
        if line.strip():
            cur.append(line)
        elif cur:
            blocks.append("\n".join(cur) + "\n\n")
            cur = []
    if cur:
        blocks.append("\n".join(cur) + "\n\n")
    return blocks


def _score_conllu_text(
    ev: Any, gold_text: str, system_text: str, metrics: Sequence[str]
) -> dict[str, float]:
    """Score one aligned (gold, system) CoNLL-U pair with the official evaluator."""
    import io

    gold_ud = ev.load_conllu(io.StringIO(gold_text))
    system_ud = ev.load_conllu(io.StringIO(system_text))
    scores = ev.evaluate(gold_ud, system_ud)
    return {m: float(scores[_METRIC_KEY[m]].f1) for m in metrics}


def _bootstrap_conllu(
    gold_text: str,
    system_text: str,
    score: Callable[[str, str], dict[str, float]],
    *,
    n_resamples: int = 999,
    level: float = 0.95,
    seed: int = 0,
) -> dict[str, BootstrapCI]:
    """Bootstrap CIs over the sentences of an aligned gold/system CoNLL-U pair.

    ``score(gold, system)`` scores one CoNLL-U pair to ``{metric: value}``. The two texts must
    be sentence-aligned (guaranteed by the gold-tokenization protocol). The resampling unit is
    the **sentence**; ``score`` is injected so the resampling is testable without the evaluator.
    """
    from ..analysis.stats import bootstrap_dict_seq

    gold_blocks = _split_conllu_sentences(gold_text)
    sys_blocks = _split_conllu_sentences(system_text)
    if len(gold_blocks) != len(sys_blocks):
        raise ValueError(
            f"gold/system sentence-count mismatch: {len(gold_blocks)} vs {len(sys_blocks)}"
        )
    pairs = list(zip(gold_blocks, sys_blocks, strict=True))

    def stat(sample: Sequence[tuple[str, str]]) -> dict[str, float]:
        return score("".join(g for g, _ in sample), "".join(s for _, s in sample))

    return bootstrap_dict_seq(pairs, stat, n_resamples=n_resamples, level=level, seed=seed)


def bootstrap_ud(
    treebank: str = "perseus",
    split: str = "test",
    *,
    metrics: Sequence[str] = ("upos", "xpos", "ufeats", "lemma", "uas", "las"),
    n_resamples: int = 999,
    level: float = 0.95,
    seed: int = 0,
    source: Path | str | None = None,
    parse: bool | None = None,
) -> dict[str, BootstrapCI]:
    """Percentile bootstrap CIs for :func:`evaluate_on_ud`'s metrics, over the fold's sentences.

    The active pipeline runs **once** over the fold; each of ``n_resamples`` draws re-scores a
    sentence resample (with replacement) with the official evaluator. Sentences are the
    resampling unit — tokens within a sentence are not independent. Activate the same backends
    you would for :func:`evaluate_on_ud`; with no parser active, ``uas``/``las`` are dropped.
    The band is sampling variability *given this fold* — read the module docstring's leakage
    caveat before quoting the Perseus fold for an AGDT-trained model.
    """
    gold_path = Path(source) if source is not None else ud_path(treebank, split)
    sentences = load_conllu(gold_path)
    if parse is None:
        from . import joint, syntax

        parse = joint.active() is not None or syntax.active() is not None
    system_text = pipeline_conllu(sentences, parse=parse)
    gold_text = gold_path.read_text(encoding="utf-8")
    wanted = [m for m in metrics if parse or m not in ("uas", "las")]
    ev = _eval_module()
    return _bootstrap_conllu(
        gold_text,
        system_text,
        lambda g, s: _score_conllu_text(ev, g, s, wanted),
        n_resamples=n_resamples,
        level=level,
        seed=seed,
    )


def evaluate_by_genre(
    treebank: str = "perseus",
    split: str = "test",
    *,
    metrics: Sequence[str] = ("upos", "lemma", "uas", "las"),
    bootstrap: bool = True,
    n_resamples: int = 999,
    level: float = 0.95,
    seed: int = 0,
    source: Path | str | None = None,
    parse: bool | None = None,
    min_sentences: int = 20,
) -> dict[str, dict[str, Any]]:
    """Score the active pipeline on a UD fold, sliced by literary genre.

    Each sentence is bucketed by its ``sent_id`` author (a TLG id, mapped through
    ``_AUTHOR_GENRE`` to epic / tragedy / comedy / prose / other). The pipeline runs **once**
    over the whole fold; each genre is then scored with the official evaluator (and, when
    ``bootstrap``, given a percentile CI). Returns ``{genre: {"n_sentences", "n_words",
    "authors", "thin" (True under ``min_sentences``), <metric>: value or BootstrapCI}}`` plus an
    ``"_unmapped"`` list of author ids not in the table (the built-in discovery step: run this
    before pinning any numbers, and extend ``_AUTHOR_GENRE`` from it).

    This is meaningful only for the leakage-clean neural model on Perseus: the offline baseline
    has seen the Perseus test sentences (see the module leakage caveat), so do not publish genre
    slices for it. ``uas``/``las`` are dropped when no parser is active."""
    gold_path = Path(source) if source is not None else ud_path(treebank, split)
    sentences = load_conllu(gold_path)
    if parse is None:
        from . import joint, syntax

        parse = joint.active() is not None or syntax.active() is not None
    wanted = [m for m in metrics if parse or m not in ("uas", "las")]
    system_text = pipeline_conllu(sentences, parse=parse)
    gold_blocks = _split_conllu_sentences(gold_path.read_text(encoding="utf-8"))
    sys_blocks = _split_conllu_sentences(system_text)
    if not (len(gold_blocks) == len(sys_blocks) == len(sentences)):
        raise ValueError(
            f"gold/system/sentence count mismatch: {len(gold_blocks)}/{len(sys_blocks)}/"
            f"{len(sentences)}"
        )

    buckets: dict[str, list[tuple[str, str]]] = {}
    authors: dict[str, set[str]] = {}
    unmapped: set[str] = set()
    for sent, g, s in zip(sentences, gold_blocks, sys_blocks):
        author, genre = _sent_genre(sent.sent_id)
        buckets.setdefault(genre, []).append((g, s))
        authors.setdefault(genre, set()).add(author)
        if genre == "other":
            unmapped.add(author)

    ev = _eval_module()
    out: dict[str, dict[str, Any]] = {}
    for genre, pairs in buckets.items():
        gold_text = "".join(g for g, _ in pairs)
        sys_text = "".join(s for _, s in pairs)
        n_words = sum(1 for line in gold_text.splitlines() if line[:1].isdigit() and "-" not in line.split("\t", 1)[0])
        entry: dict[str, Any] = {
            "n_sentences": len(pairs),
            "n_words": n_words,
            "authors": sorted(authors[genre]),
            "thin": len(pairs) < min_sentences,
        }
        if bootstrap:
            entry.update(
                _bootstrap_conllu(
                    gold_text, sys_text,
                    lambda gg, ss: _score_conllu_text(ev, gg, ss, wanted),
                    n_resamples=n_resamples, level=level, seed=seed,
                )
            )
        else:
            entry.update(_score_conllu_text(ev, gold_text, sys_text, wanted))
        out[genre] = entry
    out["_unmapped"] = {"authors": sorted(unmapped)}  # type: ignore[dict-item]
    return out


# --- the leakage-exclusion manifest ----------------------------------------------


def _agdt_sentence_forms(path: Path) -> dict[str, tuple[str, ...]]:
    """sentence id → NFC form sequence for one AGDT ``.tb.xml`` file."""
    out: dict[str, tuple[str, ...]] = {}
    cur: list[str] = []
    sid = ""
    for _event, elem in ET.iterparse(str(path), events=("start", "end")):
        tag = elem.tag.rsplit("}", 1)[-1]
        if _event == "start" and tag == "sentence":
            sid = elem.get("id") or ""
            cur = []
        elif _event == "end":
            if tag == "word":
                form = elem.get("form")
                if form:
                    cur.append(unicodedata.normalize("NFC", form))
            elif tag == "sentence":
                if sid:
                    out[sid] = tuple(cur)
                elem.clear()
    return out


def agdt_ud_overlap(
    *,
    splits: tuple[str, ...] = ("dev", "test"),
    source: Path | str | None = None,
    agdt_source: Path | str | None = None,
    verify: bool = True,
    write: bool = True,
) -> dict[str, Any]:
    """Build the AGDT ↔ UD-Perseus leakage-exclusion manifest.

    UD Perseus sentence ids are ``<agdt-file>@<sentence-id>`` — direct references into the
    AGDT source pyaegean trains on. This collects every AGDT sentence appearing in the
    given UD ``splits`` (default: dev + test, the folds that must stay unseen), verifies
    the reference by comparing NFC form sequences against the actual AGDT files, caches
    the manifest as JSON, and returns it. **Every Stage A+ training split must exclude
    these sentences** — see ``docs/benchmarks.md``.

    ``source`` overrides the UD fold path(s) and ``agdt_source`` the AGDT directory (used
    by offline tests); with defaults, both fetch to the cache on first use."""
    _repo, commit = _UD_REPO["perseus"]
    files: dict[str, set[str]] = {}
    ud_forms: dict[tuple[str, str], tuple[str, ...]] = {}
    for split in splits:
        path = Path(source) if source is not None else ud_path("perseus", split)
        for sent in load_conllu(path):
            if "@" not in sent.sent_id:
                continue
            fname, _, sid = sent.sent_id.rpartition("@")
            files.setdefault(fname, set()).add(sid)
            ud_forms[(fname, sid)] = tuple(
                unicodedata.normalize("NFC", t.form) for t in sent.tokens
            )

    checked = identical = 0
    if verify:
        from .treebank import agdt_dir

        base = Path(agdt_source) if agdt_source is not None else agdt_dir(download=True)
        for fname, ids in files.items():
            fp = base / fname
            if not fp.exists():
                continue
            gold = _agdt_sentence_forms(fp)
            for sid in ids:
                if sid in gold:
                    checked += 1
                    identical += int(gold[sid] == ud_forms[(fname, sid)])

    from .. import __version__  # lazy: aegean/__init__ imports this module

    manifest: dict[str, Any] = {
        "purpose": "AGDT sentences that appear in UD-Perseus folds; exclude from training",
        "ud_treebank": "UD_Ancient_Greek-Perseus",
        "ud_commit": commit,
        "splits": list(splits),
        "pyaegean_version": __version__,
        "files": {fname: sorted(ids, key=lambda s: (len(s), s)) for fname, ids in sorted(files.items())},
        "n_sentences": sum(len(ids) for ids in files.values()),
        "verified": {"checked": checked, "form_identical": identical} if verify else None,
    }
    if write:
        dest = cache_dir() / _CACHE_SUBDIR / _EXCLUSION_NAME
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    return manifest
