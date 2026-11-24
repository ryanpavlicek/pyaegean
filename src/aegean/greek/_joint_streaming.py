"""Internal bounded-memory sentence streaming and batching for the neural pipeline."""

from __future__ import annotations

import sys
from collections.abc import Callable, Iterable, Iterator
from typing import Any

from . import neural_preprocessing as _prep
from ._joint_confidence import _bind_stream_confidence_context
from ._joint_types import (
    LongInputMode,
    NeuralPipelineNotLoadedError,
    SentenceAnalysis,
    _long_input_mode,
)
from .confidence import AbstentionPolicy


def _copy_stream_sentence(sentence: Iterable[str], *, sentence_index: int) -> list[str]:
    """Own and validate one source sentence without retaining the caller's container."""

    if isinstance(sentence, (str, bytes)):
        raise TypeError(
            f"sentence {sentence_index} must be an iterable of token strings, not "
            f"{type(sentence).__name__}"
        )
    try:
        words = list(sentence)
    except TypeError as exc:
        raise TypeError(
            f"sentence {sentence_index} must be an iterable of token strings"
        ) from exc
    for token_index, word in enumerate(words):
        if not isinstance(word, str):
            raise TypeError(
                f"sentence {sentence_index} token {token_index} must be a string, "
                f"not {type(word).__name__}"
            )
    return words


def _stream_backend(model: Any) -> Any:
    """Capture optional wrapper state so one stream has one analysis configuration."""

    snapshot = getattr(model, "_snapshot_for_stream", None)
    return snapshot() if callable(snapshot) else model


def iter_analyze_sentences_impl(
    sentences: Iterable[Iterable[str]],
    *,
    active_fn: Callable[[], Any],
    batch_size: int | None = None,
    with_probs: bool = False,
    long_input: LongInputMode = "strict",
    domain: str | None = None,
    policy: AbstentionPolicy | None = None,
) -> Iterator[SentenceAnalysis]:
    """Core implementation of ``aegean.greek.joint.iter_analyze_sentences``."""
    if (domain is not None or policy is not None) and not with_probs:
        raise ValueError("confidence domain/policy requires with_probs=True")
    _long_input_mode(long_input)
    if batch_size is not None:
        if not isinstance(batch_size, int) or isinstance(batch_size, bool):
            raise TypeError(
                f"batch_size must be a positive integer or None, got {batch_size!r}"
            )
        if batch_size < 1:
            raise ValueError(f"batch_size must be a positive integer, got {batch_size!r}")
    if isinstance(sentences, (str, bytes)):
        raise TypeError("sentences must be an iterable of token-string iterables")
    model = active_fn()
    if model is None:
        raise NeuralPipelineNotLoadedError(
            "neural pipeline not loaded — call aegean.greek.use_neural_pipeline() first"
        )
    model = _stream_backend(model)
    method_name = "analyze" if batch_size is None else "analyze_batch"
    if not callable(getattr(model, method_name, None)):
        raise TypeError(f"active neural backend does not provide callable {method_name}()")
    captured_confidence: dict[str, Any] | None = None
    preflight = getattr(model, "_validate_stream_options", None)
    if callable(preflight):
        captured = preflight(
            with_probs=with_probs,
            long_input=long_input,
            domain=domain,
            policy=policy,
        )
        if isinstance(captured, dict):
            captured_confidence = captured

    use_options = (
        with_probs or long_input != "strict" or domain is not None or policy is not None
    )
    kwargs: dict[str, Any] = {"with_probs": with_probs, "long_input": long_input}
    if domain is not None:
        kwargs["domain"] = domain
    if policy is not None:
        kwargs["policy"] = policy

    def _iterator() -> Iterator[SentenceAnalysis]:
        source = iter(sentences)
        sentence_index = 0
        try:
            if batch_size is None:
                for sentence in source:
                    source_index = sentence_index
                    words = _copy_stream_sentence(
                        sentence, sentence_index=source_index
                    )
                    expected_tokens = tuple(_prep.normalize_tokens(words))
                    sentence_index += 1
                    with _bind_stream_confidence_context(captured_confidence):
                        analysis = (
                            model.analyze(words, **kwargs)
                            if use_options
                            else model.analyze(words)
                        )
                    if not isinstance(analysis, SentenceAnalysis):
                        raise TypeError(
                            "joint backend result at source index "
                            f"{source_index} must be SentenceAnalysis, not "
                            f"{type(analysis).__name__}"
                        )
                    if analysis.tokens != expected_tokens:
                        raise RuntimeError(
                            "joint backend did not preserve source order at index "
                            f"{source_index}: expected tokens {expected_tokens!r}, "
                            f"got {analysis.tokens!r}"
                        )
                    yield analysis
                return

            while True:
                chunk_start = sentence_index
                chunk: list[list[str]] = []
                for _ in range(batch_size):
                    try:
                        sentence = next(source)
                    except StopIteration:
                        break
                    chunk.append(
                        _copy_stream_sentence(sentence, sentence_index=sentence_index)
                    )
                    sentence_index += 1
                if not chunk:
                    return
                # Do not retain the producer's last sentence object in addition to the
                # owned copies in this chunk while results are yielded.
                del sentence
                expected_batch = [
                    tuple(_prep.normalize_tokens(words)) for words in chunk
                ]
                with _bind_stream_confidence_context(captured_confidence):
                    analyses = (
                        model.analyze_batch(chunk, **kwargs)
                        if use_options
                        else model.analyze_batch(chunk)
                    )
                if not isinstance(analyses, list):
                    raise TypeError(
                        "joint batch backend must return a list of SentenceAnalysis values"
                    )
                if len(analyses) != len(chunk):
                    chunk_end = chunk_start + len(chunk) - 1
                    raise RuntimeError(
                        "joint batch backend returned "
                        f"{len(analyses)} result(s) for {len(chunk)} sentence(s) "
                        f"at source indices {chunk_start}..{chunk_end}"
                    )
                for offset, analysis in enumerate(analyses):
                    if not isinstance(analysis, SentenceAnalysis):
                        raise TypeError(
                            "joint batch backend result at source index "
                            f"{chunk_start + offset} must be SentenceAnalysis, not "
                            f"{type(analysis).__name__}"
                        )
                    expected_tokens = expected_batch[offset]
                    if analysis.tokens != expected_tokens:
                        raise RuntimeError(
                            "joint batch backend did not preserve source order at index "
                            f"{chunk_start + offset}: expected tokens {expected_tokens!r}, "
                            f"got {analysis.tokens!r}"
                        )
                chunk_size = len(chunk)
                yield from analyses
                # `yield from` has completed: release this entire chunk before pulling
                # the next one, keeping live token ownership at one batch rather than two.
                del analysis, analyses, chunk, expected_batch, expected_tokens
                if chunk_size < batch_size:
                    return
        finally:
            primary_error = sys.exc_info()[1]
            try:
                close = getattr(source, "close", None)
            except BaseException:
                if primary_error is None:
                    raise
                close = None
            if callable(close):
                try:
                    close()
                except BaseException:
                    # Never replace a backend/source failure or consumer GeneratorExit
                    # with a secondary cleanup error. On ordinary exhaustion, however,
                    # a source's failing close remains visible to the caller.
                    if primary_error is None:
                        raise

    return _iterator()


def analyze_sentences_impl(
    sentences: Iterable[Iterable[str]],
    *,
    iter_fn: Callable[..., Iterator[SentenceAnalysis]],
    batch_size: int | None = None,
    length_bucket: bool = False,
    with_probs: bool = False,
    long_input: LongInputMode = "strict",
    domain: str | None = None,
    policy: AbstentionPolicy | None = None,
) -> list[SentenceAnalysis]:
    """Core implementation of ``aegean.greek.joint.analyze_sentences``."""
    if type(length_bucket) is not bool:
        raise TypeError("length_bucket must be a bool")
    if (
        length_bucket
        and type(batch_size) is int
        and batch_size > 1
        and long_input != "windowed"
    ):
        if isinstance(sentences, (str, bytes, bytearray)):
            raise TypeError("sentences must be an iterable of token sequences, not a single string")
        materialized = [
            _copy_stream_sentence(sentence, sentence_index=index)
            for index, sentence in enumerate(sentences)
        ]
        if not materialized:
            return list(
                iter_fn(
                    [],
                    batch_size=batch_size,
                    with_probs=with_probs,
                    long_input=long_input,
                    domain=domain,
                    policy=policy,
                )
            )
        order = sorted(range(len(materialized)), key=lambda i: len(materialized[i]))
        bucketed = list(
            iter_fn(
                (materialized[i] for i in order),
                batch_size=batch_size,
                with_probs=with_probs,
                long_input=long_input,
                domain=domain,
                policy=policy,
            )
        )
        restored: list[SentenceAnalysis] = [bucketed[0]] * len(bucketed)
        for pos, orig_idx in enumerate(order):
            restored[orig_idx] = bucketed[pos]
        return restored

    return list(
        iter_fn(
            sentences,
            batch_size=batch_size,
            with_probs=with_probs,
            long_input=long_input,
            domain=domain,
            policy=policy,
        )
    )
