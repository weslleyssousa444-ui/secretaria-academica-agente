# O grafo: nós, arestas, estado e o que o framework não deu

Complementa [`docs/arquitetura.md`](arquitetura.md) (o diagrama, as seis perguntas, a tabela de padrões, a tabela de campos do estado). Aqui ficam as **razões**: quem decide cada bifurcação, por que cada campo tem o reducer que tem, o que o LangGraph fez e o que **não** fez, e o que acontece quando um parâmetro padrão muda.

Framework: **LangGraph 1.2.12** com `langgraph-checkpoint-sqlite 3.1.1` (versões **exatas** em `requirements-agente.txt`: parte do comportamento do sistema mora na biblioteca). O LangGraph, e não só "LangChain", porque o modelo mental dele (grafo de estado) é o que a Aula 05 pediu que o grupo desenhasse à mão.

## 1. Os nós

| Nó | O que faz | Decide | Modelo? |
|---|---|---|---|
| `entrada` | reinicia o que vale por turno (`termino`, `saida`, `correcoes`, o relógio do turno) | código | não |
| `ler_memoria` | monta o bloco MEMÓRIA, **só com RA autenticado** | código | não |
| `classificar_pedido` | `saudacao`, `trancamento` ou `outro`, por expressão regular | código | não |
| `rotear` | junção dos dois ramos paralelos; a aresta condicional escolhe | código | não |
| `saudacao_fixa` | texto fixo do widget | código | não |
| **`agente`** | confere o orçamento, chama o modelo, devolve `tool_calls` ou texto | **modelo** | **sim** |
| `ferramentas` | executa o que o modelo pediu, com as guardas de negócio da Parte 1 | código | não |
| `garantir_trancamento` | pós-condição L02: se o aluno pediu trancamento e ninguém abriu o caso, **abre pelo código** | código | não |
| `validar_resposta` | confere protocolo, artigo, prazo e a marcação de suficiência no **texto** | código | não |
| `contingencia` | resposta por molde, depois de duas reprovações | código | não |
| `montar_saida` | monta o objeto `SaidaTriagem` (decisão, fonte, suficiência) | código | não |
| `escrever_memoria` | grava o episódio e o fato, **por regra** | código | não |
| `registrar_espera` | grava a espera e o prazo (idempotente) | código | não |
| **`aprovacao_coordenacao`** | `interrupt()`: o grafo para | **humano** | não |
| `registrar_decisao` | grava a decisão (idempotente) | código | não |

## 2. Os padrões e quem decide cada aresta

### 2.1 Os padrões

A tabela de padrões (sequencial com portão, *router*, paralelização, avaliador-otimizador, agente) está em [`docs/arquitetura.md`](arquitetura.md) §5. O orquestrador-trabalhador **não é usado**.

### 2.2 O avaliador-otimizador, em detalhe

O **avaliador** é `validar_resposta`: determinístico, sem modelo. O **gerador** é o `agente`. Uma volta de correção: o avaliador devolve a lista de problemas numa mensagem de sistema, e o agente reescreve. Duas reprovações levam a `contingencia`. A volta é limitada por um campo do estado (`correcoes`, no máximo 1), e **não** pelo `recursion_limit`: depender do limite do framework para encerrar um laço de correção seria usar a rede de segurança como controle de fluxo.

### 2.3 Quem decide cada aresta condicional

São 12 arestas condicionais, em 5 nós. A regra da Aula 06: **o degrau mais barato que resolve**.

| De | Para | Decide | Degrau | Por que não um degrau acima |
|---|---|---|---|---|
| `rotear` | `saudacao_fixa` \| `agente` | `tipo_pedido == "saudacao"` | **regra em código** | uma saudação se reconhece por forma ("oi", "bom dia"), e a classificação já aconteceu em `classificar_pedido` |
| `agente` | `ferramentas` \| `garantir_trancamento` \| `montar_saida` | `termino` preenchido? há `tool_calls` na última mensagem? | **regra em código** | é a presença de um campo na resposta do modelo; **o modelo decide o que pedir, mas o código decide o que fazer com isso** |
| `garantir_trancamento` | `agente` \| `validar_resposta` | o nó abriu o caso pelo código? (último evento da trilha) | **regra em código** | é um fato verificável |
| `validar_resposta` | `agente` \| `contingencia` \| `montar_saida` | o validador devolveu? reprovou de novo? (último evento) | **regra em código** | a conferência é determinística |
| `escrever_memoria` | `registrar_espera` \| FIM | `caso_trancamento` preenchido? | **regra em código** | um campo nulo ou não |

**Nenhuma aresta é decidida por embedding nem por modelo com saída estruturada** (`Literal` com as rotas). O modelo decide **dentro** do nó `agente`, e as arestas leem o resultado. Por isso não há aqui a confusão que o enunciado alerta (o *schema* garante que a resposta seja uma rota válida, e não que seja a rota certa): não há rota escolhida por modelo.

**Uma fragilidade, declarada:** `depois_do_garantir` e `depois_do_validar` decidem lendo o **último evento da trilha** (`eventos[-1]`, uma *string*). É acoplamento por texto entre o nó e a aresta: renomear um evento sem renomear a aresta quebra o grafo, e só os testes pegariam. A alternativa limpa é um campo próprio no estado (`proximo`); fica como dívida técnica.

## 3. O estado

### 3.1 Os campos

A tabela (campo, tipo, quem escreve, quem lê, de onde veio) está em [`docs/arquitetura.md`](arquitetura.md) §6. O estado é um `TypedDict` em [`src/triagem/estado.py:19`](../src/triagem/estado.py#L19).

### 3.2 Os reducers, e o que acontece sem eles

Cinco campos são acumulados e têm o reducer `add` (`mensagens`, `passos`, `tokens_gastos`, `n_chamadas_modelo`, `eventos`). **Por quê:** cada nó devolve só o que **acrescenta**; sem o reducer, o nó que devolvesse `mensagens` substituiria a conversa inteira.

**O que acontece sem reducer, executado** ([`tests/test_estado.py`](../tests/test_estado.py), grafos mínimos, versão fixada 1.2.12):

| Situação | Sem reducer | Com reducer `add` |
|---|---|---|
| dois nós **paralelos** escrevem o mesmo campo | **`InvalidUpdateError`**: *"At key 'trilha': Can receive only one value per step. Use an Annotated key to handle multiple values."* | `['a', 'b']` |
| dois nós em **sequência** escrevem o mesmo campo | **o segundo sobrescreve o primeiro, em silêncio**: `{'trilha': ['do segundo']}` | `['do primeiro', 'do segundo']` |

**Duas observações, uma delas contra o que o enunciado supõe.** (1) O enunciado diz que, em nós paralelos, um campo sem reducer é sobrescrito "sem erro nenhum". **Na versão fixada, não é assim:** o LangGraph **recusa** a atualização com um erro explícito. O defeito silencioso é o da **sequência**, e é pior, porque não levanta nada. Os dois estão travados em teste: se uma versão futura passar a aceitar o paralelo em silêncio, `test_paralelo_sem_reducer_e_recusado_pelo_framework` acusa. (2) No grafo **entregue**, os dois ramos paralelos (`ler_memoria`, `classificar_pedido`) escrevem `eventos`: sem o reducer, **todo turno falharia** (`test_no_grafo_entregue_os_dois_ramos_paralelos_aparecem_na_trilha`).

### 3.3 O que NÃO está no estado

**O que ficou na lista de mensagens:** o texto da conversa (o que o aluno disse, o que o agente respondeu) e os retornos de ferramenta, que são o que o modelo lê. **Decisão, contador e identificador não ficam lá:** estão em campos (`termino`, `tokens_gastos`, `caso_trancamento`).

**O que é derivado e não guardado:**

- o **número de passos** é `len(passos)`: guardá-lo criaria duas fontes de verdade;
- a **decisão** e a **fonte** do turno são calculadas de `passos` em `montar_saida` (`saida.decisao_da_trajetoria`), e só o resultado entra em `saida`;
- o **objeto de memória** e a **conexão com o banco** são recursos, não estado (e não são serializáveis).

### 3.4 O estado entre agentes

Há **um** agente. Não há passagem de estado entre agentes. Se a Parte 3 introduzir multiagente, o contrato de *handoff* entra em `docs/multiagente.md`.

## 4. A implementação, e a conferência contra o desenho

O grafo é montado uma vez em [`src/triagem/grafo.py:43`](../src/triagem/grafo.py#L43) (nós registrados, arestas ligadas, condicionais **com o mapa de destinos explícito**) e **compilado uma vez** em [`src/triagem/sistema.py:56`](../src/triagem/sistema.py#L56), no construtor do `Sistema`. A junção paralela é uma linha: [`src/triagem/grafo.py:58`](../src/triagem/grafo.py#L58). O `conferir_grafo.py` da raiz importa o mesmo `GRAFO`; a saída, colada em [`docs/arquitetura.md`](arquitetura.md) §4, mostra 15 nós e 24 arestas (12 condicionais).

## 5. O que o framework não deu, e o que ficou aberto

### 5.1 A conta

O LangGraph deu a **estrutura** (nós, arestas, estado, persistência, pausa). Não deu o que um sistema com ação sobre o mundo precisa para **terminar bem**. Linhas escritas para suprir isso:

| Frente | O que o framework dá | O que eu escrevi | Linhas |
|---|---|---|---|
| **motivo de término** | o nó terminal diz que acabou, **não por quê** | a taxonomia (`respondeu`, `orcamento_esgotado`, `laco_detectado`, `erro_fatal`) e o `motivo`, dentro de `agente` e de `Sistema.conversar` | [`src/triagem/nos.py:236-237`](../src/triagem/nos.py#L236-L237) (2) e [`src/triagem/sistema.py:88-100`](../src/triagem/sistema.py#L88-L100) (13) |
| **detector de laço** | `recursion_limit` **limita o dano e não detecta**: um agente preso na primeira volta gasta o teto inteiro e devolve o diagnóstico errado | `laco_detectado`: a mesma ferramenta com os mesmos argumentos 3 vezes seguidas | [`src/triagem/nos.py:93-96`](../src/triagem/nos.py#L93-L96) (4) |
| **os tetos** | só o `recursion_limit`, que conta **passos do grafo**, não chamadas de ferramenta, tokens ou segundos | os tetos de passos (8), tokens (20.000) e tempo (120 s) | [`src/triagem/nos.py:210-226`](../src/triagem/nos.py#L210-L226) (17) |
| **erro recuperável × fatal** | nada: uma exceção numa ferramenta derruba o nó | `executar_chamada`: erro de ferramenta vira **dado que ensina o modelo**; qualquer exceção é capturada sem vazar o texto interno | [`src/triagem/nos.py:99-126`](../src/triagem/nos.py#L99-L126) (28) |
| **estouro do `recursion_limit`** | levanta `GraphRecursionError` **e deixa o checkpoint no meio da execução** | captura, resposta ao aluno, e `ConversaEncerrada` para o turno seguinte | [`src/triagem/sistema.py:37-39`](../src/triagem/sistema.py#L37-L39) e o bloco de [`src/triagem/sistema.py:88-100`](../src/triagem/sistema.py#L88-L100) |

**Total: 64 linhas** nos blocos de `agente` (teto de passos, tokens, tempo e laço), `laco_detectado`, `executar_chamada`, o tratamento de `erro_fatal` e o do `recursion_limit` (a `ConversaEncerrada` não entra na soma). Pequeno em linhas, grande em consequência: sem elas, o sistema **não termina com diagnóstico**.

**O que o framework cobriu inteiro, com evidência de que eu não escrevi:**

| Frente | Evidência |
|---|---|
| persistência e retomada do estado | uma linha: [`src/triagem/sistema.py:56`](../src/triagem/sistema.py#L56). No laço da Parte 1 isso não existia: o trancamento terminava com `HUMANO` e a conversa acabava |
| pausa para a pessoa | uma linha dentro do nó: [`src/triagem/nos.py:343`](../src/triagem/nos.py#L343), e a retomada em [`src/triagem/sistema.py:144`](../src/triagem/sistema.py#L144) |
| acúmulo de campos | `Annotated[..., add]`, 5 linhas em [`src/triagem/estado.py:27`](../src/triagem/estado.py#L27) |
| junção de ramos paralelos | [`src/triagem/grafo.py:58`](../src/triagem/grafo.py#L58) |

### 5.2 Um defeito que o framework escondeu, e que o exercício de documentar achou

`GraphRecursionError` **não é tratado pelo framework** e, na primeira versão do `Sistema`, subia até a API como erro 500, e deixava `next = ('agente',)` no checkpoint, que o `conversar` confundia com **"aguardando a coordenação"** no turno seguinte. Encontrado ao documentar este parâmetro (§5.3), corrigido e coberto por `test_estourar_o_limite_de_passos_do_grafo_nao_derruba_nem_confunde_com_pausa`.

### 5.3 A decisão que virou parâmetro: `recursion_limit`

**A decisão, quando era explícita** (Parte 1): `Orcamento.max_passos = 8`, justificado pela Aula 05: um teto em **chamadas de ferramenta** (a unidade que custa tokens e escreve no mundo), com os motivos `orcamento_esgotado` e `laco_detectado`.

**O que o framework converteu em parâmetro:** o `recursion_limit`, com padrão **25** (`DEFAULT_RECURSION_LIMIT` do `langchain-core`, lido da versão instalada), que conta **superpassos do grafo** (cada nó executado é um), e não chamadas de ferramenta. A unidade mudou sem ninguém decidir. **Medido** com o modelo roteirizado: o menor limite que sustenta uma conversa até o fim é **9 + 2 por chamada de ferramenta** (9, 11, 17 e 23 superpassos para 0, 1, 4 e 7 chamadas), e **a pior conversa que o orçamento permite (8 chamadas, até `orcamento_esgotado`) pede 23**. Com o padrão de 25, a folga é de **2 superpassos**: a volta de correção do validador reexecuta 3 nós (`agente`, `garantir_trancamento`, `validar_resposta`) e, numa conversa longa, estouraria. O padrão do framework e o orçamento de 8 passos **colidem**, e nada no código da Parte 1 avisava disso.

**Declarado no código**, e com valor **diferente do padrão**: [`src/triagem/grafo.py:40`](../src/triagem/grafo.py#L40) = **60**, passado em toda chamada ([`src/triagem/sistema.py:63`](../src/triagem/sistema.py#L63)). É a rede de segurança **por baixo** do orçamento de passos, e não o orçamento.

**O que acontece se o padrão da biblioteca mudar numa atualização:**

- **Se o padrão subir** (ex.: 100): nada muda, porque o valor é declarado e não herdado.
- **Se eu o deixasse herdar e o padrão descesse** (ex.: 10): conversas legítimas passariam a terminar em `GraphRecursionError` sem nenhum commit nosso: uma regressão silenciosa de disponibilidade. **É por isso que o valor está no código, e a versão do framework, fixada.** A atualização do `langgraph` é uma **mudança de versão do sistema**, medida pela suíte da Parte 3, e não um `pip install -U`.
- **Se a semântica do contador mudar** (superpasso por chamada de ferramenta, por exemplo): o 60 passa a significar outra coisa. **Este risco não está coberto por teste**; só a leitura da nota de versão o pega.

### 5.4 O que ficou aberto (lacunas do desenho)

- **O detector de trancamento é uma expressão regular** (`trancar`, `trancamento`): um aluno que escreve "cancelar a matrícula" (caso 7 real, `docs/io.md` §4.2) **não** aciona a pós-condição L02. Quem escala, nesse caso, é o modelo. Medido: o agente real escolheu e declarou "tratado como trancamento" e pediu o RA; **não medi** se ele escalaria depois, e a pós-condição não o garantiria.
- **A L02 só age com RA confirmado** por `buscar_aluno`: sem RA, o diálogo continua com o modelo (correto), mas um modelo que nunca pede o RA nunca é corrigido pelo código.
- **O roteamento por `eventos[-1]`** (§2.3).
- **O teto de tempo é conferido entre chamadas**, não dentro delas ([`src/triagem/nos.py:36`](../src/triagem/nos.py#L36)).
