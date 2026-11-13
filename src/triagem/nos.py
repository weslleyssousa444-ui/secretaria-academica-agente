# Os nós do grafo de triagem (docs/grafo.md §1).
#
# Cada nó faz UMA coisa e diz, no comentário, QUEM decide nele: o código ou o
# modelo. Só `agente` chama o modelo; todos os outros são código. As
# ferramentas, as guardas de negócio (A3-A9 do model card), o retry de
# transporte e a pós-condição do trancamento (L02) são os da Parte 1,
# reaproveitados de src/agente.py — o grafo muda ONDE a decisão mora, não as
# regras que ela respeita.

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

from langgraph.types import interrupt

import agente
from agente import ErroFatal, ErroRecuperavel, Orcamento
from triagem import humano, janela, saida as contrato, telemetria, validacao
from triagem.memoria import Memoria
from triagem.regimento import consultar_regimento

RAIZ = Path(__file__).resolve().parents[2]
SYSTEM = (Path(__file__).resolve().parents[1] / "prompts" / "triagem-v2.txt"
          ).read_text(encoding="utf-8")

# Teto de TEMPO por turno, conferido ENTRE chamadas ao modelo. O Orcamento da
# Parte 1 (agente.Orcamento) guarda um instante de início e nunca o confere; e o
# retry de transporte chega a 8 tentativas de até 90 s. Sem este teto, um
# provedor lento segurava o turno por minutos (e, na API, a trava global do
# processo, com todos os outros alunos). LIMITE: uma única chamada em retry pode
# passar do teto; ele impede a PRÓXIMA volta, e não interrompe a em curso.
MAX_SEGUNDOS_POR_TURNO = 120.0
# Parâmetro de amostragem da única chamada ao modelo; o registro de execução o grava.
TEMPERATURA = 0

# CONTROLES DA PARTE 3 (docs/seguranca.md §3). Os três valem FORA do prompt: o
# texto injetado chega pelo mesmo canal que o prompt, e só o código o barra.
#
# ASI02: um modelo (ou quem o sequestrou) pode devolver dezenas de chamadas numa
# única resposta, e todas executariam antes de o orçamento de passos ser visto.
# CUSTO: o modelo não pode agrupar duas escritas numa volta (emitir dois
# documentos exige duas voltas, uma chamada de modelo a mais).
MAX_CHAMADAS_POR_VOLTA = 4
MAX_ESCRITAS_POR_VOLTA = 1

# ASI03: ferramentas que recebem um RA. Com sessão autenticada, o RA do argumento
# TEM de ser o da sessão ("" = RA nunca identificado, só faz sentido ao escalar).
FERRAMENTAS_COM_RA = frozenset({"buscar_aluno", "consultar_financeiro",
                                "emitir_documento", "escalar_para_humano"})

SAUDACAO_FIXA = (
    "Olá! Sou o assistente da secretaria acadêmica. Posso ajudar com "
    "declaração de matrícula, segunda via de histórico, trancamento de "
    "matrícula ou dúvidas sobre o Regimento. Como posso te ajudar?")
TEXTO_SEM_CONCLUSAO = ("Não consegui concluir seu atendimento. Abra uma nova "
                       "solicitação ou procure a secretaria.")
_SAUDACAO = re.compile(
    r"^\s*(oi+|ol[aá]+|bom dia|boa tarde|boa noite|e a[ií]|opa|hello|hi)[\s!.,?]*$",
    re.IGNORECASE)

# A ferramenta do RAG entra na tabela do agente (leitura, sem efeito colateral).
FERRAMENTAS = {**agente.FERRAMENTAS, "consultar_regimento": consultar_regimento}
DECLARACAO_REGIMENTO = {
    "type": "function",
    "function": {
        "name": "consultar_regimento",
        "description": ("Consulta o Regimento Acadêmico (regras, prazos, "
                        "condições de documentos e de trancamento) e devolve "
                        "os artigos que tratam do assunto. Use para DÚVIDA "
                        "sobre regra; não use para decidir o pedido de um "
                        "aluno (isso é buscar_aluno e consultar_financeiro)."),
        "parameters": {
            "type": "object",
            "properties": {"pergunta": {"type": "string",
                                        "description": "a dúvida, com as palavras do aluno"}},
            "required": ["pergunta"], "additionalProperties": False,
        },
    },
}
DECLARACOES = [*agente.DECLARACOES.values(), DECLARACAO_REGIMENTO]


# ------------------------------------------------------------------ utilidades

def _ultima_do_usuario(estado: dict) -> str:
    for m in reversed(estado.get("mensagens", [])):
        if m.get("role") == "user":
            return m.get("content") or ""
    return ""


def _ultima_do_assistente(estado: dict) -> str:
    """Texto da última mensagem do assistente DEPOIS da última do usuário."""
    for m in reversed(estado.get("mensagens", [])):
        if m.get("role") == "user":
            break
        if m.get("role") == "assistant" and m.get("content"):
            return m["content"]
    return ""


def assinatura(passo: dict) -> tuple:
    return (passo["ferramenta"], json.dumps(passo["argumentos"], sort_keys=True))


def laco_detectado(passos: list[dict], limite: int = 3) -> bool:
    if len(passos) < limite:
        return False
    return len({assinatura(p) for p in passos[-limite:]}) == 1


def argumentos_tentados(chamada: dict) -> dict:
    """Os argumentos que o modelo pediu, para o registro da chamada recusada."""
    try:
        valor = json.loads(chamada["function"]["arguments"])
        return valor if isinstance(valor, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def passo_recusado(nome: str, argumentos: dict, motivo: str, sugestao: str) -> dict:
    """Uma chamada que o CÓDIGO não executa: devolve erro como dado, sem efeito."""
    return {"ferramenta": nome, "argumentos": argumentos, "erro": motivo, "recusado": True,
            "resultado": {"erro": motivo, "sugestao": sugestao}}


def executar_chamada(nome: str, argumentos_json: str, ra_sessao: str | None = None) -> dict:
    """Uma chamada de ferramenta. Erro vira DADO que ensina o modelo (nota 03
    da Aula 05), nunca exceção que derruba o turno. Diferença para
    agente.executar: QUALQUER exceção da ferramenta (ex.: banco travado) é
    capturada e devolvida sem vazar detalhe interno (ASI08, docs/seguranca.md)."""
    passo = {"ferramenta": nome, "argumentos": {}, "resultado": None, "erro": None}
    try:
        passo["argumentos"] = json.loads(argumentos_json)
    except json.JSONDecodeError:
        passo["erro"] = "argumentos não são JSON válido"
        passo["resultado"] = {"erro": passo["erro"]}
        return passo
    funcao = FERRAMENTAS.get(nome)
    if funcao is None:
        passo["erro"] = f"ferramenta desconhecida: {nome}"
        passo["resultado"] = {"erro": passo["erro"], "disponiveis": sorted(FERRAMENTAS)}
        return passo
    # ASI03 (credencial delegada): o RA da ferramenta é o da SESSÃO, e não o que a
    # pessoa digitou. Fail-closed: o dado de outro aluno nem chega a ser lido.
    if ra_sessao is not None and nome in FERRAMENTAS_COM_RA:
        ra_pedido = passo["argumentos"].get("ra")
        if ra_pedido not in (ra_sessao, "", None):
            return passo_recusado(
                nome, passo["argumentos"], "ra diferente do aluno autenticado nesta sessão",
                "este atendimento só consulta o RA do próprio aluno autenticado; diga isso "
                "ao aluno e não tente outro RA")
    try:
        passo["resultado"] = funcao(**passo["argumentos"])
    except ErroRecuperavel as e:
        passo["erro"], passo["resultado"] = e.payload["erro"], e.payload
    except TypeError as e:
        passo["erro"] = f"argumentos inválidos: {e}"
        passo["resultado"] = {"erro": passo["erro"]}
    except Exception as e:  # noqa: BLE001 — fail-safe declarado acima
        passo["erro"] = f"falha interna da ferramenta ({type(e).__name__})"
        passo["resultado"] = {"erro": passo["erro"]}
    return passo


def mensagem_de_ferramenta(passo: dict, id_chamada: str) -> dict:
    conteudo = passo["resultado"] if passo["resultado"] is not None else {"erro": passo["erro"]}
    return {"role": "tool", "tool_call_id": id_chamada, "name": passo["ferramenta"],
            "content": json.dumps(conteudo, ensure_ascii=False)}


def trancamento_devido(estado: dict) -> str | None:
    """Pós-condição L02 (docs/model-card.md): o aluno pediu trancamento, o RA
    foi confirmado por `buscar_aluno` e nenhum caso de trancamento foi aberto.
    Devolve o RA a escalar. A MESMA regra de agente.escalonamento_de_
    trancamento_devido, sobre o estado do grafo."""
    pediu = any(agente.PEDIDO_DE_TRANCAMENTO.search(m.get("content") or "")
                for m in estado.get("mensagens", []) if m.get("role") == "user")
    if not pediu:
        return None
    passos = estado.get("passos", [])
    if any(p["ferramenta"] == "escalar_para_humano" and p["erro"] is None
           and p["argumentos"].get("tipo_pedido") == "trancamento_matricula" for p in passos):
        return None
    for p in reversed(passos):
        if p["ferramenta"] == "buscar_aluno" and p["erro"] is None:
            return p["resultado"]["ra"]
    return None


# ------------------------------------------------------------------ os nós

class Nos:
    """Os nós, ligados a uma memória. A memória é criada na primeira leitura,
    para que importar o grafo (conferir_grafo.py) não toque em arquivo."""

    def __init__(self, memoria: Memoria | None = None, orcamento: Orcamento | None = None,
                 max_segundos: float = MAX_SEGUNDOS_POR_TURNO):
        self._memoria = memoria
        self.orcamento = orcamento or Orcamento()
        self.max_segundos = max_segundos

    @property
    def memoria(self) -> Memoria:
        if self._memoria is None:
            self._memoria = Memoria(Path(os.environ.get(
                "TRIAGEM_MEMORIA_DIR", RAIZ / "dados" / "memoria")))
        return self._memoria

    # 1. ENTRADA — código. Reinicia o que vale por turno.
    def entrada(self, estado: dict) -> dict:
        return {"inicio_do_turno": len(estado.get("passos", [])),
                "turno_iniciado_em": time.monotonic(), "tipo_pedido": None,
                "memoria_bloco": "", "correcoes": 0, "termino": None, "motivo": None,
                "saida": None, "caso_trancamento": None, "decisao_humana": None,
                "eventos": ["entrada"]}

    # 2a. LER MEMÓRIA — código. Só com identidade (memoria.py).
    def ler_memoria(self, estado: dict) -> dict:
        bloco = self.memoria.ler_bloco(estado.get("ra_autenticado"), _ultima_do_usuario(estado))
        return {"memoria_bloco": bloco["texto"],
                "eventos": [f"ler_memoria:{bloco['episodios_usados']}"]}

    # 2b. CLASSIFICAR — regra em código (degrau mais barato, docs/grafo.md §2.3).
    def classificar_pedido(self, estado: dict) -> dict:
        texto = _ultima_do_usuario(estado)
        if _SAUDACAO.match(texto):
            tipo = "saudacao"
        elif agente.PEDIDO_DE_TRANCAMENTO.search(texto):
            tipo = "trancamento"
        else:
            tipo = "outro"
        return {"tipo_pedido": tipo, "eventos": [f"classificar_pedido:{tipo}"]}

    # 3. ROTEAR — junção dos dois ramos paralelos; a aresta condicional decide.
    def rotear(self, estado: dict) -> dict:
        return {"eventos": ["rotear"]}

    # 3b. SAUDAÇÃO — texto fixo, sem chamar o modelo.
    def saudacao_fixa(self, estado: dict) -> dict:
        return {"mensagens": [{"role": "assistant", "content": SAUDACAO_FIXA}],
                "eventos": ["saudacao_fixa"]}

    # 4. AGENTE — O MODELO DECIDE: qual ferramenta chamar, ou responder.
    def agente(self, estado: dict) -> dict:
        passos = estado.get("passos", [])
        if len(passos) >= self.orcamento.max_passos:
            return {"termino": "orcamento_esgotado",
                    "motivo": f"passos {len(passos)}/{self.orcamento.max_passos}",
                    "eventos": ["agente:orcamento"]}
        if estado.get("tokens_gastos", 0) >= self.orcamento.max_tokens:
            return {"termino": "orcamento_esgotado",
                    "motivo": f"tokens {estado['tokens_gastos']}/{self.orcamento.max_tokens}",
                    "eventos": ["agente:orcamento"]}
        decorrido = time.monotonic() - estado.get("turno_iniciado_em", time.monotonic())
        if decorrido > self.max_segundos:
            return {"termino": "orcamento_esgotado",
                    "motivo": f"tempo {decorrido:.0f}s/{self.max_segundos:.0f}s",
                    "eventos": ["agente:orcamento"]}
        if laco_detectado(passos):
            return {"termino": "laco_detectado",
                    "motivo": "mesma ferramenta e argumentos 3x seguidas",
                    "eventos": ["agente:laco"]}

        mensagens, omitidos = janela.compactar(estado["mensagens"])
        contexto = [{"role": "system", "content": SYSTEM}]
        if estado.get("memoria_bloco"):
            contexto.append({"role": "system", "content": "MEMÓRIA\n" + estado["memoria_bloco"]})
        with telemetria.chamada_ao_modelo(agente.MODELO, TEMPERATURA) as span_chat:
            try:
                resposta = agente.chamar_com_retry(
                    model=agente.MODELO, messages=contexto + mensagens,
                    tools=DECLARACOES, temperature=TEMPERATURA)
            except ErroFatal as e:
                telemetria.registrar_erro(span_chat, e, "erro_fatal")
                return {"termino": "erro_fatal", "motivo": str(e), "eventos": ["agente:erro_fatal"]}
            telemetria.registrar_resposta_do_modelo(span_chat, resposta, omitidos)

        msg = resposta.choices[0].message
        registro: dict = {"role": "assistant", "content": msg.content}
        if msg.tool_calls:
            registro["tool_calls"] = [
                {"id": c.id, "type": "function",
                 "function": {"name": c.function.name, "arguments": c.function.arguments}}
                for c in msg.tool_calls]
        return {"mensagens": [registro], "tokens_gastos": resposta.usage.total_tokens,
                "n_chamadas_modelo": 1,
                "eventos": ["agente" + (f":janela-{omitidos}" if omitidos else "")]}

    # 5. FERRAMENTAS — código. Executa o que o modelo pediu, com as guardas.
    def ferramentas(self, estado: dict) -> dict:
        ultima = estado["mensagens"][-1]
        novas, passos, escritas = [], [], 0
        ra_sessao = estado.get("ra_autenticado")
        for posicao, chamada in enumerate(ultima["tool_calls"]):
            nome = chamada["function"]["name"]
            with telemetria.execucao_de_ferramenta(nome, chamada["id"]) as span_ferramenta:
                passo = self._uma_chamada(posicao, chamada, escritas, ra_sessao)
                telemetria.registrar_ferramenta(span_ferramenta, passo, bool(passo.get("recusado")))
            escritas += nome in agente.ESCRITA and passo["erro"] is None
            passos.append(passo)
            novas.append(mensagem_de_ferramenta(passo, chamada["id"]))
        return {"mensagens": novas, "passos": passos, "eventos": ["ferramentas"]}

    def _uma_chamada(self, posicao: int, chamada: dict, escritas: int, ra_sessao: str | None) -> dict:
        """Uma chamada de ferramenta, com os controles ASI02 e ASI03."""
        nome = chamada["function"]["name"]
        # ASI02: o teto vale POR VOLTA, e toda chamada recebe uma resposta (o
        # protocolo da API exige uma mensagem de ferramenta por tool_call).
        if posicao >= MAX_CHAMADAS_POR_VOLTA:
            return passo_recusado(nome, argumentos_tentados(chamada),
                                  f"mais de {MAX_CHAMADAS_POR_VOLTA} chamadas numa só volta",
                                  "faça uma chamada por vez")
        if nome in agente.ESCRITA and escritas >= MAX_ESCRITAS_POR_VOLTA:
            return passo_recusado(nome, argumentos_tentados(chamada),
                                  f"mais de {MAX_ESCRITAS_POR_VOLTA} escrita numa só volta",
                                  "faça uma escrita por volta")
        # ASI03 está dentro de executar_chamada (precisa do RA da sessão).
        return executar_chamada(nome, chamada["function"]["arguments"], ra_sessao)

    # 6. GARANTIR TRANCAMENTO — código. Pós-condição L02 (portão).
    def garantir_trancamento(self, estado: dict) -> dict:
        ra = trancamento_devido(estado)
        if not ra:
            return {"eventos": ["garantir_trancamento:ok"]}
        argumentos = {"ra": ra, "tipo_pedido": "trancamento_matricula",
                      "motivo": "trancamento (aberto pelo código: o agente respondeu sem escalar)",
                      "chave": f"{ra}:trancamento_matricula:trancamento"}
        id_chamada = f"codigo-{len(estado.get('passos', []))}"
        # A escrita feita PELO CÓDIGO também é uma chamada de ferramenta no trace,
        # marcada com a origem: sem isso, reconstruir a decisão pelo trace não
        # veria quem abriu o caso (docs/model-card.md, Registro e retenção).
        with telemetria.execucao_de_ferramenta("escalar_para_humano", id_chamada) as span_codigo:
            passo = {"ferramenta": "escalar_para_humano", "argumentos": argumentos,
                     "resultado": agente.escalar_para_humano(**argumentos), "erro": None}
            telemetria.registrar_ferramenta(span_codigo, passo, False)
            span_codigo.set_attribute("agente.ferramenta.origem", "codigo")
        return {
            "mensagens": [
                {"role": "assistant", "content": None, "tool_calls": [
                    {"id": id_chamada, "type": "function", "function": {
                        "name": "escalar_para_humano",
                        "arguments": json.dumps(argumentos, ensure_ascii=False)}}]},
                mensagem_de_ferramenta(passo, id_chamada)],
            "passos": [passo], "eventos": ["garantir_trancamento:escalou_pelo_codigo"]}

    # 7. VALIDAR — código. O "avaliador" do avaliador-otimizador.
    def validar_resposta(self, estado: dict) -> dict:
        turno = estado.get("passos", [])[estado.get("inicio_do_turno", 0):]
        problemas = validacao.validar_resposta(
            _ultima_do_assistente(estado), estado.get("passos", []), turno)
        if not problemas:
            return {"eventos": ["validar:ok"]}
        if estado.get("correcoes", 0) < 1:
            return {"correcoes": 1, "eventos": ["validar:devolveu"],
                    "mensagens": [{"role": "system", "content": (
                        "[verificação automática] Sua resposta foi reprovada: "
                        + "; ".join(problemas) + ". Reescreva a resposta ao aluno "
                        "usando só dados devolvidos pelas ferramentas.")}]}
        return {"eventos": ["validar:contingencia"]}

    # 7b. CONTINGÊNCIA — código. Resposta por molde, sem o modelo.
    def contingencia(self, estado: dict) -> dict:
        return {"mensagens": [{"role": "assistant",
                               "content": validacao.resposta_de_contingencia(estado.get("passos", []))}],
                "eventos": ["contingencia"]}

    # 8. MONTAR SAÍDA — código. O objeto validado do contrato (saida.py).
    def montar_saida(self, estado: dict) -> dict:
        todos = estado.get("passos", [])
        turno = todos[estado.get("inicio_do_turno", 0):]
        termino = estado.get("termino") or "respondeu"
        bruto = _ultima_do_assistente(estado) or TEXTO_SEM_CONCLUSAO
        texto, declarada = validacao.separar_suficiencia(bruto)  # a marcação não vai ao aluno
        citados = validacao.artigos_citados(texto, validacao.artigos_devolvidos(todos))
        decisao = contrato.decisao_da_trajetoria(turno)
        if decisao == "responder_regimento" and declarada is False:
            decisao = "sem_acao"  # o agente disse que o Regimento não responde: é recusa
        objeto = contrato.SaidaTriagem(
            resultado=texto or TEXTO_SEM_CONCLUSAO, decisao=decisao,
            fonte=contrato.fontes_da_trajetoria(turno, citados if declarada else []),
            suficiencia=contrato.suficiencia_da_trajetoria(decisao, turno, termino, citados, declarada),
            protocolo=contrato.protocolo_da_trajetoria(turno), termino=termino)
        caso = next((p["resultado"]["protocolo"] for p in turno
                     if p["ferramenta"] == "escalar_para_humano" and p["erro"] is None
                     and p["argumentos"].get("tipo_pedido") == "trancamento_matricula"), None)
        objeto.aguardando_humano = caso is not None
        return {"saida": objeto.model_dump(), "termino": termino, "caso_trancamento": caso,
                "eventos": ["montar_saida"]}

    # 9. ESCREVER MEMÓRIA — código. A política de escrita é por regra.
    def escrever_memoria(self, estado: dict) -> dict:
        turno = estado.get("passos", [])[estado.get("inicio_do_turno", 0):]
        gravados = self.memoria.escrever_depois_do_turno(estado.get("ra_autenticado"), turno)
        return {"eventos": ["escrever_memoria:" + ("+".join(k for k, v in gravados.items() if v) or "nada")]}

    # 10. REGISTRAR ESPERA — código, idempotente, ANTES do interrupt.
    def registrar_espera(self, estado: dict) -> dict:
        protocolo = estado["caso_trancamento"]
        ra = next((p["argumentos"].get("ra") for p in estado.get("passos", [])
                   if p["ferramenta"] == "escalar_para_humano"
                   and (p["resultado"] or {}).get("protocolo") == protocolo), None)
        humano.registrar_espera(estado.get("thread_id", "?"), protocolo, ra)
        return {"eventos": ["registrar_espera"]}

    # 11. APROVAÇÃO — O HUMANO DECIDE. O nó roda de novo na retomada: nada
    #     com efeito colateral antes do interrupt (a espera já foi gravada no
    #     nó anterior, e a tela é só leitura).
    def aprovacao_coordenacao(self, estado: dict) -> dict:
        resposta = interrupt(humano.tela_da_aprovacao(estado["caso_trancamento"]))
        return {"decisao_humana": resposta, "eventos": ["aprovacao_coordenacao:retomado"]}

    # 12. REGISTRAR DECISÃO — código, idempotente (chave `<protocolo>:decisao`).
    def registrar_decisao(self, estado: dict) -> dict:
        decisao = humano.DecisaoHumana(**estado["decisao_humana"])
        gravacao = humano.registrar_decisao(estado["caso_trancamento"], decisao)
        return {"decisao_humana": {**estado["decisao_humana"], "gravacao": gravacao},
                "eventos": ["registrar_decisao"]}


# ------------------------------------------------------------------ arestas condicionais
# Cada função devolve o NOME do destino; o mapa de destinos é explícito em
# grafo.py (o `get_graph()` de conferir_grafo.py lê esse mapa).

def depois_do_rotear(estado: dict) -> str:  # decide: CÓDIGO (campo)
    return "saudacao_fixa" if estado.get("tipo_pedido") == "saudacao" else "agente"


def depois_do_agente(estado: dict) -> str:  # decide: CÓDIGO (campo e presença de tool_calls)
    if estado.get("termino"):
        return "montar_saida"
    return "ferramentas" if estado["mensagens"][-1].get("tool_calls") else "garantir_trancamento"


def depois_do_garantir(estado: dict) -> str:  # decide: CÓDIGO (trilha de eventos)
    return "agente" if estado["eventos"][-1].endswith("escalou_pelo_codigo") else "validar_resposta"


def depois_do_validar(estado: dict) -> str:  # decide: CÓDIGO (trilha de eventos)
    ultimo = estado["eventos"][-1]
    if ultimo == "validar:devolveu":
        return "agente"
    return "contingencia" if ultimo == "validar:contingencia" else "montar_saida"


def depois_da_memoria(estado: dict) -> str:  # decide: CÓDIGO (campo)
    return "registrar_espera" if estado.get("caso_trancamento") else "__fim__"
