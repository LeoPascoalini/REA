# Nova lógica de tiro da pistola (Duck Hunt) — especificação para o firmware

## Contexto
- Firmware: `pistola.ino` (ESP32-S3 Super Mini). Sensor TEPT4400 no GPIO1 (ADC, 10k para o GND), gatilho no GPIO2.
  A pistola é um gamepad HID por Bluetooth (BLE, ESP32-BLE-Gamepad + NimBLE) ou USB (USBHIDGamepad), conforme `USAR_BLUETOOTH`.
- Ela é o **controle 2** de um NES emulado (RetroArch no Recalbox, Raspberry Pi 3B+), ligado a uma TV de tubo
  (HDMI → conversor → VGA). Um quadro de TV = 16,67 ms. O emulador lê o controle 1 vez por quadro.
- Hoje: botão 1 (A) = "vejo luz" (contínuo, com `SEGURA_LUZ_MS` = 20 ms), botão 2 (B) = gatilho (pulso de 50 ms).
  O jogo decide o acerto olhando o A durante uma piscada longa (~220 ms).
- **Novo:** a pistola decide sozinha se acertou, olhando a sequência de luz que a TV mostra, e só avisa o jogo.
  O jogo (patch novo da ROM, feito à parte) mostra uma piscada curta e fixa e NUNCA espera a pistola:
  depois da piscada ele já conta erro, e só derruba o pato se chegar um "acertou" dentro de ~150 ms.

## Protocolo de botões (controle 2) — usar SÓ A e B
| Pistola manda | Quando | Significa |
|---|---|---|
| B (pulso 50 ms) | ao puxar o gatilho | tiro (igual a hoje) |
| A (pulso 50 ms) | depois do tiro | acertou (Game A) / acertou o pato 1 (Game B/C) |
| A + B juntos (pulso 50 ms) | depois do tiro | acertou o pato 2 (Game B/C) |
| nada | | errou |

- **Não usar Start, Select nem direcional.** No Recalbox o Select é Hotkey (Hotkey + Start fecha o jogo),
  e o direcional do controle 2 pilota o pato no jogo.
- O botão A deixa de significar "vejo luz": **parar de enviar a luz contínua**.
- A + B precisam sair **no mesmo relatório HID** (nunca um relatório com A e outro com B):
  - BLE: `press(BUTTON_1); press(BUTTON_2); sendReport();` (autoReport já está desligado).
  - USB: `pressButton()` envia um relatório por chamada. Use um envio único com a máscara completa de botões
    (por exemplo `gamepad.send(x, y, z, rz, rx, ry, hat, buttons)`).
- Cada pulso: segurar 50 ms (≥ 3 quadros, para o emulador não perder) e soltar tudo.

## O que a TV mostra depois do tiro
A piscada começa ~3 a 6 quadros depois do gatilho (varia com USB/BT e o emulador). Contando a partir do
1º quadro preto (quadro 0):

    Game A:      0 P | 1 P | 2 Q | 3 Q | 4 P | 5+ cena normal
    Game B / C:  0 P | 1 P | 2 Q1 | 3 Q1 | 4 P | 5 Q2 | 6 Q2 | 7 P | 8+ cena normal

P = tela preta, Q = quadrado branco no pato (Q1 = pato 1, Q2 = pato 2). A pistola NÃO sabe se é Game A ou B;
as regras abaixo funcionam para os dois.

## Como a pistola enxerga isso
Na TV de tubo o feixe passa pelo ponto mirado 1 vez por quadro: quando o ponto está claro, o sensor dá
**um pulso curto por quadro** (~16,67 ms entre pulsos). Quadro escuro = pulso que não veio.
- Detecte pulsos como hoje (`leitura > linhaBase + DELTA_LUZ`), mas registre o **instante de cada pulso**
  (`micros()`, borda de subida, com ~3 ms de "surdez" depois de cada pulso para contar 1 por quadro).
- Não use mais `SEGURA_LUZ_MS` para decidir; trabalhe com os instantes dos pulsos.

## Algoritmo por tiro (F = 16,67 ms)
1. **Gatilho** (borda, com debounce): manda o pulso de B. Guarda `tGat`. Entra no estado TIRO.
   Enquanto estiver em TIRO e no bloqueio (passo 6), **ignore novos gatilhos**.
2. **Achar o início do preto (`t0`)**:
   - Se havia pulsos regulares antes (mira em ponto claro, ex. céu): `t0` = instante do 1º pulso que **faltou**
     (último pulso + F) depois de `tGat`. Ou seja, foi detectado um intervalo > 1,5 F sem pulso.
     Nesse caso, meça `ida = t0 - tGat` e atualize uma estimativa (média ou mediana das últimas ~8 medições;
     valor inicial 70 ms).
   - Se estava escuro (mira em ponto escuro, ex. corpo do pato): `t0 = tGat + idaEstimada`.
3. **Janela 1** = pulsos entre `t0 + 1,5F` e `t0 + 3,5F` (quadros 2-3).
   No **primeiro pulso** dentro dela → manda **A** imediatamente (acertou / pato 1). Fim da decisão.
4. **Janela 2** = pulsos entre `t0 + 4,5F` e `t0 + 6,5F` (quadros 5-6), **e** nenhum pulso entre
   `t0 + 6,5F` e `t0 + 7,5F` (quadro 7 escuro). Só depois de confirmar o quadro 7 escuro → manda **A + B**
   (pato 2). A confirmação é obrigatória: no Game A a cena volta no quadro 5, e se a mira estiver no céu a
   luz é longa (não para no quadro 7). Isso NÃO é acerto.
5. Se nenhuma janela deu acerto até `t0 + 7,5F` → **não manda nada** (errou).
   Luz fora das janelas (céu voltando) é sempre ignorada.
6. **Bloqueio**: só saia do estado TIRO (aceitar novo gatilho) depois de `t0 + 8F + 160 ms`.
   Se nunca sincronizou e nada aconteceu: saia 450 ms depois de `tGat`
   (o jogo pode ter ignorado o tiro, por exemplo sem balas).
7. Nunca mande A ou A + B depois de `t0 + 8F` (o jogo só aceita até ~150 ms depois da piscada).

## Manter como está
- Pulso de B de 50 ms no gatilho, debounce do gatilho, modo mapeamento (só A e B importam),
  sono profundo, bateria, pedido de intervalo BLE curto (`BLE_INTERVALO_MIN/MAX`),
  e "enviar o relatório antes de imprimir no serial".

## Compatibilidade
- A ROM atual (V4) ainda usa o protocolo antigo (A = luz contínua).
  Coloque a lógica nova atrás de `#define PROTOCOLO 2` (1 = antigo, 2 = novo), para gravar o protocolo certo
  conforme a ROM.

## Diagnóstico pelo serial (115200)
A cada tiro, uma linha com: `tGat`, tipo de sincronia (céu / estimada), `t0 - tGat`, idaEstimada,
instantes dos pulsos relativos a `t0` (em ms e em quadros), decisão (A, A+B, nada) e o instante do envio.
Um comando `'t'` liga um **modo teste**: faz tudo, mas não envia A nem A + B (só B), só registra.
Serve para validar na TV antes de a ROM nova existir.

## Como testar
- Mirando no céu, com a ROM atual em modo teste: a sincronia "céu" precisa achar `t0` em todos os tiros,
  e `ida` deve ficar estável (variação < 1 quadro no USB).
- Game A no pato: A sai ~1 quadro depois do início do quadrado. No céu: nada.
- Game B: pato 1 → A; pato 2 → A + B ~3 quadros depois de `t0 + 5F`; céu → nada.
  No Game A mirando no céu, NUNCA pode sair A + B.
