"""UD (CoNLL-U) evaluation harness — pyaegean on the field's standard benchmark.

`aegean.greek.heldout` measures generalization *within* the AGDT under pyaegean's own
protocol, and `aegean.greek.proiel` measures it on out-of-AGDT text. This module measures
the pipeline on the **Universal Dependencies** Ancient Greek test folds with the **official
CoNLL 2018 shared-task evaluator** — the protocol behind the published cross-tool numbers
(see ``docs/benchmarks.md``) — and builds the **leakage-exclusion manifest** that every
future trained model must honour.

Data: ``UD_Ancient_Greek-Perseus`` / ``UD_Ancient_Greek-PROIEL``, pinned to commits,
licensed **CC BY-NC-SA 3.0** — fetched to the cache for **evaluation only**, never bundled
and never trained on (the PROIEL handling). The evaluator (``conll18_ud_eval.py``, Mozilla
Public License 2.0) is fetched to the cache pinned by sha256 and imported from there.

Protocol (spelled out in ``docs/benchmarks.md``):

- **Gold tokenization.** The pipeline runs over each fold's gold FORM column, so scores
  measure tagging/lemma/parsing quality, not tokenizer agreement.
- **No tagset collapsing.** UPOS and lemmas are scored exactly as emitted (unlike
  `evaluate_on_proiel`, which reconciles tagsets) — convention gaps count against us.
- **DEPREL.** pyaegean's parser emits AGDT/Prague labels, not UD relations, so LAS against
  UD gold is not meaningful for the current stack; **UAS** (unlabeled) is comparable.
- **Leakage caveat.** UD Perseus is converted *from* the AGDT: its sentence ids point
  straight at AGDT files (``tlg0008….tb.xml@197``). Models trained on the full AGDT — the
  current production models — have therefore *seen* the UD-Perseus test sentences, and
  their Perseus-fold scores are an in-training upper bound. `agdt_ud_overlap` builds
  the exclusion manifest that training splits use to remove exactly this overlap. The
  PROIEL fold is clean for pyaegean (no pyaegean model trains on PROIEL).
"""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unicodedata
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..data import cache_dir, download_file

__all__ = ["UDSentence", "UDToken", "agdt_ud_overlap", "evaluate_on_ud", "load_conllu", "ud_path"]

_CACHE_SUBDIR = "ud-grc"

# UD Ancient Greek treebanks, pinned for reproducibility (CC BY-NC-SA 3.0 — eval only).
_UD_REPO: dict[str, tuple[str, str]] = {
    "perseus": ("UD_Ancient_Greek-Perseus", "331ddef91411d0e6549744ee889e05549e6da77d"),
    "proiel": ("UD_Ancient_Greek-PROIEL", "a4ab8d436de97d4598d410d91ea20b4127d04a5f"),
}
_SPLITS = ("train", "dev", "test")

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
    ``"test"``. The data is CC BY-NC-SA 3.0 — cached for evaluation only, never bundled."""
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
