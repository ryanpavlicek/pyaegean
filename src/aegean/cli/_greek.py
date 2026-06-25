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
    fail,
    read_text,
    table,
    write_result,
)

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

    want = {
        "case": case, "number": number, "gender": gender, "tense": tense,
        "voice": voice, "mood": mood, "person": person, "pos": pos,
    }
    forms = greek.inflect(lemma, **{k: v for k, v in want.items() if v})
    if json_out:
        emit_json(list(forms))
        return
    print(" ".join(forms) if forms else f"{lemma}: no attested form for those features")


@greek_app.command()
def rarity(
    text: str = TEXT_ARG,
    corpus: str = typer.Option(
        "nt", "--corpus", help="Reference corpus: 'nt' (the Greek NT) or a path to a corpus JSON."
    ),
    top: int = typer.Option(5, "--top", help="Show the N rarest words."),
    treebank: bool = TREEBANK_OPT,
    json_out: bool = JSON_OPT,
) -> None:
    """Terminology rarity of a text vs a reference corpus — a translation-difficulty signal.

    Rarity is relative to the chosen corpus's vocabulary; rare/technical terms score high."""
    from aegean import greek
    from aegean.core.corpus import Corpus

    _activate(treebank=treebank)
    if corpus == "nt":
        print("aegean: loading the Greek NT reference corpus (first use may download)…", file=sys.stderr)
        try:
            ref: object = greek.load_nt()
        except Exception as exc:
            raise fail(f"could not load the NT corpus: {exc}") from None
    else:
        ref = Corpus.from_json(corpus)
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
    """Dialect and register tags for a word, mined from its LSJ entry (--lsj fetch on first use)."""
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
        raise fail(str(exc)) from None
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
    except KeyError as exc:
        raise fail(str(exc)) from None
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
    addressed textpart or verse line-range.

    Don't know the id? `aegean greek works` lists well-known ones; any Perseus
    canonical-greekLit / First1KGreek id works (browse them at scaife.perseus.org)."""
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


@greek_app.command()
def nt(
    book: str | None = typer.Argument(
        None, help="NT book name, e.g. John (omit to load all 27 books)."
    ),
    ref: str | None = typer.Option(
        None, "--ref", help="Select a passage: '1' (chapter) or '1.1-1.18' (verses)."
    ),
    out_path: str | None = typer.Option(None, "--output", "-o", help="Write the corpus as JSON."),
    json_out: bool = JSON_OPT,
) -> None:
    """Load the Greek New Testament (Nestle 1904): gold lemma / morph / Strong's + Koine gloss.

    With no BOOK, loads all 27 books; name a book (and optionally --ref) for one passage. Tokens
    carry per-word annotations — `aegean export <file> -f csv --level token` spreads them into
    columns. `aegean greek nt-books` lists the book names; `aegean greek gloss-nt` glosses a word."""
    from aegean.data import DataNotAvailableError
    from aegean.greek import load_nt

    try:
        c = load_nt(book, ref=ref)
    except (DataNotAvailableError, ValueError, KeyError, LookupError) as exc:
        raise fail(str(exc)) from None
    if out_path:
        c.to_json(out_path)
        print(f"wrote {len(c)} documents to {out_path}")
        return
    summary = {
        "scope": book or "whole NT",
        "ref": ref or "",
        "documents": len(c),
        "tokens": sum(len(d.tokens) for d in c),
        "first": c.documents[0].id if len(c) else "",
        "source": c.provenance.source if c.provenance else "",
        "data_version": c.provenance.data_version if c.provenance else "",
    }
    if json_out:
        emit_json(summary)
        return
    table("Greek NT", ["field", "value"], [[k, str(v)] for k, v in summary.items()])


@greek_app.command()
def works(json_out: bool = JSON_OPT) -> None:
    """List a curated catalog of well-known Greek works loadable with `aegean greek work`.

    Every id here is verified. It is a starting point, not the whole canon — `work` takes
    any Perseus canonical-greekLit / First1KGreek id; browse them at scaife.perseus.org."""
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
    limit: int = typer.Option(40, "--limit", "-n", help="Max rows to show (0 = all)."),
    output: Path | None = RESULT_OPT,
    json_out: bool = JSON_OPT,
) -> None:
    """Search the full discovery catalogue (~1,800 works) of loadable Greek texts.

    Every work with a Greek edition in Perseus canonical-greekLit + First1KGreek — far more
    than the 25 in `aegean greek works`. Bundled metadata, no network. Pass any id to
    `aegean greek work`.

    Examples:  aegean greek catalog sappho   |   aegean greek catalog --author plato"""
    from aegean.greek import catalog as greek_catalog

    rows = greek_catalog(query, author=author, title=title, source=source)
    if output is not None:
        write_result(rows, output)
        print(f"wrote {len(rows)} works to {output}")
        return
    if json_out:
        emit_json(rows)
        return
    total = len(rows)
    if not total:
        print("No works match. Try a looser filter, or browse https://scaife.perseus.org")
        return
    shown = rows if limit <= 0 else rows[:limit]
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
    print("\nLoad one in Python:  greek.load_nt('John', ref='1.1-18')")


@greek_app.command("eval")
def evaluate(
    target: str = typer.Argument(
        ..., help="ud, proiel, nt, tagger, lemmatizer, or parser (heavy: fetches/trains)."
    ),
    treebank_fold: str = typer.Option("perseus", "--treebank", help="For ud: perseus or proiel."),
    split: str = typer.Option("test", "--split", help="For ud: dev or test."),
    bootstrap: bool = typer.Option(
        False, "--bootstrap", help="For ud: percentile CIs over the fold's sentences (slower)."
    ),
    drift: bool = typer.Option(
        False, "--drift", help="For proiel: a POS-confusion / lemma convention-drift breakdown."
    ),
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
        if bootstrap:
            cis = greek.bootstrap_ud(treebank=treebank_fold, split=split)
            result = {
                k: f"{ci.estimate:.4f} [{ci.low:.4f}, {ci.high:.4f}]" for k, ci in cis.items()
            }
        else:
            result = greek.evaluate_on_ud(treebank=treebank_fold, split=split)
    elif target == "proiel":
        if drift:
            report = greek.proiel_drift()
            if json_out:
                emit_json({
                    "pos_scored": report.pos_scored, "pos_errors": report.pos_errors,
                    "lemma_errors": report.lemma_errors, "top_share": round(report.top_share, 3),
                    "pos_confusions": [
                        {"gold": g, "predicted": p, "count": c} for g, p, c in report.pos_confusions
                    ],
                })
            else:
                print(report.summary())
            return
        result = greek.evaluate_on_proiel()
    elif target == "nt":
        greek.use_neural_pipeline()  # the NT fold reports the shipped neural model's number
        result = greek.evaluate_on_nt()
    elif target == "tagger":
        result = greek.evaluate_tagger()
    elif target == "lemmatizer":
        result = greek.evaluate_lemmatizer()
    elif target == "parser":
        greek.use_parser()
        result = greek.evaluate_parser()
    else:
        raise fail("target must be ud, proiel, nt, tagger, lemmatizer, or parser")
    if json_out:
        emit_json(result)
        return
    if isinstance(result, dict):
        table(f"eval: {target}", ["metric", "value"], [[k, str(v)] for k, v in result.items()])
    else:
        print(result)
