# Observabilidade: o trace de cada execução, nas convenções semânticas GenAI do
# OpenTelemetry (docs/observabilidade.md).
#
#   invoke_agent triagem-secretaria   uma por TURNO do aluno (a raiz). A conversa
#                                      que dura vários turnos tem vários traces,
#                                      ligados por `gen_ai.conversation.id`.
#   chat <modelo>                      uma por chamada ao modelo (nó `agente`).
#   execute_tool <ferramenta>          uma por ferramenta executada ou RECUSADA.
#
# Dois atributos próprios na raiz, que a convenção não tem e sem os quais nenhum
# número se lê (docs/observabilidade.md §2): `agente.termino` (a execução que
# acabou bem × a que parou no meio) e `agente.versao` (nenhum número se compara
# entre versões sem ela).
#
# O trace é TAMBÉM o registro da decisão (docs/model-card.md, campo Registro e
# retenção): ele guarda a entrada, os artigos recuperados, as versões, as
# ferramentas com argumentos e resultado, a saída, o término e a aprovação humana.
# Por isso carrega dado pessoal; `AGENTE_TRACE_CONTEUDO=0` o desliga (o trace fica
# só com a estrutura e as métricas, e deixa de servir para reconstruir uma decisão).
#
# Sem `TRIAGEM_TRACES_DIR` nem exportador explícito, o tracer é o NO-OP do
# OpenTelemetry: instrumentar não custa nada a quem não liga.

from __future__ import annotations

import hashlib
import json
import os
import threading
from contextlib import contextmanager
from pathlib import Path

from opentelemetry import trace
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult
from opentelemetry.trace import Status, StatusCode

NOME_AGENTE = "triagem-secretaria"
PROVEDOR = "groq"
LIMITE_CONTEUDO = 2000  # caracteres por atributo de conteúdo

_provedor: TracerProvider | None = None
_versao_em_cache: dict[str, str] = {}


# ------------------------------------------------------------------ exportador

def span_para_dict(span: ReadableSpan) -> dict:
    """O span como uma linha de JSON: `trace_id` e `span_id` em hexadecimal, tempos
    em nanossegundos. É o formato que `evals/metricas.py` lê."""
    contexto, pai = span.get_span_context(), span.parent
    return {
        "name": span.name,
        "trace_id": format(contexto.trace_id, "032x"),
        "span_id": format(contexto.span_id, "016x"),
        "parent_id": format(pai.span_id, "016x") if pai else None,
        "start_ns": span.start_time, "end_ns": span.end_time,
        "status": span.status.status_code.name,
        "attributes": {k: (list(v) if isinstance(v, tuple) else v) for k, v in span.attributes.items()},
        "events": [{"name": e.name, "attributes": dict(e.attributes)} for e in span.events],
    }


class ExportadorJsonl(SpanExporter):
    """Um span por linha, em arquivo. O destino consultável mais simples: `grep`,
    `jq` e `evals/metricas.py` leem o mesmo arquivo."""

    def __init__(self, caminho: Path):
        self.caminho = Path(caminho)
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        self.caminho.touch(exist_ok=True)
        os.chmod(self.caminho, 0o600)   # L26: só o usuário do processo lê o trace
        self._trava = threading.Lock()

    def export(self, spans) -> SpanExportResult:
        linhas = "".join(json.dumps(span_para_dict(s), ensure_ascii=False, default=str) + "\n" for s in spans)
        with self._trava, self.caminho.open("a", encoding="utf-8") as arquivo:
            arquivo.write(linhas)
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        pass


def configurar(exportador: SpanExporter | None = None, destino: Path | str | None = None) -> TracerProvider | None:
    """Liga o trace. `exportador` explícito (os testes usam o da memória) ou
    `destino` (arquivo JSONL). Sem nenhum dos dois, não liga e devolve None."""
    global _provedor
    if exportador is None and destino is not None:
        exportador = ExportadorJsonl(Path(destino))
    if exportador is None:
        return None
    _provedor = TracerProvider()
    _provedor.add_span_processor(SimpleSpanProcessor(exportador))
    return _provedor


def configurar_do_ambiente() -> TracerProvider | None:
    """`TRIAGEM_TRACES_DIR` liga o trace em `<pasta>/traces.jsonl`."""
    pasta = os.environ.get("TRIAGEM_TRACES_DIR")
    return configurar(destino=Path(pasta) / "traces.jsonl") if pasta else None


def desligar() -> None:
    global _provedor
    if _provedor is not None:
        _provedor.shutdown()
    _provedor = None


def tracer() -> trace.Tracer:
    return _provedor.get_tracer("triagem") if _provedor else trace.get_tracer("triagem")


def conteudo_ligado() -> bool:
    return os.environ.get("AGENTE_TRACE_CONTEUDO", "1") != "0"


def _cortar(texto) -> str:
    texto = texto if isinstance(texto, str) else json.dumps(texto, ensure_ascii=False, default=str)
    return texto if len(texto) <= LIMITE_CONTEUDO else texto[:LIMITE_CONTEUDO] + "…[cortado]"


# ------------------------------------------------------------------ versão

def _commit() -> str:
    """O commit, sem executar programa nenhum (nenhum módulo de src/ importa
    subprocess: tests/test_seguranca.py, ASI05). Na imagem não há .git: o build
    passa o valor em `AGENTE_COMMIT`."""
    if os.environ.get("AGENTE_COMMIT"):
        return os.environ["AGENTE_COMMIT"][:7]
    raiz = Path(__file__).resolve().parents[2]
    try:
        cabeca = (raiz / ".git" / "HEAD").read_text(encoding="utf-8").strip()
        if cabeca.startswith("ref: "):
            ref = raiz / ".git" / cabeca[5:]
            if ref.exists():
                return ref.read_text(encoding="utf-8").strip()[:7]
            for linha in (raiz / ".git" / "packed-refs").read_text(encoding="utf-8").splitlines():
                if linha.endswith(cabeca[5:]):
                    return linha.split()[0][:7]
        return cabeca[:7]
    except OSError:
        return "desconhecido"


def versao_do_sistema(modelo: str, prompt: str) -> str:
    """`<commit>/<sha8 do prompt>/<modelo>`: código, prompt e modelo mudam de forma
    independente (o prompt sem deploy, o modelo por variável); a versão só do
    código não separaria o antes e o depois de nenhuma dessas mudanças."""
    chave = f"{modelo}|{hash(prompt)}"
    if chave not in _versao_em_cache:
        sha = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:8]
        _versao_em_cache[chave] = f"{_commit()}/p-{sha}/{modelo}"
    return _versao_em_cache[chave]


# ------------------------------------------------------------------ os spans

@contextmanager
def invocar_agente(thread_id: str, versao: str, *, retomada: bool = False, **atributos):
    """A raiz: `invoke_agent triagem-secretaria`."""
    with tracer().start_as_current_span(f"invoke_agent {NOME_AGENTE}") as span:
        span.set_attributes({
            "gen_ai.operation.name": "invoke_agent", "gen_ai.agent.name": NOME_AGENTE,
            "gen_ai.provider.name": PROVEDOR, "gen_ai.conversation.id": thread_id,
            "agente.versao": versao, "agente.retomada": retomada, **atributos})
        try:
            yield span
        except Exception as erro:
            # Recusas de entrada são término ELAS MESMAS (a identidade, a conversa
            # encerrada); o resto é exceção, que nunca deveria acontecer.
            rotulo = {"IdentidadeAusente": "recusado_identidade",
                      "ConversaEncerrada": "conversa_encerrada"}.get(type(erro).__name__, "excecao")
            span.set_attribute("agente.termino", rotulo)
            span.record_exception(erro)
            span.set_status(Status(StatusCode.ERROR, type(erro).__name__))
            raise


def evento_de_conteudo(span, nome: str, conteudo: str) -> None:
    if conteudo_ligado():
        span.add_event(nome, {"gen_ai.message.content": _cortar(conteudo)})


def registrar_resultado(span, resultado: dict, estado: dict) -> None:
    """O que a raiz carrega ao fim de um turno: término, decisão, suficiência e o
    que permite RECONSTRUIR a decisão (docs/model-card.md)."""
    saida = resultado["saida"]
    turno = estado.get("passos", [])[estado.get("inicio_do_turno", 0):]
    # A trilha acumula os turnos da conversa; o do turno começa no último `entrada`.
    todos = estado.get("eventos", [])
    eventos = todos[max((i for i, e in enumerate(todos) if e == "entrada"), default=0):]
    artigos = [t["id"] for p in turno if p["ferramenta"] == "consultar_regimento" and p.get("resultado")
               for t in p["resultado"].get("trechos", [])]
    # Taxonomia da Aula 05: a execução que PAROU esperando uma pessoa não é a que
    # respondeu e acabou. O resultado do turno continua `respondeu` para o aluno.
    termino = "aguardando_humano" if resultado["aguardando_humano"] else resultado["termino"]
    if resultado.get("espera"):  # turno sem modelo: só devolveu o estado da espera
        span.set_attributes({"agente.termino": termino, "agente.decisao": saida["decisao"],
                             "agente.suficiente": True, "agente.protocolo": saida["protocolo"] or "",
                             "agente.aguardando_humano": True, "agente.sem_modelo": True})
        evento_de_conteudo(span, "gen_ai.choice", saida["resultado"])
        return
    span.set_attributes({
        "agente.termino": termino, "agente.motivo": resultado.get("motivo") or "",
        "agente.decisao": saida["decisao"], "agente.suficiente": saida["suficiencia"]["suficiente"],
        "agente.protocolo": saida["protocolo"] or "", "agente.aguardando_humano": resultado["aguardando_humano"],
        "agente.contingencia": "contingencia" in eventos,
        "agente.correcoes": estado.get("correcoes", 0),
        "agente.chamadas_modelo": estado.get("n_chamadas_modelo", 0),
        "agente.tokens_gastos": estado.get("tokens_gastos", 0),
        "agente.contexto_recuperado": artigos,
        "agente.ferramentas_do_turno": [p["ferramenta"] for p in turno],
    })
    evento_de_conteudo(span, "gen_ai.choice", saida["resultado"])
    if resultado["termino"] != "respondeu":
        span.set_status(Status(StatusCode.ERROR, resultado["termino"]))


@contextmanager
def chamada_ao_modelo(modelo: str, temperatura: float):
    """`chat <modelo>`."""
    with tracer().start_as_current_span(f"chat {modelo}") as span:
        span.set_attributes({
            "gen_ai.operation.name": "chat", "gen_ai.provider.name": PROVEDOR,
            "gen_ai.request.model": modelo, "gen_ai.request.temperature": temperatura})
        yield span


def registrar_resposta_do_modelo(span, resposta, omitidos: int = 0) -> None:
    uso = resposta.usage
    atributos = {"gen_ai.usage.input_tokens": uso.prompt_tokens, "gen_ai.usage.output_tokens": uso.completion_tokens,
                 "agente.janela.omitidos": omitidos}
    servido = getattr(resposta, "model", None)  # o modelo SERVIDO pode diferir do pedido
    if servido:
        atributos["gen_ai.response.model"] = servido
    parada = getattr(resposta.choices[0], "finish_reason", None)
    if parada:
        atributos["gen_ai.response.finish_reasons"] = [parada]
    span.set_attributes(atributos)


def registrar_erro(span, erro: Exception, rotulo: str) -> None:
    span.set_attribute("error.type", rotulo)
    span.record_exception(erro)
    span.set_status(Status(StatusCode.ERROR, rotulo))


@contextmanager
def execucao_de_ferramenta(nome: str, id_chamada: str):
    """`execute_tool <ferramenta>`."""
    with tracer().start_as_current_span(f"execute_tool {nome}") as span:
        span.set_attributes({"gen_ai.operation.name": "execute_tool", "gen_ai.tool.name": nome,
                             "gen_ai.tool.call.id": id_chamada, "gen_ai.tool.type": "function"})
        yield span


def registrar_ferramenta(span, passo: dict, recusada: bool) -> None:
    span.set_attributes({"agente.ferramenta.recusada": recusada, "agente.ferramenta.erro": passo["erro"] or ""})
    if conteudo_ligado():
        span.set_attributes({"gen_ai.tool.call.arguments": _cortar(passo["argumentos"]),
                             "gen_ai.tool.call.result": _cortar(passo["resultado"])})
    if passo["erro"]:
        span.set_status(Status(StatusCode.ERROR, passo["erro"][:80]))
