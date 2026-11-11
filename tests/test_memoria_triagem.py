# A memória entre execuções do sistema (docs/memoria.md): as três memórias, a
# política de escrita, a fronteira com o checkpoint, e as três causas de
# esquecimento que o case implementa (contradição, decaimento, remoção).

from __future__ import annotations

import json
from datetime import date

import pytest

import agente
from conftest import ModeloRoteirizado, chamada, resposta
from triagem.memoria import EpisodicaLexical, Memoria
from triagem.sistema import Sistema


class Espiao(ModeloRoteirizado):
    """Guarda as mensagens que o agente enviou ao modelo em cada chamada."""

    def __init__(self, roteiro):
        super().__init__(roteiro)
        self.recebidas: list[list[dict]] = []

    def _create(self, **kwargs):
        self.recebidas.append(kwargs["messages"])
        return super()._create(**kwargs)


@pytest.fixture
def memoria(tmp_path):
    return Memoria(tmp_path / "mem")


# ------------------------------------------------------------ episódica

def test_episodio_gravado_duas_vezes_e_um_so(memoria):
    a = memoria.episodica.gravar("20231045", "2026-11-01", "declaracao_matricula", "Pedido X emitido.")
    b = memoria.episodica.gravar("20231045", "2026-11-01", "declaracao_matricula", "Pedido X emitido.")
    assert a["ja_existia"] is False and b["ja_existia"] is True
    assert len(memoria.episodica.episodios) == 1


def test_recuperar_so_traz_episodio_do_proprio_ra(memoria):
    memoria.episodica.gravar("20231045", "2026-11-01", "t", "Declaração de matrícula emitida.")
    memoria.episodica.gravar("20230198", "2026-11-02", "t", "Declaração de matrícula emitida.")
    achados = memoria.episodica.recuperar("declaração de matrícula", "20231045")
    assert [e["ra"] for e in achados] == ["20231045"]


def test_recuperar_ordena_por_similaridade_e_desempata_pelo_mais_recente(memoria):
    memoria.episodica.gravar("20231045", "2026-01-01", "a", "Trancamento encaminhado à coordenação.")
    memoria.episodica.gravar("20231045", "2026-03-01", "b", "Segunda via de histórico emitida.")
    primeiro = memoria.episodica.recuperar("segunda via do histórico", "20231045")[0]
    assert primeiro["tipo_pedido"] == "b"


# ------------------------------------------------------------ causas de esquecimento

def test_contradicao_o_fato_novo_vale_e_o_antigo_fica_em_substituiu(memoria):
    memoria.semantica.gravar("20230198", "situacao_financeira", "2 mensalidade(s) em aberto", "2026-10-01")
    novo = memoria.semantica.gravar("20230198", "situacao_financeira", "em dia", "2026-11-05")
    assert novo["substituiu"] == "2 mensalidade(s) em aberto"
    assert memoria.semantica.ler("20230198", "situacao_financeira")["valor"] == "em dia"


def test_decaimento_remove_o_episodio_velho_e_guarda_o_recente(memoria):
    memoria.episodica.gravar("20231045", "2026-01-01", "a", "Antigo.")
    memoria.episodica.gravar("20231045", "2026-10-20", "b", "Recente.")
    assert memoria.episodica.aplicar_decaimento(date(2026, 11, 11), dias=180) == 1
    assert [e["resumo"] for e in memoria.episodica.episodios] == ["Recente."]


# ------------------------------------------------------------ leitura: identidade e orçamento

def test_sem_ra_autenticado_nao_ha_memoria_de_aluno(memoria):
    memoria.semantica.gravar("20231045", "situacao_financeira", "em dia", "2026-11-01")
    memoria.episodica.gravar("20231045", "2026-11-01", "t", "Declaração emitida.")
    assert memoria.ler_bloco(None, "declaração", teto_tokens=400)["texto"] == ""


def test_um_ra_autenticado_nao_le_a_memoria_de_outro(memoria):
    memoria.semantica.gravar("20231045", "situacao_financeira", "em dia", "2026-11-01")
    memoria.episodica.gravar("20231045", "2026-11-01", "t", "Declaração emitida.")
    assert memoria.ler_bloco("20230198", "declaração")["texto"] == ""


def test_procedural_so_entra_depois_de_aprovada(memoria):
    memoria.procedural.gravar("Sempre confirmar o RA duas vezes.")
    assert "confirmar o RA" not in memoria.ler_bloco("20231045", "x")["texto"]
    memoria.procedural.aprovar("Sempre confirmar o RA duas vezes.")
    assert "confirmar o RA" in memoria.ler_bloco("20231045", "x")["texto"]


def test_estourou_o_orcamento_a_episodica_sai_primeiro(memoria):
    memoria.semantica.gravar("20231045", "situacao_financeira", "em dia", "2026-11-01")
    for i in range(3):
        memoria.episodica.gravar("20231045", f"2026-11-0{i + 1}", "t",
                                 f"Declaração de matrícula emitida no dia {i}. " * 8)
    cheio = memoria.ler_bloco("20231045", "declaração de matrícula", teto_tokens=400)
    curto = memoria.ler_bloco("20231045", "declaração de matrícula", teto_tokens=40)
    assert cheio["episodios_usados"] > 0
    assert curto["episodios_usados"] == 0 and "situação financeira" in curto["texto"]


# ------------------------------------------------------------ escrita: política e identidade

def test_escrita_so_para_o_ra_autenticado(memoria):
    passos = [{"ferramenta": "consultar_financeiro", "erro": None,
               "resultado": {"ra": "20230198", "mensalidades_em_aberto": 2, "valor_em_aberto": 890.0}}]
    assert memoria.escrever_depois_do_turno("20231045", passos) == {"episodio": None, "fato": None}
    assert memoria.semantica.fatos == {}
    gravados = memoria.escrever_depois_do_turno("20230198", passos, hoje=date(2026, 11, 11))
    assert "2 mensalidade(s)" in gravados["fato"]["valor"]


def test_o_que_o_aluno_afirma_nao_vira_memoria(memoria):
    """A política é por regra, sobre o retorno de ferramenta: 'já paguei' dito
    no chat não grava fato nenhum (envenenamento de memória, ASI06)."""
    passos = [{"ferramenta": "buscar_aluno", "erro": None, "resultado": {"ra": "20230198"}}]
    assert memoria.escrever_depois_do_turno("20230198", passos) == {"episodio": None, "fato": None}


# ------------------------------------------------------------ no sistema inteiro

def test_a_memoria_de_um_atendimento_chega_ao_proximo(banco, tmp_path, monkeypatch):
    s = Sistema(checkpoint=tmp_path / "cp.sqlite", memoria_dir=tmp_path / "mem")
    try:
        m1 = Espiao([resposta([chamada("buscar_aluno", ra="20231045")]),
                     resposta([chamada("emitir_documento", ra="20231045",
                                       tipo_documento="declaracao_matricula")]),
                     resposta(content="Emitida. Protocolo: DOC-1002.")])
        monkeypatch.setattr(agente, "client", m1)
        s.conversar("t1", "Declaração, RA 20231045.", ra_autenticado="20231045")

        m2 = Espiao([resposta(content="Posso ajudar com algo mais?")])
        monkeypatch.setattr(agente, "client", m2)
        s.conversar("t2", "Oi, preciso de outra declaração de matrícula.", ra_autenticado="20231045")
        com_memoria = json.dumps(m2.recebidas[0], ensure_ascii=False)
        assert "Atendimentos anteriores deste aluno" in com_memoria and "DOC-1002" in com_memoria

        m3 = Espiao([resposta(content="Posso ajudar com algo mais?")])
        monkeypatch.setattr(agente, "client", m3)
        s.conversar("t3", "Oi, preciso de outra declaração de matrícula.", ra_autenticado=None)
        assert "Atendimentos anteriores" not in json.dumps(m3.recebidas[0], ensure_ascii=False)
    finally:
        s.fechar()


# ------------------------------------------------------------ remoção, com verificação de cobertura

def test_remocao_do_titular_sai_de_todas_as_estruturas(banco, tmp_path, monkeypatch):
    s = Sistema(checkpoint=tmp_path / "cp.sqlite", memoria_dir=tmp_path / "mem")
    registros = tmp_path / "registros"
    registros.mkdir()
    try:
        monkeypatch.setattr(agente, "client", Espiao([
            resposta([chamada("buscar_aluno", ra="20231045")]),
            resposta([chamada("consultar_financeiro", ra="20231045")]),
            resposta([chamada("emitir_documento", ra="20231045", tipo_documento="declaracao_matricula")]),
            resposta(content="Emitida. Protocolo: DOC-1002.")]))
        s.conversar("t1", "Declaração, RA 20231045.", ra_autenticado="20231045")
        (registros / "api-ab12.json").write_text('{"ra": "20231045"}', encoding="utf-8")
        s.memoria.procedural.gravar("Caso do RA 20231045: conferir duas vezes.")

        antes = {fonte for fonte, _ in s.memoria.varrer("20231045", s.caminho_checkpoint, registros)}
        assert antes == {"episodica", "semantica", "procedural", "checkpoint", "registro"}

        relatorio = s.memoria.remover_titular("20231045", s.caminho_checkpoint, registros)
        assert relatorio["episodios"] == 1 and relatorio["fatos"] == 1
        assert relatorio["threads_de_checkpoint"] == 1 and relatorio["registros"] == 1
        # a regra procedural NÃO é editada sozinha: volta para revisão humana
        assert relatorio["regras_suspeitas"] == ["Caso do RA 20231045: conferir duas vezes."]
        restante = {fonte for fonte, _ in s.memoria.varrer("20231045", s.caminho_checkpoint, registros)}
        assert restante == {"procedural"}
    finally:
        s.fechar()
