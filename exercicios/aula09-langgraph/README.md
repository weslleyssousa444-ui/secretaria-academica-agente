# Aula 09 — Agente de triagem em LangGraph

Sem enunciado formal; implementado a partir do material da aula ("o grafo que você já escreveu"). Não substitui `src/agente.py` (Ex.6, já validado).

**Rodar:**
```bash
.pytools/python/bin/python3 -m venv .venv311   # uma vez
source .venv311/bin/activate
pip install -r exercicios/requirements-aula9-10.txt
python exercicios/aula09-langgraph/agente_langgraph.py
```

**O que prova:**
- O laço `while/if` do Ex.6 vira `StateGraph` com 3 nós (`agente`, `ferramentas`, `aprovacao_trancamento`) e arestas condicionais — mesma lógica, declarada em vez de escrita.
- Caso simples (RA 20231045, declaração): `agente → ferramentas → agente → ferramentas → agente`, emitiu DOC-1687.
- Caso trancamento (RA 20229012): `interrupt()` pausa o grafo, mostra a ação exata (`escalar_para_humano`, argumentos), e `Command(resume=...)` retoma de onde parou — fecha a lacuna que `docs/memoria.md` §1.1 registrava (hoje o Ex.6 encerra com `HUMANO` sem retomar).
- Checkpointer em arquivo (`checkpoints.sqlite`, não commitado — efêmero), não em memória: sobrevive a reiniciar o processo.

**O que o framework não deu de graça** (nota desta aula, §9): motivo de término, detector de laço, orçamento de 4 moedas, classificação erro recuperável×fatal — nenhum disso está neste arquivo. O Ex.6 (`src/agente.py`) já tem os quatro; portá-los para cá é trabalho adicional não feito aqui, por tempo.

**Achado real:** `qwen/qwen3.8-27b` (modelo do Ex.6) bateu de novo no teto de 1.000 tokens de saída/min da Groq (mesmo problema do Ex.7/Ex.8) — trocado para `openai/gpt-oss-20b` via `LANGGRAPH_MODELO`.
