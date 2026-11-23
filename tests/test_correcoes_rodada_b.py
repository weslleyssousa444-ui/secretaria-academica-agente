# Os erros que a rodada B (16 e 17/11/2026, modelo real) mediu, reproduzidos com o
# modelo roteirizado fazendo O MESMO que o modelo real fez (as trajetórias estão em
# evals/resultados/2026-11-16-B-r1/execucoes.jsonl). Cada teste falhava antes da
# correção. Ver docs/mudancas.md §14.

from __future__ import annotations

import pytest

import dados
from conftest import chamada, resposta
from triagem import validacao
from triagem.sistema import Sistema

ART_8_3 = ("Art. 8º §3º O trancamento amparado por decisão judicial liminar é processado "
           "independentemente da existência de pendência financeira ou de anuência de terceiros, "
           "e a coordenação acadêmica dá cumprimento à ordem judicial no prazo nela fixado, ou, "
           "na omissão da decisão, no prazo do Art. 9º §1º.")


@pytest.fixture
def sistema(banco, tmp_path):
    s = Sistema(checkpoint=tmp_path / "cp.sqlite", memoria_dir=tmp_path / "mem")
    yield s
    s.fechar()


def contar(tabela: str) -> int:
    con = dados.conectar()
    n = con.execute(f"SELECT COUNT(*) FROM {tabela}").fetchone()[0]
    con.close()
    return n


# ---------------------------------------------------------------- rg03

def test_citar_artigo_mencionado_no_texto_devolvido_nao_e_sem_lastro():
    """rg03: o Art. 8º §3º devolvido remete ao Art. 9º §1º. Repetir a remissão é fiel
    ao texto; o validador reprovava como 'artigo que a ferramenta não devolveu'."""
    passos = [{"ferramenta": "consultar_regimento", "argumentos": {}, "erro": None,
               "resultado": {"trechos": [{"id": "Art. 8º §3º", "texto": ART_8_3}], "total": 1}}]
    texto = ("Não: a liminar é processada independentemente de pendência (Art. 8º §3º), no prazo "
             "fixado pela ordem ou, na omissão, no do Art. 9º §1º.\n[SUFICIENTE: sim]")
    assert validacao.validar_resposta(texto, passos, passos) == []


def test_artigo_que_nem_o_texto_devolvido_menciona_continua_reprovado():
    passos = [{"ferramenta": "consultar_regimento", "argumentos": {}, "erro": None,
               "resultado": {"trechos": [{"id": "Art. 8º §3º", "texto": ART_8_3}], "total": 1}}]
    problemas = validacao.validar_resposta("Veja o Art. 12.\n[SUFICIENTE: sim]", passos, passos)
    assert any("Art.12" in p or "art12" in p.lower() for p in problemas)


# ---------------------------------------------------------------- pe01

def test_resposta_de_encaminhamento_nao_precisa_da_marcacao_de_suficiencia():
    """pe01: o agente consultou o Regimento e ESCALOU; a resposta que dá o protocolo
    não é uma resposta de dúvida, e a falta de [SUFICIENTE] a reprovava duas vezes."""
    passos = [
        {"ferramenta": "consultar_regimento", "argumentos": {}, "erro": None,
         "resultado": {"trechos": [{"id": "Art. 4º", "texto": "Art. 4º A segunda via exige quitação."}], "total": 1}},
        {"ferramenta": "escalar_para_humano", "argumentos": {}, "erro": None,
         "resultado": {"protocolo": "CASO-3001", "prazo": "48h", "tipo_pedido": "segunda_via_historico"}}]
    texto = "Encaminhei à secretaria. Protocolo: CASO-3001. Prazo: 48h."
    assert validacao.validar_resposta(texto, passos, passos) == []


def test_duvida_sem_acao_continua_exigindo_a_marcacao():
    passos = [{"ferramenta": "consultar_regimento", "argumentos": {}, "erro": None,
               "resultado": {"trechos": [{"id": "Art. 4º", "texto": "Art. 4º ..."}], "total": 1}}]
    assert any("SUFICIENTE" in p for p in validacao.validar_resposta("Pelo Art. 4º, não.", passos, passos))


def test_pendencia_sem_alegar_pagamento_nao_e_rotulada_divergencia(sistema, modelo):
    """pe01: o modelo escreveu 'divergência' no motivo sem a aluna ter dito que pagou.
    Divergência é o aluno ALEGAR pagamento contra o sistema (docs/case.md §2.12)."""
    modelo([resposta([chamada("buscar_aluno", ra="20230198")]),
            resposta([chamada("consultar_financeiro", ra="20230198")]),
            resposta([chamada("escalar_para_humano", ra="20230198", tipo_pedido="segunda_via_historico",
                              motivo="divergência financeira não resolvida",
                              chave="20230198:segunda_via_historico:divergencia_financeira")]),
            resposta(content="Encaminhei à secretaria. Protocolo: CASO-3001. Prazo: 48h.")])
    r = sistema.conversar("t1", "Quero a segunda via do meu histórico. Meu RA é 20230198.")
    assert r["saida"]["decisao"] == "escalar_pendencia"


def test_com_alegacao_de_pagamento_continua_divergencia(sistema, modelo):
    modelo([resposta([chamada("buscar_aluno", ra="20232210")]),
            resposta([chamada("consultar_financeiro", ra="20232210")]),
            resposta([chamada("escalar_para_humano", ra="20232210", tipo_pedido="segunda_via_historico",
                              motivo="divergência financeira não resolvida",
                              chave="20232210:segunda_via_historico:divergencia_financeira")]),
            resposta(content="Encaminhei à secretaria. Protocolo: CASO-3001. Prazo: 48h.")])
    r = sistema.conversar("t1", "Já paguei tudo, quero a segunda via do meu histórico. RA 20232210.")
    assert r["saida"]["decisao"] == "escalar_divergencia"


# ---------------------------------------------------------------- pe02

def test_pendencia_que_o_agente_nao_escalou_e_escalada_pelo_codigo(sistema, modelo):
    """pe02: o modelo viu a mensalidade em aberto, pediu comprovante (que o aluno não
    alegou ter) e NÃO escalou. O código abre o caso de pendência, como já fazia com o
    trancamento, e o modelo responde com o protocolo."""
    modelo([resposta([chamada("buscar_aluno", ra="20233321")]),
            resposta([chamada("consultar_financeiro", ra="20233321")]),
            resposta(content="Há uma mensalidade em aberto de R$ 445,00. Já pagou? Envie o comprovante."),
            resposta(content="Há uma mensalidade em aberto; encaminhei à secretaria. Protocolo: CASO-3001. Prazo: 48h.")])
    docs_antes = contar("documentos_emitidos")   # o banco sintético já traz o DOC-1000
    r = sistema.conversar("t1", "Quero a segunda via do meu histórico. Meu RA é 20233321.")
    assert contar("casos_pendentes") == 1 and contar("documentos_emitidos") == docs_antes
    assert r["saida"]["decisao"] == "escalar_pendencia"
    assert r["saida"]["protocolo"] == "CASO-3001"


def test_o_codigo_nao_escala_quem_esta_em_dia(sistema, modelo):
    modelo([resposta([chamada("buscar_aluno", ra="20231045")]),
            resposta([chamada("consultar_financeiro", ra="20231045")]),
            resposta(content="Você está em dia. Quer que eu emita a segunda via?")])
    sistema.conversar("t1", "Quero a segunda via do meu histórico. Meu RA é 20231045.")
    assert contar("casos_pendentes") == 0


def test_o_codigo_nao_escala_quando_o_aluno_alega_pagamento(sistema, modelo):
    """Com alegação de pagamento o caso é de divergência, e o agente decide (pede o
    comprovante uma vez, e só então escala): o código não se adianta."""
    modelo([resposta([chamada("buscar_aluno", ra="20232210")]),
            resposta([chamada("consultar_financeiro", ra="20232210")]),
            resposta(content="O sistema mostra 3 mensalidades em aberto. Tem o comprovante?")])
    sistema.conversar("t1", "Já paguei tudo, quero a segunda via do meu histórico. RA 20232210.")
    assert contar("casos_pendentes") == 0


# ---------------------------------------------------------------- rg01

def test_duvida_de_regra_respondida_de_memoria_e_devolvida_para_consultar(sistema, modelo):
    """rg01: a pergunta tinha a palavra 'trancamento', o classificador a tratou como
    pedido, e o modelo respondeu de memória, sem consultar o Regimento (e errou o
    órgão: 'secretaria', quando o Art. 6º diz coordenação). Agora a dúvida é
    classificada como dúvida, e responder sem consultar é devolvido ao modelo."""
    modelo([resposta(content="Quem decide é uma pessoa da secretaria."),
            resposta([chamada("consultar_regimento", pergunta="quem decide o trancamento")]),
            resposta(content="Quem decide é a coordenação acadêmica (Art. 6º).\n[SUFICIENTE: sim]")])
    r = sistema.conversar("t1", "Quem decide o trancamento de matrícula: o sistema ou uma pessoa?")
    assert r["saida"]["decisao"] == "responder_regimento"
    assert {"tipo": "regimento", "referencia": "Art. 6º"} in r["saida"]["fonte"]
    assert "coordenação" in r["saida"]["resultado"]


def test_pedido_pessoal_com_pergunta_nao_vira_duvida_de_regra(sistema, modelo):
    """'Quais são minhas notas?' é pedido do aluno, não dúvida do Regimento: pedir o
    RA sem consultar o Regimento continua aceito."""
    modelo([resposta(content="Para consultar suas notas, me informe o seu RA.")])
    r = sistema.conversar("t1", "Quais são minhas notas neste semestre?")
    assert "RA" in r["saida"]["resultado"]


@pytest.mark.parametrize("texto,tipo", [
    ("Quem decide o trancamento de matrícula: o sistema ou uma pessoa?", "duvida"),
    ("Posso pedir prorrogação do trancamento por mais um semestre automaticamente?", "duvida"),
    ("Quero trancar minha matrícula esse semestre. Meu RA é 20231987.", "trancamento"),
    ("Quais são minhas notas neste semestre?", "outro"),
    ("Preciso da segunda via do histórico, RA 20231045.", "outro"),
])
def test_classificacao(texto, tipo):
    from triagem.nos import classificar_texto
    assert classificar_texto(texto) == tipo
