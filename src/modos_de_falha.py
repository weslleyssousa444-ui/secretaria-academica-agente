# Reprodução dos 4 modos de falha (nota 04 desta aula) + o corpus
# desatualizado (item 6 do enunciado do Exercício 7), no case da secretaria
# acadêmica.

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from indice_rag import IndiceRAG
from rag import LIMIAR_PADRAO, montar_contexto, responder

CAMINHO_RELATORIO = Path(__file__).parent.parent / "logs" / "modos_de_falha.json"


def modo_1_recuperou_errado(indice: IndiceRAG) -> dict:
    """'Segunda via' aparece em dois artigos vizinhos — um sobre histórico
    (Art. 4º, tratado aqui) e um sobre diploma (Art. 5º, explicitamente FORA
    do escopo deste Regimento). É a mesma estrutura da armadilha da nota 04
    §3: o corpus menciona o assunto adjacente só para excluí-lo."""
    pergunta = "Quero a segunda via do meu diploma. Como faço o pedido?"
    trechos = indice.buscar(pergunta, k=2)
    r = responder(pergunta, indice, k=2)
    top1 = trechos[0]["id"]
    return {
        "pergunta": pergunta, "esperado": "Art. 5º",
        "top1_recuperado": top1,
        "recall_falhou": top1 != "Art. 5º",
        "resposta": r["resposta"], "fontes": r["fontes"],
    }


def modo_2_ignorou_no_meio(indice: IndiceRAG) -> dict:
    """Mesmos 3 trechos (Capítulo IV inteiro), em duas ordens — o correto
    (Art. 8º §3º, liminar) primeiro numa rodada, no meio na outra. Nota 04
    §4: o viés em U de LIU et al. (2023)."""
    pergunta = "Um pedido de trancamento por liminar judicial espera fila normal?"
    trechos = indice.buscar(pergunta, k=3)
    ordem_normal = trechos
    # Força o Art. 8º §3º (a resposta certa) para o meio da lista.
    alvo = [t for t in trechos if t["id"] == "Art. 8º §3º"]
    resto = [t for t in trechos if t["id"] != "Art. 8º §3º"]
    ordem_no_meio = resto[:1] + alvo + resto[1:] if alvo else trechos

    r_normal = responder(pergunta, indice, k=3, ordem_trechos=ordem_normal)
    r_meio = responder(pergunta, indice, k=3, ordem_trechos=ordem_no_meio)
    return {
        "pergunta": pergunta,
        "certo_primeiro": {"ordem": [t["id"] for t in ordem_normal],
                            "resposta": r_normal["resposta"],
                            "fontes": r_normal["fontes"]},
        "certo_no_meio": {"ordem": [t["id"] for t in ordem_no_meio],
                           "resposta": r_meio["resposta"],
                           "fontes": r_meio["fontes"]},
        "respostas_divergem": r_normal["resposta"] != r_meio["resposta"],
    }


def _chamar_sem_contrato(pergunta: str, contexto: str) -> str:
    """Réplica do 'SEM contrato' da nota 05, Exemplo 1: nem schema, nem
    campo `suficiente`, nem instrução para recusar — só "responda usando os
    trechos". É a versão ingênua que o Exercício 7 pede para contrastar."""
    from agente import chamar_com_retry
    from rag import MODELO
    r = chamar_com_retry(
        model=MODELO, temperature=0,
        messages=[
            {"role": "system", "content": (
                "Responda a pergunta do aluno usando os trechos do "
                "regimento abaixo.")},
            {"role": "user", "content": f"TRECHOS:\n{contexto}\n\nPERGUNTA: {pergunta}"},
        ],
    )
    return r.choices[0].message.content


def modo_3_respondeu_sem_base(indice: IndiceRAG) -> dict:
    """Três comparações para a mesma pergunta sem resposta no corpus:
    (a) SEM contrato nenhum (nota 05, Exemplo 1) — a falha crua;
    (b) COM contrato, mas com o portão de SCORE desligado (limiar 0.0);
    (c) COM contrato e portão normal (o pipeline de verdade).
    (b) já mostrou, na prática, que o campo `suficiente` sozinho basta
    para recusar mesmo sem o portão de score — a comparação com (a) é o
    que isola de fato o que o CONTRATO evita, e não o portão."""
    # Pergunta escolhida a dedo (nota 04 §5): tem um número plausível por
    # perto (as 48h do Art. 9º §1º) que um modelo menos cuidadoso poderia
    # transportar por engano para "prazo de reativação da bolsa", que o
    # regimento não fixa. Duas perguntas mais neutras (custo da segunda
    # via, prorrogação automática) foram testadas antes e NÃO produziram
    # alucinação nem sem contrato — ver exercicios/aula-07-resposta-que-cita.md.
    pergunta = "Em quantos dias a bolsa do aluno é reativada quando ele volta do trancamento?"
    trechos = indice.buscar(pergunta, k=3)
    contexto = montar_contexto(trechos)

    sem_contrato = _chamar_sem_contrato(pergunta, contexto)
    com_portao = responder(pergunta, indice, k=3, limiar=LIMIAR_PADRAO)
    sem_portao = responder(pergunta, indice, k=3, limiar=0.0)
    return {
        "pergunta": pergunta,
        "sem_contrato_nenhum": sem_contrato,
        "com_portao": {"portao": com_portao["portao"],
                        "suficiente": com_portao["suficiente"],
                        "resposta": com_portao["resposta"]},
        "sem_portao_de_score": {"portao": sem_portao["portao"],
                        "suficiente": sem_portao["suficiente"],
                        "resposta": sem_portao["resposta"],
                        "fontes": sem_portao["fontes"]},
    }


def modo_4_contradicao(indice: IndiceRAG) -> dict:
    """Busca SEM filtro de vigência (o padrão) recupera as duas versões do
    Art. 9º §1º. Nota 04 §6: recall alto, fidelidade alta, resposta ainda
    pode estar errada — porque o defeito está no CORPUS."""
    pergunta = "Qual o prazo de resposta da secretaria para um pedido encaminhado?"
    sem_filtro = indice.buscar(pergunta, k=3, apenas_vigentes=False)
    com_filtro = indice.buscar(pergunta, k=3, apenas_vigentes=True)

    ids_sem_filtro = [t["id"] for t in sem_filtro]
    ambas_versoes_recuperadas = (
        "Art. 9º §1º" in ids_sem_filtro
        and "Art. 9º §1º (redação de 2024, revogada)" in ids_sem_filtro
    )

    r = responder(pergunta, indice, k=3, limiar=LIMIAR_PADRAO)
    return {
        "pergunta": pergunta,
        "sem_filtro_vigencia": ids_sem_filtro,
        "com_filtro_vigencia": [t["id"] for t in com_filtro],
        "ambas_versoes_recuperadas_sem_filtro": ambas_versoes_recuperadas,
        "resposta_do_pipeline_padrao": r["resposta"],
        "fontes": r["fontes"], "suficiente": r["suficiente"],
        "sistema_detectou_a_contradicao": not r["suficiente"] or len(
            [f for f in r["fontes"] if "revogada" in f or "2024" in f]) == 0
            and "duas vers" in r["resposta"].lower(),
    }


def corpus_desatualizado(resultado_modo_4: dict) -> dict:
    """Item 6 do enunciado: o sistema TEM COMO SABER que a redação de 2024
    não vale mais, sem o filtro de metadado explícito?"""
    detectou = resultado_modo_4["sistema_detectou_a_contradicao"]
    return {
        "documento_revogado": "Art. 9º §1º (redação de 2024, revogada)",
        "sistema_detectou": detectou,
        "achado": (
            "O sistema NÃO sabe, por conta própria, que a redação de 2024 "
            "foi revogada — nada no texto do chunk diz isso; só o campo "
            "`vigente` do metadado sabe. Sem o filtro `apenas_vigentes` "
            "ativo na busca, o pipeline recupera as duas versões e depende "
            "inteiramente da instrução do prompt para não escolher uma "
            "silenciosamente. Isso não é técnica de recuperação — é "
            "curadoria de corpus (nota 04 §6): a correção real é retirar "
            "ou marcar a versão revogada antes de indexar, não pedir ao "
            "modelo para adivinhar qual vale."
            if not detectou else
            "O prompt reconheceu a existência de duas versões e recusou a "
            "decidir sozinho — mas isso é o prompt cobrindo uma lacuna do "
            "corpus, não o sistema 'sabendo' que uma foi revogada."
        ),
    }


def rodar_tudo() -> dict:
    indice = IndiceRAG()
    print("Rodando modo de falha 1 (recuperou o trecho errado)...")
    m1 = modo_1_recuperou_errado(indice)
    time.sleep(3)
    print("Rodando modo de falha 2 (recuperou e ignorou, viés de posição)...")
    m2 = modo_2_ignorou_no_meio(indice)
    time.sleep(3)
    print("Rodando modo de falha 3 (respondeu sem base)...")
    m3 = modo_3_respondeu_sem_base(indice)
    time.sleep(3)
    print("Rodando modo de falha 4 (trechos contraditórios)...")
    m4 = modo_4_contradicao(indice)
    time.sleep(3)
    print("Verificando corpus desatualizado...")
    corpus = corpus_desatualizado(m4)

    relatorio = {"modo_1": m1, "modo_2": m2, "modo_3": m3, "modo_4": m4,
                 "corpus_desatualizado": corpus}
    return relatorio


def imprimir(relatorio: dict) -> None:
    print("\nMODOS DE FALHA REPRODUZIDOS")
    m1 = relatorio["modo_1"]
    print(f"  não recuperou ......... {m1['pergunta']!r}")
    print(f"    top1 recuperado: {m1['top1_recuperado']} "
          f"(esperado {m1['esperado']}) -> "
          f"{'FALHOU' if m1['recall_falhou'] else 'ok'}")

    m2 = relatorio["modo_2"]
    print(f"  recuperou e ignorou ... {m2['pergunta']!r}")
    print(f"    respostas divergem por ordem: {m2['respostas_divergem']}")

    m3 = relatorio["modo_3"]
    print(f"  respondeu sem base .... {m3['pergunta']!r}")
    print(f"    SEM contrato nenhum: {m3['sem_contrato_nenhum']!r}")
    print(f"    com contrato, com portão de score: "
          f"suficiente={m3['com_portao']['suficiente']}")
    print(f"    com contrato, SEM portão de score: "
          f"suficiente={m3['sem_portao_de_score']['suficiente']}")

    m4 = relatorio["modo_4"]
    print(f"  contradisse ........... {m4['pergunta']!r}")
    print(f"    ambas versões recuperadas sem filtro: "
          f"{m4['ambas_versoes_recuperadas_sem_filtro']}")

    print(f"\nCORPUS DESATUALIZADO")
    c = relatorio["corpus_desatualizado"]
    print(f"  documento revogado: {c['documento_revogado']}")
    print(f"  o sistema {'detectou' if c['sistema_detectou'] else 'não detectou'}")


if __name__ == "__main__":
    relatorio = rodar_tudo()
    imprimir(relatorio)
    CAMINHO_RELATORIO.parent.mkdir(exist_ok=True)
    CAMINHO_RELATORIO.write_text(
        json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nrelatório salvo em {CAMINHO_RELATORIO}")
