"""Multi-provider AI layer — grounded, exploratory-labeled.

Providers: Anthropic (default), OpenAI, xAI Grok, Google Gemini — each an
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
    cooccurrence_evidence,
    corpus_context,
    evidence_block,
    lexicon_evidence,
    wrap_untrusted,
)

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
    "cooccurrence_evidence",
    "evidence_block",
    "wrap_untrusted",
    # errors
    "AIError",
    "ProviderNotInstalled",
    "MissingAPIKey",
    "UnknownProvider",
]
