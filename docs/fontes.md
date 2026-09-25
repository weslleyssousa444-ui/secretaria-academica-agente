# Fontes consultadas

- Material da disciplina (Senac): [senac-agentes-llm](https://github.com/celsocrivelaro/senac-agentes-llm), aula 04 — casos de uso e escolha do projeto (enunciado desta entrega).
- Código de referência para o padrão de estado/orçamento/laço do agente: `aula05-agentes/agente.py` do repositório de laboratórios da disciplina (`senac-llm-code-main`).
- Código de referência para o padrão de benchmark próprio de modelos: `aula02-modelos-e-parametros/06-benchmark-modelos.py` do mesmo repositório — reaproveitamos o trio de modelos (`ministral-3b-latest`, `mistral-small-latest`, `mistral-large-latest`) e os preços documentados ali.
- [Documentação da API Mistral](https://docs.mistral.ai/) — endpoint compatível com OpenAI, `chat/completions`, `tools`, `response_format`.
- [Mistral — página de preços](https://mistral.ai/pricing/api) — **reconfirmada em 22/09/2026**: os três preços usados em `docs/modelos.md` (§3.1) batem exatamente com o material da disciplina. Pendência anterior resolvida.
- [Mistral — Admin Console (criação de chave de API)](https://admin.mistral.ai/).
- [Groq — modelos disponíveis](https://console.groq.com/docs/models) e [Groq — tool use](https://console.groq.com/docs/tool-use), consultadas em 22/09/2026 — confirmação de que todos os modelos hospedados suportam tool calling e dos IDs exatos dos três candidatos usados em `docs/modelos.md` §3.5, após a troca de provedor (conta Mistral com cota zerada, ver `logs/README.md`).

- Material da disciplina, Aula 07 (RAG e Documentos) — as 5 notas de aula (`00-do-pdf-ao-texto`, `01-as-formas-de-recuperar`, `02-o-que-o-embedding-nao-ve`, `03-medir-o-rag`, `04-o-pipeline-e-os-quatro-modos-de-falha`, `05-a-resposta-que-cita-e-que-recusa`) e o enunciado do Exercício 7, base de todo o `exercicios/aula-07-resposta-que-cita.md`.
- [sentence-transformers — `paraphrase-multilingual-MiniLM-L12-v2`](https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2), modelo de embedding local usado no Exercício 7 (a Groq não oferece endpoint de embeddings nesta conta).
- [Redis — Agent Memory Developer Guide](https://redis.io/docs/latest/develop/ai/context-engine/agent-memory/developer-guide/) — compartilhado pelo grupo como leitura de apoio; relevante para a Aula 08 (memória de agente), não usado diretamente no Exercício 7.
- [Colab — bancos de grafo](https://colab.research.google.com/drive/1toaClO016IRJjEuX-htWZDmtJWgDzC53) — compartilhado pelo grupo; relevante para `01-as-formas-de-recuperar.md` §5 (recuperação por grafo), não implementado nesta entrega (o Exercício 7 não pede grafo).

## O que ainda falta consultar

- O Regimento Acadêmico interno (fonte real das regras de trancamento e das exceções de bolsista/convênio/liminar) — não consultado porque o grupo não tem acesso a um documento real; as regras usadas em `docs/case.md` §2.1 e em `dados/regimento_dados.py` (Exercício 7) são uma simplificação razoável, não uma transcrição de norma real.
