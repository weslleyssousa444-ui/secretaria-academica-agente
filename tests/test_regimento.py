# A recuperação do Regimento (docs/rag.md): busca textual, FTS5/BM25.
#
# Os números de docs/rag.md §4 saem destes testes: nenhum chama modelo, então
# podem ser reproduzidos a qualquer momento.
#
# Convenção de `tests/test_lacunas.py`: o teste chamado "lacuna" PASSA
# descrevendo o defeito; quando for corrigido, deve ser invertido.

from __future__ import annotations

import json

from conftest import RAIZ
from triagem.regimento import IndiceRegimento, consultar_regimento, termos_da_pergunta

CASOS = json.loads((RAIZ / "dados" / "casos_rag.json").read_text(encoding="utf-8"))


def achados(indice: IndiceRegimento, pergunta: str) -> list[str]:
    return [t["id"] for t in indice.buscar(pergunta)]


def test_recall_nas_perguntas_com_resposta_unica():
    """Dez das onze perguntas com resposta no corpus acham TODOS os artigos
    esperados nos 3 primeiros. A exceção, `c01`, é tratada abaixo."""
    indice = IndiceRegimento()
    com_resposta = [c for c in CASOS if c["artigos_esperados"] and c["id"] != "c01"]
    assert len(com_resposta) == 10
    for caso in com_resposta:
        esperados = caso["artigos_esperados"]
        assert all(a in achados(indice, caso["pergunta"]) for a in esperados), caso["id"]


def test_curadoria_exclui_o_artigo_revogado():
    """c01: o regimento tem duas redações do Art. 9º §1º (48 h vigente, 72 h
    revogada). O índice entrega só a vigente; quem decide o que vale é a
    curadoria do corpus, não a recuperação."""
    pergunta = next(c["pergunta"] for c in CASOS if c["id"] == "c01")
    ids = achados(IndiceRegimento(), pergunta)
    assert "Art. 9º §1º" in ids
    assert not any("revogada" in i for i in ids)


def test_sem_curadoria_o_defeito_aparece():
    """Reproduz o problema que a curadoria evita: com o revogado no índice, as
    duas versões voltam e nada na recuperação diz qual vale."""
    pergunta = next(c["pergunta"] for c in CASOS if c["id"] == "c01")
    ids = achados(IndiceRegimento(incluir_revogados=True), pergunta)
    assert "Art. 9º §1º" in ids and any("revogada" in i for i in ids)


def test_fora_de_dominio_nao_devolve_artigo():
    indice = IndiceRegimento()
    for caso in (c for c in CASOS if c["tipo"] == "fora_de_dominio"):
        assert achados(indice, caso["pergunta"]) == [], caso["id"]


def test_lacuna_busca_textual_nao_tem_piso_de_relevancia():
    """As duas perguntas SEM resposta no corpus (s01, s02) trazem artigos de
    ruído: basta um termo em comum para entrar no ranking. A recusa fica por
    conta do agente e do validador (docs/rag.md §4); este teste fixa o defeito."""
    indice = IndiceRegimento()
    for caso in (c for c in CASOS if c["tipo"] == "sem_resposta"):
        assert achados(indice, caso["pergunta"]) != [], caso["id"]


def test_termos_sem_acento_sem_stopword_e_sem_repeticao():
    assert termos_da_pergunta("Qual o prazo de resposta da Secretaria? Prazo!") == [
        "prazo", "resposta", "secretaria"]


def test_ferramenta_devolve_so_rotulo_e_texto_e_avisa_quando_nao_acha():
    achou = consultar_regimento("o que vale como comprovante de pagamento?")
    assert set(achou) == {"trechos", "total"} and set(achou["trechos"][0]) == {"id", "texto"}
    vazio = consultar_regimento("Quem venceu a copa do mundo de 2018?")
    assert vazio["total"] == 0 and "não responda como se tratasse" in vazio["aviso"]
