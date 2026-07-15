"""Deterministic development reports and paired model comparisons.

The report layer deliberately knows nothing about a model.  A caller supplies a
content-addressed development manifest, gold sentences, and predictions; this module
checks their alignment and derives metrics and error anatomy from that immutable
prediction artifact.  Reports are development evidence, not published claims.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from aegean.analysis.significance import mcnemar

try:  # training helpers are imported as a top-level module in focused tests
    from development_manifest import (
        MANIFEST_FORMAT,
        canonical_json,
        document_sha256,
        load_document,
        stamp_document,
        verify_manifest,
        verify_document,
        write_document,
    )
except ImportError:  # pragma: no cover - package-style import for tooling
    from .development_manifest import (  # type: ignore[no-redef]
        MANIFEST_FORMAT,
        canonical_json,
        document_sha256,
        load_document,
        stamp_document,
        verify_manifest,
        verify_document,
        write_document,
    )


REPORT_FORMAT = "pyaegean-development-report/1"
COMPARISON_FORMAT = "pyaegean-development-comparison/1"
_METRICS = ("upos", "xpos", "ufeats", "lemma", "uas", "las", "clas")
_TAG_METRICS = _METRICS[:4]
_PARSE_METRICS = _METRICS[4:]
_REQUIRED_TOKEN_FIELDS = ("form", "lemma", "upos", "xpos", "feats", "head", "deprel")
_MAX_ITEMS = 1_000_000
_MAX_TOKENS = 20_000_000
_MAX_SAMPLES = 32
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_GIT_SHA = re.compile(r"^[0-9a-f]{40}$")
_CONTENT_DEPRELS = {
    "nsubj", "obj", "iobj", "csubj", "ccomp", "xcomp", "obl", "vocative",
    "expl", "dislocated", "advcl", "advmod", "discourse", "nmod", "appos",
    "nummod", "acl", "amod", "conj", "fixed", "flat", "compound", "list",
    "parataxis", "orphan", "goeswith", "reparandum", "root", "dep",
}
_UNIVERSAL_FEATURES = {
    "PronType", "NumType", "Poss", "Reflex", "Foreign", "Abbr", "Gender",
    "Animacy", "Number", "Case", "Definite", "Degree", "VerbForm", "Mood",
    "Tense", "Aspect", "Voice", "Evident", "Polarity", "Person", "Polite",
}


class ReportError(ValueError):
    """Raised when a manifest, prediction, or report violates its contract."""


def _exact_fields(value: Mapping[str, Any], fields: set[str], *, where: str) -> None:
    actual = set(value)
    if actual != fields:
        raise ReportError(
            f"{where} fields differ (missing={sorted(fields - actual)}, "
            f"extra={sorted(actual - fields)})"
        )


def _validate_run(
    run: Mapping[str, Any], predictions: Mapping[str, Any] | None = None
) -> None:
    _exact_fields(
        run,
        {
            "model",
            "preprocessing",
            "output_profile",
            "decoder",
            "environment_receipt_sha256",
            "git_revision",
            "prediction_sha256",
        },
        where="run",
    )
    for name, fields in (
        ("model", {"identity", "asset_sha256"}),
        ("preprocessing", {"identity", "config_sha256"}),
        ("output_profile", {"identity", "tasks"}),
        ("decoder", {"identity", "mode", "long_input"}),
    ):
        value = run.get(name)
        if not isinstance(value, Mapping):
            raise ReportError(f"run.{name} must be an object")
        _exact_fields(value, fields, where=f"run.{name}")
        identity = value.get("identity")
        if not isinstance(identity, str) or not identity:
            raise ReportError(f"run.{name}.identity must be a non-empty string")
    for where, value in (
        ("run.model.asset_sha256", run["model"]["asset_sha256"]),
        ("run.preprocessing.config_sha256", run["preprocessing"]["config_sha256"]),
        ("run.environment_receipt_sha256", run["environment_receipt_sha256"]),
        ("run.prediction_sha256", run["prediction_sha256"]),
    ):
        if not isinstance(value, str) or not _SHA256.fullmatch(value):
            raise ReportError(f"{where} must be a lowercase SHA-256")
    revision = run.get("git_revision")
    if not isinstance(revision, str) or not _GIT_SHA.fullmatch(revision):
        raise ReportError("run.git_revision must be a full lowercase Git commit")
    tasks = run["output_profile"].get("tasks")
    if (
        not isinstance(tasks, list)
        or not tasks
        or any(task not in {"tagging", "parsing"} for task in tasks)
        or tasks != sorted(set(tasks))
    ):
        raise ReportError("run.output_profile.tasks must be sorted tagging/parsing tasks")
    if run["decoder"].get("mode") != "sequential":
        raise ReportError("development reports require sequential decoding")
    if run["decoder"].get("long_input") != "windowed":
        raise ReportError("development reports require full-coverage windowed long input")
    if predictions is not None:
        actual_prediction_sha256 = hashlib.sha256(
            canonical_json(predictions).encode("utf-8")
        ).hexdigest()
        if run["prediction_sha256"] != actual_prediction_sha256:
            raise ReportError(
                "run.prediction_sha256 does not match the supplied prediction artifact"
            )


_UNAVAILABLE_METRIC_REASONS = {
    "parser-not-requested",
    "tagger-not-requested",
    "no-scored-tokens",
}


def _metric_integer(value: Any, *, where: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ReportError(f"{where} must be a non-negative integer")
    return value


def _metric_number(value: Any, *, where: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ReportError(f"{where} must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise ReportError(f"{where} must be a finite number")
    return result


def _verify_ci(
    value: Any,
    *,
    where: str,
    protocol: Mapping[str, Any],
    expected_seed: int,
) -> None:
    if not isinstance(value, Mapping):
        raise ReportError(f"{where} must be an object")
    expected_level = float(protocol["level"])
    expected_resamples = int(protocol["n_resamples"])
    if value.get("reason") == "fewer-than-two-items":
        _exact_fields(
            value,
            {"low", "high", "level", "n_resamples", "reason"},
            where=where,
        )
        if value.get("low") is not None or value.get("high") is not None:
            raise ReportError(f"{where} sparse interval bounds must be null")
    else:
        _exact_fields(
            value,
            {"low", "high", "level", "n_resamples", "seed"},
            where=where,
        )
        low = _metric_number(value.get("low"), where=f"{where}.low")
        high = _metric_number(value.get("high"), where=f"{where}.high")
        if not 0.0 <= low <= high <= 1.0:
            raise ReportError(f"{where} bounds must satisfy 0 <= low <= high <= 1")
        if value.get("seed") != expected_seed:
            raise ReportError(f"{where}.seed differs from the report protocol")
    if value.get("level") != expected_level:
        raise ReportError(f"{where}.level differs from the report protocol")
    if value.get("n_resamples") != expected_resamples:
        raise ReportError(f"{where}.n_resamples differs from the report protocol")


def _verify_metric_entry(
    entry: Any,
    *,
    metric: str,
    where: str,
    aggregate: bool,
    protocol: Mapping[str, Any],
    expected_seed: int,
) -> tuple[int, int]:
    if not isinstance(entry, Mapping):
        raise ReportError(f"{where} must be an object")
    if entry.get("value") is None:
        _exact_fields(
            entry,
            {"numerator", "denominator", "value", "reason", "ci"},
            where=where,
        )
        numerator = _metric_integer(entry.get("numerator"), where=f"{where}.numerator")
        denominator = _metric_integer(
            entry.get("denominator"), where=f"{where}.denominator"
        )
        if numerator != 0 or denominator != 0 or entry.get("ci") is not None:
            raise ReportError(f"{where} unavailable metric must have zero counts and null CI")
        reason = entry.get("reason")
        if reason not in _UNAVAILABLE_METRIC_REASONS:
            raise ReportError(f"{where} has an unknown unavailable reason")
        if reason == "parser-not-requested" and metric not in _PARSE_METRICS:
            raise ReportError(f"{where} uses a parser reason for a tagging metric")
        if reason == "tagger-not-requested" and metric not in _TAG_METRICS:
            raise ReportError(f"{where} uses a tagger reason for a parsing metric")
        return numerator, denominator

    fields = {"numerator", "denominator", "value"}
    if aggregate:
        fields |= {"ci", "official_value"}
    _exact_fields(entry, fields, where=where)
    numerator = _metric_integer(entry.get("numerator"), where=f"{where}.numerator")
    denominator = _metric_integer(
        entry.get("denominator"), where=f"{where}.denominator"
    )
    if denominator < 1 or numerator > denominator:
        raise ReportError(f"{where} counts must satisfy 0 <= numerator <= denominator")
    value = _metric_number(entry.get("value"), where=f"{where}.value")
    if not 0.0 <= value <= 1.0 or not math.isclose(
        value,
        numerator / denominator,
        abs_tol=1e-12,
    ):
        raise ReportError(f"{where}.value differs from its counts")
    if aggregate:
        official = _metric_number(
            entry.get("official_value"), where=f"{where}.official_value"
        )
        if not math.isclose(value, official, abs_tol=1e-12):
            raise ReportError(f"{where} lacks official-evaluator parity")
        _verify_ci(
            entry.get("ci"),
            where=f"{where}.ci",
            protocol=protocol,
            expected_seed=expected_seed,
        )
    return numerator, denominator


def _finite(value: Any, path: str = "value") -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ReportError(f"nonfinite value at {path}")
    if isinstance(value, Mapping):
        for key, child in value.items():
            _finite(child, f"{path}.{key}")
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for i, child in enumerate(value):
            _finite(child, f"{path}[{i}]")


def _json_copy(value: Any) -> Any:
    try:
        result = copy.deepcopy(value)
        json.dumps(result, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ReportError("report input must be JSON-compatible and finite") from exc
    _finite(result)
    return result


def _item_map(manifest: Mapping[str, Any]) -> tuple[dict[str, Mapping[str, Any]], list[str]]:
    try:
        verify_manifest(manifest)
    except Exception as exc:
        raise ReportError(f"invalid development manifest: {exc}") from exc
    items = manifest.get("items")
    if not isinstance(items, list):
        raise ReportError("manifest items must be a list")
    if len(items) > _MAX_ITEMS:
        raise ReportError("manifest has too many items")
    result: dict[str, Mapping[str, Any]] = {}
    for i, item in enumerate(items):
        if not isinstance(item, Mapping):
            raise ReportError(f"manifest item {i} is not an object")
        item_id = item.get("item_id")
        if not isinstance(item_id, str) or not item_id:
            raise ReportError(f"manifest item {i} has no item_id")
        if item_id in result:
            raise ReportError(f"duplicate manifest item_id: {item_id}")
        for field in ("source", "asset_sha256", "document_id", "work_id", "sentence_id"):
            if not isinstance(item.get(field), str) or not item[field]:
                raise ReportError(f"manifest item {item_id} missing {field}")
        result[item_id] = item
    ids = sorted(result)
    if [str(item.get("item_id")) for item in items] != ids:
        raise ReportError("manifest items must be sorted by item_id")
    return result, ids


def _sentence_tokens(value: Any, *, where: str) -> list[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        if set(value) - {"tokens", "sentence_id", "item_id"}:
            raise ReportError(f"unexpected sentence fields at {where}")
        value = value.get("tokens")
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ReportError(f"{where} must be a token array")
    if len(value) > _MAX_TOKENS:
        raise ReportError(f"{where} has too many tokens")
    tokens: list[Mapping[str, Any]] = []
    for i, token in enumerate(value):
        if not isinstance(token, Mapping):
            raise ReportError(f"{where}[{i}] must be an object")
        missing = [field for field in _REQUIRED_TOKEN_FIELDS if field not in token]
        if missing:
            raise ReportError(f"{where}[{i}] missing {','.join(missing)}")
        for field in _REQUIRED_TOKEN_FIELDS[:5] + ("deprel",):
            if not isinstance(token[field], str):
                raise ReportError(f"{where}[{i}].{field} must be a string")
        head = token["head"]
        if isinstance(head, bool) or not isinstance(head, int):
            raise ReportError(f"{where}[{i}].head must be an integer")
        if "id" in token and (isinstance(token["id"], bool) or not isinstance(token["id"], int) or token["id"] < 1):
            raise ReportError(f"{where}[{i}].id must be a positive integer")
        # The upper bound depends on sentence length and is checked by caller.
        tokens.append(token)
    ids = [int(token["id"]) for token in tokens if "id" in token]
    if ids and (len(ids) != len(tokens) or ids != list(range(1, len(tokens) + 1))):
        raise ReportError(f"{where} token IDs are missing, duplicate, or reordered")
    return tokens


def _validate_sentences(
    ids: Sequence[str], values: Mapping[str, Any], *, name: str
) -> dict[str, list[Mapping[str, Any]]]:
    if not isinstance(values, Mapping):
        raise ReportError(f"{name} must be a mapping keyed by item_id")
    _finite(values, name)
    keys = list(values)
    if any(not isinstance(key, str) for key in keys):
        raise ReportError(f"{name} keys must be strings")
    missing = sorted(set(ids) - set(keys))
    extra = sorted(set(keys) - set(ids))
    if missing or extra:
        raise ReportError(
            f"{name} item IDs do not match manifest (missing={missing[:3]}, extra={extra[:3]})"
        )
    out: dict[str, list[Mapping[str, Any]]] = {}
    total = 0
    for item_id in ids:
        tokens = _sentence_tokens(values[item_id], where=f"{name}[{item_id!r}]")
        for i, token in enumerate(tokens):
            if token["head"] < 0 or token["head"] > len(tokens):
                raise ReportError(f"{name}[{item_id!r}][{i}].head is out of range")
        total += len(tokens)
        if total > _MAX_TOKENS:
            raise ReportError("input has too many tokens")
        out[item_id] = tokens
    return out


def _manifest_gold(item: Mapping[str, Any]) -> Any:
    for key in ("tokens", "gold_tokens", "sentence"):
        if key in item:
            return item[key]
    return None


def _task_set(manifest: Mapping[str, Any], item: Mapping[str, Any], run: Mapping[str, Any]) -> set[str]:
    requested: Any = run.get("tasks")
    if requested is None and isinstance(run.get("output_profile"), Mapping):
        requested = run["output_profile"].get("tasks")
    available: Any = item.get("tasks", manifest.get("tasks"))

    def normalize(raw: Any, *, where: str) -> set[str]:
        if raw is None:
            return {"tagging", "parsing"}
        if isinstance(raw, str):
            values = [raw]
        elif not isinstance(raw, Sequence) or isinstance(raw, (bytes, bytearray)):
            raise ReportError(f"{where} tasks must be a string or array")
        else:
            values = list(raw)
        aliases = {
            "parse": "parsing",
            "parser": "parsing",
            "parsing": "parsing",
            "dependency": "parsing",
            "syntax": "parsing",
            "tag": "tagging",
            "tagging": "tagging",
        }
        normalized: set[str] = set()
        for value in values:
            key = str(value).lower()
            if key not in aliases:
                raise ReportError(f"{where} contains unknown task {value!r}")
            normalized.add(aliases[key])
        return normalized

    return normalize(requested, where="run") & normalize(available, where="item")


def _tagger_applicable(
    manifest: Mapping[str, Any], item: Mapping[str, Any], run: Mapping[str, Any]
) -> bool:
    return "tagging" in _task_set(manifest, item, run)


def _parser_applicable(manifest: Mapping[str, Any], item: Mapping[str, Any], run: Mapping[str, Any]) -> bool:
    tasks = _task_set(manifest, item, run)
    if run.get("parse") is False or run.get("parser") is False:
        return False
    return "parsing" in tasks


def _canon_feats(value: str) -> str:
    # CoNLL-U treats an absent feature set and '_' identically.  Sort only the
    # canonical key/value representation; leave unusual opaque values intact.
    if value in ("", "_"):
        return "_"
    universal = [
        feature
        for feature in value.split("|")
        if feature.split("=", 1)[0] in _UNIVERSAL_FEATURES
    ]
    return "|".join(sorted(universal)) or "_"


def _forms_sha256(tokens: Sequence[Mapping[str, Any]]) -> str:
    forms = [token["form"] for token in tokens]
    return hashlib.sha256(canonical_json(forms).encode("utf-8")).hexdigest()


def _metric_hit(metric: str, gold: Mapping[str, Any], pred: Mapping[str, Any]) -> bool:
    if metric == "upos":
        return gold["upos"] == pred["upos"]
    if metric == "xpos":
        return gold["xpos"] == pred["xpos"]
    if metric == "ufeats":
        return _canon_feats(gold["feats"]) == _canon_feats(pred["feats"])
    if metric == "lemma":
        return gold["lemma"] == "_" or gold["lemma"] == pred["lemma"]
    if metric == "uas":
        return gold["head"] == pred["head"]
    if metric == "las":
        return (
            gold["head"] == pred["head"]
            and str(gold["deprel"]).split(":", 1)[0]
            == str(pred["deprel"]).split(":", 1)[0]
        )
    raise ReportError(f"unknown metric: {metric}")


def _metric_counts(
    metric: str,
    gold: Mapping[str, Any],
    pred: Mapping[str, Any],
) -> tuple[int, int]:
    """Return additive counts whose ratio is the official metric value.

    Most CoNLL metrics are aligned-word accuracy and contribute ``hit / 1``.
    CLAS is different: the official evaluator reports F1 over gold and system
    content-relation sets.  Its additive form is therefore
    ``2 * true_positives / (gold_content + system_content)``.  Treating CLAS as
    accuracy over gold content words silently ignores false-positive content
    relations and does not reproduce the official scorer.
    """
    if metric != "clas":
        return int(_metric_hit(metric, gold, pred)), 1
    gold_content = str(gold["deprel"]).split(":", 1)[0] in _CONTENT_DEPRELS
    pred_content = str(pred["deprel"]).split(":", 1)[0] in _CONTENT_DEPRELS
    denominator = int(gold_content) + int(pred_content)
    correct = gold_content and _metric_hit("las", gold, pred)
    return 2 * int(correct), denominator


def _quantile(values: Sequence[float], q: float) -> float:
    ordered = sorted(values)
    pos = q * (len(ordered) - 1)
    lo = math.floor(pos)
    hi = math.ceil(pos)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (pos - lo)


def _rng(seed: int):
    state = int(seed) & 0xFFFFFFFF

    def next_float() -> float:
        nonlocal state
        state = (state + 0x6D2B79F5) & 0xFFFFFFFF
        z = state
        z = ((z ^ (z >> 15)) * (z | 1)) & 0xFFFFFFFF
        z ^= (z + (((z ^ (z >> 7)) * (z | 61)) & 0xFFFFFFFF)) & 0xFFFFFFFF
        z ^= z >> 14
        return (z & 0xFFFFFFFF) / 4294967296.0

    return next_float


def _ci(
    counts: Sequence[tuple[int, int]], *, n_resamples: int, level: float, seed: int
) -> dict[str, Any]:
    counts = [value for value in counts if value[1] > 0]
    n = len(counts)
    if n < 2:
        return {"low": None, "high": None, "level": level, "n_resamples": n_resamples,
                "reason": "fewer-than-two-items"}
    rng = _rng(seed)
    draws: list[float] = []
    for _ in range(n_resamples):
        sample = [counts[int(rng() * n)] for _ in range(n)]
        numerator = sum(value[0] for value in sample)
        denominator = sum(value[1] for value in sample)
        draws.append(numerator / denominator if denominator else 0.0)
    alpha = (1.0 - level) / 2.0
    return {"low": _quantile(draws, alpha), "high": _quantile(draws, 1.0 - alpha),
            "level": level, "n_resamples": n_resamples, "seed": seed}


def _metric_entry(
    values: Sequence[tuple[int, int]], *, n_resamples: int, level: float, seed: int,
    reason: str | None = None,
) -> dict[str, Any]:
    numerator = sum(n for n, _ in values)
    denominator = sum(d for _, d in values)
    out: dict[str, Any] = {"numerator": numerator, "denominator": denominator,
                           "value": numerator / denominator if denominator else None}
    if reason:
        out["reason"] = reason
        out["ci"] = None
    elif not denominator:
        out["reason"] = "no-scored-tokens"
        out["ci"] = None
    else:
        out["ci"] = _ci(
            values,
            n_resamples=n_resamples, level=level, seed=seed,
        )
    return out


def _paired_ci(
    candidate: Sequence[tuple[int, int]],
    baseline: Sequence[tuple[int, int]],
    *,
    n_resamples: int,
    level: float,
    seed: int,
) -> dict[str, Any]:
    if len(candidate) != len(baseline) or len(candidate) < 2:
        raise ReportError("paired bootstrap requires at least two aligned items")
    n = len(candidate)

    def accuracy(rows: Sequence[tuple[int, int]]) -> float:
        denominator = sum(row[1] for row in rows)
        return sum(row[0] for row in rows) / denominator if denominator else 0.0

    point = accuracy(candidate) - accuracy(baseline)
    rng = _rng(seed)
    draws: list[float] = []
    for _ in range(n_resamples):
        indices = [int(rng() * n) for _ in range(n)]
        draws.append(
            accuracy([candidate[index] for index in indices])
            - accuracy([baseline[index] for index in indices])
        )
    alpha = (1.0 - level) / 2.0
    return {
        "difference": point,
        "mean_resampled_difference": math.fsum(draws) / len(draws),
        "low": _quantile(draws, alpha),
        "high": _quantile(draws, 1.0 - alpha),
        "level": level,
        "n_resamples": n_resamples,
        "seed": seed,
        "resampling_unit": "paired-sentence",
        "estimand": "official-token-micro-accuracy-difference",
    }


def _profile_values(item: Mapping[str, Any]) -> list[str]:
    result: list[str] = []
    for key in ("source", "profile", "profile_id", "domain", "domain_id", "annotation_convention"):
        value = item.get(key)
        if isinstance(value, str) and value:
            result.append(value)
    for key in ("profiles", "profile_ids", "domain_ids", "annotation_conventions"):
        raw = item.get(key)
        if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes, bytearray)):
            result.extend(str(v) for v in raw)
    return sorted(set(result)) or ["unprofiled"]


def _slice_ids(manifest: Mapping[str, Any], item_id: str, item: Mapping[str, Any]) -> list[str]:
    raw = item.get("slice_ids", item.get("slices"))
    result: set[str] = set()
    if isinstance(raw, str):
        result.add(raw)
    elif isinstance(raw, Sequence) and not isinstance(raw, (bytes, bytearray)):
        result.update(str(value) for value in raw)
    slices = manifest.get("slices")
    if isinstance(slices, Mapping):
        for slice_id, entry in slices.items():
            if isinstance(entry, Mapping) and isinstance(entry.get("item_ids"), Sequence) and not isinstance(entry.get("item_ids"), (str, bytes, bytearray)):
                if item_id in entry["item_ids"]:
                    result.add(str(slice_id))
    return sorted(result)


def _freq_band(value: Any) -> str:
    if value is None:
        return "oov"
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ReportError("token frequency must be a non-negative integer")
    if value == 0:
        return "oov"
    if value == 1:
        return "1"
    if value <= 5:
        return "2-5"
    if value <= 50:
        return "6-50"
    return "51+"


def _frequency(item: Mapping[str, Any], index: int, token: Mapping[str, Any]) -> Any:
    if "frequency" in token:
        return token["frequency"]
    for key in ("token_frequencies", "train_token_frequencies", "frequencies", "train_frequency"):
        value = item.get(key)
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            return value[index] if index < len(value) else None
    return None


def _anatomy(
    records: Sequence[Mapping[str, Any]], gold: Mapping[str, list[Mapping[str, Any]]],
    pred: Mapping[str, list[Mapping[str, Any]]], items: Mapping[str, Mapping[str, Any]],
    *, max_samples: int = _MAX_SAMPLES,
    manifest: Mapping[str, Any] | None = None, run: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    def one(item_ids: Sequence[str], *, restrict_task: str | None = None) -> dict[str, Any]:
        counts: dict[str, int] = {metric: 0 for metric in _METRICS}
        denoms: dict[str, int] = {metric: 0 for metric in _METRICS}
        pos_conf: Counter[tuple[str, str]] = Counter()
        lemma_conf: Counter[tuple[str, str]] = Counter()
        label_counts: dict[str, dict[str, list[int]]] = defaultdict(
            lambda: defaultdict(lambda: [0, 0])
        )
        samples: list[dict[str, Any]] = []
        bands: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])
        for item_id in item_ids:
            gs, ps = gold[item_id], pred[item_id]
            item = items[item_id]
            tagger = _tagger_applicable(manifest or {}, item, run or {})
            parser = _parser_applicable(manifest or {}, item, run or {})
            if restrict_task == "tagging":
                parser = False
            elif restrict_task == "parsing":
                tagger = False
            for ti, (g, p) in enumerate(zip(gs, ps, strict=True)):
                if tagger:
                    for metric in _TAG_METRICS:
                        numerator, denominator = _metric_counts(metric, g, p)
                        denoms[metric] += denominator
                        counts[metric] += numerator
                        label = (
                            g["upos"]
                            if metric == "upos"
                            else g["xpos"]
                            if metric == "xpos"
                            else g["lemma"]
                            if metric == "lemma"
                            else _canon_feats(g["feats"])
                        )
                        label_counts[metric][str(label)][0] += numerator
                        label_counts[metric][str(label)][1] += denominator
                if parser:
                    for metric in _PARSE_METRICS:
                        numerator, denominator = _metric_counts(metric, g, p)
                        if not denominator:
                            continue
                        denoms[metric] += denominator
                        counts[metric] += numerator
                        label_counts[metric][str(g["deprel"])][0] += numerator
                        label_counts[metric][str(g["deprel"])][1] += denominator
                if tagger:
                    if g["upos"] != p["upos"]:
                        pos_conf[(g["upos"], p["upos"])] += 1
                    if not _metric_hit("lemma", g, p):
                        lemma_conf[(g["lemma"], p["lemma"])] += 1
                    band = _freq_band(_frequency(item, ti, g))
                    bands[band][0] += 1
                    bands[band][1] += g["upos"] == p["upos"]
                    bands[band][2] += _metric_hit("lemma", g, p)
                applicable_metrics = (
                    (_TAG_METRICS if tagger else ())
                    + (_PARSE_METRICS if parser else ())
                )
                wrong = []
                for metric in applicable_metrics:
                    numerator, denominator = _metric_counts(metric, g, p)
                    if denominator and numerator != denominator:
                        wrong.append(metric)
                if len(samples) < max_samples and wrong:
                    samples.append({"item_id": item_id, "token_index": ti,
                                    "form": g["form"], "gold_upos": g["upos"],
                                    "pred_upos": p["upos"], "gold_lemma": g["lemma"],
                                    "pred_lemma": p["lemma"], "wrong_metrics": wrong})
        per_label = {
            metric: {
                label: {
                    "numerator": values[0],
                    "denominator": values[1],
                    "value": values[0] / values[1] if values[1] else None,
                }
                for label, values in sorted(label_counts[metric].items())
            }
            for metric in sorted(label_counts)
        }
        return {
            "denominators": denoms, "correct": counts,
            "pos_confusions": [[g, p, n] for (g, p), n in sorted(pos_conf.items(), key=lambda x: (-x[1], x[0]))],
            "lemma_confusions": [[g, p, n] for (g, p), n in sorted(lemma_conf.items(), key=lambda x: (-x[1], x[0]))],
            "per_label": per_label,
            "frequency_bands": {band: {"tokens": vals[0], "upos_correct": vals[1],
                                        "lemma_correct": vals[2]} for band, vals in sorted(bands.items())},
            "samples": samples,
        }

    groups: dict[str, Any] = {"overall": one(sorted(items))}
    source_groups: dict[str, list[str]] = defaultdict(list)
    profile_groups: dict[str, list[str]] = defaultdict(list)
    for item_id in sorted(items):
        source_groups[str(items[item_id].get("source", "unknown"))].append(item_id)
        for profile in _profile_values(items[item_id]):
            profile_groups[profile].append(item_id)
    groups["by_source"] = {key: one(ids) for key, ids in sorted(source_groups.items())}
    groups["by_profile"] = {key: one(ids) for key, ids in sorted(profile_groups.items())}
    task_groups: dict[str, list[str]] = defaultdict(list)
    for item_id in sorted(items):
        raw_tasks = items[item_id].get("tasks", ["tagging"])
        if isinstance(raw_tasks, str):
            raw_tasks = [raw_tasks]
        if isinstance(raw_tasks, Sequence):
            for task in raw_tasks:
                task_groups[str(task)].append(item_id)
    groups["by_task"] = {
        key: one(ids, restrict_task="parsing" if key in {"parse", "parser", "parsing"} else "tagging")
        for key, ids in sorted(task_groups.items())
    }
    slices: dict[str, list[str]] = defaultdict(list)
    record_slices = {str(record.get("item_id")): record.get("slice_ids", []) for record in records}
    for item_id in sorted(items):
        raw = record_slices.get(item_id, items[item_id].get("slice_ids", items[item_id].get("slices", [])))
        if isinstance(raw, str):
            raw = [raw]
        if isinstance(raw, Sequence):
            for value in raw:
                slices[str(value)].append(item_id)
    groups["by_slice"] = {key: one(ids) for key, ids in sorted(slices.items())}
    return groups


def _official_scores(
    gold: Mapping[str, list[Mapping[str, Any]]], pred: Mapping[str, list[Mapping[str, Any]]],
    metric_item_ids: Mapping[str, Sequence[str]],
) -> tuple[dict[str, float], dict[str, Any]]:
    """Return official CoNLL scores and a content binding for the evaluator."""
    try:
        from aegean.greek.ud import _eval_module

        ev = _eval_module()
        import io

        evaluator_path = Path(str(ev.__file__)).resolve()
        evaluator = {
            "identity": "CoNLL 2018 UD evaluator",
            "sha256": hashlib.sha256(evaluator_path.read_bytes()).hexdigest(),
            "source": "https://universaldependencies.org/conll18/conll18_ud_eval.py",
        }
        def text(rows: Mapping[str, list[Mapping[str, Any]]], item_ids: Sequence[str]) -> str:
            lines: list[str] = []
            for item_id in item_ids:
                for index, token in enumerate(rows[item_id], 1):
                    lines.append("\t".join((str(index), token["form"], token["lemma"], token["upos"],
                                             token["xpos"], token["feats"], str(token["head"]),
                                             token["deprel"], "_", "_")))
                lines.append("")
            return "\n".join(lines) + "\n"

        names = {"upos": "UPOS", "xpos": "XPOS", "ufeats": "UFeats", "lemma": "Lemmas",
                 "uas": "UAS", "las": "LAS", "clas": "CLAS"}
        result: dict[str, float] = {}
        score_cache: dict[tuple[str, ...], Mapping[str, Any]] = {}
        for metric in sorted(metric_item_ids):
            item_ids = tuple(metric_item_ids[metric])
            if not item_ids:
                continue
            if item_ids not in score_cache:
                score_cache[item_ids] = ev.evaluate(
                    ev.load_conllu(io.StringIO(text(gold, item_ids))),
                    ev.load_conllu(io.StringIO(text(pred, item_ids))),
                )
            result[metric] = float(score_cache[item_ids][names[metric]].f1)
        return result, evaluator
    except Exception as exc:
        raise ReportError(
            f"official CoNLL evaluator is required: {type(exc).__name__}: {exc}"
        ) from exc


def build_report(
    *, manifest: Mapping[str, Any], gold_sentences: Mapping[str, Any],
    predictions: Mapping[str, Any], run: Mapping[str, Any], n_resamples: int = 999,
    level: float = 0.95, seed: int = 0,
) -> dict[str, Any]:
    """Validate aligned output and return a stamped deterministic report."""
    if n_resamples < 1:
        raise ReportError("n_resamples must be at least 1")
    if not isinstance(level, (int, float)) or isinstance(level, bool) or not 0 < level < 1:
        raise ReportError("level must be in (0, 1)")
    manifest = _json_copy(manifest)
    run = _json_copy(run)
    _finite(manifest)
    if not isinstance(run, Mapping):
        raise ReportError("run must be an object")
    _validate_run(run, predictions)
    items, ids = _item_map(manifest)
    gold = _validate_sentences(ids, gold_sentences, name="gold_sentences")
    pred = _validate_sentences(ids, predictions, name="predictions")
    for item_id in ids:
        if any(g["form"] != p["form"] for g, p in zip(gold[item_id], pred[item_id], strict=True)):
            raise ReportError(f"prediction FORM values differ from gold for {item_id}")
        expected = _manifest_gold(items[item_id])
        if expected is not None:
            expected_tokens = _sentence_tokens(expected, where=f"manifest.items[{item_id!r}].tokens")
            if len(expected_tokens) != len(gold[item_id]):
                raise ReportError(f"gold sentence cardinality differs from manifest for {item_id}")
        item = items[item_id]
        if isinstance(item.get("form_tuple_sha256"), str) and _forms_sha256(gold[item_id]) != item["form_tuple_sha256"]:
            raise ReportError(f"gold FORM content differs from manifest for {item_id}")
        if isinstance(item.get("token_count"), int) and item["token_count"] != len(gold[item_id]):
            raise ReportError(f"gold token cardinality differs from manifest for {item_id}")

    total_tokens = sum(len(gold[item_id]) for item_id in ids)
    if total_tokens > _MAX_TOKENS:
        raise ReportError("input has too many tokens")
    item_records: list[dict[str, Any]] = []
    metric_values: dict[str, list[tuple[int, int]]] = {metric: [] for metric in _METRICS}
    for item_id in ids:
        item = items[item_id]
        tagger = _tagger_applicable(manifest, item, run)
        parser = _parser_applicable(manifest, item, run)
        counts: dict[str, int] = {metric: 0 for metric in _METRICS}
        denoms: dict[str, int] = {metric: 0 for metric in _METRICS}
        for gold_token, pred_token in zip(gold[item_id], pred[item_id], strict=True):
            for metric in (_TAG_METRICS if tagger else ()) + (_PARSE_METRICS if parser else ()):
                numerator, denominator = _metric_counts(metric, gold_token, pred_token)
                if not denominator:
                    continue
                denoms[metric] += denominator
                counts[metric] += numerator
        item_metrics: dict[str, Any] = {}
        for metric in _METRICS:
            unavailable_reason = None
            if metric in _TAG_METRICS and not tagger:
                unavailable_reason = "tagger-not-requested"
            elif metric in _PARSE_METRICS and not parser:
                unavailable_reason = "parser-not-requested"
            if unavailable_reason is not None:
                item_metrics[metric] = {"numerator": 0, "denominator": 0, "value": None,
                                        "reason": unavailable_reason, "ci": None}
            elif not denoms[metric]:
                item_metrics[metric] = {
                    "numerator": 0,
                    "denominator": 0,
                    "value": None,
                    "reason": "no-scored-tokens",
                    "ci": None,
                }
            else:
                value = counts[metric] / denoms[metric] if denoms[metric] else None
                item_metrics[metric] = {"numerator": counts[metric], "denominator": denoms[metric],
                                        "value": value}
                metric_values[metric].append((counts[metric], denoms[metric]))
        item_records.append({
            "item_id": item_id, "source": item["source"], "asset_sha256": item["asset_sha256"],
            "document_id": item["document_id"], "work_id": item["work_id"],
            "sentence_id": item["sentence_id"], "profile_ids": _profile_values(item),
            "tasks": sorted(
                str(task) for task in (
                    item.get("tasks", ["tagging"])
                    if isinstance(item.get("tasks", ["tagging"]), Sequence)
                    and not isinstance(item.get("tasks", ["tagging"]), str)
                    else [item.get("tasks", "tagging")]
                )
            ),
            "slice_ids": _slice_ids(manifest, item_id, item),
            "token_count": len(gold[item_id]), "scored_token_count": len(gold[item_id]),
            "metrics": item_metrics,
        })
    metrics: dict[str, Any] = {}
    for index, metric in enumerate(_METRICS):
        available_any = any(item["metrics"][metric].get("value") is not None for item in item_records)
        if not available_any:
            unavailable = (
                "parser-not-requested"
                if metric in _PARSE_METRICS
                else "tagger-not-requested"
            )
            reasons = {
                item["metrics"][metric].get("reason") for item in item_records
            }
            reason = unavailable if reasons == {unavailable} else "no-scored-tokens"
            metrics[metric] = {"numerator": 0, "denominator": 0, "value": None,
                               "reason": reason, "ci": None}
        else:
            metrics[metric] = _metric_entry(metric_values[metric], n_resamples=n_resamples,
                                            level=float(level), seed=seed + index)
    metric_item_ids = {
        metric: [
            item["item_id"]
            for item in item_records
            if item["metrics"][metric].get("value") is not None
        ]
        for metric in _METRICS
        if metrics[metric]["value"] is not None
    }
    official, evaluator = _official_scores(gold, pred, metric_item_ids)
    for metric, value in official.items():
        if not math.isclose(float(metrics[metric]["value"]), value, abs_tol=1e-12):
            raise ReportError(
                f"internal {metric} metric does not match the official evaluator "
                f"({metrics[metric]['value']} != {value})"
            )
        metrics[metric]["official_value"] = value
    slice_entries: dict[str, Any] = {}
    manifest_slices = manifest.get("slices", {})
    if isinstance(manifest_slices, Mapping):
        for slice_id in sorted(manifest_slices):
            value = manifest_slices[slice_id]
            if isinstance(value, Mapping):
                entry = _json_copy(value)
            else:
                entry = {"rule": value}
            declared_ids = entry.get("item_ids") if isinstance(entry, Mapping) else None
            entry["item_ids"] = [item_id for item_id in ids
                                  if item_id in declared_ids] if isinstance(declared_ids, Sequence) and not isinstance(declared_ids, (str, bytes, bytearray)) else []
            slice_entries[str(slice_id)] = entry
    report: dict[str, Any] = {
        "format": REPORT_FORMAT, "manifest_format": MANIFEST_FORMAT,
        "manifest_sha256": manifest.get("manifest_sha256", document_sha256(manifest, "manifest_sha256")),
        "claim_status": "development-only-not-published", "run": run,
        "evaluator": evaluator,
        "protocol": {"n_resamples": n_resamples, "level": float(level), "seed": seed,
                      "resampling_unit": "sentence", "aggregate": "official-token-micro"},
        "item_ids": ids, "items": item_records, "metrics": metrics,
        "slices": slice_entries,
        "error_anatomy": _anatomy(item_records, gold, pred, items, manifest=manifest, run=run),
    }
    stamped = stamp_document(report, "report_sha256")
    verify_report(stamped, manifest)
    return stamped


def verify_report(report: Mapping[str, Any], manifest: Mapping[str, Any] | None = None) -> None:
    """Verify report schema, digest, and (when supplied) manifest binding."""
    if not isinstance(report, Mapping) or report.get("format") != REPORT_FORMAT:
        raise ReportError("unknown report format")
    _exact_fields(
        report,
        {
            "format",
            "manifest_format",
            "manifest_sha256",
            "claim_status",
            "run",
            "evaluator",
            "protocol",
            "item_ids",
            "items",
            "metrics",
            "slices",
            "error_anatomy",
            "report_sha256",
        },
        where="report",
    )
    _finite(report)
    verify_document(report, "report_sha256")
    if report.get("manifest_format") != MANIFEST_FORMAT:
        raise ReportError("report is bound to an unknown manifest format")
    manifest_sha = report.get("manifest_sha256")
    if not isinstance(manifest_sha, str) or not _SHA256.fullmatch(manifest_sha):
        raise ReportError("report manifest digest is malformed")
    if report.get("claim_status") != "development-only-not-published":
        raise ReportError("report claim status is not development-only-not-published")
    run = report.get("run")
    if not isinstance(run, Mapping):
        raise ReportError("report run receipt must be an object")
    _validate_run(run)
    evaluator = report.get("evaluator")
    if not isinstance(evaluator, Mapping):
        raise ReportError("report evaluator receipt must be an object")
    _exact_fields(evaluator, {"identity", "sha256", "source"}, where="report.evaluator")
    if (
        not isinstance(evaluator.get("identity"), str)
        or not evaluator["identity"]
        or not isinstance(evaluator.get("source"), str)
        or not evaluator["source"]
        or not isinstance(evaluator.get("sha256"), str)
        or not _SHA256.fullmatch(evaluator["sha256"])
    ):
        raise ReportError("report evaluator receipt is malformed")
    protocol = report.get("protocol")
    if not isinstance(protocol, Mapping):
        raise ReportError("report protocol must be an object")
    _exact_fields(
        protocol,
        {"n_resamples", "level", "seed", "resampling_unit", "aggregate"},
        where="report.protocol",
    )
    if protocol.get("resampling_unit") != "sentence" or protocol.get("aggregate") != "official-token-micro":
        raise ReportError("report protocol uses an unknown estimand")
    n_resamples = protocol.get("n_resamples")
    level = protocol.get("level")
    seed = protocol.get("seed")
    if isinstance(n_resamples, bool) or not isinstance(n_resamples, int) or n_resamples < 1:
        raise ReportError("report.protocol.n_resamples must be a positive integer")
    if (
        isinstance(level, bool)
        or not isinstance(level, (int, float))
        or not math.isfinite(float(level))
        or not 0 < float(level) < 1
    ):
        raise ReportError("report.protocol.level must be finite and in (0, 1)")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ReportError("report.protocol.seed must be an integer")
    ids = report.get("item_ids")
    if (not isinstance(ids, list) or any(not isinstance(item_id, str) for item_id in ids)
            or ids != sorted(ids) or len(ids) != len(set(ids))):
        raise ReportError("report item IDs must be sorted and unique")
    items = report.get("items")
    if (not isinstance(items, list) or any(not isinstance(item, Mapping) for item in items)
            or [item.get("item_id") for item in items] != ids):
        raise ReportError("report item records do not match item_ids")
    item_fields = {
        "item_id",
        "source",
        "asset_sha256",
        "document_id",
        "work_id",
        "sentence_id",
        "profile_ids",
        "tasks",
        "slice_ids",
        "token_count",
        "scored_token_count",
        "metrics",
    }
    item_totals: dict[str, list[int]] = {metric: [0, 0] for metric in _METRICS}
    for index, item in enumerate(items):
        _exact_fields(item, item_fields, where=f"report.items[{index}]")
        for field in (
            "item_id",
            "source",
            "asset_sha256",
            "document_id",
            "work_id",
            "sentence_id",
        ):
            if not isinstance(item.get(field), str) or not item[field]:
                raise ReportError(f"report.items[{index}].{field} must be a non-empty string")
        if not _SHA256.fullmatch(str(item["asset_sha256"])):
            raise ReportError(f"report.items[{index}].asset_sha256 is malformed")
        for field, allow_empty in (("profile_ids", False), ("tasks", False), ("slice_ids", True)):
            values = item.get(field)
            if (
                not isinstance(values, list)
                or (not allow_empty and not values)
                or any(not isinstance(value, str) or not value for value in values)
                or values != sorted(set(values))
            ):
                raise ReportError(f"report.items[{index}].{field} is malformed")
        if not set(item["tasks"]) <= {"parse", "tagging"}:
            raise ReportError(f"report.items[{index}].tasks contains an unknown task")
        token_count = _metric_integer(
            item.get("token_count"), where=f"report.items[{index}].token_count"
        )
        scored = _metric_integer(
            item.get("scored_token_count"),
            where=f"report.items[{index}].scored_token_count",
        )
        if token_count < 1 or scored != token_count:
            raise ReportError(f"report.items[{index}] token accounting is malformed")
        item_metrics = item.get("metrics")
        if not isinstance(item_metrics, Mapping) or set(item_metrics) != set(_METRICS):
            raise ReportError(f"report.items[{index}] metrics are malformed")
        for metric_index, metric in enumerate(_METRICS):
            numerator, denominator = _verify_metric_entry(
                item_metrics[metric],
                metric=metric,
                where=f"report.items[{index}].metrics.{metric}",
                aggregate=False,
                protocol=protocol,
                expected_seed=seed + metric_index,
            )
            maximum_denominator = scored * (2 if metric == "clas" else 1)
            if denominator > maximum_denominator:
                raise ReportError(
                    f"report.items[{index}].metrics.{metric} exceeds the item token count"
                )
            item_totals[metric][0] += numerator
            item_totals[metric][1] += denominator
    metrics = report.get("metrics")
    if not isinstance(metrics, Mapping) or set(metrics) != set(_METRICS):
        raise ReportError("report metrics must be an object")
    for metric_index, metric in enumerate(_METRICS):
        numerator, denominator = _verify_metric_entry(
            metrics[metric],
            metric=metric,
            where=f"report.metrics.{metric}",
            aggregate=True,
            protocol=protocol,
            expected_seed=seed + metric_index,
        )
        if [numerator, denominator] != item_totals[metric]:
            raise ReportError(f"report.metrics.{metric} differs from its item counts")
    if not isinstance(report.get("slices"), Mapping) or not isinstance(report.get("error_anatomy"), Mapping):
        raise ReportError("report slice or error-anatomy section is malformed")
    if manifest is not None:
        manifest = _json_copy(manifest)
        manifest_items, manifest_ids = _item_map(manifest)
        del manifest_items
        if manifest_ids != ids:
            raise ReportError("report item IDs do not match manifest")
        digest = manifest.get("manifest_sha256", document_sha256(manifest, "manifest_sha256"))
        if report.get("manifest_sha256") != digest:
            raise ReportError("report is bound to a different manifest")


def compare_reports(
    candidate: Mapping[str, Any], baseline: Mapping[str, Any], *, n_resamples: int = 999,
    level: float = 0.95, seed: int = 0,
) -> dict[str, Any]:
    """Compare two reports on exactly the same sorted items and manifest."""
    if n_resamples < 1:
        raise ReportError("n_resamples must be at least 1")
    if not 0 < level < 1:
        raise ReportError("level must be in (0, 1)")
    verify_report(candidate)
    verify_report(baseline)
    if candidate.get("manifest_sha256") != baseline.get("manifest_sha256"):
        raise ReportError("reports use different manifests")
    ids = candidate["item_ids"]
    if ids != baseline["item_ids"]:
        raise ReportError("reports use different item IDs or order")
    if len(ids) < 2:
        raise ReportError("paired comparison needs at least two items")
    cand_items = {item["item_id"]: item for item in candidate["items"]}
    base_items = {item["item_id"]: item for item in baseline["items"]}
    for item_id in ids:
        for field in ("source", "profile_ids", "slice_ids"):
            if cand_items[item_id].get(field) != base_items[item_id].get(field):
                raise ReportError(f"reports use different {field} for item {item_id}")
    c_metrics = candidate.get("metrics", {})
    b_metrics = baseline.get("metrics", {})
    metric_out: dict[str, Any] = {}
    for metric_index, metric in enumerate(_METRICS):
        candidate_counts: list[tuple[int, int]] = []
        baseline_counts: list[tuple[int, int]] = []
        candidate_correct: list[bool] = []
        baseline_correct: list[bool] = []
        for item_id in ids:
            candidate_entry = cand_items[item_id]["metrics"][metric]
            baseline_entry = base_items[item_id]["metrics"][metric]
            candidate_available = candidate_entry.get("value") is not None
            baseline_available = baseline_entry.get("value") is not None
            if candidate_available != baseline_available:
                raise ReportError(
                    f"reports disagree on {metric} applicability for item {item_id}"
                )
            if not candidate_available:
                continue
            candidate_counts.append(
                (int(candidate_entry["numerator"]), int(candidate_entry["denominator"]))
            )
            baseline_counts.append(
                (int(baseline_entry["numerator"]), int(baseline_entry["denominator"]))
            )
            candidate_correct.append(
                candidate_entry["numerator"] == candidate_entry["denominator"]
            )
            baseline_correct.append(
                baseline_entry["numerator"] == baseline_entry["denominator"]
            )
        if len(candidate_counts) < 2:
            metric_out[metric] = {"candidate": c_metrics.get(metric, {}).get("value"),
                                  "baseline": b_metrics.get(metric, {}).get("value"),
                                  "difference": None, "reason": "fewer-than-two-paired-items",
                                  "paired_bootstrap": None, "mcnemar": None}
            continue
        paired = _paired_ci(
            candidate_counts,
            baseline_counts,
            n_resamples=n_resamples,
            level=float(level),
            seed=seed + metric_index,
        )
        mc = mcnemar(candidate_correct, baseline_correct)
        metric_out[metric] = {
            "candidate": c_metrics.get(metric, {}).get("value"),
            "baseline": b_metrics.get(metric, {}).get("value"),
            "difference": float(c_metrics.get(metric, {}).get("value", 0.0) or 0.0) - float(b_metrics.get(metric, {}).get("value", 0.0) or 0.0),
            "paired_bootstrap": paired,
            "mcnemar": {"b": mc.b, "c": mc.c, "statistic": mc.statistic,
                        "p_value": mc.p_value, "method": mc.method},
        }
    result = {"format": COMPARISON_FORMAT, "claim_status": "development-only-not-published",
              "manifest_sha256": candidate["manifest_sha256"], "item_ids": ids,
              "protocol": {"n_resamples": n_resamples, "level": float(level), "seed": seed},
              "metrics": metric_out}
    return stamp_document(result, "comparison_sha256")


__all__ = [
    "COMPARISON_FORMAT", "MANIFEST_FORMAT", "REPORT_FORMAT", "ReportError",
    "build_report", "compare_reports", "verify_report", "canonical_json", "document_sha256",
    "load_document", "write_document", "stamp_document", "verify_document",
]
