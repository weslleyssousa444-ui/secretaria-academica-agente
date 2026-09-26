# Memória semântica do agente de triagem — Exercício 8.
#
# Fato estável sobre uma entidade (o aluno, pelo RA). Chave-valor, lida por
# chave — nunca por similaridade (Aula 08, nota 02 §3.2): "para onde o
# F-088 costuma viajar" não é pergunta de assunto, é consulta por chave
# primária composta, e o mesmo vale para "RA X tem pendência financeira?".

from __future__ import annotations

import json
from pathlib import Path

CAMINHO_PADRAO = Path(__file__).parent.parent / "dados" / "memoria_semantica.json"


class MemoriaSemantica:
    def __init__(self, caminho: Path | None = None):
        self.caminho = caminho or CAMINHO_PADRAO
        self.fatos: dict = (json.loads(self.caminho.read_text(encoding="utf-8"))
                             if self.caminho.exists() else {})

    def _salvar(self) -> None:
        self.caminho.parent.mkdir(exist_ok=True)
        self.caminho.write_text(json.dumps(self.fatos, ensure_ascii=False, indent=2),
                                 encoding="utf-8")

    def gravar(self, entidade: str, chave: str, valor, data: str) -> dict:
        """Chave de idempotência derivada do CONTEÚDO (`entidade:chave`),
        não de uuid4() — Aula 05, nota 02 §8."""
        id_fato = f"{entidade}:{chave}"
        anterior = self.fatos.get(id_fato)
        if anterior and anterior["valor"] == valor:
            return {**anterior, "ja_existia": True}
        registro = {"entidade": entidade, "chave": chave, "valor": valor,
                    "data": data,
                    "substituiu": anterior["valor"] if anterior else None,
                    "ja_existia": False}
        self.fatos[id_fato] = registro
        self._salvar()
        return registro

    def ler(self, entidade: str, chave: str) -> dict | None:
        return self.fatos.get(f"{entidade}:{chave}")

    def remover(self, entidade: str) -> int:
        chaves = [k for k in self.fatos if k.startswith(f"{entidade}:")]
        for k in chaves:
            del self.fatos[k]
        self._salvar()
        return len(chaves)

    def contem_entidade(self, entidade: str) -> list[str]:
        """Varredura por CONTEÚDO, não só por prefixo de chave — um RA pode
        aparecer dentro do valor de um fato sobre outra entidade."""
        achados = []
        for chave, registro in self.fatos.items():
            if chave.startswith(f"{entidade}:") or entidade in json.dumps(registro, ensure_ascii=False):
                achados.append(chave)
        return achados
