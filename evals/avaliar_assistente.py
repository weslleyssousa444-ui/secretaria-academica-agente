# Medição do assistente da coordenação (o 2º agente) com o MODELO REAL, sobre
# os alunos FICTÍCIOS do banco sintético (src/dados.py). Precisa da chave.
#
#   python -m evals.avaliar_assistente                       # 6 casos, ~5 a 8 mil tokens cada
#   python -m evals.avaliar_assistente --pasta evals/resultados/2026-11-14-assistente
#
# O que faz: cria, num banco SEPARADO (não toca dados/academico.db), um pedido de
# trancamento aguardando a coordenação para cada aluno da lista, com motivos de
# tipos diferentes, e pede o parecer ao assistente pelo servidor MCP (stdio), o
# mesmo caminho do `coordenacao.py preparar`. Retomável: pula o que já está em
# execucoes.jsonl.
#
# O que mede (declarado ANTES de rodar, como a regra da Parte 3):
#   - parecer aceito pelo validador sem contingência   (meta: >= 5 de 6)
#   - parecer com recomendação de decisão no texto      (meta: 0; o código barra, mas conta)
#   - consultas a outro RA recusadas                     (registro; o esperado é 0)
#   - os FATOS conferem com o banco: a situação da matrícula e o valor em aberto
#     que o parecer cita batem com o que o banco tem  (conferido por código)
#   - tokens por caso
# Gasta a cota do MESMO modelo da rodada B (qwen/qwen3.8-27b): rode em outro dia
# que não o da rodada B, ou depois dela.

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

CASOS = [   # (ra, motivo registrado pelo agente do aluno) — alunos fictícios
    ("20229012", "aluno pediu trancamento do semestre por motivo de trabalho"),
    ("20230198", "aluna pediu trancamento; tem mensalidades em aberto"),
    ("20232210", "aluna quer trancar por motivo de saúde na família"),
    ("20231987", "aluno pediu trancamento, sem informar o motivo"),
    ("20234321", "aluna vai mudar de cidade e pediu trancamento"),
    ("20230555", "aluna pediu trancamento e perguntou se perde a bolsa"),
]
METAS = {"aceitos_sem_contingencia": 5, "com_recomendacao": 0}


def conferir_fatos(resultado: dict, ra: str) -> list[str]:
    """Confere por código o que o parecer diz contra o banco: situação e débito."""
    import agente
    erros = []
    if not resultado.get("parecer"):
        return ["sem parecer"]
    texto = json.dumps(resultado["parecer"], ensure_ascii=False).lower()
    aluno = agente.buscar_aluno(ra)
    fin = agente.consultar_financeiro(ra)
    for situacao in ("ativa", "trancada", "formado"):
        if f"matrícula {situacao}" in texto and situacao != aluno["situacao_matricula"]:
            erros.append(f"diz matrícula {situacao}; o banco tem {aluno['situacao_matricula']}")
    if fin["valor_em_aberto"]:
        valor = f"{fin['valor_em_aberto']:.2f}".replace(".", ",")
        valor2 = f"{fin['valor_em_aberto']:.2f}"
        citou_valor = valor in texto or valor2 in texto or str(int(fin["valor_em_aberto"])) in texto
        if "em aberto" in texto and not citou_valor:
            erros.append(f"fala em débito sem o valor do banco (R$ {valor})")
    else:
        nega = any(x in texto for x in ("sem pendência", "nenhuma mensalidade", "0 mensalidade", "em dia"))
        if "pendência financeira" in texto and not nega:
            erros.append("aponta débito que o banco não tem")
    return erros


async def avaliar(pasta: Path, cliente=None, casos=CASOS) -> dict:
    import agente
    import assistente_coordenacao as ac
    import dados
    from triagem import humano

    pasta.mkdir(parents=True, exist_ok=True)
    arq = pasta / "execucoes.jsonl"
    feitos = {json.loads(l)["ra"] for l in arq.read_text(encoding="utf-8").splitlines() if l.strip()} if arq.exists() else set()
    for ra, motivo in casos:
        if ra in feitos:
            continue
        r = agente.escalar_para_humano(ra, "trancamento", motivo, f"{ra}:trancamento:avaliacao")
        humano.registrar_espera(f"avaliacao-{ra}", r["protocolo"], ra)
        if cliente is None:
            async with ac.sessao_stdio() as sessao:
                res = await ac.preparar_parecer(r["protocolo"], sessao)
        else:
            from mcp.shared.memory import create_connected_server_and_client_session
            import mcp_secretaria
            async with create_connected_server_and_client_session(mcp_secretaria.servidor._mcp_server) as sessao:
                res = await ac.preparar_parecer(r["protocolo"], sessao, cliente=cliente)
        res["ra"] = ra
        res["fatos_errados"] = conferir_fatos(res, ra)
        res["com_recomendacao"] = any("recomenda" in p for p in res.get("problemas_da_ultima_tentativa", []))
        with arq.open("a", encoding="utf-8") as f:
            f.write(json.dumps(res, ensure_ascii=False) + "\n")
        print(f"{ra} {r['protocolo']}: origem={res['origem']} tokens={res['tokens']} fatos_errados={len(res['fatos_errados'])}", flush=True)
    linhas = [json.loads(l) for l in arq.read_text(encoding="utf-8").splitlines() if l.strip()]
    resumo = {
        "casos": len(linhas),
        "aceitos_sem_contingencia": sum(l["origem"] == "modelo" for l in linhas),
        "contingencia": sum(l["origem"] == "contingencia" for l in linhas),
        "com_recomendacao": sum(l["com_recomendacao"] for l in linhas),
        "recusas_de_outro_ra": sum(len(l["recusas"]) for l in linhas),
        "casos_com_fato_errado": sum(bool(l["fatos_errados"]) for l in linhas),
        "tokens_total": sum(l["tokens"] for l in linhas),
        "tokens_medio": round(sum(l["tokens"] for l in linhas) / len(linhas)) if linhas else 0,
        "modelo": linhas[0]["modelo"] if linhas else None,
        "metas": METAS,
    }
    resumo["meta_atingida"] = (resumo["aceitos_sem_contingencia"] >= METAS["aceitos_sem_contingencia"]
                               and resumo["com_recomendacao"] <= METAS["com_recomendacao"]
                               and resumo["casos"] == len(casos))
    (pasta / "resumo.json").write_text(json.dumps(resumo, ensure_ascii=False, indent=2), encoding="utf-8")
    return resumo


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Mede o assistente da coordenação com o modelo real (dados fictícios)")
    ap.add_argument("--pasta", type=Path, default=RAIZ / "evals" / "resultados" / "assistente-r1")
    args = ap.parse_args(argv)
    if not os.environ.get("ACADEMICO_DB"):   # banco separado, persistente na pasta (para retomar)
        args.pasta.mkdir(parents=True, exist_ok=True)
        os.environ["ACADEMICO_DB"] = str(args.pasta.resolve() / "academico-avaliacao.db")
    import dados
    dados.CAMINHO_DB = Path(os.environ["ACADEMICO_DB"])
    dados.inicializar()
    print(json.dumps(asyncio.run(avaliar(args.pasta)), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
