"""Stage D+ extra treebanks — Gorman and Pedalion (fetch-to-cache, pinned).

Two more AGDT-schema treebanks for the combined retrain (ROADMAP WP3 §3.6; the data mix
of the 2024 baseline, arXiv:2410.12055):

- **Gorman** (vgorman1/Greek-Dependency-Trees): hand-analyzed classical Greek prose,
  **CC BY-SA 4.0** (the repo's TREEBANK LICENSE). The ten Herodotus Book 1 files are
  **excluded at source**: PROIEL's ``hdt.xml`` — pyaegean's out-of-AGDT evaluation text —
  is the same work, so training on them would contaminate the PROIEL eval.
- **Pedalion** (perseids-publications/pedalion-trees): the KU Leuven reading-environment
  trees, **CC BY-SA 4.0** (TREEBANK_LICENSE).

Both use the AGDT ``<sentence><word form lemma postag head relation/>`` schema with
**artificial (ellipsis) nodes** (``artificial`` attribute / bracketed forms), which
``load_extra`` drops, re-resolving any head that pointed at one to its nearest real
ancestor. Sentence-level overlap exclusion against the UD folds and PROIEL happens in
build_full_dataset.py (--with-extras), not here.
"""

from __future__ import annotations

import unicodedata
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path

from aegean.data import cache_dir, download_file
from aegean.greek.treebank import _clean_lemma

__all__ = ["GORMAN_HERODOTUS_EXCLUDED", "fetch_extra", "load_extra"]

_GORMAN_COMMIT = "d823e96d253277bc1872b83ff5ac8c393a0f830a"
_PEDALION_COMMIT = "112c106b86b865ddde4be7e5f3e409d9c42689f9"

GORMAN_HERODOTUS_EXCLUDED: tuple[str, ...] = (
    "hdt 1 1-19 bu3 2019.xml",
    "hdt 1 100-119 bu3 2019.xml",
    "hdt 1 120-149 bu2 2019.xml",
    "hdt 1 150-169 bu3 2019.xml",
    "hdt 1 170-189 bu2 2019.xml",
    "hdt 1 190-216 bu2 2019.xml",
    "hdt 1 20-39 bu2 2019.xml",
    "hdt 1 40-59 bu2 2019.xml",
    "hdt 1 60-79 bu2 2019.xml",
    "hdt 1 80-99 bu5 2019.xml",
)

_GORMAN_FILES: tuple[str, ...] = (
    "Aeschines 1 1-50 bu1.xml",
    "Aeschines 1 101-150 bu1.xml",
    "Aeschines 1 151-196 bu1.xml",
    "Aeschines 1 51-100 bu1.xml",
    "Andocides_1.1-75_tree.xml",
    "Antiphon 5 bu2.xml",
    "Appian BC 1.0-1.4 bu1.xml",
    "Appian BC 1.11-14 bu1.xml",
    "Appian BC 1.5-7 bu1.xml",
    "Appian BC 1.8-10 bu1.xml",
    "Aristotle Politics book 1 bu1.xml",
    "Aristotle Politics book 2 bu2.xml",
    "Dem 59 Neaira tree.xml",
    "Demosthenes 1 bu1.xml",
    "Demosthenes_17_tree.xml",
    "Demosthenes_4_Phil1_tree.xml",
    "Isaeus_3_tree.xml",
    "Isocrates_18_tree.xml",
    "Lysias 1 bu1.xml",
    "Lysias 12 bu1.xml",
    "Lysias 14 bu1.xml",
    "Lysias 23 bu1.xml",
    "Plato_Crito_Travis_Kahl.xml",
    "Plut Alcib 1-17 bu1.xml",
    "Plut Alcib 18-39 bu1.xml",
    "Polybius 21_1-10 bu1.xml",
    "Polybius 21_11-20 bu1.xml",
    "Polybius 21_21-30 bu1.xml",
    "Polybius 21_31-47 bu1.xml",
    "Xen_Anab_book_1.1-5.xml",
    "Xen_Anab_book_1.6-9.xml",
    "Xen_Anab_book_3.xml",
    "Xenophon_Hiero.xml",
    "antiphon 1 bu2.xml",
    "antiphon 2 bu2.xml",
    "antiphon 6 bu2.xml",
    "athen12 1-9 2019.xml",
    "athen12 10-19 2019.xml",
    "athen12 20-29 2019.xml",
    "athen12 30-39 2019.xml",
    "athen12 40-49 2019.xml",
    "athen12 50-59 2019.xml",
    "athen12 60-69 2019.xml",
    "athen12 70-81 2019.xml",
    "athen13 1-9 2019.xml",
    "athen13 10-19 2019.xml",
    "athen13 20-29 2019.xml",
    "athen13 30-39 2019.xml",
    "athen13 40-49 2019.xml",
    "athen13 50-59 2019.xml",
    "athen13 60-69 2019.xml",
    "athen13 70-79 2019.xml",
    "athen13 80-89 2019.xml",
    "athen13 90-95 2019.xml",
    "dem 27 tree.xml",
    "dem 36 tree.xml",
    "dem 37 tree.xml",
    "dem 39 tree.xml",
    "dem 41 tree.xml",
    "dem 42 tree.xml",
    "dem 45 tree.xml",
    "dem 57 tree.xml",
    "dem 7 tree.xml",
    "dem_51_tree.xml",
    "dem_54_tree.xml",
    "demosthenes 18 1-50 bu2.xml",
    "demosthenes 18 101-150 bu2.xml",
    "demosthenes 18 151-200 bu2.xml",
    "demosthenes 18 201-275 bu1.xml",
    "demosthenes 18 276-324 bu1.xml",
    "demosthenes 18 51-100 bu1.xml",
    "demosthenes 46 tree.xml",
    "demosthenes 47 tree.xml",
    "demosthenes 49 tree.xml",
    "demosthenes 50 tree.xml",
    "demosthenes 52 tree.xml",
    "demosthenes 53 tree.xml",
    "diodsic 11_1-20 bu4.xml",
    "diodsic 11_81-92 bu1.xml",
    "diodsic11_21-40 bu2.xml",
    "diodsic11_41-60 bu1.xml",
    "diodsic11_61-80 bu1.xml",
    "dion hal 1.1-15 bu2.xml",
    "dion hal 1.16-30 bu1.xml",
    "dion hal 1.31-45 bu1.xml",
    "dion hal 1.46-60 bu1.xml",
    "dion hal 1.61-75 bu1.xml",
    "dion hal 1.76-90 bu1.xml",
    "josephus BJ 1.1-2 bu1.xml",
    "josephus BJ 1.11-15 bu1.xml",
    "josephus BJ 1.16-20 bu1.xml",
    "josephus BJ 1.21-25 bu1.xml",
    "josephus BJ 1.3-5 bu2.xml",
    "josephus BJ 1.6-10 bu1.xml",
    "lysias 13 bu1.xml",
    "lysias 15.xml",
    "lysias 19 bu1.xml",
    "plato apology.xml",
    "plut fortuna romanorum bu1.xml",
    "plutarch alex fort aut virt bu2.xml",
    "plutarch lycurgus 1-15 bu4.xml",
    "plutarch lycurgus 16-31 bu2.xml",
    "polybius 10_1-10 bu1.xml",
    "polybius 10_11-20 bu1.xml",
    "polybius 10_21-35 bu2.xml",
    "polybius 10_36-49 bu1.xml",
    "polybius 2_1-10 bu1.xml",
    "polybius 2_11-20 bu1.xml",
    "polybius 2_21-30 bu2.xml",
    "polybius 2_31-40 bu2.xml",
    "polybius 2_41-50 bu1.xml",
    "polybius 2_51-60 bu1.xml",
    "polybius 2_61-71 bu2.xml",
    "polybius 6 16-30 bu1.xml",
    "polybius 6 2-15 bu1.xml",
    "polybius 6 31-45 bu1.xml",
    "polybius 6 46-58 bu1.xml",
    "polybius 9_1-20 bu1.xml",
    "polybius 9_21-33 bu1.xml",
    "polybius 9_34-45 bu1.xml",
    "polybius1 1-9 2017.xml",
    "polybius1 10-19 2017.xml",
    "polybius1 20-29 2017.xml",
    "polybius1 30-39 2017.xml",
    "polybius1 40-49 2017.xml",
    "polybius1 50-59 2017.xml",
    "polybius1 60-69 2017.xml",
    "polybius1 70-79 2017.xml",
    "polybius1 80-88 2017.xml",
    "ps xen ath pol bu2.xml",
    "thuc 1 1-20 bu5.xml",
    "thuc 1 101-120 bu2.xml",
    "thuc 1 121-146 bu3.xml",
    "thuc 1 21-40 bu4.xml",
    "thuc 1 41-60 bu3.xml",
    "thuc 1 61-80 bu3.xml",
    "thuc 1 81-100 bu2.xml",
    "thuc 3.1-20 bu1.xml",
    "thuc 3.21-40 bu1.xml",
    "xen cyr 1_1-2 bu1.xml",
    "xen cyr 1_3-4 bu1.xml",
    "xen cyr 1_5 bu1.xml",
    "xen cyr 1_6 bu1.xml",
    "xen cyr 7.1-3 tree.xml",
    "xen cyr 7.4-5 tree.xml",
    "xen cyr 8.1-8.4 bu1.xml",
    "xen cyr 8.8 bu1.xml",
    "xen cyr 8_5-7 bu1.xml",
    "xen hell 1_1-4 bu2.xml",
    "xen hell 1_5-7 bu1.xml",
    "xen hell 2 bu1.xml",
    "xen hell 3 bu1.xml",
    "xen symp 1-2.xml",
    "xen symp 3-4.xml",
    "xen_cyr_2_1-2 tree.xml",
    "xen_cyr_2_3-4 tree.xml",
)

_PEDALION_FILES: tuple[str, ...] = (
    "achar.xml",
    "aeneas.xml",
    "aesop1.xml",
    "batracho.xml",
    "charb1.xml",
    "chilia-sentences.xml",
    "chion.xml",
    "crit.xml",
    "epictetus.xml",
    "epicurus1.xml",
    "euripides_medea.xml",
    "example-sentences.xml",
    "external_examplesentences.xml",
    "ez.xml",
    "genesis1.xml",
    "genesis2.xml",
    "genesis3.xml",
    "heron.xml",
    "iso.xml",
    "julian.xml",
    "longus.xml",
    "lucian_lis.xml",
    "lucian_prometheus.xml",
    "lucian_symposion.xml",
    "lysias_or24.xml",
    "menander_dyskolos.xml",
    "mimn.xml",
    "paean.xml",
    "papyri.xml",
    "phlegon.xml",
    "procopius.xml",
    "pseudo-lucian_themule.xml",
    "pseudoplato_cleitophon.xml",
    "sappho.xml",
    "semonides.xml",
    "sextus.xml",
    "theoc.xml",
    "theophr.xml",
    "thesmo.xml",
    "xenmem.xml",
)

_SOURCES = {
    "gorman": (
        f"https://raw.githubusercontent.com/vgorman1/Greek-Dependency-Trees/{_GORMAN_COMMIT}/xml%20versions/",
        _GORMAN_FILES,
    ),
    "pedalion": (
        f"https://raw.githubusercontent.com/perseids-publications/pedalion-trees/{_PEDALION_COMMIT}/public/xml/",
        _PEDALION_FILES,
    ),
}


def fetch_extra(source: str) -> list[Path]:
    """Fetch one extra treebank's files into the cache (CC BY-SA 4.0 — never bundled)."""
    base_url, files = _SOURCES[source]
    d = cache_dir() / "extra-treebanks" / source
    out = []
    for name in files:
        dest = d / name
        if not dest.exists():
            download_file(base_url + urllib.parse.quote(name), dest)
        out.append(dest)
    return out


def _is_artificial(w: ET.Element) -> bool:
    form = w.get("form") or ""
    return w.get("artificial") is not None or not form or form.startswith("[")


def load_extra(source: str, paths: list[Path] | None = None) -> list[dict]:
    """Parse one extra treebank into the build_full_dataset row-input shape.

    Artificial/ellipsis nodes are dropped; a real token whose head was artificial is
    re-attached to the nearest real ancestor (root if the chain dead-ends)."""
    rows: list[dict] = []
    for fp in paths if paths is not None else fetch_extra(source):
        for _ev, sent in ET.iterparse(str(fp), events=("end",)):
            if sent.tag.rsplit("}", 1)[-1] != "sentence":
                continue
            words = [w for w in sent if w.tag.rsplit("}", 1)[-1] == "word"]
            sid = sent.get("id") or ""
            if not sid or not words:
                sent.clear()
                continue
            by_id = {w.get("id"): w for w in words}

            def real_head(h: str, seen: int = 0) -> str:
                w = by_id.get(h)
                if w is None or seen > len(words):
                    return "0"
                if not _is_artificial(w):
                    return h
                return real_head(w.get("head") or "0", seen + 1)

            attrs = [
                {"id": w.get("id") or "", "head": real_head(w.get("head") or "0"),
                 "relation": w.get("relation") or "",
                 "form": unicodedata.normalize("NFC", w.get("form") or ""),
                 "lemma": _clean_lemma(w.get("lemma") or ""),
                 "xpos": (w.get("postag") or "").ljust(9, "-")[:9]}
                for w in words if not _is_artificial(w)
            ]
            if attrs:
                rows.append({"file": f"{source}:{fp.name}", "sid": sid, "attrs": attrs})
            sent.clear()
    return rows
