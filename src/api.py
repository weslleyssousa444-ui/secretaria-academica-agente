# API HTTP do agente de triagem — Exercício 13 (empacotamento).
#
# O mesmo `conversar()` de src/agente.py, atrás de dois endpoints, para o
# agente rodar em container como serviço (docs/empacotamento.md). Nenhuma
# regra de negócio nova aqui: a API só guarda a conversa entre turnos e
# grava o registro de execução a cada turno.
#
# O que é ESTADO e onde mora (nota 03 da Aula 13, §7):
#   - banco (documentos emitidos, casos na fila) -> ACADEMICO_DB, no volume;
#   - registro de execução                        -> LOGS_DIR, no volume;
#   - conversa em andamento                       -> memória do processo.
#     Perde-se se o container for substituído no meio dela; é a perda
#     ACEITA E DECLARADA: o aluno recomeça, e o que já foi escrito no banco
#     não se repete, porque as duas escritas são idempotentes.

from __future__ import annotations

import os
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

import agente
import dados
from agente import Estado, Orcamento, Termino, conversar, salvar_log

PASTA_LOGS = Path(os.environ["LOGS_DIR"]) if os.environ.get("LOGS_DIR") else None

_conversas: dict[str, tuple[Estado, Orcamento]] = {}
# Um turno por vez no processo inteiro: o protocolo é COUNT(*) + 1
# (agente.py, emitir_documento/escalar_para_humano), e dois turnos
# simultâneos gerariam o mesmo protocolo — limite registrado no model card.
_trava = threading.Lock()


@asynccontextmanager
async def ciclo_de_vida(_app: FastAPI):
    dados.inicializar()  # idempotente: semeia só se o banco estiver vazio
    yield


app = FastAPI(title="Agente de triagem da secretaria acadêmica",
              lifespan=ciclo_de_vida)


class Mensagem(BaseModel):
    mensagem: str = Field(min_length=1, max_length=2000)
    conversa_id: str | None = None


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


@app.post("/mensagens")
def mensagens(corpo: Mensagem) -> dict:
    """Um turno do aluno. Sem `conversa_id`, abre uma conversa nova. A
    resposta traz só o texto do agente — nunca o resultado das ferramentas,
    que contém o cadastro e o financeiro do aluno."""
    with _trava:
        if corpo.conversa_id is None:
            estado, orcamento = Estado(caso="api"), Orcamento()
            conversa_id = estado.execucao_id
            _conversas[conversa_id] = (estado, orcamento)
        elif corpo.conversa_id in _conversas:
            conversa_id = corpo.conversa_id
            estado, orcamento = _conversas[conversa_id]
            if estado.termino is not None and estado.termino is not Termino.RESPONDEU:
                raise HTTPException(409, "conversa encerrada; abra uma nova")
        else:
            raise HTTPException(404, "conversa não encontrada (o serviço pode ter "
                                     "sido reiniciado); abra uma nova")

        estado = conversar(estado, corpo.mensagem, orcamento, verboso=False)
        salvar_log(estado, "api", PASTA_LOGS)

    ultima = estado.historico[-1] if estado.historico else {}
    texto = ultima.get("content") if isinstance(ultima, dict) and \
        ultima.get("role") == "assistant" else None
    encerrada = estado.termino is not Termino.RESPONDEU
    if encerrada:
        texto = texto or ("Não consegui concluir seu atendimento. Abra uma nova "
                          "solicitação ou procure a secretaria.")
    return {"conversa_id": conversa_id, "resposta": texto,
            "termino": estado.termino.value, "motivo": estado.motivo,
            "encerrada": encerrada}
