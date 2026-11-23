# O contrato de handoff entre os dois agentes (src/triagem/handoff.py,
# docs/multiagente.md) e o trace do segundo agente. Offline: modelo roteirizado,
# servidor MCP em memória.

from __future__ import annotations

import asyncio

import pytest
from mcp.shared.memory import create_connected_server_and_client_session
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

import assistente_coordenacao as ac
import mcp_secretaria
from conftest import ModeloRoteirizado, chamada, contar, resposta
from triagem import handoff, humano, telemetria
from triagem.sistema import Sistema

RA = "20229012"


@pytest.fixture
def sistema(banco, tmp_path):
    s = Sistema(checkpoint=tmp_path / "cp.sqlite", memoria_dir=tmp_path / "mem")
    yield s
    s.fechar()


@pytest.fixture
def traces():
    exportador = InMemorySpanExporter()
    telemetria.configurar(exportador=exportador)
    yield exportador
    telemetria.desligar()


def trancar(sistema, modelo, thread="t1"):
    modelo([resposta([chamada("buscar_aluno", ra=RA)]),
            resposta([chamada("consultar_financeiro", ra=RA)]),
            resposta([chamada("escalar_para_humano", ra=RA, tipo_pedido="trancamento_matricula",
                              motivo="aluno pediu trancamento")]),
            resposta(content="Encaminhei seu pedido. Protocolo: CASO-3001. Prazo: 48h.")])
    return sistema.conversar(thread, f"Quero trancar minha matrícula. Meu RA é {RA}.")


def preparar(protocolo, roteiro):
    modelo = ModeloRoteirizado(roteiro)

    async def f():
        async with create_connected_server_and_client_session(mcp_secretaria.servidor._mcp_server) as s:
            return await ac.preparar_parecer(protocolo, s, cliente=modelo)
    return asyncio.run(f()), modelo


def parecer_ok(protocolo):
    import json
    return json.dumps({"protocolo": protocolo, "ra": RA,
                       "resumo": "Pedido de trancamento encaminhado pelo atendimento.",
                       "fatos": [{"texto": "Bruno Castro, matrícula ativa", "fonte": "buscar_aluno"}],
                       "artigos": [], "pontos_de_atencao": []}, ensure_ascii=False)


# ------------------------------------------------------------- o contrato

def test_o_grafo_grava_o_handoff_com_os_campos_do_contrato(sistema, modelo):
    r = trancar(sistema, modelo)
    assert r["aguardando_humano"] is True
    h = handoff.Handoff.model_validate(handoff.carregar("CASO-3001"))
    assert h.protocolo == "CASO-3001" and h.ra == RA and h.thread_id == "t1"
    assert h.objetivo and h.decisoes[0].razao.startswith("trancamento é decidido pela coordenação")
    assert {"ferramenta": "escalar_para_humano", "identificador": "CASO-3001"} in [e.model_dump() for e in h.escritas]
    assert h.fatos_numericos["prazo_coordenacao_horas"] == 48
    assert "mensalidades_em_aberto" in h.fatos_numericos
    assert h.chave_idempotencia == handoff.gerar_chave("CASO-3001", "t1", RA)


def test_a_chave_e_do_conteudo_e_repetir_nao_cria_outro(banco):
    h = handoff.montar("CASO-3001", "t1", RA, [])
    assert handoff.montar("CASO-3001", "t1", RA, []).chave_idempotencia == h.chave_idempotencia
    assert handoff.montar("CASO-3002", "t1", RA, []).chave_idempotencia != h.chave_idempotencia
    assert handoff.gravar(h) == {"chave": h.chave_idempotencia, "ja_existia": False}
    assert handoff.gravar(h)["ja_existia"] is True
    assert contar("handoffs") == 1


def test_erros_do_agente_do_aluno_vao_no_handoff(banco):
    passos = [{"ferramenta": "buscar_aluno", "argumentos": {"ra": "20240000"}, "resultado": {"erro": "x"},
               "erro": "aluno não encontrado"}]
    h = handoff.montar("CASO-3001", "t1", RA, passos)
    assert h.erros == ["buscar_aluno: aluno não encontrado"]


def test_a_tela_da_coordenacao_mostra_o_handoff(sistema, modelo):
    trancar(sistema, modelo)
    assert humano.tela_da_aprovacao("CASO-3001")["handoff"]["protocolo"] == "CASO-3001"


# ------------------------------------------- o assistente exige o contrato

def test_caso_sem_handoff_e_recusado_sem_chamar_o_modelo(banco):
    import agente
    r = agente.escalar_para_humano(RA, "trancamento", "pediu", f"{RA}:trancamento:sem-handoff")
    humano.registrar_espera("t-x", r["protocolo"], RA)
    saida, modelo = preparar(r["protocolo"], [resposta(content="{}")])
    assert saida["parecer"] is None and "sem contrato de handoff" in saida["erro"]
    assert modelo.chamadas == 0


def test_handoff_de_outro_caso_e_recusado(banco):
    import agente
    r = agente.escalar_para_humano(RA, "trancamento", "pediu", f"{RA}:trancamento:troca")
    humano.registrar_espera("t-x", r["protocolo"], RA)
    errado = handoff.montar(r["protocolo"], "t-x", "20230198", [])   # RA de outra aluna
    handoff.gravar(errado)
    saida, modelo = preparar(r["protocolo"], [resposta(content="{}")])
    assert saida["parecer"] is None and "não é deste caso" in saida["erro"]
    assert modelo.chamadas == 0


def test_o_parecer_carrega_a_chave_do_handoff(sistema, modelo):
    trancar(sistema, modelo)
    saida, _ = preparar("CASO-3001", [resposta([chamada("buscar_aluno", ra=RA)]),
                                      resposta(content=parecer_ok("CASO-3001"))])
    assert saida["origem"] == "modelo"
    assert saida["handoff_chave"] == handoff.gerar_chave("CASO-3001", "t1", RA)


# ------------------------------------------- um invoke_agent por agente

def test_cada_agente_tem_a_sua_raiz_no_trace(sistema, modelo, traces):
    trancar(sistema, modelo)
    preparar("CASO-3001", [resposta([chamada("buscar_aluno", ra=RA), chamada("consultar_financeiro", ra="20230198")]),
                           resposta(content=parecer_ok("CASO-3001"))])
    spans = traces.get_finished_spans()
    raizes = {s.attributes["gen_ai.agent.name"]: s for s in spans if s.name.startswith("invoke_agent ")}
    assert set(raizes) == {"triagem-secretaria", "assistente-coordenacao"}
    assistente = raizes["assistente-coordenacao"]
    assert assistente.attributes["agente.termino"] == "respondeu"
    assert assistente.attributes["agente.handoff.chave"] == handoff.gerar_chave("CASO-3001", "t1", RA)
    assert assistente.attributes["agente.recusas"] == 1
    assert assistente.attributes["agente.versao"]
    filhos = [s for s in spans if s.parent and s.parent.span_id == assistente.context.span_id]
    nomes = [s.name for s in filhos]
    assert sum(n.startswith("chat ") for n in nomes) == 2
    assert "execute_tool buscar_aluno" in nomes
    recusada = next(s for s in filhos if s.name == "execute_tool consultar_financeiro")
    assert recusada.attributes["agente.ferramenta.recusada"] is True
