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
from .inventory import greek_inventory
from .edh import load_edh
from .igcyr import load_igcyr
from .iip import load_iip
from .iospe import load_iospe
from .isicily import load_isicily
from .nt import load_nt
from .perseus import load_work

__all__ = [
    "Greek", "load_work", "load_nt", "load_isicily", "load_iip", "load_iospe", "load_igcyr",
    "load_edh",
]


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
