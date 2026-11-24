"""CNTR Manuscript Encoding Specification (MES) parser and *nomina sacra* expander.

Parses electronic diplomatic transcriptions encoded in the Center for New
Testament Restoration's Manuscript Encoding Specification (MES):

- ``=`` *nomina sacra* contractions (e.g. ``=ιυ`` → ``Ἰησοῦ``, ``=χυ`` →
  ``Χριστοῦ``, ``=θσ`` → ``Θεός``, ``=πνα`` → ``Πνεῦμα``)
- ``¯`` superline nu-bar at line end (e.g. ``εγεννησε¯`` → ``εγεννησεν``)
- ``x{original}`` / ``{corrected}`` / ``a{...}`` / ``b{...}`` scribal hand edits
- ``\\<page>`` page breaks, ``|`` column breaks, ``/`` line breaks
- ``~`` / ``+`` supplied lacuna words, ``%`` damaged letters, ``^`` missing
  letters, ``&`` / ``*`` remnant markers, ``[`` / ``]`` questionable text
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

# Common Greek New Testament nomina sacra contractions (lowercase lunate sigma).
NOMINA_SACRA: dict[str, str] = {
    # Ἰησοῦς (Jesus)
    "ισ": "Ἰησοῦς",
    "ιησ": "Ἰησοῦς",
    "ιυ": "Ἰησοῦ",
    "ιηυ": "Ἰησοῦ",
    "ιη": "Ἰησοῦ",
    "ιν": "Ἰησοῦν",
    "ιην": "Ἰησοῦν",
    # Χριστός (Christ)
    "χσ": "Χριστός",
    "χρσ": "Χριστός",
    "χυ": "Χριστοῦ",
    "χρυ": "Χριστοῦ",
    "χω": "Χριστῷ",
    "χρω": "Χριστῷ",
    "χν": "Χριστόν",
    "χρν": "Χριστόν",
    # Θεός (God)
    "θσ": "Θεός",
    "θυ": "Θεοῦ",
    "θω": "Θεῷ",
    "θν": "Θεόν",
    "θε": "Θεέ",
    # Κύριος (Lord)
    "κσ": "Κύριος",
    "κυ": "Κυρίου",
    "κω": "Κυρίῳ",
    "κν": "Κύριον",
    "κε": "Κύριε",
    # Πνεῦμα (Spirit)
    "πνα": "Πνεῦμα",
    "πνσ": "Πνεύματος",
    "πνι": "Πνεύματι",
    "πνατα": "Πνεύματα",
    "πνατων": "Πνευμάτων",
    "πνασιν": "Πνεύμασιν",
    # Πατήρ (Father)
    "πηρ": "Πατήρ",
    "πρ": "Πατήρ",
    "πρσ": "Πατρός",
    "πρι": "Πατρί",
    "πρα": "Πατέρα",
    "πρεσ": "Πατέρες",
    "πρων": "Πατέρων",
    "πρασ": "Πατέρας",
    # Μήτηρ (Mother)
    "μηρ": "Μήτηρ",
    "μρ": "Μήτηρ",
    "μρσ": "Μητρός",
    "μρι": "Μητρί",
    "μρα": "Μητέρα",
    # Υἱός (Son)
    "υσ": "Υἱός",
    "υισ": "Υἱός",
    "υυ": "Υἱοῦ",
    "υιυ": "Υἱοῦ",
    "υω": "Υἱῷ",
    "υιω": "Υἱῷ",
    "υν": "Υἱόν",
    "υιν": "Υἱόν",
    "υε": "Υἱέ",
    # Δαυίδ (David)
    "δαδ": "Δαυίδ",
    "δδ": "Δαυίδ",
    # Ἄνθρωπος (Human)
    "ανοσ": "ἄνθρωπος",
    "ανου": "ἀνθρώπου",
    "ανω": "ἀνθρώπῳ",
    "ανον": "ἄνθρωπον",
    "ανε": "ἄνθρωπε",
    "ανοι": "ἄνθρωποι",
    "ανων": "ἀνθρώπων",
    "ανοισ": "ἀνθρώποις",
    "ανουσ": "ἀνθρώπους",
    # Οὐρανός (Heaven)
    "ουνοσ": "οὐρανός",
    "ουνου": "οὐρανοῦ",
    "ουνω": "οὐρανῷ",
    "ουνον": "οὐρανόν",
    "ουνοι": "οὐρανοί",
    "ουνων": "οὐρανῶν",
    "ουνοισ": "οὐρανοῖς",
    "ουνουσ": "οὐρανούς",
    # Ἰερουσαλήμ / Ἰσραήλ (Jerusalem / Israel)
    "ιλημ": "Ἰερουσαλήμ",
    "ιηλμ": "Ἰερουσαλήμ",
    "ισλ": "Ἰσραήλ",
    "ιηλ": "Ἰσραήλ",
    "ισρλ": "Ἰσραήλ",
    # Σταυρός / Σωτήρ (Cross / Savior)
    "σρσ": "σταυρός",
    "στσ": "σταυρός",
    "σρου": "σταυροῦ",
    "στου": "σταυροῦ",
    "σρω": "σταυρῷ",
    "στω": "σταυρῷ",
    "σρον": "σταυρόν",
    "στον": "σταυρόν",
    "σωρ": "Σωτήρ",
    "σηρ": "Σωτήρ",
    "σωρσ": "Σωτῆρος",
    "σωρα": "Σωτῆρα",
}

_PAGE_BREAK_RE = re.compile(r"\\[0-9A-Za-z]*")
# Match paired original + corrector edits: x{orig} {corr} or x{orig} a{corr}
_EDIT_PAIR_RE = re.compile(r"x\{([^}]*)\}\s*[ab]?\{([^}]*)\}")
# Match standalone edit block: x{...} or a{...} or b{...} or {...}
_EDIT_SINGLE_RE = re.compile(r"([xab])?\{([^}]*)\}")
_WS_RE = re.compile(r"\s+")
_FINAL_SIGMA_RE = re.compile(r"σ(?=\s|$|[.,;·:])")


@dataclass(frozen=True, slots=True)
class WitnessReading:
    """Parsed early-manuscript reading for one verse."""

    diplomatic: str
    readable: str
    nomina_sacra: tuple[tuple[str, str], ...]
    corrections: tuple[tuple[str, str], ...]
    has_lacuna: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "diplomatic": self.diplomatic,
            "readable": self.readable,
            "nomina_sacra": [{"abbreviated": a, "expanded": e} for a, e in self.nomina_sacra],
            "corrections": [{"original": o, "corrected": c} for o, c in self.corrections],
            "has_lacuna": self.has_lacuna,
        }


def expand_nomen_sacrum(token: str) -> str | None:
    """Expand a single CNTR *nomen sacrum* token (with or without leading ``=``)."""
    clean = token.lstrip("=").strip()
    clean = re.sub(r"[%^\[\]¯/\\|]", "", clean).lower().replace("ς", "σ")
    return NOMINA_SACRA.get(clean)


def _clean_fragment(frag: str) -> str:
    frag = _PAGE_BREAK_RE.sub("", frag)
    frag = frag.replace("|", "").replace("/", "").replace("_", " ")
    frag = frag.replace("¯", "ν")
    frag = re.sub(r"[%^*&\[\]⋄$]", "", frag)
    return _WS_RE.sub(" ", frag).strip()


def parse_mes(
    raw: str,
    *,
    hand: str = "original",
    expand_nomina_sacra: bool = True,
    include_supplied: bool = True,
) -> WitnessReading:
    """Parse a CNTR MES diplomatic verse string into a structured :class:`WitnessReading`.

    Parameters
    ----------
    raw:
        The raw CNTR MES string for a verse.
    hand:
        ``'original'`` (default, first hand ``x{...}``) or ``'corrected'``
        (later corrector ``{...}`` / ``a{...}`` / ``b{...}``).
    expand_nomina_sacra:
        When ``True`` (default), expands *nomina sacra* (``=ιυ`` → ``Ἰησοῦ``).
    include_supplied:
        When ``True`` (default), retains editorially supplied lacuna words
        (``~word`` / ``+word``); when ``False``, marks them as ``[…]``.
    """
    if hand not in ("original", "corrected"):
        raise ValueError(f"hand must be 'original' or 'corrected', got {hand!r}")

    has_lacuna = any(ch in raw for ch in ("~", "+", "^", "*", "&"))
    corrections: list[tuple[str, str]] = []

    def _pick_pair(m: re.Match[str]) -> str:
        orig, corr = m.group(1), m.group(2)
        corrections.append((_clean_fragment(orig), _clean_fragment(corr)))
        return orig if hand == "original" else corr

    text = _EDIT_PAIR_RE.sub(_pick_pair, raw)

    def _pick_single(m: re.Match[str]) -> str:
        prefix, body = m.group(1), m.group(2)
        if prefix == "x":
            corrections.append((_clean_fragment(body), ""))
            return body if hand == "original" else ""
        corrections.append(("", _clean_fragment(body)))
        return "" if hand == "original" else body

    text = _EDIT_SINGLE_RE.sub(_pick_single, text)

    # Remove page/column/line breaks and convert superline nu-bar to ν.
    text = _PAGE_BREAK_RE.sub("", text)
    text = text.replace("|", "").replace("/", "").replace("_", " ")
    text = text.replace("¯", "ν")
    text = re.sub(r"[%^*&\[\]⋄$]", "", text)

    nomina_found: list[tuple[str, str]] = []
    out_words: list[str] = []
    for raw_tok in text.split():
        supplied = raw_tok.startswith(("~", "+"))
        tok = raw_tok.lstrip("~+")
        if not tok:
            continue
        if supplied and not include_supplied:
            if not out_words or out_words[-1] != "[…]":
                out_words.append("[…]")
            continue
        if tok.startswith("="):
            abbrev = tok[1:]
            expanded = expand_nomen_sacrum(tok)
            if expanded is not None:
                nomina_found.append((f"={abbrev}", expanded))
                out_words.append(expanded if expand_nomina_sacra else f"={abbrev}")
            else:
                out_words.append(abbrev if expand_nomina_sacra else tok)
        else:
            out_words.append(_FINAL_SIGMA_RE.sub("ς", tok))

    readable = unicodedata.normalize("NFC", _WS_RE.sub(" ", " ".join(out_words)).strip())
    return WitnessReading(
        diplomatic=raw,
        readable=readable,
        nomina_sacra=tuple(nomina_found),
        corrections=tuple(corrections),
        has_lacuna=has_lacuna,
    )
