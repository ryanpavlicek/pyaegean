"""Static remote-dataset registry, historical version pins, and versioned corpora map.

Re-exported from :mod:`aegean.data` so callers and tests access ``DataSpec``,
``HistoricalPin``, ``_REMOTE``, ``_REMOTE_HISTORY``, and ``_VERSIONED_CORPORA``
from ``aegean.data`` as before.
"""

from __future__ import annotations

from dataclasses import dataclass

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
    # AGDT + Gorman + Pedalion; measured UD Ancient Greek (Perseus) results and the
    # comparison protocol are in docs/benchmarks.md. URL is pinned to the grc-joint-v3 release asset; set
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
            "papygreek-fold-v4/papygreek-fold.conllu.gz"
        ),
        sha256="39c202e78ba4b439cb08a8e41b50ebd386561291f348c8d2f115efcd9e6559b3",
        license="CC BY-SA 4.0 (PapyGreek Treebanks); derived UD fold, fetched, never bundled",
        note="documentary-Koine dependency eval fold (1,551 sentences / 22,227 tokens) converted "
             "from the PapyGreek Treebanks; AGDT->UD CoNLL-U, work-disjoint from grc-joint "
             "training. Evaluation only.",
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
            "papygreek-fold-orig-v3/papygreek-fold-orig.conllu.gz"
        ),
        sha256="db338c428b63e52c715431f878740111be135dc236e4e8fb51c1a3c5e42f9d90",
        license="CC BY-SA 4.0 (PapyGreek Treebanks); derived UD fold, fetched, never bundled",
        note="the ORIG diplomatic surface layer of papygreek-fold (same 1,551 sentences and gold; "
             "FORM = raw diplomatic orthography; 1,453 forms differ). Evaluation only.",
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
            "papygreek-dev-v3/papygreek-dev-tagging.conllu.gz"
        ),
        sha256="370c0445a4204d2b25be0019a1dedcf3e93be15a85c06db6f79f67d08ba017d0",
        license="CC BY-SA 4.0 (PapyGreek Treebanks); derived DEV fold, fetched, never bundled",
        note="documentary-Koine DEV tagging track (323 sentences / 6,319 tokens); work-disjoint "
             "from grc-joint training and document-disjoint from the papygreek-fold test set; "
             "UPOS/XPOS/UFeats/lemma. Experiment data only, never a published number.",
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
            "papygreek-dev-v3/papygreek-dev-parse.conllu.gz"
        ),
        sha256="1704903391c6404ffa21e553d08c13b46305746b43f31a7be1f19535cd1d8b79",
        license="CC BY-SA 4.0 (PapyGreek Treebanks); derived DEV fold, fetched, never bundled",
        note="documentary-Koine DEV parse track (125 sentences / 1,262 tokens, directional only); "
             "work-disjoint from grc-joint training and document-disjoint from the papygreek-fold "
             "test set; UAS/LAS. Experiment data only, never a published number.",
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
             "division (1,895 words), homophone subscripts (RA₂/PU₂/TA₂), and "
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
            "isicily-corpus-v4/isicily-corpus.json"
        ),
        sha256="d716118b43bce3e3d3d194de029bbc39c13b7b10d60c6402b7d832c124c2735f",
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
            "iip-corpus-v4/iip-corpus.json"
        ),
        sha256="e426dd4c40c6e5e2baf578ad27c8d91ba9af7fea8fdc81aed798d41855259109",
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
            "iospe-corpus-v4/iospe-corpus.json"
        ),
        sha256="387bd59391331656166cf64de82fe80ce4fb0f63383384138a113b59e3f0a358",
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
            "igcyr-corpus-v4/igcyr-corpus.json"
        ),
        sha256="a9f5acc27e101b6c326e64fe3eaf96989692347aa1c9446f17adb3cef1b45178",
        license="CC-BY-NC-SA-4.0 (IGCyr2/GVCyr2, C. Dobias-Lalou et al., Univ. di Bologna, 2024)",
        note="IGCyr/GVCyr Greek inscriptions of Cyrenaica: 997 texts (Doric + verse) with title, "
             "find-place, date, from the CC BY-NC-SA EpiDoc corpus. Loadable via aegean.load('igcyr').",
        extract=False,
    ),
    "edh-corpus": DataSpec(
        name="edh-corpus",
        url=(
            "https://github.com/ryanpavlicek/pyaegean/releases/download/"
            "edh-corpus-v4/edh-corpus.json"
        ),
        sha256="e2c6923de42b58f68ccf8742e1eaefe48b3be7b69df1cfda42230351d893b393",
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
    # Extended Strong's Greek Lexicon (STEPBible TBESG CC BY 4.0 + OpenScriptures
    # Strong's CC BY-SA), built reproducibly by scripts/build_strongs_greek.py.
    # Covers NT + LXX + Apocrypha + Apostolic Fathers (11,142 entries, 4,635 with
    # etymological root chains). CC BY-SA derived asset — fetched on demand, never bundled.
    "strongs-greek": DataSpec(
        name="strongs-greek",
        url=(
            "https://github.com/ryanpavlicek/pyaegean/releases/download/"
            "strongs-greek-v1/strongs-greek.json.gz"
        ),
        sha256="96345c5d25ae972b548bb7ed16557e3c58dc53663f6093bae7b02f093b52e507",
        license="CC-BY-SA-4.0 (STEPBible TBESG CC BY 4.0 + OpenScriptures Strong's CC BY-SA); fetched, never bundled",
        note="Extended Strong's Greek Lexicon (11,142 entries: NT + LXX + Apocrypha + Apostolic "
             "Fathers, etymological root trees, Hebrew cross-references; ~1.5 MB gzip). Used by "
             "aegean.greek.bible.use_strongs() / strongs_entry() / strongs_roots().",
        extract=False,
        on_disk=("strongs-greek.json.gz",),
    ),
    # Multi-edition Greek New Testament bundle (8 editions: SBLGNT, SRGNT, BHP,
    # Tischendorf 8th, Westcott-Hort 1881, Robinson-Pierpont Byzantine Majority Text,
    # Antoniades 1904 Patriarchal Edition, Textus Receptus), built reproducibly by
    # scripts/build_nt_editions.py. Fetched on demand, never bundled.
    "nt-editions": DataSpec(
        name="nt-editions",
        url=(
            "https://github.com/ryanpavlicek/pyaegean/releases/download/"
            "nt-editions-v2/nt-editions.json.gz"
        ),
        sha256="4bbe7fddf90627d3affa87ba977744c5f2f2b54a24741135e0b6df49386a19a8",
        license=(
            "CC-BY-SA-3.0 / CC-BY-4.0 / Public Domain (SBLGNT/MorphGNT; CNTR SR, BHP & KJTR; "
            "Tischendorf 8th, Westcott-Hort 1881, Robinson-Pierpont BYZ, Antoniades 1904)"
        ),
        note=(
            "Multi-edition Greek New Testament (~3.3 MB gzip): 8 editions (SBLGNT, SRGNT, BHP, "
            "Tischendorf 8th, Westcott-Hort 1881, Byzantine Majority, Antoniades 1904 Patriarchal, "
            "Textus Receptus). Used by aegean.greek.bible.load_nt(..., edition=...) and compare_editions()."
        ),
        extract=False,
        on_disk=("nt-editions.json.gz",),
    ),
    # Early Greek New Testament Manuscript Witnesses (CNTR Class 1, CC BY-SA 4.0), built
    # reproducibly by scripts/build_nt_witnesses.py: 6 major uncials (01/Sinaiticus,
    # 02/Alexandrinus, 03/Vaticanus, 04/Ephraemi, 05/Bezae, 032/Washingtonianus) and
    # 7 landmark early papyri (P45, P46, P47, P52, P66, P72, P75).
    "nt-witnesses": DataSpec(
        name="nt-witnesses",
        url=(
            "https://github.com/ryanpavlicek/pyaegean/releases/download/"
            "nt-witnesses-v1/nt-witnesses.json.gz"
        ),
        sha256="2436abd052e92a10d7fd13a3f80b89f08f73cd3c244a0a3a3f5a00c5a4d2b478",
        license="CC-BY-SA-4.0 (Center for New Testament Restoration / Alan Bunning); fetched, never bundled",
        note="Early Greek NT manuscript witnesses (~2.0 MB gzip): 13 landmark 2nd-5th c. CE "
             "uncials and papyri (01, 02, 03, 04, 05, 032, P45, P46, P47, P52, P66, P72, P75) "
             "with CNTR MES diplomatic markup and nomina sacra. Used by aegean.greek.bible.load_witness() / compare_witnesses().",
        extract=False,
        on_disk=("nt-witnesses.json.gz",),
    ),
    "lxx-corpus": DataSpec(
        name="lxx-corpus",
        url=(
            "https://github.com/ryanpavlicek/pyaegean/releases/download/"
            "lxx-corpus-v1/lxx-corpus.json.gz"
        ),
        sha256="23d9398e70c56bd0fa660cfb2591e09bb29dfcaf5274f271649c0c39902470ee",
        license=(
            "CC BY-SA 4.0 (Open Greek and Latin / First1KGreek TEI digitization; "
            "Henry Barclay Swete 1887–1894 Public Domain Greek base text); fetched, never bundled"
        ),
        note=(
            "Swete Septuagint (LXX) corpus (~1.65 MB gzip): all 55 Greek Septuagint books "
            "(29,248 verses, NFC-normalized). Used by aegean.greek.bible.load_lxx() / search_lxx()."
        ),
        extract=False,
        on_disk=("lxx-corpus.json.gz",),
    ),
    # Calfa-GREgORI Patrologia Graeca (CGPG, LREC 2026, CC BY 4.0): 33 digitized Migne PG
    # volumes (~6.79M Greek words, automated OCR of 19th-century prints), including 9 major
    # biblical commentary volumes (Cyril of Alexandria, Procopius of Gaza, Photius, Oecumenius,
    # Theophylact of Bulgaria). Fetched on demand, never bundled.
    "patrologia-graeca-corpus": DataSpec(
        name="patrologia-graeca-corpus",
        url=(
            "https://github.com/ryanpavlicek/pyaegean/releases/download/"
            "patrologia-graeca-corpus-v1/patrologia-graeca-corpus.json.gz"
        ),
        sha256="3026b578589d5b40eb4a9df14a3bcc8a901727b27eb87571a9d0db6231a6ed5b",
        license="CC BY 4.0 (CGPG — UCLouvain GREgORI & Calfa, Vidal-Gorène & Kindt, LREC 2026); fetched, never bundled",
        note=(
            "Patrologia Graeca corpus (~23.5 MB gzip): 33 Migne PG volumes (6.79M Greek words, OCR), "
            "including 9 biblical commentary volumes (Cyril of Alexandria, Procopius of Gaza, Photius, "
            "Oecumenius, Theophylact of Bulgaria). Load via aegean.load('patrologia') or bible commentaries."
        ),
        extract=False,
        on_disk=("patrologia-graeca-corpus.json.gz",),
    ),
    # Open Apostolic Fathers (Tauber & Macdonald, CC BY-SA 4.0): 15 twice-hand-corrected
    # Greek Apostolic Fathers works (1-2 Clement, Ignatius 7 epistles, Polycarp, Didache,
    # Barnabas, Shepherd of Hermas, Martyrdom of Polycarp, Diognetus).
    "apostolic-fathers-corpus": DataSpec(
        name="apostolic-fathers-corpus",
        url=(
            "https://github.com/ryanpavlicek/pyaegean/releases/download/"
            "apostolic-fathers-corpus-v1/apostolic-fathers-corpus.json.gz"
        ),
        sha256="579a20efed447535fe04a8e515ea8a3be7e9f18f9b281b2f9ecec226cee26bf6",
        license="CC BY-SA 4.0 (Open Apostolic Fathers — James Tauber & Seumas Macdonald, Zenodo 10.5281/zenodo.2555673); fetched, never bundled",
        note=(
            "Open Apostolic Fathers Greek corpus (~1.0 MB gzip): all 15 hand-corrected works "
            "(64,944 tokens: 1–2 Clement, Ignatius, Polycarp, Didache, Barnabas, Hermas, Diognetus). "
            "Load via aegean.load('apostolic-fathers')."
        ),
        extract=False,
        on_disk=("apostolic-fathers-corpus.json.gz",),
    ),
    # Online Critical Pseudepigrapha (OCP, CC BY 4.0): 44 Greek Second Temple & Old Testament
    # Pseudepigrapha texts (1 Enoch, Psalms of Solomon, Testaments of the 12 Patriarchs,
    # Testament of Job, Testament of Solomon, Letter of Aristeas, Sibylline Oracles, etc.).
    "pseudepigrapha-corpus": DataSpec(
        name="pseudepigrapha-corpus",
        url=(
            "https://github.com/ryanpavlicek/pyaegean/releases/download/"
            "pseudepigrapha-corpus-v1/pseudepigrapha-corpus.json.gz"
        ),
        sha256="2138ba25146a145aebdcf5719d08e1b87a895ed42774e2e849ecd066a34513e3",
        license="CC BY 4.0 (Online Critical Pseudepigrapha — Ken M. Penner et al., pseudepigrapha.org); fetched, never bundled",
        note=(
            "Greek Old Testament Pseudepigrapha & Second Temple corpus (~2.7 MB gzip): 44 works "
            "(171,306 tokens: 1 Enoch, Psalms of Solomon, Testaments of the 12 Patriarchs, "
            "Testament of Job/Solomon/Abraham, Aristeas, Joseph & Aseneth, Sibylline Oracles, etc.). "
            "Load via aegean.load('pseudepigrapha')."
        ),
        extract=False,
        on_disk=("pseudepigrapha-corpus.json.gz",),
    ),
    # Inscriptions of Aphrodisias 2007 (IAph2007, King's College London, CC BY 2.5):
    # 1,471 Greek EpiDoc inscriptions from Aphrodisias in Caria (Western Asia Minor).
    "aphrodisias-corpus": DataSpec(
        name="aphrodisias-corpus",
        url=(
            "https://github.com/ryanpavlicek/pyaegean/releases/download/"
            "aphrodisias-corpus-v1/aphrodisias-corpus.json.gz"
        ),
        sha256="c092b29ebce79f77697b5d7b9d2506f35bfced2ef0d93ebeea25a85f5c15ff19",
        license="CC BY 2.5 (Inscriptions of Aphrodisias 2007 — Reynolds, Roueché & Bodard, KCL, http://insaph.kcl.ac.uk/); fetched, never bundled",
        note=(
            "Inscriptions of Aphrodisias Greek corpus (~0.5 MB gzip): 1,471 EpiDoc inscriptions "
            "(38,556 tokens) from Aphrodisias in Caria with editorial ReadingStatus. "
            "Load via aegean.load('aphrodisias')."
        ),
        extract=False,
        on_disk=("aphrodisias-corpus.json.gz",),
    ),
    # Cretan Institutional Inscriptions (Irene Vagionakis, Univ. Ca' Foscari, CC BY-NC-SA 4.0):
    # 600 Archaic-Hellenistic Greek EpiDoc inscriptions from Crete (7th-1st c. BCE).
    "crete-corpus": DataSpec(
        name="crete-corpus",
        url=(
            "https://github.com/ryanpavlicek/pyaegean/releases/download/"
            "crete-corpus-v1/crete-corpus.json.gz"
        ),
        sha256="4cb73c822f389b2d96d64bf3e70c2f79107d448e160a09f171767e99375204c3",
        license="CC BY-NC-SA 4.0 (Cretan Institutional Inscriptions — Irene Vagionakis, Univ. Ca' Foscari; NonCommercial, never bundled)",
        note=(
            "Cretan Institutional Inscriptions Greek corpus (~0.6 MB gzip): 600 Archaic–Hellenistic "
            "Cretan EpiDoc inscriptions (50,995 tokens, 7th–1st c. BCE). Load via aegean.load('crete')."
        ),
        extract=False,
        on_disk=("crete-corpus.json.gz",),
    ),
    # Byzantine & Early Modern Vernacular Greek Corpus (Public Domain / CC BY-SA 3.0):
    # 12 medieval & early modern vernacular Greek literary texts (12th-17th c.).
    "byzantine-corpus": DataSpec(
        name="byzantine-corpus",
        url=(
            "https://github.com/ryanpavlicek/pyaegean/releases/download/"
            "byzantine-corpus-v1/byzantine-corpus.json.gz"
        ),
        sha256="b640d24d14916045f26299b23368becfaa60cfb7336f623cebfc5a6d28b3b09f",
        license="Public Domain / CC BY-SA 3.0 (Wikisource & Kalonaros 1940; open-greek/byzantine-early-modern-corpus); fetched, never bundled",
        note=(
            "Byzantine & Early Modern Vernacular Greek corpus (~2.5 MB gzip): 12 texts (189,375 tokens, "
            "12th–17th c.: Digenes Akritas, Chronicle of Moreas, Ptochoprodromika, Poulologos, "
            "Apokopos, Erotokritos). Load via aegean.load('byzantine')."
        ),
        extract=False,
        on_disk=("byzantine-corpus.json.gz",),
    ),
    # Homer Multitext Project (hmt-2026a, CC BY-NC 4.0): normalized Venetus A Iliad (24 books)
    # and Homeric scholia (Venetus A main/interlinear/intermarginal/interior/exterior, Venetus B,
    # Escorial Upsilon 1.1). NonCommercial passes to the user; never bundled.
    "homer-scholia-corpus": DataSpec(
        name="homer-scholia-corpus",
        url=(
            "https://github.com/ryanpavlicek/pyaegean/releases/download/"
            "homer-scholia-corpus-v1/homer-scholia-corpus.json.gz"
        ),
        sha256="3d77c7dd44e11bd8e5c4865b2f091ba2a5f4459cdad06487aeb9a43ececa8502",
        license="CC BY-NC 4.0 (Homer Multitext Project, Center for Hellenic Studies; NonCommercial, never bundled)",
        note=(
            "Homer Multitext Venetus A Iliad & Scholia (~5.5 MB gzip): 54 documents (331,365 tokens; "
            "24 books Venetus A Iliad + Venetus A, Venetus B & Escorial Homeric scholia). "
            "Load via aegean.load('homer-scholia')."
        ),
        extract=False,
        on_disk=("homer-scholia-corpus.json.gz",),
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
            version="v3",
            url=(
                "https://github.com/ryanpavlicek/pyaegean/releases/download/"
                "isicily-corpus-v3/isicily-corpus.json"
            ),
            sha256="1aa0abb3a7f06c415599932f6b1de844aaab6f0b78ff12f79ab4842f3636063c",
            superseded="v4",
        ),
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
            version="v3",
            url=(
                "https://github.com/ryanpavlicek/pyaegean/releases/download/"
                "iip-corpus-v3/iip-corpus.json"
            ),
            sha256="d9b83daa0fb675c6cb45d9fe4ca66c10af96eef40976bb0b8816628bdc9692c7",
            superseded="v4",
        ),
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
            version="v3",
            url=(
                "https://github.com/ryanpavlicek/pyaegean/releases/download/"
                "iospe-corpus-v3/iospe-corpus.json"
            ),
            sha256="e89ef85a946eb5b3eceae3ad805c2d1a7ab621f5be53463fd1398fb8037d6971",
            superseded="v4",
        ),
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
            version="v3",
            url=(
                "https://github.com/ryanpavlicek/pyaegean/releases/download/"
                "igcyr-corpus-v3/igcyr-corpus.json"
            ),
            sha256="de1950e2543102bfe8bfacd09cdd3c1803328dc7981795066107392fc4165f75",
            superseded="v4",
        ),
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
            version="v3",
            url=(
                "https://github.com/ryanpavlicek/pyaegean/releases/download/"
                "edh-corpus-v3/edh-corpus.json"
            ),
            sha256="bcb5e4b5123cec47c725a116c291556c220252fe9cbee42a1b3f2d3715000965",
            superseded="v4",
        ),
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
            version="v3",
            url=(
                "https://github.com/ryanpavlicek/pyaegean/releases/download/"
                "papygreek-fold-v3/papygreek-fold.conllu.gz"
            ),
            sha256="de6874740b4e985c94b2e1677a2970f85a821011b1e6b8a01915410b4c6aa030",
            superseded="v4",
        ),
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
            version="v2",
            url=(
                "https://github.com/ryanpavlicek/pyaegean/releases/download/"
                "papygreek-fold-orig-v2/papygreek-fold-orig.conllu.gz"
            ),
            sha256="d920a0cd65ee7cf278f87f5a419e60f43d7680ef8d1b0564f94987fbb93afad2",
            superseded="v3",
        ),
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
            version="v2",
            url=(
                "https://github.com/ryanpavlicek/pyaegean/releases/download/"
                "papygreek-dev-v2/papygreek-dev-tagging.conllu.gz"
            ),
            sha256="81ece456f70e13a1ab3c2d95d94d3e7e466bc5f02971fb8c1715d2d65e2c96c4",
            superseded="v3",
        ),
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
            version="v2",
            url=(
                "https://github.com/ryanpavlicek/pyaegean/releases/download/"
                "papygreek-dev-v2/papygreek-dev-parse.conllu.gz"
            ),
            sha256="967d519526353eb0d709ab32102e057d6a6463b415025396847770f70faebec1",
            superseded="v3",
        ),
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
    "nt-editions": [
        HistoricalPin(
            version="v1",
            url=(
                "https://github.com/ryanpavlicek/pyaegean/releases/download/"
                "nt-editions-v1/nt-editions.json.gz"
            ),
            sha256="c538c2f5561da2e2a51d8c173e5db0b56b5d06cb75e6bd6f786709c0168a810d",
            superseded="v2",
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

