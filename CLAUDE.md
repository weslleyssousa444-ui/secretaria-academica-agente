# CLAUDE.md — leia isto primeiro

Arquivo de entrada para o Claude Code numa máquina nova. Escrito em **12/11/2026**, pouco antes de o computador original ser vendido. **Tudo o que importa do trabalho está neste repositório**; o que **não** está aqui está listado na seção 8.

## 0. Como começar (nesta ordem)

1. Leia este arquivo, depois [`CONTINUIDADE.md`](CONTINUIDADE.md) (pendências, com comandos) e [`docs/mudancas.md`](docs/mudancas.md) (histórico e defeitos achados).
2. `git log --oneline -15` e `git status`: confira que o repositório está em dia com o GitHub.
3. Monte o ambiente (seção 2) e rode os testes (seção 3). Esperado: **292 passed, 1 deselected**.
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
# esperado: 292 passed, 1 deselected
```

`OPENAI_API_KEY=x` é necessário: com a variável **vazia** a coleta dos testes quebra. O teste deselecionado é o `eval`, que usa o modelo real. O "modelo" dos testes é roteirizado: faz de propósito o que um modelo ruim faria, e o teste prova que o **código** barra.

Outros comandos úteis: `python conferir_grafo.py` (mostra os 15 nós e 24 arestas), `python src/chat.py --dica --trilha` (conversar; precisa da chave), `python src/demo_grafo.py` (8 demonstrações com o modelo real). Roteiro completo para pessoas: [`START.md`](START.md).

## 4. A cota da Groq, que decide o ritmo do trabalho

- **200.000 tokens por dia, por modelo** (plano gratuito `on_demand`, TPD). Janela **móvel de 24 h**, não um reinício à meia-noite.
- Uma rodada completa da suíte gasta **~170 a 190 mil tokens**: **quase um dia inteiro de cota**. Por isso as rodadas A e B não cabem no mesmo dia.
- Um teste de 5 tokens **pode passar com a cota quase no fim**: não use "a chamada pequena funcionou" como prova de que a cota voltou. Quando acaba, o erro é `429 ... tokens per day (TPD)`.
- O modelo **não pode ser trocado**: o sistema só sobe com modelo da lista aprovada ([`src/triagem/modelos.py`](src/triagem/modelos.py), controle ASI10) e só o `qwen/qwen3.8-27b` está nela. Exceção explícita (13/11/2026), para a correção do professor com outro modelo: `TRIAGEM_PERMITIR_MODELO_NAO_APROVADO=1` (o trace marca `agente.modelo_aprovado = false`; **não use para as rodadas A/B**). A comparação A × B exige o mesmo modelo nas duas rodadas.
- O plano pago (*Dev Tier*, `console.groq.com/settings/billing`) liberaria as duas rodadas no mesmo dia. **É decisão do grupo (cobrança); não ative sem o usuário pedir.**

## 5. Onde paramos (13/11/2026)

**Feito e no GitHub:** Partes 2 e 3 completas no que não depende de cota: grafo, API, 3 controles de segurança, trace com guarda de 90 dias, pacote `evals/`, regra de promoção **assinada antes** da versão B, *model card*, `docs/evals.md`, `docs/observabilidade.md`, `docs/seguranca.md`, `docs/mudancas.md`. Em 13/11: site publicado (Render + Hostinger), boleto, notas e documento imprimível, os opcionais (MCP, 2º agente, voz) e a apresentação de 32 slides. **263 testes passando.**

**Rodadas da suíte (37 casos, dataset `evals/dataset/golden_v1.2.0.json`):**

| Rodada | Pasta | Estado |
|---|---|---|
| **A** (código da Parte 2, **sem** o controle de identidade; `--ref parte-2` = commit `706c599`) | `evals/resultados/2026-11-11-A-r1` | **37 de 37, completa** (23/11): **86%**; identidade **0 de 3** (emitiu a declaração de outra aluna) |
| **B** (código `b9351a8`) | `evals/resultados/2026-11-16-B-r1` | **37 de 37, completa** (16 e 17/11): **86% aprovados**; reprovados pe01, pe02, rg01, rg03, rg05; SLI 94,1%, SLO violado (`docs/evidencias/rodada-B-2026-11-16.txt`). A pasta `2026-11-11-B-r1` é o registro do código anterior |
| **C** (código atual, `1a13167`: B + correções) | `evals/resultados/2026-11-23-C-r1` | **37 casos** (23/11; `em01` caiu por falha do provedor): **97%**, regra C × B cumprida, **promovida**; SLO 97,9% atendido |

O runner é **retomável**: pula o que já está em `execucoes.jsonl`. A pasta B está **versionada** justamente para a outra máquina continuar de onde parou.

**O que a rodada B completa mediu** (`python -m evals.metricas evals/resultados/2026-11-16-B-r1/traces.jsonl --slo 0.95`, só leitura): p50 2,7 s, p95 55 s; término `respondeu` 43, `aguardando_humano` 7, `erro_fatal` 1 e exceção 1 (falhas do provedor, fora do SLI); **modelo servido diferente do pedido: 0 em 113 chamadas**; **SLI de qualidade 48/51 = 94,1%**; **SLO ≥ 95%: VIOLADO**. O `rg03` voltou a sair pela **contingência**; a causa segue não apurada porque o motivo da reprovação não fica no trace (lacuna **L29**, seção 6). A rodada parcial anterior (`2026-11-11-B-r1`, código antigo) tinha dado 94,9%.

## 6. O que falta, em ordem

1. ~~Refazer a rodada B~~: **feita em 16 e 17/11** (`evals/resultados/2026-11-16-B-r1`, 37/37).
2. ~~Completar a rodada A~~: **feita em 23/11** (37/37).
3. ~~Comparação A × B~~: **feita em 23/11** (`docs/evals.md` §4.3, `docs/evidencias/comparacao-parte3.txt`). **Veredito pela regra assinada: B NÃO é promovida** (R1, R2, R4 cumpridas; **R3 violada**: pendência −20, Regimento −40). Ressalva registrada: a B rodou com o prompt v3, não o v2 que a regra previa. **Não ajuste a regra.**
4. ~~SLO e reconstrução~~: SLO registrado em `docs/observabilidade.md` §5 (94,1%, violado); decisão real (`tr05`) reconstruída no *model card* §11.
5. **L29: corrigida no código em 23/11** (`telemetria.registrar_validacao`, evento `agente.validacao.reprovada`; o `evals.reconstruir` mostra o motivo). **Falta** (cota, ~15 mil tokens) rodar de novo o `rg03` e o `re05` com trace e ler a causa: `python -m evals.rodar --rotulo B --run 2 --casos rg03,re05 --pasta evals/resultados/<data>-L29`, depois `python -m evals.reconstruir <pasta>/traces.jsonl --conversa eval-B-r2-rg03`. Hipótese **não confirmada** para `rg03`: o Art. 8º §3º remete ao Art. 9º §1º, que a busca não devolveu.
6. ~~Slides~~: atualizados em 23/11 com A e B completas (18, 21, 31).
7. ~~Versão C~~: **rodada e promovida em 23/11** (`evals/resultados/2026-11-23-C-r1`): **97% × 86% da B**, todas as regras assinadas cumpridas, SLO 97,9% atendido (`docs/evals.md` §4.3b). Pendências opcionais: repetir o `em01` (falha do provedor; o runner o refaz sozinho com o mesmo comando) e uma segunda repetição para medir ruído.

### O que só o grupo pode fazer (**não preencha por eles**)

- **Rótulo humano do juiz: feito.** Erick Sousa rotulou as 20 saídas em 16/11 (`evals/rotulagem/para_rotular.csv`); os rótulos do Claude (`rotulos_claude.csv`, IA) ficam como segunda leitura (13 de 20 iguais, `humano_vs_claude.csv`). **Juiz medido em 16/11:** 75% de concordância e 25% de recall contra o rótulo humano (limiar 85%/80%): **não adotado** (`docs/evidencias/juiz-x-humano.txt`, `evals/rotulagem/desacordos.csv`). Não ajuste o limiar; se for melhorar, mude a rubrica e meça de novo.
- **Riscos: Erick decidiu em 17/11/2026: ASI09, ASI04 e ASI03 NÃO aceitos** (`docs/seguranca.md` §4, `docs/model-card.md` §9). Seguem abertos; o que os trataria está listado em `seguranca.md` §4. **Não apresente nenhum deles como "aceito".** Tratar é decisão do grupo. **Risco aceito:** `temperature=0` não garante a mesma saída, aceito por **Erick em 23/11/2026** (comunicado por Weslley, com Erick presente; `seguranca.md` §4).
- ~~Prazo de guarda do trace~~: **decidido por Weslley em 13/11 (90 dias) e implementado** (`src/triagem/retencao.py`); L26 fechada.

### Decisões do usuário (não reabrir sem ele pedir)

- **Primeiro a Parte 2, depois a Parte 3**, sobre o mesmo repositório (já feito).
- **A chave da Groq que apareceu em texto numa sessão antiga não será revogada** (decisão de 11/11/2026; risco residual em `docs/seguranca.md` §6). Não a trate como pendência.
- **Seguir sem Docker.** O que depende dele fica **PENDENTE** em `docs/empacotamento.md`, sem ajustar o texto para parecer concluído.
- **Opcionais da Parte 3 (multiagente, MCP, multimídia): feitos em 13/11/2026 a pedido do usuário**, em volta do agente do aluno e sem mudá-lo ([`docs/multiagente.md`](docs/multiagente.md), [`docs/mcp.md`](docs/mcp.md), [`docs/multimidia.md`](docs/multimidia.md)): servidor MCP só leitura, assistente da coordenação (2º agente, não decide), voz no site. O assistente **não foi avaliado** com o modelo real; a medição está pronta (`python -m evals.avaliar_assistente`, 6 alunos fictícios, metas declaradas no arquivo) e gasta cota do mesmo modelo da rodada B. Existe uma **simulação** com modelo roteirizado (`python -m evals.simular_assistente`), rotulada como tal no slide 23: ela prova os controles, **não** é medição; não a cite como desempenho do modelo.

## 7. Apresentação ao professor Celso

32 slides em 5 etapas, com sumário, o grafo completo (slide 10), os casos de teste de segurança (slides 19 e 20), os opcionais multiagente/MCP/voz (slide 23), o vídeo (slide 25), o QR code do site (slide 27, imagem em `docs/apresentacao/video/qr-site.png`) e um vídeo real do agente (`docs/apresentacao/video/`, gravado em 13/11/2026 no site publicado), em português. Publicados como Artifact na conta do usuário (privado): <https://claude.ai/artifact/JkCytjpKSCdpmfTo2JARMp>. **O código-fonte está versionado em [`docs/apresentacao/`](docs/apresentacao/)** (`deck.json` + `slides/*.html`, formato do tipo "Slides": 1920×1080, estilo inline, notas do apresentador em `<aside>`). Se o link não abrir na conta nova, publique esses arquivos de novo como deck. Os slides com número parcial têm o aviso "[Atualizar…]" nas notas.

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
| `src/mcp_secretaria.py`, `src/assistente_coordenacao.py`, `src/triagem/handoff.py` | servidor MCP só leitura, o 2º agente (parecer para a coordenação: `python src/coordenacao.py preparar CASO-3001`) e o contrato de handoff entre os dois (23/11/2026; `docs/multiagente.md`) |
| `src/prompts/` | prompts versionados (`triagem-v3.*` é o atual; `coordenacao-v1.txt` é o do 2º agente) |
| `evals/` | `rodar.py`, `comparar.py`, `metricas.py`, `atualizar_docs.py`, `reconstruir.py`, `rotulagem.py`; dataset em `evals/dataset/`; resultados em `evals/resultados/` |
| `tests/` | 292 testes offline (`test_controles.py` tenta a ação indevida de cada controle) |
| `docs/model-card.md` | **o documento central**: autoridade, riscos, lacunas L01–L29, §11 reconstrução de decisão |
| `docs/` | `grafo.md`, `arquitetura.md`, `io.md`, `prompts.md`, `rag.md`, `memoria.md`, `humano.md`, `evals.md`, `observabilidade.md`, `seguranca.md`, `mudancas.md`, `empacotamento.md` |
| `exercicios/` | exercícios 7 a 15 da disciplina (RAG, memória, LangGraph, MCP, suíte, riscos, observabilidade) |
| `logs/parte2/` | 8 demonstrações reais da Parte 2 (**contêm dado sintético com nome e RA**; lacuna L06) |

**Lacunas P1 abertas** (separam "se comportou bem nos testes" de "pode operar com dado real"): **L01** (o controle de identidade é correto dado um portal, e o portal **não existe**), **L06** (logs com dado pessoal em repositório público), **L14** (região, retenção e uso para treino da Groq **não verificados**). A **L26** (prazo do trace) foi fechada em 13/11/2026. Conclusão do *model card*: **o sistema não deve operar com dados reais.**
