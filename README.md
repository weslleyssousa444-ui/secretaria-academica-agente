# Atendimento de secretaria acadêmica — sistema de triagem (Partes 1, 2 e 3)

> **Quer só rodar e testar?** Veja o [`START.md`](START.md): um caminho sem chave de API (testes e relatórios já gravados) e um com a chave gratuita da Groq (chat, demo, API).

**Grupo:** Weslley Soares de Sousa, Pedro Akira, Henrique Gomes Matos, Erick

**O problema em uma frase:** decidir se uma solicitação de aluno (declaração de matrícula, segunda via de histórico ou trancamento de matrícula) pode ser atendida automaticamente ou precisa ser encaminhada a um atendente humano da secretaria, cruzando o que o aluno relata com o que o sistema acadêmico registra.

A pesquisa completa do case está em [`docs/case.md`](docs/case.md) (usuários, workflow, justificativa de negócio, verificador) e [`docs/modelos.md`](docs/modelos.md) (escolha do modelo).

---

## Como rodar

O sistema (Parte 2) usa LangGraph e exige **Python 3.10 ou mais novo** (o ambiente do projeto foi montado em 3.11). Os scripts da Parte 1 (`demo.py`, `verificador.py`) continuam rodando em 3.9.

```bash
git clone https://github.com/weslleyssousa444-ui/secretaria-academica-agente.git
cd secretaria-academica-agente

python3.11 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\Activate.ps1

pip install -r requirements-dev.txt     # o sistema + os testes, com versões fixadas

cp .env.example .env
# edite .env: OPENAI_API_KEY=<sua chave da Groq>
# (crie a chave em https://console.groq.com/keys — free tier, sem cartão)

python src/dados.py              # cria e semeia o banco simulado (idempotente)
python -m pytest                 # 256 testes offline, sem chave e sem rede
```

### Rodar com outro modelo (por exemplo, na correção, com Ollama)

Por segurança (ASI10, `docs/seguranca.md` §3), o sistema **só sobe** com o modelo aprovado (`qwen/qwen3.8-27b`). Para rodar com outro modelo, ligue a liberação explícita; o sistema avisa no terminal e o trace marca as execuções como de modelo **não aprovado**:

```bash
# .env (ou variáveis de ambiente)
OPENAI_API_KEY=ollama                         # o Ollama ignora o valor, mas o SDK exige um
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODELO=gpt-oss:20b
TRIAGEM_PERMITIR_MODELO_NAO_APROVADO=1        # só o valor 1 libera
```

Os testes (`python -m pytest`) não dependem do modelo: rodam offline com um modelo roteirizado.

A instalação de `requirements-agente.txt` (o que a imagem Docker usa) foi verificada num ambiente limpo. O `requirements.txt` da raiz traz também as dependências dos Exercícios 7 e 8 (`torch`, `sentence-transformers`, ~2 GB), que **o sistema não usa**.

## Como usar

O sistema conversa em **texto livre, em português**, como o widget de chat do portal do aluno faria, e devolve um **objeto validado**. Há três formas de interagir:

| Quem | Comando | O que faz |
|---|---|---|
| **o aluno** (terminal) | `python src/chat.py --dica` | conversa com o sistema; `--trilha` mostra os nós do grafo, `--ra 20231045` simula a sessão autenticada do portal (a memória só abre com ela) |
| **o aluno** (HTTP) | `python -m uvicorn api:app --app-dir src --port 8000` | `POST /mensagens` com `{"mensagem": "...", "conversa_id": "..."}` |
| **a coordenação** | `python src/coordenacao.py listar` · `decidir CASO-3001 aprovar --por coord-1` | decide os trancamentos que o grafo deixou **esperando** |

Outros comandos: `python src/demo_grafo.py` (as 8 demonstrações da Parte 2, contra o modelo real, com log em `logs/parte2/`) · `python conferir_grafo.py` (nós e arestas do grafo entregue) · `python src/verificador.py` (os 40 casos da Parte 1).

> O modelo padrão é o `qwen/qwen3.8-27b` na **Groq** (free tier, `docs/modelos.md` §3.5). O free tier tem cota diária por modelo: se acabar (`tokens per day`), espere ou troque `LLM_MODELO` no `.env`.

**O que a pessoa digita:** uma mensagem em português descrevendo o pedido, com ou sem o RA. Exemplos: *"Preciso de uma declaração de matrícula. Meu RA é 20231045."*; *"Quero trancar minha matrícula esse semestre. Meu RA é 20229012."*; *"O que vale como comprovante de pagamento?"*.

**O que o sistema faz com aquilo:** identifica o pedido, consulta o sistema acadêmico simulado (cadastro e financeiro, em SQLite) e o Regimento (busca textual), e **decide** segundo as regras de `docs/case.md` §2.1: emite o documento, ou encaminha o caso à secretaria. Toda resposta ao aluno é conferida em código contra o que as ferramentas devolveram (protocolo, prazo, artigo citado) antes de sair.

**Que saída ela recebe** (`docs/io.md`): o texto da resposta, mais um objeto com a **decisão**, a **fonte** que a sustenta e a **suficiência** (se o sistema teve base para responder). Se emitiu: o protocolo `DOC-xxxx`. Se escalou: o protocolo `CASO-xxxx` e o prazo de 48 h.

**Exemplo completo, copiado de uma execução real** ([`logs/parte2/06-aprovacao-humana.json`](logs/parte2/06-aprovacao-humana.json), commit `cbb82d6`, 2026-11-11T14:45:43Z, modelo `qwen/qwen3.8-27b`):

> **Aluno:** Quero trancar minha matrícula esse semestre. Meu RA é 20229012.
>
> **Agente:** Olá, Bruno. Seu pedido de trancamento de matrícula foi encaminhado à secretaria para análise e decisão.
> 
> - Protocolo: CASO-3001
> - Prazo de retorno: 48h
> 
> Você será informado assim que houver uma decisão.

A saída inteira que o sistema devolveu nesse turno:

```json
{
  "resultado": "Olá, Bruno. Seu pedido de trancamento de matrícula foi encaminhado à secretaria para análise e decisão.\n\n- Protocolo: CASO-3001\n- Prazo de retorno: 48h\n\nVocê será informado assim que houver uma decisão.",
  "decisao": "escalar_trancamento",
  "fonte": [
    {
      "tipo": "ferramenta",
      "referencia": "buscar_aluno:20229012"
    },
    {
      "tipo": "ferramenta",
      "referencia": "escalar_para_humano:CASO-3001"
    }
  ],
  "suficiencia": {
    "suficiente": true,
    "motivo": "decisão tomada com o retorno de uma ferramenta"
  },
  "protocolo": "CASO-3001",
  "aguardando_humano": true,
  "termino": "respondeu"
}
```

**O que acontece quando o grafo para e espera alguém.** Esse pedido é um **trancamento**, e o agente **nunca decide trancamento**: ele abre o caso (`CASO-3001`), responde ao aluno **na hora**, e o grafo **para** (`aguardando_humano: true`) até a coordenação decidir. Enquanto espera, qualquer mensagem do aluno na mesma conversa devolve o estado do pedido, sem chamar o modelo e sem abrir outro caso. A coordenação vê a tela do caso (`listar`) e responde `aprovar`, `rejeitar` ou `aprovar_editando`:

```text
$ python src/coordenacao.py decidir CASO-3001 aprovar_editando --por coord-1 --editar semestre_efetivo=2027.1
{"protocolo": "CASO-3001", "ja_decidido": false, "decisao": "aprovado", "conflito": false}
$ (a mesma decisão, repetida)
{"protocolo": "CASO-3001", "ja_decidido": true, "decisao": "aprovado", "conflito": false}
```

A segunda chamada **não grava nada** (`ja_decidido: true`). Se ninguém responder em 48 h, o caso **vence** e volta à fila da secretaria (`python src/coordenacao.py expirar`, rodado por rotina). Detalhes: [`docs/humano.md`](docs/humano.md).

**O que o sistema não faz:**

- **não decide trancamento**: todo pedido é encaminhado, mesmo para aluno em situação regular, e a decisão é da coordenação; o sistema também não altera a matrícula;
- **não confia na palavra do aluno** quando ela contradiz o sistema financeiro sem comprovante: escala em vez de emitir;
- **não emite documento fora do catálogo** (declaração de matrícula, segunda via de histórico);
- **não verifica quem é o aluno**: qualquer RA digitado é atendido (lacuna L01 do [model card](docs/model-card.md)); por isso só use dados sintéticos;
- **não avisa o aluno** da decisão da coordenação (não há canal de saída).

**Quando o sistema não sabe responder** (`suficiencia.suficiente = false`, com o motivo): falta o RA (ele pergunta); o RA não existe (confirma uma vez e escala); a dúvida não está no Regimento (diz o que o Regimento trata e oferece encaminhar); o pedido está fora do escopo (diz o que atende). Se o provedor falhar, a conversa termina com `erro_fatal` e o aluno é orientado a procurar a secretaria: ele nunca fica sem resposta.

## Exercício 7 — RAG sobre o Regimento Acadêmico

Complementar (Aula 07), sobre um Regimento Acadêmico **simulado**. Relatório completo em [`exercicios/aula-07-resposta-que-cita.md`](exercicios/aula-07-resposta-que-cita.md).

```bash
python src/indice_rag.py    # gera o índice (baixa o modelo de embedding na 1ª vez, ~470MB)
python src/avaliar_rag.py   # recall@k, fidelidade, citação verificável, varredura do limiar
python src/modos_de_falha.py  # reproduz os 4 modos de falha + teste de corpus desatualizado
```

Resultado: recall@k 100%, citações verificáveis 100%, fidelidade 80%, 0 recusas indevidas.

## Exercício 8 — Memória do agente de triagem

Complementar (Aula 08): episódica, semântica e procedural, com idempotência, desempate de contradição por carimbo de tempo, decaimento e esquecimento seletivo verificado. Decisão de projeto em [`docs/memoria-ex8.md`](docs/memoria-ex8.md); relatório da implementação em [`exercicios/aula-08-memoria-do-case.md`](exercicios/aula-08-memoria-do-case.md).

```bash
python src/memoria_demo.py   # roda tudo: fronteira, idempotência, contradição, não reprodutibilidade, esquecimento
```

Resultado: memória muda a resposta do agente para a mesma pergunta (não reprodutibilidade real, medida); remoção de titular só ficou completa depois de verificar — a primeira passada deixou vestígio num checkpoint.

## Exercício 9 — Agente de triagem em LangGraph

Sem enunciado formal (Aula 09; o sistema integrado da Parte 2 está em `src/triagem/`). Reescreve o núcleo do Ex.6 como `StateGraph`, com checkpointer em arquivo e `interrupt()`/`Command(resume=...)` para a aprovação de trancamento pela coordenação. Ambiente Python 3.11 à parte (`exercicios/requirements-aula9-10.txt` — `mcp`/`langgraph` exigem >=3.10). Detalhes em [`exercicios/aula09-langgraph/README.md`](exercicios/aula09-langgraph/README.md).

## Exercício 10 — Servidor e cliente MCP (CNPJ + CEP, BrasilAPI)

Servidor MCP (`consultar_cnpj`, `consultar_cep`, Streamable HTTP) + cliente que encadeia as duas consultas sobre a [BrasilAPI](https://brasilapi.com.br/docs). Código e justificativas em comentário, sem relatório à parte (como o enunciado pede) — ver [`exercicios/aula10-mcp/`](exercicios/aula10-mcp/).

```bash
source .venv311/bin/activate
python exercicios/aula10-mcp/servidor_cnpj_cep.py &      # terminal 1
python exercicios/aula10-mcp/cliente_cnpj.py "19.131.243/0001-97"   # terminal 2
```

## Exercício 11 — A suíte do case

Avaliação do agente de triagem: *golden dataset* de 24 casos com origem declarada (`dados/golden_v1.json`), quatro níveis (resultado, decisão, trajetória, texto) mais um juiz LLM de fidelidade validado contra rótulos, e a regra de promoção gravada **antes** de qualquer execução (`dados/regra_de_promocao.json`, assinada em `logs/suite/assinatura-regra.txt`). Desenho em [`exercicios/aula-11-avaliacao.md`](exercicios/aula-11-avaliacao.md); resultado, matriz do juiz e decisão em [`exercicios/aula-11-suite-do-case.md`](exercicios/aula-11-suite-do-case.md).

```bash
python src/suite/executor.py --versao A --run 1      # grava logs/suite/exec-A-r1.jsonl (retomável; consome tokens da Groq)
python src/suite/juiz.py --execucoes A1,B1           # veredictos do juiz (modelo openai/gpt-oss-120b)
python src/suite/relatorio.py                        # saída completa, sem chamar modelo
python -m pytest tests/test_suite.py -v              # 20 testes dos avaliadores, offline
```

Os rótulos de validação do juiz são **provisórios, do assistente de IA, não de uma pessoa**; substituí-los por rótulos humanos é editar `dados/rotulos_juiz_v1.json` e rodar `relatorio.py` de novo.

## Exercício 12 — Model card do agente, com evidência

Governança (Aula 12): o *model card* do agente de triagem em [`docs/model-card.md`](docs/model-card.md), com 12 campos (**reescrito na Parte 3 para o sistema em grafo**; a versão do Exercício 12 está no histórico do git, `b3f4596`). Cada afirmação aponta para a linha de código, o teste, o log ou a saída de comando que a sustenta, ou está marcada como **LACUNA** (lista no fim do documento, com correção e prioridade). As saídas de comando citadas estão em [`docs/evidencias/`](docs/evidencias/).

```bash
python -m pytest -q   # 256 passed, 1 deselected (Python 3.10+), sem chave de API
```

`tests/test_autoridade.py` prova os limites aplicados fora do modelo (o roteiro de teste faz o "modelo" desobedecer o prompt e verifica que o código barra). `tests/test_lacunas.py` fixa o comportamento atual de cada lacuna; quando uma for corrigida, o teste dela falha e deve ser invertido.

## Exercício 13 — Imagem Docker e CI/CD

O agente empacotado como imagem (usuário sem privilégio, só 4 dependências, 248 MB), rodando como API (`src/api.py`) com o banco e os registros num volume, e um pipeline no GitHub Actions: segurança (hadolint, Trivy), testes offline, eval com o modelo real e publicação da imagem no GHCR. Decisões e resultados em [`docs/empacotamento.md`](docs/empacotamento.md); o que falta rodar, em [`CONTINUIDADE.md`](CONTINUIDADE.md).

```bash
docker compose up --build              # API em localhost:8000, estado no volume
curl localhost:8000/saude
```

## Exercício 14 — Os dez riscos (OWASP ASI01–ASI10)

Os dez riscos do catálogo da OWASP para aplicações agênticas, avaliados no agente de triagem: onde existe, cenário de ataque, impacto de 1 a 3 e mitigação, mais dois riscos aceitos declarados. Relatório em [`exercicios/aula14-respostas.md`](exercicios/aula14-respostas.md); evidências em [`docs/evidencias/seguranca-ex14.txt`](docs/evidencias/seguranca-ex14.txt). Os de maior impacto: **ASI03** (o agente atende qualquer RA), **ASI04** (base e dependências sem *digest*/hash, tag `latest`) e **ASI10** (o pipeline publica a imagem sem esperar o *eval*).

```bash
python -m pytest tests/test_seguranca.py tests/test_api_seguranca.py -v   # 17 + 5 testes offline, sem chave de API (os da API exigem Python >= 3.10)
```

## Exercício 15 — Plano de observabilidade

O plano de um agente de trocas de loja virtual (perguntas, árvore de *spans* nas convenções GenAI do OpenTelemetry, modos de falha, SLOs e alertas), com um apêndice que aponta o que o agente de triagem já tem e o que falta para a Parte 3. Em [`exercicios/aula15-plano-de-observabilidade.md`](exercicios/aula15-plano-de-observabilidade.md).

## Parte 3 — avaliar, governar, proteger e observar

O mesmo sistema da Parte 2, agora com **evidência** de que se comporta como o grupo diz. Tudo roda offline, exceto a suíte com o modelo real (precisa da chave e da cota da Groq).

| O quê | Onde | Como ver |
|---|---|---|
| **Avaliação**: *golden dataset* v1.2.0 (37 casos), níveis de checagem, regra de promoção assinada **antes** da versão B, juiz e rotulagem humana | [`docs/evals.md`](docs/evals.md), [`evals/`](evals/) | `python -m evals.rodar --help`, `python -m evals.comparar --help` |
| **Governança**: *model card* do sistema entregue, com lacunas e riscos aceitos | [`docs/model-card.md`](docs/model-card.md), [`docs/mudancas.md`](docs/mudancas.md) | |
| **Segurança**: riscos ASI do case, três controles **fora do prompt** (identidade da sessão, modelo aprovado, teto de chamadas), dados pessoais, chave fora do repositório | [`docs/seguranca.md`](docs/seguranca.md), [`src/triagem/modelos.py`](src/triagem/modelos.py), [`tests/test_controles.py`](tests/test_controles.py) | `python -m pytest tests/test_controles.py -v` |
| **Observabilidade**: trace OpenTelemetry (GenAI), modos de falha, SLI e SLO | [`docs/observabilidade.md`](docs/observabilidade.md), [`src/triagem/telemetria.py`](src/triagem/telemetria.py) | `TRIAGEM_TRACES_DIR=traces python src/chat.py` e depois `python -m evals.reconstruir traces/traces.jsonl --conversa <id>` |

```bash
python -m pytest -q                         # 256 passed, 1 deselected; sem chave
# com a chave da Groq e cota nova (cada rodada completa custa ~170 mil tokens): ver docs/evals.md §4.4
python -m evals.rodar --rotulo B --run 1 --pasta evals/resultados/2026-11-11-B-r1
```

**O que está medido e o que está pendente, sem arredondar:** o ataque de identidade foi medido com o modelo real na versão **sem** o controle (3 de 3 casos emitiram a declaração de outra aluna: `evals/resultados/2026-11-11-A-r1`). **A rodada B não rodou** (a cota diária do modelo acabou), então **a comparação A × B, as métricas e o SLO medido estão PENDENTES**, e os documentos dizem isso nos blocos próprios. Dependem **do grupo**: rotular 20 saídas do juiz (`evals/rotulagem/LEIA-ME.md`) e o aceite de risco de Erick (`docs/seguranca.md` §4). Os opcionais do enunciado (multiagente, MCP, multimídia) **não foram feitos**.

---

## Estrutura do repositório

```
# Parte 2 — o sistema em grafo
src/triagem/             o sistema: grafo (grafo.py), nós (nos.py), estado (estado.py), contrato de saída
                         (saida.py), validação (validacao.py), RAG (regimento.py), memória (memoria.py),
                         janela (janela.py), aprovação humana (humano.py), ponto de entrada (sistema.py)
src/prompts/             os prompts, versionados (triagem-v1 da Parte 1, triagem-v2 do grafo)
src/api.py, src/chat.py, src/coordenacao.py   as três formas de usar (aluno em HTTP, aluno em terminal, coordenação)
src/demo_grafo.py        as 8 demonstrações contra o modelo real (logs em logs/parte2/)
src/ablacao_prompt.py    a "regra da frase" (docs/prompts.md §5)
conferir_grafo.py        nós e arestas do grafo entregue, para conferir contra o desenho
docs/io.md               entrada, saída e os exemplos reais
docs/prompts.md          o plano de prompt engineering
docs/arquitetura.md      o diagrama, as seis perguntas, a defesa do nível de autonomia, o estado
docs/grafo.md            quem decide cada aresta, os reducers, o que o framework não deu
docs/rag.md              as formas de recuperar, o corpus, os números medidos
docs/memoria.md          a fronteira, as três memórias, o esquecimento, a conversa
docs/humano.md           onde o grafo para, a tela, o prazo, a aprovação repetida
logs/parte2/             as execuções reais citadas nos documentos

# Parte 3 — avaliar, governar, proteger, observar
evals/                   suíte: dataset (dataset/golden_v1.2.0.json), runner (rodar.py), comparador, métricas, juiz,
                         rotulagem humana, reconstrução de decisão pelo trace (reconstruir.py), resultados/
src/triagem/modelos.py   lista de modelos aprovados (ASI10)
src/triagem/telemetria.py  trace OpenTelemetry nas convenções GenAI
docs/evals.md            o dataset, os níveis, o juiz, a regra de promoção, o estado das rodadas
docs/seguranca.md        riscos ASI, controles fora do prompt, riscos aceitos, dados pessoais
docs/observabilidade.md  as perguntas, o trace, modos de falha, métricas, SLI e SLO
docs/mudancas.md         o histórico por commit e os defeitos que a entrega achou em si mesma

# Parte 1 e exercícios
docs/case.md          o tema, os usuários, o workflow, a justificativa de negócio
docs/modelos.md        a análise e a escolha do modelo
docs/fontes.md         tudo que foi consultado
docs/model-card.md     o model card com evidência (Exercício 12)
docs/evidencias/       saídas de comando citadas no model card
tests/                 testes de autoridade, de lacunas e de segurança (pytest, offline)
exercicios/aula-11-avaliacao.md                o desenho da avaliação (Exercício 11)
exercicios/aula-11-suite-do-case.md            o resultado da suíte (Exercício 11)
src/suite/                                     executor, avaliadores, juiz e relatório da suíte
dados/golden_v1.json, dados/regra_de_promocao.json, dados/rotulos_juiz_v1.json, dados/desacordos_juiz_v1.json
exercicios/aula14-respostas.md                 os dez riscos ASI01–ASI10 (Exercício 14)
exercicios/aula15-plano-de-observabilidade.md  o plano de observabilidade (Exercício 15)
docs/base-de-conhecimento-v1.md  o plano da base de RAG (Exercício 6)
prompts/               o system prompt do agente, versionado
src/dados.py           o "sistema acadêmico" simulado (SQLite)
src/agente.py          o laço do agente (estado, orçamento, ferramentas)
src/demo.py            roda os 4 casos de demonstração
src/verificador.py      roda os 40 casos rotulados
src/comparar_modelos.py roda a verificação mínima dos 3 modelos candidatos
dados/                  os dados simulados e os casos de teste
logs/                   as execuções gravadas (geradas ao rodar os scripts acima)

# Exercício 7 — RAG sobre o Regimento Acadêmico (exercicios/aula-07-*.md)
dados/regimento_dados.py   o Regimento Acadêmico simulado (15 artigos)
dados/casos_rag.json       perguntas rotuladas do RAG (recall/fidelidade/recusa)
src/chunking.py            corte por estrutura (1 chunk por artigo)
src/indice_rag.py          índice de embeddings local (sentence-transformers, sem banco vetorial)
src/rag.py                 pipeline: recuperar -> contexto -> gerar, citação verificável, portão de recusa
src/avaliar_rag.py         recall@k, fidelidade, varredura do limiar
src/modos_de_falha.py      reproduz os 4 modos de falha + corpus desatualizado
exercicios/aula-07-resposta-que-cita.md  o relatório do Exercício 7

# Exercício 8 — Memória do agente (exercicios/aula-08-*.md, docs/memoria-ex8.md)
src/memoria_episodica.py   índice vetorial de episódios passados, por RA, com decaimento
src/memoria_semantica.py   chave-valor idempotente, com campo `substituiu`
src/memoria_procedural.py  regras aprendidas de erro, com aprovação humana
src/memoria.py             orçamento de janela, remoção sob solicitação com verificação
src/memoria_demo.py        roda a demonstração completa
docs/memoria-ex8.md                      a decisão de projeto do Ex.8 (a memória integrada é docs/memoria.md)
exercicios/aula-08-memoria-do-case.md    o relatório da implementação
```

## Pendências antes da entrega final

- [x] ~~Ativar o plano de uso na conta Mistral~~ — a conta Mistral ficou com cota zerada (diagnóstico em `logs/README.md`) e ativar exigia cadastrar pagamento; o grupo trocou o provedor padrão para **Groq** (free tier, sem cartão — ver `docs/modelos.md` §3.5), que resolve o mesmo requisito de tool calling sem esse bloqueio.
- [x] ~~Criar uma chave gratuita, rodar `demo.py` e `verificador.py` de verdade~~ — feito em 22-23/09/2026: os 4 casos de demonstração estão em `logs/01-*.json` a `logs/04-*.json`, e o verificador completo (40 casos) atingiu **35/40 (87,5%), 0 falsos negativos em trancamento** — critério de sucesso do `case.md` §2.7 atingido (relatório em `logs/verificador.json`, diagnóstico completo em `docs/modelos.md` §3.5, incluindo dois bugs de infraestrutura encontrados e corrigidos no caminho).
- [ ] **Rodar `python src/comparar_modelos.py`** para preencher a tabela de 5 casos × 3 modelos da §3.3/3.5 — adiado por prudência com a cota diária da Groq (o candidato `openai/gpt-oss-20b` já esgotou seu teto de 200k tokens/dia só com os testes deste grupo; ver `docs/modelos.md` §3.5). Rodar quando a cota resetar.
- [x] ~~Reconfirmar os preços da Mistral em `docs/modelos.md`~~ — feito em 22/09/2026, valores confirmados sem mudança (ver `docs/fontes.md`).
- [x] ~~Substituir a linha de base estimada de `docs/case.md` §2.5 por uma medição real~~ — decisão do grupo em 22/09/2026: sem acesso a uma secretaria real para cronometrar, a linha de base continua como **estimativa declarada** (a ressalva já está escrita em `case.md` §2.5, que é a resposta válida quando a medição real não é possível). Se o grupo conseguir acesso real depois, atualizar com a fonte da medição.
