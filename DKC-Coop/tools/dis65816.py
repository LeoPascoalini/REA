"""Minimal 65816 disassembler for HiROM SNES ROMs (tracks M/X through REP/SEP).

usage: python dis65816.py <rom> <bank:pc> <count> [--m 0|1] [--x 0|1]
API:   disassemble(rom, address, count, m=1, x=1) -> [(address, bytes, text)]
"""
import sys

# (mnemonic, mode) for opcodes 0x00-0xFF.
_T = """
BRK sig|ORA dxi|COP sig|ORA sr|TSB dp|ORA dp|ASL dp|ORA dil|PHP imp|ORA imm|ASL acc|PHD imp|TSB abs|ORA abs|ASL abs|ORA lng
BPL rel|ORA diy|ORA di|ORA sri|TRB dp|ORA dpx|ASL dpx|ORA dily|CLC imp|ORA aby|INC acc|TCS imp|TRB abs|ORA abx|ASL abx|ORA lngx
JSR abs|AND dxi|JSL lng|AND sr|BIT dp|AND dp|ROL dp|AND dil|PLP imp|AND imm|ROL acc|PLD imp|BIT abs|AND abs|ROL abs|AND lng
BMI rel|AND diy|AND di|AND sri|BIT dpx|AND dpx|ROL dpx|AND dily|SEC imp|AND aby|DEC acc|TSC imp|BIT abx|AND abx|ROL abx|AND lngx
RTI imp|EOR dxi|WDM sig|EOR sr|MVP mv|EOR dp|LSR dp|EOR dil|PHA imp|EOR imm|LSR acc|PHK imp|JMP abs|EOR abs|LSR abs|EOR lng
BVC rel|EOR diy|EOR di|EOR sri|MVN mv|EOR dpx|LSR dpx|EOR dily|CLI imp|EOR aby|PHY imp|TCD imp|JML lng|EOR abx|LSR abx|EOR lngx
RTS imp|ADC dxi|PER rell|ADC sr|STZ dp|ADC dp|ROR dp|ADC dil|PLA imp|ADC imm|ROR acc|RTL imp|JMP ind|ADC abs|ROR abs|ADC lng
BVS rel|ADC diy|ADC di|ADC sri|STZ dpx|ADC dpx|ROR dpx|ADC dily|SEI imp|ADC aby|PLY imp|TDC imp|JMP axi|ADC abx|ROR abx|ADC lngx
BRA rel|STA dxi|BRL rell|STA sr|STY dp|STA dp|STX dp|STA dil|DEY imp|BIT imm|TXA imp|PHB imp|STY abs|STA abs|STX abs|STA lng
BCC rel|STA diy|STA di|STA sri|STY dpx|STA dpx|STX dpy|STA dily|TYA imp|STA aby|TXS imp|TXY imp|STZ abs|STA abx|STZ abx|STA lngx
LDY immx|LDA dxi|LDX immx|LDA sr|LDY dp|LDA dp|LDX dp|LDA dil|TAY imp|LDA imm|TAX imp|PLB imp|LDY abs|LDA abs|LDX abs|LDA lng
BCS rel|LDA diy|LDA di|LDA sri|LDY dpx|LDA dpx|LDX dpy|LDA dily|CLV imp|LDA aby|TSX imp|TYX imp|LDY abx|LDA abx|LDX aby|LDA lngx
CPY immx|CMP dxi|REP imm8|CMP sr|CPY dp|CMP dp|DEC dp|CMP dil|INY imp|CMP imm|DEX imp|WAI imp|CPY abs|CMP abs|DEC abs|CMP lng
BNE rel|CMP diy|CMP di|CMP sri|PEI di|CMP dpx|DEC dpx|CMP dily|CLD imp|CMP aby|PHX imp|STP imp|JML ail|CMP abx|DEC abx|CMP lngx
CPX immx|SBC dxi|SEP imm8|SBC sr|CPX dp|SBC dp|INC dp|SBC dil|INX imp|SBC imm|NOP imp|XBA imp|CPX abs|SBC abs|INC abs|SBC lng
BEQ rel|SBC diy|SBC di|SBC sri|PEA abs|SBC dpx|INC dpx|SBC dily|SED imp|SBC aby|PLX imp|XCE imp|JSR axi|SBC abx|INC abx|SBC lngx
"""
OPS = [tuple(cell.split()) for row in _T.strip().splitlines() for cell in row.split("|")]
assert len(OPS) == 256

FMT = {
    "imp": "", "acc": "A", "sig": "#${:02X}", "imm8": "#${:02X}", "dp": "${:02X}", "dpx": "${:02X},X",
    "dpy": "${:02X},Y", "di": "(${:02X})", "dxi": "(${:02X},X)", "diy": "(${:02X}),Y", "dil": "[${:02X}]",
    "dily": "[${:02X}],Y", "sr": "${:02X},S", "sri": "(${:02X},S),Y", "abs": "${:04X}", "abx": "${:04X},X",
    "aby": "${:04X},Y", "ind": "(${:04X})", "axi": "(${:04X},X)", "ail": "[${:04X}]", "lng": "${:06X}",
    "lngx": "${:06X},X",
}
SIZE = {"imp": 0, "acc": 0, "sig": 1, "imm8": 1, "dp": 1, "dpx": 1, "dpy": 1, "di": 1, "dxi": 1, "diy": 1,
        "dil": 1, "dily": 1, "sr": 1, "sri": 1, "rel": 1, "abs": 2, "abx": 2, "aby": 2, "ind": 2, "axi": 2,
        "ail": 2, "rell": 2, "mv": 2, "lng": 3, "lngx": 3}


def rom_offset(address):
    return ((address >> 16) & 0x3F) << 16 | (address & 0xFFFF)


def disassemble(rom, address, count, m=1, x=1):
    out = []
    for _ in range(count):
        o = rom_offset(address)
        op = rom[o]
        mne, mode = OPS[op]
        if mode == "imm":
            n = 1 if m else 2
        elif mode == "immx":
            n = 1 if x else 2
        else:
            n = SIZE[mode]
        raw = rom[o:o + 1 + n]
        val = int.from_bytes(raw[1:], "little") if n else 0
        pc = address & 0xFFFF
        if mode in ("imm", "immx"):
            arg = f"#${val:0{2 * n}X}"
        elif mode == "rel":
            arg = f"${(address & 0xFF0000) | ((pc + 2 + (val - 256 if val > 127 else val)) & 0xFFFF):06X}"
        elif mode == "rell":
            arg = f"${(address & 0xFF0000) | ((pc + 3 + (val - 65536 if val > 32767 else val)) & 0xFFFF):06X}"
        elif mode == "mv":
            arg = f"${raw[2]:02X},${raw[1]:02X}"
        else:
            arg = FMT[mode].format(val) if FMT[mode] else ""
        out.append((address, raw, f"{mne} {arg}".rstrip()))
        if mne == "REP":
            m = 0 if val & 0x20 else m
            x = 0 if val & 0x10 else x
        elif mne == "SEP":
            m = 1 if val & 0x20 else m
            x = 1 if val & 0x10 else x
        address = (address & 0xFF0000) | ((pc + 1 + n) & 0xFFFF)
    return out


def main():
    rom = open(sys.argv[1], "rb").read()
    bank, pc = sys.argv[2].split(":")
    address = int(bank, 16) << 16 | int(pc, 16)
    count = int(sys.argv[3])
    m = int(sys.argv[sys.argv.index("--m") + 1]) if "--m" in sys.argv else 1
    x = int(sys.argv[sys.argv.index("--x") + 1]) if "--x" in sys.argv else 1
    for addr, raw, text in disassemble(rom, address, count, m, x):
        print(f"{addr >> 16:02X}:{addr & 0xFFFF:04X}  {raw.hex(' '):<12} {text}")


if __name__ == "__main__":
    main()
