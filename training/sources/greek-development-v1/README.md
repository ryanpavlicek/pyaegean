# Greek development sources

This collection contains the full upstream PapyGreek documentary collection, a curated diplomatic evaluation subset, an independently located tragedy passage, two plays in review and fourteen training-exposed tragic works. Their editorial status and training histories determine which questions each can answer. The collection is separate from the installed package and the frozen 1,344-item v3 development manifest.

| Material in this directory | What is available | Suitable use |
|---|---|---|
| PapyGreek native diplomatic | 75 approved documents, 317 sentences, 5,317 eligible non-punctuation lemma targets. A conservative export contains 44 basic trees and 241 surface words. | Measure native diplomatic lemmatization. Describe parsing on the smaller, explicitly converted subset. |
| Digital Hill, Euripides’ *Suppliants* 447–449 | One sentence, 18 lexical words and two punctuation marks. Marcel Mernitz annotated the source XML. | Inspect individual analyses. One passage cannot support a genre estimate or calibration. |
| Daphne, Sophocles’ *Philoctetes* and Euripides’ *Iphigenia in Tauris* | Two complete CoNLL-U source files, 1,832 sentences and 21,171 integer-ID words. Both works are marked `in_review`. | Select passages for independent editorial review. The manifest identifies 76 sentences with protected text overlap. |
| AGDT v2.1 and KU Leuven Pedalion | Twelve native AGDT tragedy files, Pedalion’s complete *Medea* and the surviving *Exagoge* fragments. Together they contributed 8,928 v3 training rows. | Training-exposed for v3. A future independently trained model could evaluate withheld works after a new lineage and split audit. |

## Diplomatic papyri

Helsinki’s XML records separate annotations for the editorial regularization and the original reading. The project names a reviewer for the original layer in each accepted document. The release’s existing original-surface benchmark uses regularized targets on both renderings. Its scores and the native-label task here answer different questions. The linked upstream research describes the review process. [PapyGreek publication](https://doi.org/10.5334/johd.55) · [Versioned source and CC BY-SA 4.0 terms](https://github.com/ezhenrik/papygreek-treebanks/tree/0e5139b06e41d89275f3a1ace4ee0dc5513f2f7d)

- `upstream/papygreek-documentary.tar.gz` preserves **all 558** upstream documentary XML files byte-for-byte, with the original guide and license. It includes protected, training-overlapping, unscored and partially annotated material. Read the XML freely for source study. Use the curated task masks and work exclusions for model development.
- `papygreek-native.jsonl.gz` has one record per included sentence. It preserves all source word attributes, both layers, native IDs and artificial nodes. The mask `lemma_token_ids` selects eligible native targets. There are 6,732 real surface tokens in context. Native form, head or lemma values can be incomplete outside the scoring masks.
- `papygreek-lemmas.tsv.gz` has one row per eligible native lemma, keyed by sentence and native word ID. FORM derives from `orig_form`, with the established apparatus policy applied. LEMMA derives from `lemma_orig`, with the existing NFC, homonym and numeral conventions. Unresolved readings, non-Greek targets, artificial tokens and punctuation are excluded. Source XPOS is descriptive. Compare original and regularized surfaces on the same 5,317 tokens. They differ on 267. Among targets with a comparable regularized lemma, 16 normalized lemmas differ.
- `papygreek-basic-ud.conllu.gz` contains the complete basic-tree subset. The shared AGDT conversion receives only original-layer fields. The filter requires usable readings and source annotations on every real word, supported ellipsis handling and a complete single-root output. Punctuation lemmas follow the project convention. Use the exported trees for UD comparisons and the JSONL for native annotation.
- `manifest.json` records source paths, hashes, original-layer credits, coverage and mandatory grouping by Trismegistos (TM) work identity. Of the 317 sentences, 298 have a counterpart in the frozen regularized development set. Preserve every view of a document together. Three sets of distinct TM IDs also share identical normalized sentences. The resulting 71 groups are an upper bound on independent split units. Source selection and historical reuse still matter.

## Tragedy

`tragedy-diagnostic/` preserves the Digital Hill XML and adds a basic UD projection through pyaegean’s AGDT converter. The entire normalized lexical sequence matches the independent Greek edition at the specified lines. The upstream XML uses Smyth3 labels and gives πῶς the lemma πως. Retain such decisions for editorial inspection and distinguish the converted UD labels from the human-authored layer. [Digital Hill source](https://github.com/DigitalHill/treebank-data/blob/0bf1de02722c22afc5c069a61d2c1a586d85be0d/euripides/eurip_suppl_447_449.xml) · [Greek reference edition](https://github.com/PerseusDL/canonical-greekLit/blob/dacb04909e43dc47738828d33cc3d2b0635bc54c/data/tlg0006/tlg008/tlg0006.tlg008.perseus-grc2.xml)

`tragedy-in-review/` contains the two complete Daphne files exactly as supplied after decompression. *Philoctetes* has 929 sentences and 10,954 words, plus 176 empty nodes. *Iphigenia in Tauris* has 903 sentences and 10,217 words. The latter file is called *Ion* in Daphne’s catalogue. Its work identifier, opening and sustained four-word matches against the canonical Greek identify *Iphigenia in Tauris*. In the independent edition, *Ion* is `tlg0006.tlg010`. The manifest preserves the published title and the text-based identification. Both work records indicate that review is in progress and validation has not run. Across them, 1,756 sentences survive the protected-text check and are available for editorial sampling. Use the work ID with the numeric upstream sentence ID. [Daphne catalogue](https://github.com/francescomambrini/Daphne/blob/06aa1f27a34af98bba1407dc95fe2085a72f8b7f/data/catalog.yaml) · [Daphne review policy](https://github.com/francescomambrini/Daphne/blob/06aa1f27a34af98bba1407dc95fe2085a72f8b7f/data/STATUS.md) · [Greek edition and title](https://github.com/PerseusDL/canonical-greekLit/tree/dacb04909e43dc47738828d33cc3d2b0635bc54c/data/tlg0006/tlg013)

`tragedy-v3-training/` contains 14 native source files with scholarly credits. The 12 AGDT files cover Sophocles’ *Trachiniae*, *Antigone*, *Ajax*, *Oedipus Tyrannus* and *Electra*, and Aeschylus’ *Suppliant Women*, *Persians*, *Prometheus Bound*, *Seven Against Thebes*, *Agamemnon*, *Libation Bearers* and *Eumenides*. The repository distributes each entire upstream file. Coverage follows the annotated edition and passage ranges. Pedalion adds Euripides’ *Medea* and the surviving portions of Ezekiel’s *Exagoge*. The manifest reports the source sentence count and the actual supervised row count separately for each. The 8,931 source sentences account for 8,928 v3 training rows. Aeschylus’ *Suppliant Women* is a different work from the Digital Hill Euripides passage. To reserve one for a future evaluation, exclude the entire work, other editions, its lookup entries, teacher supervision and distillation lineage, silver labels, and identifiable pretraining passages before fitting. Record unknown base-model exposure. Protect the separate locked *Bacchae* test. [AGDT files](https://github.com/PerseusDL/treebank_data/tree/bf4334f0af5e13d16b04c1cccd6237e683ac6f5f/v2.1/Greek/texts) · [Pedalion data and CC BY-SA 4.0 terms](https://github.com/perseids-publications/pedalion-trees/tree/112c106b86b865ddde4be7e5f3e409d9c42689f9) · [AGDT attribution and CC BY-SA 3.0 US terms](https://github.com/PerseusDL/treebank_data/blob/bf4334f0af5e13d16b04c1cccd6237e683ac6f5f/README.md)

## Reproduce or inspect the files

The [manifest](manifest.json) gives SHA-256 digests for each exported data file and its source. The sixteen compressed tragedy source files reproduce their upstream bytes after decompression. The [source survey](SOURCES.md) records the primary catalogues and other collections investigated.

From a pyaegean checkout, prepare the historical training rows with the pinned builder. The builder fetches its registered AGDT, Gorman, Pedalion, Perseus and PROIEL inputs to the project cache. Use Python 3.10 or later with the project importable.

```bash
git worktree add --detach ../pyaegean-v3-source a027c0a848a464d218129701e48902dc9b425040
PYTHONPATH=../pyaegean-v3-source/src python ../pyaegean-v3-source/training/build_full_dataset.py \
    --with-extras --out ../v3-rows
```

Check out the following source repositories at the indicated revisions. The preparation command uses their literal directory names. The checked-in documentary archive can also be extracted to the PapyGreek input directory. An archive extracted to the same layout also works. For canonical-greekLit only the three Greek edition XML files named in the builder are required.

| Local directory | Repository | Revision |
|---|---|---|
| `../papygreek-treebanks` | [ezhenrik/papygreek-treebanks](https://github.com/ezhenrik/papygreek-treebanks) | `0e5139b06e41d89275f3a1ace4ee0dc5513f2f7d` |
| `../pedalion-trees` | [perseids-publications/pedalion-trees](https://github.com/perseids-publications/pedalion-trees) | `112c106b86b865ddde4be7e5f3e409d9c42689f9` |
| `../DigitalHill-treebank-data` | [DigitalHill/treebank-data](https://github.com/DigitalHill/treebank-data) | `0bf1de02722c22afc5c069a61d2c1a586d85be0d` |
| `../canonical-greekLit` | [PerseusDL/canonical-greekLit](https://github.com/PerseusDL/canonical-greekLit) | `dacb04909e43dc47738828d33cc3d2b0635bc54c` |
| `../Daphne` | [francescomambrini/Daphne](https://github.com/francescomambrini/Daphne) | `06aa1f27a34af98bba1407dc95fe2085a72f8b7f` |
| `../treebank_data` | [PerseusDL/treebank_data](https://github.com/PerseusDL/treebank_data) | `bf4334f0af5e13d16b04c1cccd6237e683ac6f5f` |

```bash
python training/sources/greek-development-v1/prepare.py \
    --training ../v3-rows --papygreek ../papygreek-treebanks \
    --pedalion ../pedalion-trees/public/xml/papyri.xml \
    --hill ../DigitalHill-treebank-data/euripides/eurip_suppl_447_449.xml \
    --canonical ../canonical-greekLit --daphne ../Daphne --agdt ../treebank_data \
    --out ../rebuilt-greek-development
```

The exposure index verifies the two release training/development file digests using their historical CRLF serialization. It indexes lexical forms from the 76,149 training rows and the 1,137 development rows, protected Perseus and PROIEL references, both locked PapyGreek surfaces, *Bacchae*, DBBE and Nestle 1904. Seven training rows have no normalized lexical words. Candidate forms are compared as normalized whole sentences and contiguous eight-word windows after case, accent, punctuation and elision normalization. For papyri the check uses both written and regularized forms and excludes the 450 locked document names and the corresponding TM works, plus 112 Pedalion training TM IDs. One additional catalogue name pointed to a locked work. Surface matching cannot establish the original encoder’s pretraining inventory or detect every quotation or retokenization. Preserve these bounds when describing independence.
