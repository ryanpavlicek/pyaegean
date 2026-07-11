"""Catalogued sign variants: what the sign inventories actually record (EXPLORATORY).

A deliberately narrow, honest surface. It groups signs that the *inventory's own data*
marks as variants sharing a base value, and nothing more:

- **Homophone-number variants** (Linear A, Linear B): the numbered series of the
  Bennett / GORILA transliteration, where a base romanization carries numbered siblings
  (``RA`` / ``RA2`` / ``RA3``, ``A`` / ``A2`` / ``A3``, ``PA`` / ``PA3``). These are
  *transliteration-convention* relatives: signs sharing a base romanization, numbered to
  disambiguate. In Linear B several are distinct sound values (``a2`` = /ha/, ``a3`` =
  /ai/), so the shared base is a naming relationship, not a claim they are the same sign.
- **Catalogue-suffix variants** (Cypro-Minoan): the CM sign list's letter suffixes
  (``CM012`` / ``CM012B``), a variant catalogued off a base number.

**The line this module draws, explicitly.** Palaeographic allography, the same sign
*drawn differently by different scribal hands*, is **not** in this data and is **not**
claimed here. The bundled inventories carry a label, a glyph, a codepoint, a phonetic
value where known, and a few flat attributes (``signClass``, ``sharedWithLinearB``, an
empty ``altGlyphs`` list); they do **not** carry per-hand glyph drawings or a
palaeographic variant apparatus. So :func:`variant_groups` reports only the
transliteration/catalogue variant relationships the labels encode. What it returns is a
map of how the catalogue *names* its signs, offered as a starting point for a
palaeographer, not a finding about letter-forms (EXPLORATORY).
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass

from ..core.script import get_script

__all__ = [
    "VariantGroup",
    "AllographReport",
    "variant_groups",
]

# A base romanization followed by a single homophone-disambiguation digit: PA3, RA2,
# A2, TURO2. The base is 1-4 letters; the star-numbered GORILA labels (*301) and the
# composite/ligature labels (SI+SE) never match (they carry * or +).
_NUMBERED = re.compile(r"^([A-Z]{1,4})([0-9])$")
# A Cypro-Minoan catalogue number with a trailing variant letter: CM012B, CM075B.
_CM_SUFFIX = re.compile(r"^(CM\d+)([A-Z])$")


@dataclass(frozen=True)
class VariantGroup:
    """One base value and the catalogued signs that share it (EXPLORATORY).

    ``base`` is the shared base label (e.g. ``"RA"`` or ``"CM012"``); ``members`` are the
    sign labels in the group, base first when the bare base sign exists, then the variants
    in label order. ``kind`` is ``"homophone-number"`` (a numbered transliteration series)
    or ``"catalog-suffix"`` (a CM letter-suffix variant). This is a naming/catalogue
    relationship, not a claim about how the signs were drawn."""

    base: str
    members: tuple[str, ...]
    kind: str
    script_id: str


@dataclass(frozen=True)
class AllographReport:
    """What variant structure a script's inventory records (EXPLORATORY).

    ``groups`` are the base-value variant groups (each with 2+ members), in base-label
    order. ``composite_signs`` are ligature / compound labels (``SI+SE``, ``VIR+KA``):
    the inventory carries them, but a compound of two values is not a variant of one base
    value, so they are reported separately and never folded into ``groups``.
    ``n_signs`` is the inventory size. ``notes`` is a short honest summary of what the
    data does and does not support for this script.

    The report describes the catalogue's naming, not palaeographic allography (which this
    data does not record); see the module docstring for the line drawn."""

    script_id: str
    groups: tuple[VariantGroup, ...]
    composite_signs: tuple[str, ...]
    n_signs: int
    notes: str

    def group_for(self, label: str) -> VariantGroup | None:
        """The variant group containing ``label``, or ``None`` if it is in no group."""
        for g in self.groups:
            if label in g.members:
                return g
        return None


def variant_groups(script_id: str) -> AllographReport:
    """Group a script's signs into catalogued variant sets, from the inventory's own data.

    Reads ``get_script(script_id).sign_inventory`` and groups signs sharing a base value
    by the label conventions the inventory uses: numbered homophone series (Linear A /
    Linear B) and Cypro-Minoan catalogue-letter suffixes. Only groups with 2+ members are
    returned; ligature/compound labels are listed under ``composite_signs``, not grouped.

    Returns an :class:`AllographReport`. Raises ``KeyError`` for an unregistered script id.

    **Caveat (EXPLORATORY).** These groupings come entirely from the transliteration and
    catalogue *naming* (a shared base romanization or catalogue number), which is not the
    same as palaeographic allography, the same sign drawn differently by different hands.
    That letter-form variation is not present in the bundled inventories and is not
    claimed. Use the report as a catalogue-structure starting point for a specialist, not
    as a palaeographic result."""
    inventory = get_script(script_id).sign_inventory
    labels = [s.label for s in inventory]
    label_set = set(labels)

    numbered: dict[str, list[str]] = defaultdict(list)
    suffixed: dict[str, list[str]] = defaultdict(list)
    composites: list[str] = []

    for label in labels:
        if "+" in label:
            composites.append(label)
            continue
        m = _NUMBERED.match(label)
        if m:
            numbered[m.group(1)].append(label)
            continue
        cm = _CM_SUFFIX.match(label)
        if cm:
            suffixed[cm.group(1)].append(label)

    groups: list[VariantGroup] = []

    def build(bases: dict[str, list[str]], kind: str) -> None:
        for base, variants in bases.items():
            members = ([base] if base in label_set else []) + sorted(variants)
            if len(members) >= 2:
                groups.append(
                    VariantGroup(
                        base=base,
                        members=tuple(members),
                        kind=kind,
                        script_id=script_id,
                    )
                )

    build(numbered, "homophone-number")
    build(suffixed, "catalog-suffix")
    groups.sort(key=lambda g: g.base)

    notes = _notes(script_id, groups, composites)
    return AllographReport(
        script_id=script_id,
        groups=tuple(groups),
        composite_signs=tuple(sorted(composites)),
        n_signs=len(labels),
        notes=notes,
    )


def _notes(
    script_id: str, groups: list[VariantGroup], composites: list[str]
) -> str:
    """A short honest summary of what the inventory supports for this script."""
    if not groups and not composites:
        return (
            f"The {script_id} inventory records no base-value variant markers "
            f"(no numbered homophone series, no catalogue-suffix variants); it carries "
            f"no palaeographic allography either. No variant groupings are supported."
        )
    parts: list[str] = []
    if groups:
        n_members = sum(len(g.members) for g in groups)
        kinds = sorted({g.kind for g in groups})
        parts.append(
            f"{len(groups)} base-value variant group(s) covering {n_members} signs "
            f"({', '.join(kinds)}), from the catalogue's naming conventions only"
        )
    if composites:
        parts.append(
            f"{len(composites)} ligature/compound sign(s) reported separately "
            f"(a compound of values is not a variant of one base value)"
        )
    return (
        "; ".join(parts)
        + ". Palaeographic allography (per-hand letter-forms) is not in this data "
        "and is not claimed."
    )
