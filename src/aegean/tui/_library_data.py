"""Data store, Greek work library, TUI config, and unified library manager adapters.

Re-exported from :mod:`aegean.tui.data` so screens and tests keep a single adapter import boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable

from ._bible_data import _parse_passage_spec
from .data import CorpusEntry, DatasetRow, TuiError, _store_root

if TYPE_CHECKING:
    from pathlib import Path

    from ..core.corpus import Corpus

# ── data store ─────────────────────────────────────────────────────────────────
def doctor_report() -> dict[str, Any]:
    """The full offline environment report, verbatim from
    :func:`aegean._doctor.build_report` (versions, extras, data store,
    models, analysis cache). No network is touched, and no CLI dependency
    is imported: the report builds in a ``[tui]``-only environment."""
    from .._doctor import build_report

    return build_report()


def dataset_rows() -> list[DatasetRow]:
    """Every fetchable dataset and whether it is downloaded (with its on-disk
    size), for the data-store table. The same per-dataset state ``aegean data
    list`` reports; offline."""
    from ..data import _REMOTE, downloaded_bytes, is_downloaded

    root = _store_root()
    rows: list[DatasetRow] = []
    for name, spec in sorted(_REMOTE.items()):
        # is_downloaded/downloaded_bytes (not a bare root/name probe) so a dataset
        # fetched under a different filename via index/extract is seen, matching the CLI.
        downloaded = is_downloaded(spec, root) if root is not None else False
        size = downloaded_bytes(spec, root) if (downloaded and root is not None) else None
        rows.append(
            DatasetRow(
                name=name,
                downloaded=downloaded,
                bytes=size,
                note=spec.note,
                license=spec.license,
            )
        )
    return rows


class FetchCanceled(TuiError):
    """The fetch's ``abort`` hook fired (the worker was cancelled): the partial
    download is kept on disk, so a later fetch resumes it."""


def fetch_dataset(
    name: str,
    on_progress: Callable[[str], None] | None = None,
    abort: Callable[[], bool] | None = None,
) -> "Path":
    """Download a dataset into the local store, reporting progress lines through
    ``on_progress`` (a screen runs this on a Textual worker so the UI stays live).

    Wraps :func:`aegean.data.fetch`, which is sha256-verified, resumable, and a
    no-op when the dataset is already stored. An unknown name or a network
    failure becomes a :class:`TuiError` the screen can show. ``on_progress`` is
    invoked with a short status before and after the transfer (the underlying
    fetch reports no byte-level progress). ``abort`` is polled during the
    transfer; when it returns true the download stops with :class:`FetchCanceled`
    (how a cancelled worker actually interrupts the transfer, e.g. on quit)."""
    from ..data import _REMOTE, DataNotAvailableError, FetchAborted
    from ..data import fetch as _fetch

    if name not in _REMOTE:
        raise TuiError(f"unknown dataset {name!r}")
    if on_progress is not None:
        on_progress(f"fetching {name}…")
    try:
        path = _fetch(name, abort=abort)
    except FetchAborted:
        raise FetchCanceled(f"fetch of {name} canceled (partial download kept)") from None
    except DataNotAvailableError as exc:
        raise TuiError(str(exc)) from None
    except Exception as exc:  # network / disk failure
        raise TuiError(f"could not fetch {name!r}: {exc}") from None
    if on_progress is not None:
        on_progress(f"stored {name}")
    return path


# ── Greek work library (fetch + read individual works, distinct from datasets) ──


def read_corpus_spec(spec: str) -> "Corpus":
    """Load any corpus spec — a registered id, a Greek work id (``tlg0012.tlg001``), or a
    ``.json``/``.db`` file — re-raising failures as a clean :class:`TuiError`.

    A superset of :func:`load_corpus` (registered ids only): this is how the corpus browser
    opens a fetched Greek work or a saved file. The registered corpora resolve identically."""
    from ..core.resolve import CorpusNotFound, read_corpus

    try:
        return read_corpus(spec)
    except (CorpusNotFound, KeyError):
        raise TuiError(f"no corpus {spec!r}") from None
    except Exception as exc:  # network / parse failure on a fetch-on-demand work
        raise TuiError(f"could not load {spec!r}: {exc}") from None


@dataclass(frozen=True)
class WorkRow:
    """One Greek work in the library table: catalogue metadata plus whether it is already
    fetched to the cache (and its on-disk size when so)."""

    id: str
    author: str
    title: str
    greek_title: str
    source: str
    fetched: bool
    bytes: int | None


def _fetched_works() -> list[dict[str, Any]]:
    from ..greek import list_fetched_works

    return list_fetched_works()


def fetched_work_ids() -> list[str]:
    """The CTS ids of every Greek work already downloaded to the cache (a local scan)."""
    return [w["id"] for w in _fetched_works()]


def remove_work(work_id: str) -> bool:
    """Delete one downloaded Greek work from the cache. Returns True if it was removed
    (False when it was not downloaded). Wraps ``greek.remove_fetched_works``."""
    from ..greek import remove_fetched_works

    return work_id in remove_fetched_works([work_id])


def fetched_work_entries() -> list[CorpusEntry]:
    """Every downloaded Greek work as a :class:`CorpusEntry`, so the corpus browser can list
    them alongside the registered corpora — a fetched work is a permanent, selectable corpus,
    not a transient one. Blurb is ``author — title (Greek work)``; always on disk, never
    undeciphered."""
    entries: list[CorpusEntry] = []
    for w in _fetched_works():
        label = f"{w['author']} — {w['title']}".strip(" —") or w["id"]
        entries.append(
            CorpusEntry(
                id=w["id"], blurb=f"{label} (Greek work)",
                downloaded=True, bundled=False, undeciphered=False,
            )
        )
    return entries


def catalog_rows(
    query: str | None = None,
    *,
    author: str | None = None,
    title: str | None = None,
    source: str | None = None,
) -> list[WorkRow]:
    """The Greek-work catalogue as :class:`WorkRow`s, each flagged with its fetched state.

    Case-insensitive substring filtering (the library ``catalog`` already ANDs the filters).
    The screen renders a capped slice; the full match list is returned so it can show the count."""
    from ..greek import catalog

    fetched = {w["id"]: w for w in _fetched_works()}
    out: list[WorkRow] = []
    for w in catalog(query, author=author, title=title, source=source):
        hit = fetched.get(w["id"])
        out.append(
            WorkRow(
                id=w["id"], author=w.get("author", ""), title=w.get("title", ""),
                greek_title=w.get("greek_title", ""), source=w.get("source", ""),
                fetched=hit is not None, bytes=(hit["bytes"] if hit else None),
            )
        )
    return out


def fetch_work(
    work_id: str,
    on_progress: Callable[[str], None] | None = None,
    abort: Callable[[], bool] | None = None,
) -> "Path":
    """Fetch one Greek work into the cache (via ``load_work``); returns its cache path.

    A screen runs this on a worker. ``abort`` is polled before the transfer (a single work is a
    small TEI file, so cancellation is best-effort, not mid-chunk). Errors become :class:`TuiError`."""
    from pathlib import Path

    from ..data import DataNotAvailableError, FetchAborted
    from ..greek import list_fetched_works, load_work

    if abort is not None and abort():
        raise FetchCanceled(f"fetch of {work_id} canceled")
    if on_progress is not None:
        on_progress(f"fetching {work_id}…")
    try:
        load_work(work_id)
    except FetchAborted:
        raise FetchCanceled(f"fetch of {work_id} canceled (partial download kept)") from None
    except DataNotAvailableError as exc:
        raise TuiError(str(exc)) from None
    except Exception as exc:  # network / parse failure
        raise TuiError(f"could not fetch {work_id!r}: {exc}") from None
    path = next((Path(w["path"]) for w in list_fetched_works() if w["id"] == work_id), None)
    if path is None:
        raise TuiError(f"fetched {work_id} but could not locate it in the cache")
    if on_progress is not None:
        on_progress(f"stored {work_id}")
    return path


def fetch_author_works(
    author: str,
    *,
    source: str = "auto",
    on_progress: Callable[[str], None] | None = None,
    abort: Callable[[], bool] | None = None,
) -> list[str]:
    """Fetch every catalogue work by ``author`` into the cache; returns the ids present after.

    Drives the shared ``fetch_works`` generator (idempotent — cached works are skipped), streaming
    a per-work line through ``on_progress``. A rate limit or abort surfaces as :class:`TuiError` /
    :class:`FetchCanceled` after the works already fetched are kept."""
    from ..data import FetchAborted
    from ..greek import GitHubRateLimitError, fetch_works

    src = None if source == "auto" else source
    done: list[str] = []

    def progress(i: int, total: int, w: dict[str, str]) -> None:
        if on_progress is not None:
            on_progress(f"[{i}/{total}] {w['id']} ({w.get('title', '')})…")

    try:
        for res in fetch_works(author=author, source=src, on_progress=progress, abort=abort):
            if res.status in ("fetched", "cached"):
                done.append(res.id)
    except FetchAborted:
        raise FetchCanceled(f"fetch of {author!r} works canceled (fetched works kept)") from None
    except GitHubRateLimitError as exc:
        raise TuiError(str(exc)) from None
    except Exception as exc:  # network / disk failure
        raise TuiError(f"could not fetch works by {author!r}: {exc}") from None
    return done


# ── persisted TUI config (theme, …); a sibling of the REPL history file ──


def config_path() -> "Path":
    """The TUI config file: ``$XDG_CONFIG_HOME/pyaegean/tui.json`` (or ``~/.config/...``)."""
    import os
    from pathlib import Path

    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "pyaegean" / "tui.json"


def load_tui_config() -> dict[str, Any]:
    """The persisted TUI config, or ``{}`` when missing/unreadable/invalid (never raises)."""
    import json

    try:
        return dict(json.loads(config_path().read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return {}


def save_tui_config(data: dict[str, Any]) -> None:
    """Persist the TUI config (best-effort — a write failure is swallowed, like the REPL history)."""
    import json

    path = config_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")
    except OSError:
        pass


# ── Unified library manager adapter helpers ──────────────────────────────


def library_summary() -> dict[str, Any]:
    """Unified local library status across all categories and packs (offline)."""
    from .. import library

    return library.summary()


def library_packs() -> list[Any]:
    """Installation status for every named pack (offline)."""
    from .. import library

    return library.list_packs()


def library_items(
    *,
    category: str | None = None,
    status: str | None = None,
    query: str | None = None,
    include_works: bool = False,
    limit: int | None = None,
) -> list[Any]:
    """List unified library items with optional filters (offline)."""
    from .. import library

    return library.list_items(
        category=category,
        status=status,
        query=query,
        include_works=include_works,
        limit=limit,
    )


def library_install(
    targets: str | list[str],
    *,
    force: bool = False,
    on_progress: Callable[[str], None] | None = None,
    abort: Callable[[], bool] | None = None,
) -> list[Any]:
    """Install one or more library targets (packs, datasets, works), translating errors to TuiError."""
    from .. import library
    from ..data import FetchAborted

    try:
        results = library.install(targets, force=force, progress=on_progress, abort=abort)
    except FetchAborted:
        raise FetchCanceled("download canceled (partial download kept)") from None
    except LookupError as exc:
        raise TuiError(str(exc)) from None
    except Exception as exc:
        raise TuiError(f"download failed: {exc}") from None
    failed = [r for r in results if r.status == "failed"]
    if failed and len(failed) == len(results):
        raise TuiError(f"could not install {failed[0].id}: {failed[0].error}")
    return results


def library_remove(targets: str | list[str]) -> list[Any]:
    """Remove one or more downloaded datasets, works, or packs from disk."""
    from .. import library

    try:
        results = library.remove(targets)
    except (LookupError, ValueError) as exc:
        raise TuiError(str(exc)) from None
    except Exception as exc:
        raise TuiError(f"removal failed: {exc}") from None
    failed = [r for r in results if r.status == "failed"]
    if failed and len(failed) == len(results):
        raise TuiError(f"could not remove {failed[0].id}: {failed[0].error}")
    return results


def remove_dataset(name: str) -> int:
    """Remove one downloaded dataset from disk; returns reclaimed bytes or raises TuiError."""
    from ..data import DataNotAvailableError
    from ..data import remove_dataset as _remove_dataset

    try:
        res = _remove_dataset(name)
    except DataNotAvailableError as exc:
        raise TuiError(str(exc)) from None
    if res is None:
        return 0
    return int(res["bytes"])


def missing_corpus_item(corpus_id: str) -> Any | None:
    """Return the missing LibraryItem for ``corpus_id`` if not yet downloaded, else None."""
    from .. import library

    return library.missing_for_corpus(corpus_id)


def missing_bible_items(
    *,
    tab: str = "interlinear",
    edition: str = "nestle1904",
    passage: str = "John 1.1-5",
) -> list[Any]:
    """Return missing LibraryItem(s) needed by the active BiblicalScreen view."""
    from .. import library

    book, ref = _parse_passage_spec(passage)
    return library.missing_for_bible(tab=tab, edition=edition, book=book, ref=ref)


