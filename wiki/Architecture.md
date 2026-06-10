# Architecture

pyaegean is built in **strict, downward-only layers**. Higher layers import
lower ones; the core never imports a script.

```
L6  ai (aegean.ai)        provider-agnostic LLM clients + grounded capabilities
L5  translate             hybrid: lexicon/morphology grounding → LLM
L5  greek (aegean.greek)  Greek NLP pipeline (normalize/tokenize/syllabify/…)
L4  io · geo · data      aegean.io (EpiDoc/CSV/Parquet export) · aegean.geo (GeoDataFrame) · bundled registry + cache
L3  analysis              distance · align · morphology · collocation · patterns
                          · query · accounting · structure
L2  scripts (plugins)     lineara · linearb · cypriot · cyprominoan · greek
L1  core                  Corpus · Document · Token · Sign · SignInventory ·
                          Numeral · Script(ABC) · Registry · Provenance
```

The Greek layer (L5) also hosts the **opt-in** backends — the AGDT treebank
(`treebank.py`), LSJ glossing (`lexicon.py`), the dependency parser (`syntax.py`),
the POS tagger (`tagger.py`), and the lemmatizers (`lemmatizer.py` and the neural
seq2seq backend `neural_lemmatizer.py`) — which fetch and build their artifacts
through the L4 **data/cache** layer (a `greek → data` edge); the strict
downward-only layering still holds.

## The core model (`aegean.core`)

Frozen `@dataclass(slots=True)` value objects; numpy/pandas lazy.

- **`Sign`** — one graphic unit (syllabogram, letter, logogram): `label`,
  `glyph`, `codepoint`, `phonetic`, `attrs`.
- **`Token`** — one unit in a document's text stream, with a `TokenKind`
  (`WORD`, `LOGOGRAM`, `NUMERAL`, `SEPARATOR`, `PUNCT`, `UNKNOWN`), decomposed
  `signs`, optional `line_no`/`position`.
- **`Document`** — one inscription/tablet/text: `id`, `script_id`, `tokens`,
  physical `lines`, `meta` (`DocumentMeta`: site/support/scribe/findspot/period/
  name/images). Properties: `.words`, `.numerals`, `.logograms`, `.line_tokens`.
- **`Corpus`** — the hub: `Corpus.load(script_id)` / `aegean.load(...)`,
  `.filter(**meta)`, `.get(id)`, `.word_frequencies()`,
  `.to_dataframe(level="document"|"token"|"word")`, `.to_dict()`, `.query(filters)`,
  `.to_json()` / `.from_json()` (lossless round-trip), `.provenance`.
- **`SignInventory`** — signs indexed by label / glyph / codepoint.
- **`Provenance`** — source/license/citation that travels with every corpus and
  stamps exports; `.cite()` returns a one-line citation.

## Scripts are plugins

A writing system is a plugin the core knows only by interface:

```python
from aegean.core.script import Script, register

class MyScript(Script):
    id = "myscript"
    name = "My Script"

    @property
    def sign_inventory(self): ...
    def tokenize(self, raw: str): ...

register(MyScript())
```

A corpus loader is registered separately via
`aegean.core.corpus.register_loader(script_id, fn)` so `aegean.load(script_id)`
works. The core never imports scripts (no cycles); `aegean/__init__` imports
`scripts` to register the built-ins (Linear A, Greek).

Access registered scripts:

```python
import aegean
aegean.registered_scripts()        # ['cypriot', 'cyprominoan', 'greek', 'lineara', 'linearb']
script = aegean.get_script("greek")
script.sign_inventory              # the Greek alphabet
script.tokenize("ἐν ἀρχῇ")          # [Token(...), ...]
```

## Conventions

- **The core has zero hard third-party deps.** `pandas` (optional `[data]` extra)
  and provider SDKs are **lazy-imported inside functions**; collocation stats are
  pure stdlib, so `import aegean` is instant and loads nothing heavy.
- **No large/binary assets** are bundled — that's what the
  [download-to-cache](Data-and-Provenance) layer is for. CI's
  `scripts/check_footprint.py` enforces import-clean, import-fast, and a
  code+JSON-only wheel.
- Every **exploratory** method (cross-linguistic distance, morphology
  clustering, accounting reconciliation, decipherment, AI readings) carries its
  caveat and is labeled unverified at point of use. The Linear A material is
  undeciphered — analysis is never presented as ground truth.
