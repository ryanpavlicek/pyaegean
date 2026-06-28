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
and adds **no** dictionary glosses: morphology, voice, case-role, and syntactic structure
are facts the toolkit computes reliably and that a model can use directly. It also adds a
gloss of any **idiom** present (``ai.idiom_glosses``): a non-compositional multiword
expression is the one error class per-token morphology cannot reach, since the words'
lemmas and case only reinforce the wrong literal reading, and the curated idiom lexicon
matches deterministically with a low false-positive rate, so it rides with the safe
default. ``"full"`` keeps those morphology and idiom lines and adds a gloss layer in the
configuration that helps rather than hurts: glosses sourced from a **concise,
common-sense-first** dictionary cascade (Middle Liddell, Cunliffe for Homer, Abbott-Smith /
Dodson for the NT), cleaned, and gated to the text's rare content words (see
`ai.grounding.content_glosses` with ``source="cascade"``).
That source matters: a first-sense gloss from the historical LSJ lexicon is often the
archaic meaning (καιρός, βίος), so asserting it injects errors, whereas a concise dictionary
leads with the common sense and helps most exactly on the rare vocabulary a model is likely
to miss. ``"none"`` adds no grounding.

The older ``"lemma"`` mode (lemma lines plus gated content-word LSJ glosses) is retained
unchanged for back-compatibility; its glosses are the deliberately selective LSJ ones (see
`ai.grounding.content_glosses` with the default ``source="lsj"``): only low-polysemy content
words, where the dominant-sense gloss is reliable, leaving highly polysemous words to the
model.
"""

from __future__ import annotations

import warnings
from typing import Literal

from ..ai import translate as _ai_translate
from ..ai.client import ExploratoryResult, LLMClient
from ..ai.grounding import GroundingItem, content_glosses
from ..ai.idioms import idiom_glosses

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
        # Idiom glosses ride with the morphology grounding in both modes. A
        # non-compositional multiword expression is the one error class per-token
        # morphology cannot reach (its lemmas/case only reinforce the literal reading), and
        # the curated lexicon matches deterministically with a low false-positive rate on
        # exact surface match, so it belongs in the safe default, not gated like sense
        # glosses. Best-effort: empty when no idiom is present. Source tag lexicon:idiom.
        out.extend(idiom_glosses(text))
        if mode == "full" and glosses:
            # The validated-best gloss layer: a concise, common-sense-first dictionary
            # cascade (never LSJ-first-sense), cleaned, and gated to the rare content words
            # (where a gloss helps). Best-effort: empty if no concise dictionary is loaded.
            out.extend(content_glosses(text, source="cascade", rarity_gate=True))
        return out

    # mode == "lemma": the original lemma-line + gated LSJ-gloss grounding, preserved exactly.
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
    ``analysis:rarity`` / ``lexicon:idiom`` / ``lemmatizer`` / ``lexicon:LSJ`` /
    ``transliteration``) so the result's `trace()` shows where the grounding came from.

    For ``greek``, ``mode`` selects the grounding style:

    - ``"morphology"`` (default, recommended): deterministic morphology and syntax —
      a per-token line (lemma, part of speech, case/voice/tense) plus a clause skeleton
      (main predicate, subject, object) from the dependency parse, and a rare-word flag.
      **No dictionary glosses**, but it does include a gloss of any **idiom** present (a
      curated, non-compositional multiword expression matched on surface/lemma; source
      ``lexicon:idiom``). Morphology, voice, case-role, and structure are facts the toolkit
      computes reliably and a model can use directly; an auto-selected dictionary gloss can
      surface the wrong or an archaic sense and mislead the model, so this mode omits those.
      An idiom gloss is different: the phrase is non-compositional, so the literal token
      reading is *itself* the error, and the lexicon match is deterministic and
      low-false-positive, which is why it rides with the default.
    - ``"full"``: the ``"morphology"`` lines (including idiom glosses) **and** a gloss layer
      in the configuration
      that helps. Glosses come from a concise, common-sense-first dictionary cascade
      (Middle Liddell, Cunliffe for Homer, Abbott-Smith / Dodson for the NT), cleaned, and
      gated to the rare content words. **Not** LSJ-first-sense: that historical lexicon
      orders senses etymologically, so its lead sense is often the archaic meaning and
      asserting it injects errors; a concise dictionary leads with the common sense and
      helps most on the rare vocabulary a model is likely to miss. Source tag
      ``lexicon:concise``. Best-effort: the glosses are simply absent if no concise
      dictionary is loaded (``greek.use_lexicon("middle-liddell")`` etc.).
    - ``"lemma"``: the lemma-line grounding plus gated content-word LSJ glosses (the prior
      default; retained unchanged for back-compatibility). Source tag ``lexicon:LSJ``.
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
    syntax (lemma, part of speech, case/voice/tense, clause skeleton) plus a gloss of any
    non-compositional idiom present (``ai.idiom_glosses``), with **no** dictionary glosses
    on ordinary words. Use ``mode="full"`` to add, on top of those morphology lines, a
    gloss layer sourced from a concise, common-sense-first dictionary cascade (Middle
    Liddell, Cunliffe, Abbott-Smith / Dodson), cleaned and gated to the rare content words:
    a concise dictionary leads with the common sense and helps most on rare vocabulary,
    whereas an LSJ-first-sense gloss is often the archaic meaning and misleads. Use
    ``mode="lemma"`` for the older lemma-line plus gated LSJ-gloss grounding, or
    ``mode="none"`` for no grounding.

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
