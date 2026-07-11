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
  article, have none. The article is UniMorph's only lexical-gender signal (it tags a noun's
  gender nowhere else), so a gender-unambiguous article (``ὁ``/``ἡ``/``τό`` and their
  unambiguous case forms) is harvested (`_ARTICLE_GENDER`); an ambiguous article (``τοῦ`` =
  masc-or-neut, the duals) contributes no vote, and a common-gender cell (both ``ὁ`` and
  ``ἡ``) resolves the whole lemma to *no* article gender.

  The Wiktionary article is not always right: it ships several textbook **feminine
  second-declension -ος nouns** (``ἡ δοκός``, ``ἡ κιβωτός``, ``ἡ ψῆφος``; Smyth §230 N.) with
  a wrong masculine ``ὁ``. Two guards correct it (see `build_index`): (a) each noun lemma's
  gender is cross-checked against the **attested** gender in the AGDT treebank lexicon
  (`aegean.greek.treebank`); an attestation with two or more supporting tokens overrides a
  conflicting article, and a single attestation fills an absent article gender (one isolated
  treebank token is too weak to overturn the article, e.g. the ``-εύς`` masculine
  ``Παλληνεύς``). (b) A curated feminine ``-ος`` backstop (`_FEM_OS_NOUNS`, each verified
  against LSJ) genders the canonical feminine ``-ος`` nouns the treebank does not attest.
  Separately, a ``-μα`` noun whose paradigm shows the third-declension dental (``-ματ-``)
  stem, a genitive in ``-ματος``/``-ματων``, is filled ``neut`` (the ``-ματ-`` neuter class,
  Smyth §215).

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

# Canonical feminine second-declension (-ος) nouns (Smyth §230 N.): they take the article
# ``ἡ`` though the ending looks masculine, and UniMorph's Wiktionary annotation ships several
# with a wrong masculine ``ὁ``. Pinned feminine as the backstop for the lemma the attested
# treebank cross-check cannot vote on (see `resolve_noun_gender`). Each verified against LSJ:
# ἡ ὁδός (road), ἡ νῆσος (island), ἡ νόσος (disease), ἡ ψῆφος (pebble/vote), ἡ δοκός (beam),
# ἡ κιβωτός (chest/ark), ἡ γνάθος (jaw), ἡ ῥάβδος (rod), ἡ ἄμπελος (vine), ἡ βάσανος
# (touchstone), ἡ βίβλος (book), ἡ παρθένος (maiden), ἡ ἔρημος (desert, as substantive),
# ἡ τροφός (nurse). Applied only to NOUN lemmas (an ``-ος`` two-termination adjective keeps
# its explicit UniMorph gender tag).
_FEM_OS_NOUNS = frozenset(
    unicodedata.normalize("NFC", w)
    for w in (
        "ὁδός", "νῆσος", "νόσος", "ψῆφος", "δοκός", "κιβωτός", "γνάθος", "ῥάβδος",
        "ἄμπελος", "βάσανος", "βίβλος", "παρθένος", "ἔρημος", "τροφός",
    )
)

# The genitive of a third-declension dental (-ματ-) neuter (πνεῦμα → πνεύματος). The diagnostic
# of the -ματ- neuter class (Smyth §215), matched accent-blind (the accent shifts, the stem does
# not).
_MA_GEN_ENDINGS = ("ματος", "ματων")

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


def strip_accents(s: str) -> str:
    """Accent/breathing-stripped, length-stripped, NFC. For structural ending tests where the
    accent shifts across a paradigm (``ἀπόφθεγμα`` → ``ἀποφθέγματος``) but the stem does not."""
    nfd = unicodedata.normalize("NFD", strip_length(s))
    return unicodedata.normalize("NFC", "".join(c for c in nfd if not unicodedata.combining(c)))


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


def agdt_gender_map(
    lexicon: dict[str, list[dict[str, str]]],
) -> dict[str, tuple[str, int]]:
    """The attested NOUN gender per lemma from an AGDT-shaped form→analyses lexicon.

    Returns ``{lemma (NFC): (majority_gender, winning_vote_count)}``, counting every gendered
    NOUN analysis as one vote for its lemma. Only a lemma with a **strict plurality** gender is
    included; a tie carries no attested majority and is omitted. Order-independent, so the map
    is reproducible from the (commit-pinned) treebank lexicon."""
    votes: dict[str, collections.Counter[str]] = collections.defaultdict(collections.Counter)
    for entries in lexicon.values():
        for e in entries:
            if e.get("pos") == "NOUN" and "gender" in e and "lemma" in e:
                votes[unicodedata.normalize("NFC", e["lemma"])][e["gender"]] += 1
    out: dict[str, tuple[str, int]] = {}
    for lemma, counter in votes.items():
        ranked = counter.most_common()
        if len(ranked) == 1 or ranked[0][1] > ranked[1][1]:
            out[lemma] = (ranked[0][0], ranked[0][1])
    return out


def is_ma_neuter(lemma: str, forms: dict[tuple[str, str], set[str]]) -> bool:
    """Whether a ``-μα`` lemma is a third-declension dental (-ματ-) neuter.

    True when the lemma ends ``-μα`` and its paradigm shows the dental stem, a genitive in
    ``-ματος``/``-ματων`` (Smyth §215). ``forms`` maps ``(case, number)`` to the lemma's form
    keys. The dental genitive is the class diagnostic, so this never fires on a non-neuter
    ``-μα`` word (there is none in the class)."""
    if not lemma.endswith("μα"):
        return False
    gens = forms.get(("gen", "sg"), set()) | forms.get(("gen", "pl"), set())
    return any(strip_accents(g).endswith(_MA_GEN_ENDINGS) for g in gens)


def resolve_noun_gender(
    lemma: str,
    article_gender: str | None,
    attested: dict[str, tuple[str, int]],
    ma_neuter: bool,
) -> str | None:
    """The lexical gender for a noun lemma, reconciling the UniMorph article with attested and
    structural evidence.

    Precedence: (1) a dental ``-μα`` neuter is ``neut`` (structural, always correct for the
    class); (2) the attested treebank gender overrides a conflicting article only with two or
    more supporting tokens, or fills an absent article gender with a single token (an isolated
    treebank token is too weak to overturn UniMorph's own article signal); (3) the curated
    feminine ``-ος`` backstop; (4) the article gender (possibly ``None``)."""
    if ma_neuter:
        return "neut"
    att = attested.get(lemma)
    if att is not None:
        gender, count = att
        if article_gender is None or gender == article_gender or count >= 2:
            return gender
    if lemma in _FEM_OS_NOUNS:
        return "fem"
    return article_gender


def build_index(
    rows: list[tuple[str, str, str]],
    *,
    attested: dict[str, tuple[str, int]] | None = None,
) -> dict[str, list[dict[str, str]]]:
    """Assemble the ``{form: [analysis, ...]}`` index (AGDT record shape) from the TSV rows.

    Two passes: first harvest each noun-lemma's article gender and form paradigm; then resolve
    each noun's lexical gender through `resolve_noun_gender` (article, cross-checked against the
    ``attested`` treebank gender map from `agdt_gender_map`, plus the structural ``-μα`` and
    curated feminine ``-ος`` guards) and emit every cleaned form key → analysis. ``attested``
    defaults to empty, which reproduces the article-only behaviour."""
    attested = attested or {}
    parsed: list[tuple[str, str, str, str, str | None, list[str]]] = []
    lemma_gender_votes: dict[str, set[str]] = collections.defaultdict(set)
    lemma_forms: dict[str, dict[tuple[str, str], set[str]]] = collections.defaultdict(
        lambda: collections.defaultdict(set)
    )
    for lemma_raw, form_raw, feat_raw in rows:
        pos, case, number, tag_gender = parse_features(feat_raw)
        lemma = clean_lemma(lemma_raw)
        keys, art_genders = parse_form_field(form_raw)
        if not keys:
            continue
        if pos == "NOUN":
            lemma_gender_votes[lemma] |= art_genders
            for key in keys:
                lemma_forms[lemma][(case, number)].add(key)
        parsed.append((lemma, pos, case, number, tag_gender, keys))

    noun_gender: dict[str, str | None] = {}
    for lemma in set(lemma_gender_votes) | set(lemma_forms):
        votes = lemma_gender_votes.get(lemma, set())
        article_gender = next(iter(votes)) if len(votes) == 1 else None
        noun_gender[lemma] = resolve_noun_gender(
            lemma, article_gender, attested, is_ma_neuter(lemma, lemma_forms[lemma])
        )

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


def load_attested_genders(lexicon_path: str | None) -> dict[str, tuple[str, int]]:
    """The attested NOUN gender map (`agdt_gender_map`) from the AGDT treebank lexicon.

    With ``lexicon_path`` given, reads that JSON (a specific build or a test fixture, no
    network). Otherwise builds/loads the commit-pinned AGDT lexicon via
    `aegean.greek.treebank.build_lexicon` (cached after first use) and parses it. Both paths
    are deterministic, so the resulting map is reproducible."""
    if lexicon_path:
        lexicon = json.loads(Path(lexicon_path).read_text(encoding="utf-8"))
    else:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
        from aegean.greek import treebank

        lex_path = treebank.build_lexicon()
        lexicon = json.loads(Path(lex_path).read_text(encoding="utf-8"))
    return agdt_gender_map(lexicon)


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
    ap.add_argument(
        "--agdt-lexicon",
        default="",
        help="path to an AGDT treebank lexicon JSON for the attested-gender cross-check "
        "(default: build/load the commit-pinned one via aegean.greek.treebank)",
    )
    args = ap.parse_args()

    clone_dir = Path(args.clone_dir) if args.clone_dir else Path(tempfile.gettempdir()) / "unimorph-grc"
    repo = clone_or_reuse(args.source, clone_dir)
    commit = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True
    ).stdout.strip()

    attested = load_attested_genders(args.agdt_lexicon or None)
    print(f"attested noun genders (AGDT cross-check): {len(attested)} lemmas")
    rows = read_rows(repo / "grc")
    print(f"read {len(rows)} TSV rows from {repo / 'grc'} (commit {commit or 'unknown'})")
    index = build_index(rows, attested=attested)

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
