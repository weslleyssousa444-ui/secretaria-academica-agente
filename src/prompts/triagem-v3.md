# Prompt: triagem de solicitações — v3

| Campo | Valor |
|---|---|
| Versão | v3 (13/11/2026; substitui a [v2](triagem-v2.md), que continua no repositório como histórico) |
| Modelo | `qwen/qwen3.8-27b` (Groq, free tier); o mesmo da v2 |
| Parâmetros | `temperature=0`, `tool_choice` automático, sem `max_tokens` (ver `docs/prompts.md` §3) |
| Técnica | zero-shot com regras numeradas e contrato de saída explícito (como a v2) |
| Texto carregado pelo código | [`triagem-v3.txt`](triagem-v3.txt), lido por `src/triagem/nos.py` |

## O que mudou em relação à v2, e por quê

| Mudança | Motivo |
|---|---|
| Dois tipos de pedido novos: `segunda_via_boleto` e `consulta_academica` | o sistema ganhou as ferramentas `emitir_boleto` e `consultar_historico` ([`src/triagem/servicos.py`](../triagem/servicos.py)) e os artigos 11 e 12 do Regimento |
| Regra 9 (boleto) | diz o que fazer quando há várias mensalidades em aberto (perguntar qual, ou emitir uma por vez) e quando não há nenhuma; proíbe linha digitável, valor ou vencimento que a ferramenta não devolveu |
| Regra 10 (consulta) | só o que `consultar_historico` devolveu; o agente não altera nota, e a revisão de nota é da coordenação |
| Contrato de saída: acesso ao documento | a v2 proibia falar de acesso porque nenhuma ferramenta o informava. Agora a API gera o documento (`GET /documentos/{protocolo}`) e o retorno da ferramenta traz o campo `acesso`; o agente diz **só** o que esse campo diz |
| Vencimento do boleto pela data | o validador (`validacao.py`) recusa prazo em "X dias" que não venha de artigo devolvido; a data devolvida pela ferramenta não é prazo inventado |

As regras 1 a 8 **não mudaram**.

## Efeito na avaliação

Prompt novo é sistema novo: a rodada B da suíte (`docs/evals.md`) precisa rodar de novo sobre este prompt; o trace carimba cada execução com o hash dele (`agente.versao`).
