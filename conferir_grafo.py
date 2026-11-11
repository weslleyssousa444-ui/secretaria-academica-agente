"""Confere o grafo ENTREGUE contra o desenho de docs/arquitetura.md.

Importa o MESMO objeto de grafo que `src/triagem/sistema.py` compila
(`triagem.grafo.GRAFO`), e não monta um grafo próprio: um grafo de
demonstração produziria a mesma saída bonita e não provaria nada.

Uso, a partir da raiz:  python conferir_grafo.py

Imprime os nós, as arestas (`origem -> destino`, com as condicionais
marcadas) e os parâmetros que o framework escondia. Se esta saída divergir do
desenho, vale o código, e o desenho estava errado.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))
# agente.py instancia o cliente do modelo ao ser importado; o valor é falso de
# propósito, porque este script nunca chama o modelo.
if not os.environ.get("OPENAI_API_KEY"):
    os.environ["OPENAI_API_KEY"] = "conferir-grafo-sem-chamada"

from triagem.grafo import GRAFO, RECURSION_LIMIT  # noqa: E402

grafo = GRAFO.compile().get_graph()
nos = sorted(n for n in grafo.nodes if not n.startswith("__"))
arestas = sorted(grafo.edges, key=lambda e: (e.source, e.target))

print(f"NÓS ({len(nos)})")
for no in nos:
    print(f"  {no}")
print(f"\nARESTAS ({len(arestas)})")
for e in arestas:
    marca = "   [condicional]" if e.conditional else ""
    print(f"  {e.source} -> {e.target}{marca}")
print(f"\nPARÂMETROS  recursion_limit={RECURSION_LIMIT}  "
      f"condicionais={sum(1 for e in arestas if e.conditional)}  "
      f"incondicionais={sum(1 for e in arestas if not e.conditional)}")
