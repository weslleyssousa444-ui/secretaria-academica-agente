# CLAUDE.md — leia isto primeiro

Arquivo de entrada para o Claude Code numa máquina nova. Escrito em **12/11/2026**, pouco antes de o computador original ser vendido. **Tudo o que importa do trabalho está neste repositório**; o que **não** está aqui está listado na seção 8.

## 0. Como começar (nesta ordem)

1. Leia este arquivo, depois [`CONTINUIDADE.md`](CONTINUIDADE.md) (pendências, com comandos) e [`docs/mudancas.md`](docs/mudancas.md) (histórico e defeitos achados).
2. `git log --oneline -15` e `git status`: confira que o repositório está em dia com o GitHub.
3. Monte o ambiente (seção 2) e rode os testes (seção 3). Esperado: **238 passed, 1 deselected**.
4. **Antes de gastar cota do modelo, pergunte ao usuário o que ele quer fazer.** A cota é pequena (seção 4) e a gasta de um dia não volta.
5. Responda **em português**. O usuário escreve rápido e com erros de digitação; entenda a intenção.

## 1. O que é o projeto

Trabalho da disciplina **Agentes de IA com LLMs** (professor **Celso**), em 3 entregas sobre **um único repositório**: `secretaria-academica-agente` (GitHub `weslleyssousa444-ui/secretaria-academica-agente`, ramo `master`).

- **Grupo:** Weslley Soares de Sousa (usuário que opera o Claude Code), Pedro Akira, Henrique Gomes Matos (Operação, responsável designado pelo interruptor/parada) e Erick (**responsável de risco**).
- **O sistema:** um agente de triagem de secretaria acadêmica. O aluno escreve em português; o sistema responde dúvida do Regimento citando o artigo, emite declaração de matrícula e segunda via do histórico, ou **escala** o que não pode decidir. **Trancamento de matrícula é sempre decidido pela coordenação** (Art. 6º): o agente só abre o caso e o grafo **pausa** esperando a decisão (prazo de 48 h). Dados **sintéticos** (SQLite); não há dado real.
- **Funções de 13/11/2026:** segunda via de boleto, consulta de notas e o documento imprimível (`src/triagem/servicos.py`, `src/triagem/documentos.py`, prompt **v3**, Regimento Art. 11 e 12); o sistema tem **7 ferramentas**.
- **Parte 1:** agente com 4 ferramentas, verificador, API, imagem Docker. **Parte 2:** o sistema em **grafo LangGraph** (15 nós, 24 arestas, 12 condicionais), RAG por FTS5, memória de 3 tipos, pausa humana, contrato de saída. **Parte 3:** avaliação (`evals/`), *model card*/governança, segurança fora do prompt, observabilidade (OpenTelemetry).
- **Provedor e modelo:** API da **Groq** (endpoint compatível com OpenAI, `https://api.groq.com/openai/v1`), modelo **`qwen/qwen3.8-27b`**, plano gratuito. A variável se chama `OPENAI_API_KEY`, mas guarda a **chave da Groq**.

## 2. Montar o ambiente

Python **3.10 ou mais novo** (o projeto usou 3.11). Na máquina original: macOS, sem `brew`, sem Docker, sem `gh`; o ambiente era `.venv311`, criado com `uv`.

```bash
git clone https://github.com/weslleyssousa444-ui/secretaria-academica-agente.git
cd secretaria-academica-agente
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt     # o sistema + os testes, versões fixadas
python src/dados.py                     # recria dados/academico.db (não está no git)
```

**A chave da Groq não está no repositório (de propósito).** Para qualquer coisa que chame o modelo: `cp .env.example .env` e cole a chave em `OPENAI_API_KEY=`. Chave nova e gratuita, sem cartão: <https://console.groq.com/keys>. **Nunca** coloque chave em arquivo versionado, em documento ou em mensagem de commit.

## 3. Testes (offline, sem chave, sem rede)

```bash
OPENAI_API_KEY=x PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider
# esperado: 238 passed, 1 deselected
```

`OPENAI_API_KEY=x` é necessário: com a variável **vazia** a coleta dos testes quebra. O teste deselecionado é o `eval`, que usa o modelo real. O "modelo" dos testes é roteirizado: faz de propósito o que um modelo ruim faria, e o teste prova que o **código** barra.

Outros comandos úteis: `python conferir_grafo.py` (mostra os 15 nós e 24 arestas), `python src/chat.py --dica --trilha` (conversar; precisa da chave), `python src/demo_grafo.py` (8 demonstrações com o modelo real). Roteiro completo para pessoas: [`START.md`](START.md).

## 4. A cota da Groq, que decide o ritmo do trabalho

- **200.000 tokens por dia, por modelo** (plano gratuito `on_demand`, TPD). Janela **móvel de 24 h**, não um reinício à meia-noite.
- Uma rodada completa da suíte gasta **~170 a 190 mil tokens**: **quase um dia inteiro de cota**. Por isso as rodadas A e B não cabem no mesmo dia.
- Um teste de 5 tokens **pode passar com a cota quase no fim**: não use "a chamada pequena funcionou" como prova de que a cota voltou. Quando acaba, o erro é `429 ... tokens per day (TPD)`.
- O modelo **não pode ser trocado**: o sistema só sobe com modelo da lista aprovada ([`src/triagem/modelos.py`](src/triagem/modelos.py), controle ASI10) e só o `qwen/qwen3.8-27b` está nela. Exceção explícita (13/11/2026), para a correção do professor com outro modelo: `TRIAGEM_PERMITIR_MODELO_NAO_APROVADO=1` (o trace marca `agente.modelo_aprovado = false`; **não use para as rodadas A/B**). A comparação A × B exige o mesmo modelo nas duas rodadas.
- O plano pago (*Dev Tier*, `console.groq.com/settings/billing`) liberaria as duas rodadas no mesmo dia. **É decisão do grupo (cobrança); não ative sem o usuário pedir.**

## 5. Onde paramos (12/11/2026)

**Feito e no GitHub:** Partes 2 e 3 completas no que não depende de cota nem do grupo: grafo, API, 3 controles de segurança, trace, pacote `evals/`, regra de promoção **assinada antes** da versão B, *model card* reescrito, `docs/evals.md`, `docs/observabilidade.md`, `docs/seguranca.md`, `docs/mudancas.md`, 210 testes passando. Slides da apresentação (seção 7).

**Rodadas da suíte (37 casos, dataset `evals/dataset/golden_v1.2.0.json`):**

| Rodada | Pasta | Estado |
|---|---|---|
| **A** (código da Parte 2, **sem** o controle de identidade; `--ref parte-2` = commit `706c599`) | `evals/resultados/2026-11-11-A-r1` | **3 de 37** (só identidade). Resultado: **0 de 3**; o sistema sem o controle emitiu a declaração de outra aluna |
| **B** (código atual) | `evals/resultados/2026-11-11-B-r1` | **33 de 37**, mas medidos **antes** das funções de 13/11 (boleto, consulta, prompt v3). **Precisa ser refeita inteira** no código novo, numa pasta nova (`docs/mudancas.md` §7) |

O runner é **retomável**: pula o que já está em `execucoes.jsonl`. A pasta B está **versionada** justamente para a outra máquina continuar de onde parou.

**O que a rodada B parcial mediu** (`python -m evals.metricas evals/resultados/2026-11-11-B-r1/traces.jsonl --slo 0.95`, só leitura): p50 2,2 s, p95 11,7 s; término `respondeu` 33, `aguardando_humano` 6, exceção 1 (o 429, que **não** entra no SLI); **modelo servido diferente do pedido: 0 em 94 chamadas**; **SLI de qualidade 37/39 = 94,9%**; **SLO ≥ 95%: VIOLADO** por 2 casos. Os 2 casos são **`re05` e `rg03`**: o modelo foi reprovado duas vezes pelo validador e a resposta saiu pela **contingência**. **A causa não foi apurada**: o motivo da reprovação não fica no trace (lacuna **L29**, seção 6).

## 6. O que falta, em ordem

1. **Refazer a rodada B inteira** no código atual (37 casos, ~180 mil tokens), quando houver cota, numa pasta nova (a antiga fica como registro do código anterior):
   `python -m evals.rodar --rotulo B --run 1 --pasta evals/resultados/2026-11-14-B-r1`
2. **Completar a rodada A** (34 casos, ~170 mil tokens, **em outro dia**; se der 429, retome no dia seguinte):
   `python -m evals.rodar --rotulo A --run 1 --ref 706c599 --pasta evals/resultados/2026-11-11-A-r1`
3. Com as duas completas: `python -m evals.comparar evals/resultados/2026-11-11-A-r1 evals/resultados/2026-11-11-B-r1 --salvar docs/evidencias/comparacao-parte3.txt` e depois `python -m evals.atualizar_docs --a ...A-r1 --b ...B-r1 --traces evals/resultados/2026-11-11-B-r1/traces.jsonl --slo 0.95`. **Leia** o resultado contra a regra assinada (`evals/resultados/assinatura-regra-p3.txt`). Resultado ruim é resultado: **não ajuste a regra depois**. Os blocos **PENDENTE** de `docs/evals.md` §4.3 e `docs/observabilidade.md` §4 só são preenchidos pelo `atualizar_docs`, **nunca à mão**.
4. Reconstruir uma decisão **real** pelo trace e trocar o exemplo de teste de `docs/model-card.md` §11: `python -m evals.reconstruir evals/resultados/2026-11-11-B-r1/traces.jsonl --conversa <id>`. Registrar o SLO em `docs/observabilidade.md` §5, **mesmo que viole**.
5. **L29** (só **depois** das duas rodadas, para não mudar o código sob teste no meio da comparação): registrar no trace os `problemas` de `validar_resposta` (`src/triagem/nos.py`, nó `validar_resposta`) e o rascunho reprovado (este só com `AGENTE_TRACE_CONTEUDO` ligado), com teste; depois rodar `re05` e `rg03` de novo (~15 mil tokens). Hipótese **não confirmada** para `rg03`: o Art. 8º §3º remete ao Art. 9º §1º, que a busca não devolveu, e o validador reprova artigo citado que a ferramenta não devolveu.
6. **Reveja os slides** (seção 7) quando as rodadas fecharem: slides 9, 10, 11 e 14 trazem números parciais, rotulados como tais.

### O que só o grupo pode fazer (**não preencha por eles**)

- **Rotular à mão 20 saídas do juiz** (`evals/rotulagem/LEIA-ME.md`; depois `python -m evals.rotulagem medir`). Os 75 rótulos do Exercício 11 foram feitos por uma **IA**, não por pessoas (L24). Preencher isso seria fabricar rótulo.
- **Erick aceita ou recusa os três riscos propostos** (ASI09, ASI04, ASI03 "o portal não existe") em `docs/seguranca.md` §4 e `docs/model-card.md` §9. Um aceite escrito pelo Claude **não vale** como aceite dele.
- Decidir o **prazo de guarda do trace** (proposta: 90 dias) e quem acessa (L26).

### Decisões do usuário (não reabrir sem ele pedir)

- **Primeiro a Parte 2, depois a Parte 3**, sobre o mesmo repositório (já feito).
- **A chave da Groq que apareceu em texto numa sessão antiga não será revogada** (decisão de 11/11/2026; risco residual em `docs/seguranca.md` §6). Não a trate como pendência.
- **Seguir sem Docker.** O que depende dele fica **PENDENTE** em `docs/empacotamento.md`, sem ajustar o texto para parecer concluído.
- **Opcionais do enunciado da Parte 3 (multiagente, MCP, multimídia): não feitos.** Trabalho novo e grande; só começar se o usuário pedir, e depois de a rodada B fechar.

## 7. Apresentação ao professor Celso

28 slides em 5 etapas, com sumário, o grafo completo (slide 10) e um vídeo real do agente (`docs/apresentacao/video/`, gravado em 13/11/2026 no site publicado), em português. Publicados como Artifact na conta do usuário (privado): <https://claude.ai/artifact/JkCytjpKSCdpmfTo2JARMp>. **O código-fonte está versionado em [`docs/apresentacao/`](docs/apresentacao/)** (`deck.json` + `slides/*.html`, formato do tipo "Slides": 1920×1080, estilo inline, notas do apresentador em `<aside>`). Se o link não abrir na conta nova, publique esses arquivos de novo como deck. Os slides com número parcial têm o aviso "[Atualizar…]" nas notas.

## 8. O que NÃO veio com o repositório

| O que se perdeu | O que fazer |
|---|---|
| `.env` com a chave da Groq | criar outro (seção 2) |
| `.venv*` | recriar (seção 2) |
| `dados/academico.db` | `python src/dados.py` |
| **Memória automática do Claude** (`~/.claude/projects/...`) | **substituída por este arquivo**; não procure por ela |
| Tarefa agendada para 13/11 11:43 (retomar a rodada B) | existia só na sessão antiga e morreu; faça o passo 1 da seção 6 à mão |
| Pasta de rascunho da sessão (`scratchpad`) | nada de valor: os slides foram copiados para `docs/apresentacao/` |
| Hook "GateGuard" (pede para declarar fatos antes do primeiro Write/Edit/Bash de cada arquivo) | era do ambiente do usuário (plugin ECC), **não do repositório**; se existir na máquina nova, declare os fatos pedidos e repita a operação |

## 9. Regras de honestidade e de trabalho (valem sempre)

- **Não invente número.** Só afirme o que mediu ou leu; rode antes de afirmar. Número de teste, de nó e de caso sai de comando (`pytest`, `conferir_grafo.py`, `jq`), não da memória: este projeto já corrigiu afirmações que estavam erradas (`docs/mudancas.md` §3.3).
- **Não fabrique rótulo humano nem aceite de risco** (seção 6).
- **Segredo:** nunca versionar chave. Antes de todo commit, procure padrões de chave (`gsk_`, `sk-`) nos arquivos novos.
- **Git:** commits locais são livres. **`git push` só com autorização do usuário**, e a autorização de um envio **não vale** para o seguinte. A tag `parte-2` (commit `706c599`) é o código da versão A.
- **Relate o resultado como ele é:** teste que falha, cota que acabou, passo que foi pulado. Resultado ruim entra no documento; não se ajusta o critério.
- Ao documentar o estado do GitHub, cite o **último commit enviado** e mande conferir `git log origin/master..HEAD`; não escreva "o commit X está só local" (fica falso no push seguinte).

## 10. Mapa rápido do repositório

| Onde | O quê |
|---|---|
| `src/triagem/` | o sistema em grafo: `grafo.py`, `nos.py`, `estado.py`, `sistema.py` (ponto de entrada), `validacao.py`, `humano.py`, `regimento.py`, `memoria.py`, `modelos.py` (ASI10), `telemetria.py`, `saida.py` |
| `src/agente.py` | motor da Parte 1 reaproveitado (ferramentas, guardas, orçamento); `src/api.py`, `src/chat.py`, `src/coordenacao.py` |
| `src/prompts/` | prompts versionados (`triagem-v2.*` é o atual) |
| `evals/` | `rodar.py`, `comparar.py`, `metricas.py`, `atualizar_docs.py`, `reconstruir.py`, `rotulagem.py`; dataset em `evals/dataset/`; resultados em `evals/resultados/` |
| `tests/` | 238 testes offline (`test_controles.py` tenta a ação indevida de cada controle) |
| `docs/model-card.md` | **o documento central**: autoridade, riscos, lacunas L01–L29, §11 reconstrução de decisão |
| `docs/` | `grafo.md`, `arquitetura.md`, `io.md`, `prompts.md`, `rag.md`, `memoria.md`, `humano.md`, `evals.md`, `observabilidade.md`, `seguranca.md`, `mudancas.md`, `empacotamento.md` |
| `exercicios/` | exercícios 7 a 15 da disciplina (RAG, memória, LangGraph, MCP, suíte, riscos, observabilidade) |
| `logs/parte2/` | 8 demonstrações reais da Parte 2 (**contêm dado sintético com nome e RA**; lacuna L06) |

**Lacunas P1 abertas** (separam "se comportou bem nos testes" de "pode operar com dado real"): **L01** (o controle de identidade é correto dado um portal, e o portal **não existe**), **L06** (logs com dado pessoal em repositório público), **L14** (região, retenção e uso para treino da Groq **não verificados**), **L26** (o trace não tem prazo, controle de acesso nem remoção por titular). Conclusão do *model card*: **o sistema não deve operar com dados reais.**
