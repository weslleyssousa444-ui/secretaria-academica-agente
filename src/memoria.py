# Orquestração da memória do agente de triagem — Exercício 8.
#
# Orçamento de janela (nota 03 §4) e remoção sob solicitação com
# VERIFICAÇÃO — não afirmação — de cobertura (nota 04 §3).

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from memoria_episodica import MemoriaEpisodica
from memoria_procedural import MemoriaProcedural
from memoria_semantica import MemoriaSemantica

PASTA_CHECKPOINTS = Path(__file__).parent.parent / "checkpoints"
PASTA_LOGS = Path(__file__).parent.parent / "logs"


def estimar_tokens(texto: str) -> int:
    """Aproximação grosseira (~4 caracteres/token), suficiente para o
    orçamento — não para faturamento (Aula 05, nota 02 §1)."""
    return len(texto) // 4


@dataclass
class OrcamentoDeMemoria:
    """O teto é parâmetro, não constante (Aula 05, nota 02 §1) — memória é
    a QUINTA fonte competindo pela janela do agente de triagem, ao lado do
    system prompt, do objetivo, da trajetória e das declarações de
    ferramenta (nota 03 §4)."""
    max_tokens_memoria: int = 400
    max_episodios: int = 3


def montar_bloco_memoria(episodica: MemoriaEpisodica, semantica: MemoriaSemantica,
                          procedural: MemoriaProcedural, consulta: str, ra: str,
                          orcamento: OrcamentoDeMemoria) -> dict:
    """Ordem de montagem NÃO é arbitrária (nota 03 §4): procedural,
    semântica, episódica — a mais volumosa e menos confiável (episódica)
    fica adjacente à trajetória corrente, e o mais estável (procedural)
    ocupa a extremidade oposta. Viés de posição, Aula 02."""
    texto_proc = procedural.como_system_prompt()

    fato_financeiro = semantica.ler(ra, "situacao_financeira")
    texto_sem = (f"Fato conhecido sobre o RA {ra}: situação financeira "
                 f"= {fato_financeiro['valor']} (registrado em {fato_financeiro['data']})."
                 if fato_financeiro else "")

    episodios = episodica.recuperar(consulta, k=orcamento.max_episodios, ra=ra)
    texto_epi = ("Episódios anteriores deste aluno:\n" +
                 "\n".join(f"- [{e['data']}] {e['resumo']}" for e in episodios)
                 if episodios else "")

    partes = [p for p in (texto_proc, texto_sem, texto_epi) if p]
    texto = "\n\n".join(partes)
    tokens = estimar_tokens(texto)

    if tokens > orcamento.max_tokens_memoria:
        # descarta episódico primeiro — é o mais volumoso e o mais fácil
        # de reconstruir na próxima consulta (nota 03 §4).
        partes = [p for p in (texto_proc, texto_sem) if p]
        texto = "\n\n".join(partes)
        tokens = estimar_tokens(texto)

    return {"texto": texto, "tokens": tokens, "episodios_usados": len(episodios)}


def _varrer_pasta(pasta: Path, ra: str) -> list[str]:
    if not pasta.exists():
        return []
    return [str(a.relative_to(pasta.parent)) for a in pasta.glob("*.json")
            if ra in a.read_text(encoding="utf-8")]


def verificar_remocao(ra: str, episodica: MemoriaEpisodica, semantica: MemoriaSemantica,
                        procedural: MemoriaProcedural) -> list[tuple[str, str]]:
    """A ENTREGA é a busca posterior que não encontra nada, não a chamada
    de exclusão (nota 04 §3.2). Varredura de checkpoint/log é SOMENTE
    LEITURA — inclui logs/ (entregas já commitadas de exercícios
    anteriores) só para efeito de RELATÓRIO de vestígio, nunca de remoção
    (ver `remover_titular`, que nunca toca logs/)."""
    vestigios = []
    vestigios += [("episodica", i) for i in episodica.contem_ra(ra)]
    vestigios += [("semantica", k) for k in semantica.contem_entidade(ra)]
    vestigios += [("procedural", r) for r in procedural.contem_texto(ra)]
    vestigios += [("checkpoint", a) for a in _varrer_pasta(PASTA_CHECKPOINTS, ra)]
    vestigios += [("log_de_exercicio_anterior", a) for a in _varrer_pasta(PASTA_LOGS, ra)]
    return vestigios


def remover_titular(ra: str, episodica: MemoriaEpisodica, semantica: MemoriaSemantica,
                      procedural: MemoriaProcedural, remover_checkpoints: bool = False) -> dict:
    """`remover_checkpoints` afeta SOMENTE `checkpoints/` — nunca `logs/`.
    Um checkpoint é efêmero por natureza (nota 01 §8; `checkpoints/` está
    no `.gitignore` do projeto); um log de exercício anterior é uma entrega
    já registrada e não é apagado por este demo — na vida real, seria
    tratado por uma rotina de expurgo própria, fora do escopo aqui."""
    n_ep = episodica.remover(ra)
    n_sem = semantica.remover(ra)
    regras_suspeitas = procedural.contem_texto(ra)

    n_checkpoints = 0
    if remover_checkpoints and PASTA_CHECKPOINTS.exists():
        for arquivo in PASTA_CHECKPOINTS.glob("*.json"):
            if ra in arquivo.read_text(encoding="utf-8"):
                arquivo.unlink()
                n_checkpoints += 1

    return {"episodios_removidos": n_ep, "fatos_removidos": n_sem,
            "regras_suspeitas": regras_suspeitas, "checkpoints_removidos": n_checkpoints}
