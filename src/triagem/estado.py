# O estado que atravessa o grafo (docs/grafo.md §3).
#
# Declaração de tipo, não argumento: cada campo diz QUEM escreve e COM QUE
# reducer. Um campo escrito por mais de um nó no mesmo passo precisa de
# reducer; sem ele o LangGraph recusa a atualização (demonstração em
# tests/test_estado.py e em docs/grafo.md §3.2).
#
# O que fica de fora do estado, de propósito (docs/grafo.md §3.3):
#   - o contador de passos: DERIVADO (`len(passos)`), guardá-lo criaria duas
#     fontes de verdade;
#   - o objeto de memória e a conexão do banco: são recursos, não estado.

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict


class Estado(TypedDict, total=False):
    # ---- identidade da conversa (entrada; escrita pelo chamador) -----------
    thread_id: str                 # endereço do checkpoint
    ra_autenticado: str | None     # sessão do portal; None = sem identidade

    # ---- conversa ----------------------------------------------------------
    # Reducer `add`: cada nó ACRESCENTA ao histórico. Sem ele, o nó que
    # devolve `mensagens` substituiria a conversa inteira.
    mensagens: Annotated[list[dict[str, Any]], add]
    # Trajetória: ferramenta, argumentos, resultado, erro. É o que o
    # validador, a saída, a memória e o trace leem.
    passos: Annotated[list[dict[str, Any]], add]
    tokens_gastos: Annotated[int, add]
    n_chamadas_modelo: Annotated[int, add]
    # Trilha dos nós percorridos. É o campo que DOIS nós paralelos escrevem
    # no mesmo passo (`ler_memoria` e `classificar_pedido`): por isso o reducer.
    eventos: Annotated[list[str], add]

    # ---- por turno (reiniciados no nó `entrada`) ---------------------------
    inicio_do_turno: int           # índice em `passos` onde o turno começou
    turno_iniciado_em: float       # time.monotonic() do início do turno (teto de tempo)
    tipo_pedido: str | None        # saudacao | trancamento | outro
    memoria_bloco: str
    correcoes: int                 # quantas vezes o validador devolveu a resposta
    termino: str | None            # respondeu | orcamento_esgotado | laco_detectado | erro_fatal
    motivo: str | None
    saida: dict[str, Any] | None   # SaidaTriagem.model_dump()
    caso_trancamento: str | None   # protocolo aberto NESTE turno (dispara a espera humana)

    # ---- aprovação humana --------------------------------------------------
    decisao_humana: dict[str, Any] | None
