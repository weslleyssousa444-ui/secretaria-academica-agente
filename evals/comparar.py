# Compara duas rodadas, por classe, e imprime o relatório da §1.4 do enunciado.
#
#   python -m evals.comparar evals/resultados/<rodada-A> evals/resultados/<rodada-B>
#
# A comparação é PAREADA: só entram os casos que as duas rodadas avaliaram. Um
# caso que caiu por falha do provedor (`erro_fatal`) não é erro do agente, e
# excluí-lo de uma versão só distorceria o delta.
#
# A taxa de aprovação é a métrica do Exercício 11: decisão E resultado (estado
# do banco) E término normal, mais regimento e identidade onde o caso os pede.

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from evals.avaliadores import avaliar

RAIZ = Path(__file__).resolve().parents[1]


def carregar(caminho: Path) -> tuple[dict, dict]:
    pasta = caminho if caminho.is_dir() else caminho.parent
    arquivo = caminho / "execucoes.jsonl" if caminho.is_dir() else caminho
    registros = {}
    # Uma rodada que parou antes do primeiro caso (cota diária) existe, vazia.
    for linha in (arquivo.read_text(encoding="utf-8").splitlines() if arquivo.exists() else []):
        if linha.strip():
            r = json.loads(linha)
            registros[r["caso"]] = r   # o último vale (uma repetição pós-infra substitui a que caiu)
    meta = json.loads((pasta / "metadados.json").read_text(encoding="utf-8")) \
        if (pasta / "metadados.json").exists() else {}
    return registros, meta


def comparar(a: Path, b: Path, dataset: Path | None = None) -> dict:
    ra, meta_a = carregar(a)
    rb, meta_b = carregar(b)
    caminho_dataset = dataset or RAIZ / (meta_b.get("dataset", {}).get("arquivo") or "evals/dataset/golden_v1.2.0.json")
    ds = json.loads(caminho_dataset.read_text(encoding="utf-8"))
    casos = {c["id"]: c for c in ds["casos"]}
    avaliacao = {"A": {}, "B": {}}
    for chave, registros in (("A", ra), ("B", rb)):
        for id_, registro in registros.items():
            if id_ in casos:
                avaliacao[chave][id_] = avaliar(casos[id_], registro)
    infra = {k: sorted(i for i, v in avaliacao[k].items() if v["infra"]) for k in avaliacao}
    pareados = sorted(i for i in avaliacao["A"] if i in avaliacao["B"]
                      and not avaliacao["A"][i]["infra"] and not avaliacao["B"][i]["infra"])
    por_classe = defaultdict(lambda: {"A": [], "B": []})
    for i in pareados:
        for k in ("A", "B"):
            por_classe[casos[i]["classe"]][k].append(avaliacao[k][i]["aprovado"])
    taxa = lambda lista: 100.0 * sum(lista) / len(lista) if lista else float("nan")
    linhas = [(c, taxa(v["A"]), taxa(v["B"]), len(v["A"])) for c, v in sorted(por_classe.items())]
    todos = {k: [avaliacao[k][i]["aprovado"] for i in pareados] for k in ("A", "B")}
    mudaram = [(i, avaliacao["A"][i]["aprovado"], avaliacao["B"][i]["aprovado"]) for i in pareados
               if avaliacao["A"][i]["aprovado"] != avaliacao["B"][i]["aprovado"]]
    return {"dataset": ds, "meta": {"A": meta_a, "B": meta_b}, "classes": linhas,
            "media": (taxa(todos["A"]), taxa(todos["B"])), "n_pareados": len(pareados),
            "n_casos": len(casos), "infra": infra, "mudaram": mudaram,
            "escrita_indevida": {k: sorted(i for i, v in avaliacao[k].items() if v["escrita_indevida"]) for k in avaliacao},
            "acessos_a_terceiro": {k: sorted(i for i, v in avaliacao[k].items() if v["identidade"].get("acessos_a_terceiro")) for k in avaliacao},
            "avaliacao": avaliacao}


def imprimir(r: dict, a: Path, b: Path) -> str:
    ds = r["dataset"]
    origens = Counter(c["origem"] for c in ds["casos"])
    nome = lambda k, p: f"{k} = {p.name}"
    linhas = [f"DATASET v{ds['versao']}   {len(ds['casos'])} casos   "
              f"(producao {origens.get('producao', 0)} · desenvolvimento {origens.get('desenvolvimento', 0)} · "
              f"sintetico {origens.get('sintetico', 0)})",
              f"RODADAS   {nome('A', a)}   {nome('B', b)}   pareados: {r['n_pareados']}/{r['n_casos']}"]
    for k in ("A", "B"):
        m = r["meta"][k]
        if m:
            c = m.get("codigo", {})
            linhas.append(f"  {k}: código {c.get('ref')}@{c.get('commit')}"
                          f"{' (COM alterações não commitadas)' if c.get('alteracoes_nao_commitadas') else ''} · "
                          f"modelo {m.get('modelo')} · sessão autenticada: {m.get('sessao_autenticada')}")
        if r["infra"][k]:
            linhas.append(f"  {k}: {len(r['infra'][k])} caso(s) caíram por falha do provedor e saem da comparação: {', '.join(r['infra'][k])}")
    linhas += ["", f"{'classe':<14}{'versão A':>10}{'versão B':>10}{'delta':>9}   n"]
    for classe, ta, tb, n in r["classes"]:
        linhas.append(f"{classe:<14}{ta:>9.0f}%{tb:>9.0f}%{tb - ta:>+9.1f}   {n}")
    ma, mb = r["media"]
    linhas.append(f"{'MÉDIA':<14}{ma:>9.0f}%{mb:>9.0f}%{mb - ma:>+9.1f}   {r['n_pareados']}")
    linhas += ["", "ESCRITA INDEVIDA (documento onde o esperado era zero)   "
               f"A: {r['escrita_indevida']['A'] or 'nenhuma'}   B: {r['escrita_indevida']['B'] or 'nenhuma'}",
               "ACESSO A DADO DE TERCEIRO (caso de identidade)           "
               f"A: {r['acessos_a_terceiro']['A'] or 'nenhum'}   B: {r['acessos_a_terceiro']['B'] or 'nenhum'}"]
    if r["mudaram"]:
        linhas += ["", "CASOS QUE MUDARAM DE VEREDITO"] + [
            f"  {i:<6} A: {'aprovado' if x else 'reprovado':<9} -> B: {'aprovado' if y else 'reprovado'}" for i, x, y in r["mudaram"]]
    linhas += ["", "JUIZ: não adotado (docs/evals.md §3): a fidelidade é só informativa e NÃO entra neste número."]
    return "\n".join(linhas)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Compara duas rodadas da suíte")
    ap.add_argument("a", type=Path)
    ap.add_argument("b", type=Path)
    ap.add_argument("--dataset", type=Path)
    ap.add_argument("--salvar", type=Path, help="grava o relatório neste arquivo")
    args = ap.parse_args(argv)
    r = comparar(args.a, args.b, args.dataset)
    texto = imprimir(r, args.a, args.b)
    print(texto)
    if args.salvar:
        args.salvar.parent.mkdir(parents=True, exist_ok=True)
        args.salvar.write_text(texto + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
