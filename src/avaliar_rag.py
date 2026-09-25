# Medição do pipeline RAG — Exercício 7, itens 3 e 4 do enunciado.
#
# Duas métricas SEPARADAS (nota 03 desta aula, §1-2), porque medi-las juntas
# impede o diagnóstico:
#   recall@k    -> a BUSCA trouxe o artigo certo? (não envolve o modelo)
#   fidelidade  -> a RESPOSTA se sustenta no que veio? (uma chamada extra,
#                  como o `PROMPT_FIDELIDADE` da nota 03 §1)
#
# Mais: taxa de citação verificável, taxa de recusa correta/indevida, e a
# varredura do limiar (item 3 do enunciado: "meça o limiar antes de
# escolher, rode com vários valores e olhe a curva dos dois erros").

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from agente import chamar_com_retry
from indice_rag import IndiceRAG
from rag import LIMIAR_PADRAO, MODELO, responder

CAMINHO_CASOS = Path(__file__).parent.parent / "dados" / "casos_rag.json"
CAMINHO_RELATORIO = Path(__file__).parent.parent / "logs" / "avaliar_rag.json"

PROMPT_FIDELIDADE = """Verifique se a RESPOSTA se sustenta integralmente nos \
TRECHOS fornecidos.

TRECHOS:
{contexto}

RESPOSTA:
{resposta}

Responda em JSON: {{"afirmacoes_sem_lastro": ["..."], "sustentada": true|false}}
Liste em `afirmacoes_sem_lastro` toda afirmação da RESPOSTA que não pode \
ser verificada nos TRECHOS. `sustentada` é true apenas se a lista estiver \
vazia. Não avalie se a resposta é boa; avalie apenas se ela está nos \
trechos."""


def medir_fidelidade(resposta_texto: str, trechos: list[dict]) -> dict:
    from rag import montar_contexto
    contexto = montar_contexto(trechos)
    prompt = PROMPT_FIDELIDADE.format(contexto=contexto, resposta=resposta_texto)
    r = chamar_com_retry(
        model=MODELO, temperature=0,
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": prompt}],
    )
    try:
        saida = json.loads(r.choices[0].message.content)
    except json.JSONDecodeError:
        saida = {"afirmacoes_sem_lastro": ["ERRO_PARSE_JUIZ"], "sustentada": False}
    saida.setdefault("sustentada", False)
    saida.setdefault("afirmacoes_sem_lastro", [])
    return saida


def recall_do_caso(caso: dict, ids_recuperados: list[str]) -> bool | None:
    esperados = caso.get("artigos_esperados", [])
    if not esperados:
        return None  # caso "sem_resposta" não tem recall — mede recusa, não busca
    if caso["tipo"] == "contradicao":
        return caso["artigo_vigente"] in ids_recuperados
    return all(e in ids_recuperados for e in esperados)  # multi_salto exige TODOS


def diagnostico(recall_ok: bool | None, fidelidade_ok: bool | None) -> str:
    if recall_ok is False:
        return "índice/chunking"
    if fidelidade_ok is False:
        return "prompt de resposta"
    if recall_ok is True and fidelidade_ok is True:
        return "ok (ou corpus, se a resposta ainda estiver errada — ver nota 03 §2)"
    return "—"


def varrer_limiar(k: int = 3, valores: list[float] | None = None) -> list[dict]:
    """A curva dos dois erros (item 3 do enunciado), medida SÓ com recuperação
    — sem gastar chamada de geração, porque o limiar decide antes dela.

    falso_positivo = responderia (score >= limiar) uma pergunta sem_resposta
    falso_negativo = recusaria (score <  limiar) uma pergunta que tinha resposta
    """
    valores = valores if valores is not None else [0.10, 0.15, 0.20, 0.25, 0.30,
                                                    0.35, 0.40, 0.45, 0.50, 0.55]
    indice = IndiceRAG()
    casos = json.loads(CAMINHO_CASOS.read_text(encoding="utf-8"))

    scores = []
    for caso in casos:
        trechos = indice.buscar(caso["pergunta"], k=k)
        melhor = max((t["score"] for t in trechos), default=0.0)
        scores.append({"id": caso["id"], "tipo": caso["tipo"], "score": melhor})

    linhas = []
    for limiar in valores:
        falsos_positivos = [s for s in scores
                             if s["tipo"] in ("sem_resposta", "fora_de_dominio")
                             and s["score"] >= limiar]
        falsos_negativos = [s for s in scores
                             if s["tipo"] not in ("sem_resposta", "fora_de_dominio")
                             and s["score"] < limiar]
        linhas.append({
            "limiar": limiar,
            "falsos_positivos": len(falsos_positivos),
            "falsos_positivos_ids": [s["id"] for s in falsos_positivos],
            "falsos_negativos": len(falsos_negativos),
            "falsos_negativos_ids": [s["id"] for s in falsos_negativos],
        })
    return linhas


def avaliar(k: int = 3, limiar: float = LIMIAR_PADRAO, pausa: float = 3.0) -> dict:
    indice = IndiceRAG()
    casos = json.loads(CAMINHO_CASOS.read_text(encoding="utf-8"))

    linhas = []
    for caso in casos:
        r = responder(caso["pergunta"], indice, k=k, limiar=limiar)
        ids_recuperados = r["trechos_recuperados"]
        recall_ok = recall_do_caso(caso, ids_recuperados)

        deveria_recusar = caso["tipo"] in ("sem_resposta", "fora_de_dominio")
        recusou = not r["suficiente"]

        fidelidade_ok = None
        afirmacoes_sem_lastro = []
        verif = {"inventadas": []}
        if not recusou:
            trechos_no_contexto = [c for c in indice.chunks
                                    if c["id"] in ids_recuperados]
            fid = medir_fidelidade(r["resposta"], trechos_no_contexto)
            fidelidade_ok = fid["sustentada"]
            afirmacoes_sem_lastro = fid["afirmacoes_sem_lastro"]
            verif = r.get("verificacao_citacao", {"inventadas": []})

        linhas.append({
            "id": caso["id"], "tipo": caso["tipo"], "pergunta": caso["pergunta"],
            "artigos_esperados": caso.get("artigos_esperados", []),
            "trechos_recuperados": ids_recuperados,
            "melhor_score": r["melhor_score"], "portao": r["portao"],
            "suficiente": r["suficiente"], "recusou": recusou,
            "deveria_recusar": deveria_recusar,
            "recusa_correta": (recusou == deveria_recusar),
            "recall_ok": recall_ok, "fidelidade_ok": fidelidade_ok,
            "afirmacoes_sem_lastro": afirmacoes_sem_lastro,
            "fontes_citadas": r["fontes"],
            "fontes_inventadas": verif.get("inventadas", []),
            "diagnostico": diagnostico(recall_ok, fidelidade_ok),
            "resposta": r["resposta"],
        })
        time.sleep(pausa)  # mesma cautela de rate limit do Ex.6 (docs/modelos.md §3.5)

    return montar_relatorio(linhas, k, limiar)


def montar_relatorio(linhas: list[dict], k: int, limiar: float) -> dict:
    com_recall = [l for l in linhas if l["recall_ok"] is not None]
    com_fidelidade = [l for l in linhas if l["fidelidade_ok"] is not None]
    respondidas = [l for l in linhas if not l["recusou"]]

    recall_pct = (sum(l["recall_ok"] for l in com_recall) / len(com_recall)
                  if com_recall else 0.0)
    fidelidade_pct = (sum(l["fidelidade_ok"] for l in com_fidelidade)
                       / len(com_fidelidade) if com_fidelidade else 0.0)
    citacoes_ok = sum(1 for l in respondidas if not l["fontes_inventadas"])
    citacoes_pct = citacoes_ok / len(respondidas) if respondidas else 0.0

    # "contradicao" é um terceiro caso, nem "deveria recusar" nem "não
    # deveria" no sentido binário: o comportamento correto é o portão
    # ACUSAR a contradição (recusando ou respondendo com as duas versões
    # explícitas) em vez de escolher uma em silêncio — ver modo de falha 4
    # em src/modos_de_falha.py e exercicios/aula-07-resposta-que-cita.md.
    # Por isso fica fora do denominador de recusa indevida.
    elegveis = [l for l in linhas if l["tipo"] != "contradicao"]
    recusas_corretas = [l for l in elegveis if l["deveria_recusar"] and l["recusa_correta"]]
    recusas_deveriam = [l for l in elegveis if l["deveria_recusar"]]
    recusas_indevidas = [l for l in elegveis if not l["deveria_recusar"] and l["recusou"]]
    nao_deveriam_recusar = [l for l in elegveis if not l["deveria_recusar"]]

    relatorio = {
        "k": k, "limiar": limiar, "modelo": MODELO,
        "n_perguntas": len(linhas),
        "recall_at_k_pct": round(recall_pct, 4),
        "citacoes_verificaveis_pct": round(citacoes_pct, 4),
        "fidelidade_pct": round(fidelidade_pct, 4),
        "recusas_corretas": f"{len(recusas_corretas)}/{len(recusas_deveriam)}",
        "recusas_indevidas": f"{len(recusas_indevidas)}/{len(nao_deveriam_recusar)}",
        "casos": linhas,
    }
    return relatorio


def imprimir(relatorio: dict) -> None:
    print("PIPELINE")
    print(f"  k={relatorio['k']}   limiar={relatorio['limiar']}   "
          f"modelo={relatorio['modelo']}\n")
    print(f"MÉTRICAS ({relatorio['n_perguntas']} perguntas)")
    print(f"  recall@k ................. {relatorio['recall_at_k_pct']:.0%}")
    print(f"  citações verificáveis .... {relatorio['citacoes_verificaveis_pct']:.0%}")
    print(f"  fidelidade ............... {relatorio['fidelidade_pct']:.0%}")
    print(f"  recusas corretas ......... {relatorio['recusas_corretas']}")
    print(f"  recusas indevidas ........ {relatorio['recusas_indevidas']}\n")
    print("DIAGNÓSTICO POR PERGUNTA")
    for l in relatorio["casos"]:
        r = "ok" if l["recall_ok"] else ("falhou" if l["recall_ok"] is False else "—")
        f = ("ok" if l["fidelidade_ok"] else
             ("falhou" if l["fidelidade_ok"] is False else "—"))
        print(f"  {l['id']:<4} recall {r:<6} fidelidade {f:<6} -> {l['diagnostico']}")


if __name__ == "__main__":
    print("VARREDURA DO LIMIAR (só recuperação, sem chamada de geração)")
    for linha in varrer_limiar():
        print(f"  limiar={linha['limiar']:.2f}  "
              f"FP={linha['falsos_positivos']} {linha['falsos_positivos_ids']}  "
              f"FN={linha['falsos_negativos']} {linha['falsos_negativos_ids']}")
    print()

    relatorio = avaliar()
    relatorio["varredura_limiar"] = varrer_limiar()
    imprimir(relatorio)
    CAMINHO_RELATORIO.parent.mkdir(exist_ok=True)
    CAMINHO_RELATORIO.write_text(
        json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nrelatório salvo em {CAMINHO_RELATORIO}")
