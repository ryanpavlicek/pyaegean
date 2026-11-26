# `aegean.library`

Unified manager for every corpus, Biblical text bundle, Greek literary work, patristic commentary, lexicon, and neural model supported by pyaegean.

```python
from aegean import library

# Local inventory and pack completion
print(library.summary()["installed_size"])
for pack in library.list_packs():
    print(pack.pack.id, f"{pack.installed_count}/{pack.total_count}")

# Search across all 47 hosted datasets, 3,844 Greek collection works, 1,778 Perseus/First1KGreek works, 112 commentaries, lexica, and models
hits = library.search("Chrysostom", limit=5)

# Install by pack name, alias, dataset ID, work title, TLG/OGC ID, or author:<name>
library.install("biblical")
library.install(["church-fathers", "Iliad"])

# Safely delete downloaded files to reclaim disk space
library.remove("damos")
```

::: aegean.library
