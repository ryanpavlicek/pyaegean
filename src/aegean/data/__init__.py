"""Bundled-data access + a download-to-cache layer.

Compact text data ships in the wheel (read via importlib.resources). Large or
license-restricted assets — notably the Linear A facsimile mirror (~116 MB) — are
NOT bundled; they are fetched on demand from upstream into a user cache. This
is how the package stays small regardless of how large the source corpora are.
The "cache" is a permanent local store, not an evicting one: a fetched dataset
is downloaded once in full and stays on disk (never re-fetched, evicted, or
expired) until you remove it (``aegean data remove``).

Downloads are sha256-verified (when a checksum is pinned), atomic (written to a
``.part`` file then renamed), idempotent (a present, valid cache file is a
no-op), and resumable: a transfer cut off by a network failure keeps its
``.part`` file, and the next attempt (an in-call retry, or a later ``fetch``)
continues from the bytes already on disk via an HTTP Range request rather than
restarting a multi-hundred-MB asset from zero. A dataset's URL can be
overridden without a code change via
``PYAEGEAN_<NAME>_URL`` (e.g. ``PYAEGEAN_LINEARA_IMAGES_URL``), so a researcher
can point at their own mirror before an official release is pinned.
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import re
from collections.abc import Callable
from dataclasses import dataclass
from importlib.resources import files
from typing import IO, TYPE_CHECKING, Any

from .._locking import FileLock
from .._log import get_logger

if TYPE_CHECKING:  # type-only: no runtime data -> core import edge
    from ..core.corpus import Corpus

_LOG = get_logger("data")


class DataNotAvailableError(RuntimeError):
    """Raised when a non-bundled dataset has not been fetched (or can't be)."""


def _bundled_bytes(*parts: str) -> bytes:
    return files("aegean.data").joinpath("bundled", *parts).read_bytes()


def load_bundled_json(*parts: str) -> Any:
    """Load a JSON file shipped inside the wheel, e.g.
    ``load_bundled_json("lineara", "signs.json")``."""
    return json.loads(_bundled_bytes(*parts).decode("utf-8"))


# Comfortably above the largest real index (the LSJ index is ~60 MB uncompressed) and far
# below what would OOM: a decompression bomb inflates to many GB.
_MAX_GZIP_JSON_BYTES = 512 * 1024 * 1024


def _read_gzip_capped(path: str | pathlib.Path, max_bytes: int) -> bytes:
    """gzip-decompress ``path`` to bytes, refusing a stream that inflates past ``max_bytes``.

    The capped-chunk read shared by `load_gzip_json` and `fetch_text`. A fetched asset is
    sha256-pinned, but a ``PYAEGEAN_<NAME>_URL`` mirror override disables that check, so a
    swapped mirror could serve a tiny gzip that inflates to gigabytes and exhausts memory.
    Read in chunks and stop with a clear error past ``max_bytes`` instead of loading the
    whole stream blindly."""
    import gzip

    buf = bytearray()
    with gzip.open(path, "rb") as f:
        while True:
            chunk = f.read(1 << 20)
            if not chunk:
                break
            buf += chunk
            if len(buf) > max_bytes:
                raise DataNotAvailableError(
                    f"{path} decompresses to more than {max_bytes} bytes; refusing to load it "
                    "(a possible decompression bomb from an unverified mirror)"
                )
    return bytes(buf)


def load_gzip_json(path: str | pathlib.Path, *, max_bytes: int = _MAX_GZIP_JSON_BYTES) -> Any:
    """gzip-decompress and parse a fetched ``.json.gz`` index, capping the decompressed size.

    A prebuilt index is sha256-pinned when fetched from the project release, but a
    ``PYAEGEAN_<NAME>_URL`` override disables that check, so a swapped mirror could serve a
    tiny gzip that inflates to gigabytes and exhausts memory. Decompress in chunks and stop
    with a clear error past ``max_bytes`` instead of loading the whole stream blindly."""
    return json.loads(_read_gzip_capped(path, max_bytes))


def cache_dir() -> pathlib.Path:
    """Where fetched datasets are stored (override with ``PYAEGEAN_CACHE``).

    A permanent local store, not an evicting cache: entries stay until
    explicitly removed (``aegean data remove``, or deleting this directory)."""
    base = (
        os.environ.get("PYAEGEAN_CACHE")
        or os.environ.get("XDG_CACHE_HOME")
        or os.path.join(os.path.expanduser("~"), ".cache")
    )
    p = pathlib.Path(base) / "pyaegean"
    p.mkdir(parents=True, exist_ok=True)
    return p


@dataclass(frozen=True, slots=True)
class DataSpec:
    name: str
    url: str
    license: str
    sha256: str = ""
    note: str = ""
    extract: bool = False  # when True, the download is a tar archive to unpack
    # The cache-relative name(s) a present copy of this dataset actually occupies
    # on disk. Empty means the default: one entry at ``cache_dir()/name`` (a file,
    # or a directory for ``extract`` datasets). Some datasets land elsewhere: the
    # prebuilt lexicon indexes are fetched then written under their built-index
    # filename (``lsj-perseus-index.json.gz``, not ``lsj-index``), and the
    # ``agdt-derived`` bundle's members are copied out to their own filenames
    # (``agdt-postagger.json.gz`` etc.). The fold assets fetched via ``fetch_text``
    # keep the raw ``.gz`` at ``cache_dir()/name`` AND materialize a decompressed file
    # (+ a ``.sha256`` stamp) into a subdir, so they list the raw name FIRST and then
    # the materialized artifacts (a ``/``-joined cache-relative path). Listing every
    # real name here is what lets ``aegean data list`` / ``aegean doctor`` see the full
    # footprint and ``aegean data remove`` reclaim it, not orphan the materialization.
    on_disk: tuple[str, ...] = ()


# Remote datasets, all fetched to the user cache on demand — never bundled in the
# Apache-2.0 wheel. Two hosting patterns:
#   * upstream-fetched: pulled straight from where the rights-holder publishes it
#     (the Linear A facsimile imagery comes from the ryanpavlicek/linearaworkbench
#     release; the images remain © École Française d'Athènes plus other
#     rightsholders, unaffected by fetching);
#   * project-hosted: datasets/artifacts this project derived or decoded under the
#     source license and republishes as clearly-labeled pyaegean release assets —
#     the DAMOS and SigLA corpora (CC BY-NC-SA 4.0; the NC+SA obligations pass to
#     the user), the NT and Greek epigraphy/papyri corpora (I.Sicily, IIP, IOSPE,
#     IGCyr, EDH, DDbDP), and the prebuilt LSJ index / AGDT-derived models (CC BY-SA).
# Every URL + sha256 is pinned below; each PYAEGEAN_<NAME>_URL env var overrides a
# source with your own licensed copy.
_REMOTE: dict[str, DataSpec] = {
    "lineara-images": DataSpec(
        name="lineara-images",
        url=(
            "https://github.com/ryanpavlicek/linearaworkbench/releases/download/"
            "lineara-images-v1/lineara-images.tar.gz"
        ),
        sha256="1afddcd0fc8ce4f3058e8f84d5589e7fb34f56ea615bf0c228d1b2c92722e396",
        license="© École Française d'Athènes and other rightsholders — academic reference only",
        note="3,368 facsimile/photo files (~116 MB tar.gz, ~119 MB unpacked); fetched from the linearaworkbench release.",
        extract=True,
    ),
    # The opt-in [neural] Greek lemmatizer model: GreTa seq2seq exported to ONNX, plus its
    # tokenizer and a gold form->lemma lookup, packed as a tar.gz. Derived from CC BY-SA
    # corpora, so the *model* is CC BY-SA; it is fetched (never bundled), so the wheel stays
    # Apache-2.0. URL is pinned to the grc-lemma-neural-v1 release asset; set
    # PYAEGEAN_GRC_LEMMA_NEURAL_URL to fetch from your own mirror instead.
    "grc-lemma-neural": DataSpec(
        name="grc-lemma-neural",
        url=(
            "https://github.com/ryanpavlicek/pyaegean/releases/download/"
            "grc-lemma-neural-v1/grc-lemma-neural.tar.gz"
        ),
        sha256="38126872e7a5be6389054062d4789ce5b6fc7e84327b07c2b93649a6f0f1a228",
        license="CC BY-SA 4.0 — derived from AGDT (CC BY-SA 3.0), Pedalion (CC BY-SA 4.0), Gorman (CC BY-SA 4.0)",
        note="GreTa seq2seq lemmatizer (int8 ONNX encoder/decoder + tokenizer + gold lookup), ~232 MB tar.gz; the [neural] extra.",
        extract=True,
    ),
    # The opt-in [neural] joint Greek pipeline: one GreBerta-based model for UPOS, the
    # 9-position AGDT morphology (rendered as UD FEATS), UD dependency trees (biaffine +
    # MST), and lemmas (edit-script head + train-only lookup). Trained leakage-clean on
    # AGDT + Gorman + Pedalion; the best published result on every UD Ancient Greek (Perseus) test metric
    # (docs/benchmarks.md). URL is pinned to the grc-joint-v3 release asset; set
    # PYAEGEAN_GRC_JOINT_URL to fetch from your own mirror instead.
    "grc-joint": DataSpec(
        name="grc-joint",
        url=(
            "https://github.com/ryanpavlicek/pyaegean/releases/download/"
            "grc-joint-v3/grc-joint.tar.gz"
        ),
        sha256="f646d34a08dbf612abbe076c27188f077c2289da0b7bbbc7116bfe807112b06e",
        license="CC BY-SA 4.0 — derived from AGDT (CC BY-SA 3.0), Gorman (CC BY-SA 4.0), Pedalion (CC BY-SA 4.0)",
        note="joint tagger-parser-lemmatizer (int8-weight + fp16 ONNX + tokenizer + label maps + lemma scripts/lookup), ~173 MB tar.gz; the [neural] extra (onnxruntime>=1.23).",
        extract=True,
    ),
    # Prebuilt Perseus LSJ lemma index (built by greek.lexicon.build_index from
    # PerseusDL/lexica). Hosting the ~15 MB built index lets use_lsj() skip the
    # ~270 MB TEI download + local build. CC BY-SA 4.0 (Perseus); never bundled.
    "lsj-index": DataSpec(
        name="lsj-index",
        url=(
            "https://github.com/ryanpavlicek/pyaegean/releases/download/"
            "lsj-index-v1/lsj-perseus-index.json.gz"
        ),
        sha256="12b7fdb741e98d63fd29c9a0e2a1a56c774bfac2f6c81139f113ffb96aaebee5",
        license="CC BY-SA 4.0 (Perseus Digital Library); derived index, fetched, never bundled",
        note="prebuilt LSJ lemma→entry index (~15 MB); use_lsj() prefers it over the 270 MB build.",
        extract=False,
        # use_lsj() writes the fetched index under greek.lexicon's built-index name.
        on_disk=("lsj-perseus-index.json.gz",),
    ),
    "middle-liddell-index": DataSpec(
        name="middle-liddell-index",
        url=(
            "https://github.com/ryanpavlicek/pyaegean/releases/download/"
            "grc-lexica-v1/middle-liddell-index.json.gz"
        ),
        sha256="8c4481f5b4252ac1cfdc4d11087e52be35408a720cfe72ae9815adecc74cde4f",
        license="public domain (1889); Perseus digitization CC BY-SA, Scaife data MIT; derived index, fetched, never bundled",
        note="prebuilt Middle Liddell lemma→entry index (~2.3 MB); use_lexicon('middle-liddell') prefers it.",
        extract=False,
        on_disk=("middle-liddell-index.json.gz",),
    ),
    "cunliffe-index": DataSpec(
        name="cunliffe-index",
        url=(
            "https://github.com/ryanpavlicek/pyaegean/releases/download/"
            "grc-lexica-v1/cunliffe-index.json.gz"
        ),
        sha256="3e3f0d9d9bfd89e609090aafff833041feb0e4421485e1fada14e1f338974608",
        license="public domain (1924); Scaife structured data MIT; derived index, fetched, never bundled",
        note="prebuilt Cunliffe (Homeric) lemma→entry index (~1.3 MB); use_lexicon('cunliffe') prefers it.",
        extract=False,
        on_disk=("cunliffe-index.json.gz",),
    ),
    "papygreek-fold": DataSpec(
        name="papygreek-fold",
        url=(
            "https://github.com/ryanpavlicek/pyaegean/releases/download/"
            "papygreek-fold-v3/papygreek-fold.conllu.gz"
        ),
        sha256="de6874740b4e985c94b2e1677a2970f85a821011b1e6b8a01915410b4c6aa030",
        license="CC BY-SA 4.0 (PapyGreek Treebanks); derived UD fold, fetched, never bundled",
        note="documentary-Koine dependency eval fold (1,696 sentences / 24,105 tokens) converted "
             "from the PapyGreek Treebanks; AGDT->UD CoNLL-U, leakage-clean vs grc-joint training. "
             "Evaluation only.",
        extract=False,
        # fetch() stores the raw .gz at cache_dir()/papygreek-fold; papygreek_path()
        # then materializes the decompressed CoNLL-U (+ a .sha256 stamp) into the
        # papygreek-grc/ subdir via fetch_text. Listing all three (the raw name MUST
        # stay first so list/remove still see the archive) makes ``data list`` count
        # the materialized bytes and ``data remove`` reclaim them, not orphan them.
        on_disk=(
            "papygreek-fold",
            "papygreek-grc/papygreek-test.conllu",
            "papygreek-grc/papygreek-test.conllu.sha256",
        ),
    ),
    "papygreek-fold-orig": DataSpec(
        name="papygreek-fold-orig",
        url=(
            "https://github.com/ryanpavlicek/pyaegean/releases/download/"
            "papygreek-fold-orig-v2/papygreek-fold-orig.conllu.gz"
        ),
        sha256="d920a0cd65ee7cf278f87f5a419e60f43d7680ef8d1b0564f94987fbb93afad2",
        license="CC BY-SA 4.0 (PapyGreek Treebanks); derived UD fold, fetched, never bundled",
        note="the ORIG diplomatic surface layer of papygreek-fold (same 1,696 sentences and gold; "
             "FORM = raw diplomatic orthography; 1,637 forms differ). Evaluation only.",
        extract=False,
        # raw .gz + the materialized CoNLL-U (+ stamp); see the papygreek-fold note above.
        on_disk=(
            "papygreek-fold-orig",
            "papygreek-grc/papygreek-test-orig.conllu",
            "papygreek-grc/papygreek-test-orig.conllu.sha256",
        ),
    ),
    "verse-fold": DataSpec(
        name="verse-fold",
        url=(
            "https://github.com/ryanpavlicek/pyaegean/releases/download/"
            "verse-fold-v2/verse-fold.conllu.gz"
        ),
        sha256="22c860f8504706e63d4421be9c504c003e9186928949e63e9ec26f84c0af6e28",
        license="CC BY-SA 4.0 (unesp-trees, Perseids/Arethusa, UNESP); derived UD fold, fetched, never bundled",
        note="Ancient Greek verse dependency eval fold, tragedy-only (36 sentences / 735 tokens: "
             "Euripides Bacchae 1-169); AGDT->UD, leakage-clean. Small-sample genre-conditioned "
             "datapoint, never a headline number. Evaluation only.",
        extract=False,
        # raw .gz + the materialized CoNLL-U (+ stamp); see the papygreek-fold note above.
        on_disk=(
            "verse-fold",
            "verse-grc/verse-test.conllu",
            "verse-grc/verse-test.conllu.sha256",
        ),
    ),
    "papygreek-dev-tagging": DataSpec(
        name="papygreek-dev-tagging",
        url=(
            "https://github.com/ryanpavlicek/pyaegean/releases/download/"
            "papygreek-dev-v2/papygreek-dev-tagging.conllu.gz"
        ),
        sha256="81ece456f70e13a1ab3c2d95d94d3e7e466bc5f02971fb8c1715d2d65e2c96c4",
        license="CC BY-SA 4.0 (PapyGreek Treebanks); derived DEV fold, fetched, never bundled",
        note="documentary-Koine DEV tagging track (327 sentences / 6,389 tokens); "
             "document-disjoint from the papygreek-fold test set; UPOS/XPOS/UFeats/lemma. "
             "Experiment data only, never a published number.",
        extract=False,
        # raw .gz + the materialized CoNLL-U (+ stamp); see the papygreek-fold note above.
        on_disk=(
            "papygreek-dev-tagging",
            "papygreek-grc/papygreek-dev-tagging.conllu",
            "papygreek-grc/papygreek-dev-tagging.conllu.sha256",
        ),
    ),
    "papygreek-dev-parse": DataSpec(
        name="papygreek-dev-parse",
        url=(
            "https://github.com/ryanpavlicek/pyaegean/releases/download/"
            "papygreek-dev-v2/papygreek-dev-parse.conllu.gz"
        ),
        sha256="967d519526353eb0d709ab32102e057d6a6463b415025396847770f70faebec1",
        license="CC BY-SA 4.0 (PapyGreek Treebanks); derived DEV fold, fetched, never bundled",
        note="documentary-Koine DEV parse track (126 sentences / 1,285 tokens, directional "
             "only); document-disjoint from the papygreek-fold test set; UAS/LAS. "
             "Experiment data only, never a published number.",
        extract=False,
        # raw .gz + the materialized CoNLL-U (+ stamp); see the papygreek-fold note above.
        on_disk=(
            "papygreek-dev-parse",
            "papygreek-grc/papygreek-dev-parse.conllu",
            "papygreek-grc/papygreek-dev-parse.conllu.sha256",
        ),
    ),
    "dbbe-lingann-fold": DataSpec(
        name="dbbe-lingann-fold",
        url=(
            "https://github.com/ryanpavlicek/pyaegean/releases/download/"
            "dbbe-lingann-fold-v2/dbbe-lingann-fold.conllu.gz"
        ),
        sha256="14b5496d3346cdd4df803896ee480ac1e7d05074b9ea52df7be2994e25e60008",
        license="CC BY 4.0 (DBBE gold standard, Swaelens/De Vos/Lefever, Ghent); derived fold, "
                "fetched, never bundled",
        note="Byzantine book-epigram tagging fold (825 sentences / 9,191 tokens, gold POS+lemma, "
             "no trees; scribal orthography). Evaluation only.",
        extract=False,
        # raw .gz + the materialized CoNLL-U (+ stamp); see the papygreek-fold note above.
        on_disk=(
            "dbbe-lingann-fold",
            "dbbe-grc/dbbe-lingann-test.conllu",
            "dbbe-grc/dbbe-lingann-test.conllu.sha256",
        ),
    ),
    "autenrieth-index": DataSpec(
        name="autenrieth-index",
        url=(
            "https://github.com/ryanpavlicek/pyaegean/releases/download/"
            "autenrieth-index-v2/autenrieth-index.json.gz"
        ),
        sha256="2982e716eea8c69317437c9f0887aabf661e24c0ed96c2025d7433e9084a42c6",
        license="public domain (1891); Perseus digitization CC BY-SA; derived index, fetched, never bundled",
        note="prebuilt Autenrieth (Homeric) lemma->entry index (~0.6 MB); use_lexicon('autenrieth') prefers it.",
        extract=False,
        on_disk=("autenrieth-index.json.gz",),
    ),
    "abbott-smith-index": DataSpec(
        name="abbott-smith-index",
        url=(
            "https://github.com/ryanpavlicek/pyaegean/releases/download/"
            "grc-lexica-v1/abbott-smith-index.json.gz"
        ),
        sha256="abfa896ecb196e7cae840bc8fd1f549271849dc36e6d140df236ffeec9297507",
        license="public domain (1922); derived index, fetched, never bundled",
        note="prebuilt Abbott-Smith (NT) lemma→entry index (~130 KB); use_lexicon('abbott-smith') prefers it.",
        extract=False,
        on_disk=("abbott-smith-index.json.gz",),
    ),
    # The UniMorph Ancient Greek paradigm index: form -> [{lemma, pos, case, number, gender?}]
    # (AGDT record shape), harvested from github.com/unimorph/grc by
    # scripts/build_paradigm_table.py. Supplies the irregular / third-declension / heteroclite
    # nominal paradigms the offline seed+rule lemmatizer cannot reach (γυναικός -> γυνή,
    # πατράσι -> πατήρ, ὕδατος -> ὕδωρ); opt-in via greek.use_paradigms(), fetched on demand,
    # never bundled (ShareAlike + wheel size). CC BY-SA 3.0 (UniMorph / Wikipedia).
    # Reproducible build from unimorph/grc commit 7f4a58df733726c75c1355dd3a038e950d5e308f
    # plus the AGDT treebank lexicon (Perseus commit pinned in greek/treebank.py) for the
    # attested-gender cross-check; a rebuild from the same pins yields an identical sha.
    "grc-paradigms": DataSpec(
        name="grc-paradigms",
        url=(
            "https://github.com/ryanpavlicek/pyaegean/releases/download/"
            "grc-paradigms-v2/grc-paradigms.json.gz"
        ),
        sha256="be68b4ec83509864c2533da2aedb8faf8a1b22b985c46c49d7379ef943a7fd27",
        license="CC-BY-SA-3.0 (UniMorph / Wikipedia); derived paradigm index, fetched, never bundled",
        note="prebuilt UniMorph Ancient Greek paradigm index (~234 KB gzip); use_paradigms() "
             "fetches it for offline irregular/third-declension lemma+feature coverage.",
        extract=False,
        on_disk=("grc-paradigms.json.gz",),
    ),
    # Prebuilt AGDT-derived artifacts: the treebank lexicon + the trained POS
    # tagger / lemmatizer / arc-eager parser. Hosting them lets the use_treebank/
    # use_tagger/use_lemmatizer/use_parser backends skip the 75 MB AGDT download
    # and minutes of training. CC BY-SA 3.0-derived (Perseus AGDT); never bundled.
    "agdt-derived": DataSpec(
        name="agdt-derived",
        url=(
            "https://github.com/ryanpavlicek/pyaegean/releases/download/"
            "agdt-derived-v1/agdt-derived.tar.gz"
        ),
        sha256="fb559b77a15146a51e34df5e9e2e5952347af086253282a25e8efcf65f8ba363",
        license="CC BY-SA 3.0 (derived from the Perseus AGDT); fetched, never bundled",
        note="prebuilt AGDT lexicon + tagger/lemmatizer/parser models; the opt-in "
             "Greek backends prefer these over downloading the AGDT and training.",
        extract=True,
        # fetch() unpacks the bundle to cache_dir()/agdt-derived, but the
        # use_treebank/use_tagger/use_lemmatizer/use_parser backends copy each
        # member out to its own working filename; any of these means the bundle
        # is present. (agdt-greek/ is the raw-AGDT build subdir, kept separate.)
        on_disk=(
            "agdt-derived",
            "agdt-greek-lexicon.json",
            "agdt-postagger.json.gz",
            "agdt-lemmatizer.json.gz",
            "agdt-parser-model.json.gz",
        ),
    ),
    # The SigLA-derived Linear A dataset (Salgarella & Castellan, sigla.phis.me):
    # decoded from the published web-app payload into the JSON the SigLA paper
    # describes (scripts/build_sigla_corpus.py). CC BY-NC-SA 4.0 as published by
    # SigLA — NonCommercial data is fetched on demand and never bundled in the
    # Apache-2.0 wheel; attribution/citation live in the file's _meta and NOTICE.
    "sigla-corpus": DataSpec(
        name="sigla-corpus",
        url=(
            "https://github.com/ryanpavlicek/pyaegean/releases/download/"
            "sigla-corpus-v4/sigla-corpus.json"
        ),
        sha256="9a5e4783146144fc5ac54c5dc2b372b39cc0e0ea40ca15207243f8c539f03dd8",
        license="CC BY-NC-SA 4.0 (SigLA — Salgarella & Castellan; NonCommercial, never bundled)",
        note="SigLA-derived Linear A dataset v4: 802 documents with SigLA's own word "
             "division (1,401 words), homophone subscripts (RA₂/PU₂/TA₂), and "
             "commodity ideograms (~1.3 MB JSON). Drawings stay at sigla.phis.me.",
        extract=False,
    ),
    # The DAMOS Linear B corpus (Aurora, damos.hf.uio.no): transliterations + core
    # metadata for ~5,900 Mycenaean tablets, decoded from the DAMOS public API into
    # compact JSON (scripts/build_damos_corpus.py). CC BY-NC-SA 4.0 as published by
    # DAMOS — NonCommercial data fetched on demand, never bundled in the Apache-2.0
    # wheel; attribution/citation in the file's _meta and NOTICE.
    "damos-corpus": DataSpec(
        name="damos-corpus",
        url=(
            "https://github.com/ryanpavlicek/pyaegean/releases/download/"
            "damos-corpus-v2/damos-corpus.json"
        ),
        sha256="eab9ccdfc4324b62f015bccd5e3f917f256cab8c058840842127eadecfbca2d2",
        license="CC BY-NC-SA 4.0 (DAMOS — F. Aurora; NonCommercial, never bundled)",
        note="DAMOS-derived Linear B corpus v2: ~5,900 tablets (Knossos, Pylos, Thebes, …) "
             "with transliterations, site/chronology, scribal hands, find context, and "
             "object class. Loadable via aegean.load('damos').",
        extract=False,
    ),
    # The I.Sicily Greek inscriptions (ISicily/ISicily, CC BY 4.0): the ~2,855 primary-Greek
    # texts of the ~5,120-inscription EpiDoc corpus, their Greek reading + find-place / date /
    # coordinates extracted to compact JSON (scripts/build_isicily_corpus.py). CC BY permits
    # redistribution with attribution, so — unlike DAMOS/SigLA — this is project-hosted; it is
    # still fetched on demand, never bundled. Adds epigraphic Greek to the literary/NT holdings.
    "isicily-corpus": DataSpec(
        name="isicily-corpus",
        url=(
            "https://github.com/ryanpavlicek/pyaegean/releases/download/"
            "isicily-corpus-v3/isicily-corpus.json"
        ),
        sha256="1aa0abb3a7f06c415599932f6b1de844aaab6f0b78ff12f79ab4842f3636063c",
        license="CC-BY-4.0 (I.Sicily — J. Prag et al., University of Oxford; attribution required)",
        note="I.Sicily Greek inscriptions: 2,855 primary-Greek texts from ancient Sicily with "
             "find-place, date, and coordinates, from the CC BY EpiDoc corpus. "
             "Loadable via aegean.load('isicily').",
        extract=False,
    ),
    # The IIP Greek inscriptions (Brown-University-Library/iip-texts, CC BY-NC 4.0): the ~2,113
    # primary-Greek texts of the multilingual Inscriptions of Israel/Palestine corpus, their Greek
    # reading + find-place / coordinates extracted to compact JSON (scripts/build_iip_corpus.py).
    # CC BY-NC permits redistribution as a separate self-licensed asset (NonCommercial passes to the
    # user); fetched on demand, never bundled. Also mirrored here so pyaegean survives upstream loss.
    "iip-corpus": DataSpec(
        name="iip-corpus",
        url=(
            "https://github.com/ryanpavlicek/pyaegean/releases/download/"
            "iip-corpus-v3/iip-corpus.json"
        ),
        sha256="d9b83daa0fb675c6cb45d9fe4ca66c10af96eef40976bb0b8816628bdc9692c7",
        license="CC-BY-NC-4.0 (IIP — M. L. Satlow, Brown University; NonCommercial, attribution)",
        note="IIP Greek inscriptions: 2,113 primary-Greek texts from Israel/Palestine with "
             "find-place and coordinates, from the CC BY-NC EpiDoc corpus. "
             "Loadable via aegean.load('iip').",
        extract=False,
    ),
    # The IOSPE Greek inscriptions (kingsdigitallab/iospe; repo code MIT, data CC BY): the ~1,194
    # Greek inscriptions of the Northern Black Sea (Tyras, Olbia, Chersonesos, Byzantine), their
    # Greek reading + find-place / date extracted to compact JSON (scripts/build_iospe_corpus.py).
    # Attributed to IOSPE / King's College London; fetched on demand, never bundled; mirrored here
    # so pyaegean survives upstream loss (the live site is behind anti-scraping).
    "iospe-corpus": DataSpec(
        name="iospe-corpus",
        url=(
            "https://github.com/ryanpavlicek/pyaegean/releases/download/"
            "iospe-corpus-v3/iospe-corpus.json"
        ),
        sha256="e89ef85a946eb5b3eceae3ad805c2d1a7ab621f5be53463fd1398fb8037d6971",
        license="CC-BY-4.0 (IOSPE III, King's College London; attribution; repo code is MIT)",
        note="IOSPE Greek inscriptions: 1,194 Greek texts of the Northern Black Sea with "
             "find-place and date, from the CC BY EpiDoc corpus. Loadable via aegean.load('iospe').",
        extract=False,
    ),
    # The IGCyr/GVCyr Greek inscriptions of Cyrenaica (AMS Acta 7796, CC BY-NC-SA 4.0): the 997
    # Greek inscriptions (incl. archaic Doric + the GVCyr verse subset), their Greek reading + title
    # / find-place / date extracted to compact JSON (scripts/build_igcyr_corpus.py). CC BY-NC-SA
    # permits redistribution as a self-licensed asset (NonCommercial + ShareAlike pass through);
    # fetched on demand, never bundled; mirrored so pyaegean survives upstream loss.
    "igcyr-corpus": DataSpec(
        name="igcyr-corpus",
        url=(
            "https://github.com/ryanpavlicek/pyaegean/releases/download/"
            "igcyr-corpus-v3/igcyr-corpus.json"
        ),
        sha256="de1950e2543102bfe8bfacd09cdd3c1803328dc7981795066107392fc4165f75",
        license="CC-BY-NC-SA-4.0 (IGCyr2/GVCyr2, C. Dobias-Lalou et al., Univ. di Bologna, 2024)",
        note="IGCyr/GVCyr Greek inscriptions of Cyrenaica: 997 texts (Doric + verse) with title, "
             "find-place, date, from the CC BY-NC-SA EpiDoc corpus. Loadable via aegean.load('igcyr').",
        extract=False,
    ),
    "edh-corpus": DataSpec(
        name="edh-corpus",
        url=(
            "https://github.com/ryanpavlicek/pyaegean/releases/download/"
            "edh-corpus-v3/edh-corpus.json"
        ),
        sha256="bcb5e4b5123cec47c725a116c291556c220252fe9cbee42a1b3f2d3715000965",
        license="CC-BY-SA-4.0 (Epigraphic Database Heidelberg / Heidelberg Academy of Sciences and Humanities)",
        note="EDH Ancient-Greek inscriptions: the 1,286 pure-Greek texts (Imperial Koine, largely "
             "onomastic) of the frozen CC BY-SA EDH dump, with ancient place, date, find-place, and "
             "Trismegistos id. Loadable via aegean.load('edh').",
        extract=False,
    ),
    "ddbdp-corpus": DataSpec(
        name="ddbdp-corpus",
        url=(
            "https://github.com/ryanpavlicek/pyaegean/releases/download/"
            "ddbdp-corpus-v2/ddbdp-corpus.tar.gz"
        ),
        sha256="a9c57bcefcf978cf9f832bfef25a1a4296b933f36215619b369887d98020b54a",
        license="CC-BY-3.0 (DDbDP / Duke Collaboratory for Classics Computing, papyri.info)",
        note="DDbDP Greek documentary papyri: 57,331 texts / ~4.4M tokens (~219 MB tar.gz, ~757 MB "
             "unpacked) as a SQLite database with full-text search, from the CC BY papyri.info corpus. "
             "Every token carries editorial reading status. aegean.load('ddbdp') materialises it "
             "(heavy); aegean.db.search/stream the memory-friendly path.",
        extract=True,
    ),
    # The DDbDP document-URI map: file-stem -> ddb-hybrid, harvested from papyri.info's own
    # idp.data by scripts/build_ddbdp_uri_map.py. Lets aegean.io.to_rdf mint papyri.info
    # document URIs (http://papyri.info/ddbdp/<hybrid>) for the ddbdp corpus without shipping
    # the ~70k-entry map in the wheel; fetched on demand, never bundled. CC BY 3.0 (papyri.info).
    # The RDF export falls back to Trismegistos URIs (with one warning) when this is absent, so
    # it stays offline-capable. PLACEHOLDER — integrator: after hosting the built
    # ddbdp-uris.json.gz (~337 KB gzip; built sha256
    # c767f351168c44f287edc22e0bb7cd22b190b0a019c73a78b3fe2b90e97d356c) as a release asset,
    "ddbdp-uris": DataSpec(
        name="ddbdp-uris",
        url="https://github.com/ryanpavlicek/pyaegean/releases/download/ddbdp-uris-v1/ddbdp-uris.json.gz",
        sha256="c767f351168c44f287edc22e0bb7cd22b190b0a019c73a78b3fe2b90e97d356c",
        license="CC-BY-3.0 (DDbDP / papyri.info); derived stem->hybrid map, fetched, never bundled",
        note="DDbDP document-URI map: file-stem -> ddb-hybrid entries (~337 KB gzip) harvested "
             "from papyri.info idp.data; lets to_rdf mint papyri.info document URIs.",
        extract=False,
        on_disk=("ddbdp-uris.json.gz",),
    ),
    # The Greek New Testament (Nestle 1904) with per-token lemma / Robinson morph /
    # Strong's, built from biblicalhumanities/Nestle1904 (scripts/build_nt_corpus.py).
    # The morphology, lemmas, and Strong's numbers are CC0 and the base text is public
    # domain, so — unlike DAMOS/SigLA — this asset MAY be redistributed; the full 27 books
    # fetch on demand while a sample (John 1 + Philemon) is bundled offline (load_nt).
    # Set PYAEGEAN_NT_CORPUS_URL to a local build to override the hosted asset, or use
    # the bundled sample offline.
    "nt-corpus": DataSpec(
        name="nt-corpus",
        url=(
            "https://github.com/ryanpavlicek/pyaegean/releases/download/"
            "nt-corpus-v1/nt-corpus.json"
        ),
        sha256="e7aa5dcad729eb91f77018abbef71304d13e200f29dabe1260b79fa37b153949",
        license="CC0-1.0 (morphology, lemmas, Strong's); base Greek text public domain",
        note="Greek New Testament (Nestle 1904): 260 chapters / ~137,800 tokens with gold "
             "lemma, Robinson morph, Strong's, and reconciled UD UPOS. Loadable via "
             "aegean.load('nt') / greek.load_nt(book, ref=...).",
        extract=False,
    ),
    # The prebuilt Linear A Research Workbench static web app (the browser UI), hosted as a
    # release asset on the workbench repo and served locally by `aegean workbench`. The app
    # build is Apache-2.0; the Linear A corpus data baked into it is GORILA-derived (via
    # lineara.xyz). Fetched + extracted to the cache on demand, never bundled.
    "workbench-app": DataSpec(
        name="workbench-app",
        url=(
            "https://github.com/ryanpavlicek/linearaworkbench/releases/download/"
            "workbench-app-v1.6.1/workbench-app.tar.gz"
        ),
        sha256="19a27feb47a9b49a4095c571e7f1e01c68f011a119691712438273d289c19870",
        license="Apache-2.0 (Linear A Research Workbench build); embedded Linear A data is GORILA-derived",
        note="prebuilt linearaworkbench static web app (~3 MB tar.gz); served locally by `aegean workbench`.",
        extract=True,
    ),
    # A slot for your OWN licensed Linear B export (a LiBER selection, a DAMOS EpiDoc download),
    # loaded via PYAEGEAN_LINEARB_CORPUS_URL or `aegean import --epidoc`. For a ready corpus use
    # DAMOS directly — `aegean data fetch damos` / aegean.load("damos"). LiBER (liber.cnr.it) has
    # no public download or API and is rights-restricted, so it is browse-only, never fetched.
    "linearb-corpus": DataSpec(
        name="linearb-corpus",
        url="",
        sha256="",
        license="bring-your-own; DAMOS is CC BY-NC-SA 4.0 (fetch it directly), LiBER all-rights-reserved (browse-only)",
        note="Your own licensed Linear B export. For a ready corpus fetch DAMOS ('aegean data "
             "fetch damos'); LiBER is browse-only at liber.cnr.it. No default source for this slot.",
        extract=False,
    ),
}


@dataclass(frozen=True, slots=True)
class HistoricalPin:
    """A superseded release pin for a dataset that the project still hosts.

    When an asset is rebuilt and re-hosted under a new tag (the 0.29.0 epigraphy
    re-host: ``isicily-corpus-v2`` etc.), the previous release is kept on GitHub so
    an earlier analysis can be reproduced byte-for-byte. Each `HistoricalPin` records
    that kept release: its ``version`` (the release tag suffix, ``"v1"``), the exact
    ``url`` and ``sha256`` the pin was published with, and ``superseded`` (the version
    that replaced it). ``extract`` mirrors the dataset's archive kind (a tar to unpack)
    for that historical asset. `fetch(name, version=...)` resolves these."""

    version: str
    url: str
    sha256: str
    superseded: str = ""
    extract: bool = False


# Kept prior release pins, keyed by dataset name. Populated ONLY from releases that are
# still hosted, with the REAL url + sha256 the pin carried at publish time (recovered from
# the git history of _REMOTE — never reconstructed). The six 0.29.0-superseded epigraphy
# assets were re-hosted as ``-v2`` (adding the P5 per-token ReadingStatus / edition_fidelity);
# their ``-v1`` releases remain on GitHub, so a paper pinned to the pre-0.29.0 data still
# resolves. `fetch(name, version="v1")` fetches one to a version-suffixed cache entry, leaving
# the default (current) path untouched. Set PYAEGEAN_<NAME>_<VERSION>_URL to fetch a historical
# pin from your own mirror (e.g. PYAEGEAN_ISICILY_CORPUS_V1_URL).
_REMOTE_HISTORY: dict[str, list[HistoricalPin]] = {
    "isicily-corpus": [
        HistoricalPin(
            version="v2",
            url=(
                "https://github.com/ryanpavlicek/pyaegean/releases/download/"
                "isicily-corpus-v2/isicily-corpus.json"
            ),
            sha256="38655e36fe44058780cae30b4b4594e382a20e9a4a73d26229e4ed8c9b6570c2",
            superseded="v3",
        ),
        HistoricalPin(
            version="v1",
            url=(
                "https://github.com/ryanpavlicek/pyaegean/releases/download/"
                "isicily-corpus-v1/isicily-corpus.json"
            ),
            sha256="c0242f4b52df05ae7295b17a0c786dd7b474c4ef47520be88795c8117aa8d4d1",
            superseded="v2",
        ),
    ],
    "iip-corpus": [
        HistoricalPin(
            version="v2",
            url=(
                "https://github.com/ryanpavlicek/pyaegean/releases/download/"
                "iip-corpus-v2/iip-corpus.json"
            ),
            sha256="1e3bb6c3da0a98c5dc8812c1cd191807e7ab8384a808606abd8c2ef4fa6eab88",
            superseded="v3",
        ),
        HistoricalPin(
            version="v1",
            url=(
                "https://github.com/ryanpavlicek/pyaegean/releases/download/"
                "iip-corpus-v1/iip-corpus.json"
            ),
            sha256="2fec633b5e6ea38621bc8e0b3c62f959317e4cdd84af5c348b650a479a02dc74",
            superseded="v2",
        ),
    ],
    "iospe-corpus": [
        HistoricalPin(
            version="v2",
            url=(
                "https://github.com/ryanpavlicek/pyaegean/releases/download/"
                "iospe-corpus-v2/iospe-corpus.json"
            ),
            sha256="70e729ac5afe0bf1df339bc10f4ffe161ba6aa253a8bdd175f2a6e8c8a3df375",
            superseded="v3",
        ),
        HistoricalPin(
            version="v1",
            url=(
                "https://github.com/ryanpavlicek/pyaegean/releases/download/"
                "iospe-corpus-v1/iospe-corpus.json"
            ),
            sha256="bd2143d408d13f96d2e087e54c1508da6bfdb6a096fec6d82feeeb4523e33d7e",
            superseded="v2",
        ),
    ],
    "igcyr-corpus": [
        HistoricalPin(
            version="v2",
            url=(
                "https://github.com/ryanpavlicek/pyaegean/releases/download/"
                "igcyr-corpus-v2/igcyr-corpus.json"
            ),
            sha256="c5b9f48f5ccb8abf5b77b678bce1f5ae01de1b2befd481bd6155a8d1b3e5af8f",
            superseded="v3",
        ),
        HistoricalPin(
            version="v1",
            url=(
                "https://github.com/ryanpavlicek/pyaegean/releases/download/"
                "igcyr-corpus-v1/igcyr-corpus.json"
            ),
            sha256="673481ce3041ad268d26fb1d5490987b187ad86fb29af50ef7390f919f77e28b",
            superseded="v2",
        ),
    ],
    "edh-corpus": [
        HistoricalPin(
            version="v2",
            url=(
                "https://github.com/ryanpavlicek/pyaegean/releases/download/"
                "edh-corpus-v2/edh-corpus.json"
            ),
            sha256="1bb4f6170833555143ad816eb86a9affacbe888a5276657804182c7702ca24e2",
            superseded="v3",
        ),
        HistoricalPin(
            version="v1",
            url=(
                "https://github.com/ryanpavlicek/pyaegean/releases/download/"
                "edh-corpus-v1/edh-corpus.json"
            ),
            sha256="4828a9760fb64a397a510d3ac239a3df600ef23b7bd7d146c6ad911dc33f6541",
            superseded="v2",
        ),
    ],
    "sigla-corpus": [
        HistoricalPin(
            version="v3",
            url=(
                "https://github.com/ryanpavlicek/pyaegean/releases/download/"
                "sigla-corpus-v3/sigla-corpus.json"
            ),
            sha256="683fa0147f2b923a78f7c2c1da95cf42d8c05563f9ed53c5dfa8e520f4e38569",
            superseded="v4",
        ),
        HistoricalPin(
            version="v2",
            url=(
                "https://github.com/ryanpavlicek/pyaegean/releases/download/"
                "sigla-corpus-v2/sigla-corpus.json"
            ),
            sha256="c334a9431aa985afa9655268e018efc7513c2d3aea0541ca96afffe61e29b133",
            superseded="v3",
        ),
    ],
    "papygreek-fold": [
        HistoricalPin(
            version="v2",
            url=(
                "https://github.com/ryanpavlicek/pyaegean/releases/download/"
                "papygreek-fold-v2/papygreek-fold.conllu.gz"
            ),
            sha256="75304be2d12df23419e6486ddefb40ed7c70a1f9af49da9846cf08dbbf224dc1",
            superseded="v3",
        ),
        HistoricalPin(
            version="v1",
            url=(
                "https://github.com/ryanpavlicek/pyaegean/releases/download/"
                "papygreek-fold-v1/papygreek-fold.conllu.gz"
            ),
            sha256="29bc27b6717bcf3cc9abe37fde2fd927bfc567310aea2693f3a36de4fe79b0de",
            superseded="v2",
        ),
    ],
    "papygreek-fold-orig": [
        HistoricalPin(
            version="v1",
            url=(
                "https://github.com/ryanpavlicek/pyaegean/releases/download/"
                "papygreek-fold-orig-v1/papygreek-fold-orig.conllu.gz"
            ),
            sha256="5af592199bb14c211865cd9d9494cf015f9b667e30ae2d8ad59fb68dff758b85",
            superseded="v2",
        ),
    ],
    "verse-fold": [
        HistoricalPin(
            version="v1",
            url=(
                "https://github.com/ryanpavlicek/pyaegean/releases/download/"
                "verse-fold-v1/verse-fold.conllu.gz"
            ),
            sha256="6e91adbe5096556f7fe6686b35f30b363b115325d7ee2843e39d16c75fbdf8bc",
            superseded="v2",
        ),
    ],
    "papygreek-dev-tagging": [
        HistoricalPin(
            version="v1",
            url=(
                "https://github.com/ryanpavlicek/pyaegean/releases/download/"
                "papygreek-dev-v1/papygreek-dev-tagging.conllu.gz"
            ),
            sha256="f562021d4e57351b7f669a24148bf3c628fe024902a7614f331242ff4e05d7f7",
            superseded="v2",
        ),
    ],
    "papygreek-dev-parse": [
        HistoricalPin(
            version="v1",
            url=(
                "https://github.com/ryanpavlicek/pyaegean/releases/download/"
                "papygreek-dev-v1/papygreek-dev-parse.conllu.gz"
            ),
            sha256="8044f3bc414d157fad556b4ea42876f2f62613d6adefaa5c15a22630569b025b",
            superseded="v2",
        ),
    ],
    "dbbe-lingann-fold": [
        HistoricalPin(
            version="v1",
            url=(
                "https://github.com/ryanpavlicek/pyaegean/releases/download/"
                "dbbe-lingann-fold-v1/dbbe-lingann-fold.conllu.gz"
            ),
            sha256="d9953f739af27e2beaf37c7cce4b616aaaa6816f1cd02efe6054d8474a0e3253",
            superseded="v2",
        ),
    ],
    "autenrieth-index": [
        HistoricalPin(
            version="v1",
            url=(
                "https://github.com/ryanpavlicek/pyaegean/releases/download/"
                "autenrieth-index-v1/autenrieth-index.json.gz"
            ),
            sha256="9196574a8d9e5b9ad3731c1c9f7cda7061e6b33e03b7d6d12ecf12ad6c5275dc",
            superseded="v2",
        ),
    ],
    "grc-paradigms": [
        HistoricalPin(
            version="v1",
            url=(
                "https://github.com/ryanpavlicek/pyaegean/releases/download/"
                "grc-paradigms-v1/grc-paradigms.json.gz"
            ),
            sha256="c275044ee1e71c49f0161938e7531c1967b7e723b62859b06f47776a765a186a",
            superseded="v2",
        ),
    ],
    "ddbdp-corpus": [
        HistoricalPin(
            version="v1",
            url=(
                "https://github.com/ryanpavlicek/pyaegean/releases/download/"
                "ddbdp-corpus-v1/ddbdp-corpus.tar.gz"
            ),
            sha256="7ae265384543cabc7554e543c3f3a1cccbfa1e3ca531b4cbd8755124f58845e2",
            superseded="v2",
            extract=True,
        ),
    ],
}


# corpus id -> (dataset name, how to build a Corpus from the fetched path) for the corpora
# whose loaders go through fetch AND have kept historical pins, so aegean.load(id, version=)
# can reach an earlier release. The five epigraphy JSON corpora reload via Corpus.from_json;
# ddbdp is the SQLite-in-tar corpus (materialised via db.from_sqlite).
_VERSIONED_CORPORA: dict[str, tuple[str, str]] = {
    "isicily": ("isicily-corpus", "json"),
    "iip": ("iip-corpus", "json"),
    "iospe": ("iospe-corpus", "json"),
    "igcyr": ("igcyr-corpus", "json"),
    "edh": ("edh-corpus", "json"),
    "ddbdp": ("ddbdp-corpus", "sqlite"),
}


def _corpus_dataset_name(script_id: str) -> str | None:
    """The registered dataset name backing a corpus id (``sigla`` -> ``sigla-corpus``,
    ``damos`` -> ``damos-corpus``), or ``None`` when no registered dataset matches. The
    reverse of the CLI's stem resolution, so a versioned-load error can name the
    fetchable asset a corpus's kept pins live under."""
    for candidate in (f"{script_id}-corpus", script_id):
        if candidate in _REMOTE:
            return candidate
    return None


# The version tag suffix of a pinned release URL: '.../isicily-corpus-v2/...' -> 'v2',
# '.../workbench-app-v1.6.1/...' -> 'v1.6.1'.
_TAG_VERSION = re.compile(r"-(v\d+(?:\.\d+)*)$")


def _spec_version(spec: DataSpec) -> str:
    """The current release version of a pinned dataset, read from its release tag
    (``.../releases/download/<tag>/<file>``); ``""`` when the URL is not a pinned
    project release (an env-only / bring-your-own slot)."""
    marker = "/releases/download/"
    if marker not in spec.url:
        return ""
    tag = spec.url.split(marker, 1)[1].split("/", 1)[0]
    m = _TAG_VERSION.search(tag)
    return m.group(1) if m else ""


def _version_env_url_var(name: str, version: str) -> str:
    """The per-version URL override env var, e.g. ``PYAEGEAN_ISICILY_CORPUS_V1_URL``,
    so a historical pin can be fetched from a user's own mirror."""
    v = version.upper().replace(".", "_").replace("-", "_")
    return "PYAEGEAN_" + name.upper().replace("-", "_") + "_" + v + "_URL"


def historical_versions(name: str) -> list[HistoricalPin]:
    """The kept superseded release pins for dataset ``name`` (newest-recorded first),
    or ``[]`` when the dataset has none. Each pin is a `HistoricalPin` carrying the
    version tag, its published url + sha256, and the version that superseded it —
    the reproducibility record `fetch(name, version=...)` resolves against."""
    return list(_REMOTE_HISTORY.get(name, ()))


def available_versions(name: str) -> list[dict[str, Any]]:
    """Every fetchable version of dataset ``name``: the current pin first (``current``:
    True), then each kept historical pin. Each entry is
    ``{"version", "current", "sha256", "url", "superseded"}``. Empty when ``name`` is
    not a registered dataset."""
    spec = _REMOTE.get(name)
    if spec is None:
        return []
    out: list[dict[str, Any]] = []
    cur = _spec_version(spec)
    out.append(
        {
            "version": cur or "current",
            "current": True,
            "sha256": spec.sha256,
            "url": spec.url,
            "superseded": "",
        }
    )
    for pin in _REMOTE_HISTORY.get(name, ()):
        out.append(
            {
                "version": pin.version,
                "current": False,
                "sha256": pin.sha256,
                "url": pin.url,
                "superseded": pin.superseded,
            }
        )
    return out


def _resolve_version(name: str, version: str) -> tuple[str, str, bool, str]:
    """Resolve ``(name, version)`` to ``(url, sha256_to_enforce, extract, resolved_version)``.

    ``version`` may name the current pin (from `_REMOTE`) or a kept historical pin (from
    `_REMOTE_HISTORY`). A ``PYAEGEAN_<NAME>_<VERSION>_URL`` mirror override wins (and disables
    sha enforcement, like the standard current-URL override); otherwise the pinned historical
    url + sha are used and the sha is enforced. Raises `DataNotAvailableError` for an unknown
    dataset or an unknown version (listing the versions that exist)."""
    spec = _REMOTE.get(name)
    if spec is None:
        raise DataNotAvailableError(f"unknown dataset {name!r}; known: {sorted(_REMOTE)}")
    env = os.environ.get(_version_env_url_var(name, version))
    cur = _spec_version(spec)
    if cur and version == cur:
        if env:
            return env, "", spec.extract, cur
        cur_env = os.environ.get(_env_url_var(name))
        if cur_env:  # the current asset's own PYAEGEAN_<NAME>_URL override
            return cur_env, "", spec.extract, cur
        return spec.url, spec.sha256, spec.extract, cur
    for pin in _REMOTE_HISTORY.get(name, ()):
        if pin.version == version:
            if env:
                return env, "", pin.extract, pin.version
            return pin.url, pin.sha256, pin.extract, pin.version
    avail = ([cur] if cur else []) + [p.version for p in _REMOTE_HISTORY.get(name, ())]
    raise DataNotAvailableError(
        f"dataset {name!r} has no version {version!r}; available: {avail or ['(none)']}. "
        "`aegean data versions` lists the kept historical pins."
    )


def _dir_bytes(path: pathlib.Path) -> int:
    """Recursive size of a store path (a file's own size, or a directory's files).

    A file that vanishes between the directory walk and its ``stat`` (a racing
    fetch/remove) is skipped rather than raising, so the other files still count."""
    try:
        is_dir = path.is_dir()
    except OSError:
        return 0
    if is_dir:
        total = 0
        try:
            children = list(path.rglob("*"))
        except OSError:
            return 0
        for f in children:
            try:
                if f.is_file():
                    total += f.stat().st_size
            except OSError:
                continue  # vanished mid-walk
        return total
    try:
        return path.stat().st_size
    except OSError:
        return 0


def on_disk_paths(spec: DataSpec, root: pathlib.Path) -> list[pathlib.Path]:
    """The cache paths that would exist if ``spec`` is present, whether or not
    they do. Defaults to a single ``root/name`` entry (the ``fetch`` path); a
    ``spec.on_disk`` override lists the real artifact names for datasets a
    backend writes under a different filename (the prebuilt lexicon indexes,
    the ``agdt-derived`` members). See `DataSpec.on_disk`."""
    names = spec.on_disk or (spec.name,)
    return [root / n for n in names]


def present_paths(spec: DataSpec, root: pathlib.Path) -> list[pathlib.Path]:
    """Which of ``spec``'s on-disk artifacts actually exist under ``root``."""
    return [p for p in on_disk_paths(spec, root) if p.exists()]


# The download/extraction sidecar suffixes a store entry can carry: the resumable
# ``.part`` and its ``.part.info`` validator, the ``.extract`` staging dir and ``.old``
# swap-aside of an extract dataset, the ``.sha256`` extraction stamp, and the per-entry
# ``.lock``. Used to bound a single-version match, since a version tag itself may contain
# dots (``v1.2``) and so cannot be told from a sibling by a dot alone.
_VERSION_SIBLINGS = frozenset({".part", ".part.info", ".extract", ".old", ".sha256", ".lock"})


def versioned_entry_paths(
    name: str, root: pathlib.Path, *, version: str | None = None
) -> list[pathlib.Path]:
    """Cache paths of dataset ``name``'s versioned fetches, for byte accounting and removal.

    A ``fetch(name, version=...)`` (the kept-release path) lands in a
    ``<name>@<version>`` cache entry beside the current pin: a file, or a directory for
    an ``extract`` dataset, plus, transiently, its download/extraction siblings
    (``.part``, ``.part.info``, ``.extract``, ``.old``, ``.sha256``, ``.lock``), all of
    which share the ``<name>@<version>`` prefix. The current-pin probes (`on_disk_paths`,
    `present_paths`) live at a separate location, so these versioned entries were
    invisible to ``data list`` byte accounting and unreachable by ``data remove``; this
    enumerates them.

    ``version`` restricts the result to that one kept release (``<name>@<version>`` and
    its own siblings); ``None`` returns every version's entries. The match is anchored on
    the exact ``<name>@`` prefix, and for a single ``version`` on the exact entry name or
    that entry plus one of the known download/extraction suffixes, so a sibling dataset is
    never swept in and, e.g., ``v1`` never matches ``v11`` or the distinct version ``v1.2``
    (a version tag can itself contain dots, so a plain entry-plus-dot prefix is unsafe;
    dataset names contain no ``@``). Only entries that actually exist are returned."""
    try:
        children = list(root.iterdir())
    except OSError:
        return []
    if version is None:
        prefix = name + "@"
        return sorted(p for p in children if p.name.startswith(prefix))
    entry = f"{name}@{version}"
    return sorted(
        p for p in children
        if p.name == entry or (p.name.startswith(entry) and p.name[len(entry):] in _VERSION_SIBLINGS)
    )


def versioned_bytes(name: str, root: pathlib.Path, *, version: str | None = None) -> int:
    """Total on-disk size of dataset ``name``'s versioned cache entries (0 if none).

    Persistent ``.lock`` sentinels are store metadata, not dataset payload, and are
    excluded. See `versioned_entry_paths`; ``version`` narrows it to one release."""
    return sum(
        _dir_bytes(p)
        for p in versioned_entry_paths(name, root, version=version)
        if not p.name.endswith(".lock")
    )


def is_downloaded(spec: DataSpec, root: pathlib.Path) -> bool:
    """Whether any real on-disk artifact of ``spec``'s CURRENT pin is present under ``root``.

    This is the corrected downloaded-probe: a dataset a backend fetched under a
    different filename (``lsj-index`` -> ``lsj-perseus-index.json.gz``, an
    ``agdt-derived`` member) counts as downloaded, where a bare
    ``(root/name).exists()`` check missed it. It reports the CURRENT pin only: a
    store holding only a kept historical version (``<name>@<version>``) reads not
    downloaded, since the current asset is what a plain ``fetch``/``load`` uses.
    Use `versioned_entry_paths` / `versioned_bytes` for the kept-version footprint."""
    return bool(present_paths(spec, root))


def downloaded_bytes(spec: DataSpec, root: pathlib.Path) -> int:
    """Total real on-disk size of ``spec``'s artifacts (0 if none).

    Counts the current pin's present artifacts plus any kept versioned entries
    (``<name>@<version>`` from ``fetch(name, version=...)``) that also occupy the store,
    so a dataset's reported footprint reflects every reclaimable byte it holds. The
    current-pin subset alone is ``sum(_dir_bytes(p) for p in present_paths(spec, root))``;
    the versioned subset alone is `versioned_bytes`."""
    current = sum(_dir_bytes(p) for p in present_paths(spec, root))
    return current + versioned_bytes(spec.name, root)


def bundled_data_version() -> str:
    """The version of the bundled datasets.

    Bundled data ships inside the wheel and is immutable for a given release, so
    its version *is* the package version; `versions` gives per-file sha256s."""
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version("pyaegean")
    except PackageNotFoundError:  # pragma: no cover — running from an uninstalled tree
        return "0.0.0+unknown"


def versions() -> dict[str, Any]:
    """A reproducibility manifest of every dataset pyaegean can touch.

    Returns ``{"package": …, "bundled": {…}, "fetched": {…}}``: each bundled
    JSON file with its sha256 + size (hashed from the installed wheel contents),
    and each registered fetchable asset with its pinned URL/sha256, license, and
    whether it is present in the local cache.

    **Pinning for papers**: record ``aegean.__version__`` and this manifest
    (e.g. ``json.dump(aegean.data.versions(), f)``) alongside your results;
    anyone with the same package version and matching sha256s is analyzing
    byte-identical data. Fetched assets are sha256-verified on download, so a
    matching pin in this manifest *is* the byte-level guarantee.

    When a dataset's URL is env-overridden (``PYAEGEAN_<NAME>_URL``, a user's own
    mirror), ``fetch`` does not enforce the pinned sha256 against that other
    source, so the manifest reports ``sha256_enforced: false`` and blanks the
    ``sha256`` for that entry: it would be dishonest to advertise a checksum the
    download did not verify."""
    import hashlib

    bundled: dict[str, dict[str, Any]] = {}
    root = files("aegean.data").joinpath("bundled")
    for sub in sorted(root.iterdir(), key=lambda t: t.name):
        if not sub.is_dir():
            continue
        for f in sorted(sub.iterdir(), key=lambda t: t.name):
            if f.name.endswith(".json"):
                blob = f.read_bytes()
                bundled[f"{sub.name}/{f.name}"] = {
                    "sha256": hashlib.sha256(blob).hexdigest(),
                    "bytes": len(blob),
                }
    root = cache_dir()
    fetched: dict[str, dict[str, Any]] = {}
    for name, spec in sorted(_REMOTE.items()):
        # fetch() disables sha256 verification when the URL is env-overridden, so
        # the pinned sha describes the pinned URL only. Report it as unenforced
        # (and blank the value) rather than advertise a sha the download skipped.
        overridden = bool(os.environ.get(_env_url_var(name)))
        enforced = bool(spec.sha256) and not overridden
        fetched[name] = {
            "url": _resolve_url(spec),
            "sha256": spec.sha256 if enforced else "",
            "sha256_enforced": enforced,
            "url_overridden": overridden,
            "license": spec.license,
            "cached": is_downloaded(spec, root),
            # Kept superseded release pins the project still hosts, so an earlier analysis
            # stays reproducible: fetch(name, version=...) / aegean.load(id, version=...).
            "history": [
                {
                    "version": p.version,
                    "sha256": p.sha256,
                    "url": p.url,
                    "superseded": p.superseded,
                    "cached": (root / f"{name}@{p.version}").exists(),
                }
                for p in _REMOTE_HISTORY.get(name, ())
            ],
        }
    return {"package": bundled_data_version(), "bundled": bundled, "fetched": fetched}


def _env_url_var(name: str) -> str:
    return "PYAEGEAN_" + name.upper().replace("-", "_") + "_URL"


def _resolve_url(spec: DataSpec) -> str:
    """The effective download URL: an env override wins over the pinned URL."""
    return os.environ.get(_env_url_var(spec.name)) or spec.url


def sha256_file(path: pathlib.Path, *, chunk: int = 1 << 20) -> str:
    """Streaming sha256 of a file (won't load a 500 MB asset into memory)."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


_DOWNLOAD_TIMEOUT = 30  # seconds per socket operation: a stall raises instead of hanging
_DOWNLOAD_ATTEMPTS = 3  # one initial transfer plus two in-call resume retries
_DOWNLOAD_CHUNK_SIZE = 1 << 20  # bounded-memory streaming; overridden by small semantic tests


def _part_info_path(dest_part: pathlib.Path) -> pathlib.Path:
    """The sidecar recording what a resume needs to validate a kept ``.part``."""
    return dest_part.with_name(dest_part.name + ".info")


def _read_part_info(dest_part: pathlib.Path) -> dict[str, Any]:
    try:
        raw = json.loads(_part_info_path(dest_part).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _record_part_info(dest_part: pathlib.Path, headers: Any, *, total: int | None) -> None:
    """Persist the remote's full byte length and validators next to the ``.part``,
    so a later resume can tell a continuable download from a stale one (the
    remote was republished under the same URL)."""
    info = {
        "length": total,
        "etag": headers.get("ETag") if headers is not None else None,
        "last_modified": headers.get("Last-Modified") if headers is not None else None,
    }
    try:
        if all(v is None for v in info.values()):
            # Nothing to validate a resume against: drop any sidecar from an
            # earlier transfer so it can never describe bytes it did not watch
            # being written.
            _part_info_path(dest_part).unlink(missing_ok=True)
            return
        _part_info_path(dest_part).write_text(json.dumps(info), encoding="utf-8")
    except OSError:  # the sidecar is best-effort; never fail a download over it
        pass


def _discard_part(dest_part: pathlib.Path) -> None:
    dest_part.unlink(missing_ok=True)
    _part_info_path(dest_part).unlink(missing_ok=True)


def _parse_content_range(value: str | None) -> tuple[int | None, int | None]:
    """``(start, total)`` from a Content-Range header, e.g. ``bytes 500-999/1000``
    or ``bytes */1000``; ``None`` where absent or unknown (``*``)."""
    if not value:
        return None, None
    parts = value.strip().split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bytes":
        return None, None
    range_part, _, total_part = parts[1].partition("/")
    total = int(total_part) if total_part.strip().isdigit() else None
    start_str = range_part.strip().partition("-")[0].strip()
    start = int(start_str) if start_str.isdigit() else None
    return start, total


def _expected_length(headers: Any) -> int | None:
    value = headers.get("Content-Length") if headers is not None else None
    try:
        length = int(str(value).strip()) if value is not None else None
    except ValueError:
        return None
    if length is not None and length < 0:
        raise ValueError(f"negative Content-Length: {length}")
    return length


class FetchAborted(DataNotAvailableError):
    """Raised when a fetch is canceled through its ``abort`` hook (e.g. the TUI's
    download worker being cancelled). The ``.part`` file is kept, so a later fetch
    resumes instead of restarting."""


class _ProgressCallbackError(Exception):
    """Internal marker: a user ``progress`` callback raised mid-transfer. It carries
    the original exception so the download loop can surface it *unwrapped* while
    keeping the resumable ``.part`` (a broken observer must not look like a network
    failure that discards the transfer, nor a content error)."""

    def __init__(self, original: BaseException) -> None:
        super().__init__(str(original))
        self.original = original


def _guard_progress(
    progress: Callable[[int, int], None] | None,
) -> Callable[[int, int], None] | None:
    """Wrap a user progress callback so any exception it raises becomes a
    `_ProgressCallbackError` (the download loop keeps the ``.part`` and re-raises
    the original); ``None`` passes through as ``None`` (no reporting, no overhead)."""
    if progress is None:
        return None

    def wrapped(done: int, total: int) -> None:
        try:
            progress(done, total)
        except Exception as exc:  # a broken observer must not corrupt the transfer
            raise _ProgressCallbackError(exc) from exc

    return wrapped


def _stream_body(
    resp: Any,
    out: IO[bytes],
    abort: Callable[[], bool] | None = None,
    *,
    on_progress: Callable[[int, int], None] | None = None,
    start: int = 0,
    total: int | None = None,
) -> None:
    """Chunked copy (a 500 MB asset never sits in memory) that raises when the
    body ends short of its declared Content-Length. ``read(amt)`` returns short
    silently when the connection drops, so without this check a truncated
    transfer would look complete and be thrown away at sha256 verification
    instead of kept for resume. ``abort`` is polled between chunks; when it goes
    true the transfer stops with `FetchAborted` (the ``.part`` stays resumable).

    ``on_progress`` (when given) is called after each chunk with the absolute file
    position ``start + written`` (``start`` is the resumed ``.part`` offset, 0 for a
    fresh download) and ``total`` — the full file size, or ``-1`` when the remote did
    not declare one."""
    import http.client

    expected = _expected_length(getattr(resp, "headers", None))
    written = 0
    # When Content-Length is known, stop after exactly that many bytes instead of
    # performing one extra socket read to discover EOF. On Windows that read can
    # surface a connection reset even though the complete declared body arrived.
    while expected is None or written < expected:
        if abort is not None and abort():
            raise FetchAborted("fetch canceled")
        amount = (
            _DOWNLOAD_CHUNK_SIZE
            if expected is None
            else min(_DOWNLOAD_CHUNK_SIZE, expected - written)
        )
        chunk = resp.read(amount)
        if not chunk:
            break
        out.write(chunk)
        written += len(chunk)
        if on_progress is not None:
            on_progress(start + written, total if total is not None else -1)
    if expected is not None and written < expected:
        raise http.client.IncompleteRead(b"", expected - written)


def _write_from_zero(
    resp: Any,
    dest_part: pathlib.Path,
    abort: Callable[[], bool] | None = None,
    *,
    progress: Callable[[int, int], None] | None = None,
) -> None:
    """Stream a full-body response into a fresh ``.part``, recording resume
    metadata first so a mid-stream failure leaves a continuable file behind."""
    headers = getattr(resp, "headers", None)
    total = _expected_length(headers)  # the full file size (a 200 body is the whole file)
    _record_part_info(dest_part, headers, total=total)
    with open(dest_part, "wb") as out:
        _stream_body(resp, out, abort, on_progress=progress, start=0, total=total)


def _download_full(
    url: str,
    dest_part: pathlib.Path,
    abort: Callable[[], bool] | None = None,
    *,
    progress: Callable[[int, int], None] | None = None,
) -> None:
    resp = _urlopen_verified(url, timeout=_DOWNLOAD_TIMEOUT)
    with resp:
        _write_from_zero(resp, dest_part, abort, progress=progress)


def _urlopen_verified(request: Any, *, timeout: int) -> Any:
    """Open a registered asset URL with normal TLS verification.

    Python 3.14 enables OpenSSL's ``VERIFY_X509_STRICT`` in its default HTTPS context.
    Some system-trusted enterprise/interception chains omit a CA-extension critical bit
    that strict mode newly requires, so the default ``urlopen`` rejects them even though
    hostname validation and the system trust path succeed. Use the default verified
    context and clear only that compatibility flag. ``CERT_REQUIRED`` and hostname
    checking remain enabled; this never creates an unverified context.
    """
    import ssl
    import urllib.parse
    import urllib.request

    target = request.full_url if hasattr(request, "full_url") else str(request)
    if urllib.parse.urlsplit(target).scheme.lower() != "https":
        return urllib.request.urlopen(request, timeout=timeout)  # noqa: S310
    context = ssl.create_default_context()
    strict = getattr(ssl, "VERIFY_X509_STRICT", 0)
    if strict:
        context.verify_flags &= ~strict
    return urllib.request.urlopen(request, timeout=timeout, context=context)  # noqa: S310


def _download_once(
    url: str,
    dest_part: pathlib.Path,
    abort: Callable[[], bool] | None = None,
    *,
    progress: Callable[[int, int], None] | None = None,
) -> None:
    """One transfer attempt: resume an existing ``.part`` with an HTTP Range
    request when the scheme supports it (GitHub's release CDN does), falling
    back to a clean restart from byte zero on any staleness signal: the server
    ignored Range, the offset is not satisfiable, or the remote's size or
    validators no longer match what the ``.part`` was downloaded from."""
    import urllib.error
    import urllib.parse
    import urllib.request

    offset = 0
    if urllib.parse.urlsplit(url).scheme.lower() in ("http", "https") and dest_part.exists():
        offset = dest_part.stat().st_size
    if offset <= 0:
        # Nothing to resume, or a file:// URL (the env-override / test path),
        # where Range is not meaningful and a restart is cheap.
        _download_full(url, dest_part, abort, progress=progress)
        return

    info = _read_part_info(dest_part)
    req_headers = {"Range": f"bytes={offset}-"}
    validator = info.get("etag") or info.get("last_modified")
    if isinstance(validator, str) and validator and not validator.startswith("W/"):
        # If the remote changed since the .part was written, If-Range makes the
        # server answer 200 with the full new body instead of a mismatched 206.
        req_headers["If-Range"] = validator
    req = urllib.request.Request(url, headers=req_headers)  # noqa: S310 (registered/overridable url)
    try:
        resp = _urlopen_verified(req, timeout=_DOWNLOAD_TIMEOUT)
    except urllib.error.HTTPError as e:
        if e.code != 416:
            raise
        # 416 Range Not Satisfiable: the .part is either already complete or
        # stale (a remote that shrank). Complete means our offset equals the
        # total the server reports; anything else restarts from zero.
        hdrs = getattr(e, "headers", None)
        _, total = _parse_content_range(hdrs.get("Content-Range") if hdrs is not None else None)
        if total is not None and total == offset:
            # Fully downloaded; sha256 verification has the final word. Report a
            # completed line (offset == total here) so a live consumer closes out.
            if progress is not None:
                progress(offset, offset)
            return
        _discard_part(dest_part)
        _download_full(url, dest_part, abort, progress=progress)
        return

    with resp:
        if getattr(resp, "status", None) == 206:
            start, total = _parse_content_range(resp.headers.get("Content-Range"))
            recorded = info.get("length")
            consistent = (
                start == offset
                and not (total is not None and total < offset)
                and not (isinstance(recorded, int) and total is not None and recorded != total)
            )
            if consistent:
                _record_part_info(dest_part, resp.headers, total=total)
                with open(dest_part, "ab") as out:
                    # resume: absolute position starts at the kept .part's offset;
                    # ``total`` from Content-Range is the full file size.
                    _stream_body(resp, out, abort, on_progress=progress, start=offset, total=total)
                return
            # The remote changed under the .part (its total drifted from what
            # was recorded, or the server answered a different offset): fall
            # through to a clean restart from byte zero.
        else:
            # 200: the server ignored Range, or If-Range flagged a changed
            # remote, and it is sending the whole file. Write from byte zero.
            _write_from_zero(resp, dest_part, abort, progress=progress)
            return
    _discard_part(dest_part)
    _download_full(url, dest_part, abort, progress=progress)


def _download(
    url: str,
    dest_part: pathlib.Path,
    name: str,
    abort: Callable[[], bool] | None = None,
    *,
    progress: Callable[[int, int], None] | None = None,
    expected_sha256: str = "",
) -> None:
    """Download ``url`` to ``dest_part``, resuming interrupted transfers.

    A transient network failure (a stall past the timeout, a dropped or
    truncated connection) keeps the ``.part`` file and is retried up to two
    more times within this call, each retry resuming from the bytes already on
    disk; a ``.part`` left behind by an exhausted call is picked up the same
    way by the next `fetch`. Failures that mean the content itself is wrong
    (an HTTP status error here, a checksum mismatch downstream) discard the
    ``.part`` instead. The caller verifies the assembled file's sha256 and
    performs the atomic rename, so nothing partial is ever visible at the
    final path.

    ``progress`` (already `_guard_progress`-wrapped by the caller) reports absolute
    byte counts during the transfer; if it raises, the ``.part`` is kept and the
    original error is surfaced (a broken observer never discards the transfer).
    ``expected_sha256`` lets an EOF-signaling connection reset be accepted only when
    the assembled bytes are already the complete pinned artifact; an unpinned,
    potentially truncated response still follows the normal retry path.
    """
    import http.client
    import urllib.error

    last_exc: Exception | None = None
    for _ in range(_DOWNLOAD_ATTEMPTS):
        try:
            _download_once(url, dest_part, abort, progress=progress)
        except FetchAborted:
            raise  # deliberate cancel: keep the .part so a later fetch resumes it
        except _ProgressCallbackError as e:
            # a user progress callback raised: keep the resumable .part (do NOT
            # discard) and surface the original error, not a wrapped network one
            raise e.original from None
        except urllib.error.HTTPError as e:
            # A status error (403, 404, ...) means the resource is wrong or
            # gone; no kept .part could assemble into the right file.
            _discard_part(dest_part)
            raise DataNotAvailableError(f"could not fetch {name!r} from {url}: {e}") from e
        except (http.client.HTTPException, OSError) as e:
            # A close-delimited response (no Content-Length) can deliver every byte
            # and then surface ConnectionResetError instead of a clean EOF on Windows.
            # A pinned whole-file digest is decisive: if the assembled .part already
            # matches it, the transfer completed and a Range retry would only duplicate
            # progress calls (or fail a valid download). Never use this shortcut for an
            # unpinned mirror, where a reset could have truncated arbitrary content.
            if expected_sha256 and dest_part.exists():
                try:
                    complete = sha256_file(dest_part) == expected_sha256
                except OSError:
                    complete = False
                if complete:
                    _part_info_path(dest_part).unlink(missing_ok=True)
                    return
            last_exc = e  # network-class: keep the .part and resume
        except Exception as e:
            _discard_part(dest_part)
            raise DataNotAvailableError(f"could not fetch {name!r} from {url}: {e}") from e
        else:
            _part_info_path(dest_part).unlink(missing_ok=True)
            return
    if dest_part.exists():
        # A transfer got underway and was cut off mid-stream: the .part on disk
        # holds the bytes received so far and a later fetch resumes from there.
        raise DataNotAvailableError(
            f"could not fetch {name!r} from {url} after {_DOWNLOAD_ATTEMPTS} attempts "
            f"(partial download kept; retrying will resume it): {last_exc}"
        ) from last_exc
    # Connection refused, DNS failure, or otherwise offline: no bytes were
    # transferred, so there is nothing partial to resume. Say so, and point at
    # the store and an offline-appropriate next step.
    raise DataNotAvailableError(
        f"could not fetch {name!r} from {url}: {last_exc}. Nothing was downloaded, so "
        f"{name!r} is not in your local store ({dest_part.parent}). Check your network "
        f"connection and retry; run 'aegean data list' to see what is already downloaded."
    ) from last_exc


def _verify(path: pathlib.Path, sha256: str, name: str) -> None:
    if sha256:
        got = sha256_file(path)
        if got != sha256:
            path.unlink(missing_ok=True)
            raise DataNotAvailableError(
                f"checksum mismatch for {name!r}: expected {sha256}, got {got}"
            )
        _LOG.debug("checksum verified for %r", name)


def download_file(url: str, dest: pathlib.Path, *, sha256: str = "") -> pathlib.Path:
    """Download a single URL to ``dest`` atomically (a ``.part`` temp then rename),
    optionally sha256-verified. A transfer cut off by a network failure keeps
    its ``.part``, and the next call resumes it with an HTTP Range request.
    Returns ``dest``; raises `DataNotAvailableError` on a network failure or
    checksum mismatch. Shared by `fetch` and the on-demand dataset downloaders
    (e.g. the Greek treebank)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    lock = dest.with_name(dest.name + ".lock")
    with FileLock(lock, poll_every=_LOCK_POLL_S):
        # Recheck after waiting: a concurrent caller may have completed the exact
        # destination while this caller was blocked on its shared .part file.
        if dest.exists() and (not sha256 or sha256_file(dest) == sha256):
            return dest
        tmp = dest.with_name(dest.name + ".part")
        _download(url, tmp, dest.name, expected_sha256=sha256)
        _verify(tmp, sha256, dest.name)
        tmp.replace(dest)  # atomic within the directory
    return dest


_MAX_TAR_EXTRACT_BYTES = 4 * 1024**3
_MAX_TAR_MEMBERS = 250_000


def _safe_extract_tar(
    archive: pathlib.Path,
    dest: pathlib.Path,
    *,
    progress: Callable[[int, int], None] | None = None,
    max_bytes: int = _MAX_TAR_EXTRACT_BYTES,
    max_members: int = _MAX_TAR_MEMBERS,
) -> None:
    """Extract a tar archive, refusing any member (or link target) that escapes ``dest``.

    Every member is validated up front, so an unsafe archive is rejected before any
    file is written (unchanged). ``progress`` (when given) reports
    ``progress(members_done, total_members)`` as members are extracted one at a time;
    without it the whole archive is extracted in a single ``extractall`` call (the
    unchanged default). The member count is already computed for the safety pass, so
    per-member progress adds no extra work over the default path."""
    import tarfile

    root = dest.resolve()
    with tarfile.open(archive) as tf:
        members = tf.getmembers()
        if len(members) > max_members:
            raise DataNotAvailableError(
                f"archive has {len(members):,} members; refusing more than {max_members:,}"
            )
        expanded = sum(member.size for member in members)
        if expanded > max_bytes:
            raise DataNotAvailableError(
                f"archive expands to {expanded:,} bytes; refusing more than {max_bytes:,}"
            )
        for member in members:
            if member.size < 0 or member.isdev() or member.isfifo():
                raise DataNotAvailableError(
                    f"unsafe special file in archive: {member.name!r}"
                )
            target = (root / member.name).resolve()
            if target != root and root not in target.parents:
                raise DataNotAvailableError(f"unsafe path in archive: {member.name!r}")
            if member.issym() or member.islnk():
                # A symlink target is relative to the link's own directory; a hard link
                # (or an absolute target) resolves from the extraction root.
                base = target.parent if member.issym() else root
                linked = (base / member.linkname).resolve()
                if linked != root and root not in linked.parents:
                    raise DataNotAvailableError(
                        f"unsafe link target in archive: {member.name!r} -> {member.linkname!r}"
                    )
        if progress is None:
            try:
                tf.extractall(root, filter="data")  # py3.12+ hardening
            except TypeError:  # pragma: no cover - older Python
                tf.extractall(root)
            return
        # Per-member extraction (same files as extractall) so a member-count progress
        # line can move; members are in archive order, so each seek is forward (no
        # gzip re-read penalty vs extractall).
        total = len(members)
        for i, member in enumerate(members, 1):
            try:
                tf.extract(member, root, filter="data")  # py3.12+ hardening
            except TypeError:  # pragma: no cover - older Python
                tf.extract(member, root)
            progress(i, total)


# Concurrent fetches of the SAME dataset (two threads, two processes, a doctor/TUI
# poll racing a CLI fetch) must not share the .part file or the .extract staging dir:
# a second writer appending at a moving EOF corrupts the transfer, and a second
# extractor rmtree-ing the staging mid-extraction breaks the first. One advisory
# lock file per dataset serializes them; the loser waits, then finds the winner's
# artifact via the normal idempotence check.
_LOCK_STALE_S = 3600.0  # a holder that has been silent this long is presumed dead
_LOCK_POLL_S = 0.5
_LOCK_HEARTBEAT_S = 30.0


class _DatasetLock(FileLock):
    def __init__(self, name: str) -> None:
        super().__init__(
            cache_dir() / (name + ".lock"),
            stale_after=_LOCK_STALE_S,
            poll_every=_LOCK_POLL_S,
            heartbeat_every=_LOCK_HEARTBEAT_S,
        )


def fetch(
    name: str,
    *,
    version: str | None = None,
    force: bool = False,
    abort: Callable[[], bool] | None = None,
    progress: Callable[[int, int], None] | None = None,
) -> pathlib.Path:
    """Download a registered remote dataset into the cache and return its path.

    Verifies the sha256 when one is pinned, downloads atomically, and is a no-op
    when the cache already holds it. An interrupted download keeps its ``.part``
    file and the next call resumes from it (an HTTP Range request) instead of
    restarting from zero. For ``extract`` datasets the download is a
    tar archive that is unpacked into a cache directory (returned); otherwise the
    downloaded file path is returned. Concurrent fetches of the same dataset
    (other threads or processes) are serialized on a per-dataset lock: the later
    caller waits, then returns the completed artifact. ``abort`` is an optional
    zero-argument callable polled during the transfer; when it returns true the
    fetch stops with `FetchAborted`, keeping the partial file resumable (how the
    TUI cancels a download worker).

    ``version`` (optional) fetches a specific kept release of the dataset instead
    of the current pin — the current version tag (``"v2"``) or a superseded one the
    project still hosts (``"v1"``; see `historical_versions`). A versioned fetch
    lands in a **separate** version-suffixed cache entry (``<name>@<version>``), so
    the default (``version=None``) path is completely unaffected — byte-for-byte the
    same download to the same location as before. Use it to reproduce an analysis
    pinned to an earlier release; `available_versions` lists what exists.

    ``progress`` (optional) reports the run's movement as ``progress(done, total)``:
    during the download it is **bytes** — the absolute byte position and the full
    file size, or ``total == -1`` when the remote declares no Content-Length (the
    ``[int, int]`` signature is preserved by using ``-1`` rather than ``None``, and
    ``-1`` is unambiguous where an empty file's ``0`` would not be); resume continues
    from the kept ``.part`` offset. For an ``extract`` dataset it is then called with
    **tar members** — ``progress(members_done, total_members)`` — while unpacking. A
    fresh, already-cached fetch makes no download calls (nothing to report). If
    ``progress`` raises, the transfer's resumable ``.part`` is kept and the error is
    surfaced unwrapped. Raises `DataNotAvailableError` for unknown datasets, un-pinned
    URLs, an unknown version, checksum mismatches, unsafe archives, or network
    failures — never silently, and never blocking ``import``.
    """
    spec = _REMOTE.get(name)
    if spec is None:
        raise DataNotAvailableError(f"unknown dataset {name!r}; known: {sorted(_REMOTE)}")
    if version is not None:
        # A specific kept release: separate version-suffixed cache entry; the default
        # (version=None) path below is untouched.
        return _fetch_versioned(name, version, force, abort, progress)
    url = _resolve_url(spec)
    if not url:
        raise DataNotAvailableError(
            f"dataset {name!r} has no pinned download URL yet ({spec.note}). "
            f"Set {_env_url_var(name)} to fetch from a mirror. License: {spec.license}"
        )
    # The pinned sha256 describes the pinned URL only. When the URL is overridden
    # via the env var (a user's own licensed copy), don't enforce it.
    sha256 = "" if os.environ.get(_env_url_var(name)) else spec.sha256
    guarded = _guard_progress(progress)  # a raising observer never corrupts the transfer

    with _DatasetLock(name):
        if spec.extract:
            return _fetch_and_extract(url, name, force, sha256, abort, progress=guarded)

        dest = cache_dir() / name
        final = dest
        if len(spec.on_disk) == 1 and spec.on_disk[0] != name:
            # A single-file dataset whose real artifact name differs from the dataset
            # name (the prebuilt lexicon indexes: ``on_disk`` names the built-index
            # file). Store it under that name — the same end state the backends'
            # ``fetch_prebuilt`` produces — so fetch/list/doctor/remove all agree.
            # A raw-named copy left by an older fetch is adopted in place (or dropped
            # when it is stale or redundant) instead of being re-downloaded.
            final = cache_dir() / spec.on_disk[0]
            if dest.exists():
                if not final.exists() and (not sha256 or sha256_file(dest) == sha256):
                    os.replace(dest, final)
                else:
                    dest.unlink()
        if final.exists() and not force:
            if not sha256 or sha256_file(final) == sha256:
                _LOG.debug("dataset %r already cached at %s", name, final)
                return final  # present and valid → idempotent no-op
        _LOG.info("fetching dataset %r", name)
        tmp = dest.with_name(dest.name + ".part")  # raw-named .part: resume + orphan probes key on it
        _download(
            url,
            tmp,
            name,
            abort,
            progress=guarded,
            expected_sha256=sha256,
        )
        _verify(tmp, sha256, name)
        tmp.replace(final)  # atomic within the cache dir
        return final


def fetch_prebuilt(name: str, dest: pathlib.Path, *, member: str | None = None) -> bool:
    """Place a hosted prebuilt artifact at ``dest``; return ``True`` on success.

    Lets an opt-in backend prefer a small hosted index/model over a slow local
    build (a ~270 MB download, or minutes of training), while keeping
    build-from-source as the fallback: any failure — no pinned URL, network
    error, checksum mismatch — returns ``False`` instead of raising, so the
    caller proceeds to build. ``member`` names a file inside an ``extract``
    dataset's unpacked directory.
    """
    import shutil

    try:
        got = fetch(name)
    except DataNotAvailableError:
        return False
    src = got / member if member is not None else got
    if not src.exists():
        return False
    if src.resolve() != dest.resolve():
        dest.parent.mkdir(parents=True, exist_ok=True)
        if member is None:
            # A single-file dataset: fetch() already stores it under its on_disk name,
            # so src == dest for the standard cache and this branch is a no-op guard.
            # It still MOVES (never copies) when a backend passes a different dest, or
            # the raw copy would linger uncounted and unremovable (the spec's on_disk
            # override lists only the built-index name). For a member (an extract
            # dataset), cache_dir()/name is the tracked unpacked directory: copy, keep.
            os.replace(src, dest)
        else:
            from .._atomic import atomic_path

            with atomic_path(dest) as tmp:
                shutil.copyfile(src, tmp)
    return True


def _looks_gzip(path: pathlib.Path) -> bool:
    """Whether ``path`` begins with the gzip magic number (``1f 8b``).

    Content-sniffed rather than name-sniffed, so a gzipped source is decompressed and a
    plain one is copied through regardless of how the asset is named."""
    try:
        with open(path, "rb") as f:
            return f.read(2) == b"\x1f\x8b"
    except OSError:
        return False


def fetch_text(
    name: str,
    dest: str | pathlib.Path,
    *,
    max_bytes: int = _MAX_GZIP_JSON_BYTES,
    download: bool = True,
    expect_gzip: bool | None = None,
) -> pathlib.Path:
    """Fetch dataset ``name`` and materialize it at ``dest``, gunzipping and stamping it.

    The shared fetch-then-materialize helper. It fetches the registered dataset ``name``
    (sha256-pinned, via `fetch`), gunzip-decompresses it under a ``max_bytes`` cap, and
    writes the result to ``dest``. ``expect_gzip`` declares the caller's knowledge of the
    asset: ``True`` means the asset is always a gzip archive, so a source failing the
    ``1f 8b`` magic-byte check is a corrupt or swapped archive and raises rather than
    materializing garbage; ``False`` copies through without decompressing; the default
    ``None`` sniffs the content, decompressing gzip and copying plain sources through,
    but still refuses a non-gzip source whose own name says ``.gz`` (the same
    corrupt-archive reasoning). The ``max_bytes`` cap guards a decompression-bomb (or
    otherwise oversized) payload served through a ``PYAEGEAN_<NAME>_URL`` mirror override
    that disables the pinned-sha check, exactly as `load_gzip_json` documents.

    Contract:

    * **Atomic write.** ``dest`` is written to a temp sibling then swapped into place, so an
      interrupted write never leaves a partial file to be served, and a failed write leaves
      any prior ``dest`` intact.
    * **Re-pin means re-extract.** A ``<dest>.sha256`` sidecar records the sha256 of the
      fetched source. On a later call ``dest`` is reused only when that sidecar matches the
      current source, so a re-pinned asset (new content at the same name) re-materializes. A
      missing or unreadable stamp also re-materializes: unlike `fetch`'s heavy-archive
      extract path, there is no legacy-trust carve-out here, because these are small files,
      so a fresh decompress is cheap and correctness wins.

    ``download=False`` returns ``dest`` without fetching, for referencing the cached path
    offline. Returns ``dest``. Raises `DataNotAvailableError` for an unknown or un-pinned
    dataset, a network or checksum failure (from `fetch`), or a source that exceeds
    ``max_bytes``."""
    from .._atomic import atomic_path

    dest = pathlib.Path(dest)
    stamp = dest.with_name(dest.name + ".sha256")
    if not download:
        return dest
    src = fetch(name)
    src_sha = sha256_file(src)
    if dest.exists() and stamp.exists():
        try:
            if stamp.read_text(encoding="ascii").strip() == src_sha:
                return dest  # unchanged source: the cached materialization is current
        except (OSError, UnicodeDecodeError):
            pass  # unreadable stamp: fall through and re-materialize
    is_gzip = _looks_gzip(src)
    if is_gzip and expect_gzip is not False:
        payload = _read_gzip_capped(src, max_bytes)
    elif expect_gzip is True or (expect_gzip is None and src.name.endswith(".gz") and not is_gzip):
        # The caller (or the name) promises gzip but the content is not: a corrupt
        # download or a swapped mirror body. Refuse rather than materialize garbage.
        raise DataNotAvailableError(
            f"{src} is not gzip data but the {name!r} asset must be; refusing to "
            "materialize it (a corrupt or swapped archive)"
        )
    else:
        # A plain source is copied through; check the on-disk size first (cheap) so an
        # oversized mirror payload is refused before it is read into memory.
        if src.stat().st_size > max_bytes:
            raise DataNotAvailableError(
                f"{src} is larger than {max_bytes} bytes; refusing to materialize it "
                "(a possible oversized payload from an unverified mirror)"
            )
        payload = src.read_bytes()
    with atomic_path(dest) as tmp:
        tmp.write_bytes(payload)
    # The stamp is written AFTER dest: an interruption between the two leaves a missing
    # stamp, which re-materializes on the next call rather than serving an unverified copy.
    with atomic_path(stamp) as tmp:
        tmp.write_text(src_sha, encoding="ascii")
    return dest


def _extract_stamp(name: str) -> pathlib.Path:
    """The sidecar recording the sha256 of the archive that produced an ``extract``
    dataset's unpacked directory, so a later ``fetch`` can tell whether the cached
    extraction still matches the pinned archive (the single-file path re-hashes the
    file itself; an extraction cannot, its archive is gone, hence this stamp)."""
    return cache_dir() / (name + ".sha256")


_EMBEDDED_EXTRACT_STAMP = ".pyaegean-source.sha256"


def _fetch_and_extract(
    url: str,
    name: str,
    force: bool,
    sha256: str,
    abort: Callable[[], bool] | None = None,
    *,
    progress: Callable[[int, int], None] | None = None,
    store_name: str | None = None,
) -> pathlib.Path:
    import shutil

    # ``store_name`` is the on-disk cache entry name; it equals ``name`` for a normal
    # fetch and ``<name>@<version>`` for a versioned one, so a historical release unpacks
    # beside (never over) the current extraction. ``name`` stays the log/error label.
    store = store_name or name
    target = cache_dir() / store  # a directory of unpacked files
    stamp = _extract_stamp(store)
    trash = cache_dir() / (store + ".old")
    # Recover an interrupted swap before consulting the cache.  The old directory
    # is a complete prior generation; serving it is safer than downloading again
    # with the public target temporarily missing.
    if not target.exists() and trash.exists():
        os.replace(trash, target)
    if target.exists() and not force:
        # Idempotent no-op ONLY when the extraction still matches the pinned archive.
        # An env-overridden URL disables sha enforcement (sha256==""), so trust the
        # existing extraction. A stamp that mismatches the pin means the archive was
        # re-pinned (e.g. a corpus rebuilt as -v2): fall through and re-fetch. A
        # missing stamp is a pre-stamp (legacy) extraction: trust it, so upgrading
        # does not needlessly re-download every unchanged heavy archive.
        if not sha256:
            _LOG.debug("dataset %r already extracted at %s", name, target)
            return target
        embedded_stamp = target / _EMBEDDED_EXTRACT_STAMP
        stamp_exists = embedded_stamp.exists() or stamp.exists()
        try:
            if embedded_stamp.exists():
                stamped = embedded_stamp.read_text(encoding="ascii").strip()
            elif stamp.exists():
                stamped = stamp.read_text(encoding="ascii").strip()
            else:
                stamped = ""
        except (OSError, UnicodeError):
            stamped = ""  # an unreadable present stamp is not a legacy cache
        if (not stamp_exists and stamped == "") or stamped == sha256:
            _LOG.debug("dataset %r already extracted at %s", name, target)
            return target

    _LOG.info("fetching dataset %r (archive to extract)", name)
    archive = cache_dir() / (store + ".part")
    _download(
        url,
        archive,
        name,
        abort,
        progress=progress,
        expected_sha256=sha256,
    )
    _verify(archive, sha256, name)  # removes the archive on mismatch + raises
    # Stamp what was ACTUALLY extracted, even on an unpinned (env-mirror) fetch: an
    # unstamped extraction is indistinguishable from a trusted pre-stamp legacy cache, so
    # a later PINNED fetch would serve the mirror's content unverified. With the real
    # archive sha stamped, a later pin mismatch re-downloads (and a mirror serving
    # byte-identical content stamps the matching sha and is a clean no-op).
    stamp_value = sha256 or sha256_file(archive)

    staging = cache_dir() / (store + ".extract")
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    _LOG.info("extracting dataset %r", name)
    try:
        _safe_extract_tar(archive, staging, progress=progress)
    except _ProgressCallbackError as e:
        # a user progress callback raised mid-extraction: surface it unwrapped.
        # The staging dir is orphaned (target not yet swapped, so the prior
        # extraction is intact) and the next fetch clears + re-extracts it.
        raise e.original from None
    finally:
        archive.unlink(missing_ok=True)
    # This stamp moves atomically WITH the extracted directory. If the process dies
    # after the target swap but before the compatibility sidecar below, the next fetch
    # can still distinguish this new extraction from a genuinely pre-stamp legacy one.
    (staging / _EMBEDDED_EXTRACT_STAMP).write_text(stamp_value, encoding="ascii")
    if target.exists():
        # Swap in the new extraction without an rmtree-then-replace race: on Windows a
        # just-rmtree'd directory can linger in a pending-delete state, so os.replace onto
        # it fails (WinError 5). Rename the old extraction aside first (a fast atomic move),
        # put the new one in place, then delete the old copy.
        if trash.exists():
            shutil.rmtree(trash, ignore_errors=True)
        os.replace(target, trash)
        try:
            staging.replace(target)  # atomic within the cache dir; target is now free
        except BaseException:
            # A failed second rename must not strand the previously valid corpus
            # under .old. Restore it before surfacing the replacement failure.
            if not target.exists() and trash.exists():
                os.replace(trash, target)
            raise
        shutil.rmtree(trash, ignore_errors=True)
    else:
        staging.replace(target)  # atomic within the cache dir
    # Keep the historical sibling sidecar for store tooling and older pyaegean versions,
    # but write it atomically. The embedded stamp above is the crash-consistency source.
    from .._atomic import atomic_path

    with atomic_path(stamp) as tmp:
        tmp.write_text(stamp_value, encoding="ascii")
    return target


def _fetch_versioned(
    name: str,
    version: str,
    force: bool,
    abort: Callable[[], bool] | None,
    progress: Callable[[int, int], None] | None,
) -> pathlib.Path:
    """Fetch a specific kept release of ``name`` into a version-suffixed cache entry
    (``<name>@<version>``). Mirrors the default `fetch` path (sha-verify, atomic,
    resumable, per-entry lock) but never touches the current dataset's cache location,
    so `fetch(name)` behaviour is unchanged."""
    url, sha256, extract, resolved = _resolve_version(name, version)
    store_name = f"{name}@{resolved}"
    guarded = _guard_progress(progress)  # a raising observer never corrupts the transfer
    with _DatasetLock(store_name):
        if extract:
            return _fetch_and_extract(
                url, name, force, sha256, abort, progress=guarded, store_name=store_name
            )
        dest = cache_dir() / store_name
        if dest.exists() and not force:
            if not sha256 or sha256_file(dest) == sha256:
                _LOG.debug("dataset %r version %s already cached at %s", name, resolved, dest)
                return dest  # present and valid → idempotent no-op
        _LOG.info("fetching dataset %r version %s", name, resolved)
        tmp = dest.with_name(dest.name + ".part")
        _download(
            url,
            tmp,
            store_name,
            abort,
            progress=guarded,
            expected_sha256=sha256,
        )
        _verify(tmp, sha256, store_name)
        tmp.replace(dest)  # atomic within the cache dir
        return dest


def load_corpus_version(
    script_id: str,
    version: str,
    *,
    progress: Callable[[int, int], None] | None = None,
) -> "Corpus":
    """Load a kept historical release of a fetched corpus as a `Corpus`.

    Backs ``aegean.load(script_id, version=...)`` for the corpora whose loaders go
    through `fetch` and have kept historical pins (`_VERSIONED_CORPORA`): the five
    epigraphy JSON corpora reload via `Corpus.from_json`; ``ddbdp`` materialises from
    its SQLite database (heavy). The versioned asset lands in its own cache entry, so
    the current corpus is untouched. Raises `DataNotAvailableError` for a corpus with
    no kept historical pins."""
    from ..core.corpus import Corpus

    entry = _VERSIONED_CORPORA.get(script_id)
    if entry is None:
        # A corpus whose dataset DOES keep historical pins (sigla, whose JSON layout is
        # custom, not Corpus.to_json) has no versioned aegean.load path, but its pins are
        # still fetchable — say so, instead of the false "has none".
        name = _corpus_dataset_name(script_id)
        pins = historical_versions(name) if name else []
        if pins:
            kept = ", ".join(p.version for p in pins)
            raise DataNotAvailableError(
                f"versioned load is not supported for {script_id!r} (its data layout is "
                f"not a plain Corpus.to_json); its pinned versions can be fetched with "
                f"`aegean data fetch {name} --version <v>` (kept: {kept})."
            )
        raise DataNotAvailableError(
            f"aegean.load(..., version=...) is available only for corpora with kept "
            f"historical pins ({sorted(_VERSIONED_CORPORA)}); {script_id!r} has none. "
            "Its current data loads with the plain aegean.load(script_id)."
        )
    dataset, kind = entry
    path = fetch(dataset, version=version, progress=progress)
    if kind == "json":
        return Corpus.from_json(path)
    # sqlite (ddbdp): the fetched path is the unpacked directory; load the .sqlite in it
    from ..db import from_sqlite

    db_files = sorted(pathlib.Path(path).glob("*.sqlite"))
    db_path = db_files[0] if db_files else pathlib.Path(path) / "ddbdp.sqlite"
    return from_sqlite(db_path, progress=progress)
