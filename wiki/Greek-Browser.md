# Greek Visual Corpus Browser (`aegean browse`)

`aegean browse` launches a local, zero-dependency loopback web reader over
pyaegean's Greek corpora, Biblical editions, Greek library collections,
Perseus/First1KGreek works, lexica, commentaries, and NLP pipeline.

Unlike `aegean workbench` (which serves the Aegean syllabic scripts workbench
for Linear A, Linear B, Cypriot, and Cypro-Minoan), `aegean browse` is built
for alphabetic Greek reading and grammatical inspection — and ships inside the
core wheel with no Node.js runtime or extra web framework dependencies.

```bash
aegean browse                        # opens bundled John 1:1-18
aegean browse "Gen 1:1-5"            # bundled Septuagint Genesis sample
aegean browse greek                  # bundled classical/koine Greek samples
aegean browse "John 1:1-18" --neural # pre-activate grc-joint-v3 ONNX neural pipeline
aegean browse isicily --doc 0        # open a fetched epigraphic corpus
aegean browse ogc002060              # open an Open Greek Corpus work
aegean browse mytext.txt             # open a local UTF-8 Greek text file
```

From Python (`import aegean`, no `[cli]` extra required):

```python
import aegean

# Blocking server (opens system browser; Ctrl-C stops cleanly)
aegean.browser.serve("John 1:1-18")

# Non-blocking handle for notebooks or scripts
srv = aegean.browser.create_server("greek", port=8765, open_browser=False)
print(srv.url)
srv.stop()
```

From the terminal UI (`aegean tui`), press **`v`** (or open the Command Palette
with `ctrl+p` → **Launch Greek Visual Browser**) to start the local browser on
the currently open corpus or passage.

---

## CLI options

| Option | Default | Effect |
|---|---|---|
| `target` (positional) | `John 1:1-18` | Initial corpus id (`greek`, `nt`, `lxx`, `isicily`, …), NT/LXX reference (`"John 1:1-18"`, `"Gen 1:1-5"`, `"MT Ps 23"`), Greek collection work id (`ogc002060`), *Patrologia Graeca* volume (`PG073`), or local file path. |
| `-p`, `--port INT` | `8765` | Local HTTP port. |
| `--auto-port` / `--no-auto-port` | `--auto-port` | Pick the next free port automatically if `--port` is in use. |
| `--no-browser` | off | Print the local URL without opening a system browser window. |
| `--neural` | off | Pre-activate the opt-in ONNX neural Greek pipeline (`grc-joint-v3`) on startup. |
| `--offline` | off | Serve strictly from bundled and cached data without fetching missing corpora. |
| `-e`, `--edition TEXT` | `nestle1904` | Default Greek NT edition (`nestle1904`, `sblgnt`, `srgnt`, `bhp`, `tisch`, `wh`, `byz`, `antoniades`, `tr`). |
| `-d`, `--doc INT` | `0` | Initial document index for multi-document corpora. |
| `--host TEXT` | `127.0.0.1` | Loopback interface to bind. Non-loopback hosts are rejected. |

---

## Interface overview

The browser renders a three-pane scholarly reader:

1. **Left sidebar — Corpus, Works & Library Navigation**
   - **Quick targets & corpora:** bundled and cached Greek corpora, NT/LXX
     passage bar (with Masoretic/LXX Psalm mapping), and local text paste/upload.
   - **Collections & Catalog:** search across all 3,844 categorized Greek library
     works (8 collections) and 1,778 Perseus/First1KGreek works.
   - **Library Manager tab:** unified local asset manager with live disk usage,
     store path, **Datasets** vs. **Packs** segmented views, status pills
     (`bundled`, `installed`, `available`), category filters, one-click
     **Download** / **Install Pack** / **Open** / **Activate Lexicon**, and
     two-click **Remove** (`POST /api/library/remove`) for cached files.

2. **Center pane — Interactive Greek Text Reader**
   - **Interlinear toggle:** inline word-by-word lemma, POS, and glosses
     (Dodson, Extended Strong's, or active LSJ/Middle Liddell/Cunliffe/Autenrieth/Abbott-Smith
     lexica).
   - **Parallel translations & NT editions:** align bundled or fetched translations
     and compare across 9 Greek NT editions (`compare_editions`) and 13 early
     manuscript witnesses (`01`–`05`, `032`, `P45`–`P75`).
   - **Hover & click highlighting:** hovering over a token highlights the word
     and, when parsed, its syntactic head and dependents; clicking pins the word
     in the right inspector.
   - **Tools bar:** live NLP engine toggles (baseline vs. neural `grc-joint-v3`,
     OOV reranker, calibration registry, lexica), metrical scansion overlay
     (all 10 supported metres), FTS5 search, and CoNLL-U / CSV / JSON export.

3. **Right pane — Parallel Word, Lexicon, Context & Stats Inspector**
   - **Grammar:** surface form, lemma and `LemmaSource`, UPOS, UD FEATS / XPOS,
     dependency head and relation, syllabification, accentuation, reconstructed
     Attic/Koine IPA, sandhi/crasis expansion, and rarity metrics.
   - **Lexicon & Strong's:** Dodson gloss, Extended Strong's number and
     etymological root tree, active multi-lexicon entries (LSJ, Abbott-Smith,
     Cunliffe, Autenrieth, Middle Liddell) with Logeion links, and an on-demand
     **Load NT & LXX Concordance** action (`word_study`) so word clicks stay
     instant on high-frequency particles.
   - **Context:** patristic commentaries matched to the current Biblical book
     (112 Greek commentaries across Chrysostom, Cyril, Origen, *Catenae*, and
     *Patrologia Graeca*) and classical work metadata / parallel editions.
   - **Stats:** token, lemma, and UPOS distributions for the open passage or document.

---

## Security & loopback guarantees

- The server binds **only** to loopback (`127.0.0.1`, `localhost`, or `::1`);
  attempting to pass a non-loopback host raises `ValueError`.
- State-changing endpoints (`POST /api/engine`, `POST /api/lexicon/activate`,
  `POST /api/library/fetch`, `POST /api/library/remove`) verify same-origin
  loopback headers and never delete bundled core data.
- Passing `--offline` disables all remote fetches from the UI and API.

---

## See also

- [`aegean.browser` API reference](https://pyaegean.xyz/api/browser/) — Python
  server and JSON payload functions.
- [The CLI](CLI) and [CLI Cheatsheet](CLI-Cheatsheet) — `aegean browse` alongside
  the rest of the CLI.
- [The TUI](TUI) — launching the browser from `aegean tui` with `v`.
- [Biblical & Koine Greek](New-Testament) and [Greek NLP](Greek-NLP) — underlying
  editions, lexica, commentaries, and NLP backends.
