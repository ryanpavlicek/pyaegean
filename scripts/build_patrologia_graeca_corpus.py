"""Build the Calfa–GREgORI Patrologia Graeca corpus (``patrologia-graeca-corpus.json.gz``).

Packages all 33 digitized Migne *Patrologia Graeca* volumes (~5.5 million Greek words) from
the **CGPG** (Calfa GREgORI Patrologia Graeca) project (``calfa-co/Patrologia-Graeca``,
Vidal-Gorène & Kindt, LREC 2026; **CC BY 4.0**) into a compact, volume-indexed gzipped JSON
bundle so single volumes (including the 9 major biblical commentary volumes by Cyril of
Alexandria, Procopius of Gaza, Photius, Oecumenius, and Theophylact of Bulgaria) load in
under a second while the full 33-volume corpus remains loadable via ``aegean.load("patrologia")``.

Note on provenance: CGPG texts are automated polytonic OCR of 19th-century Migne *Patrologia
Graeca* prints (Vidal-Gorène & Kindt 2026), not hand-proofread critical editions. This is
recorded in ``_meta["edition_fidelity"] = "ocr"`` and in corpus provenance.

Usage:
    python scripts/build_patrologia_graeca_corpus.py <path-to-Patrologia-Graeca> -o patrologia-graeca-corpus.json.gz
"""

from __future__ import annotations

import argparse
import gzip
import json
import re
import unicodedata
from pathlib import Path
from typing import Any

REPO = "calfa-co/Patrologia-Graeca"
COMMIT = "5895ab908dd4cac5ee06cfc0e36f2ef77723e143"

_MARKER_RE = re.compile(r"^\$0=\S+\s+\$8=(\S+)\s+\$9=(\S+)\s*$")

# (vol_id, pg_num, period, author, title, biblical_books)
VOLUMES: tuple[tuple[str, str, str, str, str, tuple[str, ...]], ...] = (
    ("PG003", "3", "Pre-Nicaean / 5th–6th c.", "Pseudo-Dionysius the Areopagite", "Opera Omnia (vol. 1)", ()),
    ("PG005", "5", "2nd century", "Ignatius, Polycarp, Melito et al.", "Apostolic & 2nd-Century Fathers", ()),
    ("PG006", "6", "2nd century", "Justin Martyr, Tatian, Athenagoras, Theophilus", "2nd-Century Apologists", ()),
    ("PG008", "8", "2nd–3rd century", "Clement of Alexandria", "Protrepticus, Paedagogus, Stromata (vol. 1)", ()),
    ("PG009", "9", "2nd–3rd century", "Clement of Alexandria", "Stromata (cont.), Quis dives salvetur, Excerpta, Eclogae (vol. 2)", ()),
    ("PG016_3", "16.3", "3rd century", "Origen & Hippolytus", "Origen Hexapla (cont.); Hippolytus Philosophumena", ()),
    ("PG021", "21", "4th century", "Eusebius of Caesarea", "Praeparatio Evangelica (vol. 3)", ()),
    ("PG042", "42", "4th century", "Epiphanius of Salamis", "Panarion (cont.), Expositio fidei, Anacephalaeosis (vol. 2)", ()),
    ("PG067", "67", "5th century", "Socrates Scholasticus & Sozomen", "Historia Ecclesiastica", ()),
    ("PG071", "71", "5th century", "Cyril of Alexandria", "Commentaries on the Twelve Minor Prophets (vol. 4)", ("Hos", "Joel", "Amos", "Obad", "Jonah", "Mic", "Nah", "Hab", "Zeph", "Hag", "Zech", "Mal")),
    ("PG073", "73", "5th century", "Cyril of Alexandria", "Commentary on the Gospel of John (vol. 6)", ("John",)),
    ("PG087_1", "87.1", "6th century", "Procopius of Gaza", "Old Testament Commentaries (Octateuch & Catenae, vol. 1)", ("Gen", "Exod", "Lev", "Num", "Deut", "Josh", "Judg", "Ruth")),
    ("PG101", "101", "9th century", "Photius of Constantinople", "Quaestiones Amphilochianae & Commentary on the New Testament (vol. 1)", ("Matt", "Mark", "Luke", "John", "Acts", "Rom", "1Cor", "2Cor", "Gal", "Eph", "Phil", "Col", "Heb")),
    ("PG107", "107", "10th century", "Leo VI the Wise", "Homilies, Panegyrics, Tactica & Juridical Works", ()),
    ("PG109", "109", "10th century", "Theophanes Continuatus, Constantine VII, Cameniates et al.", "Byzantine Historical Works", ()),
    ("PG112", "112", "10th century", "Constantine VII Porphyrogenitus", "De ceremoniis (vol. 1)", ()),
    ("PG113", "113", "10th century", "Constantine VII Porphyrogenitus & Theodosius Diaconus", "De thematibus, De administrando imperio, Vita Basilii (vol. 2)", ()),
    ("PG118", "118", "10th century", "Oecumenius (Pseudo-Oecumenius)", "Commentaries on Acts, Pauline Epistles & Catholic Epistles (vol. 1)", ("Acts", "Rom", "1Cor", "2Cor", "Gal", "Eph", "Phil", "Col", "1Thess", "2Thess", "1Tim", "2Tim", "Titus", "Phlm", "Heb", "Jas", "1Pet", "2Pet", "1John", "2John", "3John", "Jude")),
    ("PG121", "121", "11th century", "George Cedrenus", "Compendium Historiarum (vol. 1)", ()),
    ("PG122", "122", "11th century", "George Cedrenus, John Scylitzes & Michael Psellus", "Compendium Historiarum (vol. 2), Breviarium & Psellus Opera", ()),
    ("PG123", "123", "11th century", "Theophylact of Bulgaria", "Enarratio in Evangelium Matthaei, Marci, Lucae & Joannis (vol. 1)", ("Matt", "Mark", "Luke", "John")),
    ("PG124", "124", "11th century", "Theophylact of Bulgaria", "Commentarius in Joannis Evangelium (cont.) & Pauline Epistles (vol. 2)", ("John", "Rom", "1Cor", "2Cor", "Gal", "Eph", "Phil", "Col")),
    ("PG125", "125", "11th century", "Theophylact of Bulgaria", "Commentaries on Pauline Epistles (cont.) & 1–2 Peter (vol. 3)", ("1Thess", "2Thess", "1Tim", "2Tim", "Titus", "Phlm", "Heb", "1Pet", "2Pet")),
    ("PG126", "126", "11th century", "Theophylact of Bulgaria", "Commentaries on New Testament & Minor Prophets; Orations & Letters (vol. 4)", ("Acts", "Jas", "1John", "2John", "3John", "Jude", "Hos", "Hab", "Jonah", "Nah", "Mic")),
    ("PG134", "134", "12th century", "John Zonaras", "Annales (vol. 1)", ()),
    ("PG139", "139", "13th century", "Nicetas Choniates, Isidore of Thessalonica et al.", "Historia Byzantina & Thesaurus", ()),
    ("PG146", "146", "14th century", "Nicephorus Callistus", "Ecclesiastical History, Books 8–14 (vol. 2)", ()),
    ("PG148", "148", "14th century", "Nicephorus Gregoras", "Historia Byzantina, Books 1–24 (vol. 1)", ()),
    ("PG151", "151", "14th century", "Gregory Palamas, Gregory Acindynus & Barlaam", "Hesychast Theological Works (vol. 2)", ()),
    ("PG153", "153", "14th century", "John VI Cantacuzene", "Historia Byzantina, Books 1–4 (vol. 1)", ()),
    ("PG155", "155", "15th century", "Symeon of Thessalonica", "Liturgical & Theological Works", ()),
    ("PG157", "157", "15th century", "George Codinus & Ducas", "De officiis, Historia Byzantina (1341–1462)", ()),
    ("PG158", "158", "15th century", "Michael Glycas", "Annales & Letters", ()),
)


def _parse_pg_text(raw: str) -> list[dict[str, Any]]:
    """Parse CGPG ``$0=... $8=PAGE $9=LINE`` file into compact ``[{"page": ..., "text": ...}]``."""
    pages: list[dict[str, Any]] = []
    cur_page = "1"
    cur_lines: list[str] = []

    def flush() -> None:
        if cur_lines:
            joined = unicodedata.normalize("NFC", "\n".join(cur_lines))
            pages.append({"page": cur_page, "text": joined})
            cur_lines.clear()

    for line in raw.splitlines():
        m = _MARKER_RE.match(line.strip())
        if m:
            page_no = m.group(1)
            if page_no != cur_page:
                flush()
                cur_page = page_no
            continue
        stripped = line.strip()
        if stripped:
            cur_lines.append(stripped)
    flush()
    return pages


def build(repo_dir: Path) -> dict[str, Any]:
    volumes: dict[str, Any] = {}
    total_words = 0
    for vol_id, pg_num, period, author, title, books in VOLUMES:
        txt_path = repo_dir / vol_id / f"{vol_id}_text.txt"
        if not txt_path.is_file():
            raise FileNotFoundError(f"missing expected CGPG volume text: {txt_path}")
        raw = txt_path.read_text(encoding="utf-8", errors="replace")
        pages = _parse_pg_text(raw)
        wc = sum(len(p["text"].split()) for p in pages)
        total_words += wc
        volumes[vol_id] = {
            "_info": {
                "vol_id": vol_id,
                "pg": pg_num,
                "period": period,
                "author": author,
                "title": title,
                "biblical_books": list(books),
                "page_count": len(pages),
                "word_count": wc,
            },
            "pages": pages,
        }
        print(f"  {vol_id:8s} PG {pg_num:5s} {len(pages):4d} pages, {wc:7d} words — {author}: {title[:55]}")

    return {
        "_meta": {
            "name": "Calfa–GREgORI Patrologia Graeca Corpus (33 volumes, OCR)",
            "version": 1,
            "license": "CC BY 4.0 (CGPG — UCLouvain GREgORI & Calfa, Vidal-Gorène & Kindt, LREC 2026)",
            "attribution": (
                "Vidal-Gorène, C., & Kindt, B. (2026). The Patrologia Graeca Corpus: OCR, "
                "Annotation, and Open Release of Noisy Nineteenth-Century Polytonic Greek Editions. "
                "LREC 2026. https://github.com/calfa-co/Patrologia-Graeca (CC BY 4.0)."
            ),
            "source": f"https://github.com/{REPO}@{COMMIT}",
            "edition_fidelity": "ocr",
            "volume_count": len(volumes),
            "total_words": total_words,
        },
        "volumes": volumes,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Build patrologia-graeca-corpus.json.gz from CGPG repo.")
    ap.add_argument("source", type=Path, help="path to cloned/extracted calfa-co/Patrologia-Graeca dir")
    ap.add_argument("-o", "--output", type=Path, default=Path("patrologia-graeca-corpus.json.gz"))
    args = ap.parse_args()
    payload = build(args.source)
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    with args.output.open("wb") as raw_f:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw_f, compresslevel=9, mtime=0) as gz:
            gz.write(raw)
    mb = args.output.stat().st_size / 1_000_000
    print(f"wrote {args.output} ({payload['_meta']['volume_count']} volumes, {payload['_meta']['total_words']} words, {mb:.2f} MB gz)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
