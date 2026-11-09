"""Simulador do tiro do Duck Hunt: roda o código 6502 da ROM (py65) e modela o atraso até o CRT.

O que é real: todo o código do jogo a partir de $D160 (validação do tiro, flash, acerto/erro).
O que é simulado:
  - NMI: a cada 29781 ciclos põe $20/$22 = 1 e "faz o DMA" (fotografa o buffer $0200)
  - PPU: o que aparece num quadro = PPUMASK daquele quadro + sprites do DMA do início dele
  - Sensor: mira num ponto da tela; vê luz se o fundo estiver ligado (céu) ou se um sprite
    do tile $56 (quadrado branco) cobrir o ponto. Com atraso de L quadros e "segura" de H
    quadros (os 20 ms do firmware).
  - Entrada: modo "zapper" ($4017 bit 3/4, ROM original) ou "pad" (controle padrão, ROM patcheada)

Uso:
    python test_flash.py ROM_ORIGINAL [ROM_PATCHEADA] [--n 10 --k 7]
"""
import argparse
import sys
from py65.devices.mpu6502 import MPU
from py65.memory import ObservableMemory

CICLOS_QUADRO = 29781
SENTINELA = 0x0700           # endereço de RAM para onde o RTS final volta
TILE_QUADRADO = 0x56
CONFIG_RAM = None            # (K, N) gravados na RAM extra antes de cada teste


class Sim:
    def __init__(self, rom, modo, latencia=0, segura=2, mira=None, luz_sempre=False, gatilho=None):
        self.prg = rom[16:16 + 16384]
        self.modo, self.L, self.H = modo, latencia, segura
        self.mira, self.luz_sempre = mira, luz_sempre
        self.gatilho = gatilho or (lambda q: False)
        self.mem = ObservableMemory()
        self.mem.write(0xC000, list(self.prg))
        self.mem.write(0x8000, list(self.prg))
        if CONFIG_RAM:                                   # K/N na RAM extra ($6000), como o patch grava
            k, n = CONFIG_RAM
            self.mem.write(0x6000, [0x44, 0x48, k, n, k ^ n ^ 0x5A])
        self.cpu = MPU(memory=self.mem)
        self.mask = 0x1E
        self.quadro = 0
        self.oam_atual = [0xF4] * 256
        self.telas = []                  # (mask, oam) de cada quadro fechado
        self.prox_nmi = CICLOS_QUADRO
        self.indice_serial = 0
        self.eventos = []
        m = self.mem
        m.subscribe_to_write([0x2001], self._w_mask)
        m.subscribe_to_write([0x4016], self._w_strobe)
        m.subscribe_to_read([0x4016], lambda a: 0x40)
        m.subscribe_to_read([0x4017], self._r_porta2)
        m.subscribe_to_read([0x2002], lambda a: 0x80)
        m.subscribe_to_write([0x0301, 0x0351, 0x05FF], self._w_resultado)

    # ---------- periféricos ----------
    def _w_mask(self, a, v):
        self.mask = v

    def _w_strobe(self, a, v):
        self.indice_serial = 0

    def _w_resultado(self, a, v):
        self.eventos.append((self.quadro, a, v))

    def _tela_clara(self, q):
        """O ponto mirado estava claro no quadro q (já exibido)?"""
        if q < 0:
            return True                                  # antes do tiro: céu
        mask, oam = self.telas[q] if q < len(self.telas) else (self.mask, self.oam_atual)
        if self.mira is None:
            return False
        if mask & 0x08:
            return True                                  # fundo ligado (céu)
        if mask & 0x10:
            x, y = self.mira
            for i in range(0, 256, 4):
                sy, t, sx = oam[i], oam[i + 1], oam[i + 3]
                if t == TILE_QUADRADO and sy < 0xEF and sx <= x < sx + 8 and sy + 1 <= y < sy + 9:
                    return True
        return False

    def luz(self):
        if self.luz_sempre:
            return True
        return any(self._tela_clara(self.quadro - self.L - h) for h in range(self.H + 1))

    def _r_porta2(self, a):
        if self.modo == "zapper":
            return 0x40 | (0 if self.luz() else 0x08) | (0x10 if self.gatilho(self.quadro) else 0)
        i = self.indice_serial
        self.indice_serial += 1
        bit = {0: self.luz(), 1: self.gatilho(self.quadro)}.get(i, False)
        return 0x40 | (1 if bit else 0)

    def _nmi(self):
        self.telas.append((self.mask, self.oam_atual))
        self.quadro += 1
        self.oam_atual = list(self.mem._subject[0x200:0x300])
        self.mem._subject[0x20] = 1
        self.mem._subject[0x22] = 1

    # ---------- execução ----------
    def chamar(self, endereco, max_quadros=300):
        c = self.cpu
        c.sp = 0xFF
        ret = SENTINELA - 1
        self.mem._subject[0x1FF] = ret >> 8
        self.mem._subject[0x1FE] = ret & 0xFF
        c.sp = 0xFD
        c.pc = endereco
        while c.pc != SENTINELA:
            c.step()
            if c.processorCycles >= self.prox_nmi:
                self.prox_nmi += CICLOS_QUADRO
                self._nmi()
                if self.quadro > max_quadros:
                    raise RuntimeError(f"não terminou (PC=${c.pc:04X})")

    def linha_do_tempo(self):
        s = ""
        for mask, oam in self.telas:
            if mask & 0x18 == 0:
                s += "."                                 # tela preta
            elif mask & 0x08:
                s += "S"                                 # fundo (céu)
            else:
                s += "#" if any(oam[i + 1] == TILE_QUADRADO and oam[i] < 0xEF for i in range(0, 256, 4)) else "_"
        return s


def primeira_forma_valida(prg):
    for forma in range(32):
        ptr = prg[0x2B30 + 2 * forma] | prg[0x2B31 + 2 * forma] << 8
        if not (0xC000 <= ptr < 0x10000):
            continue
        dados = prg[ptr - 0xC000: ptr - 0xC000 + 64]
        if 0xAA in dados[::2][:16] and dados[0] != 0xAA:
            com_sinal = lambda v: v - 256 if v > 127 else v     # deslocamentos são bytes com sinal
            return forma, com_sinal(dados[0]), com_sinal(dados[1])
    raise SystemExit("tabela de formas não encontrada")


PATOS = {1: (0x0300, 80, 100), 2: (0x0350, 60, 180)}   # slot, Y, X


def preparar_tiro(sim, jogo, patos, modo24=False):
    s = sim.mem._subject
    forma, dy, dx = primeira_forma_valida(sim.prg)
    s[0xB9] = 1; s[0xB5] = 1; s[0xBA] = 3; s[0x09] = 0x1E
    s[0x24] = 1 if modo24 else 0
    s[0x1F] = {"A": 0, "B": 1, "C": 2}[jogo]
    alvos = {}
    for n, (slot, y, x) in PATOS.items():
        if n in patos:
            s[slot] = 1; s[slot + 1] = 3; s[slot + 2] = y; s[slot + 3] = x; s[slot + 0x0A] = forma
            alvos[n] = (x + dx + 4, y + dy + 5)                # centro do 1o sprite do quadrado
        else:
            s[slot] = 0
    return alvos


def tiro(rom, modo, jogo="A", patos=(1,), mira=None, L=0, H=2, luz_sempre=False, modo24=False):
    sim = Sim(rom, modo, L, H)
    alvos = preparar_tiro(sim, jogo, patos, modo24)
    sim.mira = alvos.get(mira) if isinstance(mira, int) else mira
    sim.luz_sempre = luz_sempre
    sim.chamar(0xD160)
    atingidos = [1 if a == 0x0301 else 2 for _, a, v in sim.eventos if a in (0x0301, 0x0351) and v == 4]
    r05ff = [v for _, a, v in sim.eventos if a == 0x05FF]
    if modo24:
        res = {1: "acerto ($05FF=1)", 2: "erro ($05FF=2)"}.get(r05ff[-1] if r05ff else 0, "?")
    else:
        res = f"ACERTO pato {atingidos[0]}" if atingidos else "erro"
    return res, sim.linha_do_tempo()


def teste_gatilho(rom, modo, pulso_quadros):
    """Chama $D131/$D160-guard 1x por quadro com B apertado por 'pulso_quadros' a partir do quadro 3."""
    sim = Sim(rom, modo, gatilho=lambda q: 3 <= q < 3 + pulso_quadros)
    s = sim.mem._subject
    s[0xB5] = 0; s[0xB6] = 0; s[0xB7] = 0; s[0xB8] = 0
    for q in range(20):
        sim.quadro = q
        sim.chamar(0xD131)
        if s[0xB5]:
            return q
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("original")
    ap.add_argument("patcheada", nargs="?")
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--k", type=int, default=7)
    a = ap.parse_args()
    orig = open(a.original, "rb").read()
    falhas = 0

    def caso(nome, obtido, esperado, linha=""):
        nonlocal falhas
        ok = obtido.startswith(esperado)
        falhas += not ok
        print(f"  [{'OK ' if ok else 'FALHOU'}] {nome:52s} -> {obtido:18s} {linha}")

    print("Legenda da linha do tempo: S = céu/fundo, . = tela preta, # = quadrado branco, _ = só sprites sem quadrado\n")
    print("ROM ORIGINAL (Zapper):")
    for L in (0, 1, 3):
        r, t = tiro(orig, "zapper", mira=1, L=L, H=0)        # Zapper real não "segura" a luz
        caso(f"Game A, mira no pato, atraso {L}", r, "ACERTO" if L == 0 else "erro", t)
    q = teste_gatilho(orig, "zapper", 3)
    caso("gatilho: pulso de 3 quadros registra o tiro", f"quadro {q}" if q is not None else "não registrou", "quadro")

    if not a.patcheada:
        print("\n(sem ROM patcheada: só a original foi testada)")
        sys.exit(1 if falhas else 0)

    pat = open(a.patcheada, "rb").read()
    N, K = a.n, a.k
    global CONFIG_RAM
    CONFIG_RAM = (K, N)
    print(f"\nROM PATCHEADA (controle padrão; N={N}, K={K}, segura H=2 quadros):")
    for L in range(0, K - 1):
        r, t = tiro(pat, "pad", mira=1, L=L)
        caso(f"Game A, mira no pato, atraso {L}", r, "ACERTO pato 1", t)
    r, t = tiro(pat, "pad", mira=None)
    caso("Game A, sem luz (A nunca apertado)", r, "erro", t)
    r, t = tiro(pat, "pad", luz_sempre=True)
    caso("Game A, A apertado o tempo todo (proteção preta)", r, "erro", t)
    r, t = tiro(pat, "pad", mira=(10, 220), L=3)
    caso("Game A, mira fora do pato (chão escuro)", r, "erro", t)
    for L in (2, 5):
        r, t = tiro(pat, "pad", "B", (1, 2), mira=1, L=L)
        caso(f"Game B, mira no pato 1, atraso {L}", r, "ACERTO pato 1", t)
        r, t = tiro(pat, "pad", "B", (1, 2), mira=2, L=L)
        caso(f"Game B, mira no pato 2, atraso {L}", r, "ACERTO pato 2", t)
    r, t = tiro(pat, "pad", "B", (1, 2), mira=None)
    caso("Game B, sem luz", r, "erro", t)
    r, t = tiro(pat, "pad", "B", (2,), mira=2, L=4)
    caso("Game B, só o pato 2 voando, mira nele", r, "ACERTO pato 2", t)
    r, t = tiro(pat, "pad", "C", (1, 2), mira=2, L=4)
    caso("Game C (pratos), mira no prato 2, atraso 4", r, "ACERTO pato 2", t)
    r, t = tiro(pat, "pad", modo24=True, mira=(128, 100), L=4)
    caso("modo $24<>0 (só fundo), mira na tela, atraso 4", r, "acerto", t)
    r, t = tiro(pat, "pad", modo24=True, luz_sempre=True)
    caso("modo $24<>0, A o tempo todo", r, "erro", t)
    for p in (3, 5, 6):
        q = teste_gatilho(pat, "pad", p)
        caso(f"gatilho: B por {p} quadros (~{p * 16.7:.0f} ms) registra o tiro", f"quadro {q}" if q is not None else "não registrou", "quadro")

    print("\nLimite de atraso (Game A, mira no pato, H=2):")
    lim = [L for L in range(0, N + 6) if tiro(pat, "pad", mira=1, L=L)[0].startswith("ACERTO")]
    print(f"  acerta com atraso de {min(lim)} a {max(lim)} quadros" if lim else "  nunca acerta")
    print(f"\n{'TUDO OK' if not falhas else f'{falhas} FALHA(S)'}")
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()
