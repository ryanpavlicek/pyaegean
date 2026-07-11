"""Build the PapyGreek documentary-Koine dependency evaluation fold (repo-only).

The PapyGreek Treebanks (github.com/ezhenrik/papygreek-treebanks, **CC BY-SA 4.0**;
Vierros et al., JOHD 10.5334/johd.55) are Greek documentary papyri (ca. 300 BCE-700 CE)
annotated in the **Ancient Greek Dependency Treebank Guidelines 2.0** scheme — the same
9-place positional postag + Prague-style head/relation the shipped joint model was trained
on. This converts the syntactically-annotated Greek trees to a single UD CoNLL-U fold via
pyaegean's own AGDT->UD converter (``training/agdt_ud_deps.convert_tree`` +
``training/agdt_ud.{copular_flags,upos_from_xpos,feats_from_xpos}``) — the exact code that
built the training labels — so the fold scores under `aegean.greek.evaluate_on_papygreek`
with the same official CoNLL 2018 evaluator every other UD fold uses. Evaluation only,
never bundled, never trained on.

PapyGreek's ``<word>`` carries two annotation layers, ``orig_*`` (diplomatic) and ``reg_*``
(editorially regularized); the default build uses the **reg** layer — the normalized reading
that matches the AGDT/UD convention the model expects.

``--layer orig`` builds the diplomatic-surface variant of this same fold. The orig and reg
layers share tokenization exactly (every ``<word>`` carries both an ``orig_form`` and a
``form_reg`` on the same element — no token is added, dropped, or merged between layers), so
the orig fold keeps the **same sentences and the same gold columns** (LEMMA/UPOS/XPOS/FEATS/
HEAD/DEPREL, all computed from the reg reading) and swaps **only** the emitted FORM column
(and the ``# text`` header) to the raw diplomatic reading. The two folds are therefore
token-aligned line-for-line and differ only in column 2, so the orig row measures purely the
effect of the harder documentary orthography (itacism, phonetic spelling, non-standard
breathing) on the model, holding the gold analysis fixed. A diplomatic form that cannot be
recovered as a clean reading with the reg apparatus stripper (a fully-lost ``$`` marker, a
private-use papyrological glyph, an uncommon editorial sign) falls back to the reg reading so
the alignment is preserved; every such fallback is counted in the manifest. The orig FORM
tuples are re-run through the same leakage exclusion (a diplomatic spelling could in principle
collide differently), and any sentence that leaks only in its orig form is dropped and
recorded. The default (reg) build is byte-identical whether or not this mode exists.

Selection criteria (each counted in the manifest), applied per ``<sentence>``:
  1. **no artificial nodes** — an elliptic/``insertion_id`` node has no surface token, so a
     gold-tokenization score cannot include it; keeping it would need empty-node handling
     that injects conversion artifacts. Sentences containing one are excluded whole.
  2. **fully annotated** — every real token must carry ``form_reg``, ``head_reg``,
     ``relation_reg``, ``postag_reg`` and ``lemma_reg`` (partial/unannotated trees dropped).
  3. **clean reading** — the Leiden/EpiDoc editorial apparatus that the reg forms preserve
     (``[restoration]``, ``(expansion)``, ``<addition>``, ``{deletion}``, ``|`` line breaks,
     presentational marks) is stripped to the reading text (`strip_apparatus`); a sentence is
     dropped if any word token does not reduce to clean Greek or a punctuation token empties
     (the safety net — anything the stripper cannot cleanly resolve, e.g. an ``_.N``
     illegibility marker or a fully-erased word, is excluded rather than corrupted).
  4. **leakage-clean** — a sentence whose NFC form tuple (full or punctuation-stripped)
     appears in the shipped model's training set (``training/data/full-{train,dev}.jsonl`` =
     AGDT + Gorman + Pedalion) is excluded, the same form-tuple exclusion `agdt_ud_overlap`
     and ``build_full_dataset`` use. Pedalion ships a ``papyri.xml`` documentary subset, so
     this removes the real (not coincidental) overlaps.

Output (``--out``): ``papygreek-test.conllu`` + ``papygreek-fold.conllu.gz`` (the release
asset) + ``papygreek-fold-manifest.json`` (source commit, counts, per-reason exclusions,
doc ids). Prints the sha256 of the gz asset for the ``_REMOTE`` DataSpec pin. ``--layer orig``
writes the diplomatic-surface variant instead: ``papygreek-test-orig.conllu`` +
``papygreek-fold-orig.conllu.gz`` + ``papygreek-fold-orig-manifest.json`` (with the surface
disposition, the reg-vs-orig diff count, and the orig leakage recheck).

Usage:
    python scripts/build_papygreek_fold.py [--repo DIR] [--out DIR]
                                           [--training-data training/data]
                                           [--layer {reg,orig}]
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import unicodedata
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from typing import Any

# The AGDT->UD converter used to build the training labels (repo-only training code).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "training"))
from agdt_ud import copular_flags, feats_from_xpos, upos_from_xpos  # noqa: E402
from agdt_ud_deps import convert_tree  # noqa: E402

from aegean.greek.treebank import _clean_lemma  # noqa: E402

# PapyGreek Treebanks, pinned for reproducibility (CC BY-SA 4.0).
REPO_URL = "https://github.com/ezhenrik/papygreek-treebanks.git"
REPO_COMMIT = "0e5139b06e41d89275f3a1ace4ee0dc5513f2f7d"
LICENSE = "CC BY-SA 4.0 (PapyGreek Treebanks — Vierros et al.)"

# --- Leiden / EpiDoc apparatus stripping ----------------------------------------
# The reg forms preserve editorial notation. Recover the reading text:
#   keep the content of restorations/expansions/additions, drop the deleted/erased,
#   drop line-break and presentational marks. Anything left non-Greek fails the reading
#   test in `is_clean_reading` and the sentence is dropped (never silently corrupted).
_DELETE = (
    re.compile(r"\{[^{}]*\}"),  # {…} editorial deletion (superfluous text)
    re.compile(r"⟦[^⟦⟧]*⟧"),  # ⟦…⟧ erasure
    re.compile(r"〚[^〚〛]*〛"),  # 〚…〛 rasura
)
_KEEP_DELIMS = set("[]()<>\\/|")  # restoration/expansion/addition/above-line/line-break
_MARKS = set("¨¯^‧❛❜⧙⧘*?‖↕〰`´˘῀“”⸍∶†〈〉„‟«»_")  # presentational / editorial marks
_HYPHENS = set("-‐‑‒–—―")  # within-word line-division hyphens
_APOS = set("'’ʼ᾽᾿ʹ")  # elision / koronis apostrophes (kept in word tokens)

# Reg-layer word attributes read off each <word> element.
_REG_KEYS = (
    "id", "form_reg", "lemma_reg", "postag_reg", "relation_reg", "head_reg",
    "artificial", "insertion_id", "lang",
)

# PapyGreek stores letter-numeral lemmas with an inline value annotation,
# "<lemma>|num:<value>|" (e.g. "β|num:2|" for beta read as the numeral 2), and some
# lemmas carry a bare trailing "|" left by an empty apparatus marker. Neither is part of
# the lemma; reduce a reg lemma to the bare form before the shared homonym cleanup.
_LEMMA_NUM_SUFFIX = re.compile(r"\|num:[^|]*\|$")


def clean_lemma(lemma_reg: str | None) -> str:
    """Clean a reg-layer lemma to the training-convention lemma.

    Strips a trailing ``|num:<value>|`` numeral annotation and a bare trailing ``|``
    (PapyGreek apparatus residue, not part of the lemma), then delegates to the shared
    `_clean_lemma` for NFC and Perseus homonym numbering (``μένω1`` -> ``μένω``)."""
    lemma = unicodedata.normalize("NFC", lemma_reg or "").strip()
    lemma = _LEMMA_NUM_SUFFIX.sub("", lemma)
    if lemma.endswith("|"):
        lemma = lemma[:-1]
    return _clean_lemma(lemma)


def strip_apparatus(form: str) -> str:
    """Reduce a reg surface form to its reading text (see the module docstring)."""
    f = unicodedata.normalize("NFC", form)
    prev = None
    while prev != f:  # nested deletions resolve innermost-first
        prev = f
        for rx in _DELETE:
            f = rx.sub("", f)
    kept = [c for c in f if c not in _KEEP_DELIMS and c not in _MARKS and c not in _HYPHENS]
    return unicodedata.normalize("NFC", "".join(kept))


def is_clean_reading(form: str) -> bool:
    """True when a stripped word form is genuine Greek (letters/diacritics/elision only)."""
    if not form:
        return False
    if not all(c.isalpha() or unicodedata.combining(c) or c in _APOS for c in form):
        return False
    return any(
        "ἀ" <= c <= "῿" or "Α" <= c <= "ω" or "Ͱ" <= c <= "Ͽ" for c in form
    )


def reg_words(sentence: ET.Element) -> list[dict[str, Any]]:
    """The ``<word>`` elements of a sentence as reg-layer attribute dicts."""
    out: list[dict[str, Any]] = []
    for w in sentence:
        if w.tag == "word":
            out.append({k: w.get(k) for k in _REG_KEYS})
    return out


def orig_form_reads(sentence: ET.Element) -> list[str | None]:
    """The raw ``orig_form`` (diplomatic-layer surface) of each ``<word>``, aligned 1:1 with
    `reg_words` (both iterate the ``<word>`` children in document order; every element carries
    both a ``form_reg`` and an ``orig_form``)."""
    return [w.get("orig_form") for w in sentence if w.tag == "word"]


def orig_token_reading(orig_form: str | None, reg_reading: str, *, is_punct: bool) -> tuple[str, str]:
    """The emitted FORM for one token's orig (diplomatic) layer, and its disposition.

    The diplomatic reading is recovered with the SAME `strip_apparatus` + `is_clean_reading`
    the reg build uses — no orig-specific editorial modeling — so the two layers are stripped
    identically. Where the diplomatic form cannot be recovered as a clean Greek reading (a
    fully-lost ``$`` marker, a private-use papyrological glyph, an uncommon editorial sign) the
    token FALLS BACK to ``reg_reading`` so the orig fold stays token-aligned with the reg fold.

    ``reg_reading`` is the already-stripped, NFC reg surface form (``strip_apparatus(form_reg)``,
    the exact string the reg fold emits). Returns ``(form, disposition)`` where disposition is
    one of ``diplomatic_diff`` (a genuine diplomatic spelling unlike reg), ``diplomatic_same``
    (the diplomatic reading equals the reg reading), ``punct`` / ``punct_diff`` (a punctuation
    token), or ``fallback_unclean`` / ``fallback_empty`` (the reg reading is substituted)."""
    stripped = strip_apparatus(orig_form or "")
    if is_punct:
        if not stripped:
            return reg_reading, "fallback_empty"
        return (stripped, "punct_diff") if stripped != reg_reading else (stripped, "punct")
    if is_clean_reading(stripped):
        if stripped == reg_reading:  # both NFC already
            return stripped, "diplomatic_same"
        return stripped, "diplomatic_diff"
    return (reg_reading, "fallback_empty") if not stripped else (reg_reading, "fallback_unclean")


def sentence_status(words: list[dict[str, Any]]) -> str:
    """Selection verdict for one sentence: ``ok`` or the exclusion reason.

    Reasons (module docstring): ``empty``, ``artificial``, ``partial``, ``apparatus``.
    ``leaked`` is decided later against the training key set."""
    if not words:
        return "empty"
    if any(w["artificial"] or w["insertion_id"] for w in words):
        return "artificial"
    for w in words:
        if not (
            w["form_reg"] and w["head_reg"] and w["relation_reg"]
            and w["postag_reg"] and w["lemma_reg"]
        ):
            return "partial"
    for w in words:
        s = strip_apparatus(w["form_reg"])
        if (w["postag_reg"] or "")[:1] == "u":  # punctuation token
            if not s:
                return "apparatus"
        elif not is_clean_reading(s):
            return "apparatus"
    return "ok"


def sentence_to_conllu(
    sent_id: str,
    words: list[dict[str, Any]],
    *,
    surface_forms: list[str] | None = None,
) -> tuple[str, tuple[str, ...]]:
    """Convert one selected sentence's reg-layer words to a CoNLL-U block.

    Returns ``(block, forms)`` where ``forms`` is the emitted NFC form tuple (for the leakage
    check). HEAD/DEPREL/UPOS/XPOS/FEATS come from the shared AGDT->UD converter; the LEMMA is
    ``clean_lemma(lemma_reg)`` (numeral value annotations stripped; punctuation reconciled to
    the reg surface form, the convention the model was trained on — training punct lemma is the
    punct char, not PapyGreek's ``punc1``).

    ``surface_forms`` (one string per word, same order/length) overlays the emitted FORM column
    (and the ``# text`` header and the returned form tuple) with an alternate reading — the orig
    (diplomatic) layer — while EVERY gold column (LEMMA, UPOS, XPOS, FEATS, HEAD, DEPREL) is
    still computed from the reg reading. An orig fold is therefore byte-identical to the reg
    fold except column 2. When ``None`` (the default) the reg reading is emitted and the output
    is the reg fold, byte-for-byte."""
    attrs: list[dict[str, Any]] = []
    reg_forms: list[str] = []
    for w in words:
        s = strip_apparatus(w["form_reg"])
        reg_forms.append(s)
        attrs.append({
            "id": w["id"],
            "head": w["head_reg"],
            "relation": w["relation_reg"],
            "form": s,
            "lemma": clean_lemma(w["lemma_reg"]),
            "xpos": (w["postag_reg"] or "").ljust(9, "-")[:9],
        })
    emit = list(surface_forms) if surface_forms is not None else reg_forms
    flags = copular_flags(attrs)
    tree = convert_tree(attrs)
    lines = [f"# sent_id = {sent_id}", f"# text = {' '.join(emit)}"]
    for i, (a, (head, deprel), flag) in enumerate(zip(attrs, tree, flags), start=1):
        xpos = a["xpos"]
        upos = upos_from_xpos(
            a["form"], xpos, lemma=a["lemma"], has_pnom_child=flag, own_relation=a["relation"]
        )
        feats = feats_from_xpos(xpos)
        lemma = a["form"] if xpos[:1] == "u" else (a["lemma"] or a["form"])
        lines.append(
            "\t".join([str(i), emit[i - 1], lemma, upos, xpos, feats, str(head), deprel, "_", "_"])
        )
    return "\n".join(lines) + "\n", tuple(emit)


# --- leakage key set (form tuples of the shipped model's training data) ----------


def _has_punct(form: str) -> bool:
    return not any(ch.isalpha() or ch.isdigit() for ch in form)


def training_form_keys(training_dir: Path) -> set[tuple[str, ...]]:
    """NFC form tuples (full + punctuation-stripped) of the training + dev sentences.

    Mirrors ``build_full_dataset._overlap_keys_ud`` / `agdt_ud_overlap`: a fold sentence
    whose form tuple lands in this set was seen by the model and is excluded."""
    keys: set[tuple[str, ...]] = set()
    for name in ("full-train.jsonl", "full-dev.jsonl"):
        path = training_dir / name
        if not path.exists():
            continue
        with open(path, encoding="utf-8") as f:
            for line in f:
                toks = tuple(
                    unicodedata.normalize("NFC", t) for t in json.loads(line)["tokens"]
                )
                keys.add(toks)
                keys.add(tuple(t for t in toks if not _has_punct(t)))
    return keys


def is_leaked(forms: tuple[str, ...], keys: set[tuple[str, ...]]) -> bool:
    """True when a fold sentence's form tuple (full or punct-stripped) is in the train keys."""
    if forms in keys:
        return True
    stripped = tuple(t for t in forms if not _has_punct(t))
    return bool(stripped) and stripped in keys


# --- driver ----------------------------------------------------------------------


def _clone(dest: Path) -> Path:
    """Clone the pinned PapyGreek repo into ``dest`` (shallow, then checkout the commit)."""
    subprocess.run(
        ["git", "clone", "--filter=blob:none", "--no-checkout", REPO_URL, str(dest)],
        check=True,
    )
    subprocess.run(["git", "-C", str(dest), "checkout", REPO_COMMIT], check=True)
    return dest


def build(repo: Path, training_dir: Path, *, layer: str = "reg") -> tuple[str, dict[str, Any]]:
    """Convert the treebank; return ``(conllu_text, manifest)``.

    ``layer`` is ``"reg"`` (the default, editorially regularized forms — byte-identical output
    whether or not the orig mode exists) or ``"orig"`` (the same sentences and gold columns, the
    emitted FORM swapped to the diplomatic reading; see the module docstring)."""
    if layer not in ("reg", "orig"):
        raise ValueError(f"layer must be 'reg' or 'orig'; got {layer!r}")
    docdir = repo / "documentary"
    if not docdir.is_dir():
        raise SystemExit(f"no documentary/ dir under {repo}")
    keys = training_form_keys(training_dir)

    reasons: Counter[str] = Counter()
    blocks: list[str] = []
    doc_ids: list[str] = []
    n_sent_total = 0
    n_tokens = 0
    # orig-mode accounting (unused in reg mode)
    disp: Counter[str] = Counter()
    n_diff = 0
    orig_leaked = 0
    orig_leaked_ids: list[str] = []
    for fp in sorted(docdir.rglob("*.xml")):
        stem = fp.name[:-4] if fp.name.endswith(".xml") else fp.name
        root = ET.parse(str(fp)).getroot()
        kept_here = 0
        for sent in root.iter("sentence"):
            n_sent_total += 1
            words = reg_words(sent)
            status = sentence_status(words)
            if status != "ok":
                reasons[status] += 1
                continue
            sent_id = f"papygreek:{stem}@{sent.get('id')}"
            # The reg forms drive selection identically in both modes: the same reg leakage
            # exclusion keeps the same base set of sentences the reg fold keeps.
            reg_block, reg_forms = sentence_to_conllu(sent_id, words)
            if is_leaked(reg_forms, keys):
                reasons["leaked"] += 1
                continue
            if layer == "orig":
                surface: list[str] = []
                local_disp: Counter[str] = Counter()
                local_diff = 0
                origs = orig_form_reads(sent)
                for w, oform, reg_read in zip(words, origs, reg_forms):
                    is_punct = (w["postag_reg"] or "")[:1] == "u"
                    read, d = orig_token_reading(oform, reg_read, is_punct=is_punct)
                    surface.append(read)
                    local_disp[d] += 1
                    if read != reg_read:
                        local_diff += 1
                block, forms = sentence_to_conllu(sent_id, words, surface_forms=surface)
                # Mandatory: a diplomatic spelling could collide with the training keys
                # differently from its reg form — re-run the exclusion on the orig FORM tuple.
                if is_leaked(forms, keys):
                    orig_leaked += 1
                    orig_leaked_ids.append(sent_id)
                    continue
                disp.update(local_disp)
                n_diff += local_diff
            else:
                block, forms = reg_block, reg_forms
            blocks.append(block)
            n_tokens += len(forms)
            kept_here += 1
        if kept_here:
            doc_ids.append(stem)

    # each block ends in "\n"; joining with "\n" gives a blank line between sentences and
    # the trailing "+\n" makes the file end with an empty line (the CoNLL-U evaluator requires it)
    conllu = ("\n".join(blocks) + "\n") if blocks else ""
    if layer == "reg":
        manifest: dict[str, Any] = {
            "purpose": "documentary-Koine (PapyGreek) dependency evaluation fold; eval only",
            "source_repo": "github.com/ezhenrik/papygreek-treebanks",
            "source_commit": REPO_COMMIT,
            "license": LICENSE,
            "annotation_scheme": "AGDT Guidelines 2.0 (reg layer)",
            "converter": "training/agdt_ud_deps.convert_tree + agdt_ud.{copular_flags,"
                         "upos_from_xpos,feats_from_xpos}",
            "leakage_reference": "training/data/full-{train,dev}.jsonl (AGDT+Gorman+Pedalion); "
                                 "NFC form-tuple exclusion (full + punct-stripped)",
            "sentences_in_source": n_sent_total,
            "sentences_kept": len(blocks),
            "tokens_kept": n_tokens,
            "documents_kept": len(doc_ids),
            "excluded": dict(sorted(reasons.items())),
            "doc_ids": doc_ids,
        }
    else:
        manifest = {
            "purpose": "documentary-Koine (PapyGreek) dependency evaluation fold — ORIG "
                       "(diplomatic) surface layer; eval only",
            "layer": "orig (diplomatic surface forms; reg gold labels)",
            "comparability": "the SAME sentences and the SAME gold columns "
                             "(LEMMA/UPOS/XPOS/FEATS/HEAD/DEPREL) as the reg papygreek-fold; "
                             "only the emitted FORM (column 2) and the '# text' header carry the "
                             "diplomatic orig reading, so the two folds are token-aligned "
                             "line-for-line and diff only in the surface form",
            "reg_fold_reference": "papygreek-fold (reg layer); same sentence selection",
            "source_repo": "github.com/ezhenrik/papygreek-treebanks",
            "source_commit": REPO_COMMIT,
            "license": LICENSE,
            "annotation_scheme": "AGDT Guidelines 2.0 (reg gold labels; orig/diplomatic "
                                 "surface forms)",
            "converter": "training/agdt_ud_deps.convert_tree + agdt_ud.{copular_flags,"
                         "upos_from_xpos,feats_from_xpos}",
            "surface_layer_policy": "diplomatic reading recovered with the reg apparatus "
                                    "stripper + clean-reading test (no orig-specific editorial "
                                    "modeling); a token whose diplomatic form is a lost '$' "
                                    "marker, a private-use glyph, or an uncommon editorial sign "
                                    "falls back to the reg reading (counted in surface_disposition)",
            "leakage_reference": "training/data/full-{train,dev}.jsonl (AGDT+Gorman+Pedalion); "
                                 "NFC form-tuple exclusion (full + punct-stripped)",
            "leakage_recheck": "the reg selection already excluded reg-leaked sentences; the "
                               "orig FORM tuples were re-run through the same exclusion (a "
                               "diplomatic spelling could collide differently)",
            "sentences_in_source": n_sent_total,
            "sentences_kept": len(blocks),
            "tokens_kept": n_tokens,
            "documents_kept": len(doc_ids),
            "excluded": dict(sorted(reasons.items())),
            "orig_leakage_rechecked_and_dropped": orig_leaked,
            "orig_leaked_sent_ids": orig_leaked_ids,
            "surface_disposition": dict(sorted(disp.items())),
            "tokens_diplomatic_differ_from_reg": n_diff,
            "doc_ids": doc_ids,
        }
    return conllu, manifest


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", default=None,
                    help="existing checkout of the PapyGreek repo (else clone the pinned commit)")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / "training" / "data"),
                    help="output directory for the conllu / gz / manifest")
    ap.add_argument("--training-data",
                    default=str(Path(__file__).resolve().parent.parent / "training" / "data"),
                    help="dir holding full-train.jsonl / full-dev.jsonl for the leakage check")
    ap.add_argument("--layer", default="reg", choices=("reg", "orig"),
                    help="reg (default, regularized forms — byte-identical to the shipped fold) "
                         "or orig (the diplomatic-surface variant; same sentences/gold, FORM only)")
    args = ap.parse_args()

    tmp: tempfile.TemporaryDirectory[str] | None = None
    if args.repo:
        repo = Path(args.repo)
    else:
        tmp = tempfile.TemporaryDirectory()
        repo = _clone(Path(tmp.name) / "papygreek-treebanks")
    try:
        conllu, manifest = build(repo, Path(args.training_data), layer=args.layer)
    finally:
        if tmp is not None:
            tmp.cleanup()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    if args.layer == "orig":
        conllu_path = out / "papygreek-test-orig.conllu"
        gz_path = out / "papygreek-fold-orig.conllu.gz"
        manifest_path = out / "papygreek-fold-orig-manifest.json"
    else:
        conllu_path = out / "papygreek-test.conllu"
        gz_path = out / "papygreek-fold.conllu.gz"
        manifest_path = out / "papygreek-fold-manifest.json"
    conllu_path.write_text(conllu, encoding="utf-8")
    raw = conllu.encode("utf-8")
    # mtime=0 + no embedded filename → the gz bytes (and sha256) are reproducible across runs.
    with open(gz_path, "wb") as fh, gzip.GzipFile(
        filename="", mode="wb", fileobj=fh, mtime=0, compresslevel=9
    ) as gz:
        gz.write(raw)
    sha = hashlib.sha256(gz_path.read_bytes()).hexdigest()
    manifest["asset_sha256"] = sha
    manifest["asset_bytes"] = gz_path.stat().st_size
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")

    summary = {k: v for k, v in manifest.items() if k != "doc_ids"}
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    print(f"\nwrote {conllu_path}")
    print(f"wrote {gz_path}  ({gz_path.stat().st_size:,} bytes)")
    print(f"wrote {manifest_path}")
    print(f"sha256 (gz asset): {sha}")


if __name__ == "__main__":
    main()
