# As métricas sobre execuções REAIS, lidas dos traces (docs/observabilidade.md §4).
#
#   python -m evals.metricas evals/resultados/<rodada>/traces.jsonl [mais arquivos]
#   python -m evals.metricas <traces...> --slo 0.95
#
# Tudo vem do trace: nenhuma métrica é recalculada de outro lugar. O corte é
# SEMPRE por `agente.versao`: um número que mistura versões soma sistemas
# diferentes.
#
# Percentil: posto mais próximo (nearest-rank). Com poucas execuções p95 é quase o
# máximo, e o relatório imprime o n junto, para ninguém ler p95 de 12 execuções
# como se fosse de mil.

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

TERMINOS_BONS = {"respondeu", "aguardando_humano"}


def carregar(arquivos: list[Path]) -> list[dict]:
    spans = []
    for arquivo in arquivos:
        spans += [json.loads(l) for l in arquivo.read_text(encoding="utf-8").splitlines() if l.strip()]
    return spans


def percentil(valores: list[float], p: float) -> float:
    if not valores:
        return float("nan")
    ordenados = sorted(valores)
    return ordenados[max(0, math.ceil(p / 100 * len(ordenados)) - 1)]


def execucoes(spans: list[dict]) -> list[dict]:
    """As raízes `invoke_agent` de TURNO (as retomadas da coordenação são outra coisa)."""
    return [s for s in spans if s["name"].startswith("invoke_agent") and s["parent_id"] is None
            and not s["attributes"].get("agente.retomada")]


def valida(raiz: dict) -> bool:
    """Execução VÁLIDA para o SLI: o sistema TENTOU decidir (chamou o modelo). A
    saudação, a espera já aberta e a recusa de identidade não entram."""
    a = raiz["attributes"]
    return (a.get("agente.chamadas_modelo", 0) or 0) >= 1 and a.get("agente.termino") != "recusado_identidade"


def boa(raiz: dict) -> bool:
    a = raiz["attributes"]
    return a.get("agente.termino") in TERMINOS_BONS and not a.get("agente.contingencia")


def metricas(spans: list[dict]) -> dict:
    por_trace = defaultdict(list)
    for s in spans:
        por_trace[s["trace_id"]].append(s)
    por_versao = defaultdict(list)
    for raiz in execucoes(spans):
        por_versao[raiz["attributes"].get("agente.versao", "sem-versao")].append(raiz)
    resultado = {}
    for versao, raizes in sorted(por_versao.items()):
        latencias = [(r["end_ns"] - r["start_ns"]) / 1e6 for r in raizes]
        tokens = [r["attributes"].get("agente.tokens_gastos", 0) or 0 for r in raizes]
        filhos = [f for r in raizes for f in por_trace[r["trace_id"]] if f["parent_id"] is not None]
        ferramentas = defaultdict(lambda: {"total": 0, "erros": 0, "recusadas": 0})
        for f in filhos:
            if f["name"].startswith("execute_tool"):
                nome = f["attributes"]["gen_ai.tool.name"]
                ferramentas[nome]["total"] += 1
                ferramentas[nome]["erros"] += f["status"] == "ERROR"
                ferramentas[nome]["recusadas"] += bool(f["attributes"].get("agente.ferramenta.recusada"))
        validas = [r for r in raizes if valida(r)]
        resultado[versao] = {
            "n": len(raizes), "latencia_p50_ms": percentil(latencias, 50), "latencia_p95_ms": percentil(latencias, 95),
            "tokens_medios": sum(tokens) / len(tokens) if tokens else 0.0, "tokens_p95": percentil(tokens, 95),
            "termino": Counter(r["attributes"].get("agente.termino") for r in raizes),
            "ferramentas": dict(ferramentas),
            "sli": {"validas": len(validas), "boas": sum(boa(r) for r in validas),
                    "valor": (sum(boa(r) for r in validas) / len(validas)) if validas else float("nan")},
        }
    return resultado


def imprimir(m: dict, slo: float | None = None) -> str:
    linhas = []
    for versao, v in m.items():
        sli = v["sli"]
        linhas += [f"VERSÃO {versao}   n = {v['n']} execuções", "",
                   f"  latência     p50 {v['latencia_p50_ms']:>8.0f} ms   p95 {v['latencia_p95_ms']:>8.0f} ms",
                   f"  tokens       média {v['tokens_medios']:>8.0f}   p95 {v['tokens_p95']:>8.0f}  "
                   "(custo em US$: 0 no free tier da Groq; ver docs/observabilidade.md §4.3)",
                   "  término      " + ", ".join(f"{k} {n} ({100 * n / v['n']:.0f}%)" for k, n in v["termino"].most_common()),
                   "  ferramentas  " + ("; ".join(f"{k} {d['erros']}/{d['total']} erro(s), {d['recusadas']} recusada(s)"
                                                  for k, d in sorted(v["ferramentas"].items())) or "nenhuma"),
                   f"  SLI de qualidade  {sli['boas']}/{sli['validas']} = {100 * sli['valor']:.1f}%"]
        if slo is not None and slo < 1 and sli["validas"]:
            consumido = (1 - sli["valor"]) / (1 - slo)  # fração do orçamento de erro já gasta
            linhas.append(f"  SLO >= {100 * slo:.0f}%        {'ATENDIDO' if sli['valor'] >= slo else 'VIOLADO'}   "
                          f"orçamento de erro consumido: {100 * consumido:.0f}% do permitido")
        linhas.append("")
    return "\n".join(linhas)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Métricas sobre os traces")
    ap.add_argument("traces", nargs="+", type=Path)
    ap.add_argument("--slo", type=float, help="alvo do SLI de qualidade (ex.: 0.95)")
    args = ap.parse_args(argv)
    print(imprimir(metricas(carregar(args.traces)), args.slo))
    return 0


if __name__ == "__main__":
    sys.exit(main())
