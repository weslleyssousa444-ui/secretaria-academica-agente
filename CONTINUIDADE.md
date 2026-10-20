# Continuidade — Exercícios 12 e 13

Situação em **16/10/2026**. O código e a documentação dos Exercícios 12 e 13 estão no GitHub (`origin/master`). Este arquivo diz o que falta e os comandos exatos. O grupo decidiu **seguir sem Docker**; o que depende dele está na seção 4, como opcional.

## 1. Testes offline (não precisam de chave nem de Docker)

Exige **Python 3.10 ou superior** (`src/api.py` usa `str | None` em modelos Pydantic). Com Python 3.9, só `tests/test_api.py` deixa de rodar.

```bash
python3.11 -m venv .venv
source .venv/bin/activate               # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
python -m pytest -v                     # esperado: 34 passed, 1 deselected
```

- [ ] Rodar em Python 3.10+ e regenerar `docs/evidencias/pytest.txt` (hoje com a saída de 24 testes, de antes da correção da L02).
- Verificado em 16/10/2026 sob Python 3.9, sem `test_api.py`: 27 passed.

## 2. Chave da Groq e eval com o modelo real

```bash
cp .env.example .env
# edite .env: OPENAI_API_KEY=<sua chave da Groq>  (https://console.groq.com/keys)
python -m pytest -m eval -v -s           # usa a OPENAI_API_KEY do .env
```

O `.env` nunca vai para o git (está no `.gitignore`). Critério do eval: trancamento 2/2 **e** pelo menos 5/6 no total. Leva cerca de 1 minuto e gasta tokens do *free tier*.

- [ ] Anotar o resultado (acertos e casos) em `docs/empacotamento.md` §6.

**Resultado em 18/10/2026 (Python 3.9, `qwen/qwen3.8-27b`, depois da correção da L02):**

| Verificação | Resultado |
|---|---|
| Eval (`pytest -m eval`), 1ª execução | 4/6, reprovado: `d01` e `s01` deram `None` (causa não confirmada; suspeita de limite da Groq) |
| Eval, 2ª execução | **6/6**, trancamento 2/2 |
| Verificador, casos `d01`–`d08`, `s01`–`s08`, `p01`–`p06`, `v01`–`v05` | **27/27 corretos** |
| Verificador, `v06`, `t01`–`t08`, `r01`–`r04` (13 casos), 1ª tentativa em 18/10 | `erro_fatal`: cota diária da Groq esgotada (`tokens per day: Limit 200000, Used 199961`) |
| Verificador, os mesmos 13 casos, refeitos em 20/10 | **12/13 corretos, 0 falso negativo em trancamento** (`t01`–`t08` certos). O erro é o `r03`, ambiguidade de rótulo conhecida (`docs/modelos.md` §3.5) |
| **Verificador, total (27 + 12)** | **39/40**, critério do `case.md` §2.7 atendido (referência anterior: 35/40) |
| GitHub Actions, commit `5ade646` | `seguranca`, `testes`, `eval` e `imagem`: todos `success` ([run](https://github.com/weslleyssousa444-ui/secretaria-academica-agente/actions/runs/39099896050)) |

- O 39/40 vem de **dois lotes** (27 em 18/10, 13 em 20/10), não de uma execução única, porque a cota diária acabou no meio. O `qwen/qwen3.8-27b` gasta cerca de 5 mil tokens por caso: eval e verificador completo no mesmo dia passam dos 200 mil tokens.
- [ ] Opcional, para ter um registro de execução única: rodar `python src/verificador.py` inteiro num dia sem outros testes e gravar `logs/verificador.json`. O arquivo versionado ainda é o de 22-23/09 (35/40).
- Observação: o verificador conta `erro_fatal` por limite do provedor como erro de decisão, e isso pode reprovar o eval do CI por acaso.

## 3. Pipeline no GitHub

1. **Settings → Secrets and variables → Actions → New repository secret:** `GROQ_API_KEY`. Sem o secret, o job `eval` é pulado (aviso), não reprovado.
2. **Settings → Actions → General → Workflow permissions:** se o push da imagem falhar com `denied`, marcar *Read and write permissions*.
3. Acompanhar em **Actions**: `seguranca`, `testes` (34 testes), `eval` e `imagem` (GHCR). Os quatro jobs rodam em `ubuntu-24.04` no GitHub, e o `imagem` faz o `docker build` lá, então **não dependem de Docker local**.
- [ ] Registrar o link da execução em `docs/empacotamento.md` e tirar o marcador "PENDENTE: o workflow nunca rodou no GitHub".

## 4. Opcional: evidências que exigem Docker local

Ficam pendentes enquanto o grupo não usar Docker. Em `docs/empacotamento.md` continuam marcadas como **PENDENTE**, sem ajustar o texto para parecer concluído.

```bash
docker build -t secretaria-academica-agente:local .
bash scripts/evidencias_ex13.sh          # regenera docs/evidencias/empacotamento.txt
```

- [ ] cache de build (camada do `pip install` sai `CACHED` depois de mudar o código);
- [ ] `POST /mensagens` com chave inválida termina em `erro_fatal`, sem escrita;
- [ ] `HEALTHCHECK` chegando a `healthy`.

## 5. Lacunas do model card ainda abertas

A L02 (trancamento escalado só se o modelo quisesse) foi **fechada em código** em 16/10/2026: `src/agente.py`, `escalonamento_de_trancamento_devido`. Restam 21 abertas (os ids vão de L01 a L21 e L23; não existe L22). As de maior prioridade:

- **L01**: sem verificação de identidade; qualquer RA digitado é atendido (P1).
- **L11**: divergência, RA não encontrado e pendência dependem só do prompt (a L02 cobriu só trancamento).
- **L03**: a chave de idempotência do `escalar_para_humano` é escrita pelo modelo.

## O que já está feito

| Item | Onde |
|---|---|
| Model card nos 12 campos, 21 lacunas abertas, 27 testes de governança | `docs/model-card.md`, `tests/test_autoridade.py`, `tests/test_lacunas.py` |
| Trancamento sempre escalado, garantido pelo código (L02) | `src/agente.py:436-476`, 4 testes em `tests/test_autoridade.py` |
| Imagem: base fixada, 4 dependências, usuário sem privilégio, `COPY` por nome, sem `.env` | `Dockerfile`, `.dockerignore`, `requirements-agente.txt` |
| API (`/saude`, `/mensagens`) com 7 testes offline | `src/api.py`, `tests/test_api.py` |
| Estado no volume (banco e registros), testado com `stop`, `rm` e container novo | `docker-compose.yml`, `docs/evidencias/empacotamento.txt` §3–4 |
| hadolint sem avisos; Trivy sem achados; controle negativo (sem `USER`) reprova | `docs/evidencias/empacotamento.txt` §2 |
| Histórico do git sem chave vazada | `docs/empacotamento.md` §5 |
| Workflow: segurança, testes, eval, imagem → GHCR; *actions* e imagens fixadas por SHA ou *digest* | `.github/workflows/ci.yml` |

Quando tudo estiver concluído, este arquivo pode ser apagado.
