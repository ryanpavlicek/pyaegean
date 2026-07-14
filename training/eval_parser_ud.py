"""Score a trained Stage C joint tagger-parser on a UD test fold (the headline numbers).

Runs the JointParser over the fold's gold tokens, decodes trees with the single-root
Chu-Liu/Edmonds MST, renders CoNLL-U (UPOS + XPOS + FEATS from the tagging heads,
HEAD/DEPREL from the parser), and scores with the official CoNLL 2018 evaluator.
Reports UAS/LAS (the Stage C targets) alongside UPOS/UFeats/CLAS.

Usage:  python training/eval_parser_ud.py --checkpoint training/out/parser/model \
            [--treebank perseus] [--split test] [--out metrics.json]
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

import torch
from torch.utils.data import DataLoader
from transformers import AutoTokenizer

sys.path.insert(0, str(Path(__file__).parent))
from agdt_ud import feats_from_xpos  # noqa: E402
from train_parser import TAG_HEADS, JointParser, collate, decode_mst, encode  # noqa: E402

from aegean.greek.ud import _eval_module, load_conllu, ud_path  # noqa: E402
from aegean.greek import neural_preprocessing as prep  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--treebank", default="perseus", choices=("perseus", "proiel"))
    ap.add_argument("--split", default="test")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    ckpt = Path(args.checkpoint)
    spec = json.loads((ckpt / "labels.json").read_text(encoding="utf-8"))
    maps: dict[str, dict[str, int]] = spec["maps"]
    inv = {h: {i: lab for lab, i in m.items()} for h, m in maps.items()}

    device = "cuda" if torch.cuda.is_available() else "cpu"
    amp_dtype = (torch.bfloat16 if device == "cuda" and torch.cuda.is_bf16_supported()
                 else torch.float16 if device == "cuda" else None)
    tokenizer = AutoTokenizer.from_pretrained(ckpt, add_prefix_space=True)
    max_len = int(spec.get("max_subwords", 256))
    prep.configure_tokenizer(tokenizer, max_len)
    if spec.get("preprocessing_version") == prep.PREPROCESSING_VERSION:
        prep.validate_tokenizer_contract(tokenizer, max_len)
    model = JointParser(spec["model_name"], {h: len(maps[h]) for h in TAG_HEADS},
                        n_rels=len(maps["deprel"]))
    model.load_state_dict(torch.load(ckpt / "joint_parser.pt", map_location=device))
    model.to(device).eval()

    gold_path = ud_path(args.treebank, args.split)
    sentences = load_conllu(gold_path)
    rows = [{"tokens": [t.form for t in s.tokens],
             "upos": ["X"] * len(s.tokens), "xpos": ["---------"] * len(s.tokens),
             "head": [0] * len(s.tokens), "deprel": ["dep"] * len(s.tokens)}
            for s in sentences]
    pad_id = tokenizer.pad_token_id or 0
    enc = [encode(r, tokenizer, maps, max_len) for r in rows]
    dl = DataLoader(enc, batch_size=32, collate_fn=lambda b: collate(b, pad_id))

    lines: list[str] = []
    si = 0
    with torch.no_grad():
        for batch in dl:
            inputs = {k: batch[k].to(device) for k in ("input_ids", "attention_mask", "word_pos")}
            with torch.autocast(device_type=device, dtype=amp_dtype, enabled=amp_dtype is not None):
                tag_logits, arc, rel, _lem = model(**inputs)
            arc = arc.float().cpu().numpy()
            relp = rel.float().cpu().permute(0, 2, 3, 1)        # [B, W, W+1, R]
            up = tag_logits["upos"].argmax(-1).cpu()
            xp = {i: tag_logits[f"x{i}"].argmax(-1).cpu() for i in range(9)}
            word_pos = batch["word_pos"]
            for b in range(word_pos.shape[0]):
                sent = sentences[si]
                si += 1
                nw = int(batch["n_words"][b])
                n_total = len(sent.tokens)
                heads = decode_mst(arc[b, :nw, : nw + 1]) if nw else []
                upos_out = ["X"] * n_total
                xpos_out = ["---------"] * n_total
                head_out = [0 if i == 0 else 1 for i in range(n_total)]
                rel_out = ["root" if i == 0 else "dep" for i in range(n_total)]
                for wi in range(nw):                            # words kept by truncation
                    sp = int(word_pos[b, wi])
                    upos_out[wi] = inv["upos"][int(up[b, sp])]
                    xpos_out[wi] = "".join(inv[f"x{i}"][int(xp[i][b, sp])] for i in range(9))
                    head_out[wi] = heads[wi]
                    rel_out[wi] = inv["deprel"][int(relp[b, wi, heads[wi]].argmax())]
                    if heads[wi] == 0:
                        rel_out[wi] = "root"
                # exactly one root even with truncated tails
                roots = [i for i in range(n_total) if head_out[i] == 0]
                first_root = roots[0] if roots else 0
                for i in roots[1:]:
                    head_out[i] = first_root + 1
                    rel_out[i] = "parataxis"
                if not roots:
                    head_out[0], rel_out[0] = 0, "root"
                if sent.sent_id:
                    lines.append(f"# sent_id = {sent.sent_id}")
                for i, t in enumerate(sent.tokens):
                    lines.append("\t".join((
                        str(i + 1), t.form, "_", upos_out[i], xpos_out[i],
                        feats_from_xpos(xpos_out[i]), str(head_out[i]), rel_out[i], "_", "_")))
                lines.append("")

    ev = _eval_module()
    with tempfile.TemporaryDirectory() as td:
        sys_path = Path(td) / "system.conllu"
        sys_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        with open(gold_path, encoding="utf-8") as gf:
            gold_ud = ev.load_conllu(gf)
        with open(sys_path, encoding="utf-8") as sf:
            system_ud = ev.load_conllu(sf)
    scores = ev.evaluate(gold_ud, system_ud)
    result = {
        "checkpoint": str(ckpt), "treebank": args.treebank, "split": args.split,
        "uas": scores["UAS"].f1, "las": scores["LAS"].f1, "clas": scores["CLAS"].f1,
        "upos": scores["UPOS"].f1, "xpos": scores["XPOS"].f1, "ufeats": scores["UFeats"].f1,
        "n_sentences": len(sentences), "n_words": sum(len(s.tokens) for s in sentences),
    }
    text = json.dumps(result, indent=1)
    print(text)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
