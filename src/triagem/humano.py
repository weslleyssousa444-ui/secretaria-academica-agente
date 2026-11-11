# Aprovação humana do trancamento (docs/humano.md).
#
# O que o agente NÃO faz: decidir trancamento. Ele abre o caso na fila
# (`escalar_para_humano`) e o grafo PARA num `interrupt()` esperando a
# coordenação. Este módulo é o lado "código" dessa pausa: o que se grava ao
# começar a esperar, o que a pessoa vê, o que ela pode devolver e como a
# decisão é gravada UMA vez só.
#
# IDEMPOTÊNCIA (Aula 05, nota 02 §8): a retomada de um `interrupt()` executa
# o nó DE NOVO desde o começo, e uma aprovação pode chegar repetida. Por isso
# as duas escritas daqui têm chave derivada do conteúdo:
#   - `aprovacoes.protocolo` (PRIMARY KEY) -> esperar duas vezes = uma linha;
#   - `decisoes_humanas.chave = <protocolo>:decisao` -> decidir duas vezes =
#     uma linha, e a PRIMEIRA decisão vale (a segunda volta com `ja_existia`
#     e, se for diferente, `conflito=True`, sem sobrescrever).

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

import dados

PRAZO_HORAS = 48  # o mesmo prazo que o agente promete ao aluno (prompts/triagem-v2)
CAMPOS_EDITAVEIS = ("semestre_efetivo", "observacao")
STATUS_DO_CASO = {"aprovar": "aprovado", "aprovar_editando": "aprovado",
                  "rejeitar": "rejeitado", "expirar": "vencido"}


def agora_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso(momento: datetime) -> str:
    return momento.strftime("%Y-%m-%dT%H:%M:%SZ")


class DecisaoHumana(BaseModel):
    """O que a coordenação devolve ao grafo. Validada ANTES de retomar: o
    grafo nunca recebe uma resposta fora do contrato."""
    decisao: Literal["aprovar", "rejeitar", "aprovar_editando", "expirar"]
    por: str = Field(min_length=1, max_length=60)
    edicao: dict[str, str] = Field(default_factory=dict)

    @field_validator("edicao")
    @classmethod
    def so_campos_editaveis(cls, edicao: dict[str, str]) -> dict[str, str]:
        invalidos = set(edicao) - set(CAMPOS_EDITAVEIS)
        if invalidos:
            raise ValueError(f"campos não editáveis: {sorted(invalidos)}")
        return edicao

    @model_validator(mode="after")
    def edicao_so_quando_edita(self) -> "DecisaoHumana":
        if self.decisao == "aprovar_editando" and not self.edicao:
            raise ValueError("aprovar_editando exige ao menos um campo editado")
        if self.decisao != "aprovar_editando" and self.edicao:
            raise ValueError("só aprovar_editando aceita edição")
        return self


def registrar_espera(thread_id: str, protocolo: str, ra: str | None,
                     agora: datetime | None = None) -> dict:
    """Marca o caso como aguardando a coordenação e fixa o prazo. Idempotente:
    se o nó rodar duas vezes, o prazo continua o da primeira."""
    agora = agora or agora_utc()
    con = dados.conectar()
    con.execute(
        "INSERT OR IGNORE INTO aprovacoes (protocolo, thread_id, ra, criado_em, prazo_ate) "
        "VALUES (?, ?, ?, ?, ?)",
        (protocolo, thread_id, ra, iso(agora), iso(agora + timedelta(hours=PRAZO_HORAS))))
    con.commit()
    linha = dict(con.execute(
        "SELECT * FROM aprovacoes WHERE protocolo = ?", (protocolo,)).fetchone())
    con.close()
    return linha


def tela_da_aprovacao(protocolo: str) -> dict:
    """O que a pessoa vê no momento da pausa (docs/humano.md §2). Montada pelo
    CÓDIGO a partir do banco, e não pelo modelo: o motivo que o modelo escreveu
    aparece como dado do caso, mas a ação, a consequência e as respostas
    aceitas são fixas."""
    con = dados.conectar()
    caso = con.execute("SELECT * FROM casos_pendentes WHERE protocolo = ?",
                       (protocolo,)).fetchone()
    aluno = con.execute("SELECT * FROM alunos WHERE ra = ?",
                        (caso["ra"],)).fetchone() if caso and caso["ra"] else None
    espera = con.execute("SELECT * FROM aprovacoes WHERE protocolo = ?",
                         (protocolo,)).fetchone()
    con.close()
    return {
        "acao": "registrar a decisão da coordenação sobre o trancamento",
        "protocolo": protocolo,
        "aluno": ({"ra": aluno["ra"], "nome": aluno["nome"], "curso": aluno["curso"],
                   "situacao_matricula": aluno["situacao_matricula"]} if aluno else None),
        "motivo_registrado": caso["motivo"] if caso else None,
        "prazo_ate": espera["prazo_ate"] if espera else None,
        "consequencia": ("Aprovar ou rejeitar grava a decisão no caso. O agente não "
                         "altera a matrícula: a efetivação é da secretaria. Sem "
                         f"resposta em {PRAZO_HORAS} h, o caso vence e volta à fila "
                         "da secretaria com prioridade."),
        "respostas_aceitas": ["aprovar", "rejeitar", "aprovar_editando"],
        "campos_editaveis": list(CAMPOS_EDITAVEIS),
    }


def registrar_decisao(protocolo: str, decisao: DecisaoHumana,
                      agora: datetime | None = None) -> dict:
    """Grava a decisão UMA vez. A primeira vale; repetir devolve a gravada."""
    agora = agora or agora_utc()
    status = STATUS_DO_CASO[decisao.decisao]
    chave = f"{protocolo}:decisao"
    con = dados.conectar()
    inseriu = con.execute(
        "INSERT OR IGNORE INTO decisoes_humanas "
        "(chave, protocolo, decisao, edicao, decidido_por, decidido_em) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (chave, protocolo, status,
         json.dumps(decisao.edicao, ensure_ascii=False) if decisao.edicao else None,
         decisao.por, iso(agora))).rowcount == 1
    if inseriu:
        con.execute("UPDATE casos_pendentes SET status = ? WHERE protocolo = ?",
                    (status, protocolo))
        con.execute("UPDATE aprovacoes SET estado = ? WHERE protocolo = ?",
                    ("vencido" if status == "vencido" else "decidido", protocolo))
    con.commit()
    gravada = dict(con.execute("SELECT * FROM decisoes_humanas WHERE chave = ?",
                               (chave,)).fetchone())
    con.close()
    return {"protocolo": protocolo, "decisao": gravada["decisao"],
            "decidido_por": gravada["decidido_por"], "decidido_em": gravada["decidido_em"],
            "ja_existia": not inseriu,
            "conflito": (not inseriu) and gravada["decisao"] != status}


def decisao_gravada(protocolo: str) -> dict | None:
    con = dados.conectar()
    linha = con.execute("SELECT * FROM decisoes_humanas WHERE chave = ?",
                        (f"{protocolo}:decisao",)).fetchone()
    con.close()
    return dict(linha) if linha else None


def vencidos(agora: datetime | None = None) -> list[dict]:
    """Esperas cujo prazo passou sem resposta (docs/humano.md §4)."""
    agora = agora or agora_utc()
    con = dados.conectar()
    linhas = con.execute(
        "SELECT * FROM aprovacoes WHERE estado = 'aguardando' AND prazo_ate < ?",
        (iso(agora),)).fetchall()
    con.close()
    return [dict(l) for l in linhas]


def pendentes() -> list[dict]:
    """O que está esperando a coordenação agora, com a tela de cada caso."""
    con = dados.conectar()
    linhas = con.execute(
        "SELECT protocolo FROM aprovacoes WHERE estado = 'aguardando' ORDER BY criado_em").fetchall()
    con.close()
    return [tela_da_aprovacao(l["protocolo"]) for l in linhas]
