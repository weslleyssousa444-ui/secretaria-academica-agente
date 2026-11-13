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
| `73462e3`, `dd1415b` | 12/11/2026 | Parte 3 | Docs com o estado real do GitHub; lacuna L29 e estado parcial da rodada B |

**Os commits da Parte 2 e da Parte 3 até `dd1415b` estão no GitHub** (envios autorizados pelo usuário em 11/11 e 12/11/2026). Commits posteriores podem estar só locais: `git log origin/master..HEAD` mostra quais.

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
| O trace **não diz por que** o validador reprovou uma resposta | investigar `re05` e `rg03` na rodada B parcial (12/11/2026): o motivo só existia no checkpoint, apagado pela suíte | **aberto**, registrado como **L29** no *model card*; a correção (evento de validação no trace) espera A e B terminarem |

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
| **Rodada B da suíte** (37 casos, código atual) | **incompleta** (12/11/2026: 33 de 37, parou em `dm01` por cota). Antes, em 11/11, **não rodou**: a cota diária do `qwen/qwen3.8-27b` (200 mil tokens) acabou. A comparação A × B está **PENDENTE** em `docs/evals.md` §4.3, com o comando para completar |
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

## 6. Depois da devolutiva da Parte 2 (13/11/2026)

A devolutiva da Parte 2 (nota 2,2) corrigiu o repositório no estado de 23/09/2026 (commit `ba7fb89`), anterior ao sistema da Parte 2 (commits de 11/11/2026, tag `parte-2`). O mapa entre cada subcritério e onde ele está no repositório: [`docs/correcao-parte2.md`](correcao-parte2.md). Duas mudanças de código saíram da leitura da devolutiva:

| Mudança | Por quê | Teste |
|---|---|---|
| `TRIAGEM_PERMITIR_MODELO_NAO_APROVADO=1` libera, explicitamente, um modelo fora da lista (ASI10) | a correção roda com outro modelo (`gpt-oss:20b` no Ollama); com o controle fail-closed o sistema **não subiria**, e "falha de código desconta" | `tests/test_controles.py`: 6 testes novos (sobe, avisa e marca; só `1` libera; a API sobe) |
| O registro de execução da API (`logs/api-<conversa>.json`) grava `versao`, `modelo`, `modelo_aprovado`, `prompt` (arquivo e sha256), `parametros` (temperature, recursion_limit, orçamento com teto de tempo), `ferramentas_do_turno`, `buscas_no_regimento`, `chamadas_ao_modelo` e `duracao_s` | só os logs das demonstrações (`logs/parte2/`) diziam com que modelo, prompt e parâmetros rodaram; o da API, que é o caminho de uso, não (critérios 2a e 3c) | `tests/test_api.py::test_conversa_em_dois_turnos_emite_e_grava_registro`, `::test_duvida_pela_api_devolve_fonte_e_conta_a_busca` |
| `POST /mensagens` devolve o contrato inteiro (`resultado`, `fonte`, `suficiencia`) | a API devolvia um recorte sem `fonte` e `suficiencia`, os dois campos que o critério 1a cobra | `tests/test_api.py::test_conversa_em_dois_turnos_emite_e_grava_registro` |

**Efeito na comparação A × B:** as duas mudanças ficam fora do caminho medido pela suíte (a liberação é desligada por padrão e o runner já tinha a sua; a suíte não passa pela API). Os 4 casos que faltam da rodada B rodam no commit novo, e o `agente.versao` do trace registra isso.

A página de chat da demonstração está em [`web/`](../web/) e mostra a fonte (artigo do Regimento) e a suficiência de cada resposta.

Testes: **217 passed, 1 deselected** (eram 210).

## 7. Mais funções: boleto, consulta acadêmica e o documento de verdade (13/11/2026)

Pedido do usuário depois de usar o sistema publicado: o agente "não emitia" (registrava o protocolo, mas nada gerava o documento) e não atendia boleto nem consulta de notas.

| Mudança | Onde | Teste |
|---|---|---|
| Base fictícia: `disciplinas_cursadas` (notas determinísticas por RA), `mensalidades` (coerentes com `financeiro`: mesma quantidade e total), `boletos_emitidos`, `codigos_verificacao` | [`src/dados.py`](../src/dados.py) | `tests/test_servicos.py::test_mensalidades_batem_com_o_financeiro` |
| Ferramenta `consultar_historico` (leitura) e `emitir_boleto` (**escrita**, idempotente por competência; com várias em aberto devolve a lista para o agente perguntar) | [`src/triagem/servicos.py`](../src/triagem/servicos.py), na camada do grafo: o laço e o verificador da Parte 1 **não mudaram** | `tests/test_servicos.py` |
| Regimento: **Art. 11** (boleto) e **Art. 12** (consulta; revisão de nota é da coordenação); o Art. 10 passa a dizer "neste Regimento" em vez de "nos artigos anteriores" | [`dados/regimento_dados.py`](../dados/regimento_dados.py) | os testes do RAG continuam passando |
| Prompt **v3** (regras 9 e 10; o acesso ao documento só pelo campo `acesso` da ferramenta) | [`src/prompts/triagem-v3.md`](../src/prompts/triagem-v3.md) | |
| Controles: as duas ferramentas novas passam pela ASI03 (RA da sessão) e `emitir_boleto` conta no limite de 1 escrita por volta (ASI02) | [`src/triagem/nos.py`](../src/triagem/nos.py) | `test_ASI03_o_ra_de_outro_aluno_e_barrado_em_toda_ferramenta` (7 ferramentas), `test_boleto_e_escrita_e_conta_no_limite_por_volta` |
| Contrato: decisões `emitir_boleto` e `informar_situacao_academica`; validador aceita `BOL-` e não trata carga horária devolvida como prazo | [`src/triagem/saida.py`](../src/triagem/saida.py), [`src/triagem/validacao.py`](../src/triagem/validacao.py) | `test_protocolo_de_boleto_inventado_e_barrado`, `test_carga_horaria_devolvida_nao_e_prazo_inventado` |
| Documento de verdade: `GET /documentos/{protocolo}?c=` e a lista `documentos` na resposta do chat | [`src/triagem/documentos.py`](../src/triagem/documentos.py), [`docs/io.md`](io.md) §6 | `test_declaracao_emitida_tem_link_e_a_pagina_abre` |

**Efeito na avaliação (decisão do usuário, 13/11/2026: fazer direto no `master`).** Ferramentas, prompt e Regimento novos são **sistema novo**: os 33 casos já rodados da rodada B foram medidos no código anterior, e a comparação A × B só vale com a rodada B **inteira refeita** neste código (`docs/evals.md` §4.4; ~180 mil tokens). A rodada A continua sendo a tag `parte-2`.

Testes: **238 passed, 1 deselected**.
