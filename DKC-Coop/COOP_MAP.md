# DKC-Coop — mapa de dependências do "jogador" no jogo original

Objetivo: antes de mudar mais comportamento, mapear **todo** o código do DKC1 que pergunta "quem é
o jogador", classificar cada ponto e definir uma regra única para o co-op simultâneo. A tabela
completa, ponto a ponto, está em `COOP_MAP_sites.csv`.

## Método

- Fonte: desmontagem da v1.0 (`dkc1-disasm/DKC1/Routine_Macros_DKC1.asm`; o co-op roda na v1.2 e
  as rotinas são as mesmas, em endereços mapeados na fase 2).
- Um extrator montou o grafo de chamadas do jogo inteiro (14.450 blocos, 12.129 ligações —
  JSR/JSL/JMP, desvios, continuação de um bloco no outro e as 128 tabelas de salto) e localizou
  todos os pontos que dependem do jogador. Para cada um: a rotina, quem chega nela (qual sprite do
  jogo — 121 da fase, 15 do mapa — ou rotina de sistema) e o que é feito com a resposta.
- Os pontos de decisão (perguntas "qual é o jogador", Kong atual, montaria, toques) foram lidos e
  classificados um a um; os sinalizadores e as tabelas por Kong foram classificados por regra
  (marcados assim no CSV).

## Por onde o jogo pergunta "quem é o jogador"

| Ponto | O que é | Usos |
|---|---|---|
| `$056F` | Kong atual (1 DK, 2 Diddy) — é **a** definição de jogador | 36 |
| `$80:9B9C` | "qual slot é o jogador" (lê `$056F`) | 93 |
| `$BB:A574`, `$BB:A64A`, `$BB:A623` | "o jogador encostou?" — testam **só o Kong ativo** | 30 + 4 |
| `$BB:A58D`, `$BB:A663/A66A` | toques por categoria / plataformas — já testam os dois | 14 + 11 |
| `$84` | índice do Kong (0 DK, 2 Diddy) para tabelas por Kong | 217 |
| `$0512/$0514` | slot do animal/carrinho que cada Kong monta | 75 |
| `$1705/$1707` | destino de volta de bônus, por Kong | 11 |
| `$0579`, `$1929` | sinalizadores do jogo (dupla, pausa, luz, congelamentos de evento) | 187 + 61 |
| `$42`, `$44`, controles | modo (1P/Contest/Team), jogador atual, leitura de controles | 26 + 30 + 87 |

São **885 pontos**. O fato central: o jogo inteiro foi escrito com **um** jogador (o Kong de
`$056F`) e um seguidor que só repete o caminho dele. Todo bug de co-op até aqui é um desses pontos
respondendo "o Kong ativo" quando a pergunta era sobre o outro.

## Categorias e regra de cada uma

| | Pergunta do jogo | Regra no co-op | Pontos |
|---|---|---|---|
| **T** toque | "algum Kong encostou nisto?" | **OU**: os dois | 49 |
| **A** alvo | "onde está o jogador?" (mirar, virar, gatilho de proximidade, sumir quando longe) | o Kong **mais próximo** | 22 |
| **C** ação | o objeto age no jogador (lançar, prender, carregar, montar, corda) | o Kong **que interagiu** | 71 |
| **L** líder | decisão única (câmera, destino, devolver animal, progresso, Squawks) | o **líder**, estável durante a sequência | 46 |
| **R** roteiro | sequência roteirizada (portas, entradas, saídas, checkpoint, fim de fase, cenas) | o **jogo original** (líder + seguidor); co-op pausa | 108 |
| **B** ambos | efeito do sistema aplicado ao jogador a cada quadro (limites, tipo de fase) | aplicar **aos dois** | 5 |
| **P** por Kong | estado do próprio Kong (`$84` = ele mesmo) | já funciona por Kong | 271 |
| **G** global | sinalizadores do jogo, modo, menus, mapa, depuração | inalterado (respeitar) | 312 |

## Achados — comportamentos errados previstos (ainda não relatados)

Pontos onde o jogo pergunta pelo Kong **ativo** e o co-op precisa de outro:

- **Cordas** (balançar e subir) — só o Kong ativo agarra (`B6:8000`, `BF:EC9B`, `BF:ED03`, `BF:EF0C`).
- **Barris-canhão** — o toque vale para os dois, mas quem é posto dentro e lançado é o **ativo**
  (`B6:F3F7`, `BF:E54F`, `BF:E7B0`); o parceiro vira seguidor (`B6:F452`).
- **Carrinho de mina** — embarque, estado e "esconder o parceiro" usam o ativo (`B6:9CD6..A6D3`,
  `B6:9F6F`).
- **Pneus, tambores de óleo, barril que solta inimigos** — toque só no ativo (`BB:A64A`): o outro
  não quica nos pneus.
- **Krusha e barril TNT** — "o jogador está montado?" olha o ativo, não o Kong que encostou
  (`B6:8624`, `BF:CFC3`, `BF:D0A6`).
- **Plataformas-guia** — ativação, "jogador em cima" e sumiço olham o ativo (`B6:AC23..AF1A`).
- **Inimigos e chefes** — miram/viram/disparam pelo ativo (22 pontos **A**).
- **Portas e saídas** — só o ativo entra (aperta cima na porta: `B6:C45C`); a entrada de bônus
  guarda o animal e as bananas **do ativo** para devolver (`BF:9EBB`) e esconde só o animal do
  ativo (`BF:92E5`).
- **Modo Team** — controles de menus e pausa vêm do "jogador atual" por `$056F`
  (`80:A2A0`, `80:C1A2`).
- **Efeitos por quadro do tipo de fase** (água/ambiente, limite de X) só no ativo
  (`80:C263`, `80:C47B`, `80:C501`, `BF:C341`, `80:8F28`).

## Regras de jogo decididas pelo usuário (2026-10-19)

1. **Importa para a fase → um líder; só muda movimento/vantagem → cada um por si.** O que traz
   troca de tela ou progresso (portas, entradas, saídas, barris que levam a bônus, fim de fase,
   checkpoint) segue um líder. Interações superficiais (pneus, cordas, barris-canhão comuns,
   inimigos, itens) respondem só ao Kong que interagiu: se um pula no pneu, só ele quica; o outro
   precisa ir até o pneu.
2. **Troca de tela é suprema.** Qualquer Kong que dispare uma troca de tela vira o líder e puxa o
   outro junto. Durante a transição o outro volta a ser o seguidor do jogo original; na área nova o
   controle é devolvido ao jogador dele.
3. **Carrinho de mina: um para os dois.** Quando um entra, o outro entra junto; o primeiro dirige
   (líder). Futuro: o segundo poder pular do carrinho e cair de volta, mantendo a inércia.
4. **Montarias seletivas.** Animais: piloto + garupa (já feito). Transformações (ex.: Squawks)
   podem existir para os dois — avaliar caso a caso.

Na tabela de categorias isso dá: **C** passa a "o Kong que interagiu, sozinho"; os pontos **C**
que levam a troca de tela (barril-canhão de bônus, porta, carrinho) passam a **L/R** com troca de
líder antes da sequência.

### Achado posterior: pedido de fim de sequência (`$1E2B`)

`$1E2B` (gravado pelo minijogo de bônus, fichas de animal, banana gigante, plataformas-guia e
chefes) é atendido pelo primeiro Kong que o lê (BF:876C, em 17 estados do Kong). É **L**: só o
líder pode atendê-lo; o outro vira seguidor. Era a causa da volta ao início da fase no bônus dos
3 barris.

## Arquitetura proposta

1. **Líder único e estável.** O líder é o Kong de `$056F`. Ele só muda por regra explícita, e
   **antes** de uma sequência começar: quem monta, quem entra numa porta ou barril, quem é atingido.
   Durante uma sequência o líder não muda. É o que torna corretas todas as decisões **L**.
2. **Modo livre × modo roteirizado.** O co-op só age com os dois Kongs em estados de jogo livre.
   Qualquer porta, entrada, saída, barril-canhão, checkpoint, fim de fase, cena ou troca de área
   (estados de roteiro, `$1929` ativo, tabela de sprites zerada) devolve os dois ao comportamento
   original — líder + seguidor — e o co-op volta depois que o seguidor assentou. Isso cobre as
   108 **R** de uma vez e substitui vários remendos atuais.
3. **Um ponto de decisão central.** A pergunta "qual slot é o jogador" (`$80:9B9C`) passa a
   responder conforme **quem perguntou**: o endereço de retorno da chamada identifica o ponto, e
   uma tabela gerada deste mapa dá a categoria — **A** → o Kong mais próximo; **C** → o Kong em
   contato com o objeto (`$88` do último toque) ou o que está nele; **L/R** → o líder.
4. **Toques sempre OU.** As três rotinas "só no ativo" (`BB:A574`, `BB:A64A`, `BB:A623`) testam os
   dois Kongs (a primeira já está feita).
5. **Efeitos para os dois.** As 5 rotinas **B** rodam também para o Kong secundário.
6. **Endereços.** O mapa usa a v1.0; as tabelas de chamador são convertidas para a v1.2 com o
   mapa v1.0→v1.2 da fase 2 e conferidas byte a byte.

## Plano

1. Revisão deste mapa com o usuário.
2. Infraestrutura: líder estável + modo livre/roteirizado (regras 1 e 2), com os remendos atuais
   reescritos sobre ela.
3. Ponto central com tabela de chamadores (regra 3), em lotes por família: cordas, barris-canhão,
   carrinho, plataformas, inimigos/chefes, portas.
4. Toques OU restantes e efeitos B (regras 4 e 5).
5. **Bateria de transições** rodando a cada mudança (rotas existentes + novas): barril DK, dano,
   montaria, as duas cavernas da Jungle Hijinxs, saída de bônus, cordas, barril-canhão, carrinho,
   checkpoint, fim de fase; regressão sem co-op idêntica.

## Limites

- **P** e **G** foram classificados por regra (código do próprio Kong; sinalizadores e menus);
  estão no CSV para revisão, mas não pedem mudança.
- O grafo é estático: chamadas por ponteiros calculados fora das tabelas de salto podem faltar; os
  pontos "sem dono" ficaram como rotinas de sistema.
- Fases de chefe, água e carrinho ainda precisam de decisões de jogo (por exemplo: no carrinho os
  dois vão juntos, como no original, ou cada um no seu?).
