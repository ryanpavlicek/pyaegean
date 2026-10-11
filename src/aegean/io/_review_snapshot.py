"""Private, content-bound review snapshots and dependency sentence ownership."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..core.corpus import Corpus
    from ..core.model import Document, Token
    from ..core.provenance import Provenance

FIELDS = ("lemma", "pos", "morph", "head", "deprel")
SNAPSHOT_COLUMNS = ("review_snapshot", "review_snapshot_sha256")
DEPENDENCY_COLUMNS = (
    "dependency_sentence_id", "dependency_index", "dependency_sentence_context",
)


def canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value: object) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def field_key(annotations: Mapping[str, str], name: str) -> str:
    if name == "pos":
        return "upos"
    if name == "morph":
        if annotations.get("morph"):
            return "morph"
        if annotations.get("feats"):
            return "feats"
        # Presence of empty UD morphology remains meaningful.
        return "feats" if "feats" in annotations and "morph" not in annotations else "morph"
    return name


def source_identity(doc: Document, provenance: Provenance | None = None) -> str:
    """Bind the entire source context, including explicit absence and alignment."""
    return digest({
        "document": doc.id, "script": doc.script_id, "source_text": doc.source_text,
        "lines": doc.lines, "transcription": doc.transcription, "glyphs": doc.glyphs,
        "metadata": asdict(doc.meta),
        "provenance": {key: value for key, value in asdict(provenance).items() if key != "notes"}
        if provenance is not None else None,
        "tokens": [{
            "text": token.text, "kind": token.kind.value, "status": token.status.value,
            "position": token.position, "line_no": token.line_no,
            "glyphs": token.glyphs, "signs": token.signs, "alt": token.alt,
            "reference": token.annotations.get("ref"),
            "alignment": asdict(token.alignment) if token.alignment is not None else None,
            "form_state": token.form_state.to_dict() if token.form_state is not None else None,
        } for token in doc.tokens],
    })


def snapshot(token: Token, source_sha256: str) -> dict[str, Any]:
    ann = token.annotations
    # The annotator persists its actual AnalysisReceipt, never a reconstructed
    # claim based on whatever model happens to be active during review export.
    analysis = {
        "kind": ann.get("analysis_kind", "external"),
        "generation": ann.get("analysis_generation", "unknown"),
        "receipt": ann.get("analysis_receipt", "unknown"),
        "model_artifact": ann.get("model_sha256", "recorded_in_receipt"
                                  if ann.get("analysis_receipt", "unknown") != "unknown" else "unknown"),
        "configuration": ann.get("analysis_configuration", "unknown"),
        "available_identity": {key: value for key, value in sorted(ann.items())
                               if key.startswith(("model_", "runtime_", "annotation_", "analysis_"))
                               and key not in {"analysis_kind", "analysis_generation", "analysis_receipt",
                                               "analysis_configuration"}},
    }
    outputs = {
        name: {"key": (key := field_key(ann, name)), "present": key in ann,
               "value": ann.get(key, "")}
        for name in FIELDS
    }
    return {
        "schema": "pyaegean-review/1", "source_sha256": source_sha256,
        "token_identity": {"position": token.position, "text": token.text, "kind": token.kind.value,
                           "alignment": {**asdict(token.alignment),
                                         "normalization_ops": list(token.alignment.normalization_ops)}
                           if token.alignment is not None else None},
        "analysis": analysis,
        "output": {"fields": outputs,
                   "lemma_source": {"present": "lemma_source" in ann,
                                    "value": ann.get("lemma_source", "")},
                   "other": {key: ann[key] for key in (
                       "xpos", "analysis_complete", "analysis_warning", "neural_analyzed",
                       "dependency_sentence_id", "dependency_index",
                   ) if key in ann}},
    }



def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("review snapshot contains duplicate JSON keys")
        result[key] = value
    return result




def _reviewed_value_matches(token: Token, key: str, claimed: str, live: Mapping[str, Any]) -> bool:
    """Replay may restore only the exact output this snapshot's latest review recorded."""
    try:
        history = json.loads(token.annotations.get("review_history", "[]"))
    except (TypeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("invalid existing review_history") from exc
    if not isinstance(history, list) or any(not isinstance(event, dict) for event in history):
        raise ValueError("invalid existing review_history")
    latest = next((event for event in reversed(history) if event.get("field") == key), None)
    return bool(latest is not None and latest.get("snapshot") == claimed
                and latest.get("action") == token.annotations.get(f"{key}_review_decision")
                and latest.get("action") in {"accept", "correct"}
                and live["present"] is True and latest.get("value") == live["value"])



def validate_snapshot(
    token: Token, row: Mapping[str, str | None], source_sha256: str,
) -> str:
    """Reject stale analysis/output identity; allow replay of this snapshot's own edits."""
    encoded = row.get("review_snapshot") or ""
    claimed = row.get("review_snapshot_sha256") or ""
    if not encoded and not claimed:
        if any(column in row for column in SNAPSHOT_COLUMNS):
            raise ValueError("review snapshot is missing; export a fresh review table")
        return ""  # Existing correction-only entrypoints remain usable.
    try:
        saved = json.loads(encoded, object_pairs_hook=_unique_pairs)
    except (json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("invalid review snapshot JSON") from exc
    try:
        saved_digest = digest(saved)
    except (RecursionError, ValueError) as exc:
        raise ValueError("invalid review snapshot JSON") from exc
    if not isinstance(saved, dict) or claimed != saved_digest:
        raise ValueError("review snapshot digest does not match its contents")
    current = snapshot(token, source_sha256)
    if set(saved) != set(current) or saved.get("schema") != current["schema"]:
        raise ValueError("invalid review snapshot schema")
    if saved["source_sha256"] != current["source_sha256"]:
        raise ValueError("source snapshot changed since export; export a fresh review table")
    if saved["token_identity"] != current["token_identity"]:
        raise ValueError("token source/alignment identity changed since export; export a fresh review table")
    if saved["analysis"] != current["analysis"]:
        raise ValueError("analysis identity changed since export; export a fresh review table")
    output = saved.get("output")
    if not isinstance(output, dict) or set(output) != {"fields", "lemma_source", "other"}:
        raise ValueError("invalid review snapshot output")
    fields = output["fields"]
    if not isinstance(fields, dict) or set(fields) != set(FIELDS):
        raise ValueError("invalid review snapshot fields")
    for name, record in fields.items():
        if (not isinstance(record, dict) or set(record) != {"key", "present", "value"}
                or not isinstance(record["key"], str) or type(record["present"]) is not bool
                or not isinstance(record["value"], str)):
            raise ValueError("invalid review snapshot field")
        prediction = row.get(f"pred_{name}")
        if prediction is not None and prediction != record["value"]:
            raise ValueError(f"{name} prediction changed since export; snapshot and row disagree")
        live = current["output"]["fields"][name]
        if live != record:
            key = record["key"]
            if (token.annotations.get(f"{key}_review_snapshot") != claimed
                    or token.annotations.get(f"{key}_review_decision") not in {"accept", "correct"}
                    or live["key"] != key
                    or not _reviewed_value_matches(token, key, claimed, live)):
                raise ValueError(f"{name} prediction changed since export; export a fresh review table")
            current["output"]["fields"][name] = record
    if current["output"]["lemma_source"] != output["lemma_source"]:
        if (token.annotations.get("lemma_review_snapshot") != claimed
                or token.annotations.get("lemma_review_decision") != "correct"
                or current["output"]["lemma_source"] != {"present": True, "value": "user"}):
            raise ValueError("lemma prediction changed since export; export a fresh review table")
        current["output"]["lemma_source"] = output["lemma_source"]
    if current["output"] != output:
        raise ValueError("analysis output changed since export; export a fresh review table")
    return claimed


@dataclass(frozen=True)
class Sentence:
    document_id: str
    id: str
    # Document-list indices, separate from sentence-local 1-based dependency indices.
    indices: tuple[int, ...]
    context: str


def dependency_sentences(corpus: Corpus) -> dict[tuple[str, int], Sentence]:
    """Use explicit sentence ownership only; never treat a physical line as a parse."""
    result: dict[tuple[str, int], Sentence] = {}
    seen_document_ids: set[str] = set()
    for doc in corpus.documents:
        if doc.id in seen_document_ids:
            raise ValueError("dependency review requires unique document IDs")
        seen_document_ids.add(doc.id)
        ids = [token.annotations.get("dependency_sentence_id") or (
            token.alignment.sentence_id if token.alignment is not None else None
        ) for token in doc.tokens]
        if any(sid is not None for sid in ids) and any(sid is None for sid in ids):
            raise ValueError("dependency sentence IDs must be complete for every token")
        groups: dict[str, list[int]] = {}
        previous: str | None = None
        closed: set[str] = set()
        for index, token in enumerate(doc.tokens):
            sid = token.annotations.get("dependency_sentence_id") or (
                token.alignment.sentence_id if token.alignment is not None else None
            )
            if sid != previous:
                if previous is not None:
                    closed.add(previous)
                if sid in closed:
                    raise ValueError("dependency sentence IDs must form contiguous runs")
            previous = sid
            if sid is not None:
                if token.alignment is not None and token.alignment.document_id != doc.id:
                    raise ValueError("dependency sentence belongs to a different source document")
                groups.setdefault(sid, []).append(index)
        for sid, indices in groups.items():
            explicit_indices = [doc.tokens[index].annotations.get("dependency_index") for index in indices]
            if any(value is not None for value in explicit_indices) and any(value is None for value in explicit_indices):
                raise ValueError("dependency indices must be complete for every sentence token")
            positions: set[int] = set()
            context: list[dict[str, object]] = []
            for ordinal, index in enumerate(indices, 1):
                token = doc.tokens[index]
                if token.position is None or token.position in positions:
                    raise ValueError("dependency sentence requires unique token positions")
                positions.add(token.position)
                explicit = token.annotations.get("dependency_index")
                if explicit is not None and explicit != str(ordinal):
                    raise ValueError("dependency indices must be complete and contiguous from 1")
                context.append({"index": ordinal, "position": token.position, "text": token.text,
                                "source_token_id": token.alignment.source_token_id
                                if token.alignment is not None else None})
            sentence = Sentence(doc.id, sid, tuple(indices), canonical(context))
            for index in indices:
                result[(doc.id, index)] = sentence
    return result


def validate_tree(heads: Sequence[str], relations: Sequence[str]) -> None:
    """Validate a complete sentence's proposed basic dependency tree in linear time."""
    size = len(heads)
    parsed: list[int] = []
    for index, (head, relation) in enumerate(zip(heads, relations), 1):
        if not head.isascii() or not head.isdecimal():
            raise ValueError(f"dependency head at index {index} must be an integer from 0 to {size}")
        value = int(head)
        if value > size:
            raise ValueError(f"dependency head at index {index} is outside its sentence")
        if value == index:
            raise ValueError("dependency head cannot refer to its own token")
        if not relation or any(char.isspace() for char in relation):
            raise ValueError("dependency relation must be a nonempty label without whitespace")
        if (value == 0) != (relation == "root"):
            raise ValueError("dependency root head and root relation must agree")
        parsed.append(value)
    if parsed.count(0) != 1:
        raise ValueError("dependency sentence must have exactly one root")
    completed: set[int] = {0}
    for start in range(1, size + 1):
        cursor = start
        visiting: set[int] = set()
        while cursor not in completed:
            if cursor in visiting:
                raise ValueError("dependency sentence contains a cycle")
            visiting.add(cursor)
            cursor = parsed[cursor - 1]
        completed.update(visiting)
