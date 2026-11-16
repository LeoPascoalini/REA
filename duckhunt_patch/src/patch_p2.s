; =============================================================================
;  Duck Hunt (NES, NROM-128) - patch V5: PROTOCOLO 2 (a pistola decide o acerto)
;
;  A pistola (controle 2) olha a piscada na TV e decide sozinha se acertou:
;      B           = gatilho (pulso de ~50 ms)
;      A           = acertou (Game A) / acertou o 1o alvo (Game B/C)
;      A + B       = acertou o 2o alvo (Game B/C), no mesmo relatório HID
;      nada        = errou
;  O jogo nunca espera a pistola:
;    - a piscada é curta e fixa: 2 pretos, 2 de quadrado, 1 preto
;      (Game B/C com 2 alvos: 2 pretos, 2 quadrado 1, 1 preto, 2 quadrado 2, 1 preto);
;    - logo depois o jogo segue pelo caminho original do ERRO ($D259);
;    - por PRAZO quadros (~150 ms) ele ainda aceita o "acertou" e, se chegar,
;      derruba o pato onde ele estiver (mesmas 3 operações do acerto original);
;    - durante o prazo a bala do tiro fica "devolvida", para o pato não fugir
;      por falta de bala antes de um "acertou" atrasado chegar.
;  Na tela de título o jogo espera o prazo e então escolhe a opção do menu.
;
;  Sem menu de calibração e sem RAM com bateria: no protocolo 2 é a pistola que
;  mede o próprio atraso (ver "firmware pistola/PROTOCOLO_NOVO.md").
;
;  ROM alvo: Duck Hunt (World), CRC32 da ROM sem cabeçalho = 24598791
;  Montador: ca65 + ld65 (cc65), usando src/patch_p2.cfg (build.py --protocolo 2)
; =============================================================================

.setcpu "6502"

PRAZO       = 9         ; quadros (~150 ms) aceitando "acertou" depois da piscada

; -----------------------------------------------------------------------------
;  Hardware
; -----------------------------------------------------------------------------
PPUMASK     = $2001
JOY1        = $4016     ; escrever aqui faz o strobe das DUAS portas
JOY2        = $4017     ; leitura serial do controle 2

; -----------------------------------------------------------------------------
;  RAM do jogo (confirmada no disassembly)
; -----------------------------------------------------------------------------
sombraMask  = $09       ; cópia do PPUMASK mantida pelo jogo
modoJogo    = $1F       ; 0 = Game A, 1 = Game B, 2 = Game C
acertos     = $AA       ; acerto: INC (original $D246)
alvo        = $B0       ; 0 = pato 1, 1 = pato 2, 2 = tiro na tela de título
rodando     = $B9       ; <> 0 durante a fase de tiro ($D160)
balas       = $BA       ; balas; 0 faz o pato fugir ($CA29)
acertosLance = $BD      ; acerto: INC (original $D246)
redesenhaBalas = $BE    ; 1 = redesenhar as balas no HUD ($C6F5)
pato1Estado = $0301
pato2Ativo  = $0350
pato2Estado = $0351
VOANDO      = $03
ATINGIDO    = $04

; -----------------------------------------------------------------------------
;  RAM nova: página $0700, que o jogo não usa (o RESET só limpa $0000-$06FF)
; -----------------------------------------------------------------------------
prazo       = $07E0     ; quadros que ainda aceitam "acertou" (0 = nenhum tiro pendente)
alvoJ1      = $07E1     ; alvo do 1o quadrado (0 = pato 1, 1 = pato 2)
alvoJ2      = $07E2     ; alvo do 2o quadrado ($FF = não houve 2o quadrado)
tmpPad      = $07E3
recebido    = $07E4     ; 0 = nada, 1 = A, 3 = A + B (o primeiro que chegou)

; -----------------------------------------------------------------------------
;  Rotinas do jogo reaproveitadas
; -----------------------------------------------------------------------------
LeControles = $C284     ; lê os dois controles (chamada 1x por quadro no laço principal)
LimpaOAM    = $C23B
EsperaNMI   = $C5D9     ; zera $20/$22 e espera o próximo NMI (preserva X e Y)
DesenhaAlvo = $D292     ; Y = $00 (pato 1) ou $50 (pato 2): quadrado no buffer de sprites
FimDoTiro   = $D259     ; fim original do tiro (paleta de volta, OAM limpa, liga a tela)
ResultadoTitulo = $D235 ; A = 1 (acerto: começa a partida) ou 2 (erro: próxima opção)


; =============================================================================
;  ALTERAÇÕES NO CÓDIGO ORIGINAL
; =============================================================================

; $C071: era 20 84 C2 (JSR $C284) no laço principal: lê os controles e, com um
; tiro pendente, confere se chegou o "acertou".
.segment "P_C071"
        jsr PorQuadro

; $D131: era AD 17 40 (LDA $4017, gatilho da Zapper).
.segment "P_D131"
        jsr LerGatilho

; $D1C7: era JSR $D292 / JSR $C61E. $D1C7 vem de $D1B3/$D1C5 (alvo escolhido,
; Y = $00 ou $50) e $D1CA do BNE em $D19D (tiro na tela de título).
.segment "P_D1C7"
        jmp FlashComQuadrado    ; $D1C7
        jmp FlashSemQuadrado    ; $D1CA


; =============================================================================
;  ROTINAS NOVAS  ($EF60, espaço livre preenchido com $FF)
; =============================================================================
.segment "NOVO"

; -----------------------------------------------------------------------------
;  LePad2 - lê A e B do controle 2.  Saída: A = %000000BA.  Preserva X e Y.
; -----------------------------------------------------------------------------
LePad2:
        lda #$01
        sta JOY1
        lda #$00
        sta JOY1
        lda JOY2                ; 1a leitura serial = A
        and #$03                ; bit 0 (controle) ou bit 1 (expansão Famicom)
        beq @a0
        lda #$01
@a0:    sta tmpPad
        lda JOY2                ; 2a leitura serial = B
        and #$03
        beq @b0
        lda #$02
        ora tmpPad
        rts
@b0:    lda tmpPad
        rts

; -----------------------------------------------------------------------------
;  LerGatilho - substitui LDA $4017 em $D131. Devolve A no formato da Zapper
;  (bit 4 = gatilho). Só conta B SOZINHO e fora do prazo: A + B é mensagem.
;  O jogo registra o tiro quando o bit volta a 0 (como a Zapper real).
; -----------------------------------------------------------------------------
LerGatilho:
        lda prazo
        bne @nada
        jsr LePad2
        cmp #$02                ; só B
        bne @nada
        lda #$10
        rts
@nada:  lda #$00
        rts

; -----------------------------------------------------------------------------
;  Escuta - guarda a primeira mensagem que chegar (1 = A, 3 = A + B).
;  O botão fica apertado ~3 quadros; olhar 1 vez por quadro basta. Preserva X e Y.
; -----------------------------------------------------------------------------
Escuta:
        lda recebido
        bne @fim
        jsr LePad2
        lsr a                   ; C = A; A = B
        bcc @fim
        rol a                   ; A = (B << 1) | 1
        sta recebido
@fim:   rts

EsperaQuadro:                   ; espera o próximo NMI e escuta o controle 2
        jsr EsperaNMI
        jmp Escuta

; -----------------------------------------------------------------------------
;  Tela durante a piscada. Os PPUMASK são escritos logo depois do NMI, como no
;  original ($D1F7-$D20B).
; -----------------------------------------------------------------------------
Apaga:                          ; tudo desligado: tela preta (paleta preta das listas 4/5)
        lda sombraMask
        and #$E7
        sta sombraMask
        sta PPUMASK
        rts

MostraAlvo:                     ; liga o quadrado (ou o fundo, no título) por 2 quadros
        lda sombraMask
        and #$E7
        ldy alvo
        cpy #$02
        beq @fundo
        ora #$10                ; só sprites: o quadrado
        bne @grava              ; (sempre salta)
@fundo: ora #$08                ; só fundo: a tela de título acesa
@grava: sta sombraMask
        sta PPUMASK
        jsr EsperaQuadro
        jmp EsperaQuadro

DoisPretos:                     ; o quadro atual (já preto) e mais um
        jsr EsperaQuadro
        jmp EsperaQuadro

; -----------------------------------------------------------------------------
;  FlashComQuadrado - tiro durante a partida. Chega aqui logo depois do NMI, com
;  a tela desligada ($C5E1), a lista 5 (paleta preta, quadrado branco) pedida e
;  Y = $00 ou $50 para o quadrado do alvo escolhido.
; -----------------------------------------------------------------------------
FlashComQuadrado:
        jsr DesenhaAlvo         ; quadrado do 1o alvo no buffer (invisível ainda)
        lda alvo
        sta alvoJ1
        lda #$FF
        sta alvoJ2
        jsr TemPato2            ; Z = 1: alvo 0 e o pato 2 também voando
        bne @umAlvo
        lda #$01
        sta alvoJ2
@umAlvo:
        lda #$00
        sta recebido
        inc balas               ; devolve a bala até o prazo acabar (o pato não foge)
        jsr DoisPretos          ; quadros 0-1: preto
        jsr MostraAlvo          ; quadros 2-3: quadrado do 1o alvo
        lda alvoJ2
        bmi @fimPisca
        jsr Apaga               ; quadro 4: preto, e troca o quadrado para o pato 2
        jsr LimpaOAM
        ldy #$50
        jsr DesenhaAlvo
        jsr EsperaQuadro
        jsr MostraAlvo          ; quadros 5-6: quadrado do pato 2
@fimPisca:
        jsr Apaga               ; último preto: dura até o NMI dentro de $D259
        lda #PRAZO
        sta prazo
        jmp FimDoTiro           ; segue como ERRO (caminho original)

; Z = 1 se o alvo atual é o pato 1 e o pato 2 também está voando. Só mexe em A.
TemPato2:
        lda alvo
        bne @nao
        lda pato2Ativo
        beq @nao
        lda pato2Estado
        cmp #VOANDO
        rts
@nao:   lda #$01
        rts

; -----------------------------------------------------------------------------
;  FlashSemQuadrado - tiro na tela de título (alvo = 2): a tela inteira acende.
;  Aqui não há pressa: espera o prazo e então decide.
; -----------------------------------------------------------------------------
FlashSemQuadrado:
        lda #$00
        sta recebido
        jsr DoisPretos
        jsr MostraAlvo          ; título aceso por 2 quadros
        jsr Apaga
        ldy #PRAZO
@espera:
        lda recebido
        bne @acertou
        jsr EsperaQuadro
        dey
        bne @espera
        lda recebido
        bne @acertou
        lda #$02                ; erro: próxima opção
        jmp ResultadoTitulo
@acertou:
        lda #$01                ; acerto: começa a partida
        jmp ResultadoTitulo

; -----------------------------------------------------------------------------
;  PorQuadro - no laço principal, 1x por quadro (no lugar de JSR $C284).
;  Com um tiro pendente: se chegou A, derruba o 1o alvo; A + B, o 2o; senão
;  conta o prazo. Quando o prazo acaba (ou chega a mensagem), gasta a bala.
; -----------------------------------------------------------------------------
PorQuadro:
        jsr LeControles
        lda prazo
        beq @sai
        lda rodando
        beq @cancela            ; a fase de tiro acabou: esquece o tiro pendente
        jsr Escuta
        lda recebido
        beq @semMsg
        cmp #$03
        beq @j2
        lda alvoJ1
        jmp @aplica
@j2:    lda alvoJ2
@aplica:
        jsr AplicaAcerto
        jmp @fecha
@semMsg:
        dec prazo
        bne @sai
@fecha:
        lda #$00
        sta prazo
        dec balas               ; agora sim gasta a bala
        lda #$01
        sta redesenhaBalas
@sai:   rts
@cancela:
        lda #$00
        sta prazo
        rts

; A = 0 (pato 1) ou 1 (pato 2); qualquer outro valor não faz nada.
; Só derruba se o pato ainda estiver voando. Mesmas operações de $D246.
AplicaAcerto:
        cmp #$00
        bne @p2
        lda pato1Estado
        cmp #VOANDO
        bne @nao
        lda #ATINGIDO
        sta pato1Estado
        bne @conta              ; (sempre salta)
@p2:    cmp #$01
        bne @nao
        lda pato2Estado
        cmp #VOANDO
        bne @nao
        lda #ATINGIDO
        sta pato2Estado
@conta: inc acertos
        inc acertosLance
@nao:   rts
