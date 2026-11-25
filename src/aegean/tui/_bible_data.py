"""Biblical & Koine Greek TUI study-screen adapters (never raise).

Re-exported from :mod:`aegean.tui.data` so screens and tests keep a single
adapter import boundary.
"""

from __future__ import annotations

from typing import Any


def _parse_passage_spec(spec: str) -> tuple[str, str | None]:
    """Parse ``'John 1.1-5'`` or ``'1Cor 13.1-3'`` or ``'John 1:18'`` -> ``(book, ref)``."""
    parts = spec.strip().split()
    if not parts:
        return "John", "1.1-5"
    if len(parts) == 1:
        return parts[0], None
    # Handle "1 Cor 13.1" as well as "1Cor 13.1"
    if parts[0].isdigit() and len(parts) >= 2:
        book = parts[0] + parts[1]
        ref = " ".join(parts[2:]) if len(parts) > 2 else None
    else:
        book = parts[0]
        ref = " ".join(parts[1:])
    if ref:
        ref = ref.replace(":", ".")
    return book, ref


def bible_read_text(passage: str, *, edition: str = "nestle1904", offline: bool = True) -> str:
    """Render an interlinear + verse view of a Greek NT or Septuagint (LXX) passage. Never raises."""
    import aegean.biblical as bib

    book, ref = _parse_passage_spec(passage)
    try:
        corp = bib.load_nt(book, ref=ref, edition=edition, offline=offline)
    except Exception as nt_exc:
        try:
            bib.resolve_lxx_book(book)
            corp = bib.load_lxx(book, ref=ref, offline=offline)
        except Exception:
            return (
                f"Could not load {passage!r} ({edition}): {nt_exc}\n"
                "Tip: run `aegean data fetch nt-corpus`, `nt-editions`, or `lxx-corpus` in Data Store (d)."
            )

    lines: list[str] = []
    cit = getattr(getattr(corp, "provenance", None), "citation", "")
    if cit:
        lines.append(cit)
        lines.append("")
    for doc in corp:
        by_v: dict[str, list[Any]] = {}
        for tok in doc.tokens:
            vkey = str(tok.annotations.get("ref") or f"{doc.id}.{tok.line_no or 0}")
            by_v.setdefault(vkey, []).append(tok)
        for vkey, toks in by_v.items():
            vlabel = vkey.rpartition(".")[2] if "." in vkey else vkey
            lines.append(f"[{doc.id}:{vlabel}]  {' '.join(t.text for t in toks)}")
            for t in toks:
                ann = t.annotations
                lem = ann.get("lemma", "")
                morph = ann.get("morph", "")
                strongs = ann.get("strongs", "")
                gloss = ann.get("gloss", "")
                if lem or morph or gloss:
                    s_part = f"G{strongs}" if strongs and not str(strongs).startswith("G") else str(strongs)
                    lines.append(f"    {t.text:<16} {lem:<16} {morph:<12} {s_part:<7} {gloss}")
            lines.append("")
    return "\n".join(lines).rstrip() or "No verses matched."


def bible_compare_text(passage: str, *, offline: bool = True) -> str:
    """Render side-by-side Greek NT edition comparison with word-level diffs. Never raises."""
    import aegean.biblical as bib

    book, ref = _parse_passage_spec(passage)
    if not ref:
        ref = "1.1-5"
    try:
        cmp = bib.compare_editions(book, ref, offline=offline)
    except Exception as exc:
        return (
            f"Multi-edition comparison unavailable for {book} {ref}: {exc}\n"
            "Tip: fetch `nt-editions` (~1.7 MB) from Data Store (d) to compare SBLGNT, SRGNT, Byzantine, and TR."
        )
    out = [f"{cmp.book} {cmp.ref} — {len(cmp.verses)} verse(s), {cmp.variant_verse_count} with variants", ""]
    for v in cmp.verses:
        tag = "identical" if v.identical else f"{len(v.variants)} variant(s)"
        out.append(f"── {v.ref} ({tag}) ──")
        for ed, txt in v.texts.items():
            out.append(f"  {ed:<10}  {txt}")
        for diff in v.variants:
            lhs = " ".join(diff.base_words) or "∅"
            rhs = " ".join(diff.edition_words) or "∅"
            out.append(f"    Δ {diff.edition} ({diff.kind}): {lhs} → {rhs}")
        out.append("")
    return "\n".join(out).rstrip()


def bible_witnesses_text(passage: str, *, hand: str = "original", offline: bool = True) -> str:
    """Render extant 2nd–5th c. CE manuscript witness comparison. Never raises."""
    import aegean.biblical as bib

    book, ref = _parse_passage_spec(passage)
    if not ref:
        ref = "1.18"
    try:
        rows = bib.compare_witnesses(book, ref, hand=hand, offline=offline)
    except Exception as exc:
        return (
            f"Early manuscript witnesses unavailable for {book} {ref}: {exc}\n"
            "Tip: fetch `nt-witnesses` (~2.0 MB) from Data Store (d) for Sinaiticus, Vaticanus, Alexandrinus, Bezae, and P45–P75."
        )
    out: list[str] = []
    for vc in rows:
        out.append(f"── {vc.ref} ({len(vc.witnesses)} early witnesses, hand={hand}) ──")
        for w in vc.witnesses:
            out.append(f"  {w.siglum:<4} ({w.alias}, {w.century})  {w.reading.readable}")
            if w.reading.nomina_sacra:
                ns = ", ".join(f"{a}→{e}" for a, e in w.reading.nomina_sacra)
                out.append(f"       nomina sacra: {ns}")
            if w.reading.corrections:
                corrs = ", ".join(f"{o or '∅'}→{n or '∅'}" for o, n in w.reading.corrections)
                out.append(f"       corrections: {corrs}")
        out.append("")
    return "\n".join(out).rstrip()


def bible_word_study_text(query: str, *, offline: bool = True) -> str:
    """Render a Strong's + NT word study report. Never raises."""
    import aegean.biblical as bib

    q = query.strip()
    if not q:
        return "Type a Strong's number (e.g. G3056, G26) or Greek lemma (e.g. λόγος, ἀγάπη)."
    try:
        ws = bib.word_study(q, limit=12, offline=offline)
    except Exception as exc:
        return f"Word study failed for {q!r}: {exc}"

    out = [f"Word Study: {ws.lemma}  ({ws.strongs or 'no Strongs'} · {ws.scope})"]
    if ws.entry is not None:
        out.append(f"  Gloss:      {ws.entry.gloss}")
        if ws.entry.translit or ws.entry.morph:
            out.append(f"  Translit:   {ws.entry.translit}   {ws.entry.morph}")
        if ws.entry.definition and ws.entry.definition != ws.entry.gloss:
            out.append(f"  Definition: {ws.entry.definition[:450]}")
        if ws.entry.derivation:
            out.append(f"  Derivation: {ws.entry.derivation}")
        if ws.entry.hebrew:
            out.append(f"  Hebrew eq.: {', '.join(ws.entry.hebrew)}")
        out.append(f"  Source:     {ws.entry.source}")
    else:
        out.append("  No Strong's entry found (fetch `strongs-greek` for all 11,142 Extended Strong's entries).")

    if ws.roots and ws.roots.get("roots"):
        out.append("")
        out.append("Root family:")
        for child in ws.roots["roots"]:
            out.append(f"  └─ {child.get('strongs', '')} {child.get('lemma', '')} — {child.get('gloss', '')}")

    out.append("")
    out.append(f"Occurrences in scope: {ws.total_occurrences}")
    if ws.by_book:
        out.append("  By book:    " + ", ".join(f"{k} ({v})" for k, v in list(ws.by_book.items())[:10]))
    if ws.by_morph:
        out.append("  Morphology: " + ", ".join(f"{k} ({v})" for k, v in list(ws.by_morph.items())[:8]))
    if ws.occurrences:
        out.append("")
        out.append("Sample concordance:")
        for hit in ws.occurrences[:10]:
            out.append(f"  {hit.ref:<12} [{hit.morph}]  {hit.verse_text[:110]}")
    return "\n".join(out)


def bible_lxx_and_catenae_text(filter_text: str = "") -> str:
    """Render searchable LXX + Patristic Catenae catalogue, LXX passage/search, and Psalm hint. Never raises."""
    import aegean.biblical as bib

    q = filter_text.strip()
    out: list[str] = []
    # 1. If the user typed a Psalm number like "23" or "ps 23", convert LXX <-> MT inline.
    digits = q.lower().removeprefix("psalm").removeprefix("ps").strip()
    if digits.isdigit():
        num = int(digits)
        if 1 <= num <= 150:
            lxx_n = ", ".join(str(x) for x in bib.psalm_mt_to_lxx(num))
            out.append(f"Psalm Numbering: MT/English Psalm {num} ↔ LXX Psalm {lxx_n}")
        if 1 <= num <= 151:
            mt_t = bib.psalm_lxx_to_mt(num)
            mt_n = ", ".join(str(x) for x in mt_t) if mt_t else "(LXX-only, not in MT)"
            out.append(f"Psalm Numbering: LXX Psalm {num} ↔ MT/English Psalm {mt_n}")
        if out:
            out.append("")

    # 2. If the user typed Greek characters (e.g. κύριος, φῶς), search the Septuagint inline.
    has_greek = any("\u0370" <= ch <= "\u03ff" or "\u1f00" <= ch <= "\u1fff" for ch in q)
    if has_greek:
        try:
            hits = bib.search_lxx(q, limit=12, offline=True)
            scope_note = "all 55 books" if bib.lxx_loaded() else "offline sample (Gen 1, Ps 22; fetch `lxx-corpus` for all 55 books)"
            out.append(f"── Septuagint (LXX) Concordance: {q!r} ({len(hits)} hit(s) in {scope_note}) ──")
            for h in hits:
                out.append(f"  {h.ref:<11} {h.verse_text}")
            if not hits:
                out.append("  No Septuagint matches in current scope.")
            out.append("")
        except Exception as exc:
            out.append(f"Septuagint search error: {exc}\n")

    # 3. If the user typed an LXX passage reference (e.g. "Gen 1.1-5" or "Ps 22.1-6"), read it inline.
    if not has_greek and " " in q:
        bk_cand, ref_cand = _parse_passage_spec(q)
        if ref_cand:
            try:
                corp = bib.load_lxx(bk_cand, ref=ref_cand, offline=True)
                out.append(f"── Septuagint Passage: {bk_cand} {ref_cand} (Swete LXX) ──")
                for doc in corp:
                    by_ref: dict[str, list[str]] = {}
                    for tok in doc.tokens:
                        rkey = str(tok.annotations.get("ref", f"{doc.id}.{tok.line_no or 0}"))
                        by_ref.setdefault(rkey, []).append(tok.text)
                    for rkey, words in by_ref.items():
                        rlabel = rkey.replace(".", " ", 1).replace(".", ":")
                        out.append(f"  {rlabel:<11} {' '.join(words)}")
                out.append("")
            except Exception:
                pass

    ql = q.lower()
    lxx = [
        b for b in bib.lxx_books()
        if not ql or has_greek or ql in b["name"].lower() or ql in b["title"].lower() or ql in b["section"].lower()
    ]
    comms = [
        c for c in bib.patristic_commentaries()
        if not ql or has_greek or ql in c["book"].lower() or ql in c["title"].lower() or ql in c["author"].lower()
    ]
    lxx_status = "cached" if bib.lxx_loaded() else "offline sample Gen 1 & Ps 22; fetch `lxx-corpus` (~1.7 MB) in Data Store (d) for all 55 books"
    out.append(f"── Septuagint (LXX) — {len(lxx)} matching book(s) ({lxx_status}) ──")
    for b in lxx[:28]:
        out.append(f"  {b['name']:<8} {b['title']:<36} [{b['section']}]  {b['work_id']}")
    if len(lxx) > 28:
        out.append(f"  … and {len(lxx) - 28} more (try typing `Gen 1.1-5`, `Ps 22.1-6`, or a Greek word like `φῶς`)")
    out.append("")
    out.append(f"── Greek Patristic Commentaries — {len(comms)} matching volume(s) (NT Catenae & Origen) ──")
    for c in comms[:24]:
        out.append(f"  {c['book']:<7} {c['work_id']:<15} {c['author']:<13} {c['title']}")
    if len(comms) > 24:
        out.append(f"  … and {len(comms) - 24} more")
    return "\n".join(out)

