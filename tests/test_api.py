# Testes da API (src/api.py): Exercício 13, religada ao grafo na Parte 2.
# Offline: o modelo é o roteiro do conftest, e o banco, o checkpoint, a memória
# e a pasta de logs são temporários.

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

import agente
import api
from conftest import chamada, contar, resposta

TOKEN = "token-de-teste-da-coordenacao"
CHAVES_DA_RESPOSTA = {"conversa_id", "resposta", "decisao", "protocolo",
                      "aguardando_coordenacao", "termino", "motivo", "encerrada"}


@pytest.fixture
def cliente(banco, tmp_path, monkeypatch):
    monkeypatch.setattr(api, "PASTA_LOGS", tmp_path / "logs")
    monkeypatch.setenv("TRIAGEM_CHECKPOINT", str(tmp_path / "cp.sqlite"))
    monkeypatch.setenv("TRIAGEM_MEMORIA_DIR", str(tmp_path / "mem"))
    monkeypatch.delenv("COORDENACAO_TOKEN", raising=False)
    monkeypatch.delenv("TRIAGEM_CONFIA_NO_PORTAL", raising=False)
    api._sistema = None
    with TestClient(api.app) as c:
        yield c
    api._sistema = None


def trancamento(cliente, modelo):
    modelo([resposta([chamada("buscar_aluno", ra="20229012")]),
            resposta([chamada("escalar_para_humano", ra="20229012", tipo_pedido="trancamento_matricula",
                              motivo="trancamento", chave="20229012:trancamento_matricula:trancamento")]),
            resposta(content="Encaminhei seu pedido. Protocolo: CASO-3001. Prazo: 48h.")])
    return cliente.post("/mensagens", json={"mensagem": "Quero trancar. Meu RA é 20229012."}).json()


# ---------------------------------------------------------------- o aluno

def test_saude_nao_chama_o_modelo(cliente, modelo):
    falso = modelo([resposta(content="não deveria ser chamado")])
    r = cliente.get("/saude")
    assert r.status_code == 200
    assert r.json() == {"ok": True, "banco": True, "modelo": agente.MODELO}
    assert falso.chamadas == 0


def test_conversa_em_dois_turnos_emite_e_grava_registro(cliente, modelo, tmp_path):
    modelo([resposta(content="Qual é o seu RA?"),
            resposta([chamada("buscar_aluno", ra="20231045")]),
            resposta([chamada("emitir_documento", ra="20231045",
                              tipo_documento="declaracao_matricula")]),
            resposta(content="Emitida. Protocolo: DOC-1002.")])
    r1 = cliente.post("/mensagens", json={"mensagem": "Preciso de uma declaração."})
    assert r1.status_code == 200 and r1.json()["resposta"] == "Qual é o seu RA?"
    conversa_id = r1.json()["conversa_id"]

    r2 = cliente.post("/mensagens", json={"mensagem": "20231045", "conversa_id": conversa_id})
    assert r2.json()["resposta"] == "Emitida. Protocolo: DOC-1002."
    assert r2.json()["decisao"] == "emitir_declaracao" and r2.json()["protocolo"] == "DOC-1002"
    assert r2.json()["encerrada"] is False
    assert contar("documentos_emitidos") == 2  # semente + a nova

    log = json.loads((tmp_path / "logs" / f"api-{conversa_id}.json").read_text(encoding="utf-8"))
    assert log["saida"]["decisao"] == "emitir_declaracao"
    assert "ferramentas" in log["trilha_de_nos"]


def test_resposta_nao_expoe_resultado_de_ferramenta(cliente, modelo):
    modelo([resposta([chamada("consultar_financeiro", ra="20230198")]),
            resposta(content="Encaminhei seu caso.")])
    corpo = cliente.post("/mensagens", json={"mensagem": "segunda via, RA 20230198"}).json()
    assert set(corpo) == CHAVES_DA_RESPOSTA
    assert "890" not in json.dumps(corpo)


def test_conversa_desconhecida_404(cliente):
    r = cliente.post("/mensagens", json={"mensagem": "oi", "conversa_id": "nao-existe"})
    assert r.status_code == 404


@pytest.mark.parametrize("mensagem", ["", "x" * 2001])
def test_mensagem_vazia_ou_longa_422(cliente, mensagem):
    assert cliente.post("/mensagens", json={"mensagem": mensagem}).status_code == 422


def test_conversa_encerrada_por_laco_recusa_novo_turno(cliente, modelo):
    modelo([resposta([chamada("buscar_aluno", ra="20231045")])])
    corpo = cliente.post("/mensagens", json={"mensagem": "oi, RA 20231045"}).json()
    assert corpo["termino"] == "laco_detectado" and corpo["encerrada"] is True
    assert corpo["resposta"]  # o aluno nunca fica sem resposta
    r = cliente.post("/mensagens", json={"mensagem": "oi?", "conversa_id": corpo["conversa_id"]})
    assert r.status_code == 409


def test_trancamento_responde_ao_aluno_e_fica_aguardando_a_coordenacao(cliente, modelo):
    corpo = trancamento(cliente, modelo)
    assert corpo["aguardando_coordenacao"] is True and corpo["protocolo"] == "CASO-3001"
    assert corpo["decisao"] == "escalar_trancamento" and corpo["encerrada"] is False


# ---------------------------------------------------------------- a identidade

def test_cabecalho_de_identidade_e_ignorado_sem_portal(cliente, modelo, tmp_path):
    modelo([resposta([chamada("buscar_aluno", ra="20231045")]),
            resposta([chamada("emitir_documento", ra="20231045", tipo_documento="declaracao_matricula")]),
            resposta(content="Emitida. Protocolo: DOC-1002.")])
    cliente.post("/mensagens", json={"mensagem": "Declaração, RA 20231045."},
                 headers={"X-Aluno-RA": "20231045"})
    assert not (tmp_path / "mem" / "episodica.json").exists()  # sem portal, sem memória


def test_cabecalho_de_identidade_vale_com_portal_e_grava_memoria(cliente, modelo, tmp_path, monkeypatch):
    monkeypatch.setenv("TRIAGEM_CONFIA_NO_PORTAL", "1")
    modelo([resposta([chamada("buscar_aluno", ra="20231045")]),
            resposta([chamada("emitir_documento", ra="20231045", tipo_documento="declaracao_matricula")]),
            resposta(content="Emitida. Protocolo: DOC-1002.")])
    cliente.post("/mensagens", json={"mensagem": "Declaração, RA 20231045."},
                 headers={"X-Aluno-RA": "20231045"})
    episodios = json.loads((tmp_path / "mem" / "episodica.json").read_text(encoding="utf-8"))
    assert episodios[0]["ra"] == "20231045" and "DOC-1002" in episodios[0]["resumo"]


# ---------------------------------------------------------------- a coordenação

def test_coordenacao_sem_token_configurado_fica_fechada(cliente):
    """Fail-closed: sem COORDENACAO_TOKEN o endpoint de decisão NÃO funciona."""
    assert cliente.get("/coordenacao/casos").status_code == 503
    r = cliente.post("/coordenacao/casos/CASO-3001/decisao",
                     json={"decisao": "aprovar", "por": "x"}, headers={"X-Coordenacao-Token": "qualquer"})
    assert r.status_code == 503


def test_coordenacao_recusa_token_ausente_ou_errado(cliente, monkeypatch):
    monkeypatch.setenv("COORDENACAO_TOKEN", TOKEN)
    assert cliente.get("/coordenacao/casos").status_code == 401
    assert cliente.get("/coordenacao/casos", headers={"X-Coordenacao-Token": "errado"}).status_code == 401


def test_coordenacao_lista_decide_e_a_segunda_decisao_nao_grava(cliente, modelo, monkeypatch):
    monkeypatch.setenv("COORDENACAO_TOKEN", TOKEN)
    cab = {"X-Coordenacao-Token": TOKEN}
    trancamento(cliente, modelo)

    lista = cliente.get("/coordenacao/casos", headers=cab).json()
    assert [c["protocolo"] for c in lista] == ["CASO-3001"] and lista[0]["aluno"]["nome"] == "Bruno Castro"

    corpo = {"decisao": "aprovar_editando", "por": "coord-1", "edicao": {"semestre_efetivo": "2027.1"}}
    primeira = cliente.post("/coordenacao/casos/CASO-3001/decisao", json=corpo, headers=cab)
    assert primeira.status_code == 200 and primeira.json()["decisao"] == "aprovado"
    segunda = cliente.post("/coordenacao/casos/CASO-3001/decisao", json=corpo, headers=cab)
    assert segunda.json()["ja_decidido"] is True and contar("decisoes_humanas") == 1
    assert cliente.get("/coordenacao/casos", headers=cab).json() == []  # nada mais espera


def test_decisao_fora_do_contrato_422_e_caso_desconhecido_404(cliente, modelo, monkeypatch):
    monkeypatch.setenv("COORDENACAO_TOKEN", TOKEN)
    cab = {"X-Coordenacao-Token": TOKEN}
    trancamento(cliente, modelo)
    sem_edicao = {"decisao": "aprovar_editando", "por": "coord-1"}
    assert cliente.post("/coordenacao/casos/CASO-3001/decisao", json=sem_edicao, headers=cab).status_code == 422
    assert cliente.post("/coordenacao/casos/CASO-9999/decisao",
                        json={"decisao": "aprovar", "por": "x"}, headers=cab).status_code == 404
