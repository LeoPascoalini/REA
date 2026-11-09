"""NES mínimo para testar o patch: CPU 6502 (py65) + PPU simplificada + controles + pistola.

Não desenha a imagem inteira: guarda nametable, paleta e OAM, e calcula a cor de um
pixel quando a pistola precisa saber se o ponto mirado está claro. Suficiente para:
  - ler a tela (nametable como texto),
  - simular a pistola com atraso de L quadros e "segura" de H quadros,
  - rodar o jogo a partir do RESET com Select/Start/direcional no controle 1.
"""
from py65.devices.mpu6502 import MPU
from py65.memory import ObservableMemory

CICLOS_QUADRO = 29781
CICLOS_VBLANK = 2273

BOTOES = ["A", "B", "SELECT", "START", "CIMA", "BAIXO", "ESQ", "DIR"]


def cor_clara(c):
    """Cores NES claras o bastante para o sensor (linhas $2x/$3x, exceto pretos $xD-$xF)."""
    return (c & 0x30) >= 0x20 and (c & 0x0F) < 0x0D


def tile_txt(t):
    if t < 10:
        return str(t)
    if t < 0x24:
        return chr(ord("A") + t - 10)
    return {0x24: " ", 0x27: "=", 0x26: ">"}.get(t, "·")


class NES:
    def __init__(self, rom, prg_ram=None):
        self.rom = rom
        prg = rom[16:16 + 16384]
        self.chr = rom[16 + 16384:16 + 16384 + 8192]
        self.mem = ObservableMemory()
        self.mem.write(0x8000, list(prg))
        self.mem.write(0xC000, list(prg))
        if prg_ram is not None:                      # conteúdo inicial da RAM extra ($6000)
            self.mem.write(0x6000, list(prg_ram))
        self.cpu = MPU(memory=self.mem)
        # PPU
        self.ctrl = self.mask = 0
        self.vblank = False
        self.w = 0
        self.t = self.v = 0
        self.scroll_x = self.scroll_y = 0
        self.vram = bytearray(0x1000)               # nametables (espelhamento vertical)
        self.pal = bytearray(32)
        self.oam = bytearray(256)
        self.buf2007 = 0
        # controles
        self.strobe = 0
        self.idx = [0, 0]
        self.estado = [0, 0]                        # byte latched: bit7=A ... bit0=Dir
        self.pad1 = lambda q: set()                 # quadro -> conjunto de botões
        self.gatilho = lambda q: False
        self.mira = None                            # (x, y) ou None
        self.L, self.H = 0, 2
        self.luz_sempre = False
        # histórico de quadros exibidos
        self.quadro = 0
        self.claro = []                             # o ponto mirado estava claro no quadro q?
        self.telas = []                             # (mask, cor de fundo $3F00) por quadro
        self.log_ppu = None                         # lista para registrar escritas em $2007
        m = self.mem
        m.subscribe_to_write([0x2000], self._w2000)
        m.subscribe_to_write([0x2001], self._w2001)
        m.subscribe_to_read([0x2002], self._r2002)
        m.subscribe_to_write([0x2005], self._w2005)
        m.subscribe_to_write([0x2006], self._w2006)
        m.subscribe_to_write([0x2007], self._w2007)
        m.subscribe_to_read([0x2007], self._r2007)
        m.subscribe_to_write([0x4014], self._w4014)
        m.subscribe_to_write([0x4016], self._w4016)
        m.subscribe_to_read([0x4016], lambda a: self._ler_porta(0))
        m.subscribe_to_read([0x4017], lambda a: self._ler_porta(1))
        m.subscribe_to_read([0x4015], lambda a: 0)
        self.cpu.reset()
        self.cpu.pc = self.cpu.WordAt(0xFFFC)

    # ---------------- PPU ----------------
    def _end_vram(self, a):
        a &= 0x3FFF
        if a >= 0x3F00:
            i = a & 0x1F
            if i in (0x10, 0x14, 0x18, 0x1C):
                i -= 0x10
            return ("pal", i)
        if a >= 0x2000:
            return ("nt", (a - 0x2000) & 0x7FF)     # vertical: $2000=$2800, $2400=$2C00
        return ("chr", a)

    def _w2000(self, a, v):
        self.ctrl = v

    def _w2001(self, a, v):
        self.mask = v

    def _r2002(self, a):
        r = (0x80 if self.vblank else 0) | 0x40     # bit 6 (sprite 0) sempre 1: o jogo não usa
        self.vblank = False
        self.w = 0
        return r

    def _w2005(self, a, v):
        if self.w == 0:
            self.scroll_x = v
        else:
            self.scroll_y = v
        self.w ^= 1

    def _w2006(self, a, v):
        if self.w == 0:
            self.t = ((v & 0x3F) << 8) | (self.t & 0xFF)
        else:
            self.t = (self.t & 0xFF00) | v
            self.v = self.t
        self.w ^= 1

    def _w2007(self, a, v):
        tipo, i = self._end_vram(self.v)
        if tipo == "pal":
            self.pal[i] = v & 0x3F
        elif tipo == "nt":
            self.vram[i] = v
        if self.log_ppu is not None:
            self.log_ppu.append((self.quadro, self.cpu.pc, self.v & 0x3FFF, v))
        self.v = (self.v + (32 if self.ctrl & 4 else 1)) & 0x3FFF

    def _r2007(self, a):
        tipo, i = self._end_vram(self.v)
        r = self.buf2007
        if tipo == "nt":
            self.buf2007 = self.vram[i]
        elif tipo == "chr":
            self.buf2007 = self.chr[i]
        elif tipo == "pal":
            r = self.pal[i]
        self.v = (self.v + (32 if self.ctrl & 4 else 1)) & 0x3FFF
        return r

    def _w4014(self, a, v):
        self.oam = bytearray(self.mem._subject[v << 8:(v << 8) + 256])
        self.cpu.processorCycles += 513

    # ---------------- controles ----------------
    def _byte_pad(self, conjunto):
        b = 0
        for i, nome in enumerate(BOTOES):
            if nome in conjunto:
                b |= 0x80 >> i
        return b

    def _latch(self):
        luz = self.luz()
        p2 = {"A"} if luz else set()
        if self.gatilho(self.quadro):
            p2.add("B")
        self.estado = [self._byte_pad(self.pad1(self.quadro)), self._byte_pad(p2)]
        self.idx = [0, 0]

    def _w4016(self, a, v):
        if v & 1:
            self.strobe = 1
        elif self.strobe:
            self.strobe = 0
            self._latch()

    def _ler_porta(self, p):
        if self.strobe:
            self._latch()
        i = self.idx[p]
        self.idx[p] += 1
        bit = (self.estado[p] >> (7 - i)) & 1 if i < 8 else 1
        return 0x40 | bit

    # ---------------- pistola ----------------
    def pixel(self, x, y):
        """Cor NES do pixel (x, y) no estado atual, com scroll ($2005 + bits de nametable do $2000).
        Espelhamento vertical: a tela de baixo repete a de cima."""
        cor = self.pal[0]
        if self.mask & 0x08:
            wx = (x + self.scroll_x + (self.ctrl & 1) * 256) % 512
            wy = (y + self.scroll_y) % 240
            nt = (wx // 256) * 0x400
            px, py = wx % 256, wy
            t = self.vram[nt + (py // 8) * 32 + (px // 8)]
            base = 0x1000 if self.ctrl & 0x10 else 0
            lo = self.chr[base + t * 16 + (py % 8)]
            hi = self.chr[base + t * 16 + 8 + (py % 8)]
            c = ((lo >> (7 - px % 8)) & 1) | (((hi >> (7 - px % 8)) & 1) << 1)
            if c:
                at = self.vram[nt + 0x3C0 + (py // 32) * 8 + (px // 32)]
                pal = (at >> (((py % 32) // 16) * 4 + ((px % 32) // 16) * 2)) & 3
                cor = self.pal[pal * 4 + c]
        if self.mask & 0x10:
            base = 0x1000 if self.ctrl & 0x08 else 0
            for i in range(0, 256, 4):
                sy, t, at, sx = self.oam[i:i + 4]
                if sx <= x < sx + 8 and sy + 1 <= y < sy + 9:
                    r, col = y - sy - 1, x - sx
                    if at & 0x80:
                        r = 7 - r
                    if at & 0x40:
                        col = 7 - col
                    lo = self.chr[base + t * 16 + r]
                    hi = self.chr[base + t * 16 + 8 + r]
                    c = ((lo >> (7 - col)) & 1) | (((hi >> (7 - col)) & 1) << 1)
                    if c:
                        return self.pal[0x10 + (at & 3) * 4 + c]
        if not (self.mask & 0x18):
            return self.pal[0]                       # tela desligada: cor de fundo
        return cor

    def _claro_agora(self):
        mira = self.mira(self) if callable(self.mira) else self.mira
        if mira is None:
            return False
        x, y = mira
        if not (0 <= x < 256 and 0 <= y < 240):
            return False
        return cor_clara(self.pixel(x, y))

    def luz(self):
        if self.luz_sempre:
            return True
        q = self.quadro
        for h in range(self.H + 1):
            f = q - self.L - h
            if f < 0:
                continue
            if f < len(self.claro) and self.claro[f]:
                return True
            if f == q and self._claro_agora():
                return True
        return False

    # ---------------- execução ----------------
    def rodar_quadros(self, n, parar_em=None):
        c = self.cpu
        for _ in range(n):
            inicio = c.processorCycles
            self.vblank = True
            if self.ctrl & 0x80:
                c.nmi()
            while c.processorCycles - inicio < CICLOS_QUADRO:
                if parar_em and c.pc in parar_em:
                    return c.pc
                c.step()
                if self.vblank and c.processorCycles - inicio >= CICLOS_VBLANK:
                    self.vblank = False
            self.claro.append(self._claro_agora())
            self.telas.append((self.mask, self.pal[0]))
            self.quadro += 1
        return None

    def apertar(self, botoes, quadros=3, soltar=6):
        """Aperta botões no controle 1 por alguns quadros e solta (debounce do jogo = 5 leituras)."""
        ini = self.quadro
        anterior = self.pad1
        self.pad1 = lambda q, a=anterior: set(botoes) if ini <= q < ini + quadros else a(q)
        self.rodar_quadros(quadros + soltar)
        self.pad1 = anterior

    def texto(self, linhas=range(30)):
        return "\n".join(f"{r:2d} " + "".join(tile_txt(self.vram[r * 32 + c]) for c in range(32)) for r in linhas)
