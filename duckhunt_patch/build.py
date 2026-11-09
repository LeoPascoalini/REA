"""Monta o patch (ca65/ld65), gera o .ips, aplica numa CÓPIA da ROM e confere tudo.

Uso:
    python build.py "C:/caminho/Duck Hunt (World).nes"
    python build.py ROM --sem-montar     # só gera o .ips a partir dos .bin já montados

Saídas:
    dist/duckhunt_pistola.ips        o patch
    dist/tabela_enderecos.md         endereços alterados (bytes originais x novos)
    build/DuckHunt_pistola.nes       cópia patcheada, só para teste (fora do git)
A ROM original nunca é escrita.
"""
import argparse
import subprocess
import sys
import zlib
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
CC65 = RAIZ / "tools" / "cc65" / "bin"
BUILD = RAIZ / "build"
DIST = RAIZ / "dist"

CRC_ESPERADO = 0x24598791          # ROM sem cabeçalho (No-Intro "Duck Hunt (World)")
BASE_CPU = 0xC000                  # NROM-128: PRG de 16 KB vista em $C000-$FFFF
TAM_CABECALHO = 16
LIVRE = (0xEF5A, 0xF2FF)           # bloco de $FF usado para o código novo

# (arquivo montado, endereço CPU, bytes originais esperados ou None = tem que ser $FF, motivo)
TRECHOS = [
    ("p_D131.bin", 0xD131, bytes.fromhex("AD1740"),
     "LDA $4017 (gatilho da Zapper) -> JSR LerZapper"),
    ("p_D1C7.bin", 0xD1C7, bytes.fromhex("2092D2201EC6"),
     "JSR $D292 / JSR $C61E -> JMP FlashComQuadrado / JMP FlashSemQuadrado"),
    ("p_C176.bin", 0xC176, bytes.fromhex("A90085"),
     "início de partida no título -> JMP IniciaJogo (modo 3 = calibração)"),
    ("p_C19E.bin", 0xC19E, bytes.fromhex("03"),
     "CPY #$03 -> #$04: Select passa por 4 opções"),
    ("p_C1C0.bin", 0xC1C0, bytes.fromhex("51"),
     "LDA #$51 -> #$71: cursor em coluna de 7 linhas"),
    ("p_C1C7.bin", 0xC1C7, bytes.fromhex("04"),
     "LDX #$04 -> #$06: limpa as 7 posições do cursor"),
    ("p_C1DF.bin", 0xC1DF, bytes.fromhex("ADFE05"),
     "LDA $05FE -> JMP PlacarTitulo (K/N no lugar do TOP SCORE no modo 3)"),
    ("p_C5C8.bin", 0xC5C8, bytes.fromhex("2017C6"),
     "JSR $C617 -> JSR DesenhaTitulo (acrescenta a linha CALIBRATION)"),
    ("p_C82B.bin", 0xC82B, bytes.fromhex("ADFE05"),
     "LDA $05FE -> JSR LeModoJogo (modo 3 nunca vira partida)"),
    ("p_NOVO.bin", 0xEF60, None,
     "rotinas novas (pistola, flash, menu, calibração) em espaço livre ($FF)"),
]

# Cabeçalho NES 2.0, bytes 6 a 15. Não depende do cabeçalho do dump (que pode
# ser iNES 1.0): o registro reescreve tudo de forma consistente.
#   6:  $03  mirroring vertical + bateria
#   7:  $08  identificador NES 2.0, mapper 0
#   8-9: $00 sem submapper, PRG/CHR sem bits altos
#   10: $70  8 KB de PRG-NVRAM (64 << 7) em $6000-$7FFF, sem RAM volátil
#   11: $00  sem CHR-RAM
#   12: $02  multi-região (como no cabeçalho No-Intro)
#   13-14: $00
#   15: $01  acessório padrão = controles padrão (antes: $08 = Zapper)
CABECALHO_OFFSET = 6
CABECALHO_NOVO = bytes([0x03, 0x08, 0x00, 0x00, 0x70, 0x00, 0x02, 0x00, 0x00, 0x01])


def offset_arquivo(endereco):
    return endereco - BASE_CPU + TAM_CABECALHO


def montar():
    BUILD.mkdir(exist_ok=True)
    ca65, ld65 = CC65 / "ca65.exe", CC65 / "ld65.exe"
    if not ca65.exists():
        sys.exit(f"ca65 não encontrado em {ca65}")
    cmds = [
        [str(ca65), "-o", str(BUILD / "patch.o"), "-l", str(BUILD / "patch.lst"), str(RAIZ / "src" / "patch.s")],
        [str(ld65), "-C", str(RAIZ / "src" / "patch.cfg"), "-m", str(BUILD / "patch.map"), str(BUILD / "patch.o")],
    ]
    for c in cmds:
        r = subprocess.run(c, cwd=RAIZ, capture_output=True, text=True)
        if r.returncode:
            sys.exit(f"Falhou: {' '.join(c)}\n{r.stdout}{r.stderr}")


def conferir_rom(rom):
    if rom[:4] != b"NES\x1a":
        sys.exit("Não é um arquivo iNES.")
    prg, chr_ = rom[4], rom[5]
    mapper = (rom[6] >> 4) | (rom[7] & 0xF0)
    trainer = bool(rom[6] & 4)
    print(f"ROM: PRG {prg}x16KB, CHR {chr_}x8KB, mapper {mapper}, trainer {trainer}, {len(rom)} bytes")
    if (prg, chr_, mapper, trainer) != (1, 1, 0, False):
        sys.exit("Formato inesperado (esperado NROM-128, 16 KB PRG + 8 KB CHR, sem trainer).")
    crc = zlib.crc32(rom[TAM_CABECALHO:]) & 0xFFFFFFFF
    print(f"CRC32 sem cabeçalho: {crc:08X} (esperado {CRC_ESPERADO:08X})")
    if crc != CRC_ESPERADO:
        sys.exit("CRC diferente: este patch foi feito para outra versão da ROM.")


def gerar_ips(registros):
    out = bytearray(b"PATCH")
    for off, dados in registros:
        assert off != 0x454F46 and len(dados) <= 0xFFFF
        out += off.to_bytes(3, "big") + len(dados).to_bytes(2, "big") + dados
    out += b"EOF"
    return bytes(out)


def aplicar_ips(rom, ips):
    """Aplicador IPS genérico (inclusive registros RLE), para validar o arquivo gerado."""
    assert ips[:5] == b"PATCH"
    rom, i = bytearray(rom), 5
    while ips[i:i + 3] != b"EOF":
        off = int.from_bytes(ips[i:i + 3], "big"); tam = int.from_bytes(ips[i + 3:i + 5], "big"); i += 5
        if tam == 0:
            n = int.from_bytes(ips[i:i + 2], "big"); dados = ips[i + 2:i + 3] * n; i += 3
        else:
            dados = ips[i:i + tam]; i += tam
        rom[off:off + len(dados)] = dados
    return bytes(rom)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rom")
    ap.add_argument("--sem-montar", action="store_true")
    a = ap.parse_args()

    rom = Path(a.rom).read_bytes()
    conferir_rom(rom)
    if not a.sem_montar:
        montar()

    registros, linhas = [], []
    orig_cab = rom[CABECALHO_OFFSET:CABECALHO_OFFSET + len(CABECALHO_NOVO)]
    registros.append((CABECALHO_OFFSET, CABECALHO_NOVO))
    linhas.append((None, CABECALHO_OFFSET, orig_cab, CABECALHO_NOVO,
                   "cabeçalho NES 2.0: 8 KB de RAM com bateria em $6000, controles padrão"))
    for nome, end, esperado, motivo in TRECHOS:
        dados = (BUILD / nome).read_bytes()
        off = offset_arquivo(end)
        orig = rom[off:off + len(dados)]
        if esperado is None:
            fim = end + len(dados) - 1
            if not (LIVRE[0] <= end and fim <= LIVRE[1]) or set(orig) != {0xFF}:
                sys.exit(f"${end:04X}-${fim:04X} não está todo dentro do espaço livre de $FF")
        elif orig != esperado:
            sys.exit(f"${end:04X}: bytes originais {orig.hex(' ')} != esperado {esperado.hex(' ')}")
        registros.append((off, dados))
        linhas.append((end, off, orig, dados, motivo))

    ips = gerar_ips(registros)
    DIST.mkdir(exist_ok=True)
    (DIST / "duckhunt_pistola.ips").write_bytes(ips)

    patcheada = aplicar_ips(rom, ips)
    BUILD.mkdir(exist_ok=True)
    (BUILD / "DuckHunt_pistola.nes").write_bytes(patcheada)

    # Confere que só mudou o que está na tabela
    mudou = [i for i in range(len(rom)) if rom[i] != patcheada[i]]
    permitido = set()
    for off, dados in registros:
        permitido.update(range(off, off + len(dados)))
    fora = [i for i in mudou if i not in permitido]
    if fora or len(patcheada) != len(rom):
        sys.exit(f"Bytes alterados fora dos trechos previstos: {[hex(i) for i in fora[:10]]}")

    def curto(b):
        h = b.hex(" ").upper()
        return h if len(b) <= 8 else f"{b[:6].hex(' ').upper()} … ({len(b)} bytes)"

    md = ["| Endereço CPU | Offset no arquivo | Bytes originais | Bytes novos | Motivo |",
          "|---|---|---|---|---|"]
    for end, off, orig, dados, motivo in linhas:
        onde = "cabeçalho" if end is None else f"${end:04X}-${end + len(dados) - 1:04X}"
        md.append(f"| {onde} | 0x{off:05X} | {curto(orig)} | {curto(dados)} | {motivo} |")
    (DIST / "tabela_enderecos.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    print("\n".join(md))
    crc_novo = zlib.crc32(patcheada[TAM_CABECALHO:]) & 0xFFFFFFFF
    print(f"\nIPS: {DIST / 'duckhunt_pistola.ips'} ({len(ips)} bytes)")
    print(f"Cópia patcheada: {BUILD / 'DuckHunt_pistola.nes'} (CRC32 sem cabeçalho {crc_novo:08X})")
    print(f"Bytes alterados: {len(mudou)}, todos dentro dos trechos da tabela.")


if __name__ == "__main__":
    main()
