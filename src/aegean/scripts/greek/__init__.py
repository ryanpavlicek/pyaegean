"""Greek script plugin.

Registers Greek as a `Script` and its bundled sample
corpus loader. The script's ``nlp`` capability exposes the `aegean.greek`
pipeline.
"""

from __future__ import annotations

from types import ModuleType

from ...core.model import SignInventory, Token
from ...core.script import Script, register
from . import loader  # noqa: F401 — registers the Corpus loader on import
from . import nt  # noqa: F401 — registers the New Testament corpus loader on import
from . import isicily  # noqa: F401 — registers the I.Sicily corpus loader on import
from . import iip  # noqa: F401 — registers the IIP corpus loader on import
from . import iospe  # noqa: F401 — registers the IOSPE corpus loader on import
from . import igcyr  # noqa: F401 — registers the IGCyr/GVCyr corpus loader on import
from . import edh  # noqa: F401 — registers the EDH corpus loader on import
from . import ddbdp  # noqa: F401 — registers the DDbDP corpus loader on import
from . import aphrodisias  # noqa: F401 — registers the IAph2007 corpus loader on import
from . import crete  # noqa: F401 — registers the Cretan Institutional Inscriptions loader
from . import apostolic_fathers  # noqa: F401 — registers the Open Apostolic Fathers loader
from . import pseudepigrapha  # noqa: F401 — registers the OCP Pseudepigrapha loader
from . import byzantine  # noqa: F401 — registers the Byzantine Vernacular Greek loader
from . import homer_scholia  # noqa: F401 — registers the Homer Multitext Scholia loader
from . import patrologia  # noqa: F401 — registers the Patrologia Graeca loader
from .inventory import greek_inventory
from typing import TYPE_CHECKING

from .aphrodisias import load_aphrodisias
from .apostolic_fathers import load_apostolic_fathers
from .byzantine import load_byzantine
from .crete import load_crete
from .ddbdp import ddbdp_db, load_ddbdp
from .edh import load_edh
from .homer_scholia import load_homer_scholia
from .igcyr import load_igcyr
from .iip import load_iip
from .iospe import load_iospe
from .isicily import load_isicily
from .nt import load_nt
from .patrologia import load_patrologia, patrologia_volumes
from .pseudepigrapha import load_pseudepigrapha

if TYPE_CHECKING:
    from .perseus import load_work

__all__ = [
    "Greek", "load_work", "load_nt", "load_isicily", "load_iip", "load_iospe", "load_igcyr",
    "load_edh", "load_ddbdp", "ddbdp_db", "load_aphrodisias", "load_crete",
    "load_apostolic_fathers", "load_pseudepigrapha", "load_byzantine",
    "load_homer_scholia", "load_patrologia", "patrologia_volumes",
]


def __getattr__(name: str) -> object:
    if name == "load_work":
        from .perseus import load_work as _load_work

        globals()["load_work"] = _load_work
        return _load_work
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
