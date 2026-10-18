# Empacotamento e CI/CD do agente de triagem

**Exercício 13 — MLOps e empacotamento.** **Grupo:** Weslley Soares de Sousa, Pedro Akira, Henrique Gomes Matos e Erick. **Data:** 16/10/2026.

O agente de triagem sai da máquina de quem o escreveu: vira uma **imagem Docker** reprodutível, roda como **API** com o estado num **volume**, e cada mudança passa por um **pipeline de CI/CD** no GitHub Actions. As saídas de comando citadas aqui estão em [`evidencias/empacotamento.txt`](evidencias/empacotamento.txt).

> **Situação em 16/10/2026.** A imagem foi construída e verificada nesta data (seções 1 a 5). Alguns itens ficaram por rodar porque a rede do Senac bloqueou o Docker e o push; estão marcados como **PENDENTE** e listados em [`CONTINUIDADE.md`](../CONTINUIDADE.md).

## 1. O que entra na imagem, e o que fica fora

| Na imagem (igual em toda execução) | Fora da imagem (varia por ambiente ou execução) | Como chega |
|---|---|---|
| Python 3.11.13 (`python:3.11.13-slim-bookworm`, fixado até o *patch*) | **segredo**: `OPENAI_API_KEY` | `--env-file .env` ou `env_file` do Compose, em tempo de execução |
| 4 dependências diretas com versão exata ([`requirements-agente.txt`](../requirements-agente.txt)) | **modelo**: Groq, pela rede | `LLM_BASE_URL` e `LLM_MODELO` no ambiente |
| `src/agente.py`, `src/dados.py`, `src/api.py`, `src/chat.py` e `prompts/triagem-v1.txt`, copiados por nome | **estado**: banco SQLite e registros de execução | volume montado em `/dados` (§4) |

**Só o que o agente importa.** O `requirements.txt` da raiz traz `torch` e `sentence-transformers`, que só os Exercícios 7 e 8 usam e não estão ligados ao agente. A imagem instala só [`requirements-agente.txt`](../requirements-agente.txt): `openai`, `python-dotenv`, `fastapi` e `uvicorn`. O resultado é uma imagem de **248 MB**, em que `import torch` falha ([evidência §1](evidencias/empacotamento.txt)).

**Limite declarado.** Só as dependências diretas estão fixadas. As transitivas (`pydantic`, `starlette`, `httpx`...) são resolvidas no build. A reprodutibilidade completa exigiria um arquivo de *lock* (por exemplo, `pip-compile`), que fica para depois.

## 2. O `Dockerfile`

[`Dockerfile`](../Dockerfile), em cinco blocos:

| # | O quê | Por quê |
|---|---|---|
| 1 | base `python:3.11.13-slim-bookworm` | `python:3.11-slim` é etiqueta móvel: a mesma linha gera imagens diferentes em dias diferentes |
| 2 | `requirements-agente.txt`, depois `pip install --no-cache-dir` | a camada cara (44 MB) só é refeita quando as dependências mudam; `--no-cache-dir` evita deixar o cache do pip na camada (regra DL3042 do hadolint) |
| 3 | usuário `agente` (uid 10001) e `/dados` com esse dono | o processo não roda como `root` (achado AVD-DS-0002 do Trivy); um volume novo montado em `/dados` herda o dono |
| 4 | `COPY` por nome dos 4 módulos e do prompt | segunda barreira contra o `.env`, além do [`.dockerignore`](../.dockerignore) |
| 5 | `ENV` dos caminhos do estado, `USER`, `EXPOSE 8000`, `HEALTHCHECK` em `/saude`, `CMD` uvicorn em `0.0.0.0` | o `127.0.0.1` do container é o *loopback* dele, e sem `0.0.0.0` a porta publicada não alcança o servidor |

Verificado em 16/10/2026 ([evidências §1 e §2](evidencias/empacotamento.txt)):

- o processo roda como `uid=10001(agente)`;
- não há `.env` na imagem;
- o `docker history` não tem camada de segredo;
- o hadolint não deu **nenhum aviso**;
- o Trivy não teve **nenhum achado**, em nenhuma severidade;
- **controle negativo:** o mesmo `Dockerfile` sem a linha `USER` é reprovado pelo Trivy com AVD-DS-0002 (HIGH) e `exit=1`. O portão de fato reprova o que deve.

**PENDENTE: teste do cache.** Mudar uma linha de `src/api.py` e reconstruir; a camada do `pip install` deve sair `CACHED`. Está no script de evidências (§3 dele).

## 3. Executar

```bash
docker build -t secretaria-academica-agente:local .

# API, com o estado num volume nomeado
docker run --rm -p 8000:8000 --env-file .env -v estado:/dados secretaria-academica-agente:local
curl localhost:8000/saude
curl -X POST localhost:8000/mensagens -H 'content-type: application/json' \
     -d '{"mensagem": "Preciso de uma declaração de matrícula. RA 20231045"}'
# turnos seguintes: o mesmo corpo com "conversa_id" devolvido no primeiro

# chat de terminal, com a mesma imagem
docker run --rm -it --env-file .env -v estado:/dados secretaria-academica-agente:local python src/chat.py

# ou tudo pelo Compose
docker compose up --build
```

A API ([`src/api.py`](../src/api.py)) tem dois *endpoints*:

| *Endpoint* | O que faz |
|---|---|
| `GET /saude` | não chama o modelo; diz se o processo e o banco respondem, e qual modelo está configurado |
| `POST /mensagens` | um turno do aluno: `{"mensagem", "conversa_id"?}` → `{"conversa_id", "resposta", "termino", "motivo", "encerrada"}` |

A resposta **nunca** traz o resultado das ferramentas, que contém o cadastro e o financeiro do aluno: `teste::test_resposta_nao_expoe_resultado_de_ferramenta`. Conversa encerrada (por orçamento, laço ou erro) recusa um novo turno com `409`; conversa desconhecida devolve `404`; mensagem vazia ou com mais de 2.000 caracteres devolve `422`. São 7 testes em [`tests/test_api.py`](../tests/test_api.py), todos offline.

**Por que síncrona.** Um turno do agente leva segundos (um caso de divergência gasta cerca de 7.500 tokens em 3 chamadas; [`docs/modelos.md` §3.5](modelos.md)), abaixo do tempo ocioso dos *proxies*. Se o agente passar a ter execuções longas, ou a aprovação da coordenação entrar no meio da conversa (o `interrupt()` do Ex.9), o caminho é fila com trabalhador e *checkpoint* externo. Isso não foi feito.

## 4. Onde mora o estado

| Estado | É derivado? | Onde mora | Evidência |
|---|---|---|---|
| Banco: `documentos_emitidos`, `casos_pendentes` | **não**: registra o que o agente fez | volume, em `/dados/academico.db` (`ACADEMICO_DB`) | [`src/dados.py:15-19`](../src/dados.py#L15-L19) |
| Cadastro e financeiro simulados (`alunos`, `financeiro`) | sim: semeados por `dados.inicializar()`, idempotente, na partida da API | o mesmo volume | [`src/api.py`](../src/api.py), `ciclo_de_vida` |
| Registro de execução, um JSON por conversa, regravado a cada turno | não: é a prova da decisão | volume, em `/dados/logs` (`LOGS_DIR`) | `teste::test_conversa_em_dois_turnos_emite_e_grava_registro` |
| Conversa em andamento | — | **memória do processo: perda aceita e declarada.** Se o container for trocado no meio, o aluno recebe `404` e recomeça; as escritas já feitas não se repetem, porque emitir e escalar são idempotentes | [`src/api.py`](../src/api.py), cabeçalho |

Verificado em 16/10/2026 ([evidências §3 e §4](evidencias/empacotamento.txt)):

- o banco nasce no volume com dono `agente`;
- `docker stop` encerra o container em **1,1 s**;
- um container novo, com o mesmo volume, encontra o banco e os registros;
- a mesma imagem **sem** o volume não tem nada em `/dados`.

**PENDENTE:**

- `POST /mensagens` com chave inválida: deve terminar em `erro_fatal`, sem escrita, e gravar o registro em `/dados/logs`. É o mesmo comportamento já provado offline por `teste::test_erro_da_api_termina_sem_escrita`;
- `HEALTHCHECK` chegando a `healthy`.

**Limites.**

- **Uma réplica só.** SQLite num volume não serve a várias réplicas. A API serializa os turnos com uma trava, porque o protocolo é `COUNT(*) + 1` (model card §8). Escalar exige Postgres e protocolo por sequência.
- **Registros com dado pessoal.** Os registros no volume continuam guardando dado pessoal completo (lacuna L06 do model card). Saíram do git, mas a minimização não foi feita.

## 5. O segredo e o histórico

```text
$ git log --all --oneline -- .env
(vazio: o .env nunca foi commitado)

$ git log --all -S "_API_KEY=" --oneline
4a41964 Troca provedor padrão de Mistral para Groq (free tier)
069942e Parte 1: case, análise de modelos, agente de triagem e verificador

$ git log --all -p -S "_API_KEY=" | grep -E "^[+-][A-Z_]*_API_KEY="
+OPENAI_API_KEY=
```

Os dois commits só tocam o `.env.example`, e a única atribuição é vazia (a outra ocorrência é a linha comentada `# OPENAI_API_KEY=<chave da Mistral...>`). Nenhuma chave vazou no histórico.

O `.env` está no [`.gitignore`](../.gitignore) e no [`.dockerignore`](../.dockerignore), e o `COPY` por nome é a segunda barreira. Se uma chave vazar algum dia, a correção é **revogar a chave** no console da Groq; reescrever o histórico não alcança clones nem imagens já publicadas.

## 6. O pipeline

[`.github/workflows/ci.yml`](../.github/workflows/ci.yml), disparado em *push* na `master`, em *pull request* e manualmente:

```text
  seguranca ──┐
              ├──> imagem   build uma vez; smoke test na própria imagem
  testes ─────┤             (uid ≠ 0, sem .env, /saude ok);
              │             publica no GHCR só em push na master:
              │             ghcr.io/<repo>:<sha> e :latest
              └──> eval     modelo real; fora de pull request e só
                            se o secret GROQ_API_KEY existir
```

| *Job* | Faz | Reprova quando |
|---|---|---|
| `seguranca` | hadolint e Trivy (config), pelas imagens oficiais fixadas por versão **e** *digest* | achado `error` no hadolint; achado HIGH ou CRITICAL no Trivy. O Trivy **reprova**, não só relata: o achado de `root` foi corrigido, então não há achado conhecido mantendo o portão vermelho |
| `testes` | `pytest`: 34 testes offline (autoridade, lacunas, API), sem chave nem rede | qualquer teste falho |
| `eval` | `pytest -m eval`: 6 casos com o modelo real | algum falso negativo em trancamento (2/2 obrigatório) ou menos de 5/6 no total |
| `imagem` | `docker build`; *smoke test*; `docker push` para o GHCR | o *smoke test* falha |

**Decisões.**

- **Ordem dos portões.** Análise estática e testes offline (segundos, gratuitos) rodam em paralelo e antes. O *eval* (minutos, custa tokens) vem depois e não bloqueia a imagem: com chave ausente ou cota esgotada no *free tier*, a imagem ainda é publicada, e o *eval* fica vermelho à parte. O *eval* não roda em *pull request*, que não recebe *secrets* de *fork*, e o custo fica restrito ao tronco.
- **Poder do *eval*.** A conta binomial está no cabeçalho de [`tests/test_eval.py`](../tests/test_eval.py). Com o acerto medido fora da série `p` (33/34, q ≈ 0,97), o portão passa com P ≈ 0,99. Com q = 0,70, ainda passa com P ≈ 0,42. Seis casos detectam regressão grosseira, como o modelo que deixou de escalar trancamento; não distinguem versões próximas. O verificador de 40 casos continua sendo a medida de qualidade.
- **Tags.** A tag `<sha>` é escrita uma vez e liga a imagem ao commit; implantar usa essa. A `latest` é só "a mais recente do tronco". O registro é o GHCR, com o `GITHUB_TOKEN` do próprio job (`packages: write` só no job `imagem`): não há senha de Docker Hub para guardar.
- **Cadeia de suprimentos.** As únicas *actions* são `actions/checkout` e `actions/setup-python`, fixadas pelo SHA do commit, com a tag em comentário. hadolint e Trivy entram pela imagem oficial com *digest*, e não por *action* de terceiro. `permissions: contents: read` é o padrão do workflow.

**O que o pipeline não verifica.**

- **Os testes unitários não rodam na imagem.** Rodam no Python do executor; na imagem roda só o *smoke test*. A diferença fica pequena porque a base é a mesma versão (3.11.13) e as dependências são as mesmas, mas não é zero.
- **Não há implantação.** O pipeline termina no registro: é integração contínua com entrega do artefato.
- **Drift do modelo.** O `qwen/qwen3.8-27b` não tem versão datada (model card, lacuna L13). Um *eval* agendado (`schedule`) detectaria mudança do provedor sem commit; não foi configurado, para poupar a cota do *free tier*.
- **PENDENTE: o workflow nunca rodou no GitHub.** O push está bloqueado nesta rede. Os comandos de `seguranca` e `imagem` foram rodados localmente; os de `testes`, também (31 passaram).

## 7. Maturidade (Google, níveis 0 a 2)

O sistema não treina modelo, então a escala se aplica ao que muda o comportamento: prompt, código e escolha de modelo.

- **Antes deste exercício: nível 0.** A avaliação era rodada à mão, e o relatório do verificador foi montado à mão (model card, L18).
- **Agora.** Toda mudança de código ou de prompt passa por portões automáticos e produz um artefato identificado pelo commit. Mas não há treino contínuo, não há monitoramento da camada de modelo em produção, e o *eval* do portão é pequeno.
- **Classificação.** É CI/CD de software com um *eval* de regressão. Pelo critério do Google, isso ainda é nível 0 de MLOps com a parte de DevOps automatizada.

## 8. O que mudou no código

| Arquivo | Mudança |
|---|---|
| [`src/dados.py`](../src/dados.py) | caminho do banco pela variável `ACADEMICO_DB`, com o padrão de antes |
| [`src/agente.py`](../src/agente.py) | `salvar_log` aceita a pasta (parâmetro opcional, mesmo comportamento por padrão) |
| [`src/api.py`](../src/api.py) | novo: a API |
| [`tests/test_api.py`](../tests/test_api.py), [`tests/test_eval.py`](../tests/test_eval.py), [`pytest.ini`](../pytest.ini) | novos: 7 testes da API; o *eval* marcado, fora do `pytest` padrão |
| `Dockerfile`, `.dockerignore`, `docker-compose.yml`, `requirements-agente.txt`, `requirements-dev.txt`, `.github/workflows/ci.yml`, `scripts/evidencias_ex13.sh` | novos |
