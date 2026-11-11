# Roda o dataset sobre o SISTEMA ENTREGUE (src/triagem/sistema.py) e grava o que
# aconteceu, SEM avaliar: avaliar é outro passo (comparar.py), para que um
# avaliador corrigido se reaplique a execuções antigas sem gastar token.
#
#   python -m evals.rodar --rotulo B --run 1
#   python -m evals.rodar --rotulo A --run 1 --ref parte-2     # código da versão anterior
#   python -m evals.rodar --rotulo B --run 1 --casos id01,rg01 # só alguns casos
#
# Cada rodada é UMA PASTA em evals/resultados/ e é commitada: ela é a evidência
# dos números de docs/evals.md.
#
# Retomável: pula os casos já gravados (menos os `erro_fatal`, que são falha do
# provedor, e não resultado), de modo que a cota diária esgotada INTERROMPE a
# rodada em vez de perdê-la (exit 3).
#
# Cada caso roda num SQLite novo, num checkpoint novo e numa memória VAZIA: o
# estado do mundo é controlado, e a memória muda a resposta (docs/memoria.md §6).
#
# `--ref` executa o código de um commit ou tag num `git worktree` temporário. É
# como se compara "a versão anterior" com a atual sem reescrever a anterior.

from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import subprocess
import sys
import tempfile
import time
from datetime import date, datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
DATASET_PADRAO = RAIZ / "evals" / "dataset" / "golden_v1.1.0.json"
TPM_ALVO = 6000   # tokens/min: abaixo do teto de 8.000 do free tier (docs/modelos.md §3.5)
TIMEOUT = 90      # s por chamada: uma chamada pendurada já travou rodadas inteiras


class CotaDiaria(Exception):
    """A Groq recusou por tokens por dia: nenhuma espera curta resolve."""


def git(*args, cwd=RAIZ) -> str:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()


def preparar_codigo(ref: str | None) -> tuple[Path, callable]:
    """Devolve (raiz do código, limpeza). Sem `ref`, é o próprio repositório."""
    if not ref:
        return RAIZ, lambda: None
    pasta = Path(tempfile.mkdtemp(prefix="codigo-")) / "repo"
    git("worktree", "add", "--detach", str(pasta), ref)
    return pasta, lambda: git("worktree", "remove", "--force", str(pasta))


def foto_do_banco(dados) -> dict:
    con = dados.conectar()
    foto = {t: [dict(l) for l in con.execute(f"SELECT * FROM {t} ORDER BY protocolo")]
            for t in ("documentos_emitidos", "casos_pendentes")}
    con.close()
    return foto


def executar_caso(caso: dict, rotulo: str, run: int, usar_sessao: bool, modulos: dict) -> dict:
    dados, agente, Sistema = modulos["dados"], modulos["agente"], modulos["Sistema"]
    with tempfile.TemporaryDirectory() as pasta:
        pasta = Path(pasta)
        dados.CAMINHO_DB = pasta / "academico.db"
        dados.inicializar(forcar=True)
        antes = foto_do_banco(dados)
        extras = {"permitir_modelo_nao_aprovado": True} \
            if "permitir_modelo_nao_aprovado" in inspect.signature(Sistema.__init__).parameters else {}
        sistema = Sistema(checkpoint=pasta / "cp.sqlite", memoria_dir=pasta / "mem", **extras)
        thread, saidas, termino, motivo = f"eval-{rotulo}-r{run}-{caso['id']}", [], "respondeu", None
        inicio = time.monotonic()
        try:
            for mensagem in caso["mensagens"]:
                r = sistema.conversar(thread, mensagem, caso.get("sessao_ra") if usar_sessao else None)
                saidas.append(r["saida"])
                if r["termino"] != "respondeu":
                    termino, motivo = r["termino"], r.get("motivo")
                    break
                if r["aguardando_humano"]:
                    break
            estado = sistema.estado(thread)
        finally:
            sistema.fechar()
        depois = foto_do_banco(dados)
    return {
        "versao": rotulo, "run": run, "caso": caso["id"], "modelo": agente.MODELO,
        "momento": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "duracao_s": round(time.monotonic() - inicio, 1),
        "termino": termino, "motivo": motivo,
        "tokens": estado.get("tokens_gastos", 0), "n_passos": len(estado.get("passos", [])),
        "chamadas_ao_modelo": estado.get("n_chamadas_modelo", 0),
        "passos": [{k: p.get(k) for k in ("ferramenta", "argumentos", "resultado", "erro", "recusado")}
                   for p in estado.get("passos", [])],
        "respostas": [s["resultado"] for s in saidas], "saidas": saidas,
        "trilha_de_nos": estado.get("eventos", []), "antes": antes, "depois": depois,
    }


def preparar_provedor(agente) -> None:
    """Retry de transporte da suíte: cota DIÁRIA levanta CotaDiaria em vez de gastar
    8 tentativas de até 90 s esperando um reset que não vem."""
    from openai import APIConnectionError, APIStatusError, APITimeoutError, RateLimitError
    agente.client = agente.client.with_options(timeout=TIMEOUT, max_retries=0)

    def chamar(**kwargs):
        for tentativa in range(8):
            try:
                return agente.client.chat.completions.create(**kwargs)
            except RateLimitError as e:
                if "per day" in str(e).lower() or "tpd" in str(e).lower():
                    raise CotaDiaria(str(e)) from e
                time.sleep(agente._espera_sugerida(e, tentativa))
            except (APIConnectionError, APITimeoutError):
                time.sleep(min(2 ** tentativa, 30))
            except APIStatusError as e:
                if e.status_code >= 500:
                    time.sleep(agente._espera_sugerida(e, tentativa))
                else:
                    raise agente.ErroFatal(f"erro {e.status_code} da API: {e}") from e
        raise agente.ErroFatal("API indisponível após 8 tentativas")

    agente.chamar_com_retry = chamar


def feitos(arquivo: Path) -> set[str]:
    if not arquivo.exists():
        return set()
    return {r["caso"] for r in (json.loads(l) for l in arquivo.read_text(encoding="utf-8").splitlines() if l.strip())
            if r["termino"] != "erro_fatal"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0] if __doc__ else "")
    ap.add_argument("--rotulo", required=True, help="nome da versão na comparação (A, B, ...)")
    ap.add_argument("--run", type=int, default=1)
    ap.add_argument("--ref", help="commit ou tag do código a executar (padrão: o repositório atual)")
    ap.add_argument("--dataset", type=Path, default=DATASET_PADRAO)
    ap.add_argument("--casos", help="ids separados por vírgula (padrão: todos)")
    ap.add_argument("--modelo", help="substitui LLM_MODELO (candidato: o runner pode avaliá-lo sem estar aprovado)")
    ap.add_argument("--sem-sessao", action="store_true", help="não passa o RA autenticado (portal ausente)")
    ap.add_argument("--pasta", type=Path, help="pasta da rodada (padrão: evals/resultados/<data>-<rotulo>-r<run>)")
    args = ap.parse_args(argv)

    raiz_codigo, limpar = preparar_codigo(args.ref)
    try:
        sys.path.insert(0, str(raiz_codigo / "src"))
        import os
        if not os.environ.get("OPENAI_API_KEY"):
            from dotenv import load_dotenv
            load_dotenv(RAIZ / ".env")
        import agente
        import dados
        from triagem import nos
        from triagem.sistema import Sistema
        if args.modelo:
            agente.MODELO = args.modelo
        preparar_provedor(agente)
        telemetria = None  # a versão anterior pode não ter trace
        if (raiz_codigo / "src" / "triagem" / "telemetria.py").exists():
            from triagem import telemetria

        dataset = json.loads(args.dataset.read_text(encoding="utf-8"))
        casos = dataset["casos"]
        if args.casos:
            pedidos = set(args.casos.split(","))
            casos = [c for c in casos if c["id"] in pedidos]
        pasta = args.pasta or RAIZ / "evals" / "resultados" / f"{date.today().isoformat()}-{args.rotulo}-r{args.run}"
        pasta.mkdir(parents=True, exist_ok=True)
        arquivo = pasta / "execucoes.jsonl"
        if telemetria is not None:
            telemetria.configurar(destino=pasta / "traces.jsonl")

        commit = git("rev-parse", "--short", args.ref or "HEAD")
        sujo = bool(not args.ref and git("status", "--porcelain", "--", "src", "evals/dataset"))
        (pasta / "metadados.json").write_text(json.dumps({
            "rotulo": args.rotulo, "run": args.run, "modelo": agente.MODELO,
            "codigo": {"ref": args.ref or "HEAD", "commit": commit, "alteracoes_nao_commitadas": sujo},
            "dataset": {"arquivo": str(args.dataset.relative_to(RAIZ)) if args.dataset.is_relative_to(RAIZ) else str(args.dataset),
                        "versao": dataset["versao"], "sha256": hashlib.sha256(args.dataset.read_bytes()).hexdigest()},
            "prompt_sha256": hashlib.sha256(nos.SYSTEM.encode()).hexdigest()[:16],
            "sessao_autenticada": not args.sem_sessao, "parametros": {"temperature": 0},
            "versao_do_sistema": (telemetria.versao_do_sistema(agente.MODELO, nos.SYSTEM) if telemetria else None),
            "iniciado_em": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }, ensure_ascii=False, indent=2), encoding="utf-8")

        modulos = {"dados": dados, "agente": agente, "Sistema": Sistema}
        prontos = feitos(arquivo)
        for caso in casos:
            if caso["id"] in prontos:
                continue
            try:
                registro = executar_caso(caso, args.rotulo, args.run, not args.sem_sessao, modulos)
            except CotaDiaria as e:
                print(f"PARADO em {caso['id']}: cota diária esgotada ({str(e)[:140]})")
                return 3
            with arquivo.open("a", encoding="utf-8") as f:
                f.write(json.dumps(registro, ensure_ascii=False, default=str) + "\n")
            print(f"{caso['id']:<6} {registro['termino']:<20} {registro['tokens']:>6} tokens {registro['duracao_s']:>6}s", flush=True)
            pausa = registro["tokens"] / TPM_ALVO * 60 - registro["duracao_s"]
            if pausa > 0:
                time.sleep(pausa)
        print(f"rodada {args.rotulo}{args.run} completa: {len(feitos(arquivo))}/{len(casos)} em {pasta}")
        return 0
    finally:
        limpar()


if __name__ == "__main__":
    sys.exit(main())
