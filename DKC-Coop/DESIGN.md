# DKC Co-op — design

Port nativo de Donkey Kong Country (SNES, USA **v1.2**, dump do cartucho do dono) com co-op
simultâneo para 2 jogadores. Base: [DKC1Recomp](https://github.com/elliotttate/DKC1Recomp) +
[snesrecomp](https://github.com/mstan/snesrecomp). Uso pessoal; ROM e código gerado ficam fora do Git.

ROM: `Donkey Kong Country (U) (V1.2) [!].smc` — HiROM FastROM, 4 MB, SRAM 2 KB, sem chip extra,
CRC32 `762af827`, SHA-1 `cd606e77ab2034438e06891cd2d067dad69b4d1a`.

## Regras do modo 2P

| # | Regra | Comparação com o original |
|---|---|---|
| 0 | Com dois Kongs em jogo, o controle 1 comanda um Kong e o controle 2 o outro. Nenhum Kong pode sair da área da tela; a câmera acompanha os dois. | No original o segundo Kong é um seguidor que repete os comandos do líder. |
| 1 | Kong que leva dano sai de cena; o jogador dele fica em espera até o outro pegar um barril DK, que traz o Kong de volta para o jogador em espera. | Igual ao original, mas agora define quem controla quem. |
| 2 | Os Kongs colidem entre si: um pode ficar em pé em cima do outro. | Novo. |
| 3 | ~~"Levantar e arremessar o parceiro"~~ — **cancelada pelo usuário em 2026-10-15**. | Não existe no DKC1. |
| 4 | Kong de baixo não pula com o outro em cima. | Novo; depende da regra 2. |
| 5 | Vidas compartilhadas; perder os dois Kongs custa uma vida. | Igual ao original. |
| 6 | Cada jogador controla um Kong diferente: um é o Donkey (maior) e o outro o Diddy (menor). Padrão: J1 = Donkey, J2 = Diddy; dá para inverter nas configurações. | Novo. |
| 8 | Troca de Kong no co-op: só com os Kongs perto (≤ 40 px na horizontal, ≤ 32 px na vertical) e os **dois** jogadores apertando A (até 30 quadros de diferença). Os jogadores trocam de Kong; os macacos ficam onde estão. Select não troca no co-op. | Original: um jogador troca a qualquer momento (A ou Select). |
| 7 | Controles configuráveis para J1 e J2 (teclado com até 2 teclas por botão + controle Xbox/XInput, analógico opcional), na janela Controles (F10) e em `dkc_controles.ini`. | Novo (feito em 2026-10-14). |

## Fases

1. Ambiente: clonar DKC1Recomp + snesrecomp, compilar a parte independente da ROM.
2. Adaptar o port à v1.2: mapa de endereços v1.0 → v1.2 via desmontagem byte-exata da v1.0
   + busca por padrão de bytes; revisão manual das funções alteradas.
3. Engenharia reversa: estrutura dos Kongs na RAM, IA do seguidor, leitura dos controles, câmera.
4. Co-op básico: regra 0.
5. Co-op completo: regras 1–5.

## Questões em aberto

- Animais (Rambi, Enguarde, Expresso, Winky, Squawks): quem monta, o que acontece com o outro Kong.
- Fases de água, carrinho de mina e barris-canhão com dois Kongs.
- Troca de Kong (Select) no modo 2P: desativar ou trocar os controles.

## Diário

### 2026-10-14 — fase 1 e medição da fase 2

Estrutura local (fora do Git do DKC1Recomp):

```
DKC-Coop/
  DKC1Recomp/      clone do port (+ submódulo snesrecomp)
  dkc1-disasm/     desmontagem Yoshifanatic1 (v1.0, GPL-3)
  framework/       SNES-ROM-Framework (tag V1.2.0 usada)
  asm10/           Global (framework V1.2.0) + DKC1 com assets extraídos da v1.2
  tools/           asar 1.91, extract_assets.py
```

- `tools/extract_assets.py` extrai os 3.617 assets da ROM v1.2 usando a tabela de endereços da v1.0
  (corrige o bug de sobreposição `Layer2_IntroSky` → `DATA_EEFE9D`).
- A desmontagem monta sem erros (`asm10/DKC1/DKC1_U1_rebuilt.sfc`): código v1.0 + dados da v1.2.
- Alinhamento por k-mers de 16 bytes, v1.0 reconstruída × v1.2 (porcentagem de bytes mapeados por banco de código):

| banco | mapeado | mesmo endereço | deslocamentos principais |
|---|---|---|---|
| 80 | 89% | 50% | −77, +14, −79, +23 |
| 81 | 99.6% | 96% | +30 |
| 8A | 88% | 82% | +5 |
| B5 | 87% | 59% | −4 |
| B6 | 91% | 56% | +53, +48, +26 |
| B8 | 93% | 74% | +290…+307 |
| B9 | 99.8% | 99.8% | — |
| BB | 99.4% | 99.4% | — |
| BC | 93% | 12% | dados realocados para outros bancos + deslocamentos |
| BD | 98% | 89% | +34 |
| BE | 85% | 54% | +7, +4 |
| BF | 87% | 50% | +73, +121 |

Conclusão: a v1.2 é uma revisão de verdade — código inserido/removido em quase todos os bancos
(o resto do banco desloca), e parte dos dados do banco BC mudou de lugar. 1–15% dos bytes de cada
banco de código não alinham automaticamente (mudanças reais ou tabelas densas de ponteiros).

Próximo passo (fase 2): ferramenta de tradução de endereços v1.0→v1.2 a partir do alinhamento;
traduzir `recomp/*.cfg` e `symbols.toml`; revisar à mão as regiões não alinhadas; gerar com
snesrecomp na v1.2 e iterar até a validação passar.

### 2026-10-14 — fase 2: port rodando na v1.2

Ferramentas (`tools/`): `addrmap.py` (alinhamento por banco: âncoras únicas → cadeia monotônica →
refinamento recursivo, blocos movidos, diff byte a byte em regiões pequenas), `dis65816.py`
(desmontador 65816 com rastreio de M/X), `resolve_masked.py` (busca de instruções com operandos
de endereço mascarados), `translate_cfg.py` (+ `work/overrides.json`, `work/manual_v12.cfg`).

Resultado da tradução dos `recomp/*.cfg` (≈4.800 diretivas): todas mapeadas; ~100 funções com
corpo alterado (início/fim mapeados). Mudanças da v1.2 identificadas:

- Otimizações em massa: `JSR x/RTS`→`JMP x`, `JSL x/RTL`→`JML x`, `LDA #0/STA`→`STZ`, RTS/RTL
  mortos removidos — origem da maior parte dos deslocamentos.
- Câmera vertical reescrita: `80:C2D4` (JSR) virou `B8:8000` (JSL, 304 bytes, código novo no
  início do banco B8) + trava `STZ $1A61/$1A63` em `80:C2F8`.
- Banco BC: testes `$0535 == 2` removidos de duas rotinas de colisão; rotina nova `BC:BCCF`.
- Fim do banco 80 (desenho de números): grupos reordenados, código morto da v1.0 realocado,
  rotina nova sem referências em `80:FEA7` (usa `$7F2094`).
- Dados do banco BC (`BC:0000-7FFF`) reorganizados.

Host (`DKC1Recomp`, branch local `v12-coop`):
- `scripts/generate_snesrecomp.py` aceita o SHA-256 da v1.2; cfgs em `recomp_v12/`.
- `runner/verified_rom.c` aceita a v1.2.
- `runner/dkc1_game.c`: vetor de NMI lido do cabeçalho da ROM (v1.0 `$A968`, v1.2 `$A976` — era
  a causa do travamento na inicialização); hooks de widescreen do interpretador com tabela por revisão.
- `build_host_v12.bat` (build completo, ~10 min) e `relink_v12.bat` (incremental).

Validação: rota `recipes/route_jungle.dks` (boot → intro → menus → mapa → Jungle Hijinxs, 8.179
quadros). Recompilado × interpretador (`SNESRECOMP_EXECUTION_MODE=lle`): WRAM, VRAM e imagem
idênticas nos checkpoints `level_entry` (quadro 7370) e `camera_0200` (quadro 8119).

Pendências da fase 2: cobertura além da primeira fase (mais rotas: água, carrinho, barris,
animais, chefes); widescreen da v1.2; regenerar `symbols.toml` com endereços da v1.2.

### 2026-10-14 — controles dos 2 jogadores

- `runner/dkc1_controls.c/.h`: bindings por jogador (2 teclas + 1 botão de controle por botão do
  SNES), controle XInput 0–3 por jogador (carregado dinamicamente), analógico esquerdo opcional,
  INI ao lado do executável (`dkc_controles.ini`), janela de configuração modal (menu
  Controles / F10) com captura de tecla/botão, "Padrões", "Salvar", "Cancelar".
- Escolha do Kong do J1 (o J2 recebe sempre o outro) — usada pelo co-op na fase 4.
- `win32_host.c`: `PollInput` agora entrega os dois controles (bits 0–11 e 12–23).
- Padrões: J1 = setas, Z (B), X (Y), S (A), A (X), Q/W (L/R), Enter, Shift direito + controle 1;
  J2 = teclado numérico (8/4/5/6, 0=B, 1=Y, 2=A, 3=X, 7/9=L/R, +/−) ou I/J/K/L + N/B/M + controle 2.

### 2026-10-14 — fase 4: co-op básico jogável

`runner/dkc1_coop.c` (+ `scripts/apply_dkc1_coop_wrappers.py`, chamado por
`generate_snesrecomp.py` quando o cfg é `recomp_v12`): as definições geradas de
`DKC1_NorSpr01_DonkeyKong_Main`, `DKC1_NorSpr02_DiddyKong_Main` e `CODE_809BEC` (câmera, v1.2
`80:9BFA`) viram `*_original`; os invólucros em C:

- Estados do Kong classificados (dispatch BF:84C5): seguidor `02 05 06 23 33 34 35 36 43`
  (marcam `$1271` bit 15), jogador = os que chamam `Player_ProcessInput`; o resto
  (barris, morte, animais, cenas) fica com o cartucho.
- Kong "secundário" (o que o cartucho trata como seguidor) sai do estado de seguidor para o
  estado 1 e roda a lógica de jogador com o contexto trocado: `$056F`, bloco `$1811–$192F`
  (histórico/cópias do líder) e palavras de controle `$0500–$0506` (cada Kong lê o controle do
  dono). Yield de fim de quadro tratado (restaura na próxima entrada).
- Botão A (trocar Kong) mascarado nos dois controles durante o co-op.
- Câmera: alvo = ponto médio dos dois Kongs (posição apresentada ao `CODE_809BEC`),
  exceto com foco forçado (`$1E29`). Os dois Kongs ficam presos à tela (margem 16 px).
- UI: janela Controles (F10) com "Modo cooperativo" e quem é Donkey/Diddy; INI
  `[General] coop=1` (padrão ligado). `DKC1_COOP=1`/`DKC1_COOP_P1=diddy` para testes;
  `DKC1_COOP_TRACE=<arquivo>` grava os dois slots por quadro.

Testes (headless, `recipes/coop_full_test.dks`: rota até os dois Kongs + controles separados):
J2 → Diddy anda sozinho; J1 → Donkey anda sozinho; os dois juntos; câmera no meio; limite de
tela segura o par. Regressão: com co-op desligado, `route_jungle` dá o mesmo `frame_sha256`
de antes (`f1ff576f…`).

Limitações conhecidas (fase 5): a câmera do jogo "olha à frente" na direção do Kong ativo, então
o arrasto pela borda começa antes da largura total da tela; dano/morte do Kong secundário, colisão
entre os Kongs, arremesso, animais, barris e carrinho ainda não tratados.

### 2026-10-14 — correções após teste do usuário

- A troca de Kong é disparada por **A e Select** (`Player_ProcessInput` → `BF:BF8E`); só o A
  estava bloqueado. Agora os dois são removidos durante o co-op: na entrada do host
  (`Dkc1CoopFilterHostInput`, antes de `RtlRunFrame`) e nas palavras de controle entregues a cada
  Kong. Decisão: **sem troca no co-op** (cada jogador fica com o seu Kong).
- "Um macaco ficou sem controle depois de inverter": consequência da troca (o antigo líder caía num
  estado de transição e o co-op se desligava). Testes `recipes/coop_swap_test.dks` com
  `DKC1_COOP_P1=donkey` e `=diddy`: sem troca, cada controle move o Kong certo nas duas configurações.

### 2026-10-14 — troca de Kong por proximidade (regra 8)

Pedido do usuário: permitir a troca, mas só de perto e com os dois apertando A.
`Dkc1CoopFilterHostInput`: detecta o aperto de A de cada controle; se os dois apertarem até 30
quadros um do outro e os Kongs estiverem a ≤ 40 px (X) / ≤ 32 px (Y), troca o dono dos Kongs
(`s_p1_kong`). A e Select nunca chegam à troca do cartucho no co-op. Teste
`recipes/coop_swap_near_test.dks`: longe + dois A → não troca; perto + só J1 → não troca;
perto + dois A → troca; depois da troca o controle 1 move o Diddy e o controle 2 o Donkey.
Ainda sem efeito sonoro/visual na troca.

### 2026-10-14 — teclado numérico e troca (2º teste do usuário)

- Bug: com NumLock desligado o Windows envia o teclado numérico como setas/navegação
  (Num8 → VK_UP, Num2 → VK_DOWN…), então o J2 (numérico) comandava o Kong do J1 (setas) e o
  A do J2 (Num2) virava "baixo" — por isso a troca não funcionava no teste real.
- Correção: `dkc1_controls.c` mantém o estado das teclas a partir das mensagens da janela
  (`Dkc1ControlsKeyEvent`) e usa o bit "extended" para separar o bloco de setas do numérico
  (`Dkc1ControlsTranslateKey`); Shift/Ctrl/Alt esquerdo/direito também. Teclas soltas fora da
  janela são reconciliadas com o estado físico; foco perdido limpa tudo. A janela de Controles
  captura teclas com a mesma tradução. Teste unitário `build/keytest`: 13/13.
- Alcance da troca: 48 px (X). Título da janela mostra o status do co-op (ATIVO, quem é o J1,
  número de trocas).

### 2026-10-14 — troca com a animação original + câmera centralizada

- A troca de co-op (regra 8) agora dispara a troca do próprio cartucho: no quadro da troca o
  invólucro entrega um Select só ao Kong ativo; o cartucho roda a animação original (pose `$11`,
  depois os Kongs passam um pelo outro em `$03/$04`, com o som de troca) e muda `$056F`. Durante a
  animação o co-op solta os dois Kongs (`s_swap_anim`) e volta quando o novo líder está num estado
  de jogador e o outro num de seguidor (limite 240 quadros). Os jogadores trocam de Kong quando
  `$056F` muda; se o cartucho recusar (8 quadros), a troca vira só de controle.
- Câmera: alvo = X − $80 + `$1A69` (look-ahead) − vel.X/~11 (`CODE_809CD0`). No co-op o invólucro
  zera `$1A69` e a vel. X apresentados à câmera → o ponto médio fica centralizado (antes um Kong
  ficava preso na borda mesmo com os dois perto).
- Testes: `recipes/coop_swap_anim_test.dks` — longe não troca, só J1 não troca, os dois perto trocam
  (posições invertidas, `$056F`=2, animação visível nos quadros), depois cada controle move o Kong
  certo. Regressão sem co-op: `frame_sha256` inalterado.

### 2026-10-14 — pausa travada (3º teste do usuário)

- Causa (código 80:A2A0, v1.0): o "jogador da vez" (`$050E`/`$0510`, lido pela pausa em 80:9AFF) é,
  no modo **2 Player Team** (`$42 = 1`), o controle do Kong ativo (`$056F`: Donkey → controle 1,
  Diddy → controle 2); no Contest (`$42 = 2`) é `$44`; senão, sempre o controle 1. Depois de uma troca
  no co-op o ativo é o Kong do outro jogador, então o Enter do J1 não despausava.
- Correção: `Dkc1CoopFilterHostInput` espelha o Start nos dois controles enquanto os dois Kongs estão
  em jogo — qualquer jogador pausa e despausa. Teste `recipes/coop_pause_test.dks` (modo 1 jogador):
  pausa/despausa e o Kong volta a andar.

### 2026-10-15 — 2º Kong não pegava bananas/itens (4º teste do usuário)

Causas encontradas:
1. **Pulo quebrado do Kong secundário**: ao sair do papel de seguidor ele ia para o estado 1 (ar),
   que não tem pulo e só termina num pouso — que nunca vinha, pois ele já estava no chão. Agora vai
   para o estado 0 (chão). Teste `coop_jump_test.dks`: Donkey sobe 81 px, Diddy 93 px.
2. **Bananas soltas** (banco B8, `CODE_B8B503` v1.2 `B8:B62F`) testam contra uma única caixa de
   coleta em `$C5–$CC`, escrita por cada Kong na própria atualização (vale a do último). O co-op
   guarda a caixa de cada Kong e roda a passada das bananas duas vezes (secundário, depois ativo),
   recriando o quadro de JSL e regravando os mesmos slots de OAM (sem sprites duplicados). Cada Kong
   também começa a própria atualização com a sua caixa. Teste `coop_banana_test.dks`: Diddy pega
   banana a 153 px do Donkey.
3. Itens-sprite (letras K-O-N-G etc.) e inimigos usam o sistema de colisão por categoria do banco BB
   (`BBA58D`: varre slots `$1C→$02`, categoria `$11A1`), que já funciona com os dois Kongs (ambos `C1`).
   Dano é marcado por slot (`$1595`) e tratado na atualização do próprio Kong (`BFA0F7`→`BFA191`):
   o Kong tocado leva o dano. Confirmado com quadros: o Kong atingido foi o que encostou no Kritter.
4. `Player_GetIndexOffset_Far` ($80:9B9C), quando chamada por sprites do banco B6, responde com o
   Kong mais próximo do sprite (inimigos miram em quem está perto).

Regressão sem co-op: `frame_sha256` inalterado.

### 2026-10-15 — Letras K-O-N-G não eram pegas pelo 2º Kong (5º teste do usuário)

- Correção do item 3 acima: as letras (e outros 29 pontos — caixas de animal, canhões-barril, nozes
  do Necky, barris TNT...) não usam a varredura por categoria sozinha, e sim `CODE_BBA574`
  (`BB:A574`, igual em v1.0/v1.2): varre por categoria mas **só aceita o slot `$056F*2`** — "tocou
  no Kong ativo?".
- Princípio adotado (sugestão do usuário): **os dois Kongs contam como ativos**. O co-op envolve
  `CODE_BBA574`: testa o Kong ativo como o original; se não houver colisão (carry limpo), restaura o
  `CpuState` e o quadro de JSL, apresenta o outro Kong como ativo (`$056F`) e testa de novo. O
  resultado (carry, `$88` = slot atingido, `$B8`) é o da passada que acertou; `$056F` volta ao valor
  original.
- Teste `recipes/coop_letter_test.dks`: o Donkey (ativo) para em x $30F no chão; o Diddy (secundário,
  J2) segue pulando e pega o "K" em x $3C7, y $146 (`$057F`=0808) com o Donkey ainda ativo.
- Regressão sem co-op: `frame_sha256` inalterado.

### 2026-10-15 — Regras 1, 2, 4 e 5 (regra 3 cancelada pelo usuário)

- **Regra 1 (Kong atingido sai; o jogador dele espera)**: o Kong atingido vai para o estado `$0C`
  (fora de cena), o mesmo em que o parceiro fica no começo da fase antes do barril DK. Bug achado
  (`recipes/coop_out_test.dks`): com o parceiro fora o co-op ficava inativo e o cartucho dava o
  Kong restante ao controle 1 — o J1 (dono do DK que saiu) movia o Diddy e o J2 não. Correção: em
  co-op o Kong ativo sempre recebe o controle do próprio dono, mesmo com o parceiro fora/ocupado.
  Medido: com o DK fora, J1 → Diddy parado (x $39D); J2 → Diddy anda até x $409. O barril DK traz o
  Kong de volta como seguidor, e o co-op o devolve ao dono (o mesmo caminho do `diddy_freed`).
- **Regra 5 (vidas compartilhadas)**: comportamento original — no mesmo teste, o Diddy sozinho bateu
  num inimigo e a fase reiniciou com uma vida a menos.
- **Regra 2 (um Kong em pé no outro)**: imita as plataformas-sprite (`CODE_BFEB58`). No fim do
  quadro, um Kong caindo (velocidade Y < 0) a até 16 px na horizontal e até 12 px abaixo da cabeça do
  parceiro (Y do parceiro + $22 DK / $1E Diddy) é posto no topo, com velocidade Y $FF00, `$1631`=0 e o
  bit $10 de `$12A5` ("apoiado em sprite"). O jogo o põe no estado de chão (pode andar e pular), e ele
  acompanha o deslocamento X do Kong de baixo.
- **Regra 4**: enquanto um Kong está em cima, o B (pulo) do dono do Kong de baixo é removido.
- Teste `recipes/coop_stand_test.dks`: o Diddy pula na cabeça do DK (pousa em y $CF, estado 00); o J1
  aperta pulo duas vezes e o DK não sai do chão; o DK anda 75 px e o Diddy vai junto; o Diddy pula e
  pousa de novo no DK.
- Colisão lateral (empurrar) não foi feita de propósito: prenderia os Kongs um no outro em passagens
  estreitas.
- Regressão sem co-op: `frame_sha256` inalterado; letras e bananas continuam ok.

### 2026-10-15 — Mundo congelado depois que o Kong do J2 apanhava (6º teste do usuário)

- Causa: no cartucho só o Kong **ativo** leva dano. A sequência (`BF:8D5F–8FEF`) é: o Kong atingido
  vai 0D → 09 → 0C; o parceiro vai 0E → 0A, corre até o lugar e termina **invertendo** `$056F` e
  limpando `$0579` bit 0 (mundo congelado); no modo Team (`$42`=1) passa antes pelo estado $53, que
  espera o botão do novo jogador. Com o Kong secundário atingido, a inversão deixava como "ativo" o
  Kong que tinha saído → o J1 andava, mas o jogo continuava tratando o Kong ausente como o líder e o
  mundo ficava parado.
- Correção: quando o Kong secundário entra no estado 0D durante a própria atualização (em que ele já
  está apresentado como ativo), o co-op o **mantém ativo** (com o próprio contexto); a sequência roda
  igual ao original e a inversão final entrega o jogo ao parceiro. Os estados 0D/0E deixam de contar
  como "jogáveis" para o co-op, então a sequência de dano roda sem a intervenção do co-op.
- Teste `recipes/coop_p2hit_test.dks`: o DK para em x $300, o Diddy (J2) anda até o Kritter →
  9600 Diddy 0D (ativo = 2) → 9670 DK assume (ativo = 1, `$0579`=0) → o J1 anda até x $43C, a câmera
  acompanha e os inimigos se movem.
- Regressão sem co-op: `frame_sha256` inalterado; `coop_stand_test` igual.

### 2026-10-15 — Montarias: o 2º Kong duplicava o animal (7º teste do usuário)

- Causa: além do teste do animal (`CODE_BFCC24`, só com o animal livre), o próprio Kong monta em
  qualquer sprite com o bit $08 da categoria (`$11A1`) em que cair (`CODE_BF888E`). O animal
  montado mantém esse bit. No original só o Kong ativo cai sozinho; no co-op o 2º Kong caía no Rambi
  já montado, "montava" de novo (`$0512/$0514` apontando para o mesmo animal, estado $14 e animação
  do animal montado) e virava um segundo rinoceronte.
- Correção (`RunKongOneRider`): enquanto um Kong monta um animal/carrinho (`$0512,índice`), esse
  sprite fica sem o bit $08 durante a atualização do outro Kong — um animal tem um só piloto.
- Passageiro: se o outro Kong cair nas costas de um animal de terra montado pelo parceiro (Rambi,
  Expresso, Winky; o Enguarde fica de fora, é aquático), ele fica sentado atrás do piloto (12 px
  atrás, 24 px acima dos pés do animal, olhando para o mesmo lado) e vai junto em tudo, inclusive no
  pulo. Esquerda/direita do dono dele são ignoradas enquanto está sentado; o B pula — pulando com uma
  direção ele desce do animal, pulando reto ele cai de volta no assento. O piloto controla o animal.
- Teste `recipes/coop_mount_test.dks` (rota até o Rambi: `coop_rambi_route.dks`, com o auxílio de
  teste `DKC1_COOP_TEST_GHOST=<quadro>`, desligado por padrão, que descarta os eventos de dano dos
  Kongs para a rota cega chegar longe): antes, o Diddy virava um 2º Rambi; agora só existe um Rambi
  (slot $0A, `$0512`=$0A, `$0514`=0), o Diddy fica sentado, acompanha a andada e o pulo do Rambi,
  ignora o direcional, e pula para fora segurando a direita e volta a andar.
- A "mancha" vermelha perto do Rambi nas capturas é o sprite $43 da própria fase.
- Pendente: carrinho de mina (no original os dois Kongs vão no mesmo carrinho — conferir), Enguarde,
  Squawks.
- Regressão sem co-op: `frame_sha256` inalterado; letras e "em pé no outro" iguais.
