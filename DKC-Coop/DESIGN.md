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

### 2026-10-15 — Montaria: pose de montado, troca de tela, travamento na entrada de área (8º teste)

- **Pose do passageiro**: ao montar, o slot do Kong piloto passa a mostrar o *animal* (poses
  $25xx–$27xx) e o slot do animal mostra o *Kong montado* (DK $058C…, Diddy $0DB0…; scripts
  BE:BE73…). O passageiro usa a pose de montado parado do próprio Kong (DK $058C / Diddy $0DB0),
  com o temporizador da pose segurado para a animação dele não trocar a pose; ao apertar B o assento
  é liberado antes, para a animação de pulo (que dá o impulso) rodar. Outras poses de montaria
  escritas fora do script não aparecem (os gráficos não vêm junto) — por isso só a parada.
- Assento a 30 px atrás do piloto: a 14 px o corpo do piloto, que se inclina para trás no pulo do
  animal, cobria o passageiro. Sentado ele fica no estado de chão (o de ar não tem pulo).
- **Troca de tela montado** (ex.: o Rambi arromba a entrada da caverna escondida da Jungle
  Hijinxs): o assento agora é persistente — só termina quando o passageiro pula para fora ou o
  piloto deixa de montar (`$0512`=0). Antes, os ids zerados da tabela de sprites durante a troca
  pareciam "animal perdido". Depois de pular para fora há 45 quadros de carência antes de poder
  sentar de novo (pulando para frente ele caía de volta nas costas do animal).
- **Travamento achado no caminho**: ao entrar numa área nova o Kong entra andando (estado $46) até
  `$1375`; a trava "manter na tela" do co-op o segurava em câmera+16 e o jogo parava ali (também
  aconteceu sem animal). A trava agora só age nos estados de jogo do Kong.
- Testes: `recipes/coop_mount_test.dks` (sentado, pulo do Rambi, descer pulando) e
  `recipes/coop_mount_travel.dks` (Rambi entra na caverna com o Diddy sentado; depois da troca de
  tela ele volta ao assento no quadro seguinte à entrada). Regressão sem co-op inalterada.
- Widescreen (pergunta do usuário): o port base tem widescreen só de apresentação (342×224 ou
  398×224, `DKC1_WIDESCREEN`/`DKC1_WIDESCREEN_EDGE`); está desligado no launcher porque os ajustes
  foram feitos para a v1.0. Teste rápido na v1.2 (Jungle Hijinxs, co-op): imagem 342×224 correta.

### 2026-10-15 — Volta ao mapa na caverna com o Diddy pilotando; câmera; dano sem corrida (9º teste)

- **Volta ao mapa**: reproduzido (`recipes/coop_mount_diddy_travel.dks`: Diddy monta o Rambi, DK
  pula na garupa, o J2 leva o Rambi à caverna escondida → tela escurece → mapa). Causa: a entrada
  (B6:C599/C573) pergunta "qual é o jogador?" por `Player_GetIndexOffset_Far` e grava o destino em
  `$1705,índice` desse Kong; o co-op respondia "o Kong mais perto do objeto" para o banco B6, então o
  destino foi gravado no DK (garupa) e o jogo carregou o do Kong ativo (vazio) → mapa. Podia
  acontecer em qualquer porta. A função voltou a responder como o cartucho (o Kong ativo); toques
  em itens/letras já valem para os dois pela `CODE_BBA574`.
- Também: o Kong que **monta** passa a ser o Kong ativo (como no original, só o ativo monta; mesma
  passagem usada no dano do secundário).
- O Kong montado não usa mais a regra "em pé na cabeça do outro" (o Rambi inteiro ficava apoiado
  na cabeça do DK e o DK não conseguia subir na garupa).
- **Garupa**: DK atrás do Diddy a 16 px (o Diddy atrás do DK continua a 30 px); o passageiro é
  desenhado na camada $E0, entre o animal ($DC) e o piloto ($E4), e volta à camada original ao
  descer.
- **Câmera com os dois montados**: a câmera original do jogo no piloto (com a antecipação da
  corrida) em vez do ponto médio — piloto a ~85 px da esquerda correndo para a direita.
- **Dano sem corrida e sem espera** (pedido do usuário): quando um Kong é atingido o cartucho põe o
  parceiro em $0E→$0A (corre até o lugar) e, no modo Team, espera o botão ($53). No co-op o parceiro
  sai do $0E direto para o estado de chão onde está, vira o Kong ativo, `$0579` bit 0 (dupla em
  jogo) e `$1929` são limpos como no fim da troca original. O Kong atingido foge como antes.
  Testes `coop_out_test` (DK atingido: o Diddy continua andando no mesmo quadro) e
  `coop_p2hit_test` (Diddy atingido: o DK assume no mesmo quadro).
- Regressão sem co-op inalterada; letras, "em pé no outro" e descer da montaria iguais.

### 2026-10-16 — Pausa "pronto?" quando um Kong sai do barril DK (pedido do usuário)

- Quando um Kong que estava fora (estado $0C: atingido, ou ainda não liberado no começo da fase)
  volta ao jogo, ele saiu de um barril DK: o co-op pausa o jogo com a pausa do próprio cartucho
  (Start injetado; `$0579` bit 6 = pausado) e só despausa quando o jogador dono desse Kong aperta um
  botão (B, Y, A, X, L, R ou Start). Durante a espera o Start dos jogadores é ignorado (o outro
  jogador não despausa) e o Select fica bloqueado (na pausa ele sai de uma fase já terminada). O
  título da janela mostra "co-op: Jn, aperte um botao quando estiver pronto".
- Cuidado achado: na pausa cada Start reinicia uma trava (`$1E33`, 80:9AFF; ~32 quadros ao pausar,
  16 depois) e só um Start com ela vencida despausa. O co-op injeta o Start de despausar quando
  `$1E33` <= 0.
- Teste `recipes/coop_ready_test.dks`: o Diddy sai do barril → pausado; J1 aperta B e Start → continua
  pausado; J2 aperta B → volta a rodar e os dois andam. As outras rotas de teste ganharam o "pronto"
  do J2 depois do barril (`wait 0579 == 0040 mask 0040`) e passam como antes.
- Regressão sem co-op inalterada.

### 2026-10-16 — Modo 1 jogador, Kong piscando na espera, pausa indevida na troca de tela (10º teste)

- **Co-op só no "2 Player Team"**: o co-op age apenas com `$42` = 1 (modo Team escolhido no menu do
  jogo). No "1 Player" (e no "2 Player Contest") o jogo fica como o original. O título da janela
  mostra "co-op: so no modo 2 Player Team" fora desse modo. As rotas de teste jogam o 1 Player e
  usam `DKC1_COOP_ANY_MODE=1` (só para teste). Verificado: sem a variável, a rota de 1 jogador
  segue com o Diddy como seguidor ($05).
- **Kong piscando na espera do barril DK**: durante a pausa nada redesenha a lista de sprites
  (`$0200`, 4 bytes por sprite); o co-op esconde/mostra a cada 8 quadros as entradas do Kong que
  saiu (identificadas pelos gráficos dele — tiles a partir do byte baixo de `$0C69,slot` — paleta e
  posição X). O Kong não desenha durante a própria atualização (o jogo desenha tudo depois, ordenado
  por camada), por isso a identificação é pelo conteúdo.
- **Pausa indevida na troca de tela**: a detecção "saiu do barril" usava qualquer saída do estado
  $0C, mas o $0C também esconde o parceiro em portas/trocas de tela (B6:9F36). O barril DK libera o
  Kong no estado $23 (BF:C9DC); só a passagem $0C → $23 dispara a pausa. Viagem montada até a
  caverna: nenhuma pausa.
- Regressão sem co-op inalterada; bateria (letras, em pé, dano, pronto, montaria) igual.

### 2026-10-16 — Saída de bônus voltando ao início da fase (11º teste)

- Relato: Diddy pilotando com o DK na garupa entrou na "segunda caverna"; ao terminar o bônus
  (errando) todos voltaram ao início da fase, DK fora da montaria e "bugado". Não reproduzido (a
  rota cega não chega a esse bônus); a caverna do Rambi (retorno por `$0565`) funciona nos modos
  1 Player e Team, montado, com volta ao ponto certo e remontagem.
- Causas plausíveis corrigidas: (1) bônus que guardam o retorno por Kong (`$1705` DK / `$1707`
  Diddy, B6:C573) são lidos pelo Kong ativo na saída (B8:8383) — se o ativo mudou, o outro índice
  pode estar vazio → início da fase. No co-op os dois índices passam a ser iguais (o que o jogo grava
  num é copiado no outro). (2) Ao sair do assento por qualquer motivo (perda do animal, recarga da
  fase) a camada de desenho e a animação do passageiro (temporizador de pose segurado) são
  restaurados — antes só no pulo para fora.
- Auxílio de teste `DKC1_COOP_TEST_TEAM=<quadro>`: joga as rotas no modo Team (`$42`=1). Bateria no
  modo Team: igual ao 1 Player.
- Launcher com o gravador de reprodução ligado (`DKC1_FLIGHT_RECORDER=1`, pasta `repro`): F9 salva
  as últimas entradas, estados e memória para diagnóstico.
- Regressão sem co-op inalterada.

### 2026-10-19 — Segunda caverna (bônus dos 3 barris) da Jungle Hijinxs (12º teste)

- Rota `recipes/coop_bonus2_test.dks` (modo Team via `DKC1_COOP_TEST_TEAM`): Diddy pilota o Rambi
  com o DK na garupa, passa pela 1ª caverna, sai, desce à esquerda e volta correndo para a direita:
  a 2ª entrada fica à direita (estados $1F/$20/$24 em x≈$10B1) e leva à sala dos 3 barris
  (câmera $5D60).
- **Achado**: na entrada da sala o parceiro entra *de dentro da parede* (tronco à esquerda) como
  seguidor ($32 → $02), andando pelo caminho do líder. O co-op o transformava em jogador no
  mesmo quadro em que era liberado, ainda dentro da parede: a colisão o jogava no estado de
  passagem estreita ($27) e para fora da sala, no alto (y $FF) — o "DK bugado". Fora dos limites,
  ao cair conta como queda no buraco: perde-se a vida e a fase recomeça do início (o sintoma
  relatado). Correção: depois de uma troca de área (tabela de sprites zerada) o parceiro que entra
  andando continua seguidor por 30 quadros antes do jogador assumir (não vale quando o parceiro
  estava ausente, $0C — barril DK). O contexto salvo do Kong secundário também é refeito numa troca
  de área. Verificado: o DK entra atrás do Diddy e fica no chão da sala (y $2F).
- O destino de volta deste bônus é `$0565` (= $6E, global). Na rota o erro na combinação faz os
  barris voltarem a girar (nova tentativa); a saída do bônus não foi alcançada na rota automática.
- Rotas antigas com os mesmos quadros de antes; regressão sem co-op inalterada.

### 2026-10-19 — Mapa completo do "jogador" e regras do usuário (etapas 1 e 2)

- `COOP_MAP.md` + `COOP_MAP_sites.csv` (885 pontos do jogo original que dependem do jogador,
  classificados T/A/C/L/R/B/P/G; scripts em `tools/coopmap/`). Regras decididas pelo usuário:
  troca de tela é suprema (líder + puxa o outro); interações superficiais são individuais;
  carrinho de mina é um para os dois (o primeiro dirige); montarias seletivas.
- **Etapa 1 — troca de tela com líder**: estados de transição ($1B/$1D/$1F/$20/$24/$3C/$3D/$4F/$51)
  — o Kong que entra num deles vira o líder antes da sequência (troca de contexto + `$056F`), o
  outro, se livre, volta a ser o seguidor do jogo original ($02) e o co-op fica pausado até a área
  nova (espera de seguidor de 30 quadros já existente).
- **Etapa 2 — cada um por si**: `Player_GetIndexOffset` ($80:9B9C) responde conforme quem
  perguntou, pela pilha de nomes do recompilador (`g_recomp_stack`): as 31 funções de mira,
  proximidade e ação no jogador (cordas, barris-canhão, plataformas-guia, caixa de animal, tapa no
  chão, inimigos e chefes) recebem o Kong mais próximo do objeto; o resto (câmera, portas,
  destinos, carrinho) recebe o líder. Tabela gerada `runner/dkc1_coop_callers.h`
  (`tools/coopmap/callers.py`). O toque "só no ativo" `BBA64A` (pneus, tambores, barris de
  inimigos) agora aceita os dois, como o `BBA574`.
- Bateria `DKC1Recomp/coop_battery.sh` (10 rotas + regressão): todas iguais às de antes; respostas
  "mais próximo" ~1800 por rota (inimigos mirando). Regressão sem co-op inalterada.
- Não testado em rota (as rotas não chegam lá): cordas (Ropey Rampage), barris-canhão (Barrel
  Cannon Canyon), pneus, carrinho de mina (Mine Cart Carnage). Carrinho: falta a regra "o
  primeiro que entra dirige" quando o secundário embarca primeiro.

### 2026-10-20 — Bônus dos 3 barris voltava ao início da fase (causa encontrada)

- Reproduzido (`recipes/coop_bonus2_test.dks`, modo Team): parar dois barris com animais
  diferentes faz os barris explodirem (erro) e o bônus termina. Comparação com o original (auxílio
  `DKC1_COOP_TEST_SOLO_FROM=<quadro>`: volta ao jogo de 1 jogador a partir do quadro): com o
  original desde antes da entrada, a saída leva a x $10E4 (logo depois da caverna) com o Diddy no
  Rambi; com co-op, ia ao começo da fase. A entrada grava o destino certo (`$0565` = $6E =
  `JungleHijinxs_ExitBonus2`) nos dois casos.
- Causa: `$1E2B` é o **pedido de fim de sequência** (fim de bônus, fichas de animal, banana gigante
  do fim de fase, fim das plataformas-guia, chefe), lido pelo código do Kong em 17 estados
  (BF:876C): o primeiro Kong que o lê faz o fim (pose $11/$55/$4E, contagem, saída) e o apaga. No
  original só o líder lê (o seguidor não passa por ali) e o seguidor é escondido ($0C). No co-op o
  DK, jogador, lia primeiro e fazia o fim "do jogador" ($11), terminando como morte → vida perdida →
  fase do início.
- Correção: com um pedido de fim pendente, o Kong que não é o líder vira seguidor do jogo original
  (puxado junto) e o pedido fica escondido durante a atualização dele; o co-op fica pausado até o
  fim. Resultado: igual ao original — DK escondido, Diddy na pose de derrota, volta a x $10E4.
  Vale também para o acerto e para os outros fins de sequência.
- Bateria (`coop_battery.sh`): tudo igual; o bônus agora chega à volta na fase. Regressão sem
  co-op inalterada.

### 2026-10-20 — Cordas (nenhum dos dois agarrava)

- Rota nova até a Ropey Rampage (`recipes/coop_rope_test.dks`, `coop_rope_dk_test.dks`) com
  auxílios de teste: `DKC1_COOP_TEST_WARP=0C` (quando o mapa inicia a Jungle Hijinxs, inicia a
  entrada $0C) e `DKC1_COOP_TEST_GIVE_PARTNER=<quadro>` (liberta o parceiro ao lado do líder como
  o barril DK faz, BF:C9DC). Reproduzido: sozinho o DK agarrava a corda (x $1A41); em co-op
  nenhum dos dois.
- Causa: o estado de corda do jogo é global de um jogador — `$1AFD` (corda vertical ao alcance),
  `$1AFF` (corda de balançar ao alcance), `$1B01` (corda segurada). A corda grava "ao alcance"
  pensando num Kong (B6:8000) e o Kong lê em `BF:8861/881C`; com dois Kongs um sobrescrevia o do
  outro.
- Correção: cada Kong tem sua cópia dessas variáveis (trocadas na atualização do secundário, como
  o contexto `$1811–$1930`, e na troca de líder). As cordas ($30 vertical, $31 de balançar) são
  envolvidas: a cada quadro cada corda trata **um** Kong — o que a segura, senão o mais próximo —
  com as variáveis desse Kong no lugar e "qual é o jogador" respondendo esse Kong.
- Testes: Diddy agarra (estado $25, x $1A41) e segue pulando; só o DK pulando: o DK agarra.
  Bateria com 12 rotas: tudo igual; regressão sem co-op inalterada.
- Limites: só a corda vertical foi vista na rota; a de balançar ($26) usa o mesmo caminho mas não
  foi vista. Dois Kongs na **mesma** corda ao mesmo tempo: a corda carrega só um deles.

### 2026-10-20 — Dois Kongs na mesma corda (gravação F9 do usuário)

- Gravações em `repro/` (Ropey Rampage, modo Team): o DK na corda vertical (estado $25) e o
  Diddy ao lado sem conseguir subir na mesma corda — a corda tratava um Kong por quadro.
- Correção: cada corda roda uma vez para o Kong que a segura (ou o mais próximo) e, se o outro
  também a segura ou está a até $40 px, roda de novo para ele, a partir do mesmo estado da corda
  (51 campos de sprite salvos/restaurados, quadro de JSL e índice de OAM como nas bananas). A
  corda fica com o estado da primeira passada (não balança nem anima em dobro); cada Kong é
  agarrado/carregado na sua passada.
- Teste `recipes/coop_rope_both_test.dks`: o Diddy agarra a corda, o DK pula reto e agarra a mesma
  — os dois pendurados (Diddy em cima, DK embaixo). Bateria com 13 rotas igual; regressão sem
  co-op inalterada.

### 2026-10-20 — Corda sem "cabeça" e queda num buraco com o parceiro vivo

- Na corda os Kongs se atravessam: a regra "em pé na cabeça do outro" não vale com qualquer um
  dos dois nos estados de corda ($25 vertical, $26 de balançar).
- Queda num buraco: no cartucho (BF:A6C9, Y < -$30) vira o estado $3B, congela a câmera
  (`$1929`), toca a música de morte e tira uma vida — no original só o líder cai. No co-op, se um
  Kong cai e o parceiro está em jogo, o Kong só sai de cena (estado $0C, sem categoria, sem
  montaria; liderança passa ao parceiro se preciso) e volta pelo barril DK, como num dano. Pego um
  pouco antes do cartucho (Y < -$18), antes da música e do congelamento. Nos bônus a queda continua
  sendo a saída do bônus; sem parceiro em jogo, vale o original (perde a vida).
- Teste (rota da corda): o DK cai no buraco → sai de cena, o Diddy vira o líder e segue (antes a
  fase recomeçava). Depois o Diddy, sozinho, cai → vida perdida, como no original.
- `coop_rope_test.dks` agora espera o Diddy na corda. Bateria igual; regressão sem co-op
  inalterada.

### 2026-10-20 — Teleporte de fase, widescreen no co-op, canhão com os dois

- **Teleporte**: menu Controles → "Ir para a fase": escolhida uma fase, a próxima fase iniciada a
  partir de um mapa (entradas $E6–$E9, $EB–$ED; $EA é a Reptile Rumble) vira a escolhida (uma vez).
  O título mostra o teleporte pendente. É o mesmo mecanismo do auxílio `DKC1_COOP_TEST_WARP`
  (agora genérico: mapa → fase).
- **Widescreen**: já existe no menu View → Aspect Ratio → Widescreen 16:9 (342×224). A trava
  "manter na tela" do co-op passou a usar a largura visível (inclui as colunas extras).
- **Barril-canhão com os dois** (`recipes/coop_cannon_both_test.dks`, Barrel Cannon Canyon via
  teleporte): os dois pulam juntos no mesmo canhão → um entra ($29), o outro fica de fora (barril
  ocupado); cada jogador atira com o próprio B; com o barril livre, o outro entra e atira.
  Um Kong por canhão de cada vez, cada um por si.
- Bateria com 14 rotas: tudo igual; regressão sem co-op inalterada.

### 2026-10-21 — Saída da 1ª caverna congelada com o DK pilotando (gravação F9)

- Gravação (`repro/capture-f00007053…`): saída do bônus 1 (entrada $08) com o DK no estado $47
  (escondido, esperando o barril de saída) em x $00F0 — lugar errado — sem barril de saída na lista
  de sprites e `$1929` = 8 (sprites congelados): nada tira o DK do $47. Carregar o retrato
  reproduz o congelamento; reproduzir a partida a partir do retrato do quadro 3600 não dá (o
  estado do co-op não está no retrato).
- Diferença em relação à minha rota (mesma saída, funcionando): `$0537` — o retrato da fase que o
  jogo salva ao entrar num bônus (BC:BBBA, a partir do caminho que lê o destino pelo Kong ativo,
  B8:8429) e restaura na volta (80:841F). Na partida do usuário ele não foi salvo: a entrada seguiu
  outro caminho. Causa provável: a porta da caverna testa o toque com os dois Kongs e pegava o
  Diddy na garupa; a regra "quem entra lidera" fazia o passageiro virar líder e as leituras de
  destino/animal desencontravam.
- Correções: (1) o Kong sentado na garupa não toca objetos (portas, itens) — o piloto toca;
  (2) um passageiro nunca vira líder por uma transição (é puxado junto); (3) `$1705/$1707` são
  igualados também no instante em que o jogo pergunta pelo jogador (não só no fim do quadro).
- Garupa: Diddy atrás do DK a 20 px (a 30 px ficava além da garupa, flutuando atrás do rabo).
- Bateria com 14 rotas igual; regressão sem co-op inalterada. A saída congelada em si não foi
  reproduzida por rota (a rota equivalente funciona) — pedir nova gravação se voltar.

### 2026-10-21 — Posição do Diddy na garupa (gravação F9)

- Retrato da gravação renderizado: o Diddy na garupa ficava quase todo atrás do corpo do DK (só
  pernas, rabo e braço à mostra) — uma mancha. Comparadas 4 posições (atrás, acima) com o auxílio
  `DKC1_COOP_SEAT=<atrás>,<acima>`: (20,0), (18,6), (22,8), (24,12). Escolhida (22,8): sentado nas
  costas do Rambi com cabeça e boné visíveis atrás do ombro do DK; (24,12) já parece flutuar.
- Bateria com 14 rotas igual; regressão sem co-op inalterada.

### 2026-10-21 — Pose do passageiro (Diddy "flutuando")

- A pose usada ($0DB0 Diddy / $058C DK) é o quadro dos scripts de montaria em que o Kong monta de
  pernas abertas; atrás do piloto, com a traseira do animal mais baixa, as pernas ficam no ar —
  parecia flutuar em qualquer altura (testadas 5).
- Comparadas poses do próprio jogo com o auxílio `DKC1_COOP_SEAT_POSE=<hex>`: montado próprio do
  Kong (`RideAnimalBuddy`, anim $83/$1B → Diddy $0D00, DK $0538), agarrado ao Winky ($0D28),
  agachado ($0D48), passagem estreita ($0D8C). Escolhidas $0D00 / $0538: sentado, compacto,
  segurando — sem pernas soltas. Diddy 22 px atrás, sem elevar; DK 16 px atrás.
- Bateria com 14 rotas igual; regressão sem co-op inalterada. Imagens em `repro/garupa_poses_*.png`.

- 2026-10-22: Diddy na garupa mais perto do DK (14 px atrás, meio escondido, a pedido do usuário). Bateria igual.

### 2026-10-23 — Squawks, Enguarde, teleporte e água

- **Squawks (Torchlight Trouble):** wrapper `DKC1_NorSpr0D_Squawks_Main` — durante a atualização
  dela, o líder é apresentado no ponto médio entre os dois Kongs (e restaurado depois), então a
  luz fica entre a dupla. Ainda não visto em jogo: a rota de teste não conseguiu soltar a Squawks.
- **Enguarde:** garupa estendida ao peixe (`RidesEnguarde`): embarque por proximidade nadando
  (sem pousar nas costas), velocidade zerada enquanto carregado, pose mantida nos estados de nado.
  Ainda não testado — ver "água" abaixo.
- **Teleporte:** funcionava, mas só age ao entrar numa fase pelo mapa, e o aviso estava só no
  título da janela. Agora a escolha abre uma caixa explicando e marca o item no menu. Testado:
  `$2E` (Mine Cart Carnage) carrega certo.
- **Achado — `DKC1_COOP_TEST_GIVE_PARTNER` na Torchlight:** o Diddy criado pelo auxílio salta
  para o reset do jogo (`80:80F2`) 30 quadros depois (pilha descontrolada). Com a dupla real
  (Diddy do barril DK na 1-1, teleporte na entrada da caverna com o novo
  `DKC1_COOP_TEST_WARP_ANY`) a Torchlight roda normal: é limitação do auxílio, não do co-op.
  Tentativa descartada: suspender o prazo do quadro nos wrappers (prendia o jogo em laço).
- **Água (Coral Capers):** o Kong secundário saía do papel de seguidor no estado de chão e andava
  invisível pelo fundo. Agora vira nado (2B) quando o parceiro nada. Mas continua seguindo o
  caminho do líder (posição = a do líder 120 quadros antes) e invisível: algum efeito de sistema
  da fase de água (categoria B do mapa, só no ativo) ainda o comanda. Pendente.
- Formato dos controles nas receitas: bits do host (B=001, Y=002, Select=004, Start=008,
  cima=010, baixo=020, esquerda=040, direita=080, A=100), J2 deslocado 12 bits.
- Diagnóstico novo (desligado por padrão): `DKC1_COOP_TRACE_NEAR=1` lista quem pediu o "Kong mais
  próximo"; `DKC1_COOP_TEST_NO_NEAR=<função>` desliga essa resposta para uma função; trace com
  `e2b`/`f1929`.

### 2026-10-23 — Kong invisível na água (Coral Capers)

- Relato: "o Diddy some sozinho, ainda dá para controlar, mas não aparece nem interage"; e com o
  Enguarde, ao quebrar um barril DK, "o macaco sumiu".
- Causa: ao sair do papel de seguidor (barril DK, troca após dano, troca de área) o co-op punha o
  Kong no estado de chão; na água, o estado de nado (2B) sem a animação de nado ($60) deixa o
  Kong sem script de animação (`$116D` lixo): não é desenhado nem colide.
- Correção: `EnterFreeState` — nado quando o parceiro nada, e inicia a animação como o cartucho
  (80:852C: estado 2B + `Player_SetAnimation` $60), chamando a rotina original num quadro de JSL
  e restaurando a CPU. O Diddy agora aparece, nada com o próprio controle e pega bananas.
- Nova rota `coop_swim_test` na bateria. Enguarde ainda não alcançado por rota (caixa longe).
- Widescreen "faixas verde e azul": é a camada de diagnóstico de procedência (F1 / View →
  Provenance Overlay), não defeito.

### 2026-10-26 — Trava de tela trocada por "coleira" (Kong atravessando parede)

- Relato: o Kong empurrado pela borda da tela contra uma parede atravessava a parede.
- Causa: `ClampToScreen` reposicionava à força quem saía da tela; com a câmera no ponto médio,
  quando um Kong avançava, a câmera andava e o de trás era empurrado sem checar o cenário.
- Correção: `LeashToPartner` — os Kongs ficam no máximo uma tela visível de distância (256 + as
  colunas extras do widescreen − 2×16); quem se afastou neste quadro é segurado, nunca além de
  onde estava no quadro anterior (posição que ele mesmo alcançou), e o outro nunca é empurrado.
  Medido: em 4:3 o Kong que corre para a 225 px do parado, em widescreen a 311 px; o parado
  não se move.
- Consequência de jogo: um jogador não arrasta mais o outro; precisa esperar ou voltar.
- Rotas ajustadas (dependiam do arrasto ou do ritmo exato de pulos): letra (pulo a partir de x
  $0340), Rambi do DK (anda até $0B78 e pula três vezes), garupa no Rambi do Diddy (o DK volta até
  $0B90 antes de pular). Limites da bateria: mount 11300, bonus2_team 14400.

### 2026-10-26 — Diddy andando no fundo depois que o DK foi atingido

- Relato: o DK morreu e o Diddy passou a andar no chão em vez de nadar.
- Causa: a escolha "nado ou chão" ao assumir o controle olhava só o parceiro; atingido, o
  parceiro sai do nado (3A → 39 → 0C), então o que assumia caía no estado de chão.
- Correção: `s_in_water` — a área é de água desde o primeiro Kong visto nadando até a troca de
  área (`$3E`); `FreeStateFor` usa isso além do parceiro.
- Novo auxílio de teste `DKC1_COOP_TEST_HURT=<quadro>,<slot>` (evento de dano `$1595` = 1).
  Testado: DK atingido na Coral Capers → Diddy assume e segue nadando. Bateria igual.

### 2026-10-26 — Saída da garupa do Enguarde

- Relato: ao descer da garupa do Enguarde o Kong continuava com pose de sentado.
- Causa: o assento segura o timer da pose; ao sair, só o timer era liberado — em terra o pulo de
  saída troca a animação, na água a braçada não, e o script ficava na pose sentada.
- Correção: ao sair do assento com a área em água, na atualização seguinte o Kong recebe o estado
  de nado com a animação de nado (`EnterFreeState`). Não testado por rota (Enguarde não alcançado).

### 2026-10-26 — Dois Enguardes, controles misturados

- Relato: com cada Kong no seu Enguarde, os controles interferiam um no outro.
- Causa: o Kong secundário montado era promovido a líder (no cartucho só o ativo monta; isso
  resolve as entradas de área que o animal abre). Com os dois montados, a liderança trocava a
  cada quadro, trocando contextos e controles.
- Correção: a promoção por montaria só acontece se o líder atual não estiver montado.
  Bateria igual; dois animais ao mesmo tempo não testados por rota.

### 2026-10-26 — Sem interação entre os Kongs na água

- Relato: um Kong fez o outro atravessar a parede (Coral Capers). Decisão do usuário: nas fases
  de água, remover a interação entre os macacos.
- `StandOnPartner` não age com `s_in_water`: sem cabeça e sem garupa no Enguarde (quem estiver
  sentado é solto e volta a nadar). Cada Kong nada sozinho ou no próprio Enguarde.
  A garupa nos animais de terra continua. Bateria igual.

### 2026-10-26 — Sem troca de controle montado

- Pedido: com um ou os dois Kongs em montaria, os jogadores não podem trocar de Kong.
- A troca do co-op (os dois apertam A, perto) fica bloqueada se algum Kong monta um animal ou
  carrinho (`$0512/$0514`) ou está sentado na garupa. Testado: DK no Rambi + A dos dois → nada;
  a pé, perto → troca. Bateria igual.

### 2026-10-26 — Uma montaria por vez (dois Enguardes)

- Relato com imagem e F9 (15:40): cada Kong no seu Enguarde (slots $0A e $10, estado $30); um
  desenhado com gráficos/cores do outro. O cartucho só prevê um animal montado (gráficos e
  paleta da montaria únicos); dois disputam esses recursos.
- Regra: uma montaria por vez. Enquanto o parceiro monta (`$0512/$0514`), todos os sprites
  montáveis (`$11A1` bit 8) ficam ocultos da atualização do outro Kong (generaliza a proteção
  "um piloto por animal"). A garupa em terra é do co-op, não montaria, e continua.
  Bateria com checkpoints idênticos.

### 2026-10-27 — Garupa do Enguarde de volta, sem deslocamento

- Pedido: ao menos a garupa no Enguarde (uma montaria por vez continua).
- Na água, a única interação é o assento no Enguarde; o passageiro fica exatamente na posição do
  piloto (sem deslocamento para trás/cima), um lugar que o piloto alcançou — o deslocamento é que
  podia cair dentro de parede. Desenhado atrás do piloto. Cabeça continua desligada na água.
  Bateria com checkpoints idênticos; garupa no Enguarde não testada por rota.
