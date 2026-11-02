# Testes da própria suíte de avaliação (Exercício 11): um avaliador que não
# foi testado contra uma falha conhecida não prova nada quando diz "passou".
# Offline, sem chave, sem rede. Cada teste fabrica o registro de uma execução
# defeituosa e confere que o avaliador do nível certo a acusa.

from __future__ import annotations

import copy
import json
import sys

import pytest

from conftest import RAIZ, chamada, resposta

sys.path.insert(0, str(RAIZ / "src" / "suite"))

import avaliadores  # noqa: E402
import executor  # noqa: E402

GOLD = json.loads((RAIZ / "dados" / "golden_v1.json").read_text(encoding="utf-8"))
CASOS = {c["id"]: c for c in GOLD["casos"]}


def registro(caso_id, passos=(), respostas=("ok",), docs=(), casos=(), termino="respondeu"):
    vazio = {"documentos_emitidos": [{"protocolo": "DOC-1000", "ra": "20234456",
                                      "tipo_documento": "declaracao_matricula", "data_emissao": "x"}]
             if caso_id == "em04" else [], "casos_pendentes": []}
    depois = copy.deepcopy(vazio)
    depois["documentos_emitidos"] += list(docs)
    depois["casos_pendentes"] += list(casos)
    return {"versao": "A", "run": 1, "caso": caso_id, "termino": termino, "antes": vazio,
            "depois": depois, "passos": [dict(p) for p in passos], "respostas": list(respostas)}


def passo(ferramenta, resultado=None, erro=None, **argumentos):
    return {"ferramenta": ferramenta, "argumentos": argumentos, "resultado": resultado, "erro": erro}


def doc(protocolo, ra, tipo):
    return {"protocolo": protocolo, "ra": ra, "tipo_documento": tipo, "data_emissao": "x"}


def linha_caso(protocolo, ra, tipo, motivo):
    return {"protocolo": protocolo, "ra": ra, "tipo_pedido": tipo, "motivo": motivo,
            "chave": protocolo, "status": "aberto"}


# ------------------------------------------------------------ o dataset

def test_dataset_cumpre_as_exigencias_de_composicao():
    casos = GOLD["casos"]
    assert len(casos) >= 20
    assert len({c["id"] for c in casos}) == len(casos)
    por_classe = {}
    for c in casos:
        por_classe.setdefault(c["classe"], []).append(c)
        assert c["origem"] in {"producao", "desenvolvimento", "sintetico"}
        assert c["por_que_existe"].strip() and c["mensagens"]
    assert len(por_classe) >= 3 and all(len(v) > 1 for v in por_classe.values())
    assert "recusa" in por_classe
    assert set(GOLD["classes_criticas"]) <= set(por_classe)


def test_todo_caso_sintetico_declara_quem_revisou():
    sinteticos = [c for c in GOLD["casos"] if c["origem"] == "sintetico"]
    assert sinteticos and all(c["revisao"]["por"] for c in sinteticos)


def test_rotulos_do_dataset_conferem_com_os_dados_semeados(banco):
    """O esperado de cada caso é regra de negócio sobre dados/dados.py: o RA do
    caso existe (ou é de propósito inexistente) e a pendência bate."""
    ras = {a[0]: a for a in banco.ALUNOS}
    com_pendencia = {f[0] for f in banco.FINANCEIRO}
    for c in GOLD["casos"]:
        ra = c["esperado"]["ra_alvo"]
        if ra is None or "escalar_ra_nao_encontrado" in c["esperado"]["decisoes"]:
            continue
        assert ra in ras, c["id"]
        if "escalar_pendencia" in c["esperado"]["decisoes"] and c["classe"] == "pendencia":
            assert ra in com_pendencia, c["id"]
        if "emitir_segunda_via" in c["esperado"]["decisoes"] and c["classe"] == "emissao":
            assert ra not in com_pendencia, c["id"]


# ------------------------------------------------------------ resultado

def test_resultado_acusa_o_agente_que_relata_o_que_nao_fez():
    """Disse 'protocolo DOC-1002' e o banco não tem linha nova: só o nível de
    resultado enxerga isso."""
    r = registro("em01", passos=[passo("buscar_aluno", {"ra": "20231045"}, ra="20231045")],
                 respostas=["Sua declaração foi emitida. Protocolo DOC-1002."])
    a = avaliadores.avaliar_resultado(CASOS["em01"], r)
    assert not a["ok"] and not a["checagens"]["n_documentos"] and not a["checagens"]["protocolos_citados_existem"]


def test_resultado_acusa_documento_emitido_duas_vezes():
    r = registro("em01", docs=[doc("DOC-1002", "20231045", "declaracao_matricula"),
                               doc("DOC-1003", "20231045", "declaracao_matricula")],
                 respostas=["Protocolo DOC-1002"])
    a = avaliadores.avaliar_resultado(CASOS["em01"], r)
    assert not a["checagens"]["sem_duplicata"] and not a["checagens"]["n_documentos"]


def test_resultado_acusa_documento_para_outro_ra():
    r = registro("em01", docs=[doc("DOC-1002", "20229012", "declaracao_matricula")], respostas=["DOC-1002"])
    assert not avaliadores.avaliar_resultado(CASOS["em01"], r)["checagens"]["ra_alvo"]


def test_resultado_idempotencia_aceita_o_protocolo_que_ja_existia():
    r = registro("em04", passos=[passo("emitir_documento", {"protocolo": "DOC-1000", "ja_existia": True},
                                      ra="20234456", tipo_documento="declaracao_matricula")],
                 respostas=["Sua declaração já existe: DOC-1000."])
    assert avaliadores.avaliar_resultado(CASOS["em04"], r)["ok"]


def test_resultado_trancamento_correto():
    r = registro("tr01", casos=[linha_caso("CASO-3001", "20221100", "trancamento_matricula", "x")],
                 respostas=["Encaminhado. CASO-3001, 48h."])
    assert avaliadores.avaliar_resultado(CASOS["tr01"], r)["ok"]


# ------------------------------------------------------------ decisão

def test_decisao_sem_ferramenta_de_escrita_e_sem_acao():
    r = registro("bo01", respostas=["Qual é o seu RA?"])
    a = avaliadores.avaliar_decisao(CASOS["bo01"], r)
    assert a["obtida"] == "sem_acao" and a["ok"]


def test_decisao_emitir_onde_devia_recusar_e_falha_e_marca_escrita_indevida():
    r = registro("re05", passos=[passo("emitir_documento", {"protocolo": "DOC-1002", "tipo_documento": "declaracao_matricula"},
                                      ra="20221100", tipo_documento="declaracao_matricula")],
                 docs=[doc("DOC-1002", "20221100", "declaracao_matricula")], respostas=["DOC-1002"])
    a = avaliadores.avaliar(CASOS["re05"], r)
    assert not a["aprovado"] and a["escrita_indevida"]


# ------------------------------------------------------------ trajetória

def test_trajetoria_ordem_escrita_antes_da_leitura_e_acusada():
    r = registro("em01", passos=[passo("emitir_documento", {"protocolo": "DOC-1002"}, ra="20231045",
                                      tipo_documento="declaracao_matricula"),
                                 passo("buscar_aluno", {"ra": "20231045"}, ra="20231045")])
    t = avaliadores.avaliar_trajetoria(CASOS["em01"], r)
    assert not t["ordem_ok"] and not t["ok"]


def test_trajetoria_cobertura_incompleta_e_superflua_sao_medidas_separadas():
    r = registro("em02", passos=[passo("buscar_aluno", {"ra": "20231045"}, ra="20231045"),
                                 passo("buscar_aluno", {"ra": "20231045"}, ra="20231045")])
    t = avaliadores.avaliar_trajetoria(CASOS["em02"], r)
    assert t["cobertura"] == 0.0 and t["superfluas"] == 1 and t["ordem_ok"]


def test_trajetoria_ferramenta_quando_nao_devia_chamar_nenhuma():
    r = registro("bo01", passos=[passo("buscar_aluno", {"ra": "?"}, ra="?")])
    assert avaliadores.avaliar_trajetoria(CASOS["bo01"], r)["superfluas"] == 1


# ------------------------------------------------------------ texto

@pytest.mark.parametrize("texto,campo", [
    ("Encaminhado, CASO-3001, prazo de 72h.", "so_o_prazo_de_48h"),
    ("Encaminhado, CASO-3001.", "informa_48h_ao_escalar"),
    ("Encaminhado em 48h. Você receberá um e-mail.", "sem_canal_inventado"),
    ("Encaminhado em 48h.", "informa_o_protocolo_ao_escalar_ou_emitir"),
])
def test_texto_acusa_cada_violacao(texto, campo):
    r = registro("tr01", passos=[passo("escalar_para_humano", {"protocolo": "CASO-3001", "prazo": "48h"},
                                      ra="20221100")], respostas=[texto])
    assert avaliadores.avaliar_texto(CASOS["tr01"], r)["checagens"][campo] is False


def test_texto_acusa_resposta_vazia_que_a_decisao_sem_acao_deixava_passar():
    """Achado de B2/re06: terminou 'respondeu' sem nenhum texto ao aluno. A decisão
    `sem_acao` era aceita e nenhum nível acusava; o texto passou a acusar."""
    r = registro("re06", passos=[passo("buscar_aluno", {"ra": "20233120"}, ra="20233120")], respostas=[])
    assert avaliadores.avaliar_decisao(CASOS["re06"], r)["ok"]
    assert avaliadores.avaliar_texto(CASOS["re06"], r)["checagens"]["resposta_nao_vazia"] is False


# ------------------------------------------------------------ executor

def test_executor_roda_cada_caso_em_banco_novo_e_grava_o_antes_e_o_depois(banco, modelo):
    modelo([resposta([chamada("buscar_aluno", ra="20231045")]),
            resposta([chamada("emitir_documento", ra="20231045", tipo_documento="declaracao_matricula")]),
            resposta(content="Declaração emitida. Protocolo DOC-1002.")])
    primeiro = executor.executar_caso(CASOS["em01"], "A", 1)
    assert [p["ferramenta"] for p in primeiro["passos"]] == ["buscar_aluno", "emitir_documento"]
    assert len(primeiro["depois"]["documentos_emitidos"]) == len(primeiro["antes"]["documentos_emitidos"]) + 1

    # segundo caso: o banco do primeiro não vaza (mesmo protocolo, mesma contagem inicial)
    modelo([resposta([chamada("buscar_aluno", ra="20231045")]),
            resposta([chamada("emitir_documento", ra="20231045", tipo_documento="declaracao_matricula")]),
            resposta(content="Protocolo DOC-1002.")])
    segundo = executor.executar_caso(CASOS["em01"], "A", 2)
    assert segundo["antes"] == primeiro["antes"]
    assert segundo["depois"]["documentos_emitidos"][-1]["protocolo"] == "DOC-1002"
    assert avaliadores.avaliar(CASOS["em01"], segundo)["aprovado"]


def test_cota_diaria_nao_e_retentada(monkeypatch):
    import httpx
    import openai
    erro = openai.RateLimitError(
        "Error code: 429 - Rate limit reached for model on tokens per day (TPD)", response=httpx.Response(429, request=httpx.Request("POST", "https://x")),
        body={"message": "Rate limit reached ... tokens per day (TPD)"})

    class Cliente:
        chat = type("C", (), {"completions": type("P", (), {"create": staticmethod(lambda **k: (_ for _ in ()).throw(erro))})})

    monkeypatch.setattr(executor.agente, "client", Cliente)
    with pytest.raises(executor.CotaDiaria):
        executor.chamar_com_retry_da_suite(model="x", messages=[])
