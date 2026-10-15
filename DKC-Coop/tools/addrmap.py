"""Build a DKC1 v1.0 -> v1.2 address map by aligning a rebuilt v1.0 ROM against the v1.2 ROM.

Per 64 KiB bank: unique k-mer anchors (unique within the bank in both ROMs) are extended to maximal
exact matches, chained monotonically (longest increasing chain by v1.2 position), and the gaps
between chained matches are classified:
  exact   bytes identical at the mapped position
  same    equal-length gap: same layout, different bytes (typically shifted pointers/operands)
  changed unequal-length gap: code/data really inserted, removed or rewritten

usage: python addrmap.py <rebuilt_v10.sfc> <v12.sfc> <out.json> [--k 12]
API:   AddressMap.load(path).translate(0xBF803C) -> (0xBF8085, "exact") | (None, "changed")
"""
import bisect
import difflib
import json
import sys
from collections import Counter

BANK = 0x10000


def maximal_matches(a, b, k):
    ca = Counter(a[i:i + k] for i in range(len(a) - k + 1))
    cb = Counter(b[i:i + k] for i in range(len(b) - k + 1))
    where = {}
    for i in range(len(b) - k + 1):
        km = b[i:i + k]
        if cb[km] == 1 and ca[km] == 1 and len(set(km)) > 2:
            where[km] = i
    matches, i = [], 0
    while i <= len(a) - k:
        j = where.get(a[i:i + k])
        if j is None:
            i += 1
            continue
        s, t = i, j
        while s > 0 and t > 0 and a[s - 1] == b[t - 1]:
            s, t = s - 1, t - 1
        e = i + k
        while e < len(a) and e - i + j < len(b) and a[e] == b[e - i + j]:
            e += 1
        matches.append((s, t, e - s))
        i = e
    return matches


def chain(matches):
    """Longest chain increasing in both coordinates, weighted by length (O(n log n) by count)."""
    matches = sorted(set(matches))
    # patience-style LIS on v1.2 start, then keep only non-overlapping in both axes
    tails, prev, idx = [], [None] * len(matches), []
    for n, (_, t, _) in enumerate(matches):
        p = bisect.bisect_left(tails, t)
        if p == len(tails):
            tails.append(t)
            idx.append(n)
        else:
            tails[p] = t
            idx[p] = n
        prev[n] = idx[p - 1] if p else None
    out, n = [], idx[-1] if idx else None
    while n is not None:
        out.append(matches[n])
        n = prev[n]
    out.reverse()
    cleaned, ea, eb = [], 0, 0
    for s, t, ln in out:
        if s < ea or t < eb:  # trim overlap with previous match
            cut = max(ea - s, eb - t)
            s, t, ln = s + cut, t + cut, ln - cut
        if ln > 0:
            cleaned.append((s, t, ln))
            ea, eb = s + ln, t + ln
    return cleaned


def align_bank(a, b, k, base_a=0, base_b=0, min_k=4):
    """Align a against b; unequal-length gaps are re-aligned recursively with smaller anchors."""
    segs = []  # (a_start, a_end, b_start, kind, b_len) in bank-relative offsets
    pa = pb = 0

    def gap(a0, a1, b0, b1):
        if a1 - a0 == b1 - b0:
            if a1 > a0:
                segs.append((base_a + a0, base_a + a1, base_b + b0, "same", b1 - b0))
            return
        if k > min_k and a1 > a0 and b1 > b0:
            inner = align_bank(a[a0:a1], b[b0:b1], max(min_k, k // 2), base_a + a0, base_b + b0, min_k)
            if any(s[3] == "exact" for s in inner):
                segs.extend(inner)
                return
        segs.append((base_a + a0, base_a + a1, base_b + b0, "changed", b1 - b0))

    for s, t, ln in chain(maximal_matches(a, b, k)):
        if s > pa or t > pb:
            gap(pa, s, pb, t)
        segs.append((base_a + s, base_a + s + ln, base_b + t, "exact", ln))
        pa, pb = s + ln, t + ln
    if pa < len(a) or pb < len(b):
        gap(pa, len(a), pb, len(b))
    return segs


def resolve_moves(segs, a, b, k=8):
    """Changed v1.0 regions whose bytes reappear elsewhere in the v1.2 bank were moved, not rewritten:
    re-align each against the whole v1.2 bank and splice in the exact pieces found."""
    out = []
    for seg in segs:
        a0, a1, b0, kind, bl = seg
        if kind != "changed" or a1 - a0 < 16:
            out.append(seg)
            continue
        piece = a[a0:a1]
        found = [(s, t, ln) for s, t, ln in maximal_matches(piece, b, k) if ln >= 8]
        if not found:
            out.append(seg)
            continue
        pos = 0
        for s, t, ln in sorted(found):
            if s < pos:
                continue
            if s > pos:
                out.append((a0 + pos, a0 + s, b0, "changed", 0))
            out.append((a0 + s, a0 + s + ln, t, "moved", ln))
            pos = s + ln
        if pos < a1 - a0:
            out.append((a0 + pos, a1, b0, "changed", 0))
    return out


def refine_small(segs, a, b, limit=2048):
    """Byte-level diff (difflib) inside small rewritten regions; emits exact sub-blocks and
    equal-length gaps between them as "same"."""
    out = []
    for seg in segs:
        a0, a1, b0, kind, bl = seg
        if kind != "changed" or not (0 < a1 - a0 <= limit and 0 < bl <= limit):
            out.append(seg)
            continue
        sm = difflib.SequenceMatcher(None, a[a0:a1], b[b0:b0 + bl], autojunk=False)
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "equal":
                out.append((a0 + i1, a0 + i2, b0 + j1, "exact", i2 - i1))
            elif tag == "replace" and i2 - i1 == j2 - j1:
                out.append((a0 + i1, a0 + i2, b0 + j1, "same", j2 - j1))
            elif i2 > i1:
                out.append((a0 + i1, a0 + i2, b0 + j1, "changed", j2 - j1))
    return out


class AddressMap:
    def __init__(self, banks):
        self.banks = banks  # {rom_bank: [(a0, a1, b0, kind, b_len)]}
        self.starts = {k: [s[0] for s in v] for k, v in banks.items()}

    @classmethod
    def load(cls, path):
        with open(path) as f:
            raw = json.load(f)
        return cls({int(k): [tuple(s) for s in v] for k, v in raw.items()})

    def translate(self, snes_address):
        """SNES HiROM address (80-BF or C0-FF banks) -> (v1.2 address or None, kind)."""
        bank, low = snes_address >> 16, snes_address & 0xFFFF
        rom_bank = bank & 0x3F
        segs = self.banks.get(rom_bank)
        if not segs:
            return None, "nobank"
        offset = low if bank >= 0xC0 or bank < 0x40 else low  # HiROM: whole bank is ROM
        i = bisect.bisect_right(self.starts[rom_bank], offset) - 1
        a0, a1, b0, kind, _ = segs[i]
        if kind == "changed":
            if offset == a0:
                # first byte of a rewritten region: its start still corresponds (code was
                # inserted/removed inside it), e.g. a function entry whose body changed
                return (bank << 16) | b0, "boundary"
            return None, kind
        return (bank << 16) | (b0 + offset - a0), kind


def main():
    a = open(sys.argv[1], "rb").read()
    b = open(sys.argv[2], "rb").read()
    out = sys.argv[3]
    k = int(sys.argv[sys.argv.index("--k") + 1]) if "--k" in sys.argv else 12
    banks = {}
    for bank in range(len(a) // BANK):
        ab, bb = a[bank * BANK:(bank + 1) * BANK], b[bank * BANK:(bank + 1) * BANK]
        segs = refine_small(resolve_moves(align_bank(ab, bb, k), ab, bb), ab, bb)
        banks[bank] = segs
        tally = Counter()
        for a0, a1, _, kind, _ in segs:
            tally[kind] += a1 - a0
        changed = sum(1 for s in segs if s[3] == "changed")
        print(f"bank {0xC0 + bank:02X}: exact {tally['exact'] / BANK:6.1%}  moved {tally['moved'] / BANK:5.1%}  same {tally['same'] / BANK:5.1%}  "
              f"changed {tally['changed'] / BANK:5.1%} in {changed} regions")
    with open(out, "w") as f:
        json.dump({str(k): v for k, v in banks.items()}, f)
    print("written", out)


if __name__ == "__main__":
    main()
