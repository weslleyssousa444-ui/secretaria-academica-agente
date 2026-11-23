# O contrato de handoff entre os dois agentes (Parte 3, §5.1; docs/multiagente.md).
#
#   agente do aluno (grafo)  --handoff-->  assistente da coordenação
#
# Quem MONTA o handoff é o código coordenador (o nó `registrar_espera` do grafo),
# e não um modelo: ele lê a trajetória do turno e grava um objeto validado. O
# assistente só aceita trabalhar sobre um caso cujo handoff valida contra este
# schema (src/assistente_coordenacao.py).
#
# Os campos são os que o enunciado pede: objetivo; decisões e razões; escritas
# executadas com o identificador que cada uma devolveu; erros cometidos; fatos
# numéricos; e a chave de idempotência GERADA PELO COORDENADOR, derivada do
# conteúdo (protocolo, conversa e RA): o mesmo caso produz a mesma chave, então
# repetir o nó (a retomada do LangGraph roda o nó de novo) não cria um segundo
# handoff, e quem consome reconhece a repetição.

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

import dados

ESCRITAS = {"emitir_documento", "escalar_para_humano", "emitir_boleto"}
PRAZO_HORAS = 48


class Decisao(BaseModel):
    decisao: str
    razao: str


class Escrita(BaseModel):
    ferramenta: str
    identificador: str


class Handoff(BaseModel):
    de: Literal["triagem-secretaria"] = "triagem-secretaria"
    para: Literal["assistente-coordenacao"] = "assistente-coordenacao"
    objetivo: str = Field(min_length=10)
    protocolo: str
    ra: str | None
    thread_id: str
    decisoes: list[Decisao] = Field(min_length=1)
    escritas: list[Escrita] = Field(min_length=1)
    erros: list[str] = Field(default_factory=list)
    fatos_numericos: dict[str, float] = Field(default_factory=dict)
    chave_idempotencia: str = Field(pattern=r"^hf-[0-9a-f]{16}$")


def gerar_chave(protocolo: str, thread_id: str, ra: str | None) -> str:
    base = f"handoff|{protocolo}|{thread_id}|{ra or ''}"
    return "hf-" + hashlib.sha256(base.encode("utf-8")).hexdigest()[:16]


def montar(protocolo: str, thread_id: str, ra: str | None, passos: list[dict]) -> Handoff:
    """Monta o handoff a partir da trajetória (todos os passos da conversa)."""
    escritas = [Escrita(ferramenta=p["ferramenta"], identificador=str(p["resultado"]["protocolo"]))
                for p in passos
                if p["ferramenta"] in ESCRITAS and p.get("erro") is None
                and isinstance(p.get("resultado"), dict) and p["resultado"].get("protocolo")]
    if not any(e.ferramenta == "escalar_para_humano" and e.identificador == protocolo for e in escritas):
        escritas.append(Escrita(ferramenta="escalar_para_humano", identificador=protocolo))
    erros = [f"{p['ferramenta']}: {p['erro']}" for p in passos if p.get("erro")]
    fatos: dict[str, float] = {"prazo_coordenacao_horas": PRAZO_HORAS}
    fin = next((p["resultado"] for p in reversed(passos)
                if p["ferramenta"] == "consultar_financeiro" and p.get("erro") is None
                and isinstance(p.get("resultado"), dict) and p["resultado"].get("ra") == ra), None)
    if fin:
        fatos["mensalidades_em_aberto"] = float(fin.get("mensalidades_em_aberto", 0))
        fatos["valor_em_aberto"] = float(fin.get("valor_em_aberto", 0.0))
    return Handoff(
        objetivo=f"preparar o parecer de apoio para a coordenação decidir o trancamento {protocolo}",
        protocolo=protocolo, ra=ra, thread_id=thread_id,
        decisoes=[Decisao(decisao="encaminhar_trancamento_a_coordenacao",
                          razao="trancamento é decidido pela coordenação (Regimento, Art. 6º); "
                                "o agente do aluno não decide")],
        escritas=escritas, erros=erros, fatos_numericos=fatos,
        chave_idempotencia=gerar_chave(protocolo, thread_id, ra))


def gravar(handoff: Handoff) -> dict:
    """Grava UMA vez por chave. Repetir devolve o gravado, com `ja_existia`."""
    con = dados.conectar()
    inseriu = con.execute(
        "INSERT OR IGNORE INTO handoffs (chave, protocolo, conteudo, criado_em) VALUES (?, ?, ?, ?)",
        (handoff.chave_idempotencia, handoff.protocolo, handoff.model_dump_json(),
         datetime.now(timezone.utc).isoformat(timespec="seconds"))).rowcount
    con.commit()
    con.close()
    return {"chave": handoff.chave_idempotencia, "ja_existia": not inseriu}


def carregar(protocolo: str) -> dict | None:
    con = dados.conectar()
    linha = con.execute("SELECT conteudo FROM handoffs WHERE protocolo = ?", (protocolo,)).fetchone()
    con.close()
    return json.loads(linha["conteudo"]) if linha else None
