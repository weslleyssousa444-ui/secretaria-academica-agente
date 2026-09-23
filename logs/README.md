# Logs de execução

Gerados rodando os scripts abaixo com uma `OPENAI_API_KEY` real configurada em `.env` (ver `README.md` da raiz):

- `python src/demo.py` — grava um arquivo `NN-nome-do-caso-<id>.json` por caso de demonstração (item 4.5 da entrega). **Feito em 22/09/2026** com `openai/gpt-oss-20b` (Groq) — os 4 arquivos `01-*.json` a `04-*.json` estão nesta pasta; ver o exemplo real no `README.md` da raiz.
- `python src/verificador.py` — grava `verificador.json`, o relatório dos 40 casos rotulados contra o critério de sucesso. **Feito em 22-23/09/2026** com `qwen/qwen3.8-27b` (Groq) — **35/40 (87,5%), critério de sucesso atingido, 0 falsos negativos em trancamento**. O relatório inclui um campo `metodologia` explicando por que o número final combina duas rodadas com um reteste isolado (ver `docs/modelos.md` §3.5 para o diagnóstico completo — dois bugs de infraestrutura encontrados e corrigidos, e duas lacunas reais no conjunto de teste, documentadas em `dados/casos_verificador.json`).
- `python src/comparar_modelos.py` — grava `comparar_modelos.csv`, a verificação mínima dos 3 modelos candidatos. **Ainda pendente** — adiado por prudência com a cota diária da Groq (ver `docs/modelos.md` §3.5).

## Pendência histórica (resolvida): conta Mistral com cota zerada

Uma chave já foi testada (04/09/2026) e está **válida** — `client.models.list()` funciona normalmente. Mas toda chamada a `chat.completions.create()` volta com `429 rate_limited` (código `1300`), e o cabeçalho da resposta mostra a causa exata:

```
x-ratelimit-limit-req-minute: 0
x-ratelimit-remaining-req-minute: 0
```

Ou seja: **não é um limite de taxa passageiro** (esperar e tentar de novo não resolve — já testamos duas vezes com alguns segundos de intervalo). É a cota de requisições de inferência da conta configurada em **zero**, o que normalmente significa que o workspace em [admin.mistral.ai](https://admin.mistral.ai/) ainda não ativou um plano de uso (em geral isso exige cadastrar um método de pagamento, mesmo que o custo real desta entrega seja centavos — ver `docs/modelos.md` §3.2).

**Antes de gerar os logs de verdade:** entrem em admin.mistral.ai → Billing/Plano, ativem o plano de uso, e confirmem que `x-ratelimit-limit-req-minute` deixou de ser `0` (dá pra checar rodando `python src/dados.py` e depois qualquer um dos três scripts — se voltar o mesmo erro 429, o plano ainda não está ativo).
