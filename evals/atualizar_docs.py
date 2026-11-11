# Cola a saída REAL do comparador e das métricas nos blocos marcados dos documentos.
#
#   python -m evals.atualizar_docs --a evals/resultados/<A> --b evals/resultados/<B> \
#          --traces evals/resultados/<B>/traces.jsonl [--slo 0.95]
#
# Os blocos são `<!-- BLOCO:nome -->` ... `<!-- /BLOCO:nome -->`. O conteúdo entre
# eles é SUBSTITUÍDO por um bloco de código com a saída da ferramenta, mais a linha
# do comando que a produziu. Assim nenhum número dos documentos é digitado: ou vem
# da ferramenta, ou o bloco diz PENDENTE.

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from evals import comparar, metricas

RAIZ = Path(__file__).resolve().parents[1]


def substituir(texto: str, nome: str, conteudo: str) -> str:
    padrao = re.compile(rf"(<!-- BLOCO:{nome} -->)(.*?)(<!-- /BLOCO:{nome} -->)", re.DOTALL)
    if not padrao.search(texto):
        raise SystemExit(f"bloco '{nome}' não encontrado")
    return padrao.sub(lambda m: f"{m.group(1)}\n{conteudo}\n{m.group(3)}", texto, count=1)


def bloco(comando: str, saida: str) -> str:
    return f"```text\n$ {comando}\n{saida}\n```"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Atualiza os blocos de resultado dos documentos")
    ap.add_argument("--a", type=Path)
    ap.add_argument("--b", type=Path)
    ap.add_argument("--traces", nargs="*", type=Path)
    ap.add_argument("--slo", type=float)
    ap.add_argument("--evals", type=Path, default=RAIZ / "docs" / "evals.md")
    ap.add_argument("--observabilidade", type=Path, default=RAIZ / "docs" / "observabilidade.md")
    args = ap.parse_args(argv)

    if args.a and args.b:
        r = comparar.comparar(args.a, args.b)
        cmd = f"python -m evals.comparar {args.a} {args.b}"
        args.evals.write_text(substituir(args.evals.read_text(encoding="utf-8"), "comparacao",
                                         bloco(cmd, comparar.imprimir(r, args.a, args.b))), encoding="utf-8")
        print(f"{args.evals}: bloco 'comparacao' atualizado")
    if args.traces:
        saida = metricas.imprimir(metricas.metricas(metricas.carregar(args.traces)), args.slo)
        cmd = "python -m evals.metricas " + " ".join(str(t) for t in args.traces) + (f" --slo {args.slo}" if args.slo else "")
        args.observabilidade.write_text(substituir(args.observabilidade.read_text(encoding="utf-8"), "metricas",
                                                   bloco(cmd, saida.rstrip())), encoding="utf-8")
        print(f"{args.observabilidade}: bloco 'metricas' atualizado")
    return 0


if __name__ == "__main__":
    sys.exit(main())
