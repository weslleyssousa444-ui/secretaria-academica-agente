# Exercício 10 — Servidor MCP de CNPJ e CEP.
#
# CARIMBO: revisão da especificação do protocolo MCP = 2026-07-28 (núcleo
# sem estado); SDK `mcp` — ver versão instalada em .venv311
# (requirements-mcp.txt). Streamable HTTP, igual ao laboratório da aula
# (00-servidor.py) — servidor roda sozinho, num terminal próprio.
#
# Embrulha duas consultas da BrasilAPI (https://brasilapi.com.br/docs, sem
# chave): CNPJ e CEP. Timeout definido em toda chamada HTTP (nota 02-
# escrever-um-servidor §4): sem ele, uma BrasilAPI lenta prende o servidor
# e o cliente junto.
#
# Classificação de erro (nota 02, §4): erro de DOMÍNIO (formato errado,
# dígito verificador inválido, não encontrado) volta como CONTEÚDO — o
# modelo/cliente lê o que errou e o que fazer. Erro de INFRAESTRUTURA
# (timeout, 5xx) vira EXCEÇÃO — o SDK do servidor converte isso em falha
# de protocolo (isError=true), tratada pelo cliente como transporte, não
# como observação para o modelo raciocinar sobre ela.

from __future__ import annotations

import re

import httpx
from mcp.server.fastmcp import FastMCP

TIMEOUT = httpx.Timeout(10.0)
BASE_URL = "https://brasilapi.com.br/api"

servidor = FastMCP("brasilapi-cnpj-cep")

UFS = {
    "AC": "Acre", "AL": "Alagoas", "AP": "Amapá", "AM": "Amazonas",
    "BA": "Bahia", "CE": "Ceará", "DF": "Distrito Federal",
    "ES": "Espírito Santo", "GO": "Goiás", "MA": "Maranhão",
    "MT": "Mato Grosso", "MS": "Mato Grosso do Sul", "MG": "Minas Gerais",
    "PA": "Pará", "PB": "Paraíba", "PR": "Paraná", "PE": "Pernambuco",
    "PI": "Piauí", "RJ": "Rio de Janeiro", "RN": "Rio Grande do Norte",
    "RS": "Rio Grande do Sul", "RO": "Rondônia", "RR": "Roraima",
    "SC": "Santa Catarina", "SP": "São Paulo", "SE": "Sergipe",
    "TO": "Tocantins",
}


def _so_digitos(texto: str) -> str:
    return re.sub(r"\D", "", texto)


def _cnpj_check_digitos_ok(digitos: str) -> bool:
    """Valida o dígito verificador localmente — evita gastar uma chamada
    HTTP com algo que já se sabe malformado antes de sair do processo."""
    def calc(nums: list[int], pesos: list[int]) -> int:
        soma = sum(n * p for n, p in zip(nums, pesos))
        resto = soma % 11
        return 0 if resto < 2 else 11 - resto

    nums = [int(c) for c in digitos]
    d1 = calc(nums[:12], [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    d2 = calc(nums[:12] + [d1], [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    return nums[12] == d1 and nums[13] == d2


def _chamar(url: str) -> httpx.Response:
    try:
        return httpx.get(url, timeout=TIMEOUT)
    except httpx.TimeoutException as e:
        raise RuntimeError(f"timeout consultando a BrasilAPI: {url}") from e
    except httpx.HTTPError as e:
        raise RuntimeError(f"falha de rede consultando a BrasilAPI: {e}") from e


@servidor.tool()
def consultar_cnpj(cnpj: str) -> dict:
    """Consulta dados cadastrais de uma empresa na Receita Federal pelo CNPJ,
    via BrasilAPI.

    cnpj: 14 dígitos, com ou sem pontuação — aceita "19.131.243/0001-97" ou
    "19131243000197". CNPJ com quantidade errada de dígitos ou com dígito
    verificador inválido devolve erro explicando o que esperava.

    Devolve: cnpj, razao_social, cep, logradouro, numero, complemento,
    bairro, municipio, uf.

    NÃO devolve coordenadas geográficas nem endereço formatado para
    exibição — para isso, pegue o campo "cep" desta resposta e chame
    consultar_cep com ele. NÃO verifica situação cadastral (ativa/baixada)
    nem traz o quadro de sócios.
    """
    digitos = _so_digitos(cnpj)
    if len(digitos) != 14:
        return {"erro": "cnpj com quantidade errada de dígitos",
                "recebido": cnpj, "esperado": "14 dígitos numéricos",
                "sugestao": "reenvie com 14 dígitos, com ou sem pontuação"}
    if not _cnpj_check_digitos_ok(digitos):
        return {"erro": "cnpj com dígito verificador inválido",
                "recebido": digitos,
                "sugestao": "confira se os 14 dígitos foram digitados "
                            "corretamente — o cálculo do dígito verificador "
                            "não bateu"}

    r = _chamar(f"{BASE_URL}/cnpj/v1/{digitos}")
    if r.status_code == 404:
        return {"erro": "cnpj não encontrado na Receita Federal",
                "recebido": digitos,
                "sugestao": "confira os dígitos; este CNPJ pode nunca ter "
                            "sido registrado"}
    if r.status_code == 400:
        return {"erro": "cnpj rejeitado pela BrasilAPI",
                "recebido": digitos, "detalhe": r.json().get("message", ""),
                "sugestao": "confira os 14 dígitos"}
    if r.status_code >= 500:
        raise RuntimeError(f"BrasilAPI indisponível (status {r.status_code}) "
                            f"ao consultar CNPJ")
    r.raise_for_status()
    dados = r.json()
    return {
        "cnpj": dados.get("cnpj"),
        "razao_social": dados.get("razao_social"),
        "cep": dados.get("cep"),
        "logradouro": dados.get("logradouro"),
        "numero": dados.get("numero"),
        "complemento": dados.get("complemento"),
        "bairro": dados.get("bairro"),
        "municipio": dados.get("municipio"),
        "uf": dados.get("uf"),
    }


@servidor.tool()
def consultar_cep(cep: str) -> dict:
    """Consulta endereço e coordenadas geográficas de um CEP, via BrasilAPI.

    cep: 8 dígitos, com ou sem hífen — aceita "01311-902" ou "01311902".
    CEP com quantidade errada de dígitos devolve erro explicando o que
    esperava.

    Devolve: cep, street, neighborhood, city, state, latitude, longitude.
    latitude/longitude vêm como null quando a BrasilAPI não tem essa
    informação para o CEP consultado — isso acontece para alguns CEPs, e
    não é erro.

    NÃO busca CEP a partir de nome de rua ou cidade — só aceita o CEP
    numérico como entrada.
    """
    digitos = _so_digitos(cep)
    if len(digitos) != 8:
        return {"erro": "cep com quantidade errada de dígitos",
                "recebido": cep, "esperado": "8 dígitos numéricos",
                "sugestao": "reenvie com 8 dígitos, com ou sem hífen"}

    r = _chamar(f"{BASE_URL}/cep/v2/{digitos}")
    if r.status_code == 404:
        return {"erro": "cep não encontrado", "recebido": digitos,
                "sugestao": "confira os dígitos; este CEP pode não existir"}
    if r.status_code == 400:
        return {"erro": "cep rejeitado pela BrasilAPI",
                "recebido": digitos, "detalhe": r.json().get("message", ""),
                "sugestao": "confira os 8 dígitos"}
    if r.status_code >= 500:
        raise RuntimeError(f"BrasilAPI indisponível (status {r.status_code}) "
                            f"ao consultar CEP")
    r.raise_for_status()
    dados = r.json()
    coords = (dados.get("location") or {}).get("coordinates") or {}
    return {
        "cep": dados.get("cep"),
        "street": dados.get("street"),
        "neighborhood": dados.get("neighborhood"),
        "city": dados.get("city"),
        "state": dados.get("state"),
        "latitude": coords.get("latitude"),
        "longitude": coords.get("longitude"),
    }


@servidor.resource("ufs://brasil")
def lista_ufs() -> dict:
    """Lista fixa das 27 UFs brasileiras (sigla -> nome por extenso).

    É RECURSO, não ferramenta (Desafio B do exercício): a aplicação sempre
    sabe, antes do laço começar, que vai precisar formatar "São Paulo (SP)"
    a partir de uma sigla — não é uma decisão que deva depender do modelo
    lembrar de chamar uma ferramenta para isso. Dado estático, sem consulta
    de rede."""
    return UFS


if __name__ == "__main__":
    servidor.run(transport="streamable-http")
