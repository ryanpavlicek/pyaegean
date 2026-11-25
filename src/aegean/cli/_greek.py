"""The `aegean greek` group: the full Greek NLP pipeline from the shell, plus
dictionary glossing.

Backend flags mirror the `use_*` activation functions: ``--treebank``,
``--tagger``, ``--lemmatizer``, ``--neural-lemmatizer``, ``--neural`` (the joint
pipeline), ``--lsj``. Each activation may download its data/model to the cache on
first use (a note goes to stderr); afterwards everything is offline. The lexicon
commands (`gloss`, `lexica`, `lexicon-link`) reach the dictionary registry;
`gloss --dict <id>` picks which dictionary to use. `stream` consumes
pre-tokenized JSONL sentences and emits neural `SentenceAnalysis` values incrementally.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Literal, cast

import typer

from . import _greek_eval, _greek_interop, _greek_works
from ._common import (
    JSON_OPT,
    RESULT_OPT,
    console,
    emit_json,
    emit_result,
    fail,
    load_corpus,
    read_text,
    table,
    to_plain,
)
from ._greek_eval import evaluate as evaluate
from ._greek_interop import (
    annotation_profiles_app as annotation_profiles_app,
)
from ._greek_interop import (
    annotation_profiles_list as annotation_profiles_list,
)
from ._greek_interop import (
    annotation_profiles_show as annotation_profiles_show,
)
from ._greek_interop import (
    conllu_app as conllu_app,
)
from ._greek_interop import (
    export as export,
)
from ._greek_interop import (
    inspect as inspect,
)
from ._greek_interop import (
    interop_app as interop_app,
)
from ._greek_interop import (
    interop_export as interop_export,
)
from ._greek_interop import (
    interop_import as interop_import,
)
from ._greek_interop import (
    interop_report as interop_report,
)
from ._greek_works import (
    _bare_textpart as _bare_textpart,
)
from ._greek_works import (
    catalog as catalog,
)
from ._greek_works import (
    work as work,
)
from ._greek_works import (
    works as works,
)

greek_app = typer.Typer(
    pretty_exceptions_show_locals=False,
    help="Greek NLP (normalize → … → parse), dictionaries, literary works (Perseus/First1KGreek), "
    "and eval reproductions.",
    no_args_is_help=True,
)

_greek_interop.register(greek_app)
_greek_works.register(greek_app)
_greek_eval.register(greek_app)

TEXT_ARG = typer.Argument(..., help="Greek text ('-' reads stdin).")
WORD_ARG = typer.Argument(..., help="One Greek word.")

TREEBANK_OPT = typer.Option(False, "--treebank", help="Activate the Perseus AGDT lexicon (~75 MB fetch on first use).")
TAGGER_OPT = typer.Option(False, "--tagger", help="Activate the generalizing POS tagger (trains from the AGDT on first use).")
LEMMATIZER_OPT = typer.Option(False, "--lemmatizer", help="Activate the edit-tree lemmatizer (trains from the AGDT on first use).")
NEURAL_LEMM_OPT = typer.Option(False, "--neural-lemmatizer", help="Activate the seq2seq lemmatizer (~232 MB model, \\[neural] extra).")
NEURAL_OPT = typer.Option(False, "--neural", help="Activate the joint neural pipeline (~173 MB model, \\[neural] extra).")
NEURAL_VARIANT_OPT = typer.Option(
    "default",
    "--neural-variant",
    help="Joint-model runtime variant: default, fast, compact, or balanced. "
    "Reserved labels fail until a qualified artifact is released.",
)
LSJ_OPT = typer.Option(False, "--lsj", help="Activate LSJ glossing (~270 MB fetch on first use).")
CONFIDENCE_OPT = typer.Option(
    False, "--confidence",
    help="Attach calibrated confidence (loads the shipped calibration). Needs --neural: "
    "it is model-only, so identity/punctuation lemmas carry none (a lookup-composed lemma "
    "does — the calibration covers the model's internal training-form lookup).",
)



def _jsonl_sentences(source: str | Path) -> Iterator[list[str]]:
    """Yield pre-tokenized sentences from a JSONL path or stdin.

    The neural streaming API takes an iterable of token iterables.  Keeping parsing in
    this generator means a file is consumed only as the backend asks for another
    sentence, rather than being read into memory before inference starts.
    """
    source_name = str(source)
    stream = sys.stdin
    owned = False
    if source_name != "-":
        try:
            # utf-8-sig, like every other user-supplied file this package reads: a JSONL
            # file written by an editor that marks UTF-8 with a BOM is still JSONL.
            stream = Path(source_name).open("r", encoding="utf-8-sig")
            owned = True
        except (OSError, UnicodeError) as exc:
            raise ValueError(f"could not open JSONL input {source_name!r}: {exc}") from None
    try:
        for line_number, line in enumerate(stream, start=1):
            if line_number == 1 and not owned:
                # stdin is decoded by the interpreter, so a BOM piped in from such a
                # file arrives as text; an opened file drops its own while decoding.
                line = line.removeprefix("\ufeff")
            # Blank lines are harmless in JSONL pipelines and are not sentences.
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"JSONL input line {line_number} is not valid JSON: {exc.msg}"
                ) from None
            if not isinstance(value, list):
                raise TypeError(
                    f"JSONL input line {line_number} must be a JSON array of token strings"
                )
            for token_number, token in enumerate(value):
                if not isinstance(token, str):
                    raise TypeError(
                        f"JSONL input line {line_number} token {token_number} must be a string"
                    )
            yield value
    finally:
        if owned:
            stream.close()


def _emit_jsonl(value: Any) -> None:
    """Write one JSONL result and flush it so downstream consumers get backpressure."""
    sys.stdout.write(json.dumps(to_plain(value), ensure_ascii=False, separators=(",", ":")))
    sys.stdout.write("\n")
    sys.stdout.flush()



def _ensure_calibration() -> None:
    """Activate the bundled calibration for a ``--confidence`` request (a no-op when one
    is already loaded), or exit with the established one clean line if none is shipped."""
    from aegean.greek import calibrate

    if calibrate.active() is not None:
        return
    try:
        calibrate.use_calibration()
    except calibrate.UncalibratedConfidenceError:
        raise fail(
            "the shipped calibration file is missing; reinstall pyaegean or run "
            "use_calibration(path)"
        ) from None


def _load_confidence_policy(path: Path) -> Any:
    """Load one caller-supplied abstention policy with strict public validation."""
    from aegean.greek import AbstentionPolicy

    try:
        return AbstentionPolicy.load(path)
    except (OSError, UnicodeError, TypeError, ValueError) as exc:
        raise fail(f"could not load confidence policy {path}: {exc}") from None


def _activate(
    *,
    treebank: bool = False,
    tagger: bool = False,
    lemmatizer: bool = False,
    neural_lemmatizer: bool = False,
    neural: bool = False,
    neural_variant: str = "default",
    lsj: bool = False,
    parser: bool = False,
) -> None:
    """Run the requested use_* activations, with a stderr note for slow ones."""
    from collections.abc import Callable

    from aegean import greek

    if not neural and neural_variant != "default":
        raise fail("--neural-variant requires --neural")

    def activate_neural() -> None:
        greek.use_neural_pipeline(variant=neural_variant)

    neural_name = (
        "neural joint pipeline"
        if neural_variant == "default"
        else f"neural joint pipeline ({neural_variant})"
    )
    steps: list[tuple[bool, str, Callable[[], object | None]]] = [
        (treebank, "treebank (Perseus AGDT)", greek.use_treebank),
        (tagger, "POS tagger", greek.use_tagger),
        (lemmatizer, "edit-tree lemmatizer", greek.use_lemmatizer),
        (neural_lemmatizer, "neural lemmatizer", greek.use_neural_lemmatizer),
        (neural, neural_name, activate_neural),
        (lsj, "LSJ lexicon", greek.use_lsj),
        (parser, "dependency parser", greek.use_parser),
    ]
    for wanted, name, fn in steps:
        if not wanted:
            continue
        print(f"aegean: activating the {name} (first use may download/build)…", file=sys.stderr)
        try:
            fn()
        except Exception as exc:
            raise fail(f"could not activate the {name}: {exc}") from None


@greek_app.command()
def normalize(
    text: str = TEXT_ARG,
    form: str = typer.Option("NFC", "--form", help="NFC, NFD, NFKC, or NFKD."),
    lenient: bool = typer.Option(
        False, "--lenient", help="Repair OCR artifacts (warnings go to stderr)."
    ),
) -> None:
    """Unicode-normalize Greek text; --lenient repairs OCR/Beta-Code artifacts."""
    import warnings

    from aegean import greek

    if form not in ("NFC", "NFD", "NFKC", "NFKD"):
        raise fail("--form must be NFC, NFD, NFKC, or NFKD")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        out = greek.normalize(read_text(text), form, lenient=lenient)  # type: ignore[arg-type]
    for w in caught:
        print(f"aegean: {w.message}", file=sys.stderr)
    print(out)


@greek_app.command()
def betacode(
    text: str = TEXT_ARG,
    reverse: bool = typer.Option(False, "--reverse", help="Unicode → Beta Code instead."),
) -> None:
    """Convert Beta Code to polytonic Greek (or back with --reverse)."""
    from aegean import greek

    s = read_text(text)
    print(greek.unicode_to_betacode(s) if reverse else greek.betacode_to_unicode(s))


@greek_app.command()
def strip(text: str = TEXT_ARG) -> None:
    """Strip all diacritics (accents, breathings, subscripts)."""
    from aegean import greek

    print(greek.strip_diacritics(read_text(text)))


@greek_app.command()
def tokenize(
    text: str = TEXT_ARG,
    sentences: bool = typer.Option(False, "--sentences", help="Split into sentences instead."),
    sentence_policy: str = typer.Option("default", "--sentence-policy", help="Sentence policy: default, prose, verse, inscription, or papyrus."),
    rich: bool = typer.Option(False, "--rich", help="Include source spans and boundary provenance with --sentences."),
    json_out: bool = JSON_OPT,
) -> None:
    """Tokenize into words+punctuation (or sentences with --sentences)."""
    from aegean import greek

    s = read_text(text)
    if rich and not sentences:
        raise fail("--rich requires --sentences")
    if sentences:
        try:
            result = greek.segment_text(s, policy=sentence_policy)
        except (TypeError, ValueError) as exc:
            raise fail(str(exc)) from None
        if rich and not json_out:
            typer.echo(f"policy: {result.policy} ({result.policy_id})")
            table(
                "sentence boundaries",
                ["start", "end", "provenance", "confidence", "text"],
                [
                    [
                        str(item.start),
                        str(item.end),
                        item.provenance,
                        "" if item.confidence is None else str(item.confidence),
                        item.text(s),
                    ]
                    for item in result.boundaries
                ],
            )
            return
        out = result.to_dict() if rich else list(result.sentences)
    else:
        out = [t.text for t in greek.tokenize(s)]
    if json_out:
        emit_json(out)
    else:
        print("\n".join(out))


@greek_app.command()
def syllabify(word: list[str] = typer.Argument(..., help="Greek word(s)."), json_out: bool = JSON_OPT) -> None:
    """Split word(s) into syllables (rules + the compound-exception lexicon)."""
    from aegean import greek

    results = {w: greek.syllabify(w) for w in word}
    if json_out:
        emit_json(results)
        return
    for w, syls in results.items():
        print(f"{w} → {'-'.join(syls)}")


@greek_app.command()
def accent(word: list[str] = typer.Argument(..., help="Greek word(s)."), json_out: bool = JSON_OPT) -> None:
    """Accent analysis: type, position, classification."""
    from aegean import greek

    rows = []
    for w in word:
        info = greek.accentuation(w)
        rows.append(
            {
                "word": w, "accent": info.accent_type or "", "position": info.position_from_end,
                "classification": info.classification or "", "syllables": list(info.syllables),
            }
        )
    if json_out:
        emit_json(rows)
        return
    table("accent analysis", ["word", "accent", "pos", "classification"],
          [[str(r["word"]), str(r["accent"]), str(r["position"]), str(r["classification"])] for r in rows])


@greek_app.command()
def quantities(word: list[str] = typer.Argument(..., help="Greek word(s)."), json_out: bool = JSON_OPT) -> None:
    """Per-syllable metrical quantity (heavy / light / common)."""
    from aegean import greek

    results = {
        w: [{"syllable": s, "quantity": q} for s, q in greek.scan(w)]
        for w in word
    }
    if json_out:
        emit_json(results)
        return
    for w, quants in results.items():
        bits = [f"{q['syllable']}:{q['quantity']}" for q in quants]
        print(f"{w} → {' | '.join(bits)}")


@greek_app.command()
def scan(
    line: str = TEXT_ARG,
    meter: str = typer.Option(
        "hexameter", "--meter",
        help="hexameter, pentameter, trimeter, or an aeolic line "
             "(glyconic, pherecratean, sapphic_hendecasyllable, adonean, "
             "alcaic_hendecasyllable, alcaic_enneasyllable, alcaic_decasyllable).",
    ),
    json_out: bool = JSON_OPT,
) -> None:
    """Metrical scansion: dactylic hexameter, elegiac pentameter, iambic trimeter, or the
    aeolic lyric lines (fixed quantity templates).

    Synizesis is lexical, not inferred: a line that only fits via synizesis on a
    word outside the curated lexicon exits 1 with the reason rather than guessing."""
    from aegean import greek

    s = read_text(line)
    try:
        sc = greek.scan_line(s, meter)
    except greek.ScansionError as exc:
        raise fail(str(exc)) from None
    except ValueError as exc:
        raise fail(str(exc)) from None
    if json_out:
        emit_json(
            {
                "meter": sc.meter, "pattern": sc.pattern, "feet": list(sc.feet),
                "syllables": list(sc.syllables), "quantities": list(sc.quantities),
                "caesura": sc.caesura, "ambiguous": sc.ambiguous,
            }
        )
        return
    print(sc.pattern)
    feet = ", ".join(f.name for f in sc.feet)
    console().print(f"{sc.meter}: {feet}; caesura: {sc.caesura or '—'}", style="dim", markup=False)


@greek_app.command()
def ipa(
    text: str = TEXT_ARG,
    period: str = typer.Option(
        "attic", "--period",
        help="attic or koine (the pronunciation period, not the find-context --period filter).",
    ),
) -> None:
    """Reconstructed IPA pronunciation."""
    from aegean import greek

    if period not in ("attic", "koine"):
        raise fail("--period must be attic or koine")
    try:
        print(greek.to_ipa(read_text(text), period=period))  # type: ignore[arg-type]
    except ValueError as exc:
        raise fail(str(exc)) from None


@greek_app.command("missing-forms")
def missing_forms_cmd(
    corpus: str = typer.Argument(..., help="A corpus id, .json/.db file, work id, or -."),
    limit: int = typer.Option(0, "--limit", "--top", help="Cap the list (0 = all)."),
    tagger: bool = TAGGER_OPT,
    lemmatizer: bool = LEMMATIZER_OPT,
    neural_lemmatizer: bool = NEURAL_LEMM_OPT,
    neural: bool = NEURAL_OPT,
    neural_variant: str = NEURAL_VARIANT_OPT,
    json_out: bool = JSON_OPT,
) -> None:
    """The Greek word forms the active lemmatizer cannot resolve, ranked by frequency.

    Each row is a candidate for a sourced contribution (see CONTRIBUTING's "Contributing
    sourced data"): confirm the form against a dictionary or edition before adding it. The
    result reflects whichever lemmatizer backends are active (the offline baseline by
    default; --treebank/--neural etc. resolve more).
    """
    from aegean import greek

    _activate(
        tagger=tagger,
        lemmatizer=lemmatizer,
        neural_lemmatizer=neural_lemmatizer,
        neural=neural,
        neural_variant=neural_variant,
    )
    c = load_corpus(corpus)
    forms = greek.missing_forms(c, limit=limit)
    if json_out:
        emit_json([
            {"form": m.form, "count": m.count,
             "example_doc_id": m.example_doc_id, "example_position": m.example_position}
            for m in forms
        ])
        return
    if not forms:
        print("no unresolved forms: the active lemmatizer covers this corpus")
        return
    table(
        f"unresolved forms: {corpus}",
        ["form", "count", "example"],
        [[m.form, str(m.count), f"{m.example_doc_id}:{m.example_position}"] for m in forms],
    )


@greek_app.command()
def profile(text: str = TEXT_ARG, json_out: bool = JSON_OPT) -> None:
    """Describe the observable features of a text (script, polytonic, Beta Code, editorial marks).

    Reports what the characters ARE (writing system, accents/breathings, majuscule share,
    apparatus markers, numeral density), never a genre or an out-of-domain guess.
    """
    import dataclasses

    from aegean import greek

    p = greek.profile_text(read_text(text))
    d = dataclasses.asdict(p)
    if emit_result(d, json_output=json_out, output=None):
        return
    rows = [[k, str(v)] for k, v in d.items()]
    table("text profile", ["feature", "value"], rows)


@greek_app.command()
def accentuate(
    word: str = typer.Argument(..., help="The Greek word (any existing accent is re-placed)."),
    recessive: bool = typer.Option(
        True, "--recessive/--persistent",
        help="Recessive (finite verbs, the default) vs persistent (nominals; needs --lemma)."),
    lemma: str = typer.Option(
        "", "--lemma", help="The lemma whose written accent fixes the home syllable (persistent)."),
    json_out: bool = JSON_OPT,
) -> None:
    """Place the legal accent on a word, by the limitation laws (recessive verb / persistent nominal)."""
    from aegean import greek

    ap = greek.place_accent(word, recessive=recessive, lemma=lemma or None)
    if json_out:
        emit_json({
            "form": ap.form, "accent": ap.accent_type, "position_from_end": ap.position_from_end,
            "classification": ap.classification, "certain": ap.certain, "note": ap.note,
        })
        return
    suffix = "" if ap.certain else f"  (uncertain: {ap.note})"
    print(f"{ap.form}\t{ap.classification}{suffix}")


@greek_app.command()
def sandhi(
    word: str = typer.Argument(..., help="A Greek token (crasis / elision / movable-nu are resolved)."),
    json_out: bool = JSON_OPT,
) -> None:
    """Resolve a surface contraction (crasis / elision / movable-nu) to its underlying word(s)."""
    from aegean import greek

    r = greek.resolve_sandhi(word)
    if json_out:
        emit_json({
            "surface": r.surface, "words": list(r.words), "kind": r.kind,
            "uncertain": r.uncertain, "note": r.note,
        })
        return
    if r.kind is None:
        print(word)
        return
    flag = "  (uncertain)" if r.uncertain else ""
    print(f"{' '.join(r.words)}\t{r.kind}{flag}")


@greek_app.command()
def tag(
    text: str = TEXT_ARG,
    treebank: bool = TREEBANK_OPT,
    tagger: bool = TAGGER_OPT,
    neural: bool = NEURAL_OPT,
    neural_variant: str = NEURAL_VARIANT_OPT,
    json_out: bool = JSON_OPT,
) -> None:
    """POS-tag a text (UD coarse tags), with the activated backends."""
    from aegean import greek

    _activate(
        treebank=treebank,
        tagger=tagger,
        neural=neural,
        neural_variant=neural_variant,
    )
    try:
        pairs = greek.pos_tags(read_text(text))
    except greek.NeuralInputTooLongError as exc:
        raise fail(str(exc)) from None
    if json_out:
        emit_json([{"token": t, "upos": u} for t, u in pairs])
        return
    print("\n".join(f"{t}\t{u}" for t, u in pairs))


@greek_app.command()
def lemmatize(
    text: str = TEXT_ARG,
    treebank: bool = TREEBANK_OPT,
    lemmatizer: bool = LEMMATIZER_OPT,
    neural_lemmatizer: bool = NEURAL_LEMM_OPT,
    neural: bool = NEURAL_OPT,
    neural_variant: str = NEURAL_VARIANT_OPT,
    json_out: bool = JSON_OPT,
) -> None:
    """Lemmatize every word of a text, with the activated backends."""
    from aegean import greek

    _activate(
        treebank=treebank, lemmatizer=lemmatizer,
        neural_lemmatizer=neural_lemmatizer, neural=neural,
        neural_variant=neural_variant,
    )
    words = greek.tokenize_words(read_text(text))
    rows = []
    for w in words:
        lemma, known = greek.lemmatize_verbose(w)
        rows.append({"form": w, "lemma": lemma, "known": known})
    if json_out:
        emit_json(rows)
        return
    for r in rows:
        mark = "" if r["known"] else "   (fallback)"
        print(f"{r['form']}\t{r['lemma']}{mark}")


@greek_app.command()
def morph(
    word: str = WORD_ARG,
    treebank: bool = TREEBANK_OPT,
    json_out: bool = JSON_OPT,
) -> None:
    """Morphological analysis: candidate parses with case/number/gender/tense/…"""
    from dataclasses import asdict

    from aegean import greek

    _activate(treebank=treebank)
    analyses = greek.analyze(word)
    if json_out:
        emit_json([asdict(a) for a in analyses])
        return
    if not analyses:
        print(f"{word}: no analysis")
        return
    for a in analyses:
        print(str(a))


# The closed value set of each inflection feature (the AGDT postag vocabulary); a value
# outside its set is a typo, distinct from a valid-but-unattested paradigm cell.
_INFLECT_VALUES: dict[str, tuple[str, ...]] = {
    "case": ("nom", "gen", "dat", "acc", "voc", "loc"),
    "number": ("sg", "pl", "du"),
    "gender": ("masc", "fem", "neut"),
    "tense": ("pres", "impf", "aor", "perf", "plup", "fut", "futperf"),
    "voice": ("act", "mid", "pass", "mp"),
    "mood": ("ind", "subj", "opt", "inf", "imp", "part"),
    "person": ("1", "2", "3"),
    "pos": ("NOUN", "VERB", "ADJ", "ADV", "DET", "PART", "CCONJ", "ADP",
            "PRON", "NUM", "INTJ", "PUNCT", "X"),
}


@greek_app.command()
def inflect(
    lemma: str = typer.Argument(..., help="Greek lemma (dictionary form)."),
    case: str = typer.Option("", "--case", help="nom/gen/dat/acc/voc/loc"),
    number: str = typer.Option("", "--number", help="sg/pl/du"),
    gender: str = typer.Option("", "--gender", help="masc/fem/neut"),
    tense: str = typer.Option("", "--tense", help="pres/impf/aor/perf/plup/fut/futperf"),
    voice: str = typer.Option("", "--voice", help="act/mid/pass/mp"),
    mood: str = typer.Option("", "--mood", help="ind/subj/opt/inf/imp/part"),
    person: str = typer.Option("", "--person", help="1/2/3"),
    pos: str = typer.Option("", "--pos", help="NOUN/VERB/ADJ/…"),
    full: bool = typer.Option(False, "--paradigm", help="List the full attested paradigm instead."),
    json_out: bool = JSON_OPT,
) -> None:
    """Inflection synthesis (inverse lemmatizer): attested form(s) of a lemma for the
    given features, from the AGDT. With --paradigm, list every attested cell."""
    from aegean import greek

    want = {
        "case": case, "number": number, "gender": gender, "tense": tense,
        "voice": voice, "mood": mood, "person": person, "pos": pos,
    }
    for name, value in want.items():
        if not value:
            continue
        canonical = value.upper() if name == "pos" else value.lower()
        if canonical not in _INFLECT_VALUES[name]:
            raise fail(
                f"--{name} must be one of {', '.join(_INFLECT_VALUES[name])}; got {value!r}"
            )
        want[name] = canonical

    print("aegean: activating inflection synthesis (first use may download/build)…", file=sys.stderr)
    try:
        greek.use_inflector()
    except Exception as exc:
        raise fail(f"could not activate inflection synthesis: {exc}") from None

    if full:
        cells = greek.paradigm(lemma)
        if json_out:
            emit_json([{"features": f, "form": form} for f, form in cells])
            return
        if not cells:
            print(f"{lemma}: no attested forms")
            return
        for feats, form in cells:
            print(f"{form}\t{' '.join(f'{k}={v}' for k, v in feats.items())}")
        return

    forms = greek.inflect(lemma, **{k: v for k, v in want.items() if v})
    if json_out:
        emit_json(list(forms))
        return
    print(" ".join(forms) if forms else f"{lemma}: no attested form for those features")


@greek_app.command()
def rarity(
    text: str = TEXT_ARG,
    corpus: str = typer.Option(
        "nt", "--corpus",
        help="Reference corpus: a corpus id (default nt, the Greek NT), a Greek work id, "
        "a path to a .json/.db corpus, or '-' for JSON on stdin.",
    ),
    top: int = typer.Option(5, "--top", "--limit", help="Show the N rarest words."),
    treebank: bool = TREEBANK_OPT,
    json_out: bool = JSON_OPT,
) -> None:
    """Terminology rarity of a text vs a reference corpus — a translation-difficulty signal.

    Rarity is relative to the chosen corpus's vocabulary; rare/technical terms score high."""
    from aegean import greek

    _activate(treebank=treebank)
    if corpus == "nt":
        print("aegean: loading the Greek NT reference corpus (first use may download)…", file=sys.stderr)
    ref = load_corpus(corpus)
    r = greek.terminology_rarity(read_text(text), ref)
    if json_out:
        emit_json({
            "overall": r.overall, "corpus_lemmas": r.corpus_lemmas, "corpus_tokens": r.corpus_tokens,
            "words": [
                {"word": w.word, "lemma": w.lemma, "count": w.count,
                 "rarity": round(w.rarity, 3), "label": w.label}
                for w in r.words
            ],
        })
        return
    print(f"overall rarity {r.overall:.2f}  (vs {r.corpus_lemmas} lemmas / {r.corpus_tokens} tokens)")
    for w in r.hardest(top):
        print(f"  {w.word}\t{w.label}\t{w.rarity:.2f}  (lemma {w.lemma}, ×{w.count})")


@greek_app.command()
def usage(
    word: str = WORD_ARG,
    json_out: bool = JSON_OPT,
) -> None:
    """Dialect and register tags for a word, mined from its LSJ entry (fetches the LSJ index on first use)."""
    from aegean import greek

    _activate(lsj=True)
    u = greek.usage(word)
    if json_out:
        emit_json({"word": word, "dialects": list(u.dialects), "registers": list(u.registers)})
        return
    print(f"{word}: dialects={', '.join(u.dialects) or '—'}  registers={', '.join(u.registers) or '—'}")


@greek_app.command()
def parse(
    sentence: str = TEXT_ARG,
    neural: bool = NEURAL_OPT,
    neural_variant: str = NEURAL_VARIANT_OPT,
    parser: bool = typer.Option(
        False, "--parser", help="Activate the pure-Python arc-eager parser (trains on first use)."
    ),
    json_out: bool = JSON_OPT,
) -> None:
    """Dependency-parse a sentence (UD relations with --neural; AGDT with --parser)."""
    from aegean import greek

    _activate(neural=neural, neural_variant=neural_variant, parser=parser)
    try:
        tree = greek.parse(read_text(sentence))
    except greek.ParserNotLoadedError:
        raise fail("no parser active — pass --neural (best) or --parser") from None
    except greek.NeuralInputTooLongError as exc:
        raise fail(str(exc)) from None
    if json_out:
        emit_json(
            [
                {"id": t.id, "form": t.form, "lemma": t.lemma, "upos": t.upos,
                 "head": t.head, "relation": t.relation, "postag": t.postag}
                for t in tree.tokens
            ]
        )
        return
    table(
        "dependency parse",
        ["id", "form", "lemma", "upos", "head", "relation"],
        [[str(t.id), t.form, t.lemma, t.upos, str(t.head), t.relation] for t in tree.tokens],
    )


@greek_app.command()
def gloss(
    lemma: str = typer.Argument(..., help="A lemma (or a form — it is lemmatized first)."),
    dictionary: str = typer.Option(
        "lsj", "--dict", "-d",
        help="Which dictionary: lsj, middle-liddell, cunliffe, abbott-smith, dodson "
        "(see `aegean greek lexica`).",
    ),
    full: bool = typer.Option(False, "--full", help="Show the full entry, not just the concise gloss."),
    json_out: bool = JSON_OPT,
) -> None:
    """Gloss a word from a registry dictionary (activates it; may fetch on first use).

    Defaults to LSJ. For dictionaries pyaegean does not host (Autenrieth, Slater, …),
    use `aegean greek lexicon-link`.
    """
    from aegean import greek

    if not json_out:
        print(
            f"aegean: activating the {dictionary} lexicon (first use may download/build)…",
            file=sys.stderr,
        )
    try:
        greek.use_lexicon(dictionary)
    except ValueError as exc:  # a deep-link-only lexicon
        # the library error names the Python call; the CLI user has `lexicon-link`
        msg = str(exc).replace("greek.lexicon_link(word)", "`aegean greek lexicon-link`")
        raise fail(msg) from None
    except KeyError:
        raise fail(f"unknown dictionary {dictionary!r}; see `aegean greek lexica`") from None
    except Exception as exc:
        raise fail(f"could not activate {dictionary!r}: {exc}") from None

    e = greek.entry(lemma, dictionary=dictionary)
    if e is None:
        raise fail(f"no {dictionary} entry found for {lemma!r}")
    if json_out:
        emit_json({
            "query": lemma, "dictionary": dictionary, "headword": e.headword,
            "gloss": e.gloss, "definition": e.body,
        })
    elif full:
        console().print(f"{e.headword}: {e.body}", markup=False)
    else:
        print(f"{e.headword}: {e.gloss}")


@greek_app.command()
def lexica(json_out: bool = JSON_OPT) -> None:
    """List the dictionaries available for `gloss --dict` and `lexicon-link`."""
    from aegean import greek

    infos = greek.lexica()
    if json_out:
        emit_json([
            {"id": i.id, "name": i.name, "scope": i.scope, "hosted": i.hosted, "license": i.license}
            for i in infos
        ])
        return
    table(
        "lexica",
        ["id", "scope", "kind", "name"],
        [[i.id, i.scope, "hosted" if i.hosted else "link", i.name] for i in infos],
    )


@greek_app.command("lexicon-link")
def lexicon_link(
    word: str = WORD_ARG,
    service: str = typer.Option("logeion", "--service", help="logeion or perseus."),
    no_lemmatize: bool = typer.Option(
        False, "--no-lemmatize", help="Link the surface form, not its lemma."
    ),
    json_out: bool = JSON_OPT,
) -> None:
    """Deep-link a word to an online dictionary aggregator (Logeion by default).

    Covers dictionaries pyaegean does not host (Autenrieth, Slater, Montanari, …).
    """
    from aegean import greek

    try:
        url = greek.lexicon_link(word, service=service, lemmatize=not no_lemmatize)
    except KeyError as exc:  # str(KeyError) is a repr — it would double the quotes
        raise fail(exc.args[0] if exc.args else str(exc)) from None
    if json_out:
        emit_json({"word": word, "service": service, "url": url})
    else:
        print(url)


@greek_app.command("stream")
def stream(
    source: str = typer.Argument(
        "-",
        metavar="INPUT",
        help="JSONL file of token arrays; '-' reads JSONL from stdin.",
    ),
    batch_size: int | None = typer.Option(
        None,
        "--batch-size",
        min=1,
        help="Analyze up to N sentences per backend batch (default: one at a time).",
    ),
    long_input: str = typer.Option(
        "strict",
        "--long-input",
        help="Long-sentence handling: strict, partial, or windowed.",
    ),
    partial: bool = typer.Option(
        False,
        "--partial",
        help="Alias for --long-input partial.",
    ),
    windowed: bool = typer.Option(
        False,
        "--windowed",
        help="Alias for --long-input windowed.",
    ),
    with_probs: bool = typer.Option(
        False,
        "--confidence",
        "--with-probs",
        help="Include calibrated per-token confidence (loads the shipped calibration).",
    ),
    domain: str | None = typer.Option(
        None,
        "--confidence-domain",
        "--domain",
        metavar="LABEL",
        help="Calibration domain label (requires --with-probs).",
    ),
    policy: Path | None = typer.Option(
        None,
        "--confidence-policy",
        "--policy",
        metavar="PATH",
        help="Abstention policy JSON (requires --with-probs).",
    ),
    neural_variant: str = NEURAL_VARIANT_OPT,
    json_out: bool = JSON_OPT,
) -> None:
    """Stream neural analyses from JSONL token arrays to JSONL stdout.

    Each non-empty input line must be a JSON array of token strings, for example
    ``["token-1", "token-2"]``. One complete ``SentenceAnalysis`` object is emitted for
    every line as soon as it is ready, with no document-sized result list held in
    memory.  Output is JSONL even when ``--json`` is supplied; the flag is accepted
    for consistency with the other data-producing Greek commands.
    """
    from aegean import greek

    del json_out  # JSONL is the only output format for this streaming command.
    if long_input not in ("strict", "partial", "windowed"):
        raise fail("--long-input must be strict, partial, or windowed")
    if partial and windowed:
        raise fail("--partial and --windowed are mutually exclusive")
    if (partial or windowed) and long_input != "strict":
        raise fail("--partial/--windowed cannot be combined with --long-input")
    if partial:
        long_input = "partial"
    elif windowed:
        long_input = "windowed"
    if domain is not None and not with_probs:
        raise fail("--confidence-domain requires --confidence")
    if policy is not None and not with_probs:
        raise fail("--confidence-policy requires --confidence")

    loaded_policy = _load_confidence_policy(policy) if policy is not None else None
    _activate(neural=True, neural_variant=neural_variant)
    if with_probs:
        _ensure_calibration()

    # The source is a generator, so this call validates options and captures the
    # active backend before opening/consuming a path or stdin.
    try:
        analyses = greek.iter_analyze_sentences(
            _jsonl_sentences(source),
            batch_size=batch_size,
            with_probs=with_probs,
            long_input=cast(Literal["strict", "partial", "windowed"], long_input),
            domain=domain,
            policy=loaded_policy,
        )
        for analysis in analyses:
            _emit_jsonl(analysis)
    except (BrokenPipeError, KeyboardInterrupt):
        raise
    except Exception as exc:
        raise fail(f"could not stream neural analyses: {exc}") from None


@greek_app.command()
def pipeline(
    text: str = TEXT_ARG,
    parse: bool = typer.Option(False, "--parse", help="Also dependency-parse (needs --neural or --parser)."),
    parser: bool = typer.Option(False, "--parser", help="Activate the arc-eager parser for --parse."),
    treebank: bool = TREEBANK_OPT,
    tagger: bool = TAGGER_OPT,
    lemmatizer: bool = LEMMATIZER_OPT,
    neural_lemmatizer: bool = NEURAL_LEMM_OPT,
    neural: bool = NEURAL_OPT,
    neural_variant: str = NEURAL_VARIANT_OPT,
    confidence: bool = CONFIDENCE_OPT,
    confidence_domain: str | None = typer.Option(
        None,
        "--confidence-domain",
        metavar="LABEL",
        help="Scope calibrated confidence to an explicit evidence domain (requires --confidence).",
    ),
    confidence_policy: Path | None = typer.Option(
        None,
        "--confidence-policy",
        metavar="PATH",
        help="Load an explicit abstention policy JSON (requires --confidence).",
    ),
    partial: bool = typer.Option(
        False,
        "--partial",
        help="Return explicitly marked placeholders past the neural subword limit (default: fail).",
    ),
    windowed: bool = typer.Option(
        False,
        "--windowed",
        help="Analyze supported long neural input in overlapping whole-word windows.",
    ),
    sentence_policy: str = typer.Option(
        "default",
        "--sentence-policy",
        help="Sentence policy: default, prose, verse, inscription, or papyrus.",
    ),
    output: Path | None = RESULT_OPT,
    json_out: bool = JSON_OPT,
) -> None:
    """The one-call pipeline: per-token records for a whole text."""
    from aegean import greek

    if partial and windowed:
        raise fail("--partial and --windowed are mutually exclusive")
    if confidence_domain is not None and not confidence:
        raise fail("--confidence-domain requires --confidence")
    if confidence_policy is not None and not confidence:
        raise fail("--confidence-policy requires --confidence")
    loaded_policy = (
        _load_confidence_policy(confidence_policy)
        if confidence_policy is not None
        else None
    )

    _activate(
        treebank=treebank, tagger=tagger, lemmatizer=lemmatizer,
        neural_lemmatizer=neural_lemmatizer, neural=neural,
        neural_variant=neural_variant, parser=parser,
    )
    if confidence:
        _ensure_calibration()
    try:
        pipeline_kwargs: dict[str, Any] = {
            "parse": parse,
            "with_confidence": confidence,
            "long_input": "partial" if partial else "windowed" if windowed else "strict",
            "sentence_policy": sentence_policy,
        }
        if confidence_domain is not None:
            pipeline_kwargs["confidence_domain"] = confidence_domain
        if loaded_policy is not None:
            pipeline_kwargs["confidence_policy"] = loaded_policy
        records = greek.pipeline(read_text(text), **pipeline_kwargs)
    except greek.ParserNotLoadedError:
        raise fail("--parse needs a parser — pass --neural (best) or --parser") from None
    except (greek.NeuralInputTooLongError, greek.NeuralWindowingError) as exc:
        raise fail(str(exc)) from None
    except ValueError as exc:
        raise fail(str(exc)) from None
    from aegean._view import format_confidence, pipeline_rows_from_records

    rows = pipeline_rows_from_records(records)  # the row shape shared with the TUI
    warning = next((r["analysis_warning"] for r in rows if r["analysis_warning"]), None)
    if warning:
        typer.echo(f"warning: {warning}", err=True)
    if emit_result(rows, json_output=json_out, output=output):
        return
    # A calibrated 'conf' column appears only when the rows actually carry a confidence
    # (--confidence with the neural pipeline active); --json keeps the raw floats/None.
    has_conf = bool(rows) and "upos_confidence" in rows[0]
    columns = ["s", "i", "token", "upos", "lemma", "src", "head", "rel", "feats"]
    if has_conf:
        columns.append("conf")
    # 'src' marks identity/unresolved lemma fallbacks; a blank is not a correctness
    # verdict. The full class is always in --json (lemma_source).
    table(
        f"{len(rows)} token(s)",
        columns,
        [
            [str(r["sentence"]), str(r["index"]), r["text"], r["upos"], r["lemma"],
             r["lemma_source"] if r["review_recommended"] else "",
             "" if r["head"] is None else str(r["head"]), r["relation"] or "", r["feats"] or ""]
            + ([format_confidence(r["upos_confidence"], r["lemma_confidence"])] if has_conf else [])
            for r in rows
        ],
    )


@greek_app.command()
def explain(
    text: str = TEXT_ARG,
    treebank: bool = TREEBANK_OPT,
    tagger: bool = TAGGER_OPT,
    lemmatizer: bool = LEMMATIZER_OPT,
    neural_lemmatizer: bool = NEURAL_LEMM_OPT,
    neural: bool = NEURAL_OPT,
    neural_variant: str = NEURAL_VARIANT_OPT,
    confidence: bool = CONFIDENCE_OPT,
    output: Path | None = RESULT_OPT,
    json_out: bool = JSON_OPT,
) -> None:
    """Explain what the pipeline did to each token and why (lemma evidence classes).

    Each row shows the analysis plus the lemma's evidence class (attested / neural_lookup /
    neural_edit / neural / rule / seed / paradigm / identity / unresolved / punct / user)
    and a plain-language note; identity
    and unresolved rows are flagged for review. Source classes are the honesty
    surface: by default there are no confidence numbers. Pass --confidence (with
    --neural) to additionally append each token's calibrated confidence to its note
    (temperature-scaled, model-only; loads the shipped calibration).
    """
    from aegean import greek
    from aegean.greek.explain import explain_pipeline, render_explanations

    _activate(
        treebank=treebank, tagger=tagger, lemmatizer=lemmatizer,
        neural_lemmatizer=neural_lemmatizer, neural=neural,
        neural_variant=neural_variant,
    )
    if confidence:
        _ensure_calibration()
    try:
        explanations = explain_pipeline(read_text(text), with_confidence=confidence)
    except greek.NeuralInputTooLongError as exc:
        raise fail(str(exc)) from None
    rows = [to_plain(e) for e in explanations]  # dataclass → dict, enum → value
    if emit_result(rows, json_output=json_out, output=output):
        return
    print(render_explanations(explanations))

