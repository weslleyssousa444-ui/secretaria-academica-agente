# O ponto de entrada do sistema (docs/io.md §0): texto livre entra, um objeto
# validado sai. É o que `src/chat.py`, a API, a suíte de avaliação e as
# demonstrações chamam.
#
# O QUE IDENTIFICA UMA CONVERSA (docs/memoria.md §5.5): o `thread_id`, que é o
# endereço do checkpoint. Mesma chave, mesma conversa; chave nova, histórico
# vazio. A mesma pessoa abrindo duas conversas ao mesmo tempo tem dois
# `thread_id` e dois históricos independentes; o que as liga é a memória de
# longo prazo, endereçada pelo RA autenticado.
#
# ONDE O CHECKPOINT GRAVA: arquivo SQLite (`TRIAGEM_CHECKPOINT`). Em arquivo,
# e não em memória: a pausa para a coordenação sobrevive ao fim do processo,
# que é o que torna a aprovação humana possível em outro dia.

from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

import dados
from triagem import humano
from triagem import nos as n
from triagem.grafo import RECURSION_LIMIT, construir
from triagem.memoria import Memoria
from triagem.saida import SaidaTriagem, Suficiencia

RAIZ = Path(__file__).resolve().parents[2]
MAX_ENTRADA = 2000  # caracteres: o mesmo teto da API da Parte 1


class Sistema:
    def __init__(self, checkpoint: Path | str | None = None,
                 memoria_dir: Path | str | None = None):
        self.caminho_checkpoint = Path(checkpoint or os.environ.get(
            "TRIAGEM_CHECKPOINT", RAIZ / "checkpoints" / "triagem.sqlite"))
        self.caminho_checkpoint.parent.mkdir(parents=True, exist_ok=True)
        self._conexao = sqlite3.connect(self.caminho_checkpoint, check_same_thread=False)
        self.memoria = Memoria(Path(memoria_dir or os.environ.get(
            "TRIAGEM_MEMORIA_DIR", RAIZ / "dados" / "memoria")))
        # O grafo é compilado UMA vez, aqui, e reaproveitado em todo turno.
        self.app = construir(n.Nos(self.memoria)).compile(
            checkpointer=SqliteSaver(self._conexao))

    def fechar(self) -> None:
        self._conexao.close()

    @staticmethod
    def _config(thread_id: str) -> dict:
        return {"configurable": {"thread_id": thread_id}, "recursion_limit": RECURSION_LIMIT}

    # ------------------------------------------------------------------ turno
    def conversar(self, thread_id: str, texto: str,
                  ra_autenticado: str | None = None) -> dict:
        """Um turno do aluno. Se a conversa está esperando a coordenação, NÃO
        chama o modelo: devolve o estado do pedido (um segundo trancamento
        não abre outro caso, e o aluno não fica sem resposta)."""
        texto = (texto or "").strip()
        if not texto:
            raise ValueError("mensagem vazia")
        if len(texto) > MAX_ENTRADA:
            raise ValueError(f"mensagem acima de {MAX_ENTRADA} caracteres")

        config = self._config(thread_id)
        instantaneo = self.app.get_state(config)
        if instantaneo.next:  # pausada num interrupt
            return self._resposta_de_espera(thread_id, instantaneo.values)

        resultado = self.app.invoke(
            {"thread_id": thread_id, "ra_autenticado": ra_autenticado,
             "mensagens": [{"role": "user", "content": texto}]}, config)
        return {"thread_id": thread_id, "saida": resultado["saida"],
                "aguardando_humano": "__interrupt__" in resultado,
                "termino": resultado["termino"], "motivo": resultado.get("motivo")}

    def _resposta_de_espera(self, thread_id: str, valores: dict) -> dict:
        protocolo = valores.get("caso_trancamento")
        con = dados.conectar()
        espera = con.execute("SELECT prazo_ate FROM aprovacoes WHERE protocolo = ?",
                             (protocolo,)).fetchone()
        con.close()
        saida = SaidaTriagem(
            resultado=(f"Seu pedido de trancamento (protocolo {protocolo}) já está com a "
                       f"coordenação, com resposta até {espera['prazo_ate'] if espera else '48h'}. "
                       "Não é preciso abrir outro."),
            decisao="sem_acao", fonte=[],
            suficiencia=Suficiencia(suficiente=True, motivo="caso já aberto, aguardando a coordenação"),
            protocolo=protocolo, aguardando_humano=True, termino="respondeu")
        return {"thread_id": thread_id, "saida": saida.model_dump(),
                "aguardando_humano": True, "termino": "respondeu", "motivo": None}

    # ----------------------------------------------------- a coordenação decide
    def decidir(self, protocolo: str, decisao: humano.DecisaoHumana) -> dict:
        """Retoma o grafo pausado com a decisão. Repetir a MESMA chamada não
        grava de novo: devolve a decisão já gravada (docs/humano.md §5)."""
        gravada = humano.decisao_gravada(protocolo)
        if gravada:
            novo_status = humano.STATUS_DO_CASO[decisao.decisao]
            return {"protocolo": protocolo, "ja_decidido": True,
                    "decisao": gravada["decisao"],
                    "conflito": gravada["decisao"] != novo_status}
        con = dados.conectar()
        espera = con.execute("SELECT thread_id FROM aprovacoes WHERE protocolo = ?",
                             (protocolo,)).fetchone()
        con.close()
        if espera is None:
            raise KeyError(f"nenhum caso aguardando a coordenação com o protocolo {protocolo}")
        config = self._config(espera["thread_id"])
        if not self.app.get_state(config).next:
            # Checkpoint perdido (ex.: removido por pedido de esquecimento): a
            # decisão ainda precisa ficar registrada no caso.
            gravacao = humano.registrar_decisao(protocolo, decisao)
            return {"protocolo": protocolo, "ja_decidido": False,
                    "decisao": gravacao["decisao"], "conflito": False}
        resultado = self.app.invoke(Command(resume=decisao.model_dump()), config)
        gravacao = resultado["decisao_humana"]["gravacao"]
        return {"protocolo": protocolo, "ja_decidido": False,
                "decisao": gravacao["decisao"], "conflito": gravacao["conflito"]}

    def expirar_vencidos(self, agora: datetime | None = None) -> list[dict]:
        """O que acontece se ninguém responde (docs/humano.md §4): passado o
        prazo, o caso vence e volta à fila da secretaria. Rodado por rotina."""
        return [self.decidir(e["protocolo"],
                             humano.DecisaoHumana(decisao="expirar", por="sistema"))
                for e in humano.vencidos(agora)]

    def estado(self, thread_id: str) -> dict:
        return self.app.get_state(self._config(thread_id)).values
