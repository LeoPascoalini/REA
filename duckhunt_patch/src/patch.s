; =============================================================================
;  Duck Hunt (NES, NROM-128) - patch para pistola de luz caseira
;
;  - Troca a leitura da Zapper pela de um controle padrão na porta 2:
;      botão A = luz detectada   ->  bit 3 = 0 (igual à Zapper)
;      botão B = gatilho         ->  bit 4 = 1 (igual à Zapper)
;  - Estica o flash do tiro: etapa preta e etapa de cada alvo duram N quadros,
;    e a luz só é conferida depois dos K primeiros quadros de cada etapa
;    (compensa o atraso emulador -> USB/BT -> CRT).
;  - Novo item "CALIBRATION" no menu (4a opção):
;      Start ou tiro na tela -> calibração automática (pisca branco/preto e mede)
;      Cima/Baixo            -> K +1/-1 (N acompanha)
;      Esquerda/Direita      -> N -1/+1
;    K e N ficam salvos na RAM extra com bateria ($6000), declarada no cabeçalho
;    pelo build.py, e aparecem na linha do TOP SCORE quando o item está
;    selecionado. Em uso, valem as cópias na RAM interna ($07E0): sem RAM com
;    bateria o patch funciona igual, só não guarda os valores ao desligar.
;
;  ROM alvo: Duck Hunt (World), CRC32 da ROM sem cabeçalho = 24598791
;  Montador: ca65 + ld65 (cc65), usando src/patch.cfg
; =============================================================================

.setcpu "6502"

; -----------------------------------------------------------------------------
;  VALORES PADRÃO E LIMITES  (usados quando a RAM extra está vazia/inválida)
; -----------------------------------------------------------------------------
;  K = quadros que o sensor leva para PARAR de ver luz (+ folga): quadros
;      ignorados no começo da etapa preta e da etapa do pato 2.
;  N = quadros que o sensor leva para COMEÇAR a ver luz (+ folga): duração da
;      etapa do 1o alvo, que é conferida desde o 1o quadro.
;  Flash: preta = K + CONF_PRETO ; 1o alvo = N ; pato 2 = max(K + 3, N)
K_PADRAO    = 7
N_PADRAO    = 8
K_MAX       = 60
N_MIN       = 2
N_MAX       = 99        ; dois dígitos na tela
CONF_PRETO  = 2         ; quadros conferidos (sem luz) no fim da etapa preta
CONF_PATO2  = 3         ; quadros conferidos, no mínimo, na etapa do pato 2

; Calibração automática
CICLOS_CAL  = 6         ; quantas vezes pisca branco/preto
ESPERA_MAX  = 90        ; quadros (1,5 s) esperando o sensor mudar; depois disso, erro
MARGEM_K    = 2         ; K = maior descida + MARGEM_K (K curto custa caro; K longo só alonga o flash)
MARGEM_N    = 3         ; N = maior subida + MARGEM_N
ASSENTA     = 6         ; quadros extras parados em cada cor antes de trocar
COR_PRETA   = $0F
COR_BRANCA  = $30

;  S = nível de sombra: em vez de apagar a tela, o tiro mostra o cenário com as
;      cores escurecidas (0 = tela preta, como o jogo original; 1 = bem escuro;
;      2 = escuro; 3 = meio escuro, só para teste manual). Cada nível tira
;      (4 - S) linhas de brilho de cada cor da paleta do cenário.
S_PADRAO    = 0
S_MAX       = 3
; Teste de sombra (roda depois da calibração automática)
SOMBRA_REPETE = 3       ; tentativas que cada nível precisa passar
CEU_QUADROS = 30        ; quadros de "céu" antes de cada tentativa (como no jogo)
COR_CEU     = $21       ; azul do céu do jogo

; -----------------------------------------------------------------------------
;  Hardware
; -----------------------------------------------------------------------------
PPUMASK     = $2001
PPUSTATUS   = $2002
PPUADDR     = $2006
PPUDATA     = $2007
APUSTATUS   = $4015
JOY1        = $4016     ; escrever aqui faz o strobe das DUAS portas
JOY2        = $4017     ; leitura serial do controle 2

; -----------------------------------------------------------------------------
;  RAM do jogo (confirmada no disassembly)
; -----------------------------------------------------------------------------
sombraMask  = $09       ; cópia do PPUMASK mantida pelo jogo
botoes1     = $16       ; controle 1 com debounce: A B Sel Start Cima Baixo Esq Dir
flagNMI     = $20       ; o NMI ($C0AA) põe 1
modoJogo    = $1F       ; 0 = Game A, 1 = Game B, 2 = Game C (durante a partida)
listaTela   = $23       ; NMI desenha a lista n-1 da tabela $E532 (1 = paleta do título)
alvo        = $B0       ; 0 = pato 1, 1 = pato 2, 2 = tiro na tela de título
bufPPU      = $0500     ; buffer [linhas<<4 | largura] + tiles, enfileirado por $C71D
modoMenu    = $05FE     ; 0 = Game A, 1 = Game B, 2 = Game C, 3 = CALIBRATION (novo)
pato2Ativo  = $0350
pato2Estado = $0351
VOANDO      = $03

; -----------------------------------------------------------------------------
;  RAM extra ($6000-$7FFF, com bateria) - só existe com o cabeçalho do patch.
;  Serve apenas para GUARDAR K/N entre sessões. Se o emulador/cartucho não tiver
;  essa RAM, as leituras dão lixo (barramento aberto) e o patch segue com a
;  cópia da RAM interna abaixo.
; -----------------------------------------------------------------------------
cfgMarca0   = $6000     ; 'D'
cfgMarca1   = $6001     ; 'J'
cfgK        = $6002
cfgN        = $6003
cfgSoma     = $6004     ; K xor N xor S xor $5A
cfgS        = $6005
MARCA0      = $44       ; 'D'
MARCA1      = $4A       ; 'J' = versão 3 (com S). Versões anteriores ('H': N = K + 3;
                        ; 'I': sem S) voltam ao padrão.

; -----------------------------------------------------------------------------
;  RAM interna livre ($07E0-$07E8): a página $0700 não é usada pelo jogo
;  (nenhuma referência na ROM e nenhum acesso nos Games A/B/C no simulador).
;  ramK/ramN são os valores EM USO; toda a lógica lê daqui.
; -----------------------------------------------------------------------------
ramMarca    = $07E0     ; 'D' se ramK/ramN já foram preenchidos nesta sessão
ramK        = $07E1
ramN        = $07E2
ramSoma     = $07E3     ; K xor N xor $5A
dirAnterior = $07E4     ; direcional do quadro anterior (para detectar borda)
calSobe     = $07E5     ; maior atraso medido escuro -> claro
calDesce    = $07E6     ; maior atraso medido claro -> escuro
calCiclos   = $07E7
calMask     = $07E8
ignora      = $07E9     ; quadros ignorados no começo da etapa atual do flash
durEtapa    = $07EA     ; duração da etapa atual do flash
ramS        = $07EB     ; nível de sombra em uso
escCor      = $07EC     ; temporário de Escurece
sombraAtiva = $07ED     ; 1 = este tiro está usando a sombra
somNivel    = $07EE     ; nível sendo testado no teste de sombra
metade      = $07EF     ; temporário de EnfileiraMetade
paletaSombra = $07F0    ; $07F0-$07FF: paleta do cenário escurecida (16 cores)

; Paletas do cenário na ROM (dados das listas 2 e 3 da tabela $E532, depois do
; cabeçalho 3F 00 20): as 16 primeiras cores são as do fundo.
PAL_AB      = $E55B     ; Game A/B
PAL_C       = $E57F     ; Game C

; -----------------------------------------------------------------------------
;  Rotinas do jogo reaproveitadas (não são alteradas)
; -----------------------------------------------------------------------------
LimpaFlags   = $C61E    ; zera $20 e $22 (só mexe em A)
EsperaNMI    = $C5D9    ; zera $20/$22 e espera o próximo NMI
LimpaOAM     = $C23B
DesenhaAlvo  = $D292    ; Y = $00 (pato 1) ou $50 (pato 2): quadrado no buffer
TrataAcerto  = $D22D    ; acerto do alvo em $B0
TrataFim     = $D28A    ; com A = $B0: erro / sem acerto
DesenhaLista = $C617    ; X/Y = ponteiro de uma lista de strings de PPU
EnfileiraPPU = $C71D    ; X/Y = endereço PPU (baixo/alto), dados em bufPPU
TXT_TOP     = $E4ED     ; "TOP SCORE =" (11 tiles) dentro da lista do título
VoltaJogo   = $C17A     ; resto do início de partida original (STA $25 ...)
VoltaPlacar = $C1E2     ; resto do desenho do TOP SCORE original (ASL A ...)
FimPlacar   = $C217     ; depois do desenho do TOP SCORE


; =============================================================================
;  ALTERAÇÕES NO CÓDIGO ORIGINAL
; =============================================================================

; --- Pistola e flash -----------------------------------------------------------

; $D131: era AD 17 40 (LDA $4017, gatilho da Zapper). Mesmo tamanho.
.segment "P_D131"
        jsr LerZapper

; $D1C7: era JSR $D292 / JSR $C61E. $D1C7 vem de $D1B3 (alvo escolhido) e
; $D1CA do BNE em $D19D (tiro na tela de título, sem quadrado).
.segment "P_D1C7"
        jmp FlashComQuadrado    ; $D1C7
        jmp FlashSemQuadrado    ; $D1CA

; --- Menu -------------------------------------------------------------------

; $C176: era A9 00 85 (LDA #$00 / STA $24): Start ou tiro na tela no título.
; O byte $C179 ($24) fica sem uso; nada salta para ele.
.segment "P_C176"
        jmp IniciaJogo

; $C19D CPY #$03 -> CPY #$04: o Select (ou tiro fora da tela) passa por 4 opções.
.segment "P_C19E"
        .byte $04

; $C1BF LDA #$51 -> #$71: cursor numa coluna de 7 linhas (linhas 17 a 23).
.segment "P_C1C0"
        .byte $71

; $C1C6 LDX #$04 -> #$06: preenche as 7 posições da coluna do cursor.
.segment "P_C1C7"
        .byte $06

; $C1DF: era AD FE 05 (LDA $05FE), início do TOP SCORE (roda a cada quadro).
.segment "P_C1DF"
        jmp PlacarTitulo

; $C5C8: era 20 17 C6 (JSR $C617), desenho da tela de título.
.segment "P_C5C8"
        jsr DesenhaTitulo

; $C82B: era AD FE 05 (LDA $05FE), modo copiado para $1F no início da partida.
.segment "P_C82B"
        jsr LeModoJogo


; =============================================================================
;  ROTINAS NOVAS  ($EF60, espaço livre preenchido com $FF)
; =============================================================================
.segment "NOVO"

; -----------------------------------------------------------------------------
;  LerZapper - lê o controle 2 e devolve A no formato da Zapper.
;    bit 3 = 0 se o botão A (luz) estiver apertado, 1 se não
;    bit 4 = 1 se o botão B (gatilho) estiver apertado
;  Preserva X e Y.
; -----------------------------------------------------------------------------
LerZapper:
        lda #$01
        sta JOY1
        lda #$00
        sta JOY1
        lda JOY2                ; 1a leitura serial = botão A
        and #$03                ; bit 0 (controle) ou bit 1 (expansão Famicom)
        beq @semLuz
        lda #$00                ; luz: bit 3 = 0
        beq @leGatilho          ; (sempre salta)
@semLuz:
        lda #$08                ; sem luz: bit 3 = 1
@leGatilho:
        pha
        lda JOY2                ; 2a leitura serial = botão B
        and #$03
        beq @semGatilho
        pla
        ora #$10                ; gatilho: bit 4 = 1
        rts
@semGatilho:
        pla
        rts

; -----------------------------------------------------------------------------
;  CarregaConfig - deixa ramK/ramN válidos. Ordem de preferência:
;    1) RAM com bateria ($6000) válida  -> copia para a RAM interna
;    2) cópia interna válida (sessão)   -> mantém (caso sem RAM com bateria)
;    3) senão                           -> K_PADRAO / N_PADRAO
;  e grava o resultado nas duas cópias.
;  SalvaConfig - grava ramK/ramN, com marca e soma, na RAM interna e na com
;  bateria (sem RAM com bateria a gravação some, sem problema).
;  Ambas preservam X e Y.
; -----------------------------------------------------------------------------
CarregaConfig:
        lda cfgMarca0
        cmp #MARCA0
        bne @semNV
        lda cfgMarca1
        cmp #MARCA1
        bne @semNV
        lda cfgK                ; marca certa: copia o que está salvo e confere
        sta ramK                ; a soma junto com a cópia da RAM interna
        lda cfgN
        sta ramN
        lda cfgS
        sta ramS
        lda cfgSoma
        sta ramSoma
        bcs @confere            ; (sempre salta: C = 1 depois do CMP igual)
@semNV:
        lda ramMarca
        cmp #MARCA0
        bne @padrao
@confere:
        jsr SomaRam
        cmp ramSoma
        bne @padrao
        lda ramK
        beq @padrao             ; K = 0 inválido
        cmp #K_MAX+1
        bcs @padrao
        lda ramS
        cmp #S_MAX+1
        bcs @padrao
        lda ramN
        cmp #N_MIN
        bcc @padrao
        cmp #N_MAX+1
        bcc SalvaConfig
@padrao:
        lda #K_PADRAO
        sta ramK
        lda #N_PADRAO
        sta ramN
        lda #S_PADRAO
        sta ramS
SalvaConfig:
        lda #MARCA0
        sta ramMarca
        sta cfgMarca0
        lda #MARCA1
        sta cfgMarca1
        lda ramK
        sta cfgK
        lda ramN
        sta cfgN
        lda ramS
        sta cfgS
        jsr SomaRam
        sta ramSoma
        sta cfgSoma
        rts

SomaRam:                        ; A = K xor N xor S xor $5A
        lda ramK
        eor ramN
        eor ramS
        eor #$5A
        rts

; -----------------------------------------------------------------------------
;  Quadro - espera um quadro inteiro (até o próximo NMI) conferindo a luz.
;  Entrada: Y = número do quadro dentro da etapa (1..durEtapa)
;  Saída:   C = 1 -> luz vista (só confere quando Y > ignora)
;           C = 0 -> o quadro acabou sem luz (ou ainda era quadro ignorado)
;  Preserva X e Y.
; -----------------------------------------------------------------------------
Quadro:
        jsr LimpaFlags          ; $20 = 0 e $22 = 0 (igual ao original)
@espera:
        lda flagNMI
        bne @fimQuadro          ; NMI chegou: fim do quadro
        cpy ignora
        bcc @espera             ; Y < ignora: ignorado
        beq @espera             ; Y = ignora: ignorado
        jsr LerZapper
        and #$08
        bne @espera             ; bit 3 = 1: sem luz
        lda flagNMI             ; se o NMI chegou durante a leitura, ela já é
        bne @fimQuadro          ; do quadro seguinte: descarta
        sec                     ; luz!
        rts
@fimQuadro:
        clc
        rts

; -----------------------------------------------------------------------------
;  FlashComQuadrado / FlashSemQuadrado - substitui $D1C7-$D290.
;  Ao chegar aqui a tela já está toda desligada ($D185 -> $C5E1).
; -----------------------------------------------------------------------------
FlashComQuadrado:               ; Y = $00 ou $50, alvo = 0 ou 1
        jsr DesenhaAlvo         ; quadrado no buffer (invisível: tela desligada)

FlashSemQuadrado:               ; alvo = 2 entra direto aqui
        jsr CarregaConfig
        lda #$00
        sta sombraAtiva
        ; ---- Etapa preta: K + CONF_PRETO quadros. Os K primeiros são ignorados
        ; (o sensor ainda vê o céu); nos últimos não pode haver luz.
        lda ramK
        sta ignora
        clc
        adc #CONF_PRETO
        sta durEtapa
        ldy #$01
@preto:
        jsr Quadro
        bcs Falhou              ; luz com a tela preta -> erro (original: $D1D8)
        cpy #$01
        bne @semSombra
        jsr LigaSombra          ; fim do 1o quadro: o jogo acabou de pôr a paleta
@semSombra:                     ; toda preta; com S > 0 entra o cenário escurecido
        cpy durEtapa
        beq @fimPreto
        iny
        bne @preto              ; (sempre salta)
@fimPreto:
        ; ---- Liga só os sprites (ou só o fundo no título): original $D1F7-$D20B
        lda sombraMask
        and #$E7
        ldy alvo
        cpy #$02
        beq @soFundo
        ora #$10                ; sprites (o quadrado)
        ldy sombraAtiva
        beq @gravaMask
        ora #$08                ; + o cenário escurecido
        bne @gravaMask          ; (sempre salta)
@soFundo:
        ora #$08                ; só fundo
@gravaMask:
        sta sombraMask
        sta PPUMASK

        ; ---- 1o alvo: N quadros, conferidos desde o 1o. A etapa preta já
        ; garantiu que o sensor está no escuro, então qualquer luz agora só pode
        ; vir do quadrado (ou da tela, no tiro do título).
        lda #$00
        sta ignora
        lda ramN
        sta durEtapa
EtapaAlvo:
        ldy #$01
@quadro:
        cpy durEtapa
        bne @semTroca
        jsr PreparaPato2        ; último quadro: põe o quadrado do pato 2 no
@semTroca:                      ; buffer, para ele entrar no quadro seguinte
        jsr Quadro
        bcs Acertou
        cpy durEtapa
        beq @fimEtapa
        iny
        bne @quadro             ; (sempre salta)
@fimEtapa:
        jsr TemPato2            ; acabou a etapa do pato 1; falta o pato 2?
        bne Falhou
        lda #$01                ; Game B: agora testa o pato 2 (original $D280)
        sta alvo
        ; ---- Pato 2: ignora K quadros (o sensor ainda pode ver o quadrado do
        ; pato 1) e dura max(K + CONF_PATO2, N).
        lda ramK
        sta ignora
        clc
        adc #CONF_PATO2
        cmp ramN
        bcs @durPato2
        lda ramN
@durPato2:
        sta durEtapa
        jmp EtapaAlvo

Acertou:
        jmp TrataAcerto

Falhou:
        lda alvo
        jmp TrataFim

; Z = 1 se o alvo atual é o pato 1 e o pato 2 também está voando. Só mexe em A.
TemPato2:
        lda alvo
        bne @nao
        lda pato2Ativo
        beq @nao
        lda pato2Estado
        cmp #VOANDO             ; Z = 1 se voando
        rts
@nao:
        lda #$01                ; Z = 0
        rts

; Se houver pato 2, troca o quadrado no buffer de sprites. Preserva Y.
PreparaPato2:
        jsr TemPato2
        bne @fim
        tya
        pha
        jsr LimpaOAM
        ldy #$50
        jsr DesenhaAlvo
        pla
        tay
@fim:
        rts

; =============================================================================
;  MENU
; =============================================================================

; Desenha a tela de título original e acrescenta a linha "CALIBRATION".
; Entra com X/Y = $E404 (carregados em $C5C4), como o JSR $C617 original.
DesenhaTitulo:
        jsr DesenhaLista
        ldx #<ListaCalibration
        ldy #>ListaCalibration
        jmp DesenhaLista

.segment "MORTO1"          ; (trecho morto/livre, ver patch.cfg)
ListaCalibration:               ; mesmo formato das listas do jogo
        .byte $22, $E8, $0B     ; PPU $22E8 = linha 23, coluna 8; 11 tiles
        .byte $0C, $0A, $15, $12, $0B, $1B, $0A, $1D, $12, $18, $17   ; CALIBRATION
        .byte $00               ; fim da lista

.segment "NOVO"

.segment "MORTO3"          ; (trecho morto/livre, ver patch.cfg)
; Início da partida ($C82B): o modo 3 nunca vira partida (segurança).
LeModoJogo:
        lda modoMenu
        cmp #$03
        bcc @ok
        lda #$00
@ok:
        rts

.segment "NOVO"

; Start ou tiro na tela de título ($C176).
IniciaJogo:
        lda modoMenu
        cmp #$03
        bne @partida
        jmp Calibracao
@partida:
        lda #$00                ; original: LDA #$00 / STA $24 / STA $25 ...
        sta $24
        jmp VoltaJogo

; Linha do TOP SCORE, a cada quadro do título ($C1DF).
PlacarTitulo:
        jsr CarregaConfig
        lda modoMenu
        cmp #$03
        beq @config
        ldx #10                 ; modos 0-2: rótulo original "TOP SCORE ="
@copia:
        lda TXT_TOP,x
        sta bufPPU+1,x
        dex
        bpl @copia
        jsr EnfileiraRotulo
        lda modoMenu
        jmp VoltaPlacar         ; segue o desenho original dos 6 dígitos

@config:                        ; modo 3: " K=07  N=08" + " S=1  " no lugar do placar
        jsr AjusteManual
        lda #$24                ; espaço
        sta bufPPU+1
        sta bufPPU+6
        sta bufPPU+7
        lda #$14                ; K
        sta bufPPU+2
        lda #$17                ; N
        sta bufPPU+8
        lda #$27                ; =
        sta bufPPU+3
        sta bufPPU+9
        lda ramK
        jsr DoisDigitos
        stx bufPPU+4
        sty bufPPU+5
        lda ramN
        jsr DoisDigitos
        stx bufPPU+10
        sty bufPPU+11
        jsr EnfileiraRotulo
        lda #$16                ; 1 linha x 6 tiles no lugar dos dígitos do placar
        sta bufPPU
        lda #$24
        ldx #5
@limpa:
        sta bufPPU+1,x
        dex
        bpl @limpa
        lda #$1C                ; S
        sta bufPPU+2
        lda #$27                ; =
        sta bufPPU+3
        lda ramS
        sta bufPPU+4
        ldx #$12
        ldy #$23
        jsr EnfileiraPPU        ; PPU $2312
        jmp FimPlacar

EnfileiraRotulo:                ; 11 tiles de bufPPU+1 em PPU $2307
        lda #$1B
        sta bufPPU
        ldx #$07
        ldy #$23
        jmp EnfileiraPPU

.segment "MORTO3"          ; (trecho morto/livre, ver patch.cfg)
; A = 0..99  ->  X = dezena, Y = unidade (tiles $00-$09 são os dígitos)
DoisDigitos:
        ldx #$00
@dez:
        cmp #10
        bcc @fim
        sbc #10                 ; C = 1 garantido pelo CMP
        inx
        bne @dez                ; (sempre salta)
@fim:
        tay
        rts

.segment "NOVO"

; Cima/Baixo: K +1/-1 (1..K_MAX).  Direita/Esquerda: N +1/-1 (N_MIN..N_MAX).
; A: S = 0, 1, 2, 3, 0...
AjusteManual:
        lda botoes1
        and #$8F                ; A ... Cima Baixo Esq Dir
        pha
        eor dirAnterior         ; o que mudou...
        sta dirAnterior
        pla
        pha
        and dirAnterior         ; ...e está apertado agora (borda)
        tax
        pla
        sta dirAnterior         ; guarda o estado atual
        txa
        bpl @naoA               ; bit 7 = A
        jsr ProximoS
        txa
@naoA:
        lsr a                   ; Direita
        bcc @naoDir
        tax
        lda ramN
        cmp #N_MAX
        bcs @x1
        inc ramN
@x1:
        txa
@naoDir:
        lsr a                   ; Esquerda
        bcc @naoEsq
        tax
        lda ramN
        cmp #N_MIN+1
        bcc @x2                 ; N mínimo = N_MIN
        dec ramN
@x2:
        txa
@naoEsq:
        lsr a                   ; Baixo
        bcc @naoBaixo
        tax
        lda ramK
        cmp #2
        bcc @x3                 ; K mínimo = 1
        dec ramK
@x3:
        txa
@naoBaixo:
        lsr a                   ; Cima
        bcc @fim
        lda ramK
        cmp #K_MAX
        bcs @fim
        inc ramK
@fim:
        jmp SalvaConfig

; =============================================================================
;  CALIBRAÇÃO AUTOMÁTICA
;  A tela fica desligada (só a cor de fundo $3F00) e alterna preto/branco.
;  Mede, em quadros, quanto o sensor demora para ver a luz depois que a tela
;  fica branca (calSobe) e para deixar de ver depois que fica preta (calDesce).
;  Resultado: K = maior calDesce + MARGEM_K ; N = maior calSobe + MARGEM_N
;  Se o sensor não mudar em ESPERA_MAX quadros, aborta sem mudar nada.
; =============================================================================
Calibracao:
        jsr CarregaConfig
        lda sombraMask
        sta calMask
        lda #$00
        sta APUSTATUS           ; silencia o som durante a medição
        sta calSobe
        sta calDesce
        lda #CICLOS_CAL
        sta calCiclos
        jsr QuadroLuz           ; sincroniza: estamos logo após um NMI
        lda #$00
        sta PPUMASK             ; tela desligada: mostra só a cor de fundo
        lda #COR_PRETA
        jsr PoeCorFundo
@ciclo:
        ldy #ESPERA_MAX         ; 1) espera o sensor ver escuro
@esperaEscuro:
        jsr QuadroLuz
        beq @escuro
        dey
        bne @esperaEscuro
        jmp @fim                ; sempre claro: erro
@escuro:
        ldy #ASSENTA
@assentaPreto:
        jsr QuadroLuz
        dey
        bne @assentaPreto
        lda #COR_BRANCA         ; 2) acende e conta até o sensor ver luz
        jsr PoeCorFundo
        ldy #$00
@esperaLuz:
        jsr QuadroLuz
        bne @acendeu
        iny
        cpy #ESPERA_MAX
        bne @esperaLuz
        jmp @fim                ; nunca viu luz: erro
@acendeu:
        cpy calSobe
        bcc @assenta2
        sty calSobe
@assenta2:
        ldy #ASSENTA
@assentaBranco:
        jsr QuadroLuz
        dey
        bne @assentaBranco
        lda #COR_PRETA          ; 3) apaga e conta até o sensor soltar
        jsr PoeCorFundo
        ldy #$00
@esperaApagar:
        jsr QuadroLuz
        beq @apagou
        iny
        cpy #ESPERA_MAX
        bne @esperaApagar
        jmp @fim                ; nunca apagou: erro
@apagou:
        cpy calDesce
        bcc @proximo
        sty calDesce
@proximo:
        dec calCiclos
        bne @ciclo
        lda calDesce            ; 4) calcula e grava
        clc
        adc #MARGEM_K
        cmp #K_MAX+1
        bcs @fim                ; atraso grande demais: mantém os valores antigos
        sta ramK
        lda calSobe
        clc
        adc #MARGEM_N
        sta ramN
        jsr TesteSombra         ; 5) com K/N novos, escolhe o nível de sombra
        jsr SalvaConfig
@fim:
        lda #$0F
        sta APUSTATUS
        lda #$01
        sta listaTela           ; o NMI recarrega a paleta do título ($E540)
        jsr EsperaNMI           ; ($C5D9 zera $22: o NMI volta às atualizações)
        lda calMask
        sta sombraMask
        sta PPUMASK
        lda #$00
        sta botoes1             ; esquece o Start que chamou a calibração
        rts

; Espera um quadro sem deixar o NMI mexer na PPU (não zera $22).
; Devolve A = $08 (Z = 0) se o sensor viu luz em algum momento do quadro,
; A = 0 (Z = 1) se não. Mexe em X; preserva Y.
QuadroLuz:
        ldx #$00
        lda #$00
        sta flagNMI
@laco:
        jsr LerZapper
        pha
        lda flagNMI
        bne @fim                ; NMI chegou: a última leitura já é do quadro
        pla                     ; seguinte e é descartada
        and #$08
        bne @laco
        ldx #$08                ; viu luz neste quadro
        bne @laco               ; (sempre salta)
@fim:
        pla
        txa
        rts

; Grava a cor A em $3F00 (chamar logo após o NMI). Com a tela desligada e o
; endereço da PPU fora da paleta, a tela inteira mostra essa cor.
PoeCorFundo:
        pha
        lda PPUSTATUS
        lda #$3F
        sta PPUADDR
        lda #$00
        sta PPUADDR
        pla
        sta PPUDATA
        lda #$00
        sta PPUADDR
        sta PPUADDR
        rts

; =============================================================================
;  SOMBRA  ($FF30, segundo bloco livre preenchido com $FF, antes dos vetores)
;  Em vez de apagar a tela durante o tiro, mostra o cenário com as cores
;  escurecidas (nível S). O quadrado branco aparece por cima, como sempre.
; =============================================================================
.segment "FIM"

; Chamada no fim do 1o quadro da etapa preta (o NMI acabou de gravar a lista 5,
; que deixa a paleta toda preta). Monta a paleta do cenário escurecida, agenda a
; gravação dela pela fila de PPU do jogo (entra no próximo NMI) e liga o fundo.
; Não faz nada no tiro da tela de título nem com S = 0. Preserva Y.
LigaSombra:
        lda alvo
        cmp #$02
        bcs @fim
        lda ramS
        beq @fim
        tya
        pha
        ldx #15
@cor:   lda modoJogo
        cmp #$02
        bcs @gameC
        lda PAL_AB,x
        bcc @escurece           ; (sempre salta: C = 0)
@gameC: lda PAL_C,x
@escurece:
        ldy ramS
        jsr Escurece
        sta paletaSombra,x
        dex
        bpl @cor
        ldx #$00                ; $3F00-$3F07
        jsr EnfileiraMetade
        ldx #$08                ; $3F08-$3F0F
        jsr EnfileiraMetade
        lda sombraMask          ; liga o fundo (a paleta ainda está preta neste
        and #$E7                ; quadro; o cenário escurecido aparece no próximo)
        ora #$08
        sta sombraMask
        sta PPUMASK
        lda #$01
        sta sombraAtiva
        pla
        tay
@fim:   rts

.segment "NOVO"          ; (trecho morto/livre, ver patch.cfg)
; X = 0 ou 8: agenda 8 cores de paletaSombra+X para $3F00+X.
EnfileiraMetade:
        stx metade
        lda #$18                ; 1 linha x 8
        sta bufPPU
        ldy #$00
@c:     lda paletaSombra,x
        sta bufPPU+1,y
        inx
        iny
        cpy #$08
        bne @c
        ldx metade
        ldy #$3F
        jmp EnfileiraPPU

.segment "FIM"

.segment "MORTO2"          ; (trecho morto/livre, ver patch.cfg)
; A = cor NES, Y = nível 1..3 -> A = cor com (4 - nível) linhas de brilho a
; menos (no mínimo a linha 0, mesma cor). Colunas $D-$F (pretos) -> $0F.
; Preserva X e Y.
Escurece:
        sta escCor
        and #$0F
        cmp #$0D
        bcs @preto
        lda escCor
        sec
        sbc SubLinhas-1,y
        bcs @fim
        lda escCor
        and #$0F
@fim:   rts
@preto: lda #$0F
        rts
SubLinhas:
        .byte $30, $20, $10     ; nível 1, 2, 3

; Botão A no menu: S = S + 1 (volta a 0 depois de S_MAX). Preserva X e Y.
ProximoS:
        inc ramS
        lda ramS
        cmp #S_MAX+1
        bcc @ok
        lda #$00
        sta ramS
@ok:    rts

.segment "FIM"

; -----------------------------------------------------------------------------
;  TesteSombra - chamado no fim da calibração automática (tela desligada, logo
;  depois de um NMI). Para o nível 2 e depois o 1, repete SOMBRA_REPETE vezes:
;    céu (COR_CEU) por CEU_QUADROS quadros, como antes de um tiro;
;    a cor mais clara do nível (CorTeste) por K + CONF_PRETO quadros: depois dos
;      K primeiros, o sensor NÃO pode ver luz;
;    branco por até N quadros: o sensor PRECISA ver luz (o quadrado continua
;      visível depois do escuro).
;  O primeiro nível que passar todas as vezes vira ramS; se nenhum passar, S = 0.
; -----------------------------------------------------------------------------
TesteSombra:
        lda ramK
        clc
        adc #CONF_PRETO
        sta durEtapa
        lda #$02
        sta somNivel
@nivel: lda #SOMBRA_REPETE
        sta calCiclos
@tentativa:
        lda #COR_CEU
        jsr PoeCorFundo
        ldy #CEU_QUADROS
@ceu:   jsr QuadroLuz
        dey
        bne @ceu
        ldy somNivel
        lda CorTeste-1,y
        jsr PoeCorFundo
        ldy #$00
@escuro:
        iny
        jsr QuadroLuz
        beq @semLuz
        cpy ramK
        bcc @semLuz             ; ainda nos K quadros ignorados
        beq @semLuz
        bne @falhou             ; luz na sombra: nível claro demais
@semLuz:
        cpy durEtapa
        bne @escuro
        lda #COR_BRANCA
        jsr PoeCorFundo
        ldy #$00
@branco:
        iny
        jsr QuadroLuz
        bne @viu
        cpy ramN
        bne @branco
        beq @falhou             ; não viu o branco a tempo
@viu:   dec calCiclos
        bne @tentativa
        lda somNivel            ; passou todas as vezes
        sta ramS
        rts
@falhou:
        dec somNivel
        bne @nivel
        lda #$00                ; nenhum nível serviu: tela preta
        sta ramS
        rts
.segment "MORTO2"
CorTeste:
        .byte $00, $10          ; nível 1: branco vira $00; nível 2: vira $10
