"""Extract DKC1 disassembly assets from a ROM using AssetPointersAndFiles.asm (same as ExtractAssets.bat).

usage: python extract_assets.py <rom> <DKC1 disassembly dir>
"""
import re
import sys
from pathlib import Path

# Pointer groups in the order of MainPointerTable, with ExtractAssets.bat's destination folders.
GROUPS = [
    ("UncompressedGFXPointers", "Graphics"),
    ("DynamicSpriteGFXPointers", "Graphics/DynamicSprites"),
    ("CompressedGFXPointers", "Graphics/Compressed"),
    ("UncompressedTilemapsPointers", "Tilemaps"),
    ("CompressedTilemapsPointers", "Tilemaps/Compressed"),
    ("Map32Pointers", "Tilemaps/Map32"),
    ("LevelDataPointers", "LevelData"),
    ("LevelSpritePointers", "LevelData/SpriteData"),
    ("BananaDataPointers", "LevelData/BananaFormations"),
    ("PalettesPointers", "Palettes"),
    ("GarbageDataPointers", "GarbageData"),
    ("MusicPointers", "SPC700/Music"),
    ("SoundEffectPointers", "SPC700/SoundEffects"),
    ("BRRPointers", "SPC700/Samples"),
]


def rom_offset(address):
    bank = address >> 16
    if bank >= 0xC0:
        return address - 0xC00000
    if 0x40 <= bank < 0x7E:
        return address - 0x400000
    if bank >= 0x80:
        return ((bank - 0x80) << 16) | (address & 0xFFFF)
    return address


def main():
    rom = Path(sys.argv[1]).read_bytes()
    root = Path(sys.argv[2])
    source = (root / "AsarScripts" / "AssetPointersAndFiles.asm").read_text(encoding="latin-1")
    filenames = dict(re.findall(r'^(\w+):\s*\n\s*db\s+"([^"]+)"', source, re.M))
    groups = []
    for group, folder in GROUPS:
        block = re.search(rf"^{group}Start:\s*\n(.*?)^{group}End:", source, re.M | re.S).group(1)
        entries = [(int(s, 16), int(e, 16), label)
                   for s, e, label in re.findall(r"dl\s+\$([0-9A-F]+),\$([0-9A-F]+),(\w+),\w+", block)]
        groups.append((group, folder, entries))
    # Some table entries run past the start of the next asset (e.g. Layer2_IntroSky into DATA_EEFE9D);
    # the sources expect each file to stop where the next one begins.
    starts = sorted({start for _, _, entries in groups for start, _, _ in entries})
    total = 0
    for group, folder, entries in groups:
        out = root / folder
        out.mkdir(parents=True, exist_ok=True)
        for start, end, label in entries:
            following = next((s for s in starts if start < s < end), None)
            if following is not None:
                print(f"  trimmed {filenames[label]}: {end:06X} -> {following:06X}")
                end = following
            (out / filenames[label]).write_bytes(rom[rom_offset(start):rom_offset(end)])
            total += 1
        print(f"{group:<30} {len(entries):>4} files -> {folder}")
    print("total files:", total)


if __name__ == "__main__":
    main()
