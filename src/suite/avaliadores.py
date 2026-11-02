# Avaliadores determinísticos da suíte (Exercício 11), um por nível. Todos
# leem o REGISTRO gravado por executor.py (passos, respostas, foto do banco
# antes/depois) e o caso do golden dataset; nenhum chama modelo. O juiz LLM
# (nível 4) está em juiz.py.
#
# Escritos a partir do desenho de exercicios/aula-11-avaliacao.md, antes de
# qualquer resultado ser lido.
#
# Por que cada nível existe aqui (a tabela completa, com a justificativa por
# propriedade, está em exercicios/aula-11-suite-do-case.md):
#   decisão     `==` contra o rótulo; o rótulo é regra de negócio, não opinião.
#   resultado   estado do banco antes/depois. É o único nível que vê o agente
#               que RELATA ter emitido e não emitiu, e o que emite duas vezes.
#   trajetória  cobertura, supérfluas e ordem, separadas (nota 02): um
#               veredito certo sem consultar o sistema é acerto por acaso.
#   texto       regex sobre a resposta: prazo e protocolo são strings
#               verificáveis; não precisam de juiz.

from __future__ import annotations

import re
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from verificador import classificar_decisao  # noqa: E402

LEITURAS = {"buscar_aluno", "consultar_financeiro"}
ESCRITAS = {"emitir_documento", "escalar_para_humano"}
PROTOCOLO = re.compile(r"\b(?:DOC|CASO)-\d+\b")
PRAZO = re.compile(r"(\d+)\s*(?:h\b|hs\b|horas?|dias?)", re.IGNORECASE)
CANAL_INVENTADO = re.compile(r"download|baixar|e-?mail|whats ?app|aplicativo|\bapp\b", re.IGNORECASE)


def _estado(registro: dict) -> SimpleNamespace:
    """Reconstitui o que classificar_decisao lê (`estado.passos`)."""
    return SimpleNamespace(passos=[SimpleNamespace(**p) for p in registro["passos"]])


def avaliar_decisao(caso: dict, registro: dict) -> dict:
    obtida = classificar_decisao(_estado(registro)) or "sem_acao"
    return {"obtida": obtida, "ok": obtida in caso["esperado"]["decisoes"]}


def avaliar_resultado(caso: dict, registro: dict) -> dict:
    esp, antes, depois = caso["esperado"], registro["antes"], registro["depois"]
    novos = {t: [l for l in depois[t] if l["protocolo"] not in {a["protocolo"] for a in antes[t]}]
             for t in ("documentos_emitidos", "casos_pendentes")}
    faixa = esp["novas_linhas"]
    n_docs, n_casos = len(novos["documentos_emitidos"]), len(novos["casos_pendentes"])
    texto = " ".join(registro["respostas"])
    existentes = {l["protocolo"] for t in depois.values() for l in t}
    citados = set(PROTOCOLO.findall(texto))

    checagens = {
        "n_documentos": faixa["documentos_emitidos"][0] <= n_docs <= faixa["documentos_emitidos"][1],
        "n_casos": faixa["casos_pendentes"][0] <= n_casos <= faixa["casos_pendentes"][1],
        # RA-alvo: toda linha nova é do aluno do caso (nenhum documento para outro RA)
        "ra_alvo": esp["ra_alvo"] is None or all(
            l["ra"] == esp["ra_alvo"] for t in novos.values() for l in t),
        "tipo_do_pedido": esp["tipo_pedido_do_caso"] is None or all(
            l["tipo_pedido"] == esp["tipo_pedido_do_caso"] for l in novos["casos_pendentes"]),
        "sem_duplicata": len({(l["ra"], l["tipo_documento"]) for l in novos["documentos_emitidos"]})
                         == n_docs,
        # o agente que relata o que não fez: protocolo citado que não existe no banco
        "protocolos_citados_existem": citados <= existentes,
        "protocolos_esperados": set(esp["protocolos_esperados"]) <= citados,
    }
    return {"novos_documentos": n_docs, "novos_casos": n_casos, "checagens": checagens,
            "ok": all(checagens.values())}


def avaliar_trajetoria(caso: dict, registro: dict) -> dict:
    esp, passos = caso["esperado"], registro["passos"]
    chamadas = [p["ferramenta"] for p in passos]
    # cobertura: das leituras que o caso exige, quantas aconteceram
    exigidas = set(esp["leituras_obrigatorias"])
    cobertura = 1.0 if not exigidas else len(exigidas & set(chamadas)) / len(exigidas)
    # supérfluas: ferramenta fora das permitidas, ou a mesma chamada repetida
    vistas, superfluas = set(), 0
    for p in passos:
        assinatura = (p["ferramenta"], repr(sorted(p["argumentos"].items())))
        if p["ferramenta"] not in esp["ferramentas_permitidas"] or assinatura in vistas:
            superfluas += 1
        vistas.add(assinatura)
    # ordem: nenhuma escrita antes da primeira leitura
    primeira_escrita = next((i for i, c in enumerate(chamadas) if c in ESCRITAS), None)
    primeira_leitura = next((i for i, c in enumerate(chamadas) if c in LEITURAS), None)
    ordem_ok = primeira_escrita is None or (
        primeira_leitura is not None and primeira_leitura < primeira_escrita)
    return {"cobertura": cobertura, "superfluas": superfluas, "ordem_ok": ordem_ok,
            "ok": cobertura == 1.0 and superfluas == 0 and ordem_ok}


def avaliar_texto(caso: dict, registro: dict) -> dict:
    final = registro["respostas"][-1] if registro["respostas"] else ""
    escalou = any(p["ferramenta"] == "escalar_para_humano" and p["erro"] is None
                  for p in registro["passos"])
    prazos = {int(n) for n in PRAZO.findall(final)}
    checagens = {
        "so_o_prazo_de_48h": prazos <= {48},
        "informa_48h_ao_escalar": (not escalou) or 48 in prazos,
        "informa_o_protocolo_ao_escalar_ou_emitir": not any(
            p["erro"] is None and p["ferramenta"] in ESCRITAS and (p["resultado"] or {}).get("protocolo")
            for p in registro["passos"]) or bool(PROTOCOLO.search(final)),
        "sem_canal_inventado": not CANAL_INVENTADO.search(final),
        # acrescentado na v1.0.1 do avaliador, depois de B2/re06 terminar "respondeu" com
        # resposta vazia e a v1.0.0 não acusar (a decisão `sem_acao` era aceita nesse caso)
        "resposta_nao_vazia": bool(final.strip()),
    }
    return {"checagens": checagens, "ok": all(checagens.values())}


def avaliar(caso: dict, registro: dict) -> dict:
    """Aprovação = decisão E resultado E término normal (a métrica principal
    da regra de promoção). Trajetória e texto são reportados à parte."""
    decisao = avaliar_decisao(caso, registro)
    resultado = avaliar_resultado(caso, registro)
    trajetoria = avaliar_trajetoria(caso, registro)
    texto = avaliar_texto(caso, registro)
    termino_ok = registro["termino"] == "respondeu"
    return {
        "caso": caso["id"], "classe": caso["classe"], "versao": registro["versao"], "run": registro["run"],
        "infra": registro["termino"] == "erro_fatal",
        "decisao": decisao, "resultado": resultado, "trajetoria": trajetoria, "texto": texto,
        "termino_ok": termino_ok,
        "aprovado": decisao["ok"] and resultado["ok"] and termino_ok,
        "escrita_indevida": caso["esperado"]["novas_linhas"]["documentos_emitidos"][1] == 0
                            and resultado["novos_documentos"] > 0,
    }
