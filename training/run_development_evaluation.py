"""Run one deterministic development evaluation and write private artifacts.

The runner is intentionally small and strict.  It consumes an already verified
development manifest, reconstructs exactly the manifest's selected sentences
from the supplied source files, invokes one caller-supplied pipeline, and hands
the resulting token mappings to :mod:`development_report`.  The command-line
entry point activates the shipped ``grc-joint-v3`` pipeline; tests can inject a
pipeline and therefore never need model weights or neural inference.  The mixed
development slice uses full-coverage neural overlap windows because it deliberately
retains several sentences beyond the model's single-pass subword budget.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any
import unicodedata

from aegean.greek.ud import UDSentence, UDToken, load_conllu, loads_conllu

try:  # The training directory is also used as a script directory.
    from . import development_manifest as manifest_mod
    from . import development_report as report_mod
except ImportError:  # pragma: no cover - exercised by ``python training/foo.py``
    import development_manifest as manifest_mod  # type: ignore[no-redef]
    import development_report as report_mod  # type: ignore[no-redef]

__all__ = [
    "RunnerError",
    "run_development_evaluation",
    "main",
]


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_GIT_SHA = re.compile(r"^[0-9a-f]{40}$")
_MODEL_ID = "grc-joint-v3"
_MODEL_ASSET_SHA256 = "f646d34a08dbf612abbe076c27188f077c2289da0b7bbbc7116bfe807112b06e"
_PREPROCESSING_CONFIG: dict[str, Any] = {
    "annotation_profile": "pyaegean-canonical-v1",
    "normalization": "NFC",
    "segmentation": "pretokenized",
    "special_token_policy": "roberta:<s>:0:</s>:2",
    "preprocessing_version": "pyaegean-neural-preprocessing-v1",
}
_PREPROCESSING_CONFIG_SHA256 = hashlib.sha256(
    manifest_mod.canonical_json(_PREPROCESSING_CONFIG).encode("utf-8")
).hexdigest()


class RunnerError(ValueError):
    """Raised when an evaluation input or output violates the runner contract."""


def _sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _read_manifest(value: Mapping[str, Any] | str | Path) -> dict[str, Any]:
    try:
        if isinstance(value, Mapping):
            manifest = manifest_mod.verify_document(value, "manifest_sha256")
        else:
            manifest = manifest_mod.load_document(value, verify=True, digest_field="manifest_sha256")
        manifest_mod.verify_manifest(manifest)
    except Exception as exc:
        raise RunnerError(f"invalid development manifest: {exc}") from exc
    return manifest


def _source_hash(path: str | Path, *, role: str) -> str:
    target = Path(path)
    try:
        raw = target.read_bytes()
    except OSError as exc:
        raise RunnerError(f"cannot read {role} source {target}: {exc}") from exc
    return _sha256_bytes(raw)


def _verify_source_hashes(
    manifest: Mapping[str, Any],
    *,
    perseus_dev: str | Path,
    papygreek_tagging: str | Path,
    papygreek_parse: str | Path,
) -> dict[str, str]:
    hashes = manifest.get("source_hashes")
    if not isinstance(hashes, Mapping):
        raise RunnerError("manifest source_hashes is missing")
    supplied = {
        "perseus_dev": _source_hash(perseus_dev, role="Perseus-dev"),
        "papygreek_tagging": _source_hash(papygreek_tagging, role="PapyGreek-tagging"),
        "papygreek_parse": _source_hash(papygreek_parse, role="PapyGreek-parse"),
    }
    for key, actual in supplied.items():
        expected = hashes.get(key)
        if not isinstance(expected, str) or not _SHA256.fullmatch(expected):
            raise RunnerError(f"manifest source hash for {key} is malformed")
        if actual != expected:
            raise RunnerError(
                f"{key} source hash mismatch: manifest {expected}, supplied {actual}"
            )
    return supplied


def _identity_fields(sentence: UDSentence, *, source: str) -> tuple[str, str, str, str]:
    if source not in {"perseus", "papygreek"}:
        raise RunnerError(f"unknown source family {source!r}")
    try:
        document_id, work_id, sentence_id = manifest_mod._identity(
            sentence,
            source=source,
        )
    except Exception as exc:
        raise RunnerError(f"invalid {source} source identity: {exc}") from exc
    item_id = f"{source}:{document_id}:{sentence_id}"
    return item_id, document_id, work_id, sentence_id


def _item_id(sentence: UDSentence, *, source: str) -> str:
    return _identity_fields(sentence, source=source)[0]


def _load_source(path: str | Path, *, source: str, role: str) -> dict[str, UDSentence]:
    try:
        sentences = load_conllu(path, strict=True)
    except Exception as exc:
        raise RunnerError(f"invalid {role} CoNLL-U: {exc}") from exc
    if not sentences:
        raise RunnerError(f"{role} source contains no sentences")
    result: dict[str, UDSentence] = {}
    for sentence in sentences:
        item_id = _item_id(sentence, source=source)
        if item_id in result:
            raise RunnerError(f"duplicate {role} sentence/item ID {item_id!r}")
        result[item_id] = sentence
    return result


def _token_dict(token: UDToken) -> dict[str, Any]:
    return {
        "id": int(token.id),
        "form": unicodedata.normalize("NFC", token.form),
        "lemma": token.lemma,
        "upos": token.upos,
        "xpos": token.xpos,
        "feats": token.feats,
        "head": int(token.head),
        "deprel": token.deprel,
    }


def _forms_sha256(tokens: Sequence[Mapping[str, Any]]) -> str:
    forms = tuple(str(token["form"]) for token in tokens)
    return hashlib.sha256(manifest_mod.canonical_json(forms).encode("utf-8")).hexdigest()


def _content_sha256(tokens: Sequence[Mapping[str, Any]]) -> str:
    forms = tuple(str(token["form"]) for token in tokens)
    return hashlib.sha256(
        manifest_mod.canonical_json({"forms": forms}).encode("utf-8")
    ).hexdigest()


def _reconstruct(
    manifest: Mapping[str, Any],
    *,
    perseus: Mapping[str, UDSentence],
    papy_tagging: Mapping[str, UDSentence],
    papy_parse: Mapping[str, UDSentence],
    source_hashes: Mapping[str, str],
) -> tuple[list[str], list[UDSentence], dict[str, list[dict[str, Any]]]]:
    items = manifest.get("items")
    if not isinstance(items, list):
        raise RunnerError("manifest items must be a list")
    ids = [str(item["item_id"]) for item in items if isinstance(item, Mapping)]
    if ids != sorted(ids) or len(ids) != len(set(ids)):
        raise RunnerError("manifest item IDs must be sorted and unique")
    sentences: list[UDSentence] = []
    gold: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        if not isinstance(item, Mapping):
            raise RunnerError("manifest item is not an object")
        item_id = str(item.get("item_id"))
        source = item.get("source")
        tracks = item.get("tracks")
        if not isinstance(source, str) or not isinstance(tracks, Sequence) or isinstance(tracks, str):
            raise RunnerError(f"manifest item {item_id!r} has malformed source/tracks")
        if source == "perseus":
            sentence = perseus.get(item_id)
            track = "perseus-dev"
        elif source == "papygreek":
            # A merged parse+tag item must use parse-track gold.  A tagging-only
            # item is deliberately sourced from the tagging file.
            if "parse" in tracks:
                sentence = papy_parse.get(item_id)
                track = "parse"
            else:
                sentence = papy_tagging.get(item_id)
                track = "tagging"
        else:
            raise RunnerError(f"manifest item {item_id!r} has unknown source {source!r}")
        if sentence is None:
            raise RunnerError(f"manifest item {item_id!r} is missing from its source track")
        actual_id, document_id, work_id, sentence_id = _identity_fields(
            sentence,
            source=source,
        )
        if actual_id != item_id:
            raise RunnerError(f"manifest item {item_id!r} differs from its source identity")
        for field, actual in (
            ("document_id", document_id),
            ("work_id", work_id),
            ("sentence_id", sentence_id),
        ):
            if item.get(field) != actual:
                raise RunnerError(
                    f"manifest item {item_id!r} {field} differs from its source identity"
                )
        if track not in tracks and source == "perseus":
            raise RunnerError(f"manifest item {item_id!r} has no Perseus track")
        tokens = [_token_dict(token) for token in sentence.tokens]
        if not tokens:
            raise RunnerError(f"manifest item {item_id!r} has no word tokens")
        if len(tokens) != item.get("token_count") or len(tokens) != item.get("scored_token_count"):
            raise RunnerError(f"manifest item {item_id!r} token cardinality drift")
        if _forms_sha256(tokens) != item.get("form_tuple_sha256"):
            raise RunnerError(f"manifest item {item_id!r} FORM content differs from manifest")
        if _content_sha256(tokens) != item.get("content_sha256"):
            raise RunnerError(f"manifest item {item_id!r} content differs from manifest")
        bindings = item.get("asset_sha256_by_track")
        if not isinstance(bindings, Mapping) or not isinstance(bindings.get(track), str):
            raise RunnerError(f"manifest item {item_id!r} lacks its selected track binding")
        source_key = {
            "perseus-dev": "perseus_dev",
            "tagging": "papygreek_tagging",
            "parse": "papygreek_parse",
        }[track]
        if bindings[track] != source_hashes[source_key]:
            raise RunnerError(f"manifest item {item_id!r} asset binding differs from supplied source")
        sentences.append(sentence)
        gold[item_id] = tokens
    return ids, sentences, gold


def _tokens_from_value(value: Any, *, where: str) -> list[dict[str, Any]]:
    if isinstance(value, UDSentence):
        return [_token_dict(token) for token in value.tokens]
    if isinstance(value, Mapping) and "tokens" in value:
        value = value["tokens"]
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise RunnerError(f"{where} must be a token sequence")
    result: list[dict[str, Any]] = []
    for index, token in enumerate(value):
        if isinstance(token, UDToken):
            result.append(_token_dict(token))
        elif isinstance(token, Mapping):
            required = ("id", "form", "lemma", "upos", "xpos", "feats", "head", "deprel")
            missing = [field for field in required if field not in token]
            if missing:
                raise RunnerError(f"{where}[{index}] is missing {','.join(missing)}")
            extra = sorted(set(token) - set(required))
            if extra:
                raise RunnerError(f"{where}[{index}] has unexpected fields {extra}")
            copied = dict(token)
            for field in ("form", "lemma", "upos", "xpos", "feats", "deprel"):
                if not isinstance(copied[field], str):
                    raise RunnerError(f"{where}[{index}].{field} is not a string")
            copied["form"] = unicodedata.normalize("NFC", copied["form"])
            if (
                isinstance(copied["id"], bool)
                or not isinstance(copied["id"], int)
                or copied["id"] < 1
            ):
                raise RunnerError(f"{where}[{index}].id is not a positive integer")
            if isinstance(copied["head"], bool) or not isinstance(copied["head"], int):
                raise RunnerError(f"{where}[{index}].head is not an integer")
            result.append(copied)
        else:
            raise RunnerError(f"{where}[{index}] is not a token object")
    return result


def _normalise_predictions(
    output: Any,
    *,
    ids: Sequence[str],
    input_sentences: Sequence[UDSentence],
) -> dict[str, list[dict[str, Any]]]:
    """Convert accepted pipeline output shapes while preserving and checking order."""

    input_id_by_sent_id = {
        sentence.sent_id: item_id
        for item_id, sentence in zip(ids, input_sentences, strict=True)
    }
    records: list[tuple[str | None, Any]] = []
    if isinstance(output, str):
        try:
            parsed = loads_conllu(output, strict=True)
        except Exception as exc:
            raise RunnerError(f"pipeline emitted invalid CoNLL-U: {exc}") from exc
        records = []
        for sentence in parsed:
            if not sentence.sent_id:
                raise RunnerError("pipeline CoNLL-U output contains a sentence without sent_id")
            records.append((input_id_by_sent_id.get(sentence.sent_id, "<unknown>"), sentence))
    elif isinstance(output, Mapping):
        keys = list(output)
        if keys != list(ids):
            raise RunnerError(
                f"pipeline item IDs are missing, extra, or reordered (expected {list(ids)!r}, got {keys!r})"
            )
        records = [(str(key), output[key]) for key in keys]
    elif isinstance(output, Sequence) and not isinstance(output, (bytes, bytearray)):
        if len(output) != len(ids):
            raise RunnerError(
                f"pipeline returned {len(output)} sentences, expected {len(ids)}"
            )
        for index, value in enumerate(output):
            if isinstance(value, UDSentence):
                if not value.sent_id:
                    raise RunnerError("pipeline output contains a sentence without sent_id")
                records.append((input_id_by_sent_id.get(value.sent_id, "<unknown>"), value))
            elif isinstance(value, Mapping) and "item_id" in value:
                records.append((str(value["item_id"]), value))
            else:
                records.append((None, value))
    else:
        raise RunnerError("pipeline output must be CoNLL-U text, a mapping, or a sentence sequence")

    if len(records) != len(ids):
        raise RunnerError(f"pipeline returned {len(records)} sentences, expected {len(ids)}")
    predictions: dict[str, list[dict[str, Any]]] = {}
    for index, (record_id, value) in enumerate(records):
        expected_id = ids[index]
        item_id = record_id or expected_id
        if item_id != expected_id:
            raise RunnerError(
                f"pipeline item IDs are reordered at position {index}: expected {expected_id!r}, got {item_id!r}"
            )
        if isinstance(value, UDSentence) and value.sent_id:
            embedded_id = input_id_by_sent_id.get(value.sent_id)
            if embedded_id != expected_id:
                raise RunnerError(
                    f"pipeline sentence identity disagrees with mapping at {expected_id!r}"
                )
        predictions[item_id] = _tokens_from_value(value, where=f"predictions[{item_id!r}]")
    if list(predictions) != list(ids):
        raise RunnerError("pipeline prediction mapping is not in manifest order")
    return predictions


def _verify_form_alignment(
    ids: Sequence[str], gold: Mapping[str, Sequence[Mapping[str, Any]]], predictions: Mapping[str, Sequence[Mapping[str, Any]]]
) -> None:
    for item_id in ids:
        gold_tokens = gold[item_id]
        pred_tokens = predictions[item_id]
        if len(pred_tokens) != len(gold_tokens):
            raise RunnerError(
                f"prediction token cardinality differs for {item_id}: expected {len(gold_tokens)}, got {len(pred_tokens)}"
            )
        gold_forms = [str(token["form"]) for token in gold_tokens]
        pred_forms = [str(token["form"]) for token in pred_tokens]
        if pred_forms != gold_forms:
            raise RunnerError(f"prediction FORM values differ from gold for {item_id}")


def _environment_sha(value: str | Path | Mapping[str, Any]) -> str:
    if isinstance(value, Mapping):
        try:
            raw = manifest_mod.canonical_json(value).encode("utf-8")
        except Exception as exc:
            raise RunnerError(f"environment receipt is not canonical JSON: {exc}") from exc
    else:
        target = Path(value)
        try:
            raw = target.read_bytes()
        except OSError as exc:
            raise RunnerError(f"cannot read environment receipt {target}: {exc}") from exc
    digest = _sha256_bytes(raw)
    if not _SHA256.fullmatch(digest):  # pragma: no cover - hashlib invariant
        raise RunnerError("could not compute environment receipt SHA-256")
    return digest


def _git_revision(value: str | None) -> str:
    if value is not None:
        if not _GIT_SHA.fullmatch(value):
            raise RunnerError("git_revision must be a full lowercase Git commit SHA")
        return value
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RunnerError("a full Git revision is required (pass --git-revision)") from exc
    revision = result.stdout.strip()
    if not _GIT_SHA.fullmatch(revision):
        raise RunnerError("git rev-parse HEAD did not return a full lowercase commit SHA")
    return revision


def _write_canonical(value: Any, path: Path) -> None:
    raw = manifest_mod.canonical_json(value).encode("utf-8")
    _write_bytes_atomic(raw + b"\n", path)


def _write_bytes_atomic(raw: bytes, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    handle: int | None = None
    try:
        handle, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        temporary = Path(name)
        with os.fdopen(handle, "wb") as stream:
            handle = None
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except OSError as exc:
        raise RunnerError(f"could not write artifact {path}: {exc}") from exc
    finally:
        if handle is not None:
            os.close(handle)
        if temporary is not None and temporary.exists():
            temporary.unlink(missing_ok=True)


def _content_addressed_artifact(value: Any, *, prefix: str, output_dir: Path) -> tuple[Path, str]:
    raw = manifest_mod.canonical_json(value).encode("utf-8")
    digest = _sha256_bytes(raw)
    target = output_dir / f"{prefix}-{digest}.json"
    if target.exists() and target.read_bytes() != raw + b"\n":
        raise RunnerError(f"content-addressed artifact collision at {target}")
    _write_bytes_atomic(raw + b"\n", target)
    if target.read_bytes() != raw + b"\n":
        raise RunnerError(f"{prefix} artifact readback differs from canonical content")
    if _sha256_bytes(raw) != digest:
        raise RunnerError(f"could not verify {prefix} artifact digest")
    return target, digest


def _build_run(
    *,
    environment_sha256: str,
    prediction_sha256: str,
    git_revision: str,
    run_identity: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    identity: Mapping[str, Any] = run_identity or {
        "model": {"identity": _MODEL_ID, "asset_sha256": _MODEL_ASSET_SHA256},
        "preprocessing": {
            "identity": "pyaegean-neural-preprocessing-v1",
            "config_sha256": _PREPROCESSING_CONFIG_SHA256,
        },
        "output_profile": {
            "identity": "pyaegean-canonical-v1",
            "tasks": ["parsing", "tagging"],
        },
        "decoder": {
            "identity": "pyaegean-release-single-root-mst-v2",
            "mode": "sequential",
            "long_input": "windowed",
        },
    }
    try:
        copied = json.loads(manifest_mod.canonical_json(identity))
    except Exception as exc:
        raise RunnerError(f"run_identity is not canonical JSON: {exc}") from exc
    if not isinstance(copied, dict) or set(copied) != {
        "model",
        "preprocessing",
        "output_profile",
        "decoder",
    }:
        raise RunnerError(
            "run_identity must contain exactly model, preprocessing, output_profile, and decoder"
        )
    return {
        **copied,
        "environment_receipt_sha256": environment_sha256,
        "git_revision": git_revision,
        "prediction_sha256": prediction_sha256,
    }


def run_development_evaluation(
    *,
    manifest: Mapping[str, Any] | str | Path,
    perseus_dev: str | Path,
    papygreek_tagging: str | Path,
    papygreek_parse: str | Path,
    environment_receipt: str | Path | Mapping[str, Any],
    output_dir: str | Path,
    git_revision: str | None = None,
    pipeline: Callable[..., Any] | None = None,
    run_identity: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Run and persist one development evaluation.

    ``pipeline`` is called exactly once as ``pipeline(sentences, parse=True,
    batch_size=None, long_input="windowed")``.  If omitted, the CLI path activates
    ``grc-joint-v3`` before calling ``aegean.greek.ud.pipeline_conllu``.  Windowing
    preserves every selected gold token; partial placeholder output is never scored.
    """

    checked_manifest = _read_manifest(manifest)
    source_hashes = _verify_source_hashes(
        checked_manifest,
        perseus_dev=perseus_dev,
        papygreek_tagging=papygreek_tagging,
        papygreek_parse=papygreek_parse,
    )
    perseus = _load_source(perseus_dev, source="perseus", role="Perseus-dev")
    papy_tagging = _load_source(
        papygreek_tagging, source="papygreek", role="PapyGreek-tagging"
    )
    papy_parse = _load_source(
        papygreek_parse, source="papygreek", role="PapyGreek-parse"
    )
    ids, sentences, gold = _reconstruct(
        checked_manifest,
        perseus=perseus,
        papy_tagging=papy_tagging,
        papy_parse=papy_parse,
        source_hashes=source_hashes,
    )

    if pipeline is None:
        from aegean import greek

        greek.use_neural_pipeline()
        from aegean.greek import ud

        pipeline = ud.pipeline_conllu
    try:
        output = pipeline(
            sentences,
            parse=True,
            batch_size=None,
            long_input="windowed",
        )
    except Exception as exc:
        raise RunnerError(f"development pipeline failed: {type(exc).__name__}: {exc}") from exc
    predictions = _normalise_predictions(output, ids=ids, input_sentences=sentences)
    _verify_form_alignment(ids, gold, predictions)

    environment_sha256 = _environment_sha(environment_receipt)
    prediction_raw = manifest_mod.canonical_json(predictions).encode("utf-8")
    prediction_sha256 = _sha256_bytes(prediction_raw)
    run = _build_run(
        environment_sha256=environment_sha256,
        prediction_sha256=prediction_sha256,
        git_revision=_git_revision(git_revision),
        run_identity=run_identity,
    )
    output_path = Path(output_dir)
    gold_path, gold_sha256 = _content_addressed_artifact(
        gold, prefix="gold", output_dir=output_path
    )
    prediction_path, _ = _content_addressed_artifact(
        predictions, prefix="predictions", output_dir=output_path
    )
    # The model/report contract validates the prediction digest itself.  Keep
    # source hashes in the return value for callers auditing the input closure.
    del source_hashes
    try:
        report = report_mod.build_report(
            manifest=checked_manifest,
            gold_sentences=gold,
            predictions=predictions,
            run=run,
        )
        report_mod.verify_report(report, checked_manifest)
    except Exception as exc:
        raise RunnerError(f"could not build development report: {exc}") from exc
    report_path = output_path / "development-report.json"
    manifest_mod.write_document(report, report_path, digest_field="report_sha256")
    checked_report = manifest_mod.load_document(
        report_path, verify=True, digest_field="report_sha256"
    )
    report_mod.verify_report(checked_report, checked_manifest)
    run_path = output_path / "run-receipt.json"
    _write_canonical(run, run_path)
    try:
        receipt_raw = run_path.read_bytes()
        receipt = json.loads(receipt_raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RunnerError(f"run receipt artifact readback failed: {exc}") from exc
    if receipt_raw != manifest_mod.canonical_json(run).encode("utf-8") + b"\n" or receipt != run:
        raise RunnerError("run receipt artifact readback differs from canonical receipt")
    return {
        "manifest": checked_manifest,
        "gold": gold,
        "predictions": predictions,
        "run": run,
        "report": checked_report,
        "paths": {
            "gold": str(gold_path),
            "predictions": str(prediction_path),
            "run": str(run_path),
            "report": str(report_path),
        },
        "gold_sha256": gold_sha256,
        "prediction_sha256": prediction_sha256,
        "environment_receipt_sha256": environment_sha256,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a private Greek development evaluation")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--perseus-dev", "--perseus-dev-source", required=True, type=Path)
    parser.add_argument("--papygreek-tagging", "--papygreek-tagging-source", required=True, type=Path)
    parser.add_argument("--papygreek-parse", "--papygreek-parse-source", required=True, type=Path)
    parser.add_argument("--environment-receipt", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--git-revision", default=None)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = run_development_evaluation(
            manifest=args.manifest,
            perseus_dev=args.perseus_dev,
            papygreek_tagging=args.papygreek_tagging,
            papygreek_parse=args.papygreek_parse,
            environment_receipt=args.environment_receipt,
            output_dir=args.output_dir,
            git_revision=args.git_revision,
        )
    except RunnerError as exc:
        _parser().error(str(exc))
    print(json.dumps({"report": result["paths"]["report"], "report_sha256": result["report"]["report_sha256"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
