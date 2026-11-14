# O segundo agente do sistema (Parte 3, opcional "multiagente").
#
#   python src/coordenacao.py preparar CASO-3001
#
# DOIS AGENTES, DOIS PAPÉIS, UM LIMITE CADA:
#   - o AGENTE DO ALUNO (src/triagem/) conversa com o aluno e, num trancamento,
#     só ABRE o caso: o grafo pausa esperando a coordenação (Art. 6º);
#   - o ASSISTENTE DA COORDENAÇÃO (este arquivo) pega um caso que está
#     esperando e prepara um PARECER DE APOIO para a pessoa que vai decidir:
#     quem é o aluno, a situação financeira e acadêmica, o artigo aplicável e
#     os pontos de atenção. Ele NÃO decide nem recomenda.
# Os dois se comunicam pelo estado gravado (a tabela `aprovacoes`): o primeiro
# escreve o caso, o segundo o lê. Não há troca de mensagens entre modelos.
#
# O assistente só enxerga o sistema pelo SERVIDOR MCP (src/mcp_secretaria.py),
# que é só leitura: ele não tem como emitir, escalar ou decidir nada, porque
# essas ferramentas não existem do lado dele.
#
# Controles no CÓDIGO (os testes provam com um modelo roteirizado que desobedece):
#   1. o caso tem de estar aguardando a coordenação, conferido antes do modelo;
#   2. ferramenta chamada com outro RA é recusada sem ir ao servidor;
#   3. o parecer é um objeto validado: RA do caso, artigo só se a busca o
#      devolveu, fonte só de ferramenta que respondeu, nenhuma recomendação;
#   4. reprovado duas vezes, o parecer sai montado pelo código a partir dos
#      retornos (origem "contingencia"), como no agente do aluno;
#   5. no máximo MAX_PASSOS chamadas ao modelo.

from __future__ import annotations

import json
import re
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError

import agente
from triagem.modelos import liberado_pelo_ambiente, verificar_modelo

PROMPT = Path(__file__).parent / "prompts" / "coordenacao-v1.txt"
MAX_PASSOS = 8
TENTATIVAS_DE_PARECER = 2
FERRAMENTAS_COM_RA = {"buscar_aluno", "consultar_financeiro", "consultar_historico"}
RECOMENDACAO = re.compile(
    r"recomend|sugiro|sugere-se|aconselh|"
    r"dev(e|eria)\s+ser\s+(aprovad|rejeitad|deferid|indeferid|negad)|"
    r"\b(aprovo|rejeito|defiro|indefiro)\b|"
    r"(pode|podem)\s+ser\s+(aprovad|deferid)\s+sem", re.IGNORECASE)


class Fato(BaseModel):
    texto: str = Field(min_length=3)
    fonte: str


class Parecer(BaseModel):
    protocolo: str
    ra: str
    resumo: str = Field(min_length=10)
    fatos: list[Fato] = Field(min_length=1)
    artigos: list[str] = Field(default_factory=list)
    pontos_de_atencao: list[str] = Field(default_factory=list)


def _ferramentas_openai(lista_mcp) -> list[dict]:
    return [{"type": "function", "function": {
        "name": t.name, "description": t.description or "",
        "parameters": t.inputSchema or {"type": "object", "properties": {}}}}
        for t in lista_mcp.tools]


def _conteudo(resultado) -> dict:
    """O retorno de uma ferramenta MCP como dict (estruturado, se houver)."""
    if getattr(resultado, "structuredContent", None):
        dado = resultado.structuredContent
        return dado.get("result", dado) if isinstance(dado, dict) and set(dado) == {"result"} else dado
    texto = "".join(getattr(c, "text", "") for c in resultado.content)
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        return {"texto": texto}


def validar_parecer(bruto: str, caso: dict, retornos: list[dict]) -> tuple[Parecer | None, list[str]]:
    """Confere o parecer contra o caso e contra o que as ferramentas devolveram."""
    texto = (bruto or "").strip()
    texto = re.sub(r"^```(?:json)?|```$", "", texto).strip()
    try:
        parecer = Parecer.model_validate(json.loads(texto))
    except (json.JSONDecodeError, ValidationError) as e:
        return None, [f"o parecer não é o objeto JSON pedido: {str(e)[:200]}"]
    problemas = []
    if parecer.protocolo != caso["protocolo"]:
        problemas.append(f"protocolo {parecer.protocolo!r} não é o do caso ({caso['protocolo']})")
    ra_caso = (caso.get("aluno") or {}).get("ra")
    if parecer.ra != ra_caso:
        problemas.append(f"RA {parecer.ra!r} não é o do caso ({ra_caso})")
    usadas = {r["ferramenta"] for r in retornos if "erro" not in r["retorno"]}
    for f in parecer.fatos:
        if f.fonte not in usadas:
            problemas.append(f"fato com fonte {f.fonte!r}, que não respondeu nesta preparação")
    devolvidos = {t["id"] for r in retornos if r["ferramenta"] == "consultar_regimento"
                  for t in r["retorno"].get("trechos", [])}
    for art in parecer.artigos:
        if not any(art.strip() == d or d.startswith(art.strip() + " ") for d in devolvidos):
            problemas.append(f"{art!r} não foi devolvido por consultar_regimento")
    texto_livre = " ".join([parecer.resumo, *parecer.pontos_de_atencao, *(f.texto for f in parecer.fatos)])
    if RECOMENDACAO.search(texto_livre):
        problemas.append("o parecer recomenda uma decisão; a decisão é da coordenação (Art. 6º)")
    return (parecer if not problemas else None), problemas


def parecer_por_codigo(caso: dict, retornos: list[dict]) -> Parecer:
    """Contingência: o parecer montado só com os retornos, sem texto do modelo."""
    aluno = caso.get("aluno") or {}
    fatos, pontos = [], []
    ultimo = {r["ferramenta"]: r["retorno"] for r in retornos if "erro" not in r["retorno"]}
    if aluno:
        fatos.append(Fato(texto=f"{aluno['nome']}, RA {aluno['ra']}, {aluno['curso']}, matrícula "
                                f"{aluno['situacao_matricula']}", fonte="casos_aguardando_coordenacao"))
    fin = ultimo.get("consultar_financeiro")
    if fin:
        fatos.append(Fato(texto=f"{fin['mensalidades_em_aberto']} mensalidade(s) em aberto, "
                                f"R$ {fin['valor_em_aberto']:.2f}", fonte="consultar_financeiro"))
        if fin["mensalidades_em_aberto"]:
            pontos.append("há pendência financeira registrada")
    hist = ultimo.get("consultar_historico")
    if hist and hist.get("coeficiente") is not None:
        fatos.append(Fato(texto=f"coeficiente {hist['coeficiente']}", fonte="consultar_historico"))
    artigos = [t["id"] for t in (ultimo.get("consultar_regimento") or {}).get("trechos", [])]
    if aluno.get("situacao_matricula") != "ativa":
        pontos.append(f"a matrícula consta como {aluno.get('situacao_matricula')}")
    return Parecer(protocolo=caso["protocolo"], ra=aluno.get("ra", ""),
                   resumo=(f"Pedido de trancamento {caso['protocolo']} encaminhado pelo agente de "
                           f"atendimento. Motivo registrado: {caso.get('motivo_registrado') or 'não informado'}. "
                           f"Prazo da coordenação: {caso.get('prazo_ate')}."),
                   fatos=fatos or [Fato(texto="caso sem dados do aluno", fonte="casos_aguardando_coordenacao")],
                   artigos=artigos, pontos_de_atencao=pontos)


async def preparar_parecer(protocolo: str, sessao, cliente=None, modelo: str | None = None) -> dict:
    """Prepara o parecer de UM caso, falando com o sistema só pela sessão MCP."""
    cliente = cliente or agente.client
    modelo = modelo or agente.MODELO
    aprovado = verificar_modelo(modelo, liberado_pelo_ambiente())

    pendentes = _conteudo(await sessao.call_tool("casos_aguardando_coordenacao", {}))
    caso = next((c for c in pendentes.get("casos", []) if c["protocolo"] == protocolo), None)
    if caso is None:
        return {"protocolo": protocolo, "erro": "caso não está aguardando a coordenação", "parecer": None}
    ra_caso = (caso.get("aluno") or {}).get("ra")

    ferramentas = _ferramentas_openai(await sessao.list_tools())
    mensagens = [{"role": "system", "content": PROMPT.read_text(encoding="utf-8")},
                 {"role": "user", "content": "Caso a preparar (tela da coordenação):\n"
                                             + json.dumps(caso, ensure_ascii=False)}]
    retornos: list[dict] = [{"ferramenta": "casos_aguardando_coordenacao", "argumentos": {}, "retorno": caso}]
    recusas, problemas, tentativas, passos, tokens = [], [], 0, 0, 0
    parecer = None
    while passos < MAX_PASSOS and tentativas < TENTATIVAS_DE_PARECER:
        passos += 1
        r = cliente.chat.completions.create(model=modelo, temperature=0, messages=mensagens, tools=ferramentas)
        tokens += getattr(getattr(r, "usage", None), "total_tokens", 0) or 0
        msg = r.choices[0].message
        if msg.tool_calls:
            mensagens.append({"role": "assistant", "content": msg.content or "", "tool_calls": [
                {"id": c.id, "type": "function", "function": {"name": c.function.name, "arguments": c.function.arguments}}
                for c in msg.tool_calls]})
            for c in msg.tool_calls:
                try:
                    args = json.loads(c.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                if c.function.name in FERRAMENTAS_COM_RA and str(args.get("ra")) != ra_caso:
                    retorno = {"erro": "recusado: o assistente só consulta o RA do caso", "ra_do_caso": ra_caso}
                    recusas.append({"ferramenta": c.function.name, "argumentos": args})
                else:
                    retorno = _conteudo(await sessao.call_tool(c.function.name, args))
                    retornos.append({"ferramenta": c.function.name, "argumentos": args, "retorno": retorno})
                mensagens.append({"role": "tool", "tool_call_id": c.id,
                                  "content": json.dumps(retorno, ensure_ascii=False)})
            continue
        tentativas += 1
        parecer, problemas = validar_parecer(msg.content, caso, retornos)
        if parecer:
            break
        mensagens += [{"role": "assistant", "content": msg.content or ""},
                      {"role": "user", "content": "O parecer foi recusado pelo código: " + "; ".join(problemas)
                                                  + ". Corrija e responda só com o JSON."}]
    origem = "modelo"
    if parecer is None:
        if not any(r["ferramenta"] == "consultar_regimento" for r in retornos):
            retorno = _conteudo(await sessao.call_tool("consultar_regimento", {"pergunta": "trancamento de matrícula"}))
            retornos.append({"ferramenta": "consultar_regimento", "argumentos": {}, "retorno": retorno})
        if not any(r["ferramenta"] == "consultar_financeiro" for r in retornos) and ra_caso:
            retorno = _conteudo(await sessao.call_tool("consultar_financeiro", {"ra": ra_caso}))
            retornos.append({"ferramenta": "consultar_financeiro", "argumentos": {"ra": ra_caso}, "retorno": retorno})
        parecer, origem = parecer_por_codigo(caso, retornos), "contingencia"
    return {"protocolo": protocolo, "origem": origem, "parecer": parecer.model_dump(),
            "decisao": "cabe à coordenação (Art. 6º)", "problemas_da_ultima_tentativa": problemas,
            "ferramentas": [r["ferramenta"] for r in retornos], "recusas": recusas,
            "chamadas_ao_modelo": passos, "tokens": tokens, "modelo": modelo, "modelo_aprovado": aprovado}


@asynccontextmanager
async def sessao_stdio():
    """Abre o servidor MCP como subprocesso (stdio), com o mesmo banco."""
    import os
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    import dados
    parametros = StdioServerParameters(
        command=sys.executable, args=[str(Path(__file__).parent / "mcp_secretaria.py")],
        env={**os.environ, "ACADEMICO_DB": str(dados.CAMINHO_DB)})
    async with stdio_client(parametros) as (leitura, escrita):
        async with ClientSession(leitura, escrita) as sessao:
            await sessao.initialize()
            yield sessao


async def preparar_pelo_servidor(protocolo: str) -> dict:
    async with sessao_stdio() as sessao:
        return await preparar_parecer(protocolo, sessao)
