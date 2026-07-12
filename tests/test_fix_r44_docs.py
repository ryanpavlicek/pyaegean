"""Regression pins for the R44 docs/notice/manifest correctness fixes.

Each test verifies the corrected content is present and the defective content is
gone, or ties a documented claim to ground truth (the offline work catalogue, the
live ``_REMOTE`` registry, the CLI command tree), rather than only importing
without error.

Plain-module test: stdlib + the installed ``aegean`` package, reaching repo files
through ``__file__`` (no repo root on ``sys.path``).
"""

from __future__ import annotations

import json
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_NOTICE = _REPO / "NOTICE"
_MANIFEST = _REPO / "scripts" / "surface-manifest.json"
_DATA_PROV = _REPO / "wiki" / "Data-and-Provenance.md"
_WORKS = _REPO / "wiki" / "Greek-Works-and-Books.md"
_CLI = _REPO / "wiki" / "CLI.md"
_CHEAT = _REPO / "wiki" / "CLI-Cheatsheet.md"
_BENCH = _REPO / "wiki" / "Benchmarks.md"


# ── FIX 1: NOTICE ────────────────────────────────────────────────────────────
def test_notice_has_verse_fold_attribution() -> None:
    """The verse-fold asset gets its own attribution block, mirroring the
    PapyGreek/DBBE folds: source repo, the UNESP teaching project, the
    ShareAlike license, evaluation-only framing."""
    text = _NOTICE.read_text(encoding="utf-8")
    assert "verse-fold asset" in text, "no verse-fold attribution block in NOTICE"
    block = text.split("verse-fold asset", 1)[1][:700]
    assert "perseids-publications/unesp-trees" in block
    assert "Anise D'Orange Ferreira" in block
    assert "TREEBANK_LICENSE CC BY-SA 4.0" in block
    assert "evaluation only" in block


def test_notice_dbbe_author_initial_is_colin() -> None:
    """The DBBE block credits C. Swaelens (Colin), not the wrong 'W. Swaelens'."""
    text = _NOTICE.read_text(encoding="utf-8")
    assert "C. Swaelens" in text
    assert "W. Swaelens" not in text, "the wrong initial 'W. Swaelens' is still in NOTICE"


# ── FIX 2: MCP greek_work docstring ──────────────────────────────────────────
def test_mcp_greek_work_docstring_documents_milestones() -> None:
    """The tool's docstring now documents the margin-milestone refs and comma
    lists it actually supports (the defect was documenting only book/chapter/
    line-range)."""
    from aegean.mcp_server import greek_work

    doc = greek_work.__doc__ or ""
    assert "17a" in doc, "docstring omits the Stephanus sub-page milestone"
    assert "1447a10" in doc, "docstring omits the Bekker line milestone"
    assert "1447a" in doc, "docstring omits the whole Bekker page-column"
    assert "comma list" in doc, "docstring omits comma-list refs"


# ── FIX 3: surface-manifest.json notes ───────────────────────────────────────
def _capability(cid: str) -> dict:
    data = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    for cap in data["capabilities"]:
        if cap["id"] == cid:
            return cap
    raise AssertionError(f"no capability {cid!r} in the manifest")


def test_manifest_tui_notes_do_not_claim_console_reachability() -> None:
    """seriation/allographs are Python-API-only: the notes must not claim the
    command console reaches them, and must state the true reason."""
    for cid in ("seriation", "allographs"):
        note = _capability(cid)["surfaces"]["tui"]["note"]
        assert "reachable via the command console" not in note, (
            f"{cid}: TUI note still falsely claims console reachability"
        )
        assert "no CLI command" in note, f"{cid}: TUI note omits the true reason"
        assert "Python-API only" in note, f"{cid}: TUI note omits Python-API-only"


def test_manifest_note_premise_no_cli_command_exists() -> None:
    """The note's premise, verified against the live CLI: there is genuinely no
    ``analyze seriate`` / ``analyze allographs`` command, so the command console
    (which mirrors the CLI) cannot reach these tools."""
    from aegean.cli._analyze import analyze_app

    names = {
        (c.name or (c.callback.__name__ if c.callback else ""))
        for c in analyze_app.registered_commands
    }
    assert "seriate" not in names, "an 'analyze seriate' CLI command now exists — update the note"
    assert "allographs" not in names, (
        "an 'analyze allographs' CLI command now exists — update the note"
    )


# ── FIX 4: Data-and-Provenance completeness ──────────────────────────────────
def test_data_provenance_lists_every_remote_dataset() -> None:
    """Every registered remote dataset appears as a backticked token in the
    provenance page, so a new dataset cannot ship without a row (this guard is
    what the three missing folds — verse-fold, dbbe-lingann-fold,
    papygreek-fold-orig — were failing)."""
    from aegean.data import _REMOTE

    text = _DATA_PROV.read_text(encoding="utf-8")
    missing = sorted(name for name in _REMOTE if f"`{name}`" not in text)
    assert not missing, f"Data-and-Provenance.md has no row for: {missing}"


def test_data_provenance_added_the_three_folds() -> None:
    text = _DATA_PROV.read_text(encoding="utf-8")
    for name in ("`verse-fold`", "`dbbe-lingann-fold`", "`papygreek-fold-orig`"):
        assert name in text, f"{name} row missing from Data-and-Provenance.md"


# ── FIX 5: Bekker-milestone honesty ──────────────────────────────────────────
def test_poetics_id_is_ground_truth() -> None:
    """The corrected example id (tlg0086.tlg034) is the Poetics — the work whose
    Bekker page is 1447a — while tlg0086.tlg035 is the Politics, per the offline
    work catalogue."""
    from aegean import greek

    cat = {w["id"]: w["title"] for w in greek.catalog()}
    assert cat.get("tlg0086.tlg034") == "Poetics"
    assert cat.get("tlg0086.tlg035") == "Politics"


def test_works_page_uses_the_poetics_not_the_politics() -> None:
    text = _WORKS.read_text(encoding="utf-8")
    assert "tlg0086.tlg034" in text, "the Bekker example must cite the Poetics"
    assert "tlg0086.tlg035" not in text, "the Bekker example still cites the Politics"


def test_bekker_semantics_stated_on_every_surface() -> None:
    """The three wiki surfaces and both perseus.py docstrings state the true
    Bekker semantics: a page-*column*, the span to the next marked line, and the
    whole physical page as the comma list 1447a,1447b."""
    from aegean.scripts.greek import perseus

    wiki_pages = {
        "Greek-Works-and-Books.md": _WORKS.read_text(encoding="utf-8"),
        "CLI.md": _CLI.read_text(encoding="utf-8"),
        "CLI-Cheatsheet.md": _CHEAT.read_text(encoding="utf-8"),
    }
    for name, text in wiki_pages.items():
        assert "page-column" in text or "page-*column*" in text, (
            f"{name}: does not call 1447a a Bekker page-column"
        )
        assert "1447a,1447b" in text, f"{name}: omits the whole-page comma list"

    for docfn in (perseus.parse_tei_work, perseus.load_work):
        doc = docfn.__doc__ or ""
        assert "page-column" in doc, f"{docfn.__name__}: docstring omits page-column"
        assert "1447a,1447b" in doc, f"{docfn.__name__}: docstring omits the comma-list page"


# ── FIX 6: Benchmarks superlative removed ────────────────────────────────────
def test_benchmarks_drops_priority_superlative() -> None:
    text = _BENCH.read_text(encoding="utf-8")
    assert "first leakage-clean tragedy evaluation anywhere" not in text, (
        "the priority superlative is still in Benchmarks.md"
    )
    assert "no prior one is known to us" in text, "the measured-fact rewording is missing"
