# Chunking do Regimento Acadêmico — corte por estrutura (Aula 06 nota 02):
# um chunk por artigo, porque a unidade natural do documento é o artigo, e
# ele já vem assim no dado de origem (dados/regimento_dados.py).
#
# O cabeçalho do capítulo é herdado dentro do texto do chunk (nota 00 desta
# aula, §5 item 5, e nota 04 §4): um artigo sozinho, sem saber a que
# capítulo pertence, ainda faz sentido para responder a maioria das
# perguntas deste corpus — mas o cabeçalho ajuda o modelo a não confundir,
# por exemplo, uma exceção do Capítulo IV com uma regra geral do Capítulo
# III quando os dois chegam juntos no contexto.

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "dados"))
from regimento_dados import REGIMENTO  # noqa: E402


def gerar_chunks(regimento: list[dict] | None = None) -> list[dict]:
    regimento = regimento if regimento is not None else REGIMENTO
    chunks = []
    for artigo in regimento:
        texto_com_cabecalho = f"[Capítulo {artigo['capitulo']}]\n{artigo['texto']}"
        chunks.append({
            "id": artigo["id"],
            "texto": texto_com_cabecalho,
            "capitulo": artigo["capitulo"],
            "vigente": artigo["vigente"],
            "data_vigencia": artigo["data_vigencia"],
        })
    return chunks


if __name__ == "__main__":
    chunks = gerar_chunks()
    vigentes = sum(1 for c in chunks if c["vigente"])
    print(f"{len(chunks)} chunks gerados ({vigentes} vigentes, "
          f"{len(chunks) - vigentes} revogado/histórico).")
    for c in chunks[:2]:
        print(f"\n--- {c['id']} ---\n{c['texto']}")
