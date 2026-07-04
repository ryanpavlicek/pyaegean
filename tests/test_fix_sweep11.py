"""Regression guards for the executable-docs sweep (0.19.13).

The wiki shows specific `dispersion` and `cooccur` outputs on the bundled Linear A
corpus. Those drifted (a tie-order shift after the 0.19.6 dispersions rewrite, and a
sign-count change) without any test noticing, so a doc reader saw a stale result. These
pin the exact shown outputs, so the next change that alters them fails here and forces
the documentation to be updated in the same commit.
"""

from __future__ import annotations

import aegean


def test_dispersion_top5_matches_the_docs():
    """Pins the top-5 dispersion order shown in Analysis.md / CLI.md. The sort is
    deterministic (dp_norm, then -frequency, then item), so the order is stable; this
    catches a silent drift of the shown result."""
    from aegean.analysis import dispersions

    c = aegean.load("lineara")
    top5 = [(x.item, round(x.dp_norm, 2)) for x in dispersions(c, top=5)]
    assert top5 == [
        ("KU-RO", 0.85), ("KI-RO", 0.94), ("SA-RA₂", 0.95), ("KU-PA₃-NU", 0.95), ("A-DU", 0.96),
    ]
    # the tie at 0.949 breaks by higher frequency first (SA-RA₂ 20 before KU-PA₃-NU 8)
    rows = dispersions(c, top=5)
    sara2 = next(r for r in rows if r.item == "SA-RA₂")
    kupanu = next(r for r in rows if r.item == "KU-PA₃-NU")
    assert round(sara2.dp_norm, 3) == round(kupanu.dp_norm, 3)
    assert sara2.frequency > kupanu.frequency
    assert list(rows).index(sara2) < list(rows).index(kupanu)


def test_cooccur_top5_matches_the_docs():
    """Pins the top-5 co-occurrence order shown in CLI-Cheatsheet.md (ranked by shared
    documents, ties broken alphabetically, so it is reproducible)."""
    from collections import Counter

    c = aegean.load("lineara")
    counter: Counter[str] = Counter()
    for d in c:
        words = {t.text for t in d.words if "-" in t.text}
        if "KU-RO" in words:
            counter.update(w for w in words if w != "KU-RO")
    ranked = sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))[:5]
    assert ranked == [
        ("KI-RO", 5), ("*306-TU", 4), ("KU-PA₃-NU", 4), ("SA-RA₂", 4), ("*324-DI-RA", 3),
    ]


def test_lineara_sign_value_count_is_50_everywhere_it_is_documented():
    """The Linear A assigned-sound-value count is 50 (the ZE/ZO reading, 0.19.8). This
    pins the number the docs state, since it drifted across several pages before."""
    inv = aegean.get_script("lineara").sign_inventory
    assert len([s for s in inv if s.phonetic]) == 50
    assert len(list(inv)) == 342
