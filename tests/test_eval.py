# Eval do portão de CI — Exercício 13. Chama o MODELO REAL: custa tokens e
# só roda com `pytest -m eval` e uma OPENAI_API_KEY de verdade (no CI, o
# secret GROQ_API_KEY). Sem chave, é pulado, e não reprovado.
#
# Seis casos de dados/casos_verificador.json, um ou dois por fatia, fora da
# série `p` (lacuna conhecida do conjunto de teste, model card §8). Dois
# critérios, declarados antes de rodar:
#   1. trancamento: 2/2 — a categoria sem tolerância (docs/case.md §2.7);
#   2. total: >= 5/6.
# Poder do critério 2 (binomial, casos independentes): com acerto real
# q = 0,97 — o medido fora da série p, 33/34 — passa com P ~ 0,99; com
# q = 0,70 ainda passa com P ~ 0,42. Detecta regressão grosseira, não
# distingue versões próximas (docs/empacotamento.md §6).

from __future__ import annotations

import json
import os
import time

import pytest

from agente import Estado, Orcamento, conversar
from conftest import RAIZ
from verificador import classificar_decisao

CASOS = ["d01", "s01", "v01", "t01", "t05", "r01"]
MINIMO = 5

pytestmark = [
    pytest.mark.eval,
    pytest.mark.skipif(os.environ.get("OPENAI_API_KEY", "teste-offline-sem-rede")
                       == "teste-offline-sem-rede", reason="sem OPENAI_API_KEY real"),
]


def test_eval_taxa_minima(banco):
    todos = json.loads((RAIZ / "dados" / "casos_verificador.json").read_text(encoding="utf-8"))
    casos = [c for c in todos if c["id"] in CASOS]
    resultados = {}
    for caso in casos:
        estado, orcamento = Estado(caso=caso["id"]), Orcamento()
        for mensagem in caso["mensagens"]:
            estado = conversar(estado, mensagem, orcamento, verboso=False)
            if estado.termino is not None and estado.termino.value != "respondeu":
                break
        resultados[caso["id"]] = (caso["decisao_esperada"], classificar_decisao(estado))
        time.sleep(8)  # teto de tokens/min do free tier (docs/modelos.md §3.5)

    print("\n" + "\n".join(f"{i}: esperado={e} obtido={o}" for i, (e, o) in resultados.items()))
    acertos = sum(e == o for e, o in resultados.values())
    trancamento = [(e, o) for e, o in resultados.values() if e == "escalar_trancamento"]
    assert all(e == o for e, o in trancamento), f"falso negativo em trancamento: {resultados}"
    assert acertos >= MINIMO, f"{acertos}/{len(casos)} < {MINIMO}: {resultados}"
