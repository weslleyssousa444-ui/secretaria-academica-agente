# O pipeline RAG do Exercício 7: recuperar -> montar contexto -> gerar,
# com citação verificável (nota 05 §3) e portão de recusa (nota 05 §2).
#
# Dois portões, não um:
#   1. LIMIAR DE SCORE, antes de chamar o modelo — se o melhor trecho
#      recuperado está abaixo do piso medido (ver medir_piso_cosseno.py e
#      exercicios/aula-07-resposta-que-cita.md), recusa sem gastar uma
#      chamada de geração. É a mesma ideia do portão da Aula 06 (nota 04
#      desta aula, §1): limiar mais frouxo que o piso deixa passar lixo.
#   2. O CAMPO `suficiente` do schema, depois de chamar o modelo — cobre o
#      caso em que a busca encontrou algo do MESMO ASSUNTO (score acima do
#      piso) mas que não responde à pergunta específica (nota 05, exemplo
#      1: prazo de submissão != prazo de depósito).

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
from openai import OpenAI

from agente import ErroFatal, chamar_com_retry
from indice_rag import IndiceRAG

load_dotenv()

client = OpenAI(
    base_url=os.environ.get("LLM_BASE_URL", "https://api.groq.com/openai/v1"),
    api_key=os.environ.get("OPENAI_API_KEY"),
)
# Modelo PRÓPRIO do RAG, independente do LLM_MODELO do agente de triagem
# (src/agente.py, Ex.6). Descoberta ao rodar de verdade: `qwen/qwen3.8-27b`
# tem um teto de 1.000 tokens de SAÍDA por minuto (OTPM) na Groq, separado
# do teto geral de 8.000 tokens/min — uma única chamada de resposta+citação
# já pediu 1.497 e foi recusada. `openai/gpt-oss-20b` não mostrou esse
# subteto nos testes (só o limite geral de 8.000 tokens/min), por isso vira
# o padrão aqui — sem mexer no modelo já validado do Ex.6.
MODELO = os.environ.get("RAG_MODELO", "openai/gpt-oss-20b")

# Medido em medir_piso_cosseno.py (nota 02 desta aula, §1: "par de
# controle"). Documentado com o valor real em
# exercicios/aula-07-resposta-que-cita.md — este é só o valor-padrão.
LIMIAR_PADRAO = 0.35

PROMPT_SISTEMA = """Você responde perguntas de alunos sobre o Regimento \
Acadêmico da secretaria, usando EXCLUSIVAMENTE os trechos fornecidos abaixo.

Cada trecho vem rotulado entre colchetes, por exemplo [Art. 6º].

Responda no formato JSON abaixo, e SOMENTE nesse formato, sem texto fora do \
JSON:
{"resposta": "...", "fontes": ["<rótulos entre colchetes usados>"], \
"suficiente": true|false}

Regras:
- `fontes`: só os rótulos dos trechos que você de fato usou para responder, \
SEM os colchetes (ex: "Art. 6º", não "[Art. 6º]"). Não invente rótulo, e \
não cite um trecho que não usou.
- `suficiente`: false quando os trechos fornecidos não contêm a informação \
necessária para responder com segurança. Nesse caso, `resposta` diz o que \
os trechos de fato tratam (se algo relacionado), e não tenta adivinhar o \
que falta.
- Não use conhecimento próprio sobre regimentos acadêmicos em geral. Não \
conclua além do que os trechos permitem.
- Se dois trechos tratarem do MESMO dispositivo com valores diferentes, \
não escolha um silenciosamente: diga que há duas versões e não decida \
qual vale, deixando `suficiente=false`."""


def montar_contexto(trechos: list[dict]) -> str:
    partes = []
    for t in trechos:
        rotulo = t["id"]
        partes.append(f"[{rotulo}]\n{t['texto']}")
    return "\n\n".join(partes)


def _chamar_llm(pergunta: str, contexto: str) -> dict:
    resposta = chamar_com_retry(
        model=MODELO,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": PROMPT_SISTEMA},
            {"role": "user", "content": (
                f"TRECHOS:\n{contexto}\n\nPERGUNTA DO ALUNO: {pergunta}")},
        ],
    )
    conteudo = resposta.choices[0].message.content
    try:
        saida = json.loads(conteudo)
    except json.JSONDecodeError:
        saida = {"resposta": conteudo, "fontes": [], "suficiente": False,
                  "erro_parse": True}
    saida.setdefault("resposta", "")
    saida.setdefault("fontes", [])
    saida.setdefault("suficiente", False)
    saida["tokens_gastos"] = resposta.usage.total_tokens
    return saida


def citacao_verificavel(fontes: list[str], trechos: list[dict]) -> dict:
    """Verificação em código (nota 05 §3) — nunca pergunta ao modelo se a
    própria citação dele está certa. Normaliza colchetes/espaços antes de
    comparar: um modelo que devolve "[Art. 6º]" em vez de "Art. 6º" não
    inventou a fonte, só formatou diferente — e uma verificação que não
    tolera isso produz falso alarme (achado real desta execução, ver
    exercicios/aula-07-resposta-que-cita.md)."""
    def normalizar(rotulo: str) -> str:
        return rotulo.strip().lstrip("[").rstrip("]").strip()

    disponiveis = [t["id"] for t in trechos]
    disponiveis_normalizados = {normalizar(d): d for d in disponiveis}
    validas, inventadas = [], []
    for f in fontes:
        original = disponiveis_normalizados.get(normalizar(f))
        (validas if original else inventadas).append(f)
    return {"citadas": fontes, "disponiveis": disponiveis,
            "validas": validas, "inventadas": inventadas}


def responder(pergunta: str, indice: IndiceRAG, k: int = 3,
              limiar: float = LIMIAR_PADRAO,
              ordem_trechos: list[dict] | None = None) -> dict:
    """`ordem_trechos`, quando fornecido, substitui a ordem natural da busca
    — é o gancho usado por modos_de_falha.py para reproduzir o modo 2
    (viés de posição, nota 04 §4) sem duplicar toda a função."""
    trechos = indice.buscar(pergunta, k=k)
    melhor_score = max((t["score"] for t in trechos), default=0.0)

    if melhor_score < limiar:
        return {
            "resposta": (
                "O regimento não parece tratar deste assunto. O trecho "
                f"mais próximo encontrado foi {trechos[0]['id']!r}, mas a "
                "semelhança está abaixo do limiar de confiança — em vez "
                "de arriscar uma resposta sobre outro assunto, prefiro "
                "recusar."
            ),
            "fontes": [], "suficiente": False,
            "trechos_recuperados": [t["id"] for t in trechos],
            "melhor_score": melhor_score, "portao": "recusou_por_score",
            "tokens_gastos": 0,
        }

    trechos_para_contexto = ordem_trechos if ordem_trechos is not None else trechos
    contexto = montar_contexto(trechos_para_contexto)
    try:
        saida = _chamar_llm(pergunta, contexto)
    except ErroFatal as e:
        return {
            "resposta": f"[erro_fatal na geração: {e}]",
            "fontes": [], "suficiente": False,
            "trechos_recuperados": [t["id"] for t in trechos],
            "melhor_score": melhor_score, "portao": "erro_fatal",
            "tokens_gastos": 0,
            "verificacao_citacao": {"citadas": [], "disponiveis": [],
                                     "validas": [], "inventadas": []},
        }
    saida["trechos_recuperados"] = [t["id"] for t in trechos]
    saida["melhor_score"] = melhor_score
    saida["portao"] = "passou"
    saida["verificacao_citacao"] = citacao_verificavel(
        saida["fontes"], trechos_para_contexto)
    return saida


if __name__ == "__main__":
    indice = IndiceRAG()
    for pergunta in [
        "Qual o prazo de resposta da secretaria para um pedido encaminhado?",
        "Qual o teto de reembolso para curso de idiomas?",
    ]:
        print(f"\nP: {pergunta}")
        r = responder(pergunta, indice)
        print(f"   portão: {r['portao']} (score {r['melhor_score']:.3f})")
        print(f"   suficiente: {r['suficiente']}")
        print(f"   resposta: {r['resposta']}")
        print(f"   fontes: {r['fontes']}")
