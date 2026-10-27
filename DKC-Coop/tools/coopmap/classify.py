"""Classify the player-dependent sites (sites_cls.json) for COOP_MAP.md.

Categories:
  T  toque: "did a Kong touch this?"            -> either Kong (OR)
  A  alvo: "where is the player?" (aim/trigger)  -> nearest Kong
  C  acao: acts on the player that interacted     -> the Kong that touched it
  L  lider: single decision for the game          -> the leader (stable)
  R  roteiro: scripted sequence                   -> cartridge (leader+follower)
  B  ambos: system effect applied to the player   -> apply to both Kongs
  P  por Kong: the Kong's own state ($84 = self)  -> already per Kong
  G  global: game flags, modes, menus, debug      -> unchanged
"""
import csv
import json
import sys

d = json.load(open(sys.argv[1]))

# Manual classification of every "which slot is the player" call outside the
# Kongs' own code (read one by one), keyed by containing label.
SLOT = {
    "CODE_8083A1": ("R", "inicio de area: poe o animal devolvido no jogador ($0512,y)"),
    "CODE_808485": ("R", "inicio de area: parceiro posicionado no jogador"),
    "CODE_8086B1": ("R", "inicio de area: rotina de entrada do jogador por EntranceID"),
    "CODE_808787": ("R", "entrada roteirizada: parceiro com a velocidade do jogador"),
    "CODE_80881E": ("R", "entrada roteirizada: parceiro posto atras do jogador"),
    "CODE_808F28": ("B", "limite de X do jogador numa fase (B080)"),
    "CODE_809BEC": ("L", "camera segue o jogador"),
    "CODE_809E32": ("L", "camera: ajuste inicial no jogador"),
    "CODE_80C263": ("B", "rotina por quadro do tipo de fase aplicada ao jogador"),
    "CODE_80C47B": ("B", "rotina por quadro do tipo de fase aplicada ao jogador"),
    "CODE_80C501": ("B", "rotina por quadro do tipo de fase (agua) aplicada ao jogador"),
    "CODE_B68000": ("C", "corda balancante: agarrar (so o jogador)"),
    "CODE_B68406": ("R", "fichas de animal: poe o jogador no estado do bonus"),
    "CODE_B68574": ("L", "fichas de animal: contador por jogador ($1703,y)"),
    "CODE_B694F2": ("A", "Mini-Necky vira para o jogador"),
    "CODE_B6970A": ("A", "barril de inimigos: dispara com o jogador perto"),
    "CODE_B69CD6": ("C", "carrinho: estado do jogador"),
    "CODE_B69F36": ("C", "carrinho: esconde o parceiro ($0C) ao embarcar"),
    "CODE_B69FD9": ("C", "carrinho: categoria do jogador"),
    "CODE_B6A1AD": ("C", "carrinho: jogador caindo nele embarca"),
    "CODE_B6A6D3": ("C", "carrinho: jogador morto/caindo"),
    "CODE_B6AA85": ("A", "Croctopus: gatilho pela posicao do jogador"),
    "CODE_B6AC23": ("A", "plataforma-guia: ativa com o jogador perto"),
    "CODE_B6AD1E": ("L", "plataforma-guia: foco de camera ($1E29) com jogador perto"),
    "CODE_B6AE2F": ("L", "plataforma-guia: modo de camera ($1E2B) pela posicao"),
    "CODE_B6AE7E": ("C", "plataforma-guia: jogador em cima dela"),
    "CODE_B6AF1A": ("A", "plataforma-guia: some com o jogador longe"),
    "CODE_B6BBDB": ("L", "objeto de camera"),
    "CODE_B6C3C1": ("R", "porta de saida subaquatica: estado do jogador"),
    "CODE_B6C3EB": ("R", "porta de saida subaquatica: jogador passou"),
    "CODE_B6C425": ("R", "porta de saida: estado do jogador"),
    "CODE_B6C45C": ("R", "porta de saida: jogador aperta cima na porta"),
    "CODE_B6C522": ("R", "entrada/parede: jogador alinhado"),
    "CODE_B6C573": ("L", "entrada: destino de volta por jogador ($1705,y)"),
    "CODE_B6C599": ("R", "entrada: jogador entra (estado $1F)"),
    "CODE_B6C694": ("R", "entrada: jogador entra"),
    "CODE_B6CA49": ("A", "minigame: posiciona item no jogador"),
    "CODE_B6CEAE": ("A", "minigame: jogador no chao"),
    "CODE_B6D6BC": ("A", "item do minigame segue o jogador"),
    "CODE_B6D71C": ("A", "item do minigame perto do jogador"),
    "CODE_B6DB9B": ("A", "chefe: altura do jogador"),
    "CODE_B6DC6D": ("A", "chefe: X do jogador"),
    "CODE_B6E109": ("A", "chefe vira para o jogador"),
    "CODE_B6E609": ("A", "chefe"),
    "CODE_B6E648": ("A", "chefe: distancia ao jogador"),
    "CODE_B6EAAA": ("R", "chefe: cena que vira o jogador"),
    "CODE_B6F3F7": ("C", "barril-canhao: poe o jogador dentro ($48)"),
    "CODE_B6F452": ("C", "barril-canhao: parceiro vira seguidor"),
    "CODE_B6F54F": ("A", "Gnawty da mo: gatilho pela posicao"),
    "CODE_B6F5EF": ("L", "Squawks acompanha o jogador"),
    "CODE_B6F76F": ("R", "checkpoint: estado do jogador"),
    "CODE_B6F7B0": ("R", "checkpoint: poe o jogador no barril"),
    "CODE_B6F983": ("R", "tempo esgotado: fim da fase"),
    "CODE_B6FB74": ("A", "chefe: distancia"),
    "CODE_B6FBC7": ("R", "banana gigante: vitoria do jogador"),
    "CODE_B6FC0A": ("R", "banana gigante: posicao"),
    "CODE_B88383": ("L", "transicao: le destino do jogador ($1705,y)"),
    "CODE_B883CD": ("L", "transicao: le destino do jogador"),
    "CODE_B88408": ("L", "transicao: devolve o animal ao jogador ($0512,y)"),
    "CODE_B88429": ("L", "transicao: guarda o animal do jogador"),
    "CODE_B88445": ("L", "transicao: le destino do jogador"),
    "CODE_B89DE7": ("G", "depuracao (mostra variaveis)"),
    "CODE_BCB872": ("R", "parceiro volta a seguir"),
    "CODE_BCB864": ("R", "parceiro volta a seguir (estado 2)"),
    "CODE_FED58F": ("A", "inimigo vira para o jogador"),
    "CODE_BF92E5": ("R", "porta: esconde os Kongs e o animal do jogador (passageiro nao)"),
    "CODE_BF9EBB": ("L", "entrada de bonus: guarda animal e bananas do jogador p/ devolver"),
    "CODE_BCB99D": ("L", "registro de progresso por jogador"),
    "CODE_BED45E": ("G", "som do Kong preso no barril DK"),
    "CODE_BED58F": ("A", "inimigo vira para o jogador"),
    "CODE_BED652": ("A", "inimigo: distancia"),
    "CODE_BEDDF5": ("A", "Manky Kong vira para o jogador"),
    "CODE_BEE5C0": ("L", "Squawks vira com o jogador"),
    "CODE_BEE687": ("A", "inimigo corre na direcao do jogador"),
    "CODE_BEE80A": ("A", "inimigo vira para o jogador"),
    "CODE_BF8091": ("R", "laco de sprites congelado: so o jogador anda"),
    "CODE_BF80C1": ("R", "laco de sprites congelado: todos menos o jogador"),
    "CODE_BF8463": ("C", "objeto carregado pelo jogador ($16F5,y)"),
    "CODE_BFC341": ("B", "rotina por quadro do sistema no jogador"),
    "CODE_BFC9DC": ("G", "barril DK: som do Kong liberado"),
    "CODE_BFCADA": ("A", "Enguarde some com o jogador longe"),
    "CODE_BFD2D6": ("C", "atingido e o jogador?"),
    "CODE_BFD3F3": ("C", "caixa do animal: jogador por cima"),
    "DKC1_NorSpr11_UnknownSprite_Main": ("R", "fim de fase: jogador passou (estado $1B)"),
    "DKC1_NorSpr12_UnknownSprite_Main": ("R", "saida para carrinho: jogador passou"),
    "CODE_BFD950": ("R", "fim de fase: destino"),
    "DKC1_NorSpr13_UnknownSprite_Main": ("R", "gatilho de fim de fase"),
    "CODE_BFE15E": ("C", "item escondido: tapa no chao do DK"),
    "CODE_BFE54F": ("C", "barril-canhao: flag do jogador"),
    "CODE_BFEC9B": ("C", "corda balancante: jogador pendurado"),
    "CODE_BFED03": ("C", "corda balancante"),
    "CODE_BFEF0C": ("C", "corda vertical"),
}

ACTIVE_ONLY_TOUCH = {"CODE_BBA574", "CODE_BBA623", "CODE_BBA64A"}


def classify(s):
    kind, lab, cls = s["kind"], s["label"], s["cls"]
    if cls == "kong" and kind in ("kong_index_84", "ridden_0512", "kong_event_1929",
                                  "flags_0579", "current_kong_056F", "touch_category_BBA58D"):
        return "P", "codigo do proprio Kong ($84 = ele mesmo)"
    if kind == "player_slot_809B9C":
        if lab == "CODE_809B9C":
            return "-", "definicao"
        return SLOT.get(lab, ("?", "revisar"))
    if kind == "touch_active_BBA574":
        return "T", "toque so no Kong ativo -> os dois (ja feito)"
    if kind == "touch_other_BBA6xx":
        if "BBA64A" in s["code"] or "BBA623" in s["code"]:
            return "T", "toque so no Kong ativo (pneus, tambores...) -> os dois"
        if "BBA6E" in s["code"] or "BBA6F" in s["code"]:
            return "G", "depuracao (movimento livre)"
        return "T", "varredura de plataforma (ja pega os dois)"
    if kind == "touch_category_BBA58D":
        return "T", "toque por categoria (ja pega os dois)"
    if kind == "active_slot_BBA564":
        return "T", "base dos toques so no ativo"
    if kind == "bonus_return_1705":
        return "L", "destino de volta por jogador (compartilhado)"
    if kind in ("flags_0579", "kong_event_1929"):
        return "G", "sinalizador do jogo (vale para os dois)"
    if kind in ("game_mode_42", "player_number_44", "pads"):
        return "G", "modo/jogador atual/controles (Team: lider)"
    if kind == "current_kong_056F":
        return "L", "Kong atual = lider"
    if kind == "ridden_0512":
        return ("C" if cls == "sprite" else "R"), "montaria do jogador"
    if kind == "kong_index_84":
        return ("C" if cls == "sprite" else "R"), "tabela por Kong usada por objeto/sistema"
    return "?", "revisar"


rows = []
for n, s in enumerate(d, 1):
    cat, note = classify(s)
    owner = ", ".join(m.replace("DKC1_", "").replace("_Main", "") for m in s["mains"][:3])
    if not owner:
        owner = "sistema: " + ", ".join(s["roots"][:2])
    rows.append([n, s["kind"], s["label"], s["line"], owner, cat, note])

with open(sys.argv[2], "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["id", "tipo", "rotina", "linha_disasm_v1.0", "dono", "categoria", "nota"])
    w.writerows(rows)

from collections import Counter
c = Counter((r[1], r[5]) for r in rows)
cats = "TACLRBPG?-"
print("tipo".ljust(24), " ".join(cats))
for k in sorted({r[1] for r in rows}):
    print(k.ljust(24), " ".join(str(c[(k, x)]).rjust(1) for x in cats))
print("total", Counter(r[5] for r in rows))
