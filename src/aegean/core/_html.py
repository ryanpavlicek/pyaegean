"""Stdlib-only HTML helpers for optional Jupyter ``_repr_html_`` rendering.

Every value object stays a plain dataclass; a few of them *also* render as
compact tables or cards inside a Jupyter/Colab notebook, with **no third-party
dependency**. These helpers build the HTML from already-structured data and
**escape every interpolated value**, so corpus- or user-derived text can never
break the markup or inject script into a notebook.

Callers that assemble HTML fragments by hand (titles, inline spans) must wrap
any dynamic text in `esc` themselves; `table` escapes its cells.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from html import escape as _escape

__all__ = ["esc", "badge", "table", "card"]


def esc(value: object) -> str:
    """HTML-escape any value (``None`` becomes an empty string)."""
    return _escape("" if value is None else str(value))


def badge(text: str, *, color: str = "#555") -> str:
    """A small inline pill — e.g. an ``EXPLORATORY`` tag or a flag."""
    return (
        f'<span style="background:{esc(color)};color:#fff;border-radius:4px;'
        f'padding:1px 6px;font-size:0.8em;font-weight:600">{esc(text)}</span>'
    )


def table(headers: Sequence[str], rows: Iterable[Sequence[object]]) -> str:
    """A simple ``<table>`` with a header row; **every cell is escaped**."""
    head = "".join(
        f"<th style='text-align:left;padding:2px 8px'>{esc(h)}</th>" for h in headers
    )
    body = "".join(
        "<tr>" + "".join(f"<td style='padding:2px 8px'>{esc(c)}</td>" for c in row) + "</tr>"
        for row in rows
    )
    return (
        "<table style='border-collapse:collapse;font-size:0.9em'>"
        f"<thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"
    )


def card(title_html: str, body_html: str) -> str:
    """Wrap pre-built (already-escaped) HTML in a titled block."""
    return (
        "<div style='font-family:sans-serif;line-height:1.4'>"
        f"<div style='font-weight:600;margin-bottom:4px'>{title_html}</div>"
        f"{body_html}</div>"
    )
