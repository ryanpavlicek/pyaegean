"""Regression: the four EpiDoc "choice-corpus" builders resolve TEI ``<choice>`` to its
preferred (edited) member instead of concatenating both alternatives into one garbled token.

Before the fix, ``<choice><corr>χαῖρε</corr><sic>χαερε</sic></choice>`` emitted the fused token
``χαῖρεχαερε`` (and ``<reg>``/``<orig>`` likewise). I.Sicily / IIP / IOSPE / IGCyr now build with
``edition_tokens(..., choice_prefer=True)`` (matching EDH/DDbDP), so only the corrected/regularized
reading survives. Two levels of check:

* the shared extractor (``_epidoc.edition_tokens``) fuses with the flag off and picks the preferred
  member with it on (proving corr>sic, reg>orig, and that the flag is what matters); and
* each shipping builder, run end-to-end on an inline TEI fixture, emits the preferred reading and
  never the fused concatenation or the discarded member (proving each builder passes the flag).
"""

from __future__ import annotations

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

# aegean.core (zero-dep) is what the builders need; skip cleanly if the package is unavailable.
pytest.importorskip("aegean")

_REPO = Path(__file__).resolve().parent.parent
_SCRIPTS = _REPO / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

# A minimal EpiDoc TEI document that satisfies BOTH builder filters at once:
#   * ``<textLang mainLang="grc">``          (I.Sicily, IIP)
#   * primary ``<div type="edition" xml:lang="grc">``  (IOSPE, IGCyr)
# Its edition carries three editorial choices separated by single spaces:
#   corr>sic, reg>orig (the fusion cases), and expan>abbr (the abbreviation-expansion case).
_FIXTURE = (
    '<TEI xmlns="http://www.tei-c.org/ns/1.0">'
    "<teiHeader><profileDesc><langUsage>"
    '<language ident="grc">Greek</language>'
    "</langUsage></profileDesc>"
    '<fileDesc><sourceDesc><msDesc><msContents>'
    '<textLang mainLang="grc">Greek</textLang>'
    "</msContents></msDesc></sourceDesc></fileDesc>"
    "</teiHeader>"
    "<text><body>"
    '<div type="edition" subtype="primary" xml:lang="grc"><ab>'
    "<choice><corr>χαῖρε</corr><sic>χαερε</sic></choice> "
    "<choice><reg>τῇ</reg><orig>τῇι</orig></choice> "
    "<choice><expan>Λ<ex>ούκιος</ex></expan><abbr>Λ</abbr></choice>"
    "</ab></div>"
    "</body></text></TEI>"
)

# The correct (preferred-member) reading of the fixture edition.
_EXPECTED = ["χαῖρε", "τῇ", "Λούκιος"]
# Readings that must NEVER appear: the discarded members and the fused concatenations.
_FORBIDDEN = ["χαερε", "τῇι", "χαῖρεχαερε", "χαερεχαῖρε", "τῇτῇι", "τῇιτῇ"]


def _edition_words(choice_prefer: bool) -> list[str]:
    from _epidoc import edition_tokens, primary_edition

    root = ET.fromstring(_FIXTURE)
    edition = primary_edition(root)
    assert edition is not None
    return [w for line in edition_tokens(edition, choice_prefer=choice_prefer) for w, _ in line]


def test_shared_driver_off_fuses_choice_members() -> None:
    """With the flag OFF (the historical default), both members concatenate — the defect."""
    words = _edition_words(choice_prefer=False)
    assert "χαῖρεχαερε" in words
    assert "τῇτῇι" in words


def test_shared_driver_on_picks_preferred_member() -> None:
    """With ``choice_prefer=True`` only the corrected/regularized member survives; no fusion."""
    words = _edition_words(choice_prefer=True)
    assert words == _EXPECTED
    for bad in _FORBIDDEN:
        assert bad not in words


# (module, the subdir under the CLI ``source`` dir that the builder globs for ``*.xml``;
# "" means the builder globs the source dir itself, i.e. igcyr).
_BUILDERS = [
    ("build_isicily_corpus", "inscriptions"),
    ("build_iip_corpus", "epidoc-files"),
    ("build_iospe_corpus", "kiln/webapps/ROOT/content/xml/tei/inscriptions"),
    ("build_igcyr_corpus", ""),  # igcyr's CLI source IS the inscriptions dir
]


@pytest.mark.parametrize("module_name,subdir", _BUILDERS)
def test_builder_resolves_choice_end_to_end(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, module_name: str, subdir: str
) -> None:
    """Each shipping builder, run on the fixture, writes the preferred reading and never a fused
    or discarded member — i.e. every builder passes ``choice_prefer=True`` through to the corpus."""
    import importlib

    module = importlib.import_module(module_name)

    src_root = tmp_path / module_name
    insc_dir = src_root / subdir if subdir else src_root
    insc_dir.mkdir(parents=True, exist_ok=True)
    (insc_dir / "fixture001.xml").write_text(_FIXTURE, encoding="utf-8")

    out = tmp_path / f"{module_name}.json"
    monkeypatch.setattr(sys, "argv", [module_name, str(src_root), "-o", str(out)])
    rc = module.main()
    assert rc == 0
    assert out.exists()

    data = json.loads(out.read_text(encoding="utf-8"))
    docs = data["documents"]
    assert len(docs) == 1, f"{module_name}: expected 1 Greek doc, got {len(docs)}"
    words = [t["text"] for t in docs[0]["tokens"]]
    assert words == _EXPECTED, f"{module_name}: {words}"
    for bad in _FORBIDDEN:
        assert bad not in words, f"{module_name}: fused/discarded reading {bad!r} survived"
