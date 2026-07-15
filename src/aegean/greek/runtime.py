"""Instance-owned Greek NLP runtime configuration.

`GreekPipeline` is the explicit owner of a neural backend and its immutable,
serializable configuration. The historical module-level API is a facade over one
replaceable default instance. Instance calls bind through a `ContextVar`, so two
pipelines can analyze concurrently without observing or mutating one another.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from threading import RLock
from typing import TYPE_CHECKING, Any, Literal

from .model_variants import (
    NeuralVariantLabel,
    NeuralVariantUnavailableError,
    neural_variant,
    variant_registry_sha256,
)

if TYPE_CHECKING:
    from ..core.model import Token
    from .confidence import AbstentionPolicy
    from .joint import LongInputMode, SentenceAnalysis, _JointModel
    from .neural_contract import AnalysisReceipt
    from .pipeline import TokenRecord
    from .sentence_segmentation import SegmenterLike

__all__ = ["GreekPipeline", "GreekPipelineConfig", "default_pipeline"]

_CONFIG_SCHEMA = 2
_VARIANT_LABELS = {"default", "fast", "compact", "balanced"}
_V3_MODEL_ID = "grc-joint-v3"
_V3_DATASET = "grc-joint"


def _config_sha256(value: str | None, field: str) -> str | None:
    if value is None:
        return None
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise TypeError(f"{field} must be a lowercase SHA-256 string or null")
    return value


@dataclass(frozen=True, slots=True)
class GreekPipelineConfig:
    """Stable configuration identity for a `GreekPipeline` instance."""

    schema_version: int
    backend: Literal["baseline", "neural"]
    model_id: str | None
    dataset: str | None
    runtime_variant: NeuralVariantLabel | None
    variant_registry_sha256: str | None
    variant_award_sha256: str | None
    qualification_sha256: str | None
    bundle_manifest_sha256: str | None
    tokenizer_revision: str | None
    annotation_profile: str
    normalization: str
    segmentation: str
    preprocessing_version: str
    execution_providers: tuple[str, ...]

    def __post_init__(self) -> None:
        """Normalize and validate values so direct construction stays immutable and typed."""
        if not isinstance(self.schema_version, int) or isinstance(self.schema_version, bool):
            raise TypeError("schema_version must be an integer")
        if self.schema_version != _CONFIG_SCHEMA:
            raise ValueError(
                f"unsupported Greek pipeline configuration schema {self.schema_version!r}; "
                f"expected {_CONFIG_SCHEMA}"
            )
        if self.backend not in ("baseline", "neural"):
            raise ValueError(f"invalid Greek pipeline backend {self.backend!r}")
        providers = self.execution_providers
        if isinstance(providers, list):
            providers = tuple(providers)
            object.__setattr__(self, "execution_providers", providers)
        if not isinstance(providers, tuple) or not all(
            isinstance(provider, str) and provider for provider in providers
        ):
            raise TypeError("execution_providers must be a tuple of non-empty strings")
        optional = (
            "model_id",
            "dataset",
            "runtime_variant",
            "variant_registry_sha256",
            "variant_award_sha256",
            "qualification_sha256",
            "bundle_manifest_sha256",
            "tokenizer_revision",
        )
        for field in optional:
            value = getattr(self, field)
            if value is not None and (not isinstance(value, str) or not value):
                raise TypeError(f"{field} must be a non-empty string or null")
        for field in (
            "variant_registry_sha256",
            "variant_award_sha256",
            "qualification_sha256",
            "bundle_manifest_sha256",
        ):
            _config_sha256(getattr(self, field), field)
        required = (
            "annotation_profile",
            "normalization",
            "segmentation",
            "preprocessing_version",
        )
        for field in required:
            value = getattr(self, field)
            if not isinstance(value, str) or not value:
                raise TypeError(f"{field} must be a non-empty string")
        if self.backend == "baseline":
            if any(getattr(self, field) is not None for field in optional) or providers:
                raise ValueError("a baseline pipeline cannot declare a model or execution provider")
        else:
            if (
                self.model_id is None
                or self.dataset is None
                or self.runtime_variant is None
                or self.variant_registry_sha256 is None
            ):
                raise ValueError(
                    "a neural pipeline requires model_id, dataset, runtime_variant, "
                    "and variant_registry_sha256"
                )
            if self.runtime_variant not in _VARIANT_LABELS:
                raise ValueError(f"invalid neural runtime variant {self.runtime_variant!r}")
            evidence = (self.variant_award_sha256, self.qualification_sha256)
            if (evidence[0] is None) != (evidence[1] is None):
                raise ValueError("variant award and qualification hashes must appear together")
            if evidence[0] is None and (
                self.runtime_variant != "default"
                or self.model_id != _V3_MODEL_ID
                or self.dataset != _V3_DATASET
            ):
                raise ValueError(
                    "only the immutable grc-joint-v3 default may omit variant award evidence"
                )

    def to_dict(self) -> dict[str, Any]:
        """Return a stable JSON-compatible representation."""
        return {
            "schema_version": self.schema_version,
            "backend": self.backend,
            "model_id": self.model_id,
            "dataset": self.dataset,
            "runtime_variant": self.runtime_variant,
            "variant_registry_sha256": self.variant_registry_sha256,
            "variant_award_sha256": self.variant_award_sha256,
            "qualification_sha256": self.qualification_sha256,
            "bundle_manifest_sha256": self.bundle_manifest_sha256,
            "tokenizer_revision": self.tokenizer_revision,
            "annotation_profile": self.annotation_profile,
            "normalization": self.normalization,
            "segmentation": self.segmentation,
            "preprocessing_version": self.preprocessing_version,
            "execution_providers": list(self.execution_providers),
        }

    def to_json(self) -> str:
        """Serialize canonically for storage or comparison."""
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> GreekPipelineConfig:
        """Validate and deserialize configuration schema 1."""
        if not isinstance(value, Mapping):
            raise ValueError("invalid Greek pipeline configuration: expected an object")
        keys = set(value)
        if any(not isinstance(key, str) for key in keys):
            raise ValueError("invalid Greek pipeline configuration keys: keys must be strings")
        expected = {
            "schema_version",
            "backend",
            "model_id",
            "dataset",
            "runtime_variant",
            "variant_registry_sha256",
            "variant_award_sha256",
            "qualification_sha256",
            "bundle_manifest_sha256",
            "tokenizer_revision",
            "annotation_profile",
            "normalization",
            "segmentation",
            "preprocessing_version",
            "execution_providers",
        }
        missing = expected - keys
        extra = keys - expected
        if missing or extra:
            raise ValueError(
                f"invalid Greek pipeline configuration keys: missing={sorted(missing)}, "
                f"extra={sorted(extra)}"
            )
        schema_version = value["schema_version"]
        if not isinstance(schema_version, int) or isinstance(schema_version, bool):
            raise ValueError("schema_version must be an integer")
        if schema_version != _CONFIG_SCHEMA:
            raise ValueError(
                f"unsupported Greek pipeline configuration schema "
                f"{value['schema_version']!r}; expected {_CONFIG_SCHEMA}"
            )
        backend = value["backend"]
        if backend not in ("baseline", "neural"):
            raise ValueError(f"invalid Greek pipeline backend {backend!r}")
        providers = value["execution_providers"]
        if not isinstance(providers, list) or not all(
            isinstance(provider, str) and provider for provider in providers
        ):
            raise ValueError("execution_providers must be a list of non-empty strings")

        def optional_string(name: str) -> str | None:
            item = value[name]
            if item is None:
                return None
            if not isinstance(item, str) or not item:
                raise ValueError(f"{name} must be a non-empty string or null")
            return item

        def required_string(name: str) -> str:
            item = value[name]
            if not isinstance(item, str) or not item:
                raise ValueError(f"{name} must be a non-empty string")
            return item

        config = cls(
            schema_version=_CONFIG_SCHEMA,
            backend=backend,
            model_id=optional_string("model_id"),
            dataset=optional_string("dataset"),
            runtime_variant=optional_string("runtime_variant"),  # type: ignore[arg-type]
            variant_registry_sha256=optional_string("variant_registry_sha256"),
            variant_award_sha256=optional_string("variant_award_sha256"),
            qualification_sha256=optional_string("qualification_sha256"),
            bundle_manifest_sha256=optional_string("bundle_manifest_sha256"),
            tokenizer_revision=optional_string("tokenizer_revision"),
            annotation_profile=required_string("annotation_profile"),
            normalization=required_string("normalization"),
            segmentation=required_string("segmentation"),
            preprocessing_version=required_string("preprocessing_version"),
            execution_providers=tuple(providers),
        )
        if config.backend == "baseline":
            if any(
                item is not None
                for item in (
                    config.model_id,
                    config.dataset,
                    config.runtime_variant,
                    config.variant_registry_sha256,
                    config.variant_award_sha256,
                    config.qualification_sha256,
                    config.bundle_manifest_sha256,
                    config.tokenizer_revision,
                )
            ) or config.execution_providers:
                raise ValueError("a baseline pipeline cannot declare a model or execution provider")
        return config

    @classmethod
    def from_json(cls, value: str) -> GreekPipelineConfig:
        """Deserialize a configuration JSON object."""
        try:
            raw = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid Greek pipeline configuration JSON: {exc}") from exc
        if not isinstance(raw, dict):
            raise ValueError("invalid Greek pipeline configuration JSON: expected an object")
        return cls.from_dict(raw)


_BASELINE_CONFIG = GreekPipelineConfig(
    schema_version=_CONFIG_SCHEMA,
    backend="baseline",
    model_id=None,
    dataset=None,
    runtime_variant=None,
    variant_registry_sha256=None,
    variant_award_sha256=None,
    qualification_sha256=None,
    bundle_manifest_sha256=None,
    tokenizer_revision=None,
    annotation_profile="pyaegean-baseline-v1",
    normalization="NFC",
    segmentation="pyaegean-punctuation-v1",
    preprocessing_version="pyaegean-baseline-v1",
    execution_providers=(),
)


def _config_for_backend(backend: Any) -> GreekPipelineConfig:
    manifest = backend.manifest
    variant = getattr(backend, "runtime_variant", None)
    if variant is None:
        raise ValueError("a neural backend must carry a registered runtime variant")
    return GreekPipelineConfig(
        schema_version=_CONFIG_SCHEMA,
        backend="neural",
        model_id=manifest.model_id,
        dataset=manifest.dataset,
        runtime_variant=variant.label,
        variant_registry_sha256=variant_registry_sha256(),
        variant_award_sha256=variant.award_sha256,
        qualification_sha256=variant.qualification_sha256,
        bundle_manifest_sha256=manifest.manifest_sha256,
        tokenizer_revision=manifest.tokenizer_revision,
        annotation_profile=manifest.annotation_profile,
        normalization=manifest.normalization,
        segmentation=manifest.segmentation,
        preprocessing_version=manifest.preprocessing_version,
        execution_providers=tuple(backend._sess.get_providers()),
    )


class GreekPipeline:
    """An isolated Greek analysis pipeline with explicit backend ownership.

    Constructing without arguments creates the zero-dependency baseline. Use
    `GreekPipeline.neural()` to load an isolated neural instance without changing
    the module-level default selected by `use_neural_pipeline()`.
    """

    __slots__ = ("_backend", "_config")

    def __init__(self) -> None:
        self._backend: Any | None = None
        self._config = _BASELINE_CONFIG

    @classmethod
    def _from_backend(
        cls, backend: Any, *, config: GreekPipelineConfig | None = None
    ) -> GreekPipeline:
        if backend is None:
            if config is not None and config.backend != "baseline":
                raise ValueError("a neural configuration requires an owned backend")
            return cls()
        if config is not None and config.backend != "neural":
            raise ValueError("an owned backend requires a neural configuration")
        instance = cls.__new__(cls)
        instance._backend = backend
        instance._config = config if config is not None else _config_for_backend(backend)
        return instance

    @classmethod
    def neural(
        cls,
        *,
        variant: str = "default",
        force: bool = False,
        expected_receipt: AnalysisReceipt | None = None,
    ) -> GreekPipeline:
        """Load one explicit neural variant without changing the default facade."""
        from .joint import _load_neural_backend

        return cls._from_backend(
            _load_neural_backend(
                variant=variant,
                force=force,
                expected_receipt=expected_receipt,
            )
        )

    @classmethod
    def from_config(
        cls, config: GreekPipelineConfig, *, force: bool = False
    ) -> GreekPipeline:
        """Recreate a pipeline and require its live configuration to match exactly."""
        if not isinstance(config, GreekPipelineConfig):
            raise TypeError("config must be a GreekPipelineConfig")
        if config.backend == "baseline":
            if config != _BASELINE_CONFIG:
                raise ValueError("baseline configuration does not match this runtime")
            return cls()
        assert config.runtime_variant is not None
        selected = neural_variant(config.runtime_variant)
        registry_sha = variant_registry_sha256()
        if config.variant_registry_sha256 != registry_sha:
            raise ValueError(
                "neural pipeline configuration mismatch: "
                f"variant_registry_sha256: expected {config.variant_registry_sha256!r}, "
                f"got {registry_sha!r}"
            )
        if not selected.available:
            raise NeuralVariantUnavailableError(
                f"neural runtime variant {selected.label!r} is reserved but unavailable"
            )
        early_fields = {
            "model_id": selected.model_id,
            "dataset": selected.dataset,
            "runtime_variant": selected.label,
            "variant_award_sha256": selected.award_sha256,
            "qualification_sha256": selected.qualification_sha256,
            "bundle_manifest_sha256": selected.bundle_manifest_sha256,
        }
        early_mismatches = [
            f"{field}: expected {getattr(config, field)!r}, got {actual!r}"
            for field, actual in early_fields.items()
            if getattr(config, field) != actual
        ]
        if early_mismatches:
            raise ValueError(
                "neural pipeline configuration mismatch: " + "; ".join(early_mismatches)
            )
        candidate = cls.neural(variant=config.runtime_variant, force=force)
        if candidate.config != config:
            mismatches = [
                f"{field}: expected {getattr(config, field)!r}, "
                f"got {getattr(candidate.config, field)!r}"
                for field in config.__dataclass_fields__
                if getattr(config, field) != getattr(candidate.config, field)
            ]
            raise ValueError("Greek pipeline configuration mismatch: " + "; ".join(mismatches))
        return candidate

    @property
    def config(self) -> GreekPipelineConfig:
        """The immutable, serializable configuration identity."""
        return self._config

    @property
    def neural_active(self) -> bool:
        """Whether this instance owns a neural backend."""
        return self._backend is not None

    def analyze(
        self,
        text: str,
        *,
        parse: bool = False,
        with_confidence: bool = False,
        confidence_domain: str | None = None,
        confidence_policy: AbstentionPolicy | None = None,
        long_input: Literal["strict", "partial", "windowed"] = "strict",
        document_id: str = "input",
        sentence_policy: str = "default",
        segmenter: SegmenterLike | None = None,
    ) -> list[TokenRecord]:
        """Analyze text with this instance's backend and exact source alignment.

        ``document_id`` scopes the deterministic sentence and source-token IDs.
        ``sentence_policy`` controls document splitting independently of the model
        configuration's pretokenized-input segmentation contract. A caller-supplied
        ``segmenter`` is validated before its boundaries reach the backend.
        """
        from .pipeline import _analyze_bound

        if confidence_policy is not None and not with_confidence:
            raise ValueError("a confidence policy requires with_confidence=True")
        if confidence_domain is not None and not with_confidence:
            raise ValueError("a confidence domain requires with_confidence=True")
        with _bind(self):
            if confidence_domain is not None or confidence_policy is not None:
                return _analyze_bound(
                    text,
                    parse=parse,
                    with_confidence=with_confidence,
                    confidence_domain=confidence_domain,
                    confidence_policy=confidence_policy,
                    long_input=long_input,
                    document_id=document_id,
                    sentence_policy=sentence_policy,
                    segmenter=segmenter,
                )
            return _analyze_bound(
                text,
                parse=parse,
                with_confidence=with_confidence,
                long_input=long_input,
                document_id=document_id,
                sentence_policy=sentence_policy,
                segmenter=segmenter,
            )

    def analyze_tokens(
        self,
        tokens: Sequence[Token],
        *,
        parse: bool = False,
        with_confidence: bool = False,
        confidence_domain: str | None = None,
        confidence_policy: AbstentionPolicy | None = None,
        long_input: Literal["strict", "partial", "windowed"] = "strict",
        document_id: str = "input",
        sentence_policy: str = "default",
        segmenter: SegmenterLike | None = None,
    ) -> list[TokenRecord]:
        """Analyze typed tokens while retaining alignment and editorial form state.

        Complete, contiguous alignment sentence IDs are authoritative. Otherwise,
        ``sentence_policy`` or the validated external ``segmenter`` groups tokens.
        """
        from .pipeline import _analyze_bound

        if confidence_policy is not None and not with_confidence:
            raise ValueError("a confidence policy requires with_confidence=True")
        if confidence_domain is not None and not with_confidence:
            raise ValueError("a confidence domain requires with_confidence=True")
        with _bind(self):
            if confidence_domain is not None or confidence_policy is not None:
                return _analyze_bound(
                    "",
                    parse=parse,
                    with_confidence=with_confidence,
                    confidence_domain=confidence_domain,
                    confidence_policy=confidence_policy,
                    long_input=long_input,
                    document_id=document_id,
                    typed_tokens=tokens,
                    sentence_policy=sentence_policy,
                    segmenter=segmenter,
                )
            return _analyze_bound(
                "",
                parse=parse,
                with_confidence=with_confidence,
                long_input=long_input,
                document_id=document_id,
                typed_tokens=tokens,
                sentence_policy=sentence_policy,
                segmenter=segmenter,
            )

    def analyze_sentence(
        self,
        words: list[str],
        *,
        with_probs: bool = False,
        long_input: LongInputMode = "strict",
        confidence_domain: str | None = None,
        confidence_policy: AbstentionPolicy | None = None,
    ) -> SentenceAnalysis:
        """Analyze one pre-tokenized sentence with this instance's neural backend."""
        from .joint import analyze_sentence

        if confidence_policy is not None and not with_probs:
            raise ValueError("a confidence policy requires with_probs=True")
        if confidence_domain is not None and not with_probs:
            raise ValueError("a confidence domain requires with_probs=True")
        with _bind(self):
            if confidence_domain is not None or confidence_policy is not None:
                return analyze_sentence(
                    words,
                    with_probs=with_probs,
                    long_input=long_input,
                    domain=confidence_domain,
                    policy=confidence_policy,
                )
            return analyze_sentence(words, with_probs=with_probs, long_input=long_input)

    def analyze_sentences(
        self,
        sentences: Iterable[Iterable[str]],
        *,
        batch_size: int | None = None,
        with_probs: bool = False,
        long_input: LongInputMode = "strict",
        confidence_domain: str | None = None,
        confidence_policy: AbstentionPolicy | None = None,
    ) -> list[SentenceAnalysis]:
        """Analyze pre-tokenized sentences with this instance's neural backend."""
        from .joint import analyze_sentences

        if confidence_policy is not None and not with_probs:
            raise ValueError("a confidence policy requires with_probs=True")
        if confidence_domain is not None and not with_probs:
            raise ValueError("a confidence domain requires with_probs=True")
        with _bind(self):
            if confidence_domain is not None or confidence_policy is not None:
                return analyze_sentences(
                    sentences,
                    batch_size=batch_size,
                    with_probs=with_probs,
                    long_input=long_input,
                    domain=confidence_domain,
                    policy=confidence_policy,
                )
            return analyze_sentences(
                sentences,
                batch_size=batch_size,
                with_probs=with_probs,
                long_input=long_input,
            )

    def iter_analyze_sentences(
        self,
        sentences: Iterable[Iterable[str]],
        *,
        batch_size: int | None = None,
        with_probs: bool = False,
        long_input: LongInputMode = "strict",
        confidence_domain: str | None = None,
        confidence_policy: AbstentionPolicy | None = None,
    ) -> Iterator[SentenceAnalysis]:
        """Yield analyses lazily from this instance's captured neural backend."""

        from .joint import iter_analyze_sentences

        if confidence_policy is not None and not with_probs:
            raise ValueError("a confidence policy requires with_probs=True")
        if confidence_domain is not None and not with_probs:
            raise ValueError("a confidence domain requires with_probs=True")
        # `iter_analyze_sentences` is a normal function returning a nested generator: it
        # captures this bound backend synchronously, so no ContextVar token spans yields or
        # follows the consumer to another thread.
        with _bind(self):
            if confidence_domain is not None or confidence_policy is not None:
                return iter_analyze_sentences(
                    sentences,
                    batch_size=batch_size,
                    with_probs=with_probs,
                    long_input=long_input,
                    domain=confidence_domain,
                    policy=confidence_policy,
                )
            return iter_analyze_sentences(
                sentences,
                batch_size=batch_size,
                with_probs=with_probs,
                long_input=long_input,
            )


_BOUND: ContextVar[GreekPipeline | None] = ContextVar("pyaegean_greek_pipeline", default=None)
_DEFAULT_LOCK = RLock()
_DEFAULT = GreekPipeline()


@contextmanager
def _bind(pipeline: GreekPipeline) -> Iterator[None]:
    token = _BOUND.set(pipeline)
    try:
        yield
    finally:
        _BOUND.reset(token)


def _active_backend() -> _JointModel | None:
    bound = _BOUND.get()
    pipeline = bound if bound is not None else _DEFAULT
    return pipeline._backend


def default_pipeline() -> GreekPipeline:
    """The immutable instance used by the historical module-level facade."""
    return _DEFAULT


def _bound_pipeline() -> GreekPipeline | None:
    """Return the instance bound for the current call, if any.

    This tiny seam keeps the compatibility shim in :mod:`joint` from masking an
    explicitly bound instance.  It is private because callers should use a
    `GreekPipeline` method rather than relying on ambient state.
    """
    return _BOUND.get()


def _legacy_backends_allowed() -> bool:
    """Whether a legacy module-level backend may participate in this call.

    The default facade intentionally keeps the historical cascade of treebank,
    tagger, lemmatizer, and parser globals. An explicitly constructed baseline
    pipeline, however, must be self-contained: consulting those globals would
    make its baseline configuration misleading. Explicit neural instances are
    allowed because their joint backend is the instance-owned source of truth.
    """
    bound = _BOUND.get()
    return bound is None or bound is _DEFAULT or bound._backend is not None


def _set_default_pipeline(pipeline: GreekPipeline) -> None:
    global _DEFAULT
    with _DEFAULT_LOCK:
        _DEFAULT = pipeline


def _replace_default_backend(backend: Any | None) -> None:
    _set_default_pipeline(
        GreekPipeline() if backend is None else GreekPipeline._from_backend(backend)
    )
