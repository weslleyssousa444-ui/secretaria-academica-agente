# Testes do sistema de triagem em grafo (Parte 2). Offline: o "modelo" é o
# roteiro de conftest.py, que de propósito faz o que um modelo ruim faria —
# esquece de escalar, inventa protocolo, cita artigo que não existe. Cada
# teste prova que o CÓDIGO do grafo barra, sem depender de o modelo acertar.
#
# Protocolos esperados no banco sintético: DOC-1002 (o semeado é DOC-1000, e o
# protocolo é COUNT+1001) e CASO-3001 (a fila começa vazia).

from __future__ import annotations

import json
import sqlite3

import pytest

import agente
from conftest import RAIZ, ModeloRoteirizado, chamada, contar, resposta
from triagem import humano, nos
from triagem.grafo import construir
from triagem.humano import DecisaoHumana
from triagem.sistema import Sistema

PERGUNTAS = {c["id"]: c for c in json.loads(
    (RAIZ / "dados" / "casos_rag.json").read_text(encoding="utf-8"))}


@pytest.fixture
def sistema(banco, tmp_path):
    s = Sistema(checkpoint=tmp_path / "cp.sqlite", memoria_dir=tmp_path / "mem")
    yield s
    s.fechar()


def declaracao_ok(ra="20231045"):
    return [resposta([chamada("buscar_aluno", ra=ra)]),
            resposta([chamada("emitir_documento", ra=ra, tipo_documento="declaracao_matricula")])]


def escalar_trancamento(ra="20229012"):
    return resposta([chamada("escalar_para_humano", ra=ra, tipo_pedido="trancamento_matricula",
                             motivo="trancamento", chave=f"{ra}:trancamento_matricula:trancamento")])


# ------------------------------------------------------------ caminho feliz e contrato

def test_caminho_feliz_emite_e_devolve_o_objeto_validado(sistema, modelo):
    modelo([*declaracao_ok(), resposta(content="Sua declaração foi emitida. Protocolo: DOC-1002.")])
    r = sistema.conversar("t1", "Preciso de uma declaração de matrícula. Meu RA é 20231045.")
    saida = r["saida"]
    assert saida["decisao"] == "emitir_declaracao"
    assert saida["protocolo"] == "DOC-1002"
    assert saida["suficiencia"]["suficiente"] is True
    assert {"tipo": "ferramenta", "referencia": "emitir_documento:DOC-1002"} in saida["fonte"]
    assert saida["aguardando_humano"] is False and r["termino"] == "respondeu"
    assert contar("documentos_emitidos") == 2


def test_saudacao_nao_chama_o_modelo(sistema, modelo):
    falso = modelo([resposta(content="não deveria ser chamado")])
    r = sistema.conversar("t1", "Oi!")
    assert falso.chamadas == 0
    assert r["saida"]["decisao"] == "sem_acao"
    assert "secretaria" in r["saida"]["resultado"]


def test_entrada_vazia_ou_gigante_e_recusada(sistema, modelo):
    falso = modelo([resposta(content="x")])
    with pytest.raises(ValueError):
        sistema.conversar("t1", "   ")
    with pytest.raises(ValueError):
        sistema.conversar("t1", "a" * 2001)
    assert falso.chamadas == 0


def test_pedir_o_ra_e_sem_acao_e_nao_suficiente(sistema, modelo):
    modelo([resposta(content="Para emitir a declaração, preciso do seu RA. Qual é?")])
    r = sistema.conversar("t1", "Preciso de uma declaração de matrícula.")
    assert r["saida"]["decisao"] == "sem_acao"
    assert r["saida"]["suficiencia"]["suficiente"] is False
    assert contar("documentos_emitidos") == 1  # só o semeado


# ------------------------------------------------------------ guardas que o grafo preserva

def test_segunda_via_com_pendencia_nao_emite_mesmo_se_o_modelo_tentar(sistema, modelo):
    """A guarda de negócio da Parte 1 continua valendo dentro do grafo."""
    modelo([resposta([chamada("emitir_documento", ra="20230198", tipo_documento="segunda_via_historico")]),
            resposta(content="Não posso emitir agora: há pendência financeira.")])
    r = sistema.conversar("t1", "Quero a segunda via do histórico. RA 20230198.")
    assert contar("documentos_emitidos") == 1
    assert r["saida"]["decisao"] == "sem_acao"


def test_ferramenta_inventada_nao_executa_nada(sistema, modelo):
    modelo([resposta([chamada("trancar_matricula", ra="20229012")]),
            resposta(content="Não consigo trancar; vou encaminhar.")])
    sistema.conversar("t1", "Quero trancar. RA 20229012.")
    assert contar("casos_pendentes") == 0  # a L02 só age com RA confirmado por buscar_aluno
    estado = sistema.estado("t1")
    assert estado["passos"][0]["erro"].startswith("ferramenta desconhecida")


def test_excecao_dentro_da_ferramenta_nao_derruba_o_turno(sistema, modelo, monkeypatch):
    """ASI08: o banco trava no meio da ferramenta. O turno termina, sem vazar o
    texto da exceção para o modelo nem para o aluno."""
    def quebrada(ra):
        raise sqlite3.OperationalError("database is locked: /dados/academico.db")
    monkeypatch.setitem(nos.FERRAMENTAS, "buscar_aluno", quebrada)
    modelo([resposta([chamada("buscar_aluno", ra="20231045")]),
            resposta(content="Tive um problema para consultar o sistema. Tente de novo.")])
    r = sistema.conversar("t1", "Declaração, RA 20231045.")
    passo = sistema.estado("t1")["passos"][0]
    assert passo["erro"] == "falha interna da ferramenta (OperationalError)"
    assert "locked" not in json.dumps(passo)
    assert r["termino"] == "respondeu"


def test_laco_detectado_termina_com_o_motivo(sistema, modelo):
    modelo([resposta([chamada("buscar_aluno", ra="20231045")])])  # repete para sempre
    r = sistema.conversar("t1", "oi, RA 20231045")
    assert r["termino"] == "laco_detectado"
    assert r["saida"]["suficiencia"]["suficiente"] is False
    assert "Não consegui concluir" in r["saida"]["resultado"]


def test_orcamento_de_passos_interrompe(sistema, modelo):
    modelo([resposta([chamada("buscar_aluno", ra=f"2023{i:04d}")]) for i in range(20)])
    r = sistema.conversar("t1", "consulte vários RAs")
    assert r["termino"] == "orcamento_esgotado"


def test_estourar_o_limite_de_passos_do_grafo_nao_derruba_nem_confunde_com_pausa(sistema, modelo, monkeypatch):
    """`recursion_limit` é um parâmetro com padrão do framework (docs/grafo.md
    §5.3). Estourado, o aluno recebe resposta, e a conversa NÃO é confundida
    com uma pausa para a coordenação no turno seguinte."""
    from triagem import sistema as modulo
    from triagem.sistema import ConversaEncerrada
    monkeypatch.setattr(modulo, "RECURSION_LIMIT", 5)
    modelo([resposta([chamada("buscar_aluno", ra=f"2023{i:04d}")]) for i in range(20)])
    r = sistema.conversar("t1", "consulte vários RAs")
    assert r["termino"] == "erro_fatal" and r["aguardando_humano"] is False
    assert "recursion_limit" in r["motivo"] and r["saida"]["resultado"]
    with pytest.raises(ConversaEncerrada):
        sistema.conversar("t1", "e agora?")


def test_teto_de_tempo_por_turno_interrompe_antes_da_proxima_chamada(banco, tmp_path, modelo):
    """O provedor lento: depois da primeira chamada o turno já passou do teto, e
    o agente NÃO faz a segunda (o que o Orcamento da Parte 1 nunca conferia)."""
    import time as relogio
    s = Sistema(checkpoint=tmp_path / "cp.sqlite", memoria_dir=tmp_path / "mem")
    s.app = construir(nos.Nos(s.memoria, max_segundos=0.05)).compile(checkpointer=s.app.checkpointer)
    falso = modelo([resposta([chamada("buscar_aluno", ra="20231045")]), resposta(content="nunca chega")])
    original = falso._create

    def lento(**kwargs):
        relogio.sleep(0.1)  # a chamada demora mais que o teto
        return original(**kwargs)

    falso.chat.completions.create = lento
    try:
        r = s.conversar("t1", "Declaração, RA 20231045.")
    finally:
        s.fechar()
    assert r["termino"] == "orcamento_esgotado" and r["motivo"].startswith("tempo")
    assert falso.chamadas == 1


def test_erro_fatal_do_provedor_termina_sem_escrita(sistema, modelo):
    import httpx
    import openai
    req = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    modelo([openai.BadRequestError("ruim", response=httpx.Response(400, request=req), body=None)])
    r = sistema.conversar("t1", "Declaração, RA 20231045.")
    assert r["termino"] == "erro_fatal"
    assert contar("documentos_emitidos") == 1


# ------------------------------------------------------------ L02 dentro do grafo

def test_trancamento_escalado_pelo_codigo_e_o_grafo_pausa(sistema, modelo):
    """O modelo confirma o RA e responde 'registrado' sem escalar. O nó
    `garantir_trancamento` abre o caso; o agente redige com o protocolo real;
    o grafo pausa esperando a coordenação."""
    modelo([resposta([chamada("buscar_aluno", ra="20229012")]),
            resposta(content="Seu trancamento foi registrado."),
            resposta(content="Encaminhei seu pedido. Protocolo: CASO-3001. Prazo: 48h.")])
    r = sistema.conversar("t1", "Quero trancar minha matrícula. Meu RA é 20229012.")
    assert contar("casos_pendentes") == 1
    assert r["saida"]["decisao"] == "escalar_trancamento"
    assert r["saida"]["protocolo"] == "CASO-3001"
    assert r["aguardando_humano"] is True
    assert "garantir_trancamento:escalou_pelo_codigo" in sistema.estado("t1")["eventos"]


def test_modelo_que_escala_sozinho_nao_duplica_o_caso(sistema, modelo):
    modelo([resposta([chamada("buscar_aluno", ra="20229012")]), escalar_trancamento(),
            resposta(content="Encaminhei. Protocolo: CASO-3001. Prazo: 48h.")])
    sistema.conversar("t1", "Quero trancar. RA 20229012.")
    assert contar("casos_pendentes") == 1


# ------------------------------------------------------------ human-in-the-loop

def conversa_pausada(sistema, modelo, thread="t1"):
    falso = modelo([resposta([chamada("buscar_aluno", ra="20229012")]), escalar_trancamento(),
            resposta(content="Encaminhei seu pedido. Protocolo: CASO-3001. Prazo: 48h.")])
    sistema.conversar(thread, "Quero trancar minha matrícula. Meu RA é 20229012.")
    return falso


def test_pausa_grava_a_espera_e_mostra_a_tela(sistema, modelo):
    conversa_pausada(sistema, modelo)
    pausa = sistema.app.get_state(sistema._config("t1"))
    assert pausa.next == ("aprovacao_coordenacao",)
    tela = pausa.tasks[0].interrupts[0].value
    assert tela["protocolo"] == "CASO-3001" and tela["aluno"]["nome"] == "Bruno Castro"
    assert tela["respostas_aceitas"] == ["aprovar", "rejeitar", "aprovar_editando"]
    assert "não altera a matrícula" in tela["consequencia"]
    espera = humano.registrar_espera("t1", "CASO-3001", "20229012")
    assert espera["estado"] == "aguardando" and espera["prazo_ate"] > espera["criado_em"]


def test_aprovar_grava_a_decisao_no_caso(sistema, modelo):
    conversa_pausada(sistema, modelo)
    r = sistema.decidir("CASO-3001", DecisaoHumana(decisao="aprovar", por="coord-1"))
    assert r == {"protocolo": "CASO-3001", "ja_decidido": False, "decisao": "aprovado", "conflito": False}
    con = sqlite3.connect(humano.dados.CAMINHO_DB)
    assert con.execute("SELECT status FROM casos_pendentes").fetchone()[0] == "aprovado"
    assert sistema.app.get_state(sistema._config("t1")).next == ()  # o grafo terminou


def test_aprovar_editando_guarda_o_que_a_pessoa_corrigiu(sistema, modelo):
    conversa_pausada(sistema, modelo)
    sistema.decidir("CASO-3001", DecisaoHumana(
        decisao="aprovar_editando", por="coord-1", edicao={"semestre_efetivo": "2027.1"}))
    assert json.loads(humano.decisao_gravada("CASO-3001")["edicao"]) == {"semestre_efetivo": "2027.1"}


def test_rejeitar_grava_rejeitado(sistema, modelo):
    conversa_pausada(sistema, modelo)
    assert sistema.decidir("CASO-3001", DecisaoHumana(decisao="rejeitar", por="coord-1"))["decisao"] == "rejeitado"


def test_aprovar_duas_vezes_nao_grava_duas_vezes(sistema, modelo):
    """§8.5: a aprovação chega repetida e a ação não se repete."""
    conversa_pausada(sistema, modelo)
    primeira = sistema.decidir("CASO-3001", DecisaoHumana(decisao="aprovar", por="coord-1"))
    segunda = sistema.decidir("CASO-3001", DecisaoHumana(decisao="aprovar", por="coord-2"))
    assert primeira["ja_decidido"] is False and segunda["ja_decidido"] is True
    assert contar("decisoes_humanas") == 1
    assert humano.decisao_gravada("CASO-3001")["decidido_por"] == "coord-1"  # a primeira vale


def test_decisao_conflitante_nao_sobrescreve(sistema, modelo):
    conversa_pausada(sistema, modelo)
    sistema.decidir("CASO-3001", DecisaoHumana(decisao="aprovar", por="coord-1"))
    r = sistema.decidir("CASO-3001", DecisaoHumana(decisao="rejeitar", por="coord-2"))
    assert r["conflito"] is True and r["decisao"] == "aprovado"


def test_registrar_decisao_repetido_devolve_a_gravada(banco):
    """O nó roda de novo na retomada; a escrita sozinha não pode duplicar."""
    d = DecisaoHumana(decisao="aprovar", por="coord-1")
    primeira = humano.registrar_decisao("CASO-9", d)
    segunda = humano.registrar_decisao("CASO-9", d)
    assert primeira["ja_existia"] is False and segunda["ja_existia"] is True
    assert contar("decisoes_humanas") == 1


def test_mensagem_durante_a_espera_nao_chama_o_modelo_nem_abre_outro_caso(sistema, modelo):
    falso = conversa_pausada(sistema, modelo)
    chamadas = falso.chamadas
    r = sistema.conversar("t1", "quero trancar de novo, por favor")
    assert falso.chamadas == chamadas
    assert "CASO-3001" in r["saida"]["resultado"] and r["aguardando_humano"] is True
    assert contar("casos_pendentes") == 1


def test_ninguem_responde_o_caso_vence_e_volta_a_fila(sistema, modelo):
    from datetime import timedelta
    conversa_pausada(sistema, modelo)
    assert sistema.expirar_vencidos() == []  # dentro do prazo, nada acontece
    depois = humano.agora_utc() + timedelta(hours=humano.PRAZO_HORAS + 1)
    r = sistema.expirar_vencidos(depois)
    assert r[0]["decisao"] == "vencido"
    con = sqlite3.connect(humano.dados.CAMINHO_DB)
    assert con.execute("SELECT status FROM casos_pendentes").fetchone()[0] == "vencido"


def test_decisao_fora_do_contrato_e_recusada_antes_de_retomar():
    with pytest.raises(ValueError):
        DecisaoHumana(decisao="aprovar", por="x", edicao={"semestre_efetivo": "2027.1"})
    with pytest.raises(ValueError):
        DecisaoHumana(decisao="aprovar_editando", por="x")
    with pytest.raises(ValueError):
        DecisaoHumana(decisao="aprovar_editando", por="x", edicao={"matricula": "ativa"})


def test_pausa_sobrevive_a_reiniciar_o_processo(banco, tmp_path, modelo):
    """O checkpoint é arquivo: outro `Sistema`, no mesmo arquivo, retoma."""
    cp, mem = tmp_path / "cp.sqlite", tmp_path / "mem"
    primeiro = Sistema(checkpoint=cp, memoria_dir=mem)
    conversa_pausada(primeiro, modelo)
    primeiro.fechar()
    segundo = Sistema(checkpoint=cp, memoria_dir=mem)
    try:
        r = segundo.decidir("CASO-3001", DecisaoHumana(decisao="aprovar", por="coord-1"))
        assert r["decisao"] == "aprovado"
    finally:
        segundo.fechar()


# ------------------------------------------------------------ validação da resposta

def test_protocolo_inventado_e_devolvido_ao_agente_uma_vez(sistema, modelo):
    falso = modelo([*declaracao_ok(),
            resposta(content="Sua declaração foi emitida. Protocolo: DOC-9999."),
            resposta(content="Sua declaração foi emitida. Protocolo: DOC-1002.")])
    r = sistema.conversar("t1", "Declaração, RA 20231045.")
    assert r["saida"]["resultado"].endswith("DOC-1002.")
    assert sistema.estado("t1")["correcoes"] == 1
    assert falso.chamadas == 4


def test_reprovou_duas_vezes_a_resposta_sai_do_molde_sem_o_modelo(sistema, modelo):
    modelo([*declaracao_ok(),
            resposta(content="Emitida. Protocolo: DOC-9999."),
            resposta(content="Emitida de novo. Protocolo: DOC-8888.")])
    r = sistema.conversar("t1", "Declaração, RA 20231045.")
    assert "DOC-1002" in r["saida"]["resultado"] and "DOC-9999" not in r["saida"]["resultado"]
    assert "validar:contingencia" in sistema.estado("t1")["eventos"]


def test_prazo_prometido_diferente_de_48h_e_reprovado(sistema, modelo):
    modelo([resposta([chamada("buscar_aluno", ra="20229012")]), escalar_trancamento(),
            resposta(content="Encaminhei. Protocolo: CASO-3001. Responderemos em 5 dias."),
            resposta(content="Encaminhei. Protocolo: CASO-3001. Prazo: 48h.")])
    r = sistema.conversar("t1", "Quero trancar. RA 20229012.")
    assert "48h" in r["saida"]["resultado"] and "5 dias" not in r["saida"]["resultado"]


# ------------------------------------------------------------ RAG como ferramenta

def duvida(caso: str, resposta_final: str):
    pergunta = PERGUNTAS[caso]["pergunta"]
    return [resposta([chamada("consultar_regimento", pergunta=pergunta)]),
            resposta(content=resposta_final)], pergunta


def test_duvida_do_regimento_cita_o_artigo_e_a_fonte_e_conferivel(sistema, modelo):
    roteiro, pergunta = duvida("r03", "Vale o que o Regimento diz no Art. 6º, conforme a consulta.\n[SUFICIENTE: sim]")
    modelo(roteiro)
    r = sistema.conversar("t1", pergunta)
    assert r["saida"]["decisao"] == "responder_regimento"
    assert {"tipo": "regimento", "referencia": "Art. 6º"} in r["saida"]["fonte"]
    assert r["saida"]["suficiencia"]["suficiente"] is True
    assert "[SUFICIENTE" not in r["saida"]["resultado"]  # a marcação não vai ao aluno
    assert contar("casos_pendentes") == 0


def test_artigo_de_ruido_com_recusa_declarada_e_sem_acao(sistema, modelo):
    """O defeito que o modelo real expôs (caso 5): a busca textual devolve
    artigo para uma pergunta que o Regimento NÃO responde, e o modelo o cita
    para explicar isso. Sem a declaração, o contrato marcaria 'suficiente'."""
    roteiro, pergunta = duvida(
        "s01", "O Regimento não trata de custo; o Art. 4º só fala da quitação. "
               "Posso encaminhar à secretaria.\n[SUFICIENTE: não]")
    modelo(roteiro)
    r = sistema.conversar("t1", pergunta)
    assert r["saida"]["decisao"] == "sem_acao"
    assert r["saida"]["suficiencia"] == {
        "suficiente": False, "motivo": "o agente declarou que o Regimento não responde à pergunta"}
    assert r["saida"]["fonte"] == [] and "[SUFICIENTE" not in r["saida"]["resultado"]


def test_marcacao_no_meio_do_texto_e_aceita_e_removida():
    """O modelo real, sem uma frase da regra 7, escreveu a marcação e continuou
    o texto depois dela. A posição não importa; a marcação sai do texto."""
    from triagem.validacao import separar_suficiencia
    texto, declarada = separar_suficiencia(
        "O Regimento não prevê isso (Art. 10).\n\n[SUFICIENTE: não]\n\nPosso encaminhar o caso.")
    assert declarada is False and "[SUFICIENTE" not in texto
    assert texto == "O Regimento não prevê isso (Art. 10).\n\nPosso encaminhar o caso."
    assert separar_suficiencia("sem marcação")[1] is None
    assert separar_suficiencia("a [SUFICIENTE: sim] depois [SUFICIENTE: não]")[1] is False  # vale a última


def test_contingencia_de_duvida_do_regimento_nao_pede_o_ra():
    from triagem.validacao import resposta_de_contingencia
    passos = [{"ferramenta": "consultar_regimento", "erro": None, "argumentos": {},
               "resultado": {"trechos": [{"id": "Art. 4º", "texto": "x"}], "total": 1}}]
    assert "RA" not in resposta_de_contingencia(passos)
    assert "dúvida" in resposta_de_contingencia(passos)


def test_resposta_do_regimento_sem_a_marcacao_volta_ao_agente_uma_vez(sistema, modelo):
    roteiro, pergunta = duvida("r03", "Vale o Art. 6º.")
    modelo([*roteiro, resposta(content="Vale o Art. 6º.\n[SUFICIENTE: sim]")])
    r = sistema.conversar("t1", pergunta)
    assert sistema.estado("t1")["correcoes"] == 1
    assert r["saida"]["suficiencia"]["suficiente"] is True


def test_artigo_citado_que_a_ferramenta_nao_devolveu_e_reprovado(sistema, modelo):
    roteiro, pergunta = duvida("r03", "Segundo o Art. 12, o prazo é longo.")
    modelo([*roteiro, resposta(content="Segundo o Art. 6º, vale a regra consultada.\n[SUFICIENTE: sim]")])
    r = sistema.conversar("t1", pergunta)
    assert "Art. 12" not in r["saida"]["resultado"] and sistema.estado("t1")["correcoes"] == 1


def test_pergunta_fora_do_corpus_e_recusa_com_suficiencia_falsa(sistema, modelo):
    roteiro, pergunta = duvida("x01", "O Regimento não trata disso. Posso encaminhar ao atendimento.")
    modelo(roteiro)
    r = sistema.conversar("t1", pergunta)
    assert r["saida"]["decisao"] == "sem_acao"
    assert r["saida"]["suficiencia"]["suficiente"] is False
    assert r["saida"]["fonte"] == []


# ------------------------------------------------------------ o contrato

def test_resultado_vazio_nao_e_saida_valida():
    from pydantic import ValidationError
    from triagem.saida import SaidaTriagem, Suficiencia
    with pytest.raises(ValidationError):
        SaidaTriagem(resultado="", decisao="sem_acao", fonte=[],
                     suficiencia=Suficiencia(suficiente=False, motivo="x"), termino="respondeu")
    with pytest.raises(ValidationError):
        SaidaTriagem(resultado="ok", decisao="inventada", fonte=[],
                     suficiencia=Suficiencia(suficiente=False, motivo="x"), termino="respondeu")


# ------------------------------------------------------------ a janela

def test_janela_omite_retorno_antigo_e_preserva_o_resto():
    from triagem import janela
    msgs = [{"role": "user", "content": "oi"}]
    for i in range(6):
        msgs += [{"role": "assistant", "content": None, "tool_calls": [{"id": f"c{i}"}]},
                 {"role": "tool", "tool_call_id": f"c{i}", "name": "buscar_aluno",
                  "content": json.dumps({"x": "y" * 400})}]
    msgs.append({"role": "user", "content": "e agora?"})
    novas, omitidos = janela.compactar(msgs, limite=300, manter_ultimas=4)
    assert omitidos > 0
    assert novas[-1]["content"] == "e agora?"                       # a última do aluno nunca sai
    assert msgs[2]["content"] != janela.MARCADOR                    # a conversa original não é alterada
    assert [m["role"] for m in novas] == [m["role"] for m in msgs]  # a estrutura continua válida
    assert all(m["content"] != janela.MARCADOR for m in novas[-4:]) # os mais recentes ficam


# ------------------------------------------------------------ a autoridade do sistema em grafo (docs/model-card.md, campo 3)

def test_o_sistema_tem_exatamente_sete_ferramentas_e_nenhuma_de_trancamento():
    esperadas = {"buscar_aluno", "consultar_financeiro", "consultar_regimento", "emitir_documento",
                 "escalar_para_humano", "consultar_historico", "emitir_boleto"}
    assert set(nos.FERRAMENTAS) == esperadas
    assert {d["function"]["name"] for d in nos.DECLARACOES} == esperadas   # o que o modelo VÊ = o que o código executa
    assert agente.ESCRITA == {"emitir_documento", "escalar_para_humano"}   # o laço da Parte 1 não mudou
    assert nos.ESCRITA == {"emitir_documento", "escalar_para_humano", "emitir_boleto"}   # as três escritas do grafo
    assert set(nos.FERRAMENTAS) - {"consultar_regimento"} <= nos.FERRAMENTAS_COM_RA  # toda ferramenta de aluno passa pela ASI03


def test_as_ferramentas_do_agente_nao_alteram_nem_apagam_nada():
    """A3: o agente só insere. O UPDATE da decisão da coordenação existe (humano.py), mas
    fica num nó que só roda DEPOIS do `interrupt`, e nenhuma ferramenta do modelo chega a ele."""
    import inspect
    from triagem import regimento, servicos
    for modulo in (agente, regimento, servicos):
        fonte = inspect.getsource(modulo).upper()
        assert "UPDATE " not in fonte and "DELETE " not in fonte and "DROP " not in fonte, modulo.__name__
    fonte_das_ferramentas = "".join(inspect.getsource(f) for f in nos.FERRAMENTAS.values())
    for so_da_coordenacao in ("registrar_decisao", "decisoes_humanas", "aprovacoes", "DecisaoHumana"):
        assert so_da_coordenacao not in fonte_das_ferramentas, so_da_coordenacao
    # topologia: `registrar_decisao` só é alcançável a partir de `aprovacao_coordenacao`
    arestas = nos_do_grafo().get_graph().edges
    origens = {e.source for e in arestas if e.target == "registrar_decisao"}
    assert origens == {"aprovacao_coordenacao"}


def nos_do_grafo():
    from triagem.grafo import GRAFO
    return GRAFO.compile()
