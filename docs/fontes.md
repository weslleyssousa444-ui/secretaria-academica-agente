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

## Consultado na Parte 2

Registro do que sustenta as decisões do sistema em grafo. **Não há páginas da web novas aqui**: o que não veio do material da disciplina foi **medido** no código instalado.

| Fonte | O que sustentou |
|---|---|
| Enunciados do trabalho (`00-visao-geral`, `01-primeira-entrega`, `02-segunda-entrega`) | o que cada frente da Parte 2 exige e como é avaliada |
| Notas de aula citadas nos comentários do código: Aula 05 (idempotência por chave derivada do conteúdo, orçamento de quatro moedas, estado × lista de mensagens), Aula 06 (degraus de decisão, chunking por estrutura), Aula 07 (as cinco formas de recuperar), Aula 08 (as três memórias, as três causas de esquecimento, verificação da remoção), Aula 09 (grafo, reducer, `interrupt`) | as decisões de desenho, que estão referenciadas nos arquivos em que se aplicam |
| `langgraph==1.2.12`, `langgraph-checkpoint-sqlite==3.1.1`, `langchain-core==1.7.7` (código instalado) | o comportamento de reducer, `interrupt`, checkpoint e `recursion_limit` foi **executado**, e não lido: `tests/test_estado.py` e a medição de `docs/grafo.md` §5.3. O valor padrão do `recursion_limit` (25) vem de `langchain_core.runnables.config.DEFAULT_RECURSION_LIMIT` |
| SQLite 3.53.1 (módulo `sqlite3` do Python 3.11.18), extensão FTS5 | a busca textual (`regimento.py`): tokenizador `unicode61 remove_diacritics 2` e `bm25`, **testados** em `tests/test_regimento.py` |
| `exercicios/aula-07-resposta-que-cita.md` e `exercicios/aula-08-memoria-do-case.md` (Exercícios 7 e 8, do próprio grupo) | a alternativa vetorial do RAG (recall medido) e a decisão original de memória (`docs/memoria-ex8.md`) |
| Logs da Groq (mensagens de erro 429 de 18/10/2026) | o limite de saída por minuto do `qwen/qwen3.8-27b` e a cota diária de 200.000 tokens (`docs/prompts.md` §3) |

**O que NÃO foi consultado e fica registrado:** nenhum regimento acadêmico real (o grupo não tem acesso, `docs/case.md` §2.11); nenhuma conversa com atendente de secretaria; nenhuma documentação online do LangGraph nesta etapa (o comportamento relevante foi medido).
