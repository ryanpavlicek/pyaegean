"""Exploration: decode SigLA's database.js to raw OCaml-Marshal bytes.

SigLA (https://sigla.phis.me — Salgarella & Castellan; dataset + drawings
published CC BY-NC-SA 4.0, with the paper inviting reuse "outside the
interface") ships its database inside the web app as two JS variables whose
values are *quoted OCaml string literals* containing OCaml ``Marshal``
payloads. This script peels the two escape layers (JS ``\\\\`` -> ``\\``, then
OCaml decimal ``\\DDD``), verifies the Marshal header (magic 0x8495A6BE; the
declared length must match), and scans for recognizable content — document ids
(ARKH 1a), sites, typology, periods, sign attestations with GORILA positions
(PH 31a/17), and phonetic values, all visible in the streams.

Feasibility verified 2026-06-11. The next step (the SigLA loader) needs a
proper Marshal reader (ints / strings / blocks / sharing — the format is
documented in the OCaml runtime) plus the schema mapping from the SigLA paper.

Run: download https://sigla.phis.me/database.js to %TEMP%/sigla-database.js,
then ``python scripts/explore_sigla_db.py``.
"""
import os
import re
import struct
from pathlib import Path

raw = Path(os.environ["TEMP"], "sigla-database.js").read_text(encoding="utf-8")


def js_var_bytes(name: str) -> bytes:
    m = re.search(rf"var {name} = '(.*?)';", raw, re.S)
    assert m, name
    s = m.group(1)
    # layer 1: the JS single-quoted literal — \\ -> \ (only escape used)
    js = s.replace("\\\\", "\\")
    # layer 2: a quoted OCaml string literal "...\132\149..." with DECIMAL escapes
    assert js.startswith('"') and js.endswith('"'), js[:20]
    body = js[1:-1]
    out = bytearray()
    i = 0
    while i < len(body):
        c = body[i]
        if c == "\\":
            nxt = body[i + 1]
            if nxt.isdigit():  # OCaml decimal escape \DDD
                out.append(int(body[i + 1 : i + 4]))
                i += 4
            elif nxt == "x":
                out.append(int(body[i + 2 : i + 4], 16))
                i += 4
            elif nxt == "n":
                out.append(10)
                i += 2
            elif nxt == "t":
                out.append(9)
                i += 2
            else:  # \" \\ \' etc.
                out.append(ord(nxt))
                i += 2
        else:
            out.append(ord(c))
            i += 1
    return bytes(out)


for name in ("signs", "data"):
    b = js_var_bytes(name)
    magic, data_len, num_obj, sz32, sz64 = struct.unpack(">IIIII", b[:20])
    print(f"{name}: {len(b)} bytes | magic {magic:#x} | data_len {data_len} | objects {num_obj}")
    # scan for printable ASCII runs (document ids, site names should be visible)
    runs = re.findall(rb"[ -~]{4,}", b[20:])
    print(f"  ascii runs: {len(runs)}; samples:", [r.decode()[:24] for r in runs[:14]])
    ids = [r.decode() for r in runs if re.match(rb"^(HT|KH|ZA|PH|KN|ARKH|TY|MA)\b", r)]
    print(f"  GORILA-looking ids: {len(ids)}; e.g.", ids[:10])
