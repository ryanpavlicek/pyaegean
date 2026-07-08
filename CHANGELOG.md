# Changelog

All notable changes to pyaegean are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and the project follows
[Semantic Versioning](https://semver.org/).

## 0.26.0 (2026-07-08)

The Greek subset of the Epigraphic Database Heidelberg.

### Added
- **`aegean.load("edh")`** — the **1,286 pure-Greek inscriptions** of the Epigraphic Database
  Heidelberg (Heidelberg Academy of Sciences and Humanities, **CC BY-SA 4.0**), extracted from the
  frozen (2021) EDH data dump. EDH is overwhelmingly Latin; this is its Ancient-Greek subset — the
  editions marked `xml:lang="grc"` — Imperial-period Koine (dedications, boundary and funerary
  texts, verse epitaphs), largely onomastic. Each document keeps its ancient place, date, modern
  find-place, and Trismegistos id (for cross-referencing). Because the EDH project has closed, this
  also preserves a corpus that will not be republished. Mirrored as a sha256-pinned release asset
  (fetched on demand, never bundled); attribution travels in the corpus provenance and `NOTICE`.
  Also fetchable as `aegean data fetch edh`.

### Fixed
- The TUI corpus overview now correctly reports the Greek-epigraphy corpora (I.Sicily, IIP, IOSPE,
  IGCyr, EDH) as **fetch-on-demand**, not bundled — previously they read as always-downloaded, so a
  screen could not prompt their fetch.

## 0.25.0 (2026-07-07)

The Greek inscriptions of Cyrenaica — archaic Doric and verse.

### Added
- **`aegean.load("igcyr")`** — the **997 Greek inscriptions** of Cyrenaica, from IGCyr²/GVCyr²
  (eds. C. Dobias-Lalou et al., Università di Bologna, **CC BY-NC-SA 4.0**), with a descriptive
  title, find-place, and date. This is a high-value dialect corpus: it includes the archaic
  epichoric **Doric** and the GVCyr metrical/**verse** subset, and its text preserves the epichoric
  letterforms (e.g. `ō`/`ē` for long o/e) — non-normalized Greek, valuable for dialect study.
  Mirrored as a sha256-pinned release asset (fetched on demand, never bundled); attribution travels
  in the corpus provenance and `NOTICE`. Also fetchable as `aegean data fetch igcyr`.

## 0.24.0 (2026-07-07)

More epigraphic Greek, and a preservation mirror.

### Added
- **Two more Greek-inscription corpora**, both fetched on demand and now **mirrored** in the
  pyaegean repo (a preservation hedge against the upstream sources going offline):
  - **`aegean.load("iip")`** — the **2,113 Greek inscriptions** of IIP (Inscriptions of
    Israel/Palestine, Brown University, **CC BY-NC 4.0**), with find-place and coordinates. Adds
    regional and late-antique Greek epigraphy (much of it in majuscule, as inscribed).
  - **`aegean.load("iospe")`** — the **1,194 Greek inscriptions** of IOSPE (Ancient Inscriptions of
    the Northern Black Sea, King's College London, data **CC BY**): Tyras, Olbia, Chersonesos, and
    Byzantine texts, with find-place and date.

  Both are sha256-pinned release assets, never bundled; attribution travels in the corpus
  provenance and `NOTICE`. Also fetchable as friendly stems (`aegean data fetch iip` / `iospe`).

### Changed
- The terminal-setup docs now recommend the best **free** classicist Greek fonts for polytonic and
  epigraphic Greek — **New Athena Unicode** (the scholarly standard) plus the OFL **Gentium Plus**,
  **Cardo**, and **GFS** families.

## 0.23.0 (2026-07-07)

Epigraphic Greek: the I.Sicily inscriptions.

### Added
- **The I.Sicily Greek-inscriptions corpus** (`aegean.load("isicily")` / `aegean info isicily` /
  `aegean data fetch isicily`). I.Sicily (ISicily/ISicily, **CC BY 4.0**) is an EpiDoc corpus of
  the inscriptions of ancient Sicily; pyaegean now hosts the **2,855 primary-Greek texts** — their
  Greek reading extracted from each inscription's primary edition (line breaks resolved,
  abbreviations expanded, restored/uncertain letters kept, lost gaps and symbols dropped) with the
  ancient find-place, date, and coordinates. This adds **epigraphic** Greek (real inscriptions on
  stone) alongside pyaegean's literary (Perseus) and New Testament Greek. Fetched on demand,
  sha256-pinned, never bundled; CC BY attribution to I.Sicily travels in the corpus provenance and
  `NOTICE`. Also fetchable as the friendly stem: `aegean data fetch isicily`.

## 0.22.0 (2026-07-07)

Manage downloaded Greek works, and a friendlier Linear B data path.

### Added
- **Delete downloaded Greek works.** `aegean greek works --remove <id>` removes one work,
  `--remove-author <name>` removes every downloaded work by an author, and `--remove-all`
  clears them all (the only way a fetched work leaves disk; re-fetch with `aegean greek work
  <id>`). In the TUI Works library, `x` removes the highlighted downloaded work. Library:
  `greek.remove_fetched_works(ids=…, author=…, remove_all=…)`.

### Changed
- **A friendly Linear B corpus path.** `aegean data fetch damos` now works directly (dataset
  stems resolve, so you no longer need the `-corpus` suffix — `nt`, `sigla` too). `data fetch
  linearb` no longer hits a bare "no pinned URL" wall: it points you at **DAMOS** (a ready,
  directly-fetchable corpus, ~5,900 tablets, CC BY-NC-SA 4.0), is honest that **LiBER** is
  browse-only (liber.cnr.it has no public download or API and is rights-restricted), and shows
  how to import your own licensed export. `data remove` accepts the same stems.

## 0.21.0 (2026-07-07)

Analyze a line while you read it, in the TUI.

### Added
- **In-reader line analysis.** With the corpus reader focused, `↑`/`↓` (and PgUp/PgDn,
  Home/End) move a highlighted **line cursor**, and `Enter` or `a` opens an **analysis
  popup** for that line. The analyses offered fit the line's script:
  - **Greek** (alphabetic Greek, the NT, fetched Greek works): the **offline parser/tagger**
    (instant), the **neural pipeline** (best-in-class tags + a dependency parse; needs the
    `[neural]` extra and downloads the model on first use), **IPA**, and **translation**.
  - **Linear B / Cypriot** (deciphered): the **Greek reading + gloss** and the **sign values**.
  - **Linear A / Cypro-Minoan** (undeciphered): the **sign glyphs** and, for Linear A, an
    **exploratory transliteration** — both plainly labelled as not a reading.

  **Translation is optional and BYOAI-gated**: it appears only when a provider API key is
  configured (e.g. `OPENAI_API_KEY`), and the popup says so otherwise rather than pretending
  to translate. The neural and translation runs happen on a background worker, so the UI never
  blocks. Esc closes the popup.

## 0.20.6 (2026-07-07)

### Changed
- **The TUI corpus reader now shows a focus highlight.** When you Tab to the reading pane it
  carries a "reading" border title and its border turns accent-coloured, so it is obvious the
  reader is active (and that the arrow keys will scroll it) without having to test-scroll. The
  corpus list's border likewise highlights when it holds focus.

## 0.20.5 (2026-07-07)

The TUI command console now shows the CLI hints the REPL shows.

### Fixed
- **Predictive completion now includes subcommands.** The ghost-text completion offered only
  top-level commands: `greek scan`, `data fetch`, `analyze clusters` and the rest never
  completed, because the sub-group check used `isinstance(cmd, click.Group)` and typer's
  `TyperGroup` is not a `click.Group`. It now duck-types the same way the REPL completer does,
  so typing `greek sc` suggests `greek scan`.

### Changed
- **The console prints the command map on entry**, exactly like `aegean repl`, so the available
  commands are visible up front instead of only surfacing as you type. The intro line advertises
  the directives: `Tab/→` completes, `↑/↓` recalls history, `:examples` prints starter lines,
  `:help` reprints the menu.

## 0.20.4 (2026-07-07)

Fixes for TUI layout collisions where widgets landed on the same row as the Header or Footer
and were painted over.

### Fixed
- **The command console prompt is now visible.** It was docked to the bottom on the same row
  the Footer occupies, so the Footer painted over it: the cursor, the typed text, and the ghost
  completion were all hidden, even though the input was working. The prompt now sits on its own
  row just above the Footer. (This completes the console fix begun in 0.20.3, which stopped a
  stray key from quitting the app but left the prompt hidden.)
- **The Works library action buttons are back on screen.** The table over-expanded and pushed
  the "Fetch selected", "Fetch all by author", and "Open" buttons off the bottom of the screen,
  below the Footer. The table now fills only the space above the buttons.
- **The Greek workbench input no longer overlaps the header.** It was docked to the top on the
  Header's row; it now flows just below the Header.

## 0.20.3 (2026-07-07)

A TUI command-console input fix.

### Fixed
- **The TUI command console now captures every keystroke.** If focus ever drifted off the
  prompt (a click on the output, or a terminal focus quirk), a bare letter fell through to a
  global shortcut instead of being typed — pressing `q` quit the whole app. The prompt now
  holds focus reliably (the output pane can no longer take it), and any stray key re-focuses
  the prompt rather than triggering a shortcut, so typing a command always works. `Esc` still
  leaves the console.

## 0.20.2 (2026-07-04)

More follow-up fixes to the TUI, and a documentation ordering improvement.

### Fixed
- **Downloaded Greek works are now permanent, selectable items in the TUI corpus browser.**
  Opening a fetched work (say the Iliad) previously loaded it transiently: it vanished the
  moment the selection changed. Every downloaded work now appears in the left list as its own
  entry (`author — title (Greek work)`), stays highlighted when open, and reloads when chosen —
  clearly distinct from the bundled "greek" sample-texts corpus.

### Changed
- In the TUI works library, **Enter** on a highlighted work opens it, the same as the `o` key.
- On the **Benchmarks** and **Methodology** wiki pages and in `docs/benchmarks.md`, the "what the
  metrics mean" section now comes before the score tables, so the terms are defined before the
  numbers that use them.

## 0.20.1 (2026-07-04)

Follow-up fixes to the 0.20.0 CLI/REPL/TUI work.

### Fixed
- **GitHub token discovery.** Fetching Greek works now finds a token in the `GH_TOKEN`
  environment variable and, when no token variable is set, falls back to the GitHub CLI's
  stored auth (`gh auth token`) — so a machine already authenticated with `gh auth login`
  hits the 5,000/hour rate limit automatically, without exporting anything. The rate-limit
  message names all the ways to authenticate.
- **The TUI document reader could not scroll.** A long document (a whole Iliad book) was
  clipped to the visible height with no way to see the rest. The reader is now a scroll
  container in the Tab cycle: Tab focuses it, then the arrow keys, PageUp/PageDown, and the
  mouse wheel move through the text.

### Changed
- **The TUI command console reads like a shell.** The boxed input is now a borderless
  `aegean>` prompt line with predictive command completion (Tab or → accepts the ghosted
  suggestion) and up/down history recall.
- **The TUI home screen is clearer.** The corpus list is framed as a menu, opens focused with
  the first entry highlighted (so ↑/↓/Enter work immediately), and the intro and key legend
  distinguish the tools the keys open (the Greek workbench, `g`) from browsing a corpus.

## 0.20.0 (2026-07-04)

A CLI/REPL/TUI usability and parity release: the terminal UI reaches feature parity with the CLI,
the Greek work library becomes first-class in the TUI, and a set of reported paper-cuts are fixed.

### Added
- **`aegean greek work all AUTHOR`** bulk-fetches every work by an author (case-insensitive),
  e.g. `aegean greek work all homer`, with `--dry-run`, `--limit`, a confirmation for large sets,
  idempotent resume, and clear guidance when the unauthenticated GitHub rate limit is reached.
- **`aegean greek works --downloaded`** lists the Greek works already in the local cache, and a
  single `aegean greek work <id>` now states whether it was downloaded or already cached, and where.
- **`aegean greek nt BOOK [PASSAGE]`** takes the chapter or range as a positional and renders the
  passage text: `aegean greek nt John 1`, `aegean greek nt Matt 1-3`. `aegean show` reads chapter
  ranges too (`show nt "Matt 1-3"`), and a dotted reference resolves (`show nt "Matt.1"`).
- **`aegean repl`** shows the command menu on startup, the same map bare `aegean` prints.
- **The terminal UI (`aegean tui`) reaches CLI parity and grows:** a **Works library** (`w`) to
  search the ~1,800-work catalogue and fetch a work or a whole author and open it; a **command
  console** (`:`) that runs any `aegean` command with full CLI/REPL parity; the corpus browser now
  opens fetched Greek works and files; a live-preview, persistent **theme picker** (`t`); a **help**
  overlay (`?`); **Esc** to exit an input or go back to the previous screen; and an Attic/Koine IPA
  selector in the Greek workbench.
- A richer offline Greek sample: the bundled New Testament sample is now two chapters, **John 1 and
  Philemon 1** (Nestle 1904, CC0), fully annotated.
- New wiki pages: **Benchmarks**, **Methodology**, **TUI**, **MCP server**, **New Testament**,
  **Evaluation**, and **Translation**, with a restructured sidebar. The benchmark and methodology
  material is now readable directly in the wiki rather than only in the repository.

## 0.19.16 (2026-07-04)

A scholarly-correctness pass ahead of a review by university professors of Ancient Greek: a
14-lens philology panel (metrical scansion, accentuation, morphology, reconstructed phonology,
dialect, Beta Code, the Greek shown in the docs, Linear B, Cypriot, the undeciphered-script
honesty framing, benchmark methodology, provenance, and framing), each finding independently
verified. The core philological surface came back clean; six localized defects are fixed.

### Fixed
- **Linear B lexicon — the reading `O-KA` = ἔχω "to hold" was a fabrication** and is removed.
  ἔχω is written *e-ke* (which the lexicon already carries correctly); *o-ka* is the distinct
  word of the Pylos "o-ka tablets", whose Greek reading is not securely established, so the
  bridge now returns an honest miss rather than a confident wrong equation.
- **Linear B lexicon — `A-PI-QO-TO`** kept its correct sense (a round, rimmed table) but was
  lemmatized as ἀμφίβροτος, the Homeric shield-epithet ("man-covering"), a mis-etymology. The
  lemma now records the honest analysis (ἀμφί- with the root of βαίνω, "go round"; no attested
  Classical form).
- **Lemmatizer — first-declension masculine `-ης` genitives** (προφήτου, Ἰωάνου, Ἡρῴδου) no
  longer fabricate a confident `-ος` non-word. The `-ου` ending cannot be told from the
  second-declension genitive, so for the common such nouns the strip is suppressed to an honest
  miss (72 confident-wrong lemmas removed on the full New Testament; all 4,275 genuine `-ος`
  genitives preserved; published accuracy unchanged).
- **Lemmatizer — a neuter carrying the acute an enclitic throws onto its ultima** (δῶρόν, as in
  δῶρόν ἐστιν) is now read as the neuter δῶρον, not the non-word `*δῶρός`; a grave-accented
  neuter (ἱερὸν) normalizes to its citation form.
- **Provenance — the UD Ancient Greek evaluation folds carry different licenses**:
  UD-Perseus is CC BY-NC-SA 2.5, UD-PROIEL is CC BY-NC-SA 3.0 (each per its own README at the
  pinned commit). The blanket "3.0" is corrected across the code and docs, and the version is
  now recorded per treebank.

## 0.19.15 (2026-07-04)

The Cypriot loader now decodes the rest of the IG XV 1 Leiden apparatus, completing the
apparatus handling begun in 0.19.9.

### Fixed
- **Illegible-sign marks are no longer read as syllabograms.** A Leiden dot on the line
  (`..`, one dot per illegible sign), a figure-dash filling a lost-sign slot in a lacuna, and
  an unread `?` previously appeared as literal "signs" inside a word (`i-te-o-..-..-..-ja`
  produced signs including `..`), and such a token could be marked `CERTAIN`. Each now marks a
  sign whose reading is not preserved: it is kept in the token text (to show the position) but
  dropped from the sign list, the token reads `UNCLEAR` (or `LOST` when the whole token is
  illegible marks), and a marker attached to a legible sign (a trailing period, an `?`) is
  stripped off the label. A retrograde arrow `↓` is recorded as a writing-direction marker,
  not a sign. The raw marked form is kept in `annotations["leiden"]` and the inscription
  `paritySha256` is unchanged (no text field changed — the fix is in the loader).

## 0.19.14 (2026-07-04)

An Ancient Greek scholarly-correctness pass, verifying the Greek against the standard
references (Smyth, LSJ, West, Ventris-Chadwick) and correcting ten confirmed errors. Metrical
scansion, reconstructed pronunciation, Beta Code, and the Greek examples shown in the
documentation were all checked and found correct.

### Fixed
- **Accent placement.** An oxytone noun/adjective now takes the circumflex in the genitive and
  dative when the ultima is long (θεός → gen. θεοῦ, dat. θεῷ; τιμή → τιμῆς, τιμῇ), per Smyth
  §163a; and the πόλις/πῆχυς type keeps its antepenult accent in the -εως/-εων genitive
  (πόλεως, not πολέως), per Smyth §275.
- **Syllable quantity.** A vowel before a double consonant ζ/ξ/ψ is now correctly heavy by
  position (ὄζος, τάξις; Smyth §144); the word-level prosody agrees with the line-level
  metrical scanner, which already applied the rule.
- **The offline lemmatizer no longer fabricates a non-word.** The augmented thematic aorist/
  imperfect in -ον (εἶπον, ἦλθον, ἔλαβον), the -όω contract verb 3sg in circumflexed -οῖ
  (δηλοῖ, σταυροῖ), the genitive/dative of a common second-declension neuter (ἔργου, δώρου),
  and the ψ/ξ sigmatic future (γράψει, διώξει) were each stripped to a confident but spurious
  -ος/-ω lemma; they now return an honest miss instead. Measured on the full Nestle 1904 New
  Testament, this removes 618 confidently-wrong lemmas without losing a single correct one.
- **Two Linear B lexicon readings corrected**: `po-ni-ki-ja` is φοινίκια "crimson" (not the
  ethnonym Φοίνικες), and `ki-ti-me-na` is the land-tenure participle κτιμένα (not the Homeric
  compound ἐϋκτίμενος), per Ventris-Chadwick.
- **Dictionary glossing** strips a leading grammatical/morphological note ("gen.", "Imp. pl.",
  "Epic also", "Root", "not used in pl.") so the actual English sense surfaces, instead of
  emitting the note as the meaning (φέρω → "carry", not "Imp. pl").

### Added
- **Propagation-parity safeguards** (`tests/test_propagation_parity.py`): for each bug class
  that has recurred as a fix applied to one site but not its siblings, a test now enumerates
  every sibling and asserts the invariant across all of them (the double-consonant quantity
  rule shares one source between prosody and meter; every script's phonetic bridge strips the
  Leiden underdot and folds case; every provider adapter wraps a call failure; every MCP corpus
  tool returns a structured error; every export is atomic; every cache/hash key is injective).
  Adding a sibling that lacks the fix now fails a test in the same commit. In passing this made
  the Anthropic and OpenAI adapters wrap a transport failure and the Linear A phonetic bridge
  strip the underdot, matching their siblings.

## 0.19.13 (2026-07-04)

A documentation-freshness pass: every documentation code block was re-run against the current
code and the shown outputs that had drifted were corrected. No library behaviour changed.

### Fixed
- **Corrected drifted example outputs in the wiki.** Several shown results were stale after
  earlier releases: the Linear A assigned-sound-value count (now 50, after ZE/ZO were read in
  0.19.8) on the Limitations page, the bundled `signs.json` byte size and the corpus JSON length
  on the Data-and-Provenance and Architecture pages, and the tie-order of the `dispersion` and
  `cooccur` example tables (both are deterministic; the docs showed the pre-0.19.6 order). The
  documented outputs now match the current code.
- Added regression guards that pin the documented `dispersion` and `cooccur` outputs and the
  Linear A sound-value count, so a future change that alters them fails a test and the
  documentation is updated in the same commit.

## 0.19.12 (2026-07-04)

A security and robustness pass over the untrusted-input surfaces: the parsers, importers, the
fetch/cache layer, and the work-fetch path handling of a hostile file or a crafted argument.
Six hardening fixes, each pinned by a regression test.

### Fixed
- **EpiDoc import is linear, not quadratic.** A deeply nested TEI document made the importer
  O(tokens x depth), so a small hostile-but-well-formed file could hang `aegean import --epidoc`
  for minutes on one CPU. The apparatus-membership and reading-status lookups are now
  precomputed in single passes, so parsing is linear (a large nesting that took seconds now
  takes a fraction of a second) with identical output.
- **Loading a prebuilt index caps its decompressed size.** A `.json.gz` lexicon/model index is
  decompressed with a size limit, so a swapped mirror (when a `PYAEGEAN_<NAME>_URL` override
  disables the checksum) cannot inflate a tiny file into gigabytes and exhaust memory.
- **`load_work` rejects a path-like work id.** A work id containing a path separator or `..` is
  refused, so a crafted id cannot escape the pinned Perseus repository and fetch a forged
  edition from an arbitrary source. (The MCP tool already did this; the guard now covers the
  CLI and the Python API too.)
- **A malformed corpus file fails cleanly at load.** `Corpus.from_json` / `from_dict` now
  validate that each line's token indices are in range and raise a clear error naming the
  document, instead of loading a corrupt object that crashes later with a bare `IndexError`.
- **The analysis cache is hardened.** Its file is created owner-only, and enabling a cache in a
  directory writable by other users warns that a cached value is unpickled on read (a shared
  cache is a code-execution trust boundary); the documentation states this for the
  `PYAEGEAN_ANALYSIS_CACHE` redirect.
- **EpiDoc import records only the file name in provenance.** The importer stamped the full
  absolute import path into the corpus provenance and every citation, leaking the user's
  directory layout into a shared export; it now uses the basename, like the other importers.

## 0.19.11 (2026-07-04)

A propagation audit: for each bug class already fixed at one site, every sibling site was
checked and the ones the fix had not reached were corrected. Eight fixes covering fourteen
sites, each pinned by a regression test.

### Fixed
- **Rebuilding a corpus database no longer risks the existing one.** `to_sqlite` (and
  `aegean db build` / `aegean export --format sqlite`) deleted the current `.db` before
  rebuilding, so a full disk or interruption mid-build left no recoverable file. It now builds
  into a temporary database and atomically replaces the target, so a failed rebuild leaves the
  prior database intact. The same temp-then-replace is applied to the JSON, CSV, Parquet, and
  EpiDoc exports, which likewise overwrote a prior file in place.
- **The Gemini provider wraps a network failure like the others.** A transport error (a
  dropped connection or timeout) is not a Gemini API-error subclass, so it leaked out of a call
  as a raw exception; it is now wrapped in `ProviderCallError`, matching the Anthropic and
  OpenAI adapters.
- **Every MCP corpus tool reports a fetch failure cleanly.** The shared corpus-loading helper
  did not catch a download failure, so a cold-cache `damos`/`sigla` fetch could leak a raw
  exception out of seven tools; it now returns the structured error the rest of the surface
  uses.
- **Cypriot transcription reads a damaged-but-legible sign correctly.** `word_to_phonetic`
  (and `analysis.compare.to_phonemes(..., "cypriot")`) now strips the Leiden underdot before
  the sign lookup, the fix Linear B already had.
- **Linear A transcription folds case.** `word_to_phonetic` now upper-cases before the lookup,
  so the standard lowercase transliteration reads the Q- and Z-series (`qa-de` → `kwade`)
  instead of falling through to raw text, matching Linear B and Cypriot.
- **The offline lemmatizer no longer fabricates a present from a sigmatic future.** The guard
  that blocks the `-ει/-εις → -ω` strip on a sigmatic future (`δώσει`) now also covers the
  other thematic endings (`δώσομεν`, `δώσετε`, `δώσουσιν`), which were stripped to a confident
  wrong `-ω` lemma; genuine present verbs still resolve.
- **A stored sign inventory can no longer be corrupted by a caller.** The `sign_inventory`
  accessors returned a shared cached inventory whose per-sign `attrs` were live dicts, so an
  edit leaked into every later reader and a subsequent load; each accessor now returns an
  independent copy, matching `Corpus.copy`.
- **Building a prebuilt lexicon index leaves no orphaned download.** `fetch_prebuilt` copied
  the fetched file to the built-index name and left the original behind, uncounted and
  unremovable; a single-file dataset is now moved into place, so no redundant copy lingers.

## 0.19.10 (2026-07-04)

A regression audit of the recent fix churn: the areas most changed across 0.19.1 through
0.19.9 were re-examined for defects those changes introduced, alongside the code no prior pass
had touched. Five regressions and two pre-existing bugs fixed, each pinned by a regression test.

### Fixed
- **`aegean data remove` can delete every downloaded dataset again.** 0.19.1 taught `data list`
  and `doctor` to recognize a dataset stored under a different filename (a prebuilt lexicon
  index, an `agdt-derived` member) but left `remove` probing only the default location, so those
  five datasets showed as downloaded yet refused removal, and their disk space could not be
  reclaimed. `remove` now uses the same on-disk-aware lookup, so the two commands agree.
- **Opening a corpus from the command palette works while the corpus browser is already open.**
  A 0.19.1 cleanup removed the message the browser used to reload on an in-place selection change,
  so selecting a different corpus from the palette while already on that screen silently kept the
  old one displayed. The browser now reconciles to the new selection in that case too.
- **`clean_gloss` keeps a real meaning that begins with a derivation abbreviation.** The 0.19.2
  guard that drops bare grammatical-derivation pointers ("adverb of", "comp. of") was too broad
  and also discarded genuine glosses like "composed of", "control of", "advantage of", leaving
  those words ungrounded. The guard now matches only when the abbreviation is a whole token.
- **The analysis cache no longer crashes a worker mid-call when it is reconfigured.** After
  0.19.7 made the cache usable from worker threads, calling `cache.enable`/`cache.disable` from
  one thread could raise a "closed database" error in a memoized call running on another. A
  concurrent close now degrades to a cache miss (the value is recomputed), honoring the
  cache's never-changes-a-result contract.
- **`persistent_accent` places the accent correctly on imparisyllabic third-declension nouns.**
  A noun that gains a syllable in the oblique cases (σῶμα → σώματος, ῥήτωρ → ῥήτορος) had its
  accent anchored from the end of the word, landing it on the penult; it now tracks the stem
  syllable from the start and recedes to the antepenult as required.
- **Workbench import attaches each document's surface forms by id.** `from_workbench_export`
  paired glyphs/transcription/images to documents positionally, but a repeated id (e.g. two
  tablet sides labeled the same) collapses to one document, which shifted every later document's
  extras onto the wrong id and dropped the last one. Extras are now keyed by id.
- The stale "48 signs carry a sound value" figure on the Limitations page is corrected to 50
  (the ZE/ZO reading in 0.19.8), matching the rest of the documentation.

## 0.19.9 (2026-07-03)

A correctness pass over the surfaces the prior audit sweeps had covered least: the AI provider
and cache layer, the MCP dictionary tool, SQLite search, and the Linear B and Cypriot script
bridges. Seven defects fixed, each pinned by a regression test that reproduces the failure and
checks the corrected output.

### Fixed
- **`db.search` no longer crashes on a token stored without a position.** A token saved with
  `position=None` (a supported, round-tripped state since 0.19.4) crashed the search with a
  `TypeError` when it matched, in both token and substring modes, because the position was
  coerced with `int()`. The position is now returned as-is (`None` stays `None`; the return
  type is `(doc_id, int | None, text)`).
- **A provider that returns an empty response no longer leaks a raw `IndexError`.** An
  OpenAI-compatible gateway (notably OpenRouter) can return HTTP 200 with an empty `choices`
  list when an upstream vendor errors or a moderation filter fires. The adapter read
  `choices[0]` outside the error-wrapping block, so this surfaced as a bare `IndexError`
  instead of the clean `ProviderCallError` the rest of the AI layer raises; it now raises
  `ProviderCallError` (carrying any `error` payload the gateway sent).
- **The AI response cache key is injective.** The key joined its fields with a NUL separator
  and no length prefix, so a NUL in the system prompt or prompt could shift a field boundary
  and collide two logically distinct requests, serving one the other's cached completion. It
  now length-prefixes each field, the same fix `Corpus.fingerprint` uses. Cache files written
  by earlier releases still load; their entries simply miss under the new key and recompute.
- **The MCP `greek_gloss` tool returns a structured error on a dictionary fetch failure.** A
  first, cold-cache use of a hosted dictionary while offline (or on a network / HTTP / checksum
  failure) leaked a raw exception out of the tool instead of the `{"error": ...}` payload the
  rest of the MCP surface returns; it is now caught and reported in the structured form.
- **Linear B `word_to_phonetic` reads a damaged-but-legible sign correctly.** A sign carrying
  the Leiden underdot (U+0323, "damaged but legible") fell through to its raw transliteration
  instead of its settled phonetic value (so `pọ-me` transcribed as `pọme`, not `pome`). The
  underdot is now normalized away before the sign lookup, matching the sibling lexicon bridge;
  this also corrects `analysis.compare.to_phonemes` for such words.
- **The Cypriot loader decodes more of the IG XV 1 Leiden apparatus.** Erasure brackets `⟦⟧`
  (deleted by the scribe, still legible), editorial-insertion angle brackets `<>`, and
  abbreviation-expansion parentheses `()` previously leaked into sign labels and left the token
  mislabeled `CERTAIN`. They are now stripped from the emitted token and its signs (the marked
  form is kept in `annotations["leiden"]`) and mapped to the right status: `⟦⟧` reads
  `UNCLEAR`, `<>` reads `RESTORED`, and `()` reads `CERTAIN` (a secure reading).
- **Linear B EpiDoc import keeps a fully-uncertain word.** An apparatus `<app>` with variant
  `<rdg>` readings but no editor-preferred `<lem>` dropped the word entirely. It now emits a
  token (reading the first variant, flagged `UNCLEAR`, with the remaining variants as
  alternate readings).

### Changed
- The published CPU-throughput figure in `docs/benchmarks.md` is now explicitly framed as
  hardware-dependent and illustrative, not a pinned benchmark like the accuracy rows, with the
  dependency-drift trigger (a model or `onnxruntime` floor change) that warrants a re-measure
  named in the claims registry.

## 0.19.8 (2026-07-03)

A cross-repo sign-table reconciliation: the Linear A z-series signs **ZE** and **ZO** now read as
signs in both the bundled inventory and the Linear A Research Workbench, closing the last standing
data discrepancy between the two projects.

### Fixed
- **ZE and ZO now read as Linear A signs.** Both are securely attested z-series syllabograms
  (ZE 46 times, ZO twice in the bundled corpus), but each occurs only as a standalone single-sign
  word, so the workbench's hyphenated-word sign aligner never walked them and both projects had
  carried them as unreadable Unicode-chart entries with no sound value. They are now read from
  their own attestations: ZE maps to U+1063C (dze, confidence 1, unanimous across its 46
  attestations); ZO maps to U+1060E (dzo, confidence 0, the chart identity, its 2 attestations
  too short to align). The aligned/read-sign count moves 95 to 97 (manifest `signCount` 95 to 97),
  and the count of signs carrying an assigned sound value moves 48 to 50. The inscription-level
  parity contract (`paritySha256`) is unchanged, as it hashes the shared text fields and not sign
  phonetics, so the corpus the two projects share does not drift. Mirrored in the Linear A
  Research Workbench 1.6.1, whose rebuilt served app (`aegean workbench`) now embeds the 97-sign
  table.

## 0.19.7 (2026-07-03)

A concurrency and thread-safety pass: the surfaces real concurrent use touches (worker
threads, overlapping MCP calls, parallel CLI processes, shared caches) were driven under
aligned concurrent workloads and every reproducible failure fixed, each pinned by a
regression test.

### Fixed
- **The analysis cache is thread-safe.** Enabling it (`cache.enable()` or
  `PYAEGEAN_ANALYSIS_CACHE`) made every memoized analysis call from any other thread crash
  with a SQLite thread-identity error — including cache hits and even `cache.disable()`.
  The connection is now shared safely behind a lock, so threaded code behaves identically
  with the cache on or off, as the cache's contract promises.
- **A paid AI response can no longer be lost to a cache-write collision.** Concurrent
  `set()` calls on a shared persistent `ResponseCache` collided on one temp file (crashing
  on Windows with the response already received, discarding it). Each persist now uses a
  unique temp name behind a lock, and a failing disk write degrades to memory-only instead
  of raising out of `complete()`.
- **SQLite reads can no longer be torn by a concurrent append.** `from_sqlite` and
  `stream()` read each document's row and tokens in separate statements, so an
  `append=True` writer committing in between could yield a document whose metadata and
  tokens came from different versions — silently. Reads now run inside transactions
  (whole-load for `from_sqlite`, per-document for `stream`), two simultaneous appenders
  take the write lock before their bookkeeping reads, and a `search()` that lands in the
  append's FTS-rebuild window falls back to the exact-match path instead of raising.
- **Concurrent fetches of one dataset are serialized.** Two `fetch()` calls for the same
  dataset (threads or processes) shared one partial-download file and one extraction
  staging directory, corrupting each other; a per-dataset lock now serializes them — the
  later caller waits, then returns the completed artifact. `aegean data remove` refuses
  cleanly while a fetch holds the lock (and reports a file-in-use error as one line, not a
  traceback).
- **A TUI download can actually be cancelled.** `fetch()` gained an abort hook, polled
  between transfer chunks, and the TUI's download worker is wired to it: quitting the app
  no longer blocks until the download completes (the partial file stays resumable), a
  second fetch press while one runs is refused instead of starting a duplicate transfer,
  and a superseded corpus search no longer writes its stale result over the newer query's
  status line.
- **`aegean workbench` stops cleanly on Ctrl+C** even when a client holds an in-flight
  request it has stopped reading (handler threads no longer block shutdown).

## 0.19.6 (2026-07-03)

A compatibility, dependency-floor, and performance pass: artifacts were cross-tested against
earlier released versions, every declared dependency minimum was install-tested at its exact
floor, and the quantified performance statements were re-measured. Each code fix is pinned by a
regression test.

### Fixed
- **Every declared dependency floor is now a verified floor.** Several extras declared minimums
  that failed outright in a freshly resolved environment: typer 0.12–0.15 crashes with today's
  click (the CLI floor is now `typer>=0.16`); tokenizers below 0.20 cannot load the shipped
  neural models' tokenizer files (`tokenizers>=0.20`, and the loader now names that fix instead
  of surfacing a bare parser error); mcp below 1.2 lacks the server API (`mcp>=1.2`, and
  `aegean-mcp` now says "upgrade mcp" rather than pointing at an extra that is already
  installed); pandas, pyarrow, shapely, anthropic, and openai floors predated the numpy 2 /
  httpx 0.28 era and could not even import as resolved today (raised to `pandas>=2.2.2`,
  `pyarrow>=16.1`, `shapely>=2.0.4`, `anthropic>=0.40`, `openai>=1.55.3`).
- **`pip install "pyaegean[tui]"` now installs a working `aegean tui`.** The extra omitted the
  CLI dependencies the documented two-line quickstart needs; it now carries them. Independently,
  the environment report the TUI's data screen renders moved to a CLI-free module
  (`aegean._doctor`), so a Python-API launch without the CLI installed degrades gracefully
  instead of crashing the screen.
- **Word queries no longer pay for co-occurrence they don't use.** `run_query` built the full
  word co-occurrence map on every call; on the New Testament corpus that was ~4 s and over a
  gigabyte of allocations per query. The map is now built only when a `word-cooccurs-with`
  filter is present, with identical results.
- **Corpus-wide dispersion is now a single pass.** `dispersions()` recomputed Gries' DP with a
  full corpus scan per vocabulary item; on the DAMOS corpus that was ~11 s. A postings-based
  formulation with identical values brings it to well under a second.
- **Schema versions are now checked on load.** Every corpus artifact records a schema version
  that no reader ever consulted; `from_json`/`from_sqlite`/`stream` now refuse a file written
  by a newer schema with the fix named ("upgrade pyaegean"), while missing or older versions
  load normally.

### Documentation
- **Corrected the neural pipeline's CPU throughput.** The published ~450 words/s was measured
  on the earlier full-precision model; the shipped quantized bundle measures roughly
  20–70 words/s (sentence-length dependent). The quantization section now states the real
  trade-off — the ~3× size reduction costs CPU throughput, with the fp32 asset available where
  speed matters — and the figures are pinned in the claims registry.
- The extras table carries the corrected floors, and the `tui` row notes the CLI dependencies
  ride along.

## 0.19.5 (2026-07-03)

### Fixed
- **Databases written by earlier releases load again.** 0.19.4's token-order fix added a column
  that the reader then required, so a `.db` file written by 0.19.3 or earlier failed with
  "no such column: token_order". Reading an old file now orders by its stored `position` (the
  best an old file carries), and appending into one migrates it in place (the column is added
  and backfilled), so existing corpus databases keep working unchanged.
- The `Corpus.copy` docstring states the measured cost honestly (one pass over the tokens, on
  the order of 100–200 ms for the largest corpora), replacing a stale "a few milliseconds" claim.

## 0.19.4 (2026-07-03)

An executable-documentation, robustness, and property-testing pass: every code example in the
README and wiki was executed and compared to its shown output, the exposed input surfaces
(importers, CLI, the local workbench server, search) were probed with adversarial input, and the
round-trip invariants (JSON, SQLite, EpiDoc, Beta Code, tokenize/syllabify) were property-tested.
15 code defects fixed, each pinned by a regression test; 33 documentation examples re-measured
against the current code.

### Fixed
- **The SQLite round-trip preserves token order.** A token whose `position` was `None` (for
  example one appended to a document) moved to the front of the document on reload, and
  out-of-order positions were silently re-sorted, corrupting the document against the stored
  line structure. Tokens now carry an explicit order column, so `from_sqlite` returns exactly
  the list `to_sqlite` was given (`position` stays pure data).
- **The corpus fingerprint is collision-proof.** The content hash serialized fields with
  separator bytes, so a control character embedded in the data could make two different corpora
  hash identically (a wrong-answer risk for the analysis cache). Every field is now
  length-prefixed, making the serialization injective.
- **Robust input handling.** `db.search` no longer raises on a query containing a NUL (the
  token itself already stored fine); a 300-digit numeral no longer crashes the accounting sum
  (it reads as infinite and reports non-balancing); `aegean import --epidoc` reports malformed
  XML as a clean one-line error instead of a traceback; the import CLI's default encoding now
  strips an Excel byte-order mark, matching `from_csv`; piping a table-printing command into a
  reader that exits early (such as `| head`) no longer dumps a traceback on Windows; the local
  workbench server returns a clean 404 for a request with invalid percent-encoding instead of
  dropping the connection.
- **Greek edge cases.** A word with a doubled leading apostrophe now tokenizes consistently
  between `tokenize` and `tokenize_words`; a medial sigma before an epigraphic letter outside
  the Beta Code alphabet (digamma) no longer folds to final sigma on the round trip; a
  combining accent that cannot precompose onto a macron- or breve-marked vowel now stays with
  its vowel in syllabification and scansion instead of splitting the word. The Beta Code and
  EpiDoc round-trip caveats (combining length marks; XML whitespace normalization) are now
  documented where the round-trip claims are made.
- `ResponseCache` expands a leading `~` in its path, so a home-relative cache file lands under
  the user's home directory.

### Documentation
- **Every shown example output in the wiki was re-run against the current code** and corrected
  where it had drifted: the cross-script comparison and nearest-neighbour figures (the
  labiovelar `qa → kwa` romanization), corpus fingerprints, the Linear A metrology, dossier,
  and balance tables, the IG XV 1 corpus example, geography coordinates and GeoDataFrame
  shapes, the fetchable-assets list (three lexicon indexes were missing), the FAQ extras table,
  the `usage`/`rarity`/`nearest`/keyness CLI outputs, the plot-scansion example (its input now
  actually scans), and the Tutorial's morphology walk-through, which now shows the output a
  reader actually gets when following the page in order.

## 0.19.3 (2026-07-03)

A methodology-and-provenance audit: a third adversarial pass focused on the parts the earlier
sweeps did not reach, the correctness of the measured numbers, the evaluation methodology, and
the limitations documentation, plus live testing of the bring-your-own-AI providers. Every code
fix is pinned by an output-verifying regression test.

### Fixed
- **A provider API error now surfaces as the library's clean error.** A failed AI call (a bad
  model id, an invalid key, a rate limit, a network drop) leaked the underlying SDK exception as
  a raw traceback out of `translate()` / `ask()`. All provider adapters (Anthropic, the
  OpenAI-compatible OpenAI/Grok/OpenRouter path, and Gemini) now wrap the SDK error in a single
  `ProviderCallError` (an `AIError`), preserving the original as its cause.
- **The corpus fingerprint covers `signs`, `glyphs`, and `alt`.** The content hash that keys the
  analysis cache hashed each token's text, kind, status, and annotations but not its decomposed
  `signs`, so two corpora differing only in their sign labels hashed identically and a cached
  sign-level `dispersions()` / `keyness()` could return the first corpus's result for the second.
  All three fields now vary the hash.
- **BibTeX citations are LaTeX-safe.** `Provenance.bibtex()` emitted field values (a title, a URL
  with `&`/`%`, a subset note) without escaping, so the entry broke at compile (`%` comments out
  the line, `&` is an alignment error). Field values are now escaped.
- Removed an unused constant in the neural pipeline (`joint._TAG_HEADS`).

### Documentation — measured numbers and methodology
- **Re-measured the pure-Python baseline table** in `docs/benchmarks.md`: five of its six UD/PROIEL
  cells had drifted since the offline tagger/lemmatizer changed and were never re-measured (PROIEL
  UPOS was off by ~3.8 points). Updated to the current stack (Perseus UPOS 86.73 / UAS 37.43;
  PROIEL UPOS 78.83 / lemma 85.63 / UAS 35.41).
- **Corrected the UD lemma-scoring description:** on the UD folds lemmas are scored by exact string
  match with no normalization (the UD gold is already NFC and homograph-free); the NFC +
  homograph-digit clean-up applies only to the native-corpus NT/PROIEL checks.
- **Fixed unreconstructible or mismatched benchmark statements:** the out-of-domain parsing lead
  over a Perseus-trained baseline is ~23 UAS (82.47 vs 59.00), not ~17; the bootstrap CIs use 999
  resamples (the reproducible default); and the bring-your-own quantization evidence is recorded in
  a new `training/results/v3-quantize-report.json` (measured sizes and the lossless comparison).
- **`training/README.md` now describes what actually ships:** the release asset is the quantized
  `grc-joint-v3` (weight-only int8 + fp16, ~173 MB), produced from the fp32 `grc-joint-v2`
  reproducibility checkpoint; the "int8 failed the gate" note refers to the rejected full-int8
  activation recipe.
- **New plain-language metric definitions** in `docs/benchmarks.md`: what UPOS, XPOS, UFeats, Lemma,
  UAS, and LAS each measure, so the tables read without prior NLP background.

### Documentation — corpus and packaging facts
- Corrected stale limitations: the Cypriot corpus is the bundled 178-inscription IG XV 1 (not "two
  illustrative inscriptions"); Linear B accounting `balance_check` folds case and fires over the
  lowercase DAMOS corpus (since 0.15.0).
- The extras table gains the `tui` extra and the `all` extra is corrected to
  `ai,epidoc,geo,data,cli,viz,mcp,tui`.
- The bundled-JSON provenance table adds the two files it omitted (`cypriot/ig_inscriptions.json`,
  `greek/idioms.json`) and corrects two byte sizes, so it again matches `data.versions()`.
- Clarified the SigLA figure: 1,376 word-division groups load as ~1,868 WORD tokens.

## 0.19.2 (2026-07-03)

A deep correctness pass: a fresh adversarial audit surfaced 28 confirmed defects across the
Greek, Aegean-script, data, and interface layers, each reproduced and then fixed with an
output-verifying regression test.

### Fixed
- **Loaded corpora no longer share mutable per-token state.** Editing a token's `annotations`
  (or a sign's `attrs`) on one loaded corpus leaked into every other copy and every later
  `load()` of the same bundled corpus, and silently changed a fresh load's fingerprint (the
  analysis-cache key). `Corpus.copy()` now gives each token and sign an independent dict, so an
  edit stays isolated and the copy still fingerprints identically to the original.
- **The offline lemmatizer stops fabricating verbs.** The thematic `-ει/-εις → -ω` rule invented
  non-existent `-ω` verbs for third-declension noun datives (`πόλει → *πόλω`), sigmatic futures
  (`δώσει`), aorist-passive participles (`ἀποκριθείς`), and `-εί` indeclinables (`ἐπεί`), and
  marked them as confidently recovered. It is now held back from those look-alike classes and the
  frequent third-declension datives are read to their correct noun lemma (`πόλει → πόλις`). Net
  effect on the full New Testament: accuracy up slightly and ~780 fewer fabricated lemmas, with
  every genuine present verb (`λέγει → λέγω`) still recovered.
- **Elegiac pentameter accepts a short final syllable** (brevis in longo): the closing anceps
  position no longer rejects a line ending in a naturally short open vowel.
- **Case-insensitive syllabic transcription.** `word_to_phonetic` for Linear B and Cypriot now
  folds case before lookup, so the standard lowercase (DAMOS / IG XV) transliteration reads the
  Q-, Z-, and X-series signs correctly instead of falling through to raw text.
- **Subscript sign labels resolve.** A sign the corpus prints with a Unicode subscript (`RA₂`)
  now resolves in the inventory whether it is stored as `RA₂` or `RA2`.
- **The Leiden underdot is a known reading.** The Cypriot and Linear B Greek-reading bridges now
  strip the combining underdot (damaged but legible) before lexicon lookup, so a legible damaged
  token resolves like its clean form.
- **Word-scope corpus queries work on alphabetic Greek.** `word-contains` / `word-prefix` /
  `word-suffix` and the other word predicates were gated on a hyphen and so matched nothing on
  Greek (and on single-sign Aegean) words; they now operate on every word token.
- **Full-text search finds punctuation tokens.** A token that the SQLite tokenizer reduces to
  empty (a standalone `·` or `—`) is now found in the default token-mode search.
- **CSV import tolerates an Excel byte-order mark.** `from_csv` defaults to a BOM-stripping
  encoding, so a spreadsheet-exported file no longer loses its id column or fails to find its
  text column.
- **EpiDoc export stays well-formed.** Token text carrying XML-invalid control characters is
  cleaned on export, so the document always re-parses.
- **Sandhi coverage.** A sentence-initial capitalized elision (`Ταῦτ' → Ταῦτα`) is now restored,
  and the unaccented enclitic copula forms (`ἐστιν`, `εἰσιν`, `φασιν`) are recognized as
  movable-nu, while the look-alike i-stem accusatives still pass through unclaimed.
- **Tokenizer consistency.** A leading prodelision apostrophe (`'στι` for `ἐστι`) is now
  classified as a word by both `tokenize` and `tokenize_words`, so `pipeline()` no longer drops
  it.
- **Morphology of the demonstratives.** The oblique forms of `οὗτος` / `ἐκεῖνος` (`τούτου`,
  `ταύτην`, `ἐκείνων`) now analyze as pronouns with case/number/gender instead of falling through
  to spurious noun readings; the smooth intensive `αὐτή` is unaffected.
- **Capital lunate sigma** (`Ϲ`) converts to Beta Code instead of leaking through untransliterated.
- **Cleaner glosses for translation grounding.** A dictionary line that is only a
  grammatical-derivation pointer (`adverb of …`, `comp. of …`, `a strengthd. form of …`) now
  yields no gloss rather than an `"adverb of"` fragment, while a real meaning that merely contains
  `of` / `from` is kept.
- **Data-store visibility reaches every surface.** The MCP `data_status` tool and the terminal
  UI's data screen now report a dataset fetched under a different filename as downloaded, matching
  `aegean data list` and `aegean doctor`.
- **MCP `query_corpus` no longer inverts on a string.** A `negate` value of `"false"` / `"no"` /
  `"0"` was read by a raw boolean conversion as true and silently returned the opposite result
  set; it is now coerced the same forgiving way as the boolean filter values.
- Smaller correctness fixes: the accounting balance no longer raises on a marker-set mismatch;
  `format_value` never renders a tiny negative as `-0`; the rarity heuristic counts the ordinary
  letter phi; a corpus doc-store size scan skips a file that vanishes mid-walk. Documentation:
  the quickstart command count (seven commands across eight steps) and the DAMOS/SigLA fetch
  sizes are stated consistently across the wiki.

## 0.19.1 (2026-07-02)

A full-program audit pass: three confirmed defects fixed, each pinned by a regression test.

### Fixed
- **Grand-total accounting reconciles correctly.** A `PO-TO-KU-RO` grand total that follows one or
  more `KU-RO` subtotals was summed against an empty running list, so it reported a computed sum of
  0 (on the bundled HT122b: stated 97, computed 0 instead of 65). It now sums the subtotals the way
  the reference implementation does (HT122b reconciles to 65, difference -32). The fix reaches
  `aegean balance`, the MCP tool, and the terminal UI, which now all route the accounting and
  pipeline tables through the shared `aegean._view` layer, so the three surfaces cannot disagree.
- **The AI response cache survives a corrupt file.** A truncated or garbage cache file (from a
  killed process or a full disk) is now treated as a cache miss rather than raising, and writes are
  atomic so no partial file is ever observable.
- **The data store reports what is actually downloaded.** Datasets fetched as an unpacked archive
  or a prebuilt index (the LSJ index, the AGDT models) were shown as "not downloaded" by
  `aegean data list` and `aegean doctor` even when present; the on-disk probe now checks each
  dataset's real footprint. The reproducibility manifest also marks a mirror-overridden URL's
  checksum as unenforced, since verification is skipped for a user's own mirror.
- **Smaller corrections.** Negative accounting quantities keep their sign; the Linear A
  sound-value count is corrected to 48 in the docs and inventory docstring; the terminal UI flags
  SigLA as undeciphered, runs its corpus search off the UI thread, and no longer carries a dead
  cross-screen message subsystem; `paired_bootstrap` validates `n_resamples`.

## 0.19.0 (2026-07-02)

### Added
- **`aegean tui` — a terminal UI.** An app-like research cockpit in the terminal (the opt-in
  `[tui]` extra, built on Textual): browse the corpora, inspect a document with its editorial
  apparatus and an inline accounting/structure analysis, a live Greek workbench that scans,
  syllabifies, glosses, and transcribes as you type, and the local data store with one-key
  dataset fetches. It is a focused view over the highest-value offline reads, not a second
  front-end for every command, and it never touches the network except when you ask it to fetch
  a dataset. Undeciphered scripts carry their caveat on screen, as everywhere else. The core stays
  zero-dependency: `import aegean` loads no part of Textual, and the UI is reached only through
  `aegean tui`. A shared view layer (`aegean._view`) computes the accounting and pipeline tables
  once, so the TUI and the CLI can never show different numbers.

## 0.18.0 (2026-07-02)

The guided release: the CLI learns to explain itself, check itself, and hold a session's context.

### Added
- **`aegean doctor`** — a one-command, fully-offline environment check: Python and package
  versions, which optional extras are installed (with the install line for the ones that aren't),
  the local data store (size, what's downloaded, leftover partial downloads named with their
  `aegean data remove` fix, and whether the store is writable), downloaded models, and the
  analysis cache. `--json` for the machine report; exit 1 when it finds a real problem. The first
  thing to run when something isn't working.
- **`aegean quickstart`** — the guided first five minutes, running eight real commands (all
  offline, all on bundled data): a corpus overview, a tablet, an accounting check, a sign search,
  the Greek pipeline, a hexameter scan, the data store, and where to go next. `--no-run` prints
  the tour without executing it.
- **A session corpus in the REPL.** `use lineara` sets a default corpus, so afterward `show HT13`,
  `balance ht13`, and `stats` need no corpus argument; `:examples` lists runnable one-liners across
  the toolkit, and command history persists between sessions where the platform supports it.
- **Shell completion, now documented.** `aegean --install-completion` (typer's built-in) was always
  there but unmentioned; the install and terminal-setup docs now cover it, along with a
  **"Set up your terminal"** guide (Windows Terminal over the legacy console, and the font needed
  for Linear A/B glyphs to render instead of showing as boxes).
- **A fifteenth MCP tool, `greek_work`** — load a Greek work by catalogue id (fetched to the store
  on first use), so an agent can reach the ~1,800-work corpus, not only the bundled registry.
- **`aegean data fetch --json`** emits `{name, path, bytes}`, completing the `--json` coverage the
  0.17.0 notes described (it had been added to `cite`, `combine`, and `import` but not `fetch`).

### Changed
- **`--top` and `--limit` are interchangeable** on every command that ranks or caps rows; the
  primary name each command showed still shows first, and a guard test keeps any future command
  from offering only one of the pair. A drift guard likewise keeps every MCP tool named in the
  documentation.

## 0.17.0 (2026-07-02)

The friendliness release: a systematic pass over every command's failure modes, dead ends, and
inconsistencies; all 74 commands now fail cleanly on bad input.

### Added
- **Did-you-mean, everywhere names are typed.** A misspelled corpus id suggests the close ones
  (`aegean load linera` → "did you mean 'lineara' or 'linearb'?"), and registered ids match
  case-insensitively as a fallback (`aegean info LINEARA` works). The same suggestions cover
  dataset names (`data fetch`/`remove`), query `--where` fields, NT book names, sign labels, and
  import `--script` values, in the CLI, the REPL, Python, and over MCP alike.
- **Six new MCP tools** (8 → 14), so an agent can do what the CLI can: `cite_corpus` (plain,
  BibTeX, or APA, with metadata filters citing the exact subset), `query_corpus` (the compound
  query engine), `data_status` (the local store: downloaded state and sizes), `greek_catalog`
  (search the ~1,800-work catalogue), `geo_sites` (coordinates, Pleiades ids, contested flags,
  per-site word attestations), and `greek_gloss` (the registry dictionaries). All fourteen tools
  now share one error convention: a structured `error` payload with suggestions, never a raised
  exception, and document ids are resolved as forgivingly as the CLI resolves them.
- **Hints at dead ends.** Empty search/query/load results, a fetched work, an imported file, and
  a built database each end with one dim line naming the next command; the bare `aegean` help
  points to a quickstart and the documentation.
- **Wider `--json` and `-o` coverage.** `cite`, `combine`, and `import` emit `--json`;
  `balance`, `greek pipeline`, `analyze structure`, `analyze hands`, `db search`, and
  `ai eval` save with `-o`; `stats`, `dispersion`, `balance`, `geo`, `structure`, and `hands`
  accept the shared metadata filters (`--site`/`--period`/`--scribe`/`--support`).
- **The web demo reads Cypriot inscriptions.** A new card loads a bundled *Inscriptiones
  Graecae* XV 1 inscription entirely in the browser: find-place, transliteration lines, the
  Greek reading where the text is Greek, and the source-edition link. The demo now covers all
  four Aegean scripts.

### Changed
- **Saving is uniform.** Every `-o` creates missing parent directories, prints one
  `wrote <path>` confirmation to stderr (stdout stays clean for data), and combines with
  `--json` instead of silently overriding it; corpus-writing commands dispatch by extension, so
  `-o corpus.db` writes real SQLite everywhere.
- **`aegean data store`** is the new name of `aegean data cache` (the old name remains as a
  deprecated alias): it is a permanent store, not an evicting cache, and the analysis cache
  (`aegean cache`) is now clearly a different thing.
- **`greek eval --fold`** replaces the fold-selector meaning of `--treebank` (deprecated alias
  kept; the backend-activation `--treebank` on tag/lemmatize/morph is unchanged).
- **`db search` opens databases read-only** (searching a missing or non-database path can no
  longer create an empty file as a side effect), and `--limit 0` means unlimited there, in
  `aegean.db.search`, and in the MCP `search_signs`.

### Fixed
- **The file-writing traceback class.** Thirteen `-o` paths (load, query, export in every
  format, geo, db build, plot, stats and its siblings, ai results) crashed with a raw traceback
  when the target directory didn't exist or wasn't writable; all now share one guard and fail in
  one line.
- **Validation before work, in one line.** Non-numeric `--where` values, unknown `export`/`geo`
  `--level`s (including geo's silently-ignored one), bad `greek eval --fold/--split`, malformed
  or out-of-range `workbench --port`, unknown `work`/`catalog --source`, invalid `inflect`
  feature values, and malformed NT refs all fail with a clean message instead of a traceback or
  a silent no-op; a `--ref` that selects nothing in a fetched work errors instead of returning
  the whole work mislabeled.
- **Missing optional extras surface their install command** (`export -f csv` without pandas,
  `geo` without geopandas) instead of a traceback; help text renders bracketed extras
  literally, so `aegean plot --help` no longer instructs `pip install 'pyaegean'` with the
  `[viz]` eaten by markup.
- **`greek rarity --corpus`** goes through the standard corpus resolver (`.db` files and clean
  errors) instead of a raw JSON load; the four neural-backend activation paths share the
  standard activation errors; `ai translate`'s grounding-quality warning prints as a visible
  stderr line instead of a swallowed Python warning; `greek nt-books` and group help maps name
  every command and end with CLI (not Python) follow-ups.

## 0.16.0 (2026-07-02)

### Added
- **`aegean data remove`** deletes downloaded dataset(s) from the local store (`remove NAME`, or
  `--all`), printing exactly what was removed and the space reclaimed; partial-download leftovers
  are cleaned with it. `aegean data list` gains a **downloaded** column showing what is actually on
  disk, with real sizes.

### Changed
- **The data store says what it is.** A fetched dataset is a complete, permanent local download:
  nothing is re-fetched, evicted, or expires until `data remove` deletes it or `fetch --force`
  replaces it. The CLI help, `data cache` output, module documentation, and wiki now state this
  guarantee plainly (the word "cache" had suggested downloads might not persist).
- **The Linear A sign table carries the corrected alignment data.** The workbench's 1.6.0 corpus
  rebuild fixed its sign aligner (the upstream damage marker no longer counts as a sign), growing
  the transliteration-aligned evidence from 127 to 236 inscriptions and the aligned signs from 84
  to 95 (recovering PU, PU₂, QI and twelve more, each verified against its Unicode chart name);
  AB-shared classification now follows the Unicode chart (66 AB-shared). The bundled table and
  manifest mirror it; the cross-project parity checksum is unchanged.
- **The bundled workbench app pin moves to 1.6.0**, carrying the workbench's stored-XSS fixes and
  the corrected sign table, so `aegean workbench` serves them.

### Fixed
- **CLI tables render square brackets literally.** Cell text was parsed as rich markup, so a value
  like `[neural]` in a dataset note silently vanished from `aegean data list`; cells are data, not
  markup, and now render as written.
- **`aegean show` (and `balance`, `analyze structure`) resolve document ids forgivingly.** A Greek
  work's book or section addresses without repeating the work id (`aegean show tlg0012.tlg001 1`,
  not `... tlg0012.tlg001:1`), case and spacing are forgiven (`ht13`, `py ta 641`), an ambiguous
  short id is never guessed (the candidates are listed instead), and the not-found error names the
  closest ids and the corpus size. `aegean greek work` now ends with the exact `show` command that
  reads the loaded text.
- **KU-RA counts as a stated total.** It is KU-RO's variant (two bundled tablets, ZA 20 and
  ARKH 2); the accounting layer now checks it, moving the measured checkable-total figures from
  35 tablets / 39 total lines to **37 / 41** (documented everywhere the old numbers appeared).
  Approximate readings (`≈ ¹⁄₆`) parse at the editor's value instead of dropping from line sums,
  which also reclassifies 29 fraction-bearing tokens that had been left unclassified.
- **The libation word list carries only attested forms.** The restoration fragment
  `A-DI-KI-TE-TE-DU` (zero corpus tokens) is replaced by the four attested a-di-ki-te family forms
  from Younger's readings of the PK Za vessels; three PK Za inscriptions now classify as libation
  (census: libation 15 → 18), and a liveness test keeps dead entries out.
- **Query: `word-contains-sign` matches sign labels as written.** `*301` (or `301`, any case) now
  finds `*301`-bearing words, and subscripted signs match only themselves (`RA₂` no longer answers
  for `RA`); a blank min/max-syllables value matches neutrally instead of raising.
- **Workbench exports re-import faithfully.** The importer reads the export schema's real field
  spellings (`period`, the nested images block), so dating and imagery survive the round trip.

## 0.15.1 (2026-07-01)

### Added
- **Resumable downloads.** A dropped or stalled connection no longer costs the whole download:
  `fetch()` keeps the partial file on network failures, retries up to twice within the call, and
  resumes with an HTTP `Range` request (guarded by `If-Range` and a recorded-length check, so a
  republished asset restarts cleanly from zero instead of splicing). A truncated response body is
  detected against the declared length rather than trusted. The sha256 verification of the
  completed file is unchanged and remains the final arbiter.

### Changed
- **The bundled workbench app pin moves to 1.5.5**, picking up the workbench's mirrored sign-table
  and phonetic corrections (the `*903` glyph fix and subscripted-sign reading that shipped here in
  0.15.0), so `aegean workbench` serves the same data conventions this library uses. The `*904`
  and `*905` sign entries are genuine, verified against Younger's readings: alias labels for
  GORILA `*319` and the fraction sign J.

## 0.15.0 (2026-07-01)

A correctness pass across the toolkit's convention boundaries: the places where a well-tested
code path meets a second data source with different conventions (upper vs lower transliteration,
suffixed morphology tags, Leiden apparatus, Unicode normalization, grave vs acute). Every fix
ships with a regression test pinning the corrected output.

### Fixed
- **NT gold UPOS: suffixed Robinson tags are reconciled correctly.** `PRT-N`, `CONJ-N`, `ADV-I`,
  `COND-K` and kin mapped to `X` because only bare tags were looked up, mistagging 3,566 tokens
  (2.6% of the corpus), among them every negative particle (οὐ, μή). Suffixes never change a
  closed-class tag's word class; the bare tag now wins (`PRT-*` → PART, `CONJ-*` → CCONJ,
  `ADV-*` → ADV, `COND-K` → SCONJ), leaving only the ARAM/HEB loanword tags as `X`. The
  out-of-domain NT benchmark row is re-measured against the corrected gold with the shipped
  model: lemma 87.03 / UPOS 86.75 (n = 137,303). The previously published 87.57 UPOS dated to
  the retired grc-joint-v1 model (0.8.1) and had gone stale when v2 shipped; the full
  decomposition (model generation, quantization, gold correction, normalization) is recorded in
  `docs/benchmarks.md`.
- **Offline lemmatizer: grave accents and the closed-class inventory.** Lookups now fold running-text
  graves to the citation acute (δὲ → δέ) and NFC-normalize, and the closed-class table covers the
  article's oblique forms, pronouns, and the high-frequency particles; `known=True` now always means
  a genuine table or rule validation, never a fabricated stem. Measured on the full NT under the
  recorded protocol (`greek.evaluate_on_nt` scoring): 45.2% → 66.0% lemma accuracy, 28,578 fixes
  against 12 regressions. This also corrects the 0.14.0 note's "14.5% → 15.4%": that figure was a
  byte-level comparison against pre-NFC gold, not the protocol score; the docs now carry the
  protocol-scored number.
- **Linear B accounting works on DAMOS.** The accounting markers matched uppercase only, so the
  lowercase DAMOS transliterations yielded zero `balance_check` totals across 5,932 tablets, and
  `to-so`/`o-pe-ro` leaked into `account_dossiers` as "account holders". Marker matching now folds
  case, `TO-SO-DE` joins the total markers, and DAMOS yields 130 tablets with stated totals
  (255 checks, 52 balancing exactly). Bundled Linear A results are unchanged (35 tablets, 39 totals;
  the README figure is corrected from "≈40" to the measured 35).
- **Cypriot inscriptions carry their editorial apparatus.** The IG loader emitted every token as
  CERTAIN and leaked Leiden markup into token text; underdotted (uncertain) readings now load as
  UNCLEAR and bracketed restorations as RESTORED, with clean text and the apparatus preserved in
  annotations (118 UNCLEAR + 56 RESTORED across the bundled corpus).
- **Linear A sign table: `*903` no longer wears the vowel I's glyph.** The entry duplicated
  U+1061A / 𐘚 (the Unicode block has no `*9xx` codepoints; glyph and codepoint are now empty), and
  `SignInventory` warns on duplicate glyph/codepoint entries instead of silently letting the last
  one shadow lookups. The tokenizer also recognizes standalone subscripted signs (PA₃, TA₂) and
  variant-letter ligatures (VIR+*313b) as logograms (27 bundled tokens regained from UNKNOWN) and
  `word_to_phonetic` reads subscripted signs as the distinct signs they are, never borrowing the
  plain series' value (the shared golden fixture value `raro` is corrected to `ra₂ro`; the
  workbench mirrors this in its next release).
- **Workbench image server: Windows path traversal closed.** The local facsimile server's guard
  only rejected forward-slash `..` segments; backslash and percent-encoded forms could escape the
  imagery directory. Requests are now decoded and separator-normalized, and the resolved path must
  remain inside the imagery root. The bundled workbench asset pin also moves from 1.5.1 to 1.5.4,
  picking up the workbench's own sanitizer hardening and gazetteer corrections.
- **`load_work` refuses to silently truncate.** A citation range crossing textparts (e.g.
  `1.1-2.50`) returned only the start part while the document id claimed the full range; it now
  raises a clear error naming the parts involved.
- **SQLite append keeps every corpus's provenance.** `to_sql(append=True)` dropped the appended
  corpus's provenance and license; the database now stores all of them, so `from_sql(...).cite()`
  cites everything that went in.
- **Empty geo results return empty GeoDataFrames.** `to_geodataframe` and `word_distribution` on a
  corpus with no mapped sites (or a word with no attestations) crashed with an opaque geometry
  error; both now return a schema-correct empty GeoDataFrame, matching the CLI's existing hint.
- **`db.search` case handling is measured and truthful.** Substring mode now matches Greek
  case-insensitively (SQLite `LIKE` folds ASCII only); the docstring states exactly what each mode
  folds (FTS5 token mode folds case but not accents).
- **AI layer provenance and caching.** Grounding passed as a generator was consumed twice, so the
  model saw it but the provenance recorded none of it: it is materialized once. The response-cache
  key now includes `max_tokens`, so a truncated completion is never served for a longer request.
  An unknown grounding mode raises with the valid modes instead of silently degrading to legacy
  lemma grounding. The verify-mode docs state the honest contract: the analysis cannot bias the
  draft, though a wrong analysis can still mislead the repair.
- **EpiDoc export never silently overwrites.** Two document ids sanitizing to the same filename
  produced one file; colliding names now get deterministic suffixes with a warning naming both ids.
- **NT loading and fetching hygiene.** `load_nt` NFC-normalizes text, lemma, and normalized forms at
  load (the source edition mixes oxia and tonos precomposition), and requesting a non-bundled book
  offline explains what is bundled and how to fetch the corpus instead of a misleading error.
  Downloads use a 30-second timeout instead of hanging on a stalled connection, and archive
  extraction validates symlink/hardlink targets before unpacking.
- **Greek tokenizer: ano teleia and the Greek question mark are punctuation.** The letter class
  spanned the whole Greek block, so U+0387 and U+037E glued into word tokens (3,330 such tokens
  when tokenizing the bundled NT's text; now zero). `pos_tag` shares the corrected letter class.
- **Diaeresis marks hiatus.** `syllabify` and `to_ipa` merged explicitly-marked non-diphthongs
  (προΐστημι is προ-ΐ-στη-μι, Smyth §8); a diaeresis vowel now never joins the preceding vowel,
  in precomposed and combining forms alike. Metrical scansion already handled this and is
  unchanged.
- **γάρ and οὖν are tagged CCONJ, not SCONJ.** Neither can subordinate a clause; the NT gold is
  unanimous (γάρ 1038/1038, οὖν 496/496) and AGDT has no conjunction reading for either.
- **The movable-nu rule only claims what it can validate.** It fires on `-ουσι(ν)` and a curated
  host lexicon (copula and athematic third persons, high-frequency dative plurals, accent-aware so
  ποσίν is listed while πόσιν is not); third-declension i-stem accusatives (γνῶσιν, φύσιν, πίστιν)
  no longer receive a fabricated bare alternative.
- **Docs carry the re-measured numbers.** The stale v1 PROIEL scores in the wiki are replaced with
  the shipped model's recorded figures, and "state of the art on the UD Ancient Greek benchmarks"
  is scoped to the measured claim (the UD Perseus test fold).

### Changed
- **`aegean.load()` returns an independent copy.** The cached loaders shared one mutable `Corpus`
  per process, so mutating `corpus.documents` corrupted every later `load()` of the same id. Each
  call now returns a structural copy (about 3 ms for the bundled Linear A corpus; frozen tokens are
  shared, containers are fresh), and the new `Corpus.copy()` is public.
- **`Corpus.fingerprint` covers what analyses consume.** It hashed only document ids and token
  text, so corpora differing in token kind, reading status, or annotations shared a fingerprint and
  the opt-in analysis cache could serve results computed for a different corpus. It now hashes
  kind, status, and annotations (and the data version); all fingerprints rotate once.

### Removed
- The empty `aegean.adapters` and `aegean.integrations` placeholder packages (0-byte, never
  documented, nothing imported them).

## 0.14.4 (2026-06-29)

### Fixed
- **Gazetteer coordinates corrected against Pleiades.** A full validation pass of the geo gazetteer
  against the Pleiades representative points found five find-site coordinates that had drifted from
  their place: Zominthos (~7.5 km), Kythera (~8.4 km), Pylos (~9.4 km), and the Cyprus and Margiana
  island centroids. All are now aligned to the Pleiades point.

### Added
- **Seven more find-sites aligned to Pleiades** (33 → 40 of 56): Ugarit (Ras Shamra), Sitia, the
  Skotino cave, Fourni and Troullos (Archanes), Poros (the harbour of Knossos), and Pyrgos, which
  had been mislocated by 39 km and is now corrected to Myrtos-Pyrgos.
- **`scripts/check_gazetteer.py`** — a repo-only guard (run weekly via `assets.yml`) that fails if a
  Pleiades-linked find-site drifts more than 6 km from its Pleiades point, so the gazetteer cannot
  silently rot.

## 0.14.3 (2026-06-29)

### Fixed
- **`geo --word` matches case-insensitively.** It was the only word-search path that did not fold
  case (`db.search`, the query engine, and `aegean search` already do), so `geo lineara --word
  ku-ro` found nothing while `KU-RO` worked. The CLI and `aegean.geo.word_distribution` now both
  fold case.
- **`aegean workbench` serves the facsimile imagery again.** The cached `lineara-images` asset
  unpacks into an `images/` subdirectory; the local server looked one level too high, so every
  facsimile returned 404 even after the asset was fetched.

### Added
- **`aegean workbench --fetch-images`** downloads the ~116 MB Linear A imagery in one step, and the
  command now hints how to fetch it when it is not cached.
- **`aegean geo` on a corpus without find-sites** prints a one-line explanation instead of an empty
  grid, and its `--help` notes which corpora produce rows (lineara, linearb, cypriot, cyprominoan,
  sigla, damos).

## 0.14.2 (2026-06-29)

### Added
- **Contested find-spot flag in the gazetteer.** `aegean.geo.SiteCoord` gains an optional
  `contested` reason string (with an `is_contested` convenience property), and the geo
  GeoDataFrames carry a matching `contested` column. The bundled Margiana (Turkmenistan) entry is
  flagged: it is kept for corpus fidelity (and cross-project parity), but no Linear A inscription is
  accepted from Central Asia, so it is never silently mapped as a genuine find-spot.

## 0.14.1 (2026-06-29)

### Fixed
- **`analysis.wilson_interval`** clamps an out-of-range count: `k > n` made p̂ > 1 and drove the
  variance (and its square root) negative; it now returns a valid in-[0,1] interval, and `n <= 0`
  returns the no-information interval `(0, 1)`.
- **`analysis.fit_heaps`** rejects a constant-x growth curve relative to the data scale instead of an
  exact-zero comparison, which float roundoff defeated into a fabricated power-law fit.

Both are unreachable from the library's own callers (`pmi_interval` keeps `joint ≤ total`; a real
vocabulary-growth curve has increasing token counts), but they match the degenerate-input contract the
rest of the statistics layer already upholds. Surfaced by a cross-repo audit of the Linear A Research
Workbench, whose ported helpers shared the same gaps.

## 0.14.0 (2026-06-28)

### Added
- **Generalizing rule-based lemmatizer (always-offline default).** With no backend loaded,
  `greek.lemmatize` now strips the regular second-declension and thematic-verb endings to recover the
  citation form (`νόμου → νόμος`) instead of only consulting a seed table. On the full Nestle 1904 New
  Testament it lifts the offline baseline from 14.5% to 15.4% (about 1,300 regular forms recovered against
  28 mis-strips), with conservative guards (contracted nominatives like `Ἰησοῦς`, neuter `-ον` nouns,
  indeclinables) preventing the regressions a naive stripper introduces. The opt-in treebank and neural
  backends remain far more accurate for serious work.
- **Whole-token and substring search modes.** `db.search(..., mode="token")` (the default) matches a
  whole token literally, so `KU-RO` matches only the token `KU-RO`, never `PO-TO-KU-RO`; `mode="substring"`
  (CLI `aegean db search --substring`) opts into the within-token search.

### Changed
- **`db.search` matches whole tokens by default.** The FTS index previously split hyphenated
  transliterations, so `KU-RO` matched the subsequence inside any longer token (`search("DA-RO")` returned
  7 hits, none of them the token `DA-RO`). Search now matches an exact whole token; pass `mode="substring"`
  for the previous within-token behaviour. The call signature is unchanged.

### Fixed
- **Accentuation:** word-final `-οις` / `-αις` (dative plural) count long, so dative plurals accent on the
  penult (`ἀνθρώποις`), not the antepenult.
- **Sandhi:** elided proclitics (`ἀπ'`, `ἐπ'`, `καθ'`, …) now resolve; the accent-keyed entries were
  unreachable under the accent-blind lookup.
- **Scansion:** `scan_hexameter` scans Iliad 1.3 to its canonical pattern via a curated long-by-nature
  lexicon, instead of returning a wrong greedy reading.
- **Beta Code:** `unicode_to_betacode` / `betacode_to_unicode` round-trip text containing literal
  `( ) / \ = + |` through a backtick escape.
- **Lenient OCR normalize:** maps Latin `v` to upsilon (the common misreading) and only repairs
  Greek-dominated tokens, leaving a mostly-Latin token untouched.
- **Collocation:** `fishers_exact` returns 1.0 on an impossible 2×2 table instead of raising.
- **Translation grounding:** the rare-word gloss gate no longer glosses every word on all-common text;
  `clean_gloss` no longer leaks etymology fragments; and the concise-gloss cascade no longer falls back to
  LSJ's archaic first sense when no concise dictionary is loaded.
- **Idioms:** nested sub-idioms are suppressed on the lemma path too (the longest idiom wins).
- **Clause skeleton:** copular clauses keep the copula and the predicate nominal/adjective, instead of
  labelling a preposition-phrase-internal noun the predicate.
- **EpiDoc:** a LOST token round-trips as LOST, distinct from RESTORED, instead of becoming RESTORED.

### Documentation
- Every public function now ships a correctness test (CONTRIBUTING and the release gate require it).
- `query(output='words')` counts are documented as document frequency, distinct from
  `Corpus.word_frequencies()` token frequency.

## 0.13.0 (2026-06-28)

### Added
- **Idiom / multiword-expression grounding.** `ai.idiom_glosses(text)` detects non-compositional Greek
  idioms (ἐφ' ἡμῖν "in our power", οὐκ ἔστιν ὅπως "there is no way that", οἷός τε "be able to", …) from
  a curated bundled lexicon and grounds their real meaning, the error class that per-token morphology
  grounding cannot reach. Detection is surface plus contiguous-lemma matching (so inflected idioms are
  caught); idioms are added to the morphology and full translation grounding by default.
- **Post-hoc verify translation** (`translate(..., verify=True)`; `aegean ai translate --verify`):
  translates the passage first, then checks the draft against the gold morphology, glosses, and idioms
  and repairs definite contradictions (wrong voice, subject/object, case, a wrong rare-word or idiom
  sense, omission/addition). Because the analysis only checks the draft, it can catch errors without
  ever biasing the translation. Costs a second model call; recommended for hard or high-stakes passages.

## 0.12.0 (2026-06-28)

### Changed
- **Grounded translation now defaults to morphology-first grounding.** `aegean.translate.translate`
  and `grounding_for` take a `mode` parameter (`"morphology"`, `"lemma"`, `"full"`, `"none"`),
  defaulting to **`"morphology"`**: the model is grounded in deterministic lemma, part-of-speech, voice,
  case-role, and clause-structure analysis from the pipeline, with rare-word flags, and no
  automatically-selected dictionary glosses. Deterministic morphology reliably helps a model with the
  grammar (voice, subject/object, case), whereas an auto-selected sense gloss can surface the wrong
  sense and mislead it. The previous lemma-plus-gloss behaviour is preserved as `mode="lemma"`. CLI:
  `aegean ai translate --mode`.

### Added
- **Concise, common-sense-first glosses for `mode="full"`.** When glosses are wanted, `mode="full"`
  adds them from a cascade of concise dictionaries (Middle Liddell, Cunliffe, Abbott-Smith, Dodson),
  rarity-gated to the words that need them and cleaned, instead of the first sense of LSJ (a historical
  lexicon whose opening sense is often the archaic one, e.g. καιρός "a row of thrums in the loom" before
  "the right time"). New helpers `ai.concise_gloss` and `ai.clean_gloss`. Most useful for rare or
  technical vocabulary and for weaker models. A new Recipe (Get the best AI translation) and a notebook
  section walk through choosing the mode.

## 0.11.0 (2026-06-28)

### Added
- **Accent placement** (`greek.place_accent`, `recessive_accent`, `persistent_accent`; `aegean greek
  accentuate`): predicts a word's accent from the Greek accentuation laws (the law of limitation,
  recessive vs persistent accent, the properispomenon rule). Dichrona (α/ι/υ, undetermined from
  spelling) are flagged honestly rather than guessed; a supplied lemma or vowel length resolves them.
- **Crasis / elision / movable-nu resolver** (`greek.resolve_sandhi`, `resolve_sentence`; `aegean greek
  sandhi`): expands surface contractions to their underlying word(s) (κἀγώ to καί + ἐγώ, τἀμά to
  τὰ + ἐμά) through a small, contribution-friendly curated lexicon. Conservative: unlisted or ambiguous
  forms are flagged uncertain, never over-expanded.
- **Wider closed-class coverage** in the zero-dependency rule POS/morphology: the indefinite and
  interrogative τις/τίς (distinguished by the written accent), the relative ὅς/ἥ/ὅ paradigm,
  determiners (ἄλλος/ἕκαστος/πᾶς), the low cardinals and ordinals, and more particles now tag and
  analyse correctly (`analyze("τις")` is no longer empty).
- **LSJ sense selection** (`ai.select_sense`) and a **grounding-regime detector** (`ai.grounding_regime`):
  offline, deterministic helpers that rank an LSJ entry's senses by fit to a context and estimate
  whether grounding a generation step will help, stay neutral, or hurt for a given text. Exploratory.
- **Evaluation receipts** (`greek.eval_receipt`): a content-addressed, tamper-evident record tying an
  evaluation result to its exact inputs (package version, data manifest, model id, protocol, scores),
  for reproducibility.
- **Paired significance testing** (`analysis.mcnemar`, `analysis.paired_bootstrap`): tests whether two
  systems differ significantly on a shared evaluation set, rather than only bounding one system's score.
- **Aegean structure tooling** (exploratory): Monte-Carlo null models with explicit, documented nulls
  (`analysis.monte_carlo_p`) so a structure statistic carries a p-value against a stated baseline;
  distributional sign embeddings (`analysis.sign_embeddings`); unsupervised morpheme segmentation
  (`analysis.segment`, `candidate_morphs`); and Brown sign-class induction (`analysis.induce_classes`),
  aimed at the least-served script, Cypro-Minoan.

## 0.10.0 (2026-06-25)

### Changed
- **Quantized neural pipeline** (`grc-joint`): the joint tagger/parser/lemmatizer now ships quantized
  at **~173 MB** (down from ~518 MB, about 3x smaller), with **no loss of accuracy** on the UD Ancient
  Greek Perseus benchmark (UPOS 97.0 / UFeats 96.0 / lemma 94.3 / UAS 90.2 / LAS 85.6, identical to the
  fp32 model within rounding). The recipe is weight-only int8 on the matrix weights plus fp16
  elsewhere, keeping activations in full precision; full int8 (quantized activations) collapses the
  encoder, so it is avoided. The `[neural]` extra now requires `onnxruntime>=1.23`; the fp32 model
  remains available at the `grc-joint-v2` release for reproducibility.

## 0.9.0 (2026-06-24)

### Added
- **Cypriot syllabic corpus** (`aegean.load("cypriot")`): 178 inscriptions of *Inscriptiones
  Graecae* XV 1, the Berlin-Brandenburg Academy digital edition (CC BY 4.0), bundled as a hosted
  snapshot with transliteration, editorial apparatus, find-place/date/material, and translations.
  The corpus grows from a 2-document illustrative sample to a real syllabic corpus.
- **Inflection synthesis** (`greek.inflect(lemma, **features)`, `greek.paradigm(lemma)`): the
  inverse of lemmatization, generating the attested inflected forms of a lemma from the AGDT.
  Activate with `greek.use_inflector()`. CLI: `aegean greek inflect`.
- **Terminology rarity** (`greek.terminology_rarity(text, corpus)`): a corpus-relative
  vocabulary-rarity score that flags rare or technical vocabulary, a translation-difficulty signal.
  CLI: `aegean greek rarity`.
- **Dialect and register tags** (`greek.usage(word)`): a word's dialect (Doric, Attic, Ionic, …)
  and register (poetic, medical, comic, …), mined from its LSJ entry. CLI: `aegean greek usage`.
- **Gated gloss grounding for translation** (`aegean.translate(text, glosses=True)`): adds gated,
  content-word LSJ glosses to the grounding (a polysemy gate, with an optional frequency gate), and
  warns when only the baseline lemmatizer is active. CLI: `aegean ai translate --glosses/--no-glosses`.
- **PROIEL convention-drift report** (`greek.proiel_drift()`): a part-of-speech confusion matrix
  and lemma-mismatch breakdown of the out-of-AGDT PROIEL evaluation, separating annotation-convention
  divergence from real error. CLI: `aegean greek eval proiel --drift`.

## 0.8.10 (2026-06-24)

### Added
- **EpiDoc inbound reader** (`aegean.io.from_epidoc` / `read_epidoc`, and `aegean import --epidoc`):
  load any EpiDoc TEI edition (a file or a folder of `.xml`) into a `Corpus` — the inverse of the
  EpiDoc writer. Recovers the id, find-place, token/line stream, editorial certainty
  (`<unclear>`/`<supplied>`), and `<app>` alternate readings, using only the stdlib XML parser
  (no extra dependency).

## 0.8.9 (2026-06-24)

### Added
- **OpenRouter AI provider** (`provider="openrouter"`, the `[openrouter]` extra): a fifth
  built-in provider reaching many models from one key through OpenRouter's OpenAI-compatible
  gateway. Set `OPENROUTER_API_KEY` for the key and `OPENROUTER_MODEL` for the `vendor/model`
  id (e.g. `anthropic/claude-3.5-sonnet`); works everywhere `--provider` is accepted.
- **Fuller CLI parity** with the Python API: `aegean greek nt` (load a New Testament book or
  passage with its gold annotations), `aegean ai summarize`, `aegean geo --word` (a word's
  per-site attestation map), `aegean greek eval ud --bootstrap` (percentile CIs), and a Linear A
  Workbench round-trip (`export -f workbench` / `import --workbench`).

## 0.8.8 (2026-06-24)

### Added
- **Pluggable lexicon registry** for Greek dictionaries. `greek.lexica()` lists the
  available dictionaries; `greek.use_lexicon(id)` activates a hosted one;
  `greek.gloss(word, dictionary=id)` and `greek.entry(word, dictionary=id)` resolve a word
  against a chosen (or any active) dictionary; `greek.lexicon_link(word)` builds a Logeion
  or Perseus deep-link for dictionaries that are not hosted. LSJ and Dodson are now backends
  in the registry; `use_lsj` / `use_dodson` / `gloss` / `lookup` keep working unchanged.
- **Three new dictionaries** behind the registry, each fetched to the cache on first use
  and built into a lemma→entry index (never bundled): the Intermediate Greek-English
  Lexicon (Middle Liddell, classical), Cunliffe's Lexicon of the Homeric Dialect (Homeric),
  and Abbott-Smith's Manual Greek Lexicon of the New Testament (Koine).
- CLI: `aegean greek lexica` lists the dictionaries, `aegean greek gloss --dict <id>` glosses
  from a chosen one, and `aegean greek lexicon-link <word>` builds a deep-link.

### Changed
- **`load_work` reference addressing** is stricter and clearer: malformed refs (empty
  components like `1..2`, a stray `-`) and descending verse ranges (`1.50-1.1`) raise with
  the reason, and the "selected no text" error lists the sections (or the line range) present
  where the ref failed.

## 0.8.7 (2026-06-23)

### Changed
- Neural pipeline model `grc-joint-v2`. UD Perseus test parsing improves to LAS 85.6 /
  UAS 90.2 (from 84.4 / 89.2), the best published result on every metric and stable across
  five training seeds. Two training changes: the AGDT→UD converter attaches
  non-coordination commas to the following token, and the relation head trains on predicted
  arcs rather than only gold arcs.

### Added
- Bootstrap confidence intervals for the UD evaluation: `greek.bootstrap_ud`, plus the
  generic `analysis.bootstrap_ci_seq` and `analysis.bootstrap_dict_seq`.
- Beta Code round-trip stage in the internal regression set (`greek.benchmark`).

### Fixed
- `docs/benchmarks.md`: corrected the Gorman treebank license to CC BY-SA 4.0, documented
  the train/dev/test split and lemma scoring, and added seed mean ± std and bootstrap CIs.

## 0.8.6 (2026-06-23)

### Changed
- Wording refinements across the README and wiki.

## 0.8.5 (2026-06-16)

### Fixed
- The `aegean` command starts under typer ≥ 0.26, which vendors its own Click. The
  interactive shell now reaches Click through typer instead of importing `click` directly.

## 0.8.4 (2026-06-16)

### Added
- Interactive shell (`aegean repl`): run subcommands without the `aegean` prefix, with
  Tab-completion and history. Adds `prompt_toolkit` to the `[cli]` extra.

## 0.8.3 (2026-06-15)

### Changed
- The in-browser demo covers every client-side feature: Greek word analysis, Koine
  glossing, the work catalogue, the syllabary→Greek bridge, Linear A accounting, the file
  importer, and cross-script comparison.
- Refreshed the README "About the author" section.

## 0.8.2 (2026-06-15)

### Added
- Universal corpus input (`aegean.read_corpus`, every `aegean` corpus command): accepts a
  registered id, a Greek work id, a `.json`/`.db` path, or `-` for JSON on stdin.
- Combine corpora (`aegean combine`; `aegean.combine`, `Corpus.merge`, `Corpus.subset`),
  with explicit duplicate-id handling (`--on-conflict`) and merged provenance.
- Save results to files (`-o/--output` on `stats`, `keyness`, `dispersion`, `search`, and
  the `analyze` commands): `.json`, `.csv`, or `.txt` by extension.
- Save AI outputs (`-o` on `ai` commands; `ExploratoryResult.to_dict/to_json/from_dict`),
  preserving the exploratory label and grounding.
- Append to a database (`aegean db add`, `to_sqlite(append=True)`, `Corpus.to_sql(append=True)`):
  upsert documents by id and refresh the FTS index.
- Save a queried subset (`aegean query ... -o`, `QueryResults.to_corpus`) with a `subset:`
  provenance note.
- Work and book discovery: `greek.popular_works()` / `aegean greek works` and
  `greek.nt_books()` / `aegean greek nt-books` (offline metadata).
- Full work catalogue (`greek.catalog()`, `aegean greek catalog`): an offline index of
  1,778 Greek works in Perseus canonical-greekLit + First1KGreek, searchable by author,
  title, or source. Metadata only; texts fetch on demand.
- Import your own text (`aegean import`; `aegean.io.from_text`, `from_text_file`,
  `from_text_dir`, `from_csv`): `.txt`, a folder, or CSV into a `Corpus`, with
  `--split whole|paragraph|line`.

### Fixed
- `Corpus` with duplicate document ids is now self-consistent: the constructor collapses
  duplicates to one document per id (keeping the last) and warns.
- `aegean analyze cooccur` returns a deterministic order (shared-document count, then word).
- Linear A sound-value count corrected in the docs: 47 of 344 inventory signs carry a sound
  value (was stated as 84).
- In-browser demo: `aegean.cache` imports sqlite3 lazily, so `import aegean` works under
  Pyodide. The footprint guard now asserts `import aegean` never imports sqlite3.

## 0.8.1 (2026-06-14)

### Added
- Greek New Testament corpus (`greek.load_nt`, `aegean.load("nt")`): Nestle 1904 with gold
  lemma, Robinson morphology, Strong's number, reconciled UPOS, and a Koine gloss per token
  (in `Token.annotations`). One book bundled; the full 27 fetch to cache.
- Koine glossing (`greek.use_dodson` / `gloss_nt` / `gloss_strongs` / `lookup_nt`): the
  Dodson lexicon (CC0), bundled.
- NT evaluation fold (`greek.evaluate_on_nt`, `aegean greek eval nt`).
- Per-token annotations (`Token.annotations`): optional `dict[str, str]`, round-trips
  losslessly and surfaces as `to_dataframe` columns.
- In-browser demo (`docs/demo/`, published at `/demo/`): the core toolkit client-side via
  Pyodide.
- MCP server (`aegean-mcp`, the `[mcp]` extra): exposes corpora, sign search, accounting,
  the Greek pipeline, scansion, and Koine glossing as MCP tools.
- Aeolic lyric scansion (`greek.scan_aeolic`): glyconic, pherecratean, sapphic, and alcaic
  line types. Adds three-vowel synizesis to the curated lexicon.
- `aegean workbench`: fetch the Linear A Research Workbench static build (sha256-pinned) and
  serve it locally.
- Scribal-hand analysis (`aegean.analysis.scribal_hands` / `hand_keyness`): profile DAMOS
  scribal hands and surface what is characteristic of each.
- SQLite persistence (`Corpus.to_sql` / `from_sql`, `aegean.db`): documents and tokens as
  rows with an optional FTS5 index, provenance preserved. `aegean.db.stream(path)` yields
  documents one at a time.

### Packaging
- License declared as the PEP 639 SPDX expression (`license = "Apache-2.0"`); wheel/sdist
  carry Metadata 2.4.
- Python 3.14 added to the CI matrix and classifiers.
- `MANIFEST.in` excludes `tests/`; README links absolutized for PyPI.
- Workbench round-trip (`aegean.io.to_workbench` / `from_workbench_export`).

## 0.8.0 (2026-06-10)

First beta of the 0.8 line: a complete Linear A sign repertoire, an editorial-status model
with a schema-valid EpiDoc round-trip, Pleiades-aligned find-sites and geographic analysis,
the full Greek NLP track including a neural pipeline, the DAMOS and SigLA corpora on demand,
and a hosted API reference.

### Added
- Neural Greek pipeline (`greek.use_neural_pipeline`, the `[neural]` extra): one
  jointly-trained, torch-free model for POS, UD FEATS, dependency trees, and lemmas. UD
  Ancient Greek (Perseus) test: 96.9 UPOS / 96.1 UFeats / 94.4 lemma / 89.2 UAS / 84.4 LAS.
  Inference is onnxruntime + numpy; the model fetches to cache.
- Standard-benchmark evaluation (`greek.evaluate_on_ud`) with the official CoNLL 2018
  evaluator, plus `greek.agdt_ud_overlap` for the leakage manifest.
- One-call analysis (`greek.pipeline`): tokenize → sentence-split → tag → lemmatize → parse.
- Full DAMOS Linear B corpus (`aegean.load("damos")`): ~5,900 tablets (CC BY-NC-SA),
  fetched to cache, carrying scribal hand, find-context, and object class.
- SigLA Linear A corpus (`aegean.load("sigla")`): 781 documents (CC BY-NC-SA).
- Full Unicode Linear A sign repertoire (344 signs).
- Editorial status on tokens (`ReadingStatus`) and variant readings (`Token.alt`), both
  surviving the JSON and EpiDoc round-trips. EpiDoc export is schema-valid and CI-validated.
- Real Greek works on demand (`greek.load_work`): a fetch-to-cache TEI reader for Perseus
  canonical-greekLit and First1KGreek, with citation addressing.
- Geographic analysis (`aegean.geo`, the `[geo]` extra): corpus → GeoDataFrame from a
  bundled, Pleiades-aligned gazetteer.
- Corpus statistics (`aegean.analysis.stats`): Gries' DP dispersion, Dunning log-likelihood
  keyness with log-ratio, and bootstrap confidence intervals (pure stdlib).
- Visualization (`aegean.viz`, the `[viz]` extra) and `aegean plot`.
- Cross-script phonetic comparison (`aegean.analysis.compare`).
- The `aegean` command line (the `[cli]` extra): the toolkit without writing Python, with
  `--json` everywhere and stdin piping.
- Grounded AI layer (`aegean.ai`): structured grounding with a provenance trace, JSON-mode
  extraction, and a groundedness eval harness.
- Iambic trimeter scansion (`greek.scan_trimeter`) with resolution, plus a curated synizesis
  lexicon.
- More Greek core: lenient normalization, a syllabification exception lexicon, and a PROIEL
  out-of-AGDT evaluator (`greek.evaluate_on_proiel`).
- Linear B sample (18 tablets) and Greek-bridge lexicon (150 entries); Cypriot lexicon (17).
- Opt-in analysis cache (`aegean.cache`) and streaming corpus views.
- Lossless JSON round-trip, compound `query()`, CSV/Parquet export, citation automation,
  and a data-versioning manifest (`data.versions()`).
- Wider public API and a hosted API reference.

### Changed
- Core has zero hard third-party dependencies; pandas is the `[data]` extra.
  `scripts/check_footprint.py` enforces import-clean/import-fast/code+JSON-only in CI.
- `greek.evaluate` renamed `greek.evaluate_parser` (the one breaking rename, before the API
  freeze).

### Fixed
- Infinite recursion with `use_tagger()` + `use_lemmatizer()` both active on an
  out-of-treebank form.
- The AI `summarize` capability now labels its result `kind="summarize"`.

## 0.7.0 (2026-06-10)

### Added
- EpiDoc (TEI) export (`aegean.io.to_epidoc`, `write_epidoc`): the inverse of the reader, so
  a written corpus reloads through `parse_epidoc`. Uses the stdlib XML writer.
- CSV / Parquet export (`aegean.io.to_csv`, `to_parquet`): CSV needs `[data]`, Parquet needs
  `[parquet]`.
- `aegean.io` exposed as a top-level subpackage.

## 0.6.0 (2026-06-10)

### Added
- Lossless JSON round-trip on `Corpus` (`to_json` / `from_json` / `from_dict`).
- `Corpus.query(filters, output=...)`: the compound-query engine as a first-class method,
  returning `QueryResults`.

## 0.5.0 (2026-06-10)

### Added
- Out-of-AGDT evaluation (`greek.evaluate_on_proiel`): scores the lemmatizer/tagger against
  PROIEL (Greek NT + Herodotus), a source none of pyaegean's models train on. Fetched for
  evaluation only (CC BY-NC-SA 3.0).
- Cypro-Minoan (`aegean.scripts.cyprominoan`): a 99-sign inventory from the Unicode Character
  Database, sign inventory and tokenization only (undeciphered; no transliteration or
  bridge).

## 0.4.0 (2026-06-10)

### Added
- Linear B script (`aegean.scripts.linearb`): a 211-sign inventory and phonetic map,
  `word_to_phonetic` transliteration, and `Corpus.load("linearb")`.
- Linear B → Greek bridge (`greek_reading`, `gloss`): a curated Mycenaean→Greek lexicon
  (`PO-ME → ποιμήν`).
- Linear B accounting: the engine recognises `to-so`/`to-sa` totals (markers are per-script).
- Bring-your-own Linear B corpus: a DAMOS-style EpiDoc reader (the `[epidoc]` extra) via
  `PYAEGEAN_LINEARB_CORPUS`. No Linear B corpus is bundled (DAMOS is CC BY-NC-SA).
- Cypriot syllabary (`aegean.scripts.cypriot`): a 55-sign inventory, transliteration, a
  curated Cypriot→Greek bridge (`PA-SI-LE-U-SE → βασιλεύς`), and a sample corpus.

### Changed
- Linear B and Cypriot sign data bundled from the Unicode Character Database (Unicode-3.0
  license; attribution in NOTICE).

## 0.3.0 (2026-06-10)

### Added
- Generalizing POS tagger (opt-in `greek.use_tagger()`): an averaged-perceptron sequence
  tagger (pure Python) trained on the AGDT, predicting POS for unseen forms. 84.4% overall /
  83.6% on unseen forms (90/10 AGDT split). Built on first use, cached.
- Generalizing lemmatizer (opt-in `greek.use_lemmatizer()`): a Chrupała edit-tree model with
  an averaged-perceptron reranker (pure Python). 84.5% overall / 40.3% on unseen forms.
- Neural lemmatizer backend (opt-in `[neural]`, `greek.use_neural_lemmatizer()`): a
  fine-tuned GreTa seq2seq exported to ONNX, 76.3% on unseen forms, ~92% overall as a hybrid
  with a bundled gold lookup. Torch-free numpy decode over int8 ONNX. Model (~232 MB,
  CC BY-SA) fetched to cache.
- Leakage-free held-out evaluation (`aegean.greek.heldout`): splits the AGDT by sentence and
  scores on the unseen subset.

### Changed
- `pos_tag`/`pos_tags` and `lemmatize` consult the trained backends (when active) for forms
  the lexicon and treebank lookup don't cover.
- Core has zero hard third-party dependencies: pandas moved to `[data]`, scipy dropped (the
  two collocation statistics are now pure stdlib). *Breaking only if you called
  `to_dataframe()` without `[data]`.*
- Footprint policy replaces the wheel-size guard.

## 0.2.0 (2026-06-08)

### Added
- LSJ glossing (opt-in `greek.use_lsj()`): fetches the Perseus LSJ lexicon (CC BY-SA 4.0,
  ~270 MB) and builds a derived index; `gloss(word)` / `lookup(word)`. Composes with the
  lemmatizer (`ἀνδρός` → `ἀνήρ`).
- Dependency parser (opt-in baseline, `greek.use_parser()`): an arc-eager
  averaged-perceptron parser (pure Python); `parse()` returns a `DepTree`, `evaluate()`
  reports held-out UAS/LAS (~0.67 / 0.57 projective). Arc-eager builds only projective trees.
- A revamped end-to-end tutorial notebook.

### Changed
- Documentation refreshed across the README and wiki for the 0.2.0 Greek NLP track.

## 0.1.0 (2026-06-08)

First public release (alpha). A specialist toolkit for Ancient Greek and the Aegean syllabic
scripts; analysis of the undeciphered Linear A material is always labeled exploratory.

### Added
- Core (`aegean.core`): a script-agnostic model (`Corpus`, `Document`, `Token`, `Sign`,
  `SignInventory`, `Numeral`, a `Script` plugin registry, and `Provenance`).
- Linear A (`aegean.scripts.lineara`): a bundled 1,721-inscription corpus, 84-sign
  inventory, sign→sound map, and transliteration.
- Analysis (`aegean.analysis`): accounting reconciliation, wildcard sign search, phonetic
  distance + alignment, morphology clustering, collocation statistics, a query engine, and
  tablet-structure classification.
- Greek NLP (`aegean.greek`): normalization, tokenization, syllabification, accent and
  prosody, dactylic scansion, reconstructed IPA, POS tagging, a rule-based morphological
  analyzer, a baseline lemmatizer, and an opt-in Perseus AGDT treebank backend.
- AI layer (`aegean.ai`, `aegean.translate`): a provider-agnostic LLM client (Anthropic,
  OpenAI, Grok, Gemini), response caching, corpus grounding, and hybrid translation. Every
  generative result is a provenanced, exploratory-labeled `ExploratoryResult`.
- Data (`aegean.data`): bundled JSON corpora plus a `fetch()` download-to-cache layer
  (sha256-verified) for large assets.

### Notes
- Requires Python ≥ 3.10. `numpy`/`pandas`/`scipy` and provider SDKs are imported lazily.
- Licensing: code Apache-2.0; Linear A corpus JSON via GORILA/mwenge; Linear A imagery not
  redistributed; Perseus AGDT is CC BY-SA 3.0 (fetched, not bundled). See `NOTICE`.
