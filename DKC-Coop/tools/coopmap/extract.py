"""Inventory of player-dependent code in the DKC1 disassembly (for DKC-Coop).

Builds a call graph over the labelled blocks of Routine_Macros_DKC1.asm
(JSR/JSL/JMP/JML/branches, fall-through, jump tables `JMP (DATA_x,x)` with
`dw` entries) and lists every site that asks "who is the player", with the
sprite routines (DKC1_*Spr*_Main) and root routines that reach it.

usage: python extract.py <Routine_Macros_DKC1.asm> <out.json>
"""
import json
import re
import sys
from collections import defaultdict, deque

src, out = sys.argv[1], sys.argv[2]
lines = open(src, encoding="latin-1").read().splitlines()

LABEL = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*):")
TARGET = re.compile(r"\b(JSR|JSL|JMP|JML|BRA|BRL|BEQ|BNE|BCC|BCS|BMI|BPL|BVC|BVS)\.[bwl]\s+([A-Za-z_][A-Za-z0-9_]*)\s*$")
TABLE_JUMP = re.compile(r"\b(JMP|JSR)\.w\s+\((DATA_[0-9A-F]+),x\)")
DW = re.compile(r"^\s*d[wl]\s+(.*)$")
ENDS = re.compile(r"\b(RTS|RTL|RTI|JMP|JML|BRA|BRL)\b")

blocks = []          # (label, first_line, last_line)
for i, l in enumerate(lines):
    m = LABEL.match(l)
    if m:
        if blocks:
            blocks[-1][2] = i - 1
        blocks.append([m.group(1), i, len(lines) - 1])
index = {b[0]: n for n, b in enumerate(blocks)}
owner_of_line = [None] * len(lines)
for name, a, b in blocks:
    for i in range(a, b + 1):
        owner_of_line[i] = name

edges = defaultdict(set)
for n, (name, a, b) in enumerate(blocks):
    last_code = None
    for i in range(a + 1, b + 1):
        code = lines[i].split(";")[0].rstrip()
        if not code.strip():
            continue
        last_code = code
        m = TARGET.search(code)
        if m and m.group(2) in index:
            edges[name].add(m.group(2))
        t = TABLE_JUMP.search(code)
        if t and t.group(2) in index:
            _, ta, tb = blocks[index[t.group(2)]]
            for j in range(ta + 1, tb + 1):
                d = DW.match(lines[j].split(";")[0])
                if d:
                    for tok in re.split(r"[,\s]+", d.group(1)):
                        if tok in index:
                            edges[name].add(tok)
    if name.startswith("DATA_"):
        continue
    if last_code is not None and not ENDS.search(last_code) and n + 1 < len(blocks):
        edges[name].add(blocks[n + 1][0])   # fall-through
    if last_code is None and n + 1 < len(blocks):
        edges[name].add(blocks[n + 1][0])   # label alias

callers = defaultdict(set)
for a, bs in edges.items():
    for b in bs:
        callers[b].add(a)

MAIN = re.compile(r"^DKC1_[A-Za-z]*Spr[0-9A-F]+_[A-Za-z0-9_]*_Main$")


def owners(label, limit=4000):
    """Sprite mains and caller-less roots that reach `label`."""
    seen, q, mains, roots = {label}, deque([label]), set(), set()
    while q and len(seen) < limit:
        x = q.popleft()
        if MAIN.match(x):
            mains.add(x)
            continue
        cs = [c for c in callers[x] if not c.startswith("DATA_")]
        if not cs:
            roots.add(x)
        for c in cs:
            if c not in seen:
                seen.add(c)
                q.append(c)
    return sorted(mains), sorted(roots)


PATTERNS = {
    "current_kong_056F": re.compile(r"(CurrentKongLo|\$056F)\b"),
    "player_slot_809B9C": re.compile(r"\b(JSL\.l CODE_809B9C|JSR\.w CODE_809BA0)\b"),
    "touch_active_BBA574": re.compile(r"\bJSL\.l CODE_BBA574\b"),
    "touch_category_BBA58D": re.compile(r"\bJSL\.l CODE_BBA58D\b"),
    "touch_other_BBA6xx": re.compile(r"\bJSL\.l CODE_BBA6[0-9A-F]{2}\b"),
    "active_slot_BBA564": re.compile(r"\bJS[RL]\.[wl] CODE_BBA564\b"),
    "kong_index_84": re.compile(r"\b(LD[AXY]|ST[AXYZ]|CMP|CP[XY])\.b \$84\b"),
    "kong_event_1929": re.compile(r"\$1929\b"),
    "flags_0579": re.compile(r"\$0579\b"),
    "player_number_44": re.compile(r"\.b \$44\b"),
    "game_mode_42": re.compile(r"\.b \$42\b"),
    "pads": re.compile(r"(PressedButtonsLo|HeldButtonsLo|\$050E|\$0510|\$0500|\$0502|\$0504|\$0506)\b"),
    "ridden_0512": re.compile(r"\$0512\b"),
    "bonus_return_1705": re.compile(r"\$1705\b"),
}

sites = []
for i, l in enumerate(lines):
    code = l.split(";")[0]
    if not code.strip() or LABEL.match(l):
        continue
    for kind, pat in PATTERNS.items():
        if pat.search(code):
            label = owner_of_line[i]
            after = [x.split(";")[0].strip() for x in lines[i + 1:i + 7]]
            after = [x for x in after if x][:5]
            mains, roots = owners(label)
            sites.append({
                "kind": kind, "line": i + 1, "label": label,
                "code": code.strip(), "after": after,
                "mains": mains, "roots": roots[:6],
            })

json.dump({"sites": sites, "blocks": len(blocks),
           "edges": sum(len(v) for v in edges.values())}, open(out, "w"), indent=1)
by = defaultdict(int)
for s in sites:
    by[s["kind"]] += 1
print("blocks", len(blocks), "edges", sum(len(v) for v in edges.values()))
for k, v in sorted(by.items()):
    print(f"{k:24s} {v}")
