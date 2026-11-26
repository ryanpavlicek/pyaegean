"""Pure-Python backend service powering the local PyAegean Greek visual corpus browser.

Every helper returns plain JSON-serializable ``dict`` / ``list`` structures so the HTTP
server, automated tests, and programmatic callers share one clean contract without
coupling to socket I/O or any third-party web framework.
"""

from __future__ import annotations

import csv
import importlib.util
import io
import json
import re
import unicodedata
from collections import Counter
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from ._translations import lookup_doc_translation, lookup_verse_translations

__all__ = [
    "activate_lexicon_payload",
    "analyze_text_payload",
    "analyze_word_payload",
    "bible_commentaries_payload",
    "bible_commentary_excerpt_payload",
    "bible_editions_payload",
    "bible_psalm_payload",
    "bible_witnesses_payload",
    "catalog_payload",
    "collections_payload",
    "configure_engine_payload",
    "document_payload",
    "engine_status_payload",
    "export_payload",
    "library_fetch_payload",
    "library_payload",
    "scan_lines_payload",
    "search_payload",
    "word_study_payload",
]


# ── Morphology Decoders (AGDT 9-char XPOS & Robinson NT Codes) ───────────────

_AGDT_POS: dict[str, str] = {
    "n": "Noun",
    "v": "Verb",
    "t": "Participle",
    "a": "Adjective",
    "d": "Adverb",
    "l": "Article",
    "g": "Particle",
    "c": "Conjunction",
    "r": "Preposition",
    "p": "Pronoun",
    "m": "Numeral",
    "i": "Interjection",
    "e": "Exclamation",
    "u": "Punctuation",
    "x": "Unassigned",
}
_AGDT_PERSON: dict[str, str] = {"1": "1st", "2": "2nd", "3": "3rd"}
_AGDT_NUMBER: dict[str, str] = {"s": "Singular", "p": "Plural", "d": "Dual"}
_AGDT_TENSE: dict[str, str] = {
    "p": "Present",
    "i": "Imperfect",
    "r": "Perfect",
    "l": "Pluperfect",
    "t": "Future Perfect",
    "f": "Future",
    "a": "Aorist",
}
_AGDT_MOOD: dict[str, str] = {
    "i": "Indicative",
    "s": "Subjunctive",
    "o": "Optative",
    "n": "Infinitive",
    "m": "Imperative",
    "p": "Participle",
}
_AGDT_VOICE: dict[str, str] = {
    "a": "Active",
    "p": "Passive",
    "m": "Middle",
    "e": "Medio-passive",
}
_AGDT_GENDER: dict[str, str] = {"m": "Masculine", "f": "Feminine", "n": "Neuter"}
_AGDT_CASE: dict[str, str] = {
    "n": "Nominative",
    "g": "Genitive",
    "d": "Dative",
    "a": "Accusative",
    "v": "Vocative",
    "l": "Locative",
}
_AGDT_DEGREE: dict[str, str] = {"c": "Comparative", "s": "Superlative"}


def decode_xpos(xpos: str | None) -> dict[str, str]:
    """Decode a 9-character AGDT/Perseus postag string into human-readable features."""
    if not xpos or len(xpos) < 9 or xpos == "---------":
        return {}
    s = xpos.lower()
    slots: list[tuple[str, str | None]] = [
        ("POS", _AGDT_POS.get(s[0])),
        ("Person", _AGDT_PERSON.get(s[1])),
        ("Number", _AGDT_NUMBER.get(s[2])),
        ("Tense", _AGDT_TENSE.get(s[3])),
        ("Mood", _AGDT_MOOD.get(s[4])),
        ("Voice", _AGDT_VOICE.get(s[5])),
        ("Gender", _AGDT_GENDER.get(s[6])),
        ("Case", _AGDT_CASE.get(s[7])),
        ("Degree", _AGDT_DEGREE.get(s[8])),
    ]
    return {k: v for k, v in slots if v is not None}


_ROB_POS: dict[str, str] = {
    "N": "Noun",
    "V": "Verb",
    "A": "Adjective",
    "T": "Article",
    "P": "Personal Pronoun",
    "R": "Relative Pronoun",
    "D": "Demonstrative Pronoun",
    "I": "Interrogative Pronoun",
    "X": "Indefinite Pronoun",
    "F": "Reflexive Pronoun",
    "C": "Reciprocal Pronoun",
    "K": "Correlative Pronoun",
    "Q": "Correlative/Interrogative",
    "S": "Possessive Pronoun",
    "PREP": "Preposition",
    "CONJ": "Conjunction",
    "COND": "Conditional",
    "PRT": "Particle",
    "ADV": "Adverb",
    "INJ": "Interjection",
    "ARAM": "Aramaic",
    "HEB": "Hebrew",
    "N-PRI": "Proper Noun (Indeclinable)",
    "N-LI": "Letter (Indeclinable)",
    "N-OI": "Noun (Other Indeclinable)",
    "A-NUI": "Numeral (Indeclinable)",
}
_ROB_TENSE: dict[str, str] = {
    "P": "Present",
    "I": "Imperfect",
    "F": "Future",
    "2F": "2nd Future",
    "A": "Aorist",
    "2A": "2nd Aorist",
    "R": "Perfect",
    "2R": "2nd Perfect",
    "L": "Pluperfect",
    "2L": "2nd Pluperfect",
}
_ROB_VOICE: dict[str, str] = {
    "A": "Active",
    "M": "Middle",
    "P": "Passive",
    "E": "Middle/Passive",
    "D": "Middle Deponent",
    "O": "Passive Deponent",
    "N": "Mid/Pass Deponent",
    "Q": "Impersonal Active",
    "X": "No Voice",
}
_ROB_MOOD: dict[str, str] = {
    "I": "Indicative",
    "S": "Subjunctive",
    "O": "Optative",
    "M": "Imperative",
    "N": "Infinitive",
    "P": "Participle",
    "R": "Imperative Participle",
}
_ROB_CASE: dict[str, str] = {
    "N": "Nominative",
    "G": "Genitive",
    "D": "Dative",
    "A": "Accusative",
    "V": "Vocative",
}
_ROB_NUM: dict[str, str] = {"S": "Singular", "P": "Plural"}
_ROB_GEN: dict[str, str] = {"M": "Masculine", "F": "Feminine", "N": "Neuter"}


def decode_robinson(code: str | None) -> dict[str, str]:
    """Decode a Robinson NT morphology code (e.g. ``V-AAI-3S``, ``N-NSM``) to labels."""
    if not code:
        return {}
    raw = code.strip().upper()
    if raw in _ROB_POS:
        return {"POS": _ROB_POS[raw]}
    parts = raw.split("-")
    out: dict[str, str] = {}
    head = parts[0]
    if head in _ROB_POS:
        out["POS"] = _ROB_POS[head]
    if head == "V" and len(parts) >= 2:
        tvm = parts[1]
        m = re.match(r"^(2?[PIFARL])([AMPEODNQX])([ISOMNPR])$", tvm)
        if m:
            if m.group(1) in _ROB_TENSE:
                out["Tense"] = _ROB_TENSE[m.group(1)]
            if m.group(2) in _ROB_VOICE:
                out["Voice"] = _ROB_VOICE[m.group(2)]
            if m.group(3) in _ROB_MOOD:
                out["Mood"] = _ROB_MOOD[m.group(3)]
        if len(parts) >= 3:
            tail = parts[2]
            if len(tail) == 2 and tail[0] in ("1", "2", "3"):
                out["Person"] = f"{tail[0]}{'st' if tail[0]=='1' else 'nd' if tail[0]=='2' else 'rd'}"
                if tail[1] in _ROB_NUM:
                    out["Number"] = _ROB_NUM[tail[1]]
            elif len(tail) == 3:
                if tail[0] in _ROB_CASE:
                    out["Case"] = _ROB_CASE[tail[0]]
                if tail[1] in _ROB_NUM:
                    out["Number"] = _ROB_NUM[tail[1]]
                if tail[2] in _ROB_GEN:
                    out["Gender"] = _ROB_GEN[tail[2]]
    elif len(parts) >= 2:
        spec = parts[1]
        if len(spec) >= 3 and spec[0] in ("1", "2", "3"):
            out["Person"] = f"{spec[0]}{'st' if spec[0]=='1' else 'nd' if spec[0]=='2' else 'rd'}"
            spec = spec[1:]
        if len(spec) >= 2 and spec[0] in _ROB_CASE and spec[1] in _ROB_NUM:
            out["Case"] = _ROB_CASE[spec[0]]
            out["Number"] = _ROB_NUM[spec[1]]
            if len(spec) >= 3 and spec[2] in _ROB_GEN:
                out["Gender"] = _ROB_GEN[spec[2]]
    return out


def _fold(text: str) -> str:
    nfd = unicodedata.normalize("NFD", text or "")
    stripped = "".join(ch for ch in nfd if unicodedata.category(ch) != "Mn")
    return unicodedata.normalize("NFC", stripped).lower().replace("ς", "σ")


def _json_safe(obj: Any) -> Any:
    """Recursively convert dataclasses, sets, and Paths into plain JSON primitives."""
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, Path):
        return str(obj)
    if is_dataclass(obj) and not isinstance(obj, type):
        return _json_safe(asdict(obj))
    if isinstance(obj, dict):
        return {str(k): _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set, frozenset)):
        return [_json_safe(v) for v in obj]
    if hasattr(obj, "to_dict") and callable(obj.to_dict):
        return _json_safe(obj.to_dict())
    return str(obj)


# ── Engine Status & Live Toggling ────────────────────────────────────────────

def engine_status_payload() -> dict[str, Any]:
    """Return the active PyAegean Greek NLP backend, lexica, and provider status."""
    from ..greek import calibrate, documentary, joint, lemma_rerank, lexicons, treebank
    from ..greek.bible import strongs_loaded

    neural_installed = importlib.util.find_spec("onnxruntime") is not None
    neural_active = joint.active() is not None
    backend_info: dict[str, Any] = {}
    if neural_active:
        try:
            backend_info = dict(joint.neural_backend_info())
        except Exception:
            backend_info = {}
    else:
        try:
            from ..greek import _ort

            if neural_installed:
                import onnxruntime as ort

                backend_info = {
                    "available_providers": list(ort.get_available_providers()),
                    "resolved_providers": list(_ort.resolve_providers()),
                    "active_providers": [],
                }
        except Exception:
            backend_info = {}

    reranker_mode = "off"
    if lemma_rerank.oov_lemma_reranker_active():
        reranker_mode = "weighted" if lemma_rerank._ACTIVE_CONFIG is not None else "unique"

    return {
        "neural_installed": neural_installed,
        "neural_active": neural_active,
        "treebank_active": treebank.active() is not None,
        "oov_reranker": reranker_mode,
        "calibration_active": calibrate.active() is not None or calibrate.active_registry() is not None,
        "documentary_reconciliation": documentary.documentary_reconciliation_active(),
        "documentary_lemma_rescue": documentary.documentary_lemma_rescue_active(),
        "active_lexica": list(lexicons.active_lexica()),
        "strongs_extended_cached": strongs_loaded(),
        "backend_info": _json_safe(backend_info),
    }


def configure_engine_payload(options: dict[str, Any]) -> dict[str, Any]:
    """Toggle PyAegean Greek NLP runtime options (neural, treebank, reranker, calibration)."""
    from ..greek import calibrate, documentary, joint, lemma_rerank, treebank

    if "neural" in options:
        want_neural = bool(options["neural"])
        if want_neural:
            joint.use_neural_pipeline()
        else:
            joint.disable_neural_pipeline()

    if "treebank" in options:
        if bool(options["treebank"]):
            treebank.use_treebank()
        else:
            treebank.disable_treebank()

    if "oov_reranker" in options:
        mode = str(options["oov_reranker"]).strip().lower()
        if mode in ("off", "false", "none", ""):
            lemma_rerank.disable_oov_lemma_reranker()
        elif mode == "weighted":
            if joint.active() is None:
                joint.use_neural_pipeline()
            lemma_rerank.use_oov_lemma_reranker(config="weighted")
        elif mode in ("unique", "deterministic", "true"):
            if joint.active() is None:
                joint.use_neural_pipeline()
            lemma_rerank.use_oov_lemma_reranker()
        else:
            raise ValueError(f"unsupported oov_reranker mode: {mode!r}")

    if "calibration" in options:
        if bool(options["calibration"]):
            calibrate.use_calibration_registry()
        else:
            calibrate.disable_calibration()

    if "documentary_reconciliation" in options:
        if bool(options["documentary_reconciliation"]):
            if joint.active() is None:
                joint.use_neural_pipeline()
            documentary.use_documentary_reconciliation()
        else:
            documentary.disable_documentary_reconciliation()

    if "documentary_lemma_rescue" in options:
        if bool(options["documentary_lemma_rescue"]):
            if joint.active() is None:
                joint.use_neural_pipeline()
            documentary.use_documentary_lemma_rescue()
        else:
            documentary.disable_documentary_lemma_rescue()

    return engine_status_payload()


# ── Catalog & 3,844-Work Collections Index ───────────────────────────────────

def catalog_payload() -> dict[str, Any]:
    """Return the complete Greek corpus, Bible, collection, lexicon, and engine catalog."""
    import aegean
    from ..core.catalog import CORPORA
    from ..data import _REMOTE, cache_dir, present_paths
    from ..greek import bible, lexicons
    from ..scripts.greek._collections import collections as greek_collections

    cdir = cache_dir()
    greek_corpora: list[dict[str, Any]] = []
    for spec in CORPORA:
        if spec.script_id != "greek":
            continue
        cached = spec.bundled
        if not cached and spec.asset_name and spec.asset_name in _REMOTE:
            cached = bool(present_paths(_REMOTE[spec.asset_name], cdir))
        greek_corpora.append(
            {
                "id": spec.id,
                "title": spec.title,
                "blurb": spec.blurb,
                "description": spec.description,
                "category": spec.category,
                "bundled": spec.bundled,
                "cached": cached,
                "size_hint": spec.size_hint or ("bundled" if spec.bundled else ""),
                "license": spec.license,
                "asset_name": spec.asset_name,
            }
        )

    featured: list[dict[str, Any]] = [
        {
            "label": "NT John 1:1–18 (Nestle 1904)",
            "target": "John 1:1-18",
            "badge": "Biblical · Offline Ready",
            "blurb": "Prologue of John with gold morphology, Strong's, parallel WEB translation, and linked patristic commentaries.",
        },
        {
            "label": "LXX Genesis 1:1–5 (Swete)",
            "target": "Gen 1:1-5",
            "badge": "Septuagint · Offline Ready",
            "blurb": "Creation narrative in Swete's Greek Septuagint with Brenton parallel translation and interlinear lexicon.",
        },
        {
            "label": "LXX Psalm 22 / MT 23 (Swete)",
            "target": "MT Ps 23:1-6",
            "badge": "Septuagint · MT Numbering",
            "blurb": "The Shepherd Psalm with automatic LXX ↔ Masoretic Psalm numbering and interlinear glosses.",
        },
        {
            "label": "NT Philemon 1 (Nestle 1904)",
            "target": "Phlm 1:1-25",
            "badge": "Biblical · Offline Ready",
            "blurb": "Complete Epistle to Philemon with gold lemmas, Robinson morphology, Strong's, and parallel translation.",
        },
        {
            "label": "Homer, Iliad 1.1 (Epic)",
            "target": "greek",
            "doc_index": 0,
            "badge": "Classical · Scansion Ready",
            "blurb": "Opening hexameter of the Iliad — try Metrical Scansion, Attic/Epic IPA, and LSJ/Cunliffe lookup.",
        },
        {
            "label": "Herodotus, Histories 1.1 (Ionic)",
            "target": "greek",
            "doc_index": 3,
            "badge": "Classical · Ionic Prose",
            "blurb": "Proem of Herodotus with parallel Godley translation and syntactic analysis.",
        },
        {
            "label": "Sappho, Hymn to Aphrodite (Aeolic)",
            "target": "greek",
            "doc_index": 4,
            "badge": "Lyric · Aeolic",
            "blurb": "Opening of Sappho fr. 1 with Aeolic forms and phonetic transcription.",
        },
    ]

    lex_rows = []
    active_set = set(lexicons.active_lexica())
    for info in lexicons.lexica():
        lex_rows.append(
            {
                "id": info.id,
                "name": info.name,
                "scope": info.scope,
                "license": info.license,
                "hosted": info.hosted,
                "active": info.id in active_set,
            }
        )

    return {
        "version": aegean.__version__,
        "featured": featured,
        "corpora": greek_corpora,
        "collections": _json_safe(greek_collections()),
        "nt_books": _json_safe(bible.nt_books()),
        "nt_editions": _json_safe(bible.nt_editions()),
        "lxx_books": _json_safe(bible.lxx_books()),
        "lxx_loaded": bible.lxx_loaded(),
        "witnesses": _json_safe(bible.witnesses()),
        "lexica": lex_rows,
        "engine": engine_status_payload(),
    }


def collections_payload(
    *,
    collection: str | None = None,
    query: str | None = None,
    period: str | None = None,
    limit: int = 60,
    offset: int = 0,
) -> dict[str, Any]:
    """Browse and filter all 3,844 open-licensed Greek library works offline."""
    from ..scripts.greek._collections import collection_works

    all_works = collection_works(
        collection or None,
        query=query or None,
    )
    if period and period.strip():
        p_low = period.strip().lower()
        all_works = [w for w in all_works if p_low in str(w.get("period", "")).lower()]
    total = len(all_works)
    safe_offset = max(0, offset)
    safe_limit = max(1, min(limit, 250))
    page = all_works[safe_offset : safe_offset + safe_limit]
    return {
        "total": total,
        "offset": safe_offset,
        "limit": safe_limit,
        "works": _json_safe(page),
    }


# ── Document Loading, Token Enrichment & Sentence Dependency Structures ──────

_NT_REF_RE = re.compile(
    r"^(?:nt:)?(?P<book>[1-3]?\s*[A-Za-z][A-Za-z.\s]{0,24}?)"
    r"(?:\s+(?P<ref>\d+(?:[.:]\d+(?:-\d+)?)?(?:-\d+)?))?$"
)
_MT_PSALM_RE = re.compile(r"^mt\s+ps(?:alm|alms|a)?\.?\s*(?P<ref>\d+(?:[.:]\d+(?:-\d+)?)?(?:-\d+)?)?$", re.IGNORECASE)


def _try_parse_bible_target(
    target: str,
    ref: str | None,
    edition: str,
    numbering: str,
) -> tuple[str, str, str | None, str] | None:
    """Detect whether ``target`` names an NT or LXX book/passage.

    Returns ``("nt" | "lxx", book_name, effective_ref, effective_numbering)`` or ``None``.
    """
    from ..greek import bible
    from ..scripts.greek.nt import _resolve_book as resolve_nt_book

    raw = target.strip()
    if not raw:
        return None

    low = raw.lower()
    if low.startswith("nt:"):
        body = raw[3:].strip()
        m = _NT_REF_RE.match(body)
        if m:
            try:
                bk = resolve_nt_book(m.group("book").strip())
                return ("nt", bk, ref or m.group("ref"), "lxx")
            except Exception:
                pass
    if low.startswith("lxx:"):
        body = raw[4:].strip()
        m_mt = _MT_PSALM_RE.match(body)
        if m_mt:
            return ("lxx", "Ps", ref or m_mt.group("ref"), "mt")
        m = _NT_REF_RE.match(body)
        if m:
            try:
                spec = bible.resolve_lxx_book(m.group("book").strip())
                return ("lxx", spec.name, ref or m.group("ref"), numbering)
            except Exception:
                pass

    m_mt = _MT_PSALM_RE.match(raw)
    if m_mt:
        return ("lxx", "Ps", ref or m_mt.group("ref"), "mt")

    # Avoid hijacking registered corpus IDs, PG volumes, ogc* works, or file paths.
    from ..core.catalog import CORPUS_BY_ID

    if low in CORPUS_BY_ID or low.startswith(("ogc", "pg", "tlg")) or "/" in raw or "\\" in raw:
        return None
    if Path(raw).exists():
        return None

    m = _NT_REF_RE.match(raw)
    if not m:
        return None
    book_cand = m.group("book").strip()
    ref_cand = ref or m.group("ref")

    # Prefer NT when book matches NT (e.g. "John 1:1-18", "Phlm 1"), else LXX ("Gen 1:1-5", "Ps 22").
    try:
        nt_bk = resolve_nt_book(book_cand)
        return ("nt", nt_bk, ref_cand, "lxx")
    except Exception:
        pass
    try:
        lxx_spec = bible.resolve_lxx_book(book_cand)
        return ("lxx", lxx_spec.name, ref_cand, numbering)
    except Exception:
        return None


def _short_gloss(surface: str, lemma: str, existing: str | None) -> tuple[str, str]:
    """Return ``(concise_gloss, strongs_id)`` using existing annotations, active lexica, or offline Strong's/Dodson."""
    from ..greek import lexicons
    from ..greek.bible import strongs_entry

    strongs_id = ""
    if existing:
        gloss = existing.strip()
        ent = strongs_entry(lemma or surface, allow_fetch=False)
        if ent is not None:
            strongs_id = ent.strongs
        return (gloss[:64], strongs_id)

    # Active hosted lexica (LSJ, Cunliffe, Abbott-Smith, Dodson, etc.) take priority when loaded
    if lexicons.active_lexica():
        for cand in (lemma, surface):
            if not cand:
                continue
            try:
                g = lexicons.gloss(cand)
                if g:
                    ent = strongs_entry(lemma or surface, allow_fetch=False)
                    return (g.strip()[:64], ent.strongs if ent else "")
            except Exception:
                pass

    ent = strongs_entry(lemma or surface, allow_fetch=False)
    if ent is None and lemma and surface and _fold(lemma) != _fold(surface):
        ent = strongs_entry(surface, allow_fetch=False)
    if ent is not None:
        return (ent.gloss.strip()[:64], ent.strongs)
    return ("", "")


def _enrich_tokens_and_sentences(
    tokens_raw: list[dict[str, Any]],
    *,
    prefer_gold: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Run active Greek NLP pipeline (neural when active, else baseline + gold) over tokens.

    Returns ``(enriched_tokens, sentences)`` where each sentence carries token indices and
    dependency arcs ready for inline SVG rendering.
    """
    from ..greek import calibrate, joint, lemmatize, pos_tag

    neural_model = joint.active()
    cal_active = calibrate.active() is not None or calibrate.active_registry() is not None

    # Partition tokens into logical sentences (by verse ref, line break, or Greek sentence punctuation)
    sent_groups: list[list[int]] = []
    cur: list[int] = []
    last_ref: str | None = None
    last_line: int | None = None

    for idx, t in enumerate(tokens_raw):
        t_ref = t.get("ref")
        t_line = t.get("line_no")
        if cur:
            if t_ref and last_ref and t_ref != last_ref:
                sent_groups.append(cur)
                cur = []
            elif not t_ref and t_line is not None and last_line is not None and t_line != last_line and len(cur) >= 18:
                sent_groups.append(cur)
                cur = []
        cur.append(idx)
        last_ref = t_ref
        last_line = t_line
        txt = t["text"]
        if txt.endswith((".", ";", "·", "\u037e", "\u0387", "!", "?")) and len(cur) >= 2:
            sent_groups.append(cur)
            cur = []
        elif len(cur) >= 65:
            sent_groups.append(cur)
            cur = []
    if cur:
        sent_groups.append(cur)

    enriched: list[dict[str, Any]] = [dict(t) for t in tokens_raw]
    sentences: list[dict[str, Any]] = []
    gloss_cache: dict[tuple[str, str], tuple[str, str]] = {}

    for s_idx, idxs in enumerate(sent_groups):
        words = [enriched[i]["text"] for i in idxs]
        ana = None
        if neural_model is not None and words:
            try:
                ana = joint.analyze_sentence(
                    words,
                    with_probs=cal_active,
                    domain="literary" if cal_active else None,
                    long_input="windowed",
                )
            except Exception:
                ana = None

        sent_toks_out: list[dict[str, Any]] = []
        for pos_in_s, global_i in enumerate(idxs):
            tok = enriched[global_i]
            ann = tok.get("annotations") or {}
            surface = tok["text"]

            gold_lem = str(ann.get("lemma") or "")
            gold_upos = str(ann.get("upos") or "")
            gold_morph = str(ann.get("morph") or "")
            gold_strongs = str(ann.get("strongs") or "")
            gold_gloss = str(ann.get("gloss") or "")

            robinson = gold_morph if (gold_morph and ("-" in gold_morph or gold_morph in _ROB_POS)) else ""
            robinson_decoded = decode_robinson(robinson) if robinson else {}

            if ana is not None:
                n_upos = ana.upos[pos_in_s]
                n_xpos = ana.xpos[pos_in_s]
                n_feats = ana.feats[pos_in_s]
                n_lem = ana.lemma[pos_in_s]
                n_head = int(ana.head[pos_in_s])
                n_rel = ana.deprel[pos_in_s]
                n_src = ana.lemma_source[pos_in_s].value if ana.lemma_source else "neural"
                raw_p_pos = ana.upos_prob[pos_in_s] if ana.upos_prob else None
                raw_p_lem = ana.lemma_script_prob[pos_in_s] if ana.lemma_script_prob else None
                conf_pos = round(float(raw_p_pos), 4) if raw_p_pos is not None else None
                conf_lem = round(float(raw_p_lem), 4) if raw_p_lem is not None else None
                lemma = gold_lem if (prefer_gold and gold_lem) else n_lem
                upos = gold_upos if (prefer_gold and gold_upos) else n_upos
                xpos = n_xpos
                feats = n_feats
                head_rel_sent = n_head
                relation = n_rel
                lemma_source = "corpus-gold" if (prefer_gold and gold_lem) else n_src
            else:
                lemma = gold_lem or lemmatize(surface)
                upos = gold_upos or (
                    gold_morph if gold_morph in {"NOUN", "VERB", "ADJ", "ADV", "ADP", "DET", "PRON", "CCONJ", "SCONJ", "PART", "NUM", "INTJ", "PROPN", "AUX", "PUNCT", "X"} else ""
                ) or pos_tag(surface)
                xpos = str(ann.get("xpos") or "")
                feats = str(ann.get("feats") or "")
                head_raw = ann.get("head")
                head_rel_sent = int(head_raw) if isinstance(head_raw, int) else 0
                relation = str(ann.get("deprel") or "")
                lemma_source = str(ann.get("lemma_source") or ann.get("annotation_source") or ("corpus-gold" if gold_lem else "offline-rule"))
                conf_pos = None
                conf_lem = None

            cache_key = (surface, lemma)
            if cache_key not in gloss_cache:
                gloss_cache[cache_key] = _short_gloss(surface, lemma, gold_gloss or None)
            gloss_val, resolved_strongs = gloss_cache[cache_key]
            raw_strongs = gold_strongs or resolved_strongs
            if raw_strongs:
                from ..greek.bible import normalize_strongs_id

                strongs_val = normalize_strongs_id(raw_strongs) or raw_strongs
            else:
                strongs_val = ""

            head_global: int | None = None
            if head_rel_sent > 0 and (head_rel_sent - 1) < len(idxs):
                head_global = idxs[head_rel_sent - 1]

            tok.update(
                {
                    "id": global_i,
                    "text": surface,
                    "lemma": lemma,
                    "lemma_folded": _fold(lemma),
                    "lemma_source": lemma_source,
                    "upos": upos,
                    "xpos": xpos,
                    "xpos_decoded": decode_xpos(xpos),
                    "feats": feats,
                    "robinson": robinson,
                    "robinson_decoded": robinson_decoded,
                    "head_sent": head_rel_sent,
                    "head_global": head_global,
                    "relation": relation,
                    "gloss": gloss_val,
                    "strongs": strongs_val,
                    "confidence_pos": conf_pos,
                    "confidence_lemma": conf_lem,
                    "sentence_index": s_idx,
                    "sentence_token_index": pos_in_s,
                }
            )
            tok.pop("annotations", None)
            sent_toks_out.append(
                {
                    "id": global_i,
                    "index": pos_in_s + 1,
                    "text": surface,
                    "lemma": lemma,
                    "upos": upos,
                    "head": head_rel_sent,
                    "relation": relation,
                }
            )

        sentences.append(
            {
                "index": s_idx,
                "ref": enriched[idxs[0]].get("ref") if idxs else None,
                "text": " ".join(words),
                "token_ids": idxs,
                "has_dependencies": any(t["relation"] for t in sent_toks_out),
                "tokens": sent_toks_out,
            }
        )

    return enriched, sentences


def _build_reader_payload(
    *,
    title: str,
    subtitle: str,
    target: str,
    doc_id: str,
    doc_index: int,
    documents_menu: list[dict[str, Any]],
    raw_tokens: list[dict[str, Any]],
    total_tokens_in_doc: int,
    offset: int,
    max_tokens: int,
    provenance: dict[str, Any],
    context: dict[str, Any],
    doc_translations: list[str] | None = None,
    prefer_gold: bool = False,
    custom_translation: str | None = None,
) -> dict[str, Any]:
    """Assemble the unified Reader JSON payload shared by corpus, Bible, and scratchpad views."""
    enriched, sentences = _enrich_tokens_and_sentences(raw_tokens, prefer_gold=prefer_gold)

    # Resolve parallel translations (custom > verse-level NT/LXX > doc.translations / sample table)
    translation_info: dict[str, Any] = {
        "available": False,
        "source": "",
        "license": "",
        "document_text": "",
        "by_ref": {},
    }
    if custom_translation and custom_translation.strip():
        translation_info = {
            "available": True,
            "source": "User-supplied parallel translation",
            "license": "Local session",
            "document_text": custom_translation.strip(),
            "by_ref": {},
        }
    else:
        refs_in_page = list(dict.fromkeys(str(t["ref"]) for t in enriched if t.get("ref")))
        is_lxx = context.get("testament") == "lxx"
        is_nt = context.get("testament") == "nt"
        v_trans = lookup_verse_translations(refs_in_page, is_lxx=is_lxx) if (is_nt or is_lxx) else None
        if v_trans is not None and v_trans.by_ref:
            translation_info = {
                "available": True,
                "source": v_trans.source,
                "license": v_trans.license,
                "document_text": " ".join(v_trans.by_ref[r] for r in refs_in_page if r in v_trans.by_ref),
                "by_ref": dict(v_trans.by_ref),
            }
        else:
            d_trans = lookup_doc_translation(doc_id, doc_translations)
            if d_trans is not None and d_trans.document_text:
                translation_info = {
                    "available": True,
                    "source": d_trans.source,
                    "license": d_trans.license,
                    "document_text": d_trans.document_text,
                    "by_ref": {},
                }

    # Build display blocks (grouped by verse ref for Biblical texts, or by line/paragraph for literary)
    blocks: list[dict[str, Any]] = []
    if any(t.get("ref") for t in enriched):
        by_ref_order: list[str] = []
        by_ref_toks: dict[str, list[dict[str, Any]]] = {}
        by_ref_mt: dict[str, str] = {}
        for t in enriched:
            r = str(t.get("ref") or doc_id)
            if r not in by_ref_toks:
                by_ref_order.append(r)
                by_ref_toks[r] = []
            by_ref_toks[r].append(t)
            if t.get("mt_ref"):
                by_ref_mt[r] = str(t["mt_ref"])
        for r in by_ref_order:
            blocks.append(
                {
                    "kind": "verse",
                    "ref": r,
                    "mt_ref": by_ref_mt.get(r),
                    "translation": translation_info["by_ref"].get(r, ""),
                    "tokens": by_ref_toks[r],
                }
            )
    else:
        by_line_order: list[int] = []
        by_line_toks: dict[int, list[dict[str, Any]]] = {}
        for t in enriched:
            ln = int(t.get("line_no") or 1)
            if ln not in by_line_toks:
                by_line_order.append(ln)
                by_line_toks[ln] = []
            by_line_toks[ln].append(t)
        for ln in by_line_order:
            blocks.append(
                {
                    "kind": "line",
                    "line_no": ln,
                    "ref": f"L{ln}",
                    "translation": "",
                    "tokens": by_line_toks[ln],
                }
            )

    # Document lexical statistics & clickable lemma frequency index
    pos_counts = Counter(t["upos"] for t in enriched if t.get("upos"))
    lemma_occ: dict[str, list[int]] = {}
    lemma_display: dict[str, str] = {}
    lemma_gloss: dict[str, str] = {}
    lemma_pos: dict[str, str] = {}
    for t in enriched:
        lf = t.get("lemma_folded") or _fold(t.get("lemma") or t["text"])
        if not lf or not any(ch.isalpha() for ch in lf):
            continue
        lemma_occ.setdefault(lf, []).append(t["id"])
        lemma_display.setdefault(lf, t.get("lemma") or t["text"])
        if t.get("gloss") and lf not in lemma_gloss:
            lemma_gloss[lf] = t["gloss"]
        if t.get("upos") and lf not in lemma_pos:
            lemma_pos[lf] = t["upos"]

    top_lemmas = [
        {
            "lemma": lemma_display[lf],
            "folded": lf,
            "count": len(ids),
            "upos": lemma_pos.get(lf, ""),
            "gloss": lemma_gloss.get(lf, ""),
            "token_ids": ids,
        }
        for lf, ids in sorted(lemma_occ.items(), key=lambda kv: (-len(kv[1]), kv[0]))[:60]
    ]

    return {
        "title": title,
        "subtitle": subtitle,
        "target": target,
        "doc_id": doc_id,
        "doc_index": doc_index,
        "documents": documents_menu,
        "pagination": {
            "offset": offset,
            "limit": max_tokens,
            "returned_tokens": len(enriched),
            "total_tokens": total_tokens_in_doc,
            "has_more": (offset + len(enriched)) < total_tokens_in_doc,
        },
        "blocks": blocks,
        "sentences": sentences,
        "translation": translation_info,
        "stats": {
            "tokens": len(enriched),
            "unique_lemmas": len(lemma_occ),
            "sentences": len(sentences),
            "pos_counts": dict(pos_counts.most_common()),
            "top_lemmas": top_lemmas,
            "hapax_count": sum(1 for ids in lemma_occ.values() if len(ids) == 1),
        },
        "provenance": provenance,
        "context": context,
        "engine": engine_status_payload(),
    }


def document_payload(
    target: str,
    *,
    doc_index: int = 0,
    ref: str | None = None,
    edition: str = "nestle1904",
    numbering: str = "lxx",
    max_tokens: int = 500,
    offset: int = 0,
    offline: bool = False,
) -> dict[str, Any]:
    """Load any PyAegean Greek corpus, Bible passage, collection work, or file for the visual reader."""
    import aegean
    from ..greek import bible
    from ..scripts.greek._collections import collection_works, resolve_collection_work

    raw_target = (target or "John 1:1-18").strip()
    safe_limit = max(25, min(int(max_tokens), 1200))
    safe_offset = max(0, int(offset))

    context: dict[str, Any] = {
        "is_biblical": False,
        "testament": None,
        "book": None,
        "ref": ref,
        "edition": edition,
        "numbering": numbering,
        "related_commentaries": [],
        "related_works": [],
        "work_meta": None,
    }

    bible_parsed = _try_parse_bible_target(raw_target, ref, edition, numbering)
    prefer_gold = False

    if bible_parsed is not None:
        testament, book_name, eff_ref, eff_num = bible_parsed
        context["is_biblical"] = True
        context["testament"] = testament
        context["book"] = book_name
        context["ref"] = eff_ref
        context["numbering"] = eff_num
        if testament == "nt":
            nt_ref = _normalize_nt_ref(eff_ref)
            corpus = bible.load_nt(book_name, nt_ref, edition=edition, offline=offline)
            prefer_gold = edition == "nestle1904"
            title = f"{book_name} {eff_ref or ''}".strip()
            subtitle = f"Greek New Testament · {edition}"
        else:
            corpus = bible.load_lxx(
                book_name,
                eff_ref,
                numbering=eff_num,
                interlinear=True,
                offline=offline,
            )
            spec = bible.resolve_lxx_book(book_name)
            title = f"{spec.title} {eff_ref or ''}".strip()
            subtitle = f"Greek Septuagint (Swete LXX{' · Masoretic numbering' if eff_num == 'mt' else ''})"
        # Attach linked patristic commentaries for this Biblical book!
        try:
            comms = bible.patristic_commentaries(book=book_name)
            context["related_commentaries"] = _json_safe(comms[:40])
        except Exception:
            context["related_commentaries"] = []
    else:
        # Try Open Greek collection work metadata lookup for rich classical/patristic context
        work_meta = None
        if raw_target.lower().startswith("ogc") or ":" in raw_target:
            try:
                work_meta = resolve_collection_work(raw_target)
            except Exception:
                work_meta = None
        if work_meta is not None:
            context["work_meta"] = _json_safe(work_meta)
            author = str(work_meta.get("author") or "")
            col_id = str(work_meta.get("collection") or "")
            if author:
                related = [
                    w
                    for w in collection_works(col_id or None, query=author)
                    if w.get("work_id") != work_meta.get("work_id")
                ][:12]
                context["related_works"] = _json_safe(related)

        corpus = aegean.open(raw_target, offline=offline)
        title = raw_target
        subtitle = corpus.provenance.source if corpus.provenance else "Greek Corpus"
        if work_meta is not None:
            title = f"{work_meta.get('author', '')} — {work_meta.get('title', raw_target)}".strip(" —")
            subtitle = f"{work_meta.get('collection', '')} · {work_meta.get('period', '')} · {work_meta.get('license', '')}".strip(" ·")

    docs = list(corpus.documents)
    if not docs:
        raise ValueError(f"no documents found in {raw_target!r}")

    safe_doc_idx = max(0, min(int(doc_index), len(docs) - 1))
    doc = docs[safe_doc_idx]
    docs_menu = [
        {
            "index": i,
            "id": d.id,
            "name": (d.meta.name if d.meta and d.meta.name else d.id),
            "period": (d.meta.period if d.meta and d.meta.period else ""),
            "tokens": len(d.tokens),
        }
        for i, d in enumerate(docs[:200])
    ]

    if doc.meta and doc.meta.name and not context["is_biblical"] and context["work_meta"] is None:
        title = doc.meta.name
    if doc.meta and doc.meta.period:
        context["period"] = doc.meta.period
    if doc.meta and doc.meta.site:
        context["site"] = doc.meta.site

    # Related classical/literary hints for bundled samples (Homer -> Homer Scholia, etc.)
    if not context["is_biblical"] and not context["related_works"]:
        doc_low = f"{doc.id} {title}".lower()
        if "iliad" in doc_low or "homer" in doc_low:
            context["related_works"] = _json_safe(collection_works("classical-greek", query="Homer")[:8])
        elif "herodotus" in doc_low:
            context["related_works"] = _json_safe(collection_works("classical-greek", query="Herodotus")[:8])
        elif "sappho" in doc_low:
            context["related_works"] = _json_safe(collection_works("classical-greek", query="Sappho")[:8])
        elif "heraclitus" in doc_low:
            context["related_works"] = _json_safe(collection_works("classical-greek", query="Plato")[:8])

    all_doc_tokens = list(doc.tokens)
    sliced = all_doc_tokens[safe_offset : safe_offset + safe_limit]
    raw_tokens: list[dict[str, Any]] = []
    for tok in sliced:
        ann = dict(tok.annotations or {})
        raw_tokens.append(
            {
                "text": tok.text,
                "line_no": tok.line_no or 1,
                "ref": ann.get("ref"),
                "mt_ref": ann.get("mt_ref"),
                "annotations": ann,
            }
        )

    prov_dict: dict[str, Any] = {}
    if corpus.provenance is not None:
        prov_dict = {
            "source": corpus.provenance.source,
            "license": corpus.provenance.license,
            "url": corpus.provenance.url,
            "notes": list(corpus.provenance.notes),
        }

    return _build_reader_payload(
        title=title,
        subtitle=subtitle,
        target=raw_target,
        doc_id=doc.id,
        doc_index=safe_doc_idx,
        documents_menu=docs_menu,
        raw_tokens=raw_tokens,
        total_tokens_in_doc=len(all_doc_tokens),
        offset=safe_offset,
        max_tokens=safe_limit,
        provenance=prov_dict,
        context=context,
        doc_translations=list(doc.translations or ()),
        prefer_gold=prefer_gold,
    )


def analyze_text_payload(
    text: str,
    *,
    betacode: bool = False,
    translation: str | None = None,
    title: str = "Custom Greek Passage",
) -> dict[str, Any]:
    """Analyze arbitrary pasted Greek (or Beta Code) text for interactive reading & inspection."""
    from ..greek import betacode_to_unicode, normalize, tokenize

    src = (text or "").strip()
    if not src:
        raise ValueError("text must be non-empty")
    if betacode:
        src = betacode_to_unicode(src)
    src = normalize(src, form="NFC")

    raw_tokens: list[dict[str, Any]] = []
    for line_no, raw_line in enumerate(src.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        for tok in tokenize(line):
            if not any(ch.isalpha() or ch.isdigit() for ch in tok.text):
                continue
            raw_tokens.append(
                {
                    "text": tok.text,
                    "line_no": line_no,
                    "ref": None,
                    "mt_ref": None,
                    "annotations": {},
                }
            )
    if not raw_tokens:
        raise ValueError("no analyzable Greek tokens found in input")

    return _build_reader_payload(
        title=title,
        subtitle="Interactive Greek Workbench · Custom Passage" + (" (from Beta Code)" if betacode else ""),
        target="scratchpad",
        doc_id="scratchpad",
        doc_index=0,
        documents_menu=[{"index": 0, "id": "scratchpad", "name": title, "period": "", "tokens": len(raw_tokens)}],
        raw_tokens=raw_tokens,
        total_tokens_in_doc=len(raw_tokens),
        offset=0,
        max_tokens=len(raw_tokens),
        provenance={"source": "Local scratchpad input", "license": "User text", "url": "", "notes": []},
        context={
            "is_biblical": False,
            "testament": None,
            "book": None,
            "ref": None,
            "related_commentaries": [],
            "related_works": [],
            "input_unicode": src,
        },
        custom_translation=translation,
    )


# ── Deep Word Inspector (Grammar + Lexica + Strong's + Phonology + Study) ────

def analyze_word_payload(
    surface: str,
    *,
    lemma: str | None = None,
    upos: str | None = None,
    xpos: str | None = None,
    feats: str | None = None,
    robinson: str | None = None,
    strongs: str | None = None,
    sentence_text: str | None = None,
    book: str | None = None,
) -> dict[str, Any]:
    """Return deep linguistic, grammatical, lexical, etymological, and concordance data for one word."""
    from ..greek import (
        accent,
        bible,
        inflect,
        lemmatize,
        lexicons,
        morphology,
        normalize,
        pos_tag,
        syllabify,
        to_ipa,
        unicode_to_betacode,
    )

    word = normalize((surface or "").strip(), form="NFC")
    if not word:
        raise ValueError("word must be non-empty")

    resolved_lemma = (lemma or "").strip() or lemmatize(word)
    resolved_upos = (upos or "").strip() or pos_tag(word)

    # 1. Orthography, syllables, accentuation, and 3-period IPA pronunciation
    try:
        acc = accent.accentuation(word)
        accent_dict = _json_safe(acc)
    except Exception:
        accent_dict = {}

    try:
        syls = list(syllabify(word))
    except Exception:
        syls = []

    ipa: dict[str, str] = {}
    for period in ("attic", "koine"):
        try:
            ipa[period] = to_ipa(word, period=period)  # type: ignore[arg-type]
        except Exception:
            ipa[period] = ""

    try:
        betacode = unicode_to_betacode(word)
    except Exception:
        betacode = ""

    # 2. Morphological candidates & paradigm inflections
    try:
        morph_cands = [_json_safe(a) for a in morphology.analyze(word)[:8]]
    except Exception:
        morph_cands = []

    paradigm_forms: list[str] = []
    try:
        forms = inflect(resolved_lemma)
        paradigm_forms = list(dict.fromkeys(forms))[:18]
    except Exception:
        paradigm_forms = []

    # 3. Strong's & Etymological Root Tree
    s_entry = bible.strongs_entry(strongs or resolved_lemma, allow_fetch=False)
    if s_entry is None and _fold(word) != _fold(resolved_lemma):
        s_entry = bible.strongs_entry(word, allow_fetch=False)

    roots_tree: dict[str, Any] | None = None
    if s_entry is not None:
        try:
            roots_tree = _json_safe(bible.strongs_roots(s_entry.strongs))
        except Exception:
            roots_tree = None

    # 4. Multi-dictionary entries across all active hosted lexica + external scholarly links
    lex_entries: list[dict[str, Any]] = []
    for lex_id in lexicons.active_lexica():
        hit = None
        for cand in (resolved_lemma, word):
            if not cand:
                continue
            try:
                hit = lexicons.entry(cand, dictionary=lex_id)
                if hit is not None:
                    break
            except Exception:
                hit = None
        if hit is not None:
            lex_entries.append(_json_safe(hit))

    external_links: list[dict[str, str]] = []
    for label, svc in (
        ("Logeion (LSJ / Middle Liddell / Bailly / DGE)", "logeion"),
        ("Perseus Word Study Tool", "perseus"),
        ("Liddell-Scott-Jones (LSJ)", "lsj"),
    ):
        try:
            url = lexicons.lexicon_link(resolved_lemma, service=svc, lemmatize=False)
            external_links.append({"label": label, "service": svc, "url": url})
        except Exception:
            pass

    # 5. Offline Biblical Word Study summary (NT + LXX distribution)
    study_summary: dict[str, Any] | None = None
    try:
        ws = bible.word_study(s_entry.strongs if s_entry else resolved_lemma, offline=True)
        wsd = ws.to_dict()
        study_summary = {
            "lemma": wsd.get("lemma"),
            "strongs": wsd.get("strongs"),
            "scope": wsd.get("scope"),
            "total_occurrences": wsd.get("total_occurrences", 0),
            "by_book": dict(list((wsd.get("by_book") or {}).items())[:12]),
            "lxx_total": wsd.get("lxx_total", 0),
            "lxx_by_book": dict(list((wsd.get("lxx_by_book") or {}).items())[:12]),
            "sample_occurrences": (wsd.get("occurrences") or [])[:6],
            "sample_lxx_occurrences": (wsd.get("lxx_occurrences") or [])[:6],
        }
    except Exception:
        study_summary = None

    # 6. Decision explanation trace from explain_pipeline if sentence context is given
    explanation: dict[str, Any] | None = None
    if sentence_text and sentence_text.strip():
        try:
            from ..greek import explain_pipeline

            exp_rows = explain_pipeline(sentence_text.strip())
            wf = _fold(word)
            matched = next((r for r in exp_rows if r.token == word or _fold(r.token) == wf), None)
            if matched is not None:
                explanation = {
                    "token": matched.token,
                    "upos": matched.upos,
                    "lemma": matched.lemma,
                    "lemma_source": matched.lemma_source.value,
                    "needs_review": matched.needs_review,
                    "morphology": matched.morphology,
                    "note": matched.note,
                }
        except Exception:
            explanation = None

    # 7. Linked commentaries for book if applicable
    linked_commentaries: list[dict[str, Any]] = []
    if book:
        try:
            linked_commentaries = _json_safe(bible.patristic_commentaries(book=book)[:10])
        except Exception:
            linked_commentaries = []

    return {
        "surface": word,
        "folded": _fold(word),
        "betacode": betacode,
        "lemma": resolved_lemma,
        "upos": resolved_upos,
        "xpos": xpos or "",
        "xpos_decoded": decode_xpos(xpos),
        "feats": feats or "",
        "robinson": robinson or "",
        "robinson_decoded": decode_robinson(robinson),
        "syllables": syls,
        "accent": accent_dict,
        "ipa": ipa,
        "morph_candidates": morph_cands,
        "paradigm_forms": paradigm_forms,
        "strongs": _json_safe(s_entry) if s_entry is not None else None,
        "roots": roots_tree,
        "lexicon_entries": lex_entries,
        "active_lexica": list(lexicons.active_lexica()),
        "available_lexica": [
            {"id": info.id, "name": info.name, "scope": info.scope, "hosted": info.hosted}
            for info in lexicons.lexica()
        ],
        "external_links": external_links,
        "word_study": study_summary,
        "explanation": explanation,
        "linked_commentaries": linked_commentaries,
    }


def _normalize_nt_ref(ref: str | None) -> str | None:
    """Convert natural colon/shorthand NT refs (``1:1-18`` -> ``1.1-1.18``) for ``bible.load_nt``."""
    if ref is None or not ref.strip():
        return None
    s = ref.strip().replace(":", ".")
    if "-" in s:
        lo, _, hi = s.partition("-")
        lo = lo.strip()
        hi = hi.strip()
        if "." in lo and "." not in hi and hi.isdigit():
            chap = lo.split(".", 1)[0]
            return f"{lo}-{chap}.{hi}"
        return f"{lo}-{hi}"
    return s


# ── Biblical Context Tools (Editions, Witnesses, Commentaries, Psalms) ───────

def bible_editions_payload(book: str, ref: str, *, offline: bool = False) -> dict[str, Any]:
    """Compare available Greek NT editions word-by-word for a book & passage."""
    from ..greek import bible

    cmp = bible.compare_editions(book, _normalize_nt_ref(ref) or ref, offline=offline)
    return _json_safe(cmp)  # type: ignore[no-any-return]


def bible_witnesses_payload(book: str, ref: str, *, offline: bool = False) -> dict[str, Any]:
    """Compare 2nd–5th c. Greek NT manuscript witnesses (CNTR MES) for a passage."""
    from ..greek import bible

    rows = bible.compare_witnesses(
        book, _normalize_nt_ref(ref) or ref, expand_nomina_sacra=True, offline=offline
    )
    return {"book": book, "ref": ref, "verses": _json_safe(rows)}


def bible_commentaries_payload(book: str | None = None, kind: str | None = None) -> dict[str, Any]:
    """List patristic commentaries (Catenae, Origen, John Chrysostom, Cyril PG)."""
    from ..greek import bible

    rows = bible.patristic_commentaries(book=book or None, kind=kind or None)
    return {"book": book, "kind": kind, "total": len(rows), "commentaries": _json_safe(rows)}


def bible_commentary_excerpt_payload(
    book: str,
    *,
    work_id: str | None = None,
    query: str | None = None,
    ref: str | None = None,
    limit: int = 5,
) -> dict[str, Any]:
    """Fetch Greek patristic commentary excerpts for a Biblical book/work/term."""
    from ..greek import bible

    excerpts = bible.commentary_excerpt(
        book,
        work_id=work_id or None,
        query=query or None,
        ref=ref or None,
        limit=max(1, min(limit, 15)),
    )
    return {
        "book": book,
        "work_id": work_id,
        "query": query,
        "excerpts": _json_safe(excerpts),
    }


def bible_psalm_payload(number: int, direction: str = "mt_to_lxx") -> dict[str, Any]:
    """Convert Psalm numbers between Masoretic (Hebrew/English) and Septuagint (LXX)."""
    from ..greek import bible

    if direction == "lxx_to_mt":
        target = bible.psalm_lxx_to_mt(int(number))
    else:
        target = bible.psalm_mt_to_lxx(int(number))
    return {"number": int(number), "direction": direction, "mapped": list(target)}


# ── Metrical Scansion, Search, Word Study, Lexicon & Library Management ──────

def scan_lines_payload(lines: list[str], *, meter: str = "hexameter") -> dict[str, Any]:
    """Scan one or more lines of Greek verse across PyAegean's metrical scanners."""
    from ..greek import scan_line

    results: list[dict[str, Any]] = []
    for raw in lines[:40]:
        line = raw.strip()
        if not line:
            continue
        try:
            sc = scan_line(line, meter=meter)
            results.append(
                {
                    "line": line,
                    "meter": sc.meter,
                    "pattern": str(sc),
                    "caesura": sc.caesura,
                    "caesura_index": sc.caesura_index,
                    "ambiguous": sc.ambiguous,
                    "feet": [
                        {
                            "name": f.name,
                            "syllables": list(f.syllables),
                            "quantities": list(f.quantities),
                        }
                        for f in sc.feet
                    ],
                    "error": None,
                }
            )
        except Exception as exc:
            results.append({"line": line, "meter": meter, "pattern": "", "feet": [], "error": str(exc)})
    return {"meter": meter, "results": results}


def search_payload(
    query: str,
    *,
    target: str = "bible",
    limit: int = 30,
    offline: bool = True,
) -> dict[str, Any]:
    """Search Greek NT/LXX or any FTS5-indexed corpus and return jump-ready hits."""
    from ..greek import bible
    from ..search import search_text

    q = (query or "").strip()
    if not q:
        raise ValueError("search query must be non-empty")
    safe_limit = max(1, min(int(limit), 100))

    if target in ("bible", "both", "nt+lxx"):
        hits = bible.search_bible(q, corpus="both", limit=safe_limit, offline=offline)
        nt_names = {b["name"] for b in bible.nt_books()}
        out_hits: list[dict[str, Any]] = []
        for h in hits:
            src_kind = "nt" if h.book in nt_names else "lxx"
            ref_tail = h.ref.split(" ", 1)[1] if " " in h.ref else (h.ref.split(".", 1)[1] if "." in h.ref else h.ref)
            out_hits.append(
                {
                    "source": src_kind,
                    "book": h.book,
                    "ref": h.ref,
                    "open_target": f"{src_kind}:{h.book} {ref_tail}".strip(),
                    "text": h.verse_text,
                    "snippet": h.verse_text,
                    "surface": h.surface,
                    "lemma": h.lemma,
                    "strongs": h.strongs,
                }
            )
        return {
            "query": q,
            "target": "bible",
            "count": len(out_hits),
            "hits": out_hits,
        }

    shits = search_text(q, target, limit=safe_limit, offline=offline)
    return {
        "query": q,
        "target": target,
        "count": len(shits),
        "hits": [
            {
                "source": h.source,
                "doc_id": h.doc_id,
                "ref": h.ref,
                "open_target": target,
                "text": h.text,
                "snippet": h.snippet,
            }
            for h in shits
        ],
    }


def word_study_payload(query: str, *, offline: bool = True) -> dict[str, Any]:
    """Run a unified Strong's + NT + LXX word study for any Greek lemma or Strong's ID."""
    from ..greek import bible

    q = (query or "").strip()
    if not q:
        raise ValueError("query must be non-empty")
    ws = bible.word_study(q, offline=offline)
    return _json_safe(ws.to_dict())  # type: ignore[no-any-return]


def activate_lexicon_payload(lexicon_id: str) -> dict[str, Any]:
    """Activate (fetching to cache if needed) a hosted Greek dictionary or Extended Strong's."""
    from ..greek import bible, lexicons

    lid = (lexicon_id or "").strip().lower()
    if lid in ("strongs", "strongs-greek"):
        count = bible.use_strongs(fetch=True)
        return {
            "id": "strongs-greek",
            "status": "active",
            "entries": count,
            "engine": engine_status_payload(),
        }
    lexicons.use_lexicon(lid)
    return {
        "id": lid,
        "status": "active",
        "engine": engine_status_payload(),
    }


def library_payload() -> dict[str, Any]:
    """Return local PyAegean Library Manager status (datasets and curated packs)."""
    from .. import library

    items = library.list_items()
    packs = library.list_packs()
    return {
        "summary": _json_safe(library.summary()),
        "items": [_json_safe(it) for it in items],
        "packs": [_json_safe(p) for p in packs],
    }


def library_fetch_payload(dataset: str) -> dict[str, Any]:
    """Install a PyAegean dataset or pack into the local cache."""
    from .. import library

    name = (dataset or "").strip()
    if not name:
        raise ValueError("dataset name must be non-empty")
    results = library.install([name])
    return {
        "requested": name,
        "results": [_json_safe(r) for r in results],
        "library": library_payload(),
    }


def export_payload(
    *,
    fmt: str,
    title: str,
    sentences: list[dict[str, Any]],
    blocks: list[dict[str, Any]],
) -> tuple[str, str, str]:
    """Export currently viewed tokens as JSON, CoNLL-U, or CSV.

    Returns ``(content, content_type, filename)``.
    """
    safe_stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", (title or "passage").strip()).strip("_") or "passage"
    kind = (fmt or "json").strip().lower()

    if kind == "conllu":
        lines: list[str] = []
        tok_by_id: dict[int, dict[str, Any]] = {}
        for blk in blocks:
            for t in blk.get("tokens") or []:
                tok_by_id[int(t["id"])] = t
        for s in sentences:
            lines.append(f"# sent_id = {s.get('ref') or ('s' + str(int(s.get('index', 0)) + 1))}")
            lines.append(f"# text = {s.get('text', '')}")
            for i, tid in enumerate(s.get("token_ids") or [], start=1):
                t = tok_by_id.get(int(tid), {})
                misc_parts: list[str] = []
                if t.get("gloss"):
                    misc_parts.append(f"Gloss={t['gloss']}")
                if t.get("strongs"):
                    misc_parts.append(f"Strongs={t['strongs']}")
                misc = "|".join(misc_parts) or "_"
                row = [
                    str(i),
                    str(t.get("text") or "_"),
                    str(t.get("lemma") or "_"),
                    str(t.get("upos") or "_"),
                    str(t.get("xpos") or "_"),
                    str(t.get("feats") or "_"),
                    str(t.get("head_sent") if t.get("head_sent") is not None else "_"),
                    str(t.get("relation") or "_"),
                    "_",
                    misc,
                ]
                lines.append("\t".join(row))
            lines.append("")
        return ("\n".join(lines), "text/plain; charset=utf-8", f"{safe_stem}.conllu")

    if kind == "csv":
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["ref", "token", "lemma", "upos", "xpos", "feats", "robinson", "head", "relation", "strongs", "gloss"])
        for blk in blocks:
            ref = blk.get("ref") or ""
            for t in blk.get("tokens") or []:
                writer.writerow(
                    [
                        t.get("ref") or ref,
                        t.get("text") or "",
                        t.get("lemma") or "",
                        t.get("upos") or "",
                        t.get("xpos") or "",
                        t.get("feats") or "",
                        t.get("robinson") or "",
                        t.get("head_sent") or 0,
                        t.get("relation") or "",
                        t.get("strongs") or "",
                        t.get("gloss") or "",
                    ]
                )
        return (buf.getvalue(), "text/csv; charset=utf-8", f"{safe_stem}.csv")

    payload = json.dumps({"title": title, "blocks": blocks, "sentences": sentences}, indent=2, ensure_ascii=False)
    return (payload, "application/json; charset=utf-8", f"{safe_stem}.json")
