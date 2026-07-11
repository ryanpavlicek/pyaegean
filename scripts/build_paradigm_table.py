"""Build the UniMorph Ancient Greek paradigm table (repo-only; not shipped in the wheel).

Source: github.com/unimorph/grc (**CC BY-SA 3.0**, derived from Wiktionary inflection
tables). The ``grc`` file is a 3-column TSV — ``lemma <TAB> form <TAB> features`` — where
``features`` is a UniMorph feature bundle (``N;NOM;SG``, ``ADJ;GEN;PL;FEM``). The corpus is
purely **nominal**: the only parts of speech are ``N`` (nouns) and ``ADJ`` (adjectives);
there are no verbs. It supplies exactly the irregular / third-declension / heteroclite
nominal paradigms the rule engine cannot reach (``γυνή → γυναικός``, ``πατήρ → πατράσι``,
``ὕδωρ → ὕδατος``, ``κόλαξ → κόλακος``).

Two data caveats the avenues audit flagged, both cleaned here:

* **The form field carries the definite article** (``ὁ βοηθός``, ``αἱ γυναῖκες``, and the
  common-gender ``ὁ, ἡ ἔλαφος`` / ``ὁ/ἡ σῦς``). The leading run of article tokens is
  stripped (the exact set is `_ARTICLE`, documented below); vocatives, which never take the
  article, have none. The article is also the ONLY signal of a noun's lexical gender —
  UniMorph tags a noun's gender nowhere else — so a gender-unambiguous article
  (``ὁ``/``ἡ``/``τό`` and their unambiguous case forms) is harvested to gender the noun
  (`_ARTICLE_GENDER`); an ambiguous article (``τοῦ`` = masc-or-neut, the duals) contributes
  no vote, and a common-gender cell (both ``ὁ`` and ``ἡ``) resolves the whole lemma to *no*
  gender rather than guess.

* **Forms carry metrical breve/macron length marks** (``ᾰ``/``ᾱ``, prosodic notation absent
  from real polytonic text). They are stripped with the project's established normalization
  — NFD → drop the combining length marks U+0304 (macron) and U+0306 (breve) → NFC — which
  keeps every accent and breathing (the same NFD/filter-combining/NFC shape as
  ``greek.normalize.strip_diacritics`` and ``treebank._strip_accents``, restricted to the
  two length marks).

Additional cleaning: multi-variant cells (``γυναῖκες / γυναί``, ``σπέος, σπεῖος``) are split
into their attested variants on ``/`` and ``,``; parenthesised optional letters
(``γυναιξί(ν)``) are expanded to both spellings (``γυναιξί`` and ``γυναιξίν``); keys are
lower-cased NFC (accents kept), matching the AGDT lexicon's ``_norm``.

Output: a gzip-compressed JSON object ``{form: [{lemma, pos, case, number, gender?}, ...]}``
— the SAME record shape as the AGDT treebank lexicon (``greek/treebank.py``), so the paradigm
backend and the treebank backend serve byte-identical analysis dicts and the consumer
(``greek.morphology.Analysis`` / ``lemmatize``) stays uniform. Hosted as the ``grc-paradigms``
release asset and fetched lazily by ``greek.paradigms.use_paradigms()``; never bundled
(ShareAlike + wheel size).

Feature-mapping table (UniMorph tag → project convention, matching ``treebank.decode_postag``):

    part of speech   N → NOUN     ADJ → ADJ
    case             NOM → nom    GEN → gen    DAT → dat    ACC → acc    VOC → voc
    number           SG → sg      PL → pl      DU → du
    gender           MASC → masc  FEM → fem    NEUT → neut

(No tense/voice/mood/person/degree: the corpus is nominal, so those AGDT feature fields never
appear. Any UniMorph tag outside the tables above is a hard error — a future data revision
that adds verbs must extend the map deliberately, not drop tags silently.)

Usage::

    python scripts/build_paradigm_table.py                    # clone to temp, build the asset
    python scripts/build_paradigm_table.py <unimorph-grc>     # reuse an existing clone
    python scripts/build_paradigm_table.py -o out.json.gz --clone-dir /path/to/clone
"""

from __future__ import annotations

import argparse
import collections
import gzip
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path

_GRC_REPO = "https://github.com/unimorph/grc.git"

# --- UniMorph feature bundle → project (AGDT) convention ----------------------
_POS_MAP = {"N": "NOUN", "ADJ": "ADJ"}
_CASE_MAP = {"NOM": "nom", "GEN": "gen", "DAT": "dat", "ACC": "acc", "VOC": "voc"}
_NUMBER_MAP = {"SG": "sg", "PL": "pl", "DU": "du"}
_GENDER_MAP = {"MASC": "masc", "FEM": "fem", "NEUT": "neut"}

# --- length-mark stripping (the two metrical combining marks only) ------------
_MACRON = "̄"
_BREVE = "̆"
_ACUTE = "́"
_GRAVE = "̀"


def strip_length(s: str) -> str:
    """Drop the metrical breve/macron combining marks, keeping accents/breathings; NFC."""
    nfd = unicodedata.normalize("NFD", s)
    kept = "".join(c for c in nfd if c not in (_MACRON, _BREVE))
    return unicodedata.normalize("NFC", kept)


def _fold(tok: str) -> str:
    """Article-match key: length-stripped, grave→acute (running-text notation), lower NFC."""
    nfd = unicodedata.normalize("NFD", strip_length(tok)).replace(_GRAVE, _ACUTE)
    return unicodedata.normalize("NFC", nfd).lower()


# --- the definite article (Attic + the Doric/epic forms present in UniMorph grc) ----
# Written in citation accent (`_fold` maps running-text graves onto them). A leading run of
# these tokens is the article the source prepends to each articled cell; it is stripped.
_ARTICLE_MASC = {"ὁ", "οἱ", "τόν", "τούς", "τοί"}
_ARTICLE_FEM = {"ἡ", "αἱ", "τῆς", "τῇ", "τήν", "τάς", "ταῖς",
                "ἁ", "ταί", "τᾶς", "τᾶν", "τᾷ", "τάν"}
_ARTICLE_NEUT = {"τό", "τά"}
# Case-syncretic articles that do NOT fix a gender (masc-or-neut genitive/dative, the duals):
# in the set so they are stripped, but they contribute no gender vote.
_ARTICLE_AMBIG = {"τοῦ", "τῷ", "τῶν", "τοῖς", "τώ", "τοῖν"}

_ARTICLE_GENDER: dict[str, str] = {}
for _w in _ARTICLE_MASC:
    _ARTICLE_GENDER[_fold(_w)] = "masc"
for _w in _ARTICLE_FEM:
    _ARTICLE_GENDER[_fold(_w)] = "fem"
for _w in _ARTICLE_NEUT:
    _ARTICLE_GENDER[_fold(_w)] = "neut"
_ARTICLE = {_fold(w) for w in (_ARTICLE_MASC | _ARTICLE_FEM | _ARTICLE_NEUT | _ARTICLE_AMBIG)}

_GREEK_RE = re.compile(r"[Ͱ-Ͽἀ-῿]")
_PUNCT_STRIP = " ,.··;:"


def _is_article(tok: str) -> bool:
    """Whether a single token (possibly a slash-joined common-gender article) is the article."""
    parts = _fold(tok.rstrip(",")).split("/")
    return bool(parts) and all(p in _ARTICLE for p in parts)


def _article_genders(tok: str) -> set[str]:
    """The gender(s) an article token unambiguously encodes (empty when syncretic)."""
    gs = {_ARTICLE_GENDER.get(p) for p in _fold(tok.rstrip(",")).split("/")}
    gs.discard(None)
    return gs  # type: ignore[return-value]


def _expand_parens(v: str) -> set[str]:
    """A form with a parenthesised optional letter → both spellings (``γυναιξί(ν)`` →
    ``{γυναιξί, γυναιξίν}``); a form without parentheses → just itself."""
    if "(" not in v:
        return {v}
    without = re.sub(r"\([^)]*\)", "", v)
    inline = re.sub(r"\(([^)]*)\)", r"\1", v)
    return {without, inline}


def parse_form_field(field: str) -> tuple[list[str], set[str]]:
    """Clean one FORM field into ``(form_keys, article_genders)``.

    Strips the leading article run (harvesting its gender votes), splits the remaining
    variant forms on ``/`` and ``,``, expands parenthesised optionals, and returns
    lower-cased NFC keys with the length marks removed."""
    field = strip_length(field)
    toks = field.split()
    i = 0
    genders: set[str] = set()
    while i < len(toks) and _is_article(toks[i]):
        genders |= _article_genders(toks[i])
        i += 1
    region = " ".join(toks[i:])
    keys: list[str] = []
    for variant in re.split(r"\s*/\s*|,\s*", region):
        variant = variant.strip(_PUNCT_STRIP)
        if not variant:
            continue
        for spelling in _expand_parens(variant):
            key = unicodedata.normalize("NFC", spelling.strip(_PUNCT_STRIP)).lower()
            # A clean single Greek word only (drop any residue with an interior space or no
            # Greek letter — the rare epic junk like a bare diaeresis fragment).
            if key and " " not in key and _GREEK_RE.search(key):
                keys.append(key)
    return keys, genders


def clean_lemma(lemma: str) -> str:
    """The citation lemma: length-marks dropped, NFC, case preserved."""
    return strip_length(unicodedata.normalize("NFC", lemma).strip())


def parse_features(feat: str) -> tuple[str, str, str, str | None]:
    """A UniMorph bundle → ``(pos, case, number, gender_from_tag)`` in project convention.

    Raises on any unmapped tag so a future data revision cannot silently drop features."""
    parts = feat.split(";")
    pos = _POS_MAP.get(parts[0])
    if pos is None:
        raise ValueError(f"unmapped UniMorph POS in {feat!r}")
    case = number = None
    gender: str | None = None
    for tag in parts[1:]:
        if tag in _CASE_MAP:
            case = _CASE_MAP[tag]
        elif tag in _NUMBER_MAP:
            number = _NUMBER_MAP[tag]
        elif tag in _GENDER_MAP:
            gender = _GENDER_MAP[tag]
        else:
            raise ValueError(f"unmapped UniMorph tag {tag!r} in {feat!r}")
    if case is None or number is None:
        raise ValueError(f"missing case/number in {feat!r}")
    return pos, case, number, gender


def read_rows(grc_file: Path) -> list[tuple[str, str, str]]:
    """The 3-column ``lemma, form, features`` rows (blank paradigm-separator lines dropped)."""
    rows: list[tuple[str, str, str]] = []
    for line in grc_file.read_text(encoding="utf-8").split("\n"):
        parts = line.split("\t")
        if len(parts) == 3 and parts[0] and parts[1] and parts[2]:
            rows.append((parts[0], parts[1], parts[2]))
    return rows


def build_index(rows: list[tuple[str, str, str]]) -> dict[str, list[dict[str, str]]]:
    """Assemble the ``{form: [analysis, ...]}`` index (AGDT record shape) from the TSV rows.

    Two passes: first harvest each noun-lemma's gender from its articles (a noun's gender is
    constant across its paradigm, so the votes are unioned per lemma and resolved to the sole
    unambiguous gender, else left unset); then emit every cleaned form key → analysis."""
    parsed: list[tuple[str, str, str, str, str | None, list[str]]] = []
    lemma_gender_votes: dict[str, set[str]] = collections.defaultdict(set)
    for lemma_raw, form_raw, feat_raw in rows:
        pos, case, number, tag_gender = parse_features(feat_raw)
        lemma = clean_lemma(lemma_raw)
        keys, art_genders = parse_form_field(form_raw)
        if not keys:
            continue
        if pos == "NOUN":
            lemma_gender_votes[lemma] |= art_genders
        parsed.append((lemma, pos, case, number, tag_gender, keys))

    noun_gender: dict[str, str | None] = {}
    for lemma, votes in lemma_gender_votes.items():
        noun_gender[lemma] = next(iter(votes)) if len(votes) == 1 else None

    index: dict[str, list[dict[str, str]]] = {}
    for lemma, pos, case, number, tag_gender, keys in parsed:
        gender = tag_gender if pos == "ADJ" else noun_gender.get(lemma)
        analysis: dict[str, str] = {"lemma": lemma, "pos": pos, "case": case, "number": number}
        if gender:
            analysis["gender"] = gender
        for key in keys:
            bucket = index.setdefault(key, [])
            if analysis not in bucket:
                bucket.append(analysis)
    return {k: index[k] for k in sorted(index)}


def clone_or_reuse(source: str | None, clone_dir: Path) -> Path:
    if source:
        repo = Path(source)
        if not (repo / "grc").exists():
            raise SystemExit(f"{source!r} is not a unimorph/grc clone (no 'grc' file)")
        return repo
    if (clone_dir / "grc").exists():
        print(f"reusing existing clone at {clone_dir}")
        return clone_dir
    print(f"cloning {_GRC_REPO} into {clone_dir} ...")
    subprocess.run(["git", "clone", "--depth", "1", _GRC_REPO, str(clone_dir)], check=True)
    return clone_dir


def main() -> int:
    ap = argparse.ArgumentParser(description="Build the UniMorph grc paradigm table.")
    ap.add_argument("source", nargs="?", help="path to an existing unimorph/grc clone")
    ap.add_argument("-o", "--output", default="grc-paradigms.json.gz")
    ap.add_argument("--clone-dir", default="", help="where to clone when no source is given")
    args = ap.parse_args()

    clone_dir = Path(args.clone_dir) if args.clone_dir else Path(tempfile.gettempdir()) / "unimorph-grc"
    repo = clone_or_reuse(args.source, clone_dir)
    commit = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True
    ).stdout.strip()

    rows = read_rows(repo / "grc")
    print(f"read {len(rows)} TSV rows from {repo / 'grc'} (commit {commit or 'unknown'})")
    index = build_index(rows)

    out = Path(args.output)
    payload = json.dumps(index, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    # A REPRODUCIBLE gzip so the pinned sha256 matches any rebuild: no embedded mtime (the
    # default is wall-clock) and an explicit empty filename (``GzipFile`` otherwise embeds the
    # output file's own name from ``fileobj.name``, so the sha would vary with ``-o``).
    with open(out, "wb") as raw, gzip.GzipFile(
        filename="", mode="wb", fileobj=raw, mtime=0
    ) as f:
        f.write(payload.encode("utf-8"))

    lemmas = {a["lemma"] for al in index.values() for a in al}
    ambiguous = sum(1 for al in index.values() if len({a["lemma"] for a in al}) > 1)
    sha = hashlib.sha256(out.read_bytes()).hexdigest()
    print(f"forms (keys):        {len(index)}")
    print(f"distinct lemmas:     {len(lemmas)}")
    print(f"ambiguous forms:     {ambiguous} (map to >1 lemma)")
    print(f"analyses total:      {sum(len(al) for al in index.values())}")
    print(f"asset:               {out} ({out.stat().st_size} bytes gzip)")
    print(f"uncompressed JSON:   {len(payload.encode('utf-8'))} bytes")
    print(f"sha256:              {sha}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
    raise SystemExit(main())
