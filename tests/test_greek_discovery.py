"""Discovery helpers: greek.nt_books() / greek.popular_works() and their CLI commands.

These answer "which books/works can I load?" — the fixed 27-book NT list and a curated,
verified catalog of well-known Perseus works. CLI assertions use --json so they don't
depend on Rich's terminal-width rendering.
"""

from __future__ import annotations

import json
import re

from aegean import greek


def test_nt_books_lists_all_27() -> None:
    books = greek.nt_books()
    assert len(books) == 27
    names = [b["name"] for b in books]
    assert names[0] == "Matt" and names[-1] == "Rev"
    john = next(b for b in books if b["name"] == "John")
    assert {"john", "jn"} <= set(john["aliases"])
    # every alias resolves through load_nt's accepted-name map
    from aegean.scripts.greek.nt import _ALIAS

    for b in books:
        for alias in b["aliases"]:
            assert _ALIAS[alias] == b["name"]


def test_popular_works_catalog_well_formed() -> None:
    works = greek.popular_works()
    assert len(works) >= 20
    ids = [w["id"] for w in works]
    assert len(ids) == len(set(ids))  # no duplicates
    assert all(re.fullmatch(r"tlg\d{4}\.tlg\d{3}", i) for i in ids)
    assert all({"id", "author", "title"} <= set(w) for w in works)
    assert {"id": "tlg0012.tlg001", "author": "Homer", "title": "Iliad"} in works
    # caller can't mutate the module catalog
    works[0]["title"] = "MUTATED"
    assert greek.popular_works()[0]["title"] == "Iliad"


def test_cli_nt_books_json() -> None:
    from typer.testing import CliRunner

    from aegean.cli import _build_app

    r = CliRunner().invoke(_build_app(), ["greek", "nt-books", "--json"])
    assert r.exit_code == 0, r.output
    data = json.loads(r.stdout)
    assert len(data) == 27 and any(b["name"] == "John" for b in data)


def test_cli_works_json() -> None:
    from typer.testing import CliRunner

    from aegean.cli import _build_app

    r = CliRunner().invoke(_build_app(), ["greek", "works", "--json"])
    assert r.exit_code == 0, r.output
    data = json.loads(r.stdout)
    assert any(w["title"] == "Iliad" for w in data)


def test_resolve_documents_expands_a_chapter_range() -> None:
    """The show/nt chapter-range logic: 'Matt 1-3' -> the Matt 1..3 documents in order,
    a dotted id resolves, a plain id yields one, and no match yields an empty list."""
    from aegean.core.corpus import Corpus
    from aegean.core.model import Document, Token, TokenKind
    from aegean.core.resolve import resolve_documents

    docs = [
        Document(id=f"Matt {n}", script_id="greek",
                 tokens=[Token("x", TokenKind.WORD, position=0)], lines=[[0]])
        for n in (1, 2, 3, 4)
    ]
    corpus = Corpus(docs, script_id="greek")
    assert [d.id for d in resolve_documents(corpus, "Matt 1-3")] == ["Matt 1", "Matt 2", "Matt 3"]
    assert [d.id for d in resolve_documents(corpus, "Matt.2")] == ["Matt 2"]  # dot-fold
    assert [d.id for d in resolve_documents(corpus, "Matt 4")] == ["Matt 4"]  # plain id
    assert resolve_documents(corpus, "Mark 9") == []  # no such document
