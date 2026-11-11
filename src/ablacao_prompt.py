# A "regra da frase" (docs/prompts.md §5): se uma frase sai do prompt e nada
# muda, ela não fazia nada. Este script remove UMA frase da regra 7 e roda o
# MESMO par de perguntas, contra o modelo real, com e sem a frase.
#
# A frase: "não responda com conhecimento próprio" (regra 7), que existe para
# impedir a resposta sobre o Regimento tirada da cabeça do modelo.
#
# Uso: python src/ablacao_prompt.py [prefixo-da-pergunta] [repeticoes]
#      (grava logs/parte2/ablacao-regra7.json)

from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parents[1]
load_dotenv(RAIZ / ".env")

import agente  # noqa: E402
import dados  # noqa: E402
from triagem import nos  # noqa: E402
from triagem.sistema import Sistema  # noqa: E402

FRASE = ("Se a ferramenta não devolver\n   artigo que trate do assunto, diga que o Regimento não trata disso e\n"
         "   ofereça encaminhar o caso à secretaria; não responda com conhecimento\n   próprio.")
SEM_A_FRASE = "Se a ferramenta não devolver\n   artigo que trate do assunto, ofereça encaminhar o caso à secretaria."

# As duas perguntas do conjunto do RAG cujo assunto o Regimento toca, mas cuja
# resposta ele NÃO tem (`s01`, `s02` de dados/casos_rag.json): a ferramenta
# devolve artigo de ruído, e é aí que a frase atua. Uma primeira tentativa com
# perguntas de fora do domínio ("mensalidade", "previsão do tempo") não
# exercitou a frase: o modelo recusou por escopo sem chamar a ferramenta
# (logs/parte2/ablacao-regra7-tentativa1-fora-de-dominio.json).
PERGUNTAS = {"s01-custo-da-segunda-via": "Quanto custa emitir a segunda via do histórico escolar?",
             "s02-prorrogacao": "Posso pedir prorrogação do trancamento por mais um semestre automaticamente?"}


def rodar(rotulo: str, prompt: str, chave: str, pergunta: str, repeticao: int = 1) -> dict:
    nos.SYSTEM = prompt
    with tempfile.TemporaryDirectory() as pasta:
        pasta = Path(pasta)
        dados.CAMINHO_DB = pasta / "a.db"
        dados.inicializar(forcar=True)
        s = Sistema(checkpoint=pasta / "cp.sqlite", memoria_dir=pasta / "mem")
        try:
            thread = f"ablacao-{rotulo}-{chave}-{repeticao}"
            r = s.conversar(thread, pergunta)
            estado = s.estado(thread)
            passos = estado["passos"]
        finally:
            s.fechar()
    return {"variante": rotulo, "pergunta": chave, "resposta": r["saida"]["resultado"],
            "decisao": r["saida"]["decisao"], "suficiente": r["saida"]["suficiencia"]["suficiente"],
            "ferramentas": [(p["ferramenta"], (p["resultado"] or {}).get("total")) for p in passos],
            "termino": r["termino"], "repeticao": repeticao,
            "validador": [e for e in estado["eventos"] if e.startswith("validar:")]}


def main() -> None:
    original = nos.SYSTEM
    assert FRASE in original, "a frase não está mais no prompt v2: atualize o script"
    variantes = {"com_a_frase": original, "sem_a_frase": original.replace(FRASE, SEM_A_FRASE)}
    prefixo = sys.argv[1] if len(sys.argv) > 1 else ""
    repeticoes = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    resultados = []
    for rotulo, prompt in variantes.items():
        for chave, pergunta in PERGUNTAS.items():
            if not chave.startswith(prefixo):
                continue
            for repeticao in range(1, repeticoes + 1):
                print(f"{rotulo} / {chave} / {repeticao} ...", flush=True)
                resultados.append(rodar(rotulo, prompt, chave, pergunta, repeticao))
                time.sleep(12)
    nos.SYSTEM = original
    saida = RAIZ / "logs" / "parte2" / "ablacao-regra7.json"
    saida.write_text(json.dumps({"modelo": agente.MODELO, "frase_removida": FRASE,
                                 "resultados": resultados}, ensure_ascii=False, indent=2), encoding="utf-8")
    for r in resultados:
        print(f"{r['variante']:<12} {r['pergunta']:<26} #{r['repeticao']} decisao={r['decisao']:<20} "
              f"suficiente={str(r['suficiente']):<5} validador={r['validador']} | {r['resposta'][:70]!r}")


if __name__ == "__main__":
    main()
