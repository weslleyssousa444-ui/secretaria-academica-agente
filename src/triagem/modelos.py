# ASI10 (agentes desgovernados): a lista de modelos APROVADOS, em código.
#
# O risco (docs/seguranca.md): `LLM_MODELO` é uma variável de ambiente livre, e
# trocar o modelo muda o comportamento do sistema inteiro, sem nenhum commit e
# sem nenhum eval. O `qwen/qwen3.8-27b` foi escolhido por evidência (0 falso
# negativo em trancamento); o `openai/gpt-oss-20b` foi AVALIADO E NÃO PROMOVIDO
# (exercicios/aula-11-suite-do-case.md: pendência 50%).
#
# O controle: o Sistema se RECUSA a subir com um modelo que não está aqui
# (fail-closed). Aprovar um modelo novo é uma mudança de código, que carrega a
# referência do eval que o aprovou: o próprio commit é o registro da decisão.
#
# O que o controle custou: não dá mais para "trocar LLM_MODELO no .env" quando a
# cota gratuita do dia acaba. Sem um segundo modelo aprovado, o sistema para, em
# vez de seguir com um modelo que ninguém mediu.

from __future__ import annotations

MODELOS_APROVADOS: dict[str, str] = {
    "qwen/qwen3.8-27b": (
        "docs/modelos.md §3.5 (35/40 em 22-23/09/2026); verificador 39/40 com 0 falso "
        "negativo em trancamento em 18-20/10/2026 (docs/model-card.md, L02); "
        "suíte do Exercício 11 (aprovação 100% nas 2 repetições)"),
}


class ModeloNaoAprovado(Exception):
    """O modelo configurado não passou pelo eval que a lista exige."""


def verificar_modelo(modelo: str, permitir_nao_aprovado: bool = False) -> bool:
    """True se o modelo está aprovado. Se não está, levanta ModeloNaoAprovado,
    a menos que `permitir_nao_aprovado` seja True. Só o runner do eval usa essa
    permissão: avaliar um candidato é como ele ENTRA na lista, e o trace marca
    a execução como `agente.modelo_aprovado = false`."""
    if modelo in MODELOS_APROVADOS:
        return True
    if permitir_nao_aprovado:
        return False
    raise ModeloNaoAprovado(
        f"o modelo {modelo!r} não está em MODELOS_APROVADOS (src/triagem/modelos.py). "
        "Rode a suíte de avaliação sobre ele (python -m evals.rodar) e, se aprovado, "
        "acrescente-o à lista com a referência do resultado.")
