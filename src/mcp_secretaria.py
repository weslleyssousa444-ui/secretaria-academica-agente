# Servidor MCP da secretaria (Parte 3, opcional "MCP").
#
#   python src/mcp_secretaria.py                 # stdio (o assistente da coordenação o abre assim)
#   python src/mcp_secretaria.py --http 8765     # Streamable HTTP, para outro cliente MCP
#
# POR QUE EXISTE: até 13/11 o sistema tinha UM agente, e o MCP não se
# justificava (docs/case.md §7). Com o segundo agente (o assistente da
# coordenação, src/assistente_coordenacao.py), a consulta ao sistema acadêmico
# passa a ter dois consumidores, e é isso que este servidor publica: as
# MESMAS funções que o agente do aluno usa, num protocolo que qualquer
# cliente MCP entende.
#
# SÓ LEITURA, de propósito. Nenhuma ferramenta de escrita (emitir documento,
# boleto, escalar, decidir) é publicada aqui: as escritas do sistema passam
# pelos controles do grafo (RA da sessão, no máximo 1 escrita por turno,
# docs/seguranca.md), e um servidor MCP aberto seria um caminho para contorná-
# los. O teste `test_mcp_nao_publica_escrita` trava isso.
#
# Erro de DOMÍNIO (RA inexistente) volta como CONTEÚDO, com a sugestão, como
# no Exercício 10: quem chamou lê e decide. Erro de infraestrutura vira exceção.

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mcp.server.fastmcp import FastMCP  # noqa: E402

import agente  # noqa: E402
import dados  # noqa: E402
from triagem import humano, regimento, servicos  # noqa: E402

servidor = FastMCP("secretaria-academica")

FERRAMENTAS_PUBLICADAS = ("buscar_aluno", "consultar_financeiro", "consultar_historico",
                          "consultar_regimento", "casos_aguardando_coordenacao")


def _dominio(funcao, *args) -> dict:
    try:
        return funcao(*args)
    except agente.ErroRecuperavel as e:
        return e.payload


@servidor.tool()
def buscar_aluno(ra: str) -> dict:
    """Cadastro do aluno pelo RA: nome, curso e situação da matrícula. Só leitura."""
    return _dominio(agente.buscar_aluno, ra)


@servidor.tool()
def consultar_financeiro(ra: str) -> dict:
    """Mensalidades em aberto e valor em aberto do aluno. Só leitura."""
    return _dominio(agente.consultar_financeiro, ra)


@servidor.tool()
def consultar_historico(ra: str) -> dict:
    """Disciplinas cursadas, notas por semestre e coeficiente do aluno. Só leitura."""
    return _dominio(servicos.consultar_historico, ra)


@servidor.tool()
def consultar_regimento(pergunta: str) -> dict:
    """Artigos do Regimento Acadêmico que tratam da pergunta (busca FTS5). Só leitura."""
    return regimento.consultar_regimento(pergunta)


@servidor.tool()
def casos_aguardando_coordenacao() -> dict:
    """Trancamentos que o agente do aluno encaminhou e que esperam a coordenação,
    com o motivo registrado e o prazo. Só leitura: decidir é da pessoa."""
    casos = humano.pendentes()
    return {"casos": casos, "total": len(casos)}


def main() -> int:
    ap = argparse.ArgumentParser(description="Servidor MCP (só leitura) da secretaria acadêmica")
    ap.add_argument("--http", type=int, metavar="PORTA", help="Streamable HTTP em 127.0.0.1:PORTA")
    args = ap.parse_args()
    dados.inicializar()
    if args.http:
        servidor.settings.host, servidor.settings.port = "127.0.0.1", args.http
        servidor.run(transport="streamable-http")
    else:
        servidor.run(transport="stdio")
    return 0


if __name__ == "__main__":
    sys.exit(main())
