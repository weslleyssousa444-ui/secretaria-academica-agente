# Testes da API (src/api.py) — Exercício 13. Offline: o modelo é o roteiro
# do conftest, e o banco e a pasta de logs são temporários.

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

import agente
import api
from conftest import chamada, contar, resposta


@pytest.fixture
def cliente(banco, tmp_path, monkeypatch):
    monkeypatch.setattr(api, "PASTA_LOGS", tmp_path / "logs")
    api._conversas.clear()
    with TestClient(api.app) as c:
        yield c


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
            resposta(content="Protocolo DOC-1001.")])
    r1 = cliente.post("/mensagens", json={"mensagem": "Preciso de uma declaração."})
    assert r1.status_code == 200 and r1.json()["resposta"] == "Qual é o seu RA?"
    conversa_id = r1.json()["conversa_id"]

    r2 = cliente.post("/mensagens", json={"mensagem": "20231045", "conversa_id": conversa_id})
    assert r2.json()["resposta"] == "Protocolo DOC-1001."
    assert r2.json()["encerrada"] is False
    assert contar("documentos_emitidos") == 2  # semente + a nova

    log = json.loads((tmp_path / "logs" / f"api-{conversa_id}.json").read_text(encoding="utf-8"))
    assert [p["ferramenta"] for p in log["passos"]] == ["buscar_aluno", "emitir_documento"]


def test_resposta_nao_expoe_resultado_de_ferramenta(cliente, modelo):
    modelo([resposta([chamada("consultar_financeiro", ra="20230198")]),
            resposta(content="Encaminhei seu caso.")])
    corpo = cliente.post("/mensagens", json={"mensagem": "segunda via, RA 20230198"}).json()
    assert set(corpo) == {"conversa_id", "resposta", "termino", "motivo", "encerrada"}
    assert "890" not in json.dumps(corpo)


def test_conversa_desconhecida_404(cliente):
    r = cliente.post("/mensagens", json={"mensagem": "oi", "conversa_id": "nao-existe"})
    assert r.status_code == 404


@pytest.mark.parametrize("mensagem", ["", "x" * 2001])
def test_mensagem_vazia_ou_longa_422(cliente, mensagem):
    assert cliente.post("/mensagens", json={"mensagem": mensagem}).status_code == 422


def test_conversa_encerrada_por_laco_recusa_novo_turno(cliente, modelo):
    modelo([resposta([chamada("buscar_aluno", ra="20231045")])])
    corpo = cliente.post("/mensagens", json={"mensagem": "oi"}).json()
    assert corpo["termino"] == "laco_detectado" and corpo["encerrada"] is True
    assert corpo["resposta"]  # o aluno nunca fica sem resposta
    r = cliente.post("/mensagens", json={"mensagem": "oi?", "conversa_id": corpo["conversa_id"]})
    assert r.status_code == 409
