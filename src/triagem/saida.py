# O contrato de saída do sistema (docs/io.md).
#
# A saída é um OBJETO VALIDADO, montado pelo código a partir do que as
# ferramentas devolveram — não texto solto do modelo. O modelo escreve o
# `resultado` (a resposta ao aluno); a `decisao`, a `fonte` e a `suficiencia`
# vêm da trajetória. É isso que torna a fonte conferível: ela aponta para uma
# ferramenta que de fato respondeu, e não para o que o modelo disse ter usado.
#
# Os rótulos de `decisao` são os mesmos de `verificador.classificar_decisao`
# (Parte 1) e do golden dataset (Exercício 11): a suíte compara o campo
# direto, sem tradução.

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Decisao = Literal[
    "emitir_declaracao", "emitir_segunda_via",
    "escalar_trancamento", "escalar_pendencia", "escalar_divergencia",
    "escalar_ra_nao_encontrado", "escalar_outro",
    "responder_regimento", "sem_acao",
    # 13/11/2026: segunda via de boleto e consulta acadêmica (src/triagem/servicos.py)
    "emitir_boleto", "informar_situacao_academica",
]


class Fonte(BaseModel):
    """O que sustenta o resultado, conferível: uma chamada de ferramenta
    (`ferramenta:<identificador>`) ou um artigo do Regimento."""
    tipo: Literal["ferramenta", "regimento"]
    referencia: str


class Suficiencia(BaseModel):
    """Se o sistema teve base para responder. A recusa faz parte do contrato:
    `suficiente=False` com o motivo é uma saída válida."""
    suficiente: bool
    motivo: str


class SaidaTriagem(BaseModel):
    resultado: str = Field(min_length=1)
    decisao: Decisao
    fonte: list[Fonte]
    suficiencia: Suficiencia
    protocolo: str | None = None
    aguardando_humano: bool = False
    termino: str


def _decisao_de_escalonamento(resultado: dict) -> str:
    motivo = (resultado.get("motivo") or "").lower()
    if resultado.get("tipo_pedido") == "trancamento_matricula":
        return "escalar_trancamento"
    # "encontrad" cobre "RA não encontrado" sem casar "financeira não resolvida"
    # (mesmo cuidado de verificador.classificar_decisao).
    if "encontrad" in motivo:
        return "escalar_ra_nao_encontrado"
    if "diverg" in motivo:
        return "escalar_divergencia"
    if "pend" in motivo:
        return "escalar_pendencia"
    return "escalar_outro"


def decisao_da_trajetoria(passos: list[dict]) -> str:
    """Rótulo da ÚLTIMA ação de decisão bem-sucedida; se não houve, dúvida do
    regimento respondida, ou `sem_acao` (só perguntas, recusa, orçamento)."""
    for passo in reversed(passos):
        if passo.get("erro") is not None or passo.get("resultado") is None:
            continue
        nome, resultado = passo["ferramenta"], passo["resultado"]
        if nome == "emitir_documento":
            return {"declaracao_matricula": "emitir_declaracao",
                    "segunda_via_historico": "emitir_segunda_via"}.get(
                        resultado.get("tipo_documento"), "sem_acao")
        if nome == "escalar_para_humano":
            return _decisao_de_escalonamento(resultado)
        if nome == "emitir_boleto":
            return "emitir_boleto"
    if any(p["ferramenta"] == "consultar_historico" and p.get("erro") is None
           and p.get("resultado") for p in passos):
        return "informar_situacao_academica"
    # Só é "responder do regimento" se algum artigo voltou; zero artigo é recusa.
    if any(p["ferramenta"] == "consultar_regimento" and p.get("erro") is None
           and (p.get("resultado") or {}).get("total", 0) > 0 for p in passos):
        return "responder_regimento"
    return "sem_acao"


def fontes_da_trajetoria(passos: list[dict], artigos_citados: list[str]) -> list[Fonte]:
    fontes: list[Fonte] = []
    for passo in passos:
        if passo.get("erro") is not None or passo.get("resultado") is None:
            continue
        resultado = passo["resultado"]
        nome = passo["ferramenta"]
        if nome in ("buscar_aluno", "consultar_financeiro", "consultar_historico"):
            fontes.append(Fonte(tipo="ferramenta", referencia=f"{nome}:{resultado.get('ra')}"))
        elif nome in ("emitir_documento", "escalar_para_humano", "emitir_boleto"):
            fontes.append(Fonte(tipo="ferramenta",
                                referencia=f"{nome}:{resultado.get('protocolo')}"))
    fontes += [Fonte(tipo="regimento", referencia=a) for a in artigos_citados]
    return fontes


def protocolo_da_trajetoria(passos: list[dict]) -> str | None:
    for passo in reversed(passos):
        if (passo["ferramenta"] in ("emitir_documento", "escalar_para_humano", "emitir_boleto")
                and passo.get("erro") is None and passo.get("resultado")):
            return passo["resultado"].get("protocolo")
    return None


def suficiencia_da_trajetoria(decisao: str, passos: list[dict], termino: str,
                              artigos_citados: list[str],
                              declarada: bool | None = None) -> Suficiencia:
    if termino != "respondeu":
        return Suficiencia(suficiente=False,
                           motivo=f"a execução terminou por {termino}, sem conclusão")
    if decisao.startswith(("emitir_", "escalar_")):
        return Suficiencia(suficiente=True,
                           motivo="decisão tomada com o retorno de uma ferramenta")
    if decisao == "informar_situacao_academica":
        return Suficiencia(suficiente=True,
                           motivo="resposta com os dados acadêmicos devolvidos pela ferramenta")
    if decisao == "responder_regimento":
        # Suficiente = o agente DECLAROU que os artigos respondem E o texto cita
        # ao menos um artigo devolvido (a citação é conferida em código).
        if declarada is True and artigos_citados:
            return Suficiencia(suficiente=True,
                               motivo="resposta com artigo do Regimento citado e conferido")
        return Suficiencia(suficiente=False,
                           motivo="a resposta não cita artigo devolvido ou não declara suficiência")
    if declarada is False:
        return Suficiencia(suficiente=False,
                           motivo="o agente declarou que o Regimento não responde à pergunta")
    return Suficiencia(suficiente=False,
                       motivo="nenhuma ação tomada: falta informação do aluno, ou fora do escopo")
