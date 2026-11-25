"""Load the Online Critical Pseudepigrapha Greek corpus (opt-in, fetched).

Extracts all Greek Second Temple and Old Testament Pseudepigrapha editions from the
*Online Critical Pseudepigrapha* (Ken M. Penner et al., pseudepigrapha.org; **CC BY 4.0**),
including *Psalms of Solomon*, *Testament of Solomon*, *Testaments of the Twelve Patriarchs*,
*1 Enoch*, *3–4 Baruch*, *Life of Adam and Eve*, *Testament of Job*, *Testament of Abraham*
(Recensions A & B), *Letter of Aristeas*, *Joseph and Aseneth*, *Sibylline Oracles*,
*3–4 Maccabees*, *Jubilees* (Greek), *Lives of the Prophets*, *Ezekiel the Tragedian*, and
Hellenistic Jewish fragments.
"""

from __future__ import annotations

from typing import Any


def load_pseudepigrapha() -> Any:
    """Load the Greek Old Testament Pseudepigrapha corpus as a `Corpus` (CC BY 4.0)."""
    from ...core.corpus import Corpus
    from ...data import fetch

    path = fetch("pseudepigrapha-corpus")
    return Corpus.from_json(path)


from ...core.corpus import register_loader  # noqa: E402

register_loader("pseudepigrapha", load_pseudepigrapha, fresh=True)
