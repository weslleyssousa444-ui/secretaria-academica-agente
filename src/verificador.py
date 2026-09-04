# O verificador do item 2.6 do case: roda os 40 casos rotulados contra o
# agente e compara a decisão tomada com o rótulo esperado (docs/case.md
# §2.6-2.7). O rótulo de cada caso é uma regra de negócio determinística —
# não é opinião — derivada dos dados semeados em dados.py.
#
# Uso:
#   python src/verificador.py
#
# Exige OPENAI_API_KEY configurada no .env. Grava um relatório em
# logs/verificador.json ao final.

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import dados
from agente import Estado, Orcamento, conversar

CAMINHO_CASOS = Path(__file__).parent.parent / "dados" / "casos_verificador.json"
CAMINHO_RELATORIO = Path(__file__).parent.parent / "logs" / "verificador.json"

CRITERIO_ACERTO = 34  # de 40 (85%) — docs/case.md §2.7


def classificar_decisao(estado: Estado) -> str | None:
    """Lê a trajetória e devolve o rótulo da ÚLTIMA ação de decisão bem
    sucedida (emitir_documento ou escalar_para_humano). None se o agente
    não chegou a uma decisão (orçamento, laço, ou só perguntas)."""
    for passo in reversed(estado.passos):
        if passo.erro is not None or passo.resultado is None:
            continue
        if passo.ferramenta == "emitir_documento":
            tipo = passo.resultado.get("tipo_documento")
            return {"declaracao_matricula": "emitir_declaracao",
                    "segunda_via_historico": "emitir_segunda_via"}.get(tipo)
        if passo.ferramenta == "escalar_para_humano":
            motivo = (passo.resultado.get("motivo") or "").lower()
            if passo.resultado.get("tipo_pedido") == "trancamento_matricula":
                return "escalar_trancamento"
            if "encontrad" in motivo or "ra não" in motivo or "ra nao" in motivo:
                return "escalar_ra_nao_encontrado"
            if "diverg" in motivo:
                return "escalar_divergencia"
            if "pend" in motivo:
                return "escalar_pendencia"
            return "escalar_outro"
    return None


def main() -> None:
    dados.inicializar()
    casos = json.loads(CAMINHO_CASOS.read_text(encoding="utf-8"))

    linhas = []
    acertos = 0
    falsos_negativos_trancamento = 0

    for caso in casos:
        estado = Estado(caso=caso["id"])
        orcamento = Orcamento()
        for mensagem in caso["mensagens"]:
            estado = conversar(estado, mensagem, orcamento, verboso=False)
            if estado.termino is not None and estado.termino.value != "respondeu":
                break

        obtida = classificar_decisao(estado)
        esperada = caso["decisao_esperada"]
        acertou = obtida == esperada
        acertos += acertou

        if esperada == "escalar_trancamento" and obtida != "escalar_trancamento":
            falsos_negativos_trancamento += 1

        linha = {"id": caso["id"], "esperada": esperada, "obtida": obtida,
                 "acertou": acertou, "termino": estado.termino.value,
                 "n_passos": estado.n_passos}
        linhas.append(linha)
        marca = "OK  " if acertou else "ERRO"
        print(f"{marca} {caso['id']:<5} esperado={esperada:<28} obtido={obtida}")

    total = len(casos)
    print(f"\n{acertos}/{total} corretos ({acertos / total:.0%})")
    print(f"falsos negativos em trancamento: {falsos_negativos_trancamento} "
          f"(critério do §2.7: precisa ser 0)")

    passou = acertos >= CRITERIO_ACERTO and falsos_negativos_trancamento == 0
    print(f"\nCRITÉRIO DE SUCESSO (§2.7): "
          f"{'ATINGIDO' if passou else 'NÃO ATINGIDO'}")

    CAMINHO_RELATORIO.parent.mkdir(exist_ok=True)
    CAMINHO_RELATORIO.write_text(json.dumps({
        "acertos": acertos, "total": total,
        "falsos_negativos_trancamento": falsos_negativos_trancamento,
        "criterio_atingido": passou, "casos": linhas,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"relatório salvo em {CAMINHO_RELATORIO}")


if __name__ == "__main__":
    main()
