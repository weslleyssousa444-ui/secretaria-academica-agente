# Índice de embeddings do Regimento Acadêmico — Exercício 7.
#
# Escolha de embedding: LOCAL (sentence-transformers), não pela API da Groq.
# A Groq (docs/modelos.md §3.5) não oferece endpoint de embeddings nesta
# conta — `client.models.list()` não devolve nenhum modelo desse tipo. Em
# vez de trocar de provedor de novo, usamos um modelo de embedding local,
# multilíngue, sem custo e sem risco de rate limit — o mesmo motivo prático
# que já levou à troca Mistral -> Groq no Exercício 6.
#
# Escolha de banco: NENHUM banco vetorial. O corpus tem ~14 artigos — a
# mesma ordem de grandeza que docs/base-de-conhecimento-v1.md §3 já havia
# previsto ("dezenas de chunks, não milhares") e para a qual a nota 04 da
# Aula 06 mediu que uma matriz numpy em memória vence bancos vetoriais.

from __future__ import annotations

from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

from chunking import gerar_chunks

MODELO_EMBEDDING = "paraphrase-multilingual-MiniLM-L12-v2"
CAMINHO_CACHE = Path(__file__).parent.parent / "dados" / "embeddings_regimento.npz"

_modelo = None


def _carregar_modelo() -> SentenceTransformer:
    global _modelo
    if _modelo is None:
        _modelo = SentenceTransformer(MODELO_EMBEDDING)
    return _modelo


class IndiceRAG:
    """Busca vetorial por cosseno, em matriz numpy — sem banco vetorial
    (ver cabeçalho do arquivo). `apenas_vigentes` é o filtro de metadado da
    nota 02 §2 ("filtrar ANTES de ordenar por similaridade"); por padrão
    fica desligado de propósito, para que o modo de falha 4 (nota 04 §6)
    seja reproduzível — ver `src/modos_de_falha.py`."""

    def __init__(self, chunks: list[dict] | None = None):
        self.chunks = chunks if chunks is not None else gerar_chunks()
        self.matriz = self._carregar_ou_calcular()

    def _carregar_ou_calcular(self) -> np.ndarray:
        ids_atuais = [c["id"] for c in self.chunks]
        if CAMINHO_CACHE.exists():
            dados = np.load(CAMINHO_CACHE, allow_pickle=True)
            if list(dados["ids"]) == ids_atuais:
                return dados["matriz"]
        modelo = _carregar_modelo()
        textos = [c["texto"] for c in self.chunks]
        matriz = modelo.encode(textos, normalize_embeddings=True)
        CAMINHO_CACHE.parent.mkdir(exist_ok=True)
        np.savez(CAMINHO_CACHE, matriz=matriz,
                 ids=np.array(ids_atuais, dtype=object))
        return matriz

    def buscar(self, pergunta: str, k: int = 3,
               apenas_vigentes: bool = False) -> list[dict]:
        modelo = _carregar_modelo()
        vetor_pergunta = modelo.encode([pergunta], normalize_embeddings=True)[0]
        # Vetores normalizados -> produto escalar == similaridade de cosseno
        # (Aula 06, nota 01).
        scores = self.matriz @ vetor_pergunta

        indices = range(len(self.chunks))
        if apenas_vigentes:
            indices = [i for i in indices if self.chunks[i]["vigente"]]
        indices_ordenados = sorted(indices, key=lambda i: scores[i],
                                    reverse=True)[:k]

        resultados = []
        for i in indices_ordenados:
            r = dict(self.chunks[i])
            r["score"] = float(scores[i])
            resultados.append(r)
        return resultados


if __name__ == "__main__":
    indice = IndiceRAG()
    print(f"Índice com {len(indice.chunks)} chunks, "
          f"modelo de embedding: {MODELO_EMBEDDING}\n")
    for pergunta in ["qual o prazo de resposta da secretaria?",
                     "posso trancar só uma disciplina?"]:
        print(f"pergunta: {pergunta!r}")
        for r in indice.buscar(pergunta, k=3):
            vig = "vigente" if r["vigente"] else "REVOGADO"
            print(f"  {r['score']:.4f}  {r['id']:<32} [{vig}]")
        print()
