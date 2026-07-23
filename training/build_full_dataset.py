"""Build the leakage-clean dataset for the full joint model (tags + trees + lemmas).

Rows extend parser rows with source identity, compact original-label binding,
and lemma supervision:

    {"file","sid","source","annotation_profile","source_token_ids",
     "source_label_sha256","tokens","upos","xpos","head","deprel","lemma","script"}

``script`` is the per-token **edit-script class**: the Chrupała edit tree transforming
form → lemma (reusing `aegean.greek.lemmatizer`'s pure-Python build_tree/apply_tree;
trees are JSON-native, so the inventory is a list of JSON keys). The inventory keeps
scripts seen ≥ --min-freq times in TRAIN; rarer pairs get label -100 (the lookup or the
identity fallback covers them at inference). Also written, all TRAIN-ONLY (these may ship
with model assets, so they must never see the test folds):

    lemma-scripts.json   the script inventory (id → JSON edit tree)
    lemma-lookup.json    {"form": {exact NFC form → most frequent lemma},
                          "form_upos": {"form|UPOS" → most frequent lemma},
                          "form_lower": {lowercased form → most frequent lemma}}

Usage:  python training/build_full_dataset.py [--out training/data] [--min-freq 2]
"""

from __future__ import annotations

import argparse
import json
import sys
import unicodedata
import xml.etree.ElementTree as ET
from collections import Counter
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
from agdt_ud import copular_flags, upos_from_xpos  # noqa: E402
from agdt_ud_deps import convert_tree  # noqa: E402

from aegean.greek.lemmatizer import _key, build_tree  # noqa: E402
from aegean.greek.documentary import COORDINATORS, coordinator_norm  # noqa: E402
from aegean.greek.treebank import (  # noqa: E402
    _AGDT_FILES,
    _COMMIT as _AGDT_COMMIT,
    _clean_lemma,
    agdt_dir,
)
from build_upos_dataset import split_ids  # noqa: E402
from reproducibility import (  # noqa: E402
    canonical_sha256,
    document_sha256,
    sha256_file as _sha256_file,
    stamp_document,
)


_POLICY_PATH = Path(__file__).with_name("canonicalization-policy-v3.json")
_MANIFEST_FORMAT = "pyaegean-canonical-training-data/1"
_OUTPUT_NAMES = (
    "full-train.jsonl",
    "full-dev.jsonl",
    "lemma-scripts.json",
    "lemma-lookup.json",
    "full-stats.json",
)


def load_label_policy(path: Path = _POLICY_PATH) -> dict[str, Any]:
    """Load the versioned label policy and fail if its source revisions drift."""
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid canonicalization policy {path}: {exc}") from exc
    if not isinstance(value, dict) or value.get("format") != (
        "pyaegean-training-canonicalization-policy/1"
    ):
        raise ValueError("unsupported canonicalization policy")
    sources = value.get("sources")
    if not isinstance(sources, dict) or set(sources) != {"agdt", "gorman", "pedalion"}:
        raise ValueError("canonicalization policy must define exactly three training sources")
    from extra_treebanks import _GORMAN_COMMIT, _PEDALION_COMMIT

    expected = {
        "agdt": _AGDT_COMMIT,
        "gorman": _GORMAN_COMMIT,
        "pedalion": _PEDALION_COMMIT,
    }
    for source, revision in expected.items():
        config = sources[source]
        if not isinstance(config, dict) or config.get("revision") != revision:
            raise ValueError(f"canonicalization policy revision drift for {source}")
        positions = config.get("coordinator_source_pos")
        if (
            not isinstance(positions, list)
            or positions != sorted(set(positions))
            or any(not isinstance(pos, str) or len(pos) != 1 for pos in positions)
        ):
            raise ValueError(f"invalid coordinator source POS policy for {source}")
    return value


LABEL_POLICY = load_label_policy()


def _source_label_sha256(attrs: list[dict[str, Any]]) -> str:
    labels = [
        {
            "form": a.get("source_form", a.get("form", "")),
            "head": a.get("source_head", a.get("head", "")),
            "id": a.get("id", ""),
            "lemma": a.get("source_lemma", a.get("lemma", "")),
            "relation": a.get("source_relation", a.get("relation", "")),
            "xpos": a.get("source_xpos", a.get("xpos", "")),
        }
        for a in attrs
    ]
    return canonical_sha256(labels)


def _canonical_xpos(source: str, form: str, xpos: str, deprel: str) -> str:
    """Apply only the predeclared, structurally confirmed coordinator correction."""
    config = LABEL_POLICY["sources"][source]
    allowed = config["coordinator_source_pos"]
    if (
        deprel == "cc"
        and xpos[:1] in allowed
        and coordinator_norm(form) in COORDINATORS
    ):
        return "c" + xpos[1:]
    return xpos


def _is_nonlexical_mark(form: str) -> bool:
    """True for forms made entirely of punctuation/symbol/whitespace characters."""
    return bool(form.strip()) and all(
        char.isspace() or unicodedata.category(char)[0] in "PS" for char in form
    )


_APOSTROPHE_CHARS = "'’ʼ᾽̓̓"


def _norm(value: str) -> str:
    """Accent/breathing-stripped lowercase key with trailing apostrophes removed."""
    decomposed = unicodedata.normalize("NFD", value)
    stripped = "".join(char for char in decomposed if not unicodedata.combining(char))
    return stripped.lower().rstrip(_APOSTROPHE_CHARS)


def _nfc(value: str) -> str:
    return unicodedata.normalize("NFC", value)


# The Smyth §2163 closed coordinator set, keyed by normalized LEMMA (the surface-keyed
# lexicon in aegean.greek.documentary covers the same set for the inference-side lever).
_COORDINATOR_LEMMAS = frozenset({
    "και", "δε", "τε", "αλλα", "η", "ουδε", "ουτε", "μηδε", "μητε", "ηδε",
    "ειτε", "αταρ", "αυταρ",
})
_COORDINATOR_RELATION_BASES = frozenset({"COORD", "AuxY", "AuxZ"})

_DEI_IMPERSONAL_FORMS = frozenset(
    _nfc(form)
    for form in (
        "δεῖ", "ἔδει", "δέῃ", "δέοι", "δεήσει", "δεήσῃ", "δεήσοι",
        "ἐδέησε", "ἐδέησεν", "δεῖν", "δεήσειν",
    )
)
_DEI_QUANTITY_LEMMAS = frozenset({"πολυς", "ολιγος", "μικρος", "τοσουτος"})
_EN_SURFACES = frozenset(_nfc(form) for form in ("ἐν", "Ἐν", "ἔν"))


def _relation_base(relation: str) -> str:
    return relation.split("_", 1)[0]


def _coordinator_xpos_pass(
    source: str,
    attrs: list[dict[str, Any]],
    xpos_list: list[str],
    tree: list[tuple[int, str]],
) -> list[str]:
    """Coordinator POS completion: rewrite the closed set's XPOS initial by lemma.

    Extends the surface-keyed cc rule with lemma-keyed coverage (crasis, elision,
    epic variants) and resolves the Pedalion particle class stuck at the unknown
    fallback. Non-cc coordinator readings keep their source labels: the pinned
    evaluation folds disagree with each other on that convention.
    """
    lemmas = [_norm(str(a.get("lemma", "") or a.get("form", ""))) for a in attrs]
    result = list(xpos_list)
    for index, (attr, xpos, (_head, deprel)) in enumerate(zip(attrs, xpos_list, tree)):
        if xpos[:1] == "c":
            continue
        lemma = lemmas[index]
        if lemma not in _COORDINATOR_LEMMAS:
            continue
        # 1. Any closed-set lemma the conversion marked cc is a coordinator.
        if deprel == "cc":
            result[index] = "c" + xpos[1:]
            continue
        # 2. Pedalion's particle POS falls through to the unknown fallback; for
        #    non-cc uses the coordination-family source relations license the
        #    adverb POS. Non-cc coordinator readings are deliberately NOT
        #    canonicalized further: the pinned evaluation folds disagree with
        #    each other on that convention, so the mixed source labels stand.
        if (
            source == "pedalion"
            and xpos[:1] == "b"
            and _relation_base(str(attr.get("source_relation", attr.get("relation", ""))))
            in _COORDINATOR_RELATION_BASES
        ):
            result[index] = "d" + xpos[1:]
    return result


def _copula_upos_pass(
    attrs: list[dict[str, Any]],
    upos_list: list[str],
    tree: list[tuple[int, str]],
) -> list[str]:
    """A cop-attached εἰμί is AUX; (VERB, cop) is contradictory under UD v2."""
    result = list(upos_list)
    for index, (attr, upos, (_head, deprel)) in enumerate(zip(attrs, upos_list, tree)):
        if (
            upos == "VERB"
            and deprel == "cop"
            and _norm(str(attr.get("lemma", ""))) == "ειμι"
        ):
            result[index] = "AUX"
    return result


def _lemma_pass(
    attrs: list[dict[str, Any]],
    xpos_list: list[str],
    tree: list[tuple[int, str]],
) -> list[str]:
    """Sentence-level lemma canonicalization (policy shared rules)."""
    children: dict[int, list[int]] = {}
    for index, (head, _deprel) in enumerate(tree):
        children.setdefault(head, []).append(index)
    result: list[str] = []
    for index, (attr, xpos) in enumerate(zip(attrs, xpos_list)):
        form = str(attr.get("form", ""))
        lemma = _canonical_lemma(form, str(attr.get("lemma", "") or form))
        nfc_form = _nfc(form)
        nfc_lemma = _nfc(lemma)
        # ἐν is never lemma εἰς: the class is a verified annotation defect.
        if nfc_lemma == _nfc("εἰς") and nfc_form in _EN_SURFACES:
            lemma = _nfc("ἐν")
        # Suppletive aorist: εἰπ- verb forms belong to εἶπον, not λέγω.
        elif (
            nfc_lemma == _nfc("λέγω")
            and _norm(form).startswith("ειπ")
            and xpos[:1] == "v"
            and xpos[3:4] == "a"
        ):
            lemma = _nfc("εἶπον")
        # Impersonal δεῖ with positive structural evidence of the frame.
        elif nfc_lemma == _nfc("δέω") and nfc_form in _DEI_IMPERSONAL_FORMS:
            if xpos[1:2] != "2" and xpos[5:6] not in ("m", "p", "e"):
                child_indexes = children.get(index + 1, [])
                has_clausal = any(
                    tree[j][1] in ("csubj", "ccomp", "xcomp") for j in child_indexes
                )
                genitive_children = [
                    j for j in child_indexes if xpos_list[j][7:8] == "g"
                ]
                quantity = any(
                    _norm(str(attrs[j].get("lemma", ""))) in _DEI_QUANTITY_LEMMAS
                    for j in genitive_children
                ) or (
                    index >= 1
                    and _norm(str(attrs[index - 1].get("form", "")))
                    in ("πολλου", "ολιγου", "μικρου", "τοσουτου")
                )
                has_nominative_subject = any(
                    tree[j][1].startswith("nsubj") and xpos_list[j][7:8] == "n"
                    for j in child_indexes
                )
                if (
                    (has_clausal or genitive_children)
                    and not quantity
                    and not has_nominative_subject
                ):
                    lemma = _nfc("δεῖ")
        result.append(lemma)
    return result


def _canonical_lemma(form: str, lemma: str) -> str:
    """Apply the policy's lemma canonicalizations (punctuation placeholder, grave accent)."""
    if lemma == "punc" and _is_nonlexical_mark(form):
        return form
    decomposed = unicodedata.normalize("NFD", lemma)
    # Combining grave (U+0300) becomes combining acute (U+0301).
    if "̀" in decomposed:
        return unicodedata.normalize("NFC", decomposed.replace("̀", "́"))
    return lemma


def _record_audit(
    audit: dict[str, Any],
    *,
    source: str,
    attrs: list[dict[str, Any]],
    source_upos: list[str],
    canonical_upos: list[str],
    canonical_xpos: list[str],
    canonical_lemma: list[str],
    tree: list[tuple[int, str]],
) -> None:
    entry = audit.setdefault(
        source,
        {
            "sentences": 0,
            "tokens": 0,
            "head_changes": 0,
            "deprel_mappings": Counter(),
            "upos_changes": Counter(),
            "xpos_changes": Counter(),
            "lemma_changes": Counter(),
        },
    )
    entry["sentences"] += 1
    entry["tokens"] += len(attrs)
    id_to_pos = {str(a.get("id", "")): index + 1 for index, a in enumerate(attrs)}
    for attr, old_upos, new_upos, new_xpos, new_lemma, (new_head, new_deprel) in zip(
        attrs, source_upos, canonical_upos, canonical_xpos, canonical_lemma, tree
    ):
        old_relation = str(attr.get("source_relation", attr.get("relation", "")))
        old_xpos = str(attr.get("source_xpos", attr.get("xpos", "")))
        old_lemma = str(attr.get("lemma", "") or attr.get("form", ""))
        effective_head = id_to_pos.get(str(attr.get("head", "")), 0)
        if effective_head != new_head:
            entry["head_changes"] += 1
        entry["deprel_mappings"][(old_relation, new_deprel)] += 1
        if old_upos != new_upos:
            entry["upos_changes"][(old_upos, new_upos)] += 1
        if old_xpos != new_xpos:
            entry["xpos_changes"][(old_xpos, new_xpos)] += 1
        if old_lemma != new_lemma:
            entry["lemma_changes"][(old_lemma, new_lemma)] += 1


def _finalize_audit(audit: Mapping[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for source in sorted(audit):
        raw = audit[source]
        result[source] = {
            "sentences": raw["sentences"],
            "tokens": raw["tokens"],
            "head_changes": raw["head_changes"],
            "deprel_mappings": {
                f"{old or '<empty>'}->{new}": count
                for (old, new), count in sorted(raw["deprel_mappings"].items())
            },
            "upos_changes": {
                f"{old}->{new}": count
                for (old, new), count in sorted(raw["upos_changes"].items())
            },
            "xpos_changes": {
                f"{old or '<empty>'}->{new}": count
                for (old, new), count in sorted(raw["xpos_changes"].items())
            },
            "lemma_changes": {
                f"{old or '<empty>'}->{new}": count
                for (old, new), count in sorted(raw["lemma_changes"].items())
            },
        }
    return result


def row_from_attrs(
    file: str,
    sid: str,
    attrs: list[dict[str, Any]],
    *,
    source: str = "agdt",
    audit: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Convert one sentence's AGDT-schema attrs into a full dataset row (labels via the
    validated converters)."""
    if source not in LABEL_POLICY["sources"]:
        raise ValueError(f"unknown training source {source!r}")
    flags = copular_flags(attrs)
    tree = convert_tree(attrs)
    normalized_xpos = [str(a.get("xpos", "")).lower().ljust(9, "-")[:9] for a in attrs]
    source_upos = [
        upos_from_xpos(
            str(a.get("form", "")),
            xpos,
            lemma=str(a.get("lemma", "")),
            has_pnom_child=flag,
            own_relation=str(a.get("relation", "")),
        )
        for a, xpos, flag in zip(attrs, normalized_xpos, flags)
    ]
    canonical_xpos = [
        _canonical_xpos(source, str(a.get("form", "")), xpos, deprel)
        for a, xpos, (_head, deprel) in zip(attrs, normalized_xpos, tree)
    ]
    canonical_xpos = _coordinator_xpos_pass(source, attrs, canonical_xpos, tree)
    canonical_upos = [
        upos_from_xpos(
            str(a.get("form", "")),
            xpos,
            lemma=str(a.get("lemma", "")),
            has_pnom_child=flag,
            own_relation=str(a.get("relation", "")),
        )
        for a, xpos, flag in zip(attrs, canonical_xpos, flags)
    ]
    canonical_upos = _copula_upos_pass(attrs, canonical_upos, tree)
    canonical_lemma = _lemma_pass(attrs, canonical_xpos, tree)
    if audit is not None:
        _record_audit(
            audit,
            source=source,
            attrs=attrs,
            source_upos=source_upos,
            canonical_upos=canonical_upos,
            canonical_xpos=canonical_xpos,
            canonical_lemma=canonical_lemma,
            tree=tree,
        )
    return {
        "file": file,
        "sid": sid,
        "source": source,
        "annotation_profile": LABEL_POLICY["sources"][source]["annotation_profile"],
        "source_token_ids": [str(a.get("id", "")) for a in attrs],
        "source_label_sha256": _source_label_sha256(attrs),
        "tokens": [a["form"] for a in attrs],
        "upos": canonical_upos,
        "xpos": canonical_xpos,
        "head": [h for h, _r in tree],
        "deprel": [r for _h, r in tree],
        "lemma": canonical_lemma,
    }


def load_agdt_full(
    base: Path,
    *,
    paths: Iterable[Path] | None = None,
    skip_ids: set[tuple[str, str]] | None = None,
    audit: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Load canonical AGDT rows, optionally skipping protected sentence identities early."""
    rows: list[dict[str, Any]] = []
    skipped = skip_ids or set()
    selected = sorted(paths) if paths is not None else sorted(base.glob("*.tb.xml"))
    for fp in selected:
        for _ev, sent in ET.iterparse(str(fp), events=("end",)):
            if sent.tag.rsplit("}", 1)[-1] != "sentence":
                continue
            words = [w for w in sent if w.tag.rsplit("}", 1)[-1] == "word" and w.get("form")]
            sid = sent.get("id") or ""
            if sid and words and (fp.name, sid) not in skipped:
                attrs = [
                    {"id": w.get("id") or "", "head": w.get("head") or "",
                     "relation": w.get("relation") or "",
                     "form": unicodedata.normalize("NFC", w.get("form") or ""),
                     "lemma": _clean_lemma(w.get("lemma") or ""),
                     "xpos": (w.get("postag") or "").ljust(9, "-")[:9],
                     "source_head": w.get("head") or "0",
                     "source_relation": w.get("relation") or "",
                     "source_xpos": w.get("postag") or "",
                     "source_lemma": w.get("lemma") or ""}
                    for w in words
                ]
                rows.append(row_from_attrs(fp.name, sid, attrs, source="agdt", audit=audit))
            sent.clear()
    return rows


def _haspunct(form: str) -> bool:
    return not any(ch.isalpha() or ch.isdigit() for ch in form)


def _overlap_keys_ud(splits: tuple[str, ...]) -> set[tuple[str, ...]]:
    """Form-tuple keys (full + punctuation-stripped) of the UD-Perseus fold sentences."""
    from aegean.greek.ud import load_conllu, ud_path

    keys: set[tuple[str, ...]] = set()
    for split in splits:
        for s in load_conllu(ud_path("perseus", split)):
            forms = tuple(unicodedata.normalize("NFC", t.form) for t in s.tokens)
            keys.add(forms)
            keys.add(tuple(f for f in forms if not _haspunct(f)))
    return keys


def _overlap_keys_proiel() -> set[tuple[str, ...]]:
    """Form-tuple keys of the PROIEL evaluation sentences (PROIEL has no punct tokens)."""
    from aegean.greek.proiel import load_proiel_gold

    return {tuple(t.form for t in sent) for sent in load_proiel_gold()}


def load_extras_clean(
    ud_keys: set[tuple[str, ...]],
    proiel_keys: set[tuple[str, ...]],
    *,
    paths_by_source: Mapping[str, list[Path]] | None = None,
    transform_audit: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, int]]]:
    """Gorman + Pedalion rows with overlap-matched sentences excluded (train-only data)."""
    from extra_treebanks import load_extra

    rows: list[dict[str, Any]] = []
    overlap_audit = {
        "gorman": {"kept": 0, "excluded": 0},
        "pedalion": {"kept": 0, "excluded": 0},
    }
    for source in ("gorman", "pedalion"):
        selected = None if paths_by_source is None else paths_by_source[source]
        for r in load_extra(source, paths=selected):
            forms = tuple(a["form"] for a in r["attrs"])
            stripped = tuple(f for f in forms if not _haspunct(f))
            if forms in ud_keys or stripped in ud_keys or stripped in proiel_keys:
                overlap_audit[source]["excluded"] += 1
                continue
            overlap_audit[source]["kept"] += 1
            rows.append(
                row_from_attrs(
                    r["file"],
                    r["sid"],
                    r["attrs"],
                    source=source,
                    audit=transform_audit,
                )
            )
    return rows, overlap_audit


def validate_split_separation(
    train: list[dict[str, Any]],
    dev: list[dict[str, Any]],
    *,
    dev_ids: set[tuple[str, str]],
    test_ids: set[tuple[str, str]],
) -> None:
    """Fail closed on duplicate, crossed, incomplete, or protected split identities."""
    train_ids = [(str(r["file"]), str(r["sid"])) for r in train]
    dev_rows = [(str(r["file"]), str(r["sid"])) for r in dev]
    if len(train_ids) != len(set(train_ids)):
        raise ValueError("training split contains duplicate sentence identities")
    if len(dev_rows) != len(set(dev_rows)):
        raise ValueError("development split contains duplicate sentence identities")
    if set(train_ids) & set(dev_rows):
        raise ValueError("training and development splits overlap")
    agdt_train = {
        identity for identity, row in zip(train_ids, train) if row.get("source") == "agdt"
    }
    if agdt_train & (dev_ids | test_ids):
        raise ValueError("protected AGDT development/test identity entered training")
    if any(row.get("source") != "agdt" for row in dev):
        raise ValueError("development split must contain only the frozen AGDT development rows")
    if set(dev_rows) != dev_ids:
        raise ValueError("development split differs from the frozen AGDT development identities")
    if set(dev_rows) & test_ids:
        raise ValueError("protected AGDT test identity entered development")


def _file_record(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"source/output file is missing: {path}")
    return {"path": path.name, "bytes": path.stat().st_size, "sha256": _sha256_file(path)}


def _source_records(paths_by_source: Mapping[str, list[Path]]) -> dict[str, Any]:
    records: dict[str, Any] = {}
    for source in sorted(paths_by_source):
        config = LABEL_POLICY["sources"][source]
        paths = sorted(paths_by_source[source], key=lambda path: path.name)
        if len({path.name for path in paths}) != len(paths):
            raise ValueError(f"duplicate source filenames for {source}")
        records[source] = {
            "revision": config["revision"],
            "license": config["license"],
            "annotation_profile": config["annotation_profile"],
            "files": [_file_record(path) for path in paths],
        }
    return records


def build_training_manifest(
    *,
    output_dir: Path,
    source_paths: Mapping[str, list[Path]],
    train: list[dict[str, Any]],
    dev: list[dict[str, Any]],
    dev_ids: set[tuple[str, str]],
    test_ids: set[tuple[str, str]],
    extras_audit: Mapping[str, Any] | None,
    transform_audit: Mapping[str, Any],
) -> dict[str, Any]:
    train_sources = Counter(str(row["source"]) for row in train)
    document: dict[str, Any] = {
        "format": _MANIFEST_FORMAT,
        "policy": {
            "path": _POLICY_PATH.name,
            "policy_id": LABEL_POLICY["policy_id"],
            "hash_mode": "canonical-json",
            "sha256": canonical_sha256(LABEL_POLICY),
        },
        "sources": _source_records(source_paths),
        "outputs": [_file_record(output_dir / name) for name in _OUTPUT_NAMES],
        "splits": {
            "train_sentences": len(train),
            "development_sentences": len(dev),
            "train_source_sentences": dict(sorted(train_sources.items())),
        },
        "leakage": {
            "agdt_development_id_count": len(dev_ids),
            "agdt_test_id_count": len(test_ids),
            "protected_test_rows_emitted": 0,
            "extra_sentence_overlap_audit": extras_audit,
        },
        "transformations": _finalize_audit(transform_audit),
    }
    return stamp_document(document, "manifest_sha256")


def verify_training_manifest(path: Path) -> dict[str, Any]:
    """Verify the self-digest and every generated-output record."""
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid training-data manifest {path}: {exc}") from exc
    if not isinstance(value, dict) or value.get("format") != _MANIFEST_FORMAT:
        raise ValueError("unsupported training-data manifest")
    recorded = value.get("manifest_sha256")
    actual = document_sha256(value, "manifest_sha256")
    if recorded != actual:
        raise ValueError("training-data manifest digest mismatch")
    expected_policy = {
        "path": _POLICY_PATH.name,
        "policy_id": LABEL_POLICY["policy_id"],
        "hash_mode": "canonical-json",
        "sha256": canonical_sha256(LABEL_POLICY),
    }
    if value.get("policy") != expected_policy:
        raise ValueError("training-data manifest policy binding mismatch")
    outputs = value.get("outputs")
    if not isinstance(outputs, list):
        raise ValueError("training-data manifest outputs must be an array")
    output_paths: list[str] = []
    for record in outputs:
        if not isinstance(record, dict) or set(record) != {"path", "bytes", "sha256"}:
            raise ValueError("invalid generated-output record")
        output_path = record["path"]
        if not isinstance(output_path, str) or Path(output_path).name != output_path:
            raise ValueError("invalid generated-output path")
        output_paths.append(output_path)
        candidate = path.parent / output_path
        if _file_record(candidate) != record:
            raise ValueError(f"generated-output record mismatch for {candidate.name}")
    if sorted(output_paths) != sorted(_OUTPUT_NAMES):
        raise ValueError("training-data manifest does not list the exact generated outputs")
    return value


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Build the leakage-clean full joint-model training dataset."
    )
    ap.add_argument("--out", default=str(Path(__file__).parent / "data"))
    ap.add_argument("--min-freq", type=int, default=2)
    ap.add_argument("--with-extras", action="store_true",
                    help="Add Gorman + Pedalion to TRAIN (overlap-audited "
                         "against UD-Perseus dev/test and PROIEL; dev unchanged)")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    print("fetching/locating AGDT + UD folds (cache) ...", flush=True)
    base = agdt_dir(download=True)
    dev_ids = split_ids("dev")
    test_ids = split_ids("test")
    agdt_paths = [base / name for name in _AGDT_FILES]
    missing = [path.name for path in agdt_paths if not path.is_file()]
    if missing:
        raise SystemExit(f"pinned AGDT source files are missing: {missing}")
    source_paths: dict[str, list[Path]] = {"agdt": agdt_paths}
    transform_audit: dict[str, Any] = {}
    # Skip protected test identities before token labels are read or canonicalized.
    rows = load_agdt_full(
        base,
        paths=agdt_paths,
        skip_ids=test_ids,
        audit=transform_audit,
    )
    train = [r for r in rows if (r["file"], r["sid"]) not in dev_ids]
    dev = [r for r in rows if (r["file"], r["sid"]) in dev_ids]

    extras_audit = None
    if args.with_extras:
        from extra_treebanks import fetch_extra

        print("fetching/auditing Gorman + Pedalion (overlap vs UD dev/test + PROIEL) ...",
              flush=True)
        extra_paths = {source: fetch_extra(source) for source in ("gorman", "pedalion")}
        source_paths.update(extra_paths)
        ud_keys = _overlap_keys_ud(("dev", "test"))
        proiel_keys = _overlap_keys_proiel()
        extra_rows, extras_audit = load_extras_clean(
            ud_keys,
            proiel_keys,
            paths_by_source=extra_paths,
            transform_audit=transform_audit,
        )
        train = train + extra_rows
        print(f"extras merged into train: {extras_audit}", flush=True)

    validate_split_separation(
        train,
        dev,
        dev_ids=dev_ids,
        test_ids=test_ids,
    )

    # --- the edit-script inventory + train-only lookups (TRAIN data only) ----------
    script_counts: Counter[str] = Counter()
    form_lemma: dict[str, Counter[str]] = {}
    form_upos_lemma: dict[str, Counter[str]] = {}
    lower_lemma: dict[str, Counter[str]] = {}
    for r in train:
        for form, upos, lemma in zip(r["tokens"], r["upos"], r["lemma"]):
            script_counts[_key(build_tree(form, lemma))] += 1
            form_lemma.setdefault(form, Counter())[lemma] += 1
            form_upos_lemma.setdefault(f"{form}|{upos}", Counter())[lemma] += 1
            lower_lemma.setdefault(form.lower(), Counter())[lemma] += 1
    scripts = [k for k, c in script_counts.most_common() if c >= args.min_freq]
    script_id = {k: i for i, k in enumerate(scripts)}

    def label(form: str, lemma: str) -> int:
        return script_id.get(_key(build_tree(form, lemma)), -100)

    for split_rows in (train, dev):
        for r in split_rows:
            r["script"] = [label(f, le) for f, le in zip(r["tokens"], r["lemma"])]

    for name, data in (("full-train.jsonl", train), ("full-dev.jsonl", dev)):
        with open(out / name, "w", encoding="utf-8", newline="\n") as f:
            for r in data:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    (out / "lemma-scripts.json").write_text(json.dumps(scripts, ensure_ascii=False),
                                            encoding="utf-8", newline="\n")
    (out / "lemma-lookup.json").write_text(json.dumps({
        "form": {f: c.most_common(1)[0][0] for f, c in form_lemma.items()},
        "form_upos": {k: c.most_common(1)[0][0] for k, c in form_upos_lemma.items()},
        "form_lower": {f: c.most_common(1)[0][0] for f, c in lower_lemma.items()},
    }, ensure_ascii=False), encoding="utf-8", newline="\n")

    n_train = sum(len(r["tokens"]) for r in train)
    cov_train = sum(1 for r in train for s in r["script"] if s != -100)
    n_dev = sum(len(r["tokens"]) for r in dev)
    cov_dev = sum(1 for r in dev for s in r["script"] if s != -100)
    stats = {
        "format": "pyaegean-full-training-stats/1",
        "canonicalization_policy": LABEL_POLICY["policy_id"],
        "with_extras": bool(args.with_extras),
        "extras_audit": extras_audit,
        "train_sentences": len(train), "dev_sentences": len(dev),
        "train_tokens": n_train, "dev_tokens": n_dev,
        "n_scripts": len(scripts), "min_freq": args.min_freq,
        "script_coverage_train": round(cov_train / n_train, 4),
        "script_coverage_dev": round(cov_dev / n_dev, 4),
        # label inventories come from the ACTUAL dataset (train incl. any extras + dev),
        # never from the AGDT rows alone because extras can introduce their own
        # characters and labels.
        "upos_labels": sorted({u for r in train + dev for u in r["upos"]}),
        "deprels": sorted({d for r in train + dev for d in r["deprel"]}),
        "xpos_position_chars": [
            sorted({x[i] for r in train + dev for x in r["xpos"]}) for i in range(9)
        ],
        "protocol": "Parser rows + lemma supervision + edit-script classes; "
                    "inventory and lookups are train-only. See docs/benchmarks.md.",
    }
    (out / "full-stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=1),
                                           encoding="utf-8", newline="\n")
    manifest = build_training_manifest(
        output_dir=out,
        source_paths=source_paths,
        train=train,
        dev=dev,
        dev_ids=dev_ids,
        test_ids=test_ids,
        extras_audit=extras_audit,
        transform_audit=transform_audit,
    )
    manifest_path = out / "training-data-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    verify_training_manifest(manifest_path)
    print(json.dumps({k: v for k, v in stats.items() if k != "xpos_position_chars"},
                     ensure_ascii=False, indent=1))
    print(f"training-data manifest: {manifest['manifest_sha256']}")


if __name__ == "__main__":
    main()
