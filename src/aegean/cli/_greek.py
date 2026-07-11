"""The `aegean greek` group: the full Greek NLP pipeline from the shell, plus
dictionary glossing.

Backend flags mirror the `use_*` activation functions: ``--treebank``,
``--tagger``, ``--lemmatizer``, ``--neural-lemmatizer``, ``--neural`` (the joint
pipeline), ``--lsj``. Each activation may download its data/model to the cache on
first use (a note goes to stderr); afterwards everything is offline. The lexicon
commands (`gloss`, `gloss-nt`, `lexica`, `lexicon-link`) reach the dictionary
registry; `gloss --dict <id>` picks which dictionary to use.
"""

from __future__ import annotations

import sys
from pathlib import Path

import typer

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
    write_corpus,
)

greek_app = typer.Typer(
    pretty_exceptions_show_locals=False,
    help="Greek NLP (normalize → … → parse), dictionaries, real works (Perseus/NT), "
    "and the eval reproductions.",
    no_args_is_help=True,
)

TEXT_ARG = typer.Argument(..., help="Greek text ('-' reads stdin).")
WORD_ARG = typer.Argument(..., help="One Greek word.")

TREEBANK_OPT = typer.Option(False, "--treebank", help="Activate the Perseus AGDT lexicon (~75 MB fetch on first use).")
TAGGER_OPT = typer.Option(False, "--tagger", help="Activate the generalizing POS tagger (trains from the AGDT on first use).")
LEMMATIZER_OPT = typer.Option(False, "--lemmatizer", help="Activate the edit-tree lemmatizer (trains from the AGDT on first use).")
NEURAL_LEMM_OPT = typer.Option(False, "--neural-lemmatizer", help="Activate the seq2seq lemmatizer (~232 MB model, \\[neural] extra).")
NEURAL_OPT = typer.Option(False, "--neural", help="Activate the joint neural pipeline (~173 MB model, \\[neural] extra).")
LSJ_OPT = typer.Option(False, "--lsj", help="Activate LSJ glossing (~270 MB fetch on first use).")
CONFIDENCE_OPT = typer.Option(
    False, "--confidence",
    help="Attach calibrated confidence (loads the shipped calibration). Needs --neural: "
    "it is model-only, so identity/punctuation lemmas carry none (a lookup-composed lemma "
    "does — the calibration covers the model's internal training-form lookup).",
)


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


def _activate(
    *,
    treebank: bool = False,
    tagger: bool = False,
    lemmatizer: bool = False,
    neural_lemmatizer: bool = False,
    neural: bool = False,
    lsj: bool = False,
    parser: bool = False,
) -> None:
    """Run the requested use_* activations, with a stderr note for slow ones."""
    from collections.abc import Callable

    from aegean import greek

    steps: list[tuple[bool, str, Callable[[], object]]] = [
        (treebank, "treebank (Perseus AGDT)", greek.use_treebank),
        (tagger, "POS tagger", greek.use_tagger),
        (lemmatizer, "edit-tree lemmatizer", greek.use_lemmatizer),
        (neural_lemmatizer, "neural lemmatizer", greek.use_neural_lemmatizer),
        (neural, "neural joint pipeline", greek.use_neural_pipeline),
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
    json_out: bool = JSON_OPT,
) -> None:
    """Tokenize into words+punctuation (or sentences with --sentences)."""
    from aegean import greek

    s = read_text(text)
    if sentences:
        out = greek.sentences(s)
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
    json_out: bool = JSON_OPT,
) -> None:
    """The Greek word forms the active lemmatizer cannot resolve, ranked by frequency.

    Each row is a candidate for a sourced contribution (see CONTRIBUTING's "Contributing
    sourced data"): confirm the form against a dictionary or edition before adding it. The
    result reflects whichever lemmatizer backends are active (the offline baseline by
    default; --treebank/--neural etc. resolve more).
    """
    from aegean import greek

    _activate(tagger=tagger, lemmatizer=lemmatizer,
              neural_lemmatizer=neural_lemmatizer, neural=neural)
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

    p = greek.profile_text(read_text(text))  # type: ignore[arg-type]
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
    json_out: bool = JSON_OPT,
) -> None:
    """POS-tag a text (UD coarse tags), with the activated backends."""
    from aegean import greek

    _activate(treebank=treebank, tagger=tagger, neural=neural)
    pairs = greek.pos_tags(read_text(text))
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
    json_out: bool = JSON_OPT,
) -> None:
    """Lemmatize every word of a text, with the activated backends."""
    from aegean import greek

    _activate(
        treebank=treebank, lemmatizer=lemmatizer,
        neural_lemmatizer=neural_lemmatizer, neural=neural,
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
    parser: bool = typer.Option(
        False, "--parser", help="Activate the pure-Python arc-eager parser (trains on first use)."
    ),
    json_out: bool = JSON_OPT,
) -> None:
    """Dependency-parse a sentence (UD relations with --neural; AGDT with --parser)."""
    from aegean import greek

    _activate(neural=neural, parser=parser)
    try:
        tree = greek.parse(read_text(sentence))
    except greek.ParserNotLoadedError:
        raise fail("no parser active — pass --neural (best) or --parser") from None
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


@greek_app.command("gloss-nt")
def gloss_nt(
    word: str = typer.Argument(..., help="A Greek word, or a Strong's number with --strongs."),
    strongs: bool = typer.Option(False, "--strongs", help="Treat the argument as a Strong's number."),
    full: bool = typer.Option(False, "--full", help="Show the full Dodson entry (lemma + definition)."),
    json_out: bool = JSON_OPT,
) -> None:
    """Koine (New Testament) gloss from the bundled Dodson lexicon — no download (CC0)."""
    from aegean import greek

    greek.use_dodson()
    if strongs:
        g = greek.gloss_strongs(word)
        if g is None:
            raise fail(f"no Dodson entry for Strong's {word!r}")
        if json_out:
            emit_json({"strongs": word, "gloss": g})
        else:
            print(g)
        return
    entry = greek.lookup_nt(word)
    if entry is None:
        raise fail(f"no Dodson entry for {word!r}")
    if json_out:
        emit_json({
            "word": word, "lemma": entry.lemma, "strongs": entry.strongs,
            "gloss": entry.gloss, "definition": entry.definition,
        })
    elif full:
        console().print(f"{entry.lemma} (G{entry.strongs}): {entry.definition}", markup=False)
    else:
        print(entry.gloss)


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
    confidence: bool = CONFIDENCE_OPT,
    output: Path | None = RESULT_OPT,
    json_out: bool = JSON_OPT,
) -> None:
    """The one-call pipeline: per-token records for a whole text."""
    from aegean import greek

    _activate(
        treebank=treebank, tagger=tagger, lemmatizer=lemmatizer,
        neural_lemmatizer=neural_lemmatizer, neural=neural, parser=parser,
    )
    if confidence:
        _ensure_calibration()
    try:
        records = greek.pipeline(read_text(text), parse=parse, with_confidence=confidence)
    except greek.ParserNotLoadedError:
        raise fail("--parse needs a parser — pass --neural (best) or --parser") from None
    from aegean._view import format_confidence, pipeline_rows_from_records

    rows = pipeline_rows_from_records(records)  # the row shape shared with the TUI
    if emit_result(rows, json_output=json_out, output=output):
        return
    # A calibrated 'conf' column appears only when the rows actually carry a confidence
    # (--confidence with the neural pipeline active); --json keeps the raw floats/None.
    has_conf = bool(rows) and "upos_confidence" in rows[0]
    columns = ["s", "i", "token", "upos", "lemma", "src", "head", "rel", "feats"]
    if has_conf:
        columns.append("conf")
    # 'src' shows the lemma's evidence class only when it is worth a second look
    # (an identity fall-through or an unresolved miss); grounded lemmas leave it blank
    # so the table stays scannable. The full class is always in --json (lemma_source).
    table(
        f"{len(rows)} token(s)",
        columns,
        [
            [str(r["sentence"]), str(r["index"]), r["text"], r["upos"], r["lemma"],
             "" if r["lemma_known"] else r["lemma_source"],
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
    confidence: bool = CONFIDENCE_OPT,
    output: Path | None = RESULT_OPT,
    json_out: bool = JSON_OPT,
) -> None:
    """Explain what the pipeline did to each token and why (lemma evidence classes).

    Each row shows the analysis plus the lemma's evidence class (attested / neural /
    rule / seed / paradigm / identity / unresolved / punct) and a plain-language note; identity
    and unresolved rows are flagged for review. Source classes are the honesty
    surface: by default there are no confidence numbers. Pass --confidence (with
    --neural) to additionally append each token's calibrated confidence to its note
    (temperature-scaled, model-only; loads the shipped calibration).
    """
    from aegean.greek.explain import explain_pipeline, render_explanations

    _activate(
        treebank=treebank, tagger=tagger, lemmatizer=lemmatizer,
        neural_lemmatizer=neural_lemmatizer, neural=neural,
    )
    if confidence:
        _ensure_calibration()
    explanations = explain_pipeline(read_text(text), with_confidence=confidence)
    rows = [to_plain(e) for e in explanations]  # dataclass → dict, enum → value
    if emit_result(rows, json_output=json_out, output=output):
        return
    print(render_explanations(explanations))


def _work_all(
    author: str | None,
    *,
    source: str,
    limit: int,
    dry_run: bool,
    assume_yes: bool,
    json_out: bool,
) -> None:
    """`greek work all [author]`: bulk-fetch every catalogue work by an author (or all)."""
    import os

    from aegean.data import DataNotAvailableError, FetchAborted
    from aegean.greek import GitHubRateLimitError, WorkFetchResult
    from aegean.greek import catalog as greek_catalog
    from aegean.greek import fetch_works, list_fetched_works

    if source not in ("auto", "perseus", "first1k"):
        raise fail("--source must be auto, perseus, or first1k")
    src = None if source == "auto" else source
    rows = greek_catalog(author=author, source=src)
    fetched_ids = {w["id"] for w in list_fetched_works()}
    pending = [r for r in rows if r["id"] not in fetched_ids]

    if not rows:
        if json_out:
            emit_json({"mode": "all", "author": author, "matched": 0, "works": []})
        else:
            who = f"author {author!r}" if author else "the catalogue"
            hint = f" — try `aegean greek catalog {author}`" if author else ""
            print(f"no works match {who}{hint}")
        return

    if dry_run:
        preview = [
            {"id": r["id"], "author": r["author"], "title": r["title"],
             "status": "cached" if r["id"] in fetched_ids else "pending"}
            for r in rows
        ]
        if json_out:
            emit_json({"mode": "all", "author": author, "matched": len(rows), "dry_run": True,
                       "to_fetch": len(pending), "cached": len(rows) - len(pending), "works": preview})
            return
        table(f"greek work all {author or ''} (dry run)".strip(),
              ["id", "author", "title", "status"],
              [[p["id"], p["author"], p["title"], p["status"]] for p in preview])
        print(f"\n{len(pending)} to fetch, {len(rows) - len(pending)} already cached. "
              "Run without --dry-run to fetch.")
        return

    if len(pending) > 50 and not assume_yes and not json_out:
        has_token = bool(os.environ.get("PYAEGEAN_GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN"))
        rate = ("5,000/hr (token set)" if has_token
                else "~60/hr unauthenticated — set PYAEGEAN_GITHUB_TOKEN to raise it")
        if sys.stdin.isatty():
            if not typer.confirm(f"Fetch {len(pending)} works? Each needs a GitHub API call ({rate})."):
                raise fail("aborted")
        else:
            raise fail(f"{len(pending)} works exceeds the safe unauthenticated batch — "
                       "pass --yes to confirm or --limit N to cap")

    lim = limit if limit > 0 else None
    results: list[WorkFetchResult] = []
    stopped: str | None = None
    note: str | None = None

    def progress(i: int, total: int, w: dict[str, str]) -> None:
        print(f"[{i}/{total}] {w['id']} ({w.get('author', '')} — {w.get('title', '')})…",
              file=sys.stderr)

    # --json stays quiet on stderr so its stdout is a clean, parseable document
    on_progress = None if json_out else progress
    try:
        for res in fetch_works(author=author, works=rows, source=src, limit=lim, on_progress=on_progress):
            results.append(res)
            if not json_out:
                print(f"    {res.status}" + (f": {res.error}" if res.error else ""), file=sys.stderr)
    except GitHubRateLimitError as exc:
        stopped, note = "rate_limit", str(exc)
    except FetchAborted:
        stopped = "aborted"
    except KeyboardInterrupt:
        stopped, note = "aborted", "interrupted — already-cached works are kept"
    except DataNotAvailableError as exc:
        stopped, note = "failed", str(exc)

    summary = {
        "mode": "all", "author": author, "matched": len(rows),
        "fetched": sum(r.status == "fetched" for r in results),
        "cached": sum(r.status == "cached" for r in results),
        "failed": sum(r.status == "failed" for r in results),
        "stopped": stopped,
        "works": [to_plain(r) for r in results],
    }
    if note:
        summary["message"] = note
    if json_out:
        emit_json(summary)
        return
    table(f"greek work all {author or ''}".strip(),
          ["id", "author", "title", "status"],
          [[r.id, r.author, r.title, r.status] for r in results])
    print(f"\nfetched {summary['fetched']}, cached {summary['cached']}, failed {summary['failed']}"
          + (f" — stopped: {stopped}" if stopped else ""), file=sys.stderr)
    if note:
        print(note, file=sys.stderr)


@greek_app.command()
def work(
    work_id: str | None = typer.Argument(
        None, help="CTS-style work id, e.g. tlg0012.tlg001 (Iliad); or 'all' to bulk-fetch by author."
    ),
    author: str | None = typer.Argument(
        None, help="With 'all': fetch every work by this author (case-insensitive)."
    ),
    ref: str | None = typer.Option(
        None, "--ref", help="Select a section: '1' (book), '1.2' (chapter), '1.1-1.50' (lines)."
    ),
    source: str = typer.Option("auto", "--source", help="auto, perseus, or first1k."),
    edition: str | None = typer.Option(None, "--edition", help="Pick a specific edition file."),
    limit: int = typer.Option(
        0, "--limit", "--top", help="With 'all': cap NEW downloads (0 = all)."
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="With 'all': show what would be fetched; fetch nothing."
    ),
    yes: bool = typer.Option(
        False, "--yes", "-y", help="With 'all': skip the confirmation prompt for large sets."
    ),
    output: Path | None = typer.Option(
        None, "--output", "-o",
        help="Save the corpus to a .json or .db/.sqlite file (by extension).",
    ),
    json_out: bool = JSON_OPT,
) -> None:
    """Fetch a real Greek work (Perseus canonical-greekLit / First1KGreek, CC BY-SA).

    The TEI file is fetched once to the cache (pinned commit = reproducible),
    parsed into one document per book/chapter — or, with --ref, just the
    addressed textpart or verse line-range.

    `aegean greek work all AUTHOR` bulk-fetches every work by an author (case-
    insensitive), e.g. `aegean greek work all homer`; `aegean greek works
    --downloaded` lists what is already on disk.

    Don't know the id? `aegean greek works` lists well-known ones; any Perseus
    canonical-greekLit / First1KGreek id works (browse them at scaife.perseus.org)."""
    from aegean.data import DataNotAvailableError
    from aegean.greek import list_fetched_works, load_work

    if work_id is not None and work_id.lower() == "all":
        if output is not None:
            raise fail("-o is not used with 'all' (works land in the cache; "
                       "save one with `aegean greek work <id> -o file.json`)")
        _work_all(author, source=source, limit=limit, dry_run=dry_run,
                  assume_yes=yes, json_out=json_out)
        return
    if author is not None:
        raise fail("the second argument is only used with 'all' "
                   "(single-work section selection uses --ref)")
    if work_id is None:
        raise fail(
            "give a work id (e.g. tlg0012.tlg001) — `aegean greek works` lists "
            "well-known ids; `aegean greek catalog NAME` searches ~1,800; "
            "`aegean greek work all AUTHOR` fetches a whole author"
        )
    if source not in ("auto", "perseus", "first1k"):
        raise fail("--source must be auto, perseus, or first1k")
    was_cached = any(w["id"] == work_id for w in list_fetched_works())
    try:
        c = load_work(work_id, ref=ref, source=source, edition=edition)
    except (DataNotAvailableError, ValueError) as exc:
        exit1 = fail(str(exc))
        if "." not in work_id or "tlg" not in work_id.lower():
            # the id isn't even work-shaped: the catalog searches by name
            print(f"search it by name:  aegean greek catalog {work_id}", file=sys.stderr)
        raise exit1 from None
    if output is not None:
        write_corpus(c, output)
        print(f"wrote {len(c)} documents to {output}", file=sys.stderr)
        return
    path = next((w["path"] for w in list_fetched_works() if w["id"] == work_id), None)
    summary = {
        "work": work_id,
        "documents": len(c),
        "tokens": sum(len(d.tokens) for d in c),
        "first": c.documents[0].id if len(c) else "",
        "name": c.documents[0].meta.name if len(c) else "",
        "source": c.provenance.source if c.provenance else "",
        "data_version": c.provenance.data_version if c.provenance else "",
        "cached": was_cached,
        "path": path,
    }
    if json_out:
        emit_json(summary)
        return
    table(f"{work_id}", ["field", "value"],
          [[k, str(v)] for k, v in summary.items() if k not in ("work", "cached", "path")])
    if path is not None:
        status = "already cached at" if was_cached else "downloaded to"
        print(f"{status}  {path}", file=sys.stderr)
    if len(c):
        section = str(summary["first"]).split(":", 1)[-1]
        print(f"read it:  aegean show {work_id} {section}")
    if c.provenance is not None and c.provenance.citation:
        print(f"cite it:  {c.provenance.citation}")


@greek_app.command()
def nt(
    book: str | None = typer.Argument(
        None, help="NT book name, e.g. John (omit to load all 27 books)."
    ),
    passage: str | None = typer.Argument(
        None, help="Chapter or range to read: '1', '1-3', or '1.1-1.18' (verses)."
    ),
    ref: str | None = typer.Option(
        None, "--ref", help="Alias for the passage argument ('1', '1-3', '1.1-1.18')."
    ),
    output: Path | None = typer.Option(
        None, "--output", "-o",
        help="Save the corpus to a .json or .db/.sqlite file (by extension).",
    ),
    json_out: bool = JSON_OPT,
) -> None:
    """Read the Greek New Testament (Nestle 1904): gold lemma / morph / Strong's + Koine gloss.

    Name a BOOK, and optionally a chapter or range, to read it:
    `aegean greek nt John 1`, `aegean greek nt Matt 1-3`. With no BOOK, loads all 27 books
    (a summary). Tokens carry per-word annotations — `aegean export <file> -f csv --level token`
    spreads them into columns. `aegean greek nt-books` lists the book names."""
    from aegean.data import DataNotAvailableError
    from aegean.greek import load_nt

    if passage is not None and ref is not None:
        raise fail("give the passage as a positional OR --ref, not both")
    selection = passage or ref
    try:
        c = load_nt(book, ref=selection)
    except (DataNotAvailableError, ValueError, KeyError, LookupError) as exc:
        # the library speaks Python (greek.nt_books()); the CLI speaks CLI
        msg = str(exc).replace(
            "greek.nt_books() lists all 27", "`aegean greek nt-books` lists all 27"
        )
        raise fail(msg) from None
    if output is not None:
        write_corpus(c, output)
        print(f"wrote {len(c)} documents to {output}", file=sys.stderr)
        return
    summary = {
        "scope": book or "whole NT",
        "ref": selection or "",
        "documents": len(c),
        "tokens": sum(len(d.tokens) for d in c),
        "first": c.documents[0].id if len(c) else "",
        "source": c.provenance.source if c.provenance else "",
        "data_version": c.provenance.data_version if c.provenance else "",
    }
    if json_out:
        emit_json(summary)
        return
    # No book -> a summary (rendering all 27 books is not useful). A named book -> read the text.
    if book is None:
        table("Greek NT", ["field", "value"], [[k, str(v)] for k, v in summary.items()])
        if len(c):
            print("read a book:  aegean greek nt John 1   (a chapter or range, e.g. Matt 1-3)")
        return
    if not len(c):
        raise fail("that selection has no text")
    header = f"{summary['scope']} {selection or ''}".strip()
    console().print(
        f"{header}  ({summary['documents']} chapter"
        f"{'' if summary['documents'] == 1 else 's'}, {summary['tokens']} tokens)",
        style="bold", markup=False,
    )
    for doc in c:
        console().print(doc.meta.name or doc.id, style="bold cyan", markup=False)
        for line in doc.lines:
            if not line:
                continue
            verse = doc.tokens[line[0]].line_no
            label = str(verse) if verse is not None else "-"
            text = " ".join(doc.tokens[i].text for i in line)
            console().print(f"  {label}: {text}", markup=False)


@greek_app.command()
def works(
    downloaded: bool = typer.Option(
        False, "--downloaded", "--local",
        help="List Greek works already downloaded to the cache, instead of the curated set.",
    ),
    remove: str | None = typer.Option(
        None, "--remove", help="Delete one downloaded work by id (e.g. tlg0012.tlg001)."
    ),
    remove_author: str | None = typer.Option(
        None, "--remove-author",
        help="Delete every downloaded work by an author (case-insensitive substring).",
    ),
    remove_all: bool = typer.Option(
        False, "--remove-all", help="Delete ALL downloaded Greek works from the cache."
    ),
    json_out: bool = JSON_OPT,
) -> None:
    """List a curated catalog of well-known Greek works loadable with `aegean greek work`.

    Every id here is verified. It is a starting point, not the whole canon — `work` takes
    any Perseus canonical-greekLit / First1KGreek id; browse them at scaife.perseus.org.

    `--downloaded` lists instead the works already fetched to your local cache. Delete
    downloaded works with `--remove <id>`, `--remove-author <name>`, or `--remove-all`
    (the only way a fetched work leaves disk; re-fetch with `aegean greek work <id>`)."""
    if remove is not None or remove_author is not None or remove_all:
        from aegean.greek import list_fetched_works, remove_fetched_works

        before = {w["id"]: w for w in list_fetched_works()}
        removed = remove_fetched_works(
            [remove] if remove else None, author=remove_author, remove_all=remove_all
        )
        if json_out:
            emit_json({"removed": removed})
            return
        if not removed:
            if remove:
                print(f"{remove!r} is not a downloaded work "
                      "(`aegean greek works --downloaded` lists what is).")
            elif remove_author:
                print(f"no downloaded works by an author matching {remove_author!r} "
                      "(`aegean greek works --downloaded` lists what is).")
            else:
                print("no Greek works are downloaded.")
            return
        for rid in removed:
            meta = before.get(rid, {})
            label = f"{meta.get('author', '')} — {meta.get('title', '')}".strip(" —") or rid
            print(f"removed {rid}  ({label})")
        print(f"\nremoved {len(removed)} work{'' if len(removed) == 1 else 's'} from the cache.")
        return

    if downloaded:
        from aegean.greek import list_fetched_works

        fw = list_fetched_works()
        if json_out:
            emit_json({"downloaded": fw})
            return
        if not fw:
            print("No Greek works downloaded yet. Fetch one with `aegean greek work <id>`, "
                  "or a whole author with `aegean greek work all <author>`.")
            return

        def _sz(n: int) -> str:
            return f"{n / 1_048_576:.1f} MB" if n >= 1_048_576 else f"{n / 1024:.0f} KB"

        table("Downloaded Greek works", ["id", "author", "title", "source", "size"],
              [[w["id"], w["author"], w["title"], w["source"], _sz(w["bytes"])] for w in fw])
        print(f"\n{len(fw)} work{'' if len(fw) == 1 else 's'} in the cache. "
              "Read one with `aegean show <id> <section>`.")
        return

    from aegean.greek import popular_works

    ws = popular_works()
    if json_out:
        emit_json(ws)
        return
    table("Popular Greek works", ["id", "author", "title"],
          [[w["id"], w["author"], w["title"]] for w in ws])
    print("\nLoad one with, e.g.:  aegean greek work tlg0012.tlg001 --ref 1.1-1.10")
    print("This is a curated subset — search the full ~1,800-work canon with `aegean greek catalog`")


@greek_app.command()
def catalog(
    query: str | None = typer.Argument(
        None, help="Free-text filter across id, author, and title (English or Greek)."
    ),
    author: str | None = typer.Option(None, "--author", "-a", help="Filter by author (substring)."),
    title: str | None = typer.Option(None, "--title", "-t", help="Filter by title (English or Greek)."),
    source: str | None = typer.Option(None, "--source", help="Limit to 'perseus' or 'first1k'."),
    limit: int = typer.Option(
        40, "--limit", "--top", "-n",
        help="Max rows (0 = all); --json and -o keep the untruncated count in 'matched'.",
    ),
    output: Path | None = RESULT_OPT,
    json_out: bool = JSON_OPT,
) -> None:
    """Search the full discovery catalogue (~1,800 works) of loadable Greek texts.

    Every work with a Greek edition in Perseus canonical-greekLit + First1KGreek — far more
    than the 25 in `aegean greek works`. Bundled metadata, no network. Pass any id to
    `aegean greek work`.

    Examples:  aegean greek catalog sappho   |   aegean greek catalog --author plato"""
    from aegean.greek import catalog as greek_catalog

    if source is not None and source not in ("perseus", "first1k"):
        raise fail("--source must be perseus or first1k")
    rows = greek_catalog(query, author=author, title=title, source=source)
    total = len(rows)
    shown = rows if limit <= 0 else rows[:limit]
    if emit_result({"matched": total, "works": shown}, json_output=json_out, output=output):
        return
    if not total:
        print("No works match. Try a looser filter, or browse https://scaife.perseus.org")
        return
    table(
        f"Greek works ({total} match{'' if total == 1 else 'es'})",
        ["id", "author", "title", "greek", "src"],
        [[r["id"], r["author"], r["title"], r.get("greek_title", ""), r["source"]] for r in shown],
    )
    if limit > 0 and total > limit:
        print(f"\n… and {total - limit} more — narrow with --author/--title, or --limit 0 to list all (-o to save).")
    print("Load one with, e.g.:  aegean greek work tlg0012.tlg001 --ref 1.1-1.10")


@greek_app.command("nt-books")
def nt_books_cmd(json_out: bool = JSON_OPT) -> None:
    """List the 27 books of the Greek New Testament and the names `gloss-nt`/load_nt accept."""
    from aegean.greek import nt_books

    books = nt_books()
    if json_out:
        emit_json(books)
        return
    table("New Testament books (Nestle 1904)", ["book", "accepted names"],
          [[b["name"], ", ".join(b["aliases"])] for b in books])
    print("\nLoad one:  aegean greek nt John --ref 1.1-1.18")


@greek_app.command("eval")
def evaluate(
    target: str = typer.Argument(
        ...,
        help="ud, proiel, nt, papygreek, tagger, lemmatizer, or parser (heavy: fetches/trains).",
    ),
    fold: str = typer.Option(
        "perseus", "--fold", help="For ud: which UD Ancient Greek fold, perseus or proiel."
    ),
    fold_alias: str | None = typer.Option(
        None, "--treebank", hidden=True, help="Deprecated alias for --fold."
    ),
    split: str = typer.Option("test", "--split", help="For ud: dev or test."),
    bootstrap: bool = typer.Option(
        False, "--bootstrap", help="For ud: percentile CIs over the fold's sentences (slower)."
    ),
    drift: bool = typer.Option(
        False, "--drift",
        help="For ud/proiel/nt: an error analysis (POS confusion matrix, per-POS accuracy, "
             "lemma confusions) instead of the aggregate score. For papygreek: the "
             "UPOS/XPOS convention decomposition (coordinator / common-gender / '_'-encoding "
             "vs real error).",
    ),
    by_genre: bool = typer.Option(
        False, "--by-genre",
        help="For ud: score the fold sliced by literary genre (epic/tragedy/prose, from the "
             "sent_id author). Note: the leakage-clean Perseus test fold is prose-only.",
    ),
    batch_size: int | None = typer.Option(
        None, "--batch-size",
        help="For ud/nt/papygreek with the neural pipeline: run the encoder over N sentences "
             "at a time (faster on long folds; the published numbers use the sequential "
             "default).",
    ),
    neural: bool = NEURAL_OPT,
    tagger: bool = TAGGER_OPT,
    lemmatizer: bool = LEMMATIZER_OPT,
    neural_lemmatizer: bool = NEURAL_LEMM_OPT,
    output: Path | None = RESULT_OPT,
    json_out: bool = JSON_OPT,
) -> None:
    """Reproduce pyaegean's measured numbers (official evaluators, fetched gold data).

    `ud` scores the active pipeline on a UD Ancient Greek fold with the official
    CoNLL 2018 evaluator; `proiel` is the neutral out-of-AGDT check; the rest
    are the leakage-free held-out evaluations of the trainable backends."""
    from aegean import greek

    if fold_alias is not None:
        # On every other greek command --treebank is the boolean AGDT activation;
        # here it was the fold selector. Deprecated in 0.17, removal per policy.
        print("aegean: `greek eval --treebank` is deprecated; use --fold", file=sys.stderr)
        fold = fold_alias
    if fold not in ("perseus", "proiel"):
        raise fail("--fold must be perseus or proiel")
    if split not in ("dev", "test"):
        raise fail("--split must be dev or test")
    if batch_size is not None:
        if batch_size < 1:
            raise fail("--batch-size must be at least 1")
        # bootstrap_ud and the error analyses run their own inference loops without a
        # batching hook; --by-genre threads batch_size through pipeline_conllu like ud.
        if target not in ("ud", "nt", "papygreek") or drift or (bootstrap and not by_genre):
            raise fail("--batch-size applies to `eval ud`, `eval nt`, and `eval papygreek` "
                       "score runs (not --drift/--bootstrap)")
    _activate(
        tagger=tagger, lemmatizer=lemmatizer,
        neural_lemmatizer=neural_lemmatizer, neural=neural,
    )
    def emit_drift(report: object) -> None:  # ErrorAnalysis -> --json dict / text summary
        if emit_result(report.as_dict(), json_output=json_out, output=output):  # type: ignore[attr-defined]
            return
        print(report.summary())  # type: ignore[attr-defined]

    def live_progress(done: int, total: int) -> None:
        # A single repainted stderr line, TTY-only: piped/captured runs (CI, --json > f)
        # stay clean, but a scholar watching the ~1 h NT eval sees it moving.
        if not sys.stderr.isatty():
            return
        step = max(1, total // 200)
        if done % step and done != total:
            return
        end = "\n" if done == total else ""
        print(f"\r  scoring {done:,}/{total:,} sentences ({100 * done // total}%)",
              file=sys.stderr, end=end, flush=True)

    result: object
    if target == "ud":
        if drift:
            if fold == "proiel":
                # the PROIEL drift view includes the convention decomposition: the
                # measured split of the UFeats/LAS gaps into scheme-absent vs shared
                _activate(neural=True)
                emit_drift(greek.proiel_convention_report(split=split, progress=live_progress))
                return
            emit_drift(greek.ud_error_analysis(treebank=fold, split=split))
            return
        if by_genre:
            # batch_size is forwarded only when given, so the default invocation stays
            # identical to the recorded protocol's call (same pattern below).
            if batch_size is not None:
                by = greek.evaluate_by_genre(
                    fold, split, bootstrap=bootstrap, progress=live_progress,
                    batch_size=batch_size,
                )
            else:
                by = greek.evaluate_by_genre(fold, split, bootstrap=bootstrap, progress=live_progress)
            unmapped = by.pop("_unmapped", {}).get("authors", [])  # type: ignore[union-attr]
            if emit_result({**by, "_unmapped": unmapped}, json_output=json_out, output=output):
                return
            rows = []
            for genre, d in by.items():
                flag = " (thin)" if d.get("thin") else ""
                cells = [f"{k}={d[k]}" for k in ("upos", "lemma", "uas", "las") if k in d]
                rows.append([f"{genre}{flag}", str(d["n_sentences"]), str(d["n_words"]), ", ".join(cells)])
            table(f"eval ud {fold}/{split} by genre", ["genre", "sents", "words", "metrics"], rows)
            if unmapped:
                print(f"unmapped authors (counted as 'other'): {', '.join(unmapped)}", file=sys.stderr)
            return
        if bootstrap:
            cis = greek.bootstrap_ud(treebank=fold, split=split)
            result = {
                k: f"{ci.estimate:.4f} [{ci.low:.4f}, {ci.high:.4f}]" for k, ci in cis.items()
            }
        elif batch_size is not None:
            result = greek.evaluate_on_ud(
                treebank=fold, split=split, progress=live_progress, batch_size=batch_size
            )
        else:
            result = greek.evaluate_on_ud(treebank=fold, split=split, progress=live_progress)
    elif target == "proiel":
        if drift:
            emit_drift(greek.proiel_error_analysis())
            return
        result = greek.evaluate_on_proiel(progress=live_progress)
    elif target == "nt":
        _activate(neural=True)  # the NT fold reports the shipped neural model's number
        if drift:
            emit_drift(greek.nt_error_analysis())
            return
        if batch_size is not None:
            result = greek.evaluate_on_nt(progress=live_progress, batch_size=batch_size)
        else:
            result = greek.evaluate_on_nt(progress=live_progress)
    elif target == "papygreek":
        _activate(neural=True)  # the documentary-Koine fold reports the shipped neural model
        if drift:
            # the convention decomposition: the measured split of the UPOS/XPOS gaps into
            # coordinator / common-gender / '_'-encoding convention vs residual real error.
            # One canonical SEQUENTIAL run (batch-32 is not prediction-identical on this fold).
            emit_drift(greek.papygreek_convention_report(progress=live_progress))
            return
        if batch_size is not None:
            result = greek.evaluate_on_papygreek(progress=live_progress, batch_size=batch_size)
        else:
            result = greek.evaluate_on_papygreek(progress=live_progress)
    elif target == "tagger":
        result = greek.evaluate_tagger()
    elif target == "lemmatizer":
        result = greek.evaluate_lemmatizer()
    elif target == "parser":
        _activate(parser=True)
        result = greek.evaluate_parser()
    else:
        raise fail("target must be ud, proiel, nt, papygreek, tagger, lemmatizer, or parser")
    if emit_result(result, json_output=json_out, output=output):
        return
    if isinstance(result, dict):
        table(f"eval: {target}", ["metric", "value"], [[k, str(v)] for k, v in result.items()])
    else:
        print(result)
