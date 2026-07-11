"""Build the PapyGreek documentary-Koine DEV fold (repo-only; experiment data only).

This is the companion experiment set to ``scripts/build_papygreek_fold.py`` (the pinned
**test** fold, ``papygreek-fold``). The test fold is measured once per shipped change and
nothing is ever fitted, tuned, or model-selected against it. This dev asset is the
document-disjoint experiment material used to rank levers and catch regressions **without
touching the pinned test fold**.

**Document-level disjointness is the invariant.** The test fold keeps the "ok" (fully
annotated, cleanly readable, leakage-clean) sentences of the PapyGreek ``documentary/``
corpus; a document that contributed at least one such sentence is a *fold document*. Dev is
built **only** from the documents that contributed ZERO sentences to the fold (re-derived
here by re-running the exact fold-selection logic of ``build_papygreek_fold``, and
cross-checked against the doc ids present in the pinned test fold's CoNLL-U). Those non-fold
documents have, by construction, no clean parseable non-leaked sentence — their material is
the *artificial* (elliptic/ellipsis node) and *partial* (a token lacks head/relation)
sentences the fold build discards.

Two tracks, one logical asset (``papygreek-dev-v1``), two gzipped CoNLL-U files:

  * **tagging track** (``papygreek-dev-tagging.conllu.gz``) — the annotated *surface* tokens
    of the non-fold artificial + partial sentences (artificial nodes dropped; a surface token
    is kept iff it carries ``form``/``postag``/``lemma`` and reduces to clean Greek). Scores
    UPOS / XPOS / UFeats / lemma over gold tokens (no head/relation needed). Used to rank the
    coordinator / common-gender / ``_``-normalization / lemma-OOV levers.

  * **parse track** (``papygreek-dev-parse.conllu.gz``) — the non-fold artificial sentences
    with **exactly one** artificial node whose real tokens are fully parse-annotated, put
    through the empty-node reattachment below. Scores UAS / LAS. Thinner: treat as
    directional and gate parse levers additionally on the literary dev folds.

**Empty-node reattachment (deterministic; parse track).** For a sentence with exactly one
artificial node ``A`` (a surface-less reconstructed token, e.g. the elided verb of an
epistolary opening): every real token whose ``head_reg`` is ``A``'s id is re-attached to
``A``'s own ``head_reg`` (``A``'s parent — a real token id, or ``0`` for the root), then
``A`` is dropped. This is the standard *basic-tree projection* of an empty node — the
dependencies routed through the empty node collapse to its parent. When ``A`` was the
sentence root (head ``0``), its promoted children become roots and the shared AGDT->UD
converter's single-root normalization keeps the first and attaches the rest as ``parataxis``.
It is a pure transform of the gold tree, not a judgement call.

**Leakage refilter (mandatory).** The fold build only leak-checks its "ok" sentences; the
artificial/partial dev candidates are leak-checked here with the *same* NFC form-tuple
exclusion (full + punctuation-stripped, vs ``training/data/full-{train,dev}.jsonl``). Every
excluded sentence is counted in the manifest.

Everything reuses ``build_papygreek_fold``'s conventions verbatim (same pinned PapyGreek
commit, the same ``sentence_to_conllu`` AGDT->UD converter, the same ``clean_lemma`` incl.
the numeral fix, the same apparatus stripper and reading test), so the dev tokens are scored
byte-for-byte the way the fold tokens are.

Output (``--out``): ``papygreek-dev-v1/`` holding the two ``.conllu`` + ``.conllu.gz`` files
and ``papygreek-dev-manifest.json`` (source commit, doc-set accounting, per-track counts,
full exclusion accounting, reattachment rule, per-file sha256). Prints each gz sha256 for the
``_REMOTE`` DataSpec pins.

Usage:
    python scripts/build_papygreek_dev.py [--repo DIR] [--out DIR]
                                          [--training-data training/data]
                                          [--fold-conllu papygreek-test.conllu]
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
import tempfile
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Reuse the pinned-fold build verbatim (same commit, converter, cleaners, leakage keys).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_papygreek_fold import (  # noqa: E402
    LICENSE,
    REPO_COMMIT,
    _clone,
    is_clean_reading,
    is_leaked,
    reg_words,
    sentence_status,
    sentence_to_conllu,
    strip_apparatus,
    training_form_keys,
)


def tagging_annotated(w: dict[str, Any]) -> bool:
    """True when a surface (non-artificial) token can be scored for UPOS/XPOS/UFeats/lemma:
    it carries ``form``/``postag``/``lemma`` and reduces to a clean reading (punctuation may
    reduce to any non-empty mark; a word must reduce to genuine Greek)."""
    if not (w["form_reg"] and w["postag_reg"] and w["lemma_reg"]):
        return False
    s = strip_apparatus(w["form_reg"])
    if (w["postag_reg"] or "")[:1] == "u":  # punctuation token
        return bool(s)
    return is_clean_reading(s)


def _is_artificial(w: dict[str, Any]) -> bool:
    return bool(w["artificial"] or w["insertion_id"])


def _fully_parse_annotated(w: dict[str, Any]) -> bool:
    """A real token usable in the parse track: form/head/relation/postag/lemma all present
    and the surface form reduces to a clean reading (or, for punctuation, is non-empty)."""
    if not (
        w["form_reg"] and w["head_reg"] and w["relation_reg"]
        and w["postag_reg"] and w["lemma_reg"]
    ):
        return False
    s = strip_apparatus(w["form_reg"])
    if (w["postag_reg"] or "")[:1] == "u":
        return bool(s)
    return is_clean_reading(s)


@dataclass
class SentRec:
    stem: str
    sid: str
    words: list[dict[str, Any]]
    status: str
    leaked: bool


def scan(docdir: Path, keys: set[tuple[str, ...]]) -> list[SentRec]:
    """Every ``<sentence>`` of the documentary corpus with its fold-selection verdict.

    ``status`` is `build_papygreek_fold.sentence_status`; ``leaked`` is the NFC form-tuple
    leakage verdict, computed for "ok" sentences (the ones the fold build would keep) so the
    fold-document set can be re-derived exactly."""
    recs: list[SentRec] = []
    for fp in sorted(docdir.rglob("*.xml")):
        stem = fp.name[:-4] if fp.name.endswith(".xml") else fp.name
        root = ET.parse(str(fp)).getroot()
        for sent in root.iter("sentence"):
            words = reg_words(sent)
            status = sentence_status(words)
            leaked = False
            if status == "ok":
                _, forms = sentence_to_conllu(f"x:{stem}@{sent.get('id')}", words)
                leaked = is_leaked(forms, keys)
            recs.append(SentRec(stem, sent.get("id") or "", words, status, leaked))
    return recs


def fold_doc_ids_from_conllu(path: Path) -> set[str]:
    """The document stems present in a built fold's CoNLL-U (from ``# sent_id =
    papygreek:<stem>@<sid>``) — the authoritative fold-document set to be disjoint from."""
    stems: set[str] = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        if raw.startswith("# sent_id"):
            sid = raw.split("=", 1)[1].strip()
            if sid.startswith("papygreek:") and "@" in sid:
                stems.add(sid[len("papygreek:"):].rsplit("@", 1)[0])
    return stems


def build_tagging(nonfold: list[SentRec], keys: set[tuple[str, ...]]) -> tuple[list[str], dict[str, Any]]:
    """The tagging track: annotated surface tokens of non-fold artificial + partial sentences."""
    blocks: list[str] = []
    n_tokens = 0
    excl: Counter[str] = Counter()
    src_sent: Counter[str] = Counter()
    for r in nonfold:
        if r.status not in ("artificial", "partial"):
            continue
        src_sent[r.status] += 1
        annotated = [w for w in r.words if not _is_artificial(w) and tagging_annotated(w)]
        if not annotated:
            excl["no_annotated_token"] += 1
            continue
        block, forms = sentence_to_conllu(f"papygreek-dev:{r.stem}@{r.sid}", annotated)
        if is_leaked(forms, keys):
            excl["leaked"] += 1
            continue
        blocks.append(block)
        n_tokens += len(forms)
    stats = {
        "sentences_kept": len(blocks),
        "tokens_kept": n_tokens,
        "source_sentences": dict(sorted(src_sent.items())),
        "excluded": dict(sorted(excl.items())),
    }
    return blocks, stats


def _reattach_single_artificial(words: list[dict[str, Any]]) -> list[dict[str, Any]] | None:
    """Basic-tree projection for a sentence with exactly one artificial node.

    Returns the real tokens (artificial node dropped) with each child of the artificial node
    re-attached to the artificial node's own head, or ``None`` if the sentence does not have
    exactly one artificial node or a real token is not fully parse-annotated."""
    arts = [w for w in words if _is_artificial(w)]
    if len(arts) != 1:
        return None
    art = arts[0]
    a_id = art["id"]
    a_head = art["head_reg"] or "0"  # the artificial node's parent (real id, or 0 = root)
    real = [w for w in words if not _is_artificial(w)]
    if not real or not all(_fully_parse_annotated(w) for w in real):
        return None
    out: list[dict[str, Any]] = []
    for w in real:
        w2 = dict(w)
        if w2["head_reg"] == a_id:  # a child of the elided node → promote to its parent
            w2["head_reg"] = a_head
        out.append(w2)
    return out


def build_parse(nonfold: list[SentRec], keys: set[tuple[str, ...]]) -> tuple[list[str], dict[str, Any]]:
    """The parse track: non-fold artificial sentences with one artificial node, reattached."""
    blocks: list[str] = []
    n_tokens = 0
    excl: Counter[str] = Counter()
    n_artificial = 0
    for r in nonfold:
        if r.status != "artificial":
            continue
        n_artificial += 1
        real = _reattach_single_artificial(r.words)
        if real is None:
            arts = [w for w in r.words if _is_artificial(w)]
            excl["multi_artificial" if len(arts) != 1 else "real_token_not_parse_annotated"] += 1
            continue
        block, forms = sentence_to_conllu(f"papygreek-dev:{r.stem}@{r.sid}", real)
        if is_leaked(forms, keys):
            excl["leaked"] += 1
            continue
        blocks.append(block)
        n_tokens += len(forms)
    stats = {
        "sentences_kept": len(blocks),
        "tokens_kept": n_tokens,
        "source_artificial_sentences": n_artificial,
        "excluded": dict(sorted(excl.items())),
    }
    return blocks, stats


def _conllu(blocks: list[str]) -> str:
    """Join sentence blocks into a CoNLL-U file (blank line between, trailing empty line)."""
    return ("\n".join(blocks) + "\n") if blocks else ""


def _write_gz(text: str, gz_path: Path) -> str:
    """Write ``text`` gzipped reproducibly (mtime=0, no filename) and return its sha256."""
    raw = text.encode("utf-8")
    with open(gz_path, "wb") as fh, gzip.GzipFile(
        filename="", mode="wb", fileobj=fh, mtime=0, compresslevel=9
    ) as gz:
        gz.write(raw)
    return hashlib.sha256(gz_path.read_bytes()).hexdigest()


def build(repo: Path, training_dir: Path, fold_conllu: Path | None) -> tuple[str, str, dict[str, Any]]:
    docdir = repo / "documentary"
    if not docdir.is_dir():
        raise SystemExit(f"no documentary/ dir under {repo}")
    keys = training_form_keys(training_dir)
    recs = scan(docdir, keys)

    all_docs = {r.stem for r in recs}
    fold_docs = {r.stem for r in recs if r.status == "ok" and not r.leaked}
    nonfold_docs = all_docs - fold_docs
    nonfold = [r for r in recs if r.stem in nonfold_docs]

    # Cross-check the re-derived fold-document set against the pinned test fold's own doc ids:
    # every document present in the pinned fold MUST be classified as a fold document here, so
    # the dev set is provably disjoint from the actual pinned fold.
    crosscheck: dict[str, Any] = {"performed": False}
    if fold_conllu is not None and fold_conllu.exists():
        pinned = fold_doc_ids_from_conllu(fold_conllu)
        missing = sorted(pinned - fold_docs)
        overlap = sorted(pinned & nonfold_docs)
        crosscheck = {
            "performed": True,
            "fold_conllu": fold_conllu.name,
            "pinned_fold_documents": len(pinned),
            "pinned_not_reclassified_as_fold": missing,
            "pinned_in_nonfold_dev_pool": overlap,
        }
        if missing or overlap:
            raise SystemExit(
                "document-disjointness FAILED: the pinned fold shares documents with the dev "
                f"pool (missing={missing[:5]}, overlap={overlap[:5]})"
            )

    whole_status: Counter[str] = Counter()
    for r in recs:
        whole_status["leaked" if (r.status == "ok" and r.leaked) else r.status] += 1

    tag_blocks, tag_stats = build_tagging(nonfold, keys)
    parse_blocks, parse_stats = build_parse(nonfold, keys)
    tag_text = _conllu(tag_blocks)
    parse_text = _conllu(parse_blocks)

    manifest: dict[str, Any] = {
        "purpose": "documentary-Koine (PapyGreek) DEV fold; experiment/lever-ranking only, "
                   "document-disjoint from the pinned papygreek-fold test set; never a "
                   "published number, never fitted against the test fold",
        "source_repo": "github.com/ezhenrik/papygreek-treebanks",
        "source_commit": REPO_COMMIT,
        "license": LICENSE,
        "annotation_scheme": "AGDT Guidelines 2.0 (reg layer)",
        "converter": "training/agdt_ud_deps.convert_tree + agdt_ud.{copular_flags,"
                     "upos_from_xpos,feats_from_xpos} (shared with build_papygreek_fold)",
        "leakage_reference": "training/data/full-{train,dev}.jsonl (AGDT+Gorman+Pedalion); "
                             "NFC form-tuple exclusion (full + punct-stripped)",
        "document_sets": {
            "documents_in_source": len(all_docs),
            "fold_documents": len(fold_docs),
            "nonfold_documents": len(nonfold_docs),
            "derivation": "fold document = contributed >=1 ok & non-leaked sentence "
                          "(re-run of build_papygreek_fold selection); dev = the rest",
            "crosscheck_vs_pinned_fold": crosscheck,
        },
        "whole_corpus_sentence_status": dict(sorted(whole_status.items())),
        "reattachment_rule": "parse track: the single artificial (elliptic) node's surface "
                             "children re-attach to the artificial node's own head; the node "
                             "is dropped; convert_tree normalizes to a single root",
        "tagging_track": {
            "file": "papygreek-dev-tagging.conllu.gz",
            "scores": "UPOS/XPOS/UFeats/lemma over gold tokens (parse=False)",
            **tag_stats,
        },
        "parse_track": {
            "file": "papygreek-dev-parse.conllu.gz",
            "scores": "UAS/LAS (+ UPOS/XPOS/UFeats/lemma) over gold tokens (parse=True)",
            **parse_stats,
        },
        "nonfold_documents": sorted(nonfold_docs),
    }
    return tag_text, parse_text, manifest


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", default=None,
                    help="existing checkout of the PapyGreek repo (else clone the pinned commit)")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / "training" / "data"),
                    help="output directory (a papygreek-dev-v1/ subdir is created under it)")
    ap.add_argument("--training-data",
                    default=str(Path(__file__).resolve().parent.parent / "training" / "data"),
                    help="dir holding full-train.jsonl / full-dev.jsonl for the leakage check")
    ap.add_argument("--fold-conllu", default=None,
                    help="the pinned test fold's papygreek-test.conllu, for the disjointness "
                         "cross-check (strongly recommended)")
    args = ap.parse_args()

    tmp: tempfile.TemporaryDirectory[str] | None = None
    if args.repo:
        repo = Path(args.repo)
    else:
        tmp = tempfile.TemporaryDirectory()
        repo = _clone(Path(tmp.name) / "papygreek-treebanks")
    try:
        fold_conllu = Path(args.fold_conllu) if args.fold_conllu else None
        tag_text, parse_text, manifest = build(repo, Path(args.training_data), fold_conllu)
    finally:
        if tmp is not None:
            tmp.cleanup()

    out = Path(args.out) / "papygreek-dev-v1"
    out.mkdir(parents=True, exist_ok=True)
    tag_conllu = out / "papygreek-dev-tagging.conllu"
    parse_conllu = out / "papygreek-dev-parse.conllu"
    tag_gz = out / "papygreek-dev-tagging.conllu.gz"
    parse_gz = out / "papygreek-dev-parse.conllu.gz"
    tag_conllu.write_text(tag_text, encoding="utf-8")
    parse_conllu.write_text(parse_text, encoding="utf-8")
    tag_sha = _write_gz(tag_text, tag_gz)
    parse_sha = _write_gz(parse_text, parse_gz)
    manifest["tagging_track"]["asset_sha256"] = tag_sha
    manifest["tagging_track"]["asset_bytes"] = tag_gz.stat().st_size
    manifest["parse_track"]["asset_sha256"] = parse_sha
    manifest["parse_track"]["asset_bytes"] = parse_gz.stat().st_size
    manifest_path = out / "papygreek-dev-manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")

    summary = {k: v for k, v in manifest.items() if k != "nonfold_documents"}
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    print(f"\nwrote {tag_conllu}")
    print(f"wrote {tag_gz}  ({tag_gz.stat().st_size:,} bytes)  sha256={tag_sha}")
    print(f"wrote {parse_conllu}")
    print(f"wrote {parse_gz}  ({parse_gz.stat().st_size:,} bytes)  sha256={parse_sha}")
    print(f"wrote {manifest_path}")


if __name__ == "__main__":
    main()
