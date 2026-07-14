"""Regression tests for the error-message quality pass.

Each section is owned by one fix group; append your own functions with a unique
group-scoped prefix so concurrent groups do not collide.
"""

from __future__ import annotations

import pytest

import aegean
from aegean.core.corpus import Corpus


# ── group: core/corpus.py — Corpus.load / aegean.load casefold + did-you-mean ──
# The primary Python entry point now inherits the shared forgiving-resolution rule
# (case-insensitive ids + a did-you-mean hint), matching its read_corpus sibling.


def test_corpusload_forgives_case_and_loads() -> None:
    """``aegean.load('LINEARA')`` loads lineara instead of raising (casefold)."""
    corpus = aegean.load("LINEARA")
    assert len(corpus) == 1721
    assert corpus.script_id == "lineara"


def test_corpusload_casefold_via_classmethod() -> None:
    """The same case-folding is on the classmethod, not just the aegean.load wrapper."""
    corpus = Corpus.load("Lineara")
    assert len(corpus) == 1721
    assert corpus.script_id == "lineara"


def test_corpusload_typo_suggests_close_matches() -> None:
    """A near-miss id yields a did-you-mean hint (no bare KeyError, no traceback text)."""
    with pytest.raises(KeyError) as exc:
        aegean.load("lineraa")
    msg = exc.value.args[0]
    assert msg.startswith("no registered corpus 'lineraa' — did you mean 'lineara' or 'linearb'?")
    assert "available: [" in msg
    # the full available list is still present for reference
    assert "'lineara'" in msg and "'nt'" in msg
    assert "Traceback" not in msg


def test_corpusload_single_suggestion() -> None:
    with pytest.raises(KeyError) as exc:
        aegean.load("greeek")
    msg = exc.value.args[0]
    assert msg.startswith("no registered corpus 'greeek' — did you mean 'greek'?")
    assert "available: [" in msg


def test_corpusload_no_close_match_keeps_available_list() -> None:
    """An id with no near match keeps the plain listing (no manufactured suggestion)."""
    with pytest.raises(KeyError) as exc:
        aegean.load("zzzzzz")
    msg = exc.value.args[0]
    assert "did you mean" not in msg
    assert msg.startswith("no registered corpus 'zzzzzz'; available: [")
    assert "'lineara'" in msg


def test_corpusload_parity_with_read_corpus_on_case() -> None:
    """Corpus.load and its flexible sibling read_corpus agree on a wrong-case id."""
    from aegean.core.resolve import read_corpus

    assert len(aegean.load("LINEARA")) == len(read_corpus("LINEARA")) == 1721


# ── group: query (analysis/query.py — run_query field/type guard) ─────────────
# The shared compound-query primitive now validates its filters before the engine
# dereferences them, so a direct Python-API caller gets a clean WHAT + a pointer
# to aegean.analysis.FIELDS instead of a raw KeyError/AttributeError from deep in
# the predicate engine. The CLI `aegean query` and MCP query_corpus wrappers
# already validated the same way; the guard now also lives in the one shared place.


def test_query_unknown_field_is_clean_valueerror() -> None:
    """A wrong-but-plausible field id raises a ValueError naming the field and the
    valid FIELDS, not a raw KeyError from inside the predicate engine."""
    from aegean.analysis import FilterRow

    with pytest.raises(ValueError) as exc:
        aegean.load("greek").query([FilterRow(field="nonsense", value="x")])
    msg = str(exc.value)
    assert "nonsense" in msg
    assert "unknown query field" in msg
    assert "fields:" in msg
    assert "word-prefix" in msg
    # Not the old raw KeyError (whose message is just the bare key repr).
    assert msg != "'nonsense'"
    assert "Traceback" not in msg


def test_query_plausible_typo_field_lists_fields() -> None:
    """Hyphenated field ids make near-miss ids ('site' vs the real 'site-is') a
    genuine error class; the guard still names the valid fields."""
    from aegean.analysis import FilterRow

    with pytest.raises(ValueError) as exc:
        aegean.load("greek").query([FilterRow(field="site", value="x")])
    msg = str(exc.value)
    assert "site" in msg and "fields:" in msg
    assert "site-is" in msg


def test_query_string_instead_of_filterrows_is_clean_typeerror() -> None:
    """Passing a bare 'field=value' string (the natural CLI/doc mistake) where a
    Sequence[FilterRow] is expected raises a TypeError naming FilterRow with the
    correct shape, not a confusing AttributeError on 'str'."""
    with pytest.raises(TypeError) as exc:
        aegean.load("greek").query("word-prefix=KU")  # type: ignore[arg-type]
    msg = str(exc.value)
    assert "FilterRow" in msg
    assert "query filters must be a sequence" in msg
    assert "word-prefix" in msg  # constructive example
    assert "has no attribute" not in msg  # not the old misleading AttributeError


def test_query_run_query_direct_string_guarded() -> None:
    """run_query is the shared primitive; a string passed straight to it (not via
    Corpus.query) is guarded the same way."""
    from aegean.analysis.query import run_query

    with pytest.raises(TypeError) as exc:
        run_query(aegean.load("greek"), "word-prefix=KU")  # type: ignore[arg-type]
    assert "FilterRow" in str(exc.value)


def test_query_valid_field_still_runs() -> None:
    """The guard must not break a well-formed query: a valid field with a neutral
    blank value matches every inscription."""
    from aegean.analysis import FilterRow

    res = aegean.load("greek").query([FilterRow(field="word-prefix", value="")])
    assert len(res.inscriptions) > 0


def test_query_guard_field_list_matches_registry() -> None:
    """The message enumerates exactly the public FIELDS registry (the next-step
    pointer), so it can never drift from the real field set."""
    from aegean.analysis import FIELDS, FilterRow
    from aegean.analysis.query import run_query

    with pytest.raises(ValueError) as exc:
        run_query(aegean.load("greek"), [FilterRow(field="bogus", value="x")])
    msg = str(exc.value)
    for fld in FIELDS:
        assert fld in msg


# ── group C: data/__init__.py — download failure states the true cache state ──
# A cold-cache fetch that cannot connect (connection refused / DNS failure /
# offline) transfers no bytes, so there is nothing partial to resume. The
# message must not claim a kept partial download in that case, and must instead
# say the dataset is simply not in the local store and give an offline-
# appropriate next step. A transfer cut off AFTER it started keeps a resumable
# ``.part`` and keeps the original "partial kept; resume" wording.


def _groupC_refused_url() -> str:
    """A URL whose port is closed, so a connection is refused immediately.

    Bind a socket to an ephemeral port, read the port, then release it: nothing
    is listening there, so ``urlopen`` fails fast with a connection error (an
    ``OSError`` subclass) without any bytes crossing the wire.
    """
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    return f"http://127.0.0.1:{port}/x.json"


def test_groupC_offline_cold_cache_reports_empty_store_not_kept_partial(
    tmp_path, monkeypatch
) -> None:
    # The friend's scenario: offline / connection-refused on a cold cache,
    # reached through the public fetch() path. No bytes transfer, so no .part
    # exists; the message must NOT claim a kept/resumable partial download.
    import hashlib

    from aegean import data
    from aegean.data import DataNotAvailableError, DataSpec, fetch

    monkeypatch.setenv("PYAEGEAN_CACHE", str(tmp_path / "cache"))
    monkeypatch.setitem(
        data._REMOTE,
        "blobmiss",
        DataSpec(
            name="blobmiss",
            url=_groupC_refused_url(),
            license="x",
            sha256=hashlib.sha256(b"unused").hexdigest(),
        ),
    )
    with pytest.raises(DataNotAvailableError) as excinfo:
        fetch("blobmiss")

    msg = str(excinfo.value)
    # WHAT: the dataset is simply not present; no false "partial kept" claim.
    assert "partial download kept" not in msg
    assert "will resume it" not in msg
    assert "Nothing was downloaded" in msg
    assert "not in your local store" in msg
    # WHERE: names the dataset and the store directory it is absent from.
    assert "'blobmiss'" in msg
    assert str(data.cache_dir()) in msg
    # NEXT STEP: an offline-appropriate action and a real command to inspect.
    assert "network" in msg.lower()
    assert "aegean data list" in msg
    assert "Traceback" not in msg
    # And the disk state the message describes is the true one: no .part.
    assert not (data.cache_dir() / "blobmiss.part").exists()
    assert not (data.cache_dir() / "blobmiss.part.info").exists()


def test_groupC_truncated_transfer_keeps_resumable_partial_wording(tmp_path) -> None:
    # A transfer that got underway and was cut off leaves a resumable .part
    # (simulated: a pre-seeded .part + a refused retry keeps it). Here the
    # original "partial download kept; retrying will resume it" wording is
    # accurate and must be preserved.
    from aegean import data
    from aegean.data import DataNotAvailableError

    dest_part = tmp_path / "asset.bin.part"
    dest_part.write_bytes(b"partialbytes")  # 12 bytes already on disk

    with pytest.raises(DataNotAvailableError) as excinfo:
        data._download(_groupC_refused_url(), dest_part, "asset.bin")

    msg = str(excinfo.value)
    assert "partial download kept; retrying will resume it" in msg
    assert f"after {data._DOWNLOAD_ATTEMPTS} attempts" in msg
    assert "'asset.bin'" in msg
    assert "Traceback" not in msg
    # The bytes on disk survived, so the resume promise is true.
    assert dest_part.exists()
    assert dest_part.read_bytes() == b"partialbytes"


# ── group: neural-extra activation ordering (greek/joint.py, greek/neural_lemmatizer.py) ──
# use_neural_pipeline / use_neural_lemmatizer must check the [neural] extra BEFORE fetching
# the model bundle (~173 MB). On a fresh machine with no cached model and no extra, the old
# fetch-first ordering surfaced a network/fetch error telling the user to retry the download,
# never that they must `pip install 'pyaegean[neural]'` (the actual, cheap, local fix).

import builtins  # noqa: E402
import importlib  # noqa: E402
import sys  # noqa: E402
from collections.abc import Iterator  # noqa: E402
from contextlib import contextmanager  # noqa: E402

from aegean.greek import joint as _joint  # noqa: E402
from aegean.greek import neural_lemmatizer as _neural_lemmatizer  # noqa: E402


@contextmanager
def _neuralextra_block_imports(*names: str) -> Iterator[None]:
    """Make ``import <name>`` (and submodules) raise ModuleNotFoundError, as on a machine
    that never installed the ``[neural]`` extra — without uninstalling the real package."""
    blocked = set(names)
    real_import = builtins.__import__
    saved = {k: v for k, v in sys.modules.items() if k.split(".")[0] in blocked}
    for mod in list(saved):
        del sys.modules[mod]

    def fake_import(name, *args, **kwargs):  # type: ignore[no-untyped-def]
        if name.split(".")[0] in blocked:
            raise ModuleNotFoundError(f"No module named {name!r}", name=name)
        return real_import(name, *args, **kwargs)

    builtins.__import__ = fake_import
    try:
        yield
    finally:
        builtins.__import__ = real_import
        sys.modules.update(saved)


def test_neuralextra_pipeline_checks_extra_before_fetch(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """use_neural_pipeline raises the missing-extra error and never reaches fetch()."""
    fetch_calls: list[object] = []
    monkeypatch.setattr(_joint, "fetch", lambda *a, **k: fetch_calls.append((a, k)))

    with _neuralextra_block_imports("onnxruntime", "tokenizers"):
        with pytest.raises(_joint.NeuralPipelineNotLoadedError) as excinfo:
            _joint.use_neural_pipeline()

    msg = str(excinfo.value)
    assert "pip install 'pyaegean[neural]'" in msg
    assert "optional dependencies" in msg
    # The fix: the extra is probed BEFORE any download, so fetch is never called and the
    # user is never told to retry a ~173 MB transfer they cannot complete.
    assert fetch_calls == []
    assert _joint.active() is None


def test_neuralextra_lemmatizer_checks_extra_before_fetch(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """use_neural_lemmatizer raises the missing-extra error and never reaches fetch()."""
    fetch_calls: list[object] = []
    monkeypatch.setattr(
        _neural_lemmatizer, "fetch", lambda *a, **k: fetch_calls.append((a, k))
    )

    with _neuralextra_block_imports("onnxruntime", "tokenizers"):
        with pytest.raises(_neural_lemmatizer.NeuralLemmatizerNotLoadedError) as excinfo:
            _neural_lemmatizer.use_neural_lemmatizer()

    msg = str(excinfo.value)
    assert "pip install 'pyaegean[neural]'" in msg
    assert "optional dependencies" in msg
    assert fetch_calls == []
    assert _neural_lemmatizer.active() is None


def test_neuralextra_probe_passes_when_extra_present() -> None:
    """With the [neural] extra installed (the dev env), the probe is a no-op — it must not
    false-positive and block a real activation before the model even fetches. The assertion
    is that neither call raises. Skips where the extra genuinely is absent (the plain CI
    cells): there the probe raising is the correct behavior, covered by the tests above."""
    pytest.importorskip("onnxruntime")
    pytest.importorskip("tokenizers")
    _joint._require_neural_extra()
    _neural_lemmatizer._require_neural_extra()


def test_neuralextra_error_is_not_a_fetch_error(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """The raised type is the actionable NeuralPipeline/Lemmatizer error, not the
    DataNotAvailableError the old fetch-first ordering surfaced."""
    from aegean.data import DataNotAvailableError

    monkeypatch.setattr(_joint, "fetch", lambda *a, **k: pytest.fail("fetch reached"))
    monkeypatch.setattr(
        _neural_lemmatizer, "fetch", lambda *a, **k: pytest.fail("fetch reached")
    )
    with _neuralextra_block_imports("onnxruntime", "tokenizers"):
        with pytest.raises(_joint.NeuralPipelineNotLoadedError) as p:
            _joint.use_neural_pipeline()
        with pytest.raises(_neural_lemmatizer.NeuralLemmatizerNotLoadedError) as le:
            _neural_lemmatizer.use_neural_lemmatizer()
    assert not isinstance(p.value, DataNotAvailableError)
    assert not isinstance(le.value, DataNotAvailableError)


def test_neuralextra_block_helper_restores_modules() -> None:
    """The import-blocking helper fully restores onnxruntime/tokenizers afterward, so it
    cannot poison later tests in the same worker. Only meaningful where the modules are
    really installed (skips on the plain CI cells)."""
    pytest.importorskip("onnxruntime")
    pytest.importorskip("tokenizers")
    with _neuralextra_block_imports("onnxruntime", "tokenizers"):
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module("onnxruntime")
    assert importlib.import_module("onnxruntime") is not None
    assert importlib.import_module("tokenizers") is not None


# ── group db.py — from_sqlite corpus-db guard (the shared .db load primitive) ──
# Pointing any corpus-load path at a .db that is not a pyaegean corpus (a valid
# SQLite file with a foreign schema, or a plain file renamed .db) used to leak a
# raw sqlite3 traceback ("no such table: meta", "file is not a database") with no
# path context and no next step. The primitive now raises a clean ValueError that
# names the file and the way to build one, so every load path (Corpus.from_sql,
# aegean.db.from_sqlite, and the CLI info/show/load/stats/... via load_corpus)
# inherits the guard the sibling `aegean db search` already had. A locked database
# is reported distinctly (retry) rather than mislabelled as not-a-corpus.


def _dbmsg_foreign_sqlite(path) -> None:  # type: ignore[no-untyped-def]
    """Create a valid SQLite file with a non-pyaegean schema at ``path``."""
    import sqlite3

    conn = sqlite3.connect(str(path))
    conn.execute("CREATE TABLE notes(x)")
    conn.commit()
    conn.close()


def _dbmsg_real_corpus_db(path) -> None:  # type: ignore[no-untyped-def]
    """Write a tiny genuine pyaegean corpus database at ``path``."""
    from aegean.core.corpus import Corpus
    from aegean.core.model import Document, DocumentMeta, Token, TokenKind

    doc = Document(
        id="D1", script_id="lineara",
        tokens=[Token("KU-RO", TokenKind.WORD, ("KU", "RO"), line_no=0, position=0)],
        lines=[[0]], meta=DocumentMeta(site="Test"),
    )
    Corpus([doc], script_id="lineara").to_sql(path)


def test_dbmsg_from_sqlite_foreign_schema_is_clean_valueerror(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """A valid SQLite file that is not a pyaegean corpus raises a ValueError naming
    the file and the build step, not a raw ``no such table: meta`` sqlite3 error."""
    from aegean import db

    p = tmp_path / "other.db"
    _dbmsg_foreign_sqlite(p)
    with pytest.raises(ValueError) as exc:
        db.from_sqlite(p)
    msg = str(exc.value)
    # WHAT + WHERE: names the file and characterizes it correctly.
    assert str(p) in msg
    assert "is not a pyaegean corpus database" in msg
    # NEXT STEP: a real build command / API, no fabricated URL.
    assert "aegean db build" in msg
    assert "aegean.db.to_sqlite" in msg
    # The raw sqlite internal never leaks.
    assert "no such table" not in msg
    assert "Traceback" not in msg


def test_dbmsg_non_sqlite_file_is_clean_valueerror(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """A plain text file renamed .db (not a database at all) gets the same clean
    domain error, not a raw ``file is not a database`` sqlite3 error."""
    from aegean import db

    p = tmp_path / "notadb.db"
    p.write_text("this is not a database" * 3, encoding="utf-8")
    with pytest.raises(ValueError) as exc:
        db.from_sqlite(p)
    msg = str(exc.value)
    assert str(p) in msg
    assert "is not a pyaegean corpus database" in msg
    assert "aegean db build" in msg
    assert "file is not a database" not in msg  # the raw sqlite phrasing is gone
    assert "Traceback" not in msg


def test_dbmsg_from_sql_classmethod_inherits_guard(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """The guard lives in the shared primitive, so ``Corpus.from_sql`` inherits it."""
    from aegean.core.corpus import Corpus

    p = tmp_path / "foreign.db"
    _dbmsg_foreign_sqlite(p)
    with pytest.raises(ValueError) as exc:
        Corpus.from_sql(p)
    assert "is not a pyaegean corpus database" in str(exc.value)


def test_dbmsg_locked_database_reports_distinct_retry_message(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """A real corpus database held under an exclusive lock is reported as locked
    (retry), NOT mislabelled as 'not a pyaegean corpus database'."""
    import sqlite3

    from aegean import db

    p = tmp_path / "real.db"
    _dbmsg_real_corpus_db(p)
    holder = sqlite3.connect(str(p), isolation_level=None)
    holder.execute("BEGIN EXCLUSIVE")  # block any concurrent reader
    try:
        with pytest.raises(ValueError) as exc:
            db.from_sqlite(p)
        msg = str(exc.value)
        assert "is locked" in msg
        assert "retry" in msg
        assert str(p) in msg
        assert "not a pyaegean corpus database" not in msg  # distinct condition
        assert "Traceback" not in msg
    finally:
        holder.rollback()
        holder.close()


def test_dbmsg_valid_corpus_db_still_loads(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """The guard must not disturb a good database: it round-trips unchanged."""
    from aegean import db

    p = tmp_path / "good.db"
    _dbmsg_real_corpus_db(p)
    back = db.from_sqlite(p)
    assert len(back) == 1
    assert back.documents[0].id == "D1"
    assert back.documents[0].tokens[0].text == "KU-RO"


def test_dbmsg_newer_schema_message_survives_guard(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """A newer-schema database raises the specific 'upgrade pyaegean' ValueError
    (from _check_schema_version); the sqlite guard must not swallow or re-label it,
    since that error is a ValueError, not a sqlite3.Error."""
    import sqlite3

    from aegean import db

    p = tmp_path / "future.db"
    _dbmsg_real_corpus_db(p)
    conn = sqlite3.connect(str(p))
    conn.execute("UPDATE meta SET value = '99' WHERE key = 'schema_version'")
    conn.commit()
    conn.close()
    with pytest.raises(ValueError, match="schema version 99.*upgrade pyaegean"):
        db.from_sqlite(p)


def test_dbmsg_cli_info_on_foreign_db_is_one_clean_line(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """End-to-end: `aegean info <foreign.db>` exits 1 with one clean line carrying
    the build next-step, and no raw sqlite traceback."""
    from typer.testing import CliRunner

    from aegean.cli import _build_app

    p = tmp_path / "other.db"
    _dbmsg_foreign_sqlite(p)
    res = CliRunner().invoke(_build_app(), ["info", str(p)])
    assert res.exit_code == 1
    assert "is not a pyaegean corpus database" in res.output
    assert "aegean db build" in res.output
    assert "no such table" not in res.output
    assert "Traceback" not in res.output


# ── group onnxcorrupt: greek/joint.py + greek/neural_lemmatizer.py — corrupt model ──
# A truncated/corrupt cached model .onnx (an interrupted extract, disk corruption, or
# a legacy pre-0.29 extract cache that fetch() trusts without re-hashing) made
# onnxruntime raise a bare protobuf/parse traceback straight out of the library API
# (use_neural_pipeline / use_neural_lemmatizer). The InferenceSession construction is
# now wrapped — like the tokenizer.json load beside it — into the module's own
# *NotLoadedError with a WHAT + WHERE + re-fetch NEXT STEP. The raw onnxruntime error
# stays chained (__cause__) for debugging, but is not the type that escapes.


def _onnxcorrupt_extra_or_skip() -> None:
    """Skip unless the [neural] extra (onnxruntime/tokenizers/numpy) is installed — the
    _JointModel/_NeuralModel constructors import all three before building the session."""
    pytest.importorskip("onnxruntime")
    pytest.importorskip("tokenizers")
    pytest.importorskip("numpy")


def test_onnxcorrupt_joint_model_is_wrapped(
    tmp_path, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    _onnxcorrupt_extra_or_skip()
    from types import SimpleNamespace

    from aegean.greek import joint

    # A non-protobuf blob where the largest bundle file (model.onnx) should be — the
    # realistic truncation/corruption onnxruntime parses into an INVALID_PROTOBUF error.
    (tmp_path / "model.onnx").write_bytes(b"not a real onnx protobuf " * 64)
    # This test isolates the ONNX wrapper. Bundle-manifest corruption and missing files
    # are rejected earlier and have their own adversarial tests in test_neural_contract.
    monkeypatch.setattr(
        joint.ModelBundleManifest,
        "load",
        lambda *_args, **_kwargs: SimpleNamespace(
            output_heads=("upos", *(f"x{i}" for i in range(9)), "arc", "rel", "lemma"),
            preprocessing_version="grc-joint-v3",
        ),
    )
    with pytest.raises(joint.NeuralPipelineNotLoadedError) as exc:
        joint._JointModel(tmp_path)
    msg = str(exc.value)
    # WHAT + WHERE: names the corrupt file and characterizes the failure honestly.
    assert "could not load the joint model at" in msg
    assert "model.onnx" in msg
    assert "corrupt or incompletely downloaded" in msg
    # NEXT STEP: a real remediation command + the force re-fetch call (both verified real).
    assert "aegean data remove grc-joint" in msg
    assert "use_neural_pipeline(force=True)" in msg
    # The raw onnxruntime error is chained for debugging, not leaked as the raised type.
    assert exc.value.__cause__ is not None
    assert type(exc.value.__cause__).__module__.startswith("onnxruntime")
    assert "Traceback" not in msg


def test_onnxcorrupt_lemmatizer_model_is_wrapped(tmp_path) -> None:  # type: ignore[no-untyped-def]
    _onnxcorrupt_extra_or_skip()
    from aegean.greek import neural_lemmatizer as nl

    # The encoder session is built first, so a corrupt encoder_model.onnx is what is named.
    (tmp_path / "encoder_model.onnx").write_bytes(b"not a real onnx protobuf " * 64)
    with pytest.raises(nl.NeuralLemmatizerNotLoadedError) as exc:
        nl._NeuralModel(tmp_path)
    msg = str(exc.value)
    assert "could not load the neural lemmatizer model at" in msg
    assert "encoder_model.onnx" in msg  # WHERE: the exact failing file
    assert "corrupt or incompletely downloaded" in msg
    assert "aegean data remove grc-lemma-neural" in msg
    assert "use_neural_lemmatizer(force=True)" in msg
    assert exc.value.__cause__ is not None
    assert type(exc.value.__cause__).__module__.startswith("onnxruntime")
    assert "Traceback" not in msg


def test_onnxcorrupt_cli_activation_keeps_next_step(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """The CLI reduces an activation failure to one clean line — and the re-fetch NEXT
    STEP now survives that reduction (the wrapped message previously had none to carry)."""
    pytest.importorskip("typer")
    from typer.testing import CliRunner

    from aegean.cli import _build_app
    from aegean.greek.joint import NeuralPipelineNotLoadedError

    def _corrupt(*a: object, **k: object) -> None:
        raise NeuralPipelineNotLoadedError(
            "could not load the joint model at /c/grc-joint/model.onnx "
            "(onnxruntime: INVALID_PROTOBUF) — the cached model looks corrupt or "
            "incompletely downloaded. Re-fetch it: run `aegean data remove grc-joint` "
            "and retry, or call use_neural_pipeline(force=True)."
        )

    monkeypatch.setattr("aegean.greek.use_neural_pipeline", _corrupt)
    res = CliRunner().invoke(_build_app(), ["greek", "eval", "nt"])
    assert res.exit_code != 0
    out = res.output
    assert "could not activate the neural joint pipeline" in out
    assert "aegean data remove grc-joint" in out
    assert "use_neural_pipeline(force=True)" in out
    assert "Traceback" not in out


# ── group: io/epidoc.py — EpiDoc import error messages (WHERE + not-found + empty) ──
# read_epidoc/from_epidoc now (1) name the offending FILE when a malformed document sits
# inside a directory import (a directory has no "line 4"), (2) give the friendly
# "no such EpiDoc file" not-found message its text/csv siblings give instead of leaking a
# raw OSError [Errno 2], and (3) refuse a zero-document source loudly (WHY + a next step)
# rather than reporting a cheerful "wrote 0" success and returning an empty corpus.

_EPIDOC_GOOD = (
    '<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body><div type="edition">'
    "<ab><w>Alpha</w></ab></div></body></text></TEI>"
)
# a well-formed prologue with an undefined entity (&amps;) on line 4 — a common real defect.
_EPIDOC_BAD = (
    '<?xml version="1.0"?>\n'
    '<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body><div type="edition">\n'
    "<ab>\n<w>Alpha &amps; Beta</w>\n</ab></div></body></text></TEI>"
)
# valid XML that is not EpiDoc: no <div type="edition"> / <body> in the TEI namespace.
_EPIDOC_NOT = "<catalog><book>x</book></catalog>"


def _epidoc_cli(tmp_path, source, out_name="out.json"):  # type: ignore[no-untyped-def]
    """Run ``aegean import <source> -o <out> --epidoc`` and return the CliRunner result."""
    from typer.testing import CliRunner

    from aegean.cli import _build_app

    return CliRunner().invoke(
        _build_app(),
        ["import", str(source), "-o", str(tmp_path / out_name), "--epidoc"],
    )


# F1 — a malformed file inside a directory import names that file, not the directory.
def test_epidoc_dir_parse_error_names_offending_file(tmp_path) -> None:  # type: ignore[no-untyped-def]
    import xml.etree.ElementTree as ET

    from aegean.io import read_epidoc

    d = tmp_path / "mixed"
    d.mkdir()
    (d / "aaa_good.xml").write_text(_EPIDOC_GOOD, encoding="utf-8")
    (d / "zzz_bad.xml").write_text(_EPIDOC_BAD, encoding="utf-8")
    with pytest.raises(ET.ParseError) as exc:
        read_epidoc(d, script_id="greek")
    msg = str(exc.value)
    assert msg.startswith("zzz_bad.xml:")  # the offending file, not the directory
    assert "undefined entity" in msg  # the parser's detail is kept
    assert exc.value.position[0] == 4  # line/column position preserved for API consumers


def test_epidoc_dir_parse_error_cli_shows_file_no_traceback(tmp_path) -> None:  # type: ignore[no-untyped-def]
    d = tmp_path / "mixeddir"
    d.mkdir()
    (d / "aaa_good.xml").write_text(_EPIDOC_GOOD, encoding="utf-8")
    (d / "zzz_bad.xml").write_text(_EPIDOC_BAD, encoding="utf-8")
    res = _epidoc_cli(tmp_path, d)
    assert res.exit_code == 1, res.output
    assert "zzz_bad.xml" in res.output  # the broken inscription is named
    assert "not well-formed EpiDoc/TEI XML" in res.output
    assert "Traceback" not in res.output


def test_epidoc_single_file_parse_error_not_double_named(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """A single-file import already carries the path via the CLI frame; the reader must not
    redundantly prefix the basename, and the ParseError type/position stay intact."""
    import xml.etree.ElementTree as ET

    from aegean.io import read_epidoc

    f = tmp_path / "zzz_bad.xml"
    f.write_text(_EPIDOC_BAD, encoding="utf-8")
    with pytest.raises(ET.ParseError) as exc:
        read_epidoc(f, script_id="greek")
    # bare parser message (no "zzz_bad.xml:" prefix added by the reader) + position kept
    assert str(exc.value).startswith("undefined entity")
    assert exc.value.position[0] == 4


# F2 — a missing path gives the friendly not-found message, not a raw OSError [Errno 2].
def test_epidoc_missing_file_friendly_error() -> None:
    from aegean.io import from_epidoc

    with pytest.raises(FileNotFoundError) as exc:
        from_epidoc("nonexistent.xml")
    msg = str(exc.value)
    assert msg == "no such EpiDoc file: nonexistent.xml"
    assert "Errno" not in msg  # not the leaked OS errno string


def test_epidoc_missing_file_cli_matches_siblings(tmp_path) -> None:  # type: ignore[no-untyped-def]
    res = _epidoc_cli(tmp_path, tmp_path / "nonexistent.xml")
    assert res.exit_code == 1, res.output
    assert "no such EpiDoc file:" in res.output
    assert "nonexistent.xml" in res.output
    assert "Errno" not in res.output and "Traceback" not in res.output


# F3a — a valid but non-EpiDoc source refuses loudly with WHY + a next step.
def test_epidoc_non_epidoc_file_reports_why(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from aegean.io import from_epidoc

    f = tmp_path / "not_epidoc.xml"
    f.write_text(_EPIDOC_NOT, encoding="utf-8")
    with pytest.raises(ValueError) as exc:
        from_epidoc(f)
    msg = str(exc.value)
    assert "no EpiDoc editions found in not_epidoc.xml" in msg
    assert '<div type="edition">' in msg and "<body>" in msg  # names what was expected
    assert "Using-Critical-Editions" in msg  # a real wiki page, the next step


def test_epidoc_non_epidoc_file_cli_no_silent_success(tmp_path) -> None:  # type: ignore[no-untyped-def]
    f = tmp_path / "not_epidoc.xml"
    f.write_text(_EPIDOC_NOT, encoding="utf-8")
    res = _epidoc_cli(tmp_path, f, out_name="out_a.json")
    assert res.exit_code == 1, res.output
    assert "no EpiDoc editions found" in res.output
    assert "wrote 0 document" not in res.output  # no cheerful false-success line
    assert "Traceback" not in res.output


# F3b — a directory with no *.xml mirrors from_text_dir's empty-match error.
def test_epidoc_empty_dir_reports_no_xml(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from aegean.io import read_epidoc

    d = tmp_path / "emptydir"
    d.mkdir()
    with pytest.raises(FileNotFoundError) as exc:
        read_epidoc(d)
    assert "no *.xml files in" in str(exc.value)
    assert "emptydir" in str(exc.value)


def test_epidoc_empty_dir_cli_no_silent_success(tmp_path) -> None:  # type: ignore[no-untyped-def]
    d = tmp_path / "emptydir"
    d.mkdir()
    res = _epidoc_cli(tmp_path, d, out_name="out_b.json")
    assert res.exit_code == 1, res.output
    assert "no *.xml files in" in res.output
    assert "wrote 0 document" not in res.output
    assert "Traceback" not in res.output


# guard — the zero-document check fires only on a TOTAL miss; partial imports still succeed.
def test_epidoc_dir_partial_import_still_succeeds(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from aegean.io import from_epidoc

    d = tmp_path / "mixed_valid"
    d.mkdir()
    (d / "a_good.xml").write_text(_EPIDOC_GOOD, encoding="utf-8")
    (d / "b_notepidoc.xml").write_text(_EPIDOC_NOT, encoding="utf-8")
    corpus = from_epidoc(d, script_id="greek")
    assert len(corpus) == 1  # the one real edition loads; the non-EpiDoc file is skipped
