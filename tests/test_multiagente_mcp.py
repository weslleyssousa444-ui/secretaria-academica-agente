# O servidor MCP (src/mcp_secretaria.py) e o segundo agente, o assistente da
# coordenação (src/assistente_coordenacao.py). Offline: o servidor roda em
# memória (sessão MCP real, sem subprocesso) e o modelo é roteirizado. Cada
# controle é provado com um roteiro que faz o que um modelo ruim faria.

from __future__ import annotations

import asyncio
import json

import pytest
from mcp.shared.memory import create_connected_server_and_client_session

import agente
import assistente_coordenacao as ac
import mcp_secretaria
from conftest import ModeloRoteirizado, chamada, resposta
from triagem import humano

RA_CASO = "20229012"      # Bruno Castro, ativo, em dia (dados sintéticos)
RA_OUTRO = "20230198"     # Marina Alves, com débito


def rodar(coro):
    return asyncio.run(coro)


async def _com_sessao(func):
    async with create_connected_server_and_client_session(mcp_secretaria.servidor._mcp_server) as sessao:
        return await func(sessao)


@pytest.fixture
def caso(banco):
    r = agente.escalar_para_humano(RA_CASO, "trancamento", "aluno pediu trancamento do semestre",
                                   f"{RA_CASO}:trancamento:teste")
    humano.registrar_espera("thread-teste", r["protocolo"], RA_CASO)
    return r["protocolo"]


def parecer_json(protocolo, **mudar):
    p = {"protocolo": protocolo, "ra": RA_CASO,
         "resumo": "Pedido de trancamento do aluno Bruno Castro, de Direito, encaminhado pelo atendimento.",
         "fatos": [{"texto": "Bruno Castro, Direito, matrícula ativa", "fonte": "buscar_aluno"},
                   {"texto": "nenhuma mensalidade em aberto", "fonte": "consultar_financeiro"}],
         "artigos": ["Art. 6º"], "pontos_de_atencao": ["motivo registrado é genérico"]}
    p.update(mudar)
    return json.dumps(p, ensure_ascii=False)


def coleta(protocolo):
    return [resposta(tool_calls=[chamada("buscar_aluno", ra=RA_CASO),
                                 chamada("consultar_financeiro", ra=RA_CASO),
                                 chamada("consultar_regimento", pergunta="trancamento de matrícula")])]


# ------------------------------------------------------------- o servidor MCP

def test_mcp_publica_so_as_ferramentas_de_leitura(banco):
    nomes = rodar(_com_sessao(lambda s: s.list_tools()))
    assert sorted(t.name for t in nomes.tools) == sorted(mcp_secretaria.FERRAMENTAS_PUBLICADAS)


def test_mcp_nao_publica_escrita(banco):
    nomes = {t.name for t in rodar(_com_sessao(lambda s: s.list_tools())).tools}
    escrita = agente.ESCRITA | {"emitir_boleto", "decidir", "registrar_decisao"}
    assert not nomes & escrita


def test_mcp_devolve_os_mesmos_dados_que_a_funcao(banco):
    async def f(s):
        return ac._conteudo(await s.call_tool("buscar_aluno", {"ra": RA_CASO}))
    assert rodar(_com_sessao(f)) == agente.buscar_aluno(RA_CASO)


def test_mcp_ra_inexistente_volta_como_conteudo(banco):
    async def f(s):
        return await s.call_tool("buscar_aluno", {"ra": "20240000"})
    r = rodar(_com_sessao(f))
    assert not r.isError and "erro" in ac._conteudo(r)


def test_mcp_lista_o_caso_aguardando(caso):
    async def f(s):
        return ac._conteudo(await s.call_tool("casos_aguardando_coordenacao", {}))
    r = rodar(_com_sessao(f))
    assert r["total"] == 1 and r["casos"][0]["protocolo"] == caso


# ------------------------------------------------- o assistente da coordenação

def preparar(protocolo, roteiro):
    modelo = ModeloRoteirizado(roteiro)
    r = rodar(_com_sessao(lambda s: ac.preparar_parecer(protocolo, s, cliente=modelo)))
    return r, modelo


def test_parecer_valido_sai_do_modelo(caso):
    r, _ = preparar(caso, coleta(caso) + [resposta(content=parecer_json(caso))])
    assert r["origem"] == "modelo"
    assert r["parecer"]["ra"] == RA_CASO and r["parecer"]["artigos"] == ["Art. 6º"]
    assert r["decisao"].startswith("cabe à coordenação")


def test_assistente_nao_decide_o_caso(caso):
    preparar(caso, coleta(caso) + [resposta(content=parecer_json(caso))])
    assert humano.decisao_gravada(caso) is None
    assert [c["protocolo"] for c in humano.pendentes()] == [caso]


def test_caso_que_nao_esta_aguardando_nao_chama_o_modelo(banco):
    r, modelo = preparar("CASO-9999", [resposta(content="{}")])
    assert r["parecer"] is None and modelo.chamadas == 0


def test_outro_ra_e_recusado_sem_ir_ao_servidor(caso):
    roteiro = [resposta(tool_calls=[chamada("consultar_financeiro", ra=RA_OUTRO)])] + coleta(caso) \
        + [resposta(content=parecer_json(caso))]
    r, _ = preparar(caso, roteiro)
    assert r["recusas"] == [{"ferramenta": "consultar_financeiro", "argumentos": {"ra": RA_OUTRO}}]
    assert "890" not in json.dumps(r, ensure_ascii=False)     # o débito da outra aluna não vaza


def test_recomendacao_e_reprovada_e_cai_na_contingencia(caso):
    ruim = parecer_json(caso, resumo="Recomendo aprovar o trancamento, o aluno está em dia.")
    r, _ = preparar(caso, coleta(caso) + [resposta(content=ruim)])
    assert r["origem"] == "contingencia"
    assert any("recomenda" in p for p in r["problemas_da_ultima_tentativa"])
    assert not ac.RECOMENDACAO.search(json.dumps(r["parecer"], ensure_ascii=False))


def test_artigo_que_a_busca_nao_devolveu_e_reprovado(caso):
    ruim = parecer_json(caso, artigos=["Art. 6º", "Art. 99"])
    r, _ = preparar(caso, coleta(caso) + [resposta(content=ruim)])
    assert r["origem"] == "contingencia"
    assert any("Art. 99" in p for p in r["problemas_da_ultima_tentativa"])


def test_fonte_inventada_e_reprovada(caso):
    ruim = parecer_json(caso, fatos=[{"texto": "coeficiente 9,5", "fonte": "consultar_historico"}])
    r, _ = preparar(caso, coleta(caso) + [resposta(content=ruim)])
    assert r["origem"] == "contingencia"


def test_segunda_tentativa_corrigida_e_aceita(caso):
    ruim = parecer_json(caso, ra=RA_OUTRO)
    r, _ = preparar(caso, coleta(caso) + [resposta(content=ruim), resposta(content=parecer_json(caso))])
    assert r["origem"] == "modelo"


def test_laco_de_ferramentas_para_no_limite(caso):
    r, modelo = preparar(caso, [resposta(tool_calls=[chamada("buscar_aluno", ra=RA_CASO)])])
    assert modelo.chamadas == ac.MAX_PASSOS and r["origem"] == "contingencia"


def test_contingencia_traz_dados_reais_do_caso(caso):
    r, _ = preparar(caso, [resposta(content="não sei")])
    p = r["parecer"]
    assert p["ra"] == RA_CASO and p["protocolo"] == caso
    assert any(f["fonte"] == "consultar_financeiro" for f in p["fatos"])
    assert "Art. 6º" in p["artigos"]


def test_modelo_nao_aprovado_e_recusado(caso):
    from triagem.modelos import ModeloNaoAprovado
    with pytest.raises(ModeloNaoAprovado):
        rodar(ac.preparar_parecer(caso, sessao=None, cliente=ModeloRoteirizado([resposta(content="{}")]),
                                  modelo="modelo/qualquer"))     # recusa antes de abrir qualquer consulta


def test_servidor_sobe_como_subprocesso_stdio(caso):
    """O caminho real do `coordenacao.py preparar`: o servidor num processo à parte, mesmo banco."""
    async def f():
        async with ac.sessao_stdio() as s:
            nomes = sorted(t.name for t in (await s.list_tools()).tools)
            pend = ac._conteudo(await s.call_tool("casos_aguardando_coordenacao", {}))
            return nomes, pend
    nomes, pend = rodar(f())
    assert nomes == sorted(mcp_secretaria.FERRAMENTAS_PUBLICADAS)
    assert pend["casos"][0]["protocolo"] == caso
