"""A6 typed form-state and persistence compatibility checks."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from aegean.core.corpus import Corpus
from aegean.core.model import (
    Document,
    FormSegment,
    ReadingStatus,
    SourceMarkupRef,
    Token,
    TokenFormState,
    TokenKind,
)
from aegean.db import from_sqlite, to_sqlite


def _state() -> TokenFormState:
    return TokenFormState(
        diplomatic="a-b",
        regularized="ab",
        normalized="ab",
        model_input="ab",
        segments=(
            FormSegment("a"),
            FormSegment(
                "b",
                ReadingStatus.RESTORED,
                SourceMarkupRef("ed-1", "text/body/w[1]", "supplied", (("reason", "lost"),)),
            ),
            FormSegment("", ReadingStatus.LOST),
        ),
        model_input_ops=("join",),
        model_input_source="normalized",
    )


def _corpus(state: TokenFormState | None = None) -> Corpus:
    token = Token(
        "a-b",
        TokenKind.WORD,
        position=0,
        annotations={"form_diplomatic": "spoof"},
        form_state=state,
    )
    return Corpus([Document("d", "greek", [token], [[0]])], script_id="greek")


def test_form_state_invariants_and_json_roundtrip() -> None:
    state = _state()
    assert state.original == "a-b"
    assert state.supplied and state.restored
    assert state.supplied_text == "b"
    assert state.unclear_text == ""
    assert state.lost and state.has_damage and not state.has_uncertainty
    assert state.editorial_status is ReadingStatus.LOST
    restored = TokenFormState.from_dict(json.loads(json.dumps(state.to_dict())))
    assert restored == state

    with pytest.raises(ValueError, match="only LOST"):
        FormSegment("", ReadingStatus.CERTAIN)
    with pytest.raises(ValueError, match="path"):
        SourceMarkupRef("ed", "", "w")
    with pytest.raises(ValueError, match="duplicate source markup attribute"):
        SourceMarkupRef("ed", "w[1]", "w", (("resp", "a"), ("resp", "b")))
    with pytest.raises(ValueError, match="source"):
        TokenFormState("x", model_input="x", model_input_source=None)


def test_json_roundtrip_and_schema_one_two_default_none() -> None:
    corpus = _corpus(_state())
    loaded = Corpus.from_json(corpus.to_json())
    assert loaded.documents[0].tokens[0].form_state == _state()
    for schema in (1, 2):
        raw = json.loads(corpus.to_json())
        raw["_meta"]["schemaVersion"] = schema
        assert Corpus.from_dict(raw).documents[0].tokens[0].form_state is None


def _legacy_db(path: Path, schema: int = 1) -> None:
    assert schema in (1, 2)
    document_columns = """
                doc_order INTEGER, id TEXT PRIMARY KEY, script_id TEXT, glyphs TEXT,
                transcription TEXT, translations TEXT, site TEXT, support TEXT, scribe TEXT,
                findspot TEXT, period TEXT, name TEXT, images TEXT, notes TEXT, lines TEXT
    """
    token_columns = """
                doc_id TEXT, position INTEGER, line_no INTEGER, text TEXT, kind TEXT,
                glyphs TEXT, status TEXT, signs TEXT, alt TEXT, annotations TEXT
    """
    if schema == 2:
        document_columns = document_columns.replace(
            "                findspot TEXT, period TEXT, name TEXT, images TEXT, notes TEXT, lines TEXT\n",
            "                findspot TEXT, period TEXT, name TEXT, images TEXT, notes TEXT, lines TEXT,\n"
            "                source_text TEXT\n",
        )
        token_columns = token_columns.replace(
            "                doc_id TEXT, position INTEGER,",
            "                doc_id TEXT, token_order INTEGER, position INTEGER,",
        ).replace(
            "                glyphs TEXT, status TEXT, signs TEXT, alt TEXT, annotations TEXT\n",
            "                glyphs TEXT, status TEXT, signs TEXT, alt TEXT, annotations TEXT, alignment TEXT\n",
        )
    with sqlite3.connect(path) as conn:
        conn.executescript(
            f"""
            CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
            CREATE TABLE documents ({document_columns});
            CREATE TABLE tokens ({token_columns});
            """
        )
        conn.execute("INSERT INTO meta VALUES ('schema_version', ?)", (str(schema),))
        conn.execute("INSERT INTO meta VALUES ('script_id', 'greek')")
        conn.execute("INSERT INTO meta VALUES ('provenance', 'null')")
        conn.execute("INSERT INTO meta VALUES ('sign_inventory', 'null')")
        document_values = (0, "old", "greek", "", "", "[]", "", "", "", "", "", "", "", "", "[[0]]")
        if schema == 2:
            document_values += (None,)
        conn.execute(
            f"INSERT INTO documents VALUES ({','.join('?' for _ in document_values)})",
            document_values,
        )
        token_values = ("old", 0, 0, "old", "word", None, "certain", "[]", "[]", "{}")
        if schema == 2:
            token_values = ("old", 0) + token_values[1:] + (None,)
        conn.execute(
            f"INSERT INTO tokens VALUES ({','.join('?' for _ in token_values)})",
            token_values,
        )


@pytest.mark.parametrize("schema", (1, 2))
def test_sqlite_append_migrates_old_schema_atomically_and_roundtrips(
    tmp_path: Path, schema: int
) -> None:
    path = tmp_path / "legacy.db"
    _legacy_db(path, schema=schema)
    # A written-by-schema-2 artifact is readable before migration, with no form state.
    if schema == 2:
        assert from_sqlite(path).get("old").tokens[0].form_state is None
    to_sqlite(_corpus(_state()), path, append=True, fts=False)
    with sqlite3.connect(path) as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(tokens)")}
        assert "form_state_json" in columns
        assert conn.execute(
            "SELECT value FROM meta WHERE key='schema_version'"
        ).fetchone()[0] == "3"
    loaded = from_sqlite(path)
    assert loaded.get("old").tokens[0].form_state is None
    assert loaded.get("d").tokens[0].form_state == _state()


@pytest.mark.parametrize("schema", (1, 2))
def test_sqlite_failed_append_rolls_back_a6_migration(
    tmp_path: Path, schema: int
) -> None:
    path = tmp_path / "legacy.db"
    _legacy_db(path, schema=schema)

    def fail_after_insert(_done: int, _total: int) -> None:
        raise RuntimeError("injected progress failure")

    with pytest.raises(RuntimeError, match="injected progress failure"):
        to_sqlite(
            _corpus(_state()),
            path,
            append=True,
            fts=False,
            progress=fail_after_insert,
        )
    with sqlite3.connect(path) as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(tokens)")}
        assert "form_state_json" not in columns
        assert conn.execute(
            "SELECT value FROM meta WHERE key='schema_version'"
        ).fetchone()[0] == str(schema)
        assert conn.execute("SELECT id FROM documents ORDER BY id").fetchall() == [("old",)]


def test_sqlite_malformed_form_state_is_contextual(tmp_path: Path) -> None:
    path = tmp_path / "bad.db"
    to_sqlite(_corpus(_state()), path, fts=False)
    with sqlite3.connect(path) as conn:
        conn.execute("UPDATE tokens SET form_state_json='[]'")
    with pytest.raises(ValueError, match="malformed token form_state.*document 'd'"):
        from_sqlite(path)


def test_malformed_nested_form_state_and_newer_schema_refuse_cleanly(tmp_path: Path) -> None:
    raw = json.loads(_corpus(_state()).to_json())
    raw["documents"][0]["tokens"][0]["form_state"]["segments"][0]["text"] = ""
    raw["documents"][0]["tokens"][0]["form_state"]["segments"][0]["status"] = "certain"
    with pytest.raises(ValueError, match="malformed token form_state.*only LOST"):
        Corpus.from_dict(raw)

    newer = json.loads(_corpus(_state()).to_json())
    newer["_meta"]["schemaVersion"] = 4
    with pytest.raises(ValueError, match="schema version 4"):
        Corpus.from_dict(newer)

    path = tmp_path / "newer.db"
    to_sqlite(_corpus(_state()), path, fts=False)
    with sqlite3.connect(path) as conn:
        conn.execute("UPDATE meta SET value='4' WHERE key='schema_version'")
    with pytest.raises(ValueError, match="schema version 4"):
        from_sqlite(path)
    with pytest.raises(ValueError, match="schema version 4"):
        to_sqlite(_corpus(_state()), path, append=True, fts=False)


def test_fingerprint_and_dataframe_protect_form_state() -> None:
    legacy = _corpus()
    assert legacy.fingerprint() == _corpus().fingerprint()
    with_state = _corpus(_state())
    assert with_state.fingerprint() != legacy.fingerprint()
    changed = _state()
    changed = TokenFormState(
        changed.diplomatic, changed.regularized, changed.normalized, changed.model_input,
        changed.segments, ("different",), changed.model_input_source,
    )
    assert _corpus(changed).fingerprint() != with_state.fingerprint()
    row = with_state.to_dataframe(level="token").iloc[0]
    assert row["form_diplomatic"] == "a-b"
    assert row["form_diplomatic"] != "spoof"
    assert row["form_model_input"] == "ab"
    assert json.loads(row["form_segments"])[1]["status"] == "restored"
    assert row["form_editorial_status"] == "lost"


def test_fingerprint_distinguishes_missing_and_explicit_empty_forms() -> None:
    absent = TokenFormState("x", regularized=None)
    explicit = TokenFormState("x", regularized="")
    assert _corpus(absent).fingerprint() != _corpus(explicit).fingerprint()
