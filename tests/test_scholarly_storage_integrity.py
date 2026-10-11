"""SQLite replacement and edited CoNLL-U must preserve coherent source evidence."""

from __future__ import annotations

import sqlite3
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from aegean import Corpus, db
from aegean.core.model import Document, Token, TokenKind
from aegean.greek.ud import dump_conllu, load_conllu, load_conllu_document


def _corpus(doc_id: str, text: str, *, payload: str = "") -> Corpus:
    token = Token(text, TokenKind.WORD, position=0, annotations={"payload": payload})
    return Corpus([Document(doc_id, "greek", tokens=[token], lines=[[0]])], script_id="greek")


def _rows(path: Path) -> list[tuple[str, list[str]]]:
    return [(doc.id, [token.text for token in doc.tokens]) for doc in db.from_sqlite(path)]


def test_replacement_keeps_live_committed_wal_and_reader_snapshot_coherent(tmp_path) -> None:
    path = tmp_path / "corpus.sqlite"
    db.to_sqlite(_corpus("old", "παλαιός"), path)
    inode = path.stat().st_ino
    holder = sqlite3.connect(path)
    try:
        assert holder.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
        holder.execute("UPDATE tokens SET text = 'τροποποιημένος'")
        holder.commit()
        assert Path(str(path) + "-wal").stat().st_size > 0
        holder.execute("BEGIN")
        assert holder.execute("SELECT text FROM tokens").fetchone()[0] == "τροποποιημένος"

        db.to_sqlite(_corpus("new", "νέος"), path)

        assert path.stat().st_ino == inode
        assert _rows(path) == [("new", ["νέος"])]
        assert db.search(path, "νέος") == [("new", 0, "νέος")]
        assert holder.execute("SELECT id FROM documents").fetchone()[0] == "old"
        assert holder.execute("SELECT text FROM tokens").fetchone()[0] == "τροποποιημένος"
        holder.rollback()
        assert holder.execute("SELECT id FROM documents").fetchone()[0] == "new"
        assert holder.execute("SELECT text FROM tokens").fetchone()[0] == "νέος"
        assert holder.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        # The same old connection can keep writing the replaced database safely.
        holder.execute("UPDATE tokens SET text = 'νεότερος'")
        holder.commit()
        assert _rows(path) == [("new", ["νεότερος"])]
    finally:
        holder.close()
    assert _rows(path) == [("new", ["νεότερος"])]


@pytest.mark.parametrize("journal_mode", ["DELETE", "WAL"])
def test_replacement_blocked_by_writer_preserves_committed_and_uncommitted_state(
    tmp_path, monkeypatch, journal_mode: str
) -> None:
    path = tmp_path / "corpus.sqlite"
    db.to_sqlite(_corpus("old", "παλαιός"), path)
    holder = sqlite3.connect(path)
    try:
        holder.execute(f"PRAGMA journal_mode={journal_mode}")
        holder.execute("UPDATE tokens SET text = 'committed'")
        holder.commit()
        holder.execute("BEGIN IMMEDIATE")
        holder.execute("UPDATE tokens SET text = 'pending'")
        monkeypatch.setattr(db, "_REPLACEMENT_BUSY_TIMEOUT", 0.0)

        with pytest.raises(sqlite3.OperationalError, match="locked.*cannot replace"):
            db.to_sqlite(_corpus("new", "νέος"), path)

        assert _rows(path) == [("old", ["committed"])]
        assert holder.execute("SELECT text FROM tokens").fetchone()[0] == "pending"
        holder.commit()
        assert _rows(path) == [("old", ["pending"])]
        assert not list(tmp_path.glob(".corpus.sqlite.*.tmp"))
    finally:
        holder.close()


def test_rollback_reader_blocks_replacement_without_losing_its_snapshot(tmp_path, monkeypatch) -> None:
    path = tmp_path / "corpus.sqlite"
    db.to_sqlite(_corpus("old", "παλαιός"), path)
    holder = sqlite3.connect(path)
    try:
        holder.execute("BEGIN")
        assert holder.execute("SELECT id FROM documents").fetchone()[0] == "old"
        monkeypatch.setattr(db, "_REPLACEMENT_BUSY_TIMEOUT", 0.0)
        with pytest.raises(sqlite3.OperationalError, match="locked.*cannot replace"):
            db.to_sqlite(_corpus("new", "νέος"), path)
        assert holder.execute("SELECT text FROM tokens").fetchone()[0] == "παλαιός"
        assert _rows(path) == [("old", ["παλαιός"])]
        holder.rollback()
        db.to_sqlite(_corpus("new", "νέος"), path)
        assert _rows(path) == [("new", ["νέος"])]
    finally:
        holder.close()


def test_replacement_waits_for_an_active_writer_to_commit(tmp_path, monkeypatch) -> None:
    path = tmp_path / "corpus.sqlite"
    db.to_sqlite(_corpus("old", "παλαιός"), path)
    holder = sqlite3.connect(path)
    holder.execute("PRAGMA journal_mode=WAL")
    holder.execute("UPDATE tokens SET text = 'pending'")
    original_connect = sqlite3.connect
    busy: list[int] = []

    class ObservedConnection(sqlite3.Connection):
        def backup(self, target, *, pages=-1, progress=None, name="main", sleep=0.250):
            def finish_writer(status: int, remaining: int, total: int) -> None:
                if progress is not None:
                    progress(status, remaining, total)
                if status == 5:  # SQLITE_BUSY
                    busy.append(status)
                    holder.commit()

            return super().backup(target, pages=pages, progress=finish_writer,
                                  name=name, sleep=sleep)

    def connect(*args, **kwargs):
        return original_connect(*args, **kwargs, factory=ObservedConnection)

    try:
        monkeypatch.setattr(db.sqlite3, "connect", connect)
        db.to_sqlite(_corpus("new", "νέος"), path)
        assert busy
        assert _rows(path) == [("new", ["νέος"])]
        assert holder.execute("SELECT id, text FROM documents, tokens").fetchone() == (
            "new", "νέος"
        )
    finally:
        holder.close()


@pytest.mark.parametrize("journal_mode", ["DELETE", "WAL"])
def test_interrupted_backup_rolls_back_after_copying_pages(
    tmp_path, monkeypatch, journal_mode: str
) -> None:
    path = tmp_path / "corpus.sqlite"
    db.to_sqlite(_corpus("old", "παλαιός"), path, fts=False)
    holder = sqlite3.connect(path)
    holder.execute(f"PRAGMA journal_mode={journal_mode}")
    original_connect = sqlite3.connect
    copied_pages: list[int] = []

    class InterruptingConnection(sqlite3.Connection):
        def backup(self, target, *, pages=-1, progress=None, name="main", sleep=0.250):
            def interrupt(status: int, remaining: int, total: int) -> None:
                if progress is not None:
                    progress(status, remaining, total)
                if status == 0 and remaining > 0:  # SQLITE_OK, also on Python 3.10
                    copied_pages.append(total - remaining)
                    raise KeyboardInterrupt("interrupted after backup started")

            return super().backup(target, pages=1, progress=interrupt, name=name, sleep=sleep)

    def connect(*args, **kwargs):
        return original_connect(*args, **kwargs, factory=InterruptingConnection)

    try:
        monkeypatch.setattr(db.sqlite3, "connect", connect)
        with pytest.raises(KeyboardInterrupt, match="backup started"):
            db.to_sqlite(_corpus("new", "νέος", payload="x" * 2_000_000), path, fts=False)
        assert copied_pages and copied_pages[0] > 0
        assert _rows(path) == [("old", ["παλαιός"])]
        assert holder.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert not list(tmp_path.glob(".corpus.sqlite.*.tmp"))
    finally:
        holder.close()


def test_replacement_matches_nondefault_wal_page_size(tmp_path) -> None:
    path = tmp_path / "corpus.sqlite"
    db.to_sqlite(_corpus("old", "παλαιός"), path)
    holder = sqlite3.connect(path)
    try:
        holder.execute("PRAGMA page_size=8192")
        holder.execute("VACUUM")
        holder.execute("PRAGMA journal_mode=WAL")
        holder.execute("UPDATE tokens SET text = 'committed'")
        holder.commit()
        db.to_sqlite(_corpus("new", "νέος"), path)
        assert _rows(path) == [("new", ["νέος"])]
        assert holder.execute("PRAGMA page_size").fetchone()[0] == 8192
        assert holder.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert holder.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        holder.close()


@pytest.mark.parametrize("journal_mode", ["DELETE", "WAL"])
def test_crashed_backup_recovers_the_original_database(tmp_path, journal_mode: str) -> None:
    path = tmp_path / "corpus.sqlite"
    db.to_sqlite(_corpus("old", "παλαιός"), path, fts=False)
    holder = sqlite3.connect(path)
    holder.execute(f"PRAGMA journal_mode={journal_mode}")
    child = r'''
import os
import sqlite3
import sys
from aegean import Corpus, db
from aegean.core.model import Document, Token, TokenKind

original_connect = sqlite3.connect
class CrashingConnection(sqlite3.Connection):
    def backup(self, target, **kwargs):
        target.execute("PRAGMA cache_size=1")
        def crash(status, remaining, total):
            if status == 0 and total - remaining >= 8 and remaining > 0:
                os._exit(73)
        return super().backup(target, pages=8, progress=crash)

def connect(*args, **kwargs):
    return original_connect(*args, **kwargs, factory=CrashingConnection)
sqlite3.connect = connect
token = Token("new", TokenKind.WORD, position=0, annotations={"payload": "x" * 2_000_000})
corpus = Corpus([Document("new", "greek", tokens=[token], lines=[[0]])], script_id="greek")
db.to_sqlite(corpus, sys.argv[1], fts=False)
'''
    try:
        result = subprocess.run([sys.executable, "-c", child, str(path)], capture_output=True,
                                text=True, timeout=15)
        assert result.returncode == 73, result.stderr
        assert _rows(path) == [("old", ["παλαιός"])]
        assert holder.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        holder.close()


def test_creator_racing_at_publication_is_replaced_through_its_live_wal(tmp_path, monkeypatch) -> None:
    path = tmp_path / "corpus.sqlite"
    holders: list[sqlite3.Connection] = []
    original_link = db.os.link
    inode: list[int] = []

    def concurrent_creator(source, destination):
        if not path.exists():
            # Race after the absent-file observation and before atomic publication.
            monkeypatch.setattr(db.os, "link", original_link)
            db.to_sqlite(_corpus("racing", "παλαιός"), path)
            inode.append(path.stat().st_ino)
            holder = sqlite3.connect(path)
            holders.append(holder)
            holder.execute("PRAGMA journal_mode=WAL")
            holder.execute("UPDATE tokens SET text = 'racing WAL'")
            holder.commit()
        return original_link(source, destination)

    try:
        monkeypatch.setattr(db.os, "link", concurrent_creator)
        db.to_sqlite(_corpus("new", "νέος"), path)
        assert _rows(path) == [("new", ["νέος"])]
        assert path.stat().st_ino == inode[0]
        assert holders[0].execute("SELECT id, text FROM documents, tokens").fetchone() == (
            "new", "νέος"
        )
    finally:
        for holder in holders:
            holder.close()


def test_failed_first_build_leaves_no_destination_or_temporary_database(tmp_path) -> None:
    path = tmp_path / "nested" / "corpus.sqlite"

    def interrupt(done: int, total: int) -> None:
        assert not path.exists()
        raise RuntimeError("cancelled")

    with pytest.raises(RuntimeError, match="cancelled"):
        db.to_sqlite(_corpus("new", "νέος"), path, progress=interrupt)
    assert not path.exists()
    assert list(path.parent.iterdir()) == []


def test_replacement_refuses_foreign_bytes_without_changing_them(tmp_path) -> None:
    path = tmp_path / "corpus.sqlite"
    original = b"unrelated research material"
    path.write_bytes(original)
    with pytest.raises(sqlite3.DatabaseError):
        db.to_sqlite(_corpus("new", "νέος"), path)
    assert path.read_bytes() == original
    assert not list(tmp_path.glob(".corpus.sqlite.*.tmp"))


@pytest.mark.parametrize("suffix", ["-wal", "-shm", "-journal"])
def test_creation_refuses_orphan_sidecars_without_deleting_them(tmp_path, suffix: str) -> None:
    path = tmp_path / "corpus.sqlite"
    sidecar = Path(str(path) + suffix)
    original = b"possibly recoverable SQLite state"
    sidecar.write_bytes(original)
    with pytest.raises(sqlite3.OperationalError, match="recover the original"):
        db.to_sqlite(_corpus("new", "νέος"), path)
    assert not path.exists()
    assert sidecar.read_bytes() == original


_EXTENSION_BLOCK = (
    "# sent_id = original\r\n"
    "# sent_id_orig = source-id\r\n"
    "# text = λόγος ἐστίν\r\n"
    "# text_en = it is a word = translation\r\n"
    "# text_source = diplomatic\r\n"
    "# note without a key\r\n"
    "1-2\tλόγοςἐστίν\t_\t_\t_\t_\t_\t_\t_\tMWT=Yes\r\n"
    "1\tλόγος\tλόγος\tNOUN\t_\t_\t0\troot\t0:root\tNote=x|Note=y\r\n"
    "2\tἐστίν\tεἰμί\tVERB\t_\t_\t1\tcop\t_\t_\r\n"
    "2.1\tἐστίν\tεἰμί\tVERB\t_\t_\t_\t_\t1:cop\t_\r\n\r\n"
)


@pytest.mark.parametrize("strict", [False, True])
def test_extension_comments_do_not_replace_parsed_metadata_or_source_bytes(strict: bool) -> None:
    document = load_conllu_document(_EXTENSION_BLOCK, strict=strict)
    sentence = document.sentences[0]
    assert sentence.sent_id == "original"
    assert sentence.text == "λόγος ἐστίν"
    assert document.dumps() == _EXTENSION_BLOCK


@pytest.mark.parametrize("canonical", [False, True])
def test_edited_metadata_preserves_extension_comments_multiwords_and_empty_nodes(
    canonical: bool,
) -> None:
    sentence = load_conllu(_EXTENSION_BLOCK, strict=True)[0]
    changed = replace(sentence, sent_id="edited", text="λόγος ἦν", tokens=(
        sentence.tokens[0], replace(sentence.tokens[1], form="ἦν"),
    ))
    output = dump_conllu([changed], canonical=canonical)
    for comment in sentence.comments:
        if comment.startswith(("# sent_id_orig", "# text_en", "# text_source", "# note")):
            assert output.count(comment + "\n") == 1
    restored = load_conllu(output, strict=True)[0]
    assert restored.sent_id == "edited"
    assert restored.text == "λόγος ἦν"
    assert restored.tokens[1].form == "ἦν"
    assert restored.multiword_tokens == sentence.multiword_tokens
    assert restored.empty_nodes == sentence.empty_nodes
    assert restored.tokens[0].misc == sentence.tokens[0].misc


def test_extension_only_comments_stay_extensions_when_metadata_is_added() -> None:
    raw = (
        "# sent_id_orig = external\n# text_en = English\n# text-other = another\n"
        "1\ta\t_\tNOUN\t_\t_\t0\troot\t_\t_\n\n"
    )
    sentence = load_conllu(raw, strict=True)[0]
    assert sentence.sent_id == sentence.text == ""
    assert dump_conllu([sentence], canonical=True) == raw
    changed = replace(sentence, sent_id="added", text="a")
    output = dump_conllu([changed])
    assert output.startswith("# sent_id = added\n# text = a\n")
    assert "# sent_id_orig = external\n# text_en = English\n# text-other = another\n" in output


def test_exact_comment_keys_accept_spacing_and_do_not_leak_from_preamble() -> None:
    raw = (
        "# sent_id = preamble\n# text = preamble text\n\n"
        "# sent_id_extra = external\n# text_en = translation\n"
        "1\ta\t_\tNOUN\t_\t_\t0\troot\t_\t_\n\n"
    )
    sentence = load_conllu(raw, strict=True)[0]
    assert sentence.sent_id == sentence.text == ""
    spaced = raw.replace("# sent_id_extra = external", "#\tsent_id\t=\texact")
    spaced = spaced.replace("# text_en = translation", "#text= exact text")
    sentence = load_conllu(spaced, strict=True)[0]
    assert (sentence.sent_id, sentence.text) == ("exact", "exact text")


@pytest.mark.parametrize("as_document", [False, True])
def test_canonical_output_keeps_document_edge_comments_in_separate_blocks(as_document: bool) -> None:
    raw = (
        "# sent_id = document preamble\n# text_en = preamble English\n\n"
        + _EXTENSION_BLOCK
        + "# text_en = trailer English\n# sent_id_orig = trailer-id\n\n"
    )
    document = load_conllu_document(raw, strict=True)
    output = dump_conllu(document if as_document else document.sentences, canonical=True)
    restored = load_conllu_document(output, strict=True)
    assert restored.leading_comments == document.leading_comments
    assert restored.trailing_comments == document.trailing_comments
    assert restored.sentences[0].sent_id == "original"
    assert restored.sentences[0].text == "λόγος ἐστίν"
    assert restored.sentences[0].comments == document.sentences[0].comments


def test_edited_document_keeps_document_edge_extensions_and_sentence_structure() -> None:
    document = load_conllu_document(
        "# text_en = preamble\n\n" + _EXTENSION_BLOCK + "# sent_id_orig = trailer\n\n",
        strict=True,
    )
    edited = replace(document, sentences=(replace(document.sentences[0], sent_id="edited"),))
    restored = load_conllu_document(edited.dumps(), strict=True)
    assert restored.leading_comments == document.leading_comments
    assert restored.trailing_comments == document.trailing_comments
    assert restored.sentences[0].sent_id == "edited"
    assert restored.sentences[0].multiword_tokens == document.sentences[0].multiword_tokens
    assert restored.sentences[0].empty_nodes == document.sentences[0].empty_nodes
