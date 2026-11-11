# Chat interativo com o sistema de triagem — para teste manual.
#
# Uso: python src/chat.py [--dica] [--trilha] [--ra 20231045] [--conversa ID]
#
#   --dica       mostra RAs de teste;
#   --trilha     imprime os nós que o grafo percorreu em cada turno;
#   --ra RA      simula a sessão autenticada do portal (`ra_autenticado`): só
#                com ela o sistema lê e grava a memória de longo prazo;
#   --conversa   retoma uma conversa pelo id (o checkpoint é um arquivo).
#
# Quando o pedido é um trancamento, o grafo PARA esperando a coordenação. O
# aluno já recebeu o protocolo; quem decide usa `python src/coordenacao.py`.
# Este chat não decide nada pela coordenação.

from __future__ import annotations

import sys
from uuid import uuid4

import dados
from triagem.nos import SAUDACAO_FIXA
from triagem.sistema import Sistema

DICAS_DE_TESTE = (
    "20231045 (ativa, sem pendência) · 20230198 (ativa, com pendência) · "
    "20221100 (trancada) · 20229012 (ativa, para testar trancamento) · "
    "20240000 (não existe)"
)
# A saudação é texto fixo do WIDGET, não uma chamada ao modelo — o sistema é
# reativo por desenho (docs/case.md §2.2: "quem começa: o aluno procura o
# sistema").


def argumento(nome: str) -> str | None:
    if nome in sys.argv:
        posicao = sys.argv.index(nome) + 1
        return sys.argv[posicao] if posicao < len(sys.argv) else None
    return None


def main() -> None:
    dados.inicializar()
    sistema = Sistema()
    conversa = argumento("--conversa") or uuid4().hex
    ra = argumento("--ra")
    print(f"agente: {SAUDACAO_FIXA}\n")
    if "--dica" in sys.argv:
        print(f"[dica de teste, não aparece num portal real — RAs: {DICAS_DE_TESTE}]\n")
    print(f"(digite 'sair' para encerrar · conversa {conversa}"
          f"{' · sessão autenticada de ' + ra if ra else ''})\n")
    try:
        while True:
            mensagem = input("você: ").strip()
            if mensagem.lower() in ("sair", "exit", "quit"):
                break
            if not mensagem:
                continue
            try:
                r = sistema.conversar(conversa, mensagem, ra)
            except ValueError as e:
                print(f"[{e}]\n")
                continue
            print(f"agente: {r['saida']['resultado']}")
            if r["aguardando_humano"]:
                print(f"[caso {r['saida']['protocolo']} aguardando a coordenação · "
                      f"use: python src/coordenacao.py listar]")
            if "--trilha" in sys.argv:
                trilha = sistema.estado(conversa).get("eventos", [])
                print(f"[nós: {' > '.join(trilha[-12:])}]")
            print()
            if r["termino"] != "respondeu":
                print(f"[conversa encerrada: {r['termino']} ({r['motivo']})]")
                break
    finally:
        sistema.fechar()


if __name__ == "__main__":
    main()
