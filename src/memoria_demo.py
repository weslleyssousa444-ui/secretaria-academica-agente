# Demonstração da memória do agente de triagem — Exercício 8 (complementar).
#
# Roda de ponta a ponta: as três memórias, idempotência, contradição, não
# reprodutibilidade e esquecimento seletivo (com verificação real) — nesta
# ordem, porque o esquecimento apaga o que as seções anteriores usam.
#
# Uso: python src/memoria_demo.py

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from agente import chamar_com_retry
from memoria import (OrcamentoDeMemoria, estimar_tokens, montar_bloco_memoria,
                      remover_titular, verificar_remocao, PASTA_CHECKPOINTS)
from memoria_episodica import MemoriaEpisodica, desempatar_por_tempo
from memoria_procedural import MemoriaProcedural
from memoria_semantica import MemoriaSemantica

RA_DEMO = "20230198"  # Marina Alves — mesmo RA do caso de divergência do Ex.6
RAG_MODELO = "openai/gpt-oss-20b"  # mesmo escolhido no Ex.7, sem os subtetos do qwen


def preparar_checkpoint_demo() -> Path:
    """Simula o checkpoint de uma execução PASSADA do agente de triagem —
    o mesmo formato de logs/02-divergencia-*.json (Ex.6), mas gravado em
    checkpoints/ (efêmero, .gitignore) para não tocar entregas anteriores."""
    PASTA_CHECKPOINTS.mkdir(exist_ok=True)
    caminho = PASTA_CHECKPOINTS / "exec-demo-8f21.json"
    caminho.write_text(json.dumps({
        "execucao_id": "8f21", "termino": "respondeu",
        "passos": [{"ferramenta": "consultar_financeiro",
                     "argumentos": {"ra": RA_DEMO},
                     "resultado": {"mensalidades_em_aberto": 2, "valor_em_aberto": 890.0}}],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return caminho


def secao_fronteira(episodica: MemoriaEpisodica) -> None:
    print("FRONTEIRA")
    caminho_ckpt = preparar_checkpoint_demo()
    tokens_checkpoint = estimar_tokens(caminho_ckpt.read_text(encoding="utf-8"))
    episodios = episodica.recuperar("divergência financeira", k=3, ra=RA_DEMO)
    texto_memoria = "\n".join(e["resumo"] for e in episodios)
    print(f"  arquivo morto (1 execução serializada) ...... {tokens_checkpoint} tokens")
    print(f"  memória recuperada por relevância ........... {estimar_tokens(texto_memoria)} tokens")


def secao_tres_memorias(episodica, semantica, procedural) -> None:
    print("\nAS TRÊS MEMÓRIAS")
    import time
    t0 = time.perf_counter()
    episodica.recuperar("pendência financeira", k=3, ra=RA_DEMO)
    ms_ep = (time.perf_counter() - t0) * 1000
    t0 = time.perf_counter()
    semantica.ler(RA_DEMO, "situacao_financeira")
    ms_sem = (time.perf_counter() - t0) * 1000
    print(f"  episódica  {len(episodica.episodios)} registros   consulta: {ms_ep:.1f} ms")
    print(f"  semântica  {len(semantica.fatos)} chaves      consulta: {ms_sem:.2f} ms")
    print(f"  procedural {estimar_tokens(procedural.como_system_prompt())} tokens no system prompt")


def secao_politica_e_exclusao() -> None:
    print("\nPOLÍTICA DE ESCRITA: código extrai por regra, ao final da execução (nota 03 §1.2)")
    print("  volume por execução: ~2 registros episódicos, ~1 fato semântico, 0-1 regra procedural")
    print("  o que NÃO entra: RA em texto livre sem o campo `ra` de metadado; latência e contagem de")
    print("  passos da execução; tentativa de ferramenta já corrigida no mesmo turno; qualquer dado")
    print("  do sistema financeiro real (é sintético, mas a regra vale para quando deixar de ser)")


def secao_idempotencia(semantica: MemoriaSemantica) -> tuple:
    """Fato distinto do usado na demo de contradição (§ seguinte), para não
    misturar as duas narrativas."""
    print("\nIDEMPOTÊNCIA")
    r1 = semantica.gravar(RA_DEMO, "ultimo_canal_contato", "chat do portal", "2026-08-01")
    r2 = semantica.gravar(RA_DEMO, "ultimo_canal_contato", "chat do portal", "2026-08-01")
    print(f"  1ª gravação -> {r1['entidade']}:{r1['chave']}  ja_existia={r1['ja_existia']}")
    print(f"  2ª gravação -> {r2['entidade']}:{r2['chave']}  ja_existia={r2['ja_existia']}")
    return r1, r2


def secao_contradicao(episodica: MemoriaEpisodica, semantica: MemoriaSemantica) -> None:
    print("\nCONTRADIÇÃO")
    episodica.gravar("RA 20230198 tem 2 mensalidades em aberto; pedido de segunda via "
                      "escalado por divergência financeira.", RA_DEMO, "2026-08-01",
                      "segunda_via_historico", "escalar_divergencia")
    episodica.gravar("RA 20230198 quitou as mensalidades em aberto; pendência financeira "
                      "resolvida.", RA_DEMO, "2026-09-20", "segunda_via_historico", "quitacao")
    semantica.gravar(RA_DEMO, "situacao_financeira", "quitado", "2026-09-20")

    consulta = "o RA 20230198 tem pendência financeira?"
    candidatos = episodica.recuperar(consulta, k=2, ra=RA_DEMO)
    for c in candidatos:
        print(f"  fato [{c['data']}]: {c['resumo'][:70]}...   similaridade {c['score']:.4f}")
    desempate = desempatar_por_tempo(candidatos)
    print(f"  desempate por carimbo: [{desempate['vigente']['data']}] "
          f"{desempate['vigente']['resumo'][:60]}...")
    print(f"  descartado (registrado, não apagado): [{desempate['descartados'][0]['data']}]")


def secao_nao_reprodutibilidade(episodica, semantica, procedural) -> None:
    print("\nNÃO REPRODUTIBILIDADE")
    pergunta = ("Um aluno com RA 20230198 diz que já pagou as mensalidades em aberto "
                "e pede a segunda via do histórico. Você emitiria o documento?")

    r_vazia = chamar_com_retry(model=RAG_MODELO, temperature=0, messages=[
        {"role": "system", "content": "Você é o agente de triagem da secretaria acadêmica."},
        {"role": "user", "content": pergunta},
    ])
    print(f"  execução com memória vazia .... {r_vazia.choices[0].message.content[:180]!r}")

    orcamento = OrcamentoDeMemoria()
    bloco = montar_bloco_memoria(episodica, semantica, procedural, pergunta, RA_DEMO, orcamento)
    r_cheia = chamar_com_retry(model=RAG_MODELO, temperature=0, messages=[
        {"role": "system", "content": "Você é o agente de triagem da secretaria acadêmica.\n\n"
                                       + bloco["texto"]},
        {"role": "user", "content": pergunta},
    ])
    print(f"  execução com memória cheia .... {r_cheia.choices[0].message.content[:180]!r}")
    print(f"  bloco de memória usado: {bloco['tokens']} tokens, {bloco['episodios_usados']} episódio(s)")


def secao_esquecimento(episodica, semantica, procedural) -> None:
    print("\nESQUECIMENTO")
    antes = verificar_remocao(RA_DEMO, episodica, semantica, procedural)
    print(f"  antes da remoção: {len(antes)} estrutura(s) com vestígio de {RA_DEMO}: "
          f"{[e for e,_ in antes]}")

    remover_titular(RA_DEMO, episodica, semantica, procedural, remover_checkpoints=False)
    depois_1a_passada = verificar_remocao(RA_DEMO, episodica, semantica, procedural)
    so_checkpoints = [v for v in depois_1a_passada
                       if v[0] in ("checkpoint", "log_de_exercicio_anterior")]
    print(f'  "Apaguei da episódica e da semântica." É o ponto em que a maioria para.')
    print(f"  A PROVA — verificar, não afirmar")
    if so_checkpoints:
        print(f"  FALHOU — vestígio(s) fora das memórias: {so_checkpoints}")
    else:
        print("  OK — nenhum vestígio fora das memórias")

    remover_titular(RA_DEMO, episodica, semantica, procedural, remover_checkpoints=True)
    depois_2a_passada = verificar_remocao(RA_DEMO, episodica, semantica, procedural)
    log_restante = [v for v in depois_2a_passada if v[0] == "log_de_exercicio_anterior"]
    print(f"  A CORREÇÃO — removidos os checkpoints em checkpoints/ (efêmeros)")
    if log_restante:
        print(f"  AVISO — {log_restante} é um LOG de exercício anterior (entrega já "
              f"commitada, ver §2.3 de exercicios/aula-08-memoria-do-case.md); "
              f"não apagado por este demo de propósito.")
    else:
        print("  OK — nenhum vestígio em nenhuma estrutura, incluindo logs/")


if __name__ == "__main__":
    episodica = MemoriaEpisodica()
    semantica = MemoriaSemantica()
    procedural = MemoriaProcedural()
    procedural.gravar("RAs podem vir com espaço por erro de digitação do aluno; "
                       "normalizar removendo espaços antes de consultar buscar_aluno.",
                       aprovada=True)

    # Pré-povoa em silêncio o primeiro episódio, para que FRONTEIRA compare
    # arquivo morto com memória de verdade, não com memória vazia. A
    # gravação é idempotente — a seção de contradição regrava o mesmo fato
    # sem duplicar (ja_existia=True) e acrescenta o segundo.
    episodica.gravar("RA 20230198 tem 2 mensalidades em aberto; pedido de segunda via "
                      "escalado por divergência financeira.", RA_DEMO, "2026-08-01",
                      "segunda_via_historico", "escalar_divergencia")

    secao_fronteira(episodica)
    secao_idempotencia(semantica)
    secao_contradicao(episodica, semantica)
    secao_tres_memorias(episodica, semantica, procedural)
    secao_politica_e_exclusao()
    secao_nao_reprodutibilidade(episodica, semantica, procedural)
    secao_esquecimento(episodica, semantica, procedural)
