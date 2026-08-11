"""Correctness tests for four promises the geo / viz / profile / MCP surfaces make.

Each is checked against a hand-computed answer, never merely that the call runs:

* every corpus argument in `aegean.geo` and `aegean.viz` takes the `QueryResults`
  that `Corpus.query` returns, so "query a subset, then map or plot it" is one step;
* a word argument that is not text fails with a typed error naming what arrived,
  instead of an attribute error thrown from inside the matcher;
* `greek.profile_text` flags Beta Code only where the markers are dense, so the
  English fragments, file paths, and code its own documentation names as
  non-triggers stay unflagged while real Beta Code is still recognized;
* `mcp_server.greek_gloss` reports a dictionary whose index could not be downloaded
  as exactly that, in the structured form the tool surface promises.
"""

from __future__ import annotations

from typing import Any

import pytest

from aegean.analysis import FilterRow
from aegean.analysis.query import QueryResults
from aegean.core.corpus import Corpus
from aegean.core.model import Document, DocumentMeta, Token, TokenKind
from aegean.greek.profile import profile_text


def _doc(doc_id: str, words: list[str], site: str = "", period: str = "") -> Document:
    tokens = [
        Token(w, TokenKind.WORD, tuple(w.split("-")), None, 0, i) for i, w in enumerate(words)
    ]
    return Document(
        id=doc_id,
        script_id="lineara",
        tokens=tokens,
        lines=[list(range(len(tokens)))] if tokens else [],
        meta=DocumentMeta(site=site, period=period),
    )


# Two gazetteer sites (both asserted present by tests/test_geo.py) plus one that is not in
# the gazetteer, so the mapped/dropped split is a known quantity: Haghia Triada 2, Knossos 1.
DOCS = [
    _doc("X1", ["sa-ro"], site="Nowhere at all"),
    _doc("A1", ["ku-ro", "pa-i-to"], site="Haghia Triada", period="Third century BC"),
    _doc("A2", ["KU-RO"], site="Haghia Triada"),
    _doc("B1", ["ku-ro", "da-ku"], site="Knossos"),
]


def _results(docs: list[Document]) -> QueryResults:
    """The result set an inscription-scoped query over ``docs`` produces."""
    return QueryResults(inscriptions=list(docs), words=[])


@pytest.fixture(autouse=True)
def _headless_figures():
    """Draw to the headless Agg backend and close every figure a test opened."""
    try:
        import matplotlib
    except ImportError:  # the [viz] extra is absent; the non-plotting tests still run
        yield
        return
    matplotlib.use("Agg")
    yield
    import matplotlib.pyplot as plt

    plt.close("all")


# ── query results are accepted wherever a corpus is: geo ─────────────────────


def test_geo_site_level_maps_query_results() -> None:
    """A result set maps to the sites of exactly its matched documents: Haghia Triada
    twice, Knossos once, and the unmapped find-place dropped."""
    pytest.importorskip("geopandas")
    from aegean.geo import to_geodataframe

    gdf = to_geodataframe(_results(DOCS), level="site")
    assert dict(zip(gdf["site"], gdf["inscriptions"], strict=True)) == {
        "Haghia Triada": 2,
        "Knossos": 1,
    }


def test_geo_inscription_level_maps_query_results() -> None:
    """Inscription level yields one row per mapped document, with its own site label."""
    pytest.importorskip("geopandas")
    from aegean.geo import to_geodataframe

    gdf = to_geodataframe(_results(DOCS), level="inscription")
    assert sorted(gdf["id"]) == ["A1", "A2", "B1"]
    assert dict(zip(gdf["id"], gdf["site"], strict=True))["B1"] == "Knossos"


def test_geo_word_distribution_maps_query_results() -> None:
    """Per-site counts for a word over a result set, case-insensitively (A2 writes KU-RO)."""
    pytest.importorskip("geopandas")
    from aegean.geo import word_distribution

    gdf = word_distribution(_results(DOCS), "ku-ro")
    assert dict(zip(gdf["site"], gdf["count"], strict=True)) == {
        "Haghia Triada": 2,
        "Knossos": 1,
    }


def test_geo_maps_a_real_query_result_from_corpus_query() -> None:
    """The documented journey end to end: query a corpus for one site, map the result."""
    pytest.importorskip("geopandas")
    from aegean.geo import to_geodataframe

    results = Corpus(DOCS).query([FilterRow("site-is", "Knossos")], output="inscriptions")
    assert [d.id for d in results.inscriptions] == ["B1"]
    gdf = to_geodataframe(results, level="site")
    assert list(gdf["site"]) == ["Knossos"]
    assert list(gdf["inscriptions"]) == [1]


def test_geo_query_results_and_their_documents_map_identically() -> None:
    """A result set is not a different corpus: it maps exactly as its documents do."""
    pytest.importorskip("geopandas")
    from aegean.geo import to_geodataframe, word_distribution

    assert to_geodataframe(_results(DOCS), level="site").equals(
        to_geodataframe(DOCS, level="site")
    )
    assert word_distribution(_results(DOCS), "ku-ro").equals(word_distribution(DOCS, "ku-ro"))


# ── query results are accepted wherever a corpus is: viz ─────────────────────


def test_viz_findspots_counts_the_result_sets_sites() -> None:
    """The find-site plot titles the mapped sites and inscriptions of the result set."""
    pytest.importorskip("matplotlib")
    from aegean import viz

    ax = viz.plot_findspots(_results(DOCS))
    assert ax.get_title() == "find-sites (2 sites, 3 inscriptions)"


def test_viz_timeline_bins_reads_a_result_sets_dates() -> None:
    """One document carries a readable date (3rd c. BC, midpoint -250.5 -> the -300 bin);
    the other three are counted as unparsed rather than dropped."""
    from aegean import viz

    tl = viz.timeline_bins(_results(DOCS))
    assert tl.total == 4 and tl.parsed == 1 and tl.unparsed == 3
    assert [(b.start, b.count) for b in tl.bins] == [(-300, 1)]


def test_viz_dispersion_and_frequencies_read_a_result_sets_words() -> None:
    """Five distinct word forms in the result set (``KU-RO`` is written as it stands, so
    it is its own form); only lower-case ``ku-ro`` reaches frequency 2, so the dispersion
    scatter carries exactly one point."""
    pytest.importorskip("matplotlib")
    from aegean import viz

    freq = viz.plot_sign_frequencies(_results(DOCS), kind="words", top=10)
    assert freq.get_title() == "top 5 words"
    disp = viz.plot_dispersion(_results(DOCS), kind="words", min_frequency=2)
    assert len(disp.collections[0].get_offsets()) == 1


def test_viz_networks_read_a_result_sets_cooccurrences() -> None:
    """Word co-occurrence over the result set: ku-ro pairs with pa-i-to (A1) and da-ku
    (B1), so three nodes and two edges are drawn."""
    pytest.importorskip("matplotlib")
    from aegean import viz

    ax = viz.plot_sign_network(_results(DOCS), level="word", scope="document", min_count=1)
    assert len(ax.collections) == 3  # one scatter per node
    assert len(ax.lines) == 2  # one line per edge


def test_viz_keyness_compares_two_result_sets() -> None:
    """Keyness takes a result set on either side; ku-ro is over-used in the Knossos-free
    target, so its bar sits on the positive side."""
    pytest.importorskip("matplotlib")
    from aegean import viz

    target = _results([DOCS[0], DOCS[1]])
    reference = _results([DOCS[2], DOCS[3]])
    ax = viz.plot_keyness(target, reference, kind="words", min_target=1)
    assert ax.get_title().startswith("keyness (words)")
    assert len(ax.patches) >= 1


# Every corpus-taking entry point across the two modules. A new one that forgets the
# coercion fails here in the same commit.
_CORPUS_ENTRY_POINTS = [
    "geo.to_geodataframe",
    "geo.word_distribution",
    "viz.plot_sign_frequencies",
    "viz.plot_dispersion",
    "viz.plot_keyness",
    "viz.plot_collocation_network",
    "viz.plot_balance",
    "viz.plot_findspots",
    "viz.plot_timeline",
    "viz.plot_sign_network",
    "viz.timeline_bins",
]


def _entry_point(name: str) -> Any:
    """The named entry point, bound to the arguments its signature needs beyond the corpus."""
    from aegean import geo, viz

    calls = {
        "geo.to_geodataframe": geo.to_geodataframe,
        "geo.word_distribution": lambda c: geo.word_distribution(c, "ku-ro"),
        "viz.plot_sign_frequencies": viz.plot_sign_frequencies,
        "viz.plot_dispersion": viz.plot_dispersion,
        "viz.plot_keyness": lambda c: viz.plot_keyness(c, DOCS, min_target=1),
        "viz.plot_collocation_network": lambda c: viz.plot_collocation_network(c, min_count=1),
        "viz.plot_balance": viz.plot_balance,
        "viz.plot_findspots": viz.plot_findspots,
        "viz.plot_timeline": viz.plot_timeline,
        "viz.plot_sign_network": lambda c: viz.plot_sign_network(c, level="word", min_count=1),
        "viz.timeline_bins": viz.timeline_bins,
    }
    assert set(calls) == set(_CORPUS_ENTRY_POINTS)  # the table and the ids stay in step
    return calls[name]


@pytest.mark.parametrize("name", _CORPUS_ENTRY_POINTS)
def test_every_corpus_entry_point_accepts_query_results(name: str) -> None:
    """No entry point may reject a result set as the wrong type. ``plot_balance`` has
    nothing to reconcile in this fixture, so it may only raise its own domain error —
    which still proves the documents reached the accounting check."""
    pytest.importorskip("matplotlib")
    if name.startswith("geo."):
        pytest.importorskip("geopandas")
    try:
        out = _entry_point(name)(_results(DOCS))
    except ValueError as exc:  # a domain refusal, not an input-type refusal
        assert name == "viz.plot_balance", f"{name}: {exc}"
        assert "stated total" in str(exc)
        return
    assert out is not None


# ── a non-text word argument fails cleanly ───────────────────────────────────


@pytest.mark.parametrize("word", [123, None, b"ku-ro", ["ku-ro"]])
def test_geo_word_distribution_rejects_a_non_string_word(word: Any) -> None:
    """The matcher case-folds the word, so a non-string used to escape as an
    ``AttributeError``; it is now a ``TypeError`` naming the type that arrived."""
    pytest.importorskip("geopandas")
    from aegean.geo import word_distribution

    with pytest.raises(TypeError) as excinfo:
        word_distribution(DOCS, word)
    assert "word must be a string" in str(excinfo.value)
    assert type(word).__name__ in str(excinfo.value)


@pytest.mark.parametrize("word", [123, b"ku-ro", ["ku-ro"]])
def test_viz_collocation_network_rejects_a_non_string_word(word: Any) -> None:
    """The ego-network word is text or nothing; anything else is refused up front rather
    than silently matching no pair."""
    pytest.importorskip("matplotlib")
    from aegean import viz

    with pytest.raises(TypeError) as excinfo:
        viz.plot_collocation_network(DOCS, word, min_count=1)
    assert "word must be a string or None" in str(excinfo.value)
    assert type(word).__name__ in str(excinfo.value)


def test_viz_collocation_network_still_takes_none_for_the_whole_network() -> None:
    """``None`` remains the documented "no ego network" value."""
    pytest.importorskip("matplotlib")
    from aegean import viz

    ax = viz.plot_collocation_network(DOCS, None, min_count=1)
    assert ax.get_title().startswith("co-occurrence network")


@pytest.mark.parametrize("corpus", ["a corpus", 42, [1, 2, 3]])
def test_geo_rejects_something_that_is_not_a_corpus(corpus: Any) -> None:
    """A string or a list of non-documents is refused with a message that says what the
    argument should be, rather than an attribute error from the middle of the loop."""
    pytest.importorskip("geopandas")
    from aegean.geo import to_geodataframe

    with pytest.raises(TypeError) as excinfo:
        to_geodataframe(corpus)
    assert "expected a corpus, query results, or a list of documents" in str(excinfo.value)


# ── the Beta Code density bar ────────────────────────────────────────────────

# The strings `_looks_like_betacode` names as non-triggers, plus their neighbours: a stray
# marker in English, a path, a URL, and code with two slash-divisions.
_NOT_BETACODE = [
    "and/or",
    "I/O",
    "a/b",
    "yes and/or no",
    "x = a/b",
    "if a/b > 1: return a/b",
    "ratio = a/b + 1",
    "read/write access",
    "the input/output buffer",
    "C:/Users/ryan/corpus/data.txt",
    "src/aegean/greek/profile.py",
    "https://example.org/data/a.html",
    "see docs/guide/intro.md and docs/api/ref.md",
]

# Real Beta Code: the Iliad opening, a fuller line with diaeresis and capital markers, a
# particle-heavy clause where two of four words carry an accent, and iota subscripts.
_IS_BETACODE = [
    "mh=nin a)/eide qea/",
    "mh=nin a)/eide qea\\ Phlhi+a/dew A)xilh=os",
    r"o( de\ a)nh\r e)/fh",
    r"tw=| lo/gw| e)/dwke",
]


@pytest.mark.parametrize("text", _NOT_BETACODE)
def test_english_paths_and_code_are_not_read_as_betacode(text: str) -> None:
    """One stray marker, or a marker on a minority of the words, is not Beta Code."""
    assert profile_text(text).looks_like_betacode is False


@pytest.mark.parametrize("text", _IS_BETACODE)
def test_real_betacode_is_still_recognized(text: str) -> None:
    """Densely accented ASCII with no Unicode Greek still reads as Beta Code, and carries
    no combining diacritics of its own."""
    profile = profile_text(text)
    assert profile.looks_like_betacode is True
    assert profile.is_polytonic is False


def test_betacode_needs_two_marked_words_and_half_the_text() -> None:
    """The bar exactly: two accented words out of four clear it, the same two out of five
    do not, and one accented word never does however short the text."""
    assert profile_text("qea/ lo/gos kai de").looks_like_betacode is True
    assert profile_text("qea/ lo/gos kai de men").looks_like_betacode is False
    assert profile_text("qea/ kai de").looks_like_betacode is False
    assert profile_text("lo/gos").looks_like_betacode is False


def test_unicode_greek_is_never_betacode() -> None:
    """Real polytonic Greek is Greek, not a transliteration of it."""
    assert profile_text("μῆνιν ἄειδε θεά").looks_like_betacode is False


# ── the MCP dictionary-download error ────────────────────────────────────────


@pytest.fixture()
def _empty_store(tmp_path, monkeypatch):
    """Point the local data store at an empty directory, so a dictionary index has to be
    downloaded, and leave no lexicon active behind the test."""
    monkeypatch.setenv("PYAEGEAN_CACHE", str(tmp_path))
    yield tmp_path / "pyaegean"
    from aegean import greek

    for name in ("autenrieth", "lsj", "cunliffe"):
        greek.disable_lexicon(name)


@pytest.mark.parametrize("dictionary", ["autenrieth", "lsj", "cunliffe"])
def test_greek_gloss_reports_a_failed_download_as_a_failed_download(
    dictionary: str, _empty_store, monkeypatch
) -> None:
    """With no network and an empty store, the tool says the index could not be
    downloaded and points at what an agent can actually do next. It must not claim the
    dictionary is unhosted, and must not send an agent to a repository build script."""
    import urllib.error
    import urllib.request

    def _no_network(*_args: Any, **_kwargs: Any) -> Any:
        raise urllib.error.URLError("getaddrinfo failed")

    monkeypatch.setattr(urllib.request, "urlopen", _no_network)
    from aegean import mcp_server

    res = mcp_server.greek_gloss("ἀνήρ", dictionary=dictionary)
    assert set(res) == {"error"}
    message = res["error"]
    assert dictionary in message
    assert "could not be downloaded" in message
    assert "data_status" in message  # the store-inspecting tool an agent can call
    assert "not hosted" not in message
    assert "scripts/" not in message  # no repository-only remediation


def test_greek_gloss_reports_a_damaged_index_instead_of_raising(
    _empty_store, monkeypatch
) -> None:
    """A truncated or corrupt index file in the store is a structured error too: the
    gzip failure is an OSError, which used to escape as a traceback."""
    _empty_store.mkdir(parents=True, exist_ok=True)
    (_empty_store / "autenrieth-index.json.gz").write_bytes(b"not a gzip stream")
    from aegean import mcp_server

    res = mcp_server.greek_gloss("ἀνήρ", dictionary="autenrieth")
    assert set(res) == {"error"}
    assert "autenrieth" in res["error"] and "not readable" in res["error"]


def test_greek_gloss_bundled_dictionary_still_answers(_empty_store) -> None:
    """The bundled Koine lexicon is unaffected by an empty store: it needs no download,
    so the download error can never be reported for it."""
    from aegean import mcp_server

    res = mcp_server.greek_gloss("λόγος", dictionary="dodson")
    assert res["headword"] == "λόγος" and "error" not in res
