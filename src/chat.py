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

SAUDACAO = (
    "Olá! Sou o assistente da secretaria acadêmica. Posso ajudar com "
    "declaração de matrícula, segunda via de histórico ou trancamento de "
    "matrícula. Como posso te ajudar?"
)
# A saudação é texto fixo do WIDGET, não uma chamada ao modelo — o sistema é
# reativo por desenho (docs/case.md §2.2: "quem começa: o aluno procura o
# sistema"); é a mesma distinção da nota 01 de Aula 10 entre o que a
# APLICAÇÃO decide mostrar e o que o MODELO decide.

DICAS_DE_TESTE = (
    "20231045 (ativa, sem pendência) · 20230198 (ativa, com pendência) · "
    "20221100 (trancada) · 20240000 (não existe)"
)

if __name__ == "__main__":
    import sys

    dados.inicializar()
    print(f"agente: {SAUDACAO}\n")
    if "--dica" in sys.argv:
        print(f"[dica de teste, não aparece num portal real — RAs: "
              f"{DICAS_DE_TESTE}]\n")
    print("(digite 'sair' para encerrar; rode com --dica para ver RAs de "
          "teste)\n")

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
