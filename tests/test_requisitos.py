# O requirements.txt da raiz é o do sistema entregue (Parte 3, §6), e tem de ser
# igual ao que a imagem instala (requirements-agente.txt), com versão fixada.

from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def _pacotes(nome):
    return {l.strip() for l in (RAIZ / nome).read_text(encoding="utf-8").splitlines()
            if l.strip() and not l.startswith("#") and not l.startswith("-r")}


def test_requirements_da_raiz_e_o_do_sistema():
    assert _pacotes("requirements.txt") == _pacotes("requirements-agente.txt")


def test_tudo_fixado_inclusive_framework_otel_e_mcp():
    pacotes = _pacotes("requirements.txt")
    assert all("==" in p for p in pacotes)
    nomes = {p.split("==")[0] for p in pacotes}
    assert {"openai", "langgraph", "opentelemetry-sdk", "mcp"} <= nomes
