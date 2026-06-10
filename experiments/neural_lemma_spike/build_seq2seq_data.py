"""Build the form->lemma data bundle for the GreTa seq2seq lemmatizer.

The SOTA Ancient Greek lemmatizer (GreTa, arXiv:2410.12055) is a T5 seq2seq that
*generates* the lemma — which generalizes to unseen forms where edit-tree classification
caps out (~58%). We fine-tune the pretrained bowphs/GreTa on plain form->lemma pairs.

Train: UNIQUE (form, lemma) pairs from AGDT-train + genuinely-new, AGDT-disjoint treebanks
(Pedalion + Gorman's non-AGDT authors), deduped by sentence against ALL of AGDT so the dev
split can't leak. Dev: the identical AGDT held-out tokens (so the number stays comparable to
the edit-tree runs). Forms/lemmas are NFC (case preserved); gold lemmas are _clean_lemma'd.
"""
from __future__ import annotations

import json
import pathlib
import re
import unicodedata
from collections import Counter

from aegean.greek import heldout, syntax
from aegean.greek.morphology import _bare
from aegean.greek.treebank import _clean_lemma

HOLDOUT = 0.1
GOLD_UPSAMPLE = 3  # repeat treebank (AGDT-convention) pairs so they stay the majority signal
OUT = pathlib.Path(__file__).parent / "data"
TMP = pathlib.Path(r"C:\Users\Ryan.Pavlicek\AppData\Local\Temp\multitreebank")
EXTRA_DIRS = [TMP / "pedalion", TMP / "gorman"]
WIKT = pathlib.Path(r"C:\Users\Ryan.Pavlicek\AppData\Local\Temp\wiktionary\AncientGreek.jsonl")

_WORD = re.compile(r"<word\b[^>]*>")


def _attr(tag: str, name: str) -> str | None:
    m = re.search(name + r"=(['\"])(.*?)\1", tag)
    return m.group(2) if m else None


def parse_treebank(path: pathlib.Path):
    text = path.read_text(encoding="utf-8", errors="replace")
    for chunk in re.split(r"<sentence\b", text)[1:]:
        chunk = chunk.split("</sentence>")[0]
        toks = []
        for wm in _WORD.finditer(chunk):
            tag = wm.group(0)
            form, lemma = _attr(tag, "form"), _attr(tag, "lemma")
            if form and lemma and not form.startswith("["):
                toks.append((form, lemma))
        if toks:
            yield toks


def _nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def _fp(forms) -> tuple[str, ...]:
    return tuple(_bare(f).lower() for f in forms)


_GREEK = re.compile(r"[Ͱ-Ͽἀ-῿]")  # Greek + Greek Extended


def _ok(form: str, lemma: str) -> bool:
    return (bool(form) and bool(lemma) and len(form) <= 40 and len(lemma) <= 40
            and _GREEK.search(form) is not None)  # word-forms only (punct/numbers aren't scored)


# --- Wiktionary (kaikki Ancient-Greek dump) -------------------------------------------
# Full inflection paradigms add the morphological breadth treebanks lack — the lever for
# unseen-form generalization. CC BY-SA 4.0, compatible with the shipped CC BY-SA model.

_LEN = {0x0304, 0x0306}  # combining macron + breve: vowel-length marks AGDT does not write


def _strip_len(s: str) -> str:
    nfd = unicodedata.normalize("NFD", s)
    return unicodedata.normalize("NFC", "".join(c for c in nfd if ord(c) not in _LEN))


# forms[] tags that aren't inflected Greek surface forms we want as training targets
_SKIP_FORM_TAGS = {"romanization", "transliteration", "inflection-template",
                   "table-tags", "class", "canonical"}
_LATIN = re.compile(r"[A-Za-z]")
_MAX_FORMS_PER_LEMMA = 24  # principal paradigm cells; trims the rare/poetic long tail


def _wikt_ok(form: str) -> bool:
    return bool(form) and " " not in form and "*" not in form and _LATIN.search(form) is None


def wiktionary_pairs(path: pathlib.Path, dev_unseen: set[str]):
    """Yield normalized (form, lemma) pairs from the kaikki Ancient-Greek dump.

    Two signals: a lemma page's ``forms[]`` (the full paradigm) paired with the page
    ``word``; and a non-lemma page's ``senses[].form_of[].word`` (the lemma it inflects).
    Vowel-length marks (U+0304/U+0306), which AGDT does not write, are stripped from the
    surface form (codepoint-targeted, so accents/breathings survive); romanizations,
    reconstructions, Latin, multiword forms, and dev-UNSEEN forms are dropped.
    """
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("lang_code") != "grc":
                continue
            word = entry.get("word") or ""
            if not word or word.startswith("*"):  # Reconstruction: namespace
                continue

            # Strategy 1: lemma page -> its paradigm forms.
            lemma = _clean_lemma(_nfc(word))
            kept = 0
            for fo in entry.get("forms", []):
                if kept >= _MAX_FORMS_PER_LEMMA:
                    break
                if set(fo.get("tags", ())) & _SKIP_FORM_TAGS:
                    continue
                form = _strip_len(_nfc(fo.get("form") or ""))
                if not _wikt_ok(form) or _bare(form).lower() in dev_unseen:
                    continue
                if _ok(form, lemma):
                    yield form, lemma
                    kept += 1

            # Strategy 2: non-lemma page -> the lemma it is a form of (already length-clean).
            w_form = _nfc(word)
            if _wikt_ok(w_form) and _bare(w_form).lower() not in dev_unseen:
                for sense in entry.get("senses", []):
                    for fof in sense.get("form_of", ()):
                        tgt = fof.get("word") if isinstance(fof, dict) else fof
                        if tgt:
                            tlemma = _clean_lemma(_nfc(tgt))
                            if _ok(w_form, tlemma):
                                yield w_form, tlemma


def main() -> None:
    trees = syntax.load_gold_trees()
    cut = max(1, int(len(trees) * (1 - HOLDOUT)))
    agdt_fps = {_fp([t.form for t in tr.tokens]) for tr in trees}

    # The held-out dev split defines seen/unseen against AGDT-train. Any *supplementary*
    # source (extra treebanks or the dictionary) must not introduce a dev-UNSEEN form, or
    # the model would train on it and the unseen number would stop measuring generalization.
    # The sentence-fingerprint guard below can't catch this for isolated forms, so guard
    # every supplementary token explicitly.
    sp = heldout.split_tokens(holdout=HOLDOUT)
    dev_unseen = {_bare(tk.form).lower()
                  for sent in sp.sentences for tk in sent
                  if tk.scored and not tk.seen}

    # Gold = treebank pairs (AGDT-train + AGDT-disjoint Pedalion/Gorman). These carry the
    # AGDT lemma conventions the dev set is scored against, so they are upsampled to stay the
    # majority of the training signal; Wiktionary supplies breadth, not the output convention.
    gold: set[tuple[str, str]] = set()
    src: Counter[str] = Counter()
    for tr in trees[:cut]:
        for t in tr.tokens:
            f, lm = _nfc(t.form), _clean_lemma(t.lemma)
            if _ok(f, lm) and (f, lm) not in gold:
                gold.add((f, lm))
                src["AGDT"] += 1
    skipped = leaked = 0
    for d in EXTRA_DIRS:
        for path in sorted(d.glob("*.xml")):
            for toks in parse_treebank(path):
                if _fp([f for f, _ in toks]) in agdt_fps:
                    skipped += 1
                    continue
                for f, lm in toks:
                    nf, nl = _nfc(f), _clean_lemma(lm)
                    if _bare(nf).lower() in dev_unseen:
                        leaked += 1
                        continue
                    if _ok(nf, nl) and (nf, nl) not in gold:
                        gold.add((nf, nl))
                        src[path.parent.name] += 1

    # Wiktionary = breadth source, deduped against gold (gold wins on overlap).
    wikt: set[tuple[str, str]] = set()
    if WIKT.exists():
        for f, lm in wiktionary_pairs(WIKT, dev_unseen):
            if (f, lm) not in gold and (f, lm) not in wikt:
                wikt.add((f, lm))
                src["wiktionary"] += 1
    else:
        print(f"(no Wiktionary dump at {WIKT} — skipping that source)")

    with (OUT / "train.jsonl").open("w", encoding="utf-8") as fh:
        for _ in range(GOLD_UPSAMPLE):
            for f, lm in sorted(gold):
                fh.write(json.dumps({"form": f, "lemma": lm, "src": "treebank"}, ensure_ascii=False) + "\n")
        for f, lm in sorted(wikt):
            fh.write(json.dumps({"form": f, "lemma": lm, "src": "wikt"}, ensure_ascii=False) + "\n")

    n_dev = n_un = 0
    with (OUT / "dev.jsonl").open("w", encoding="utf-8") as fh:
        for sent in sp.sentences:
            for tk in sent:
                fh.write(json.dumps({
                    "form": _nfc(tk.form), "lemma": tk.lemma,
                    "seen": tk.seen, "scored": tk.scored,
                }, ensure_ascii=False) + "\n")
                if tk.scored:
                    n_dev += 1
                    n_un += int(not tk.seen)

    g, w = len(gold), len(wikt)
    rows = g * GOLD_UPSAMPLE + w
    print(f"train rows: {rows}  =  gold {g} x{GOLD_UPSAMPLE} ({g * GOLD_UPSAMPLE}) + wiktionary {w}  "
          f"(gold share {g * GOLD_UPSAMPLE / rows:.0%})")
    print(f"  unique pairs by source: {dict(src)}")
    print(f"  dropped: {skipped} overlap sentences; {leaked} supplementary tokens hitting dev-unseen")
    print(f"dev tokens (per-token): scored {n_dev}, unseen {n_un}")


if __name__ == "__main__":
    main()
