"""Testes da V5 (protocolo 2: a pistola decide o acerto), rodando a ROM inteira no NES simulado.

A pistola simulada segue as regras de "firmware pistola/PROTOCOLO_NOVO.md", em quadros:
  - vê a TV com atraso Lout (quadros entre o jogo desenhar e o tubo mostrar);
  - o que ela aperta chega no jogo com atraso Lin;
  - sincroniza pelo início do preto quando a mira está num ponto claro, e mede a "ida";
    num ponto escuro usa a ida medida antes;
  - janela 1 (quadros 2-3 do preto): primeira luz -> A;
  - janela 2 (quadros 5-6) + quadro 7 escuro -> A + B;
  - ignora o próprio gatilho até o fim do tiro.

Uso:
    python -P test_p2.py build/DuckHunt_V5.nes
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sim_nes import NES, cor_clara  # noqa: E402

falhas = 0
PRAZO = 9


def caso(nome, ok, detalhe=""):
    global falhas
    falhas += not ok
    print(f"  [{'OK ' if ok else 'FALHOU'}] {nome:62s} {detalhe}")


class Pistola2:
    IDA_INICIAL = 9             # ~150 ms: pulso do gatilho (50 ms) + jogo + atrasos

    def __init__(self, n, Lout=2, Lin=2):
        self.n, self.Lout, self.Lin = n, Lout, Lin
        self.botoes = {}            # quadro do jogo -> botões
        self.ida = self.IDA_INICIAL # ida estimada (gatilho -> 1o quadro preto na TV)
        self.medidas = []
        self.e = None
        self.decisoes = []

    def pad2(self, q):
        return self.botoes.get(q, set())

    def _apertar(self, q0, bot, n=3):
        for q in range(q0, q0 + n):
            self.botoes.setdefault(q, set()).update(bot)

    def _tv(self, t):
        """Luz no ponto mirado no quadro t da TV (o jogo desenhou esse quadro em t - Lout)."""
        q = t - self.Lout
        return 0 <= q < len(self.n.claro) and self.n.claro[q]

    def livre(self):
        return self.e is None or self.e["fim"]

    def atirar(self):
        if not self.livre():
            return False
        tg = self.n.quadro
        self._apertar(tg + self.Lin, {"B"})
        self.e = dict(tg=tg, t0=None, sync=None, prox=2, decidiu=None, luz2=False, fim=False)
        return True

    def passo(self):
        e = self.e
        if e is None or e["fim"]:
            return
        t = self.n.quadro - 1                      # agora a TV mostra o quadro t
        tg = e["tg"]
        if e["t0"] is None:
            # início do preto: claro -> escuro, escuro por 2 quadros, depois do pulso do
            # gatilho. Antes da 1a medição aceita qualquer um; depois, só perto da ida
            # medida (-2..+3), para o pato passando sob a mira não enganar.
            c = t - 1
            perto = not self.medidas or -2 <= c - (tg + self.ida) <= 3
            if c > tg + 3 and self._tv(c - 1) and not self._tv(c) and not self._tv(t) and perto:
                e["t0"], e["sync"] = c, "céu"
                self.medidas.append(c - tg)
                self.ida = round(sum(self.medidas[-8:]) / len(self.medidas[-8:]))
            elif self.medidas and t >= tg + self.ida + 5:   # só com ida medida; passou a janela
                t0 = tg + self.ida
                if not self._tv(t0) and not self._tv(t0 + 1):
                    e["t0"], e["sync"] = t0, "estimada"
                else:                               # onde devia haver preto há luz:
                    e["sync"], e["fim"] = "falhou", True    # estimativa errada, não arrisca
                    self.medidas, self.ida = [], self.IDA_INICIAL   # reaprende a ida no próximo tiro
        if e["t0"] is not None:
            # avalia em ordem os quadros já vistos (pode olhar para trás no histórico)
            while e["prox"] <= t - e["t0"] and not e["fim"]:
                rel = e["prox"]
                luz = self._tv(e["t0"] + rel)
                if rel in (2, 3) and luz and not e["decidiu"]:
                    e["decidiu"] = "A"
                    self._apertar(t + self.Lin, {"A"})
                if rel in (5, 6) and luz:
                    e["luz2"] = True
                if rel == 7 and not e["decidiu"] and e["luz2"] and not luz:
                    e["decidiu"] = "A+B"
                    self._apertar(t + self.Lin, {"A", "B"})
                if rel >= 8 + 10:
                    e["fim"] = True
                e["prox"] += 1
        if t - tg > 30:
            e["fim"] = True
        if e["fim"]:
            self.decisoes.append(e["decidiu"])


def rodar(n, p, k):
    for _ in range(k):
        n.rodar_quadros(1)
        p.passo()


def esperar_voando(n, p, slots, limite=3000):
    s = n.mem._subject
    for _ in range(limite):
        rodar(n, p, 1)
        if all(s[b] and s[b + 1] == 3 for b in slots):
            return True
    return False


def nova_partida(rom, modo, Lout=2, Lin=2):
    n = NES(rom)
    p = Pistola2(n, Lout, Lin)
    n.pad2 = p.pad2
    rodar(n, p, 60)
    s = n.mem._subject
    while s[0x5FE] != modo:
        n.apertar(["SELECT"], quadros=8, soltar=8)
    n.apertar(["START"], quadros=8, soltar=8)
    return n, p


def segue(slot):
    return lambda nes: (nes.mem._subject[slot + 3], nes.mem._subject[slot + 2])


def tiro(n, p, mira, quadros=45):
    """Atira e devolve (máscaras da tela por quadro, tiros registrados, acertos, balas antes/depois)."""
    s = n.mem._subject
    n.mira = mira
    tiros, acertos, on = [], [], [True]
    n.mem.subscribe_to_write([0x00B5], lambda a, v: tiros.append(n.quadro) if v == 1 and on[0] else None)
    n.mem.subscribe_to_write([0x0301, 0x0351], lambda a, v: acertos.append(1 if a == 0x0301 else 2) if v == 4 and on[0] else None)
    balas = s[0xBA]
    while not p.livre():
        rodar(n, p, 1)
    rodar(n, p, p.Lout + 3)             # mira antes de atirar (a pistola vê a TV com atraso)
    balas = s[0xBA]
    assert p.atirar()
    masks = []
    for _ in range(quadros):
        rodar(n, p, 1)
        masks.append(n.mask & 0x18)
    on[0] = False                       # py65 não remove inscrições: desliga esta
    return masks, tiros, acertos, balas, s[0xBA]


def piscada(masks):
    """Trecho entre o primeiro quadro diferente do normal ($18) e a volta ao normal."""
    i = next((k for k, m in enumerate(masks) if m != 0x18), None)
    if i is None:
        return []
    j = next((k for k in range(i, len(masks)) if masks[k] == 0x18), len(masks))
    return masks[i:j]


FORMA_1 = [0x00, 0x00, 0x10, 0x10, 0x00]
FORMA_2 = [0x00, 0x00, 0x10, 0x10, 0x00, 0x10, 0x10, 0x00]
CEU = (128, 30)


def main():
    rom = Path(sys.argv[1]).read_bytes()

    print("Game A (Lout=2, Lin=2): céu, depois o pato")
    n, p = nova_partida(rom, 0)
    s = n.mem._subject
    caso("pato voando", esperar_voando(n, p, (0x0300,)))
    masks, tiros, acertos, b0, b1 = tiro(n, p, CEU)
    caso("piscada: 2 pretos, 2 quadrado, 1 preto", piscada(masks) == FORMA_1, f"{[hex(m) for m in piscada(masks)]}")
    caso("mira no céu -> nenhum acerto", not acertos, f"{acertos}")
    caso("um tiro registrado (B não vira tiro fantasma)", len(tiros) == 1, f"{tiros}")
    caso("bala gasta depois do prazo", b1 == b0 - 1, f"{b0}->{b1}")
    caso("pistola sincronizou pelo céu e mediu a ida", p.ida is not None, f"ida={p.ida} quadros")
    caso("pato continua voando", s[0x0301] == 3)
    masks, tiros, acertos, b0, b1 = tiro(n, p, segue(0x0300))
    caso("mira no pato -> acerto no pato 1", acertos == [1], f"{acertos}, pistola: {p.decisoes[-1]}")
    caso("um tiro registrado", len(tiros) == 1, f"{tiros}")
    caso("bala gasta", b1 == b0 - 1, f"{b0}->{b1}")

    print("\nGame A, última bala no céu: o pato só foge depois do prazo")
    n, p = nova_partida(rom, 0)
    s = n.mem._subject
    esperar_voando(n, p, (0x0300,))
    tiro(n, p, CEU); tiro(n, p, CEU)
    n.mira = CEU
    while not p.livre():
        rodar(n, p, 1)
    rodar(n, p, p.Lout + 3)
    p.atirar()
    fim_pisca, fugiu = None, None
    for k in range(60):
        rodar(n, p, 1)
        if fim_pisca is None and k > 3 and n.mask & 0x18 == 0x18:
            fim_pisca = k
        if fugiu is None and s[0x4E]:
            fugiu = k
    caso("o pato fugiu", fugiu is not None, f"quadro {fugiu}")
    caso("só depois do prazo (~9 quadros após a piscada)", fugiu is not None and fim_pisca is not None and fugiu - fim_pisca >= PRAZO - 1,
         f"fim da piscada {fim_pisca}, fuga {fugiu}")
    caso("balas = 0", s[0xBA] == 0, f"{s[0xBA]}")

    print("\nGame A, última bala no pato com Bluetooth lento (Lin=5): acerto atrasado ainda vale")
    n, p = nova_partida(rom, 0, Lout=2, Lin=5)
    s = n.mem._subject
    esperar_voando(n, p, (0x0300,))
    tiro(n, p, CEU); tiro(n, p, CEU)
    masks, tiros, acertos, b0, b1 = tiro(n, p, segue(0x0300))
    caso("acerto no pato 1", acertos == [1], f"{acertos}, pistola: {p.decisoes[-1]}")
    caso("o pato não fugiu antes", s[0x4E] == 0, f"$4E={s[0x4E]}")

    print("\nPistola com a ida errada (medição antiga de outra conexão), mirando no céu")
    for ida_errada in (4, 15):
        n, p = nova_partida(rom, 0)
        s = n.mem._subject
        esperar_voando(n, p, (0x0300,))
        p.medidas, p.ida = [ida_errada], ida_errada
        masks, tiros, acertos, b0, b1 = tiro(n, p, CEU)
        caso(f"ida {ida_errada} (real ~9): nenhum acerto falso", not acertos, f"{acertos}, sincronia: {p.e['sync']}")
        tiro(n, p, CEU)
        caso(f"ida {ida_errada}: no tiro seguinte reaprende a ida", p.e["sync"] == "céu", f"ida={p.ida}, sincronia: {p.e['sync']}")
        if s[0x0301] != 3:
            esperar_voando(n, p, (0x0300,))
        masks, tiros, acertos, b0, b1 = tiro(n, p, segue(0x0300))
        caso(f"ida {ida_errada}: e volta a acertar o pato", acertos == [1], f"{acertos}")

    print("\nGame B (2 patos): pato 2, pato 1, céu")
    for alvo, slot in ((2, 0x0350), (1, 0x0300)):
        n, p = nova_partida(rom, 1)
        s = n.mem._subject
        esperar_voando(n, p, (0x0300, 0x0350))
        tiro(n, p, CEU)                                     # mede a ida
        if not (s[0x0301] == 3 and s[0x0351] == 3):
            esperar_voando(n, p, (0x0300, 0x0350))
        masks, tiros, acertos, b0, b1 = tiro(n, p, segue(slot))
        caso(f"piscada com 2 quadrados", piscada(masks) == FORMA_2, f"{[hex(m) for m in piscada(masks)]}")
        caso(f"mira no pato {alvo} -> acerto só no pato {alvo}", acertos == [alvo], f"{acertos}, pistola: {p.decisoes[-1]}")
        outro = 0x0301 if alvo == 2 else 0x0351
        caso(f"o outro pato continua voando", s[outro] == 3, f"estado {s[outro]}")
        caso("um tiro registrado", len(tiros) == 1, f"{tiros}")

    print("\nGame C (pratos): prato 2")
    n, p = nova_partida(rom, 2)
    s = n.mem._subject
    esperar_voando(n, p, (0x0300, 0x0350))
    tiro(n, p, CEU)
    if not (s[0x0301] == 3 and s[0x0351] == 3):
        esperar_voando(n, p, (0x0300, 0x0350))
    masks, tiros, acertos, b0, b1 = tiro(n, p, segue(0x0350))
    caso("mira no prato 2 -> acerto no prato 2", acertos == [2], f"{acertos}, pistola: {p.decisoes[-1]}")

    print("\nAtrasos diferentes (Game A, mira no pato)")
    for Lout, Lin in ((1, 1), (2, 4), (3, 3)):
        n, p = nova_partida(rom, 0, Lout, Lin)
        esperar_voando(n, p, (0x0300,))
        tiro(n, p, CEU)
        masks, tiros, acertos, b0, b1 = tiro(n, p, segue(0x0300))
        caso(f"Lout={Lout} Lin={Lin}: acerto", acertos == [1], f"{acertos}, ida={p.ida}")

    print("\nTela de título")
    n = NES(rom)
    p = Pistola2(n, 2, 2)
    n.pad2 = p.pad2
    rodar(n, p, 60)
    s = n.mem._subject
    claro = next(((x, y) for y in range(24, 120, 2) for x in range(40, 216, 2) if cor_clara(n.pixel(x, y))), None)
    caso("achei um ponto claro no logotipo", claro is not None, f"{claro}")
    n.mira = None
    rodar(n, p, 5)
    p.atirar(); rodar(n, p, 60)
    caso("tiro fora da TV -> próxima opção", s[0x5FE] == 1, f"modo {s[0x5FE]}")
    n.mira = claro
    rodar(n, p, 5)
    p.atirar(); rodar(n, p, 90)
    caso("tiro na TV -> começa a partida", s[0x24] == 0, f"$24={s[0x24]} modo={s[0x5FE]}")

    print(f"\n{'TUDO OK' if not falhas else f'{falhas} FALHA(S)'}")
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()
