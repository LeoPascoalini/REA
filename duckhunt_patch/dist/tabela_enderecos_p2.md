| Endereço CPU | Offset no arquivo | Bytes originais | Bytes novos | Motivo |
|---|---|---|---|---|
| cabeçalho | 0x00006 | 01 08 00 00 00 00 … (10 bytes) | 01 08 00 00 00 00 … (10 bytes) | cabeçalho NES 2.0: controles padrão, sem RAM extra |
| $C071-$C073 | 0x00081 | 20 84 C2 | 20 5B F0 | JSR $C284 (lê os controles) -> JSR PorQuadro (confere o acertou no prazo) |
| $D131-$D133 | 0x01141 | AD 17 40 | 20 87 EF | LDA $4017 (gatilho da Zapper) -> JSR LerGatilho (só B sozinho, fora do prazo) |
| $D1C7-$D1CC | 0x011D7 | 20 92 D2 20 1E C6 | 4C DA EF 4C 31 F0 | JSR $D292 / JSR $C61E -> JMP FlashComQuadrado / JMP FlashSemQuadrado (piscada curta) |
| $EF60-$F0BF | 0x02F70 | FF FF FF FF FF FF … (352 bytes) | A9 01 8D 16 40 A9 … (352 bytes) | rotinas novas (gatilho, piscada, prazo do acerto) em espaço livre ($FF) |
