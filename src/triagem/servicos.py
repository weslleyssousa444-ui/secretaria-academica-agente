# Ferramentas acrescentadas em 13/11/2026: consulta acadêmica e segunda via de
# boleto. Ficam na camada do grafo (como `consultar_regimento`), e não em
# src/agente.py, para não mudar o laço e o verificador da Parte 1.
#
# As regras (Regimento, Art. 11 e Art. 12) são conferidas AQUI, em código: o
# modelo pede, a ferramenta decide se pode. Mesma defesa em profundidade de
# `emitir_documento` (docs/case.md §2.11).
#
# TUDO É FICTÍCIO: o boleto não tem banco, código de barras nem valor de
# pagamento; a linha digitável começa com "000" (nenhum banco usa) e o documento
# impresso traz a marca "SEM VALOR DE PAGAMENTO".

from __future__ import annotations

from datetime import date, timedelta

import dados
from agente import ErroRecuperavel

DIAS_PARA_VENCER = 5  # Regimento, Art. 11: vencimento em 5 dias corridos da emissão


def _aluno(conexao, ra: str):
    aluno = conexao.execute("SELECT * FROM alunos WHERE ra = ?", (ra,)).fetchone()
    if aluno is None:
        conexao.close()
        raise ErroRecuperavel(
            "RA não encontrado no sistema acadêmico", recebido=ra,
            sugestao="peça ao aluno para confirmar o RA uma vez; se não encontrar de "
                     "novo, use escalar_para_humano com motivo 'RA não encontrado'")
    return aluno


def coeficiente(disciplinas: list[dict]) -> float | None:
    """Média das notas concluídas, ponderada pela carga horária (2 casas)."""
    concluidas = [d for d in disciplinas if d["nota"] is not None]
    carga = sum(d["carga_horaria"] for d in concluidas)
    if not carga:
        return None
    return round(sum(d["nota"] * d["carga_horaria"] for d in concluidas) / carga, 2)


def consultar_historico(ra: str) -> dict:
    """LEITURA: disciplinas, notas, situação e coeficiente do aluno (Art. 12)."""
    conexao = dados.conectar()
    aluno = _aluno(conexao, ra)
    linhas = conexao.execute(
        "SELECT codigo, nome, semestre, carga_horaria, nota, situacao FROM disciplinas_cursadas "
        "WHERE ra = ? ORDER BY semestre, codigo", (ra,)).fetchall()
    conexao.close()
    disciplinas = [dict(linha) for linha in linhas]
    return {
        "ra": ra, "nome": aluno["nome"], "curso": aluno["curso"],
        "situacao_matricula": aluno["situacao_matricula"],
        "disciplinas": disciplinas,
        "coeficiente_rendimento": coeficiente(disciplinas),
        "aprovadas": sum(d["situacao"] == "aprovado" for d in disciplinas),
        "reprovadas": sum(d["situacao"] == "reprovado" for d in disciplinas),
        "cursando": sum(d["situacao"] == "cursando" for d in disciplinas),
    }


def linha_digitavel(protocolo: str, valor: float, vencimento: str) -> str:
    """Linha FICTÍCIA no formato visual de um boleto. Banco "000" (inexistente)
    e campos derivados do protocolo: não é pagável em lugar nenhum."""
    numero = protocolo.split("-")[-1].zfill(5)
    centavos = f"{round(valor * 100):010d}"
    dia = vencimento.replace("-", "")
    return f"00090.{numero[:5]} 00000.{dia[:6]} 00000.{dia[6:]}0000 0 0000{centavos}"


def emitir_boleto(ra: str, competencia: str = "") -> dict:
    """ESCRITA: segunda via do boleto de UMA mensalidade em aberto (Art. 11).
    Sem `competencia`, só emite se houver exatamente uma em aberto; com mais de
    uma, devolve a lista para o agente perguntar qual. Idempotente por
    (ra, competencia): pedir de novo devolve o mesmo boleto."""
    conexao = dados.conectar()
    _aluno(conexao, ra)
    abertas = [dict(r) for r in conexao.execute(
        "SELECT competencia, valor, vencimento FROM mensalidades WHERE ra = ? AND status = 'aberta' "
        "ORDER BY competencia", (ra,)).fetchall()]
    if not abertas:
        conexao.close()
        raise ErroRecuperavel(
            "o aluno não tem mensalidade em aberto: não há boleto a emitir (Art. 11)",
            sugestao="diga ao aluno que não há débito em aberto no sistema")
    if not competencia:
        if len(abertas) > 1:
            conexao.close()
            raise ErroRecuperavel(
                "há mais de uma mensalidade em aberto: informe a competência",
                competencias_em_aberto=abertas,
                sugestao="pergunte ao aluno qual competência (AAAA-MM) ele quer, ou "
                         "emita uma de cada vez se ele pedir todas")
        competencia = abertas[0]["competencia"]
    escolhida = next((m for m in abertas if m["competencia"] == competencia), None)
    if escolhida is None:
        conexao.close()
        raise ErroRecuperavel(
            "não há mensalidade em aberto nessa competência (Art. 11: não se emite "
            "boleto de mensalidade quitada ou inexistente)", recebido=competencia,
            competencias_em_aberto=[m["competencia"] for m in abertas])

    existente = conexao.execute(
        "SELECT * FROM boletos_emitidos WHERE ra = ? AND competencia = ?",
        (ra, competencia)).fetchone()
    if existente:
        conexao.close()
        return {**dict(existente), "tipo_documento": "segunda_via_boleto", "ja_existia": True,
                "acesso": "o boleto fica no botão 'Abrir documento' desta conversa"}

    protocolo = f"BOL-{conexao.execute('SELECT COUNT(*) FROM boletos_emitidos').fetchone()[0] + 5001}"
    vencimento = str(date.today() + timedelta(days=DIAS_PARA_VENCER))
    linha = linha_digitavel(protocolo, escolhida["valor"], vencimento)
    conexao.execute(
        "INSERT INTO boletos_emitidos (protocolo, ra, competencia, valor, vencimento, "
        "linha_digitavel, emitido_em) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (protocolo, ra, competencia, escolhida["valor"], vencimento, linha, str(date.today())))
    conexao.commit()
    conexao.close()
    return {"protocolo": protocolo, "ra": ra, "tipo_documento": "segunda_via_boleto",
            "competencia": competencia, "valor": escolhida["valor"], "vencimento": vencimento,
            "linha_digitavel": linha, "ja_existia": False,
            "acesso": "o boleto fica no botão 'Abrir documento' desta conversa"}


FERRAMENTAS = {"consultar_historico": consultar_historico, "emitir_boleto": emitir_boleto}
ESCRITA = {"emitir_boleto"}

DECLARACOES = [
    {"type": "function", "function": {
        "name": "consultar_historico",
        "description": ("Consulta disciplinas, notas, situação (aprovado, reprovado, "
                        "cursando) e coeficiente de rendimento do aluno pelo RA. Use "
                        "quando o aluno perguntar das notas, disciplinas ou situação "
                        "acadêmica. Não altera nada."),
        "parameters": {"type": "object",
                       "properties": {"ra": {"type": "string"}},
                       "required": ["ra"], "additionalProperties": False}}},
    {"type": "function", "function": {
        "name": "emitir_boleto",
        "description": ("ESCRITA: emite a segunda via do boleto de UMA mensalidade em "
                        "aberto. Sem competência, só funciona se houver uma única em "
                        "aberto; se houver várias, a ferramenta devolve a lista para "
                        "você perguntar ao aluno. Nunca use para mensalidade já paga."),
        "parameters": {"type": "object",
                       "properties": {"ra": {"type": "string"},
                                      "competencia": {"type": "string",
                                                      "description": "AAAA-MM; vazio se o aluno não disse"}},
                       "required": ["ra"], "additionalProperties": False}}},
]
