"""Build the bundled Cypriot IG XV 1 corpus snapshot from the BBAW telota IG edition.

Repo-only (NOT shipped in the wheel — it is a build tool). Fetches the Cypriot syllabic
inscriptions of *Inscriptiones Graecae* XV 1 from the telota EpiDoc API (CC-BY 4.0), parses
each into the script-agnostic corpus record format, and writes a HOSTED snapshot to
``src/aegean/data/bundled/cypriot/ig_inscriptions.json`` so the package never depends on the
source staying online. Re-run to refresh.

    py -3.12 scripts/build_cypriot_ig.py [--max N]

Attribution (CC-BY 4.0): Inscriptiones Graecae, Berlin-Brandenburg Academy of Sciences and
Humanities (telota.bbaw.de/ig). Each record keeps its own source URL for the required link-back.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

API = "https://telota.bbaw.de/ig/api/xml/"
OUT = Path(__file__).resolve().parents[1] / "src/aegean/data/bundled/cypriot/ig_inscriptions.json"
_GREEK = tuple(range(0x0370, 0x0400)) + tuple(range(0x1F00, 0x2000))


def _is_greek(s: str) -> bool:
    return any(ord(c) in _GREEK for c in s)


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _first(root: ET.Element, name: str) -> ET.Element | None:
    return next((e for e in root.iter() if _local(e.tag) == name), None)


def _flat(elem: ET.Element) -> str:
    """Full text content, turning <lb/> into newlines and reading-direction marks into spaces."""
    out: list[str] = []

    def rec(e: ET.Element) -> None:
        if _local(e.tag) == "lb":
            out.append("\n")
        if e.text:
            out.append(e.text)
        for c in e:
            rec(c)
            if c.tail:
                out.append(c.tail)

    rec(elem)
    return "".join(out).replace("←", " ").replace("→", " ")


def fetch(n: int) -> str | None:
    url = API + urllib.parse.quote(f"IG XV 1, {n}")
    req = urllib.request.Request(url, headers={"User-Agent": "pyaegean-build/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310 - fixed trusted host
            return r.read().decode("utf-8") if r.status == 200 else None
    except Exception:  # noqa: BLE001
        return None


def parse(xml: str, n: int) -> dict | None:
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return None
    title_el = _first(root, "title")
    title = (title_el.text or "").strip() if title_el is not None else ""
    place_el, date_el, support_el = _first(root, "origPlace"), _first(root, "origDate"), _first(root, "support")
    place = "".join(place_el.itertext()).strip() if place_el is not None else ""
    date = "".join(date_el.itertext()).strip() if date_el is not None else ""
    support = " ".join("".join(support_el.itertext()).split()) if support_el is not None else ""

    # edition: the <div type="edition"> (fall back to first <ab>)
    edition = next((d for d in root.iter() if _local(d.tag) == "div" and d.get("type") == "edition"), None)
    if edition is None:
        edition = _first(root, "ab")
    apparatus = {"|", "]", "[", "‒", "—", "·", "/", "//", "("}
    syllabic_lines: list[list[str]] = []
    greek_bits: list[str] = []
    transcription = ""
    if edition is not None:
        transcription = " ".join(_flat(edition).split())
        for raw_line in _flat(edition).split("\n"):
            units = raw_line.split()
            greek_bits += [u for u in units if _is_greek(u)]
            syll = [u for u in units if u and not _is_greek(u) and u not in apparatus]
            if syll:
                syllabic_lines.append(syll)

    # translation: prefer an English div, else the substantive (non-"[eteokyprisch]") one
    tdivs = [d for d in root.iter() if _local(d.tag) == "div" and d.get("type") == "translation"]
    def _lang(d: ET.Element) -> str:
        return d.get("{http://www.w3.org/XML/1998/namespace}lang", "")
    cands = [(_lang(d), " ".join(_flat(d).split())) for d in tdivs]
    cands = [(lg, t) for lg, t in cands if t.strip("[] ")]
    translation = ""
    if cands:
        en = [t for lg, t in cands if lg.startswith("en")]
        translation = en[0] if en else max((t for _lg, t in cands), key=len)

    words = [w for line in syllabic_lines for w in line]
    if not words and not transcription:
        return None  # nothing usable
    rec: dict = {
        "id": f"IG XV 1, {n}",
        "site": place,
        "support": support,
        "context": date,
        "name": title,
        "lines": syllabic_lines,
        "transcription": transcription,
        "source_url": f"https://telota.bbaw.de/ig/digitale-edition/inschrift/IG XV 1, {n}",
    }
    if translation and translation.strip("[] "):
        rec["translations"] = [translation]
    if greek_bits:
        rec["greek"] = " ".join(greek_bits)
    return rec


def main() -> int:
    cap = 300  # the IG XV 1 numbering has gaps; probe the whole range rather than stop on a run of gaps
    if "--max" in sys.argv:
        cap = int(sys.argv[sys.argv.index("--max") + 1])
    records: list[dict] = []
    for n in range(1, cap + 1):
        xml = fetch(n)
        if xml is not None:
            rec = parse(xml, n)
            if rec is not None:
                records.append(rec)
        if n % 25 == 0:
            print(f"  …{n} probed, {len(records)} parsed", flush=True)
        time.sleep(0.15)
    OUT.write_text(json.dumps(records, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"wrote {len(records)} IG XV 1 Cypriot inscriptions → {OUT}")
    print(f"  with translation: {sum('translations' in r for r in records)}; "
          f"with Greek (bilingual): {sum('greek' in r for r in records)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
