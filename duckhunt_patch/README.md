# Duck Hunt (NES): patch para pistola de luz caseira

Patch IPS que faz o Duck Hunt ler a pistola caseira (TEPT4400 + ESP32-S3) como um **controle padrão na porta 2**, **estica o flash do tiro** para compensar o atraso entre emulador, USB/Bluetooth e CRT, e acrescenta um item **CALIBRATION** no menu para ajustar esse atraso dentro do jogo.

- **Botão A** = luz detectada (vira o bit 3 = 0 da Zapper)
- **Botão B** = gatilho (vira o bit 4 = 1 da Zapper). O firmware manda um pulso de 50 ms (`PULSO_B_MS`).
- **K** = quantos quadros o sensor leva para *parar* de ver luz (com folga). **N** = quantos quadros ele leva para *começar* a ver luz (com folga).
- O flash tem três partes:
  - **etapa preta** de K + 2 quadros: os K primeiros são ignorados (o sensor ainda vê o céu) e nos 2 últimos não pode haver luz;
  - **etapa do 1º alvo** de N quadros, conferida desde o 1º quadro: a etapa preta já garantiu que o sensor está no escuro;
  - **etapa do pato 2** (só no Game B) de max(K + 3, N) quadros, com os K primeiros ignorados, porque o sensor ainda pode estar vendo o quadrado do pato 1.
- **S** = nível de **sombra**: em vez de apagar a tela no tiro, mostra o cenário com as cores escurecidas e o quadrado branco por cima. `0` = tela preta (como o jogo original), `1` = bem escuro, `2` = escuro, `3` = meio escuro (só para teste manual). A calibração escolhe o S sozinha, testando o que o seu sensor ainda enxerga como escuro.
- K, N e S ficam salvos na **RAM extra com bateria** (`$6000`), igual ao save de um jogo, e são ajustados pelo menu. Se o emulador ou o cartucho não tiver essa RAM, o patch funciona do mesmo jeito (com uma cópia na RAM interna), só não guarda os valores ao desligar.
- Pontuação, sons, IA dos patos e o restante do menu não foram alterados.

ROM alvo: **Duck Hunt (World)**, NROM-128 (16 KB PRG + 8 KB CHR), **CRC32 da ROM sem cabeçalho `24598791`**. Use o dump do seu cartucho. Se o CRC bater, os bytes são idênticos.

## Como usar o menu CALIBRATION

Na tela de título, o **Select** do controle 1 (ou um **tiro fora da TV**, como no jogo original) passa por:

```
  > GAME A   1 DUCK
    GAME B   2 DUCKS
    GAME C   CLAY SHOOTING
    CALIBRATION
     K=07  N=08 S=0      <- aparece no lugar do TOP SCORE quando CALIBRATION está selecionado
```

Com **CALIBRATION** selecionado:

| Ação | Efeito |
|---|---|
| **Start** no controle 1, ou **tiro na TV** | Calibração automática. Mire a pistola na TV e não mexa: a tela pisca preto/branco 6 vezes (~3 s), depois faz o **teste de sombra** (azul, cinza, branco, até ~6 s) e volta ao título com os novos K, N e S. |
| **Cima / Baixo** | K +1 / −1 (de 1 a 60) |
| **Direita / Esquerda** | N +1 / −1 (de 2 a 99) |
| **A** | S = 0, 1, 2, 3, 0... |

Tudo é salvo na hora. Também dá para usar o menu só com a pistola: tiro fora da TV troca a opção, tiro na TV escolhe. No tiro do título, o jogo original acende a tela inteira, então basta mirar na TV.

**O que a calibração mede**, em quadros:
- **subida**: quanto tempo o sensor demora para ver a luz depois que a tela fica branca;
- **descida**: quanto tempo demora para deixar de ver depois que a tela fica preta. Esse valor já inclui os 20 ms que o firmware segura o A.

Com o maior valor de cada um em 6 piscadas:
- **K = maior descida + 2** (`MARGEM_K`: K curto faz errar tiros certos; K longo só alonga o flash)
- **N = maior subida + 3** (`MARGEM_N`)

**Teste de sombra** (logo depois, com o K e o N novos): para o nível 2 e depois o 1, repete 3 vezes:
1. "céu" azul por meio segundo, como antes de um tiro;
2. a cor mais clara que aquele nível usa (`$10` cinza no nível 2, `$00` cinza-escuro no nível 1) por K + 2 quadros: depois dos K primeiros, o sensor **não pode** ver luz;
3. branco por até N quadros: o sensor **precisa** ver luz.

O S fica com o primeiro nível que passar as 3 vezes. Se nenhum passar, S = 0 (tela preta). O teste usa a tela inteira na cor mais clara do nível, então é mais exigente que o jogo, onde quase todo o cenário fica mais escuro que isso.

Se o sensor não mudar em 1,5 s (pistola fora da TV ou sensor sempre aceso), a calibração é cancelada e os valores antigos ficam. Na primeira vez, ou se a RAM estiver corrompida, os valores padrão são **K=7, N=8, S=0**. Saves das versões anteriores do patch também voltam ao padrão: recalibre depois de atualizar.

**Sem RAM com bateria** (emulador ou flashcart que ignora a PRG-RAM no mapper 0): o jogo começa com K=7, N=8. Calibração e ajuste manual funcionam normalmente, mas valem só até desligar. Se o menu mostrar `K=96 N=96`, é sinal de que você está usando uma versão antiga do patch nessa situação.

> **Solte o Start** logo depois de apertar. Se ele continuar segurado quando a calibração acabar, ela começa de novo.

## Arquivos

| Arquivo | O que é |
|---|---|
| `src/patch.s` | Código-fonte (ca65), comentado. Valores padrão, limites e parâmetros da calibração no topo. |
| `src/patch.cfg` | Configuração do ld65 (um trecho por endereço alterado) |
| `build.py` | Monta, gera o `.ips` (com o cabeçalho), aplica numa cópia e confere que só mudou o previsto |
| `test_flash.py` | Simulador do tiro: código 6502 da ROM com atraso de vídeo e sensor simulados |
| `sim_nes.py` | NES mínimo (CPU + PPU simplificada + controles + pistola) para rodar o jogo inteiro |
| `test_menu.py` | Testes do menu, da calibração, da RAM com bateria e de uma partida completa |
| `dist/duckhunt_pistola.ips` | O patch |
| `dist/tabela_enderecos.md` | Tabela de endereços alterados (gerada pelo build) |

`tools/` (cc65), `build/` e qualquer `.nes` ficam fora do Git.

## Endereços alterados

| Endereço CPU | Offset no arquivo | Bytes originais | Bytes novos | Motivo |
|---|---|---|---|---|
| cabeçalho | `0x00006` | `01 08 00 00 00 00 02 00 00 08` | `03 08 00 00 70 00 02 00 00 01` | NES 2.0: bateria + 8 KB de PRG-NVRAM em `$6000`; acessório padrão = controles (antes: Zapper) |
| `$D131-$D133` | `0x01141` | `AD 17 40` | `20 60 EF` | `LDA $4017` (gatilho da Zapper) vira `JSR LerZapper` |
| `$D1C7-$D1CC` | `0x011D7` | `20 92 D2 20 1E C6` | `4C EF EF 4C F2 EF` | Entradas do flash viram a rotina nova |
| `$C176-$C178` | `0x00186` | `A9 00 85` | `4C 8B F0` | Start/tiro no título: com CALIBRATION, calibra em vez de começar a partida |
| `$C19E` | `0x001AE` | `03` | `04` | `CPY #$03` vira `#$04`: o Select passa por 4 opções |
| `$C1C0` | `0x001D0` | `51` | `71` | Cursor numa coluna de 7 linhas (17 a 23) |
| `$C1C7` | `0x001D7` | `04` | `06` | Limpa as 7 posições da coluna do cursor |
| `$C1DF-$C1E1` | `0x001EF` | `AD FE 05` | `4C 9C F0` | Linha do TOP SCORE: mostra K, N e S no modo 3 e ajuste pelo direcional e pelo A |
| `$C5C8-$C5CA` | `0x005D8` | `20 17 C6` | `20 68 F0` | Desenho do título + lista nova com "CALIBRATION" (`$22E8`) |
| `$C82B-$C82D` | `0x0083B` | `AD FE 05` | `20 81 F0` | Segurança: o modo 3 nunca vira partida |
| `$EF60-$F2F7` | `0x02F70` | `FF` × 920 | código novo (920 bytes) | Rotinas novas no bloco livre `$EF5A-$F2FF` (sobram 8 bytes) |
| `$FF30-$FFDF` | `0x03F40` | `FF` × 176 | código novo (176 bytes) | Sombra e teste de sombra, no bloco livre `$FF2F-$FFF9` antes dos vetores |
| `$D1CD-$D1DB` | `0x011DD` | código original morto | lista "CALIBRATION" | Laço original da Zapper, que ninguém mais executa |
| `$D1F4-$D223` | `0x01204` | código original morto | `Escurece`, `ProximoS`, cores do teste | Etapa original do quadrado, que ninguém mais executa |
| `$D270-$D286` | `0x01280` | código original morto | `LeModoJogo`, `DoisDigitos` | Troca original para o pato 2, que ninguém mais executa |

**Código original morto:** o patch desvia o tiro em `$D1C7`/`$D1CA`, e a partir daí o jogo nunca mais passa por `$D1CD-$D1DC`, `$D1F4-$D22C` e `$D270-$D289`. Os únicos saltos para esses trechos vinham de dentro deles mesmos. Num teste com o simulador (Games A, B e C, ~16 mil quadros, 57 acertos, erros, tiros sem pato e no título), nenhum dos três foi executado, e todas as rotinas vizinhas que continuam em uso foram. O `build.py` só aceita código novo dentro desses limites.

A conversão é offset = endereço − `$C000` + `$10`. O NROM tem um banco só, então o código novo está no mesmo banco que o chamador. Os trechos originais de resultado do tiro (`$D22D` para acerto, `$D28A` para erro), o desenhista de listas (`$C617`) e a fila de escrita na PPU (`$C71D`) são reaproveitados sem alteração.

**Registro do cabeçalho:** reescreve os bytes 6 a 15 inteiros. Assim o resultado é um NES 2.0 consistente, mesmo que o dump tenha cabeçalho iNES 1.0. Ele também troca o acessório padrão de Zapper para controles padrão, para o Mesen não colocar a Zapper na porta 2 sozinho.

### RAM extra com bateria (`$6000`): só para guardar

| Endereço | Conteúdo |
|---|---|
| `$6000-$6001` | Marca `'D' 'J'` (`'D' 'H'` e `'D' 'I'` eram as versões anteriores) |
| `$6002` / `$6003` | K / N |
| `$6004` | Soma de verificação (K xor N xor S xor `$5A`) |
| `$6005` | S |

### RAM interna (`$07E0`): valores em uso

A página `$0700` não é usada pelo jogo: nenhuma referência na ROM e nenhum acesso nos Games A, B e C no simulador. Toda a lógica lê K e N daqui. A cada quadro do título (e antes de cada tiro), `CarregaConfig` copia o que está salvo em `$6000`, se for válido. Se não for, mantém a cópia da sessão; se nem ela for válida, usa o padrão. Depois grava o resultado nas duas cópias.

| Endereço | Conteúdo |
|---|---|
| `$07E0` | Marca `'D'` |
| `$07E1` / `$07E2` | K / N em uso |
| `$07E3` | Soma de verificação |
| `$07E4-$07E8` | Uso temporário (direcional anterior, medições da calibração, PPUMASK salvo) |
| `$07E9` / `$07EA` | Quadros ignorados / duração da etapa atual do flash |
| `$07EB` | S em uso |
| `$07EC-$07EF` | Uso temporário da sombra |
| `$07F0-$07FF` | Paleta do cenário escurecida |

### Como a sombra funciona

No tiro, o jogo original pede a lista de cores 4 e depois a 5, que deixam a paleta toda preta (só o quadrado branco). O patch espera o 1º quadro preto e então, se S > 0:
1. pega as 16 cores do cenário direto da ROM (lista 2 em `$E55B` para os Games A/B, lista 3 em `$E57F` para o Game C);
2. tira (4 − S) linhas de brilho de cada cor (`$21` → `$01` com S=1 ou 2; `$30` → `$00` com S=1 e `$10` com S=2; pretos `$xD-$xF` → `$0F`);
3. agenda essas cores pela fila de escrita na PPU do próprio jogo (`$C71D`), que grava tudo no momento seguro da tela (NMI), e liga o fundo.

A partir do 3º quadro aparece o cenário escurecido, sem os patos e o cachorro (os sprites já foram trocados pelo quadrado). Depois do tiro, o jogo devolve as cores normais sozinho, como sempre fez. No tiro da tela de título nada muda.

## Como gerar e aplicar

```powershell
cd C:\Users\leopa\Documents\repositorios\REA\duckhunt_patch
python build.py "C:\caminho\do\seu\dump.nes"
```

O script:
1. confere o cabeçalho (NROM-128) e o CRC32;
2. confere os bytes originais em cada endereço e que o código novo cai só em `$FF`;
3. gera o `.ips`, aplica numa cópia (`build/DuckHunt_pistola.nes`) e confirma que nenhum byte mudou fora da tabela.

**A ROM original nunca é escrita.**

Para aplicar no seu dump: copie o arquivo e aplique `dist/duckhunt_pistola.ips` na cópia com o **Floating IPS** ou o **Rom Patcher JS**. Também pode usar direto a cópia `build/DuckHunt_pistola.nes`.

CRC32 esperado da cópia patcheada, sem cabeçalho: **`F85C4174`**.

## Calibração manual: o que cada valor faz

- **K** precisa cobrir o atraso máximo mais a "segura" de 20 ms do sensor. Com os valores padrão (K=7), o atraso aceito vai de 0 a 5 quadros.
- **N** precisa cobrir o atraso para acender, com folga para a variação (comum no Bluetooth).
- Duração do flash: acerto no 1º alvo ≈ K + 2 + atraso + 1 quadros; erro no Game A ≈ K + 2 + N; Game B ≈ K + 2 + N + max(K + 3, N).
- Em relação à versão anterior, no simulador, com cada versão calibrada: o flash ficou **15 a 25% mais curto no Game A** e **6 a 11% no Game B** (atraso de 1 a 5 quadros).

| Sintoma | Causa provável | Ajuste no menu |
|---|---|---|
| Todo tiro dá erro, mesmo mirando certo (pior com céu claro) | K curto: o sensor ainda vê o céu na parte conferida da etapa preta | Cima (K+1) |
| No Game B, mirando no pato 1, o jogo conta acerto no pato 2 | K curto: o quadrado 1 ainda está no tubo quando começa a etapa do pato 2 | Cima |
| Acertos falham de vez em quando, sem padrão | N curto para a variação de atraso (comum no Bluetooth) | Direita (N+1) |
| Tiro às vezes não sai | Pulso do gatilho curto | Suba `PULSO_B_MS` para 80–100 ms no firmware |
| Flash longo e incômodo | K ou N maiores que o necessário | Baixo (K−1) ou Esquerda (N−1), sem passar dos sintomas acima |
| Com sombra (S > 0), tiros no céu ou no mato contam como acerto, ou todo tiro dá erro | O sensor vê o cenário escurecido como luz | A até S ficar menor (ou recalibre); S=0 volta à tela preta |
| Tela preta incomoda e o S ficou 0 | O sensor vê até os tons escuros como luz | Teste S=1 com A; se der os sintomas acima, diminua a sensibilidade (`DELTA_LUZ`) no firmware e recalibre |

## Testes

### 1. Simuladores (sem emulador)

```powershell
python -P test_flash.py "C:\caminho\do\seu\dump.nes" build\DuckHunt_pistola.nes --n 8 --k 7
python -P test_menu.py build\DuckHunt_pistola.nes
```

**`test_flash.py`** (33 casos) testa:
- tiro com atraso de 0 a 5 quadros;
- sem luz;
- A apertado o tempo todo;
- mira fora do pato;
- Game B mirando em cada pato, e com só o pato 2 voando;
- Game C;
- tiro no título;
- tiro sem RAM com bateria (valores padrão);
- pulsos de gatilho de 50 a 100 ms;
- o limite de atraso que N e K aguentam.

**`test_menu.py`** (73 casos, ~4 min) roda o jogo inteiro desde o RESET e testa:
- a linha CALIBRATION e o cursor nas 4 opções;
- K, N e S na tela, e o A trocando o S;
- saves das versões anteriores voltando ao padrão;
- o ajuste manual e os limites;
- a RAM com bateria (desligar/ligar, RAM com lixo);
- a calibração com atraso de 0, 2, 3, 5 e 8 quadros, que deve dar exatamente K = L+4 e N = L+3 (com 2 quadros de "segura");
- a calibração cancelada (pistola fora da TV, sensor sempre aceso);
- o teste de sombra com sensores de sensibilidades diferentes (S = 2, 1 e 0);
- a navegação só com a pistola;
- 30 s parado no título sem iniciar partida;
- partidas dos Games A (S=2 e S=0), B (S=1, no pato 2) e C (S=2): acerto mirando no alvo, erro mirando no céu, cenário escurecido durante o tiro e cores normais depois;
- sem RAM com bateria: valores padrão, ajuste manual e calibração valendo na sessão.

### 2. Mesen, sem a pistola (teclado)

1. Abra `build/DuckHunt_pistola.nes`. Porta 1: controle padrão. Porta 2: **controle padrão**, com A e B no teclado.
2. **Confira a RAM com bateria:** em CALIBRATION, mude K com Cima/Baixo. Feche o jogo e abra de novo: o valor tem que continuar. O Mesen cria um arquivo `.sav` com o nome da ROM na pasta de saves.
3. Para testar o tiro no teclado, **reduza a velocidade de emulação** para 10–25%. Toque B e segure A quando o quadrado branco aparecer: deve dar acerto. Toque B sem A: erro. Segure A o tempo todo: erro.

### 3. Pistola no CRT

1. Por USB: título, CALIBRATION, mire na TV e aperte Start (ou atire na TV). Anote K e N.
2. Faça 20 tiros mirando no pato e 20 mirando no chão ou no céu. O esperado é 20 acertos e 0 acertos.
3. Se precisar, ajuste com o direcional seguindo a tabela acima. Recalibre ao trocar para Bluetooth.

> **Importante:** o ESP32 só pode mandar A e B na porta 2. No Game A, o direcional do controle 2 pilota o pato (rotina em `$CA7C`).

## Pendências (confirmar no Mesen)

- **RAM com bateria no mapper 0:** confirmar que o Mesen respeita o cabeçalho NES 2.0 e salva o `.sav` (teste 2.2 acima). Se não salvar, o patch continua funcionando, só sem guardar K e N.
- **Code/Data Logger:** jogar Game A, B e C, o título e um game over, e confirmar que `$EF60-$F2F7`, `$FF30-$FFDF` e os três trechos mortos nunca são executados nem lidos pelo código original, e que `$07E0-$07FF` nunca é acessado por ele.

Já resolvido no código: o "modo `$24≠0`" é o **tiro na tela de título** (acerto = começar, erro = próxima opção), e o Game C usa a mesma rotina de flash (`$1F = 2`).
