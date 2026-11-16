/*
  Revolver do Duck Hunt - firmware da pistola
  Placa: ESP32-S3 Super Mini  (Arduino IDE: "ESP32S3 Dev Module")

  A pistola aparece no PC/Raspberry como um CONTROLE (gamepad):
    Botao 1 (A) = luz detectada pelo sensor
    Botao 2 (B) = gatilho
  O patch da ROM le esses dois botoes no lugar da Zapper.

  Ligacoes (iguais ao esquema eletrico do projeto):
    GPIO1 (ADC1) <- emissor do TEPT4400 + resistor 10k para o GND
    GPIO2        <- microswitch do gatilho (outro terminal no GND)
    GPIO3 (ADC1) <- divisor 100k/100k das pilhas (opcional)

  Bibliotecas:
    Bluetooth: "ESP32-BLE-Gamepad" (lemmingDev) + "NimBLE-Arduino" (h2zero)
    Cabo USB : ja vem no pacote esp32 da Espressif
               (Ferramentas > USB Mode: "USB-OTG (TinyUSB)")

  Monitor serial (115200):
    ">> LUZ / GATILHO"  -> cada mudanca e se foi enviada pelo Bluetooth
    "### BLUETOOTH"     -> estado da conexao (desconectado / sem pareamento seguro / CONECTADO)
    Comandos: 'd' liga/desliga a linha detalhada do sensor (a cada 100 ms),
              '+'/'-' ajusta a sensibilidade,
              'b' reinicia em modo de gravacao (sem apertar BOOT/RST).
*/

#include <Arduino.h>
#include <stdint.h>

// ======================= CONFIGURACAO =======================
#define USAR_BLUETOOTH  1      // 1 = sem fio (BLE)   0 = cabo USB

const int PINO_SENSOR  = 1;
const int PINO_GATILHO = 2;
const int PINO_BATERIA = -1;    // 3 se montar o divisor 100k/100k; -1 = sem divisor (informa 100%)

int   DELTA_LUZ        = 300;   // quanto a leitura precisa subir acima da linha de base (0-4095)
const uint32_t SEGURA_LUZ_MS   = 20;    // "segura" a luz depois de cada pulso do CRT
const uint32_t DEBOUNCE_MS     = 5;     // filtro do microswitch
const uint32_t PULSO_B_MS      = 50;    // duracao do "aperto" de B a cada tiro (~3 quadros)
const uint32_t DORMIR_APOS_MS  = 10UL * 60UL * 1000UL;  // dorme apos 10 min parada
const float    BAT_CHEIA_V     = 4.6f;  // 3x AA alcalinas novas
const float    BAT_VAZIA_V     = 3.4f;  // abaixo disso o regulador nao segura 3,3 V
const float    BAT_CORRECAO    = 1.00f; // ajuste fino comparando com um multimetro

// Intervalo de conexao Bluetooth pedido ao Recalbox, em unidades de 1,25 ms.
// O Linux usa 30-50 ms se a pistola nao pedir nada; cada envio espera o proximo
// "encontro" de conexao, entao intervalo menor = luz/gatilho chegam mais cedo.
// 6..12 = 7,5..15 ms. Se a conexao ficar instavel (Pi 3B+ com Wi-Fi ligado), use 12..24.
const uint16_t BLE_INTERVALO_MIN = 6;
const uint16_t BLE_INTERVALO_MAX = 12;
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
bool     luzAtual    = false;
bool     gatilhoAtual = false;
bool     gatilhoBruto = false;
uint32_t mudouGatilho = 0;
uint32_t ultimaAtividade = 0;
uint32_t ultimoDebug = 0, ultimaBateria = 0;
bool     debug = false;          // 'd' no monitor serial liga a linha detalhada a cada 100 ms
int      leituraMax = 0;

// ---------------- saida para o gamepad ----------------
// Envia PRIMEIRO e so depois escreve no monitor serial: a mensagem nunca atrasa o botao.
void enviar(bool luz, bool gatilho) {
#if USAR_BLUETOOTH
  bool ok = gamepad.isConnected();
  if (ok) {
    luz     ? gamepad.press(BUTTON_1) : gamepad.release(BUTTON_1);
    gatilho ? gamepad.press(BUTTON_2) : gamepad.release(BUTTON_2);
    gamepad.sendReport();
  }
  Serial.printf(">> LUZ: %s | GATILHO: %s | %s\n",
                luz ? "ACIONADA" : "apagada ", gatilho ? "ACIONADO" : "solto   ",
                ok ? "enviado por Bluetooth" : "NAO ENVIADO (Bluetooth sem conexao HID)");
#else
  luz     ? gamepad.pressButton(0) : gamepad.releaseButton(0);
  gatilho ? gamepad.pressButton(1) : gamepad.releaseButton(1);
  Serial.printf(">> LUZ: %s | GATILHO: %s | enviado por USB\n",
                luz ? "ACIONADA" : "apagada ", gatilho ? "ACIONADO" : "solto   ");
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
  Serial.printf("Revolver do Duck Hunt pronto. Modo: %s\n", modoMapa ? "MAPEAMENTO" : "normal");
}

void loop() {
  uint32_t agora = millis();

  // ---------- sensor de luz ----------
  int leitura = analogRead(PINO_SENSOR);
  if (leitura > leituraMax) leituraMax = leitura;
  bool pulso = leitura > linhaBase + DELTA_LUZ;
  static uint32_t ultimoBase = 0;
  if (pulso) {
    ultimaLuz = agora;
  } else if (agora != ultimoBase) {
    // acompanha devagar (~0,5 s) a luz ambiente / brilho medio da tela, 1x por ms,
    // para nao "engolir" o flash do quadrado branco
    ultimoBase = agora;
    linhaBase += (leitura - linhaBase) * 0.002f;
  }
  bool luz = (agora - ultimaLuz) < SEGURA_LUZ_MS && ultimaLuz != 0;

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
      pulsoAte = agora + PULSO_B_MS;
    }
  }
  // o jogo dispara quando o bit do gatilho volta a 0, como na Zapper real:
  // por isso B fica apertado so durante o pulso, mesmo segurando o gatilho
  bool gatilho = (int32_t)(pulsoAte - agora) > 0;

  // ---------- envia so quando muda ----------
  if (luz != luzAtual || gatilho != gatilhoAtual) {
    luzAtual = luz;
    gatilhoAtual = gatilho;
    enviar(luzAtual, gatilhoAtual);
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
    if (estado == 2) enviar(luzAtual, gatilhoAtual);   // manda o estado atual ao conectar
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
  }
  if (debug && agora - ultimoDebug > 100) {
    ultimoDebug = agora;
    Serial.printf("leitura max=%4d  base=%4.0f  limiar=%4.0f  luz=%d  gatilho=%d\n",
                  leituraMax, linhaBase, linhaBase + DELTA_LUZ, luzAtual, gatilhoAtual);
    leituraMax = 0;
  }

  // ---------- economia de pilha ----------
  // nunca dorme ligada no computador (assim a IDE sempre encontra a porta)
  if (usbConectado()) ultimaAtividade = agora;
  if (agora - ultimaAtividade > DORMIR_APOS_MS) dormir();
}