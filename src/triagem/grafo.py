# A topologia do grafo (docs/grafo.md §1). O desenho em ASCII mora em
# docs/arquitetura.md; `conferir_grafo.py`, na raiz, imprime nós e arestas
# DESTE objeto e a saída é colada lá. Se divergirem, vale o código.
#
#   START -> entrada -+-> ler_memoria --------+
#                     |                        +-> rotear -+-(saudação)-> saudacao_fixa --+
#                     +-> classificar_pedido --+           |                              |
#                                                          +-(demais)--> agente <------+  |
#                                                                          |   ^       |  |
#                               +--------- (sem término e com tool_calls) -+   |       |  |
#                               v                                              |       |  |
#                           ferramentas ----------------------------------------+       |  |
#                                                                                       |  |
#   agente --(sem tool_calls)--> garantir_trancamento --(escalou)---------------------->+  |
#                                       |                                                  |
#                                       +--> validar_resposta --(devolveu)---> agente      |
#                                                  |                                       |
#                                                  +--(contingência)--> contingencia -+    |
#                                                  +--(ok)----------------------------+    |
#                                                                                     v    v
#                                                                               montar_saida <- (término)
#                                                                                     |
#                                                                               escrever_memoria
#                                                                                     |
#                                          +-------- (trancamento aberto) -----------+------ (senão) -> END
#                                          v
#                                  registrar_espera -> aprovacao_coordenacao [interrupt] -> registrar_decisao -> END

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from triagem import nos as n
from triagem.estado import Estado

# `recursion_limit` do LangGraph é um parâmetro com valor padrão (25) que
# esconde uma decisão: o teto de passos do grafo. O orçamento de passos do
# AGENTE (8 chamadas de ferramenta) é o limite de negócio; este é a rede de
# segurança por baixo dele. Declarado aqui, e não herdado (docs/grafo.md §5.3).
RECURSION_LIMIT = 60


def construir(nos: n.Nos | None = None) -> StateGraph:
    nos = nos or n.Nos()
    g = StateGraph(Estado)

    for nome in ("entrada", "ler_memoria", "classificar_pedido", "rotear",
                 "saudacao_fixa", "agente", "ferramentas", "garantir_trancamento",
                 "validar_resposta", "contingencia", "montar_saida",
                 "escrever_memoria", "registrar_espera", "aprovacao_coordenacao",
                 "registrar_decisao"):
        g.add_node(nome, getattr(nos, nome))

    g.add_edge(START, "entrada")
    # Paralelização (sectioning): dois ramos independentes, ambos locais.
    g.add_edge("entrada", "ler_memoria")
    g.add_edge("entrada", "classificar_pedido")
    g.add_edge(["ler_memoria", "classificar_pedido"], "rotear")

    g.add_conditional_edges("rotear", n.depois_do_rotear,
                            {"saudacao_fixa": "saudacao_fixa", "agente": "agente"})
    g.add_edge("saudacao_fixa", "montar_saida")

    g.add_conditional_edges("agente", n.depois_do_agente,
                            {"ferramentas": "ferramentas",
                             "garantir_trancamento": "garantir_trancamento",
                             "montar_saida": "montar_saida"})
    g.add_edge("ferramentas", "agente")

    g.add_conditional_edges("garantir_trancamento", n.depois_do_garantir,
                            {"agente": "agente", "validar_resposta": "validar_resposta"})
    g.add_conditional_edges("validar_resposta", n.depois_do_validar,
                            {"agente": "agente", "contingencia": "contingencia",
                             "montar_saida": "montar_saida"})
    g.add_edge("contingencia", "montar_saida")

    g.add_edge("montar_saida", "escrever_memoria")
    g.add_conditional_edges("escrever_memoria", n.depois_da_memoria,
                            {"registrar_espera": "registrar_espera", "__fim__": END})
    g.add_edge("registrar_espera", "aprovacao_coordenacao")
    g.add_edge("aprovacao_coordenacao", "registrar_decisao")
    g.add_edge("registrar_decisao", END)
    return g


# O MESMO objeto que o Sistema compila e que conferir_grafo.py lê.
GRAFO = construir()
