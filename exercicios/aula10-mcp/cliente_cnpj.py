# Exercício 10 — Cliente MCP: CNPJ -> CEP -> endereço.
#
# Uso: python cliente_cnpj.py 19.131.243/0001-97
# (com o servidor já rodando: python servidor_cnpj_cep.py)
#
# RESPOSTA À QUESTÃO DO ENUNCIADO: "o cliente que você escreveu conhece a
# BrasilAPI? O que mudaria se o servidor trocasse de fonte?"
#
# Não conhece. Este arquivo não tem nenhuma linha com "brasilapi.com.br" —
# só chama `consultar_cnpj`/`consultar_cep` pelo nome, via MCP. Se o
# servidor trocasse a BrasilAPI por outra fonte (Receita direto, um banco
# interno), o único lugar que mudaria é servidor_cnpj_cep.py: os nomes das
# ferramentas, os campos que elas devolvem (cnpj, razao_social, cep...) e
# os formatos de erro já são o CONTRATO — é exatamente o ponto da nota 01
# desta aula (§1): o cliente depende do schema publicado, não da
# implementação por trás dele. Única ressalva: se os NOMES dos campos
# devolvidos mudassem (ex.: "street" virasse "logradouro" no CEP), este
# cliente quebraria — é o preço do "contrato público" da nota 02, §2.

from __future__ import annotations

import asyncio
import json
import sys

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

SERVIDOR_URL = "http://127.0.0.1:8000/mcp"


def _conteudo(resposta) -> dict:
    """`structuredContent` vem None com `-> dict` solto (sem schema
    nomeado); o dado real está em content[0].text, como JSON."""
    if resposta.structuredContent is not None:
        return resposta.structuredContent
    return json.loads(resposta.content[0].text)


def _so_digitos(texto: str) -> str:
    return "".join(c for c in texto if c.isdigit())


def _formatar_cep(digitos: str) -> str:
    return f"{digitos[0:5]}-{digitos[5:8]}"


async def principal(cnpj_bruto: str) -> None:
    async with streamablehttp_client(SERVIDOR_URL) as (leitura, escrita, _):
        async with ClientSession(leitura, escrita) as sessao:
            await sessao.initialize()

            ferramentas = (await sessao.list_tools()).tools
            nomes = {f.name for f in ferramentas}
            print(f"SERVIDOR: brasilapi-cnpj-cep   "
                  f"(ferramentas: {', '.join(sorted(nomes))})\n")
            faltando = {"consultar_cnpj", "consultar_cep"} - nomes
            if faltando:
                print(f"ERRO: o servidor não expõe {faltando}")
                return

            resp_cnpj = await sessao.call_tool(
                "consultar_cnpj", {"cnpj": cnpj_bruto})
            dados_cnpj = _conteudo(resp_cnpj)

            print(f"CNPJ ............ {cnpj_bruto}")
            if "erro" in dados_cnpj:
                print(f"ERRO ............ {dados_cnpj['erro']}")
                if dados_cnpj.get("detalhe"):
                    print(f"                  {dados_cnpj['detalhe']}")
                print(f"Sugestão ........ {dados_cnpj.get('sugestao', '')}")
                return  # requisito 4: erro de domínio na 1ª consulta -> não faz a 2ª

            print(f"Razão social .... {dados_cnpj['razao_social']}")
            cep = dados_cnpj["cep"]
            print(f"CEP ............. {_formatar_cep(cep)}")

            resp_cep = await sessao.call_tool("consultar_cep", {"cep": cep})
            dados_cep = _conteudo(resp_cep)

            if "erro" in dados_cep:
                print(f"ERRO (CEP) ...... {dados_cep['erro']}")
                return

            endereco = (f"{dados_cep['street']} — {dados_cep['neighborhood']}, "
                        f"{dados_cep['city']}/{dados_cep['state']}")
            print(f"Endereço ........ {endereco}")

            lat, lon = dados_cep.get("latitude"), dados_cep.get("longitude")
            if lat and lon:
                print(f"Lat / Long ...... {lat} / {lon}")
            else:
                print("Lat / Long ...... não disponível para este CEP")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("uso: python cliente_cnpj.py <CNPJ>")
        sys.exit(1)
    asyncio.run(principal(sys.argv[1]))


# ============================================================================
# SAÍDA REAL dos três testes exigidos (copiada de uma execução, 02/10/2026)
# ============================================================================
#
# $ python cliente_cnpj.py "19.131.243/0001-97"   (válido, com coordenadas)
# SERVIDOR: brasilapi-cnpj-cep   (ferramentas: consultar_cep, consultar_cnpj)
#
# CNPJ ............ 19.131.243/0001-97
# Razão social .... OPEN KNOWLEDGE BRASIL
# CEP ............. 01311-902
# Endereço ........ Avenida Paulista 37 — Bela Vista, São Paulo/SP
# Lat / Long ...... -23.5475 / -46.63611
#
# $ python cliente_cnpj.py "123.456"   (formato inválido — poucos dígitos)
# SERVIDOR: brasilapi-cnpj-cep   (ferramentas: consultar_cep, consultar_cnpj)
#
# CNPJ ............ 123.456
# ERRO ............ cnpj com quantidade errada de dígitos
# Sugestão ........ reenvie com 14 dígitos, com ou sem pontuação
#
# $ python cliente_cnpj.py "11.111.111/0001-99"   (14 dígitos, mas inválido)
# SERVIDOR: brasilapi-cnpj-cep   (ferramentas: consultar_cep, consultar_cnpj)
#
# CNPJ ............ 11.111.111/0001-99
# ERRO ............ cnpj com dígito verificador inválido
# Sugestão ........ confira se os 14 dígitos foram digitados corretamente —
#                   o cálculo do dígito verificador não bateu
#
# Achado real: a BrasilAPI valida o dígito verificador do CNPJ antes de
# consultar a Receita, e nunca devolveu um 404 "formato válido, mas não
# existe" nos testes feitos (até CNPJs com dígito verificador correto, mas
# gerados ao acaso, bateram em empresas reais — o espaço de CNPJs válidos
# está densamente ocupado). Por isso este terceiro teste usa um CNPJ de
# formato correto com dígito verificador inválido, que é o caso real mais
# comum de erro do usuário (digitou um número errado), em vez de um 404
# genuíno que a API, na prática, não produziu nos testes.
