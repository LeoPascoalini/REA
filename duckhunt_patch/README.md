# Duck Hunt (NES): patch para pistola de luz caseira

Patch IPS que faz o Duck Hunt ler a pistola caseira (TEPT4400 + ESP32-S3) como um **controle padrão na porta 2**, **estica o flash do tiro** para compensar o atraso entre emulador, USB/Bluetooth e CRT, e acrescenta um item **CALIBRATION** no menu para ajustar esse atraso dentro do jogo.

- **Botão A** = luz detectada (vira o bit 3 = 0 da Zapper)
- **Botão B** = gatilho (vira o bit 4 = 1 da Zapper). O firmware manda um pulso de 50 ms (`PULSO_B_MS`).
- O flash tem uma etapa preta de N quadros e uma etapa de N quadros por alvo. A luz só é conferida depois dos K primeiros quadros de cada etapa.
- K e N ficam salvos na **RAM extra com bateria** (`$6000`), igual ao save de um jogo, e são ajustados pelo menu.
- Pontuação, sons, IA dos patos e o restante do menu não foram alterados.

ROM alvo: **Duck Hunt (World)**, NROM-128 (16 KB PRG + 8 KB CHR), **CRC32 da ROM sem cabeçalho `24598791`**. Use o dump do seu cartucho. Se o CRC bater, os bytes são idênticos.

## Como usar o menu CALIBRATION

Na tela de título, o **Select** do controle 1 (ou um **tiro fora da TV**, como no jogo original) passa por:

```
  > GAME A   1 DUCK
    GAME B   2 DUCKS
    GAME C   CLAY SHOOTING
    CALIBRATION
     K=07  N=10          <- aparece no lugar do TOP SCORE quando CALIBRATION está selecionado
```

Com **CALIBRATION** selecionado:

| Ação | Efeito |
|---|---|
| **Start** no controle 1, ou **tiro na TV** | Calibração automática. Mire a pistola na TV: a tela pisca preto/branco 6 vezes (~3 s) e volta ao título com os novos K e N. |
| **Cima / Baixo** | K +1 / −1 (N acompanha) |
| **Direita / Esquerda** | N +1 / −1 (N fica sempre maior que K) |

Tudo é salvo na hora. Também dá para usar o menu só com a pistola: tiro fora da TV troca a opção, tiro na TV escolhe. No tiro do título, o jogo original acende a tela inteira, então basta mirar na TV.

**O que a calibração mede**, em quadros:
- **subida**: quanto tempo o sensor demora para ver a luz depois que a tela fica branca;
- **descida**: quanto tempo demora para deixar de ver depois que a tela fica preta. Esse valor já inclui os 20 ms que o firmware segura o A.

Com o maior valor de cada um em 6 piscadas:
- **K = maior descida + 1**
- **N = max(K, maior subida) + 3**

Se o sensor não mudar em 1,5 s (pistola fora da TV ou sensor sempre aceso), a calibração é cancelada e os valores antigos ficam. Na primeira vez, ou se a RAM estiver corrompida, os valores padrão são **K=7, N=10**.

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
| `$C1DF-$C1E1` | `0x001EF` | `AD FE 05` | `4C 9C F0` | Linha do TOP SCORE: mostra K e N no modo 3 e ajuste pelo direcional |
| `$C5C8-$C5CA` | `0x005D8` | `20 17 C6` | `20 68 F0` | Desenho do título + lista nova com "CALIBRATION" (`$22E8`) |
| `$C82B-$C82D` | `0x0083B` | `AD FE 05` | `20 81 F0` | Segurança: o modo 3 nunca vira partida |
| `$EF60-$F274` | `0x02F70` | `FF` × 789 | código novo (789 bytes) | Rotinas novas no bloco livre `$EF5A-$F2FF` |

A conversão é offset = endereço − `$C000` + `$10`. O NROM tem um banco só, então o código novo está no mesmo banco que o chamador. Os trechos originais de resultado do tiro (`$D22D` para acerto, `$D28A` para erro), o desenhista de listas (`$C617`) e a fila de escrita na PPU (`$C71D`) são reaproveitados sem alteração.

**Registro do cabeçalho:** reescreve os bytes 6 a 15 inteiros. Assim o resultado é um NES 2.0 consistente, mesmo que o dump tenha cabeçalho iNES 1.0. Ele também troca o acessório padrão de Zapper para controles padrão, para o Mesen não colocar a Zapper na porta 2 sozinho.

### RAM extra (`$6000`)

| Endereço | Conteúdo |
|---|---|
| `$6000-$6001` | Marca `'D' 'H'` |
| `$6002` / `$6003` | K / N |
| `$6004` | Soma de verificação (K xor N xor `$5A`) |
| `$6005-$6009` | Uso temporário (direcional anterior, medições da calibração) |

## Como gerar e aplicar

```powershell
cd C:\Users\leopa\Desktop\REA\duckhunt_patch
python build.py "C:\caminho\do\seu\dump.nes"
```

O script:
1. confere o cabeçalho (NROM-128) e o CRC32;
2. confere os bytes originais em cada endereço e que o código novo cai só em `$FF`;
3. gera o `.ips`, aplica numa cópia (`build/DuckHunt_pistola.nes`) e confirma que nenhum byte mudou fora da tabela.

**A ROM original nunca é escrita.**

Para aplicar no seu dump: copie o arquivo e aplique `dist/duckhunt_pistola.ips` na cópia com o **Floating IPS** ou o **Rom Patcher JS**. Também pode usar direto a cópia `build/DuckHunt_pistola.nes`.

CRC32 esperado da cópia patcheada, sem cabeçalho: **`01368767`**.

## Calibração manual: o que cada valor faz

- **K** precisa cobrir o atraso máximo mais a "segura" de 20 ms do sensor. Com os valores padrão (K=7), o atraso aceito vai de 0 a 5 quadros.
- **N − K** é o número de quadros conferidos em cada etapa. Com **N ≥ K + 3** há folga para variação de atraso.
- Duração do flash: Game A ≈ 2N quadros, Game B ≈ 3N.

| Sintoma | Causa provável | Ajuste no menu |
|---|---|---|
| Todo tiro dá erro, mesmo mirando certo (pior com céu claro) | K curto: o sensor ainda vê o céu na parte conferida da etapa preta | Cima (K+1) |
| No Game B, mirando no pato 1, o jogo conta acerto no pato 2 | K curto: o quadrado 1 ainda está no tubo quando começa a etapa do pato 2 | Cima |
| Acertos falham de vez em quando, sem padrão | N − K pequeno para a variação de atraso (comum no Bluetooth) | Direita (N+1) |
| Tiro às vezes não sai | Pulso do gatilho curto | Suba `PULSO_B_MS` para 80–100 ms no firmware |
| Flash longo e incômodo | N maior que o necessário | Esquerda (N−1) |

## Testes

### 1. Simuladores (sem emulador)

```powershell
python -P test_flash.py "C:\caminho\do\seu\dump.nes" build\DuckHunt_pistola.nes --n 10 --k 7
python -P test_menu.py build\DuckHunt_pistola.nes
```

**`test_flash.py`** (25 casos) testa:
- tiro com atraso de 0 a 5 quadros;
- sem luz;
- A apertado o tempo todo;
- mira fora do pato;
- Game B mirando em cada pato, e com só o pato 2 voando;
- Game C;
- tiro no título;
- pulsos de gatilho de 50 a 100 ms;
- o limite de atraso que N e K aguentam.

**`test_menu.py`** (41 casos, ~2 min) roda o jogo inteiro desde o RESET e testa:
- a linha CALIBRATION e o cursor nas 4 opções;
- K e N na tela;
- o ajuste manual e os limites;
- a RAM com bateria (desligar/ligar, RAM com lixo);
- a calibração com atraso de 0, 2, 3, 5 e 8 quadros, que deve dar exatamente K = L+3 e N = K+3;
- a calibração cancelada (pistola fora da TV, sensor sempre aceso);
- a navegação só com a pistola;
- 30 s parado no título sem iniciar partida;
- uma partida do Game A com acerto no pato depois de calibrar.

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

- **RAM com bateria no mapper 0:** confirmar que o Mesen respeita o cabeçalho NES 2.0 e salva o `.sav` (teste 2.2 acima). Isso não dá para verificar no simulador.
- **Code/Data Logger:** jogar Game A, B e C, o título e um game over, e confirmar que `$EF60-$F274` nunca é executado nem lido pelo código original.

Já resolvido no código: o "modo `$24≠0`" é o **tiro na tela de título** (acerto = começar, erro = próxima opção), e o Game C usa a mesma rotina de flash (`$1F = 2`).
