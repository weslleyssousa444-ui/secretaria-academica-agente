# O estado do grafo e os reducers (docs/grafo.md §3.2).
#
# Duas demonstrações, em grafos mínimos, do que o reducer evita — e uma prova,
# no grafo entregue, de que os campos acumulados têm reducer.
#
#   1. Dois nós PARALELOS escrevem o mesmo campo sem reducer: o LangGraph
#      recusa a atualização (`InvalidUpdateError`). Esse é o comportamento da
#      versão fixada (langgraph 1.2.12) e é o que o teste trava: se uma versão
#      futura passar a aceitar em silêncio, o teste acusa.
#   2. Dois nós em SEQUÊNCIA escrevem o mesmo campo sem reducer: o segundo
#      SOBRESCREVE o primeiro, sem erro nem aviso. Esse é o defeito silencioso:
#      é o que aconteceria com `mensagens` e `passos` se o reducer faltasse.

from __future__ import annotations

from operator import add
from typing import Annotated, TypedDict

import pytest
from langgraph.errors import InvalidUpdateError
from langgraph.graph import END, START, StateGraph

from conftest import chamada, resposta
from triagem.sistema import Sistema


class SemReducer(TypedDict, total=False):
    trilha: list[str]


class ComReducer(TypedDict, total=False):
    trilha: Annotated[list[str], add]


def _paralelo(tipo):
    g = StateGraph(tipo)
    g.add_node("a", lambda e: {"trilha": ["a"]})
    g.add_node("b", lambda e: {"trilha": ["b"]})
    g.add_edge(START, "a")
    g.add_edge(START, "b")
    g.add_edge(["a", "b"], END)
    return g.compile()


def _sequencia(tipo):
    g = StateGraph(tipo)
    g.add_node("primeiro", lambda e: {"trilha": ["do primeiro"]})
    g.add_node("segundo", lambda e: {"trilha": ["do segundo"]})
    g.add_edge(START, "primeiro")
    g.add_edge("primeiro", "segundo")
    g.add_edge("segundo", END)
    return g.compile()


def test_paralelo_sem_reducer_e_recusado_pelo_framework():
    with pytest.raises(InvalidUpdateError):
        _paralelo(SemReducer).invoke({"trilha": []})


def test_paralelo_com_reducer_junta_os_dois_ramos():
    assert sorted(_paralelo(ComReducer).invoke({"trilha": []})["trilha"]) == ["a", "b"]


def test_sequencia_sem_reducer_sobrescreve_em_silencio():
    """O trabalho do primeiro nó desaparece, sem exceção e sem aviso."""
    assert _sequencia(SemReducer).invoke({"trilha": []})["trilha"] == ["do segundo"]


def test_sequencia_com_reducer_acumula():
    assert _sequencia(ComReducer).invoke({"trilha": []})["trilha"] == ["do primeiro", "do segundo"]


def test_no_grafo_entregue_os_dois_ramos_paralelos_aparecem_na_trilha(banco, tmp_path, modelo):
    """`ler_memoria` e `classificar_pedido` rodam em paralelo e escrevem em
    `eventos`: sem o reducer `add`, este turno falharia com InvalidUpdateError."""
    modelo([resposta(content="Qual é o seu RA?")])
    s = Sistema(checkpoint=tmp_path / "cp.sqlite", memoria_dir=tmp_path / "mem")
    try:
        s.conversar("t1", "Preciso de uma declaração.")
        eventos = s.estado("t1")["eventos"]
    finally:
        s.fechar()
    assert any(e.startswith("ler_memoria") for e in eventos)
    assert any(e.startswith("classificar_pedido") for e in eventos)


def test_todo_campo_acumulado_do_estado_entregue_tem_reducer():
    """O que o `Estado` declara como acumulado (lista ou contador) tem `add`."""
    import typing
    from triagem.estado import Estado
    dicas = typing.get_type_hints(Estado, include_extras=True)
    acumulados = {nome for nome, tipo in dicas.items() if typing.get_origin(tipo) is Annotated}
    assert acumulados == {"mensagens", "passos", "tokens_gastos", "n_chamadas_modelo", "eventos"}
