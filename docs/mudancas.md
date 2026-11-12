# Mudanças do sistema, e o que cada etapa achou

Registro do que mudou entre a Parte 1 e a entrega da Parte 3, **commit a commit**, e dos **defeitos que apareceram ao documentar, testar ou rodar com o modelo real**. É o histórico que o *model card* (§12) resume. Datas e hashes vêm de `git log`; nada aqui foi reconstruído de memória.

**Convenção:** "achado" é um defeito ou uma afirmação falsa que **a própria entrega descobriu em si mesma** e corrigiu, com o teste ou a medição que o mostrou. Um defeito que **continua aberto** está no *model card*, seção Lacunas, e não aqui.

## 0. De onde se partiu

Em 11/11/2026, ao ler os enunciados das três entregas contra o repositório, a **Parte 2 não estava entregue**. Existiam a Parte 1 (agente, verificador, API, imagem), os Exercícios 7 a 15 (RAG, memória, LangGraph de exercício, MCP, suíte, riscos, observabilidade) e o *model card* da Parte 1. **Faltava** o sistema da Parte 2 como o enunciado o pede:

| Faltava | Onde está agora |
|---|---|
| o grafo integrado (RAG, memória, pausa humana, contrato de saída) | [`src/triagem/`](../src/triagem/), [`docs/grafo.md`](grafo.md) |
| os documentos de entrada e saída, prompts, arquitetura, RAG, humano | [`io.md`](io.md), [`prompts.md`](prompts.md), [`arquitetura.md`](arquitetura.md), [`rag.md`](rag.md), [`humano.md`](humano.md) |
| o prompt em pasta própria e versionado | [`src/prompts/`](../src/prompts/) (`prompts/` foi movido com `git mv`) |
| o conferidor do grafo e as demonstrações | [`conferir_grafo.py`](../conferir_grafo.py), [`src/demo_grafo.py`](../src/demo_grafo.py), [`logs/parte2/`](../logs/parte2/) |

O usuário decidiu: **primeiro a Parte 2, depois a Parte 3**, sobre o mesmo repositório.

## 1. Os commits

| Commit | Data | Etapa | O que entrou |
|---|---|---|---|
| `8fa0ae4` | 11/11/2026 | Parte 2 | O núcleo: grafo LangGraph (estado, nós, arestas), RAG por FTS5, memória de três tipos, pausa humana |
| `cbb82d6` | 11/11/2026 | Parte 2 | API e chat sobre o grafo; coordenação com token; `conferir_grafo.py`; marca de suficiência |
| `706c599` | 11/11/2026 | Parte 2 | Documentação completa; 8 demonstrações reais; as correções achadas ao documentar |
| `51c278b` | 11/11/2026 | Parte 3 | Três controles fora do prompt (ASI03, ASI10, ASI02), com testes que **tentam** a ação indevida |
| `616fea5` | 11/11/2026 | Parte 3 | Trace OpenTelemetry nas convenções GenAI |
| `1dfea71` | 11/11/2026 | Parte 3 | Pacote `evals/`: dataset v1.1.0, runner, comparador, métricas |
| `31979bf` | 11/11/2026 | Parte 3 | Rodada A parcial com o modelo real; comparador tolerante a rodada vazia |
| `57d5fa1` | 11/11/2026 | Parte 3 | Regra de promoção declarada **antes** da versão B; juiz e ficha de rotulagem; `seguranca.md` |
| `483cc20` | 11/11/2026 | Parte 3 | Dataset v1.2.0 (+4 casos de demonstração), `docs/evals.md` e `docs/observabilidade.md`, atributo `agente.aprovacao.edicao`, testes de autoridade, *model card* reescrito, este arquivo |
| `6925603` | 11/11/2026 | Parte 3 | Registra a decisão do usuário de não revogar a chave da Groq, com o risco residual declarado |

**Os commits da Parte 2 e da Parte 3 até `483cc20` estão no GitHub** (envio autorizado pelo usuário em 11/11/2026). O commit `6925603` (decisão de não revogar a chave) foi feito depois e está só local, aguardando autorização.

## 2. O que mudou na autoridade do sistema (em relação à Parte 1)

| Antes (Parte 1) | Agora | Onde |
|---|---|---|
| 4 ferramentas, laço próprio | 5 ferramentas (`consultar_regimento`), laço como grafo de 15 nós | [`docs/grafo.md`](grafo.md) |
| qualquer RA digitado era atendido | o RA vem da **sessão**; ferramenta recusa outro RA (ASI03) | `model-card.md` A8 |
| `LLM_MODELO` aceitava qualquer valor | só o modelo da lista sobe (ASI10) | `model-card.md` O6 |
| sem teto por volta do modelo | 4 chamadas, 1 escrita por volta (ASI02); 120 s por turno | `model-card.md` O1, O2 |
| trancamento: escalonado pelo código, fim | escalonado pelo código **e o grafo pausa** até a coordenação decidir (48h) | `model-card.md` A11, §10 |
| resposta final sem validação | protocolo, prazo e artigo citado validados em código | `model-card.md` A12 |
| exceção de ferramenta derrubava o processo | vira resultado de erro; o turno continua | `model-card.md` F3 |
| registro: JSON editável sem instante nem versão | trace com instante, versão, modelo, protocolo e revisão humana | `model-card.md` §11 |

## 3. Os achados (defeitos que a entrega achou em si mesma)

### 3.1 Ao construir a Parte 2

| Achado | Como apareceu | Correção |
|---|---|---|
| Mover `prompts/` para `src/prompts/` **quebrou** caminhos montados em código em `src/suite/juiz.py` e em `exercicios/aula09-langgraph/agente_langgraph.py` | a suíte de testes falhou depois do `git mv` | caminhos corrigidos; **teste de regressão** que confere os caminhos |
| Testes **tautológicos** (`or True`) e um teste **vazio** | revisão dos próprios testes | trocados por asserções exatas |
| Caso 5 com o modelo real: um artigo de **ruído** foi marcado como suficiente | demonstração 5 em `logs/parte2/05-fora-do-corpus.json` | marca `[SUFICIENTE: sim\|não]` declarada pelo modelo e **exigida pelo código**; ablação em `logs/parte2/ablacao-regra7*.json` |
| O parser **rígido** da marca mandou a resposta à contingência | a ablação, tentativa 3 | parser **tolerante à posição** (aceita a marca em qualquer ponto e a remove) |
| `GraphRecursionError` **não tratado**: a API respondia 500, e o estado parado era confundido com a pausa humana | teste do limite de passos | termina em `erro_fatal`; `ConversaEncerrada` separa "parou no meio" de "pausada" |
| **Sem teto de tempo** por turno | revisão do orçamento | 120 s por turno, checado antes de cada chamada |
| O **decaimento** da memória nunca era chamado | busca por quem chamava a função | roda ao subir o `Sistema`; teste `test_o_sistema_aplica_o_decaimento_ao_subir` |
| `subprocess` em `src/` violava o teste de ASI05 (execução de comando) | o teste de segurança | o commit é lido de `.git/HEAD`, sem processo filho |

### 3.2 Ao escrever a documentação e o trace (Parte 3)

| Achado | Como apareceu | Correção |
|---|---|---|
| A saída da reconstrução de decisão **não mostrava o que a coordenação corrigiu** | exemplo de reconstrução offline | atributo `agente.aprovacao.edicao` (só com o conteúdo ligado) e linha `editou:` em `evals/reconstruir.py` |
| `comparar` **quebrava** com uma rodada vazia | a rodada B morreu na cota | tolerante a rodada vazia |
| Gerador de documentos: `f-string` com contrabarra | erro de sintaxe ao gerar `docs/evals.md` | marcadores `@@nome@@` substituídos |
| Contagem de casos sintéticos **errada** no dataset (17, eram 12) | conferência da contagem | corrigida; casos de demonstração separados como v1.2.0 (`dm01` a `dm04`) |
| O sistema não tinha **nenhum teste** de que a lista de ferramentas é fechada | revisão do campo "autoridade" do *model card* | `test_o_sistema_tem_exatamente_cinco_ferramentas_e_nenhuma_de_trancamento` e `test_as_ferramentas_do_agente_nao_alteram_nem_apagam_nada` |

### 3.3 Afirmações minhas que estavam **erradas** e foram corrigidas

São o tipo de achado que mais importa para a honestidade da entrega: o texto afirmava mais do que a evidência.

| Afirmação | O que era verdade |
|---|---|
| "regras **cumulativas**" | não eram cumulativas; a redação foi corrigida |
| "a **secretaria** efetiva" | a decisão efetiva é da coordenação; a secretaria recebe a fila |
| "**rótulo humano**" para os rótulos do juiz do Ex.11 | eram de uma **IA**; a ressalva está em `docs/evals.md` §3 e no *model card* (L24) |
| "quatorze nós são código" | são **13** |
| contagens de dependências | recontadas do `requirements-agente.txt` |
| "71 testes" | contados: o número agora vem de `pytest`, não da memória |

## 4. O que a Parte 3 **não** entregou, e por quê

| Item | Situação |
|---|---|
| **Rodada B da suíte** (37 casos, código atual) | **não rodou**: a cota diária do `qwen/qwen3.8-27b` (200 mil tokens) acabou. A comparação A × B está **PENDENTE** em `docs/evals.md` §4.3, com o comando para completar |
| Rodada A completa | 3 de 37 casos (identidade). Resultado: **0 de 3**: o sistema sem o controle emitiu a declaração de outra aluna |
| Métricas, SLO medido, **trace real** | dependem da rodada B; `docs/observabilidade.md` §4 diz **PENDENTE** |
| Rótulos humanos do juiz | **o grupo precisa rotular** 20 saídas ([`evals/rotulagem/LEIA-ME.md`](../evals/rotulagem/LEIA-ME.md)); nenhum rótulo foi preenchido por código |
| Aceite de risco | **Erick** precisa aceitar ou recusar os três riscos propostos (`docs/seguranca.md` §4) |
| Multiagente, MCP, multimídia (opcionais do enunciado) | **não feitos** |

## 5. Para completar, na ordem

1. Esperar a cota do provedor voltar e rodar a rodada B, depois terminar a A (`docs/evals.md` §4.4).
2. `python -m evals.comparar`, `python -m evals.atualizar_docs` e `python -m evals.metricas`; **ler** o resultado contra a regra assinada antes de promover.
3. Reconstruir uma decisão real com `python -m evals.reconstruir` e **substituir** o exemplo de teste no *model card* §11.
4. O grupo rotula as 20 saídas; `python -m evals.rotulagem medir`.
5. Erick registra o aceite (ou a recusa) em `docs/seguranca.md` §4 e `docs/model-card.md` §9.
6. ~~Revogar a chave da Groq~~ que esteve num arquivo local (apagado, nunca commitado): o usuário decidiu em 11/11/2026 **não revogar** (`docs/seguranca.md` §6).
