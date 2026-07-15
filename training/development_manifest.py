"""Strict, deterministic development-source manifests for Greek model experiments.

This module deliberately has no model or third-party data dependencies beyond the
project's existing CoNLL-U reader.  It turns the two eligible development sources
into an auditable, document-disjoint manifest.  Locked folds are read only far
enough to establish stable identities and exclusion sets; their linguistic rows are
never emitted as development items.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import tempfile
import unicodedata
from collections import Counter, defaultdict
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from aegean.greek.ud import UDSentence, UDToken, load_conllu

__all__ = [
    "MANIFEST_FORMAT",
    "MAX_DOCUMENT_BYTES",
    "ManifestError",
    "canonical_json",
    "document_sha256",
    "stamp_document",
    "verify_document",
    "load_document",
    "write_document",
    "verify_manifest",
    "build_manifest",
]

MANIFEST_FORMAT = "pyaegean-development-manifest/1"
# JSON contracts are intentionally bounded.  CoNLL-U inputs are streamed by the
# existing parser; this limit protects only the persistent contract reader/writer.
MAX_DOCUMENT_BYTES = 32 * 1024 * 1024
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_DIGEST_FIELD = "manifest_sha256"
_UNAVAILABLE = {
    "tragedy": "no eligible document-disjoint tragedy/poetry development source",
    "nt_koine": "New Testament/Koine source is locked or training-seen",
    "byzantine": "DBBE/Byzantine source is locked or training-seen",
    "diplomatic": "PapyGreek diplomatic/original source is locked or training-seen",
}
_LENGTH_BINS: tuple[tuple[str, int, int | None], ...] = (
    ("1-5", 1, 5),
    ("6-10", 6, 10),
    ("11-20", 11, 20),
    ("21-40", 21, 40),
    ("41+", 41, None),
)
_FREQUENCY_BINS: tuple[tuple[str, int, int | None], ...] = (
    ("1", 1, 1),
    ("2-5", 2, 5),
    ("6-50", 6, 50),
    ("51+", 51, None),
)


class ManifestError(ValueError):
    """Raised for malformed, ambiguous, leaked, or tampered documents."""


def _strict_jsonable(value: Any, path: str = "$", *, _seen: set[int] | None = None) -> None:
    """Reject values that ``json.dumps`` would silently coerce or serialize oddly."""

    if _seen is None:
        _seen = set()
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ManifestError(f"{path} contains a non-finite number")
        return
    ident = id(value)
    if ident in _seen:
        raise ManifestError(f"{path} contains a recursive value")
    _seen.add(ident)
    try:
        if isinstance(value, Mapping):
            for key, child in value.items():
                if not isinstance(key, str):
                    raise ManifestError(f"{path} has a non-string object key")
                _strict_jsonable(child, f"{path}.{key}", _seen=_seen)
        elif isinstance(value, (list, tuple)):
            for index, child in enumerate(value):
                _strict_jsonable(child, f"{path}[{index}]", _seen=_seen)
        else:
            raise ManifestError(f"{path} contains unsupported JSON type {type(value).__name__}")
    finally:
        _seen.remove(ident)


def canonical_json(value: Any) -> str:
    """Serialize strict canonical UTF-8 JSON used for every content digest."""

    _strict_jsonable(value)
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:  # defensive: the preflight above is stricter
        raise ManifestError(f"value is not canonical JSON: {exc}") from exc


def document_sha256(document: Mapping[str, Any], digest_field: str = _DIGEST_FIELD) -> str:
    """Return the SHA-256 of a document after removing its self-digest field."""

    if not isinstance(document, Mapping):
        raise ManifestError("document must be an object")
    if not isinstance(digest_field, str) or not digest_field:
        raise ManifestError("digest_field must be a non-empty string")
    payload = dict(document)
    payload.pop(digest_field, None)
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def stamp_document(document: Mapping[str, Any], digest_field: str = _DIGEST_FIELD) -> dict[str, Any]:
    """Return a fresh mapping with a recomputed top-level digest."""

    if not isinstance(document, Mapping):
        raise ManifestError("document must be an object")
    stamped = dict(document)
    stamped.pop(digest_field, None)
    stamped[digest_field] = document_sha256(stamped, digest_field)
    return stamped


def _digest_field(document: Mapping[str, Any]) -> str:
    candidates = [key for key in document if key.endswith("_sha256")]
    if _DIGEST_FIELD in document:
        return _DIGEST_FIELD
    if len(candidates) == 1:
        return candidates[0]
    raise ManifestError("document must contain exactly one recognizable self-digest field")


def verify_document(
    document: Mapping[str, Any] | str | os.PathLike[str],
    digest_field: str | None = None,
) -> dict[str, Any]:
    """Validate and return a strict document, including its self-digest.

    A mapping is copied; a path is loaded with :func:`load_document`.  Returning a
    copy makes this function convenient in a complete write/read/verify journey
    while still raising on every mismatch.
    """

    if isinstance(document, (str, os.PathLike)):
        loaded = load_document(Path(document), verify=False)
    elif isinstance(document, Mapping):
        loaded = dict(document)
    else:
        raise ManifestError("document must be an object or path")
    field = digest_field or _digest_field(loaded)
    recorded = loaded.get(field)
    if not isinstance(recorded, str) or not _SHA256.fullmatch(recorded):
        raise ManifestError(f"invalid {field} digest")
    actual = document_sha256(loaded, field)
    if actual != recorded:
        raise ManifestError(f"{field} mismatch: expected {recorded}, recomputed {actual}")
    return dict(loaded)


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ManifestError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _parse_strict_json(text: str, *, context: str) -> Any:
    try:
        return json.loads(
            text,
            object_pairs_hook=_reject_duplicate_pairs,
            parse_constant=lambda value: (_ for _ in ()).throw(
                ManifestError(f"non-finite JSON constant {value!r} in {context}")
            ),
        )
    except ManifestError:
        raise
    except json.JSONDecodeError as exc:
        raise ManifestError(f"invalid JSON in {context}: {exc}") from exc


def load_document(
    path: str | os.PathLike[str],
    *,
    verify: bool = True,
    digest_field: str | None = None,
) -> dict[str, Any]:
    """Read a bounded UTF-8 canonical JSON document with duplicate-key rejection."""

    target = Path(path)
    try:
        size = target.stat().st_size
    except OSError as exc:
        raise ManifestError(f"cannot stat document {target}: {exc}") from exc
    if size > MAX_DOCUMENT_BYTES:
        raise ManifestError(f"document exceeds {MAX_DOCUMENT_BYTES} bytes")
    try:
        raw = target.read_bytes()
        text = raw.decode("utf-8")
        value = _parse_strict_json(text, context=str(target))
    except ManifestError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ManifestError(f"invalid JSON document {target}: {exc}") from exc
    if not isinstance(value, dict):
        raise ManifestError("document root must be a JSON object")
    if len(raw) > MAX_DOCUMENT_BYTES:
        raise ManifestError(f"document exceeds {MAX_DOCUMENT_BYTES} bytes")
    canonical = canonical_json(value).encode("utf-8")
    # A single terminal LF is the conventional on-disk representation emitted by
    # :func:`write_document`; whitespace elsewhere is never accepted.
    if raw != canonical and raw != canonical + b"\n":
        raise ManifestError("document is not canonical UTF-8 JSON")
    if verify:
        return verify_document(value, digest_field)
    return value


def write_document(
    document: Mapping[str, Any],
    path: str | os.PathLike[str],
    *,
    digest_field: str | None = None,
) -> Path:
    """Atomically write a bounded canonical document after verifying its digest."""

    checked = verify_document(document, digest_field)
    raw = canonical_json(checked).encode("utf-8")
    if len(raw) + 1 > MAX_DOCUMENT_BYTES:
        raise ManifestError(f"document exceeds {MAX_DOCUMENT_BYTES} bytes")
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    handle: int | None = None
    temporary: Path | None = None
    try:
        handle, name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
        temporary = Path(name)
        with os.fdopen(handle, "wb") as stream:
            handle = None
            stream.write(raw)
            stream.write(b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        # load_document insists on exact canonical bytes, including no trailing byte;
        # the newline is intentional for human-friendly files and is accepted below.
        os.replace(temporary, target)
    except OSError as exc:
        raise ManifestError(f"could not write document {target}: {exc}") from exc
    finally:
        if handle is not None:
            os.close(handle)
        if temporary is not None and temporary.exists():
            temporary.unlink(missing_ok=True)
    return target


def _read_json_mapping(path: Path, *, context: str) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
        if len(raw) > MAX_DOCUMENT_BYTES:
            raise ManifestError(f"{context} exceeds {MAX_DOCUMENT_BYTES} bytes")
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_pairs,
            parse_constant=lambda x: (_ for _ in ()).throw(ManifestError(f"non-finite JSON constant {x!r}")),
        )
    except ManifestError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ManifestError(f"invalid {context}: {exc}") from exc
    if not isinstance(value, dict):
        raise ManifestError(f"{context} must be a JSON object")
    return value


def _as_path(value: Any, context: str) -> Path:
    if isinstance(value, (str, os.PathLike)):
        path = Path(value)
        if not path.is_file():
            raise ManifestError(f"{context} is not a file: {path}")
        return path
    raise ManifestError(f"{context} must be a path")


def _file_hash(path: Path) -> dict[str, Any]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            size += len(chunk)
            digest.update(chunk)
    # Keep manifests relocatable and safe to publish: the role-specific parent
    # field supplies provenance, while an operator's absolute checkout path is
    # neither useful nor appropriate evidence.
    return {"path": path.name, "bytes": size, "sha256": digest.hexdigest()}


def _extract_comment_value(sentence: UDSentence, prefix: str) -> str | None:
    for comment in sentence.comments:
        if comment.startswith(prefix) and "=" in comment:
            value = comment.split("=", 1)[1].strip()
            if value:
                return value
    return None


def _identity(sentence: UDSentence, *, source: str) -> tuple[str, str, str]:
    sent_id = sentence.sent_id.strip()
    if not sent_id:
        raise ManifestError(f"{source} contains a sentence without # sent_id")
    # PapyGreek and UD-Perseus both use a source-native document stem followed by
    # ``@ordinal``.  Keep the entire source-native document stem, but remove the
    # local dataset namespace that the PapyGreek development builder adds.
    identity = re.fullmatch(r"(.+)@([1-9][0-9]*)", sent_id)
    if identity is None:
        raise ManifestError(
            f"{source} sentence {sent_id!r} must end in a positive numeric ordinal"
        )
    stem = identity.group(1)
    # The sentence ID is the source-native authority.  ``# newdoc id`` may only
    # appear on the first sentence of a document and would otherwise make later
    # rows depend on parser state; retaining the stem keeps every row independently
    # auditable and stable under reordering.
    if source.startswith("papygreek"):
        prefix = "papygreek-dev:"
        if not stem.startswith(prefix) or len(stem) == len(prefix):
            raise ManifestError(
                f"{source} sentence {sent_id!r} must use the papygreek-dev namespace"
            )
        document_id = stem.removeprefix(prefix)
        if "@" in document_id:
            raise ManifestError(f"{source} sentence {sent_id!r} has an invalid document identity")
        work_id = document_id
    elif source.startswith("perseus"):
        document_id = stem
        match = re.match(r"^(tlg\d+\.tlg\d+)(?:\.|$)", stem)
        if match is None:
            raise ManifestError(
                f"{source} sentence {sent_id!r} has no source-native TLG work identity"
            )
        work_id = match.group(1)
    else:  # pragma: no cover - callers use one of the two declared source families
        raise ManifestError(f"unknown development source {source!r}")
    if not document_id or not work_id:
        raise ManifestError(f"{source} sentence {sent_id!r} has no document/work identity")
    return document_id, work_id, sent_id


def _has_punct(form: str) -> bool:
    return not any(character.isalpha() or character.isdigit() for character in form)


def _normal_forms(sentence: UDSentence) -> tuple[str, ...]:
    return tuple(unicodedata.normalize("NFC", token.form) for token in sentence.tokens)


def _form_key(forms: tuple[str, ...]) -> tuple[str, ...]:
    return forms


def _punct_stripped(forms: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(form for form in forms if not _has_punct(form))


def _token_dict(token: UDToken) -> dict[str, Any]:
    return {
        "id": token.id,
        "form": unicodedata.normalize("NFC", token.form),
        "lemma": token.lemma,
        "upos": token.upos,
        "xpos": token.xpos,
        "feats": token.feats,
        "head": token.head,
        "deprel": token.deprel,
    }


def _item_content(sentence: UDSentence) -> tuple[str, list[dict[str, Any]], str]:
    tokens = [_token_dict(token) for token in sentence.tokens]
    # Content identity is the scored surface sentence, not an annotation track's
    # task-specific labels.  This is what permits PapyGreek's tagging and parse
    # tracks to merge when their heads/relations differ while still rejecting a
    # same-ID form/text substitution.
    forms = tuple(token["form"] for token in tokens)
    payload = {"forms": forms}
    content = hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
    form_hash = hashlib.sha256(canonical_json(forms).encode("utf-8")).hexdigest()
    return content, tokens, form_hash


def _source_label(kind: str) -> tuple[str, str, str]:
    if kind == "perseus":
        return "ud-perseus-agdt", "literary", "agdt"
    return "papygreek-regularized", "documentary-koine", "papygreek"


def _load_sentences(value: Any, *, context: str) -> tuple[Path, list[UDSentence]]:
    path = _as_path(value, context)
    try:
        sentences = load_conllu(path, strict=True)
    except Exception as exc:
        raise ManifestError(f"invalid {context} CoNLL-U: {exc}") from exc
    if not sentences:
        raise ManifestError(f"{context} contains no sentences")
    return path, sentences


def _training_info(
    training_dir: Any,
) -> tuple[set[tuple[str, ...]], set[tuple[str, ...]], Counter[str], set[str], list[dict[str, Any]]]:
    root = Path(training_dir)
    if not root.exists() or not root.is_dir():
        raise ManifestError(f"training_dir is not a directory: {root}")
    train_keys: set[tuple[str, ...]] = set()
    all_keys: set[tuple[str, ...]] = set()
    frequencies: Counter[str] = Counter()
    work_ids: set[str] = set()
    files: list[dict[str, Any]] = []
    for name in ("full-train.jsonl", "full-dev.jsonl"):
        path = root / name
        if not path.is_file():
            raise ManifestError(f"required training file is missing: {path}")
        files.append(_file_hash(path))
        try:
            with path.open("r", encoding="utf-8") as stream:
                for line_number, line in enumerate(stream, 1):
                    if not line.strip():
                        continue
                    row = _parse_strict_json(
                        line,
                        context=f"training JSONL {path}:{line_number}",
                    )
                    if not isinstance(row, Mapping):
                        raise ManifestError(f"training row {path}:{line_number} is not an object")
                    raw_tokens = row.get("tokens", row.get("forms"))
                    if not isinstance(raw_tokens, list):
                        raise ManifestError(f"training row {path}:{line_number} has no token list")
                    forms: list[str] = []
                    for token in raw_tokens:
                        if isinstance(token, Mapping):
                            token = token.get("form", token.get("FORM"))
                        if not isinstance(token, str) or not token:
                            raise ManifestError(f"training row {path}:{line_number} has invalid token")
                        form = unicodedata.normalize("NFC", token)
                        forms.append(form)
                        if name == "full-train.jsonl":
                            frequencies[form] += 1
                    tuple_forms = tuple(forms)
                    all_keys.add(tuple_forms)
                    stripped = _punct_stripped(tuple_forms)
                    if stripped:
                        all_keys.add(stripped)
                    if name == "full-train.jsonl":
                        train_keys.add(tuple_forms)
                        if stripped:
                            train_keys.add(stripped)
                    file_name = row.get("file", row.get("document_id", row.get("work_id")))
                    if isinstance(file_name, str) and file_name:
                        work_ids.add(file_name)
        except (OSError, UnicodeError) as exc:
            raise ManifestError(f"cannot read training file {path}: {exc}") from exc
    return train_keys, all_keys, frequencies, work_ids, files


def _locked_doc_ids(manifest: Mapping[str, Any]) -> set[str]:
    raw = manifest.get("doc_ids", manifest.get("document_ids"))
    if not isinstance(raw, list) or not raw or any(not isinstance(item, str) or not item for item in raw):
        raise ManifestError("PapyGreek locked manifest must contain non-empty doc_ids")
    return set(raw)


def _parse_audit(value: Any) -> tuple[set[str], dict[str, Any], str]:
    if value is None:
        raise ManifestError("papygreek_training_work_audit is required for selection eligibility")
    if isinstance(value, Mapping):
        audit = dict(value)
        digest_source = None
    else:
        path = _as_path(value, "papygreek_training_work_audit")
        audit = _read_json_mapping(path, context="papygreek_training_work_audit")
        digest_source = _file_hash(path)
    raw = audit.get("excluded_document_ids", audit.get("doc_ids"))
    if raw is None and isinstance(audit.get("document_sets"), Mapping):
        raw = audit["document_sets"].get("training_overlap_document_ids")
    if not isinstance(raw, list) or any(not isinstance(item, str) or not item for item in raw):
        raise ManifestError("PapyGreek training-work audit must contain excluded_document_ids")
    if digest_source is not None:
        audit = dict(audit)
        audit["audit_file"] = digest_source
        digest = str(digest_source["sha256"])
    else:
        digest = hashlib.sha256(canonical_json(audit).encode("utf-8")).hexdigest()
    return set(raw), audit, digest


def _item_entry(
    sentence: UDSentence,
    *,
    source: str,
    track: str,
    task: str,
    asset_sha256: str,
) -> dict[str, Any]:
    document_id, work_id, sentence_id = _identity(sentence, source=source)
    content_hash, tokens, form_hash = _item_content(sentence)
    profile, domain, convention = _source_label(source)
    item_id = f"{source}:{document_id}:{sentence_id}"
    asset_bindings = {track: asset_sha256}
    return {
        "item_id": item_id,
        "source": source,
        "asset_sha256": hashlib.sha256(
            canonical_json(asset_bindings).encode("utf-8")
        ).hexdigest(),
        "asset_sha256_by_track": asset_bindings,
        "document_id": document_id,
        "work_id": work_id,
        "sentence_id": sentence_id,
        "tasks": [task],
        "tracks": [track],
        "profile_ids": [profile],
        "domain_ids": [domain],
        "annotation_conventions": [convention],
        "token_count": len(tokens),
        "scored_token_count": len(tokens),
        "content_sha256": content_hash,
        "form_tuple_sha256": form_hash,
        "v3_exposure": "selection-dev" if source == "perseus" else "unseen-after-audit",
    }


def _merge_items(base: dict[str, Any], incoming: dict[str, Any]) -> None:
    if base["content_sha256"] != incoming["content_sha256"]:
        raise ManifestError(f"same ID has unexpected content: {base['item_id']}")
    for field in ("tasks", "tracks"):
        base[field] = sorted(set(base[field]) | set(incoming[field]))
    bindings = dict(base.get("asset_sha256_by_track", {}))
    incoming_bindings = incoming.get("asset_sha256_by_track", {})
    if isinstance(incoming_bindings, Mapping):
        bindings.update({str(key): str(value) for key, value in incoming_bindings.items()})
    base["asset_sha256_by_track"] = dict(sorted(bindings.items()))
    base["asset_sha256"] = hashlib.sha256(
        canonical_json(base["asset_sha256_by_track"]).encode("utf-8")
    ).hexdigest()


def _slice_counts(items: list[dict[str, Any]], *, rule: str, selected: list[dict[str, Any]], minimum: int = 2) -> dict[str, Any]:
    docs = sorted({item["document_id"] for item in selected})
    works = sorted({item["work_id"] for item in selected})
    tokens = sum(int(item["scored_token_count"]) for item in selected)
    total = len(items)
    return {
        "rule": rule,
        "available": True,
        "item_count": len(selected),
        "token_count": tokens,
        "document_count": len(docs),
        "work_count": len(works),
        "coverage": (len(selected) / total) if total else 0.0,
        "minimum_sample": minimum,
        "thin": len(selected) < minimum,
        "item_ids": [item["item_id"] for item in selected],
    }


def _build_slices(items: list[dict[str, Any]]) -> dict[str, Any]:
    slices: dict[str, Any] = {}
    slices["source:perseus"] = _slice_counts(items, rule="source == 'perseus'", selected=[i for i in items if i["source"] == "perseus"])
    slices["source:papygreek"] = _slice_counts(items, rule="source == 'papygreek'", selected=[i for i in items if i["source"] == "papygreek"])
    slices["domain:literary"] = _slice_counts(items, rule="'literary' in domain_ids", selected=[i for i in items if "literary" in i["domain_ids"]])
    slices["documentary-koine"] = _slice_counts(items, rule="'documentary-koine' in domain_ids", selected=[i for i in items if "documentary-koine" in i["domain_ids"]])
    slices["prose"] = _slice_counts(items, rule="source == 'perseus' and profile is prose-eligible", selected=[i for i in items if i["source"] == "perseus"])
    slices["regularized"] = _slice_counts(items, rule="source == 'papygreek' and profile == 'regularized'", selected=[i for i in items if i["source"] == "papygreek"])
    for name, low, high in _LENGTH_BINS:
        selected = [i for i in items if int(i["scored_token_count"]) >= low and (high is None or int(i["scored_token_count"]) <= high)]
        slices[f"length:{name}"] = _slice_counts(items, rule=f"scored_token_count in [{low},{high or 'infinity'}]", selected=selected)
    for item in items:
        frequencies = item.get("train_token_frequencies", [])
        item["oov_token_count"] = sum(1 for frequency in frequencies if frequency == 0)
        item["train_frequency_min"] = min(frequencies) if frequencies else 0
    slices["oov"] = _slice_counts(items, rule="oov_token_count > 0", selected=[i for i in items if i["oov_token_count"] > 0])
    for name, low, high in _FREQUENCY_BINS:
        selected = [i for i in items if i["oov_token_count"] == 0 and int(i["train_frequency_min"]) >= low and (high is None or int(i["train_frequency_min"]) <= high)]
        slices[f"frequency:{name}"] = _slice_counts(items, rule=f"all token train frequencies in [{low},{high or 'infinity'}]", selected=selected)
    slices["annotation:agdt"] = _slice_counts(items, rule="'agdt' in annotation_conventions", selected=[i for i in items if "agdt" in i["annotation_conventions"]])
    slices["annotation:papygreek"] = _slice_counts(items, rule="'papygreek' in annotation_conventions", selected=[i for i in items if "papygreek" in i["annotation_conventions"]])
    for name, reason in _UNAVAILABLE.items():
        slices[name] = {"rule": "unavailable", "available": False, "item_count": 0, "token_count": 0, "document_count": 0, "work_count": 0, "coverage": 0.0, "minimum_sample": 2, "thin": True, "item_ids": [], "unavailable": True, "reason": reason}
    return slices


def _exact_fields(value: Mapping[str, Any], fields: set[str], *, where: str) -> None:
    actual = set(value)
    if actual != fields:
        raise ManifestError(
            f"{where} fields differ (missing={sorted(fields - actual)}, "
            f"extra={sorted(actual - fields)})"
        )


def verify_manifest(manifest: Mapping[str, Any]) -> None:
    """Verify the complete development-manifest schema and self-digest."""

    if not isinstance(manifest, Mapping):
        raise ManifestError("manifest must be an object")
    _exact_fields(
        manifest,
        {
            "format",
            "kind",
            "policy",
            "sources",
            "source_hashes",
            "locked_file_hashes",
            "items",
            "slices",
            "audit",
            "manifest_sha256",
        },
        where="manifest",
    )
    if manifest.get("format") != MANIFEST_FORMAT:
        raise ManifestError("unknown manifest format")
    if manifest.get("kind") != "development-source-manifest":
        raise ManifestError("unknown manifest kind")
    verify_document(manifest, "manifest_sha256")

    policy = manifest.get("policy")
    if not isinstance(policy, Mapping):
        raise ManifestError("manifest policy must be an object")
    _exact_fields(
        policy,
        {
            "eligible_sources",
            "normalization",
            "training_overlap",
            "locked_work_exclusion",
            "selection_claim_status",
        },
        where="manifest.policy",
    )
    if policy.get("selection_claim_status") != "development-only-not-published":
        raise ManifestError("manifest claim status must remain development-only")

    sources = manifest.get("sources")
    if not isinstance(sources, Mapping):
        raise ManifestError("manifest sources must be an object")
    _exact_fields(
        sources,
        {
            "perseus_dev",
            "perseus_locked",
            "papygreek_tagging",
            "papygreek_parse",
            "revisions",
            "training_files",
            "papygreek_locked_manifest",
            "papygreek_training_work_audit",
        },
        where="manifest.sources",
    )
    revisions = sources.get("revisions")
    if (
        not isinstance(revisions, Mapping)
        or not revisions
        or any(not isinstance(key, str) or not key or not isinstance(value, str) or not value
               for key, value in revisions.items())
    ):
        raise ManifestError("manifest source revisions are malformed")
    source_hashes = manifest.get("source_hashes")
    if (
        not isinstance(source_hashes, Mapping)
        or not source_hashes
        or any(not isinstance(key, str) or not isinstance(value, str) or not _SHA256.fullmatch(value)
               for key, value in source_hashes.items())
    ):
        raise ManifestError("manifest source hashes are malformed")
    for key in ("perseus_dev", "perseus_locked", "papygreek_tagging", "papygreek_parse"):
        record = sources.get(key)
        if not isinstance(record, Mapping) or record.get("sha256") != source_hashes.get(key):
            raise ManifestError(f"manifest source hash binding differs for {key}")
    training_files = sources.get("training_files")
    if not isinstance(training_files, list):
        raise ManifestError("manifest training files must be an array")
    for index, record in enumerate(training_files):
        if not isinstance(record, Mapping):
            raise ManifestError(f"manifest training file {index} is malformed")
        key = f"training:{record.get('path')}"
        if record.get("sha256") != source_hashes.get(key):
            raise ManifestError(f"manifest source hash binding differs for {key}")
    locked_manifest = sources.get("papygreek_locked_manifest")
    if not isinstance(locked_manifest, Mapping):
        raise ManifestError("manifest PapyGreek locked reference is malformed")
    locked_file = locked_manifest.get("file")
    if isinstance(locked_file, Mapping):
        if locked_file.get("sha256") != source_hashes.get("papygreek_locked_manifest"):
            raise ManifestError("manifest locked PapyGreek hash binding differs")
    work_audit = sources.get("papygreek_training_work_audit")
    if not isinstance(work_audit, Mapping):
        raise ManifestError("manifest PapyGreek training-work audit is malformed")
    audit_file = work_audit.get("audit_file")
    if isinstance(audit_file, Mapping):
        if audit_file.get("sha256") != source_hashes.get("papygreek_training_work_audit"):
            raise ManifestError("manifest PapyGreek audit hash binding differs")
    locked_hashes = manifest.get("locked_file_hashes")
    if not isinstance(locked_hashes, Mapping) or set(locked_hashes) != {
        "perseus_locked",
        "papygreek_locked_manifest",
    }:
        raise ManifestError("manifest locked file hashes are malformed")
    if locked_hashes["perseus_locked"] != source_hashes.get("perseus_locked"):
        raise ManifestError("manifest locked Perseus hash binding differs")
    if locked_hashes["papygreek_locked_manifest"] != source_hashes.get(
        "papygreek_locked_manifest"
    ):
        raise ManifestError("manifest locked PapyGreek hash binding differs")

    items = manifest.get("items")
    if not isinstance(items, list):
        raise ManifestError("manifest items must be an array")
    item_fields = {
        "item_id",
        "source",
        "asset_sha256",
        "asset_sha256_by_track",
        "document_id",
        "work_id",
        "sentence_id",
        "tasks",
        "tracks",
        "profile_ids",
        "domain_ids",
        "annotation_conventions",
        "token_count",
        "scored_token_count",
        "content_sha256",
        "form_tuple_sha256",
        "v3_exposure",
        "train_token_frequencies",
        "oov_token_count",
        "train_frequency_min",
    }
    item_ids: list[str] = []
    content_hashes: set[str] = set()
    for index, item in enumerate(items):
        if not isinstance(item, Mapping):
            raise ManifestError(f"manifest.items[{index}] must be an object")
        _exact_fields(item, item_fields, where=f"manifest.items[{index}]")
        for field in ("item_id", "source", "document_id", "work_id", "sentence_id", "v3_exposure"):
            if not isinstance(item.get(field), str) or not item[field]:
                raise ManifestError(f"manifest.items[{index}].{field} is invalid")
        for field in ("asset_sha256", "content_sha256", "form_tuple_sha256"):
            if not isinstance(item.get(field), str) or not _SHA256.fullmatch(item[field]):
                raise ManifestError(f"manifest.items[{index}].{field} is invalid")
        for field in ("tasks", "tracks", "profile_ids", "domain_ids", "annotation_conventions"):
            values = item.get(field)
            if (
                not isinstance(values, list)
                or not values
                or any(not isinstance(value, str) or not value for value in values)
                or values != sorted(set(values))
            ):
                raise ManifestError(f"manifest.items[{index}].{field} is invalid")
        if not set(item["tasks"]) <= {"parse", "tagging"}:
            raise ManifestError(f"manifest.items[{index}].tasks contains an unknown task")
        bindings = item.get("asset_sha256_by_track")
        if (
            not isinstance(bindings, Mapping)
            or set(bindings) != set(item["tracks"])
            or any(not isinstance(value, str) or not _SHA256.fullmatch(value) for value in bindings.values())
        ):
            raise ManifestError(f"manifest.items[{index}] asset bindings are invalid")
        expected_binding = hashlib.sha256(canonical_json(bindings).encode("utf-8")).hexdigest()
        if item["asset_sha256"] != expected_binding:
            raise ManifestError(f"manifest.items[{index}] asset binding digest mismatch")
        count = item.get("token_count")
        scored = item.get("scored_token_count")
        frequencies = item.get("train_token_frequencies")
        if (
            isinstance(count, bool)
            or not isinstance(count, int)
            or count < 1
            or scored != count
            or not isinstance(frequencies, list)
            or len(frequencies) != count
            or any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in frequencies)
        ):
            raise ManifestError(f"manifest.items[{index}] token accounting is invalid")
        item_id = str(item["item_id"])
        item_ids.append(item_id)
        content = str(item["content_sha256"])
        if content in content_hashes:
            raise ManifestError(f"duplicate manifest content hash {content}")
        content_hashes.add(content)
    if item_ids != sorted(item_ids) or len(item_ids) != len(set(item_ids)):
        raise ManifestError("manifest item IDs must be sorted and unique")

    slices = manifest.get("slices")
    if not isinstance(slices, Mapping):
        raise ManifestError("manifest slices must be an object")
    all_ids = set(item_ids)
    base_slice_fields = {
        "rule",
        "available",
        "item_count",
        "token_count",
        "document_count",
        "work_count",
        "coverage",
        "minimum_sample",
        "thin",
        "item_ids",
    }
    for slice_id, entry in slices.items():
        if not isinstance(slice_id, str) or not slice_id or not isinstance(entry, Mapping):
            raise ManifestError("manifest slice entries are malformed")
        unavailable = entry.get("available") is False
        fields = base_slice_fields | ({"unavailable", "reason"} if unavailable else set())
        _exact_fields(entry, fields, where=f"manifest.slices[{slice_id!r}]")
        ids = entry.get("item_ids")
        if (
            not isinstance(ids, list)
            or ids != sorted(set(ids))
            or not set(ids) <= all_ids
            or entry.get("item_count") != len(ids)
        ):
            raise ManifestError(f"manifest slice {slice_id!r} has invalid item IDs")
        if unavailable and (ids or entry.get("unavailable") is not True or not entry.get("reason")):
            raise ManifestError(f"unavailable slice {slice_id!r} is malformed")


def build_manifest(
    *,
    perseus_dev: Any,
    perseus_locked: Any,
    papygreek_tagging: Any,
    papygreek_parse: Any,
    papygreek_locked_manifest: Any,
    training_dir: Any,
    papygreek_training_work_audit: Any = None,
    expected_source_hashes: Mapping[str, str] | None = None,
    source_revisions: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Build the deterministic, leakage-safe development source/slice manifest."""

    train_keys, training_keys, train_frequencies, train_work_ids, training_files = _training_info(training_dir)
    audit_docs, work_audit, work_audit_sha256 = _parse_audit(
        papygreek_training_work_audit
    )
    perseus_path, perseus_sents = _load_sentences(perseus_dev, context="perseus_dev")
    locked_perseus_path, locked_perseus_sents = _load_sentences(perseus_locked, context="perseus_locked")
    tagging_path, tagging_sents = _load_sentences(papygreek_tagging, context="papygreek_tagging")
    parse_path, parse_sents = _load_sentences(papygreek_parse, context="papygreek_parse")
    locked_manifest = (
        dict(papygreek_locked_manifest)
        if isinstance(papygreek_locked_manifest, Mapping)
        else _read_json_mapping(_as_path(papygreek_locked_manifest, "papygreek_locked_manifest"), context="papygreek_locked_manifest")
    )
    locked_manifest_record = (
        _file_hash(_as_path(papygreek_locked_manifest, "papygreek_locked_manifest"))
        if isinstance(papygreek_locked_manifest, (str, os.PathLike))
        else None
    )
    papy_locked_docs = _locked_doc_ids(locked_manifest)
    hashes = {
        "perseus_dev": _file_hash(perseus_path),
        "perseus_locked": _file_hash(locked_perseus_path),
        "papygreek_tagging": _file_hash(tagging_path),
        "papygreek_parse": _file_hash(parse_path),
    }
    actual_source_hashes = {key: str(value["sha256"]) for key, value in hashes.items()}
    if locked_manifest_record is not None:
        actual_source_hashes["papygreek_locked_manifest"] = str(
            locked_manifest_record["sha256"]
        )
    else:
        actual_source_hashes["papygreek_locked_manifest"] = hashlib.sha256(
            canonical_json(locked_manifest).encode("utf-8")
        ).hexdigest()
    actual_source_hashes["papygreek_training_work_audit"] = work_audit_sha256
    for record in training_files:
        actual_source_hashes[f"training:{record['path']}"] = str(record["sha256"])
    if not isinstance(expected_source_hashes, Mapping):
        raise ManifestError("expected_source_hashes is required")
    expected = {str(key): str(value) for key, value in expected_source_hashes.items()}
    if set(expected) != set(actual_source_hashes):
        raise ManifestError(
            "expected_source_hashes keys differ from the exact input set "
            f"(expected={sorted(expected)}, actual={sorted(actual_source_hashes)})"
        )
    for key, actual in actual_source_hashes.items():
        pinned = expected[key]
        if not _SHA256.fullmatch(pinned) or pinned != actual:
            raise ManifestError(
                f"source hash drift for {key}: expected {pinned}, actual {actual}"
            )
    if not isinstance(source_revisions, Mapping) or not source_revisions:
        raise ManifestError("source_revisions is required")
    revisions = {str(key): str(value) for key, value in source_revisions.items()}
    if any(not key or not value for key, value in revisions.items()):
        raise ManifestError("source_revisions keys and values must be non-empty strings")
    locked_work_ids: set[str] = set()
    locked_ids: set[str] = set()
    for sentence in locked_perseus_sents:
        document_id, work_id, sentence_id = _identity(sentence, source="perseus_locked")
        del document_id
        locked_work_ids.add(work_id)
        locked_ids.add(sentence_id)
    items_by_id: dict[str, dict[str, Any]] = {}
    excluded: Counter[str] = Counter()
    seen_perseus: set[str] = set()
    for sentence in perseus_sents:
        document_id, work_id, sentence_id = _identity(sentence, source="perseus_dev")
        del document_id
        if sentence_id in seen_perseus:
            raise ManifestError(f"duplicate Perseus sentence ID {sentence_id!r}")
        seen_perseus.add(sentence_id)
        if work_id in locked_work_ids:
            excluded["perseus_locked_work"] += 1
            continue
        item = _item_entry(sentence, source="perseus", track="perseus-dev", task="tagging", asset_sha256=hashes["perseus_dev"]["sha256"])
        forms = _normal_forms(sentence)
        if _form_key(forms) in train_keys or (_punct_stripped(forms) and _punct_stripped(forms) in train_keys):
            raise ManifestError(f"Perseus development sentence overlaps training forms: {sentence_id}")
        item["train_token_frequencies"] = [train_frequencies.get(form, 0) for form in forms]
        item["tasks"] = ["parse", "tagging"]
        if item["item_id"] in items_by_id:
            raise ManifestError(f"duplicate item ID {item['item_id']!r}")
        items_by_id[item["item_id"]] = item
    seen_papy: set[str] = set()
    seen_papy_tracks: set[tuple[str, str]] = set()
    for track, path, sentences, task in (("tagging", tagging_path, tagging_sents, "tagging"), ("parse", parse_path, parse_sents, "parse")):
        del path
        for sentence in sentences:
            document_id, _work_id, sentence_id = _identity(sentence, source="papygreek")
            if (track, sentence_id) in seen_papy_tracks:
                raise ManifestError(f"duplicate PapyGreek {track} sentence ID {sentence_id!r}")
            seen_papy_tracks.add((track, sentence_id))
            if track == "tagging":
                seen_papy.add(sentence_id)
            if document_id in papy_locked_docs:
                raise ManifestError(f"PapyGreek development document overlaps locked test: {document_id}")
            if document_id in audit_docs:
                excluded["papygreek_training_work"] += 1
                continue
            item = _item_entry(sentence, source="papygreek", track=track, task=task, asset_sha256=hashes[f"papygreek_{track}"]["sha256"])
            if track == "parse":
                # The parse asset carries complete POS/morphology/lemma columns as
                # well as dependency gold, so its items are eligible for both task
                # families even when the tagging track has no matching sentence.
                item["tasks"] = ["parse", "tagging"]
            forms = _normal_forms(sentence)
            if _form_key(forms) in training_keys or (_punct_stripped(forms) and _punct_stripped(forms) in training_keys):
                raise ManifestError(f"PapyGreek development sentence overlaps training forms: {sentence_id}")
            item["train_token_frequencies"] = [train_frequencies.get(form, 0) for form in forms]
            if item["item_id"] in items_by_id:
                _merge_items(items_by_id[item["item_id"]], item)
            else:
                items_by_id[item["item_id"]] = item
    # Repeated formulae occur in documentary texts.  They must not silently receive
    # extra selection weight, and the manifest contract requires unique canonical
    # content.  Keep the richest task record, then the lexical item ID, and record
    # every deterministic exclusion.
    content_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items_by_id.values():
        content_groups[str(item["content_sha256"])].append(item)
    duplicate_content_exclusions: list[dict[str, Any]] = []
    selected_items: list[dict[str, Any]] = []
    for content_sha256, group in sorted(content_groups.items()):
        ordered = sorted(group, key=lambda item: (-len(item["tasks"]), item["item_id"]))
        selected_items.append(ordered[0])
        for duplicate in ordered[1:]:
            excluded["duplicate_development_content"] += 1
            duplicate_content_exclusions.append(
                {
                    "content_sha256": content_sha256,
                    "kept_item_id": ordered[0]["item_id"],
                    "excluded_item_id": duplicate["item_id"],
                }
            )
    # The report contract compares exact sorted IDs; item content remains bound by
    # the manifest digest, so source/file input order cannot affect ordering.
    items = sorted(selected_items, key=lambda item: item["item_id"])
    for item in items:
        item["tasks"] = sorted(set(item["tasks"]))
        item["tracks"] = sorted(set(item["tracks"]))
    content_ids: dict[str, str] = {}
    for item in items:
        prior = content_ids.setdefault(item["content_sha256"], item["item_id"])
        if prior != item["item_id"]:
            raise ManifestError(
                f"duplicate canonical content for {prior!r} and {item['item_id']!r}"
            )
    manifest: dict[str, Any] = {
        "format": MANIFEST_FORMAT,
        "kind": "development-source-manifest",
        "policy": {
            "eligible_sources": ["perseus-dev", "papygreek-dev-tagging", "papygreek-dev-parse"],
            "normalization": "NFC",
            "training_overlap": "full and punctuation-stripped form tuples",
            "locked_work_exclusion": True,
            "selection_claim_status": "development-only-not-published",
        },
        "sources": {
            **hashes,
            "revisions": dict(sorted(revisions.items())),
            "training_files": training_files,
            "papygreek_locked_manifest": {"doc_ids": sorted(papy_locked_docs), "asset_sha256": locked_manifest.get("asset_sha256"), "file": locked_manifest_record},
            "papygreek_training_work_audit": work_audit,
        },
        "source_hashes": dict(sorted(actual_source_hashes.items())),
        "locked_file_hashes": {
            "perseus_locked": hashes["perseus_locked"]["sha256"],
            "papygreek_locked_manifest": locked_manifest_record["sha256"] if locked_manifest_record else None,
        },
        "items": items,
        "slices": _build_slices(items),
        "audit": {
            "parsed_counts": {"perseus_dev": len(perseus_sents), "perseus_locked": len(locked_perseus_sents), "papygreek_tagging": len(tagging_sents), "papygreek_parse": len(parse_sents)},
            "eligible_item_count": len(items),
            "excluded_counts": dict(sorted(excluded.items())),
            "locked_perseus_work_count": len(locked_work_ids),
            "locked_perseus_sentence_count": len(locked_ids),
            "papygreek_locked_document_count": len(papy_locked_docs),
            "training_form_key_count": len(training_keys),
            "training_work_count": len(train_work_ids),
            "training_file_count": len(training_files),
            "duplicate_content_exclusions": duplicate_content_exclusions,
        },
    }
    stamped = stamp_document(manifest)
    verify_manifest(stamped)
    return stamped


def main() -> None:
    """Build and write one manifest from explicitly pinned local inputs."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--perseus-dev", required=True)
    parser.add_argument("--perseus-locked", required=True)
    parser.add_argument("--papygreek-tagging", required=True)
    parser.add_argument("--papygreek-parse", required=True)
    parser.add_argument("--papygreek-locked-manifest", required=True)
    parser.add_argument("--papygreek-training-work-audit", required=True)
    parser.add_argument("--training-dir", required=True)
    parser.add_argument(
        "--pins",
        required=True,
        help="bounded JSON object with expected_source_hashes and source_revisions",
    )
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    pins = _read_json_mapping(Path(args.pins), context="development source pins")
    _exact_fields(
        pins,
        {"format", "expected_source_hashes", "source_revisions"},
        where="development source pins",
    )
    if pins.get("format") != "pyaegean-development-source-pins/1":
        raise ManifestError("unknown development source pin format")
    expected = pins.get("expected_source_hashes")
    revisions = pins.get("source_revisions")
    if not isinstance(expected, Mapping) or not isinstance(revisions, Mapping):
        raise ManifestError("development source pins are malformed")
    manifest = build_manifest(
        perseus_dev=Path(args.perseus_dev),
        perseus_locked=Path(args.perseus_locked),
        papygreek_tagging=Path(args.papygreek_tagging),
        papygreek_parse=Path(args.papygreek_parse),
        papygreek_locked_manifest=Path(args.papygreek_locked_manifest),
        training_dir=Path(args.training_dir),
        papygreek_training_work_audit=Path(args.papygreek_training_work_audit),
        expected_source_hashes=expected,
        source_revisions=revisions,
    )
    output = write_document(manifest, Path(args.output))
    print(
        canonical_json(
            {
                "manifest": output.name,
                "manifest_sha256": manifest["manifest_sha256"],
                "items": len(manifest["items"]),
            }
        )
    )


if __name__ == "__main__":
    main()
