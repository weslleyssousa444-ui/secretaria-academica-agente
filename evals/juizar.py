# Roda o juiz de FIDELIDADE (src/suite/juiz.py, rubrica v1.1.0) sobre uma rodada.
#
#   python -m evals.juizar --rodada evals/resultados/<rodada> [--casos id01,rg01]
#
# Grava `veredictos_juiz.jsonl` NA PASTA DA RODADA, com a `chave` que a ficha de
# rotulagem humana usa (`<rodada>:<caso>`). O juiz é `openai/gpt-oss-120b`, outro
# modelo e outra cota que o agente. O juiz NÃO está adotado (docs/evals.md §3): o
# veredito é informativo e não entra na taxa de aprovação.
#
# A política mostrada ao juiz é o prompt do sistema sob avaliação (v2).

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from evals.avaliadores import RAIZ  # também prepara o sys.path e a chave de import

from suite import juiz  # noqa: E402

POLITICA = RAIZ / "src" / "prompts" / "triagem-v2.txt"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Juiz de fidelidade sobre uma rodada")
    ap.add_argument("--rodada", required=True, type=Path)
    ap.add_argument("--casos")
    ap.add_argument("--dataset", type=Path, default=RAIZ / "evals" / "dataset" / "golden_v1.2.0.json")
    args = ap.parse_args(argv)

    casos = {c["id"]: c for c in json.loads(args.dataset.read_text(encoding="utf-8"))["casos"]}
    registros = {}
    for linha in (args.rodada / "execucoes.jsonl").read_text(encoding="utf-8").splitlines():
        if linha.strip():
            r = json.loads(linha)
            registros[r["caso"]] = r
    pedidos = set(args.casos.split(",")) if args.casos else None
    saida = args.rodada / "veredictos_juiz.jsonl"
    feitos = {json.loads(l)["caso"] for l in saida.read_text(encoding="utf-8").splitlines() if l.strip()} if saida.exists() else set()

    for id_, registro in registros.items():
        if registro["termino"] != "respondeu" or id_ in feitos or (pedidos and id_ not in pedidos):
            continue
        try:
            v = juiz.julgar(casos[id_], registro, politica_arquivo=POLITICA)
        except juiz.CotaDiaria as e:
            print(f"PARADO: cota diária do juiz esgotada ({str(e)[:120]})")
            return 3
        with saida.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"chave": f"{args.rodada.name}:{id_}", "caso": id_, "rodada": args.rodada.name,
                                "rubrica": juiz.RUBRICA_VERSAO, "juiz": juiz.MODELO_DO_JUIZ, **v}, ensure_ascii=False) + "\n")
        print(f"{id_:<6} fiel={v['fiel']}  ({v['tokens']} tokens)", flush=True)
        time.sleep(v["tokens"] / 6000 * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
