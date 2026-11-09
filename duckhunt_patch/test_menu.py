"""Testes do menu CALIBRATION e da calibração automática, rodando a ROM inteira no NES simulado.

Uso:
    python -P test_menu.py build/DuckHunt_pistola.nes
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sim_nes import NES, cor_clara  # noqa: E402

falhas = 0


def caso(nome, ok, detalhe=""):
    global falhas
    falhas += not ok
    print(f"  [{'OK ' if ok else 'FALHOU'}] {nome:58s} {detalhe}")


def linha(n, r):
    return n.texto([r])[3:].rstrip()


def cfg(n):
    s = n.mem._subject
    return s[0x6002], s[0x6003]


def boot(rom, prg_ram=None):
    n = NES(rom, prg_ram)
    n.rodar_quadros(60)
    return n


def ir_para_modo(n, modo):
    while n.mem._subject[0x5FE] != modo:
        n.apertar(["SELECT"], quadros=8, soltar=8)


def calibrar(n, L, H=2, mira=(128, 120), luz_sempre=False):
    ir_para_modo(n, 3)
    n.mira, n.L, n.H, n.luz_sempre = mira, L, H, luz_sempre
    n.apertar(["START"], quadros=8, soltar=8)
    n.rodar_quadros(700)
    n.luz_sempre = False


def tela_titulo_ok(n):
    return (linha(n, 17).endswith("GAME A   1 DUCK") and linha(n, 23).endswith("CALIBRATION")
            and n.mask & 0x18 and n.pal[0] == 0x0F)


def ponto_claro_titulo(n):
    for y in range(24, 120, 2):
        for x in range(40, 216, 2):
            if cor_clara(n.pixel(x, y)):
                return (x, y)
    return None


def main():
    rom = Path(sys.argv[1]).read_bytes()

    print("Tela de título:")
    n = boot(rom)
    caso("linha 23 mostra CALIBRATION", linha(n, 23).strip() == "CALIBRATION", f"'{linha(n, 23).strip()}'")
    caso("linha 24 mostra TOP SCORE no Game A", "TOP SCORE = 12000" in linha(n, 24))
    caso("valores padrão na RAM extra vazia", cfg(n) == (7, 10), f"K,N={cfg(n)}")

    print("\nSelect passa pelas 4 opções:")
    esperado = [(1, 19), (2, 21), (3, 23), (0, 17)]
    for modo, lin in esperado:
        n.apertar(["SELECT"], quadros=8, soltar=8)
        caso(f"modo {modo}: cursor na linha {lin}", n.mem._subject[0x5FE] == modo and linha(n, lin).strip().startswith(">"))
        if modo == 3:
            caso("modo 3: linha 24 mostra K e N", linha(n, 24).strip() == "K=07  N=10", f"'{linha(n, 24).strip()}'")
        if modo == 0:
            caso("de volta ao Game A: TOP SCORE restaurado", "TOP SCORE = 12000" in linha(n, 24))

    print("\nAjuste manual (modo 3):")
    ir_para_modo(n, 3)
    passos = [("CIMA", (8, 11)), ("CIMA", (9, 12)), ("BAIXO", (8, 11)), ("DIR", (8, 12)),
              ("ESQ", (8, 11)), ("ESQ", (8, 10)), ("ESQ", (8, 9)), ("ESQ", (8, 9))]
    for b, ok in passos:
        n.apertar([b], quadros=8, soltar=8)
        caso(f"{b:5s} -> K,N = {ok}", cfg(n) == ok, f"obtido {cfg(n)}, tela '{linha(n, 24).strip()}'")
    for _ in range(9):
        n.apertar(["BAIXO"], quadros=8, soltar=8)
    caso("K não desce abaixo de 1", cfg(n)[0] == 1, f"{cfg(n)}")

    print("\nRAM com bateria:")
    salvo = bytes(n.mem._subject[0x6000:0x6010])
    n2 = boot(rom, salvo)
    ir_para_modo(n2, 3)
    caso("valores voltam depois de desligar/ligar", cfg(n2) == cfg(n), f"{cfg(n2)} / tela '{linha(n2, 24).strip()}'")
    lixo = bytes([0xA7, 0x13, 0x00, 0xFF, 0x42] + [0x55] * 11)
    n3 = boot(rom, lixo)
    caso("RAM com lixo vira o padrão 7/10", cfg(n3) == (7, 10), f"{cfg(n3)}")

    print("\nCalibração automática (H = 2 quadros de 'segura'):")
    for L in (0, 2, 3, 5, 8):
        n = boot(rom)
        calibrar(n, L)
        K = L + 2 + 1
        N = max(K, L) + 3
        s = n.mem._subject
        caso(f"atraso {L}: K={K} N={N}", cfg(n) == (K, N),
             f"obtido {cfg(n)} (sobe={s[0x6006]}, desce={s[0x6007]})")
        caso(f"atraso {L}: tela de título restaurada", tela_titulo_ok(n))
    n = boot(rom)
    antes = cfg(n)
    calibrar(n, 3, mira=None)
    caso("pistola fora da TV: não muda nada", cfg(n) == antes and tela_titulo_ok(n), f"{cfg(n)}")
    n = boot(rom)
    calibrar(n, 3, luz_sempre=True)
    caso("sensor sempre aceso: não muda nada", cfg(n) == antes and tela_titulo_ok(n), f"{cfg(n)}")

    print("\nSó com a pistola na tela de título:")
    n = boot(rom)
    n.L, n.H = 3, 2
    alvo = ponto_claro_titulo(n)
    caso("achei um ponto claro no logotipo para mirar", alvo is not None, f"{alvo}")

    def atirar(n, mira):
        n.mira = mira
        ini = n.quadro
        n.gatilho = lambda q: ini + 2 <= q < ini + 5      # pulso de 3 quadros (~50 ms)
        n.rodar_quadros(80)
        n.gatilho = lambda q: False

    for esperado_modo in (1, 2, 3):
        atirar(n, None)
        caso(f"tiro fora da tela -> modo {esperado_modo}", n.mem._subject[0x5FE] == esperado_modo)
    atirar(n, alvo)
    n.rodar_quadros(600)
    caso("tiro na tela com CALIBRATION -> calibra", cfg(n) == (6, 9) and tela_titulo_ok(n), f"{cfg(n)}")

    print("\nTítulo parado no modo 3 (procura demonstração automática):")
    n.mira = None
    n.rodar_quadros(1800)
    s = n.mem._subject
    caso("30 s parado: continua no título, modo 3", s[0x24] == 1 and s[0x5FE] == 3 and tela_titulo_ok(n),
         f"$24={s[0x24]} modo={s[0x5FE]}")

    print("\nPartida do Game A depois da calibração (atraso 3, K=6 N=9):")
    acertos = []
    n.mem.subscribe_to_write([0x0301], lambda a, v: acertos.append(n.quadro) if v == 4 else None)
    ir_para_modo(n, 0)
    n.apertar(["START"], quadros=8, soltar=8)
    for _ in range(1500):
        n.rodar_quadros(1)
        if s[0x0300] and s[0x0301] == 3:
            break
    caso("pato 1 voando", s[0x0300] and s[0x0301] == 3, f"quadro {n.quadro}")
    n.mira = lambda nes: (nes.mem._subject[0x0303], nes.mem._subject[0x0302])   # segue o pato
    balas = s[0xBA]
    atirar(n, n.mira)
    caso("tiro mirando no pato -> acerto", bool(acertos), f"balas {balas}->{s[0xBA]}, acerto no quadro {acertos[:1]}")
    caso("partida seguiu normal (modo $1F = 0)", s[0x1F] == 0)

    print(f"\n{'TUDO OK' if not falhas else f'{falhas} FALHA(S)'}")
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()
