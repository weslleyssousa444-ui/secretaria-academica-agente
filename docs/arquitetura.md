# Arquitetura do sistema de triagem

O sistema é um **grafo de estado** em LangGraph: nós que fazem uma coisa cada, arestas que decidem o que vem depois e um estado tipado que atravessa tudo. Substitui, como arquitetura de referência, a [v1 do Exercício 5](arquitetura-v1.md) (o laço sequencial da Parte 1), cujo motor (ferramentas, guardas, retry) o grafo reaproveita. O detalhe de cada nó, das arestas e do estado está em [`docs/grafo.md`](grafo.md); a pausa para a coordenação, em [`docs/humano.md`](humano.md).

Código: [`src/triagem/`](../src/triagem/) · ponto de entrada: [`Sistema`](../src/triagem/sistema.py) · conferência: [`conferir_grafo.py`](../conferir_grafo.py).

## 1. O diagrama

`[C]` = **código** decide · `[M]` = **modelo** decide · `[H]` = **humano** decide. As ferramentas ficam dentro do nó `ferramentas`.

```text
 texto do aluno (+ thread_id, ra_autenticado)
        |
        v
  entrada [C] ----+--> ler_memoria [C] ---------+
  (reinicia o     |                              +--> rotear [C] --(saudacao)--> saudacao_fixa [C] ------------+
   turno)         +--> classificar_pedido [C] ---+       |                                                      |
                       (regra em codigo)                 | (demais)                                             |
                                                         v                                                      |
                                    +--------------> agente [M] <------------------------------+                |
                                    |                  |   |                                   |                |
                                    |                  |   +-- termino: orcamento / laco /     |                |
                                    |                  |       tempo / erro_fatal --------------+----------------+
                                    |        (tool_calls)  |                                   |                |
                                    |                  v   | (sem tool_calls)                  |                |
                                    |            ferramentas [C] --------------------------> (volta)            |
                                    |                      v                                                    |
                                    |        garantir_trancamento [C]  (pos-condicao L02: se o aluno pediu      |
                                    |            |         |            trancamento e ninguem abriu o caso,     |
                                    +-(escalou)--+         |            o CODIGO abre e o agente redige)        |
                                                           v (ok)                                               |
                                    +-(devolveu, 1x)-- validar_resposta [C] --(reprovou 2x)--> contingencia [C] |
                                    |                      | (ok)                                  |           |
                                    |                      v                                       |           |
                                    +----------------> montar_saida [C] <--------------------------+-----------+
                                                       (objeto validado)
                                                           |
                                                           v
                                                   escrever_memoria [C]
                                                           |
                        +----- (caso de trancamento aberto neste turno) ----+---- (senao) ----> FIM
                        v
                registrar_espera [C] --> aprovacao_coordenacao [H] --> registrar_decisao [C] --> FIM
                (idempotente)             interrupt: o grafo PARA       (idempotente)
```

**Treze dos quinze nós são código.** Um é o modelo (`agente`) e um é a pessoa (`aprovacao_coordenacao`). O modelo decide em **um** lugar; o sistema para e espera uma pessoa em **um** ponto.

## 2. As seis perguntas

| | |
|---|---|
| **as ferramentas** | cinco. `buscar_aluno` e `consultar_financeiro` (leitura, contra o SQLite acadêmico); `consultar_regimento` (leitura, contra o índice FTS5, `docs/rag.md`); `emitir_documento` e `escalar_para_humano` (**escrita**, reversíveis: um documento se reemite, um caso se reabre). Nenhuma ferramenta executa trancamento, paga, ou altera cadastro (A3, `docs/model-card.md`). Executadas pelo nó `ferramentas` ([`src/triagem/nos.py:99-126`](../src/triagem/nos.py#L99-L126)), que devolve **erro como dado**, e não como exceção |
| **o laço** | a cada volta: o `agente` (modelo) pede ferramentas ou responde; se pediu, `ferramentas` executa e o controle **volta** ao `agente`; se respondeu, a resposta passa por `garantir_trancamento` e `validar_resposta` e sai. **O que faz a volta seguinte existir:** o modelo ter devolvido `tool_calls`. A volta de **correção** (o validador reprovou) acontece no máximo **uma vez** |
| **o estado** | um `TypedDict` declarado ([`src/triagem/estado.py`](../src/triagem/estado.py)): 17 campos, 5 com reducer. **No estado:** a trajetória (`passos`), as decisões (`termino`, `caso_trancamento`, `decisao_humana`), os contadores e o objeto de saída. **Na lista de mensagens:** só o texto da conversa e os retornos de ferramenta, que o modelo lê. Tabela completa no §6 |
| **o orçamento** | tetos de **passos** (8 chamadas de ferramenta por conversa), de **tokens** (20.000 por conversa) e de **tempo** (120 s por turno, [`src/triagem/nos.py:36`](../src/triagem/nos.py#L36)), conferidos no início do nó `agente` ([`src/triagem/nos.py:208-223`](../src/triagem/nos.py#L208-L223)). Por baixo deles, o `recursion_limit` do grafo (60, [`src/triagem/grafo.py:40`](../src/triagem/grafo.py#L40)). **Limite do teto de tempo:** é conferido **entre** chamadas ao modelo; uma chamada em retry (até 8 tentativas de 90 s) pode passar dele |
| **o término** | **respondeu**; **orcamento_esgotado** (passos, tokens ou tempo; o `motivo` diz qual); **laco_detectado** (a mesma ferramenta com os mesmos argumentos 3 vezes seguidas); **erro_fatal** (o provedor falhou depois do retry, ou o `recursion_limit` estourou). **A pausa para a coordenação não é um término:** a execução está viva, e o campo é `aguardando_humano`; e o vencimento é um estado do **caso** (`vencido`), e não da execução. Registrado em `termino` e `motivo`, e lido pela API |
| **o humano** | a **coordenação acadêmica**, no nó `aprovacao_coordenacao`, só para trancamento. Vê a tela montada pelo código e devolve aprovar, rejeitar ou **aprovar editando**. **Se não responde em 48 h**, o caso vence e volta à fila da secretaria (`docs/humano.md` §4) |

## 3. A defesa do nível de autonomia

**O nível é o de agente (laço com ferramentas), e ele é o degrau mais caro.** A regra é usar o mais baixo que resolve. Por que o de baixo não servia:

- **Workflow (sequência fixa de passos).** Não serve porque a **sequência de chamadas depende do que o aluno escreve e do que as ferramentas devolvem**. Nas execuções reais (`logs/parte2/`): o caso simples chama `buscar_aluno` e `emitir_documento`; a divergência chama `buscar_aluno` e `consultar_financeiro` e **não emite**; o RA inexistente chama `buscar_aluno` e recebe um erro que o modelo contorna **perguntando uma vez e só depois escalando**; a dúvida de regra chama só `consultar_regimento`. Quatro trajetórias diferentes para a mesma entrada de texto.
- **Roteador (classificar e despachar para um workflow fixo).** Não serve porque o pedido chega **sem estrutura**, em turnos: falta o RA, o RA não existe, o aluno diz "já paguei" contra o registro, "cancelar" não é pedido do catálogo. Cada um exige **entender o texto e decidir o próximo passo em tempo de execução**, e um roteador resolve só a primeira bifurcação.

**A decisão que só o modelo toma, apontada no diagrama:** o nó **`agente`** escolhe (a) qual ferramenta chamar e com quais argumentos, (b) quando parar de perguntar e encaminhar (a regra 5: confirmar o RA uma vez), (c) se a alegação do aluno **contradiz** o registro, e (d) se uma pergunta é dúvida de regra (chama o Regimento) ou pedido (não chama). **Tudo o mais é código**, inclusive as regras que **não podem** depender do modelo: o trancamento nunca é decidido (a pós-condição abre o caso), a emissão é validada dentro da ferramenta, a resposta é conferida contra o que as ferramentas devolveram.

**Se o laço livre não estivesse aqui**, o que se perderia: o diálogo de várias trocas do `docs/case.md` §2.2, que é o motivo de o produto ser um agente e não um formulário. O que se ganha com o grafo em volta dele: o agente é **um nó**, com orçamento, validador e portão à sua volta.

## 4. O desenho, conferido contra o código

O script [`conferir_grafo.py`](../conferir_grafo.py) importa o **mesmo objeto de grafo** que o `Sistema` compila (`triagem.grafo.GRAFO`) e imprime os nós e as arestas. **Se o desenho do §1 e esta saída divergirem, vale o código, e o desenho estava errado.** Comando: `python conferir_grafo.py`. Saída, copiada da execução:

```text
NÓS (15)
  agente
  aprovacao_coordenacao
  classificar_pedido
  contingencia
  entrada
  escrever_memoria
  ferramentas
  garantir_trancamento
  ler_memoria
  montar_saida
  registrar_decisao
  registrar_espera
  rotear
  saudacao_fixa
  validar_resposta

ARESTAS (24)
  __start__ -> entrada
  agente -> ferramentas   [condicional]
  agente -> garantir_trancamento   [condicional]
  agente -> montar_saida   [condicional]
  aprovacao_coordenacao -> registrar_decisao
  classificar_pedido -> rotear
  contingencia -> montar_saida
  entrada -> classificar_pedido
  entrada -> ler_memoria
  escrever_memoria -> __end__   [condicional]
  escrever_memoria -> registrar_espera   [condicional]
  ferramentas -> agente
  garantir_trancamento -> agente   [condicional]
  garantir_trancamento -> validar_resposta   [condicional]
  ler_memoria -> rotear
  montar_saida -> escrever_memoria
  registrar_decisao -> __end__
  registrar_espera -> aprovacao_coordenacao
  rotear -> agente   [condicional]
  rotear -> saudacao_fixa   [condicional]
  saudacao_fixa -> montar_saida
  validar_resposta -> agente   [condicional]
  validar_resposta -> contingencia   [condicional]
  validar_resposta -> montar_saida   [condicional]

PARÂMETROS  recursion_limit=60  condicionais=12  incondicionais=12
```

O desenho do §1 tem os mesmos 15 nós; as 24 arestas aparecem agrupadas (a aresta de `entrada` para os dois ramos paralelos, e as saídas condicionais de `agente`, `garantir_trancamento`, `validar_resposta`, `rotear` e `escrever_memoria`).

## 5. Os padrões, nomeados e justificados

| Padrão | Onde, no grafo | Por que ele, e não o de baixo | Condição de não uso |
|---|---|---|---|
| **sequencial com portão** | `agente` → `garantir_trancamento` → `validar_resposta` → `montar_saida`: dois portões em código entre a resposta do modelo e a saída | a regra "trancamento nunca é decidido" e a conferência do texto **não podem** depender de o modelo as seguir (o prompt diz; o portão garante) | não vale para o que é só leitura sem consequência |
| **router** | `classificar_pedido` + `rotear`: `saudação` vai ao texto fixo, o resto ao agente | evita uma chamada de modelo (e a cota) para "oi". É o degrau mais barato: **regra em código** (uma expressão regular) | com mais rotas, de assunto e não de forma, a regra deixaria de bastar (seria embedding) |
| **paralelização (*sectioning*)** | `ler_memoria` ‖ `classificar_pedido`, depois da `entrada`, juntando em `rotear` ([`src/triagem/grafo.py:58`](../src/triagem/grafo.py#L58)) | os dois ramos não dependem um do outro. **Não afirmo ganho de tempo:** os dois são locais e levam milissegundos; a paralelização está aqui porque o ramo de memória pode crescer (leitura de índice), e porque exige o reducer de `eventos`, que é o que `docs/grafo.md` §3.2 demonstra | se um dos ramos chamasse o modelo contra um provedor que atende uma requisição por vez, o total tenderia à **soma**, e não ao maior (medido na Aula 09) |
| **orquestrador-trabalhador** | **não usado** | o número de subtarefas não é dinâmico: um pedido é um pedido | se um pedido gerasse N subpedidos a despachar |
| **avaliador-otimizador** | `validar_resposta` (avaliador, **em código**) ↔ `agente` (gerador), no máximo **uma** volta; reprovando de novo, `contingencia` | a conferência de protocolo, prazo e artigo é **determinística**: não precisa de um modelo-juiz. Uma volta basta: duas reprovações indicam que o modelo não vai acertar com mais uma, e a resposta de molde é segura | a invenção de **canal** não é detectável por regra; para ela, o avaliador seria um juiz (Parte 3), que o grupo não adotou (recall de 60%) |
| **agente (laço)** | `agente` ↔ `ferramentas` | §3: a decisão que só o modelo toma | um pedido de documento com RA e regra satisfeita é, na prática, um *workflow* de três passos; o agente é necessário pelos casos em volta dele |

## 6. O estado: quem escreve e quem lê

Dezessete campos. **Os cinco com reducer** (`add`) são os acumulados: `mensagens`, `passos`, `tokens_gastos`, `n_chamadas_modelo`, `eventos`. Os demais têm **um escritor por passo** (o último valor vale).

| Campo | Tipo | Quem **escreve** | Quem **lê** | De onde veio |
|---|---|---|---|---|
| `thread_id` | `str` | o chamador (`Sistema.conversar`) | `registrar_espera` | entrada do `invoke` |
| `ra_autenticado` | `str \| None` | o chamador | `ler_memoria`, `escrever_memoria` | o portal (cabeçalho), quando confiável |
| `mensagens` ⊕ | `list[dict]` | chamador (aluno), `agente`, `ferramentas`, `garantir_trancamento`, `validar_resposta`, `contingencia`, `saudacao_fixa` | `agente`, `garantir_trancamento`, `validar_resposta`, `montar_saida` | a conversa |
| `passos` ⊕ | `list[dict]` | `ferramentas`, `garantir_trancamento` | `agente` (laço, orçamento), `garantir_trancamento`, `validar_resposta`, `montar_saida`, `escrever_memoria`, `registrar_espera` | retorno das ferramentas |
| `tokens_gastos` ⊕ | `int` | `agente` | `agente` (teto) | `usage` do provedor |
| `n_chamadas_modelo` ⊕ | `int` | `agente` | métricas (Parte 3) | contador |
| `eventos` ⊕ | `list[str]` | **todos os nós** (inclusive os dois **paralelos**) | arestas `depois_do_garantir` e `depois_do_validar`; testes; a API | trilha |
| `inicio_do_turno` | `int` | `entrada` | `montar_saida`, `escrever_memoria`, `validar_resposta` | `len(passos)` |
| `turno_iniciado_em` | `float` | `entrada` | `agente` (teto de tempo) | `time.monotonic()` |
| `tipo_pedido` | `str \| None` | `classificar_pedido` | `depois_do_rotear` | regra em código |
| `memoria_bloco` | `str` | `ler_memoria` | `agente` | a memória, filtrada por RA |
| `correcoes` | `int` | `entrada` (0), `validar_resposta` (1) | `validar_resposta` | o validador |
| `termino` | `str \| None` | `entrada` (reinicia), `agente`, `montar_saida` | `depois_do_agente`, `montar_saida`, a API | taxonomia do §2 |
| `motivo` | `str \| None` | `entrada` (reinicia), `agente` | `Sistema.conversar` → API | o teto que estourou |
| `saida` | `dict` | `entrada` (reinicia), `montar_saida` | `Sistema.conversar` | `SaidaTriagem` |
| `caso_trancamento` | `str \| None` | `entrada` (reinicia), `montar_saida` | `depois_da_memoria`, `registrar_espera`, `aprovacao_coordenacao`, `registrar_decisao` | o protocolo do caso |
| `decisao_humana` | `dict \| None` | `entrada` (reinicia), `aprovacao_coordenacao`, `registrar_decisao` | `registrar_decisao`, `Sistema.decidir` | a coordenação |

**Corrida?** Os campos sem reducer escritos por mais de um nó (`termino`, `saida`...) são escritos em **sequência**, nunca no mesmo passo: a única fronteira paralela do grafo é `ler_memoria` ‖ `classificar_pedido`, e eles escrevem campos **diferentes** (`memoria_bloco`, `tipo_pedido`) e o campo compartilhado `eventos`, que tem reducer. O que acontece sem o reducer está demonstrado em [`docs/grafo.md`](grafo.md) §3.2.

## 7. Onde o grafo para

**Um ponto de parada:** `aprovacao_coordenacao`, marcado `[H]` no diagrama. Critério: o trancamento é decisão sobre a situação acadêmica do aluno, **reservada à coordenação** pelo Regimento (Art. 6º). Os critérios "custo acima de um teto" e "confiança baixa" **não se aplicam** (o sistema não move dinheiro e não mede confiança). Tela, respostas aceitas, prazo e idempotência: [`docs/humano.md`](humano.md).
