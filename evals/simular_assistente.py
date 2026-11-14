# SIMULAÇÃO, não medição. Roda o mesmo script de medição do 2º agente
# (evals/avaliar_assistente.py) sobre os mesmos 6 alunos fictícios, mas com um
# MODELO ROTEIRIZADO no lugar do modelo real, offline, sem chave e sem cota.
#
#   python -m evals.simular_assistente
#
# O que isto PROVA: o encanamento de ponta a ponta (caso aberto, servidor MCP,
# assistente, validador, contingência, conferência de fatos, resumo) e que os
# controles barram o que o roteiro faz de errado de propósito.
# O que isto NÃO prova: a qualidade do parecer do modelo real. Os números do
# resumo dizem o que o ROTEIRO fez, e foram escolhidos por quem escreveu o
# roteiro. Nenhum deles pode ser citado como desempenho do modelo.
#
# O roteiro, por aluno (comportamento escolhido para exercitar cada controle):
#   20229012 correto
#   20230198 recomenda a decisão nas duas tentativas -> contingência
#   20232210 cita um artigo que a busca não devolveu, corrige na 2ª tentativa
#   20231987 tenta consultar outro RA (recusado), depois correto
#   20234321 correto
#   20230555 entra em laço de ferramentas -> limite de passos -> contingência

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
os.environ.setdefault("OPENAI_API_KEY", "simulacao-sem-rede")

COMPORTAMENTO = {"20229012": "correto", "20230198": "recomenda", "20232210": "artigo_errado",
                 "20231987": "outro_ra", "20234321": "correto", "20230555": "laco"}


def _resp(tool_calls=None, content=None):
    return SimpleNamespace(usage=SimpleNamespace(total_tokens=0),
                           choices=[SimpleNamespace(message=SimpleNamespace(tool_calls=tool_calls, content=content))])


def _call(nome, **args):
    return SimpleNamespace(id=f"sim-{nome}-{len(json.dumps(args))}",
                           function=SimpleNamespace(name=nome, arguments=json.dumps(args)))


class ModeloRoteirizado:
    """Responde conforme o comportamento do aluno do caso, lido da mensagem do usuário."""

    def __init__(self):
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, messages, **_):
        caso = json.loads(messages[1]["content"].split("\n", 1)[1])
        ra, prot = caso["aluno"]["ra"], caso["protocolo"]
        modo = COMPORTAMENTO.get(ra, "correto")
        respostas_do_modelo = sum(1 for m in messages if m["role"] == "assistant" and not m.get("tool_calls"))
        chamou = [m for m in messages if m["role"] == "assistant" and m.get("tool_calls")]
        if modo == "laco":
            return _resp(tool_calls=[_call("buscar_aluno", ra=ra)])
        if modo == "outro_ra" and not chamou:
            return _resp(tool_calls=[_call("consultar_financeiro", ra="20230198")])
        if len(chamou) < (2 if modo == "outro_ra" else 1):
            return _resp(tool_calls=[_call("buscar_aluno", ra=ra), _call("consultar_financeiro", ra=ra),
                                     _call("consultar_regimento", pergunta="trancamento de matrícula")])
        fin = next(json.loads(m["content"]) for m in messages if m["role"] == "tool"
                   and "mensalidades_em_aberto" in m["content"] and '"ra": "' + ra in m["content"])
        aluno = caso["aluno"]
        fatos = [{"texto": f"{aluno['nome']}, {aluno['curso']}, matrícula {aluno['situacao_matricula']}", "fonte": "buscar_aluno"},
                 {"texto": (f"{fin['mensalidades_em_aberto']} mensalidade(s) em aberto, R$ {fin['valor_em_aberto']:.2f}"
                            if fin["mensalidades_em_aberto"] else "nenhuma mensalidade em aberto"), "fonte": "consultar_financeiro"}]
        resumo = f"Pedido de trancamento {prot} de {aluno['nome']}, encaminhado pelo atendimento."
        artigos = ["Art. 6º"]
        if modo == "recomenda":
            resumo += " Recomendo aprovar o trancamento."
        if modo == "artigo_errado" and respostas_do_modelo == 0:
            artigos = ["Art. 6º", "Art. 15"]
        pontos = ["há pendência financeira registrada"] if fin["mensalidades_em_aberto"] else []
        return _resp(content=json.dumps({"protocolo": prot, "ra": ra, "resumo": resumo, "fatos": fatos,
                                         "artigos": artigos, "pontos_de_atencao": pontos}, ensure_ascii=False))


def main() -> int:
    pasta = RAIZ / "evals" / "resultados" / "simulacao-assistente-roteirizado"
    if (pasta / "execucoes.jsonl").exists():
        (pasta / "execucoes.jsonl").unlink()
    import dados
    dados.CAMINHO_DB = Path(tempfile.mkdtemp()) / "simulacao.db"
    dados.inicializar(forcar=True)
    from evals import avaliar_assistente as av
    resumo = asyncio.run(av.avaliar(pasta, cliente=ModeloRoteirizado()))
    resumo = {"AVISO": "SIMULAÇÃO com modelo roteirizado (evals/simular_assistente.py). NÃO é medição do modelo real; "
                       "os números refletem o roteiro, escrito para exercitar os controles.", **resumo,
              "modelo": "roteiro offline (nenhuma chamada ao modelo real)",
              "meta_atingida": "não se aplica: a meta é do modelo real; o roteiro errou de propósito em 2 dos 6 casos"}
    (pasta / "resumo.json").write_text(json.dumps(resumo, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(resumo, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
