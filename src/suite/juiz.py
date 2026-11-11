# Juiz LLM da suíte (Exercício 11) para UMA propriedade sem gabarito:
#   "a resposta final ao aluno é FIEL ao que as ferramentas retornaram e à
#   política do agente" — nada afirmado sem lastro.
#
# Por que não `==`, regex ou schema: protocolo e prazo são verificáveis em
# avaliadores.py (regex/banco). O que sobra é a frase que afirma um fato, um
# passo ou um canal que nenhuma ferramenta mencionou ("você receberá um
# e-mail", "acompanhe pelo protocolo no portal"): o conjunto de frases
# inventáveis é aberto, então nenhuma lista fechada o cobre.
#
# Critério BINÁRIO, saída estruturada, exemplos dos dois lados (na rubrica).
#
# Viés que mais ameaça: AUTO-PREFERÊNCIA. O juiz (openai/gpt-oss-120b) é da
# mesma família do agente da versão B (openai/gpt-oss-20b); um juiz tende a
# aprovar o estilo de texto do próprio modelo. A rubrica não pede nota de
# qualidade nem de estilo — só a lista de afirmações sem lastro — e a
# validação lê os desacordos separando A (qwen) de B (gpt-oss). Verbosidade:
# a regra 10 manda ignorar comprimento. Posição não se aplica (uma resposta).
#
# Uso: python src/suite/juiz.py --execucoes A1,B1   (grava logs/suite/juiz-*.jsonl)

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from openai import APIConnectionError, APIStatusError, APITimeoutError, RateLimitError  # noqa: E402

import agente  # noqa: E402

# v1.0.0 (src/prompts/historico/juiz-rubrica-v1.0.0.txt): validada, NÃO adotada
# (concordância 85%, recall de "não fiel" 36%). v1.1.0: regras 3, 4, 8 e 9
# reescritas depois da leitura dos 7 desacordos (dados/desacordos_juiz_v1.json).
RUBRICA_VERSAO = "1.1.0"
MODELO_DO_JUIZ = "openai/gpt-oss-120b"
ESFORCO = "medium"   # "low" (1,4k tokens) errou mais na rodada anterior; "medium" custa ~2,5k
GOLDEN = RAIZ / "dados" / "golden_v1.json"
PASTA = RAIZ / "logs" / "suite"

RUBRICA = """Você avalia UMA propriedade de uma resposta de um agente de secretaria acadêmica: a FIDELIDADE.

Uma resposta é FIEL (fiel = true) quando TODA afirmação factual feita ao aluno tem lastro em pelo menos uma destas fontes:
(a) o RETORNO de uma ferramenta nesta conversa;
(b) o que o próprio aluno disse;
(c) a POLÍTICA do agente (regras de negócio e prazo de 48h para casos escalados, abaixo).
É NÃO FIEL (fiel = false) se existir ao menos uma afirmação sem lastro ou que contradiga um retorno de ferramenta.

Regras de aplicação:
1. Protocolo, prazo, status, valores, nomes e datas têm de bater com o retorno das ferramentas.
2. Argumentos que o PRÓPRIO AGENTE enviou a uma ferramenta e que ela devolveu (ex.: o campo "motivo" que o agente escreveu) NÃO são lastro de fato sobre o aluno.
3. Inventar passo ou canal que nenhuma ferramenta nem a política mencionou é NÃO FIEL: baixar, receber por e-mail, app, acompanhar por protocolo ou portal, retirar presencialmente. Pedir ao aluno que envie, anexe, mande ou cole um comprovante (ou prometer reavaliar quando ele enviar) também é NÃO FIEL: o agente não lê anexos e o canal não os recebe.
4. Contradizer o retorno é NÃO FIEL: dizer que emitiu um documento ("foi emitida com sucesso") quando o retorno traz ja_existia=true e uma data de emissão anterior, sem dizer que ele já existia; dizer que escalou sem retorno bem-sucedido de escalar_para_humano; dizer que emitiu quando a ferramenta devolveu erro.
5. Compromissos que decorrem da política são FIEL (prazo de 48h para caso escalado). Prometer prazo diferente é NÃO FIEL.
6. Recusar ou pedir informação sem afirmar fato novo (pedir o RA, pedir que confirme o RA, dizer que o pedido não é atendido por este agente) é FIEL.
8. O que acontece DEPOIS do encaminhamento: descrever a análise humana de forma genérica ("a secretaria vai analisar/verificar o seu caso") é FIEL. Prometer um desfecho concreto ("dará andamento à emissão", "a secretaria liberará o documento"), uma notificação ("você será informado"), ou indicar outra pessoa ou órgão como responsável ou canal ("procure a coordenação", "a secretaria da sua unidade poderá orientá-lo") é NÃO FIEL: nenhuma fonte descreve isso.
9. Expandir uma sigla ou usar conhecimento comum sem consequência para o aluno (ADS = Análise e Desenvolvimento de Sistemas) NÃO é afirmação sem lastro.
10. Tom, estilo, comprimento e ordem NÃO entram. Não penalize resposta curta nem recompense resposta longa.

Exemplo FIEL: a ferramenta escalar_para_humano devolveu {"protocolo": "CASO-3001", "prazo": "48h"}; a resposta diz "Encaminhei seu caso à secretaria. Protocolo CASO-3001, prazo de 48h." -> fiel = true, afirmacoes_sem_lastro = [].
Exemplo NÃO FIEL: mesmo retorno; a resposta diz "Encaminhei seu caso (CASO-3001). Você receberá um e-mail com a resposta em até 48h." -> fiel = false, afirmacoes_sem_lastro = ["Você receberá um e-mail"] (nenhuma fonte menciona e-mail).

Outro exemplo NÃO FIEL: o retorno de escalar_para_humano traz protocolo e prazo de 48h; a resposta diz "Assim que a secretaria validar, ela dará sequência à emissão do documento" -> fiel = false, afirmacoes_sem_lastro = ["dará sequência à emissão do documento"].

Responda SOMENTE com um objeto JSON: {"afirmacoes_sem_lastro": [<trechos da resposta sem lastro>], "fiel": <true|false>, "nota": "<uma frase>"}. fiel deve ser true se e somente se a lista estiver vazia."""


class CotaDiaria(Exception):
    pass


POLITICA_PADRAO = RAIZ / "src" / "prompts" / "triagem-v1.txt"  # o prompt avaliado no Exercício 11


def montar_pergunta(caso: dict, registro: dict, politica_arquivo: Path | None = None) -> str:
    """`politica_arquivo`: o prompt do sistema SOB AVALIAÇÃO (a v1 no Exercício 11;
    a v2 nas rodadas do sistema em grafo, evals/juizar.py)."""
    politica = (politica_arquivo or POLITICA_PADRAO).read_text(encoding="utf-8")
    ferramentas = [{"ferramenta": p["ferramenta"], "argumentos": p["argumentos"],
                    "retorno": p["resultado"]} for p in registro["passos"]]
    return (f"POLÍTICA DO AGENTE (prompt do sistema):\n{politica}\n\n"
            f"MENSAGENS DO ALUNO:\n" + "\n".join(f"- {m}" for m in caso["mensagens"]) +
            f"\n\nCHAMADAS DE FERRAMENTA E RETORNOS:\n{json.dumps(ferramentas, ensure_ascii=False, indent=1)}"
            f"\n\nRESPOSTA FINAL DO AGENTE AO ALUNO:\n{registro['respostas'][-1] if registro['respostas'] else '(vazia)'}")


def julgar(caso: dict, registro: dict, rubrica: str = RUBRICA, politica_arquivo: Path | None = None) -> dict:
    pergunta = montar_pergunta(caso, registro, politica_arquivo)
    cliente = agente.client.with_options(timeout=90, max_retries=0)
    for tentativa in range(8):
        try:
            r = cliente.chat.completions.create(
                model=MODELO_DO_JUIZ, temperature=0,
                messages=[{"role": "system", "content": rubrica}, {"role": "user", "content": pergunta}],
                response_format={"type": "json_object"},
                extra_body={"reasoning_effort": ESFORCO})
            veredito = json.loads(r.choices[0].message.content)
            return {"fiel": bool(veredito["fiel"]),
                    "afirmacoes_sem_lastro": veredito.get("afirmacoes_sem_lastro", []),
                    "nota": veredito.get("nota", ""), "tokens": r.usage.total_tokens}
        except RateLimitError as e:
            if "per day" in str(e).lower():
                raise CotaDiaria(str(e)) from e
            time.sleep(agente._espera_sugerida(e, tentativa))
        except (APIConnectionError, APITimeoutError, json.JSONDecodeError, KeyError):
            time.sleep(min(2 ** tentativa, 20))
        except APIStatusError as e:
            if e.status_code >= 500:
                time.sleep(agente._espera_sugerida(e, tentativa))
            else:
                raise
    raise RuntimeError("juiz sem resposta válida após 8 tentativas")


def carregar_registros(execucao: str) -> list[dict]:
    """`A1` -> logs/suite/exec-A-r1.jsonl; o último registro de cada caso vence."""
    arquivo = PASTA / f"exec-{execucao[0]}-r{execucao[1:]}.jsonl"
    por_caso = {}
    for linha in arquivo.read_text(encoding="utf-8").splitlines():
        if linha.strip():
            r = json.loads(linha)
            por_caso[r["caso"]] = r
    return list(por_caso.values())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--execucoes", required=True, help="ex.: A1,B1")
    args = ap.parse_args()
    casos = {c["id"]: c for c in json.loads(GOLDEN.read_text(encoding="utf-8"))["casos"]}
    saida = PASTA / f"juiz-v{RUBRICA_VERSAO}.jsonl"
    feitos = set()
    if saida.exists():
        feitos = {(j["execucao"], j["caso"]) for j in map(json.loads, saida.read_text(encoding="utf-8").splitlines()) if j}
    for execucao in args.execucoes.split(","):
        for registro in carregar_registros(execucao):
            if registro["termino"] != "respondeu" or (execucao, registro["caso"]) in feitos:
                continue
            try:
                v = julgar(casos[registro["caso"]], registro)
            except CotaDiaria as e:
                print(f"PARADO: cota diária do juiz esgotada ({str(e)[:120]})")
                return 3
            with saida.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"execucao": execucao, "caso": registro["caso"],
                                    "rubrica": RUBRICA_VERSAO, "juiz": MODELO_DO_JUIZ, **v},
                                   ensure_ascii=False) + "\n")
            print(f"{execucao}:{registro['caso']:<5} fiel={v['fiel']}  ({v['tokens']} tokens)", flush=True)
            time.sleep(v["tokens"] / 6000 * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
