# conda-forge packaging for `pyaegean`

This directory holds the conda-forge v1 (`rattler-build`) recipe for
`pyaegean` core (`noarch: python`, zero third-party runtime dependencies).

## Submitting to `conda-forge/staged-recipes`

1. Fork [conda-forge/staged-recipes](https://github.com/conda-forge/staged-recipes)
   and create a branch from `main`.
2. Copy [`recipe.yaml`](recipe.yaml) to `recipes/pyaegean/recipe.yaml` in the
   staged-recipes fork.
3. Verify the version and `sha256` against the current PyPI source distribution:
   ```bash
   python3 -c 'import json, urllib.request; d = json.loads(urllib.request.urlopen("https://pypi.org/pypi/pyaegean/json").read()); print(d["info"]["version"], [u["digests"]["sha256"] for u in d["urls"] if u["packagetype"] == "sdist"])'
   ```
   When bumping from `0.73.1` to `0.74.0+`, add `- aegean.browser` to
   `tests[0].python.imports`.
4. Open a pull request against `conda-forge/staged-recipes` and complete the
   conda-forge recipe checklist.

## Installing optional extras in a conda environment

The base `pyaegean` feedstock installs the zero-dependency core (including
bundled corpora, Greek rule-based NLP, and the stdlib local visual corpus
browser in `0.74.0+`). Optional extras install cleanly from `conda-forge`
alongside `pyaegean`:

| Feature | conda-forge packages |
|---|---|
| CLI (`aegean`) | `typer >=0.16` `rich >=13` `prompt_toolkit >=3.0` |
| TUI (`aegean tui`) | `textual >=8.0` + CLI packages |
| Neural Greek NLP (`[neural]`) | `onnxruntime >=1.23` `tokenizers >=0.20` `numpy >=1.24` |
| DataFrames & Parquet (`[data,parquet]`) | `pandas >=2.2.2` `pyarrow >=16.1` |
| Geospatial (`[geo]`) | `geopandas >=0.14` `shapely >=2.0.4` |
| EpiDoc XML (`[epidoc]`) | `lxml >=5.0` |
| Plots (`[viz]`) | `matplotlib-base >=3.8` |
