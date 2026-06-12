"""The `aegean greek` group: the full Greek NLP pipeline from the shell.

Backend flags mirror the `use_*` activation functions: ``--treebank``,
``--tagger``, ``--lemmatizer``, ``--neural-lemmatizer``, ``--neural`` (the joint
pipeline), ``--lsj``. Each activation may download its data/model to the cache on
first use (a note goes to stderr); afterwards everything is offline.
"""

from __future__ import annotations

import sys

import typer

from ._common import JSON_OPT, console, emit_json, fail, read_text, table

greek_app = typer.Typer(
    pretty_exceptions_show_locals=False,
    help="Greek NLP: normalize → tokenize → … → parse.",
    no_args_is_help=True,
)

TEXT_ARG = typer.Argument(..., help="Greek text ('-' reads stdin).")
WORD_ARG = typer.Argument(..., help="One Greek word.")

TREEBANK_OPT = typer.Option(False, "--treebank", help="Activate the Perseus AGDT lexicon (~75 MB fetch on first use).")
TAGGER_OPT = typer.Option(False, "--tagger", help="Activate the generalizing POS tagger (trains from the AGDT on first use).")
LEMMATIZER_OPT = typer.Option(False, "--lemmatizer", help="Activate the edit-tree lemmatizer (trains from the AGDT on first use).")
NEURAL_LEMM_OPT = typer.Option(False, "--neural-lemmatizer", help="Activate the seq2seq lemmatizer (~232 MB model, [neural] extra).")
NEURAL_OPT = typer.Option(False, "--neural", help="Activate the joint neural pipeline (~518 MB model, [neural] extra).")
LSJ_OPT = typer.Option(False, "--lsj", help="Activate LSJ glossing (~270 MB fetch on first use).")


def _activate(
    *,
    treebank: bool = False,
    tagger: bool = False,
    lemmatizer: bool = False,
    neural_lemmatizer: bool = False,
    neural: bool = False,
    lsj: bool = False,
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
        "hexameter", "--meter", help="hexameter, pentameter, or trimeter."
    ),
    json_out: bool = JSON_OPT,
) -> None:
    """Metrical scansion (dactylic hexameter / elegiac pentameter / iambic trimeter).

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
    period: str = typer.Option("attic", "--period", help="attic or koine."),
) -> None:
    """Reconstructed IPA pronunciation."""
    from aegean import greek

    if period not in ("attic", "koine"):
        raise fail("--period must be attic or koine")
    try:
        print(greek.to_ipa(read_text(text), period=period))  # type: ignore[arg-type]
    except ValueError as exc:
        raise fail(str(exc)) from None


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

    _activate(neural=neural)
    if parser:
        print("aegean: activating the dependency parser (first use trains from the AGDT)…", file=sys.stderr)
        greek.use_parser()
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
    json_out: bool = JSON_OPT,
) -> None:
    """Short LSJ gloss (activates the LSJ index; ~270 MB fetch on first use)."""
    from aegean import greek

    _activate(lsj=True)
    g = greek.gloss(lemma)
    if g is None:
        lem, known = greek.lemmatize_verbose(lemma)
        if known:
            g = greek.gloss(lem)
    if g is None:
        raise fail(f"no LSJ entry found for {lemma!r}")
    if json_out:
        emit_json({"query": lemma, "gloss": g})
    else:
        print(g)


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
    json_out: bool = JSON_OPT,
) -> None:
    """The one-call pipeline: per-token records for a whole text."""
    from aegean import greek

    _activate(
        treebank=treebank, tagger=tagger, lemmatizer=lemmatizer,
        neural_lemmatizer=neural_lemmatizer, neural=neural,
    )
    if parser:
        print("aegean: activating the dependency parser (first use trains from the AGDT)…", file=sys.stderr)
        greek.use_parser()
    try:
        records = greek.pipeline(read_text(text), parse=parse)
    except greek.ParserNotLoadedError:
        raise fail("--parse needs a parser — pass --neural (best) or --parser") from None
    if json_out:
        emit_json(records)
        return
    table(
        f"{len(records)} token(s)",
        ["s", "i", "token", "upos", "lemma", "head", "rel", "feats"],
        [
            [str(r.sentence), str(r.index), r.text, r.upos, r.lemma,
             "" if r.head is None else str(r.head), r.relation or "", r.feats or ""]
            for r in records
        ],
    )


@greek_app.command()
def work(
    work_id: str = typer.Argument(..., help="CTS-style work id, e.g. tlg0012.tlg001 (Iliad)."),
    ref: str | None = typer.Option(
        None, "--ref", help="Select a section: '1' (book), '1.2' (chapter), '1.1-1.50' (lines)."
    ),
    source: str = typer.Option("auto", "--source", help="auto, perseus, or first1k."),
    edition: str | None = typer.Option(None, "--edition", help="Pick a specific edition file."),
    out_path: str | None = typer.Option(None, "--output", "-o", help="Write the corpus as JSON."),
    json_out: bool = JSON_OPT,
) -> None:
    """Fetch a real Greek work (Perseus canonical-greekLit / First1KGreek, CC BY-SA).

    The TEI file is fetched once to the cache (pinned commit = reproducible),
    parsed into one document per book/chapter — or, with --ref, just the
    addressed textpart or verse line-range."""
    from aegean.data import DataNotAvailableError
    from aegean.greek import load_work

    try:
        c = load_work(work_id, ref=ref, source=source, edition=edition)
    except (DataNotAvailableError, ValueError) as exc:
        raise fail(str(exc)) from None
    if out_path:
        c.to_json(out_path)
        print(f"wrote {len(c)} documents to {out_path}")
        return
    summary = {
        "work": work_id,
        "documents": len(c),
        "tokens": sum(len(d.tokens) for d in c),
        "first": c.documents[0].id if len(c) else "",
        "name": c.documents[0].meta.name if len(c) else "",
        "source": c.provenance.source if c.provenance else "",
        "data_version": c.provenance.data_version if c.provenance else "",
    }
    if json_out:
        emit_json(summary)
        return
    table(f"{work_id}", ["field", "value"], [[k, str(v)] for k, v in summary.items() if k != "work"])


@greek_app.command("eval")
def evaluate(
    target: str = typer.Argument(
        ..., help="ud, proiel, tagger, lemmatizer, or parser (heavy: fetches/trains)."
    ),
    treebank_fold: str = typer.Option("perseus", "--treebank", help="For ud: perseus or proiel."),
    split: str = typer.Option("test", "--split", help="For ud: dev or test."),
    neural: bool = NEURAL_OPT,
    tagger: bool = TAGGER_OPT,
    lemmatizer: bool = LEMMATIZER_OPT,
    neural_lemmatizer: bool = NEURAL_LEMM_OPT,
    json_out: bool = JSON_OPT,
) -> None:
    """Reproduce pyaegean's measured numbers (official evaluators, fetched gold data).

    `ud` scores the active pipeline on a UD Ancient Greek fold with the official
    CoNLL 2018 evaluator; `proiel` is the neutral out-of-AGDT check; the rest
    are the leakage-free held-out evaluations of the trainable backends."""
    from aegean import greek

    _activate(
        tagger=tagger, lemmatizer=lemmatizer,
        neural_lemmatizer=neural_lemmatizer, neural=neural,
    )
    result: object
    if target == "ud":
        result = greek.evaluate_on_ud(treebank=treebank_fold, split=split)
    elif target == "proiel":
        result = greek.evaluate_on_proiel()
    elif target == "tagger":
        result = greek.evaluate_tagger()
    elif target == "lemmatizer":
        result = greek.evaluate_lemmatizer()
    elif target == "parser":
        greek.use_parser()
        result = greek.evaluate_parser()
    else:
        raise fail("target must be ud, proiel, tagger, lemmatizer, or parser")
    if json_out:
        emit_json(result)
        return
    if isinstance(result, dict):
        table(f"eval: {target}", ["metric", "value"], [[k, str(v)] for k, v in result.items()])
    else:
        print(result)
