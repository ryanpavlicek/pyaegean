#!/usr/bin/env python3
"""Verify that a rebuilt PapyGreek fold changed only the intended sentences.

The checker compares compressed CoNLL-U artifacts before and after a fold rebuild.
It accepts sentence removal, but requires every retained sentence block to remain
byte-identical.  The regularized and diplomatic outputs must retain the same
sentence order and token layout, and may differ only in FORM and ``# text``.

The module is deliberately independent of the training or inference stack.  Its
public :func:`check_fold_correction` function returns a JSON-serializable receipt;
the command-line entry point prints the same receipt with stable JSON formatting.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, NoReturn


MAX_ARTIFACT_BYTES = 64 * 1024 * 1024
MAX_MANIFEST_BYTES = 4 * 1024 * 1024
RECEIPT_SCHEMA = 1
RECEIPT_FORMAT = "pyaegean-papygreek-fold-correction/1"


class FoldCorrectionError(ValueError):
    """Raised when a fold correction cannot be established exactly."""


class _Sentence:
    __slots__ = ("sent_id", "raw", "rows")

    def __init__(self, sent_id: str, raw: bytes, rows: tuple[tuple[str, ...], ...]) -> None:
        self.sent_id = sent_id
        self.raw = raw
        self.rows = rows


class _Artifact:
    __slots__ = ("path", "raw", "compressed_bytes", "sentences", "by_id", "sha256")

    def __init__(
        self,
        path: Path,
        raw: bytes,
        compressed_bytes: int,
        sentences: tuple[_Sentence, ...],
        sha256: str,
    ) -> None:
        self.path = path
        self.raw = raw
        self.compressed_bytes = compressed_bytes
        self.sentences = sentences
        self.by_id = {sentence.sent_id: sentence for sentence in sentences}
        self.sha256 = sha256


_SENT_ID = re.compile(r"^# sent_id = (.+)$")


def _fail(message: str) -> NoReturn:
    raise FoldCorrectionError(message)


class _BytesReader:
    """Small seekable binary reader used to avoid an unbounded gzip wrapper."""

    def __init__(self, data: bytes) -> None:
        from io import BytesIO

        self._stream = BytesIO(data)

    def read(self, size: int = -1) -> bytes:
        return self._stream.read(size)

    def seek(self, offset: int, whence: int = 0) -> int:
        return self._stream.seek(offset, whence)

    def tell(self) -> int:
        return self._stream.tell()


def _split_blocks(raw: bytes, path: Path) -> tuple[bytes, ...]:
    """Split UTF-8 CoNLL-U bytes without normalizing line endings."""
    if not (raw.endswith(b"\n\n") or raw.endswith(b"\r\n\r\n")):
        _fail(f"artifact does not end with an empty line: {path}")
    # Keep every line ending in the sentence bytes.  A blank line is a line whose
    # content is empty after removing only CR/LF; spaces on a separator are not a
    # valid CoNLL-U separator and are rejected below.
    blocks: list[bytes] = []
    current: list[bytes] = []
    for line in raw.splitlines(keepends=True):
        content = line.rstrip(b"\r\n")
        if not content:
            if current:
                blocks.append(b"".join(current))
                current = []
            continue
        current.append(line)
    if current:
        blocks.append(b"".join(current))
    if not blocks:
        _fail(f"artifact has no sentence blocks: {path}")
    return tuple(blocks)


def _parse_sentence(block: bytes, path: Path, index: int) -> _Sentence:
    text = block.decode("utf-8")
    sent_ids: list[str] = []
    rows: list[tuple[str, ...]] = []
    for line_no, line in enumerate(text.splitlines(), 1):
        match = _SENT_ID.match(line)
        if match:
            sent_id = match.group(1).strip()
            if not sent_id:
                _fail(f"empty sent_id in {path} block {index}")
            sent_ids.append(sent_id)
            continue
        if line.startswith("#"):
            continue
        fields = tuple(line.split("\t"))
        if len(fields) != 10:
            _fail(f"malformed CoNLL-U row in {path} block {index} line {line_no}")
        if not fields[0]:
            _fail(f"empty token ID in {path} block {index} line {line_no}")
        rows.append(fields)
    if len(sent_ids) != 1:
        reason = "missing" if not sent_ids else "duplicate"
        _fail(f"{reason} sent_id in {path} block {index}")
    token_ids = [row[0] for row in rows]
    expected_ids = [str(value) for value in range(1, len(rows) + 1)]
    if token_ids != expected_ids:
        _fail(f"token IDs are missing, duplicate, or reordered in {path} block {index}")
    return _Sentence(sent_ids[0], block, tuple(rows))


def _load_artifact(path: Path, *, limit: int) -> _Artifact:
    # Hash the compressed bytes exactly as received, while parsing decompressed
    # bytes for sentence identity and column checks.
    try:
        compressed = path.read_bytes()
    except OSError as exc:
        _fail(f"cannot read {path}: {exc}")
    if len(compressed) > limit:
        _fail(f"compressed input exceeds limit: {path}")
    try:
        with gzip.GzipFile(fileobj=_BytesReader(compressed), mode="rb") as gz:
            out = bytearray()
            while True:
                chunk = gz.read(min(1024 * 1024, limit + 1 - len(out)))
                if not chunk:
                    break
                out.extend(chunk)
                if len(out) > limit:
                    _fail(f"decompressed input exceeds limit: {path}")
    except FoldCorrectionError:
        raise
    except (OSError, EOFError, gzip.BadGzipFile) as exc:
        _fail(f"invalid gzip artifact {path}: {exc}")
    raw = bytes(out)
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        _fail(f"artifact is not UTF-8: {path}: {exc}")
    blocks = _split_blocks(raw, path)
    sentences = tuple(_parse_sentence(block, path, i) for i, block in enumerate(blocks, 1))
    ids = [sentence.sent_id for sentence in sentences]
    if len(ids) != len(set(ids)):
        duplicates = sorted({sid for sid in ids if ids.count(sid) > 1})
        _fail(f"duplicate sent_id in {path}: {duplicates}")
    return _Artifact(
        path, raw, len(compressed), sentences, hashlib.sha256(compressed).hexdigest()
    )


def _load_manifest(path: Path, *, limit: int) -> tuple[Mapping[str, Any], str, int]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        _fail(f"cannot read {path}: {exc}")
    if len(raw) > limit:
        _fail(f"manifest exceeds limit: {path}")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        _fail(f"manifest is not UTF-8: {path}: {exc}")
    try:
        def object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            result: dict[str, Any] = {}
            for key, child in pairs:
                if key in result:
                    _fail(f"duplicate manifest key {key!r}: {path}")
                result[key] = child
            return result

        value = json.loads(
            text,
            object_pairs_hook=object_pairs,
            parse_constant=lambda value: _fail(
                f"non-finite manifest value {value!r}: {path}"
            ),
        )
    except json.JSONDecodeError as exc:
        _fail(f"malformed manifest {path}: {exc}")
    if not isinstance(value, dict):
        _fail(f"manifest root must be an object: {path}")
    return value, hashlib.sha256(raw).hexdigest(), len(raw)


def _id_order(artifact: _Artifact) -> list[str]:
    return [sentence.sent_id for sentence in artifact.sentences]


def _assert_removal_only(old: _Artifact, new: _Artifact, label: str) -> list[str]:
    old_ids = _id_order(old)
    new_ids = _id_order(new)
    old_set, new_set = set(old_ids), set(new_ids)
    added = sorted(new_set - old_set)
    if added:
        _fail(f"{label} introduces sentence IDs: {added}")
    removed = [sid for sid in old_ids if sid not in new_set]
    retained = [sid for sid in old_ids if sid in new_set]
    if new_ids != retained:
        _fail(f"{label} changes retained sentence order")
    for sid in retained:
        if old.by_id[sid].raw != new.by_id[sid].raw:
            _fail(f"retained sentence block drift in {label}: {sid}")
    return removed


def _assert_same_ids(reg: _Artifact, orig: _Artifact, label: str) -> None:
    reg_ids, orig_ids = _id_order(reg), _id_order(orig)
    if reg_ids != orig_ids:
        _fail(f"regularized/diplomatic {label} sentence order mismatch")


def _compare_new_layers(reg: _Artifact, orig: _Artifact) -> int:
    """Check the allowed reg/orig differences and return FORM difference count."""
    _assert_same_ids(reg, orig, "new")
    differences = 0
    for reg_sentence, orig_sentence in zip(reg.sentences, orig.sentences, strict=True):
        if len(reg_sentence.rows) != len(orig_sentence.rows):
            _fail(f"regularized/diplomatic token alignment mismatch: {reg_sentence.sent_id}")
        for reg_row, orig_row in zip(reg_sentence.rows, orig_sentence.rows, strict=True):
            if reg_row[0] != orig_row[0]:
                _fail(f"regularized/diplomatic token alignment mismatch: {reg_sentence.sent_id}")
            if len(reg_row) != 10 or len(orig_row) != 10:
                _fail(f"malformed token row: {reg_sentence.sent_id}")
            if reg_row[1] != orig_row[1]:
                differences += 1
            if reg_row[2:] != orig_row[2:]:
                _fail(f"gold-column difference beyond FORM: {reg_sentence.sent_id}")
        reg_comments = [
            line for line in reg_sentence.raw.decode("utf-8").splitlines()
            if line.startswith("#") and not line.startswith("# text = ")
        ]
        orig_comments = [
            line for line in orig_sentence.raw.decode("utf-8").splitlines()
            if line.startswith("#") and not line.startswith("# text = ")
        ]
        if reg_comments != orig_comments:
            _fail(f"comment difference beyond # text: {reg_sentence.sent_id}")
    return differences


def _manifest_removed_docs(manifest: Mapping[str, Any]) -> dict[str, int]:
    work = manifest.get("work_disjointness")
    if not isinstance(work, dict):
        _fail("manifest lacks work_disjointness object")
    if work.get("result") != "pass":
        _fail("manifest work_disjointness result is not pass")
    rows = work.get("excluded_documents")
    if not isinstance(rows, list):
        _fail("manifest work_disjointness.excluded_documents must be a list")
    docs: dict[str, int] = {}
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            _fail(f"manifest excluded_documents row {index} is not an object")
        doc = row.get("document_id")
        count = row.get("sentences_newly_excluded")
        if not isinstance(doc, str) or not doc.strip():
            _fail(f"manifest excluded_documents row {index} has no document_id")
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            _fail(f"manifest excluded_documents row {index} has invalid sentences_newly_excluded")
        if count > 0:
            normalized = doc.strip()
            if normalized in docs:
                _fail("manifest has duplicate newly excluded document IDs")
            docs[normalized] = count
    declared_documents = work.get("newly_excluded_document_count")
    declared_sentences = work.get("newly_excluded_sentence_count")
    if declared_documents != len(docs):
        _fail("manifest newly excluded document count differs from its rows")
    if declared_sentences != sum(docs.values()):
        _fail("manifest newly excluded sentence count differs from its rows")
    return dict(sorted(docs.items()))


def _removed_docs(sent_ids: Sequence[str]) -> dict[str, int]:
    docs: Counter[str] = Counter()
    for sid in sent_ids:
        if not sid.startswith("papygreek:") or "@" not in sid:
            _fail(f"cannot derive document ID from removed sent_id: {sid}")
        doc, sentence = sid[len("papygreek:"):].rsplit("@", 1)
        if not doc or not sentence:
            _fail(f"malformed removed sent_id: {sid}")
        docs[doc] += 1
    return dict(sorted(docs.items()))


def check_fold_correction(
    old_regularized: str | Path,
    new_regularized: str | Path,
    old_diplomatic: str | Path,
    new_diplomatic: str | Path,
    new_regularized_manifest: str | Path,
    *,
    max_artifact_bytes: int = MAX_ARTIFACT_BYTES,
    max_manifest_bytes: int = MAX_MANIFEST_BYTES,
) -> dict[str, Any]:
    """Validate a PapyGreek fold correction and return a deterministic receipt."""
    if max_artifact_bytes <= 0 or max_manifest_bytes <= 0:
        _fail("input limits must be positive")
    old_reg = _load_artifact(Path(old_regularized), limit=max_artifact_bytes)
    new_reg = _load_artifact(Path(new_regularized), limit=max_artifact_bytes)
    old_orig = _load_artifact(Path(old_diplomatic), limit=max_artifact_bytes)
    new_orig = _load_artifact(Path(new_diplomatic), limit=max_artifact_bytes)
    manifest, manifest_hash, manifest_bytes = _load_manifest(
        Path(new_regularized_manifest), limit=max_manifest_bytes
    )

    _assert_same_ids(old_reg, old_orig, "old")
    removed_reg = _assert_removal_only(old_reg, new_reg, "regularized fold")
    removed_orig = _assert_removal_only(old_orig, new_orig, "diplomatic fold")
    if removed_reg != removed_orig:
        _fail("regularized and diplomatic removed sentence IDs differ")
    if not removed_reg:
        _fail("correction removed no sentences")
    # The new artifacts are checked against one another after each artifact has
    # separately proven removal-only behavior.
    form_differences = _compare_new_layers(new_reg, new_orig)
    removed_doc_counts = _removed_docs(removed_reg)
    manifest_docs = _manifest_removed_docs(manifest)
    if removed_doc_counts != manifest_docs:
        _fail("removed document counts differ from manifest work_disjointness")

    def token_count(artifact: _Artifact) -> int:
        return sum(len(sentence.rows) for sentence in artifact.sentences)

    receipt: dict[str, Any] = {
        "format": RECEIPT_FORMAT,
        "schema": RECEIPT_SCHEMA,
        "artifacts": {
            "old_regularized": {
                "sha256": old_reg.sha256,
                "compressed_bytes": old_reg.compressed_bytes,
                "sentences": len(old_reg.sentences),
            },
            "new_regularized": {
                "sha256": new_reg.sha256,
                "compressed_bytes": new_reg.compressed_bytes,
                "sentences": len(new_reg.sentences),
            },
            "old_diplomatic": {
                "sha256": old_orig.sha256,
                "compressed_bytes": old_orig.compressed_bytes,
                "sentences": len(old_orig.sentences),
            },
            "new_diplomatic": {
                "sha256": new_orig.sha256,
                "compressed_bytes": new_orig.compressed_bytes,
                "sentences": len(new_orig.sentences),
            },
            "new_regularized_manifest": {
                "sha256": manifest_hash,
                "bytes": manifest_bytes,
            },
        },
        "counts": {
            "old_regularized_sentences": len(old_reg.sentences),
            "new_regularized_sentences": len(new_reg.sentences),
            "old_diplomatic_sentences": len(old_orig.sentences),
            "new_diplomatic_sentences": len(new_orig.sentences),
            "removed_sentences": len(removed_reg),
            "removed_tokens": token_count(old_reg) - token_count(new_reg),
            "old_regularized_tokens": token_count(old_reg),
            "new_regularized_tokens": token_count(new_reg),
            "old_diplomatic_tokens": token_count(old_orig),
            "new_diplomatic_tokens": token_count(new_orig),
        },
        "removed_sent_ids": removed_reg,
        "removed_document_ids": sorted(removed_doc_counts),
        "removed_sentences_by_document": removed_doc_counts,
        "retained_byte_identity": {"regularized": True, "diplomatic": True},
        "form_difference_count": form_differences,
        "gold_column_difference_count": 0,
    }
    receipt["receipt_sha256"] = hashlib.sha256(
        receipt_json(receipt).encode("utf-8")
    ).hexdigest()
    return receipt


def receipt_json(receipt: Mapping[str, Any]) -> str:
    """Serialize a receipt without timestamps or other machine-dependent fields."""
    return json.dumps(receipt, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--old-reg", "--old-regularized", dest="old_reg", required=True)
    parser.add_argument("--new-reg", "--new-regularized", dest="new_reg", required=True)
    parser.add_argument("--old-orig", "--old-diplomatic", dest="old_orig", required=True)
    parser.add_argument("--new-orig", "--new-diplomatic", dest="new_orig", required=True)
    parser.add_argument(
        "--new-reg-manifest", "--new-regularized-manifest", dest="manifest", required=True
    )
    parser.add_argument(
        "--output",
        help="optional path for the canonical JSON receipt (stdout is always emitted)",
    )
    args = parser.parse_args(argv)
    try:
        receipt = check_fold_correction(
            args.old_reg, args.new_reg, args.old_orig, args.new_orig, args.manifest
        )
    except FoldCorrectionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 2
    serialized = receipt_json(receipt)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(serialized + "\n", encoding="utf-8", newline="\n")
    print(serialized)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
