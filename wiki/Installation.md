# Installation

pyaegean requires **Python ≥ 3.10**. The core has zero hard third-party
dependencies — the wheel ships code and JSON only, so `import aegean` is
instant. Everything heavier is an optional extra: `pandas` (DataFrame interop),
the provider AI SDKs, and the Greek NLP backends are all imported lazily inside
their adapters and pulled in only when you ask for them.

## From PyPI

```bash
pip install pyaegean            # core: Linear A + Greek, zero hard deps
```

### Optional extras

| Extra | Pulls in | For |
| --- | --- | --- |
| `pyaegean[data]` | `pandas` | DataFrame interop (`to_dataframe`) |
| `pyaegean[neural]` | `onnxruntime`, `tokenizers`, `numpy` | the neural Greek pipeline (`use_neural_pipeline()`) and lemmatizer (`use_neural_lemmatizer()`) |
| `pyaegean[anthropic]` | `anthropic` | Anthropic (default) AI provider |
| `pyaegean[openai]` | `openai` | OpenAI provider |
| `pyaegean[grok]` | `openai` | xAI Grok (OpenAI-API-compatible) |
| `pyaegean[gemini]` | `google-genai` | Google Gemini provider |
| `pyaegean[ai]` | all of the above providers | the full AI layer |
| `pyaegean[epidoc]` | `lxml` | EpiDoc I/O |
| `pyaegean[geo]` | `geopandas`, `shapely` | geographic analysis |
| `pyaegean[parquet]` | `pyarrow` | Parquet export (`io.to_parquet`) |
| `pyaegean[cli]` | `typer`, `rich` | the [`aegean` command line](CLI) |
| `pyaegean[all]` | `ai`, `epidoc`, `geo`, `data`, `cli` | everything except `neural` and `parquet` |

```bash
pip install "pyaegean[ai]"
pip install "pyaegean[neural]"
pip install "pyaegean[all]"
```

## Verify

```python
import aegean
print(aegean.__version__)
print(aegean.registered_scripts())       # ['cypriot', 'cyprominoan', 'greek', 'lineara', 'linearb']
print(len(aegean.load("lineara")))        # 1721
print(len(aegean.load("greek")))          # 5  (bundled offline sample; real works
                                          #     via greek.load_work("tlg0012.tlg001"))
```

## Offline & data

The compact text corpora (Linear A inscriptions/signs, Greek seeds) ship inside
the wheel and work fully offline. Large assets are **not** bundled — they are fetched
on demand into a user cache on first use: the ~116 MB Linear A facsimile imagery, plus
the opt-in Greek backends' data — the Perseus AGDT treebank (~75 MB,
`greek.use_treebank()`) and the full Perseus LSJ (~270 MB, `greek.use_lsj()`).
The pure-Python backends each cache a small trained model: `greek.use_parser()`,
`greek.use_tagger()`, and `greek.use_lemmatizer()`. The neural lemmatizer
(`greek.use_neural_lemmatizer()`, the `[neural]` extra) fetches a ~232 MB int8 ONNX
GreTa model; the neural joint pipeline (`greek.use_neural_pipeline()`, same extra)
fetches a ~518 MB fp32 ONNX model bundle. All remain offline after the first fetch.
See [Data & Provenance](Data-and-Provenance).

## From source

See [Development](Development).
