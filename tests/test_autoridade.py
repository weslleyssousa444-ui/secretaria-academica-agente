# Evidência dos limites de autoridade APLICADOS FORA DO MODELO
# (docs/model-card.md, campo Autoridade). Cada teste corresponde a uma linha
# da tabela de autoridade; o nome do teste é o que o model card cita.

from __future__ import annotations

import httpx
import openai
import pytest

import agente
from agente import ErroRecuperavel, Estado, Orcamento, Termino, conversar
from conftest import chamada, contar, resposta


# ------------------------------------------------ ausência de ferramenta

def test_nao_existe_ferramenta_de_trancamento():
    """Trancar matrícula, pagar, alterar cadastro: nenhuma ferramenta faz."""
    assert set(agente.FERRAMENTAS) == {
        "buscar_aluno", "consultar_financeiro",
        "emitir_documento", "escalar_para_humano"}
    assert set(agente.DECLARACOES) == set(agente.FERRAMENTAS)
    assert agente.ESCRITA == {"emitir_documento", "escalar_para_humano"}


def test_modelo_pede_ferramenta_inexistente_nada_e_executado(banco, modelo):
    """O modelo 'inventa' trancar_matricula: o laço devolve erro e não escreve."""
    modelo([resposta([chamada("trancar_matricula", ra="20229012")]),
            resposta(content="Não consigo trancar; vou encaminhar.")])
    antes = (contar("documentos_emitidos"), contar("casos_pendentes"))
    estado = conversar(Estado(), "Quero trancar. RA 20229012", Orcamento(), verboso=False)
    assert estado.passos[0].erro == "ferramenta desconhecida: trancar_matricula"
    assert (contar("documentos_emitidos"), contar("casos_pendentes")) == antes


# ------------------------------------------------ código (emitir_documento)

def test_emitir_recusa_trancamento(banco):
    with pytest.raises(ErroRecuperavel) as erro:
        agente.emitir_documento("20229012", "trancamento_matricula")
    assert "não emitido por este agente" in str(erro.value)
    assert contar("documentos_emitidos") == 1  # só a semente DOC-1000


def test_emitir_recusa_documento_fora_do_catalogo(banco):
    with pytest.raises(ErroRecuperavel):
        agente.emitir_documento("20231045", "segunda_via_diploma")


def test_segunda_via_bloqueada_com_pendencia(banco):
    """Regra de divergência: 'já paguei' não passa — 20230198 tem 2 em aberto."""
    with pytest.raises(ErroRecuperavel) as erro:
        agente.emitir_documento("20230198", "segunda_via_historico")
    assert erro.value.payload["mensalidades_em_aberto"] == 2
    assert contar("documentos_emitidos") == 1


def test_declaracao_bloqueada_matricula_nao_ativa(banco):
    with pytest.raises(ErroRecuperavel) as erro:
        agente.emitir_documento("20221100", "declaracao_matricula")  # trancada
    assert erro.value.payload["situacao"] == "trancada"


def test_emitir_ra_inexistente(banco):
    with pytest.raises(ErroRecuperavel):
        agente.emitir_documento(banco.RA_INEXISTENTE, "declaracao_matricula")


def test_modelo_desobedece_prompt_e_codigo_barra_emissao(banco, modelo):
    """O cenário que o prompt sozinho não garante: o aluno diz 'já paguei' e
    o modelo tenta emitir mesmo assim. A ferramenta revalida e recusa."""
    modelo([resposta([chamada("emitir_documento", ra="20230198",
                              tipo_documento="segunda_via_historico")]),
            resposta(content="Não foi possível emitir.")])
    estado = conversar(Estado(), "Já paguei, quero a segunda via. RA 20230198",
                       Orcamento(), verboso=False)
    assert "pendência financeira" in estado.passos[0].erro
    assert contar("documentos_emitidos") == 1


# ------------------------------------------------ código (idempotência)

def test_emitir_idempotente(banco):
    r1 = agente.emitir_documento("20231045", "declaracao_matricula")
    r2 = agente.emitir_documento("20231045", "declaracao_matricula")
    assert r1["protocolo"] == r2["protocolo"]
    assert (r1["ja_existia"], r2["ja_existia"]) == (False, True)


def test_escalar_idempotente_pela_chave(banco):
    chave = "20229012:trancamento_matricula:trancamento"
    r1 = agente.escalar_para_humano("20229012", "trancamento_matricula", "trancamento", chave)
    r2 = agente.escalar_para_humano("20229012", "trancamento_matricula", "trancamento", chave)
    assert r1["protocolo"] == r2["protocolo"] and r2["ja_existia"] is True
    assert contar("casos_pendentes") == 1


# ------------------------------------------------ código (orçamento e laço)

def test_trancamento_escalado_pelo_codigo_se_modelo_nao_escalar(banco, modelo):
    """L02 corrigida: o modelo confirma o RA e responde em texto 'trancamento
    registrado' sem chamar escalar_para_humano. O código abre o caso, e o
    modelo redige a resposta final depois, com o protocolo real."""
    modelo([resposta([chamada("buscar_aluno", ra="20229012")]),
            resposta(content="Seu trancamento foi registrado."),
            resposta(content="Encaminhei seu pedido à coordenação.")])
    estado = conversar(Estado(), "Quero trancar. RA 20229012", Orcamento(), verboso=False)
    assert estado.termino is Termino.RESPONDEU
    assert estado.historico[-1]["content"] == "Encaminhei seu pedido à coordenação."
    assert contar("casos_pendentes") == 1
    passo = estado.passos[-1]
    assert passo.ferramenta == "escalar_para_humano"
    assert passo.argumentos["tipo_pedido"] == "trancamento_matricula"
    assert passo.resultado["protocolo"].startswith("CASO-")


def test_trancamento_nao_duplica_caso_aberto_pelo_modelo(banco, modelo):
    """Se o modelo já escalou, o código não abre um segundo caso."""
    modelo([resposta([chamada("buscar_aluno", ra="20229012")]),
            resposta([chamada("escalar_para_humano", ra="20229012",
                              tipo_pedido="trancamento_matricula",
                              motivo="pedido de trancamento",
                              chave="20229012:trancamento_matricula:pedido")]),
            resposta(content="Encaminhado.")])
    estado = conversar(Estado(), "Quero trancar. RA 20229012", Orcamento(), verboso=False)
    assert estado.termino is Termino.RESPONDEU
    assert contar("casos_pendentes") == 1


def test_trancamento_sem_ra_confirmado_nao_abre_caso(banco, modelo):
    """Sem RA confirmado por buscar_aluno (agente pedindo o RA, ou RA
    inexistente), o código não escala: o modelo segue o diálogo."""
    modelo([resposta(content="Qual é o seu RA?")])
    estado = conversar(Estado(), "Quero trancar minha matrícula", Orcamento(), verboso=False)
    assert estado.termino is Termino.RESPONDEU
    assert contar("casos_pendentes") == 0

    modelo([resposta([chamada("buscar_aluno", ra="20239999")]),
            resposta(content="Não encontrei esse RA. Pode confirmar?")])
    estado = conversar(Estado(), "Quero trancar. RA 20239999", Orcamento(), verboso=False)
    assert contar("casos_pendentes") == 0


def test_outros_pedidos_nao_disparam_escalonamento_de_trancamento(banco, modelo):
    modelo([resposta([chamada("buscar_aluno", ra="20231045")]),
            resposta(content="Posso emitir sua declaração.")])
    estado = conversar(Estado(), "Preciso de uma declaração. RA 20231045",
                       Orcamento(), verboso=False)
    assert estado.termino is Termino.RESPONDEU
    assert contar("casos_pendentes") == 0


def test_orcamento_de_passos_interrompe(banco, modelo):
    ras = ["20231045", "20230198", "20229012", "20221100", "20233321"]
    modelo([resposta([chamada("buscar_aluno", ra=ra)]) for ra in ras])
    estado = conversar(Estado(), "oi", Orcamento(max_passos=3), verboso=False)
    assert estado.termino is Termino.ORCAMENTO
    assert estado.n_passos == 3


def test_orcamento_de_tokens_interrompe(banco, modelo):
    ras = ["20231045", "20230198", "20229012", "20221100", "20233321"]
    modelo([resposta([chamada("buscar_aluno", ra=ra)]) for ra in ras])
    estado = conversar(Estado(), "oi", Orcamento(max_tokens=250), verboso=False)
    assert estado.termino is Termino.ORCAMENTO
    assert estado.motivo.startswith("tokens")


def test_laco_detectado(banco, modelo):
    modelo([resposta([chamada("buscar_aluno", ra="20231045")])])
    estado = conversar(Estado(), "oi", Orcamento(), verboso=False)
    assert estado.termino is Termino.LACO
    assert estado.n_passos == 3


# ------------------------------------------------ falha de controle

def test_erro_da_api_termina_sem_escrita(banco, modelo):
    """Falha não recuperável do provedor (4xx): termina em erro_fatal, sem
    nenhuma escrita — o comportamento é fail-closed."""
    requisicao = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    erro = openai.BadRequestError("bad request", response=httpx.Response(400, request=requisicao),
                                  body=None)
    modelo([erro])
    antes = (contar("documentos_emitidos"), contar("casos_pendentes"))
    estado = conversar(Estado(), "Declaração, RA 20231045", Orcamento(), verboso=False)
    assert estado.termino is Termino.ERRO_FATAL
    assert (contar("documentos_emitidos"), contar("casos_pendentes")) == antes
