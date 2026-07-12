"""Build the Ancient Greek VERSE dependency evaluation fold (repo-only).

The ``unesp-trees`` repository (github.com/perseids-publications/unesp-trees, **CC BY-SA
4.0** per its ``TREEBANK_LICENSE``; the Perseids/Arethusa treebanks of Prof. Anise
D'Orange Ferreira's UNESP project, manual gold dependency annotation by named human
annotators) holds AGDT-scheme (``format="aldt"``) syntactic trees. This builds a single
**verse** evaluation fold out of the poetic material the shipped joint model has never
seen, converting the gold trees through the *same* AGDT->UD machinery
(``training/agdt_ud_deps.convert_tree`` + ``training/agdt_ud.{copular_flags,upos_from_xpos,
feats_from_xpos}``, via `build_papygreek_fold.sentence_to_conllu`) that built the training
labels, so the fold scores under `aegean.greek.evaluate_on_verse` with the same official
CoNLL 2018 evaluator every other UD fold uses. Evaluation only, never bundled, never
trained on.

One labeled track, carried under a ``sent_id`` prefix in the CoNLL-U file:

  * ``verse:tragedy:...`` — **Euripides, Bacchae 1-169** (spoken trimeter + the parodos'
    lyric): ``euripides-ba-1-22.xml`` + ``euripides-ba-23-169.xml`` (the 2021 aldt files).
    The **first leakage-clean tragedy dependency evaluation** for the shipped model.

The Maximus *Peri katarchon* 1.4 material (``maximus-astrol-1-4.xml``) is **not** built into
the fold: its annotation is the prose paraphrase of the poem, not the verse — the annotated
lines do not scan (``ἐν δὲ τῇ δευτέρᾳ ἡμέρᾳ ἐν μὲν νυκτὶ οὐ δεῖ ἀποδημεῖν`` is plain prose;
``ἔμπρακτον γὰρ γίνεται`` is a 7-syllable clause) — so labelling it ``hexameter`` would
misdescribe it. Maximus is retained only as a forbidden training work
(``work_level_disjointness``) so a future re-addition stays leakage-guarded.

**Near-duplicates excluded** (documented, never converted): ``eur-ba-23-169.xml`` is an
earlier content-duplicate of ``euripides-ba-23-169.xml`` (same 733-token passage, older
2020 header); ``max-astrol-I-4-1-14.xml`` is a second annotation of the same Maximus material
in the ``smyth3`` format (the Maximus material is excluded from the fold regardless; see
above).

The gold LEMMA is additionally repaired for two malformed-headword classes the UNESP source
carries: Latin homoglyph vowels (Latin ``í``/``ó`` for Greek ``ί``/``ό``) embedded in an
otherwise-Greek lemma are mapped to Greek, and an LSJ citation-form tail (a trailing
enumeration of endings, an article, or a parenthetical gloss) is truncated at the first comma
or opening parenthesis. Every repair is recorded in the manifest (``lemma_cleanings``,
before -> after), and the build asserts every emitted lemma is a clean single Greek-script
headword (elided apostrophe-final forms allowed), failing loudly otherwise. The FORM column
is left untouched.

Selection criteria (each counted in the manifest), applied per ``<sentence>`` via
`build_papygreek_fold.sentence_status`:
  1. **no artificial nodes** — an elliptic/reconstructed (``artificial``/``insertion_id``)
     node, or a bracketed/empty placeholder form, has no scorable surface position; a
     sentence containing one is excluded whole (this fold reads standard AGDT ``<word>``
     attributes, where such a node may carry the ``artificial`` attribute, an
     ``insertion_id``, or only a bracketed form — the adapter flags all three).
  2. **fully annotated** — every real token carries ``form``/``head``/``relation``/
     ``postag``/``lemma`` (partial/unannotated trees dropped).
  3. **clean reading** — the shared apparatus stripper (`strip_apparatus`) reduces each
     form to reading text (line-division hyphens / crasis marks removed, e.g. the
     Arethusa crasis fragment ``τ-`` -> ``τ``); a sentence is dropped if any word does not
     reduce to genuine Greek or a punctuation token empties.
  4. **leakage-clean** — a sentence whose NFC form tuple (full or punctuation-stripped)
     appears in the shipped model's training set (``training/data/full-{train,dev}.jsonl`` =
     AGDT + Gorman + Pedalion) is excluded, the same form-tuple exclusion the PapyGreek
     fold and `agdt_ud_overlap` use. Re-run inside the build; **any leak fails the build.**

Beyond the sentence-level leakage exclusion, the build asserts **work-level disjointness**:
the training rows carry a ``file`` field, so it verifies no training document is the same
work as either track's source (Euripides Bacchae / Maximus), failing on a match and
recording the same-author training files for the manifest (the only trained Euripides is
Medea, via Pedalion).

Output (``--out``): ``verse-test.conllu`` + ``verse-fold.conllu.gz`` (the release asset) +
``verse-fold-manifest.json`` (source commit, per-track/per-file exclusion accounting,
near-duplicate exclusions, leakage + disjointness verdicts, lemma repairs,
annotator/provenance credits). Prints the sha256 of the gz asset for the ``_REMOTE``
DataSpec pin.

Usage:
    python scripts/build_verse_fold.py [--repo DIR] [--out DIR]
                                       [--training-data training/data]
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

# Reuse the PapyGreek fold build verbatim (the shared AGDT->UD converter, apparatus
# stripper, reading test, leakage keys, and the CoNLL-U emitter). This guarantees the verse
# tokens are converted and scored byte-for-byte the way the papygreek and training tokens
# are.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_papygreek_fold import (  # noqa: E402
    _APOS,
    _HYPHENS,
    is_leaked,
    sentence_status,
    sentence_to_conllu,
    training_form_keys,
)

# unesp-trees, pinned for reproducibility (CC BY-SA 4.0).
REPO_URL = "https://github.com/perseids-publications/unesp-trees.git"
REPO_COMMIT = "a6367b9721b228aa5ccd2a7c3a79bb9c7bb7d8ff"
LICENSE = (
    "CC BY-SA 4.0 (unesp-trees — Perseids/Arethusa, Prof. Anise D'Orange Ferreira, UNESP)"
)

# track -> source XML files (repo-relative). Order is the fold's document order.
# Tragedy only: the annotated Maximus material is prose paraphrase, not verse (see the
# module docstring), so it is not built into the fold.
TRACKS: dict[str, tuple[str, ...]] = {
    "tragedy": (
        "public/xml/euripides-ba-1-22.xml",
        "public/xml/euripides-ba-23-169.xml",
    ),
}

# Near-duplicate annotations excluded from the fold, with the reason (recorded in the
# manifest; never converted).
EXCLUDED_NEAR_DUPS: dict[str, str] = {
    "public/xml/eur-ba-23-169.xml":
        "earlier content-duplicate of euripides-ba-23-169.xml (same 733-token Bacchae "
        "23-169 passage, older 2020 header)",
    "public/xml/max-astrol-I-4-1-14.xml":
        "second annotation of the same Maximus Peri katarchon 1.4 material in the smyth3 "
        "format; the Maximus material is excluded from the fold regardless (it is the prose "
        "paraphrase, not verse)",
}

# Work-level disjointness: no training document may be the same work as any verse source
# considered for this fold. ``file`` values in training/data/full-{train,dev}.jsonl are
# matched against these; any match fails the build. Bacchae = TLG tlg0006.tlg017; Maximus
# astrologus = TLG tlg1385 (Maximus is not built into the fold — see the module docstring —
# but is kept here as a forbidden work so a future re-addition stays leakage-guarded).
_FORBIDDEN_TRAINING: dict[str, re.Pattern[str]] = {
    "tragedy": re.compile(r"tlg0006\.tlg017|bacch", re.IGNORECASE),
    "hexameter": re.compile(r"tlg1385|maxim|astrol|katarch", re.IGNORECASE),
}
# Same-author reference patterns, reported (not forbidden) so the manifest records exactly
# which same-author documents the training set does contain (Euripides -> only Medea).
_SAME_AUTHOR: dict[str, re.Pattern[str]] = {
    "tragedy": re.compile(r"tlg0006|eurip", re.IGNORECASE),
}

# --- gold lemma repair -----------------------------------------------------------
# The UNESP gold carries two malformed-headword classes the shared clean_lemma does not
# touch: Latin precomposed accented vowels used as homoglyphs for Greek tonos vowels, and
# LSJ citation-form tails (a trailing enumeration of endings, an article, or a parenthetical
# gloss). Repair both conservatively; the FORM column is untouched.
_LATIN_TO_GREEK_VOWEL: dict[str, str] = {
    "á": "ά",  # á -> ά (alpha with tonos)
    "é": "έ",  # é -> έ (epsilon)
    "í": "ί",  # í -> ί (iota)
    "ó": "ό",  # ó -> ό (omicron)
    "ú": "ύ",  # ú -> ύ (upsilon)
    "Á": "Ά",  # Á -> Ά
    "É": "Έ",  # É -> Έ
    "Í": "Ί",  # Í -> Ί
    "Ó": "Ό",  # Ó -> Ό
    "Ú": "Ύ",  # Ú -> Ύ
}
# citation-form tail begins at the first comma or opening parenthesis (a real headword
# contains neither); ASCII and fullwidth comma both covered.
_TAIL_START = set(",(，")


def _is_greek_char(c: str) -> bool:
    return unicodedata.name(c, "").startswith("GREEK")


def clean_verse_lemma(raw: str | None) -> str:
    """Repair a malformed UNESP gold lemma to a clean single Greek-script headword.

    Two conservative repairs, each firing only on structurally-invalid input a real lemma
    never contains, so a well-formed lemma is returned unchanged (modulo NFC):
      * an LSJ citation-form tail is dropped — the lemma is truncated at the first comma or
        opening parenthesis, then surrounding whitespace and stray non-breaking hyphens are
        stripped;
      * Latin homoglyph vowels (á/é/í/ó/ú with acute) embedded in an otherwise-Greek lemma
        are mapped to their Greek tonos equivalents."""
    lemma = unicodedata.normalize("NFC", raw or "")
    cut = next((i for i, c in enumerate(lemma) if c in _TAIL_START), len(lemma))
    lemma = lemma[:cut]
    lemma = lemma.strip().strip("".join(_HYPHENS)).strip()
    if any(_is_greek_char(c) for c in lemma) and any(c in _LATIN_TO_GREEK_VOWEL for c in lemma):
        lemma = "".join(_LATIN_TO_GREEK_VOWEL.get(c, c) for c in lemma)
    return unicodedata.normalize("NFC", lemma)


def is_clean_headword(lemma: str) -> bool:
    """True when a lemma is a single Greek-script headword: every character is a Greek
    letter, a combining diacritic, or an elision apostrophe (no Latin homoglyphs, no
    citation punctuation, no whitespace), and at least one Greek letter is present."""
    if not lemma:
        return False
    for c in lemma:
        if unicodedata.combining(c) or c in _APOS:
            continue
        if not _is_greek_char(c):
            return False
    return any(_is_greek_char(c) for c in lemma)


def assert_clean_lemmas(conllu: str) -> None:
    """Fail the build (SystemExit) if any emitted non-punctuation lemma is not a clean
    Greek-script headword (a punctuation token's lemma is the punctuation character)."""
    bad: list[tuple[str, str]] = []
    for ln in conllu.splitlines():
        if not ln or ln.startswith("#"):
            continue
        cols = ln.split("\t")
        if len(cols) < 5 or cols[4][:1] == "u":  # punctuation lemma = the punct char
            continue
        if not is_clean_headword(cols[2]):
            bad.append((cols[1], cols[2]))
    if bad:
        raise SystemExit(
            f"lemma validation FAILED: {len(bad)} emitted lemma(s) are not a clean "
            f"Greek-script headword: {bad[:12]}"
        )


def agdt_reg_words(sentence: ET.Element) -> list[dict[str, Any]]:
    """The ``<word>`` elements of a standard AGDT sentence, mapped to the reg-layer key
    names `build_papygreek_fold.sentence_status`/`sentence_to_conllu` expect.

    unesp-trees is a standard AGDT (``aldt``) treebank with plain ``form``/``lemma``/
    ``postag``/``relation``/``head`` attributes (no PapyGreek orig/reg layers), so the
    surface form is copied straight into ``form_reg`` etc. A reconstructed/elliptic node is
    flagged ``artificial`` robustly: the ``artificial`` attribute, an ``insertion_id``, or a
    bracketed/empty placeholder form all set it, so no reconstructed token can survive
    selection even when the attribute is absent."""
    out: list[dict[str, Any]] = []
    for w in sentence:
        if w.tag != "word":
            continue
        form = w.get("form") or ""
        artificial = w.get("artificial")
        if not artificial and (not form or form.startswith("[")):
            artificial = "bracketed"  # a placeholder node without the attribute
        out.append({
            "id": w.get("id"),
            "form_reg": form,
            "lemma_reg": w.get("lemma"),
            "postag_reg": w.get("postag"),
            "relation_reg": w.get("relation"),
            "head_reg": w.get("head"),
            "artificial": artificial,
            "insertion_id": w.get("insertion_id"),
            "lang": w.get("lang") or "grc",
        })
    return out


def _stem(rel_path: str) -> str:
    """The document stem of a repo-relative XML path (``public/xml/foo.xml`` -> ``foo``)."""
    name = rel_path.rsplit("/", 1)[-1]
    return name[:-4] if name.endswith(".xml") else name


def _file_doc_id(root: ET.Element) -> str:
    """The first non-empty ``document_id`` in a treebank (for the manifest provenance)."""
    for sent in root.iter("sentence"):
        did = sent.get("document_id")
        if did:
            return did
    return ""


def _annotators(root: ET.Element) -> list[str]:
    """Named human annotators of a treebank (``<annotator><name>``; empty names skipped)."""
    names: list[str] = []
    for ann in root.iter("annotator"):
        name = (ann.findtext("name") or "").strip()
        if name and name not in names:
            names.append(name)
    return names


def training_files(training_dir: Path) -> set[str]:
    """The ``file`` field of every training + dev row (the training document set)."""
    files: set[str] = set()
    for name in ("full-train.jsonl", "full-dev.jsonl"):
        path = training_dir / name
        if not path.exists():
            continue
        with open(path, encoding="utf-8") as f:
            for line in f:
                fname = json.loads(line).get("file")
                if fname:
                    files.add(fname)
    return files


def check_disjointness(train_files: set[str]) -> dict[str, Any]:
    """Assert work-level disjointness of every forbidden verse work from the training set.

    Every verse source considered for this fold (the tragedy source, and Maximus — retained
    as a forbidden work though its prose-paraphrase annotation is not built into the fold)
    must be absent from the training documents. Fails the build (SystemExit) if any training
    document is the same work; returns a per-work record of the forbidden-match verdict and
    the same-author training files that DO legitimately exist (Euripides -> only Medea)."""
    record: dict[str, Any] = {}
    for work in _FORBIDDEN_TRAINING:
        forbidden = sorted(f for f in train_files if _FORBIDDEN_TRAINING[work].search(f))
        if forbidden:
            raise SystemExit(
                f"work-level disjointness FAILED for {work!r}: the training set "
                f"contains the same work(s): {forbidden}"
            )
        entry: dict[str, Any] = {"forbidden_matches": forbidden}
        if work in _SAME_AUTHOR:
            entry["same_author_in_training"] = sorted(
                f for f in train_files if _SAME_AUTHOR[work].search(f)
            )
        record[work] = entry
    return record


def build(repo: Path, training_dir: Path) -> tuple[str, dict[str, Any]]:
    """Convert the verse trees; return ``(conllu_text, manifest)``. Fails on any leak."""
    keys = training_form_keys(training_dir)
    train_files = training_files(training_dir)
    disjointness = check_disjointness(train_files)

    blocks: list[str] = []
    n_sent_total = 0
    n_tokens = 0
    track_stats: dict[str, Any] = {}
    sources: list[dict[str, Any]] = []
    lemma_cleanings: list[dict[str, str]] = []

    for track, files in TRACKS.items():
        reasons: Counter[str] = Counter()
        kept = 0
        kept_tokens = 0
        for rel in files:
            fp = repo / rel
            if not fp.exists():
                raise SystemExit(f"missing source file {rel} under {repo}")
            root = ET.parse(str(fp)).getroot()
            stem = _stem(rel)
            src_kept = 0
            src_sent = 0
            for sent in root.iter("sentence"):
                src_sent += 1
                n_sent_total += 1
                words = agdt_reg_words(sent)
                status = sentence_status(words)
                if status != "ok":
                    reasons[status] += 1
                    continue
                sent_id = f"verse:{track}:{stem}@{sent.get('id')}"
                # repair malformed gold lemmas in place (logged before -> after); the FORM
                # column is untouched, so selection/leakage are unaffected.
                for w in words:
                    raw = w["lemma_reg"] or ""
                    repaired = clean_verse_lemma(raw)
                    if repaired != unicodedata.normalize("NFC", raw):
                        lemma_cleanings.append({
                            "sent_id": sent_id,
                            "form": w["form_reg"] or "",
                            "before": raw,
                            "after": repaired,
                        })
                        w["lemma_reg"] = repaired
                block, forms = sentence_to_conllu(sent_id, words)
                if is_leaked(forms, keys):
                    # mandatory: any leak fails the build (never silently drop)
                    raise SystemExit(
                        f"LEAKAGE FAILURE: {sent_id} form tuple is in the training set: "
                        f"{forms[:8]}"
                    )
                blocks.append(block)
                kept += 1
                kept_tokens += len(forms)
                src_kept += 1
            sources.append({
                "track": track,
                "path": rel,
                "stem": stem,
                "format": root.get("format"),
                "date": root.findtext("date"),
                "document_id": _file_doc_id(root),
                "annotators": _annotators(root),
                "sentences_in_source": src_sent,
                "sentences_kept": src_kept,
            })
        n_tokens += kept_tokens
        track_stats[track] = {
            "sentences_kept": kept,
            "tokens_kept": kept_tokens,
            "excluded": dict(sorted(reasons.items())),
        }

    conllu = ("\n".join(blocks) + "\n") if blocks else ""
    # every emitted lemma must be a clean single Greek-script headword (fail loudly otherwise)
    assert_clean_lemmas(conllu)
    manifest: dict[str, Any] = {
        "purpose": "Ancient Greek verse (tragedy) dependency evaluation fold; eval only, "
                   "SMALL-SAMPLE genre-conditioned datapoint, never a headline number",
        "source_repo": "github.com/perseids-publications/unesp-trees",
        "source_commit": REPO_COMMIT,
        "license": LICENSE,
        "annotation_scheme": "AGDT (aldt) manual gold dependency annotation",
        "converter": "build_papygreek_fold.sentence_to_conllu "
                     "(training/agdt_ud_deps.convert_tree + agdt_ud.{copular_flags,"
                     "upos_from_xpos,feats_from_xpos}) — shared with the PapyGreek fold",
        "maximus_excluded": "the annotated Maximus (Peri katarchon 1.4) material is the prose "
                            "paraphrase, not the verse — the lines do not scan — so it is not "
                            "built into the fold; it is retained as a forbidden training work "
                            "(work_level_disjointness.hexameter) so a future re-addition stays "
                            "leakage-guarded",
        "lemma_repair": "malformed UNESP gold lemmas repaired to clean Greek-script headwords: "
                        "Latin homoglyph vowels (Latin i/o-acute for Greek tonos) mapped to "
                        "Greek, and LSJ citation-form tails truncated at the first comma or "
                        "opening parenthesis; every emitted lemma validated as a clean headword",
        "leakage_reference": "training/data/full-{train,dev}.jsonl (AGDT+Gorman+Pedalion); "
                             "NFC form-tuple exclusion (full + punct-stripped); "
                             "re-run in-build, any leak fails the build",
        "leakage_result": {"leaked_sentences": 0, "checked_sentences": len(blocks)},
        "work_level_disjointness": disjointness,
        "tracks": track_stats,
        "sentences_in_source": n_sent_total,
        "sentences_kept": len(blocks),
        "tokens_kept": n_tokens,
        "lemma_cleanings_count": len(lemma_cleanings),
        "lemma_cleanings": lemma_cleanings,
        "sources": sources,
        "excluded_near_duplicates": EXCLUDED_NEAR_DUPS,
        "sent_id_scheme": "verse:<track>:<document-stem>@<sentence-id>",
    }
    return conllu, manifest


def _clone(dest: Path) -> Path:
    """Clone the pinned unesp-trees repo into ``dest`` (blob-less, then checkout the commit)."""
    subprocess.run(
        ["git", "clone", "--filter=blob:none", "--no-checkout", REPO_URL, str(dest)],
        check=True,
    )
    subprocess.run(["git", "-C", str(dest), "checkout", REPO_COMMIT], check=True)
    return dest


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", default=None,
                    help="existing checkout of unesp-trees (else clone the pinned commit)")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / "training" / "data"),
                    help="output directory for the conllu / gz / manifest")
    ap.add_argument("--training-data",
                    default=str(Path(__file__).resolve().parent.parent / "training" / "data"),
                    help="dir holding full-train.jsonl / full-dev.jsonl for the leakage check")
    args = ap.parse_args()

    tmp: tempfile.TemporaryDirectory[str] | None = None
    if args.repo:
        repo = Path(args.repo)
    else:
        tmp = tempfile.TemporaryDirectory()
        repo = _clone(Path(tmp.name) / "unesp-trees")
    try:
        conllu, manifest = build(repo, Path(args.training_data))
    finally:
        if tmp is not None:
            tmp.cleanup()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    conllu_path = out / "verse-test.conllu"
    gz_path = out / "verse-fold.conllu.gz"
    manifest_path = out / "verse-fold-manifest.json"
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

    print(json.dumps(manifest, ensure_ascii=False, indent=1))
    print(f"\nwrote {conllu_path}")
    print(f"wrote {gz_path}  ({gz_path.stat().st_size:,} bytes)")
    print(f"wrote {manifest_path}")
    print(f"sha256 (gz asset): {sha}")


if __name__ == "__main__":
    main()
