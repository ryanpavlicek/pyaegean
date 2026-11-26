"""Greek script plugin.

Registers Greek as a `Script`, its bundled sample corpus loader, its specialized
loaders (``nt``, ``ddbdp``, ``patrologia``), and every hosted JSON Greek corpus
declared in :mod:`aegean.core.catalog`. The script's ``nlp`` capability exposes
the `aegean.greek` pipeline.
"""

from __future__ import annotations

from types import ModuleType
from typing import TYPE_CHECKING, Any

from ...core.catalog import CORPORA as _CORPORA
from ...core.catalog import make_json_corpus_loader as _make_json_corpus_loader
from ...core.corpus import register_loader as _register_loader
from ...core.model import SignInventory, Token
from ...core.script import Script, register
from . import ddbdp  # noqa: F401 — registers the DDbDP corpus loader on import
from . import loader  # noqa: F401 — registers the bundled Greek sample loader
from . import nt  # noqa: F401 — registers the New Testament corpus loader
from . import patrologia  # noqa: F401 — registers the Patrologia Graeca loader
from .ddbdp import ddbdp_db, load_ddbdp
from .inventory import greek_inventory
from .nt import load_nt
from .patrologia import load_patrologia, patrologia_volumes

if TYPE_CHECKING:
    from .perseus import load_work

# Specialized Greek corpora with custom loaders (bundled sample, NT, SQLite DDbDP,
# volume-scoped Patrologia Graeca). Every other hosted Greek corpus in
# aegean.core.catalog is a standard JSON/JSON.gz release asset registered below.
_CUSTOM_GREEK_CORPORA = frozenset({"greek", "nt", "ddbdp", "patrologia"})

_DYNAMIC_LOADERS: dict[str, Any] = {}
for _spec in _CORPORA:
    if (
        _spec.script_id == "greek"
        and not _spec.bundled
        and _spec.asset_name
        and _spec.id not in _CUSTOM_GREEK_CORPORA
    ):
        _fn_name = f"load_{_spec.id.replace('-', '_')}"
        _fn = _make_json_corpus_loader(
            _spec.asset_name,
            name=_fn_name,
            doc=f"Load {_spec.title} as a `Corpus` (opt-in, fetched).",
        )
        _register_loader(_spec.id, _fn, fresh=True)
        _DYNAMIC_LOADERS[_fn_name] = _fn

load_aphrodisias = _DYNAMIC_LOADERS["load_aphrodisias"]
load_apostolic_fathers = _DYNAMIC_LOADERS["load_apostolic_fathers"]
load_byzantine = _DYNAMIC_LOADERS["load_byzantine"]
load_crete = _DYNAMIC_LOADERS["load_crete"]
load_edh = _DYNAMIC_LOADERS["load_edh"]
load_homer_scholia = _DYNAMIC_LOADERS["load_homer_scholia"]
load_igcyr = _DYNAMIC_LOADERS["load_igcyr"]
load_iip = _DYNAMIC_LOADERS["load_iip"]
load_iospe = _DYNAMIC_LOADERS["load_iospe"]
load_isicily = _DYNAMIC_LOADERS["load_isicily"]
load_pseudepigrapha = _DYNAMIC_LOADERS["load_pseudepigrapha"]

__all__ = [
    "Greek",
    "load_work",
    "load_nt",
    "load_isicily",
    "load_iip",
    "load_iospe",
    "load_igcyr",
    "load_edh",
    "load_ddbdp",
    "ddbdp_db",
    "load_aphrodisias",
    "load_crete",
    "load_apostolic_fathers",
    "load_pseudepigrapha",
    "load_byzantine",
    "load_homer_scholia",
    "load_patrologia",
    "patrologia_volumes",
]


def __getattr__(name: str) -> object:
    if name == "load_work":
        from .perseus import load_work as _load_work

        globals()["load_work"] = _load_work
        return _load_work
    if name in _DYNAMIC_LOADERS:
        return _DYNAMIC_LOADERS[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


class Greek(Script):
    """Ancient Greek — the alphabetic script; the full NLP pipeline is on ``.nlp``."""

    id = "greek"
    name = "Ancient Greek"

    @property
    def sign_inventory(self) -> SignInventory:
        return greek_inventory().copy()  # independent copy: a caller's attrs edit must not leak

    def tokenize(self, raw: str) -> list[Token]:
        from ...greek.tokenize import tokenize as _tokenize

        return _tokenize(raw)

    @property
    def nlp(self) -> ModuleType:
        """The Greek NLP pipeline module (normalize/tokenize/syllabify/…)."""
        from ... import greek

        return greek


register(Greek())
