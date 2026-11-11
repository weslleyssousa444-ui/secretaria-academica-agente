# A validação do juiz contra rótulo HUMANO (docs/evals.md §3).
#
#   python -m evals.rotulagem preparar --rodada evals/resultados/<a> [--rodada <b>] -n 20
#   (a pessoa preenche `rotulo_humano` e `nota_humana` em evals/rotulagem/para_rotular.csv)
#   python -m evals.rotulagem medir --rotulos evals/rotulagem/para_rotular.csv \
#                                   --veredictos evals/resultados/<a>/veredictos_juiz.jsonl [...]
#
# POR QUE ISTO EXISTE: os 75 rótulos do Exercício 11 foram dados por um
# assistente de IA, e não por uma pessoa (docs/evals.md §3). Eles medem a
# concordância do juiz com uma segunda leitura, feita por modelo, da mesma rubrica;
# não provam que o juiz está certo. O enunciado pede vinte saídas rotuladas À MÃO,
# com uma nota escrita por caso. Este módulo prepara a ficha e mede o resultado
# quando o grupo a preencher. Ele NÃO preenche rótulo nenhum.
#
# Para não enviesar, o veredito do juiz NÃO está na ficha: quem rotula não o vê.

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
PASTA = RAIZ / "evals" / "rotulagem"
CAMPOS = ["chave", "caso", "classe", "mensagens_do_aluno", "retornos_das_ferramentas",
          "resposta_do_agente", "rotulo_humano", "nota_humana", "rotulador"]
ROTULOS = {"fiel": True, "nao_fiel": False}
LIMIARES = {"concordancia": 0.85, "recall_nao_fiel": 0.80}   # os do Exercício 11, declarados antes de medir


def preparar(rodadas: list[Path], n: int, semente: int, dataset: Path, saida: Path) -> int:
    casos = {c["id"]: c for c in json.loads(dataset.read_text(encoding="utf-8"))["casos"]}
    candidatos = []
    for rodada in rodadas:
        ultimo = {}
        for linha in (rodada / "execucoes.jsonl").read_text(encoding="utf-8").splitlines():
            if linha.strip():
                r = json.loads(linha)
                ultimo[r["caso"]] = r
        candidatos += [(rodada, r) for r in ultimo.values() if r["termino"] == "respondeu" and r["respostas"] and r["passos"]]
    escolhidos = random.Random(semente).sample(candidatos, min(n, len(candidatos)))
    saida.parent.mkdir(parents=True, exist_ok=True)
    with saida.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS)
        w.writeheader()
        for rodada, r in escolhidos:
            caso = casos[r["caso"]]
            w.writerow({
                "chave": f"{rodada.name}:{r['caso']}", "caso": r["caso"], "classe": caso["classe"],
                "mensagens_do_aluno": " | ".join(caso["mensagens"]),
                "retornos_das_ferramentas": json.dumps([{"ferramenta": p["ferramenta"], "argumentos": p["argumentos"],
                                                         "retorno": p["resultado"]} for p in r["passos"]], ensure_ascii=False),
                "resposta_do_agente": r["respostas"][-1], "rotulo_humano": "", "nota_humana": "", "rotulador": ""})
    print(f"{len(escolhidos)} saídas em {saida}. Preencha `rotulo_humano` (fiel | nao_fiel), `nota_humana` e `rotulador`.")
    return 0


def matriz(pares: list[tuple[bool, bool]]) -> dict:
    """pares = (juiz_fiel, humano_fiel). Positivo = 'não fiel': é o que o juiz existe para achar."""
    vp = sum(1 for j, h in pares if not j and not h)   # juiz: não fiel / humano: não fiel
    fp = sum(1 for j, h in pares if not j and h)       # juiz: não fiel / humano: fiel
    fn = sum(1 for j, h in pares if j and not h)       # juiz: fiel / humano: não fiel
    vn = sum(1 for j, h in pares if j and h)
    n = len(pares)
    return {"n": n, "juiz_fiel_humano_fiel": vn, "juiz_fiel_humano_nao": fn, "juiz_nao_humano_fiel": fp,
            "juiz_nao_humano_nao": vp, "concordancia": (vp + vn) / n if n else float("nan"),
            "recall_nao_fiel": vp / (vp + fn) if (vp + fn) else float("nan"),
            "precisao_nao_fiel": vp / (vp + fp) if (vp + fp) else float("nan")}


def medir(rotulos: Path, veredictos: list[Path], desacordos: Path) -> dict:
    humano = {}
    sem_rotulo = []
    with rotulos.open(encoding="utf-8", newline="") as f:
        for linha in csv.DictReader(f):
            if linha["rotulo_humano"].strip() not in ROTULOS:
                sem_rotulo.append(linha["chave"])
            else:
                humano[linha["chave"]] = (ROTULOS[linha["rotulo_humano"].strip()], linha)
    if sem_rotulo:
        raise SystemExit(f"{len(sem_rotulo)} saída(s) sem rótulo humano válido (fiel | nao_fiel): {sem_rotulo[:5]}...")
    juiz = {}
    for arquivo in veredictos:
        for l in arquivo.read_text(encoding="utf-8").splitlines():
            if l.strip():
                v = json.loads(l)
                juiz[v["chave"]] = v
    faltam = sorted(set(humano) - set(juiz))
    if faltam:
        raise SystemExit(f"{len(faltam)} saída(s) rotulada(s) sem veredito do juiz (rode evals.juizar): {faltam[:5]}...")
    pares = [(juiz[k]["fiel"], humano[k][0]) for k in humano]
    m = matriz(pares)
    discordam = [(k, juiz[k], humano[k][1]) for k in humano if juiz[k]["fiel"] != humano[k][0]]
    with desacordos.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["chave", "juiz_fiel", "nota_do_juiz", "humano_fiel", "nota_humana", "defeito_de (juiz | rubrica | rotulo)", "leitura"])
        for k, v, linha in discordam:
            w.writerow([k, v["fiel"], v.get("nota", ""), humano[k][0], linha["nota_humana"], "", ""])
    m["adotado"] = m["concordancia"] >= LIMIARES["concordancia"] and m["recall_nao_fiel"] >= LIMIARES["recall_nao_fiel"]
    m["desacordos"] = len(discordam)
    return m


def imprimir(m: dict) -> str:
    return "\n".join([
        f"                    humano: fiel   humano: não fiel",
        f"    juiz: fiel      {m['juiz_fiel_humano_fiel']:>10}   {m['juiz_fiel_humano_nao']:>14}",
        f"    juiz: não fiel  {m['juiz_nao_humano_fiel']:>10}   {m['juiz_nao_humano_nao']:>14}",
        f"  n={m['n']}  concordância: {100 * m['concordancia']:.0f}%  recall de 'não fiel': {100 * m['recall_nao_fiel']:.0f}%  "
        f"precisão: {100 * m['precisao_nao_fiel']:.0f}%  limiar declarado: {100 * LIMIARES['concordancia']:.0f}% e {100 * LIMIARES['recall_nao_fiel']:.0f}%  "
        f"VEREDITO: {'adotar' if m['adotado'] else 'não adotar'}",
        f"  desacordos: {m['desacordos']} (classifique cada um em desacordos.csv: defeito do juiz, da rubrica ou do rótulo)"])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Ficha de rotulagem humana e medição do juiz")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("preparar")
    p.add_argument("--rodada", action="append", required=True, type=Path)
    p.add_argument("-n", type=int, default=20)
    p.add_argument("--semente", type=int, default=7)
    p.add_argument("--dataset", type=Path, default=RAIZ / "evals" / "dataset" / "golden_v1.2.0.json")
    p.add_argument("--saida", type=Path, default=PASTA / "para_rotular.csv")
    m = sub.add_parser("medir")
    m.add_argument("--rotulos", type=Path, default=PASTA / "para_rotular.csv")
    m.add_argument("--veredictos", action="append", required=True, type=Path)
    m.add_argument("--desacordos", type=Path, default=PASTA / "desacordos.csv")
    args = ap.parse_args(argv)
    if args.cmd == "preparar":
        return preparar(args.rodada, args.n, args.semente, args.dataset, args.saida)
    print(imprimir(medir(args.rotulos, args.veredictos, args.desacordos)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
