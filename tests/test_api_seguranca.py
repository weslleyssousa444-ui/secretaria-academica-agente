# Evidência do Exercício 14 para os riscos que moram em src/api.py
# (exercicios/aula14-respostas.md: ASI03 e ASI08), atualizada para a API em
# grafo (Parte 2). Mesma convenção de test_seguranca.py: "lacuna" = o teste
# PASSA descrevendo o defeito; quando for corrigido, falha e deve ser invertido.
#
# O que mudou com a Parte 2: o `conversa_id` deixou de ter 32 bits (a lacuna
# virou mitigação) e a conversa deixou de viver num dicionário do processo
# (agora é o checkpoint em arquivo).
#
# Exige FastAPI, que exige Python >= 3.10 (src/api.py usa `str | None` em
# modelos Pydantic). Em Python 3.9 o módulo inteiro é pulado.

from __future__ import annotations

import re
import sys
import threading

import pytest

if sys.version_info < (3, 10):
    pytest.skip("src/api.py exige Python >= 3.10", allow_module_level=True)
pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

import api  # noqa: E402
from conftest import resposta  # noqa: E402


@pytest.fixture
def cliente(banco, tmp_path, monkeypatch):
    monkeypatch.setattr(api, "PASTA_LOGS", tmp_path / "logs")
    monkeypatch.setenv("TRIAGEM_CHECKPOINT", str(tmp_path / "cp.sqlite"))
    monkeypatch.setenv("TRIAGEM_MEMORIA_DIR", str(tmp_path / "mem"))
    api._sistema = None
    with TestClient(api.app) as c:
        yield c
    api._sistema = None


# ---------------------------------------------------------------- ASI03

def test_ASI03_lacuna_a_api_atende_sem_nenhuma_credencial(cliente, modelo):
    """Nenhum cabeçalho de autenticação, nenhum token: o POST /mensagens é
    atendido (src/api.py não declara dependência de segurança nesse endpoint)."""
    modelo([resposta(content="Olá! Qual é o seu RA?")])
    r = cliente.post("/mensagens", json={"mensagem": "Quero a segunda via, RA 20230198"})
    assert r.status_code == 200
    assert r.json()["resposta"]


def test_ASI03_mitigacao_o_conversa_id_tem_128_bits(cliente, modelo):
    """Era 8 hexadecimais (32 bits, enumerável); agora é uuid4 inteiro."""
    modelo([resposta(content="ok")])
    conversa_id = cliente.post("/mensagens", json={"mensagem": "oi"}).json()["conversa_id"]
    assert re.fullmatch(r"[0-9a-f]{32}", conversa_id)


def test_ASI03_lacuna_qualquer_cliente_continua_a_conversa_de_outro(cliente, modelo):
    """Um segundo cliente, sem nenhum vínculo com o primeiro, continua a
    conversa só por conhecer o `conversa_id` (a API não confere dono)."""
    modelo([resposta(content="primeiro"), resposta(content="segundo")])
    id_da_vitima = cliente.post("/mensagens", json={"mensagem": "oi, sou o aluno A"}).json()["conversa_id"]
    with TestClient(api.app) as outro_cliente:
        r = outro_cliente.post("/mensagens", json={"mensagem": "continuando", "conversa_id": id_da_vitima})
    assert r.status_code == 200
    assert r.json()["conversa_id"] == id_da_vitima


# ---------------------------------------------------------------- ASI08

def test_ASI08_lacuna_a_trava_global_serializa_todos_os_alunos(cliente, modelo):
    """Um turno de UM aluno em andamento (o `with _trava` de src/api.py)
    bloqueia o turno de QUALQUER outro: a trava é do processo, não da
    conversa. Com *retry* do provedor de até 90 s por tentativa, uma conversa
    lenta segura todas."""
    modelo([resposta(content="ok")])
    resultado = {}

    def outro_aluno():
        resultado["r"] = cliente.post("/mensagens", json={"mensagem": "oi, sou outro aluno"})

    api._trava.acquire()                  # simula o turno do aluno A, ainda em curso
    try:
        fio = threading.Thread(target=outro_aluno)
        fio.start()
        fio.join(timeout=0.5)
        assert fio.is_alive(), "o turno do aluno B deveria estar bloqueado pela trava global"
        assert "r" not in resultado
    finally:
        api._trava.release()
    fio.join(timeout=5)
    assert resultado["r"].status_code == 200


def test_ASI08_lacuna_conversas_acumulam_no_checkpoint_sem_limite_nem_expiracao(cliente, modelo):
    """A conversa saiu da memória do processo e foi para o arquivo de
    checkpoint, mas continua sem limite de quantidade nem prazo de expiração."""
    modelo([resposta(content="ok")])
    for _ in range(60):
        cliente.post("/mensagens", json={"mensagem": "oi, preciso de ajuda"})
    con = api.obter_sistema()._conexao
    assert con.execute("SELECT COUNT(DISTINCT thread_id) FROM checkpoints").fetchone()[0] == 60
