# Chat interativo com o agente de triagem — para teste manual.
#
# Uso: python src/chat.py
#
# Diferente de demo.py/verificador.py (casos fixos), aqui é você quem
# digita. Reaproveita o mesmo `conversar()` do agente (src/agente.py) —
# nenhuma lógica nova, só o laço de entrada/saída que faltava.

from __future__ import annotations

import dados
from agente import Estado, Orcamento, conversar, resumo

if __name__ == "__main__":
    dados.inicializar()
    print("Agente de triagem da secretaria acadêmica — digite sua mensagem "
          "(ou 'sair' para encerrar)\n")
    print("RAs de teste: 20231045 (ativa, sem pendência) · 20230198 "
          "(ativa, com pendência) · 20221100 (trancada) · 20240000 "
          "(não existe)\n")

    estado = Estado(caso="chat-interativo")
    orcamento = Orcamento()

    while True:
        mensagem = input("você: ").strip()
        if mensagem.lower() in ("sair", "exit", "quit"):
            break
        if not mensagem:
            continue

        estado = conversar(estado, mensagem, orcamento, verboso=True)

        if estado.termino is not None and estado.termino.value != "respondeu":
            print(f"\n[{resumo(estado)}]")
            break
