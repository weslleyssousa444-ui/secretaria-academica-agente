# Agente de triagem da secretaria acadêmica — Parte 1 (agente simples).
#
# Padrão de estado/orçamento/laço reaproveitado de `aula05-agentes/agente.py`
# do repositório de laboratórios da disciplina, simplificado para o escopo
# desta entrega: sem compaction, sem checkpoint em disco, sem confirmação
# humana (nenhuma ferramenta daqui executa ação irreversível — ver
# docs/case.md §2.4, a ação irreversível de verdade nunca é do agente).
#
#     mensagens[] é FORMATO DE TRANSPORTE, não é o estado do agente.
#
# O estado é o objeto Estado; a lista de mensagens enviada ao modelo é
# derivada dele a cada volta por montar_mensagens().

import json
import os
import time
from dataclasses import dataclass, field, asdict
from datetime import date
from enum import Enum
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
from openai import OpenAI, RateLimitError, APIConnectionError, APIStatusError

import dados

load_dotenv()

client = OpenAI(
    base_url=os.environ.get("LLM_BASE_URL", "https://api.mistral.ai/v1"),
    api_key=os.environ.get("OPENAI_API_KEY"),
)
MODELO = os.environ.get("LLM_MODELO", "mistral-small-latest")

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "triagem-v1.txt"
SYSTEM = PROMPT_PATH.read_text(encoding="utf-8")

# Preços documentados em docs/modelos.md §3.1 (US$ por 1M de tokens).
# Reconfirme em https://mistral.ai/pricing antes de usar em produção.
PRECOS = {
    "ministral-3b-latest": {"entrada": 0.10, "saida": 0.10},
    "mistral-small-latest": {"entrada": 0.15, "saida": 0.60},
    "mistral-large-latest": {"entrada": 0.50, "saida": 1.50},
}


def custo(entrada: int, saida: int, modelo: str | None = None) -> float:
    """`modelo=None` lê o MODELO atual do módulo em tempo de chamada, não em
    tempo de definição — é o que permite `comparar_modelos.py` trocar
    `agente.MODELO` em runtime e ter o custo certo por candidato."""
    preco = PRECOS.get(modelo or MODELO)
    if not preco:
        return 0.0
    return (entrada * preco["entrada"] + saida * preco["saida"]) / 1_000_000


# ============================================================ EXCEÇÕES
# A distinção da nota 03 de aula05: quem classifica o erro é o CÓDIGO,
# não o modelo.

class ErroRecuperavel(Exception):
    """O modelo pode contornar mudando a chamada. Volta como observação —
    é ela quem carrega a sugestão que ensina o modelo a se corrigir."""

    def __init__(self, mensagem: str, **contexto):
        super().__init__(mensagem)
        self.payload = {"erro": mensagem, **contexto}


class ErroFatal(Exception):
    """Nenhuma decisão do modelo resolve (ex.: API fora do ar). Aborta o laço."""


# ============================================================ O ESTADO

class Termino(str, Enum):
    RESPONDEU = "respondeu"
    ORCAMENTO = "orcamento_esgotado"
    ERRO_FATAL = "erro_fatal"
    LACO = "laco_detectado"


@dataclass
class Passo:
    indice: int
    ferramenta: str
    argumentos: dict
    resultado: dict | None = None
    erro: str | None = None


@dataclass
class Estado:
    execucao_id: str = field(default_factory=lambda: uuid4().hex[:8])
    caso: str = ""
    passos: list[Passo] = field(default_factory=list)
    tokens_gastos: int = 0
    custo_estimado: float = 0.0
    termino: Termino | None = None
    motivo: str | None = None
    historico: list[dict] = field(default_factory=list)  # visto pelo modelo

    @property
    def n_passos(self) -> int:
        return len(self.passos)

    def registrar(self, passo: Passo) -> None:
        self.passos.append(passo)


@dataclass
class Orcamento:
    """Três moedas. Igual à nota da aula 05: `max_passos` sozinho não é
    orçamento — um passo custa entre centenas e milhares de tokens."""
    max_passos: int = 8
    max_tokens: int = 20_000
    max_reais: float = 0.05
    inicio: float = field(default_factory=time.monotonic)

    def excedido(self, estado: Estado) -> str | None:
        if estado.n_passos >= self.max_passos:
            return f"passos {estado.n_passos}/{self.max_passos}"
        if estado.tokens_gastos >= self.max_tokens:
            return f"tokens {estado.tokens_gastos}/{self.max_tokens}"
        if estado.custo_estimado >= self.max_reais:
            return f"custo US$ {estado.custo_estimado:.4f}/{self.max_reais}"
        return None


# ============================================================ FERRAMENTAS
# As quatro do catálogo (docs/case.md §2.4). Todas conversam com o SQLite
# de dados.py — nenhuma lê estrutura Python em memória (item 4.2).

TIPOS_DOCUMENTO_VALIDOS = {"declaracao_matricula", "segunda_via_historico"}


def buscar_aluno(ra: str) -> dict:
    conexao = dados.conectar()
    linha = conexao.execute(
        "SELECT * FROM alunos WHERE ra = ?", (ra,)).fetchone()
    conexao.close()
    if linha is None:
        raise ErroRecuperavel(
            "RA não encontrado no sistema acadêmico", recebido=ra,
            sugestao="peça ao aluno para confirmar o RA uma vez; se não "
                     "encontrar de novo, use escalar_para_humano com motivo "
                     "'RA não encontrado'")
    return dict(linha)


def consultar_financeiro(ra: str) -> dict:
    conexao = dados.conectar()
    aluno = conexao.execute(
        "SELECT ra FROM alunos WHERE ra = ?", (ra,)).fetchone()
    if aluno is None:
        conexao.close()
        raise ErroRecuperavel("RA não encontrado no sistema acadêmico",
                              recebido=ra, sugestao="confirme o RA com o aluno")
    linha = conexao.execute(
        "SELECT mensalidades_em_aberto, valor_em_aberto FROM financeiro "
        "WHERE ra = ?", (ra,)).fetchone()
    conexao.close()
    if linha is None:
        return {"ra": ra, "mensalidades_em_aberto": 0, "valor_em_aberto": 0.0}
    return {"ra": ra, **dict(linha)}


def emitir_documento(ra: str, tipo_documento: str) -> dict:
    """ESCRITA, reversível (um documento pode ser reemitido). Valida a regra
    de novo aqui — defesa em profundidade: mesmo que o modelo erre no passo
    de análise, esta ferramenta não deixa passar (docs/case.md §2.11)."""
    if tipo_documento not in TIPOS_DOCUMENTO_VALIDOS:
        raise ErroRecuperavel(
            "tipo de documento não emitido por este agente", recebido=tipo_documento,
            validos=sorted(TIPOS_DOCUMENTO_VALIDOS),
            sugestao="se for trancamento_matricula, use escalar_para_humano")

    conexao = dados.conectar()
    aluno = conexao.execute(
        "SELECT * FROM alunos WHERE ra = ?", (ra,)).fetchone()
    if aluno is None:
        conexao.close()
        raise ErroRecuperavel("RA não encontrado", recebido=ra)

    if tipo_documento == "declaracao_matricula" and aluno["situacao_matricula"] != "ativa":
        conexao.close()
        raise ErroRecuperavel(
            "aluno não está com matrícula ativa — não é possível emitir "
            "declaração de matrícula", situacao=aluno["situacao_matricula"],
            sugestao="use escalar_para_humano")

    if tipo_documento == "segunda_via_historico":
        financeiro = conexao.execute(
            "SELECT mensalidades_em_aberto FROM financeiro WHERE ra = ?",
            (ra,)).fetchone()
        pendencias = financeiro["mensalidades_em_aberto"] if financeiro else 0
        if pendencias > 0:
            conexao.close()
            raise ErroRecuperavel(
                "aluno tem pendência financeira — segunda via exige quitação "
                "total", mensalidades_em_aberto=pendencias,
                sugestao="use escalar_para_humano com motivo 'pendência financeira'")

    existente = conexao.execute(
        "SELECT * FROM documentos_emitidos WHERE ra = ? AND tipo_documento = ?",
        (ra, tipo_documento)).fetchone()
    if existente:
        conexao.close()
        return {**dict(existente), "ja_existia": True}

    protocolo = f"DOC-{conexao.execute('SELECT COUNT(*) FROM documentos_emitidos').fetchone()[0] + 1001}"
    hoje = str(date.today())
    conexao.execute(
        "INSERT INTO documentos_emitidos (protocolo, ra, tipo_documento, "
        "data_emissao) VALUES (?, ?, ?, ?)", (protocolo, ra, tipo_documento, hoje))
    conexao.commit()
    conexao.close()
    return {"protocolo": protocolo, "ra": ra, "tipo_documento": tipo_documento,
            "data_emissao": hoje, "ja_existia": False}


def escalar_para_humano(ra: str, tipo_pedido: str, motivo: str, chave: str) -> dict:
    """ESCRITA, reversível (a fila pode ser reaberta). `chave` é a chave de
    idempotência — mesma técnica de `abrir_chamado` em aula05-agentes: deriva
    do conteúdo (ra:tipo_pedido:motivo), não de um id gerado por tentativa."""
    conexao = dados.conectar()
    existente = conexao.execute(
        "SELECT * FROM casos_pendentes WHERE chave = ?", (chave,)).fetchone()
    if existente:
        conexao.close()
        return {**dict(existente), "ja_existia": True}

    protocolo = f"CASO-{conexao.execute('SELECT COUNT(*) FROM casos_pendentes').fetchone()[0] + 3001}"
    conexao.execute(
        "INSERT INTO casos_pendentes (protocolo, ra, tipo_pedido, motivo, chave) "
        "VALUES (?, ?, ?, ?, ?)", (protocolo, ra, tipo_pedido, motivo, chave))
    conexao.commit()
    conexao.close()
    return {"protocolo": protocolo, "ra": ra, "tipo_pedido": tipo_pedido,
            "motivo": motivo, "prazo": "48h", "ja_existia": False}


FERRAMENTAS = {
    "buscar_aluno": buscar_aluno,
    "consultar_financeiro": consultar_financeiro,
    "emitir_documento": emitir_documento,
    "escalar_para_humano": escalar_para_humano,
}

ESCRITA = {"emitir_documento", "escalar_para_humano"}

# A descrição É PROMPT (aula 03): diz o que faz, quando usar e quando não usar.
DECLARACOES = {
    "buscar_aluno": {
        "type": "function",
        "function": {
            "name": "buscar_aluno",
            "description": ("Consulta cadastro e situação de matrícula de um "
                            "aluno pelo RA. Use sempre antes de decidir "
                            "qualquer coisa sobre o pedido."),
            "parameters": {
                "type": "object",
                "properties": {"ra": {"type": "string",
                                      "description": "registro acadêmico do aluno"}},
                "required": ["ra"], "additionalProperties": False,
            },
        },
    },
    "consultar_financeiro": {
        "type": "function",
        "function": {
            "name": "consultar_financeiro",
            "description": ("Consulta mensalidades em aberto de um aluno pelo "
                            "RA. Use antes de emitir segunda via de histórico, "
                            "e sempre que o aluno alegar que está em dia."),
            "parameters": {
                "type": "object",
                "properties": {"ra": {"type": "string"}},
                "required": ["ra"], "additionalProperties": False,
            },
        },
    },
    "emitir_documento": {
        "type": "function",
        "function": {
            "name": "emitir_documento",
            "description": ("ESCRITA: emite declaracao_matricula ou "
                            "segunda_via_historico. Use só depois de checar, "
                            "com as ferramentas de consulta, que a regra do "
                            "documento está satisfeita. NUNCA use para "
                            "trancamento_matricula."),
            "parameters": {
                "type": "object",
                "properties": {
                    "ra": {"type": "string"},
                    "tipo_documento": {"type": "string",
                                       "enum": sorted(TIPOS_DOCUMENTO_VALIDOS)},
                },
                "required": ["ra", "tipo_documento"], "additionalProperties": False,
            },
        },
    },
    "escalar_para_humano": {
        "type": "function",
        "function": {
            "name": "escalar_para_humano",
            "description": ("ESCRITA: encaminha o caso para a secretaria "
                            "humana decidir. Use para trancamento_matricula "
                            "(sempre), divergência não resolvida, RA não "
                            "encontrado após confirmação, ou pendência "
                            "financeira que bloqueia o documento pedido."),
            "parameters": {
                "type": "object",
                "properties": {
                    "ra": {"type": "string",
                          "description": "vazio se o RA nunca foi identificado"},
                    "tipo_pedido": {"type": "string",
                                   "enum": ["declaracao_matricula",
                                            "segunda_via_historico",
                                            "trancamento_matricula"]},
                    "motivo": {"type": "string"},
                    "chave": {"type": "string",
                             "description": "chave de idempotência: ra:tipo_pedido:motivo"},
                },
                "required": ["ra", "tipo_pedido", "motivo", "chave"],
                "additionalProperties": False,
            },
        },
    },
}


# ============================================================ O LAÇO

def chamar_com_retry(**kwargs):
    """Backoff exponencial — retry só para falha de TRANSPORTE, nunca para
    falha de CONTEÚDO (isso quem corrige é o modelo, com o erro como dado)."""
    for tentativa in range(5):
        try:
            return client.chat.completions.create(**kwargs)
        except (RateLimitError, APIConnectionError):
            time.sleep(2 ** tentativa)
        except APIStatusError as e:
            if e.status_code >= 500:
                time.sleep(2 ** tentativa)
            else:
                raise ErroFatal(f"erro {e.status_code} da API: {e}") from e
    raise ErroFatal("API indisponível após 5 tentativas")


def montar_mensagens(estado: Estado) -> list[dict]:
    return [{"role": "system", "content": SYSTEM}, *estado.historico]


def mensagem_de_tool(passo: Passo, tool_call_id: str) -> dict:
    conteudo = passo.resultado if passo.resultado is not None else {"erro": passo.erro}
    return {"role": "tool", "tool_call_id": tool_call_id, "name": passo.ferramenta,
            "content": json.dumps(conteudo, ensure_ascii=False)}


def executar(chamada, estado: Estado) -> Passo:
    nome = chamada.function.name
    passo = Passo(indice=estado.n_passos, ferramenta=nome, argumentos={})
    try:
        passo.argumentos = json.loads(chamada.function.arguments)
    except json.JSONDecodeError:
        passo.erro = "argumentos não são JSON válido"
        passo.resultado = {"erro": passo.erro}
        return passo

    funcao = FERRAMENTAS.get(nome)
    if funcao is None:
        passo.erro = f"ferramenta desconhecida: {nome}"
        passo.resultado = {"erro": passo.erro, "disponiveis": list(FERRAMENTAS)}
        return passo

    try:
        passo.resultado = funcao(**passo.argumentos)
    except ErroRecuperavel as e:
        passo.erro = e.payload["erro"]
        passo.resultado = e.payload
    except TypeError as e:
        passo.erro = f"argumentos inválidos: {e}"
        passo.resultado = {"erro": passo.erro}
    return passo


def assinatura(passo: Passo) -> tuple:
    return (passo.ferramenta, json.dumps(passo.argumentos, sort_keys=True))


def detectar_laco(estado: Estado, limite: int = 3) -> bool:
    if estado.n_passos < limite:
        return False
    recentes = [assinatura(p) for p in estado.passos[-limite:]]
    return len(set(recentes)) == 1


def conversar(estado: Estado, mensagem_usuario: str, orcamento: Orcamento,
              verboso: bool = True) -> Estado:
    """Processa UM turno do aluno: pode disparar zero ou mais chamadas de
    ferramenta antes do modelo devolver texto. É chamada de novo a cada nova
    mensagem do aluno, reaproveitando o mesmo `estado` (o histórico não é
    reiniciado — é isso que permite o diálogo de várias trocas do §2.2)."""
    estado.historico.append({"role": "user", "content": mensagem_usuario})

    try:
        while True:
            motivo = orcamento.excedido(estado)
            if motivo:
                estado.termino, estado.motivo = Termino.ORCAMENTO, motivo
                return estado

            if detectar_laco(estado):
                estado.termino = Termino.LACO
                estado.motivo = "mesma ferramenta e argumentos 3x seguidas"
                return estado

            resposta = chamar_com_retry(
                model=MODELO, messages=montar_mensagens(estado),
                tools=list(DECLARACOES.values()), temperature=0)
            uso = resposta.usage
            estado.tokens_gastos += uso.total_tokens
            estado.custo_estimado += custo(uso.prompt_tokens, uso.completion_tokens)

            msg = resposta.choices[0].message
            if not msg.tool_calls:
                estado.termino = Termino.RESPONDEU
                estado.motivo = None
                estado.historico.append({"role": "assistant", "content": msg.content})
                if verboso:
                    print(f"   agente: {msg.content}")
                return estado

            estado.historico.append(msg)
            for chamada in msg.tool_calls:
                passo = executar(chamada, estado)
                estado.registrar(passo)
                estado.historico.append(mensagem_de_tool(passo, chamada.id))
                if verboso:
                    marca = "ERRO " if passo.erro else "     "
                    print(f"   {marca}{passo.ferramenta}({passo.argumentos}) -> "
                          f"{json.dumps(passo.resultado, ensure_ascii=False)[:90]}")
    except ErroFatal as e:
        estado.termino, estado.motivo = Termino.ERRO_FATAL, str(e)
        return estado


def salvar_log(estado: Estado, nome_caso: str) -> Path:
    """Serializa mensagens não-JSON-nativas (objetos da SDK) antes de gravar —
    é por isso que o log passa por `default=str`."""
    pasta = Path(__file__).parent.parent / "logs"
    pasta.mkdir(exist_ok=True)
    caminho = pasta / f"{nome_caso}-{estado.execucao_id}.json"
    caminho.write_text(json.dumps(asdict(estado), ensure_ascii=False,
                                  default=str, indent=2), encoding="utf-8")
    return caminho


def resumo(estado: Estado) -> str:
    return (f"TERMINO: {estado.termino.value}"
            f"{' (' + estado.motivo + ')' if estado.motivo else ''} | "
            f"{estado.n_passos} passos | {estado.tokens_gastos} tokens | "
            f"US$ {estado.custo_estimado:.5f}")
