/*
  Revolver do Duck Hunt - firmware da pistola
  Placa: ESP32-S3 Super Mini  (Arduino IDE: "ESP32S3 Dev Module")

  A pistola aparece no PC/Raspberry como um CONTROLE (gamepad), no controle 2.
  Dois protocolos (escolha em PROTOCOLO, conforme a ROM):

    PROTOCOLO 1 - ROM V4 (o jogo decide o acerto)
      Botao 1 (A) = luz detectada pelo sensor (continuo)
      Botao 2 (B) = gatilho (pulso de 50 ms)

    PROTOCOLO 2 - ROM V5 (a pistola decide o acerto; ver PROTOCOLO_NOVO.md)
      B (pulso de 50 ms)       = gatilho
      A (pulso de 50 ms)       = acertou (Game A) / acertou o 1o alvo (Game B/C)
      A + B (pulso de 50 ms)   = acertou o 2o alvo (Game B/C), no MESMO relatorio
      nada                     = errou (o jogo ja conta erro sozinho)
      A pistola olha a piscada da TV: 2 pretos, 2 quadros de quadrado, 1 preto
      (Game B/C: + 2 quadros do 2o quadrado e 1 preto) e decide sozinha.

  Ligacoes (iguais ao esquema eletrico do projeto):
    GPIO1 (ADC1) <- emissor do TEPT4400 + resistor 10k para o GND
    GPIO2        <- microswitch do gatilho (outro terminal no GND)
    GPIO3 (ADC1) <- divisor 100k/100k das pilhas (opcional)

  Bibliotecas:
    Bluetooth: "ESP32-BLE-Gamepad" (lemmingDev) + "NimBLE-Arduino" (h2zero)
    Cabo USB : ja vem no pacote esp32 da Espressif
               (Ferramentas > USB Mode: "USB-OTG (TinyUSB)")

  Monitor serial (115200):
    ">> A / B"          -> cada mudanca dos botoes e se foi enviada
    "### TIRO"          -> (protocolo 2) resumo de cada tiro: sincronia, ida, pulsos, decisao
    "### BLUETOOTH"     -> estado da conexao (desconectado / sem pareamento seguro / CONECTADO)
    Comandos: 'd' liga/desliga a linha detalhada do sensor (a cada 100 ms),
              '+'/'-' ajusta a sensibilidade,
              't' (protocolo 2) modo teste: decide e mostra no serial, mas nao manda A nem A + B,
              'b' reinicia em modo de gravacao (sem apertar BOOT/RST).
*/

#include <Arduino.h>
#include <stdint.h>

// ======================= CONFIGURACAO =======================
#define USAR_BLUETOOTH  1      // 1 = sem fio (BLE)   0 = cabo USB
#define PROTOCOLO       2      // 1 = ROM V4 (A = luz continua)   2 = ROM V5 (a pistola decide)

const int PINO_SENSOR  = 1;
const int PINO_GATILHO = 2;
const int PINO_BATERIA = -1;    // 3 se montar o divisor 100k/100k; -1 = sem divisor (informa 100%)

int   DELTA_LUZ        = 300;   // quanto a leitura precisa subir acima da linha de base (0-4095)
const uint32_t SEGURA_LUZ_MS   = 20;    // (protocolo 1) "segura" a luz depois de cada pulso do CRT
const uint32_t DEBOUNCE_MS     = 5;     // filtro do microswitch
const uint32_t PULSO_B_MS      = 50;    // duracao do "aperto" de B a cada tiro (~3 quadros)
const uint32_t DORMIR_APOS_MS  = 10UL * 60UL * 1000UL;  // dorme apos 10 min parada
const float    BAT_CHEIA_V     = 4.6f;  // 3x AA alcalinas novas
const float    BAT_VAZIA_V     = 3.4f;  // abaixo disso o regulador nao segura 3,3 V
const float    BAT_CORRECAO    = 1.00f; // ajuste fino comparando com um multimetro

// Intervalo de conexao Bluetooth pedido ao Recalbox, em unidades de 1,25 ms.
// O Linux usa 30-50 ms se a pistola nao pedir nada; cada envio espera o proximo
// "encontro" de conexao, entao intervalo menor = botoes chegam mais cedo.
// 6..12 = 7,5..15 ms. Se a conexao ficar instavel (Pi 3B+ com Wi-Fi ligado), use 12..24.
const uint16_t BLE_INTERVALO_MIN = 6;
const uint16_t BLE_INTERVALO_MAX = 12;

// Protocolo 2 (ver PROTOCOLO_NOVO.md)
const uint32_t QUADRO_US      = 16667;   // 1 quadro da TV (60 Hz)
const uint32_t PULSO_MSG_MS   = 50;      // A / A + B ficam apertados ~3 quadros
const uint32_t IDA_INICIAL_US = 150000;  // gatilho -> 1o quadro preto na TV, antes de medir
const uint32_t SURDEZ_US      = 3000;    // depois de um pulso do tubo, ignora ~3 ms (1 pulso por quadro)
const uint32_t BLOQUEIO_US    = 160000;  // depois de t0 + 8 quadros, ainda ignora o gatilho
// =============================================================

#include "esp_sleep.h"
#include "driver/rtc_io.h"
#include "soc/rtc_cntl_reg.h"

#if USAR_BLUETOOTH
  #include <BleGamepad.h>
  #include <NimBLEDevice.h>
  BleGamepad gamepad("Revolver Duck Hunt", "DIY", 100);
#else
  #include "USB.h"
  #include "USBHIDGamepad.h"
  USBHIDGamepad gamepad;
#endif

// ---- estado ----
float    linhaBase   = 0;     // nivel de luz "normal" (ambiente + tela), acompanhado devagar
uint32_t ultimaLuz   = 0;
bool     saidaA      = false; // o que esta sendo mandado agora
bool     saidaB      = false;
bool     gatilhoBruto = false;
uint32_t mudouGatilho = 0;
uint32_t ultimaAtividade = 0;
uint32_t ultimoDebug = 0, ultimaBateria = 0;
bool     debug = false;          // 'd' no monitor serial liga a linha detalhada a cada 100 ms
int      leituraMax = 0;

// ---------------- saida para o gamepad ----------------
// A e B vao SEMPRE no mesmo relatorio HID (o jogo nunca ve um sem o outro no A + B).
// Envia PRIMEIRO e so depois escreve no monitor serial: a mensagem nunca atrasa o botao.
void enviar(bool a, bool b) {
#if USAR_BLUETOOTH
  bool ok = gamepad.isConnected();
  if (ok) {
    a ? gamepad.press(BUTTON_1) : gamepad.release(BUTTON_1);
    b ? gamepad.press(BUTTON_2) : gamepad.release(BUTTON_2);
    gamepad.sendReport();
  }
  Serial.printf(">> A: %s | B: %s | %s\n", a ? "APERTADO" : "solto   ", b ? "APERTADO" : "solto   ",
                ok ? "enviado por Bluetooth" : "NAO ENVIADO (Bluetooth sem conexao HID)");
#else
  uint32_t botoes = (a ? 0x01 : 0) | (b ? 0x02 : 0);
  gamepad.send(0, 0, 0, 0, 0, 0, 0, botoes);         // um relatorio so, com os dois botoes
  Serial.printf(">> A: %s | B: %s | enviado por USB\n",
                a ? "APERTADO" : "solto   ", b ? "APERTADO" : "solto   ");
#endif
}

// ---------------- MODO MAPEAMENTO (configurar o controle no Recalbox) ----------------
// Ligue a pistola SEGURANDO o gatilho por 3 s. Nesse modo:
//   luz no sensor        -> botao 1 (A)
//   puxada LONGA (>1 s)  -> botao 2 (B)
//   puxada CURTA         -> botoes "falsos" 3, 4, 5... (para direcional, Start, Select, hotkey)
// Desligue e ligue de novo para voltar ao modo normal.
bool    modoMapa = false;
uint8_t proximoFalso = 3;

void pulsoBotao(uint8_t n) {
#if USAR_BLUETOOTH
  if (!gamepad.isConnected()) {
    Serial.printf("[mapa] botao %d NAO ENVIADO (Bluetooth sem conexao HID)\n", n);
    return;
  }
  gamepad.press(n);   gamepad.sendReport(); delay(250);
  gamepad.release(n); gamepad.sendReport();
#else
  gamepad.pressButton(n - 1); delay(250); gamepad.releaseButton(n - 1);
#endif
  Serial.printf("[mapa] botao %d\n", n);
}

// =============================================================
//  PROTOCOLO 2: a pistola decide o acerto
// =============================================================
// Historico dos pulsos do tubo (instante em micros, 1 por quadro quando o ponto esta claro)
const int N_PULSOS = 64;
uint32_t pulsos[N_PULSOS];
int      iPulso = 0, nPulsos = 0;
uint32_t ultimoPulsoUs = 0;

// "Ida" = do gatilho ate o 1o quadro preto na TV. Media das ultimas medicoes.
uint32_t idaMedidas[8];
int      nIda = 0, iIda = 0;
uint32_t idaUs = IDA_INICIAL_US;

bool     modoTeste = false;      // 't': decide mas nao manda A / A + B
uint32_t msgAAte = 0, msgBAte = 0;  // millis ate quando A / B (da mensagem) ficam apertados

enum { SYNC_PROCURANDO = 0, SYNC_CEU = 1, SYNC_ESTIMADA = 2, SYNC_FALHOU = 3 };
enum { DEC_NADA = 0, DEC_A = 1, DEC_AB = 2 };

struct Tiro {
  bool     ativo;
  uint32_t tGat;          // instante do gatilho (micros)
  bool     temT0;
  uint32_t t0;            // instante do 1o quadro preto na TV (micros)
  uint8_t  sync;
  bool     luzPreto, luzJ1, luzJ2, luzQ7;   // luz nos quadros 0-1, 2-3, 5-6 e 7 da piscada
  uint8_t  decidiu;
  uint32_t enviouUs;
  uint8_t  nRel;
  int16_t  rel[12];       // quadro (contado a partir de t0) de cada pulso visto, para o log
} tiro;

void guardaPulso(uint32_t t) {
  pulsos[iPulso] = t;
  iPulso = (iPulso + 1) % N_PULSOS;
  if (nPulsos < N_PULSOS) nPulsos++;
  ultimoPulsoUs = t;
}

void guardaIda(uint32_t ida) {
  idaMedidas[iIda] = ida;
  iIda = (iIda + 1) % 8;
  if (nIda < 8) nIda++;
  uint64_t soma = 0;
  for (int i = 0; i < nIda; i++) soma += idaMedidas[i];
  idaUs = (uint32_t)(soma / nIda);
}

// Em qual quadro da piscada caiu um pulso (0, 1 = preto; 2, 3 = 1o quadrado; 4 = preto;
// 5, 6 = 2o quadrado; 7 = preto) e marca as janelas.
void classificaPulso(uint32_t tp) {
  int32_t d = (int32_t)(tp - tiro.t0);
  if (d < -(int32_t)(QUADRO_US / 2)) return;
  int k = (d + (int32_t)(QUADRO_US / 2)) / (int32_t)QUADRO_US;
  if (tiro.nRel < 12) tiro.rel[tiro.nRel++] = (int16_t)k;
  if (k <= 1)                tiro.luzPreto = true;
  else if (k <= 3)           tiro.luzJ1 = true;
  else if (k == 5 || k == 6) tiro.luzJ2 = true;
  else if (k == 7)           tiro.luzQ7 = true;
}

void defineT0(uint32_t t0, uint8_t sync) {
  tiro.t0 = t0;
  tiro.temT0 = true;
  tiro.sync = sync;
  // olha para tras no historico: pulsos que ja chegaram depois de t0
  for (int i = 0; i < nPulsos; i++) {
    uint32_t p = pulsos[(iPulso - 1 - i + N_PULSOS) % N_PULSOS];
    if ((int32_t)(p - t0) >= -(int32_t)(QUADRO_US / 2)) classificaPulso(p);
  }
  // sem sincronia pelo ceu, so vale se onde devia haver preto estava mesmo escuro;
  // senao a estimativa esta errada (e a luz seria o ceu): nao arrisca acerto falso
  if (sync == SYNC_ESTIMADA && tiro.luzPreto) {
    tiro.sync = SYNC_FALHOU;
    nIda = 0;                 // a ida guardada nao serve mais (trocou USB/BT?): reaprende no proximo tiro
    iIda = 0;
    idaUs = IDA_INICIAL_US;
  }
}

void mandaMensagem(uint8_t tipo, uint32_t agoraUs, uint32_t agoraMs) {
  tiro.decidiu = tipo;
  tiro.enviouUs = agoraUs;
  if (modoTeste) return;
  msgAAte = agoraMs + PULSO_MSG_MS;
  if (tipo == DEC_AB) msgBAte = agoraMs + PULSO_MSG_MS;
}

void comecaTiro(uint32_t agoraUs) {
  memset(&tiro, 0, sizeof(tiro));
  tiro.ativo = true;
  tiro.tGat = agoraUs;
}

void logTiro() {
  static const char* nomeSync[] = { "nenhuma", "ceu", "estimada", "FALHOU (luz onde devia haver preto)" };
  static const char* nomeDec[]  = { "nada (errou)", "A (acertou / alvo 1)", "A+B (alvo 2)" };
  Serial.printf("### TIRO | sincronia: %s | t0-gatilho: %.1f ms | ida estimada: %.1f ms (%d medicoes) | pulsos nos quadros:",
                nomeSync[tiro.sync], tiro.temT0 ? (int32_t)(tiro.t0 - tiro.tGat) / 1000.0f : -1.0f,
                idaUs / 1000.0f, nIda);
  for (int i = 0; i < tiro.nRel; i++) Serial.printf(" %d", tiro.rel[i]);
  Serial.printf(" | decisao: %s", nomeDec[tiro.decidiu]);
  if (tiro.decidiu) Serial.printf(" em t0+%.1f ms", (int32_t)(tiro.enviouUs - tiro.t0) / 1000.0f);
  Serial.printf("%s\n", modoTeste ? " | MODO TESTE (nao enviado)" : "");
}

void cuidaDoTiro(uint32_t agoraUs, uint32_t agoraMs) {
  if (!tiro.ativo) return;
  const int32_t F = (int32_t)QUADRO_US;

  if (!tiro.temT0) {
    // 1) inicio do preto: o ultimo pulso (ponto claro) foi seguido de 2 quadros sem pulso.
    //    Antes da 1a medicao aceita qualquer um depois do pulso do gatilho; depois, so
    //    perto da ida medida (-2..+3 quadros): o pato passando sob a mira nao engana.
    if (ultimoPulsoUs != 0 && (int32_t)(agoraUs - ultimoPulsoUs) > F * 5 / 2) {
      uint32_t c = ultimoPulsoUs + QUADRO_US;
      int32_t rel = (int32_t)(c - tiro.tGat);
      bool perto = nIda == 0 || (rel >= (int32_t)idaUs - 2 * F && rel <= (int32_t)idaUs + 3 * F);
      if (rel > 3 * F && perto) {
        defineT0(c, SYNC_CEU);
        guardaIda((uint32_t)rel);
      }
    }
    // 2) sem sincronia ate passar a janela: usa gatilho + ida e confere o historico.
    //    So com ida ja medida: sem medicao nao ha estimativa confiavel (aprende no ceu).
    if (!tiro.temT0 && nIda > 0 && (int32_t)(agoraUs - tiro.tGat) >= (int32_t)idaUs + 5 * F) {
      defineT0(tiro.tGat + idaUs, SYNC_ESTIMADA);
    }
  }

  if (tiro.temT0 && tiro.sync != SYNC_FALHOU && tiro.decidiu == DEC_NADA) {
    int32_t d = (int32_t)(agoraUs - tiro.t0);
    // 3) janela 1 (quadros 2-3): primeira luz -> A, na hora
    if (tiro.luzJ1 && d < 8 * F) mandaMensagem(DEC_A, agoraUs, agoraMs);
    // 4) janela 2 (quadros 5-6) com o quadro 7 escuro -> A + B. No Game A a cena volta
    //    no quadro 5; mirando no ceu a luz continua no 7, e isso NAO e acerto.
    else if (d >= F * 15 / 2 && d < 8 * F && tiro.luzJ2 && !tiro.luzQ7) mandaMensagem(DEC_AB, agoraUs, agoraMs);
  }

  // 5) fim do tiro (e do bloqueio do gatilho)
  uint32_t fim = tiro.temT0 ? tiro.t0 + 8 * QUADRO_US + BLOQUEIO_US : tiro.tGat + 600000;
  if ((int32_t)(agoraUs - fim) >= 0) {
    logTiro();
    tiro.ativo = false;
  }
}

// ---------------- bateria ----------------
int nivelBateria() {
  if (PINO_BATERIA < 0) return 100;
  uint32_t mv = 0;
  for (int i = 0; i < 8; i++) mv += analogReadMilliVolts(PINO_BATERIA);
  float v = (mv / 8.0f) / 1000.0f * 2.0f * BAT_CORRECAO;   // divisor 100k/100k
  float p = (v - BAT_VAZIA_V) / (BAT_CHEIA_V - BAT_VAZIA_V) * 100.0f;
  return constrain((int)p, 0, 100);
}

// ---------------- USB ligada no computador? ----------------
bool usbConectado() {
#if ARDUINO_USB_MODE && ARDUINO_USB_CDC_ON_BOOT
  return Serial.isConnected();       // true quando o PC esta "conversando" com a placa
#else
  return false;
#endif
}

// ---------------- reinicia direto no modo de gravacao (comando 'b') ----------------
void modoGravacao() {
  Serial.println("Entrando no modo de gravacao... pode enviar o programa pela IDE.");
  delay(100);
  REG_WRITE(RTC_CNTL_OPTION1_REG, RTC_CNTL_FORCE_DOWNLOAD_BOOT);
  esp_restart();
}

// ---------------- sono profundo ----------------
void dormir() {
  Serial.println("Dormindo... puxe o gatilho para acordar.");
  delay(50);
  rtc_gpio_pullup_en((gpio_num_t)PINO_GATILHO);
  rtc_gpio_pulldown_dis((gpio_num_t)PINO_GATILHO);
  esp_sleep_enable_ext0_wakeup((gpio_num_t)PINO_GATILHO, 0);   // acorda com o gatilho em LOW
  esp_deep_sleep_start();
}

void setup() {
  Serial.begin(115200);
  pinMode(PINO_GATILHO, INPUT_PULLUP);
  analogReadResolution(12);
  analogSetPinAttenuation(PINO_SENSOR, ADC_11db);
  if (PINO_BATERIA >= 0) analogSetPinAttenuation(PINO_BATERIA, ADC_11db);

#if USAR_BLUETOOTH
  // Anuncia um controle "completo" (16 botoes, direcional e 2 eixos) para o
  // Recalbox/Linux reconhecer como joystick. Na pratica so os botoes 1 e 2 sao usados;
  // eixos e direcional ficam sempre centralizados.
  BleGamepadConfiguration cfg;
  cfg.setControllerType(CONTROLLER_TYPE_GAMEPAD);
  cfg.setButtonCount(16);
  cfg.setHatSwitchCount(1);
  cfg.setWhichAxes(true, true, false, false, false, false, false, false);   // X e Y
  cfg.setAxesMin(-32767);
  cfg.setAxesMax(32767);                 // 0 = centro
  cfg.setAutoReport(false);              // so envia quando algo muda (menos atraso/consumo)
  gamepad.begin(&cfg);
#else
  gamepad.begin();
  USB.begin();
#endif

  // gatilho segurado por 3 s ao ligar -> modo mapeamento
  if (digitalRead(PINO_GATILHO) == LOW) {
    uint32_t t0 = millis();
    while (digitalRead(PINO_GATILHO) == LOW && millis() - t0 < 3000) delay(10);
    if (millis() - t0 >= 3000) {
      modoMapa = true;
      Serial.println("MODO MAPEAMENTO: luz = botao 1 | puxada longa = botao 2 | puxada curta = 3, 4, 5...");
      while (digitalRead(PINO_GATILHO) == LOW) delay(10);   // espera soltar
    }
  }

  // linha de base inicial: media de leituras com a pistola parada
  long soma = 0;
  for (int i = 0; i < 200; i++) { soma += analogRead(PINO_SENSOR); delayMicroseconds(200); }
  linhaBase = soma / 200.0f;
  ultimaAtividade = millis();
  Serial.printf("Revolver do Duck Hunt pronto. Modo: %s | Protocolo %d (%s)\n",
                modoMapa ? "MAPEAMENTO" : "normal", PROTOCOLO,
                PROTOCOLO == 2 ? "ROM V5: a pistola decide o acerto" : "ROM V4: A = luz");
}

void loop() {
  uint32_t agora = millis();
  uint32_t agoraUs = micros();

  // ---------- sensor de luz ----------
  int leitura = analogRead(PINO_SENSOR);
  if (leitura > leituraMax) leituraMax = leitura;
  bool pulso = leitura > linhaBase + DELTA_LUZ;
  static uint32_t ultimoBase = 0;
  static bool acima = false;
  if (pulso) {
    ultimaLuz = agora;
    // borda de subida de um pulso do tubo (1 por quadro): guarda o instante
    if (!acima && (ultimoPulsoUs == 0 || agoraUs - ultimoPulsoUs > SURDEZ_US)) {
      guardaPulso(agoraUs);
      if (tiro.ativo && tiro.temT0) classificaPulso(agoraUs);
    }
  } else if (agora != ultimoBase) {
    // acompanha devagar (~0,5 s) a luz ambiente / brilho medio da tela, 1x por ms,
    // para nao "engolir" o flash do quadrado branco
    ultimoBase = agora;
    linhaBase += (leitura - linhaBase) * 0.002f;
  }
  acima = pulso;

  // ---------- gatilho (com filtro) ----------
  static bool gatilhoEstavel = false;
  static uint32_t pulsoAte = 0, puxouEm = 0;
  bool g = digitalRead(PINO_GATILHO) == LOW;
  if (g != gatilhoBruto) { gatilhoBruto = g; mudouGatilho = agora; }
  if (agora - mudouGatilho >= DEBOUNCE_MS && gatilhoBruto != gatilhoEstavel) {
    gatilhoEstavel = gatilhoBruto;
    ultimaAtividade = agora;
    if (modoMapa) {
      if (gatilhoEstavel) puxouEm = agora;
      else if (agora - puxouEm > 1000) pulsoBotao(2);                 // puxada longa = B
      else { pulsoBotao(proximoFalso); if (++proximoFalso > 16) proximoFalso = 3; }
    } else if (gatilhoEstavel) {          // acabou de puxar: gera um pulso curto em B
#if PROTOCOLO == 2
      if (tiro.ativo) {
        Serial.println("(gatilho ignorado: tiro anterior ainda em andamento)");
      } else {
        pulsoAte = agora + PULSO_B_MS;
        comecaTiro(agoraUs);
      }
#else
      pulsoAte = agora + PULSO_B_MS;
#endif
    }
  }
  // o jogo dispara quando o bit do gatilho volta a 0, como na Zapper real:
  // por isso B fica apertado so durante o pulso, mesmo segurando o gatilho
  bool gatilho = (int32_t)(pulsoAte - agora) > 0;

  // ---------- o que mandar ----------
  bool a, b;
#if PROTOCOLO == 2
  cuidaDoTiro(micros(), agora);
  a = (int32_t)(msgAAte - agora) > 0;
  b = gatilho || (int32_t)(msgBAte - agora) > 0;
#else
  a = (agora - ultimaLuz) < SEGURA_LUZ_MS && ultimaLuz != 0;   // luz, "segurada" entre pulsos
  b = gatilho;
#endif

  // ---------- envia so quando muda ----------
  if (a != saidaA || b != saidaB) {
    saidaA = a;
    saidaB = b;
    enviar(saidaA, saidaB);
  }

  // ---------- avisa quando o Bluetooth conecta/desconecta ----------
#if USAR_BLUETOOTH
  // 0 = sem conexao | 1 = conexao aberta, mas o host NAO completou o pareamento seguro
  // 2 = conectado como controle (pareado e criptografado: os botoes chegam)
  static int estadoPrev = -1;
  static uint32_t entrouEstado = 0, ultimoPedido = 0;
  static int pedidos = 0;
  static bool intervaloPedido = false, intervaloInformado = false;
  NimBLEServer* srv = NimBLEDevice::getServer();

  // Seguranca: pede pareamento COM chaves guardadas (bonding), sem PIN, com Secure Connections.
  // Sem isso o Linux/Recalbox pareia mas nao cria o controle (fica "Bonded: no").
  static bool segurancaOk = false;
  if (!segurancaOk && srv) {
    NimBLEDevice::setSecurityAuth(true, false, true);          // bonding, sem MITM, Secure Connections
    NimBLEDevice::setSecurityIOCap(BLE_HS_IO_NO_INPUT_OUTPUT);  // "Just Works" (sem PIN)
    NimBLEDevice::setSecurityInitKey(BLE_SM_PAIR_KEY_DIST_ENC | BLE_SM_PAIR_KEY_DIST_ID);
    NimBLEDevice::setSecurityRespKey(BLE_SM_PAIR_KEY_DIST_ENC | BLE_SM_PAIR_KEY_DIST_ID);
    segurancaOk = true;
    Serial.println("### Seguranca: pareamento com chaves guardadas (bonding) ativado");
  }
  int links = srv ? srv->getConnectedCount() : 0;
  int estado = gamepad.isConnected() ? 2 : (links > 0 ? 1 : 0);
  if (estado != estadoPrev) {
    estadoPrev = estado;
    entrouEstado = agora;
    pedidos = 0;
    intervaloPedido = intervaloInformado = false;
    if (estado == 2) {
      bool bonded = srv && links > 0 && srv->getPeerInfo(0).isBonded();
      Serial.printf("### BLUETOOTH: CONECTADO como controle | chaves guardadas (bonded): %s\n",
                    bonded ? "SIM" : "NAO - o Recalbox nao vai criar o controle");
    }
    else if (estado == 1) Serial.println("### BLUETOOTH: conexao aberta, MAS SEM PAREAMENTO SEGURO (o host nao terminou o pareamento)");
    else                  Serial.println("### BLUETOOTH: desconectado (aguardando o Recalbox)");
    if (estado == 2) enviar(saidaA, saidaB);   // manda o estado atual ao conectar
  }
  // conectado sem pareamento seguro: a PISTOLA pede o pareamento ao Recalbox
  // (1 s depois de conectar e de novo a cada 5 s, ate 5 tentativas)
  if (estado == 1 && srv && pedidos < 5 && agora - entrouEstado > 1000 &&
      (pedidos == 0 || agora - ultimoPedido > 5000)) {
    ultimoPedido = agora;
    pedidos++;
    NimBLEConnInfo peer = srv->getPeerInfo(0);
    NimBLEDevice::startSecurity(peer.getConnHandle());
    Serial.printf("### Pedindo pareamento seguro ao Recalbox (tentativa %d de 5)...\n", pedidos);
  }
  // conectado como controle: 1 s depois pede o intervalo curto; 3 s depois mostra o
  // intervalo que o Recalbox aceitou (o Linux guarda e usa nas proximas conexoes)
  if (estado == 2 && srv && links > 0) {
    if (!intervaloPedido && agora - entrouEstado > 1000) {
      intervaloPedido = true;
      NimBLEConnInfo peer = srv->getPeerInfo(0);
      Serial.printf("### Intervalo de conexao atual: %.2f ms. Pedindo %.2f a %.2f ms...\n",
                    peer.getConnInterval() * 1.25f,
                    BLE_INTERVALO_MIN * 1.25f, BLE_INTERVALO_MAX * 1.25f);
      // latencia 0 = a pistola responde em todo encontro; timeout 200 x 10 ms = 2 s
      srv->updateConnParams(peer.getConnHandle(), BLE_INTERVALO_MIN, BLE_INTERVALO_MAX, 0, 200);
    }
    if (intervaloPedido && !intervaloInformado && agora - entrouEstado > 3000) {
      intervaloInformado = true;
      float ms = srv->getPeerInfo(0).getConnInterval() * 1.25f;
      Serial.printf("### Intervalo de conexao agora: %.2f ms %s\n", ms,
                    ms <= BLE_INTERVALO_MAX * 1.25f ? "(OK)" : "(o Recalbox NAO aceitou o pedido)");
    }
  }
#endif

  // ---------- bateria (a cada 30 s) ----------
#if USAR_BLUETOOTH
  if (agora - ultimaBateria > 30000) {
    ultimaBateria = agora;
    gamepad.setBatteryLevel(nivelBateria());
  }
#endif

  // ---------- comandos e debug pelo monitor serial ----------
  while (Serial.available()) {
    char c = Serial.read();
    if (c == 'd') debug = !debug;
    if (c == 'b') modoGravacao();
    if (c == '+') { DELTA_LUZ = max(20, DELTA_LUZ - 20); Serial.printf("DELTA_LUZ = %d (mais sensivel)\n", DELTA_LUZ); }
    if (c == '-') { DELTA_LUZ += 20; Serial.printf("DELTA_LUZ = %d (menos sensivel)\n", DELTA_LUZ); }
    if (c == 't') { modoTeste = !modoTeste;
                    Serial.printf("MODO TESTE %s (decide, mas %s A / A+B)\n", modoTeste ? "LIGADO" : "desligado",
                                  modoTeste ? "NAO manda" : "manda"); }
  }
  if (debug && agora - ultimoDebug > 100) {
    ultimoDebug = agora;
    Serial.printf("leitura max=%4d  base=%4.0f  limiar=%4.0f  A=%d  B=%d  tiro=%d  ida=%.0f ms\n",
                  leituraMax, linhaBase, linhaBase + DELTA_LUZ, saidaA, saidaB, tiro.ativo, idaUs / 1000.0f);
    leituraMax = 0;
  }

  // ---------- economia de pilha ----------
  // nunca dorme ligada no computador (assim a IDE sempre encontra a porta)
  if (usbConectado()) ultimaAtividade = agora;
  if (agora - ultimaAtividade > DORMIR_APOS_MS) dormir();
}
