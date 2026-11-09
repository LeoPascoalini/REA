| Endereço CPU | Offset no arquivo | Bytes originais | Bytes novos | Motivo |
|---|---|---|---|---|
| cabeçalho | 0x00006 | 01 08 00 00 00 00 … (10 bytes) | 03 08 00 00 70 00 … (10 bytes) | cabeçalho NES 2.0: 8 KB de RAM com bateria em $6000, controles padrão |
| $D131-$D133 | 0x01141 | AD 17 40 | 20 60 EF | LDA $4017 (gatilho da Zapper) -> JSR LerZapper |
| $D1C7-$D1CC | 0x011D7 | 20 92 D2 20 1E C6 | 4C EF EF 4C F2 EF | JSR $D292 / JSR $C61E -> JMP FlashComQuadrado / JMP FlashSemQuadrado |
| $C176-$C178 | 0x00186 | A9 00 85 | 4C 8B F0 | início de partida no título -> JMP IniciaJogo (modo 3 = calibração) |
| $C19E-$C19E | 0x001AE | 03 | 04 | CPY #$03 -> #$04: Select passa por 4 opções |
| $C1C0-$C1C0 | 0x001D0 | 51 | 71 | LDA #$51 -> #$71: cursor em coluna de 7 linhas |
| $C1C7-$C1C7 | 0x001D7 | 04 | 06 | LDX #$04 -> #$06: limpa as 7 posições do cursor |
| $C1DF-$C1E1 | 0x001EF | AD FE 05 | 4C 9C F0 | LDA $05FE -> JMP PlacarTitulo (K/N no lugar do TOP SCORE no modo 3) |
| $C5C8-$C5CA | 0x005D8 | 20 17 C6 | 20 68 F0 | JSR $C617 -> JSR DesenhaTitulo (acrescenta a linha CALIBRATION) |
| $C82B-$C82D | 0x0083B | AD FE 05 | 20 81 F0 | LDA $05FE -> JSR LeModoJogo (modo 3 nunca vira partida) |
| $EF60-$F274 | 0x02F70 | FF FF FF FF FF FF … (789 bytes) | A9 01 8D 16 40 A9 … (789 bytes) | rotinas novas (pistola, flash, menu, calibração) em espaço livre ($FF) |
