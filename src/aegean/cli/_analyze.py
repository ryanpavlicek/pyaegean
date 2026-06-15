"""The `aegean analyze` group: the workbench analysis methods from the shell.

The Linear A material is undeciphered — these are **exploratory** surface
analyses (evidence to weigh, not conclusions), exactly as in the Python API.
"""

from __future__ import annotations

from pathlib import Path

import typer

from ._common import (
    CORPUS_ARG,
    JSON_OPT,
    RESULT_OPT,
    emit_json,
    fail,
    load_corpus,
    table,
    write_result,
)

analyze_app = typer.Typer(
    pretty_exceptions_show_locals=False,
    help="Analysis: distance, alignment, cross-script compare/nearest, association stats, clusters, structure.",
    no_args_is_help=True,
)


@analyze_app.command()
def distance(
    word1: str = typer.Argument(..., help="First word (transliterated, e.g. KU-RO)."),
    word2: str = typer.Argument(..., help="Second word."),
    json_out: bool = JSON_OPT,
) -> None:
    """Weighted phonetic distance in [0,1] (0 = identical)."""
    from aegean.analysis import phonetic_distance

    d = phonetic_distance(word1, word2)
    if json_out:
        emit_json({"word1": word1, "word2": word2, "distance": d})
    else:
        print(f"{word1} ↔ {word2}: {d:.3f}")


@analyze_app.command()
def align(
    word1: str = typer.Argument(..., help="First word."),
    word2: str = typer.Argument(..., help="Second word."),
    json_out: bool = JSON_OPT,
) -> None:
    """Per-position phonetic alignment (match / vowel / same-class / far / gap)."""
    from aegean.analysis import align_phonetic

    cells = align_phonetic(word1, word2)
    if json_out:
        emit_json(cells)
        return
    table(
        f"{word1} ↔ {word2}",
        ["a", "b", "op"],
        [[c.a or "·", c.b or "·", c.op] for c in cells],
    )


_SCRIPT_OPT = typer.Option(
    "linearb", "--script-a", help="Script of WORD1 (greek/lineara/linearb/cypriot)."
)
_SCRIPT_B_OPT = typer.Option("greek", "--script-b", help="Script of WORD2.")
_FOLD_OPT = typer.Option(
    False, "--fold-aspiration", help="Map θ/φ/χ → t/p/k (fairer vs syllabic spelling)."
)


@analyze_app.command()
def compare(
    word1: str = typer.Argument(..., help="First word (e.g. a Linear B transliteration po-me)."),
    word2: str = typer.Argument(..., help="Second word (e.g. Greek ποιμήν)."),
    script_a: str = _SCRIPT_OPT,
    script_b: str = _SCRIPT_B_OPT,
    fold_aspiration: bool = _FOLD_OPT,
    json_out: bool = JSON_OPT,
) -> None:
    """Compare two words ACROSS scripts by sound: romanize each, then align.

    e.g. `aegean analyze compare po-me ποιμήν` (Linear B vs Greek 'shepherd').
    Exploratory: syllabic spelling is defective, so read the alignment and the
    ranking, not the absolute number."""
    from aegean.analysis import phonetic_compare

    try:
        cmp = phonetic_compare(
            word1, script_a, word2, script_b, fold_aspiration=fold_aspiration
        )
    except ValueError as e:
        raise fail(str(e)) from None
    if json_out:
        emit_json(
            {
                "word1": word1, "script_a": script_a, "phonemes_a": cmp.phonemes_a,
                "word2": word2, "script_b": script_b, "phonemes_b": cmp.phonemes_b,
                "distance": cmp.distance, "similarity": cmp.similarity,
                "alignment": list(cmp.alignment),
            }
        )
        return
    print(f"{word1} [{script_a}] → {cmp.phonemes_a}    {word2} [{script_b}] → {cmp.phonemes_b}")
    print(f"similarity {cmp.similarity:.2f}  (distance {cmp.distance:.3f})")
    table(
        "alignment",
        ["a", "b", "op"],
        [[c.a or "·", c.b or "·", c.op] for c in cmp.alignment],
    )


@analyze_app.command()
def nearest(
    word: str = typer.Argument(..., help="The query word (e.g. Linear B qa-si-re-u)."),
    corpus: str = typer.Argument(..., help="Corpus whose words are the candidates (e.g. greek)."),
    script_a: str = _SCRIPT_OPT,
    fold_aspiration: bool = _FOLD_OPT,
    top: int = typer.Option(10, "--top", help="How many nearest candidates."),
    json_out: bool = JSON_OPT,
) -> None:
    """Rank a corpus's words by phonetic closeness to WORD across scripts.

    e.g. `aegean analyze nearest qa-si-re-u greek` finds the Greek words that
    sound closest to Linear B qa-si-re-u (→ βασιλεύς). The candidate script is
    the corpus's own."""
    from aegean.analysis import nearest as _nearest

    c = load_corpus(corpus)
    cand_script = c.script_id or "greek"
    candidates = sorted({t.text for d in c for t in d.words})
    try:
        ranked = _nearest(
            word, script_a, candidates, cand_script, top=top, fold_aspiration=fold_aspiration
        )
    except ValueError as e:
        raise fail(str(e)) from None
    if json_out:
        emit_json([{"candidate": w, "distance": d} for w, d in ranked])
        return
    table(
        f"nearest in {corpus} [{cand_script}] to {word} [{script_a}]",
        ["candidate", "distance"],
        [[w, f"{d:.3f}"] for w, d in ranked],
    )


@analyze_app.command()
def assoc(
    corpus: str = CORPUS_ARG,
    word1: str = typer.Argument(..., help="First word."),
    word2: str = typer.Argument(..., help="Second word."),
    output: Path | None = RESULT_OPT,
    json_out: bool = JSON_OPT,
) -> None:
    """Document-level association between two words: χ², log-likelihood, Fisher, PMI.

    The 2×2 table counts documents containing both, each alone, and neither."""
    from aegean.analysis import (
        chi_squared_2x2,
        chi_squared_p_value,
        fishers_exact,
        log_likelihood_ratio_2x2,
        pmi_interval,
    )

    c = load_corpus(corpus)
    docs = [{t.text for t in d.words} for d in c]
    total = len(docs)
    joint = sum(1 for s in docs if word1 in s and word2 in s)
    count1 = sum(1 for s in docs if word1 in s)
    count2 = sum(1 for s in docs if word2 in s)
    if count1 == 0 or count2 == 0:
        raise fail(f"{word1!r} or {word2!r} does not occur in {corpus!r}")
    chi2 = chi_squared_2x2(joint, count1, count2, total)
    data = {
        "word1": word1, "word2": word2,
        "counts": {"joint": joint, "word1": count1, "word2": count2, "documents": total},
        "chi_squared": chi2,
        "p_value": chi_squared_p_value(chi2),
        "log_likelihood": log_likelihood_ratio_2x2(joint, count1, count2, total),
        "fisher_p": fishers_exact(joint, count1, count2, total),
        "pmi_interval": list(pmi_interval(joint, count1, count2, total)),
    }
    if output is not None:
        write_result(data, output)
        return
    if json_out:
        emit_json(data)
        return
    table(
        f"{word1} ~ {word2} over {total} documents",
        ["measure", "value"],
        [["joint / w1 / w2 / docs", f"{joint} / {count1} / {count2} / {total}"]]
        + [[k, f"{v:.4g}" if isinstance(v, float) else str(v)]
           for k, v in data.items() if k not in ("word1", "word2", "counts")],
    )


@analyze_app.command()
def cooccur(
    corpus: str = CORPUS_ARG,
    word: str = typer.Argument(..., help="A multi-sign word, e.g. KU-RO."),
    top: int = typer.Option(20, "--top", help="How many co-occurring words."),
    output: Path | None = RESULT_OPT,
    json_out: bool = JSON_OPT,
) -> None:
    """Words sharing a document with WORD, ranked by shared-document count."""
    from collections import Counter

    c = load_corpus(corpus)
    counter: Counter[str] = Counter()
    for d in c:
        words = {t.text for t in d.words if "-" in t.text}
        if word in words:
            counter.update(w for w in words if w != word)
    if not counter:
        raise fail(f"{word!r} does not co-occur with anything in {corpus!r}")
    # Deterministic order: by shared-document count, then alphabetically by word to break
    # ties, so the output is reproducible (the per-document word sets iterate in hash order,
    # which would otherwise make tied rows shuffle between runs).
    ranked = sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))
    pairs = ranked if top <= 0 else ranked[:top]
    payload = [{"word": w, "shared_documents": n} for w, n in pairs]
    if output is not None:
        write_result(payload, output)
        return
    if json_out:
        emit_json(payload)
        return
    table(f"co-occurs with {word}", ["word", "shared docs"], [[w, str(n)] for w, n in pairs])


@analyze_app.command()
def clusters(
    corpus: str = CORPUS_ARG,
    min_size: int = typer.Option(2, "--min-size", help="Minimum cluster size."),
    top: int = typer.Option(15, "--top", help="How many clusters."),
    output: Path | None = RESULT_OPT,
    json_out: bool = JSON_OPT,
) -> None:
    """Morphological clusters: stems with productive-suffix derivations (exploratory)."""
    from aegean.analysis import find_morphological_clusters

    c = load_corpus(corpus)
    found = find_morphological_clusters(c.word_frequencies(), min_cluster_size=min_size)
    shown = found[: top if top > 0 else None]
    if output is not None:
        write_result(shown, output)
        return
    if json_out:
        emit_json(shown)
        return
    table(
        f"{corpus}: {len(found)} cluster(s) (exploratory; showing {len(shown)})",
        ["stem", "members", "suffixes"],
        [
            [cl.stem, ", ".join(m.word for m in cl.members[:6]), ", ".join(cl.suffixes)]
            for cl in shown
        ],
    )


@analyze_app.command()
def structure(
    corpus: str = CORPUS_ARG,
    doc_id: str | None = typer.Argument(None, help="One document; omit for the corpus census."),
    json_out: bool = JSON_OPT,
) -> None:
    """Heuristic document categories: accounting / libation / list / text / other."""
    from aegean.analysis import classify_corpus, classify_structure

    c = load_corpus(corpus)
    if doc_id is not None:
        doc = c.get(doc_id)
        if doc is None:
            raise fail(f"no document {doc_id!r} in {corpus!r}")
        category = classify_structure(doc)
        if json_out:
            emit_json({"doc": doc_id, "category": category})
        else:
            print(f"{doc_id}: {category}")
        return
    buckets = classify_corpus(c)
    if json_out:
        emit_json({k: len(v) for k, v in buckets.items()})
        return
    table(
        f"{corpus}: structure census (heuristic)",
        ["category", "documents"],
        [[k, str(len(v))] for k, v in buckets.items()],
    )


@analyze_app.command()
def hands(
    corpus: str = CORPUS_ARG,
    hand: str | None = typer.Option(
        None, "--hand", help="Keyness for one hand vs the rest; omit to profile every hand."
    ),
    top: int = typer.Option(20, "--top", help="Rows to show."),
    min_docs: int = typer.Option(1, "--min-docs", help="Minimum tablets for a hand to be listed."),
    signs: bool = typer.Option(False, "--signs", help="For --hand: key signs instead of words."),
    output: Path | None = RESULT_OPT,
    json_out: bool = JSON_OPT,
) -> None:
    """Scribal-hand analysis over a corpus that records a hand per document (e.g. DAMOS).

    Without --hand: profile every scribal hand (tablets, tokens, top words). With --hand:
    what is characteristic of that hand versus all the others (log-likelihood keyness)."""
    from aegean.analysis import hand_keyness, scribal_hands

    c = load_corpus(corpus)
    if hand is not None:
        try:
            rows = hand_keyness(c, hand, kind="signs" if signs else "words")[:top]
        except ValueError as exc:
            raise fail(str(exc)) from None
        payload = [
            {"item": r.item, "in_hand": r.target_count, "elsewhere": r.reference_count,
             "log_likelihood": r.log_likelihood, "log_ratio": r.log_ratio}
            for r in rows
        ]
        if output is not None:
            write_result(payload, output)
            return
        if json_out:
            emit_json(payload)
            return
        table(
            f"hand {hand}: characteristic {'signs' if signs else 'words'} vs the rest",
            ["item", "in-hand", "elsewhere", "G²", "log-ratio"],
            [[r.item, str(r.target_count), str(r.reference_count),
              f"{r.log_likelihood:.4g}", f"{r.log_ratio:+.2f}"] for r in rows],
        )
        return
    profiles = scribal_hands(c, min_docs=min_docs)[:top]
    if not profiles:
        raise fail(f"no scribal hands recorded in {corpus!r} (needs meta.scribe)")
    payload = [
        {"hand": p.hand, "doc_count": p.doc_count, "token_count": p.token_count,
         "word_count": p.word_count, "sites": p.sites, "top_words": p.top_words}
        for p in profiles
    ]
    if output is not None:
        write_result(payload, output)
        return
    if json_out:
        emit_json(payload)
        return
    table(
        f"scribal hands in {corpus}",
        ["hand", "tablets", "tokens", "top words"],
        [[p.hand, str(p.doc_count), str(p.token_count),
          ", ".join(w for w, _ in p.top_words[:5])] for p in profiles],
    )
