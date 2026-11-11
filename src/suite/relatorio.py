# Relatório da suíte (Exercício 11): lê as execuções gravadas por executor.py,
# aplica os avaliadores, a validação do juiz e a REGRA DE PROMOÇÃO escrita em
# dados/regra_de_promocao.json antes de qualquer execução, e imprime a saída
# pedida pelo enunciado. Não chama modelo.
#
# Uso: python src/suite/relatorio.py            (aceita execuções parciais)
#
# Execução ausente nunca é preenchida: sem A1, A2, B1 e B2 a decisão sai
# "NÃO CONCLUÍDA", e o que falta é dito.

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter, OrderedDict
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from avaliadores import avaliar  # noqa: E402
from juiz import MODELO_DO_JUIZ, RUBRICA_VERSAO  # noqa: E402

GOLDEN = RAIZ / "dados" / "golden_v1.json"
REGRA = RAIZ / "dados" / "regra_de_promocao.json"
ROTULOS = RAIZ / "dados" / "rotulos_juiz_v1.json"
DESACORDOS = RAIZ / "dados" / "desacordos_juiz_v1.json"
PASTA = RAIZ / "logs" / "suite"
EXECUCOES = ["A1", "A2", "B1", "B2"]
PISO_PP = 5.0
LIMIAR_CONCORDANCIA, LIMIAR_RECALL_NAO_FIEL = 85.0, 80.0


def carregar_execucao(nome: str, casos: dict) -> dict[str, dict] | None:
    arquivo = PASTA / f"exec-{nome[0]}-r{nome[1:]}.jsonl"
    if not arquivo.exists():
        return None
    registros = {}
    for linha in arquivo.read_text(encoding="utf-8").splitlines():
        if linha.strip():
            r = json.loads(linha)
            registros[r["caso"]] = r          # o último registro do caso vence (refeito após erro_fatal)
    return {cid: avaliar(casos[cid], r) for cid, r in registros.items()}


def taxa(avaliacoes: dict[str, dict], classe: str | None = None) -> tuple[float, int] | None:
    validas = [a for a in avaliacoes.values()
               if not a["infra"] and (classe is None or a["classe"] == classe)]
    if not validas:
        return None
    return 100 * sum(a["aprovado"] for a in validas) / len(validas), len(validas)


def pass2(ex1: dict, ex2: dict, classe: str | None = None) -> float | None:
    ids = [c for c in ex1 if c in ex2 and (classe is None or ex1[c]["classe"] == classe)]
    if not ids:
        return None
    return 100 * sum(ex1[c]["aprovado"] and ex2[c]["aprovado"] for c in ids) / len(ids)


def validacao_do_juiz(versao: str = RUBRICA_VERSAO, conjunto: str | None = None) -> dict | None:
    """`conjunto`: None = todos os rótulos; "holdout" = só os de A2/B2 (escritos depois da revisão da rubrica);
    "insample" = os de A1/B1, que orientaram a revisão."""
    arquivo = PASTA / f"juiz-v{versao}.jsonl"
    if not ROTULOS.exists() or not arquivo.exists():
        return None
    juiz = {(j["execucao"], j["caso"]): j for j in map(json.loads, arquivo.read_text(encoding="utf-8").splitlines()) if j}
    rotulos = json.loads(ROTULOS.read_text(encoding="utf-8"))["rotulos"]
    if conjunto:
        rotulos = [r for r in rotulos if (r.get("conjunto") == "holdout") == (conjunto == "holdout")]
    pares = [(r, juiz[(r["execucao"], r["caso"])]) for r in rotulos if (r["execucao"], r["caso"]) in juiz]
    if not pares:
        return None
    m = Counter((j["fiel"], r["fiel"]) for r, j in pares)   # (juiz, humano)
    n = len(pares)
    humano_nao = m[(True, False)] + m[(False, False)]
    concord = 100 * (m[(True, True)] + m[(False, False)]) / n
    recall = 100 * m[(False, False)] / humano_nao if humano_nao else float("nan")
    desacordos = [(r, j) for r, j in pares if r["fiel"] != j["fiel"]]
    classificacao = {}
    if DESACORDOS.exists():
        for lida in json.loads(DESACORDOS.read_text(encoding="utf-8"))["leituras"]:
            if lida["rubrica"] == versao:    # a leitura vale para a rubrica que a gerou
                classificacao = {(d["execucao"], d["caso"]): d["classe"] for d in lida["desacordos"]}
    return {"n": n, "m": m, "concordancia": concord, "recall_nao_fiel": recall,
            "adotar": concord >= LIMIAR_CONCORDANCIA and recall >= LIMIAR_RECALL_NAO_FIEL,
            "desacordos": desacordos, "classificacao": classificacao, "juiz": juiz}


def fidelidade(nome: str, validacao: dict) -> float | None:
    julgados = [j for (e, _), j in validacao["juiz"].items() if e == nome]
    return 100 * sum(j["fiel"] for j in julgados) / len(julgados) if julgados else None


def carimbo(gold: dict) -> list[tuple[str, str]]:
    sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()[:12]
    return [
        ("prompt", f"src/prompts/triagem-v1.txt (sha256 {sha(RAIZ / 'src' / 'prompts' / 'triagem-v1.txt')})"),
        ("modelo do agente", "A: qwen/qwen3.8-27b · B: openai/gpt-oss-20b (Groq)"),
        ("parâmetros de amostragem", "temperature=0; sem top_p/seed (a API da Groq não garante determinismo)"),
        ("orçamento por conversa", "max_passos=8 · max_tokens=20000 · max_reais=0.05 (src/agente.py)"),
        ("arquitetura", "laço de ferramentas de um agente + pós-condição L02 em código (trancamento)"),
        ("ferramentas", "buscar_aluno, consultar_financeiro, emitir_documento, escalar_para_humano"),
        ("índice (RAG)", "NÃO USA — o agente de triagem não consulta o Regimento"),
        ("modelo de embedding", "NÃO USA — sem RAG no agente"),
        ("estado da memória", "NÃO USA — memória existe como subsistema (src/memoria*.py), não ligada ao laço"),
        ("framework", "laço próprio em src/agente.py (LangGraph só no Ex.9, fora desta suíte)"),
        ("servidor MCP", "NÃO USA — nenhuma ferramenta passa por MCP"),
        ("versão do dataset", f"golden_v{gold['versao']} (sha256 {sha(GOLDEN)}) · estado do mundo: SQLite novo por execução"),
        ("versão da rubrica do juiz", f"v{RUBRICA_VERSAO} · juiz {MODELO_DO_JUIZ} · critério binário"),
    ]


def imprimir_carimbo(gold: dict) -> None:
    print("\nCARIMBO")
    for campo, valor in carimbo(gold):
        print(f"  {campo:<28}{valor}")


def main() -> int:
    gold = json.loads(GOLDEN.read_text(encoding="utf-8"))
    casos = {c["id"]: c for c in gold["casos"]}
    regra = json.loads(REGRA.read_text(encoding="utf-8"))
    classes = list(OrderedDict.fromkeys(c["classe"] for c in gold["casos"]))
    criticas = set(gold["classes_criticas"])

    print(f"DATASET v{gold['versao']}   {len(casos)} casos")
    por_origem = Counter(c["origem"] for c in casos.values())
    print("  por origem:   " + "   ".join(f"{o} {por_origem.get(o, 0)}" for o in ("producao", "desenvolvimento", "sintetico")))
    por_classe = Counter(c["classe"] for c in casos.values())
    print("  por classe:   " + "  ".join(f"{c} {por_classe[c]}" for c in classes))

    versoes = sorted(p.stem.removeprefix("juiz-v") for p in PASTA.glob("juiz-v*.jsonl")) or [RUBRICA_VERSAO]
    v = None
    blocos = [(vs, None) for vs in versoes if vs != RUBRICA_VERSAO] + [
        (RUBRICA_VERSAO, "insample"), (RUBRICA_VERSAO, "holdout")]
    for versao, conjunto in blocos:
        vv = validacao_do_juiz(versao, conjunto)
        nome = {None: "", "insample": " — mesmos casos que orientaram a revisão (otimista)",
                "holdout": " — HOLD-OUT: rotulado depois da revisão"}[conjunto]
        print(f"\nVALIDAÇÃO DO JUIZ (rubrica v{versao}){nome}")
        if vv is None:
            print("  PENDENTE: faltam rótulos (dados/rotulos_juiz_v1.json) ou veredictos do juiz.")
            continue
        m = vv["m"]
        print("                    humano: fiel   humano: não fiel   (rótulos provisórios)")
        print(f"    juiz: fiel        {m[(True, True)]:>6}          {m[(True, False)]:>6}")
        print(f"    juiz: não fiel    {m[(False, True)]:>6}          {m[(False, False)]:>6}")
        veredito = "adotar" if vv["adotar"] else "não"
        print(f"  n={vv['n']}  concordância: {vv['concordancia']:.0f}%  recall de 'não fiel': {vv['recall_nao_fiel']:.0f}%  "
              f"limiar declarado: {LIMIAR_CONCORDANCIA:.0f}% e {LIMIAR_RECALL_NAO_FIEL:.0f}%   VEREDITO: {veredito}")
        c = Counter(vv["classificacao"].get((r["execucao"], r["caso"]), "não lido") for r, _ in vv["desacordos"])
        print(f"  desacordos: {len(vv['desacordos'])}  (juiz {c['juiz']} · rubrica {c['rubrica']} · rótulo {c['rótulo']}"
              f"{' · não classificados ' + str(c['não lido']) if c['não lido'] else ''})")
        if versao == RUBRICA_VERSAO and conjunto == "holdout":
            v = vv   # só o hold-out pode decidir a adoção

    ex = {n: carregar_execucao(n, casos) for n in EXECUCOES}
    ausentes = [n for n, e in ex.items() if e is None or len(e) < len(casos)]
    print("\nRUÍDO DE BASE")
    ta = [taxa(ex[n]) if ex[n] else None for n in ("A1", "A2")]
    if None in ta or "A1" in ausentes or "A2" in ausentes:
        print(f"  versão A, execuções: {', '.join('%.1f%%' % t[0] if t else 'ausente' for t in ta)}   "
              "dispersão: NÃO MEDIDA (falta execução ou execução incompleta)")
        ruido = None
    else:
        ruido = abs(ta[0][0] - ta[1][0])
        print(f"  versão A, execuções: {ta[0][0]:.1f}%, {ta[1][0]:.1f}%   dispersão: {ruido:.1f} pontos")

    print("\nSUÍTE (taxa de aprovação = decisão ∧ resultado; média das execuções)")
    print(f"  {'classe':<14}{'A':>8}{'B':>8}{'delta':>8}   pass^2 A / B")

    def media(versao, classe=None):
        ts = [taxa(ex[f"{versao}{i}"], classe) for i in (1, 2) if ex[f"{versao}{i}"]]
        ts = [t for t in ts if t]
        return sum(t[0] for t in ts) / len(ts) if ts else None

    def p2(versao, classe=None):
        e1, e2 = ex[f"{versao}1"], ex[f"{versao}2"]
        return pass2(e1, e2, classe) if e1 and e2 else None

    fmt = lambda x: f"{x:.0f}%" if x is not None else "  —"
    linhas = {}
    for classe in classes + [None]:
        a, b = media("A", classe), media("B", classe)
        linhas[classe] = (a, b)
        d = f"{b - a:+.1f}" if a is not None and b is not None else "  —"
        print(f"  {(classe or 'MÉDIA'):<14}{fmt(a):>8}{fmt(b):>8}{d:>8}   {fmt(p2('A', classe))} / {fmt(p2('B', classe))}")

    print("\nTRAJETÓRIA e TEXTO (fração de execuções que cumprem; não entram na decisão)")
    for nome in EXECUCOES:
        if not ex[nome]:
            continue
        av = [a for a in ex[nome].values() if not a["infra"]]
        if not av:
            continue
        print(f"  {nome}: n={len(av)}  cobertura completa {100*sum(a['trajetoria']['cobertura']==1 for a in av)/len(av):.0f}%  "
              f"sem supérfluas {100*sum(a['trajetoria']['superfluas']==0 for a in av)/len(av):.0f}%  "
              f"ordem {100*sum(a['trajetoria']['ordem_ok'] for a in av)/len(av):.0f}%  "
              f"texto {100*sum(a['texto']['ok'] for a in av)/len(av):.0f}%  "
              f"infra {sum(a['infra'] for a in ex[nome].values())}")

    print("\nDECISÃO")
    if ausentes:
        faltam = ", ".join(f"{n} ({'ausente' if ex[n] is None else str(len(ex[n])) + '/' + str(len(casos))})" for n in ausentes)
        print(f"  NÃO CONCLUÍDA — execuções incompletas: {faltam}")
        print("  regra aplicada: nenhuma (a regra não é aplicada a execução parcial).")
        imprimir_carimbo(gold)
        return 0
    delta = linhas[None][1] - linhas[None][0]
    minimo = max(2 * ruido, PISO_PP)
    r1 = delta >= minimo
    r2 = all(linhas[c][1] >= linhas[c][0] and (p2("B", c) or 0) >= (p2("A", c) or 0) for c in criticas)
    r3 = all(linhas[c][1] - linhas[c][0] >= -10 for c in classes if c not in criticas)
    r4 = not any(a["escrita_indevida"] for n in ("B1", "B2") for a in ex[n].values())
    r5 = None
    if v and v["adotar"]:
        r5 = (fidelidade("B1", v) + fidelidade("B2", v)) / 2 >= (fidelidade("A1", v) + fidelidade("A2", v)) / 2 - 5
    marca = lambda ok: "ATENDIDA" if ok else "VIOLADA"
    print(f"  R1 delta {delta:+.1f} pp  vs  mínimo max(2×ruído={2*ruido:.1f}, {PISO_PP:.0f}) = {minimo:.1f} pp: {marca(r1)}")
    print(f"  R2 classes críticas ({', '.join(sorted(criticas))}) sem queda, inclusive pass^2: {marca(r2)}")
    print(f"  R3 demais classes com queda ≤ 10 pp: {marca(r3)}")
    print(f"  R4 nenhuma escrita indevida em B: {marca(r4)}")
    print(f"  R5 fidelidade: {'não aplicável (juiz não adotado ou sem validação)' if r5 is None else marca(r5)}")
    promover = r1 and r2 and r3 and r4 and (r5 is not False)
    print(f"  DECISÃO: {'promover' if promover else 'não promover'}")
    print(f"  regra aplicada: dados/regra_de_promocao.json v{regra['versao']}, declarada em {regra['declarada_em']}")
    imprimir_carimbo(gold)
    return 0


if __name__ == "__main__":
    sys.exit(main())
