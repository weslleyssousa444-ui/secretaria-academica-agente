# Aula 09 — O agente de triagem (Ex.6, src/agente.py) reescrito como
# LangGraph. Sem enunciado formal nesta aula: o próprio material aponta
# para isto ("Exemplo 2 — o grafo que você já escreveu"), e a Parte 2 do
# trabalho exige o grafo em LangChain/LangGraph.
#
# NÃO substitui src/agente.py (já validado, 35/40 no verificador do Ex.6).
# É um arquivo novo, lado a lado, rodando em ambiente Python 3.11 à parte
# (exercicios/requirements-aula9-10.txt — o mcp e o langgraph exigem
# Python >= 3.10, e o venv principal do projeto é 3.9).
#
# O QUE ESTE EXERCÍCIO FECHA que o src/agente.py não fechava: o trancamento
# hoje (Ex.6) termina com `HUMANO` e a conversa acaba ali — não há como a
# coordenação retomar depois (docs/memoria.md §1.1 já registrava isso como
# lacuna). Aqui, `interrupt()` + checkpointer em arquivo fecham o laço:
# o grafo pausa esperando a decisão da coordenação, e retoma de onde parou,
# em outro processo, outro dia.

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated, TypedDict

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
import dados  # mesmo "sistema acadêmico" simulado do Ex.6 (SQLite)

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / ".env")

from langchain_core.messages import AnyMessage, SystemMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.types import Command, interrupt

# ============================================================ FERRAMENTAS
# Mesma lógica de negócio do src/agente.py (docs/case.md §2.1), reescrita
# com @tool do LangChain — é o mesmo corpo de função, só a declaração muda
# de lugar (nota 02-escrever-um-servidor §1 desta mesma disciplina, uma
# aula depois, faz a MESMA observação sobre MCP: "o corpo não muda").

@tool
def buscar_aluno(ra: str) -> dict:
    """Consulta cadastro e situação de matrícula do aluno pelo RA."""
    con = dados.conectar()
    linha = con.execute("SELECT * FROM alunos WHERE ra = ?", (ra,)).fetchone()
    con.close()
    if not linha:
        return {"erro": "RA não encontrado no sistema acadêmico",
                "recebido": ra, "sugestao": "peça para o aluno confirmar o RA"}
    return dict(linha)


@tool
def consultar_financeiro(ra: str) -> dict:
    """Consulta mensalidades em aberto do aluno pelo RA."""
    con = dados.conectar()
    linha = con.execute(
        "SELECT * FROM financeiro WHERE ra = ?", (ra,)).fetchone()
    con.close()
    if not linha:
        return {"ra": ra, "mensalidades_em_aberto": 0, "valor_em_aberto": 0.0}
    return dict(linha)


@tool
def emitir_documento(ra: str, tipo_documento: str) -> dict:
    """Emite declaração de matrícula ou segunda via de histórico.
    tipo_documento: "declaracao_matricula" ou "segunda_via_historico"."""
    if tipo_documento not in ("declaracao_matricula", "segunda_via_historico"):
        return {"erro": "tipo de documento fora do catálogo",
                "recebido": tipo_documento}
    con = dados.conectar()
    aluno = con.execute(
        "SELECT * FROM alunos WHERE ra = ?", (ra,)).fetchone()
    if not aluno:
        con.close()
        return {"erro": "RA não encontrado", "recebido": ra}
    if aluno["situacao_matricula"] != "ativa" and tipo_documento == "declaracao_matricula":
        con.close()
        return {"erro": "matrícula não ativa, declaração não pode ser emitida"}
    if tipo_documento == "segunda_via_historico":
        fin = con.execute(
            "SELECT * FROM financeiro WHERE ra = ?", (ra,)).fetchone()
        if fin and fin["mensalidades_em_aberto"] > 0:
            con.close()
            return {"erro": "pendência financeira impede a emissão"}
    protocolo = f"DOC-{hash((ra, tipo_documento)) % 9000 + 1000}"
    con.execute("INSERT OR IGNORE INTO documentos_emitidos "
                "(protocolo, ra, tipo_documento, data_emissao) "
                "VALUES (?, ?, ?, date('now'))", (protocolo, ra, tipo_documento))
    con.commit()
    con.close()
    return {"protocolo": protocolo, "ra": ra, "tipo_documento": tipo_documento}


@tool
def escalar_para_humano(ra: str, tipo_pedido: str, motivo: str, chave: str) -> dict:
    """Abre caso na fila da secretaria/coordenação, com idempotência pela chave."""
    con = dados.conectar()
    existente = con.execute(
        "SELECT * FROM casos_pendentes WHERE chave = ?", (chave,)).fetchone()
    if existente:
        con.close()
        return {**dict(existente), "ja_existia": True}
    protocolo = f"CASO-{hash(chave) % 9000 + 1000}"
    con.execute("INSERT INTO casos_pendentes "
                "(protocolo, ra, tipo_pedido, motivo, chave, status) "
                "VALUES (?, ?, ?, ?, ?, 'aberto')",
                (protocolo, ra, tipo_pedido, motivo, chave))
    con.commit()
    con.close()
    return {"protocolo": protocolo, "ra": ra, "tipo_pedido": tipo_pedido,
            "motivo": motivo, "ja_existia": False}


FERRAMENTAS = [buscar_aluno, consultar_financeiro, emitir_documento,
               escalar_para_humano]

SYSTEM = (Path(__file__).parent.parent.parent / "prompts" / "triagem-v1.txt"
          ).read_text(encoding="utf-8")


# ============================================================ O ESTADO
# O `EstadoAgente` do Ex.6 vira TypedDict; `mensagens` ganha o reducer
# add_messages (nota 01 desta aula, §6) — sem ele, cada nó SUBSTITUIRIA o
# histórico em vez de acrescentar a ele.

class Estado(TypedDict):
    mensagens: Annotated[list[AnyMessage], add_messages]


# ============================================================ OS NÓS
# O laço while/if do src/agente.py (`montar_mensagens`, a chamada ao
# modelo, o `if not msg.tool_calls`) vira dois nós e uma aresta condicional
# — é literalmente o Exemplo 2 da nota desta aula.

modelo = ChatOpenAI(
    # qwen/qwen3.8-27b (LLM_MODELO do Ex.6) tem teto de 1.000 tokens de
    # saída/min na Groq (achado do Ex.7/Ex.8) — reaproveitado aqui.
    model=__import__("os").environ.get("LANGGRAPH_MODELO", "openai/gpt-oss-20b"),
    base_url=__import__("os").environ.get("LLM_BASE_URL",
                                           "https://api.groq.com/openai/v1"),
    api_key=__import__("os").environ.get("OPENAI_API_KEY"),
    temperature=0,
).bind_tools(FERRAMENTAS)


def no_agente(estado: Estado) -> dict:
    mensagens = [SystemMessage(SYSTEM)] + estado["mensagens"]
    resposta = modelo.invoke(mensagens)
    return {"mensagens": [resposta]}


def no_aprovacao_trancamento(estado: Estado) -> dict:
    """O HUMANO NO MEIO DO GRAFO (nota desta aula, §8/Parte 5). Só existe
    porque há checkpointer: a pausa é um checkpoint gravado, endereçado
    pelo thread_id, e a retomada prossegue exatamente daqui."""
    ultima = estado["mensagens"][-1]
    chamada_trancamento = next(
        c for c in ultima.tool_calls if c["name"] == "escalar_para_humano"
        and c["args"].get("tipo_pedido") == "trancamento_matricula")

    decisao = interrupt({
        "acao": chamada_trancamento["name"],
        "argumentos": chamada_trancamento["args"],
        "pergunta": "Confirma o encaminhamento deste trancamento à coordenação?",
    })
    # decisao chega aqui só quando alguém retomar com Command(resume=...)
    resultado = escalar_para_humano.invoke(chamada_trancamento["args"]) \
        if decisao.get("aprovado") else {"status": "rejeitado_pela_coordenacao"}
    from langchain_core.messages import ToolMessage
    return {"mensagens": [ToolMessage(content=str(resultado),
                                       tool_call_id=chamada_trancamento["id"])]}


def rota_apos_agente(estado: Estado) -> str:
    ultima = estado["mensagens"][-1]
    if not getattr(ultima, "tool_calls", None):
        return END
    for c in ultima.tool_calls:
        if c["name"] == "escalar_para_humano" and \
                c["args"].get("tipo_pedido") == "trancamento_matricula":
            return "aprovacao_trancamento"
    return "ferramentas"


# ============================================================ O GRAFO

grafo = StateGraph(Estado)
grafo.add_node("agente", no_agente)
grafo.add_node("ferramentas", ToolNode(FERRAMENTAS, messages_key="mensagens"))
grafo.add_node("aprovacao_trancamento", no_aprovacao_trancamento)
grafo.set_entry_point("agente")
grafo.add_conditional_edges("agente", rota_apos_agente,
                             {"ferramentas": "ferramentas",
                              "aprovacao_trancamento": "aprovacao_trancamento",
                              END: END})
grafo.add_edge("ferramentas", "agente")
grafo.add_edge("aprovacao_trancamento", "agente")

# Checkpointer em ARQUIVO, não em memória (nota desta aula, §7): "fecha o
# terminal, reabre, a conversa continua" exige isso — em memória, a
# promessa não se cumpre.
CAMINHO_CHECKPOINT = Path(__file__).parent / "checkpoints.sqlite"
_gerenciador_checkpoint = SqliteSaver.from_conn_string(str(CAMINHO_CHECKPOINT))
_checkpointer = _gerenciador_checkpoint.__enter__()
aplicativo = grafo.compile(checkpointer=_checkpointer)


if __name__ == "__main__":
    dados.inicializar()

    print("=== CASO 1: pedido simples, sem interrupção ===")
    config1 = {"configurable": {"thread_id": "demo-simples"}}
    for evento in aplicativo.stream(
        {"mensagens": [("user", "Preciso de uma declaração de matrícula. "
                                 "Meu RA é 20231045.")]}, config1):
        for no, saida in evento.items():
            if saida.get("mensagens"):
                print(f"  [{no}] {saida['mensagens'][-1].content[:150]}")

    print("\n=== CASO 2: trancamento — pausa para aprovação humana ===")
    config2 = {"configurable": {"thread_id": "demo-trancamento"}}
    resultado = aplicativo.invoke(
        {"mensagens": [("user", "Quero trancar minha matrícula. "
                                 "Meu RA é 20229012.")]}, config2)
    if "__interrupt__" in resultado:
        pausa = resultado["__interrupt__"][0]
        print(f"  PAUSADO: {pausa.value}")
        print("  (processo poderia encerrar aqui — retomando no mesmo "
              "processo só para a demo)")
        final = aplicativo.invoke(Command(resume={"aprovado": True}), config2)
        print(f"  RETOMADO: {final['mensagens'][-1].content[:200]}")
    else:
        print("  (não pausou — ver tool_calls do modelo)")
