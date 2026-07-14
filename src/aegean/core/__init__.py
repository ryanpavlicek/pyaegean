"""Script-agnostic core: data model, script plugin contract, corpus, numerals."""

from __future__ import annotations

from .corpus import Corpus, register_loader
from .model import (
    Document,
    DocumentMeta,
    FormSegment,
    ReadingStatus,
    Sign,
    SignInventory,
    SourceAlignment,
    SourceMarkupRef,
    Token,
    TokenFormState,
    TokenKind,
)
from .provenance import SCHEMA_VERSION, Provenance
from .script import Script, get_script, register, registered_scripts

__all__ = [
    "Corpus",
    "register_loader",
    "Document",
    "DocumentMeta",
    "FormSegment",
    "Sign",
    "SignInventory",
    "SourceAlignment",
    "SourceMarkupRef",
    "Token",
    "TokenFormState",
    "TokenKind",
    "ReadingStatus",
    "Provenance",
    "SCHEMA_VERSION",
    "Script",
    "get_script",
    "register",
    "registered_scripts",
]
