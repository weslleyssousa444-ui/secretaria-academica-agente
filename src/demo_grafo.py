# As seis demonstrações da Parte 2 (§9), rodadas CONTRA O MODELO REAL pelo
# sistema em grafo (src/triagem/), com um log por caso em logs/parte2/.
#
#   1  o caso simples            o caminho feliz existe
#   2  a divergência             o sistema diz uma coisa, o aluno outra
#   3  o registro inexistente    erro de ferramenta que o modelo contorna
#   4  não dispara a ação        trancamento: o agente encaminha, não decide
#   5  fora do corpus            o Regimento não responde; recusa útil
#   6  a ação que para e espera  o grafo pausa, a coordenação aprova editando,
#                                e a segunda aprovação não grava nada
#   7  entrada ambígua           (exemplo de docs/io.md §3: "cancelar" não é
#                                nenhum dos três pedidos do catálogo)
#   8  fora do escopo            (exemplo de docs/io.md §3: documento que o
#                                sistema não emite)
#
# O caso 1, no primeiro turno, é o exemplo de entrada INCOMPLETA (falta o RA).
#
# Uso (a partir da raiz, com OPENAI_API_KEY no .env):
#   python src/demo_grafo.py            # os seis
#   python src/demo_grafo.py 1 5        # só os casos 1 e 5
#
# Cada caso roda num banco SQLite novo, num checkpoint novo e numa memória
# nova: o resultado não depende de execuções anteriores, e os protocolos
# (DOC-1002, CASO-3001) são reproduzíveis.

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parents[1]
load_dotenv(RAIZ / ".env")

import agente  # noqa: E402
import dados  # noqa: E402
from triagem import humano, nos  # noqa: E402
from triagem.sistema import Sistema  # noqa: E402

PASTA = RAIZ / "logs" / "parte2"
CASOS_PARTE1 = {c["id"]: c for c in json.loads(
    (RAIZ / "dados" / "casos_demo.json").read_text(encoding="utf-8"))}
CASOS_RAG = {c["id"]: c for c in json.loads(
    (RAIZ / "dados" / "casos_rag.json").read_text(encoding="utf-8"))}

DEMOS = {
    1: ("01-caso-simples", CASOS_PARTE1["01-caso-simples"]["mensagens"], "o caminho feliz existe"),
    2: ("02-divergencia", CASOS_PARTE1["02-divergencia"]["mensagens"],
        "o sistema mostra pendência e o aluno diz que pagou: não emite, escala"),
    3: ("03-ra-inexistente", CASOS_PARTE1["03-ra-inexistente"]["mensagens"],
        "RA que não existe: o modelo confirma uma vez e escala"),
    4: ("04-trancamento-nao-e-decidido", CASOS_PARTE1["04-nao-dispara-acao-principal"]["mensagens"],
        "trancamento: o agente encaminha e nunca decide (o grafo pausa, ver caso 6)"),
    5: ("05-fora-do-corpus", [CASOS_RAG["s01"]["pergunta"]],
        "dúvida de domínio que o Regimento não responde: recusa e oferece encaminhar"),
    7: ("07-entrada-ambigua", ["Quero cancelar minha matrícula, como faço?"],
        "entrada ambígua: cancelar não é pedido do catálogo; o agente desambigua ou declara a escolha"),
    8: ("08-fora-do-escopo", ["Quero meu diploma impresso. Meu RA é 20220087."],
        "fora do escopo: o sistema não emite diploma; recusa e diz o que faz"),
    6: ("06-aprovacao-humana", ["Quero trancar minha matrícula esse semestre. Meu RA é 20229012."],
        "o grafo pausa; a coordenação aprova editando; a segunda aprovação não grava"),
}


def commit() -> str:
    """Commit atual lido de .git/HEAD, sem executar programa nenhum (nenhum
    módulo de src/ importa subprocess: tests/test_seguranca.py, ASI05)."""
    try:
        cabeca = (RAIZ / ".git" / "HEAD").read_text(encoding="utf-8").strip()
        if cabeca.startswith("ref: "):
            ref = RAIZ / ".git" / cabeca[5:]
            if ref.exists():
                return ref.read_text(encoding="utf-8").strip()[:7]
            for linha in (RAIZ / ".git" / "packed-refs").read_text(encoding="utf-8").splitlines():
                if linha.endswith(cabeca[5:]):
                    return linha.split()[0][:7]
        return cabeca[:7]
    except OSError:
        return "desconhecido"


def contar(tabela: str) -> int:
    con = dados.conectar()
    n = con.execute(f"SELECT COUNT(*) FROM {tabela}").fetchone()[0]
    con.close()
    return n


def rodar(numero: int) -> dict:
    nome, mensagens, descricao = DEMOS[numero]
    with tempfile.TemporaryDirectory() as pasta:
        pasta = Path(pasta)
        dados.CAMINHO_DB = pasta / "academico.db"
        dados.inicializar(forcar=True)
        sistema = Sistema(checkpoint=pasta / "cp.sqlite", memoria_dir=pasta / "mem")
        turnos, thread = [], f"demo-{nome}"
        inicio = time.monotonic()
        try:
            for texto in mensagens:
                r = sistema.conversar(thread, texto)
                turnos.append({"aluno": texto, "agente": r["saida"]["resultado"],
                               "saida": r["saida"], "termino": r["termino"],
                               "aguardando_humano": r["aguardando_humano"]})
                print(f"  aluno:  {texto}\n  agente: {r['saida']['resultado'][:160]}")
                if r["termino"] != "respondeu" or r["aguardando_humano"]:
                    break

            decisoes = None
            if numero == 6 and turnos[-1]["aguardando_humano"]:
                protocolo = turnos[-1]["saida"]["protocolo"]
                decisao = humano.DecisaoHumana(decisao="aprovar_editando", por="coord-demo",
                                               edicao={"semestre_efetivo": "2027.1"})
                primeira = sistema.decidir(protocolo, decisao)
                segunda = sistema.decidir(protocolo, decisao)
                decisoes = {"primeira_aprovacao": primeira, "segunda_aprovacao": segunda,
                            "decisoes_gravadas": contar("decisoes_humanas"),
                            "gravada": humano.decisao_gravada(protocolo)}
                print(f"  coordenação: {primeira}\n  repetida:    {segunda}")

            estado = sistema.estado(thread)
            registro = {
                "caso": nome, "descricao": descricao,
                "executado_em": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "commit": commit(), "modelo": agente.MODELO,
                "prompt": {"arquivo": "src/prompts/triagem-v3.txt",
                           "sha256": hashlib.sha256(nos.SYSTEM.encode()).hexdigest()[:16]},
                "parametros": {"temperature": 0, "recursion_limit": 60,
                               "orcamento": {"max_passos": 8, "max_tokens": 20000}},
                "duracao_s": round(time.monotonic() - inicio, 1),
                "turnos": turnos,
                "trajetoria": [{"ferramenta": p["ferramenta"], "argumentos": p["argumentos"],
                                "resultado": p["resultado"], "erro": p["erro"]}
                               for p in estado.get("passos", [])],
                "trilha_de_nos": estado.get("eventos", []),
                "tokens_gastos": estado.get("tokens_gastos"),
                "chamadas_ao_modelo": estado.get("n_chamadas_modelo"),
                "contagens": {t: contar(t) for t in
                              ("documentos_emitidos", "casos_pendentes", "aprovacoes", "decisoes_humanas")},
                "aprovacao_humana": decisoes,
            }
        finally:
            sistema.fechar()
    PASTA.mkdir(parents=True, exist_ok=True)
    (PASTA / f"{nome}.json").write_text(
        json.dumps(registro, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return registro


def main() -> int:
    escolhidos = [int(a) for a in sys.argv[1:]] or sorted(DEMOS)
    for numero in escolhidos:
        nome, _, descricao = DEMOS[numero]
        print(f"\n{'=' * 72}\n{nome}: {descricao}\n{'=' * 72}")
        registro = rodar(numero)
        print(f"  -> {registro['trilha_de_nos'][-1]} | {registro['chamadas_ao_modelo']} chamadas | "
              f"{registro['tokens_gastos']} tokens | logs/parte2/{nome}.json")
        time.sleep(15)  # abaixo do teto de 8.000 tokens/min do free tier
    return 0


if __name__ == "__main__":
    sys.exit(main())
