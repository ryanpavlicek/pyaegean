"""Build the DBBE Byzantine book-epigram tagging evaluation fold (repo-only).

The DBBE linguistic-annotation gold standard (github.com/coswaele/ByzantineGreekDatasets,
``lingAnn_GS_medievalGreek.tsv``; Swaelens, De Vos & Lefever, *Linguistic annotation of
Byzantine book epigrams*, Language Resources and Evaluation 59.1 (2025) 109-134,
doi:10.1007/s10579-023-09703-x) is ~10k tokens of **unedited** medieval-Greek verse from the
Database of Byzantine Book Epigrams, manually annotated for part-of-speech, morphology and
lemma. It is a register no other pyaegean fold covers: later Byzantine verse (7th-15th c., the
DBBE's documented scope) in
**non-normalised scribal orthography** (itacism, missing iota subscript, dropped breathings),
with lemmas standardised to Attic dictionary headwords.

The gold uses the **Ancient Greek Dependency Treebank (AGDT) 9-position positional postag** —
the same scheme the shipped joint model was trained on — so this converts it to a UD CoNLL-U
fold with pyaegean's OWN AGDT->UD converter (``training/agdt_ud.upos_from_xpos`` +
``aegean.greek.udfeats.feats_from_xpos``), the exact code that built the training labels, so
the fold scores under the same official CoNLL 2018 evaluator every other UD fold uses. There
are **no dependency trees** in the source (POS/morph/lemma only), so this is a **tagging-only**
fold: it yields UPOS / XPOS / UFeats / lemma but NOT UAS/LAS (placeholder HEAD/DEPREL; score
with ``parse=False``). Evaluation only, never bundled, never trained on.

**Tagset note (why not dilemma's DBBE_TO_UPOS).** The `dilemma` project maps the postag's
first character with a crude 12-entry table (``c``->CCONJ, ``g``->PART, no ``u``/``x``). That
mis-handles the two real UD splits this gold exercises: ``c`` conflates coordinating (καί,
ἀλλά) with SUBORDINATING (ὡς, εἰ, ὅπως, ὅτι) conjunctions, and καί itself is tagged both
``g`` (particle) and ``c`` (conj). pyaegean's converter resolves ``c`` ->
CCONJ/SCONJ form-deterministically (its validated closed-class subordinator lexicon) and maps
``u``->PUNCT / ``x``->X, so the gold is mapped under the SAME conventions as the training
labels. The one convention it cannot resolve here is ``v`` -> AUX (copular εἰμί), which is a
TREE signal (a PNOM dependent) the tagging-only source lacks: every ``v`` stays VERB, so a
copula the model predicts AUX is scored wrong (a small, documented systematic cap).

**Selection (each counted in the manifest), applied per token; an unusable WORD token drops the
whole sentence (never silently corrupt), while an unusable punctuation or marker-glyph token is
dropped in place, keeping the words:**
  1. **empty** — a blank/tab-only row (empty form or empty postag).
  2. **illegible** — a form carrying an illegibility marker (``(...)`` / ``(…`` / ``…``) or an
     alphabetic token mis-filed under the punctuation postag (e.g. ``suprascr.``).
  3. **marker_glyph** — a non-linguistic marker glyph (no alphabetic character, e.g. ``+`` / ``∙``
     / ``※`` / ``᾽`` / ``++:+``) that the gold mis-filed under a WORD postag (NOUN/CCONJ/PART/…);
     the mirror of the alphabetic-under-punct case, dropped in place with its own counter.
  4. **malformed_tag** — a postag longer than 9 chars, or carrying an annotation artifact
     (``_`` as in ``c_crasis``, or an embedded ``plus``), or whose first char is not an AGDT
     POS code. (A short postag missing only trailing ``-`` positions is padded, not dropped.)
  5. **no_word** — a sentence left with only punctuation after segmentation.
  6. **leaked** — a sentence whose NFC form tuple (full or punctuation-stripped) appears in the
     shipped model's training set (``training/data/full-{train,dev}.jsonl`` = AGDT + Gorman +
     Pedalion), the same form-tuple exclusion `agdt_ud_overlap` / build_papygreek_fold use.
     Expected ~0 for Byzantine verse; run anyway.

**Sentence segmentation.** The source is one continuous token stream (no sentence column); the
paper infers sentences from punctuation. This splits after a terminal punctuation token (a full
stop ``.``, ano teleia ``·``/``·``, Greek/Latin ``;``, or any compound punctuation token
containing one) or after a standalone ``+`` epigram marker — the ``+`` recognised by FORM
regardless of its (sometimes erroneous) gold POS — yielding verse/clause-sized sentences.
Non-terminal punctuation (comma, colon) stays inline. Segmentation only affects the context
window the model sees; the gold labels are per-token under gold tokenization.

Output (``--out``): ``dbbe-lingann-test.conllu`` + ``dbbe-lingann-fold.conllu.gz`` (the release
asset) + ``dbbe-lingann-fold-manifest.json`` (source commit, counts, per-reason exclusions).
Prints the sha256 of the gz asset for the ``_REMOTE`` DataSpec pin. DO NOT measure the pinned
row here — the integrator measures it once, sequentially, with the neural pipeline active.

Usage:
    python scripts/build_dbbe_fold.py [--repo DIR | --tsv FILE] [--out DIR]
                                      [--training-data training/data]
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import subprocess
import sys
import tempfile
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

# pyaegean's own AGDT->UD converters (the code that built the training labels).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "training"))
from agdt_ud import upos_from_xpos  # noqa: E402

from aegean.greek.treebank import _clean_lemma  # noqa: E402
from aegean.greek.udfeats import feats_from_xpos  # noqa: E402

# ByzantineGreekDatasets, pinned for reproducibility.
REPO_URL = "https://github.com/coswaele/ByzantineGreekDatasets.git"
REPO_COMMIT = "0b0133a97f8dd39190ffcc5ceeb3a6597ba5958d"
GOLD_FILE = "lingAnn_GS_medievalGreek.tsv"
# The repository README states the datasets are released under CC BY 4.0 (the underlying DBBE
# licence); its LICENSE file is a CC0 1.0 dedication. Both permit re-hosting; we attribute per
# CC BY 4.0 (the stricter of the two, and the DBBE-consistent choice). Recorded honestly.
LICENSE = (
    "CC BY 4.0 (ByzantineGreekDatasets README; repo LICENSE file is CC0 1.0) — "
    "Swaelens, De Vos & Lefever / DBBE, Ghent University"
)

# AGDT postag position alphabets (position 0 = POS). Used only to detect malformed tags.
_POS_CODES = set("nvadlgcrpmieux")
_TAG_CHARS = set("nvadlgcrpmieux") | set("123") | set("spd") | set("piarlft") | set(
    "isom"
) | set("ampe") | set("mfn") | set("ngdavl") | set("cs") | {"-"}

# Terminal punctuation: a punctuation token ending a sentence when it contains one of these.
_TERMINALS = {".", ";", "·", "·", "+"}  # full stop, semicolon, both ano-teleia codepoints, epigram +


def read_gold(path: Path) -> list[tuple[str, str, str]]:
    """Parse the 3-column TSV into ``(form, postag, lemma)`` triples (raw, unfiltered).

    A row that does not split into exactly three tab fields is returned with empty strings in
    the missing slots so the selection logic can count it as ``empty``/``malformed`` rather than
    the parse silently dropping it."""
    out: list[tuple[str, str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.split("\t")
        if len(parts) == 3:
            f, t, lem = parts
        else:
            f = parts[0] if parts else ""
            t = parts[1] if len(parts) > 1 else ""
            lem = parts[2] if len(parts) > 2 else ""
        out.append((unicodedata.normalize("NFC", f), t.strip(), unicodedata.normalize("NFC", lem)))
    return out


def _is_terminal(form: str, postag: str) -> bool:
    """True when a token closes a sentence.

    A standalone ``+`` is an epigram terminal by DBBE convention regardless of its
    (sometimes erroneous) gold POS, so it is recognised by FORM not tag. Otherwise a
    punctuation token closes a sentence when it carries a terminal mark."""
    if form == "+":
        return True
    if postag[:1] != "u":
        return False
    return any(ch in _TERMINALS for ch in form)


def token_reason(form: str, postag: str, lemma: str) -> str | None:
    """The exclusion reason for one token, or ``None`` when it is usable.

    Reasons (module docstring): ``empty``, ``illegible``, ``malformed_tag``,
    ``marker_glyph``."""
    if not form or not postag:
        return "empty"
    if postag[:1] == "u":
        # punctuation: reject illegibility fillers and alphabetic tokens mis-filed as punct
        if any(c in form for c in "()…") or "..." in form:
            return "illegible"
        if any(c.isalpha() for c in form):
            return "illegible"
        return None
    if any(c in form for c in "()…") or "..." in form:
        return "illegible"
    if len(postag) > 9 or "_" in postag or postag[0] not in _POS_CODES:
        return "malformed_tag"
    if any(c not in _TAG_CHARS for c in postag):
        return "malformed_tag"
    # mirror of the alphabetic-under-punct case: a non-linguistic marker glyph (no alphabetic
    # character) that the gold mis-filed under a WORD postag (e.g. + / ∙ / ※ / ᾽ as NOUN/CCONJ)
    if not any(c.isalpha() for c in form):
        return "marker_glyph"
    return None


def segment(rows: list[tuple[str, str, str]]) -> list[list[tuple[str, str, str]]]:
    """Split the token stream into sentences after each terminal punctuation token.

    Empty rows are treated as hard breaks. A trailing non-terminated run becomes its own
    sentence. Empty sentences are dropped here; punctuation-only sentences are dropped later."""
    sents: list[list[tuple[str, str, str]]] = []
    cur: list[tuple[str, str, str]] = []
    for form, postag, lemma in rows:
        if not form and not postag:  # blank/tab-only row → hard break
            if cur:
                sents.append(cur)
                cur = []
            continue
        cur.append((form, postag, lemma))
        if _is_terminal(form, postag):
            sents.append(cur)
            cur = []
    if cur:
        sents.append(cur)
    return sents


def xpos9(postag: str) -> str:
    """A clean token's raw AGDT postag padded to 9 positions (never truncated: callers pass
    only postags of length <= 9 that passed `token_reason`)."""
    return postag.ljust(9, "-")


def sentence_to_conllu(sent_id: str, toks: list[tuple[str, str, str]]) -> tuple[str, tuple[str, ...]]:
    """Convert one selected sentence to a CoNLL-U block (tagging-only: placeholder tree).

    Returns ``(block, forms)`` with ``forms`` the NFC form tuple (for the leakage check). UPOS
    comes from pyaegean's `upos_from_xpos` (no tree context: ``has_pnom_child=False`` so copular
    εἰμί stays VERB); XPOS is the padded 9-char postag; FEATS is `feats_from_xpos`; LEMMA is the
    cleaned gold lemma, or the surface form for punctuation (the training convention). HEAD/DEPREL
    are a placeholder chain (token 1 root, the rest attached to it) — never scored; evaluate with
    ``parse=False``."""
    forms = tuple(f for f, _, _ in toks)
    lines = [f"# sent_id = {sent_id}", f"# text = {' '.join(forms)}"]
    for i, (form, postag, lemma) in enumerate(toks, start=1):
        xpos = xpos9(postag)
        upos = upos_from_xpos(form, xpos, lemma=lemma)
        feats = feats_from_xpos(xpos)
        out_lemma = form if xpos[:1] == "u" else (_clean_lemma(lemma) or form)
        head = "0" if i == 1 else "1"
        deprel = "root" if i == 1 else "dep"
        lines.append("\t".join([str(i), form, out_lemma, upos, xpos, feats, head, deprel, "_", "_"]))
    return "\n".join(lines) + "\n", forms


# --- leakage key set (mirrors build_papygreek_fold / agdt_ud_overlap) -------------


def _has_punct(form: str) -> bool:
    return not any(ch.isalpha() or ch.isdigit() for ch in form)


def training_form_keys(training_dir: Path) -> set[tuple[str, ...]]:
    """NFC form tuples (full + punctuation-stripped) of the training + dev sentences."""
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
    if not keys:
        return False
    if forms in keys:
        return True
    stripped = tuple(t for t in forms if not _has_punct(t))
    return bool(stripped) and stripped in keys


# --- driver -----------------------------------------------------------------------


def _clone_gold(dest: Path) -> Path:
    """Clone the pinned ByzantineGreekDatasets repo and return the gold TSV path."""
    subprocess.run(
        ["git", "clone", "--filter=blob:none", "--no-checkout", REPO_URL, str(dest)],
        check=True,
    )
    subprocess.run(["git", "-C", str(dest), "checkout", REPO_COMMIT], check=True)
    return dest / GOLD_FILE


def build(gold_tsv: Path, training_dir: Path) -> tuple[str, dict[str, Any]]:
    """Parse, segment, select, convert; return ``(conllu_text, manifest)``."""
    rows = read_gold(gold_tsv)
    keys = training_form_keys(training_dir)

    reasons: Counter[str] = Counter()
    dropped_punct = 0  # noise punctuation tokens dropped in-sentence (no word context lost)
    dropped_marker = 0  # non-linguistic marker glyphs mis-tagged as words, dropped in-sentence
    blocks: list[str] = []
    n_tokens = 0
    n_sent_total = 0
    non_canonical_tags = 0  # kept tokens whose raw postag was not exactly 9 chars (padded)

    for idx, sent in enumerate(segment(rows)):
        n_sent_total += 1
        clean: list[tuple[str, str, str]] = []
        sent_bad: str | None = None
        for form, postag, lemma in sent:
            r = token_reason(form, postag, lemma)
            if r is None:
                clean.append((form, postag, lemma))
            elif postag[:1] == "u":
                dropped_punct += 1  # unusable punctuation → drop the token, keep the words
            elif r == "marker_glyph":
                dropped_marker += 1  # non-linguistic marker mis-tagged as a word → drop token
            else:
                sent_bad = r  # unusable WORD token → the sentence cannot be scored cleanly
                break
        if sent_bad:
            reasons[sent_bad] += 1
            continue
        if not any(t[:1] != "u" for _, t, _ in clean):  # punctuation-only after cleaning
            reasons["no_word"] += 1
            continue
        sent_id = f"dbbe:lingann@{idx}"
        block, forms = sentence_to_conllu(sent_id, clean)
        if is_leaked(forms, keys):
            reasons["leaked"] += 1
            continue
        for _, postag, _ in clean:
            if len(postag) != 9:
                non_canonical_tags += 1
        blocks.append(block)
        n_tokens += len(forms)

    conllu = ("\n".join(blocks) + "\n") if blocks else ""
    manifest: dict[str, Any] = {
        "purpose": "Byzantine book-epigram (DBBE) POS/morph/lemma tagging evaluation fold; "
                   "eval only, tagging-only (no dependency trees → no UAS/LAS)",
        "source_repo": "github.com/coswaele/ByzantineGreekDatasets",
        "source_commit": REPO_COMMIT,
        "source_file": GOLD_FILE,
        "license": LICENSE,
        "citation": "Swaelens, De Vos & Lefever (2025), Linguistic annotation of Byzantine "
                    "book epigrams, Language Resources and Evaluation 59(1):109-134, "
                    "doi:10.1007/s10579-023-09703-x",
        "register": "unedited (non-normalised, scribal-orthography) medieval Greek verse, "
                    "7th-15th c. (the DBBE's documented scope); lemmas standardised to "
                    "Attic dictionary headwords",
        "annotation_scheme": "AGDT 9-position positional postag (POS/morph) + lemma",
        "converter": "training/agdt_ud.upos_from_xpos + aegean.greek.udfeats.feats_from_xpos "
                     "(no tree context: has_pnom_child=False, so copular εἰμί scores VERB)",
        "leakage_reference": "training/data/full-{train,dev}.jsonl (AGDT+Gorman+Pedalion); "
                             "NFC form-tuple exclusion (full + punct-stripped)",
        "leakage_reference_present": bool(keys),
        "segmentation": "split after terminal punctuation (. ; · · +) and blank rows",
        "sentences_in_source": n_sent_total,
        "sentences_kept": len(blocks),
        "tokens_kept": n_tokens,
        "kept_tokens_with_padded_tag": non_canonical_tags,
        "dropped_noise_punct_tokens": dropped_punct,
        "dropped_marker_glyph_tokens": dropped_marker,
        "excluded_sentences": dict(sorted(reasons.items())),
    }
    return conllu, manifest


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", default=None,
                    help="existing checkout of ByzantineGreekDatasets (else clone the pinned commit)")
    ap.add_argument("--tsv", default=None,
                    help="path to lingAnn_GS_medievalGreek.tsv directly (overrides --repo)")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / "training" / "data"),
                    help="output directory for the conllu / gz / manifest")
    ap.add_argument("--training-data",
                    default=str(Path(__file__).resolve().parent.parent / "training" / "data"),
                    help="dir holding full-train.jsonl / full-dev.jsonl for the leakage check")
    args = ap.parse_args()

    tmp: tempfile.TemporaryDirectory[str] | None = None
    if args.tsv:
        gold = Path(args.tsv)
    elif args.repo:
        gold = Path(args.repo) / GOLD_FILE
    else:
        tmp = tempfile.TemporaryDirectory()
        gold = _clone_gold(Path(tmp.name) / "ByzantineGreekDatasets")
    try:
        conllu, manifest = build(gold, Path(args.training_data))
    finally:
        if tmp is not None:
            tmp.cleanup()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    conllu_path = out / "dbbe-lingann-test.conllu"
    gz_path = out / "dbbe-lingann-fold.conllu.gz"
    manifest_path = out / "dbbe-lingann-fold-manifest.json"
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
