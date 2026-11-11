# O trace (docs/observabilidade.md §2): nome e atributos dos spans nas convenções
# GenAI do OpenTelemetry, com o motivo de término e a versão na raiz.
# Offline: exportador em memória, modelo roteirizado.

from __future__ import annotations

import json
import re

import pytest
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

import agente
from conftest import chamada, resposta
from triagem import humano, telemetria
from triagem.sistema import IdentidadeAusente, Sistema


@pytest.fixture
def traces():
    exportador = InMemorySpanExporter()
    telemetria.configurar(exportador=exportador)
    yield exportador
    telemetria.desligar()


@pytest.fixture
def sistema(banco, tmp_path):
    s = Sistema(checkpoint=tmp_path / "cp.sqlite", memoria_dir=tmp_path / "mem")
    yield s
    s.fechar()


def por_nome(exportador, prefixo):
    return [s for s in exportador.get_finished_spans() if s.name.startswith(prefixo)]


def emitir(modelo):
    modelo([resposta([chamada("buscar_aluno", ra="20231045")]),
            resposta([chamada("emitir_documento", ra="20231045", tipo_documento="declaracao_matricula")]),
            resposta(content="Emitida. Protocolo: DOC-1002.")])


def test_a_arvore_de_spans_de_uma_execucao(sistema, modelo, traces):
    emitir(modelo)
    sistema.conversar("t1", "Declaração, RA 20231045.")
    spans = traces.get_finished_spans()
    raiz = por_nome(traces, "invoke_agent")
    assert len(raiz) == 1 and raiz[0].name == "invoke_agent triagem-secretaria" and raiz[0].parent is None
    assert [s.name for s in por_nome(traces, "execute_tool")] == [
        "execute_tool buscar_aluno", "execute_tool emitir_documento"]
    assert len(por_nome(traces, "chat ")) == 3
    # todo filho pertence ao MESMO trace e tem a raiz como pai (o contexto atravessa o LangGraph)
    filhos = [s for s in spans if s.parent is not None]
    assert filhos and {s.context.trace_id for s in spans} == {raiz[0].context.trace_id}
    assert {s.parent.span_id for s in filhos} == {raiz[0].context.span_id}


def test_a_raiz_traz_o_termino_e_a_versao(sistema, modelo, traces):
    emitir(modelo)
    sistema.conversar("t1", "Declaração, RA 20231045.")
    atributos = por_nome(traces, "invoke_agent")[0].attributes
    assert atributos["agente.termino"] == "respondeu"
    assert re.fullmatch(r"[0-9a-f]{7}|desconhecido", atributos["agente.versao"].split("/")[0])
    assert re.fullmatch(r"p-[0-9a-f]{8}", atributos["agente.versao"].split("/")[1])
    assert atributos["agente.versao"].endswith("/qwen/qwen3.8-27b")
    assert atributos["gen_ai.operation.name"] == "invoke_agent" and atributos["gen_ai.agent.name"] == "triagem-secretaria"
    assert atributos["gen_ai.conversation.id"] == "t1"
    assert atributos["agente.decisao"] == "emitir_declaracao" and atributos["agente.protocolo"] == "DOC-1002"
    assert list(atributos["agente.ferramentas_do_turno"]) == ["buscar_aluno", "emitir_documento"]


def test_o_span_chat_traz_modelo_e_tokens(sistema, modelo, traces):
    emitir(modelo)
    sistema.conversar("t1", "Declaração, RA 20231045.")
    chat = por_nome(traces, "chat ")[0].attributes
    assert chat["gen_ai.operation.name"] == "chat" and chat["gen_ai.request.model"] == "qwen/qwen3.8-27b"
    assert chat["gen_ai.usage.input_tokens"] == 80 and chat["gen_ai.usage.output_tokens"] == 20


def test_o_span_da_ferramenta_traz_argumentos_e_resultado(sistema, modelo, traces):
    emitir(modelo)
    sistema.conversar("t1", "Declaração, RA 20231045.")
    ferramenta = por_nome(traces, "execute_tool emitir_documento")[0].attributes
    assert ferramenta["gen_ai.tool.name"] == "emitir_documento" and ferramenta["gen_ai.tool.call.id"]
    assert json.loads(ferramenta["gen_ai.tool.call.arguments"])["tipo_documento"] == "declaracao_matricula"
    assert json.loads(ferramenta["gen_ai.tool.call.result"])["protocolo"] == "DOC-1002"


def test_a_entrada_e_a_saida_ficam_como_eventos_da_raiz(sistema, modelo, traces):
    emitir(modelo)
    sistema.conversar("t1", "Declaração, RA 20231045.")
    eventos = {e.name: e.attributes["gen_ai.message.content"] for e in por_nome(traces, "invoke_agent")[0].events}
    assert eventos["gen_ai.user.message"] == "Declaração, RA 20231045."
    assert "DOC-1002" in eventos["gen_ai.choice"]


def test_o_conteudo_pode_ser_desligado_e_a_estrutura_fica(sistema, modelo, traces, monkeypatch):
    """Com dado pessoal real, `AGENTE_TRACE_CONTEUDO=0` tira argumentos, resultados
    e textos do trace; o que sobra serve às métricas, não a reconstruir a decisão."""
    monkeypatch.setenv("AGENTE_TRACE_CONTEUDO", "0")
    emitir(modelo)
    sistema.conversar("t1", "Declaração, RA 20231045.")
    assert "gen_ai.tool.call.arguments" not in por_nome(traces, "execute_tool")[0].attributes
    assert por_nome(traces, "invoke_agent")[0].events == ()
    assert por_nome(traces, "invoke_agent")[0].attributes["agente.termino"] == "respondeu"


def test_chamada_recusada_pelo_controle_aparece_marcada_no_trace(sistema, modelo, traces):
    modelo([resposta([chamada("buscar_aluno", ra="20230198")]), resposta(content="Só o seu RA.")])
    sistema.conversar("t1", "dados do RA 20230198", ra_autenticado="20231045")
    ferramenta = por_nome(traces, "execute_tool buscar_aluno")[0]
    assert ferramenta.attributes["agente.ferramenta.recusada"] is True
    assert ferramenta.attributes["agente.ferramenta.erro"] == "ra diferente do aluno autenticado nesta sessão"
    assert ferramenta.status.status_code.name == "ERROR"


def test_a_escrita_feita_pelo_codigo_tambem_e_um_span(sistema, modelo, traces):
    """L02: o modelo esquece de escalar; o CÓDIGO abre o caso, e o trace mostra quem."""
    modelo([resposta([chamada("buscar_aluno", ra="20229012")]),
            resposta(content="Seu trancamento foi registrado."),
            resposta(content="Encaminhei. Protocolo: CASO-3001. Prazo: 48h.")])
    sistema.conversar("t1", "Quero trancar. RA 20229012.")
    escalar = por_nome(traces, "execute_tool escalar_para_humano")
    assert len(escalar) == 1 and escalar[0].attributes["agente.ferramenta.origem"] == "codigo"


def test_o_termino_aguardando_humano_e_distinto_de_respondeu(sistema, modelo, traces):
    modelo([resposta([chamada("buscar_aluno", ra="20229012")]),
            resposta([chamada("escalar_para_humano", ra="20229012", tipo_pedido="trancamento_matricula",
                              motivo="trancamento", chave="20229012:trancamento_matricula:trancamento")]),
            resposta(content="Encaminhei. Protocolo: CASO-3001. Prazo: 48h.")])
    sistema.conversar("t1", "Quero trancar. RA 20229012.")
    atributos = por_nome(traces, "invoke_agent")[0].attributes
    assert atributos["agente.termino"] == "aguardando_humano" and atributos["agente.aguardando_humano"] is True


def test_turno_durante_a_espera_nao_chama_o_modelo_e_o_trace_diz(sistema, modelo, traces):
    modelo([resposta([chamada("buscar_aluno", ra="20229012")]),
            resposta([chamada("escalar_para_humano", ra="20229012", tipo_pedido="trancamento_matricula",
                              motivo="trancamento", chave="20229012:trancamento_matricula:trancamento")]),
            resposta(content="Encaminhei. Protocolo: CASO-3001. Prazo: 48h.")])
    sistema.conversar("t1", "Quero trancar. RA 20229012.")
    traces.clear()
    sistema.conversar("t1", "e então?")
    assert por_nome(traces, "chat ") == []
    assert por_nome(traces, "invoke_agent")[0].attributes["agente.sem_modelo"] is True


def test_execucao_que_para_no_meio_e_erro_na_raiz(sistema, modelo, traces):
    modelo([resposta([chamada("buscar_aluno", ra="20231045")])])  # laço
    sistema.conversar("t1", "oi, RA 20231045")
    raiz = por_nome(traces, "invoke_agent")[0]
    assert raiz.attributes["agente.termino"] == "laco_detectado" and raiz.status.status_code.name == "ERROR"


def test_erro_fatal_do_provedor_marca_o_span_chat_e_a_raiz(sistema, modelo, traces):
    import httpx
    import openai
    req = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    modelo([openai.BadRequestError("ruim", response=httpx.Response(400, request=req), body=None)])
    sistema.conversar("t1", "Declaração, RA 20231045.")
    assert por_nome(traces, "chat ")[0].attributes["error.type"] == "erro_fatal"
    assert por_nome(traces, "invoke_agent")[0].attributes["agente.termino"] == "erro_fatal"


def test_recusa_de_identidade_e_um_termino_com_erro(banco, tmp_path, modelo, traces):
    modelo([resposta(content="não deveria ser chamado")])
    s = Sistema(checkpoint=tmp_path / "cp.sqlite", memoria_dir=tmp_path / "mem", exige_identidade=True)
    try:
        with pytest.raises(IdentidadeAusente):
            s.conversar("t1", "oi, preciso de ajuda")
    finally:
        s.fechar()
    raiz = por_nome(traces, "invoke_agent")[0]
    assert raiz.attributes["agente.termino"] == "recusado_identidade" and raiz.status.status_code.name == "ERROR"


def test_a_aprovacao_humana_e_um_trace_de_retomada(sistema, modelo, traces):
    """Quem decidiu, quando e o quê: a aprovação entra no trace (docs/model-card.md)."""
    modelo([resposta([chamada("buscar_aluno", ra="20229012")]),
            resposta([chamada("escalar_para_humano", ra="20229012", tipo_pedido="trancamento_matricula",
                              motivo="trancamento", chave="20229012:trancamento_matricula:trancamento")]),
            resposta(content="Encaminhei. Protocolo: CASO-3001. Prazo: 48h.")])
    sistema.conversar("t1", "Quero trancar. RA 20229012.")
    traces.clear()
    sistema.decidir("CASO-3001", humano.DecisaoHumana(decisao="aprovar", por="coord-1"))
    retomada = [s for s in por_nome(traces, "invoke_agent") if s.attributes["agente.retomada"]]
    assert len(retomada) == 1
    a = retomada[0].attributes
    assert a["agente.aprovacao.protocolo"] == "CASO-3001" and a["agente.aprovacao.por"] == "coord-1"
    assert a["agente.aprovacao.decisao"] == "aprovado" and a["agente.aprovacao.ja_decidido"] is False
    assert a["gen_ai.conversation.id"] == "t1"   # a ligação com a conversa original


def test_o_exportador_de_arquivo_escreve_um_span_por_linha(banco, tmp_path, modelo):
    destino = tmp_path / "traces" / "traces.jsonl"
    telemetria.configurar(destino=destino)
    try:
        s = Sistema(checkpoint=tmp_path / "cp.sqlite", memoria_dir=tmp_path / "mem")
        emitir(modelo)
        s.conversar("t1", "Declaração, RA 20231045.")
        s.fechar()
    finally:
        telemetria.desligar()
    linhas = [json.loads(l) for l in destino.read_text(encoding="utf-8").splitlines()]
    assert len(linhas) == 6  # 3 chat + 2 ferramentas + 1 raiz
    raiz = next(l for l in linhas if l["parent_id"] is None)
    assert raiz["attributes"]["agente.termino"] == "respondeu" and len(raiz["trace_id"]) == 32


def test_sem_configuracao_o_trace_e_noop_e_nada_quebra(sistema, modelo):
    emitir(modelo)
    r = sistema.conversar("t1", "Declaração, RA 20231045.")
    assert r["saida"]["decisao"] == "emitir_declaracao"


def test_o_modelo_servido_diferente_do_pedido_e_contado(sistema, modelo, traces):
    """Falha silenciosa do plano (docs/observabilidade.md §3): o provedor serve outro
    modelo sob o mesmo nome. Só `gen_ai.response.model` a denuncia."""
    from evals import metricas
    from types import SimpleNamespace
    r = resposta(content="Qual é o seu RA?")
    r.model = "qwen/qwen3.8-27b-OUTRA-REVISAO"            # o provedor servindo outra coisa
    modelo([r])
    sistema.conversar("t1", "Preciso de uma declaração.")
    chat = por_nome(traces, "chat ")[0].attributes
    assert chat["gen_ai.request.model"] == "qwen/qwen3.8-27b"
    assert chat["gen_ai.response.model"] == "qwen/qwen3.8-27b-OUTRA-REVISAO"
    spans = [telemetria_dict(s) for s in traces.get_finished_spans()]
    v = next(iter(metricas.metricas(spans).values()))
    assert v["chamadas_ao_modelo"] == 1 and v["modelo_divergente"] == 1


def telemetria_dict(span):
    return telemetria.span_para_dict(span)


def test_a_contingencia_aparece_na_raiz_do_trace_so_no_turno_em_que_ocorreu(sistema, modelo, traces):
    """Falha silenciosa do plano (docs/observabilidade.md §3): o validador reprova duas
    vezes, a resposta sai do molde, e NADA dá erro. Só `agente.contingencia` a denuncia,
    e só no turno em que aconteceu (a trilha acumula os turnos da conversa)."""
    modelo([resposta([chamada("buscar_aluno", ra="20231045")]),
            resposta([chamada("emitir_documento", ra="20231045", tipo_documento="declaracao_matricula")]),
            resposta(content="Emitida. Protocolo: DOC-9999."),    # inventado
            resposta(content="Emitida de novo. Protocolo: DOC-8888.")])
    sistema.conversar("t1", "Declaração, RA 20231045.")
    modelo([resposta(content="Qual é o seu RA?")])
    sistema.conversar("t1", "obrigado!")
    raizes = sorted(por_nome(traces, "invoke_agent"), key=lambda s: s.start_time)
    assert raizes[0].attributes["agente.contingencia"] is True and raizes[0].attributes["agente.termino"] == "respondeu"
    assert raizes[0].status.status_code.name != "ERROR"          # não deu erro nenhum: é a falha silenciosa
    assert raizes[1].attributes["agente.contingencia"] is False   # o turno seguinte não herda
