# Evidência das LACUNAS declaradas em docs/model-card.md.
#
# Estes testes PASSAM descrevendo o comportamento atual, que é o defeito.
# Quando uma lacuna for corrigida, o teste correspondente passa a falhar e
# deve ser invertido (virar um teste de autoridade em test_autoridade.py).
# O identificador L-xx no nome é o da seção Lacunas do model card.

from __future__ import annotations

import inspect
import json
from dataclasses import asdict
from pathlib import Path

import agente
from agente import Estado
from conftest import RAIZ, contar

LOG_DIVERGENCIA = RAIZ / "logs" / "02-divergencia-9aee9313.json"


def test_L01_sem_verificacao_de_identidade(banco):
    """Nenhuma ferramenta recebe a identidade de quem está no chat: qualquer
    pessoa que digite um RA de terceiro recebe a declaração com o nome dele."""
    for nome, funcao in agente.FERRAMENTAS.items():
        assert "ra_autenticado" not in inspect.signature(funcao).parameters, nome
    r = agente.emitir_documento("20231234", "declaracao_matricula")  # RA de outra pessoa
    assert r["ja_existia"] is False
    assert agente.buscar_aluno("20231234")["nome"] == "Pedro Akira"
    assert agente.consultar_financeiro("20230198")["valor_em_aberto"] == 890.0


# L02 (escalonamento de trancamento dependia do modelo) foi corrigida em
# src/agente.py (`escalonamento_de_trancamento_devido`); o teste virou
# test_trancamento_*_pelo_codigo em test_autoridade.py.


def test_L03_chave_de_idempotencia_vem_do_modelo(banco):
    """A chave é argumento escrito pelo modelo: duas redações do mesmo motivo
    abrem dois casos para o mesmo pedido."""
    agente.escalar_para_humano("20229012", "trancamento_matricula", "trancamento",
                               "20229012:trancamento_matricula:trancamento")
    agente.escalar_para_humano("20229012", "trancamento_matricula", "trancamento",
                               "20229012:trancamento_matricula:pedido de trancamento")
    assert contar("casos_pendentes") == 2


def test_L04_limite_de_custo_inerte_nos_modelos_groq():
    """Preço 0 no dicionário: `max_reais` nunca é atingido no provedor atual,
    e modelo fora do dicionário também custa 0."""
    assert agente.custo(10**7, 10**7, "qwen/qwen3.8-27b") == 0.0
    assert agente.custo(10**7, 10**7, "modelo-que-nao-esta-no-dicionario") == 0.0


def test_L05_registro_sem_instante_modelo_prompt_nem_revisao():
    """O registro de execução (asdict(Estado)) não tem instante, modelo
    servido, versão de prompt, versão de política nem campo de revisão H."""
    campos = set(asdict(Estado()))
    assert campos == {"execucao_id", "caso", "passos", "tokens_gastos",
                      "custo_estimado", "termino", "motivo", "historico"}


def test_L06_log_versionado_guarda_dado_pessoal_e_raciocinio():
    """O log real do caso de divergência, versionado no git, guarda nome,
    valor em aberto e o raciocínio do modelo em texto livre."""
    texto = LOG_DIVERGENCIA.read_text(encoding="utf-8")
    assert "Marina Alves" in texto
    assert "890.0" in texto
    assert "reasoning=" in texto
    log = json.loads(texto)
    assert "modelo" not in log and "t" not in log


def test_L07_chat_nao_grava_registro_de_execucao():
    """O ponto de entrada interativo (chat.py) não chama salvar_log: uma
    conversa real não deixa registro nenhum."""
    fonte = (RAIZ / "src" / "chat.py").read_text(encoding="utf-8")
    assert "salvar_log" not in fonte
    fonte_verificador = (RAIZ / "src" / "verificador.py").read_text(encoding="utf-8")
    assert "salvar_log" not in fonte_verificador


def test_L08_uma_unica_chave_para_todos_os_componentes():
    """Agente, RAG, juiz de fidelidade, memória e LangGraph leem a mesma
    variável OPENAI_API_KEY: não há chave por carga de trabalho."""
    arquivos = ["src/agente.py", "src/rag.py",
                "exercicios/aula09-langgraph/agente_langgraph.py"]
    for caminho in arquivos:
        fonte = (RAIZ / caminho).read_text(encoding="utf-8")
        assert 'environ.get("OPENAI_API_KEY")' in fonte, caminho


def test_L09_nomes_da_base_sintetica_coincidem_com_o_grupo():
    """docs/case.md §2.9 afirma nomes fictícios; três coincidem com
    integrantes do grupo."""
    import dados
    nomes = {nome for _, nome, _, _ in dados.ALUNOS}
    assert {"Weslley Sousa", "Pedro Akira", "Henrique Matos"} <= nomes


def test_L10_protocolo_do_langgraph_depende_do_hash_do_processo():
    """O agente LangGraph gera o protocolo com hash() do Python, que muda a
    cada processo (PYTHONHASHSEED): o mesmo pedido recebe protocolos
    diferentes em execuções diferentes, e a idempotência quebra."""
    fonte = (RAIZ / "exercicios" / "aula09-langgraph" / "agente_langgraph.py").read_text(
        encoding="utf-8")
    assert 'f"DOC-{hash((ra, tipo_documento))' in fonte
    assert "INSERT OR IGNORE INTO documentos_emitidos" in fonte
