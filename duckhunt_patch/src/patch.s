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
;    K e N ficam na RAM extra com bateria ($6000), declarada no cabeçalho pelo
;    build.py, e aparecem na linha do TOP SCORE quando o item está selecionado.
;
;  ROM alvo: Duck Hunt (World), CRC32 da ROM sem cabeçalho = 24598791
;  Montador: ca65 + ld65 (cc65), usando src/patch.cfg
; =============================================================================

.setcpu "6502"

; -----------------------------------------------------------------------------
;  VALORES PADRÃO E LIMITES  (usados quando a RAM extra está vazia/inválida)
; -----------------------------------------------------------------------------
K_PADRAO    = 7         ; quadros iniciais ignorados em cada etapa do flash
N_PADRAO    = 10        ; duração de cada etapa (preta, pato 1, pato 2)
K_MAX       = 60
N_MAX       = 99        ; dois dígitos na tela

; Calibração automática
CICLOS_CAL  = 6         ; quantas vezes pisca branco/preto
ESPERA_MAX  = 90        ; quadros (1,5 s) esperando o sensor mudar; depois disso, erro
ASSENTA     = 6         ; quadros extras parados em cada cor antes de trocar
COR_PRETA   = $0F
COR_BRANCA  = $30

.if K_PADRAO >= N_PADRAO
    .error "K_PADRAO precisa ser menor que N_PADRAO"
.endif

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
listaTela   = $23       ; NMI desenha a lista n-1 da tabela $E532 (1 = paleta do título)
alvo        = $B0       ; 0 = pato 1, 1 = pato 2, 2 = tiro na tela de título
bufPPU      = $0500     ; buffer [linhas<<4 | largura] + tiles, enfileirado por $C71D
modoMenu    = $05FE     ; 0 = Game A, 1 = Game B, 2 = Game C, 3 = CALIBRATION (novo)
pato2Ativo  = $0350
pato2Estado = $0351
VOANDO      = $03

; -----------------------------------------------------------------------------
;  RAM extra ($6000-$7FFF, com bateria) - só existe com o cabeçalho do patch
; -----------------------------------------------------------------------------
cfgMarca0   = $6000     ; 'D'
cfgMarca1   = $6001     ; 'H'
cfgK        = $6002
cfgN        = $6003
cfgSoma     = $6004     ; K xor N xor $5A
dirAnterior = $6005     ; direcional do quadro anterior (para detectar borda)
calSobe     = $6006     ; maior atraso medido escuro -> claro
calDesce    = $6007     ; maior atraso medido claro -> escuro
calCiclos   = $6008
calMask     = $6009
MARCA0      = $44
MARCA1      = $48

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
;  CarregaConfig - garante K/N válidos na RAM extra (senão grava o padrão).
;  SalvaConfig   - grava marca e soma de verificação.  Ambas preservam X e Y.
; -----------------------------------------------------------------------------
CarregaConfig:
        lda cfgMarca0
        cmp #MARCA0
        bne @padrao
        lda cfgMarca1
        cmp #MARCA1
        bne @padrao
        lda cfgK
        eor cfgN
        eor #$5A
        cmp cfgSoma
        bne @padrao
        lda cfgK
        beq @padrao             ; K = 0 inválido
        cmp cfgN
        bcs @padrao             ; K >= N inválido
        lda cfgN
        cmp #N_MAX+1
        bcs @padrao
        rts
@padrao:
        lda #K_PADRAO
        sta cfgK
        lda #N_PADRAO
        sta cfgN
SalvaConfig:
        lda #MARCA0
        sta cfgMarca0
        lda #MARCA1
        sta cfgMarca1
        lda cfgK
        eor cfgN
        eor #$5A
        sta cfgSoma
        rts

; -----------------------------------------------------------------------------
;  Quadro - espera um quadro inteiro (até o próximo NMI) conferindo a luz.
;  Entrada: Y = número do quadro dentro da etapa (1..N)
;  Saída:   C = 1 -> luz vista (só confere quando Y > K)
;           C = 0 -> o quadro acabou sem luz (ou ainda era quadro ignorado)
;  Preserva X e Y.
; -----------------------------------------------------------------------------
Quadro:
        jsr LimpaFlags          ; $20 = 0 e $22 = 0 (igual ao original)
@espera:
        lda flagNMI
        bne @fimQuadro          ; NMI chegou: fim do quadro
        cpy cfgK
        bcc @espera             ; Y < K: ignorado
        beq @espera             ; Y = K: ignorado
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
        ; ---- Etapa preta: N quadros; nos últimos (N-K) não pode haver luz ----
        ldy #$01
@preto:
        jsr Quadro
        bcs Falhou              ; luz com a tela preta -> erro (original: $D1D8)
        cpy cfgN
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
        ora #$10                ; só sprites (o quadrado)
        bne @gravaMask          ; (sempre salta)
@soFundo:
        ora #$08                ; só fundo
@gravaMask:
        sta sombraMask
        sta PPUMASK

        ; ---- Etapa de cada alvo: N quadros; luz nos últimos (N-K) = acerto ----
EtapaAlvo:
        ldy #$01
@quadro:
        cpy cfgN
        bne @semTroca
        jsr PreparaPato2        ; último quadro: põe o quadrado do pato 2 no
@semTroca:                      ; buffer, para ele entrar no quadro seguinte
        jsr Quadro
        bcs Acertou
        cpy cfgN
        beq @fimEtapa
        iny
        bne @quadro             ; (sempre salta)
@fimEtapa:
        jsr TemPato2            ; acabou a etapa do pato 1; falta o pato 2?
        bne Falhou
        lda #$01                ; Game B: agora testa o pato 2 (original $D280)
        sta alvo
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

ListaCalibration:               ; mesmo formato das listas do jogo
        .byte $22, $E8, $0B     ; PPU $22E8 = linha 23, coluna 8; 11 tiles
        .byte $0C, $0A, $15, $12, $0B, $1B, $0A, $1D, $12, $18, $17   ; CALIBRATION
        .byte $00               ; fim da lista

; Início da partida ($C82B): o modo 3 nunca vira partida (segurança).
LeModoJogo:
        lda modoMenu
        cmp #$03
        bcc @ok
        lda #$00
@ok:
        rts

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

@config:                        ; modo 3: " K=07  N=10" + placar apagado
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
        lda cfgK
        jsr DoisDigitos
        stx bufPPU+4
        sty bufPPU+5
        lda cfgN
        jsr DoisDigitos
        stx bufPPU+10
        sty bufPPU+11
        jsr EnfileiraRotulo
        lda #$16                ; 1 linha x 6 tiles: apaga os dígitos do placar
        sta bufPPU
        lda #$24
        ldx #5
@limpa:
        sta bufPPU+1,x
        dex
        bpl @limpa
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

; Cima/Baixo: K +1/-1 e N junto.  Esquerda/Direita: N -1/+1 (N > K sempre).
AjusteManual:
        lda botoes1
        and #$0F                ; Cima Baixo Esq Dir
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
        lsr a                   ; Direita
        bcc @naoDir
        tax
        lda cfgN
        cmp #N_MAX
        bcs @x1
        inc cfgN
@x1:
        txa
@naoDir:
        lsr a                   ; Esquerda
        bcc @naoEsq
        tax
        lda cfgK
        clc
        adc #1
        cmp cfgN
        bcs @x2                 ; só se N - 1 > K
        dec cfgN
@x2:
        txa
@naoEsq:
        lsr a                   ; Baixo
        bcc @naoBaixo
        tax
        lda cfgK
        cmp #2
        bcc @x3                 ; K mínimo = 1
        dec cfgK
        dec cfgN
@x3:
        txa
@naoBaixo:
        lsr a                   ; Cima
        bcc @fim
        lda cfgN
        cmp #N_MAX
        bcs @fim
        lda cfgK
        cmp #K_MAX
        bcs @fim
        inc cfgK
        inc cfgN
@fim:
        jmp SalvaConfig

; =============================================================================
;  CALIBRAÇÃO AUTOMÁTICA
;  A tela fica desligada (só a cor de fundo $3F00) e alterna preto/branco.
;  Mede, em quadros, quanto o sensor demora para ver a luz depois que a tela
;  fica branca (calSobe) e para deixar de ver depois que fica preta (calDesce).
;  Resultado: K = maior calDesce + 1 ; N = max(K, maior calSobe) + 3
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
        ldy calDesce            ; 4) calcula e grava
        iny
        cpy #K_MAX+1
        bcs @fim
        sty cfgK
        tya
        cmp calSobe
        bcs @usaK
        lda calSobe
@usaK:
        clc
        adc #3
        sta cfgN
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
