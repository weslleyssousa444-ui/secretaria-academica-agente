# Validação da resposta final ao aluno, em código (docs/prompts.md §4).
#
# O contrato de saída do prompt diz "não invente protocolo, prazo nem artigo".
# Dizer não é garantir: um modelo que escreve "protocolo DOC-9999" sem nenhuma
# ferramenta ter devolvido isso passa por qualquer instrução. Esta validação
# confere o TEXTO contra o que as ferramentas devolveram, e é o "avaliador" do
# padrão avaliador-otimizador do grafo (docs/grafo.md §2): se reprova, o
# agente reescreve uma vez; se reprova de novo, o nó de contingência monta a
# resposta por modelo de texto, sem o modelo.
#
# O que NÃO está aqui, e fica declarado: invenção de CANAL ("acompanhe pelo
# portal") não é detectável por regra sem falso positivo; é o risco aceito
# ASI09 (docs/seguranca.md) e o que o juiz da suíte mede (docs/evals.md).

from __future__ import annotations

import re

PRAZO_PROMETIDO_HORAS = 48

_PROTOCOLO = re.compile(r"\b(?:DOC|CASO)-\d+\b")
_ARTIGO = re.compile(r"Art\.?\s*\d+\s*º?(?:\s*§\s*\d+\s*º?)?", re.IGNORECASE)
_PRAZO = re.compile(r"\b(\d+)\s*(h|horas?|dias?|semanas?)\b", re.IGNORECASE)


def normalizar_artigo(rotulo: str) -> str:
    return re.sub(r"[\s.]", "", rotulo.lower())


def protocolos_devolvidos(passos: list[dict]) -> set[str]:
    return {p["resultado"]["protocolo"] for p in passos
            if p.get("erro") is None and p.get("resultado")
            and isinstance(p["resultado"], dict) and p["resultado"].get("protocolo")}


def artigos_devolvidos(passos: list[dict]) -> list[str]:
    ids: list[str] = []
    for p in passos:
        if p["ferramenta"] == "consultar_regimento" and p.get("resultado"):
            ids += [t["id"] for t in p["resultado"].get("trechos", [])]
    return ids


def artigos_citados(texto: str, devolvidos: list[str]) -> list[str]:
    """Os rótulos DEVOLVIDOS que o texto cita. Citar "Art. 7º" aceita o
    "Art. 7º §1º" devolvido (o prefixo identifica o artigo)."""
    citados = {normalizar_artigo(m) for m in _ARTIGO.findall(texto)}
    return [d for d in devolvidos
            if any(normalizar_artigo(d).startswith(c) for c in citados)]


def validar_resposta(texto: str, passos: list[dict]) -> list[str]:
    """Lista de problemas; vazia quando a resposta passa."""
    problemas: list[str] = []

    inventados = set(_PROTOCOLO.findall(texto)) - protocolos_devolvidos(passos)
    if inventados:
        problemas.append(f"protocolo(s) que nenhuma ferramenta devolveu: {sorted(inventados)}")

    devolvidos = artigos_devolvidos(passos)
    citados_brutos = {normalizar_artigo(m) for m in _ARTIGO.findall(texto)}
    sem_lastro = [c for c in citados_brutos
                  if not any(normalizar_artigo(d).startswith(c) for d in devolvidos)]
    if sem_lastro:
        problemas.append(f"artigo(s) citado(s) que a ferramenta não devolveu: {sorted(sem_lastro)}")

    # Prazo: só vale 48 h (o que o agente promete) ou um número que o próprio
    # artigo devolvido contém. Um prazo qualquer em texto livre é promessa.
    texto_dos_artigos = " ".join(
        t["texto"] for p in passos if p["ferramenta"] == "consultar_regimento" and p.get("resultado")
        for t in p["resultado"].get("trechos", []))
    permitidos = {(str(PRAZO_PROMETIDO_HORAS), "h")} | {
        (n, u[0].lower()) for n, u in _PRAZO.findall(texto_dos_artigos)}
    for numero, unidade in _PRAZO.findall(texto):
        if (numero, unidade[0].lower()) not in permitidos:
            problemas.append(f"prazo '{numero} {unidade}' que nem o agente promete "
                             f"({PRAZO_PROMETIDO_HORAS} h) nem consta no artigo devolvido")
    return problemas


def resposta_de_contingencia(passos: list[dict]) -> str:
    """Texto montado pelo código quando o modelo reprovou duas vezes. Só afirma
    o que as ferramentas devolveram."""
    for passo in reversed(passos):
        if passo.get("erro") is not None or not passo.get("resultado"):
            continue
        resultado = passo["resultado"]
        if passo["ferramenta"] == "emitir_documento":
            return (f"Seu documento foi emitido. Protocolo: {resultado['protocolo']}. "
                    "Se precisar de mais alguma coisa, é só pedir.")
        if passo["ferramenta"] == "escalar_para_humano":
            return (f"Seu caso foi encaminhado à secretaria. Protocolo: "
                    f"{resultado['protocolo']}. Prazo de resposta: {PRAZO_PROMETIDO_HORAS}h.")
    return ("Não consegui concluir sua solicitação por aqui. Informe seu RA e o "
            "que precisa, ou procure a secretaria.")
