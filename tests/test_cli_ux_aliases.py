"""`--top` / `--limit` are interchangeable spellings on every capped-rows option.

Every command that caps how many rows it prints declares BOTH names on the same
typer option, with the command's original name kept primary in `--help`. The sweep
half introspects the real command tree (every registered command, every option), so
a future command that grows a `--top` or `--limit` cannot ship without the alias.
The behavioral half runs representative commands both ways and requires
byte-identical output, plus proof the option is live (a different N changes the
output). Option help is asserted via the click parameter objects, never by grepping
rendered `--help` (rich wraps at the console width)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

typer = pytest.importorskip("typer")

from typer.main import get_command  # noqa: E402
from typer.testing import CliRunner  # noqa: E402

from aegean.cli import _build_app  # noqa: E402
from aegean.core.corpus import Corpus  # noqa: E402
from aegean.core.model import Document, DocumentMeta, Token, TokenKind  # noqa: E402

runner = CliRunner()


@pytest.fixture(scope="module")
def app():  # type: ignore[no-untyped-def]
    return _build_app()


def _stdout(res) -> str:  # type: ignore[no-untyped-def]
    """stdout alone when this click version separates it, else the mixed output."""
    try:
        return res.stdout
    except (ValueError, AttributeError):
        return res.output


# ── the sweep: every --top/--limit option in the whole command tree ──────────


def _walk(cmd, path):  # type: ignore[no-untyped-def]
    # Duck-typed: a group carries a `.commands` dict. (typer builds its command
    # objects on an internal click layer, so an isinstance check against
    # click.Group is version-dependent; the attribute is not.)
    subcommands = getattr(cmd, "commands", None)
    if isinstance(subcommands, dict):
        for name, sub in sorted(subcommands.items()):
            yield from _walk(sub, (*path, name))
    else:
        yield " ".join(path), cmd


def _capped_row_options() -> list[tuple[str, tuple[str, ...], frozenset[str], str]]:
    """Every (command path, option names, all spellings, help) that spells --top or --limit."""
    rows = []
    for path, cmd in _walk(get_command(_build_app()), ()):
        for p in cmd.params:
            names = set(getattr(p, "opts", ())) | set(getattr(p, "secondary_opts", ()))
            if names & {"--top", "--limit"}:
                rows.append((path, tuple(p.opts), frozenset(names), p.help or ""))
    return rows


_SWEPT = _capped_row_options()

# plot's --top is the one capped-rows option not yet aliased (it sits outside the
# option-declaration pass that introduced the aliases). Remove it from this set once
# it gains --limit and the sweep enforces it like the rest.
_NOT_YET_ALIASED: set[str] = set()  # every --top/--limit command is now aliased

# The primary (help-leading) spelling each command had before the alias existed:
# the alias must never displace it.
_PRIMARY = {
    "load": "--limit",
    "query": "--limit",
    "db search": "--limit",
    "greek catalog": "--limit",
    "stats": "--top",
    "dispersion": "--top",
    "keyness": "--top",
    "analyze nearest": "--top",
    "analyze cooccur": "--top",
    "analyze clusters": "--top",
    "analyze hands": "--top",
    "greek rarity": "--top",
    "plot": "--top",
}

# Commands whose row cap has no "0 = all" contract, so their help must not claim it:
# greek rarity's hardest(n) slices [:n] (0 shows nothing), and plot forwards its
# count straight to the viz one-liners.
_NO_ZERO_ALL = {"greek rarity", "plot"}


def test_the_sweep_sees_the_known_surface() -> None:
    """The introspection really enumerates the command tree (guards the guard)."""
    assert set(_PRIMARY) <= {path for path, _, _, _ in _SWEPT}


@pytest.mark.parametrize(
    "path,opts,names",
    [(p, o, n) for p, o, n, _ in _SWEPT],
    ids=[p for p, _, _, _ in _SWEPT],
)
def test_every_top_or_limit_option_spells_both(
    path: str, opts: tuple[str, ...], names: frozenset[str]
) -> None:
    if path in _NOT_YET_ALIASED:
        pytest.xfail(f"`aegean {path}` does not carry the alias yet")
    assert {"--top", "--limit"} <= names, (
        f"`aegean {path}` declares {sorted(names & {'--top', '--limit'})} without the "
        "other spelling; add it to the same typer.Option"
    )
    want = _PRIMARY.get(path)
    if want is not None:  # a future command is alias-checked above, primary-free here
        assert opts[0] == want, f"`aegean {path}`: {want} must stay the primary help name"


def test_zero_means_all_documented_where_true() -> None:
    """Every aliased cap documents '0 = all', except where 0 = all is not true."""
    undocumented = [
        path
        for path, _, _, help_text in _SWEPT
        if path not in _NO_ZERO_ALL and "0 = all" not in help_text
    ]
    assert undocumented == []
    overclaimed = [
        path
        for path, _, _, help_text in _SWEPT
        if path in _NO_ZERO_ALL and "0 = all" in help_text
    ]
    assert overclaimed == []


# ── behavior: both spellings give byte-identical output ─────────────────────

# Offline commands runnable on bundled data alone. Each case must print at least
# two rows at N=3, so the liveness check (N=1 differs) can bite.
_CASES = [
    ("stats", ["stats", "lineara", "--json"]),
    ("load", ["load", "lineara", "--json"]),
    ("query", ["query", "lineara", "--where", "site-is=Zakros", "--json"]),
    ("dispersion", ["dispersion", "lineara", "--json"]),
    ("keyness", ["keyness", "lineara", "--site", "Zakros", "--json"]),
    ("analyze cooccur", ["analyze", "cooccur", "lineara", "KU-RO", "--json"]),
    ("analyze clusters", ["analyze", "clusters", "lineara", "--json"]),
    ("analyze nearest", ["analyze", "nearest", "qa-si-re-u", "greek", "--json"]),
    ("greek catalog", ["greek", "catalog", "--author", "plato", "--json"]),
]


@pytest.mark.parametrize("name,args", _CASES, ids=[c[0] for c in _CASES])
def test_alias_spellings_give_identical_output(app, name: str, args: list[str]) -> None:  # type: ignore[no-untyped-def]
    top = runner.invoke(app, args + ["--top", "3"])
    lim = runner.invoke(app, args + ["--limit", "3"])
    assert top.exit_code == 0, _stdout(top)
    assert lim.exit_code == 0, _stdout(lim)
    assert _stdout(top) == _stdout(lim)
    # and the option is live, not merely parsed: a different N changes the output
    one = runner.invoke(app, args + ["--top", "1"])
    assert one.exit_code == 0
    assert _stdout(one) != _stdout(top)


def test_stats_alias_output_is_the_correct_cap(app) -> None:  # type: ignore[no-untyped-def]
    """Not just identical: the aliased spelling caps to exactly N rows."""
    res = runner.invoke(app, ["stats", "lineara", "--json", "--limit", "3"])
    assert res.exit_code == 0
    rows = json.loads(_stdout(res))
    assert len(rows) == 3
    assert rows[0] == {"item": "KU-RO", "count": 37}  # the top Linear A word (37 tokens)


# ── db search and greek rarity need a file argument ──────────────────────────


def _word(text: str, position: int) -> Token:
    return Token(text, TokenKind.WORD, tuple(text.split("-")), line_no=0, position=position)


@pytest.fixture(scope="module")
def tiny_db(tmp_path_factory) -> Path:  # type: ignore[no-untyped-def]
    """Three documents; KU-RO occurs five times."""
    from aegean import db

    docs = [
        Document(
            id=f"D{i}", script_id="lineara",
            tokens=[_word("KU-RO", 0), _word("A-DU" if i == 2 else "KU-RO", 1)],
            lines=[[0, 1]], meta=DocumentMeta(site="Haghia Triada"),
        )
        for i in range(3)
    ]
    p = tmp_path_factory.mktemp("aliases") / "tiny.db"
    db.to_sqlite(Corpus(docs, script_id="lineara"), p)
    return p


def test_db_search_alias_identical_and_correct(app, tiny_db: Path) -> None:  # type: ignore[no-untyped-def]
    args = ["db", "search", str(tiny_db), "KU-RO", "--json"]
    top = runner.invoke(app, args + ["--top", "2"])
    lim = runner.invoke(app, args + ["--limit", "2"])
    assert top.exit_code == 0 and lim.exit_code == 0
    assert _stdout(top) == _stdout(lim)
    assert len(json.loads(_stdout(top))) == 2  # 5 KU-RO hits exist; the cap bites
    one = runner.invoke(app, args + ["--top", "1"])
    assert len(json.loads(_stdout(one))) == 1


@pytest.fixture(scope="module")
def greek_sample_json(tmp_path_factory) -> Path:  # type: ignore[no-untyped-def]
    """The bundled 5-passage Greek sample as a reusable .json reference corpus."""
    import aegean

    p = tmp_path_factory.mktemp("aliases") / "greek-sample.json"
    aegean.load("greek").to_json(p)
    return p


def test_greek_rarity_alias_identical_output(app, greek_sample_json: Path) -> None:  # type: ignore[no-untyped-def]
    args = ["greek", "rarity", "μῆνιν ἄειδε θεά", "--corpus", str(greek_sample_json)]
    top = runner.invoke(app, args + ["--top", "1"])
    lim = runner.invoke(app, args + ["--limit", "1"])
    assert top.exit_code == 0, _stdout(top)
    assert lim.exit_code == 0, _stdout(lim)
    assert _stdout(top) == _stdout(lim)
    two = runner.invoke(app, args + ["--top", "2"])
    assert _stdout(two) != _stdout(top)  # the cap drives the rows shown
