"""Multi-provider AI layer — grounded, exploratory-labeled.

Providers: Anthropic (default), OpenAI, xAI Grok, Google Gemini, and OpenRouter. Each is an
optional extra, lazily imported. Capabilities: translate, gloss,
decipher_hypotheses, nlp_assist, ask, summarize. Every generative output is an
`ExploratoryResult` with provenance and an unverified flag.

    from aegean import ai
    client = ai.get_client("anthropic")          # needs pyaegean[anthropic] + a key
    result = ai.translate("μῆνιν ἄειδε θεά", client=client)
    print(result.labeled())                       # carries the EXPLORATORY tag
"""

from __future__ import annotations

from . import providers  # noqa: F401 — registers the built-in providers on import
from .cache import ResponseCache
from .capabilities import (
    PROMPT_VERSION,
    ask,
    decipher_hypotheses,
    extract,
    gloss,
    nlp_assist,
    parse_json,
    summarize,
    translate,
    verify_translation,
)
from .client import (
    AIError,
    ExploratoryResult,
    LLMClient,
    LLMResponse,
    MissingAPIKey,
    ProviderNotInstalled,
    UnknownProvider,
    get_client,
    register_provider,
)
from .eval import (
    DEFAULT_CASES,
    CaseResult,
    EvalReport,
    GroundingCase,
    run_eval,
    score_text,
)
from .client import providers as list_providers
from .grounding import (
    GroundingItem,
    as_item,
    clean_gloss,
    concise_gloss,
    content_glosses,
    cooccurrence_evidence,
    corpus_context,
    evidence_block,
    lexicon_evidence,
    wrap_untrusted,
)
from .idioms import idiom_glosses
from .sense import RegimeSignal, SenseCandidate, grounding_regime, select_sense

__all__ = [
    # client / factory
    "get_client",
    "list_providers",
    "register_provider",
    "LLMClient",
    "LLMResponse",
    "ExploratoryResult",
    "ResponseCache",
    # capabilities
    "translate",
    "verify_translation",
    "gloss",
    "decipher_hypotheses",
    "nlp_assist",
    "ask",
    "summarize",
    "extract",
    "parse_json",
    "PROMPT_VERSION",
    # grounded-generation eval
    "GroundingCase",
    "CaseResult",
    "EvalReport",
    "run_eval",
    "score_text",
    "DEFAULT_CASES",
    # grounding
    "GroundingItem",
    "as_item",
    "corpus_context",
    "lexicon_evidence",
    "content_glosses",
    "concise_gloss",
    "clean_gloss",
    "cooccurrence_evidence",
    "evidence_block",
    "wrap_untrusted",
    "idiom_glosses",
    # sense selection + grounding regime (exploratory)
    "select_sense",
    "grounding_regime",
    "SenseCandidate",
    "RegimeSignal",
    # errors
    "AIError",
    "ProviderNotInstalled",
    "MissingAPIKey",
    "UnknownProvider",
]
