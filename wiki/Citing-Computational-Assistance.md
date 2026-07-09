# Citing computational assistance

If pyaegean helped produce a result in your work, cite what it used, so a reader can trace the
claim: the edition or dataset, the tool and its version, the exact number, and any place a
human corrected the automated output. This page shows how. It is a how-to for citing your own
work, not a methods paper about pyaegean.

The guiding idea matches the rest of the toolkit: name the register. An **established** fact,
a **measured** number, and an **exploratory** reading are three different kinds of claim, and a
citation should make clear which one you are leaning on.

## Cite the corpus (or the exact subset)

Every corpus carries its provenance (source edition, license, citation), and any filtered
subset carries a note recording the filter, so you cite precisely what you used:

```python
from aegean import load
c = load("isicily")
print(c.cite())                       # a ready citation line for the whole corpus
print(c.provenance.bibtex())          # BibTeX
print(c.provenance.apa())             # APA

sub = c.filter(site="Catina")
print(sub.cite())                     # cites the corpus AND records "subset: filter(site='Catina')"
```

A query result cites exactly the query behind it (`QueryResults.cite()`), so a table in a
paper can point at the precise slice of the corpus that produced it. Underlying editions keep
their own rights: cite the original edition too (each document's provenance names it).

## Cite the tool and its version

Reproducibility needs the version. `aegean.__version__` and the repository's `CITATION.cff`
(GitHub renders it as a "Cite this repository" button giving APA and BibTeX) identify the
release. Pin the exact version in a paper so the numbers are reproducible:

```python
import aegean
print(aegean.__version__)
```

## Cite a measured number reproducibly

Measured claims come from a recorded protocol ([Methodology](Methodology),
[Benchmarks](Benchmarks)). For a number you report, an **evaluation receipt**
(`aegean.greek.eval_receipt`) is a content-addressed record of the settings that produced it,
so the figure in your paper can be checked. Cite the number with its protocol, not on its own.

## Cite reviewed (human-corrected) output

If you exported machine annotations, corrected them, and used the corrected corpus (see
[When the Tool Is Wrong](When-the-Tool-Is-Wrong)), that corpus records the correction: each
corrected token keeps the machine value under a `<field>__pred` key, and the provenance gains a
`review:` note. Say so in your methods: which fields were machine-produced, that a human
reviewed them, and who. That is more honest than presenting corrected output as if it were
either fully automated or fully hand-done.

## Cite exploratory output as exploratory

Exploratory results (Linear A / Cypro-Minoan structure, AI readings, generative translation)
are labeled unverified at the point of use, and a citation should carry that label: present
them as hypotheses generated with computational assistance, not as readings. Do not let a
formatted table launder an exploratory result into an established one.

## A worked phrasing

> Inscriptions were read from I.Sicily (Prag et al., CC BY 4.0) as distributed in pyaegean
> vX.Y.Z; lemma and part-of-speech annotations were produced by pyaegean's neural joint
> pipeline and reviewed by the author, with corrections recorded in the corpus provenance;
> the reported lemma accuracy is the UD-Perseus test figure from the project's benchmark
> protocol.

## See also

- [Data & Provenance](Data-and-Provenance): what provenance records and how to pin a data snapshot.
- [For Specialists](For-Specialists): the register model in full.
- [Benchmarks](Benchmarks) and [Methodology](Methodology): the measured numbers and the protocol.
