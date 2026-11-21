"""Rebuild the evaluation-source snapshots. No model or predictions are used."""

# ruff: noqa: E402 -- local conversion modules must follow the repository path setup.
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "training"), str(ROOT / "scripts")]
from aegean.greek.papygreek import papygreek_orig_path, papygreek_path
from aegean.greek.dbbe import dbbe_path
from aegean.greek.proiel import load_proiel_gold, proiel_dir
from aegean.greek.ud import ud_path
from aegean.greek.verse_eval import verse_path
from aegean.data import fetch
from build_papygreek_fold import (
    clean_lemma,
    is_clean_reading,
    papygreek_work_id,
    pedalion_training_work_reference,
    sentence_to_conllu,
    strip_apparatus,
)
from build_papygreek_dev import _reattach_single_artificial

PAP_TREE = "f2dcadbc70b92298f71b7855e43cea1c89d7f5994b8855aaf7b1f88523b2c57c"
NGRAM = 8
RESULTS = ROOT / "training" / "results"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    return json.loads(path.read_bytes())


def gz(path, content):
    with path.open("wb") as out, gzip.GzipFile(filename="", fileobj=out, mode="wb", mtime=0) as f:
        f.write(content.encode("utf-8") if isinstance(content, str) else content)
    return sha(path.read_bytes())


def conllu_blocks(text):
    return [block for block in text.strip().split("\n\n") if block.strip()]


def rows(block):
    return [line.split("\t") for line in block.splitlines() if line.split("\t", 1)[0].isdigit()]


@lru_cache(maxsize=160_000)
def letters(form):
    return "".join(
        c
        for c in unicodedata.normalize("NFD", form.replace("ʼ", "").replace("᾽", "")).casefold()
        if c.isalnum()
    )


def signature(forms):
    return tuple(v for w in forms if (v := letters(w)))


class Exposure:
    def __init__(self):
        self.sentences = set()
        self.shingles = set()
        self.counts = Counter()
        self.files = {}
        self.train_files = Counter()

    def add(self, forms, source):
        words = signature(forms)
        if not words:
            return
        self.counts[source] += 1
        self.sentences.add(words)
        self.shingles.update(words[i : i + NGRAM] for i in range(len(words) - NGRAM + 1))

    def overlap(self, forms):
        words = signature(forms)
        if words in self.sentences:
            return "sentence"
        if any(words[i : i + NGRAM] in self.shingles for i in range(len(words) - NGRAM + 1)):
            return "eight_words"
        return None


def exposure(training_dir):
    idx = Exposure()
    pins = read_json(ROOT / "training" / "development-source-pins.json")["expected_source_hashes"]
    for name in ("full-train.jsonl", "full-dev.jsonl"):
        path = training_dir / name
        raw = path.read_bytes().replace(b"\r\n", b"\n")
        digest = sha(raw.replace(b"\n", b"\r\n"))
        if digest != pins["training:" + name]:
            raise ValueError(f"{name} disagrees with the shipped training reference")
        idx.files[name] = digest
        for row in raw.splitlines():
            record = json.loads(row)
            idx.add(record["tokens"], name)
            if name == "full-train.jsonl":
                idx.train_files[record["file"]] += 1
    for name, path in [
        ("UD Perseus dev", ud_path("perseus", "dev")),
        ("UD Perseus test", ud_path("perseus", "test")),
        ("UD PROIEL test", ud_path("proiel", "test")),
        ("PapyGreek regularized test", papygreek_path()),
        ("PapyGreek diplomatic test", papygreek_orig_path()),
        ("Bacchae test", verse_path()),
        ("DBBE test", dbbe_path()),
    ]:
        raw = path.read_bytes()
        idx.files[name] = sha(raw)
        for block in conllu_blocks(raw.decode()):
            idx.add([r[1] for r in rows(block)], name)
    native_dir = proiel_dir()
    for name in ("greek-nt.xml", "hdt.xml"):
        idx.files["native PROIEL / " + name] = sha((native_dir / name).read_bytes())
    for sentence in load_proiel_gold():
        idx.add([word.form for word in sentence], "native PROIEL")
    nt_file = fetch("nt-corpus")
    idx.files["Nestle 1904"] = sha(nt_file.read_bytes())
    for chapter in read_json(nt_file)["documents"]:
        verses = defaultdict(list)
        for token in chapter["tokens"]:
            verses[token["v"]].append(token["t"])
        for verse in verses.values():
            idx.add(verse, "Nestle 1904")
    return idx


def artificial(token):
    return bool(token.get("artificial") or token.get("insertion_id"))


def orig_fields(token):
    # The shared AGDT converter names its input slots *_reg. Fill every one from orig.
    return {
        "id": token["id"],
        "form_reg": token.get("orig_form", ""),
        **{k + "_reg": token.get(k + "_orig", "") for k in ("lemma", "postag", "head", "relation")},
        **{k: token.get(k, "") for k in ("artificial", "insertion_id", "lang")},
    }


def lemma_target(token):
    raw = token.get("lemma_orig", "")
    lemma = clean_lemma(raw)
    tag = token.get("postag_orig", "")
    if (
        artificial(token)
        or token.get("lang", "grc") not in ("", "grc")
        or tag.startswith("u")
        or not is_clean_reading(strip_apparatus(token.get("orig_form", "")))
        or not is_clean_reading(lemma)
        or any(c in raw for c in "[]{}<>$")
    ):
        return None
    return lemma


def complete_tree(pairs, *, single_root=True):
    heads = dict(pairs)
    roots = sum(h == "0" for h in heads.values())
    if len(heads) != len(pairs) or not roots or (single_root and roots != 1):
        return False
    for node in heads:
        seen = set()
        while node != "0":
            if node in seen or node not in heads:
                return False
            seen.add(node)
            node = heads[node]
    return True


def basic_tree(words, sentence_id):
    if not words or any(
        not all(t.get(key) for key in ("id", "head_orig", "relation_orig")) for t in words
    ):
        return None
    # AGDT allows several words (often sentence punctuation) to attach to root 0.
    if not complete_tree([(t["id"], t["head_orig"]) for t in words], single_root=False):
        return None
    real = [t for t in words if not artificial(t)]
    if not real or any(
        not re.fullmatch(r"[a-z123-]{9}", t.get("postag_orig", ""))
        or (not t["postag_orig"].startswith("u") and not lemma_target(t))
        or not strip_apparatus(t.get("orig_form", ""))
        for t in real
    ):
        return None
    source = [orig_fields(t) for t in words]
    if len(real) < len(words):
        source = _reattach_single_artificial(source)
        if not source:
            return None
    if not complete_tree([(t["id"], t["head_reg"]) for t in source], single_root=False):
        return None
    block, _ = sentence_to_conllu(sentence_id, source)
    if not complete_tree([(r[0], r[6]) for r in rows(block)]):
        return None
    return block


def papyri(args, idx):
    files = sorted((args.papygreek / "documentary").rglob("*.xml"))
    binding = hashlib.sha256()
    for f in files:
        binding.update(
            f.relative_to(args.papygreek).as_posix().encode()
            + b"\0"
            + hashlib.sha256(f.read_bytes()).digest()
        )
    if binding.hexdigest() != PAP_TREE:
        raise ValueError("PapyGreek source snapshot mismatch")
    old = read_json(RESULTS / "papygreek-dev-manifest.json")
    candidates = set(old["nonfold_documents"])
    locked_docs = set(read_json(RESULTS / "papygreek-fold-manifest.json")["doc_ids"])
    locked_docs.update(read_json(RESULTS / "papygreek-fold-orig-manifest.json")["doc_ids"])
    work_ids = {f.stem: papygreek_work_id(ET.parse(f).getroot()) for f in files}
    blocked_tm = {work_ids[k] for k in locked_docs}
    train_tm, ref = pedalion_training_work_reference(args.pedalion)
    if ref["source_sha256"] != old["document_sets"]["training_work_reference"]["source_sha256"]:
        raise ValueError("Pedalion work inventory mismatch")
    regular = {
        i["sentence_id"]
        for i in read_json(RESULTS / "development-source-manifest.json")["items"]
        if i["source"] == "papygreek"
    }
    totals, skipped = Counter(), Counter()
    docs, native, basic, lemmas = {}, [], [], []
    observed = set()
    surface_owners = defaultdict(set)
    for path in files:
        doc = path.stem
        if doc not in candidates:
            continue
        tm = work_ids[doc]
        if doc in locked_docs or tm in blocked_tm | train_tm:
            skipped["document_work_overlap"] += 1
            continue
        root = ET.parse(path).getroot()
        reviewers = sorted(
            {
                a.get("name")
                for a in root.findall("annotator")
                if a.get("layer") == "orig" and a.get("role") == "approved" and a.get("name")
            }
        )
        if not reviewers:
            skipped["document_without_orig_approval"] += 1
            continue
        credits = [
            {k: a.get(k) for k in ("name", "role", "date") if a.get(k)}
            for a in root.findall("annotator")
            if a.get("layer") == "orig" and a.get("name")
        ]
        for sent in root.findall("sentence"):
            sid = sent.attrib["id"]
            key = f"papygreek-orig:{doc}@{sid}"
            if key in observed:
                raise ValueError("duplicate sentence " + key)
            observed.add(key)
            words = [w.attrib.copy() for w in sent.findall("word")]
            real = [w for w in words if not artificial(w)]
            overlap = next(
                (
                    hit
                    for layer in ("orig_form", "form_reg")
                    if (hit := idx.overlap([strip_apparatus(w.get(layer, "")) for w in real]))
                ),
                None,
            )
            if overlap:
                skipped[overlap] += 1
                continue
            targets = [(w, lemma_target(w)) for w in real]
            valid = [(w, lemma) for w, lemma in targets if lemma]
            if not valid:
                skipped["no_eligible_lemma"] += 1
                continue
            block = basic_tree(words, key)
            if block:
                basic.append(block)
                totals["basic_tree_words"] += len(real)
            for w, lemma in valid:
                cols = [
                    key,
                    tm,
                    w["id"],
                    strip_apparatus(w["orig_form"]),
                    lemma,
                    w.get("postag_orig") or "_",
                ]
                if any("\t" in v or "\n" in v for v in cols):
                    raise ValueError("unexpected separator in " + key)
                lemmas.append("\t".join(cols))
                totals["different_surface_among_lemma_targets"] += strip_apparatus(
                    w["orig_form"]
                ) != strip_apparatus(w.get("form_reg", ""))
                totals["different_lemma_among_comparable_targets"] += bool(
                    w.get("lemma_reg")
                ) and lemma != clean_lemma(w["lemma_reg"])
            for layer in ("orig_form", "form_reg"):
                seq = signature([strip_apparatus(w.get(layer, "")) for w in real])
                if seq:
                    surface_owners[seq].add(tm)
            paired = f"papygreek-dev:{doc}@{sid}" in regular
            native.append(
                json.dumps(
                    {
                        "id": key,
                        "tm": tm,
                        "paired_with_frozen_reg_dev": paired,
                        "lemma_token_ids": [w["id"] for w, _ in valid],
                        "basic_tree_exported": bool(block),
                        "words": words,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
            )
            totals["paired_with_frozen_reg_dev"] += paired
            totals["surface_tokens"] += len(real)
            docs[doc] = {
                "tm_id": tm,
                "path": path.relative_to(args.papygreek).as_posix(),
                "sha256": sha(path.read_bytes()),
                "orig_approved_by": reviewers,
                "orig_credits": credits,
            }
    if not basic or not lemmas:
        raise ValueError("empty output")
    # Keep identical sentences in either rendering together across accepted documents.
    tm_groups = {d["tm_id"]: {d["tm_id"]} for d in docs.values()}
    for group in surface_owners.values():
        if len(group) > 1:
            joined = set().union(*(tm_groups[tm] for tm in group))
            for tm in joined:
                tm_groups[tm] = joined
    split_groups = sorted({tuple(sorted(g)) for g in tm_groups.values()})
    out = args.out
    files_out = {
        "papygreek-native.jsonl.gz": gz(
            out / "papygreek-native.jsonl.gz", "\n".join(native) + "\n"
        ),
        "papygreek-lemmas.tsv.gz": gz(
            out / "papygreek-lemmas.tsv.gz",
            "sentence_id\ttm_id\tnative_word_id\tform\tlemma\tsource_xpos\n"
            + "\n".join(lemmas)
            + "\n",
        ),
        "papygreek-basic-ud.conllu.gz": gz(
            out / "papygreek-basic-ud.conllu.gz", "\n".join(basic) + "\n"
        ),
    }
    return {
        "upstream": "https://github.com/ezhenrik/papygreek-treebanks/tree/0e5139b06e41d89275f3a1ace4ee0dc5513f2f7d",
        "snapshot_digest": PAP_TREE,
        "pool_documents": len(candidates),
        "locked_documents": len(locked_docs),
        "pedalion_training_tm_ids": len(train_tm),
        "required_tm_split_groups": split_groups,
        "documents": docs,
        "counts": {
            **totals,
            "documents": len(docs),
            "tm_ids": len({r["tm_id"] for r in docs.values()}),
            "sentences": len(native),
            "lemma_targets": len(lemmas),
            "basic_trees": len(basic),
        },
        "excluded": dict(sorted(skipped.items())),
        "files": files_out,
    }


# Immutable upstream bytes. Each class of evidence has a separate output directory.
DAPHNE = "06aa1f27a34af98bba1407dc95fe2085a72f8b7f"
HILL = "0bf1de02722c22afc5c069a61d2c1a586d85be0d"
AGDT = "bf4334f0af5e13d16b04c1cccd6237e683ac6f5f"
GREEKLIT = "dacb04909e43dc47738828d33cc3d2b0635bc54c"
DRAFTS = {
    "tlg0011.tlg006": (
        "Philoctetes",
        "Philoctetes",
        "2d359f6f9347e62fdd2402cbd589a06bcc37ecf2a981e9d0a7b1e14171310d74",
    ),
    "tlg0006.tlg013": (
        "Iphigenia in Tauris",
        "Ion",
        "14bf2e7d0feb3c097149aea3f04fc65aef22e8ee5e8e8c03c43e3982b6087134",
    ),
}
RESERVE = {
    "tlg0011.tlg002.perseus-grc2.tb.xml": (
        "Antigone",
        "6bcddb0fa4b712608642693f4ae6226c370444dfc203c33a248c85639371cda0",
    ),
    "tlg0011.tlg005.perseus-grc2.tb.xml": (
        "Electra",
        "705a06c8e20858f44801b797acb23ef22feef6641336daa9b52ad60617b9dea8",
    ),
    "tlg0085.tlg005.perseus-grc1.tb.xml": (
        "Agamemnon",
        "2b86c8e533a1519f6814013aef45e7b54728825db3009911a4484dfc5a30239f",
    ),
    "tlg0085.tlg007.perseus-grc1.tb.xml": (
        "Eumenides",
        "86444df205dc025c44f71d48363dc2c821b4d4f2fd395e7af2933739da2f7620",
    ),
}


def check_bytes(path, digest):
    raw = path.read_bytes()
    if sha(raw) != digest:
        raise ValueError(f"upstream identity mismatch: {path}")
    return raw


def tei_lines(path):
    ns = "{http://www.tei-c.org/ns/1.0}"
    return [(line.get("n"), " ".join(line.itertext())) for line in ET.parse(path).iter(ns + "l")]


def tragedy(args, idx):
    tiny = args.out / "tragedy-diagnostic"
    draft = args.out / "tragedy-in-review"
    reserve = args.out / "tragedy-v3-training"
    for folder in (tiny, draft, reserve):
        folder.mkdir(exist_ok=True)

    hill_file = "eurip_suppl_447_449.xml"
    raw = check_bytes(args.hill, "e9af3064c1ce661c4e600b45616fde58fc230b824685e6df84bf94bd821cf7b1")
    root = ET.fromstring(raw)
    (sentence,) = root.findall("sentence")
    words = list(sentence.findall("word"))
    forms = [w.attrib["form"] for w in words]
    work = "tlg0006.tlg008"
    if idx.overlap(forms) or any(work in name for name in idx.train_files):
        raise ValueError("Digital Hill passage overlaps a protected source")
    canon = args.canonical / "data/tlg0006/tlg008/tlg0006.tlg008.perseus-grc2.xml"
    check_bytes(canon, "c4608b2612a5728672b97efe1e373d3253430f4b00328bf08182d15a558d1fce")
    quote = [w for n, line in tei_lines(canon) if n in ("447", "448", "449") for w in line.split()]
    if signature(forms) != signature(quote):
        raise ValueError("Suppliants citation does not match the reference Greek")
    if not complete_tree([(w.attrib["id"], w.attrib["head"]) for w in words], single_root=False):
        raise ValueError("invalid Digital Hill basic tree")
    attrs = [
        {
            "id": w.attrib["id"],
            "form_reg": w.attrib["form"],
            "postag_reg": w.attrib["postag"],
            "head_reg": w.attrib["head"],
            "lemma_reg": w.attrib["lemma"],
            "relation_reg": w.attrib["relation"],
        }
        for w in words
    ]
    block, _ = sentence_to_conllu("digitalhill:tlg0006.tlg008:447-449", attrs)
    if len(rows(block)) != len(words) or not complete_tree([(r[0], r[6]) for r in rows(block)]):
        raise ValueError("Digital Hill projection is incomplete")
    (tiny / hill_file).write_bytes(raw)
    conllu = tiny / "suppliants-447-449.conllu"
    conllu.write_bytes((block + "\n").encode())
    hill = {
        "source": f"https://github.com/DigitalHill/treebank-data/blob/{HILL}/euripides/{hill_file}",
        "cts": work,
        "citation": "447–449",
        "annotator": "Marcel Mernitz",
        "use": "single-annotator diagnostic only",
        "words_with_punctuation": len(forms),
        "sentences": 1,
        "raw_sha256": sha(raw),
        "conllu_sha256": sha(conllu.read_bytes()),
        "canonical_xml_sha256": sha(canon.read_bytes()),
        "matches_all_three_lines": True,
    }

    catalog_hash = "317bbe36c11b212ef1a3a4055d9b2c8ba7f72cad6d7e2baa14bf24c27041fc40"
    check_bytes(args.daphne / "data/catalog.yaml", catalog_hash)
    drafts = {}
    for work, (title, catalogue_title, digest) in DRAFTS.items():
        a, b = work.split(".")
        name = work + ".daphne_tb-grc1.conllu"
        rel = f"data/annotation/{a}/{b}/{name}"
        raw = check_bytes(args.daphne / rel, digest)
        if any(work in n for n in idx.train_files):
            raise ValueError("Daphne work appears as a v3 training source: " + work)
        excluded, counts = {}, Counter()
        canon = args.canonical / f"data/{a}/{b}/{work}.perseus-grc2.xml"
        check_bytes(
            canon,
            {
                "tlg0011.tlg006": "a1233e43b1723c01fe8b11349ebb78143a13477cc32c41a043323c075061d11a",
                "tlg0006.tlg013": "dae8c3abd8083b0f185c0213485faf42378828d03056032e956b7b138044f08c",
            }[work],
        )
        reference = signature([w for _, line in tei_lines(canon) for w in line.split()])
        k = 4
        phrases = {reference[i : i + k] for i in range(len(reference) - k + 1)}
        for block in conllu_blocks(raw.decode()):
            rows_ = rows(block)
            forms = [r[1] for r in rows_]
            (sid,) = [
                ln.split("=", 1)[1].strip()
                for ln in block.splitlines()
                if ln.startswith("# sent_id =")
            ]
            if reason := idx.overlap(forms):
                excluded[sid] = reason
            counts["sentences"] += 1
            counts["integer_words"] += len(rows_)
            counts["empty_nodes"] += sum(
                bool(re.match(r"^\d+\.\d+\t", line)) for line in block.splitlines()
            )
            counts["structurally_complete_basic_trees"] += complete_tree(
                [(r[0], r[6]) for r in rows_]
            )
            surface = signature(forms)
            for i in range(len(surface) - k + 1):
                counts["reference_four_word_windows"] += 1
                counts["reference_four_word_matches"] += surface[i : i + k] in phrases
        if counts["reference_four_word_matches"] < counts["reference_four_word_windows"] * 0.75:
            raise ValueError("work identity needs manual verification: " + work)
        drafts[work] = {
            "title": title,
            "catalog_title_as_published": catalogue_title,
            "annotation_status": "in_review",
            "source": f"https://github.com/francescomambrini/Daphne/blob/{DAPHNE}/{rel}",
            "raw_sha256": digest,
            "gzip_sha256": gz(draft / (name + ".gz"), raw),
            "canonical_xml_sha256": sha(canon.read_bytes()),
            "counts": dict(counts),
            "protected_overlap_sentence_ids": excluded,
            "use": "expert adjudication queue only",
        }

    training_gold = {}
    for name, (title, digest) in RESERVE.items():
        raw = check_bytes(args.agdt / "v2.1/Greek/texts" / name, digest)
        used = idx.train_files[name]
        if not used:
            raise ValueError("v3 exposure accounting mismatch: " + name)
        training_gold[name] = {
            "title": title,
            "use": "v3 supervised training; reserve only for a new work-excluded lineage",
            "source": f"https://github.com/PerseusDL/treebank_data/blob/{AGDT}/v2.1/Greek/texts/{name}",
            "raw_sha256": digest,
            "v3_training_sentences": used,
            "gzip_sha256": gz(reserve / (name + ".gz"), raw),
        }
    return {
        "reference_edition_revision": GREEKLIT,
        "daphne_catalog_sha256": catalog_hash,
        "digital_hill": hill,
        "daphne": drafts,
        "agdt": training_gold,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("training", "papygreek", "pedalion", "hill", "canonical", "daphne", "agdt", "out"):
        p.add_argument("--" + name, type=Path, required=True)
    args = p.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    index = exposure(args.training)
    report = {
        "format": "pyaegean-greek-development-sources/1",
        "use": "Consult the individual source eligibility records before use.",
        "protected_form_sources": dict(index.counts),
        "protected_file_sha256": index.files,
        "papygreek": papyri(args, index),
        "tragedy": tragedy(args, index),
    }
    (args.out / "manifest.json").write_bytes(
        (json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    )


if __name__ == "__main__":
    main()
