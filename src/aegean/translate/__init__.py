"""Hybrid translation: lexicon/morphology grounding → LLM.

Builds grounding evidence from the package's own tooling (deterministic Greek
morphology and dependency syntax, optionally gated content-word LSJ glosses;
Linear A sign→sound transliteration), then hands the text plus that evidence to
`aegean.ai.translate`. The grounding step is deterministic and local; the
translation itself is generative and returned as an exploratory, provenanced
`ExploratoryResult`.

Greek grounding has several **modes** (see `grounding_for`). The default,
``"morphology"``, grounds the model in deterministic morphology and syntax (lemma,
part of speech, case/voice/tense, and a clause skeleton from the dependency parse)
and adds **no** dictionary glosses. This is the recommended mode: morphology, voice,
case-role, and syntactic structure are facts the toolkit computes reliably and that a
model can use directly, whereas an auto-selected dictionary gloss can surface the wrong
or an archaic sense and steer the model away from a correct reading. The older
``"lemma"`` mode (lemma lines plus gated content-word LSJ glosses) is retained for
back-compatibility; ``"full"`` combines morphology lines with the conservative gated
glosses; ``"none"`` adds no grounding.

The gated glosses used by ``"lemma"`` and ``"full"`` are deliberately selective
(see `ai.grounding.content_glosses`): they gloss only low-polysemy content words, where
the dominant-sense gloss is reliable, and leave highly polysemous words to the model. An
ungated first-sense gloss for a word like στάσις or κρίσις is often the wrong contextual
sense.
"""

from __future__ import annotations

import warnings
from typing import Literal

from ..ai import translate as _ai_translate
from ..ai.client import ExploratoryResult, LLMClient
from ..ai.grounding import GroundingItem, content_glosses

_SOURCE_NAMES = {"greek": "Ancient Greek", "lineara": "Linear A"}

GroundingMode = Literal["morphology", "lemma", "full", "none"]

# Content parts of speech worth a clause role / rarity flag.
_CONTENT_POS = frozenset({"NOUN", "VERB", "ADJ", "ADV", "PROPN"})

# UD FEATS values → short, readable forms for the per-token morphology line. Keyed by
# (feature, value) so identical values under different features (Mood=Imp imperative vs
# Aspect=Imp imperfect) never collide; an unmapped value falls back to lower-case.
_FEAT_SHORT = {
    ("Case", "Nom"): "nom", ("Case", "Gen"): "gen", ("Case", "Dat"): "dat",
    ("Case", "Acc"): "acc", ("Case", "Voc"): "voc",
    ("Number", "Sing"): "sg", ("Number", "Plur"): "pl", ("Number", "Dual"): "du",
    ("Gender", "Masc"): "m", ("Gender", "Fem"): "f", ("Gender", "Neut"): "n",
    ("Voice", "Act"): "active", ("Voice", "Mid"): "middle", ("Voice", "Pass"): "passive",
    ("Tense", "Pres"): "pres", ("Tense", "Past"): "past", ("Tense", "Fut"): "fut",
    ("Tense", "Aor"): "aor", ("Tense", "Pqp"): "pluperf",
    ("Mood", "Ind"): "ind", ("Mood", "Sub"): "subj", ("Mood", "Opt"): "opt",
    ("Mood", "Imp"): "imper",
    ("Person", "1"): "1st", ("Person", "2"): "2nd", ("Person", "3"): "3rd",
}

# Order in which morphological features are rendered on a token line.
_FEAT_KEYS = ("Case", "Number", "Gender", "Voice", "Tense", "Mood", "Person")


def _rich_lemmatizer_active() -> bool:
    """Whether a lemmatizer better than the bundled seed table is loaded — the
    treebank, neural pipeline, GreTa, or edit-tree backend. Lexical grounding on rare
    or inflected forms depends on one of these being active."""
    from ..greek import joint, lemmatizer, neural_lemmatizer, treebank

    return any(m.active() is not None for m in (joint, treebank, neural_lemmatizer, lemmatizer))


def _readable_feats(feats: str | None, *keys: str) -> str:
    """Render selected UD FEATS values as a compact, readable string.

    ``_readable_feats("Case=Acc|Number=Sing", "Case", "Number")`` → ``"acc sg"``.
    Unknown values fall back to lower-case; absent features are skipped."""
    if not feats or feats == "_":
        return ""
    parsed = dict(kv.split("=", 1) for kv in feats.split("|") if "=" in kv)
    out: list[str] = []
    for k in keys:
        v = parsed.get(k)
        if v is None:
            continue
        out.append(_FEAT_SHORT.get((k, v), v.lower()))
    return " ".join(out)


def _morphology_items(text: str) -> list[GroundingItem]:
    """Deterministic morphology + syntax grounding for Greek, no dictionary glosses.

    Produces, in order: an optional clause-skeleton line from the dependency parse
    (main predicate plus subject/object), one compact line per non-punct token
    (``word = lemma (pos, readable-morph)``), and an optional rare-word flag line. Uses
    the active backends via `greek.pipeline(text, parse=True)` and degrades gracefully:
    without a parser the skeleton is simply omitted; rule-based POS/lemma still populate
    the token lines. Never raises."""
    from ..greek import pipeline

    try:
        recs = pipeline(text, parse=True)
    except Exception:
        # No parser loaded (or a backend failed): fall back to the unparsed analysis,
        # which still gives POS + lemma for the per-token lines.
        try:
            recs = pipeline(text, parse=False)
        except Exception:
            return []

    out: list[GroundingItem] = []

    # Clause skeleton: roots (head == 0) that head a clause, with their subject/object.
    skeleton: list[str] = []
    for rt in recs:
        if rt.head != 0 or rt.upos not in {"VERB", "ADJ", "NOUN"}:
            continue
        pred = _readable_feats(rt.feats, "Voice", "Tense", "Number", "Person")
        kids = {r.relation: r.text for r in recs if r.head == rt.index and r.relation}
        parts = [f"main predicate '{rt.text}' ({rt.lemma}{', ' + pred if pred else ''})"]
        if "nsubj" in kids:
            parts.append(f"subject {kids['nsubj']}")
        if "obj" in kids:
            parts.append(f"object {kids['obj']}")
        skeleton.append("; ".join(parts))
    if skeleton:
        out.append(
            GroundingItem(
                "Clause skeleton: " + " | ".join(skeleton),
                source="analysis:syntax",
                ref="clause",
            )
        )

    # One compact morphology line per non-punctuation token.
    for r in recs:
        if r.upos == "PUNCT":
            continue
        morph = _readable_feats(r.feats, *_FEAT_KEYS)
        body = f"{r.text} = {r.lemma} ({r.upos.lower()}{', ' + morph if morph else ''})"
        out.append(GroundingItem(body, source="analysis:morphology", ref=r.text))

    rare_line = _rare_word_line(text)
    if rare_line:
        out.append(
            GroundingItem(
                "Rare / easily-mistranslated words: " + rare_line,
                source="analysis:rarity",
                ref="rare",
            )
        )
    return out


def _rare_word_line(text: str) -> str:
    """Comma-joined rare/uncommon content words in ``text``, or ``""``.

    Rarity is measured against the Greek NT as a reference corpus (`greek.load_nt`),
    a register-broad Koine baseline that is offline and bundled-on-demand. Best-effort:
    if the corpus or the rarity computation is unavailable, returns ``""`` rather than
    raising — the rest of the morphology grounding still stands."""
    try:
        from ..greek import load_nt, terminology_rarity

        result = terminology_rarity(text, load_nt())
    except Exception:
        return ""
    rare = [w.word for w in result.hardest(4) if w.label != "common"]
    return ", ".join(dict.fromkeys(rare))  # dedupe, preserve order


def _greek_grounding(
    text: str, *, mode: GroundingMode = "morphology", glosses: bool = True
) -> list[GroundingItem]:
    from ..greek import lemmatize_verbose, tokenize_words

    if mode == "none":
        return []

    if mode in ("morphology", "full"):
        out = _morphology_items(text)
        if mode == "full" and glosses:
            out.extend(content_glosses(text))
        return out

    # mode == "lemma": the original lemma-line + gated-gloss grounding, preserved exactly.
    out = []
    for w in tokenize_words(text):
        lemma, known = lemmatize_verbose(w)
        if known:
            out.append(GroundingItem(f"{w} → lemma {lemma}", source="lemmatizer", ref=w))
    if glosses:
        # Gated LSJ glosses for content words — best-effort, empty without greek.use_lsj().
        out.extend(content_glosses(text))
    return out


def _lineara_grounding(text: str) -> list[GroundingItem]:
    from ..scripts.lineara.phonetic import word_to_phonetic

    return [
        GroundingItem(f"{w} → /{word_to_phonetic(w)}/", source="transliteration", ref=w)
        for w in text.split()
        if "-" in w
    ]


def grounding_for(
    text: str,
    script: str,
    *,
    mode: GroundingMode = "morphology",
    glosses: bool = True,
) -> list[GroundingItem]:
    """Local, deterministic grounding evidence for ``text`` in ``script`` — each item
    tagged with its source (``analysis:morphology`` / ``analysis:syntax`` /
    ``analysis:rarity`` / ``lemmatizer`` / ``lexicon:LSJ`` / ``transliteration``) so the
    result's `trace()` shows where the grounding came from.

    For ``greek``, ``mode`` selects the grounding style:

    - ``"morphology"`` (default, recommended): deterministic morphology and syntax —
      a per-token line (lemma, part of speech, case/voice/tense) plus a clause skeleton
      (main predicate, subject, object) from the dependency parse, and a rare-word flag.
      **No dictionary glosses.** Morphology, voice, case-role, and structure are facts the
      toolkit computes reliably and a model can use directly; an auto-selected dictionary
      gloss can surface the wrong or an archaic sense and mislead the model, so this mode
      omits glosses entirely.
    - ``"lemma"``: the lemma-line grounding plus gated content-word LSJ glosses (the prior
      default; retained for back-compatibility).
    - ``"full"``: the ``"morphology"`` lines **and** the gated content-word glosses.
    - ``"none"``: no grounding.

    ``glosses`` is retained for back-compatibility and is **superseded by** ``mode``:
    it only affects the gloss-bearing modes (``"lemma"``, ``"full"``), where
    ``glosses=False`` drops the glosses (lemma-only / morphology-only). It has no effect
    on ``"morphology"`` (already gloss-free) or ``"none"``.

    The ``"morphology"`` grounding uses the active backends (``greek.pipeline(text,
    parse=True)``): with `use_neural_pipeline` active it carries gold morphology and a UD
    parse; without it, rule-based POS and lemmas still populate the token lines and the
    clause skeleton is simply omitted. It never raises.
    """
    if script == "greek":
        return _greek_grounding(text, mode=mode, glosses=glosses)
    if script == "lineara":
        return _lineara_grounding(text)
    return []


def translate(
    text: str,
    *,
    script: str = "greek",
    target: str = "English",
    mode: GroundingMode = "morphology",
    glosses: bool = True,
    client: LLMClient | None = None,
) -> ExploratoryResult:
    """Translate ``text`` (a ``greek`` or ``lineara`` string) into ``target``,
    grounded in locally-derived morphology/lexicon/transliteration evidence.

    Exploratory: the grounding is real, the translation is a model hypothesis —
    especially for undeciphered Linear A.

    For ``greek``, ``mode`` (default ``"morphology"``) selects the grounding style; see
    `grounding_for`. The default grounds the model in deterministic morphology and
    syntax (lemma, part of speech, case/voice/tense, clause skeleton) with **no**
    dictionary glosses. This is recommended: morphology, voice, case-role, and syntactic
    structure reliably help a model, whereas an auto-selected dictionary gloss can surface
    the wrong or an archaic sense and steer the model away from a correct reading. Use
    ``mode="lemma"`` for the older lemma-line plus gated-gloss grounding, ``mode="full"``
    to add those gated glosses on top of the morphology lines, or ``mode="none"`` for no
    grounding.

    ``glosses`` is retained for back-compatibility and is superseded by ``mode``: it only
    affects the gloss-bearing modes (``"lemma"``, ``"full"``), where ``glosses=False``
    drops the glosses.

    Coverage of rare or inflected forms (and the clause skeleton) depends on the active
    backends, so a warning is raised when only the baseline seed table is loaded (call
    ``aegean.greek.use_treebank()``, or ``use_neural_pipeline()`` for gold morphology and a
    UD parse, first).
    """
    if script == "greek" and mode != "none" and not _rich_lemmatizer_active():
        warnings.warn(
            "Grounded Greek translation is using the baseline lemmatizer; morphology and "
            "lexical grounding will miss many rare or inflected forms and the clause "
            "skeleton will be omitted. Call aegean.greek.use_treebank() (or "
            "aegean.greek.use_neural_pipeline() for gold morphology and a dependency parse) "
            "first for fuller grounding.",
            stacklevel=2,
        )
    source = _SOURCE_NAMES.get(script, script)
    return _ai_translate(
        text,
        source=source,
        target=target,
        grounding=grounding_for(text, script, mode=mode, glosses=glosses),
        client=client,
    )


__all__ = ["translate", "grounding_for"]
