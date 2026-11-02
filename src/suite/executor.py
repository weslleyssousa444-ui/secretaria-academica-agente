# Executor da suíte do case (Exercício 11): roda o golden dataset contra uma
# versão do sistema e grava o que aconteceu — SEM avaliar. Avaliar é outro
# passo (avaliadores.py) justamente para que um avaliador corrigido possa ser
# reaplicado sobre execuções antigas sem gastar tokens de novo.
#
# Uso (a partir da raiz do repositório):
#   python src/suite/executor.py --versao A --run 1
#   python src/suite/executor.py --versao B --run 2 --casos em01,tr01
#
# Retomável: lê o .jsonl da (versão, run) e pula o que já foi executado, de
# modo que uma cota diária esgotada interrompe a rodada em vez de perdê-la.
#
# Parâmetros e justificativas:
#   VERSOES        A = sistema como está em master (qwen/qwen3.8-27b); B = a
#                  mudança que o grupo pretende fazer, condicionada em
#                  docs/modelos.md §3.5 a este teste (openai/gpt-oss-20b).
#                  Tudo o mais — prompt, ferramentas, orçamento, pós-condição
#                  L02, temperatura 0 — é idêntico nas duas versões.
#   banco novo     cada caso roda num SQLite novo semeado por dados.py: o
#                  estado do mundo é controlado, não medido (nota 01 §3).
#   TPM_ALVO       6000 tokens/min, abaixo do teto de 8000 do free tier
#                  (docs/modelos.md §3.5): pausa preventiva em vez de depender
#                  de 429 + retry, que desperdiça tentativas.
#   TIMEOUT        90 s por chamada: uma chamada pendurada travou rodadas
#                  inteiras em execuções anteriores.
#   cota diária    "tokens per day" NÃO é retentado: interrompe e deixa a
#                  rodada retomável (esperar 24 h não cabe no laço de retry).

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))

from openai import APIConnectionError, APIStatusError, APITimeoutError, RateLimitError  # noqa: E402

import agente  # noqa: E402
import dados  # noqa: E402
from agente import ErroFatal, Estado, Orcamento, conversar  # noqa: E402

GOLDEN = RAIZ / "dados" / "golden_v1.json"
REGRA = RAIZ / "dados" / "regra_de_promocao.json"
PASTA = RAIZ / "logs" / "suite"

VERSOES = {
    "A": {"modelo": "qwen/qwen3.8-27b", "descricao": "sistema atual de master"},
    "B": {"modelo": "openai/gpt-oss-20b", "descricao": "troca de modelo (docs/modelos.md §3.5)"},
}
TPM_ALVO = 6000
TIMEOUT = 90


class CotaDiaria(Exception):
    """A Groq recusou por tokens por dia: nenhuma espera curta resolve."""


def sha(caminho: Path) -> str:
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


def chamar_com_retry_da_suite(**kwargs):
    """Mesmo contrato de agente.chamar_com_retry (retry só de transporte), com
    uma diferença de infraestrutura: cota DIÁRIA levanta CotaDiaria em vez de
    gastar 8 tentativas de até 90 s esperando um reset que não vem."""
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
                raise ErroFatal(f"erro {e.status_code} da API: {e}") from e
    raise ErroFatal("API indisponível após 8 tentativas")


def foto_do_banco() -> dict:
    conexao = dados.conectar()
    foto = {t: [dict(l) for l in conexao.execute(f"SELECT * FROM {t} ORDER BY protocolo")]
            for t in ("documentos_emitidos", "casos_pendentes")}
    conexao.close()
    return foto


def executar_caso(caso: dict, versao: str, run: int) -> dict:
    with tempfile.TemporaryDirectory() as pasta:
        dados.CAMINHO_DB = Path(pasta) / "academico.db"
        dados.inicializar(forcar=True)
        antes = foto_do_banco()
        estado, orcamento = Estado(caso=caso["id"]), Orcamento()
        inicio = time.monotonic()
        for mensagem in caso["mensagens"]:
            estado = conversar(estado, mensagem, orcamento, verboso=False)
            if estado.termino is not None and estado.termino.value != "respondeu":
                break
        depois = foto_do_banco()
    return {
        "versao": versao, "run": run, "caso": caso["id"], "modelo": agente.MODELO,
        "momento": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "duracao_s": round(time.monotonic() - inicio, 1),
        "termino": estado.termino.value if estado.termino else None, "motivo": estado.motivo,
        "tokens": estado.tokens_gastos, "n_passos": estado.n_passos,
        "passos": [{"ferramenta": p.ferramenta, "argumentos": p.argumentos,
                    "resultado": p.resultado, "erro": p.erro} for p in estado.passos],
        "respostas": [m["content"] for m in estado.historico
                      if isinstance(m, dict) and m.get("role") == "assistant" and m.get("content")],
        "antes": antes, "depois": depois,
        "dataset_sha": sha(GOLDEN), "regra_sha": sha(REGRA),
    }


def feitos(arquivo: Path) -> set[str]:
    if not arquivo.exists():
        return set()
    registros = [json.loads(l) for l in arquivo.read_text(encoding="utf-8").splitlines() if l.strip()]
    # erro_fatal é falha de infraestrutura (provedor), não resultado: refaz.
    return {r["caso"] for r in registros if r["termino"] != "erro_fatal"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--versao", required=True, choices=sorted(VERSOES))
    ap.add_argument("--run", type=int, required=True)
    ap.add_argument("--casos", help="ids separados por vírgula (padrão: todos)")
    args = ap.parse_args()

    agente.MODELO = VERSOES[args.versao]["modelo"]
    agente.client = agente.client.with_options(timeout=TIMEOUT, max_retries=0)
    agente.chamar_com_retry = chamar_com_retry_da_suite

    casos = json.loads(GOLDEN.read_text(encoding="utf-8"))["casos"]
    if args.casos:
        pedidos = set(args.casos.split(","))
        casos = [c for c in casos if c["id"] in pedidos]
    PASTA.mkdir(parents=True, exist_ok=True)
    arquivo = PASTA / f"exec-{args.versao}-r{args.run}.jsonl"
    prontos = feitos(arquivo)

    for caso in casos:
        if caso["id"] in prontos:
            continue
        try:
            registro = executar_caso(caso, args.versao, args.run)
        except CotaDiaria as e:
            print(f"PARADO em {caso['id']}: cota diária esgotada ({str(e)[:160]})")
            return 3
        with arquivo.open("a", encoding="utf-8") as f:
            f.write(json.dumps(registro, ensure_ascii=False) + "\n")
        print(f"{caso['id']:<5} {registro['termino']:<20} {registro['tokens']:>6} tokens "
              f"{registro['duracao_s']:>6}s", flush=True)
        # pausa para ficar sob TPM_ALVO em média
        pausa = registro["tokens"] / TPM_ALVO * 60 - registro["duracao_s"]
        if pausa > 0:
            time.sleep(pausa)
    print(f"rodada {args.versao}{args.run} completa: {len(feitos(arquivo))}/{len(casos)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
