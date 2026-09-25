# Regimento Acadêmico simulado — a fonte de RAG do Exercício 7.
#
# 100% sintético (mesma regra de dados.py, docs/case.md §2.9). O grupo não
# tem acesso ao regimento real da instituição (docs/case.md §2.10-2.11,
# docs/fontes.md) — este arquivo é o "regimento simulado" anunciado em
# docs/base-de-conhecimento-v1.md como placeholder da v1.
#
# Cada artigo é um chunk (corte por estrutura, Aula 06 nota 02). Os campos
# além de `texto` são o metadado que a nota 00/02 desta aula pede:
# procedência (capítulo), vigência e revogação (para o modo de falha 4).
#
# Dois artigos são deliberadamente armadilhas de RAG, nomeados como os
# exemplos das notas de aula:
#   - ART_9_1 / ART_9_1_REVOGADO: duas versões do mesmo dispositivo (prazo),
#     uma vigente (48h) e uma revogada (72h) — modo de falha 4 (nota 04 §6).
#   - Art. 7º §2º: menciona "aplicativo do banco" só para EXCLUÍ-LO como
#     comprovante — armadilha de negação (nota 02 §2, modo de falha 1).

REGIMENTO = [
    # ---- Capítulo I — Disposições gerais ----
    {
        "id": "Art. 1º",
        "capitulo": "I — Disposições Gerais",
        "texto": (
            "Art. 1º Este Regimento disciplina a emissão de documentos "
            "acadêmicos e o trancamento de matrícula na instituição, e se "
            "aplica a todos os alunos regularmente matriculados."
        ),
        "vigente": True,
        "data_vigencia": "2026-01-01",
    },
    {
        "id": "Art. 2º",
        "capitulo": "I — Disposições Gerais",
        "texto": (
            "Art. 2º Os pedidos de que trata este Regimento são recebidos "
            "pelo canal digital da secretaria acadêmica e processados na "
            "ordem de chegada, ressalvada a prioridade legal de gestantes, "
            "lactantes e pessoas com deficiência."
        ),
        "vigente": True,
        "data_vigencia": "2026-01-01",
    },

    # ---- Capítulo II — Declaração de matrícula e segunda via ----
    {
        "id": "Art. 3º",
        "capitulo": "II — Declaração de Matrícula e Segunda Via",
        "texto": (
            "Art. 3º A declaração de matrícula é emitida a qualquer aluno "
            "com situação de matrícula ativa, independentemente de "
            "pendência financeira, e tem validade de 90 dias a partir da "
            "emissão."
        ),
        "vigente": True,
        "data_vigencia": "2026-01-01",
    },
    {
        "id": "Art. 4º",
        "capitulo": "II — Declaração de Matrícula e Segunda Via",
        "texto": (
            "Art. 4º A segunda via do histórico escolar exige quitação "
            "financeira total do aluno, apurada na data do pedido. A "
            "existência de qualquer mensalidade em aberto impede a emissão "
            "até a regularização ou a confirmação do pagamento pela "
            "secretaria."
        ),
        "vigente": True,
        "data_vigencia": "2026-01-01",
    },
    {
        "id": "Art. 5º",
        "capitulo": "II — Declaração de Matrícula e Segunda Via",
        "texto": (
            "Art. 5º Não há segunda via de diploma por este canal. Pedidos "
            "de segunda via de diploma seguem processo próprio, junto à "
            "secretaria de registros acadêmicos, e não são tratados por "
            "este Regimento."
        ),
        "vigente": True,
        "data_vigencia": "2026-01-01",
    },

    # ---- Capítulo III — Trancamento de matrícula ----
    {
        "id": "Art. 6º",
        "capitulo": "III — Do Trancamento de Matrícula",
        "texto": (
            "Art. 6º O trancamento de matrícula é sempre decidido pela "
            "coordenação acadêmica, mediante confirmação humana explícita, "
            "e nunca por sistema automatizado, independentemente da "
            "situação cadastral ou financeira do aluno no momento do "
            "pedido."
        ),
        "vigente": True,
        "data_vigencia": "2026-01-01",
    },
    {
        "id": "Art. 7º §1º",
        "capitulo": "III — Do Trancamento de Matrícula",
        "texto": (
            "Art. 7º §1º O trancamento de matrícula não pode ser parcial: "
            "não existe trancamento de disciplina isolada por este "
            "Regimento. O aluno que deseja cursar menos disciplinas no "
            "semestre deve procurar a coordenação do curso para ajuste de "
            "grade, matéria que este Regimento não disciplina."
        ),
        "vigente": True,
        "data_vigencia": "2026-01-01",
    },
    {
        "id": "Art. 7º §2º",
        "capitulo": "III — Do Trancamento de Matrícula",
        "texto": (
            "Art. 7º §2º O comprovante de pagamento aceito para fins de "
            "regularização financeira é o extrato ou recibo emitido "
            "diretamente pela instituição financeira, com autenticação "
            "mecânica ou código de verificação. Uma captura de tela do "
            "aplicativo do banco, sem os elementos acima, NÃO é aceita "
            "como comprovante e não supera a pendência registrada no "
            "sistema financeiro."
        ),
        "vigente": True,
        "data_vigencia": "2026-01-01",
    },

    # ---- Capítulo IV — Exceções ao trancamento ----
    {
        "id": "Art. 8º §1º",
        "capitulo": "IV — Das Exceções",
        "texto": (
            "Art. 8º §1º O aluno bolsista integral que solicitar "
            "trancamento de matrícula tem sua bolsa automaticamente "
            "suspensa a partir da data de deferimento pela coordenação, e "
            "a retomada da bolsa ao retornar depende de nova análise "
            "socioeconômica, não sendo automática."
        ),
        "vigente": True,
        "data_vigencia": "2026-01-01",
    },
    {
        "id": "Art. 8º §2º",
        "capitulo": "IV — Das Exceções",
        "texto": (
            "Art. 8º §2º O aluno vinculado a convênio empresarial que "
            "solicitar trancamento deve, cumulativamente, apresentar "
            "anuência por escrito da empresa conveniada, sem a qual o "
            "pedido é considerado incompleto e não avança para decisão da "
            "coordenação."
        ),
        "vigente": True,
        "data_vigencia": "2026-01-01",
    },
    {
        "id": "Art. 8º §3º",
        "capitulo": "IV — Das Exceções",
        "texto": (
            "Art. 8º §3º O trancamento amparado por decisão judicial "
            "liminar é processado independentemente da existência de "
            "pendência financeira ou de anuência de terceiros, e a "
            "coordenação acadêmica dá cumprimento à ordem judicial no "
            "prazo nela fixado, ou, na omissão da decisão, no prazo do "
            "Art. 9º §1º."
        ),
        "vigente": True,
        "data_vigencia": "2026-01-01",
    },

    # ---- Capítulo V — Prazos (o par vigente/revogado do modo de falha 4) ----
    {
        "id": "Art. 9º §1º",
        "capitulo": "V — Dos Prazos",
        "texto": (
            "Art. 9º §1º O prazo de resposta da secretaria para qualquer "
            "pedido encaminhado à coordenação, incluindo trancamento e "
            "divergência financeira não resolvida, é de 48 (quarenta e "
            "oito) horas úteis, contadas do protocolo."
        ),
        "vigente": True,
        "data_vigencia": "2026-01-01",
    },
    {
        "id": "Art. 9º §1º (redação de 2024, revogada)",
        "capitulo": "V — Dos Prazos",
        "texto": (
            "Art. 9º §1º O prazo de resposta da secretaria para qualquer "
            "pedido encaminhado à coordenação é de 72 (setenta e duas) "
            "horas úteis, contadas do protocolo."
        ),
        "vigente": False,
        "data_vigencia": "2024-03-01",
        "revoga_ou_e_revogado_por": "Art. 9º §1º",
        "observacao": (
            "ARMADILHA DELIBERADA (modo de falha 4, nota 04 §6): mesma "
            "redação e mesmo assunto do Art. 9º §1º vigente, diferindo só "
            "no valor numérico do prazo (72h vs. 48h). Existe no corpus "
            "para testar se o pipeline detecta a contradição ou responde "
            "com a versão revogada."
        ),
    },
    {
        "id": "Art. 9º §2º",
        "capitulo": "V — Dos Prazos",
        "texto": (
            "Art. 9º §2º Não corre prazo enquanto o pedido estiver "
            "aguardando complementação de dado pelo próprio aluno, "
            "inclusive confirmação de RA ou envio de comprovante."
        ),
        "vigente": True,
        "data_vigencia": "2026-01-01",
    },

    # ---- Capítulo VI — Disposições finais ----
    {
        "id": "Art. 10",
        "capitulo": "VI — Disposições Finais",
        "texto": (
            "Art. 10 Os casos omissos neste Regimento são decididos pela "
            "coordenação acadêmica, vedada a decisão automatizada em "
            "qualquer matéria não expressamente autorizada nos artigos "
            "anteriores."
        ),
        "vigente": True,
        "data_vigencia": "2026-01-01",
    },
]


def artigos_vigentes():
    return [a for a in REGIMENTO if a["vigente"]]


if __name__ == "__main__":
    vigentes = artigos_vigentes()
    print(f"{len(REGIMENTO)} artigos no arquivo, {len(vigentes)} vigentes "
          f"({len(REGIMENTO) - len(vigentes)} revogado/histórico).")
