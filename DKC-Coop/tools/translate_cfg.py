"""Translate DKC1Recomp recomp/*.cfg from v1.0 to v1.2 addresses using work/addrmap.json.

Writes translated cfgs to <out_dir> and a review list of every directive that could not be
translated mechanically (address inside a "changed" region, or a function whose length changed).

usage: python translate_cfg.py <addrmap.json> <cfg_dir> <out_dir> [--overrides o.json] [--manual m.cfg]
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from addrmap import AddressMap  # noqa: E402

HEX6 = re.compile(r"\b([89A-F][0-9A-F])([0-9A-F]{4})\b")


def load_manual(path):
    regions, current = [], None
    for line in Path(path).read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("[region"):
            _, bank, lo, hi = line.strip("[]").split()
            current = (int(bank, 16), int(lo, 16), int(hi, 16), [])
            regions.append(current)
        elif line.startswith("[insert"):
            _, bank = line.strip("[]").split()
            current = (int(bank, 16), None, None, [])  # new in v1.2: appended to the bank's cfg
            regions.append(current)
        else:
            current[3].append(line)
    return regions


def directive_address(kind, body, bank):
    if kind in ("func", "data_region") or kind == "indirect_dispatch":
        pc = body[2] if kind != "indirect_dispatch" else body[1]
        return bank << 16 | int(pc, 16)
    if kind == "exit_mx_at":
        return int(body[1], 16)
    return None


def main():
    amap = AddressMap.load(sys.argv[1])
    overrides = {}
    if "--overrides" in sys.argv:
        overrides = {int(k, 16): int(v, 16) for k, v in json.load(open(sys.argv[sys.argv.index("--overrides") + 1])).items()}
    manual = load_manual(sys.argv[sys.argv.index("--manual") + 1]) if "--manual" in sys.argv else []
    base_translate = amap.translate

    def translate(address):
        if address in overrides:
            return overrides[address], "manual"
        return base_translate(address)
    amap.translate = translate
    cfg_dir, out_dir = Path(sys.argv[2]), Path(sys.argv[3])
    out_dir.mkdir(parents=True, exist_ok=True)
    stats, review = Counter(), []

    for cfg in sorted(cfg_dir.glob("bank*.cfg")):
        bank = None
        lines_out = []
        for lineno, line in enumerate(cfg.read_text().splitlines(), 1):
            body = line.split("#", 1)[0].split()
            if not body:
                lines_out.append(line)
                continue
            kind = body[0]
            if kind == "bank":
                bank = int(body[2], 16)
                lines_out.append(line)
                continue

            problems = []
            address = directive_address(kind, body, bank)
            region = next((r for r in manual if bank == r[0] and address is not None and r[1] is not None
                           and r[1] <= (address & 0xFFFF) < r[2] and (address >> 16) == bank), None)
            if region is not None:
                lines_out.extend(region[3])  # emitted once, at the first replaced directive
                region[3][:] = []
                stats[(kind, "manual")] += 1
                continue

            def tr(addr):
                new, how = amap.translate(addr)
                if new is None:
                    problems.append(f"{addr:06X}:{how}")
                    return addr
                return new

            def tr16(pc16):
                if int(pc16, 16) == 0x10000:
                    return 0x10000  # end of bank
                return tr((bank << 16) | int(pc16, 16)) & 0xFFFF

            new = line
            if kind == "func":
                name, start = body[1], body[2]
                ns = tr16(start)
                parts = [f"func {name} {ns:04X}"]
                end_new = None
                for token in body[3:]:
                    if token.startswith("end:"):
                        end_old = int(token[4:], 16)
                        end_new = tr16(token[4:])
                        if not problems and (end_new - ns) != (end_old - int(start, 16)):
                            problems.append(f"length {end_old - int(start, 16)}->{end_new - ns}")
                        token = f"end:{end_new:04X}"
                    parts.append(token)
                # keep the original name: symbols and hand-written code refer to it
                new = " ".join(parts)
            elif kind == "data_region":
                new = f"data_region {body[1]} {tr16(body[2]):04X} {tr16(body[3]) if body[3] != '10000' else 0x10000:04X}"
            elif kind == "indirect_dispatch":
                site = tr16(body[1])
                rest = []
                for token in body[3:]:
                    if token.startswith("targets:"):
                        targets = [f"{tr(int(t, 16)):06X}" for t in token[8:].split(",")]
                        token = "targets:" + ",".join(targets)
                    rest.append(token)
                new = " ".join(["indirect_dispatch", f"{site:04X}", body[2], *rest])
            elif kind == "exit_mx_at":
                new = " ".join(["exit_mx_at", f"{tr(int(body[1], 16)):06X}", *body[2:]])
            stats[(kind, "review" if problems else "ok")] += 1
            if problems:
                review.append(f"{cfg.name}:{lineno}: {kind} {' '.join(body[1:3])}  <- {'; '.join(problems)}")
                new += "  # REVIEW " + "; ".join(problems)
            lines_out.append(new)
        for r in manual:
            if r[1] is None and r[0] == bank:  # [insert]: directives with no v1.0 counterpart
                lines_out.extend(r[3])
                stats[("insert", "manual")] += len(r[3])
        (out_dir / cfg.name).write_text("\n".join(lines_out) + "\n")

    for (kind, state), n in sorted(stats.items()):
        print(f"{kind:<18} {state:<6} {n}")
    (out_dir / "REVIEW.txt").write_text("\n".join(review) + "\n")
    print(f"review items: {len(review)} -> {out_dir / 'REVIEW.txt'}")


if __name__ == "__main__":
    main()
