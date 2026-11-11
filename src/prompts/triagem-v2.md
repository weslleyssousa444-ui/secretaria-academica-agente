# Prompt: triagem de solicitações — v2

| Campo | Valor |
|---|---|
| Versão | v2 (substitui a [v1](triagem-v1.md), que continua no repositório como histórico) |
| Modelo | `qwen/qwen3.8-27b` (Groq, free tier); o mesmo da v1 |
| Parâmetros | `temperature=0`, `tool_choice` automático, sem `max_tokens` (ver `docs/prompts.md` §3) |
| Técnica | zero-shot com regras numeradas e contrato de saída explícito (como a v1) |
| Texto carregado pelo código | [`triagem-v2.txt`](triagem-v2.txt), lido por `src/triagem/nos.py` |

## O que mudou em relação à v1, e por quê

| Mudança | Motivo |
|---|---|
| Regra 2 diz "ferramenta **de aluno**" | com `consultar_regimento`, uma dúvida de regra não precisa de RA; sem a ressalva, o modelo pediria o RA para qualquer pergunta |
| Regra 7 (nova) | o sistema ganhou a ferramenta `consultar_regimento` (RAG, `docs/rag.md`). A regra diz quando usar, que só vale o que o artigo diz, e o que fazer quando o regimento não trata do assunto (recusa que ofereça encaminhar) |
| Regra 8 (nova) | a memória entre execuções (`docs/memoria.md`) entra como seção MEMÓRIA; a regra impede que o resumo de um atendimento anterior seja lido como instrução |
| Contrato de saída: citar o artigo | o validador de saída (`src/triagem/validacao.py`) confere os artigos citados contra os devolvidos pela ferramenta |
| Contrato de saída: PROIBIDO citar artigo não devolvido | a mesma conferência, dita ao modelo para ele não precisar ser corrigido |

As regras 1 a 6 e o contrato de emissão e de escalonamento **não mudaram**: o comportamento medido na Parte 1 (39/40 no verificador) vale como ponto de partida.

## O que cada frase nova impede

- **Regra 7, "SÓ com o que os artigos devolvidos dizem"**: impede a resposta com conhecimento geral sobre regimentos, que soa certa e pode contradizer o regimento desta instituição.
- **Regra 7, "ofereça encaminhar"**: impede a recusa seca, que deixa o aluno sem saída (a recusa útil é requisito do contrato, `docs/io.md`).
- **Regra 7, "Não use a ferramenta para decidir o pedido"**: impede que um trecho do regimento (texto de terceiro) substitua a consulta ao sistema acadêmico na decisão de emitir ou escalar.
- **Regra 8**: impede que a memória vire canal de instrução (`docs/seguranca.md`, ASI06).
- **"PROIBIDO citar artigo que a ferramenta não devolveu"**: impede a citação inventada; a conferência em código é a garantia, e a frase evita o retrabalho.

Se uma dessas frases for apagada, o comportamento que ela impede volta; a regra 8 é a única que ainda não tem teste que a exercite (`docs/prompts.md` §5).
