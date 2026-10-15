# DKC1 — engenharia reversa dos Kongs (fase 3)

Fontes: desmontagem Yoshifanatic1 (v1.0, rótulos `CODE_xxxxxx`), dumps de WRAM do port v1.2,
tradução de endereços `tools/addrmap.py`. Endereços de código em v1.0 → v1.2.

## Atores e slots

- Todos os atores são *struct of arrays* em WRAM: cada campo é uma tabela de 0x34 bytes
  (26 slots × 16 bits) indexada por `X = slot` (par). Campos úteis (`RAM_Map_DKC1.asm`):
  X `$0B19`, Y `$0BC1`, vel. X `$0E89`, vel. Y `$0EF1`, ID `$0D45`, animação `$10D1`,
  pose `$0D11`, atributos OAM `$0C69` (bit `$4000` = espelhado), ordem de desenho `$0B8D`,
  **estado `$1029`**, X/Y anteriores `$0FC1`/`$0FF5`.
- **Donkey = sprite `$0001` no slot `$02`; Diddy = sprite `$0002` no slot `$04`.**
  Parceiro de um slot = `slot XOR 6`.
- `$84` = índice do Kong (0 = Donkey, 2 = Diddy) — indexa as tabelas *por Kong* em `$1699–$16FF`
  (ex.: `$16AD` animação atual, `$1699` flags, `$16CD` direção/flags, `$16E9`/`$16ED` botões
  apertados/segurados, `$16C1`/`$16C5` velocidades guardadas, `$16FD` evento pendente).
- `$82` (`NorSpr_CurrentIndex`) = slot do ator sendo processado.

## Máquina de estados do Kong

- `DKC1_NorSpr02_DiddyKong_Main` BF:849F→**BF:84A4** (`$84 = 2`) e
  `DKC1_NorSpr01_DonkeyKong_Main` BF:84A6→**BF:84AB** (`$84 = 0`) caem no mesmo despachante:
  `JMP (DATA_BF84C5, estado*2)` com 87 estados (`$1029,slot`).
- **Estado 1** BF:87F2→**BF:87FD** = Kong controlado pelo jogador
  (chama `Player_ProcessInput` com A=1).
- **Estado 2** BF:8984→**BF:898F** = Kong seguidor: consulta o estado do parceiro
  (`$1029,slot^6`: 0x25/0x26/0x29/0x2F/0x40 = casos especiais), depois
  `BFC42D` (segue o histórico), `BF8CB0` (vira de lado), `BF8A79` (copia animações especiais).

## Como o seguidor funciona (posição, não comandos)

- O líder grava um histórico circular de 32 entradas sempre que se move
  (`CODE_BFC386` BF:C386→**BF:C3D7**): X `$1815,i`, Y `$1855,i`, flags/direção `$1895,i`,
  animação `$18D5,i`; índice de escrita `$1813`, de leitura `$1811` (passo 2, máscara `$3F`).
- O seguidor (`CODE_BFC42D` BF:C42D→**BF:C486**) copia X/Y da entrada `$1811` — é um
  "fantasma" que percorre o mesmo caminho alguns quadros depois. Ele não tem física,
  colisão nem entrada própria.
- Globais do "par" usadas por isso: `$1915`, `$1917` (flags: bit0 histórico cheio, bit3 longe,
  bit4 virar, bit5…), `$1919`–`$1929` (cópias do líder: vel. X, `0F25`, `1631`, anim.).

## Entrada (controles)

- `$0500`/`$0502` segurados P1/P2, `$0504`/`$0506` recém-apertados P1/P2.
- `Player_ProcessInput` BF:B27C→**BF:B2C5**: `$44` = qual controle ler. No modo 2
  jogadores (`$42 == 1`), `$44 = ($056F & 2) >> 1` → o controle segue o **Kong ativo** (é o
  "revezamento" original). Os botões vão para `$80`/`$7E` e para as tabelas do Kong
  (`$16E9,$84` / `$16ED,$84`). Truque de código: com cheat ativo, mistura botões dos dois
  controles.

## Kong ativo e troca

- `$056F` (`Player_CurrentKong`): 1 = Donkey ativo, 2 = Diddy ativo. Slot ativo =
  `$056F * 2` (`CODE_809BA0` 80:9BA0→**80:9BAE**, usado pela câmera e afins).
- Troca (botão A / ao perder um Kong): `$056F ^= 3`, o Kong que assume vai para o estado 1,
  troca a ordem de desenho (`$0B8D`) e recupera velocidades guardadas (`$16C1`/`$16C5`).
- 23 leituras e 12 escritas de `$056F` no jogo (tabela abaixo) — são os pontos que "pensam
  num só jogador" e precisam de revisão no co-op.

## Câmera

- Inicialização em 80:9xxx usa `CODE_809BA0` (slot ativo) e grava os alvos `$1A4F`/`$1A51`
  (X/Y), `$1A4B`/`$1A4D`, `$1A5D`/`$1A5F`, `$1A61`/`$1A63`; rolagem horizontal em 80:C2BF
  e vertical em **B8:8000** (reescrita na v1.2).

## Plano técnico do co-op (fase 4)

Implementação em C sobre o port (mecanismo de *replacement*: a função gerada vira
`*_original` e uma versão escrita à mão a envolve), sem patch na ROM:

1. Modo 2P ligado e os dois Kongs presentes → o Kong do J2 roda o **estado 1** (como líder)
   em vez do estado 2. Antes de processar cada Kong, o host troca o "contexto de jogador":
   `$056F`, `$44`, as globais `$1811–$192F` e afins; depois restaura. Assim a lógica original
   (física, colisão, animação) roda para cada Kong com o seu próprio controle.
2. Câmera: alvo = ponto médio entre os dois Kongs; posição de cada Kong limitada à área visível.
3. Histórico do seguidor desativado enquanto os dois estão ativos; reativado quando volta a
   ter um só Kong (regra 1).
4. Validação com rotas gravadas e o oráculo (interpretador × recompilado).

## Questões em aberto

- Lista completa de globais "do jogador" que precisam ir para o contexto (descobrir rodando).
- Colisão Kong × inimigo / itens só para o Kong ativo? (provável: checam `$056F` ou estado 1.)
- Animais, barris-canhão, carrinho, água.

## Leituras/escritas de `$056F` (v1.0 → v1.2)

| rotina (v1.0) | v1.2 | acesso |
|---|---|---|
| CODE_808131 | 80812F | LDA.w |
| CODE_808131 | 80812F | STA.w |
| CODE_809BA0 | 809BAE | LDA.w |
| CODE_80A2A0 | 80A2AE | LDA.w |
| CODE_80C1A2 | 80C1CE | LDA.w |
| CODE_80CEBC | 80CE6F | STA.w |
| CODE_80E2FE | 80E2C4 | LDA.w |
| CODE_80E3D2 | 80E398 | LDA.w |
| CODE_80EE05 | 80EDB6 | LDA.w |
| CODE_80F52F | 80F4E0 | LDA.w |
| CODE_B69F6F | B69F7B | AND.w |
| CODE_B880E4 | B88214 | LDA.w |
| CODE_B88288 | B883B8 | STA.w |
| CODE_B884D7 | B8860A | STA.w |
| CODE_B892D0 | B89403 | STA.w |
| CODE_B89314 | B89447 | LDA.w |
| CODE_BBA564 | BBA564 | LDA.w |
| CODE_BCB927 | BCB937 | LDA.w |
| CODE_BEA795 | BEA799 | LDA.w |
| CODE_BF8E48 | BF8E58 | LDA.w |
| CODE_BF8E48 | BF8E58 | STA.w |
| CODE_BF8F16 | BF8F26 | LDA.w |
| CODE_BF8F16 | BF8F26 | STA.w |
| CODE_BF936E | BF9382 | LDA.w |
| CODE_BF936E | BF9382 | STA.w |
| CODE_BFB27C | BFB2C5 | LDA.w |
| CODE_BFBFF1 | BFC042 | LDA.w |
| CODE_BFC014 | BFC065 | STA.w |
| CODE_BFC027 | BFC078 | STA.w |
| CODE_BFC075 | BFC0C6 | LDA.w |
| CODE_BFC16E | BFC1BF | LDA.w |
| CODE_BFC17C | BFC1CD | STA.w |
| CODE_BFC183 | BFC1D4 | STA.w |
| CODE_BFC9DC | BFCA55 | LDA.w |
| CODE_BFE7B0 | BFE81D | LDA.w |
| CODE_BFE7C4 | BFE831 | LDA.w |
