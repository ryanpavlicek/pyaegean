"""Rule-based Ancient Greek morphological analysis.

Given an inflected form, `analyze` returns the **candidate** morphological
analyses implied by its ending — part of speech plus the relevant features
(case, number, gender for nominals; tense, voice, mood, person, number for
verbs) — together with a reconstructed lemma. Greek inflection is heavily
ambiguous (``-ων`` is the genitive plural of *every* declension and gender;
``-α`` is a first-declension or neuter-plural or third-declension ending), so a
form legitimately yields several analyses; the caller disambiguates with
context.

This is a **baseline** engine, high-precision on the *regular* paradigms it
encodes — the article and pronouns (closed classes), the first/second
declensions and common third-declension endings, and **thematic** verbs in the
present, imperfect, future and (sigmatic) aorist indicative, plus the common
infinitives and the mediopassive participle. Its limits are well-defined:

- **Accent is not restored** on a rule-reconstructed lemma (accent recession is
  not derivable from the ending alone); when the bundled seed lexicon knows the
  form, its correctly-accented lemma is used instead, otherwise the lemma is the
  unaccented reconstructed stem and `Analysis.lemma_certain` is ``False``.
- Athematic, contract, irregular and suppletive forms (``εἶπον`` → ``λέγω``) are
  outside a purely rule-based reach — those need the treebank-derived lexicon
  (see `aegean.greek.use_treebank`).

Feature analyses are **exploratory** for ambiguous forms: trust the closed
classes and the feature set, treat a single auto-picked reading with care.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from functools import lru_cache

# Seed tier only: the rule engine's lemma hints must not depend on backend state (the
# trained backends call back into analyze(), and _rule_analyze's cache must stay valid).
from .lemmatize import seed_lemma_verbose
from .pos import _LEXICON  # closed-class lexicon (article, prepositions, …)

# --- feature inventories -----------------------------------------------------

CASES = ("nom", "gen", "dat", "acc", "voc")
NUMBERS = ("sg", "pl")
GENDERS = ("masc", "fem", "neut")
TENSES = ("pres", "impf", "fut", "aor")
VOICES = ("act", "mp")
MOODS = ("ind", "inf", "part")
PERSONS = ("1", "2", "3")


@dataclass(frozen=True, slots=True)
class Analysis:
    """One candidate morphological reading of a form."""

    lemma: str
    pos: str
    case: str | None = None
    number: str | None = None
    gender: str | None = None
    tense: str | None = None
    voice: str | None = None
    mood: str | None = None
    person: str | None = None
    degree: str | None = None
    lemma_certain: bool = True

    def features(self) -> dict[str, str]:
        """The non-empty morphological features, in a stable order."""
        order = (
            "case", "number", "gender", "tense", "voice", "mood", "person", "degree",
        )
        out: dict[str, str] = {}
        for name in order:
            value = getattr(self, name)
            if value is not None:
                out[name] = value
        return out

    def __str__(self) -> str:
        feats = " ".join(self.features().values())
        return f"{self.lemma} [{self.pos}{' ' + feats if feats else ''}]"

    def _repr_html_(self) -> str:
        """Rich rendering in Jupyter/Colab (plain ``repr`` everywhere else)."""
        from ..core._html import badge, card, esc

        lemma = esc(self.lemma)
        if not self.lemma_certain:
            lemma += " " + badge("reconstructed", color="#b8860b")
        feats = self.features()
        feat_html = (
            " ".join(
                "<span style='background:#eef;border-radius:3px;padding:1px 5px;"
                f"margin-right:3px'>{esc(k)}=<strong>{esc(v)}</strong></span>"
                for k, v in feats.items()
            )
            or "<em>—</em>"
        )
        title = f"{lemma} <span style='color:#888;font-weight:400'>· {esc(self.pos)}</span>"
        return card(title, feat_html)


# --- helpers -----------------------------------------------------------------


def _bare(word: str) -> str:
    """Lowercase, diacritic-stripped form (final ς folded to σ) for ending match."""
    nfd = unicodedata.normalize("NFD", word).lower()
    stripped = "".join(c for c in nfd if not unicodedata.combining(c))
    return stripped.replace("ς", "σ")


def _closed_key(word: str) -> str:
    """Normalisation matching the closed-class lexicon keys in `.pos`."""
    grave, acute = "̀", "́"
    nfc = unicodedata.normalize("NFC", word).lower()
    nfd = unicodedata.normalize("NFD", nfc).replace(grave, acute)
    return unicodedata.normalize("NFC", nfd)


# --- nominal endings ---------------------------------------------------------
# Each entry: bare ending → (declension, list of (case, number, gender), the
# bare nominative-singular ending used to rebuild the lemma; None = the lemma is
# not recoverable from the ending alone, e.g. most of the third declension).

_F = "fem"
_M = "masc"
_N = "neut"

# Endings are matched against the *bare* form, so final sigma is written σ.
_NOMINAL: tuple[tuple[str, tuple[tuple[str, str, str], ...], str | None], ...] = (
    # --- second declension (-ος masc/fem, -ον neut) ---
    ("ουσ", (("acc", "pl", _M), ("acc", "pl", _F)), "ος"),
    ("οισ", (("dat", "pl", _M), ("dat", "pl", _F), ("dat", "pl", _N)), "ος"),
    ("οι", (("nom", "pl", _M), ("nom", "pl", _F)), "ος"),
    ("ον", (("acc", "sg", _M), ("acc", "sg", _F),
            ("nom", "sg", _N), ("acc", "sg", _N), ("voc", "sg", _N)), "ος"),
    ("ου", (("gen", "sg", _M), ("gen", "sg", _F), ("gen", "sg", _N)), "ος"),
    ("οσ", (("nom", "sg", _M), ("nom", "sg", _F)), "ος"),
    ("ω", (("dat", "sg", _M), ("dat", "sg", _F), ("dat", "sg", _N)), "ος"),
    # --- first declension (-η/-α feminine; -ης/-ας masculine) ---
    ("αισ", (("dat", "pl", _F),), "η"),
    ("ων", (("gen", "pl", _M), ("gen", "pl", _F), ("gen", "pl", _N)), None),
    ("αι", (("nom", "pl", _F),), "η"),
    ("ασ", (("acc", "pl", _F), ("gen", "sg", _M)), None),
    ("ησ", (("gen", "sg", _F), ("nom", "sg", _M)), None),
    ("ην", (("acc", "sg", _F),), "η"),
    ("αν", (("acc", "sg", _F),), "α"),
    ("η", (("nom", "sg", _F), ("dat", "sg", _F), ("voc", "sg", _F)), "η"),
    ("α", (("nom", "sg", _F), ("dat", "sg", _F), ("voc", "sg", _F),
           ("nom", "pl", _N), ("acc", "pl", _N)), None),
    # --- common third-declension endings (lemma not rule-recoverable) ---
    ("σιν", (("dat", "pl", _M), ("dat", "pl", _F), ("dat", "pl", _N)), None),
    ("σι", (("dat", "pl", _M), ("dat", "pl", _F), ("dat", "pl", _N)), None),
    ("εσ", (("nom", "pl", _M), ("nom", "pl", _F)), None),
    ("ι", (("dat", "sg", _M), ("dat", "sg", _F), ("dat", "sg", _N)), None),
)


# Endings whose dative singular (ῳ/ῃ/ᾳ) is told apart from the other readings
# only by the iota subscript, which bare-stripping discards.
_SUBSCRIPT_ENDINGS = {"ω", "η", "α"}


def _nominal(word: str) -> list[Analysis]:
    bare = _bare(word)
    has_subscript = "ͅ" in unicodedata.normalize("NFD", word)
    seed_lemma, seed_known = seed_lemma_verbose(word)
    matches = [
        (ending, feats, nom_ending)
        for ending, feats, nom_ending in _NOMINAL
        if bare.endswith(ending) and len(bare) > len(ending)
    ]
    if not matches:
        return []
    longest = max(len(e) for e, _, _ in matches)
    out: list[Analysis] = []
    for ending, feats, nom_ending in matches:
        if len(ending) != longest:
            continue  # only the longest matching ending(s) apply
        if seed_known:
            lemma, certain = seed_lemma, True
        elif nom_ending is not None:
            lemma, certain = bare[: -len(ending)] + nom_ending, False
        else:
            lemma, certain = bare, False  # third declension: stem ≠ nominative
        for case, number, gender in feats:
            # An iota subscript marks the dative singular (ῳ/ῃ/ᾳ); without it
            # these bare vowels are nominative/vocative/plural instead.
            if ending in _SUBSCRIPT_ENDINGS and (case == "dat") != has_subscript:
                continue
            out.append(
                Analysis(
                    lemma=lemma, pos="NOUN", case=case, number=number,
                    gender=gender, lemma_certain=certain,
                )
            )
    return out


# --- verbal endings ----------------------------------------------------------
# Each entry: bare ending → (tense, voice, mood, person, number, augmented?).
# ``augmented`` strips a leading augment when rebuilding the present-stem lemma.

@dataclass(frozen=True, slots=True)
class _VerbEnding:
    ending: str
    tense: str
    voice: str
    mood: str
    person: str | None = None
    number: str | None = None
    augment: bool = False  # strip a leading augment when rebuilding the lemma


_VERBAL: tuple[_VerbEnding, ...] = (
    # present active indicative
    _VerbEnding("ομεν", "pres", "act", "ind", "1", "pl"),
    _VerbEnding("ουσιν", "pres", "act", "ind", "3", "pl"),
    _VerbEnding("ουσι", "pres", "act", "ind", "3", "pl"),
    _VerbEnding("ετε", "pres", "act", "ind", "2", "pl"),
    _VerbEnding("εισ", "pres", "act", "ind", "2", "sg"),
    _VerbEnding("ει", "pres", "act", "ind", "3", "sg"),
    _VerbEnding("ω", "pres", "act", "ind", "1", "sg"),
    # present mediopassive indicative
    _VerbEnding("ομεθα", "pres", "mp", "ind", "1", "pl"),
    _VerbEnding("ονται", "pres", "mp", "ind", "3", "pl"),
    _VerbEnding("εσθε", "pres", "mp", "ind", "2", "pl"),
    _VerbEnding("εται", "pres", "mp", "ind", "3", "sg"),
    _VerbEnding("ομαι", "pres", "mp", "ind", "1", "sg"),
    # imperfect active indicative (augmented)
    _VerbEnding("ομεν", "impf", "act", "ind", "1", "pl", augment=True),
    _VerbEnding("ετε", "impf", "act", "ind", "2", "pl", augment=True),
    _VerbEnding("ον", "impf", "act", "ind", "1", "sg", augment=True),
    _VerbEnding("ες", "impf", "act", "ind", "2", "sg", augment=True),
    _VerbEnding("εν", "impf", "act", "ind", "3", "sg", augment=True),
    # future active indicative (σ marker)
    _VerbEnding("σομεν", "fut", "act", "ind", "1", "pl"),
    _VerbEnding("σουσιν", "fut", "act", "ind", "3", "pl"),
    _VerbEnding("σουσι", "fut", "act", "ind", "3", "pl"),
    _VerbEnding("σετε", "fut", "act", "ind", "2", "pl"),
    _VerbEnding("σεισ", "fut", "act", "ind", "2", "sg"),
    _VerbEnding("σει", "fut", "act", "ind", "3", "sg"),
    _VerbEnding("σω", "fut", "act", "ind", "1", "sg"),
    # first (sigmatic) aorist active indicative (augmented, σ marker)
    _VerbEnding("σαμεν", "aor", "act", "ind", "1", "pl", augment=True),
    _VerbEnding("σατε", "aor", "act", "ind", "2", "pl", augment=True),
    _VerbEnding("σαν", "aor", "act", "ind", "3", "pl", augment=True),
    _VerbEnding("σασ", "aor", "act", "ind", "2", "sg", augment=True),
    _VerbEnding("σεν", "aor", "act", "ind", "3", "sg", augment=True),
    _VerbEnding("σα", "aor", "act", "ind", "1", "sg", augment=True),
    # infinitives
    _VerbEnding("εσθαι", "pres", "mp", "inf"),
    _VerbEnding("σαι", "aor", "act", "inf"),
    _VerbEnding("ειν", "pres", "act", "inf"),
)

# Mediopassive present participle (declines, but the -μενο/-μενη marker is
# distinctive); reconstruct the present-stem lemma from the -ομενο- linker.
_MP_PARTICIPLE: tuple[tuple[str, str], ...] = tuple(
    (ending.replace("ς", "σ"), gender)
    for ending, gender in (
        ("ομενος", _M), ("ομενη", _F), ("ομενον", _N),
        ("ομενου", _M), ("ομενης", _F),
        ("ομενοι", _M), ("ομεναι", _F), ("ομενα", _N),
    )
)


def _strip_augment(stem: str) -> str:
    """Remove a syllabic augment (leading ε-) when rebuilding a present lemma."""
    if stem.startswith("ε") and len(stem) > 1:
        return stem[1:]
    return stem


def _verbal(word: str) -> list[Analysis]:
    bare = _bare(word)
    # An iota subscript (ῳ/ῃ) marks a dative singular, never a finite verb.
    if "ͅ" in unicodedata.normalize("NFD", word):
        return []
    # The mediopassive participle marker is distinctive — check it first.
    for ending, gender in _MP_PARTICIPLE:
        if bare.endswith(ending) and len(bare) > len(ending):
            return [
                Analysis(
                    lemma=bare[: -len(ending)] + "ω", pos="VERB", tense="pres",
                    voice="mp", mood="part", gender=gender, lemma_certain=False,
                )
            ]
    matches = [
        ve for ve in _VERBAL
        if bare.endswith(ve.ending) and len(bare) > len(ve.ending)
    ]
    if not matches:
        return []
    longest = max(len(ve.ending) for ve in matches)
    out: list[Analysis] = []
    for ve in matches:
        if len(ve.ending) != longest:
            continue  # only the longest matching ending(s) apply
        stem = bare[: -len(ve.ending)]
        # Past tenses (imperfect/aorist) are marked by an augment; requiring one
        # keeps an unaugmented noun like λόγον from reading as a verb. (Epic
        # omits the augment freely — a documented gap, not handled here.)
        if ve.augment:
            if not stem.startswith("ε") or len(stem) < 2:
                continue
            stem = _strip_augment(stem)
        out.append(
            Analysis(
                lemma=stem + "ω", pos="VERB", tense=ve.tense, voice=ve.voice,
                mood=ve.mood, person=ve.person, number=ve.number,
                lemma_certain=False,
            )
        )
    return out


# --- closed-class pronoun paradigms ------------------------------------------
# Fully-inflected, attested paradigms (Smyth §§333-340) for the closed pronouns
# whose forms the ending rules can't read from the stem alone. Each form maps to
# its case/number/gender analyses; these take precedence over the flat POS
# lexicon (which carries only a coarse tag). Forms are stored under the
# `_closed_key` normalization (lowercase NFC, grave→acute) so running-text
# variants match. Genuinely ambiguous forms (e.g. relative ᾧ vs the same shape
# elsewhere) legitimately yield several readings — the caller disambiguates.


def _pron(lemma: str, *cells: tuple[str, str, str, str]) -> dict[str, list[Analysis]]:
    """Build a form→analyses map from ``(form, case, number, gender)`` cells.

    Multiple cells may share a form (Greek syncretism); their analyses
    accumulate under that form's normalized key."""
    out: dict[str, list[Analysis]] = {}
    for form, case, number, gender in cells:
        out.setdefault(_closed_key(form), []).append(
            Analysis(lemma=lemma, pos="PRON", case=case, number=number, gender=gender)
        )
    return out


def _merge(*maps: dict[str, list[Analysis]]) -> dict[str, tuple[Analysis, ...]]:
    merged: dict[str, list[Analysis]] = {}
    for m in maps:
        for key, analyses in m.items():
            merged.setdefault(key, []).extend(analyses)
    return {k: tuple(v) for k, v in merged.items()}


# Interrogative τίς, τί (Smyth §333): persistent acute, never enclitic. Both the
# pronominal (τίνος …) and the article-borrowed (τοῦ, τῷ) genitive/dative are
# attested for the interrogative; only the pronominal series is listed here, the
# borrowed forms coincide with the article and are tagged there.
_INTERROGATIVE = _pron(
    "τίς",
    ("τίς", "nom", "sg", "masc"), ("τίς", "nom", "sg", "fem"),
    ("τίνος", "gen", "sg", "masc"), ("τίνος", "gen", "sg", "fem"), ("τίνος", "gen", "sg", "neut"),
    ("τίνι", "dat", "sg", "masc"), ("τίνι", "dat", "sg", "fem"), ("τίνι", "dat", "sg", "neut"),
    ("τίνα", "acc", "sg", "masc"), ("τίνα", "acc", "sg", "fem"),
    ("τί", "nom", "sg", "neut"), ("τί", "acc", "sg", "neut"),
    ("τίνες", "nom", "pl", "masc"), ("τίνες", "nom", "pl", "fem"),
    ("τίνων", "gen", "pl", "masc"), ("τίνων", "gen", "pl", "fem"), ("τίνων", "gen", "pl", "neut"),
    ("τίσι", "dat", "pl", "masc"), ("τίσι", "dat", "pl", "fem"), ("τίσι", "dat", "pl", "neut"),
    ("τίσιν", "dat", "pl", "masc"), ("τίσιν", "dat", "pl", "fem"), ("τίσιν", "dat", "pl", "neut"),
    ("τίνας", "acc", "pl", "masc"), ("τίνας", "acc", "pl", "fem"),
    ("τίνα", "nom", "pl", "neut"), ("τίνα", "acc", "pl", "neut"),
)

# Indefinite τις, τι (Smyth §334): enclitic, unaccented citation form. The
# accent on a key distinguishes it from the interrogative above.
_INDEFINITE = _pron(
    "τις",
    ("τις", "nom", "sg", "masc"), ("τις", "nom", "sg", "fem"),
    ("τινός", "gen", "sg", "masc"), ("τινός", "gen", "sg", "fem"), ("τινός", "gen", "sg", "neut"),
    ("τινί", "dat", "sg", "masc"), ("τινί", "dat", "sg", "fem"), ("τινί", "dat", "sg", "neut"),
    ("τινά", "acc", "sg", "masc"), ("τινά", "acc", "sg", "fem"),
    ("τι", "nom", "sg", "neut"), ("τι", "acc", "sg", "neut"),
    ("τινές", "nom", "pl", "masc"), ("τινές", "nom", "pl", "fem"),
    ("τινῶν", "gen", "pl", "masc"), ("τινῶν", "gen", "pl", "fem"), ("τινῶν", "gen", "pl", "neut"),
    ("τισί", "dat", "pl", "masc"), ("τισί", "dat", "pl", "fem"), ("τισί", "dat", "pl", "neut"),
    ("τισίν", "dat", "pl", "masc"), ("τισίν", "dat", "pl", "fem"), ("τισίν", "dat", "pl", "neut"),
    ("τινάς", "acc", "pl", "masc"), ("τινάς", "acc", "pl", "fem"),
    ("τινά", "nom", "pl", "neut"), ("τινά", "acc", "pl", "neut"),
)

# Relative ὅς, ἥ, ὅ (Smyth §339). Many cells coincide with the article in shape
# (ᾧ, ᾗ, οἷς, αἷς, ὧν, …) but differ in being unaspirated vs the relative's rough
# breathing; here only the relative (rough-breathing) forms are keyed, so they do
# not collide with the article's τ-forms in the POS lexicon.
_RELATIVE = _pron(
    "ὅς",
    ("ὅς", "nom", "sg", "masc"), ("ἥ", "nom", "sg", "fem"), ("ὅ", "nom", "sg", "neut"),
    ("οὗ", "gen", "sg", "masc"), ("ἧς", "gen", "sg", "fem"), ("οὗ", "gen", "sg", "neut"),
    ("ᾧ", "dat", "sg", "masc"), ("ᾗ", "dat", "sg", "fem"), ("ᾧ", "dat", "sg", "neut"),
    ("ὅν", "acc", "sg", "masc"), ("ἥν", "acc", "sg", "fem"), ("ὅ", "acc", "sg", "neut"),
    ("οἵ", "nom", "pl", "masc"), ("αἵ", "nom", "pl", "fem"), ("ἅ", "nom", "pl", "neut"),
    ("ὧν", "gen", "pl", "masc"), ("ὧν", "gen", "pl", "fem"), ("ὧν", "gen", "pl", "neut"),
    ("οἷς", "dat", "pl", "masc"), ("αἷς", "dat", "pl", "fem"), ("οἷς", "dat", "pl", "neut"),
    ("οὕς", "acc", "pl", "masc"), ("ἅς", "acc", "pl", "fem"), ("ἅ", "acc", "pl", "neut"),
)

_CLOSED_PARADIGM: dict[str, tuple[Analysis, ...]] = _merge(
    _INTERROGATIVE, _INDEFINITE, _RELATIVE
)


# --- public API --------------------------------------------------------------


@lru_cache(maxsize=4096)
def _rule_analyze(word: str) -> tuple[Analysis, ...]:
    """Rule-based candidate analyses — the baseline engine behind `analyze`."""
    paradigm = _CLOSED_PARADIGM.get(_closed_key(word))
    if paradigm is not None:
        return paradigm
    fixed = _LEXICON.get(_closed_key(word))
    if fixed is not None:
        lemma, _ = seed_lemma_verbose(word)
        return (Analysis(lemma=lemma, pos=fixed),)
    seen: set[tuple[object, ...]] = set()
    out: list[Analysis] = []
    for a in _verbal(word) + _nominal(word):
        key = (a.pos, a.case, a.number, a.gender, a.tense, a.voice, a.mood, a.person)
        if key not in seen:
            seen.add(key)
            out.append(a)
    return tuple(out)


def analyze(word: str) -> tuple[Analysis, ...]:
    """All candidate morphological analyses of ``word`` (possibly several, given
    Greek's ambiguity; empty only for unanalysable tokens).

    Closed-class words (article, prepositions, conjunctions, particles, pronouns,
    the copula) resolve to a single high-confidence analysis; open-class words
    yield the readings their ending permits. When the AGDT treebank backend is
    active (see `aegean.greek.use_treebank`), an attested form's analyses —
    correctly accented and covering irregular forms the rule engine can't — are
    returned instead, with the rule engine as the fallback for unattested forms."""
    from . import treebank

    lex = treebank.active()
    if lex is not None:
        hit = lex.analyze(word)
        if hit:
            return hit
    return _rule_analyze(word)


def lemmas(word: str) -> list[str]:
    """The distinct lemma candidates for a form (closed-class or rule-derived)."""
    out: list[str] = []
    for a in analyze(word):
        if a.lemma not in out:
            out.append(a.lemma)
    return out


def best_pos(word: str) -> str | None:
    """A single best part-of-speech guess from morphology, or ``None`` when the
    form yields no analysis. Returns the most likely reading's tag (verbal and
    closed-class readings, which are listed first, take precedence over the
    nominal default), or ``ADJ`` when a degree is marked."""
    analyses = analyze(word)
    if not analyses:
        return None
    if any(a.degree for a in analyses):
        return "ADJ"
    return analyses[0].pos
