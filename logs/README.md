# Logs de execução

Gerados rodando os scripts abaixo com uma `OPENAI_API_KEY` real configurada em `.env` (ver `README.md` da raiz):

- `python src/demo.py` — grava um arquivo `NN-nome-do-caso-<id>.json` por caso de demonstração (item 4.5 da entrega). **Os 4 exigidos ainda não foram gerados** porque não havia uma chave da Mistral disponível quando este repositório foi montado.
- `python src/verificador.py` — grava `verificador.json`, o relatório dos 40 casos rotulados contra o critério de sucesso.
- `python src/comparar_modelos.py` — grava `comparar_modelos.csv`, a verificação mínima dos 3 modelos candidatos.

Esta pasta fica vazia até o grupo rodar esses três comandos.

## Pendência conhecida: conta Mistral com cota zerada

Uma chave já foi testada (04/09/2026) e está **válida** — `client.models.list()` funciona normalmente. Mas toda chamada a `chat.completions.create()` volta com `429 rate_limited` (código `1300`), e o cabeçalho da resposta mostra a causa exata:

```
x-ratelimit-limit-req-minute: 0
x-ratelimit-remaining-req-minute: 0
```

Ou seja: **não é um limite de taxa passageiro** (esperar e tentar de novo não resolve — já testamos duas vezes com alguns segundos de intervalo). É a cota de requisições de inferência da conta configurada em **zero**, o que normalmente significa que o workspace em [admin.mistral.ai](https://admin.mistral.ai/) ainda não ativou um plano de uso (em geral isso exige cadastrar um método de pagamento, mesmo que o custo real desta entrega seja centavos — ver `docs/modelos.md` §3.2).

**Antes de gerar os logs de verdade:** entrem em admin.mistral.ai → Billing/Plano, ativem o plano de uso, e confirmem que `x-ratelimit-limit-req-minute` deixou de ser `0` (dá pra checar rodando `python src/dados.py` e depois qualquer um dos três scripts — se voltar o mesmo erro 429, o plano ainda não está ativo).
