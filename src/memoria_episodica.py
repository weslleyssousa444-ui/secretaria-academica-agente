# Memória episódica do agente de triagem — Exercício 8.
#
# O que aconteceu, e quando, em execuções passadas. Reaproveita o mesmo
# embedding local do Exercício 7 (src/indice_rag.py) — mesmo motivo: a Groq
# não tem endpoint de embeddings nesta conta, e o volume aqui é ainda menor
# que o do Regimento.
#
# Metadado por episódio, e por que (Aula 08, nota 02 §3.1, adaptado das
# cegueiras da Aula 07 nota 02):
#   ra    -> cegueira de entidade: identificador não é significado
#   data  -> cegueira de tempo: o vetor não representa anterioridade

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

MODELO_EMBEDDING = "paraphrase-multilingual-MiniLM-L12-v2"  # mesmo do Ex.7
CAMINHO_PADRAO = Path(__file__).parent.parent / "dados" / "memoria_episodica.json"

_modelo = None


def _carregar_modelo() -> SentenceTransformer:
    global _modelo
    if _modelo is None:
        _modelo = SentenceTransformer(MODELO_EMBEDDING)
    return _modelo


class MemoriaEpisodica:
    def __init__(self, caminho: Path | None = None):
        self.caminho = caminho or CAMINHO_PADRAO
        self.episodios: list[dict] = (
            json.loads(self.caminho.read_text(encoding="utf-8"))
            if self.caminho.exists() else [])

    def _salvar(self) -> None:
        self.caminho.parent.mkdir(exist_ok=True)
        self.caminho.write_text(json.dumps(self.episodios, ensure_ascii=False, indent=2),
                                 encoding="utf-8")

    def gravar(self, resumo: str, ra: str, data: str, tipo_pedido: str,
               veredito: str) -> dict:
        """Chave de idempotência derivada do CONTEÚDO — ra+data+resumo —,
        não de uuid4()."""
        id_ep = hashlib.sha1(f"{ra}:{data}:{resumo}".encode()).hexdigest()[:10]
        if any(e["id"] == id_ep for e in self.episodios):
            return {"id": id_ep, "ja_existia": True}
        vetor = _carregar_modelo().encode([resumo], normalize_embeddings=True)[0].tolist()
        registro = {"id": id_ep, "resumo": resumo, "ra": ra, "data": data,
                    "tipo_pedido": tipo_pedido, "veredito": veredito, "vetor": vetor}
        self.episodios.append(registro)
        self._salvar()
        return {"id": id_ep, "ja_existia": False}

    def recuperar(self, consulta: str, k: int = 3, ra: str | None = None,
                   meia_vida_dias: int = 180) -> list[dict]:
        """Filtra por RA (metadado) ANTES de ordenar por similaridade — Aula
        07, nota 02 §2. `score_ponderado` REBAIXA por idade (decaimento,
        Aula 08 nota 04 §2), sem apagar: o episódio raro e antigo continua
        recuperável, só perde a competição com um mais recente equivalente."""
        candidatos = self.episodios if ra is None else [e for e in self.episodios if e["ra"] == ra]
        if not candidatos:
            return []
        vetor_consulta = _carregar_modelo().encode([consulta], normalize_embeddings=True)[0]
        hoje = date.today()
        resultados = []
        for e in candidatos:
            score = float(np.dot(np.array(e["vetor"]), vetor_consulta))
            idade_dias = max((hoje - date.fromisoformat(e["data"])).days, 0)
            peso_recencia = 0.5 ** (idade_dias / meia_vida_dias)
            resultados.append({
                "id": e["id"], "resumo": e["resumo"], "ra": e["ra"], "data": e["data"],
                "tipo_pedido": e["tipo_pedido"], "veredito": e["veredito"],
                "score": score, "score_ponderado": round(score * peso_recencia, 4),
            })
        resultados.sort(key=lambda r: r["score_ponderado"], reverse=True)
        return resultados[:k]

    def remover(self, ra: str) -> int:
        antes = len(self.episodios)
        self.episodios = [e for e in self.episodios if e["ra"] != ra]
        self._salvar()
        return antes - len(self.episodios)

    def contem_ra(self, ra: str) -> list[str]:
        """Varredura por CONTEÚDO, não só por metadado — o RA pode aparecer
        dentro do texto do resumo mesmo que o campo `ra` seja de outro
        titular (ex.: um episódio que cita os dois lados de uma comparação)."""
        return [e["id"] for e in self.episodios if e["ra"] == ra or ra in e["resumo"]]


def mais_recente(candidatos: list[dict], campo: str = "data") -> dict | None:
    """O desempate de contradição (Aula 08, nota 04 §1.1) — determinístico,
    sem chamada ao modelo. Delegar isso ao modelo é o antipadrão: ele erra,
    cobra uma chamada e não é verificável."""
    return max(candidatos, key=lambda c: c[campo]) if candidatos else None


def desempatar_por_tempo(recuperados: list[dict]) -> dict:
    """O descarte é REGISTRADO (nota 04 §1.2) — um agente que ignora um
    fato contraditório em silêncio é indistinguível de um que nunca o
    recuperou."""
    vencedor = mais_recente(recuperados)
    return {"vigente": vencedor,
            "descartados": [r for r in recuperados if r["id"] != vencedor["id"]]}
