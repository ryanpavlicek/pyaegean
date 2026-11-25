"""Load the Calfa–GREgORI Patrologia Graeca corpus (opt-in, fetched, CC BY 4.0).

Packages 33 digitized Migne *Patrologia Graeca* volumes (~5.5 million Greek words, OCR of
19th-century prints) from the CGPG project (UCLouvain GREgORI & Calfa, Vidal-Gorène & Kindt,
LREC 2026; **CC BY 4.0**). Includes 9 major biblical commentary volumes (Cyril of Alexandria
on John & Minor Prophets, Procopius of Gaza on the Old Testament, Photius on the New
Testament, Oecumenius on Acts/Paul/Catholic Epistles, and Theophylact of Bulgaria on the
Gospels, Paul, 1–2 Peter, and Minor Prophets) alongside Pre-Nicaean Fathers, Church
historians, Gregory Palamas, and Byzantine chroniclers.

Use ``load_patrologia("PG073")`` to load a single volume in under a second, or
``aegean.load("patrologia")`` to load all 33 volumes.
"""

from __future__ import annotations

import unicodedata
from typing import Any

_PG_BUNDLE_CACHE: dict[str, Any] | None = None

# Offline metadata for all 33 CGPG Patrologia Graeca volumes.
PG_VOLUMES: tuple[dict[str, Any], ...] = (
    {"id": "PG003", "pg": "3", "period": "5th–6th c.", "author": "Pseudo-Dionysius the Areopagite", "title": "Opera Omnia (vol. 1)", "biblical_books": ()},
    {"id": "PG005", "pg": "5", "period": "2nd c.", "author": "Ignatius, Polycarp, Melito et al.", "title": "Apostolic & 2nd-Century Fathers", "biblical_books": ()},
    {"id": "PG006", "pg": "6", "period": "2nd c.", "author": "Justin Martyr, Tatian, Athenagoras, Theophilus", "title": "2nd-Century Apologists", "biblical_books": ()},
    {"id": "PG008", "pg": "8", "period": "2nd–3rd c.", "author": "Clement of Alexandria", "title": "Protrepticus, Paedagogus, Stromata (vol. 1)", "biblical_books": ()},
    {"id": "PG009", "pg": "9", "period": "2nd–3rd c.", "author": "Clement of Alexandria", "title": "Stromata (cont.), Quis dives, Excerpta, Eclogae (vol. 2)", "biblical_books": ()},
    {"id": "PG016_3", "pg": "16.3", "period": "3rd c.", "author": "Origen & Hippolytus", "title": "Origen Hexapla (cont.); Hippolytus Philosophumena", "biblical_books": ()},
    {"id": "PG021", "pg": "21", "period": "4th c.", "author": "Eusebius of Caesarea", "title": "Praeparatio Evangelica (vol. 3)", "biblical_books": ()},
    {"id": "PG042", "pg": "42", "period": "4th c.", "author": "Epiphanius of Salamis", "title": "Panarion (cont.), Expositio fidei (vol. 2)", "biblical_books": ()},
    {"id": "PG067", "pg": "67", "period": "5th c.", "author": "Socrates Scholasticus & Sozomen", "title": "Historia Ecclesiastica", "biblical_books": ()},
    {"id": "PG071", "pg": "71", "period": "5th c.", "author": "Cyril of Alexandria", "title": "Commentaries on the Twelve Minor Prophets (vol. 4)", "biblical_books": ("Hos", "Joel", "Amos", "Obad", "Jonah", "Mic", "Nah", "Hab", "Zeph", "Hag", "Zech", "Mal")},
    {"id": "PG073", "pg": "73", "period": "5th c.", "author": "Cyril of Alexandria", "title": "Commentary on the Gospel of John (vol. 6)", "biblical_books": ("John",)},
    {"id": "PG087_1", "pg": "87.1", "period": "6th c.", "author": "Procopius of Gaza", "title": "Old Testament Commentaries (Octateuch & Catenae, vol. 1)", "biblical_books": ("Gen", "Exod", "Lev", "Num", "Deut", "Josh", "Judg", "Ruth")},
    {"id": "PG101", "pg": "101", "period": "9th c.", "author": "Photius of Constantinople", "title": "Quaestiones Amphilochianae & NT Commentary (vol. 1)", "biblical_books": ("Matt", "Mark", "Luke", "John", "Acts", "Rom", "1Cor", "2Cor", "Gal", "Eph", "Phil", "Col", "Heb")},
    {"id": "PG107", "pg": "107", "period": "10th c.", "author": "Leo VI the Wise", "title": "Homilies, Panegyrics, Tactica & Juridical Works", "biblical_books": ()},
    {"id": "PG109", "pg": "109", "period": "10th c.", "author": "Theophanes Continuatus, Constantine VII et al.", "title": "Byzantine Historical Works", "biblical_books": ()},
    {"id": "PG112", "pg": "112", "period": "10th c.", "author": "Constantine VII Porphyrogenitus", "title": "De ceremoniis (vol. 1)", "biblical_books": ()},
    {"id": "PG113", "pg": "113", "period": "10th c.", "author": "Constantine VII Porphyrogenitus & Theodosius", "title": "De thematibus, De administrando imperio (vol. 2)", "biblical_books": ()},
    {"id": "PG118", "pg": "118", "period": "10th c.", "author": "Oecumenius (Pseudo-Oecumenius)", "title": "Commentaries on Acts, Pauline & Catholic Epistles (vol. 1)", "biblical_books": ("Acts", "Rom", "1Cor", "2Cor", "Gal", "Eph", "Phil", "Col", "1Thess", "2Thess", "1Tim", "2Tim", "Titus", "Phlm", "Heb", "Jas", "1Pet", "2Pet", "1John", "2John", "3John", "Jude")},
    {"id": "PG121", "pg": "121", "period": "11th c.", "author": "George Cedrenus", "title": "Compendium Historiarum (vol. 1)", "biblical_books": ()},
    {"id": "PG122", "pg": "122", "period": "11th c.", "author": "George Cedrenus, John Scylitzes & Michael Psellus", "title": "Compendium Historiarum (vol. 2) & Psellus Opera", "biblical_books": ()},
    {"id": "PG123", "pg": "123", "period": "11th c.", "author": "Theophylact of Bulgaria", "title": "Enarratio in Evangelia Matthaei, Marci, Lucae & Joannis (vol. 1)", "biblical_books": ("Matt", "Mark", "Luke", "John")},
    {"id": "PG124", "pg": "124", "period": "11th c.", "author": "Theophylact of Bulgaria", "title": "Commentarius in Joannem (cont.) & Pauline Epistles (vol. 2)", "biblical_books": ("John", "Rom", "1Cor", "2Cor", "Gal", "Eph", "Phil", "Col")},
    {"id": "PG125", "pg": "125", "period": "11th c.", "author": "Theophylact of Bulgaria", "title": "Commentaries on Pauline Epistles (cont.) & 1–2 Peter (vol. 3)", "biblical_books": ("1Thess", "2Thess", "1Tim", "2Tim", "Titus", "Phlm", "Heb", "1Pet", "2Pet")},
    {"id": "PG126", "pg": "126", "period": "11th c.", "author": "Theophylact of Bulgaria", "title": "Commentaries on NT & Minor Prophets; Orations & Letters (vol. 4)", "biblical_books": ("Acts", "Jas", "1John", "2John", "3John", "Jude", "Hos", "Hab", "Jonah", "Nah", "Mic")},
    {"id": "PG134", "pg": "134", "period": "12th c.", "author": "John Zonaras", "title": "Annales (vol. 1)", "biblical_books": ()},
    {"id": "PG139", "pg": "139", "period": "13th c.", "author": "Nicetas Choniates, Isidore of Thessalonica et al.", "title": "Historia Byzantina & Thesaurus", "biblical_books": ()},
    {"id": "PG146", "pg": "146", "period": "14th c.", "author": "Nicephorus Callistus", "title": "Ecclesiastical History, Books 8–14 (vol. 2)", "biblical_books": ()},
    {"id": "PG148", "pg": "148", "period": "14th c.", "author": "Nicephorus Gregoras", "title": "Historia Byzantina, Books 1–24 (vol. 1)", "biblical_books": ()},
    {"id": "PG151", "pg": "151", "period": "14th c.", "author": "Gregory Palamas, Acindynus & Barlaam", "title": "Hesychast Theological Works (vol. 2)", "biblical_books": ()},
    {"id": "PG153", "pg": "153", "period": "14th c.", "author": "John VI Cantacuzene", "title": "Historia Byzantina, Books 1–4 (vol. 1)", "biblical_books": ()},
    {"id": "PG155", "pg": "155", "period": "15th c.", "author": "Symeon of Thessalonica", "title": "Liturgical & Theological Works", "biblical_books": ()},
    {"id": "PG157", "pg": "157", "period": "15th c.", "author": "George Codinus & Ducas", "title": "De officiis, Historia Byzantina (1341–1462)", "biblical_books": ()},
    {"id": "PG158", "pg": "158", "period": "15th c.", "author": "Michael Glycas", "title": "Annales & Letters", "biblical_books": ()},
)

_PG_ALIAS: dict[str, str] = {}
for _v in PG_VOLUMES:
    _vid = _v["id"]
    _pg = _v["pg"]
    for _k in (_vid, _vid.lower(), _pg, f"pg{_pg}", f"pg {_pg}", _pg.replace(".", "_")):
        _PG_ALIAS[_k.strip().lower().replace(" ", "").replace("-", "")] = _vid


def resolve_pg_volume(volume: str) -> str:
    """Resolve a Patrologia Graeca volume identifier (e.g. ``'PG073'``, ``'73'``, ``'87.1'``)."""
    key = volume.strip().lower().replace(" ", "").replace("-", "")
    if key in _PG_ALIAS:
        return _PG_ALIAS[key]
    if key.isdigit():
        padded = f"pg{int(key):03d}"
        if padded in _PG_ALIAS:
            return _PG_ALIAS[padded]
    valid = ", ".join(v["id"] for v in PG_VOLUMES[:8]) + ", …"
    raise ValueError(f"unknown Patrologia Graeca volume {volume!r}; examples: {valid}")


def patrologia_volumes() -> list[dict[str, Any]]:
    """List metadata for all 33 CGPG Patrologia Graeca volumes (works offline)."""
    return [dict(v) for v in PG_VOLUMES]


def _load_bundle(*, allow_fetch: bool = True) -> dict[str, Any]:
    global _PG_BUNDLE_CACHE
    if _PG_BUNDLE_CACHE is not None:
        return _PG_BUNDLE_CACHE
    from ...data import _REMOTE, DataNotAvailableError, cache_dir, fetch, load_gzip_json, present_paths

    paths = present_paths(_REMOTE["patrologia-graeca-corpus"], cache_dir())
    if not paths:
        if not allow_fetch:
            raise DataNotAvailableError(
                "patrologia-graeca-corpus is not cached — run "
                "`aegean library install patrologia-graeca-corpus` or pass offline=False"
            )
        path = fetch("patrologia-graeca-corpus")
    else:
        path = paths[0]
    _PG_BUNDLE_CACHE = load_gzip_json(path)
    return _PG_BUNDLE_CACHE


def _volume_to_doc(vol_id: str, entry: dict[str, Any]) -> Any:
    from ...core.model import Document, DocumentMeta, Token, TokenKind
    from ...greek.tokenize import tokenize

    info = entry.get("_info", {})
    tokens: list[Token] = []
    lines: list[list[int]] = []
    for page_obj in entry.get("pages", ()):
        page_label = str(page_obj.get("page", ""))
        for raw_line in str(page_obj.get("text", "")).splitlines():
            line_no = len(lines)
            idxs: list[int] = []
            for tok in tokenize(raw_line):
                if not any(ch.isalpha() for ch in tok.text):
                    continue
                word = unicodedata.normalize("NFC", tok.text)
                pos = len(tokens)
                tokens.append(
                    Token(
                        text=word,
                        kind=TokenKind.WORD,
                        glyphs=word,
                        line_no=line_no,
                        position=pos,
                        annotations={"page": page_label} if page_label else {},
                    )
                )
                idxs.append(pos)
            if idxs:
                lines.append(idxs)
    author = info.get("author", "")
    title = info.get("title", vol_id)
    notes = [f"PG {info.get('pg', vol_id)} (CGPG OCR, LREC 2026)"]
    if info.get("biblical_books"):
        notes.append("Biblical books: " + ", ".join(info["biblical_books"]))
    return Document(
        id=vol_id,
        script_id="greek",
        tokens=tokens,
        lines=lines,
        meta=DocumentMeta(
            name=f"{author}: {title}" if author else title,
            period=info.get("period", "Patristic / Byzantine"),
            notes=tuple(notes),
        ),
    )


def load_patrologia(
    volume: str | None = None,
    *,
    offline: bool = False,
) -> Any:
    """Load the Calfa–GREgORI Patrologia Graeca corpus (33 volumes, CC BY 4.0, OCR).

    Pass ``volume`` (e.g. ``'PG073'``, ``'73'``, ``'PG123'``) to load a single volume
    quickly, or omit ``volume`` to load all 33 volumes.
    """
    from ...core.corpus import Corpus
    from ...core.provenance import Provenance
    from .inventory import greek_inventory

    bundle = _load_bundle(allow_fetch=not offline)
    meta = bundle.get("_meta", {})
    volumes_map: dict[str, Any] = bundle["volumes"]

    if volume is not None:
        vid = resolve_pg_volume(volume)
        docs = [_volume_to_doc(vid, volumes_map[vid])]
        scope = f"{vid} ({volumes_map[vid]['_info'].get('author', '')})"
    else:
        docs = [_volume_to_doc(vid, entry) for vid, entry in volumes_map.items()]
        scope = f"all {len(docs)} CGPG Patrologia Graeca volumes"

    prov = Provenance(
        source=meta.get("name", "Calfa–GREgORI Patrologia Graeca Corpus (33 volumes, OCR)"),
        license=meta.get("license", "CC BY 4.0"),
        url=meta.get("source", "https://github.com/calfa-co/Patrologia-Graeca"),
        citation=meta.get("attribution", ""),
        edition_fidelity="ocr",
        notes=(f"Scope: {scope}",),
    )
    return Corpus(docs, sign_inventory=greek_inventory(), provenance=prov, script_id="greek")


from ...core.corpus import register_loader  # noqa: E402

register_loader("patrologia", load_patrologia, fresh=True)
