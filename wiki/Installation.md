# Installation

pyaegean requires **Python ≥ 3.10**. The core stays import-light:
`numpy`/`pandas`/`scipy` are imported lazily (only inside DataFrame interop and
the collocation statistics), and provider AI SDKs are optional extras imported
lazily inside their adapters — so `import aegean` is fast and dependency-light.

## From PyPI

```bash
pip install pyaegean            # core + Linear A + Greek NLP
```

### Optional extras

| Extra | Pulls in | For |
| --- | --- | --- |
| `pyaegean[anthropic]` | `anthropic` | Anthropic (default) AI provider |
| `pyaegean[openai]` | `openai` | OpenAI provider |
| `pyaegean[grok]` | `openai` | xAI Grok (OpenAI-API-compatible) |
| `pyaegean[gemini]` | `google-genai` | Google Gemini provider |
| `pyaegean[ai]` | all of the above | the full AI layer |
| `pyaegean[epidoc]` | `lxml` | EpiDoc I/O |
| `pyaegean[geo]` | `geopandas`, `shapely` | geographic analysis |
| `pyaegean[all]` | everything | |

```bash
pip install "pyaegean[ai]"
pip install "pyaegean[all]"
```

## Verify

```python
import aegean
print(aegean.__version__)
print(aegean.registered_scripts())       # ['greek', 'lineara']
print(len(aegean.load("lineara")))        # 1721
print(len(aegean.load("greek")))          # 5  (bundled sample corpus)
```

## Offline & data

The compact text corpora (Linear A inscriptions/signs, Greek seeds) ship inside
the wheel and work fully offline. Large assets — notably the ~116 MB Linear A
facsimile imagery — are **not** bundled; they are fetched on demand into a user
cache. See [Data & Provenance](Data-and-Provenance).

## From source

See [Development](Development).
