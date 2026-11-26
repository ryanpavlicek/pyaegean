"""Unified predictive command, option, and domain-value completion for pyaegean.

Shared by three surfaces so they can never drift:

1. ``aegean`` / ``aegean repl`` (``prompt_toolkit`` live dropdown + dim inline ghost-text);
2. ``aegean tui`` command console (``:`` screen floating dropdown + inline ghost-text);
3. Native shell tab-completion (``aegean --install-completion`` via Typer/Click callbacks).

All value providers are strictly offline and read only bundled/static metadata (registered
corpus IDs, 47 remote dataset names, 27 NT books, 56 LXX books, 9 NT editions, 13
early manuscript witnesses, 10 Greek meters, 6 dictionaries, etc.) so keystroke prediction
stays instantaneous and never triggers a network fetch.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

import typer

# Shell-only directives shared by `aegean repl` and the TUI `:` console.
SHELL_DIRECTIVES: tuple[tuple[str, str], ...] = (
    ("use ", "set a session corpus (corpus-first commands default to it)"),
    (":examples", "copyable starter command lines"),
    (":help", "show the command map"),
    (":exit", "leave the shell"),
)

_CORPUS_FIRST_PATHS: frozenset[tuple[str, ...]] = frozenset(
    {
        ("info",),
        ("load",),
        ("show",),
        ("search",),
        ("query",),
        ("stats",),
        ("dispersion",),
        ("keyness",),
        ("balance",),
        ("cite",),
        ("export",),
        ("geo",),
        ("sign",),
        ("db", "build"),
        ("analyze", "assoc"),
        ("analyze", "cooccur"),
        ("analyze", "clusters"),
        ("analyze", "structure"),
        ("analyze", "hands"),
    }
)


@dataclass(frozen=True, slots=True)
class CompletionItem:
    """One predicted completion for the current token/line."""

    insert: str
    """Token or full-line text to insert for the current slot."""
    full_line: str
    """Complete input line after accepting this item (used by dropdown + inline ghost-text)."""
    description: str = ""
    """Short dim description shown alongside the completion."""
    replace_len: int = 0
    """How many characters before the cursor ``insert`` replaces."""


def is_group(cmd: object) -> bool:
    """Whether a Click/Typer command object has subcommands (typer-version-safe)."""
    return hasattr(cmd, "get_command") and hasattr(cmd, "list_commands")


def short_help(cmd: Any) -> str:
    """Collapse a Click/Typer command's one-line help text."""
    getter = getattr(cmd, "get_short_help_str", None)
    if callable(getter):
        try:
            text = getter(limit=64)
        except TypeError:
            text = getter()
        except Exception:
            text = ""
        if text:
            return " ".join(str(text).split())
    doc = (getattr(cmd, "help", "") or getattr(cmd, "short_help", "") or "").strip()
    first = doc.splitlines()[0] if doc else ""
    return " ".join(first.split())


def walk_command_paths(
    group: Any,
    *,
    include_directives: bool = True,
) -> list[tuple[str, str]]:
    """Recursively enumerate every command path in ``group`` to arbitrary nesting depth.

    Covers top-level commands, 2-level subcommands (``bible read``, ``greek scan``), and
    3-level subcommands (``greek interop export``, ``greek conllu inspect``,
    ``greek annotation-profiles list``), plus the shell directives when requested.
    """
    ctx = typer.Context(group, info_name="aegean")
    out: list[tuple[str, str]] = []

    def _walk(node: Any, prefix: str) -> None:
        names = (
            list(node.list_commands(ctx))
            if hasattr(node, "list_commands")
            else sorted(getattr(node, "commands", ()))
        )
        for name in sorted(names):
            sub = node.get_command(ctx, name) if hasattr(node, "get_command") else None
            if sub is None:
                continue
            path = f"{prefix} {name}" if prefix else name
            out.append((path, short_help(sub)))
            if is_group(sub):
                _walk(sub, path)

    _walk(group, "")
    if include_directives:
        out.extend(SHELL_DIRECTIVES)
    return out


# ── Offline domain value providers (cached once per process) ──────────────────


def _corpus_choices() -> list[tuple[str, str]]:
    import aegean  # noqa: F401
    from aegean.core.corpus import _LOADERS

    return [(name, "corpus") for name in sorted(_LOADERS)]


def _dataset_choices() -> list[tuple[str, str]]:
    from aegean.data import _REMOTE

    out: list[tuple[str, str]] = []
    for name in sorted(_REMOTE):
        spec = _REMOTE[name]
        desc = (spec.note or spec.license or "dataset").split(".")[0][:54]
        out.append((name, desc))
    return out


def _nt_book_choices() -> list[tuple[str, str]]:
    from aegean.scripts.greek.nt import nt_books

    return [(b["name"], ", ".join(b["aliases"][:2])) for b in nt_books()]


def _lxx_book_choices() -> list[tuple[str, str]]:
    from aegean.greek.bible._catalogs import lxx_books

    return [(b["name"], f"{b['title']} ({b['section']})") for b in lxx_books()]


def _nt_edition_choices() -> list[tuple[str, str]]:
    from aegean.greek.bible._editions import nt_editions

    return [(e["id"], e["name"]) for e in nt_editions()]


def _witness_choices() -> list[tuple[str, str]]:
    from aegean.greek.bible._witnesses import witnesses

    return [(w["siglum"], f"{w['alias']} · {w['name']} ({w['century']})") for w in witnesses()]


def _commentary_book_choices() -> list[tuple[str, str]]:
    from aegean.greek.bible._catalogs import patristic_commentaries

    seen: dict[str, int] = {}
    for row in patristic_commentaries():
        bk = row["book"]
        seen[bk] = seen.get(bk, 0) + 1
    return [(bk, f"{n} commentary volume(s)") for bk, n in seen.items()]


def _lxx_section_choices() -> list[tuple[str, str]]:
    from aegean.greek.bible._catalogs import lxx_books

    secs = sorted({b["section"] for b in lxx_books()})
    return [(s, "Septuagint section") for s in secs]


def _meter_choices() -> list[tuple[str, str]]:
    from aegean.greek.meter import AEOLIC_LINES

    base = [
        ("hexameter", "dactylic hexameter (Homer/Hesiod)"),
        ("pentameter", "elegiac pentameter"),
        ("trimeter", "iambic trimeter (tragedy)"),
    ]
    aeolic = [(name, "Aeolic lyric meter") for name in sorted(AEOLIC_LINES)]
    return base + aeolic


def _dictionary_choices() -> list[tuple[str, str]]:
    return [
        ("lsj", "Liddell-Scott-Jones (~15 MB)"),
        ("middle-liddell", "Middle Liddell (~2.3 MB)"),
        ("cunliffe", "Cunliffe Homeric (~1.3 MB)"),
        ("autenrieth", "Autenrieth Homeric (~0.6 MB)"),
        ("abbott-smith", "Abbott-Smith NT (~130 KB)"),
        ("dodson", "Dodson Koine NT (bundled offline)"),
    ]


def _option_value_choices(
    cmd_path: tuple[str, ...],
    opt: str,
    prior_tokens: Sequence[str],
) -> tuple[list[tuple[str, str]], bool]:
    """Return ``(choices, comma_separated)`` for a value-taking option ``opt``."""
    is_lxx = "--lxx" in prior_tokens

    # Biblical & Koine Greek options
    if cmd_path and cmd_path[0] == "bible":
        if opt == "--editions" or (opt == "-e" and cmd_path == ("bible", "compare")):
            return _nt_edition_choices(), True
        if opt in ("-e", "--edition"):
            return _nt_edition_choices(), False
        if opt in ("-s", "--sigla") and cmd_path == ("bible", "witnesses"):
            return _witness_choices(), True
        if opt == "--hand":
            return [
                ("original", "first-hand scribal reading"),
                ("corrected", "corrected manuscript reading"),
            ], False
        if opt == "--by":
            return [
                ("lemma", "match dictionary headword"),
                ("text", "match surface form"),
                ("strongs", "match Strong's ID (e.g. G3056)"),
                ("morph", "match Robinson morphology (e.g. V-AAI)"),
                ("gloss", "match English gloss"),
            ], False
        if opt in ("-b", "--book"):
            return (_lxx_book_choices() if is_lxx else _nt_book_choices()), False
        if opt == "--section":
            return _lxx_section_choices(), False
        if opt in ("-k", "--kind"):
            return [
                ("catena", "Greek NT Catenae (30 volumes)"),
                ("origen", "Origen biblical commentaries (41 volumes)"),
                ("chrysostom", "John Chrysostom commentaries & homilies (26 series)"),
                ("patristic", "First1KGreek Fathers (Cyril, Methodius, Eusebius, Clement)"),
                ("patrologia", "Patrologia Graeca commentaries (Cyril, Theophylact, Oecumenius, Photius, Procopius)"),
            ], False
        if opt == "--corpus":
            return [
                ("auto", "NT by default; LXX automatically for LXX books"),
                ("nt", "Greek New Testament only"),
                ("lxx", "Greek Septuagint (LXX, 56 books) only"),
                ("both", "Search both New Testament and Septuagint"),
            ], False
        if opt == "--from":
            return [
                ("mt", "Masoretic / Hebrew / English numbering (1–150)"),
                ("lxx", "Septuagint numbering (1–151)"),
            ], False

    # Unified full-text search options (`aegean find`)
    if cmd_path == ("find",):
        if opt in ("-e", "--edition"):
            return _nt_edition_choices(), False
        if opt in ("-b", "--book"):
            return _nt_book_choices() + _lxx_book_choices(), False

    # Greek NLP options
    if cmd_path and cmd_path[0] == "greek":
        if opt in ("-m", "--meter"):
            return _meter_choices(), False
        if opt in ("-d", "--dict", "--dictionary"):
            return _dictionary_choices(), False
        if opt in ("-p", "--period"):
            return [("attic", "Classical Attic (5th c. BCE)"), ("koine", "Koine (1st c. CE)")], False
        if opt in ("--policy", "--sentence-policy"):
            return [
                ("default", "general Greek punctuation"),
                ("prose", "literary prose"),
                ("verse", "verse lines"),
                ("inscription", "epigraphic text"),
                ("papyrus", "documentary papyri"),
            ], False
        if opt == "--fold":
            return [
                ("perseus", "UD Ancient Greek Perseus"),
                ("proiel", "UD Ancient Greek PROIEL"),
                ("papygreek", "PapyGreek regularized fold"),
                ("papygreek-orig", "PapyGreek diplomatic ORIG fold"),
                ("verse", "Euripides Bacchae verse fold"),
                ("dbbe", "DBBE Byzantine book epigrams"),
            ], False
        if opt == "--target":
            return [("spacy", "spaCy Doc"), ("stanza", "Stanza Document"), ("cltk", "CLTK Doc")], False
        if opt == "--source":
            return [
                ("auto", "search Perseus then First1KGreek"),
                ("perseus", "Perseus canonical-greekLit"),
                ("first1k", "OpenGreekAndLatin First1KGreek"),
            ], False

    # Cross-cutting CLI options
    if opt in ("-f", "--format") and cmd_path == ("export",):
        return [
            ("json", "lossless corpus JSON"),
            ("csv", "tabular CSV"),
            ("tsv", "tab-separated values"),
            ("epidoc", "EpiDoc TEI XML"),
            ("conllu", "Universal Dependencies CoNLL-U"),
            ("parquet", "Apache Parquet"),
            ("turtle", "RDF Turtle"),
            ("jsonld", "RDF JSON-LD"),
            ("workbench", "Linear A Research Workbench JSON"),
        ], False
    if opt == "--style" and cmd_path == ("cite",):
        return [("plain", "plain-text citation"), ("bibtex", "BibTeX entry"), ("apa", "APA style")], False
    if opt == "--layout" and cmd_path[:1] == ("review",):
        return [
            ("editable", "compact 28-column spreadsheet + companion sidecar"),
            ("full", "complete 60-column review table"),
        ], False
    if opt == "--priority" and cmd_path[:1] == ("review",):
        return [
            ("calibrated-risk", "highest calibrated error risk first"),
            ("review-recommended", "unverified/fallback lemmas first"),
            ("document-order", "natural document order"),
        ], False
    if opt == "--provider" and cmd_path[:1] == ("ai",):
        return [
            ("anthropic", "Anthropic Claude"),
            ("openai", "OpenAI"),
            ("grok", "xAI Grok"),
            ("gemini", "Google Gemini"),
            ("openrouter", "OpenRouter"),
            ("local", "local OpenAI-compatible server (Ollama/vLLM)"),
        ], False
    if opt in ("-c", "--category") and cmd_path[:1] == ("library",):
        return _library_category_choices(), False
    return [], False


def _library_category_choices() -> list[tuple[str, str]]:
    return [
        ("corpus", "30 Aegean & Greek corpora"),
        ("bible", "6 Biblical & Koine Greek bundles"),
        ("patristics", "5 Greek Church Fathers & Patristic collections"),
        ("classical", "5 Archaic, Classical, Hellenistic, Imperial & Late Antique collections"),
        ("byzantine", "2 Byzantine Greek collections (up to 1453 + vernacular)"),
        ("work", "3,844 collection works + 1,778 Perseus / First1KGreek works"),
        ("commentary", "112 Greek patristic commentaries (11 Fathers/traditions)"),
        ("lexicon", "5 hosted Greek dictionaries"),
        ("model", "4 NLP & neural models"),
        ("other", "benchmarks, images, and web app"),
    ]


def _library_install_choices() -> list[tuple[str, str]]:
    from aegean.library import PACKS
    from aegean.scripts.greek.perseus import POPULAR_WORKS

    out: list[tuple[str, str]] = [
        (p.id, f"pack · {p.title} ({p.size_hint})") for p in PACKS
    ]
    out.extend(_dataset_choices())
    for w in POPULAR_WORKS:
        out.append((w["id"], f"{w['author']} — {w['title']}"))
    return out


def _library_remove_choices() -> list[tuple[str, str]]:
    from aegean.library import PACKS, list_items

    out: list[tuple[str, str]] = []
    for it in list_items(status="downloaded", include_works=True):
        out.append((it.id, f"installed · {it.title[:48]}"))
    for p in PACKS:
        out.append((p.id, f"pack · {p.title}"))
    return out


def _bible_install_choices() -> list[tuple[str, str]]:
    return [
        ("biblical", "all 5 core Biblical & Koine Greek bundles (~27 MB)"),
        ("patristic", "Apostolic Fathers, Pseudepigrapha & 33 Patrologia Graeca vols (~27 MB)"),
        ("nt", "27-book Greek NT Nestle 1904 (~18 MB)"),
        ("editions", "8 Greek NT editions: SBLGNT, SRGNT, BHP, Tisch, WH, BYZ, Antoniades, TR (~3.3 MB)"),
        ("witnesses", "13 early 2nd–5th c. CE manuscripts (~2.0 MB)"),
        ("strongs", "11,142 Extended Strong's entries (~1.5 MB)"),
        ("lxx", "55-book Swete Septuagint (~1.7 MB)"),
    ]


def _commentary_work_choices(book_filter: str | None = None) -> list[tuple[str, str]]:
    from aegean.greek.bible._catalogs import patristic_commentaries

    try:
        rows = patristic_commentaries(book_filter)
    except ValueError:
        rows = patristic_commentaries()
    return [
        (r["work_id"], f"{r['book']} · {r['author']} — {r['title'][:42]}")
        for r in rows
    ]


def _find_target_choices() -> list[tuple[str, str]]:
    extra = [
        ("lxx", "Swete Septuagint (55 Greek OT books)"),
        ("nt-editions", "9 Greek NT editions bundle"),
        ("PG073", "Patrologia Graeca Vol. 73 — Cyril of Alexandria on John"),
        ("PG123", "Patrologia Graeca Vol. 123 — Theophylact on Gospels"),
    ]
    return _corpus_choices() + extra + _nt_book_choices() + _lxx_book_choices()


def _positional_choices(
    cmd_path: tuple[str, ...],
    pos_index: int,
    prior_tokens: Sequence[str],
) -> list[tuple[str, str]]:
    """Return offline domain choices for positional argument ``pos_index`` of ``cmd_path``."""
    pos_tokens = [t for t in prior_tokens if not t.startswith("-")]
    if cmd_path == ("library", "install"):
        return _library_install_choices()
    if cmd_path == ("library", "remove"):
        return _library_remove_choices()
    if cmd_path == ("bible", "install"):
        return _bible_install_choices()
    if cmd_path == ("find",) and pos_index == 1:
        return _find_target_choices()
    if pos_index == 0:
        if cmd_path in _CORPUS_FIRST_PATHS:
            return _corpus_choices()
        if cmd_path in (("data", "fetch"), ("data", "remove")):
            return _dataset_choices()
        if cmd_path == ("library", "list"):
            return _library_category_choices()
        if cmd_path == ("library", "info"):
            return _library_install_choices()
        if cmd_path == ("bridge",):
            return [("linearb", "Mycenaean Linear B"), ("cypriot", "Cypriot syllabary")]
        if cmd_path == ("bible", "read"):
            if "--lxx" in prior_tokens:
                return _lxx_book_choices()
            # Offer NT books first, then LXX books so both `John` and `Gen` complete naturally.
            nt = _nt_book_choices()
            seen = {name.lower() for name, _ in nt}
            lxx = [(n, d) for n, d in _lxx_book_choices() if n.lower() not in seen]
            return nt + lxx
        if cmd_path in (("bible", "compare"), ("bible", "witnesses")):
            return _nt_book_choices()
        if cmd_path == ("bible", "books"):
            return [
                ("nt", "27 Greek New Testament books"),
                ("lxx", "56 Septuagint books (Swete + Ecclesiastes)"),
                ("editions", "9 Greek NT editions"),
                ("witnesses", "13 early 2nd–5th c. CE manuscript witnesses"),
                ("all", "summary of all biblical catalogs"),
            ]
        if cmd_path == ("bible", "commentary"):
            verbs = [
                ("read", "read commentary sections by book or work ID"),
                ("search", "search commentary text for a Greek term"),
                ("list", "list available volumes"),
            ]
            return verbs + _commentary_book_choices() + _commentary_work_choices()
        if cmd_path == ("db", "search"):
            return [("ddbdp", "DDbDP documentary papyri SQLite FTS")]
    if cmd_path == ("bible", "commentary") and pos_tokens:
        verb = pos_tokens[0].lower()
        if pos_index == 1 and verb in ("read", "search"):
            return _commentary_book_choices() + _commentary_work_choices()
        if pos_index == 1 and verb == "list":
            return _commentary_book_choices()
        if pos_index == 2 and verb == "read":
            return _commentary_work_choices(pos_tokens[1])
    return []


# ── Tokenizing partial lines safely (even with unclosed quotes) ───────────────


def _split_partial(text: str) -> tuple[list[str], str, str]:
    """Split ``text`` into ``(completed_tokens, current_word, line_prefix)``.

    Unlike bare ``shlex.split``, handles an in-progress quoted string gracefully without
    dropping completions, and preserves the exact ``line_prefix`` before ``current_word``
    so full-line suggestions splice back cleanly.
    """
    if not text:
        return [], "", ""
    tokens: list[str] = []
    cur: list[str] = []
    quote: str | None = None
    i = 0
    n = len(text)
    tok_start = 0
    in_tok = False
    while i < n:
        ch = text[i]
        if quote is not None:
            if ch == "\\" and quote == '"' and i + 1 < n:
                cur.append(text[i + 1])
                i += 2
                continue
            if ch == quote:
                quote = None
                i += 1
                continue
            cur.append(ch)
            i += 1
            continue
        if ch in ("'", '"'):
            if not in_tok:
                tok_start = i
                in_tok = True
            quote = ch
            i += 1
            continue
        if ch.isspace():
            if in_tok:
                tokens.append("".join(cur))
                cur = []
                in_tok = False
            i += 1
            continue
        if not in_tok:
            tok_start = i
            in_tok = True
        cur.append(ch)
        i += 1

    if in_tok:
        word = "".join(cur)
        prefix = text[:tok_start]
        return tokens, word, prefix
    return tokens, "", text


def _option_takes_value(cmd: Any, opt: str) -> bool:
    for param in getattr(cmd, "params", ()):
        if getattr(param, "is_flag", False):
            continue
        opts = list(getattr(param, "opts", ())) + list(getattr(param, "secondary_opts", ()))
        if opt in opts:
            return True
    return False


def _count_positionals(cmd: Any, tail_tokens: Sequence[str]) -> int:
    count = 0
    skip_next = False
    for tok in tail_tokens:
        if skip_next:
            skip_next = False
            continue
        if tok.startswith("-"):
            if "=" not in tok and _option_takes_value(cmd, tok):
                skip_next = True
            continue
        count += 1
    return count


_FLAG_PRIORITY: dict[str, int] = {
    "--interlinear": 1,
    "--edition": 2,
    "--editions": 2,
    "--sigla": 2,
    "--book": 3,
    "--by": 3,
    "--roots": 3,
    "--lxx": 4,
    "--neural": 4,
    "--limit": 5,
    "--top": 6,
    "--output": 7,
    "--offline": 8,
    "--json": 9,
    "--help": 99,
}


def _flag_completions(cmd: Any, word: str, prefix: str, used_tokens: Sequence[str]) -> list[CompletionItem]:
    used = {t.partition("=")[0] for t in used_tokens if t.startswith("-")}
    seen: set[str] = set()
    items: list[CompletionItem] = []
    word_low = word.casefold()
    for param in getattr(cmd, "params", ()):
        help_txt = " ".join(str(getattr(param, "help", "") or "").split())[:64]
        all_opts = list(getattr(param, "opts", ())) + list(getattr(param, "secondary_opts", ()))
        # Prefer long options first (more readable in dropdowns & ghost-text)
        ordered = sorted(all_opts, key=lambda o: (not o.startswith("--"), o))
        multiple = bool(getattr(param, "multiple", False))
        if not multiple and any(o in used for o in all_opts):
            continue
        for opt in ordered:
            if not opt.startswith("-") or opt in seen:
                continue
            if opt.casefold().startswith(word_low):
                seen.add(opt)
                items.append(
                    CompletionItem(
                        insert=opt,
                        full_line=prefix + opt,
                        description=help_txt,
                        replace_len=len(word),
                    )
                )
    items.sort(key=lambda it: (not it.insert.startswith("--"), _FLAG_PRIORITY.get(it.insert, 50), it.insert))
    return items


def complete_line(
    group: Any,
    text: str,
    *,
    directives: bool = True,
) -> list[CompletionItem]:
    """Return ranked predictive completions for the typed command line ``text``."""
    tokens, word, prefix = _split_partial(text)
    ctx = typer.Context(group, info_name="aegean")

    # 1. Shell-only `use CORPUS` directive
    if directives and tokens and tokens[0] == "use" and len(tokens) == 1:
        choices = _corpus_choices() + [("off", "clear the session corpus")]
        return _filter_value_choices(choices, word, prefix, comma_separated=False)

    # 2. Walk down nested subcommand groups
    cmd: Any = group
    cmd_path: list[str] = []
    tail_start = 0
    for idx, tok in enumerate(tokens):
        if not is_group(cmd):
            break
        sub = cmd.get_command(ctx, tok)
        if sub is None:
            break
        cmd = sub
        cmd_path.append(tok)
        tail_start = idx + 1

    path_tuple = tuple(cmd_path)
    tail_tokens = tokens[tail_start:]
    word_low = word.casefold()

    # 3. Option flags (`--...` or `-...`)
    if word.startswith("-"):
        return _flag_completions(cmd, word, prefix, tail_tokens)

    # 4. Subcommands when still at a group (including top-level directives)
    if is_group(cmd) and not tail_tokens:
        items: list[CompletionItem] = []
        sub_names = (
            list(cmd.list_commands(ctx))
            if hasattr(cmd, "list_commands")
            else sorted(getattr(cmd, "commands", ()))
        )
        for name in sorted(sub_names):
            if name.casefold().startswith(word_low):
                sub = cmd.get_command(ctx, name)
                items.append(
                    CompletionItem(
                        insert=name,
                        full_line=prefix + name,
                        description=short_help(sub) if sub is not None else "",
                        replace_len=len(word),
                    )
                )
        if directives and not cmd_path:
            for d_name, d_desc in SHELL_DIRECTIVES:
                if d_name.casefold().startswith(word_low):
                    items.append(
                        CompletionItem(
                            insert=d_name,
                            full_line=prefix + d_name,
                            description=d_desc,
                            replace_len=len(word),
                        )
                    )
        return items

    # 5. Value for the immediately preceding value-taking option (e.g. `-e `, `--sigla `)
    if tail_tokens:
        prev = tail_tokens[-1]
        if prev.startswith("-") and "=" not in prev and _option_takes_value(cmd, prev):
            choices, is_csv = _option_value_choices(path_tuple, prev, tail_tokens[:-1])
            if choices:
                return _filter_value_choices(choices, word, prefix, comma_separated=is_csv)
            return []

    # 6. Positional argument domain values (e.g. `bible read J`, `data fetch lxx`, `show lin`)
    pos_index = _count_positionals(cmd, tail_tokens)
    pos_choices = _positional_choices(path_tuple, pos_index, tail_tokens)
    if pos_choices:
        return _filter_value_choices(pos_choices, word, prefix, comma_separated=False)

    return []


def _filter_value_choices(
    choices: Sequence[tuple[str, str]],
    word: str,
    prefix: str,
    *,
    comma_separated: bool,
) -> list[CompletionItem]:
    if comma_separated and "," in word:
        head, _, frag = word.rpartition(",")
        used = {p.strip().casefold() for p in head.split(",") if p.strip()}
        frag_low = frag.casefold()
        out: list[CompletionItem] = []
        for val, desc in choices:
            if val.casefold() in used:
                continue
            if val.casefold().startswith(frag_low):
                ins = f"{head},{val}"
                out.append(
                    CompletionItem(
                        insert=ins,
                        full_line=prefix + ins,
                        description=desc,
                        replace_len=len(word),
                    )
                )
        return out

    w_low = word.casefold()
    out = []
    for val, desc in choices:
        if val.casefold().startswith(w_low):
            out.append(
                CompletionItem(
                    insert=val,
                    full_line=prefix + val,
                    description=desc,
                    replace_len=len(word),
                )
            )
    return out


def suggest_inline(
    group: Any,
    text: str,
    *,
    history: Iterable[str] = (),
    directives: bool = True,
) -> str | None:
    """Return one full-line inline ghost-text suggestion for ``text``, or ``None``.

    Checks recent history first (most recent entry starting with ``text``), then falls back
    to the top live completion from :func:`complete_line`. Never returns a string shorter
    than or identical to ``text``.
    """
    if not text or not text.strip():
        return None
    low = text.casefold()
    # Most recent history match wins (fish / zsh-autosuggestions behavior).
    hist_list = list(history)
    for entry in reversed(hist_list):
        if len(entry) > len(text) and entry.casefold().startswith(low):
            return text + entry[len(text) :]

    items = complete_line(group, text, directives=directives)
    for item in items:
        cand = item.full_line
        if len(cand) > len(text) and cand.casefold().startswith(low):
            return text + cand[len(text) :]
    return None


# ── Native shell-completion callbacks for Typer/Click options & arguments ────


def _click_complete(choices: Sequence[tuple[str, str]], incomplete: str) -> list[tuple[str, str]]:
    inc = incomplete.casefold()
    return [(v, d) for v, d in choices if v.casefold().startswith(inc)]


def shell_complete_nt_book(incomplete: str) -> list[tuple[str, str]]:
    return _click_complete(_nt_book_choices(), incomplete)


def shell_complete_bible_book(ctx: Any, incomplete: str) -> list[tuple[str, str]]:
    params = getattr(ctx, "params", {}) or {}
    if params.get("lxx"):
        return _click_complete(_lxx_book_choices(), incomplete)
    nt = _nt_book_choices()
    seen = {n.lower() for n, _ in nt}
    lxx = [(n, d) for n, d in _lxx_book_choices() if n.lower() not in seen]
    return _click_complete(nt + lxx, incomplete)


def shell_complete_edition(incomplete: str) -> list[tuple[str, str]]:
    return _click_complete(_nt_edition_choices(), incomplete)


def shell_complete_witness(incomplete: str) -> list[tuple[str, str]]:
    if "," in incomplete:
        head, _, frag = incomplete.rpartition(",")
        used = {p.strip().casefold() for p in head.split(",") if p.strip()}
        return [
            (f"{head},{v}", d)
            for v, d in _witness_choices()
            if v.casefold() not in used and v.casefold().startswith(frag.casefold())
        ]
    return _click_complete(_witness_choices(), incomplete)


def shell_complete_bible_collection(incomplete: str) -> list[tuple[str, str]]:
    return _click_complete(
        [
            ("nt", "27 Greek New Testament books"),
            ("lxx", "56 Septuagint books (Swete + Ecclesiastes)"),
            ("editions", "9 Greek NT editions"),
            ("witnesses", "13 early manuscript witnesses"),
        ],
        incomplete,
    )


def shell_complete_dataset(incomplete: str) -> list[tuple[str, str]]:
    return _click_complete(_dataset_choices(), incomplete)


def shell_complete_corpus(incomplete: str) -> list[tuple[str, str]]:
    return _click_complete(_corpus_choices(), incomplete)


def shell_complete_library_category(incomplete: str) -> list[tuple[str, str]]:
    return _click_complete(_library_category_choices(), incomplete)


def shell_complete_library_install_target(incomplete: str) -> list[tuple[str, str]]:
    return _click_complete(_library_install_choices(), incomplete)


def shell_complete_library_remove_target(incomplete: str) -> list[tuple[str, str]]:
    return _click_complete(_library_remove_choices(), incomplete)


def shell_complete_bible_install(incomplete: str) -> list[tuple[str, str]]:
    return _click_complete(_bible_install_choices(), incomplete)

