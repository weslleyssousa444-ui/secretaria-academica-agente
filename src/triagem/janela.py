# Orçamento de janela da conversa (docs/memoria.md §5, "o que sai quando a
# janela enche").
#
# Cinco fontes disputam a janela do agente: o prompt de sistema, a memória, a
# conversa, os retornos de ferramenta e as declarações de ferramenta. Sem
# decisão, o provedor trunca — e trunca no fim, que é onde está o mais
# recente. A ORDEM DE DESCARTE aqui é decidida:
#
#   1. bloco de memória episódica        (mais volumoso, mais fácil de refazer;
#                                         tratado em memoria.py)
#   2. retornos de ferramenta ANTIGOS     (trocados por um marcador: a decisão
#                                         já foi tomada com eles; o que sai é
#                                         o texto, e a estrutura assistente/
#                                         ferramenta continua válida)
#   NUNCA: o prompt de sistema, a última mensagem do aluno e os retornos de
#   ferramenta dos últimos `manter_ultimas` itens.
#
# Perde-se: a possibilidade de o modelo reler um retorno antigo (por exemplo,
# o cadastro consultado três turnos atrás). Quem precisar dele chama a
# ferramenta de novo.

from __future__ import annotations

import json

LIMITE_TOKENS_JANELA = 6000
MARCADOR = json.dumps({"omitido": "retorno de ferramenta antigo removido pelo "
                                  "orçamento de janela"}, ensure_ascii=False)


def estimar_tokens(mensagem: dict) -> int:
    """~4 caracteres por token: serve ao orçamento, não à fatura."""
    return len(json.dumps(mensagem, ensure_ascii=False, default=str)) // 4


def compactar(mensagens: list[dict], limite: int = LIMITE_TOKENS_JANELA,
              manter_ultimas: int = 6) -> tuple[list[dict], int]:
    """Devolve (mensagens, quantos retornos foram omitidos). Não altera a
    lista recebida: a conversa completa continua no estado."""
    resultado = [dict(m) for m in mensagens]
    omitidos = 0
    candidatos = [i for i, m in enumerate(resultado[:-manter_ultimas] if manter_ultimas else resultado)
                  if m.get("role") == "tool"]
    for indice in candidatos:  # do mais antigo para o mais novo
        if sum(estimar_tokens(m) for m in resultado) <= limite:
            break
        if resultado[indice]["content"] != MARCADOR:
            resultado[indice]["content"] = MARCADOR
            omitidos += 1
    return resultado, omitidos
