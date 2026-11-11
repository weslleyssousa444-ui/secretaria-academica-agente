# Continuidade — Partes 2 e 3

Situação em **11/11/2026**. O sistema em grafo (Parte 2) e a avaliação, governança, segurança e observabilidade (Parte 3) estão **no repositório local**. Este arquivo diz o que **falta**, quem tem de fazer, e os comandos exatos. O grupo decidiu **seguir sem Docker**; o que depende dele está na seção 6, como opcional. O histórico do que foi feito e dos defeitos achados está em [`docs/mudancas.md`](docs/mudancas.md).

## 0. Os commits não estão no GitHub

O último envio autorizado foi `41d7a0c`. **Todos os commits da Parte 2 e da Parte 3 existem só localmente.** Enviar exige a autorização do usuário (`git push origin master`).

## 1. Testes offline (não precisam de chave nem de Docker)

Exige **Python 3.10 ou superior** (a API usa `str | None` em modelos Pydantic). No Mac sem `brew`, o ambiente do grupo é o `.venv311`, criado com `uv`:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv311/bin/python -m pytest -q -p no:cacheprovider
# esperado em 11/11/2026: 210 passed, 1 deselected
```

- [ ] Regenerar `docs/evidencias/pytest.txt` (ainda é de 16/10, de antes da Parte 2): `python -m pytest -v > docs/evidencias/pytest.txt`.
- [ ] Regenerar `docs/evidencias/autoridade-efetiva.txt`, `inventario-dados-pessoais.txt` e `historico-git.txt`, que descrevem o agente da Parte 1 (`docs/model-card.md`, L26).

## 2. Rodar a suíte com o modelo real (precisa da chave da Groq e de **cota nova**)

```bash
cp .env.example .env        # edite: OPENAI_API_KEY=<sua chave da Groq>
```

A cota do `qwen/qwen3.8-27b` é de **200 mil tokens por dia**, e uma rodada completa custa **~170 mil**. A rodada B **parou na cota** em 11/11/2026. **Nada mais deve usar o `qwen` no dia em que a suíte rodar.** Os comandos estão em [`docs/evals.md` §4.4](docs/evals.md) e o runner é retomável (pula o que já fez):

```bash
# Dia 1 (cota nova):
python -m evals.rodar --rotulo B --run 1 --pasta evals/resultados/2026-11-11-B-r1
# Dia 2 (a rodada A tem 3 casos de 37):
python -m evals.rodar --rotulo A --run 1 --ref parte-2 --pasta evals/resultados/2026-11-11-A-r1
# Depois:
python -m evals.comparar evals/resultados/2026-11-11-A-r1 evals/resultados/2026-11-11-B-r1 --salvar docs/evidencias/comparacao-parte3.txt
python -m evals.atualizar_docs --a evals/resultados/2026-11-11-A-r1 --b evals/resultados/2026-11-11-B-r1 \
       --traces evals/resultados/2026-11-11-B-r1/traces.jsonl --slo 0.95
```

- [ ] Rodada B (37 casos) e rodada A completa.
- [ ] **Ler** a comparação contra a regra de promoção **assinada antes** da versão B (`evals/resultados/assinatura-regra-p3.txt`). Um resultado ruim é um resultado: não ajustar a regra depois.
- [ ] Os blocos **PENDENTE** de `docs/evals.md` §4.3 e `docs/observabilidade.md` §4 são preenchidos pelo `atualizar_docs`, **nunca à mão**.
- [ ] Reconstruir **uma decisão real** pelo trace e trocar o exemplo de teste de `docs/model-card.md` §11:
  `python -m evals.reconstruir evals/resultados/2026-11-11-B-r1/traces.jsonl --conversa <id>`.
- [ ] Conferir, nesse trace real, se o provedor devolve o **modelo servido** (L13).
- [ ] Anotar o resultado do **SLO** (≥ 95% em 7 dias) em `docs/observabilidade.md` §5, **mesmo que viole**.

## 3. O que só o grupo pode fazer (não foi, e não será, preenchido por código)

- [ ] **Rotular 20 saídas do juiz à mão** (~30 min, uma pessoa): `evals/rotulagem/LEIA-ME.md`; depois `python -m evals.rotulagem medir`. Hoje os 75 rótulos do Ex.11 são de uma IA (L24).
- [ ] **Erick aceita ou recusa** os três riscos propostos (ASI09, ASI04, ASI03 "o portal não existe") em `docs/seguranca.md` §4 e `docs/model-card.md` §9 (L15).
- [ ] **Revogar a chave da Groq** que esteve num arquivo local (apagado, nunca commitado) e gerar outra (`docs/seguranca.md` §6).
- [ ] Decidir o **prazo de guarda** do trace (proposta: 90 dias) e o acesso (L26).

## 4. Lacunas do *model card* que a Parte 3 deixou abertas

Estado completo em `docs/model-card.md`, seção Lacunas. As de prioridade **P1**:

- **L01** (a premissa): o controle de identidade é correto **dado** um portal; **o portal não existe**. Antes de dado real, de expor a porta (`docker-compose.yml` publica `8000:8000`) ou de ligar um portal, reavaliar.
- **L06**: logs com dado pessoal no repositório público; `logs/parte2/` acrescentou 8 execuções reais.
- **L14**: região, retenção e uso para treino da Groq **não verificados**.
- **L26**: o trace não tem prazo nem controle de acesso e não está na remoção por titular.

## 5. Pipeline no GitHub

1. **Settings → Secrets and variables → Actions → New repository secret:** `GROQ_API_KEY`. Sem o secret, o job `eval` é pulado (aviso), não reprovado.
2. **Settings → Actions → General → Workflow permissions:** se o push da imagem falhar com `denied`, marcar *Read and write permissions*.
3. Depois do push (seção 0), acompanhar em **Actions**: `seguranca`, `testes`, `eval` e `imagem`. O workflow ainda **não foi rodado** sobre os commits das Partes 2 e 3; o `Dockerfile` e o `ci.yml` receberam `ARG COMMIT`/`AGENTE_COMMIT` e `TRIAGEM_TRACES_DIR`, e `requirements-agente.txt` passou a fixar `langgraph`, `langgraph-checkpoint-sqlite` e `opentelemetry-*`. **Nada disso foi construído**: este ambiente não tem Docker.
- [ ] Registrar o link da execução em `docs/empacotamento.md`.

## 6. Opcional: evidências que exigem Docker local

Ficam pendentes enquanto o grupo não usar Docker. Em `docs/empacotamento.md` continuam marcadas como **PENDENTE**, sem ajustar o texto para parecer concluído.

```bash
docker build -t secretaria-academica-agente:local .
bash scripts/evidencias_ex13.sh          # regenera docs/evidencias/empacotamento.txt
```

- [ ] A imagem **com as dependências da Parte 2** (o que `docs/empacotamento.md` mediu, 248 MB e 4 dependências, era a da Parte 1);
- [ ] cache de build, `POST /mensagens` com chave inválida, `HEALTHCHECK`.

## 7. Os opcionais do enunciado da Parte 3

**Multiagente, MCP e multimídia: não feitos.** Não há pendência escondida neles; se o grupo quiser, são trabalho novo.

Quando tudo estiver concluído, este arquivo pode ser apagado.
