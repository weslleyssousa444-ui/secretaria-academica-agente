# RAG do Regimento Acadêmico — busca textual (SQLite FTS5, BM25).
#
# POR QUE TEXTUAL E NÃO VETORIAL (docs/rag.md §2): o corpus tem 15 artigos
# numerados, e as perguntas do aluno carregam o vocabulário do próprio
# regimento ("comprovante", "prazo", "trancamento", "gestante"). A busca por
# termo acha isso sem modelo de embedding, sem torch (a imagem do agente tem
# 4 dependências, docs/empacotamento.md §1) e de forma determinística. O que
# ela NÃO acha é paráfrase sem termo em comum — a perda é medida em
# docs/rag.md §4 e é o motivo de o pipeline vetorial do Exercício 7
# (src/rag.py) continuar no repositório como alternativa medida.
#
# CORTE: um chunk por artigo (src/chunking.py), com o capítulo no texto.
# CURADORIA: o artigo revogado (Art. 9º, versão de 72 h) NÃO entra no índice.
# Quem decide que um documento deixou de valer é a curadoria do corpus, e não
# a recuperação — `incluir_revogados=True` existe só para reproduzir o defeito
# (tests/test_regimento.py).

from __future__ import annotations

import re
import sqlite3
import unicodedata
from functools import lru_cache

from chunking import gerar_chunks

# Palavras que casariam com quase todo artigo e só diluem o BM25.
STOPWORDS = frozenset("""
a o as os um uma uns umas de do da dos das em no na nos nas por para com sem
sobre ao aos à às e ou mas que se ser é são foi era está estão como qual quais
quando onde quem meu minha meus minhas seu sua seus suas eu me te lhe nos
isso isto esse essa este esta aquele aquela já não sim também só até mais
menos muito muita pode podem posso preciso precisa quero queria quer fazer
tenho tem têm ter há existe""".split())

TAMANHO_DO_PREFIXO = 5  # casa "emitir/emissão", "trancar/trancamento"


def _sem_acento(texto: str) -> str:
    base = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in base if unicodedata.category(c) != "Mn")


_STOPWORDS_SEM_ACENTO = frozenset(_sem_acento(s) for s in STOPWORDS)


def termos_da_pergunta(pergunta: str) -> list[str]:
    """Palavras com conteúdo, sem acento, sem repetição e sem stopword."""
    vistos: list[str] = []
    for palavra in re.findall(r"[a-zà-ú0-9]+", pergunta.lower()):
        limpa = _sem_acento(palavra)
        if len(limpa) < 3 or limpa in _STOPWORDS_SEM_ACENTO:
            continue
        if limpa not in vistos:
            vistos.append(limpa)
    return vistos


def consulta_fts(termos: list[str]) -> str:
    """OR de prefixos: um trecho basta casar um termo para entrar no ranking;
    o BM25 ordena por quantos e quão raros."""
    partes = []
    for termo in termos:
        radical = termo[:TAMANHO_DO_PREFIXO] if len(termo) > TAMANHO_DO_PREFIXO else termo
        partes.append(f'"{radical}"*')
    return " OR ".join(partes)


class IndiceRegimento:
    def __init__(self, regimento: list[dict] | None = None,
                 incluir_revogados: bool = False):
        self.incluir_revogados = incluir_revogados
        self.chunks = [c for c in gerar_chunks(regimento)
                       if incluir_revogados or c["vigente"]]
        self._por_rowid = {i + 1: c for i, c in enumerate(self.chunks)}
        self._con = sqlite3.connect(":memory:", check_same_thread=False)
        self._con.execute(
            "CREATE VIRTUAL TABLE regimento USING fts5("
            "texto, tokenize='unicode61 remove_diacritics 2')")
        self._con.executemany(
            "INSERT INTO regimento (rowid, texto) VALUES (?, ?)",
            [(rowid, c["texto"]) for rowid, c in self._por_rowid.items()])

    def buscar(self, pergunta: str, k: int = 3) -> list[dict]:
        """Até `k` trechos, do mais relevante ao menos. Lista vazia quando
        nenhum termo da pergunta aparece no regimento: é a recusa por
        ausência, sem limiar a calibrar (o BM25 não tem piso comparável)."""
        termos = termos_da_pergunta(pergunta)
        if not termos:
            return []
        linhas = self._con.execute(
            "SELECT rowid, bm25(regimento) FROM regimento WHERE regimento MATCH ? "
            "ORDER BY bm25(regimento) LIMIT ?", (consulta_fts(termos), k)).fetchall()
        return [{**self._por_rowid[rowid], "score": round(-pontos, 4)}
                for rowid, pontos in linhas]


@lru_cache(maxsize=1)
def indice_padrao() -> IndiceRegimento:
    return IndiceRegimento()


def consultar_regimento(pergunta: str) -> dict:
    """FERRAMENTA do agente (leitura, sem efeito colateral). O modelo decide
    quando chamar (docs/rag.md §5); o retorno traz só os rótulos e o texto
    dos artigos, que são o que ele precisa citar."""
    trechos = indice_padrao().buscar(pergunta)
    if not trechos:
        return {"trechos": [], "total": 0,
                "aviso": "nenhum artigo do Regimento trata deste assunto; "
                         "não responda como se tratasse"}
    return {"trechos": [{"id": t["id"], "texto": t["texto"]} for t in trechos],
            "total": len(trechos)}
