"""Provider-agnostic LLM client contract + result/labeling types.

The AI layer is **multi-provider** (Anthropic default, plus OpenAI, xAI Grok,
Google Gemini, OpenRouter, and `local` for a locally hosted OpenAI-compatible endpoint) and
**optional**: provider SDKs are extras, imported lazily inside
each adapter, so ``import aegean`` never requires them. Every generative output
is wrapped in an `ExploratoryResult` carrying provenance (provider, model,
prompt version) and an ``exploratory`` flag — generative readings of this
material are hypotheses, never ground truth.

Model selection is **configurable and current** by design (model ids drift):
each provider resolves its model from an explicit ``model=`` argument, then a
``<PROVIDER>_MODEL`` environment variable, then a default constant. Point
``ANTHROPIC_MODEL`` at the latest flagship Claude for maximum capability.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class AIError(RuntimeError):
    """Base class for AI-layer errors."""


class ProviderNotInstalled(AIError):
    """Raised when a provider's optional SDK isn't installed."""


class MissingAPIKey(AIError):
    """Raised when no API key is available for a provider."""


class UnknownProvider(AIError):
    """Raised for an unregistered provider id."""


class ProviderCallError(AIError):
    """Raised when a provider's API call fails (bad model id, authentication, rate
    limit, network). Wraps the SDK's exception so callers see one `AIError` type
    instead of a provider-specific traceback; the underlying error is the ``__cause__``."""


@dataclass(frozen=True, slots=True)
class LLMResponse:
    """A raw completion from a provider."""

    text: str
    provider: str
    model: str
    raw: Any = None  # provider-native object; never serialized into exports


@dataclass(frozen=True, slots=True)
class ExploratoryResult:
    """A generative result, explicitly labeled exploratory and provenanced.

    ``grounding`` is the structured corpus/lexicon/analysis evidence fed to the
    model (each a `GroundingItem` with a source and a ref). Use `labeled` when
    surfacing to a user so the caveat travels with the text, `trace` to audit
    which local evidence grounded the output, and `data` (when set by a structured
    capability) for the parsed JSON payload. ``grounding_runtime`` retains the
    complete local execution provenance; a compact backend/coverage summary may
    also appear among the prompt evidence.
    ``draft`` retains the complete original result when a translation receives
    an optional model checking pass. Translation audit data separates the final
    wording, model-reported uncertainty and changes, and the exact raw response;
    a structured format status validates its shape, not the translation.
    """

    text: str
    kind: str            # "translate" | "gloss" | "decipher" | "nlp_assist" | "ask" | "summarize" | "extract"
    provider: str
    model: str
    prompt_version: str
    grounding: tuple[GroundingItem, ...] = ()
    exploratory: bool = True
    data: Any = None     # parsed structured output, when a capability requested JSON
    grounding_runtime: dict[str, Any] | None = None
    # Local grounding execution facts (backend/config/failure policy). These are
    # provenance only: this full mapping is not sent to the provider. A builder
    # can supply compact runtime evidence separately through GroundingItem.
    draft: ExploratoryResult | None = None

    def _translation_notes(self) -> str:
        """Render reported audit information without implying scholarly review."""
        if self.kind != "translate" or not isinstance(self.data, dict):
            return ""
        data = self.data
        if "format_status" not in data:
            return ""
        if data["format_status"] != "structured":
            warning = (
                "[Unstructured response: separate translation, uncertainty and change "
                "information unavailable; raw response retained.]"
            )
            retained = self._retained_draft_notes(concise=data.get("style") == "concise")
            return warning + (f"\n{retained}" if retained else "")
        uncertainties = data.get("uncertainties")
        changes = data.get("changes")
        if not isinstance(uncertainties, list) or not isinstance(changes, list):
            return "[Translation audit information unavailable; inspect the saved response.]"
        lines: list[str] = []
        if data.get("change_report_status") == "unreported_text_difference":
            lines.append(
                "[Exact text comparison: final text differs from the draft, but the "
                "model reported no changes. This is a wording difference, not a quality assessment.]"
            )
        elif data.get("change_report_status") == "reported_changes" and data.get("text_changed") is False:
            lines.append(
                "[Exact text comparison: final text is identical to the draft; the "
                "model's reported changes are not independently verified.]"
            )
        elif data.get("change_report_status") == "no_text_difference":
            lines.append("[Exact text comparison: final translation text is identical to the draft.]")
        elif "draft_text" in data and data.get("change_report_status") == "not_comparable":
            note = data.get("comparison_note")
            lines.append(
                f"[{note}]" if isinstance(note, str)
                else "[Exact translation comparison unavailable for this draft.]"
            )
        if data.get("style") == "concise":
            lines.append(
                f"[Model-reported notes: {len(uncertainties)} uncertainty note(s), "
                f"{len(changes)} change(s); details retained in trace and JSON.]"
            )
        else:
            lines.append("Model-reported uncertainties:")
            lines.extend(f"- {note}" for note in uncertainties)
            if not uncertainties:
                lines.append("- None listed by the model; this is not a correctness assessment.")
            if changes or "draft_text" in data:
                lines.append("Model-reported changes (not independently verified):")
                for change in changes:
                    if not isinstance(change, dict):
                        continue
                    lines.append(f"- {change.get('before', '')} → {change.get('after', '')}")
                    lines.append(f"  Reason: {change.get('reason', '')}")
                    evidence = change.get("evidence")
                    refs = "; ".join(str(ref) for ref in evidence) if isinstance(evidence, list) else ""
                    lines.append(f"  Evidence reported by model: {refs or 'none supplied'}")
                if not changes:
                    lines.append("- None listed by the model; this is not a correctness assessment.")
        retained = self._retained_draft_notes(concise=data.get("style") == "concise")
        if retained:
            lines.append(retained)
        return "\n".join(lines)

    def _retained_draft_notes(self, *, concise: bool) -> str:
        lines: list[str] = []
        if self.draft is not None:
            draft_data = self.draft.data if isinstance(self.draft.data, dict) else {}
            draft_uncertainties = draft_data.get("uncertainties")
            if isinstance(draft_uncertainties, list) and draft_uncertainties:
                lines.append(
                    f"Retained draft: {len(draft_uncertainties)} original uncertainty note(s); "
                    "their omission from the final notes does not establish resolution."
                )
                if not concise:
                    lines.extend(f"- {note}" for note in draft_uncertainties)
            lines.append("The complete draft and its provenance are retained in trace and JSON.")
        elif isinstance(self.data, dict) and "draft_text" in self.data:
            lines.append("The original string draft is retained in trace and JSON; provenance was not supplied.")
        return "\n".join(lines)

    def labeled(self) -> str:
        """The text prefixed with an unmistakable exploratory provenance tag."""
        tag = f"[EXPLORATORY · {self.kind} · {self.provider}/{self.model}]"
        summary = ""
        if self.grounding_runtime is not None:
            runtime = self.grounding_runtime
            pipeline = runtime.get("pipeline")
            if isinstance(pipeline, dict):
                summary = f"\n[Greek grounding · {pipeline.get('backend', '')} · {pipeline.get('selection', '')}"
                coverage = runtime.get("coverage")
                if isinstance(coverage, dict) and runtime.get("mode") != "none":
                    total = coverage.get("tokens")
                    summary += f" · {coverage.get('analyzed_tokens', 0)}/{total if total is not None else 'unknown'} tokens analyzed"
                if runtime.get("mode") == "none":
                    summary += " · local analysis disabled"
                if runtime.get("degraded"):
                    summary += " · degraded: " + (", ".join(runtime.get("missing_stages", ())) or "local analysis")
                summary += "]"
        notes = self._translation_notes()
        return f"{tag}{summary}\n{self.text}" + (f"\n\n{notes}" if notes else "")

    def trace(self) -> str:
        """A human-readable provenance trace: the generative step and the local,
        non-generative evidence that grounded it, grouped by source.

        Makes the exploratory result auditable — every grounding line names the
        source (corpus, lexicon, analysis step) and the ref it came from, so a
        reader can check the output against the evidence it was given rather than
        taking it on trust."""
        from collections import defaultdict

        lines = [
            f"EXPLORATORY {self.kind} via {self.provider}/{self.model} "
            f"(prompt {self.prompt_version})",
        ]
        if self.kind == "translate" and isinstance(self.data, dict) and "format_status" in self.data:
            import json

            lines.append("  translation audit (model-reported; format status describes shape only):")
            lines.extend(
                f"      {line}" for line in json.dumps(
                    self.data, ensure_ascii=False, indent=2
                ).splitlines()
            )
        if self.draft is not None:
            import json

            lines.append("  retained draft (original result and provenance):")
            lines.extend(
                f"      {line}" for line in json.dumps(
                    self.draft.to_dict(), ensure_ascii=False, indent=2
                ).splitlines()
            )
        if self.grounding_runtime is not None:
            runtime = self.grounding_runtime
            lines.append("  grounding runtime:")
            lines.append(f"      script: {runtime.get('script', '')}")
            lines.append(f"      mode: {runtime.get('mode', '')}")
            lines.append(f"      failure policy: {runtime.get('failure_policy', '')}")
            pipeline = runtime.get("pipeline")
            if isinstance(pipeline, dict):
                selection = pipeline.get("selection", "")
                backend = pipeline.get("backend", "")
                lines.append(f"      Greek pipeline: {selection} ({backend})")
                config = pipeline.get("config")
                if config is not None:
                    import json

                    lines.append(
                        "      Greek pipeline config: "
                        + json.dumps(config, ensure_ascii=False, sort_keys=True)
                    )
                note = pipeline.get("note")
                if note:
                    lines.append(f"      note: {note}")
            failures = runtime.get("failures", ())
            coverage = runtime.get("coverage")
            if isinstance(coverage, dict):
                total = coverage.get("tokens")
                lines.append(
                    f"      coverage: {coverage.get('analyzed_tokens', 0)}/{total if total is not None else 'unknown'} "
                    "tokens analyzed; "
                    f"{coverage.get('feature_tokens', 0)} with morphological features; "
                    f"{coverage.get('dependency_tokens', 0)} with dependencies"
                )
            missing = runtime.get("missing_stages")
            if missing:
                lines.append(f"      unavailable or incomplete: {', '.join(missing)}")
            if isinstance(failures, (list, tuple)):
                for failure in failures:
                    if isinstance(failure, dict):
                        lines.append(
                            "      degraded: "
                            f"{failure.get('stage', 'grounding')} "
                            f"({failure.get('error_type', 'error')})"
                        )
        if not self.grounding:
            lines.append("  grounding: none (ungrounded generation — weigh accordingly)")
            return "\n".join(lines)
        by_source: dict[str, list[GroundingItem]] = defaultdict(list)
        for item in self.grounding:
            by_source[item.source].append(item)
        lines.append(f"  grounded in {len(self.grounding)} item(s) from {len(by_source)} source(s):")
        for source in sorted(by_source):
            items = by_source[source]
            lines.append(f"  • {source} ({len(items)}):")
            lines.extend(f"      - {item.render()}" for item in items)
        return "\n".join(lines)

    def provenance(self) -> dict[str, Any]:
        result = {
            "provider": self.provider,
            "model": self.model,
            "prompt_version": self.prompt_version,
            "kind": self.kind,
            "exploratory": self.exploratory,
            "grounding": [
                g.to_dict() for g in self.grounding
            ],
        }
        if self.grounding_runtime is not None:
            result["grounding_runtime"] = self.grounding_runtime
        if self.draft is not None:
            result["draft"] = self.draft.provenance()
        return result

    def to_dict(self) -> dict[str, Any]:
        """A stable, JSON-ready serialization. Keeps the ``exploratory`` flag, the text, the
        grounding, and any structured ``data`` — so a saved AI result can never be mistaken
        for ground truth when read back."""
        result = {
            "_meta": {"tool": "pyaegean", "type": "ExploratoryResult", "schemaVersion": 1},
            "kind": self.kind,
            "text": self.text,
            "provider": self.provider,
            "model": self.model,
            "prompt_version": self.prompt_version,
            "exploratory": self.exploratory,
            "grounding": [
                g.to_dict() for g in self.grounding
            ],
            "data": self.data,
        }
        if self.grounding_runtime is not None:
            result["grounding_runtime"] = self.grounding_runtime
        if self.draft is not None:
            result["draft"] = self.draft.to_dict()
        return result

    def to_json(self, path: str | Path | None = None, *, indent: int | None = 2) -> str | None:
        """Serialize to JSON: returns the string, or writes it to ``path`` and returns ``None``."""
        import json

        text = json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)
        if path is None:
            return text
        from .._atomic import atomic_path

        with atomic_path(path) as tmp:
            tmp.write_text(text, encoding="utf-8")
        return None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExploratoryResult":
        """Reconstruct an `ExploratoryResult` from `to_dict` output."""
        grounding_runtime = data.get("grounding_runtime")
        if grounding_runtime is not None and not isinstance(grounding_runtime, dict):
            raise ValueError("grounding_runtime must be an object or null")
        draft = data.get("draft")
        if draft is not None and not isinstance(draft, dict):
            raise ValueError("draft must be an ExploratoryResult object or null")
        return cls(
            text=data["text"],
            kind=data.get("kind", ""),
            provider=data.get("provider", ""),
            model=data.get("model", ""),
            prompt_version=data.get("prompt_version", ""),
            grounding=tuple(
                GroundingItem.from_dict(g)
                for g in data.get("grounding", ())
            ),
            exploratory=data.get("exploratory", True),
            data=data.get("data"),
            grounding_runtime=(
                dict(grounding_runtime) if grounding_runtime is not None else None
            ),
            draft=cls.from_dict(draft) if draft is not None else None,
        )

    def _repr_html_(self) -> str:
        """Rich rendering in Jupyter/Colab — the exploratory tag is unmissable."""
        from ..core._html import badge, card, esc

        tag = badge(f"EXPLORATORY · {self.kind}", color="#b00")
        body = (
            f"<div style='margin:4px 0'>{tag} "
            f"<span style='color:#888;font-size:0.85em'>{esc(self.provider)}/{esc(self.model)}"
            "</span></div>"
            f"<div style='white-space:pre-wrap'>{esc(self.text)}</div>"
        )
        notes = self._translation_notes()
        if notes:
            body += f"<div style='white-space:pre-wrap;margin-top:6px'>{esc(notes)}</div>"
        if self.draft is not None:
            body += (
                "<details style='margin-top:6px'><summary>Retained original draft</summary>"
                f"<div style='white-space:pre-wrap'>{esc(self.draft.labeled())}</div></details>"
            )
        if self.grounding:
            items = "".join(
                f"<li>{esc(g.render())}</li>"
                for g in self.grounding
            )
            body += (
                "<div style='color:#666;font-size:0.85em;margin-top:6px'>grounding:"
                f"<ul style='margin:2px 0'>{items}</ul></div>"
            )
        return card("AI result", body)


class LLMClient(ABC):
    """Abstract provider client. Subclasses implement `_complete`."""

    provider: str = ""
    env_key: str = ""        # API-key environment variable
    env_model: str = ""      # model-override environment variable
    default_model: str = ""  # fallback when neither arg nor env is set

    def __init__(
        self,
        model: str | None = None,
        *,
        api_key: str | None = None,
        cache: ResponseCache | None = None,
    ) -> None:
        self.model = model or os.environ.get(self.env_model) or self.default_model
        self._api_key = api_key or os.environ.get(self.env_key)
        self.cache = cache

    def _require_key(self) -> str:
        if not self._api_key:
            raise MissingAPIKey(
                f"no API key for {self.provider!r}; set ${self.env_key} or pass api_key="
            )
        return self._api_key

    @abstractmethod
    def _complete(self, *, prompt: str, system: str | None, max_tokens: int) -> LLMResponse:
        """Provider-specific single-turn completion."""

    def _cache_id(self) -> str:
        """The provider identity the response cache keys on. A provider whose responses
        depend on per-instance routing state (the ``local`` provider's endpoint URL: two
        servers can host different models under one name) must fold that state in here,
        or one endpoint's cached completion would be served for the other's."""
        return self.provider

    def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        """A cached single-turn completion (cache is keyed on provider identity/model/
        system/prompt/max_tokens so re-asking is free and deterministic)."""
        if self.cache is not None:
            hit = self.cache.get(self._cache_id(), self.model, system, prompt, max_tokens=max_tokens)
            if hit is not None:
                return LLMResponse(hit, self.provider, self.model)
        resp = self._complete(prompt=prompt, system=system, max_tokens=max_tokens)
        if self.cache is not None:
            self.cache.set(self._cache_id(), self.model, system, prompt, resp.text, max_tokens=max_tokens)
        return resp


# Provider registry — adapters register themselves on import.
_PROVIDERS: dict[str, type[LLMClient]] = {}


def register_provider(cls: type[LLMClient]) -> type[LLMClient]:
    """Register an ``LLMClient`` subclass under its ``provider`` name (each adapter calls this)."""
    _PROVIDERS[cls.provider] = cls
    return cls


def get_client(
    provider: str = "anthropic",
    *,
    model: str | None = None,
    api_key: str | None = None,
    cache: ResponseCache | None = None,
) -> LLMClient:
    """Construct a client for ``provider`` (default Anthropic). Importing
    `aegean.ai` registers all built-in providers."""
    try:
        cls = _PROVIDERS[provider]
    except KeyError:
        raise UnknownProvider(
            f"unknown provider {provider!r}; available: {sorted(_PROVIDERS)}"
        ) from None
    return cls(model, api_key=api_key, cache=cache)


def providers() -> list[str]:
    """Sorted names of registered providers, e.g. ``['anthropic', 'gemini', 'grok', 'local', 'openai', 'openrouter']``."""
    return sorted(_PROVIDERS)


# Imported here to avoid a circular import at module top (cache imports nothing
# from this module, but keep the public type available for annotations above).
from .cache import ResponseCache  # noqa: E402
from .grounding import GroundingItem  # noqa: E402
