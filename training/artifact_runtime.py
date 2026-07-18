"""Run artifact evaluation, operational measurement, and qualification.

The command evaluates one already-created schema-1 model bundle in an isolated
process.  It measures the complete development manifest on CPU, probes the
declared provider matrix, then asks :mod:`artifact_qualification` to rebuild and
judge every bound evidence record.  Conversion commands invoke this module before
promoting a staged artifact to a final directory or archive.
"""

from __future__ import annotations

import argparse
import contextlib
import ctypes
import hashlib
import importlib
import json
import os
import platform
import sys
import threading
import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any

try:  # The training directory is also used directly as a script directory.
    from . import artifact_qualification as qualification
    from . import development_manifest as manifest_mod
    from . import model_selection as selection_mod
    from . import run_development_evaluation as development_runner
except ImportError:  # pragma: no cover - exercised by ``python training/foo.py``
    import artifact_qualification as qualification  # type: ignore[no-redef]
    import development_manifest as manifest_mod  # type: ignore[no-redef]
    import model_selection as selection_mod  # type: ignore[no-redef]
    import run_development_evaluation as development_runner  # type: ignore[no-redef]

__all__ = [
    "ArtifactRuntimeError",
    "artifact_record",
    "evaluate_artifact",
    "main",
    "qualify_artifact",
]

_MAX_FILES = 64
_MAX_FILE_BYTES = 2_000_000_000
_MAX_JSON_BYTES = 512 * 1024 * 1024
_OUTPUT_FIELDS = ("upos", "xpos", "ufeats", "lemma", "head", "deprel")
_ENV_PROVIDER = "PYAEGEAN_ORT_PROVIDERS"


class ArtifactRuntimeError(RuntimeError):
    """Raised when runtime measurement or artifact evaluation fails."""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
    except OSError as exc:
        raise ArtifactRuntimeError(f"cannot hash artifact file {path}: {exc}") from exc
    return digest.hexdigest()


def artifact_record(artifact_dir: str | Path) -> dict[str, Any]:
    """Validate a flat artifact directory and return exact file/size/hash evidence."""

    root = Path(artifact_dir)
    if not root.is_dir():
        raise ArtifactRuntimeError(f"artifact directory does not exist: {root}")
    try:
        entries = sorted(root.iterdir(), key=lambda path: path.name)
    except OSError as exc:
        raise ArtifactRuntimeError(f"cannot list artifact directory {root}: {exc}") from exc
    if not entries or len(entries) > _MAX_FILES:
        raise ArtifactRuntimeError(f"artifact directory must contain 1..{_MAX_FILES} flat files")
    files: list[dict[str, Any]] = []
    for path in entries:
        if path.is_symlink() or not path.is_file():
            raise ArtifactRuntimeError(f"artifact entry must be a regular non-symlink file: {path.name}")
        try:
            size = path.stat().st_size
        except OSError as exc:
            raise ArtifactRuntimeError(f"cannot stat artifact file {path}: {exc}") from exc
        if size < 1 or size > _MAX_FILE_BYTES:
            raise ArtifactRuntimeError(
                f"artifact file {path.name!r} has invalid size {size}; limit is {_MAX_FILE_BYTES}"
            )
        files.append({"path": path.name, "bytes": size, "sha256": _sha256_file(path)})
    by_name = {entry["path"]: entry for entry in files}
    if "model.onnx" not in by_name or "manifest.json" not in by_name:
        raise ArtifactRuntimeError("artifact must contain model.onnx and manifest.json")
    directory_sha = hashlib.sha256(manifest_mod.canonical_json(files).encode("utf-8")).hexdigest()
    try:
        from aegean.greek.neural_contract import ModelBundleManifest

        bundle = ModelBundleManifest.load(root)
    except Exception as exc:
        raise ArtifactRuntimeError(f"invalid model bundle: {type(exc).__name__}: {exc}") from exc
    return {
        "identity": bundle.model_id,
        "directory_sha256": directory_sha,
        "model_sha256": by_name["model.onnx"]["sha256"],
        "artifact_size_bytes": sum(int(entry["bytes"]) for entry in files),
        "model_size_bytes": int(by_name["model.onnx"]["bytes"]),
        "files": files,
    }


def _resident_bytes() -> tuple[int, str]:
    if os.name == "nt":
        class ProcessMemoryCounters(ctypes.Structure):
            _fields_ = [
                ("cb", ctypes.c_ulong),
                ("PageFaultCount", ctypes.c_ulong),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        counters = ProcessMemoryCounters()
        counters.cb = ctypes.sizeof(counters)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        kernel32.GetCurrentProcess.restype = ctypes.c_void_p
        psapi.GetProcessMemoryInfo.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ProcessMemoryCounters),
            ctypes.c_ulong,
        ]
        psapi.GetProcessMemoryInfo.restype = ctypes.c_int
        handle = kernel32.GetCurrentProcess()
        if not psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
            raise ArtifactRuntimeError(f"GetProcessMemoryInfo failed: {ctypes.get_last_error()}")
        return int(counters.WorkingSetSize), "windows-working-set-sampler"
    proc_statm = Path("/proc/self/statm")
    if proc_statm.is_file():
        try:
            resident_pages = int(proc_statm.read_text(encoding="ascii").split()[1])
            return resident_pages * int(os.sysconf("SC_PAGE_SIZE")), "proc-statm-rss-sampler"
        except (OSError, ValueError, IndexError) as exc:
            raise ArtifactRuntimeError(f"cannot sample /proc/self/statm: {exc}") from exc
    try:
        import resource

        peak = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    except (ImportError, OSError, ValueError) as exc:  # pragma: no cover - uncommon platform
        raise ArtifactRuntimeError(f"resident-memory measurement is unsupported: {exc}") from exc
    multiplier = 1 if sys.platform == "darwin" else 1024
    return peak * multiplier, "resource-peak-rss"


class _MemorySampler:
    def __init__(self, interval_ms: int) -> None:
        self.interval_ms = interval_ms
        self.baseline, self.method = _resident_bytes()
        self.peak = self.baseline
        self._stop = threading.Event()
        self._error: BaseException | None = None
        self._thread = threading.Thread(target=self._run, name="artifact-rss-sampler", daemon=True)

    def _sample(self) -> None:
        value, method = _resident_bytes()
        if method != self.method:
            raise ArtifactRuntimeError("resident-memory sampling method changed during evaluation")
        self.peak = max(self.peak, value)

    def _run(self) -> None:
        try:
            while not self._stop.wait(self.interval_ms / 1000):
                self._sample()
        except BaseException as exc:  # pragma: no cover - surfaced synchronously by stop()
            self._error = exc

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> dict[str, Any]:
        self._stop.set()
        self._thread.join(timeout=max(1.0, self.interval_ms / 1000 * 4))
        if self._thread.is_alive():
            raise ArtifactRuntimeError("resident-memory sampler did not stop")
        if self._error is not None:
            raise ArtifactRuntimeError(f"resident-memory sampler failed: {self._error}") from self._error
        self._sample()
        return {
            "method": self.method,
            "sample_interval_ms": self.interval_ms,
            "baseline_resident_bytes": self.baseline,
            "peak_resident_bytes": self.peak,
            "incremental_peak_bytes": self.peak - self.baseline,
        }


@contextlib.contextmanager
def _provider_environment(provider: str) -> Iterator[None]:
    previous = os.environ.get(_ENV_PROVIDER)
    os.environ[_ENV_PROVIDER] = provider
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop(_ENV_PROVIDER, None)
        else:
            os.environ[_ENV_PROVIDER] = previous


def _backend_factory(
    artifact_dir: Path, *, asset_sha256: str, asset_sha256_enforced: bool
) -> Any:
    from aegean.greek.joint import _JointModel

    return _JointModel(
        artifact_dir,
        asset_sha256=asset_sha256,
        asset_sha256_enforced=asset_sha256_enforced,
    )


def _analysis_tokens(analysis: Any, forms: Sequence[str]) -> list[dict[str, Any]]:
    fields = ("lemma", "upos", "xpos", "feats", "head", "deprel")
    for field in fields:
        values = getattr(analysis, field, None)
        if not isinstance(values, (list, tuple)) or len(values) != len(forms):
            raise ArtifactRuntimeError(
                f"artifact analysis field {field!r} has invalid cardinality"
            )
    return [
        {
            "id": index + 1,
            "form": form,
            "lemma": analysis.lemma[index],
            "upos": analysis.upos[index],
            "xpos": analysis.xpos[index],
            "feats": analysis.feats[index],
            "head": analysis.head[index],
            "deprel": analysis.deprel[index],
        }
        for index, form in enumerate(forms)
    ]


def _analyze(backend: Any, sentences: Sequence[Any]) -> list[list[dict[str, Any]]]:
    output: list[list[dict[str, Any]]] = []
    for sentence in sentences:
        forms = [token.form for token in sentence.tokens]
        analysis = backend.analyze(forms, long_input="windowed")
        output.append(_analysis_tokens(analysis, forms))
    return output


def _probe_indices(sentences: Sequence[Any]) -> list[int]:
    if not sentences:
        raise ArtifactRuntimeError("development runner supplied no sentences")
    ordered = sorted(
        range(len(sentences)),
        key=lambda index: (len(sentences[index].tokens), index),
    )
    return sorted(set((ordered[0], ordered[len(ordered) // 2], ordered[-1])))


def _prediction_digest(predictions: Any) -> str:
    return hashlib.sha256(manifest_mod.canonical_json(predictions).encode("utf-8")).hexdigest()


def _probe_disagreement(reference: Any, candidate: Any) -> dict[str, float]:
    if len(reference) != len(candidate):
        raise ArtifactRuntimeError("provider probe sentence cardinality differs from CPU")
    counts = {field: [0, 0] for field in _OUTPUT_FIELDS}
    token_field = {
        "upos": "upos",
        "xpos": "xpos",
        "ufeats": "feats",
        "lemma": "lemma",
        "head": "head",
        "deprel": "deprel",
    }
    for left_sentence, right_sentence in zip(reference, candidate, strict=True):
        if len(left_sentence) != len(right_sentence):
            raise ArtifactRuntimeError("provider probe token cardinality differs from CPU")
        for left, right in zip(left_sentence, right_sentence, strict=True):
            if left["id"] != right["id"] or left["form"] != right["form"]:
                raise ArtifactRuntimeError("provider probe alignment differs from CPU")
            for field, key in token_field.items():
                counts[field][1] += 1
                counts[field][0] += int(left[key] != right[key])
    return {
        field: (different / compared if compared else 0.0)
        for field, (different, compared) in counts.items()
    }


def _runtime_environment() -> dict[str, str]:
    def version(module_name: str) -> str:
        try:
            module = importlib.import_module(module_name)
        except ImportError as exc:
            raise ArtifactRuntimeError(
                f"runtime dependency {module_name!r} is not installed"
            ) from exc
        found = getattr(module, "__version__", None)
        if not isinstance(found, str) or not found:
            raise ArtifactRuntimeError(
                f"runtime dependency {module_name!r} does not expose a version"
            )
        return found

    return {
        "python": platform.python_version(),
        "platform": platform.platform() or "unknown",
        "machine": platform.machine() or "unknown",
        "processor": platform.processor() or "unknown",
        "onnxruntime": version("onnxruntime"),
        "numpy": version("numpy"),
        "tokenizers": version("tokenizers"),
    }


def _run_identity(artifact_dir: Path, record: Mapping[str, Any]) -> dict[str, Any]:
    from aegean.greek.neural_contract import ModelBundleManifest

    bundle = ModelBundleManifest.load(artifact_dir)
    preprocessing_config = {
        "annotation_profile": bundle.annotation_profile,
        "normalization": bundle.normalization,
        "segmentation": bundle.segmentation,
        "special_token_policy": bundle.special_token_policy,
        "preprocessing_version": bundle.preprocessing_version,
        "max_subwords": bundle.max_subwords,
        "tokenizer_revision": bundle.tokenizer_revision,
    }
    return {
        "model": {
            "identity": bundle.model_id,
            "asset_sha256": record["directory_sha256"],
        },
        "preprocessing": {
            "identity": bundle.preprocessing_version,
            "config_sha256": hashlib.sha256(
                manifest_mod.canonical_json(preprocessing_config).encode("utf-8")
            ).hexdigest(),
        },
        "output_profile": {
            "identity": bundle.annotation_profile,
            "tasks": ["parsing", "tagging"],
        },
        "decoder": {
            "identity": "pyaegean-release-single-root-mst-v2",
            "mode": "sequential",
            "long_input": "windowed",
        },
    }


def _provider_matrix(
    *,
    gate: Mapping[str, Any],
    profile_id: str,
    artifact_dir: Path,
    record: Mapping[str, Any],
    sentences: Sequence[Any],
    cpu_predictions: Any,
    backend_factory: Callable[..., Any],
    available_providers: Sequence[str],
    cpu_session_providers: Sequence[str],
) -> list[dict[str, Any]]:
    profile = gate["profiles"][profile_id]
    required = set(profile["required_providers"])
    configured = sorted(required | set(profile["optional_providers"]))
    matrix: list[dict[str, Any]] = []
    cpu_digest = _prediction_digest(cpu_predictions)
    for provider in configured:
        is_required = provider in required
        available = provider in available_providers
        if provider == "CPUExecutionProvider":
            if not available or provider not in cpu_session_providers:
                matrix.append(
                    {
                        "provider": provider,
                        "required": True,
                        "available": available,
                        "status": "fail",
                        "session_providers": list(cpu_session_providers),
                        "prediction_sha256": None,
                        "cpu_disagreement_fraction": None,
                        "error": "canonical CPU session did not activate CPUExecutionProvider",
                    }
                )
            else:
                matrix.append(
                    {
                        "provider": provider,
                        "required": True,
                        "available": True,
                        "status": "pass",
                        "session_providers": list(cpu_session_providers),
                        "prediction_sha256": cpu_digest,
                        "cpu_disagreement_fraction": {field: 0.0 for field in _OUTPUT_FIELDS},
                        "error": None,
                    }
                )
            continue
        if not available:
            if is_required:
                matrix.append(
                    {
                        "provider": provider,
                        "required": True,
                        "available": False,
                        "status": "fail",
                        "session_providers": [],
                        "prediction_sha256": None,
                        "cpu_disagreement_fraction": None,
                        "error": "required provider is not available",
                    }
                )
            else:
                matrix.append(
                    {
                        "provider": provider,
                        "required": False,
                        "available": False,
                        "status": "unavailable",
                        "session_providers": [],
                        "prediction_sha256": None,
                        "cpu_disagreement_fraction": None,
                        "error": None,
                    }
                )
            continue
        try:
            with _provider_environment(provider):
                backend = backend_factory(
                    artifact_dir,
                    asset_sha256=str(record["directory_sha256"]),
                    asset_sha256_enforced=False,
                )
                session_providers = list(backend._sess.get_providers())
                predictions = _analyze(backend, sentences)
            if provider not in session_providers:
                raise ArtifactRuntimeError("session did not activate the requested provider")
            matrix.append(
                {
                    "provider": provider,
                    "required": is_required,
                    "available": True,
                    "status": "pass",
                    "session_providers": session_providers,
                    "prediction_sha256": _prediction_digest(predictions),
                    "cpu_disagreement_fraction": _probe_disagreement(
                        cpu_predictions, predictions
                    ),
                    "error": None,
                }
            )
        except Exception as exc:
            message = f"{type(exc).__name__}: {exc}"[:1000]
            matrix.append(
                {
                    "provider": provider,
                    "required": is_required,
                    "available": True,
                    "status": "fail",
                    "session_providers": [],
                    "prediction_sha256": None,
                    "cpu_disagreement_fraction": None,
                    "error": message,
                }
            )
    return matrix


def evaluate_artifact(
    *,
    gate: Mapping[str, Any],
    profile_id: str,
    manifest: Mapping[str, Any] | str | Path,
    perseus_dev: str | Path,
    papygreek_tagging: str | Path,
    papygreek_parse: str | Path,
    artifact_dir: str | Path,
    output_dir: str | Path,
    git_revision: str | None = None,
    backend_factory: Callable[..., Any] | None = None,
    available_providers: Sequence[str] | None = None,
    runtime_environment: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Evaluate one artifact and persist candidate report plus operational evidence."""

    qualification.validate_gate(gate)
    if profile_id not in gate["profiles"]:
        raise ArtifactRuntimeError(f"unknown qualification profile {profile_id!r}")
    checked_manifest = development_runner._read_manifest(manifest)
    if checked_manifest["manifest_sha256"] != gate["development_manifest_sha256"]:
        raise ArtifactRuntimeError("artifact gate and development manifest digests differ")
    artifact_path = Path(artifact_dir)
    output_path = Path(output_dir)
    record = artifact_record(artifact_path)
    factory = backend_factory or _backend_factory
    measurement = gate["measurement"]
    sampler = _MemorySampler(int(measurement["memory_sample_interval_ms"]))
    captured: dict[str, Any] = {}
    sampler.start()
    try:
        with _provider_environment("CPUExecutionProvider"):
            backend = factory(
                artifact_path,
                asset_sha256=str(record["directory_sha256"]),
                asset_sha256_enforced=False,
            )
            session_providers = list(backend._sess.get_providers())

            def pipeline(
                sentences: list[Any],
                *,
                parse: bool,
                batch_size: object,
                long_input: str,
            ) -> list[list[dict[str, Any]]]:
                if not parse or batch_size is not None or long_input != "windowed":
                    raise ArtifactRuntimeError("qualification runner changed its canonical call")
                warmups = min(int(measurement["warmup_items"]), len(sentences))
                _analyze(backend, sentences[:warmups])
                started = time.perf_counter_ns()
                predictions = _analyze(backend, sentences)
                elapsed = max(1, time.perf_counter_ns() - started)
                indices = _probe_indices(sentences)
                captured.update(
                    {
                        "sentences": list(sentences),
                        "probe_sentences": [sentences[index] for index in indices],
                        "probe_predictions": [predictions[index] for index in indices],
                        "warmup_items": warmups,
                        "timed_items": len(sentences),
                        "timed_tokens": sum(len(sentence.tokens) for sentence in sentences),
                        "elapsed_ns": elapsed,
                    }
                )
                return predictions

            environment = (
                dict(runtime_environment)
                if runtime_environment is not None
                else _runtime_environment()
            )
            result = development_runner.run_development_evaluation(
                manifest=checked_manifest,
                perseus_dev=perseus_dev,
                papygreek_tagging=papygreek_tagging,
                papygreek_parse=papygreek_parse,
                environment_receipt=environment,
                output_dir=output_path,
                git_revision=git_revision,
                pipeline=pipeline,
                run_identity=_run_identity(artifact_path, record),
            )
    except Exception as exc:
        sampler.stop()
        if isinstance(exc, ArtifactRuntimeError):
            raise
        raise ArtifactRuntimeError(
            f"artifact development evaluation failed: {type(exc).__name__}: {exc}"
        ) from exc
    memory = sampler.stop()
    if not captured:
        raise ArtifactRuntimeError("artifact pipeline did not produce timing/probe evidence")
    providers = list(available_providers) if available_providers is not None else None
    if providers is None:
        try:
            import onnxruntime

            providers = list(onnxruntime.get_available_providers())
        except Exception as exc:
            raise ArtifactRuntimeError(f"cannot enumerate ONNX Runtime providers: {exc}") from exc
    provider_matrix = _provider_matrix(
        gate=gate,
        profile_id=profile_id,
        artifact_dir=artifact_path,
        record=record,
        sentences=captured["probe_sentences"],
        cpu_predictions=captured["probe_predictions"],
        backend_factory=factory,
        available_providers=providers,
        cpu_session_providers=session_providers,
    )
    timed_tokens = int(captured["timed_tokens"])
    elapsed_ns = int(captured["elapsed_ns"])
    operational = qualification.stamp_operational_evidence(
        {
            "format": qualification.EVIDENCE_FORMAT,
            "claim_status": qualification.CLAIM_STATUS,
            "profile_id": measurement["profile_id"],
            "development_manifest_sha256": checked_manifest["manifest_sha256"],
            "artifact": record,
            "timing": {
                "mode": "sequential",
                "long_input": "windowed",
                "warmup_items": int(captured["warmup_items"]),
                "timed_items": int(captured["timed_items"]),
                "timed_tokens": timed_tokens,
                "elapsed_ns": elapsed_ns,
                "latency_ms_per_100_tokens": elapsed_ns / 1_000_000 * 100 / timed_tokens,
            },
            "memory": memory,
            "provider_matrix": provider_matrix,
            "environment": environment,
        }
    )
    operational_path = output_path / "operational-evidence.json"
    manifest_mod.write_document(operational, operational_path, digest_field="evidence_sha256")
    return {
        **result,
        "operational": operational,
        "paths": {**result["paths"], "operational": str(operational_path)},
    }


def qualify_artifact(
    *,
    gate: Mapping[str, Any],
    selection_gate: Mapping[str, Any],
    manifest: Mapping[str, Any] | str | Path,
    profile_id: str,
    perseus_dev: str | Path,
    papygreek_tagging: str | Path,
    papygreek_parse: str | Path,
    artifact_dir: str | Path,
    output_dir: str | Path,
    reference_report: Mapping[str, Any],
    reference_predictions: Mapping[str, Any],
    reference_operational: Mapping[str, Any] | None = None,
    git_revision: str | None = None,
    backend_factory: Callable[..., Any] | None = None,
    available_providers: Sequence[str] | None = None,
    runtime_environment: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Run the artifact and persist an independently reproduced gate decision."""

    checked_manifest = development_runner._read_manifest(manifest)
    evaluated = evaluate_artifact(
        gate=gate,
        profile_id=profile_id,
        manifest=checked_manifest,
        perseus_dev=perseus_dev,
        papygreek_tagging=papygreek_tagging,
        papygreek_parse=papygreek_parse,
        artifact_dir=artifact_dir,
        output_dir=output_dir,
        git_revision=git_revision,
        backend_factory=backend_factory,
        available_providers=available_providers,
        runtime_environment=runtime_environment,
    )
    inputs = {
        "gate": gate,
        "selection_gate": selection_gate,
        "manifest": checked_manifest,
        "profile_id": profile_id,
        "gold": evaluated["gold"],
        "reference_report": reference_report,
        "reference_predictions": reference_predictions,
        "candidate_report": evaluated["report"],
        "candidate_predictions": evaluated["predictions"],
        "candidate_operational": evaluated["operational"],
        "reference_operational": reference_operational,
    }
    decision = qualification.build_qualification_report(**inputs)
    qualification.verify_qualification_report(decision, **inputs)
    decision_path = Path(output_dir) / "qualification-report.json"
    manifest_mod.write_document(decision, decision_path, digest_field="qualification_sha256")
    return {
        **evaluated,
        "qualification": decision,
        "paths": {**evaluated["paths"], "qualification": str(decision_path)},
    }


def _load_json(path: Path, *, where: str) -> dict[str, Any]:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ArtifactRuntimeError(f"duplicate JSON key in {where}: {key!r}")
            result[key] = value
        return result

    try:
        size = path.stat().st_size
        if size < 2 or size > _MAX_JSON_BYTES:
            raise ArtifactRuntimeError(
                f"{where} size {size} is outside the allowed range 2..{_MAX_JSON_BYTES} bytes"
            )
        raw = path.read_bytes()
        if len(raw) != size:
            raise ArtifactRuntimeError(f"{where} changed while it was being read")
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=reject_duplicates)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ArtifactRuntimeError(f"invalid {where} {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ArtifactRuntimeError(f"{where} must be a JSON object")
    return value


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-dir", required=True, type=Path)
    parser.add_argument("--profile", required=True, choices=("export", "optimization"))
    parser.add_argument(
        "--gate",
        type=Path,
        default=Path(__file__).with_name("artifact-qualification-gate-v2.json"),
    )
    parser.add_argument(
        "--selection-gate",
        type=Path,
        default=Path(__file__).with_name("model-selection-gate-v2.json"),
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path(__file__).parent / "results" / "development-source-manifest.json",
    )
    parser.add_argument("--perseus-dev-source", required=True, type=Path)
    parser.add_argument("--papygreek-tagging-source", required=True, type=Path)
    parser.add_argument("--papygreek-parse-source", required=True, type=Path)
    parser.add_argument("--reference-report", required=True, type=Path)
    parser.add_argument("--reference-predictions", required=True, type=Path)
    parser.add_argument("--reference-operational", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--git-revision")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        gate = qualification.load_gate(args.gate)
        selection_gate = selection_mod.load_gate(args.selection_gate)
        manifest = manifest_mod.load_document(
            args.manifest, verify=True, digest_field="manifest_sha256"
        )
        reference_report = manifest_mod.load_document(
            args.reference_report, verify=True, digest_field="report_sha256"
        )
        reference_predictions = _load_json(
            args.reference_predictions, where="reference predictions"
        )
        reference_operational = (
            None
            if args.reference_operational is None
            else _load_json(args.reference_operational, where="reference operational evidence")
        )
        result = qualify_artifact(
            gate=gate,
            selection_gate=selection_gate,
            manifest=manifest,
            profile_id=args.profile,
            perseus_dev=args.perseus_dev_source,
            papygreek_tagging=args.papygreek_tagging_source,
            papygreek_parse=args.papygreek_parse_source,
            artifact_dir=args.artifact_dir,
            output_dir=args.output_dir,
            reference_report=reference_report,
            reference_predictions=reference_predictions,
            reference_operational=reference_operational,
            git_revision=args.git_revision,
        )
    except (ArtifactRuntimeError, qualification.QualificationError, ValueError) as exc:
        parser.error(str(exc))
    decision = result["qualification"]
    print(
        manifest_mod.canonical_json(
            {
                "qualified": decision["qualified"],
                "qualification_sha256": decision["qualification_sha256"],
                "report": result["paths"]["qualification"],
                "failures": decision["failures"],
            }
        )
    )
    return 0 if decision["qualified"] else 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
