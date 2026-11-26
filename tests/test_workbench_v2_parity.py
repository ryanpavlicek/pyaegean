"""Cross-repo parity & bidirectional workbench bridge tests (linearaworkbench v2.0.0)."""

from __future__ import annotations

import json
import socketserver
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

import aegean
from aegean.analysis.lb_divergence import (
    build_lb_divergence,
    linear_a_sign_value_counts,
    parse_damos_frequencies,
)
from aegean.analysis.structure import LIBATION_WORDS, classify_structure
from aegean.cli._workbench import (
    _build_launch_url,
    _is_loopback_origin,
    _load_corpus_bytes,
    _make_handler,
)
from aegean.core.model import Document, DocumentMeta, ReadingStatus, TokenKind
from aegean.io import (
    BACKUP_KIND,
    WorkbenchBackup,
    from_workbench_export,
    load_workbench_backup,
    save_workbench_backup,
    to_workbench,
)
from aegean.scripts.lineara.commodities import is_lexical_word
from aegean.scripts.lineara.loader import classify
from aegean.scripts.lineara.phonetic import phonetic_map


def _doc(words: list[str]) -> Document:
    tokens = [classify(w, 0, i) for i, w in enumerate(words)]
    return Document(
        id="TEST1",
        script_id="lineara",
        tokens=tokens,
        lines=[list(range(len(tokens)))] if tokens else [],
        meta=DocumentMeta(site="Haghia Triada"),
    )


class TestLinearAParityFixes:
    def test_ni_inside_hyphenated_words_is_lexical(self) -> None:
        assert is_lexical_word("MA-NI") is True
        assert is_lexical_word("KU-NI-SU") is True
        assert is_lexical_word("NI-KA-RA") is True
        assert is_lexical_word("NI") is False
        assert is_lexical_word("GRA-PA") is False

        corpus = aegean.load("lineara")
        ni_words = {
            t.text
            for d in corpus
            for t in d.tokens
            if "-" in t.text and "NI" in t.text.split("-") and is_lexical_word(t.text)
        }
        assert len(ni_words) == 45

    def test_lb_divergence_bridges_labiovelars_and_affricates_and_counts_ni(self) -> None:
        la = linear_a_sign_value_counts([("QA-QE", 2), ("ZA-ZE-ZO", 1), ("MA-NI", 3)])
        assert la.by_value["ni"].count == 3
        lb = parse_damos_frequencies(
            {"documents": [{"content": ".1. qa-qe za-ze-zo ma-ni"}]}
        )
        rows = {r.value: r for r in build_lb_divergence(la, lb)}
        for val in ("kwa", "kwe", "dza", "dze", "dzo", "ma", "ni"):
            assert val in rows, f"missing bridged value {val}"

    def test_phonetic_map_has_we_and_wo(self) -> None:
        pmap = phonetic_map()
        assert pmap["WE"] == "we"
        assert pmap["WO"] == "wo"
        assert len(pmap) == 52

    def test_structure_recognizes_all_14_libation_words_fractions_and_totals(self) -> None:
        assert len(LIBATION_WORDS) == 14
        for word in ("TA-NA-TE", "I-DA-MA-TE", "SI-RU-TE", "U-NA-KA-NA-SI", "I-PI-NA-MA"):
            assert word in LIBATION_WORDS
            assert classify_structure(_doc([word, "A-DI"])) == "libation"
        # Fraction-only numerals + >2 multi-sign words -> accounting
        assert classify_structure(_doc(["A-B", "C-D", "E-F", "³⁄₄"])) == "accounting"
        assert classify_structure(_doc(["A-B", "C-D", "E-F", "≈ ¹⁄₆"])) == "accounting"
        # KU-RA and PO-TO-KU-RO trigger accounting
        assert classify_structure(_doc(["DA-RO", "KU-RA"])) == "accounting"
        assert classify_structure(_doc(["DA-RO", "PO-TO-KU-RO"])) == "accounting"


class TestLosslessWorkbenchIOAndBackup:
    def test_from_workbench_export_restores_lineara_apparatus_inventory_and_rights(self) -> None:
        payload = {
            "_meta": {"tool": "Linear A Research Workbench", "schemaVersion": 1},
            "inscriptions": [
                {
                    "id": "HT999",
                    "site": "Haghia Triada",
                    "period": "LMIB",
                    "lines": [["KU-RO", "𐄁", "VIN", "𐝫", "VIR+[?]", "³⁄₄"]],
                    "images": {
                        "facsimile": ["images/HT999-Facsimile.jpg"],
                        "photograph": [],
                        "rights": "EFA",
                        "rightsUrl": "https://cefael.efa.gr/",
                    },
                }
            ],
        }
        corpus = from_workbench_export(payload)
        assert corpus.sign_inventory is not None
        assert corpus.sign_inventory.by_label("KU") is not None
        doc = corpus.get("HT999")
        assert doc is not None
        kinds = [t.kind for t in doc.tokens]
        statuses = [t.status for t in doc.tokens]
        assert kinds == [
            TokenKind.WORD,
            TokenKind.SEPARATOR,
            TokenKind.LOGOGRAM,
            TokenKind.UNKNOWN,
            TokenKind.LOGOGRAM,
            TokenKind.NUMERAL,
        ]
        assert statuses == [
            ReadingStatus.CERTAIN,
            ReadingStatus.CERTAIN,
            ReadingStatus.CERTAIN,
            ReadingStatus.LOST,
            ReadingStatus.UNCLEAR,
            ReadingStatus.CERTAIN,
        ]
        assert "imageRights: EFA" in doc.meta.notes
        assert "imageRightsURL: https://cefael.efa.gr/" in doc.meta.notes

        # Round-trip back through to_workbench preserves imageRights/imageRightsURL
        emitted = to_workbench(corpus)
        assert emitted[0]["imageRights"] == "EFA"
        assert emitted[0]["imageRightsURL"] == "https://cefael.efa.gr/"

    def test_backup_round_trip_and_query_conversion(self, tmp_path: Path) -> None:
        backup = WorkbenchBackup(
            annotations=[
                {"kind": "word", "value": "KU-RO", "meaning": "total", "confidence": "high"}
            ],
            collections=[{"id": "c1", "name": "HT ledgers", "items": ["HT13"]}],
            notes=[{"id": "n1", "title": "HT13", "body": "Checks KU-RO sum."}],
            saved_queries=[
                {
                    "name": "HT tablets",
                    "rows": [
                        {"rid": "1", "field": "site-is", "value": "Haghia Triada", "connector": "and"}
                    ],
                }
            ],
            tablet_categories={"HT13": "accounting"},
            extra={"settings": {"theme": "light"}, "lb-sign-frequencies": {"totalSigns": 100}},
        )
        out = tmp_path / "workspace.json"
        written = save_workbench_backup(backup, out)
        assert written["kind"] == BACKUP_KIND
        loaded = load_workbench_backup(out)
        assert loaded.annotations == backup.annotations
        assert loaded.collections == backup.collections
        assert loaded.notes == backup.notes
        assert loaded.tablet_categories == {"HT13": "accounting"}
        assert loaded.extra["settings"] == {"theme": "light"}

        rows = loaded.to_filter_rows("HT tablets")
        assert len(rows) == 1
        assert rows[0].field == "site-is"
        assert rows[0].value == "Haghia Triada"
        corpus = aegean.load("lineara")
        res = corpus.query(rows)
        assert len(res.inscriptions) > 100

    def test_backup_rejects_invalid_and_strips_prototype_keys(self) -> None:
        with pytest.raises(ValueError, match="kind"):
            load_workbench_backup({"kind": "wrong", "version": 1, "data": {}})
        with pytest.raises(ValueError, match="version"):
            load_workbench_backup({"kind": BACKUP_KIND, "version": 99, "data": {}})
        b = load_workbench_backup(
            {
                "kind": BACKUP_KIND,
                "version": 1,
                "data": {"__proto__": {"polluted": True}, "constructor": "bad", "ok": 1},
            }
        )
        assert "__proto__" not in b.extra
        assert "constructor" not in b.extra
        assert b.extra["ok"] == 1


class TestWorkbenchServerBridge:
    def test_launch_url_builder(self) -> None:
        assert _build_launch_url(8000) == "http://localhost:8000/"
        url = _build_launch_url(
            8123,
            has_corpus=True,
            has_damos=True,
            has_state=True,
            module="signref",
            site="Haghia Triada",
            period="LMIB",
        )
        assert url.startswith("http://localhost:8123/?")
        assert "corpus=%2Fapi%2Flocal%2Fcorpus.json" in url
        assert "damos=%2Fapi%2Flocal%2Fdamos-corpus.json" in url
        assert "localState=1" in url
        assert "#/m/signref?site=Haghia+Triada&period=LMIB" in url

        doc_url = _build_launch_url(8000, doc="HT13", module="arith", site="Haghia Triada")
        assert doc_url.endswith("#/i/HT13?m=arith&site=Haghia+Triada")

    def test_loopback_origin_guard(self) -> None:
        assert _is_loopback_origin(None) is True
        assert _is_loopback_origin("http://localhost:8000") is True
        assert _is_loopback_origin("http://127.0.0.1:5173") is True
        assert _is_loopback_origin("https://evil.example") is False
        assert _is_loopback_origin("http://127.0.0.1.evil.example") is False

    def test_live_local_api_endpoints(self, tmp_path: Path) -> None:
        static_dir = tmp_path / "dist"
        static_dir.mkdir()
        (static_dir / "index.html").write_text("<html>ok</html>", encoding="utf-8")
        damos_file = tmp_path / "damos-corpus.json"
        damos_file.write_text('{"documents": []}', encoding="utf-8")
        state_path = tmp_path / "workspace.json"
        corpus_bytes = _load_corpus_bytes("lineara")

        handler = _make_handler(
            static_dir,
            None,
            corpus_bytes=corpus_bytes,
            damos_path=damos_file,
            state_path=state_path,
        )
        server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), handler)
        server.daemon_threads = True
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f"http://127.0.0.1:{port}"
            # 1. Mounted custom corpus
            with urllib.request.urlopen(f"{base}/api/local/corpus.json") as r:
                assert r.status == 200
                assert r.headers.get("Cache-Control") == "no-store"
                records = json.loads(r.read().decode("utf-8"))
                assert len(records) == 1721

            # 2. Mounted DAMOS file
            with urllib.request.urlopen(f"{base}/api/local/damos-corpus.json") as r:
                assert r.status == 200
                assert json.loads(r.read().decode("utf-8")) == {"documents": []}

            # 3. Backup GET returns 204 before first PUT
            with urllib.request.urlopen(f"{base}/api/local/backup") as r:
                assert r.status == 204

            # 4. Cross-origin PUT is rejected with 403
            backup_body = json.dumps(
                WorkbenchBackup(
                    notes=[{"id": "n1", "title": "Loopback", "body": "Saved via API"}]
                ).to_dict()
            ).encode("utf-8")
            bad_req = urllib.request.Request(
                f"{base}/api/local/backup",
                data=backup_body,
                method="PUT",
                headers={
                    "Content-Type": "application/json",
                    "Origin": "https://evil.example",
                },
            )
            with pytest.raises(urllib.error.HTTPError) as exc:
                urllib.request.urlopen(bad_req)
            assert exc.value.code == 403

            # 5. Valid loopback PUT persists atomically and GET reads it back
            good_req = urllib.request.Request(
                f"{base}/api/local/backup",
                data=backup_body,
                method="PUT",
                headers={
                    "Content-Type": "application/json",
                    "Origin": f"http://localhost:{port}",
                },
            )
            with urllib.request.urlopen(good_req) as r:
                assert r.status == 200
                assert json.loads(r.read().decode("utf-8")) == {"ok": True}

            with urllib.request.urlopen(f"{base}/api/local/backup") as r:
                assert r.status == 200
                saved = load_workbench_backup(json.loads(r.read().decode("utf-8")))
                assert saved.notes[0]["title"] == "Loopback"
            assert load_workbench_backup(state_path).notes[0]["title"] == "Loopback"
        finally:
            server.shutdown()
            server.server_close()

    def test_new_cli_options_wired(self) -> None:
        import click
        import typer

        from aegean.cli import _build_app

        app = _build_app()
        group = typer.main.get_command(app)
        cmd = group.get_command(click.Context(group), "workbench")
        assert cmd is not None
        opts = {opt for param in cmd.params for opt in param.opts}
        for flag in (
            "--port",
            "--corpus",
            "--site",
            "--period",
            "--scribe",
            "--support",
            "--module",
            "--doc",
            "--damos",
            "--state",
            "--dir",
        ):
            assert flag in opts, f"missing CLI flag {flag}"
