"""CLI friendliness of the `aegean greek` group (and the loaders it surfaces).

What is pinned here, each by its output contract (not "it runs"):

- `greek eval`: --fold/--split validated before any fetch; the old --treebank fold
  selector survives as a hidden deprecated alias whose value still selects the fold;
  results save with -o.
- The four formerly bare activation sites (parse --parser, pipeline --parser,
  eval parser, eval nt) fail with _activate's one clean line, never a traceback.
- `greek work`: a missing id and a bad --source fail with guidance; an un-work-shaped
  id gets the catalog bridge hint; -o dispatches by extension via write_corpus.
- `greek nt`: malformed --ref and unknown-book errors are human (nt.py owns the
  messages), the summary ends with a read-it hint, -o dispatches by extension.
- `load_work` ref selection: a ref that matches no textpart errors instead of
  returning the whole work mislabeled with the ref.
- `greek catalog`: --source validated; --limit applies to --json/-o with the
  untruncated total kept in 'matched'.
- Small text contracts: lexicon-link's KeyError text, gloss's deep-link pointer,
  the nt-books footer, rarity --corpus resolution, inflect feature validation,
  bracket-escaped extra names in rendered help.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

typer = pytest.importorskip("typer")

from typer.testing import CliRunner  # noqa: E402

from aegean.cli import _build_app  # noqa: E402

runner = CliRunner()

TEI_FIXTURE = Path(__file__).parent / "fixtures" / "greeklit" / "sample.xml"


@pytest.fixture(scope="module")
def app():  # type: ignore[no-untyped-def]
    return _build_app()


def ok(app, *args: str) -> str:  # type: ignore[no-untyped-def]
    res = runner.invoke(app, list(args))
    assert res.exit_code == 0, res.output
    return res.output


def err(app, *args: str) -> str:  # type: ignore[no-untyped-def]
    res = runner.invoke(app, list(args))
    assert res.exit_code != 0, res.output
    return res.output


def _boom(*args: object, **kwargs: object) -> None:
    raise RuntimeError("boom")


# ── eval: fold/split validation + the deprecated --treebank alias ────────────
def test_eval_rejects_bad_fold(app):
    msg = err(app, "greek", "eval", "ud", "--fold", "bogus")
    assert "--fold must be perseus or proiel" in msg
    assert "Traceback" not in msg


def test_eval_rejects_bad_split(app):
    msg = err(app, "greek", "eval", "ud", "--split", "train")
    assert "--split must be dev or test" in msg


def test_eval_treebank_alias_warns_and_is_validated(app):
    # the alias value flows into the same validation as --fold
    msg = err(app, "greek", "eval", "ud", "--treebank", "bogus")
    assert "deprecated" in msg and "--fold" in msg
    assert "--fold must be perseus or proiel" in msg


def test_eval_fold_and_alias_select_the_fold(app, monkeypatch):
    seen: list[dict[str, str]] = []

    def fake_eval(*, treebank: str, split: str) -> dict[str, float]:
        seen.append({"treebank": treebank, "split": split})
        return {"upos": 0.97}

    monkeypatch.setattr("aegean.greek.evaluate_on_ud", fake_eval)
    out = ok(app, "greek", "eval", "ud", "--fold", "proiel", "--split", "dev", "--json")
    assert json.loads(out[out.index("{"):]) == {"upos": 0.97}
    # the deprecated alias reaches the very same parameter
    res = runner.invoke(app, ["greek", "eval", "ud", "--treebank", "proiel", "--json"])
    assert res.exit_code == 0, res.output
    assert "deprecated" in res.output
    assert seen == [
        {"treebank": "proiel", "split": "dev"},
        {"treebank": "proiel", "split": "test"},
    ]


def test_eval_saves_result_with_output(app, monkeypatch, tmp_path):
    monkeypatch.setattr("aegean.greek.evaluate_tagger", lambda: {"accuracy": 0.5})
    out_file = tmp_path / "metrics.json"
    out = ok(app, "greek", "eval", "tagger", "-o", str(out_file))
    assert json.loads(out_file.read_text(encoding="utf-8")) == {"accuracy": 0.5}
    assert f"wrote {out_file}" in out  # write_result's single confirmation


# ── the four formerly bare activation sites ──────────────────────────────────
def test_parse_parser_activation_failure_is_one_clean_line(app, monkeypatch):
    monkeypatch.setattr("aegean.greek.use_parser", _boom)
    msg = err(app, "greek", "parse", "λόγος", "--parser")
    assert "could not activate the dependency parser: boom" in msg
    assert "Traceback" not in msg


def test_pipeline_parser_activation_failure_is_one_clean_line(app, monkeypatch):
    monkeypatch.setattr("aegean.greek.use_parser", _boom)
    msg = err(app, "greek", "pipeline", "λόγος", "--parse", "--parser")
    assert "could not activate the dependency parser: boom" in msg
    assert "Traceback" not in msg


def test_eval_parser_activation_failure_is_one_clean_line(app, monkeypatch):
    monkeypatch.setattr("aegean.greek.use_parser", _boom)
    msg = err(app, "greek", "eval", "parser")
    assert "could not activate the dependency parser: boom" in msg
    assert "Traceback" not in msg


def test_eval_nt_activation_failure_is_one_clean_line(app, monkeypatch):
    monkeypatch.setattr("aegean.greek.use_neural_pipeline", _boom)
    msg = err(app, "greek", "eval", "nt")
    assert "could not activate the neural joint pipeline: boom" in msg
    assert "Traceback" not in msg


# ── greek work: id guidance, --source validation, -o dispatch ────────────────
def test_work_without_id_names_works_and_catalog(app):
    msg = err(app, "greek", "work")
    assert "give a work id" in msg
    assert "aegean greek works" in msg and "aegean greek catalog" in msg


def test_work_validates_source_before_fetching(app):
    msg = err(app, "greek", "work", "tlg0012.tlg001", "--source", "bogus")
    assert "--source must be auto, perseus, or first1k" in msg


def test_work_unshaped_id_gets_the_catalog_bridge_hint(app, monkeypatch):
    from aegean.data import DataNotAvailableError

    def fake_load_work(work: str, **kwargs: object):  # type: ignore[no-untyped-def]
        raise DataNotAvailableError(
            f"could not fetch {work!r} (perseus: work must look like "
            f"'tlg0012.tlg001', got {work!r})"
        )

    monkeypatch.setattr("aegean.greek.load_work", fake_load_work)
    msg = err(app, "greek", "work", "iliad")
    assert "could not fetch 'iliad'" in msg
    assert "search it by name:  aegean greek catalog iliad" in msg
    # a well-shaped id that merely doesn't resolve gets no bridge hint
    msg = err(app, "greek", "work", "tlg0012.tlg999")
    assert "search it by name" not in msg


def test_work_output_dispatches_by_extension(app, monkeypatch, tmp_path):
    import aegean

    bundled = aegean.load("greek")
    monkeypatch.setattr("aegean.greek.load_work", lambda work, **kw: bundled)
    out_db = tmp_path / "work.db"
    out = ok(app, "greek", "work", "tlg0012.tlg001", "-o", str(out_db))
    assert f"wrote {len(bundled)} documents to {out_db}" in out
    assert out_db.read_bytes()[:15] == b"SQLite format 3"  # a real SQLite corpus
    back = aegean.Corpus.from_sql(out_db)
    assert [d.id for d in back] == [d.id for d in bundled]
    msg = err(app, "greek", "work", "tlg0012.tlg001", "-o", str(tmp_path / "work.xyz"))
    assert "use a .json or .db/.sqlite extension" in msg


# ── load_work ref selection: no silent whole-work fallback ───────────────────
def test_ref_matching_no_textpart_errors_instead_of_mislabeling():
    from aegean.scripts.greek.perseus import parse_tei_work

    blob = TEI_FIXTURE.read_bytes()
    with pytest.raises(ValueError, match="ref 'abc' selected no text"):
        parse_tei_work(blob, "w", ref="abc")
    # the error still names the sections that do exist
    with pytest.raises(ValueError, match="sections here: 1, 2"):
        parse_tei_work(blob, "w", ref="abc")
    # a non-numeric tail below a matched textpart refuses too
    with pytest.raises(ValueError, match="selected no text"):
        parse_tei_work(blob, "w", ref="1.abc")
    # several unmatched components can never be a single line selector
    with pytest.raises(ValueError, match="selected no text"):
        parse_tei_work(blob, "w", ref="9.9.9")


def test_ref_guard_leaves_valid_selection_intact():
    from aegean.scripts.greek.perseus import parse_tei_work

    blob = TEI_FIXTURE.read_bytes()
    _, _, docs = parse_tei_work(blob, "w", ref="1.1")  # book 1, line 1
    assert docs[0].id == "w:1.1" and len(docs[0].lines) == 1
    _, _, docs = parse_tei_work(blob, "w", ref="2")  # the prose textpart
    assert docs[0].id == "w:2" and len(docs[0].lines) == 2


# ── greek nt: human errors, read-it hint, -o dispatch ────────────────────────
def test_nt_ref_parser_message_names_the_accepted_shapes():
    from aegean.scripts.greek.nt import _parse_ref

    for bad in ("abc", "1.1-abc", "1.x"):
        with pytest.raises(ValueError) as exc:
            _parse_ref(bad)
        assert f"malformed NT ref {bad!r}" in str(exc.value)
        assert "use '1' (chapter) or '1.1-1.18' (verses)" in str(exc.value)
        assert "invalid literal" not in str(exc.value)
    # the accepted shapes still parse to the same tuples
    assert _parse_ref("3") == (3, None, 3, None)
    assert _parse_ref("3.16") == (3, 16, 3, 16)
    assert _parse_ref("3.16-18") == (3, 16, 3, 18)
    assert _parse_ref("3.16-3.18") == (3, 16, 3, 18)
    assert _parse_ref("3-5") == (3, None, 5, None)


def test_nt_unknown_book_suggests_the_canonical_name():
    from aegean.scripts.greek.nt import _resolve_book

    with pytest.raises(ValueError) as exc:
        _resolve_book("Jhon")
    msg = str(exc.value)
    # the closest candidate is the alias 'jhn'; the answer is the canonical 'John'
    assert "did you mean 'John'?" in msg
    # the library speaks Python; the CLI swaps in its own command form
    assert "greek.nt_books()" in msg
    from typer.testing import CliRunner

    from aegean.cli import _build_app

    res = CliRunner().invoke(_build_app(), ["greek", "nt", "Jhon"])
    assert res.exit_code == 1
    assert "aegean greek nt-books" in res.output
    with pytest.raises(ValueError) as exc:
        _resolve_book("Habakkuk")  # nothing close: static examples + the pointer
    msg = str(exc.value)
    assert "'John', 'Jn', 'Matthew', '1Cor', 'Rev'" in msg
    assert "greek.nt_books()" in msg
    assert _resolve_book("jn") == "John"  # aliases still resolve


def test_cli_nt_bad_ref_is_human(app):
    # Philemon is the bundled offline book, so this never needs the network
    msg = err(app, "greek", "nt", "Philemon", "--ref", "abc")
    assert "malformed NT ref 'abc'" in msg
    assert "invalid literal" not in msg and "Traceback" not in msg


def test_cli_nt_unknown_book_did_you_mean(app):
    msg = err(app, "greek", "nt", "Jhon")
    assert "did you mean 'John'?" in msg
    assert "nt-books" in msg


def test_cli_nt_summary_ends_with_read_it_hint(app):
    out = ok(app, "greek", "nt", "Philemon")
    assert 'read it:  aegean show nt "Phlm 1"' in out


def test_cli_nt_output_dispatches_by_extension(app, tmp_path):
    import aegean

    out_db = tmp_path / "phlm.db"
    out = ok(app, "greek", "nt", "Philemon", "-o", str(out_db))
    assert f"wrote 1 documents to {out_db}" in out
    assert out_db.read_bytes()[:15] == b"SQLite format 3"
    back = aegean.Corpus.from_sql(out_db)
    assert back.documents[0].id == "Phlm 1"
    msg = err(app, "greek", "nt", "Philemon", "-o", str(tmp_path / "phlm.xyz"))
    assert "use a .json or .db/.sqlite extension" in msg


def test_nt_books_footer_is_a_cli_command(app):
    out = ok(app, "greek", "nt-books")
    assert "aegean greek nt John --ref 1.1-1.18" in out
    assert "load_nt(" not in out  # no Python in the shell's next step


# ── greek catalog: --source validation + --limit/--json semantics ────────────
def test_catalog_validates_source(app):
    msg = err(app, "greek", "catalog", "--source", "bogus")
    assert "--source must be perseus or first1k" in msg


def test_catalog_limit_applies_to_json_with_untruncated_total(app):
    data = json.loads(ok(app, "greek", "catalog", "homer", "--limit", "1", "--json"))
    assert data["matched"] > 1  # the total is not truncated
    assert len(data["works"]) == 1
    assert {"id", "author", "title", "source"} <= set(data["works"][0])
    everything = json.loads(ok(app, "greek", "catalog", "homer", "--limit", "0", "--json"))
    assert len(everything["works"]) == everything["matched"] == data["matched"]


def test_catalog_output_file_matches_json_shape(app, tmp_path):
    out_file = tmp_path / "homer.json"
    out = ok(app, "greek", "catalog", "homer", "--limit", "2", "-o", str(out_file))
    saved = json.loads(out_file.read_text(encoding="utf-8"))
    assert saved["matched"] > 2 and len(saved["works"]) == 2
    assert f"wrote {out_file}" in out
    assert "works to" not in out  # the bespoke confirmation is gone


def test_catalog_output_csv_tabulates_the_works(app, tmp_path):
    out_file = tmp_path / "homer.csv"
    ok(app, "greek", "catalog", "--author", "Homer", "--limit", "3", "-o", str(out_file))
    lines = out_file.read_text(encoding="utf-8").strip().splitlines()
    assert lines[0].startswith("id,author,title")
    assert len(lines) == 4  # header + the 3 limited rows
    assert any("tlg0012" in line for line in lines[1:])


# ── pipeline -o ───────────────────────────────────────────────────────────────
def test_pipeline_saves_the_same_records_it_prints(app, tmp_path):
    out_file = tmp_path / "tokens.json"
    res = runner.invoke(
        app, ["greek", "pipeline", "ἦν ὁ λόγος.", "--json", "-o", str(out_file)]
    )
    assert res.exit_code == 0, res.output
    printed = json.loads(res.stdout)  # stdout is pure JSON; the wrote-line is stderr
    saved = json.loads(out_file.read_text(encoding="utf-8"))
    assert saved == printed and len(saved) == 4
    assert saved[2]["text"] == "λόγος" and saved[2]["upos"] == "NOUN"


def test_pipeline_saves_csv(app, tmp_path):
    out_file = tmp_path / "tokens.csv"
    ok(app, "greek", "pipeline", "ἦν ὁ λόγος.", "-o", str(out_file))
    lines = out_file.read_text(encoding="utf-8").strip().splitlines()
    assert lines[0].split(",")[:5] == ["sentence", "index", "text", "upos", "lemma"]
    assert len(lines) == 5  # header + 4 tokens


# ── small text contracts ──────────────────────────────────────────────────────
def test_lexicon_link_bad_service_has_no_doubled_quotes(app):
    msg = err(app, "greek", "lexicon-link", "λόγος", "--service", "bogus")
    assert "aegean: unknown link service 'bogus'" in msg
    assert 'aegean: "unknown' not in msg  # the old str(KeyError) repr wrapping


def test_gloss_deep_link_error_names_the_cli_command(app):
    msg = err(app, "greek", "gloss", "λόγος", "--dict", "autenrieth")
    assert "aegean greek lexicon-link" in msg
    assert "greek.lexicon_link(" not in msg


def test_rarity_corpus_resolves_like_every_other_corpus_argument(app):
    msg = err(app, "greek", "rarity", "λόγος", "--corpus", "nosuchfile.json")
    assert "no such corpus file" in msg
    assert "Traceback" not in msg
    out = ok(app, "greek", "rarity", "λόγος", "--corpus", "lineara")
    assert "overall rarity" in out  # a registered id now works as the reference


def test_inflect_rejects_a_feature_typo_before_activation(app):
    msg = err(app, "greek", "inflect", "λύω", "--tense", "bogus")
    assert "--tense must be one of" in msg and "aor" in msg
    assert "activating" not in msg  # validated before any download/build


def test_help_renders_extra_names_literally(app):
    # rendered wide so rich cannot wrap mid-token (never grep option names at 80 cols)
    res = runner.invoke(app, ["greek", "tag", "--help"], env={"COLUMNS": "200"})
    assert "[neural]" in res.output
    res = runner.invoke(app, ["greek", "usage", "--help"], env={"COLUMNS": "200"})
    assert "fetches the LSJ index on first use" in res.output
