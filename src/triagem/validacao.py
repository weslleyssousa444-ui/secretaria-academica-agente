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
# O agente declara, no fim da resposta a uma dúvida do Regimento, se os artigos
# devolvidos respondem à pergunta. A busca textual não tem piso de relevância
# (docs/rag.md §4): ela devolve artigo de ruído para uma pergunta sem resposta,
# e só o modelo, lendo o texto, sabe dizer que o artigo não responde. O CÓDIGO
# exige a marcação, confere o resto e a remove antes de mostrar ao aluno.
#
# O prompt pede a marcação NA ÚLTIMA LINHA, mas o código a aceita em QUALQUER
# posição: o modelo real, sem uma frase da regra 7, escreveu `[SUFICIENTE: não]`
# e continuou o texto depois dela, e um parser que exigia o fim reprovava boas
# respostas e as trocava pelo molde de contingência (docs/prompts.md §5). A
# marcação é um token de máquina; a posição dela não carrega significado.
_MARCACAO = re.compile(r"[ \t]*\[SUFICIENTE:\s*(sim|n[aã]o)\][ \t]*", re.IGNORECASE)


def separar_suficiencia(texto: str) -> tuple[str, bool | None]:
    """(texto sem a marcação, declarada). `None` quando o texto não a traz.
    Com mais de uma marcação, vale a ÚLTIMA."""
    achados = list(_MARCACAO.finditer(texto))
    if not achados:
        return texto.strip(), None
    limpo = _MARCACAO.sub(" ", texto)
    limpo = re.sub(r"[ \t]*\n[ \t]*\n(?:[ \t]*\n)+", "\n\n", limpo).strip()
    return limpo, achados[-1].group(1).lower() == "sim"


def consultou_regimento_com_artigo(passos: list[dict]) -> bool:
    return any(p["ferramenta"] == "consultar_regimento" and p.get("erro") is None
               and (p.get("resultado") or {}).get("total", 0) > 0 for p in passos)


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


def validar_resposta(texto: str, passos: list[dict],
                     passos_do_turno: list[dict] | None = None) -> list[str]:
    """Lista de problemas; vazia quando a resposta passa."""
    problemas: list[str] = []
    if consultou_regimento_com_artigo(passos_do_turno if passos_do_turno is not None else passos) \
            and separar_suficiencia(texto)[1] is None:
        problemas.append("falta a linha final [SUFICIENTE: sim] ou [SUFICIENTE: não]")

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
    if consultou_regimento_com_artigo(passos):
        return ("Não consegui responder sua dúvida com segurança. Se quiser, posso "
                "encaminhar o caso à secretaria.")
    return ("Não consegui concluir sua solicitação por aqui. Informe seu RA e o "
            "que precisa, ou procure a secretaria.")
