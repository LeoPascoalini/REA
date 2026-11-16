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


MARGEM_K, MARGEM_N = 2, 3       # iguais às do src/patch.s
K_PADRAO, N_PADRAO = 7, 8


def cfg(n):
    """K/N salvos na RAM com bateria."""
    s = n.mem._subject
    return s[0x6002], s[0x6003]


def sombra(n):
    """S salvo na RAM com bateria e S em uso."""
    s = n.mem._subject
    return s[0x6005], s[0x07EB]


def nv(K, N, S):
    """Conteúdo da RAM com bateria com K/N/S gravados (versão 3, marca 'DJ')."""
    return bytes([0x44, 0x4A, K, N, K ^ N ^ S ^ 0x5A, S] + [0] * 10)


def escurece(c, S):
    """Mesma conta da rotina Escurece do patch."""
    if c & 0x0F >= 0x0D:
        return 0x0F
    r = c - (0x40 - 0x10 * S)
    return r if r >= 0 else c & 0x0F


def em_uso(n):
    """K/N em uso (cópia na RAM interna)."""
    s = n.mem._subject
    return s[0x07E1], s[0x07E2]


def esperado_cal(L, H=2):
    K = L + H + MARGEM_K
    return K, L + MARGEM_N


def boot(rom, prg_ram=None, sem_nvram=False):
    n = NES(rom, prg_ram, sem_nvram)
    n.rodar_quadros(60)
    return n


def ir_para_modo(n, modo):
    while n.mem._subject[0x5FE] != modo:
        n.apertar(["SELECT"], quadros=8, soltar=8)


def calibrar(n, L, H=2, mira=(128, 120), luz_sempre=False):
    ir_para_modo(n, 3)
    n.mira, n.L, n.H, n.luz_sempre = mira, L, H, luz_sempre
    n.apertar(["START"], quadros=8, soltar=8)
    n.rodar_quadros(900)
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


PAL_JOGO = {0: bytes.fromhex("2107290A2130290A210F2918210F3016"),     # lista 2 ($E55B)
            2: bytes.fromhex("2C2919092C07291A2C0F29102C0F3016")}     # lista 3 ($E57F)


def esperar_voando(n, slots, limite=2500):
    s = n.mem._subject
    for _ in range(limite):
        n.rodar_quadros(1)
        if any(s[b] and s[b + 1] == 3 for b in slots):
            return True
    return False


def partida(n, modo, S, alvos):
    """Joga uma partida (n já no título): para cada alvo (1 = pato 1, 2 = pato 2, None = céu),
    espera os patos voarem, atira e confere acerto/erro, a tela durante o tiro e a volta ao normal."""
    s = n.mem._subject
    n.L, n.H = 3, 2
    acertos = []
    n.mem.subscribe_to_write([0x0301, 0x0351], lambda a, v: acertos.append(1 if a == 0x0301 else 2) if v == 4 else None)
    ir_para_modo(n, modo)
    n.apertar(["START"], quadros=8, soltar=8)
    pal_normal = PAL_JOGO[2 if modo == 2 else 0]
    for alvo in alvos:
        slots = (0x0300, 0x0350) if alvo is None else ((0x0300,) if alvo == 1 else (0x0350,))
        if not esperar_voando(n, slots):
            caso(f"modo {modo}: alvo voando", False, f"quadro {n.quadro}")
            return
        if alvo is None:
            n.mira = (128, 30)                                                  # céu
        else:
            b = 0x0300 if alvo == 1 else 0x0350
            n.mira = lambda nes, b=b: (nes.mem._subject[b + 3], nes.mem._subject[b + 2])   # segue o alvo
        antes = len(acertos)
        ini = n.quadro
        n.gatilho = lambda q: ini + 2 <= q < ini + 5
        telas = []
        for _ in range(80):
            n.rodar_quadros(1)
            telas.append((n.mask, bytes(n.pal[:16])))
        n.gatilho = lambda q: False
        novos = acertos[antes:]
        nome = "céu" if alvo is None else f"alvo {alvo}"
        if alvo is None:
            caso(f"modo {modo}, S={S}: mira no {nome} -> erro", not novos, f"acertos {novos}")
        else:
            caso(f"modo {modo}, S={S}: mira no {nome} -> acerto", novos[:1] == [alvo], f"acertos {novos}")
        if S:
            escuro = bytes(escurece(c, S) for c in pal_normal)
            viu = any(m & 0x08 and p == escuro for m, p in telas)
            caso(f"modo {modo}, S={S}: cenário escurecido durante o tiro", viu, f"esperado {escuro.hex(' ')}")
        else:
            preta = any(m & 0x18 in (0x00, 0x10) for m, _ in telas)
            escurecida = any(m & 0x08 and p[0] != pal_normal[0] and p != bytes([0x0F]) * 16 for m, p in telas)
            caso(f"modo {modo}, S=0: tela preta durante o tiro (sem sombra)", preta and not escurecida)
        n.rodar_quadros(90)
        caso(f"modo {modo}, S={S}: depois do tiro, cores e tela normais",
             bytes(n.pal[1:16]) == pal_normal[1:] and n.mask & 0x18 == 0x18 and s[0x1F] == modo,
             f"pal {bytes(n.pal[:16]).hex(' ')} mask {n.mask:02X}")


def main():
    rom = Path(sys.argv[1]).read_bytes()

    print("Tela de título:")
    n = boot(rom)
    caso("linha 23 mostra CALIBRATION", linha(n, 23).strip() == "CALIBRATION", f"'{linha(n, 23).strip()}'")
    caso("linha 24 mostra TOP SCORE no Game A", "TOP SCORE = 12000" in linha(n, 24))
    caso("valores padrão na RAM extra vazia", cfg(n) == (K_PADRAO, N_PADRAO), f"K,N={cfg(n)}")

    print("\nSelect passa pelas 4 opções:")
    esperado = [(1, 19), (2, 21), (3, 23), (0, 17)]
    for modo, lin in esperado:
        n.apertar(["SELECT"], quadros=8, soltar=8)
        caso(f"modo {modo}: cursor na linha {lin}", n.mem._subject[0x5FE] == modo and linha(n, lin).strip().startswith(">"))
        if modo == 3:
            caso("modo 3: linha 24 mostra K, N e S", linha(n, 24).strip() == "K=07  N=08 S=0", f"'{linha(n, 24).strip()}'")
        if modo == 0:
            caso("de volta ao Game A: TOP SCORE restaurado", "TOP SCORE = 12000" in linha(n, 24))

    print("\nAjuste manual (modo 3):")
    ir_para_modo(n, 3)
    passos = [("CIMA", (8, 8)), ("CIMA", (9, 8)), ("BAIXO", (8, 8)), ("DIR", (8, 9)),
              ("ESQ", (8, 8)), ("ESQ", (8, 7))]
    for b, ok in passos:
        n.apertar([b], quadros=8, soltar=8)
        caso(f"{b:5s} -> K,N = {ok}", cfg(n) == ok, f"obtido {cfg(n)}, tela '{linha(n, 24).strip()}'")
    for _ in range(9):
        n.apertar(["BAIXO"], quadros=8, soltar=8)
    caso("K não desce abaixo de 1", cfg(n)[0] == 1, f"{cfg(n)}")
    for _ in range(9):
        n.apertar(["ESQ"], quadros=8, soltar=8)
    caso("N não desce abaixo de 2", cfg(n)[1] == 2, f"{cfg(n)}")
    n.apertar(["DIR"], quadros=8, soltar=8)
    for esperado_s in (1, 2, 3, 0, 1):
        n.apertar(["A"], quadros=8, soltar=8)
        caso(f"A -> S = {esperado_s}", sombra(n) == (esperado_s, esperado_s) and linha(n, 24).strip().endswith(f"S={esperado_s}"),
             f"{sombra(n)} / '{linha(n, 24).strip()}'")

    print("\nRAM com bateria:")
    salvo = bytes(n.mem._subject[0x6000:0x6010])
    n2 = boot(rom, salvo)
    ir_para_modo(n2, 3)
    caso("valores voltam depois de desligar/ligar", cfg(n2) == cfg(n), f"{cfg(n2)} / tela '{linha(n2, 24).strip()}'")
    caso("S volta depois de desligar/ligar", sombra(n2) == sombra(n) == (1, 1), f"{sombra(n2)}")
    for marca, nome in ((0x48, "1 (DH)"), (0x49, "2 (DI)")):
        antigo = bytes([0x44, marca, 7, 10, 7 ^ 10 ^ 0x5A] + [0] * 11)
        n4 = boot(rom, antigo)
        caso(f"save da versão {nome} volta ao padrão", cfg(n4) == (K_PADRAO, N_PADRAO) and sombra(n4) == (0, 0),
             f"{cfg(n4)} S={sombra(n4)}")
    lixo = bytes([0xA7, 0x13, 0x00, 0xFF, 0x42] + [0x55] * 11)
    n3 = boot(rom, lixo)
    caso("RAM com lixo vira o padrão 7/8", cfg(n3) == (K_PADRAO, N_PADRAO), f"{cfg(n3)}")

    print("\nCalibração automática (H = 2 quadros de 'segura'):")
    for L in (0, 2, 3, 5, 8):
        n = boot(rom)
        calibrar(n, L)
        K, N = esperado_cal(L)
        s = n.mem._subject
        caso(f"atraso {L}: K={K} N={N}", cfg(n) == (K, N) and em_uso(n) == (K, N),
             f"obtido {cfg(n)} (sobe={s[0x07E5]}, desce={s[0x07E6]})")
        caso(f"atraso {L}: tela de título restaurada, S=2", tela_titulo_ok(n) and sombra(n) == (2, 2), f"S={sombra(n)}")
    n = boot(rom)
    antes = cfg(n)
    calibrar(n, 3, mira=None)
    caso("pistola fora da TV: não muda nada", cfg(n) == antes and tela_titulo_ok(n), f"{cfg(n)}")
    n = boot(rom)
    calibrar(n, 3, luz_sempre=True)
    caso("sensor sempre aceso: não muda nada", cfg(n) == antes and tela_titulo_ok(n), f"{cfg(n)}")

    print("\nTeste de sombra com sensores de sensibilidades diferentes:")
    for linha_clara, S_esp, desc in ((1, 1, "vê $1x como claro"), (0, 0, "vê até $0x como claro")):
        n = boot(rom)
        n.linha_clara = linha_clara
        calibrar(n, 3)
        caso(f"sensor que {desc} -> S={S_esp}", sombra(n) == (S_esp, S_esp) and cfg(n) == esperado_cal(3),
             f"S={sombra(n)} K,N={cfg(n)}")

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
    n.rodar_quadros(900)
    caso("tiro na tela com CALIBRATION -> calibra", cfg(n) == esperado_cal(3) and sombra(n) == (2, 2) and tela_titulo_ok(n),
         f"{cfg(n)} S={sombra(n)}")

    print("\nTítulo parado no modo 3 (procura demonstração automática):")
    n.mira = None
    n.rodar_quadros(1800)
    s = n.mem._subject
    caso("30 s parado: continua no título, modo 3", s[0x24] == 1 and s[0x5FE] == 3 and tela_titulo_ok(n),
         f"$24={s[0x24]} modo={s[0x5FE]}")

    print("\nPartida do Game A depois da calibração (atraso 3, K=%d N=%d, S=2):" % esperado_cal(3))
    partida(n, 0, 2, alvos=(1, None))

    print("\nPartida do Game B com S=1 (mira no pato 2, depois no céu):")
    partida(boot(rom, nv(7, 6, 1)), 1, 1, alvos=(2, None))

    print("\nPartida do Game C com S=2 (mira no prato 1, depois no céu):")
    partida(boot(rom, nv(7, 6, 2)), 2, 2, alvos=(1, None))

    print("\nPartida do Game A com S=0 (tela preta, como antes):")
    partida(boot(rom, nv(7, 6, 0)), 0, 0, alvos=(1,))

    print("\nSem RAM com bateria (emulador/cartucho que ignora $6000):")
    n = boot(rom, sem_nvram=True)
    caso("usa os valores padrão", em_uso(n) == (K_PADRAO, N_PADRAO), f"{em_uso(n)}")
    ir_para_modo(n, 3)
    caso("tela mostra K=07  N=08 S=0", linha(n, 24).strip() == "K=07  N=08 S=0", f"'{linha(n, 24).strip()}'")
    n.apertar(["CIMA"], quadros=8, soltar=8)
    caso("ajuste manual vale na sessão", em_uso(n) == (8, 8), f"{em_uso(n)} / '{linha(n, 24).strip()}'")
    calibrar(n, 5)
    caso("calibração termina e vale na sessão", em_uso(n) == esperado_cal(5) and tela_titulo_ok(n),
         f"{em_uso(n)}, esperado {esperado_cal(5)}")
    n.rodar_quadros(120)
    caso("valor calibrado continua depois de 2 s no título", em_uso(n) == esperado_cal(5), f"{em_uso(n)}")

    print(f"\n{'TUDO OK' if not falhas else f'{falhas} FALHA(S)'}")
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()
