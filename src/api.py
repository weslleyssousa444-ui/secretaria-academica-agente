# API HTTP do sistema de triagem (Exercício 13, religada ao grafo na Parte 2).
#
# Dois lados, dois públicos:
#   /mensagens, /saude      o aluno (texto livre entra, objeto validado sai);
#   /coordenacao/*          a coordenação (lista o que espera, decide).
#
# O que é ESTADO e onde mora (nota 03 da Aula 13, §7):
#   - banco (documentos, fila, esperas, decisões) -> ACADEMICO_DB, no volume;
#   - conversa em andamento (checkpoint)           -> TRIAGEM_CHECKPOINT, no volume;
#   - memória entre execuções                      -> TRIAGEM_MEMORIA_DIR, no volume;
#   - registro de execução                         -> LOGS_DIR, no volume.
# Tudo em volume: a conversa e a pausa para a coordenação sobrevivem à troca
# do contêiner (diferente do Ex.13, em que a conversa morria com o processo).
#
# IDENTIDADE (docs/seguranca.md, ASI03): esta API NÃO autentica o aluno. A
# memória de longo prazo só abre com `ra_autenticado`, e ele só é aceito do
# cabeçalho `X-Aluno-RA` quando `TRIAGEM_CONFIA_NO_PORTAL=1`, isto é, quando há
# um portal na frente que o define (e que remove o cabeçalho vindo de fora).
# Sem isso, o cabeçalho é ignorado e não há memória: um RA digitado no chat
# nunca abre o histórico de ninguém.
#
# COORDENAÇÃO: o endpoint que decide um trancamento exige o token de
# `COORDENACAO_TOKEN`. Sem a variável, ele responde 503 e NÃO funciona: um
# endpoint de aprovação aberto seria pior que nenhum (fail-closed).

from __future__ import annotations

import hmac
import json
import os
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

import agente
import dados
from triagem import humano
from triagem.sistema import ConversaEncerrada, Sistema

PASTA_LOGS = Path(os.environ["LOGS_DIR"]) if os.environ.get("LOGS_DIR") else None

_sistema: Sistema | None = None
# Um turno por vez no processo inteiro: o protocolo é COUNT(*) + 1
# (agente.py, emitir_documento/escalar_para_humano), e dois turnos
# simultâneos gerariam o mesmo protocolo — limite registrado no model card.
_trava = threading.Lock()


def obter_sistema() -> Sistema:
    global _sistema
    if _sistema is None:
        _sistema = Sistema()
    return _sistema


@asynccontextmanager
async def ciclo_de_vida(_app: FastAPI):
    global _sistema
    dados.inicializar()  # idempotente: semeia só se o banco estiver vazio
    yield
    if _sistema is not None:
        _sistema.fechar()
        _sistema = None


app = FastAPI(title="Sistema de triagem da secretaria acadêmica", lifespan=ciclo_de_vida)


class Mensagem(BaseModel):
    mensagem: str = Field(min_length=1, max_length=2000)
    conversa_id: str | None = None


class Decisao(BaseModel):
    decisao: Literal["aprovar", "rejeitar", "aprovar_editando", "expirar"]
    por: str = Field(min_length=1, max_length=60)
    edicao: dict[str, str] = Field(default_factory=dict)


@app.get("/saude")
def saude() -> dict:
    """Não chama o modelo: diz só se o processo e o banco respondem."""
    try:
        conexao = dados.conectar()
        conexao.execute("SELECT 1").fetchone()
        conexao.close()
        banco = True
    except Exception:
        banco = False
    return {"ok": banco, "banco": banco, "modelo": agente.MODELO}


def _gravar_registro(conversa_id: str, resultado: dict, estado: dict) -> None:
    if PASTA_LOGS is None:
        return
    PASTA_LOGS.mkdir(parents=True, exist_ok=True)
    (PASTA_LOGS / f"api-{conversa_id}.json").write_text(json.dumps({
        "conversa_id": conversa_id, "saida": resultado["saida"],
        "termino": resultado["termino"], "motivo": resultado["motivo"],
        "trilha_de_nos": estado.get("eventos", []),
        "tokens_gastos": estado.get("tokens_gastos"),
    }, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


@app.post("/mensagens")
def mensagens(corpo: Mensagem, x_aluno_ra: str | None = Header(default=None)) -> dict:
    """Um turno do aluno. Sem `conversa_id`, abre uma conversa nova. A resposta
    traz o texto, a decisão e o protocolo, e nunca o resultado cru das
    ferramentas (que contém o cadastro e o financeiro do aluno)."""
    ra_autenticado = x_aluno_ra if os.environ.get("TRIAGEM_CONFIA_NO_PORTAL") == "1" else None
    with _trava:
        sistema = obter_sistema()
        if corpo.conversa_id is None:
            conversa_id = uuid4().hex
        else:
            conversa_id = corpo.conversa_id
            anterior = sistema.estado(conversa_id)
            if not anterior:
                raise HTTPException(404, "conversa não encontrada; abra uma nova")
            if anterior.get("termino") not in (None, "respondeu"):
                raise HTTPException(409, "conversa encerrada; abra uma nova")
        try:
            resultado = sistema.conversar(conversa_id, corpo.mensagem, ra_autenticado)
        except ConversaEncerrada as e:
            raise HTTPException(409, "conversa encerrada; abra uma nova") from e
        _gravar_registro(conversa_id, resultado, sistema.estado(conversa_id))

    saida = resultado["saida"]
    return {"conversa_id": conversa_id, "resposta": saida["resultado"],
            "decisao": saida["decisao"], "protocolo": saida["protocolo"],
            "aguardando_coordenacao": resultado["aguardando_humano"],
            "termino": resultado["termino"], "motivo": resultado["motivo"],
            "encerrada": resultado["termino"] != "respondeu"}


# ------------------------------------------------------------------ coordenação

def _exigir_coordenacao(token: str | None) -> None:
    esperado = os.environ.get("COORDENACAO_TOKEN")
    if not esperado:
        raise HTTPException(503, "coordenação não configurada (COORDENACAO_TOKEN ausente)")
    if not token or not hmac.compare_digest(token, esperado):
        raise HTTPException(401, "token da coordenação ausente ou inválido")


@app.get("/coordenacao/casos")
def casos_aguardando(x_coordenacao_token: str | None = Header(default=None)) -> list[dict]:
    """O que espera a coordenação, com a tela de cada caso (docs/humano.md §2)."""
    _exigir_coordenacao(x_coordenacao_token)
    return humano.pendentes()


@app.post("/coordenacao/casos/{protocolo}/decisao")
def decidir(protocolo: str, corpo: Decisao,
            x_coordenacao_token: str | None = Header(default=None)) -> dict:
    """Retoma o grafo pausado. Repetir a chamada devolve a decisão já gravada."""
    _exigir_coordenacao(x_coordenacao_token)
    try:
        decisao = humano.DecisaoHumana(**corpo.model_dump())
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    with _trava:
        try:
            return obter_sistema().decidir(protocolo, decisao)
        except KeyError as e:
            raise HTTPException(404, str(e)) from e


@app.post("/coordenacao/expirar")
def expirar(x_coordenacao_token: str | None = Header(default=None)) -> list[dict]:
    """Vence as esperas que passaram do prazo (docs/humano.md §4); rodado por rotina."""
    _exigir_coordenacao(x_coordenacao_token)
    with _trava:
        return obter_sistema().expirar_vencidos()
