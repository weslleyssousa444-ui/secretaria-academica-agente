# Funções de 13/11/2026: consulta acadêmica, segunda via de boleto e o documento
# de verdade (src/triagem/servicos.py, src/triagem/documentos.py). Offline: o
# "modelo" é roteirizado e o banco é o sintético de dados.py.
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

import api
import dados
from agente import ErroRecuperavel
from conftest import chamada, contar, resposta
from triagem import documentos, servicos, validacao
from triagem.saida import decisao_da_trajetoria
from triagem.sistema import Sistema

SEM_DEBITO = "20231045"    # Weslley Sousa, ADS, ativo, em dia
UMA_ABERTA = "20233321"    # Diego Ramos, 1 mensalidade (2026-10, R$ 445,00)
DUAS_ABERTAS = "20230198"  # Marina Alves, 2 mensalidades (2026-09 e 2026-10)


@pytest.fixture
def sistema(banco, tmp_path):
    s = Sistema(checkpoint=tmp_path / "cp.sqlite", memoria_dir=tmp_path / "mem")
    yield s
    s.fechar()


# ---------------------------------------------------------------- a base fictícia

def test_mensalidades_batem_com_o_financeiro(banco):
    """A tabela nova não contradiz a antiga: mesma quantidade e mesmo total."""
    conexao = dados.conectar()
    for ra, quantidade, total in dados.FINANCEIRO:
        linhas = conexao.execute("SELECT valor FROM mensalidades WHERE ra = ? AND status = 'aberta'",
                                 (ra,)).fetchall()
        assert len(linhas) == quantidade and round(sum(r["valor"] for r in linhas), 2) == total
    conexao.close()


def test_historico_e_deterministico_e_coerente_com_a_matricula(banco):
    assert dados.historico_sintetico() == dados.historico_sintetico()
    h = servicos.consultar_historico(SEM_DEBITO)
    assert h["nome"] == "Weslley Sousa" and h["curso"] == "ADS" and h["cursando"] == 2
    trancado = servicos.consultar_historico("20221100")
    assert trancado["cursando"] == 0  # trancado não cursa o semestre atual
    assert all(d["nota"] is None for d in h["disciplinas"] if d["situacao"] == "cursando")
    assert all((d["nota"] >= 6) == (d["situacao"] == "aprovado")
               for d in h["disciplinas"] if d["nota"] is not None)


def test_coeficiente_e_ponderado_pela_carga():
    assert servicos.coeficiente([{"nota": 10.0, "carga_horaria": 60},
                                 {"nota": 5.0, "carga_horaria": 20},
                                 {"nota": None, "carga_horaria": 80}]) == 8.75
    assert servicos.coeficiente([{"nota": None, "carga_horaria": 80}]) is None


# ---------------------------------------------------------------- as regras do boleto (Art. 11), em código

def test_boleto_de_uma_mensalidade_e_emitido_e_e_idempotente(banco):
    b = servicos.emitir_boleto(UMA_ABERTA)
    assert b["protocolo"] == "BOL-5001" and b["competencia"] == "2026-10" and b["valor"] == 445.0
    assert b["linha_digitavel"].startswith("00090.") and b["ja_existia"] is False
    de_novo = servicos.emitir_boleto(UMA_ABERTA, "2026-10")
    assert de_novo["protocolo"] == "BOL-5001" and de_novo["ja_existia"] is True
    assert contar("boletos_emitidos") == 1


def test_varias_em_aberto_sem_competencia_devolve_a_lista(banco):
    with pytest.raises(ErroRecuperavel) as erro:
        servicos.emitir_boleto(DUAS_ABERTAS)
    competencias = [m["competencia"] for m in erro.value.payload["competencias_em_aberto"]]
    assert competencias == ["2026-09", "2026-10"] and contar("boletos_emitidos") == 0


@pytest.mark.parametrize("ra,competencia", [(SEM_DEBITO, ""), (UMA_ABERTA, "2026-08"),
                                            (DUAS_ABERTAS, "2025-01")])
def test_nao_ha_boleto_de_mensalidade_paga_ou_inexistente(banco, ra, competencia):
    with pytest.raises(ErroRecuperavel):
        servicos.emitir_boleto(ra, competencia)
    assert contar("boletos_emitidos") == 0


def test_ra_inexistente_nas_ferramentas_novas(banco):
    for funcao in (servicos.consultar_historico, servicos.emitir_boleto):
        with pytest.raises(ErroRecuperavel) as erro:
            funcao("20240000")
        assert "RA não encontrado" in erro.value.payload["erro"]


# ---------------------------------------------------------------- no grafo: decisão, contrato, validador

def test_boleto_pelo_agente_sai_no_contrato(sistema, modelo):
    modelo([resposta([chamada("emitir_boleto", ra=UMA_ABERTA)]),
            resposta(content="Pronto! Segunda via emitida. Protocolo: BOL-5001.")])
    r = sistema.conversar("t1", f"Quero a segunda via do boleto. RA {UMA_ABERTA}")
    assert r["saida"]["decisao"] == "emitir_boleto" and r["saida"]["protocolo"] == "BOL-5001"
    assert {"tipo": "ferramenta", "referencia": "emitir_boleto:BOL-5001"} in r["saida"]["fonte"]
    assert r["saida"]["suficiencia"]["suficiente"] is True


def test_consulta_de_notas_sai_como_informar_situacao(sistema, modelo):
    modelo([resposta([chamada("consultar_historico", ra=SEM_DEBITO)]),
            resposta(content="Você tem 4 disciplinas concluídas; ADS101 (80 horas) com nota 8,4.")])
    r = sistema.conversar("t1", f"Quais são minhas notas? RA {SEM_DEBITO}")
    assert r["saida"]["decisao"] == "informar_situacao_academica"
    assert r["saida"]["suficiencia"]["suficiente"] is True
    # "80 horas" é a carga que a ferramenta devolveu: o validador não a trata como prazo inventado
    assert "Você tem 4 disciplinas" in r["saida"]["resultado"]


def test_protocolo_de_boleto_inventado_e_barrado():
    passos = [{"ferramenta": "buscar_aluno", "erro": None, "argumentos": {}, "resultado": {"ra": "1"}}]
    assert any("BOL-9999" in p for p in validacao.validar_resposta("Seu boleto BOL-9999 foi emitido.", passos))


def test_carga_horaria_devolvida_nao_e_prazo_inventado():
    passos = [{"ferramenta": "consultar_historico", "erro": None, "argumentos": {},
               "resultado": {"disciplinas": [{"carga_horaria": 80}]}}]
    assert validacao.validar_resposta("A disciplina tem 80 horas.", passos) == []
    assert validacao.validar_resposta("Responderemos em 72 horas.", passos)  # prazo de verdade continua barrado


def test_boleto_e_escrita_e_conta_no_limite_por_volta(sistema, modelo):
    """ASI02: duas escritas na MESMA volta, a segunda não executa."""
    modelo([resposta([chamada("emitir_boleto", ra=DUAS_ABERTAS, competencia="2026-09"),
                      chamada("emitir_boleto", ra=DUAS_ABERTAS, competencia="2026-10")]),
            resposta(content="Emiti o boleto BOL-5001.")])
    sistema.conversar("t1", f"Quero os dois boletos. RA {DUAS_ABERTAS}")
    assert contar("boletos_emitidos") == 1


def test_decisao_da_trajetoria_novas():
    ok = lambda nome, res: {"ferramenta": nome, "erro": None, "argumentos": {}, "resultado": res}
    assert decisao_da_trajetoria([ok("consultar_historico", {"ra": "1"})]) == "informar_situacao_academica"
    assert decisao_da_trajetoria([ok("consultar_historico", {"ra": "1"}),
                                  ok("emitir_boleto", {"protocolo": "BOL-5001"})]) == "emitir_boleto"


# ---------------------------------------------------------------- o documento de verdade

@pytest.fixture
def cliente(banco, tmp_path, monkeypatch):
    monkeypatch.setattr(api, "PASTA_LOGS", None)
    monkeypatch.setenv("TRIAGEM_CHECKPOINT", str(tmp_path / "cp.sqlite"))
    monkeypatch.setenv("TRIAGEM_MEMORIA_DIR", str(tmp_path / "mem"))
    monkeypatch.delenv("TRIAGEM_CONFIA_NO_PORTAL", raising=False)
    api._sistema = None
    with TestClient(api.app) as c:
        yield c
    api._sistema = None


def test_declaracao_emitida_tem_link_e_a_pagina_abre(cliente, modelo):
    modelo([resposta([chamada("buscar_aluno", ra=SEM_DEBITO)]),
            resposta([chamada("emitir_documento", ra=SEM_DEBITO, tipo_documento="declaracao_matricula")]),
            resposta(content="Emitida. Protocolo: DOC-1002.")])
    corpo = cliente.post("/mensagens", json={"mensagem": f"Declaração, RA {SEM_DEBITO}"}).json()
    [doc] = corpo["documentos"]
    assert doc["protocolo"] == "DOC-1002" and doc["titulo"] == "Declaração de matrícula"
    pagina = cliente.get(doc["url"])
    assert pagina.status_code == 200 and "text/html" in pagina.headers["content-type"]
    assert "Weslley Sousa" in pagina.text and "DOC-1002" in pagina.text and "fictício" in pagina.text.lower()


def test_sem_o_codigo_o_documento_nao_abre(cliente, modelo):
    modelo([resposta([chamada("emitir_boleto", ra=UMA_ABERTA)]), resposta(content="Boleto BOL-5001.")])
    corpo = cliente.post("/mensagens", json={"mensagem": f"boleto, RA {UMA_ABERTA}"}).json()
    url = corpo["documentos"][0]["url"]
    assert cliente.get(url).status_code == 200
    assert "SEM VALOR DE PAGAMENTO" in cliente.get(url).text
    sem_codigo = cliente.get("/documentos/BOL-5001")
    errado = cliente.get("/documentos/BOL-5001?c=chute")
    inexistente = cliente.get("/documentos/BOL-9999?c=chute")
    assert sem_codigo.status_code == errado.status_code == inexistente.status_code == 404
    assert errado.json() == inexistente.json()  # sem oráculo: a mesma resposta


def test_historico_impresso_traz_as_disciplinas(banco):
    conexao = dados.conectar()
    conexao.execute("INSERT INTO documentos_emitidos VALUES ('DOC-1002', ?, 'segunda_via_historico', '2026-11-13')",
                    (SEM_DEBITO,))
    conexao.commit(); conexao.close()
    codigo = documentos.codigo_de("DOC-1002")
    pagina = documentos.pagina_do_documento("DOC-1002", codigo)
    assert "Algoritmos e Lógica de Programação" in pagina and "coeficiente de rendimento" in pagina
    assert codigo == documentos.codigo_de("DOC-1002")  # o código é estável


def test_nome_com_html_e_escapado(banco):
    conexao = dados.conectar()
    conexao.execute("UPDATE alunos SET nome = '<script>x</script>' WHERE ra = ?", (SEM_DEBITO,))
    conexao.execute("INSERT INTO documentos_emitidos VALUES ('DOC-1002', ?, 'declaracao_matricula', '2026-11-13')",
                    (SEM_DEBITO,))
    conexao.commit(); conexao.close()
    pagina = documentos.pagina_do_documento("DOC-1002", documentos.codigo_de("DOC-1002"))
    assert "<script>x</script>" not in pagina and "&lt;script&gt;" in pagina
