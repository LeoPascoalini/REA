"""Resolve v1.0 addresses that the byte alignment could not map, by masked instruction search.

For each address the code at v1.0 is decoded (M/X from the enclosing cfg function, tracked through
REP/SEP), turned into a pattern where address-like operands are wildcards, and searched for in
v1.2 between the nearest addresses that did map. Also re-checks every mapped function entry whose
opcode differs between versions.

usage: python resolve_masked.py <v10.sfc> <v12.sfc> <addrmap.json> <cfg_dir> <out_overrides.json>
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from addrmap import AddressMap  # noqa: E402
from dis65816 import OPS, disassemble, rom_offset  # noqa: E402

WILD_MODES = {"abs", "abx", "aby", "ind", "axi", "ail", "lng", "lngx", "rel", "rell"}
INSTRUCTIONS = 8


def pattern_at(rom, address, m, x):
    parts = []
    for _, raw, _ in disassemble(rom, address, INSTRUCTIONS, m, x):
        mode = OPS[raw[0]][1]
        parts.append(re.escape(raw[:1]))
        if len(raw) > 1:
            parts.append(b"." * (len(raw) - 1) if mode in WILD_MODES else re.escape(raw[1:]))
    return re.compile(b"".join(parts), re.S)


def load_funcs(cfg_dir):
    funcs = []
    for cfg in sorted(Path(cfg_dir).glob("bank*.cfg")):
        bank = None
        for line in cfg.read_text().splitlines():
            t = line.split("#")[0].split()
            if not t:
                continue
            if t[0] == "bank":
                bank = int(t[2], 16)
            elif t[0] == "func":
                start = bank << 16 | int(t[2], 16)
                end = next((bank << 16 | int(v[4:], 16) for v in t[3:] if v.startswith("end:")), start + 1)
                mx = next((v[9:].split(",") for v in t[3:] if v.startswith("entry_mx:")), ["1", "1"])
                funcs.append((start, end, int(mx[0]), int(mx[1]), t[1]))
    return funcs


def mx_at(rom, func, address):
    start, _, m, x, _ = func
    a = start
    while a < address:
        (_, raw, text), = disassemble(rom, a, 1, m, x)
        if text.startswith("REP"):
            m = 0 if raw[1] & 0x20 else m
            x = 0 if raw[1] & 0x10 else x
        elif text.startswith("SEP"):
            m = 1 if raw[1] & 0x20 else m
            x = 1 if raw[1] & 0x10 else x
        a += len(raw)
    return m, x


def neighbours(amap, address):
    lo = hi = None
    for d in range(1, 0x800):
        if lo is None:
            v, _ = amap.translate(address - d)
            if v is not None:
                lo = v + d - 0x100
        if hi is None:
            v, _ = amap.translate(address + d)
            if v is not None:
                hi = v - d + 0x100
        if lo is not None and hi is not None:
            break
    return lo, hi


def main():
    a, b = open(sys.argv[1], "rb").read(), open(sys.argv[2], "rb").read()
    amap = AddressMap.load(sys.argv[3])
    funcs = load_funcs(sys.argv[4])
    wanted = set()
    for cfg in sorted(Path(sys.argv[4]).glob("bank*.cfg")):
        bank = None
        for line in cfg.read_text().splitlines():
            t = line.split("#")[0].split()
            if t and t[0] == "bank":
                bank = int(t[2], 16)
            for tok in re.findall(r"\b[89AB][0-9A-F]{5}\b", line.split("#")[0]):
                wanted.add(int(tok, 16))
            if t and t[0] in ("func",):
                wanted.add(bank << 16 | int(t[2], 16))
    overrides, report = {}, []
    for address in sorted(wanted):
        mapped, kind = amap.translate(address)
        func = next((f for f in funcs if f[0] <= address < f[1]), None)
        if func is None:
            continue
        needs = mapped is None or a[rom_offset(address)] != b[rom_offset(mapped)]
        if not needs:
            continue
        m, x = mx_at(a, func, address)
        pat = pattern_at(a, address, m, x)
        lo, hi = neighbours(amap, address)
        bank = address & 0xFF0000
        lo = max(bank | 0x8000, lo if lo is not None else address - 0x800)
        hi = min(bank | 0xFFFF, hi if hi is not None else address + 0x800)
        hits = [bank | (h.start() & 0xFFFF) for h in pat.finditer(b, rom_offset(lo), rom_offset(hi) + 1)]
        if len(hits) == 1:
            overrides[f"{address:06X}"] = f"{hits[0]:06X}"
            report.append(f"{address:06X} -> {hits[0]:06X}  ({func[4]}, was {kind}{'' if mapped is None else f' {mapped:06X}'})")
        else:
            report.append(f"{address:06X} UNRESOLVED ({len(hits)} hits in {lo:06X}-{hi:06X}; {func[4]})")
    Path(sys.argv[5]).write_text(json.dumps(overrides, indent=1))
    print("\n".join(report))
    print(f"overrides: {len(overrides)}")


if __name__ == "__main__":
    main()
