# Infraestrutura dos testes de governança (Exercício 12).
#
# Os testes rodam OFFLINE: nenhuma chamada à Groq. O cliente do modelo é
# substituído por um roteiro (`ModeloRoteirizado`) que devolve as chamadas
# de ferramenta que um modelo real PODERIA propor — inclusive as proibidas.
# É isso que permite provar que um limite vale "fora do modelo": o roteiro
# desobedece o prompt de propósito, e o teste verifica que o código barra.
#
# Cada teste usa um banco SQLite próprio em tmp_path — nunca toca
# dados/academico.db.

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / "src"))

# agente.py instancia o cliente OpenAI no import; sem chave o SDK recusa.
# O valor é falso de propósito: nenhum teste chega a usar a rede.
os.environ.setdefault("OPENAI_API_KEY", "teste-offline-sem-rede")

import agente  # noqa: E402
import dados  # noqa: E402


@pytest.fixture
def banco(tmp_path, monkeypatch):
    """Banco sintético novo por teste, com as mesmas sementes de dados.py."""
    monkeypatch.setattr(dados, "CAMINHO_DB", tmp_path / "academico.db")
    dados.inicializar(forcar=True)
    return dados


def contar(tabela: str) -> int:
    conexao = dados.conectar()
    n = conexao.execute(f"SELECT COUNT(*) FROM {tabela}").fetchone()[0]
    conexao.close()
    return n


def chamada(nome: str, **argumentos) -> SimpleNamespace:
    return SimpleNamespace(
        id=f"call-{nome}-{len(json.dumps(argumentos))}",
        function=SimpleNamespace(name=nome, arguments=json.dumps(argumentos)))


def resposta(tool_calls=None, content=None) -> SimpleNamespace:
    return SimpleNamespace(
        usage=SimpleNamespace(total_tokens=100, prompt_tokens=80, completion_tokens=20),
        choices=[SimpleNamespace(message=SimpleNamespace(
            tool_calls=tool_calls, content=content))])


class ModeloRoteirizado:
    """Substitui `agente.client`: devolve as respostas na ordem do roteiro.
    Quando o roteiro acaba, repete a última (útil para testar orçamento e
    detector de laço)."""

    def __init__(self, roteiro: list):
        self.roteiro = list(roteiro)
        self.chamadas = 0
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.chamadas += 1
        item = self.roteiro.pop(0) if len(self.roteiro) > 1 else self.roteiro[0]
        if isinstance(item, Exception):
            raise item
        return item


@pytest.fixture
def modelo(monkeypatch):
    def instalar(roteiro: list) -> ModeloRoteirizado:
        falso = ModeloRoteirizado(roteiro)
        monkeypatch.setattr(agente, "client", falso)
        return falso
    return instalar
