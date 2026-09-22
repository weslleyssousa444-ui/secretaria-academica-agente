# Fontes consultadas

- Material da disciplina (Senac): [senac-agentes-llm](https://github.com/celsocrivelaro/senac-agentes-llm), aula 04 — casos de uso e escolha do projeto (enunciado desta entrega).
- Código de referência para o padrão de estado/orçamento/laço do agente: `aula05-agentes/agente.py` do repositório de laboratórios da disciplina (`senac-llm-code-main`).
- Código de referência para o padrão de benchmark próprio de modelos: `aula02-modelos-e-parametros/06-benchmark-modelos.py` do mesmo repositório — reaproveitamos o trio de modelos (`ministral-3b-latest`, `mistral-small-latest`, `mistral-large-latest`) e os preços documentados ali.
- [Documentação da API Mistral](https://docs.mistral.ai/) — endpoint compatível com OpenAI, `chat/completions`, `tools`, `response_format`.
- [Mistral — página de preços](https://mistral.ai/pricing/api) — **reconfirmada em 22/09/2026**: os três preços usados em `docs/modelos.md` (§3.1) batem exatamente com o material da disciplina. Pendência anterior resolvida.
- [Mistral — Admin Console (criação de chave de API)](https://admin.mistral.ai/).
- [Groq — modelos disponíveis](https://console.groq.com/docs/models) e [Groq — tool use](https://console.groq.com/docs/tool-use), consultadas em 22/09/2026 — confirmação de que todos os modelos hospedados suportam tool calling e dos IDs exatos dos três candidatos usados em `docs/modelos.md` §3.5, após a troca de provedor (conta Mistral com cota zerada, ver `logs/README.md`).

## O que ainda falta consultar

- O Regimento Acadêmico interno (fonte real das regras de trancamento e das exceções de bolsista/convênio/liminar) — não consultado nesta Parte 1 porque o grupo não tem acesso a um documento real; as regras usadas em `docs/case.md` §2.1 são uma simplificação razoável, não uma transcrição de norma real. Vira insumo do RAG na Parte 2 (`docs/case.md` §2.10).
