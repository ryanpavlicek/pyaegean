"""AGDT (Prague-style) → UD dependency conversion for Stage C training trees.

Authored transforms + a POS-sensitive label map, **validated against** the UD-Perseus
train fold (validate_agdt_ud_deps.py; the UD folds are CC BY-NC-SA — evaluation/
validation only). The Prague→UD differences are structural, not just labels:

- **Coordination**: Prague heads conjuncts on the conjunction (``X_CO`` children of
  ``COORD``); UD promotes the first conjunct and chains the rest as ``conj``, the
  conjunction becoming ``cc`` on the conjunct that follows it.
- **AuxP**: prepositions head their phrase in Prague; UD promotes the complement and
  demotes the preposition to ``case``.
- **AuxC**: subordinators head their clause; UD promotes the verb and demotes the
  conjunction to ``mark``.
- **Copula**: εἰμί heads its predicate (``PNOM``); UD promotes the predicate and demotes
  the copula to ``cop``, re-attaching its other dependents to the promoted node.
- **AuxK** (final punctuation) re-attaches to the root token; ``APOS`` operators become
  ``punct``/``appos`` chains. Everything else is a label map keyed on the AGDT relation
  and coarse POS (note: the UD-Perseus convention prefers ``nmod`` over ``amod``).

The converter runs at dataset-build time on gold AGDT trees; the trained parser predicts
UD heads/relations directly, so inference needs none of this.

Input: ``words`` = one sentence's real (form-bearing) tokens, each a dict with ``id``,
``head``, ``relation``, ``form``, ``lemma``, ``xpos`` (AGDT attribute strings).
Output: ``[(head, deprel), …]`` per token — heads 1-based into the same list, 0 = root.
"""

from __future__ import annotations

from agdt_ud import _strip

__all__ = ["convert_tree"]

_PUNCT_RELS = ("AuxK", "AuxX", "AuxG")
_COPULA = frozenset({"ειμι"})
_AUX_BYSTANDERS = frozenset({"AuxX", "AuxG", "AuxK", "AuxY", "AuxZ", "COORD", "APOS"})


def _base(rel: str) -> str:
    """The relation without coordination/apposition suffixes (``OBJ_CO`` → ``OBJ``)."""
    return rel.split("_", 1)[0] if rel else ""


def _label(rel: str, xpos: str, *, in_aux_p: bool = False, in_aux_c: bool = False) -> str:
    """The UD deprel for an AGDT relation, keyed on coarse POS (``xpos[0]``)."""
    pos = xpos[:1] if xpos else "-"
    base = _base(rel)
    if base in _PUNCT_RELS:
        return "punct"
    if base == "PRED":
        return "root"
    if base == "SBJ":
        # finite/infinitive verbal subjects are clausal; substantivized participles are nominal
        return "csubj" if pos == "v" and len(xpos) > 4 and xpos[4] != "p" else "nsubj"
    if base == "OBJ":
        if in_aux_p:
            return "obl"
        if pos == "v":
            # finite verbs are clausal objects; infinitives/participles open complements
            return "ccomp" if len(xpos) > 4 and xpos[4] in "isom" else "xcomp"
        return "obj"  # the dative iobj case is sibling-dependent — handled in convert_tree
    if base == "ATR":
        if pos == "l":
            return "det"
        if pos == "m":
            return "nummod"
        if pos == "v":
            return "acl"
        return "nmod"
    if base == "ADV":
        if in_aux_p:
            return "obl"
        if in_aux_c or pos == "v":
            return "advcl"
        if pos in ("n", "p", "l", "m"):
            return "obl"
        return "advmod"  # adverbs AND adverbial-accusative adjectives
    if base in ("PNOM", "ATV", "AtvV", "OCOMP"):
        return "xcomp"
    if base in ("AuxY", "AuxZ"):
        return "case" if pos == "r" else "advmod"  # AuxZ "improper prepositions"
    if base == "AuxP":
        return "case"
    if base == "AuxC":
        return "mark"
    if base == "AuxV":
        return "aux"
    if base in ("COORD", "APOS"):
        return "cc"
    if base == "ExD":
        return "vocative" if pos in ("n", "p", "a") else "advmod"
    return "dep"


def convert_tree(words: list[dict]) -> list[tuple[int, str]]:
    n = len(words)
    id2idx = {w.get("id"): i for i, w in enumerate(words)}
    rels = [w.get("relation") or "" for w in words]
    xpos = [(w.get("xpos") or w.get("postag") or "").ljust(9, "-") for w in words]
    lemma = [_strip(w.get("lemma") or "") for w in words]
    head0 = [-1] * n  # original 0-based parents (-1 = root); heads on dropped nodes → root
    for i, w in enumerate(words):
        h = w.get("head") or "0"
        head0[i] = -1 if h == "0" else id2idx.get(h, -1)

    out_head = list(head0)              # evolving structure
    fixed: list[str | None] = [None] * n  # deprels set structurally
    in_aux_p = [False] * n
    in_aux_c = [False] * n

    def kids_of(i: int) -> list[int]:
        return [c for c in range(n) if out_head[c] == i]

    def move_children(src: int, dst: int, keep: set[int]) -> None:
        for c in range(n):
            if out_head[c] == src and c != dst and c not in keep:
                out_head[c] = dst

    # innermost-first: deepest nodes restructure before their ancestors
    def depth(i: int) -> int:
        d, j = 0, i
        while head0[j] >= 0 and d <= n:
            d, j = d + 1, head0[j]
        return d

    for i in sorted(range(n), key=lambda i: -depth(i)):
        base = _base(rels[i])
        kids = kids_of(i)

        if base in ("COORD", "APOS"):
            suffix = "_CO" if base == "COORD" else "_AP"
            members = [c for c in kids if rels[c].endswith(suffix)]
            if not members:
                continue
            first, rest = members[0], members[1:]
            out_head[first] = out_head[i]
            in_aux_p[first] = in_aux_p[first] or in_aux_p[i]
            in_aux_c[first] = in_aux_c[first] or in_aux_c[i]
            rels[first] = _base(rels[first])  # the conjunct keeps its own role, suffix-free
            for r in rest:
                out_head[r] = first
                fixed[r] = "appos" if base == "APOS" else "conj"
            # the coordinator attaches to the first conjunct (UD-Perseus convention)
            out_head[i] = first
            fixed[i] = "punct" if base == "APOS" or xpos[i][0] == "u" else "cc"
            # separator punctuation between conjuncts attaches FORWARD, to the next member;
            # other shared dependents re-attach to the first conjunct
            for c in range(n):
                if out_head[c] != i or c == first or c in rest:
                    continue
                if _base(rels[c]) in ("AuxX", "AuxG") or xpos[c][0] == "u":
                    nxt = [m for m in members if m > c]
                    out_head[c] = nxt[0] if nxt else first
                    fixed[c] = "punct"
                else:
                    out_head[c] = first

        elif base == "AuxP":
            payload = [c for c in kids if _base(rels[c]) not in _AUX_BYSTANDERS
                       and _base(rels[c]) != "AuxP"]
            if not payload:
                continue
            promoted = payload[-1]
            out_head[promoted] = out_head[i]
            in_aux_p[promoted] = True
            out_head[i] = promoted
            fixed[i] = "case"
            move_children(i, promoted, keep={i, promoted})

        elif base == "AuxC":
            payload = [c for c in kids if _base(rels[c]) not in _AUX_BYSTANDERS
                       and _base(rels[c]) != "AuxC"]
            if not payload:
                continue
            promoted = payload[-1]
            out_head[promoted] = out_head[i]
            in_aux_c[promoted] = True
            out_head[i] = promoted
            fixed[i] = "mark"
            move_children(i, promoted, keep={i, promoted})

        elif xpos[i][0] == "v" and lemma[i] in _COPULA and fixed[i] is None:
            pnoms = [c for c in kids if _base(rels[c]) == "PNOM"]
            if not pnoms:
                continue
            promoted = pnoms[0]
            out_head[promoted] = out_head[i]
            in_aux_p[promoted] = in_aux_p[i]
            in_aux_c[promoted] = in_aux_c[i]
            rels[promoted] = rels[i]          # the predicate takes the copula's role
            out_head[i] = promoted
            fixed[i] = "cop"
            move_children(i, promoted, keep={i, promoted})

    # AuxK (final punctuation) hangs off the root token; force a single root
    roots = [i for i in range(n) if out_head[i] == -1]
    root_tok = roots[0] if roots else 0
    for i in range(n):
        if _base(rels[i]) == "AuxK" and fixed[i] is None:
            if i != root_tok:
                out_head[i] = root_tok
            fixed[i] = "punct"
    roots = [i for i in range(n) if out_head[i] == -1]
    root_tok = roots[0] if roots else 0
    for i in roots[1:]:
        out_head[i] = root_tok
        if fixed[i] is None:
            fixed[i] = "parataxis"

    result: list[tuple[int, str]] = []
    for i in range(n):
        head = out_head[i] + 1 if out_head[i] >= 0 else 0
        rel = fixed[i]
        if rel is None:
            rel = _label(rels[i], xpos[i], in_aux_p=in_aux_p[i], in_aux_c=in_aux_c[i])
        if head == 0:
            rel = "root"
        elif rel == "root":
            rel = "parataxis"  # a PRED no longer at the root
        result.append((head, rel))

    # dative iobj is sibling-dependent: an OBJ dative is iobj only beside a direct object
    for i in range(n):
        if result[i][1] == "obj" and len(xpos[i]) > 7 and xpos[i][7] == "d":
            h = result[i][0]
            has_direct = any(
                j != i and result[j][0] == h and result[j][1] == "obj"
                and len(xpos[j]) > 7 and xpos[j][7] == "a"
                for j in range(n)
            )
            if has_direct:
                result[i] = (h, "iobj")

    # two child-dependent label refinements (measured on the UD train fold):
    # - an attributive participle with dependents is a (reduced) relative clause → acl;
    #   a bare one is treated like a nominal attribute → nmod
    # - an infinitive object with its own subject (accusative-with-infinitive) → ccomp
    has_kid = [False] * n
    for h, _r in result:
        if h > 0:
            has_kid[h - 1] = True
    for i in range(n):
        if result[i][1] == "acl" and _base(rels[i]) == "ATR" and not has_kid[i]:
            result[i] = (result[i][0], "nmod")
        elif result[i][1] == "xcomp" and _base(rels[i]) == "OBJ" and xpos[i][4] == "n":
            if any(out_head[j] == i and _base(rels[j]) == "SBJ" for j in range(n)):
                result[i] = (result[i][0], "ccomp")
    return result
