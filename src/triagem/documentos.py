# O DOCUMENTO de verdade (13/11/2026). Até aqui o agente registrava a emissão
# (protocolo em `documentos_emitidos`), mas nada gerava o documento. Este módulo
# monta a página imprimível (o navegador salva como PDF) da declaração de
# matrícula, da segunda via do histórico e da segunda via do boleto.
#
# ACESSO: o protocolo é sequencial (DOC-1002, DOC-1003...) e daria para
# adivinhar o documento de outra pessoa. Por isso o link leva um CÓDIGO DE
# VERIFICAÇÃO aleatório, criado na primeira vez que o link é pedido e conferido
# em tempo constante. Protocolo inexistente e código errado dão a MESMA resposta
# (sem oráculo).
#
# TUDO É FICTÍCIO e o documento diz isso no próprio corpo.

from __future__ import annotations

import hmac
import secrets
from datetime import date, datetime
from html import escape

import dados
from triagem import servicos

TITULOS = {"declaracao_matricula": "Declaração de matrícula",
           "segunda_via_historico": "Segunda via do histórico escolar",
           "segunda_via_boleto": "Segunda via de boleto"}
VALIDADE_DECLARACAO_DIAS = 90  # Regimento, Art. 3º


class DocumentoNaoEncontrado(Exception):
    """Protocolo inexistente OU código errado: a mesma exceção para os dois."""


def codigo_de(protocolo: str) -> str:
    """O código de verificação do documento, criado na primeira vez."""
    conexao = dados.conectar()
    linha = conexao.execute("SELECT codigo FROM codigos_verificacao WHERE protocolo = ?",
                            (protocolo,)).fetchone()
    if linha:
        conexao.close()
        return linha["codigo"]
    codigo = secrets.token_urlsafe(9)
    conexao.execute("INSERT OR IGNORE INTO codigos_verificacao (protocolo, codigo) VALUES (?, ?)",
                    (protocolo, codigo))
    conexao.commit()
    codigo = conexao.execute("SELECT codigo FROM codigos_verificacao WHERE protocolo = ?",
                             (protocolo,)).fetchone()["codigo"]
    conexao.close()
    return codigo


def documentos_do_turno(passos: list[dict]) -> list[dict]:
    """Os documentos que o turno emitiu (ou reemitiu), com o link de cada um.
    Só entra o que uma ferramenta de emissão devolveu sem erro."""
    vistos, saida = set(), []
    for p in passos:
        if (p["ferramenta"] not in ("emitir_documento", "emitir_boleto")
                or p.get("erro") is not None or not p.get("resultado")):
            continue
        protocolo = p["resultado"].get("protocolo")
        if not protocolo or protocolo in vistos:
            continue
        vistos.add(protocolo)
        tipo = p["resultado"].get("tipo_documento", "")
        saida.append({"protocolo": protocolo, "tipo": tipo,
                      "titulo": TITULOS.get(tipo, "Documento"),
                      "url": f"/documentos/{protocolo}?c={codigo_de(protocolo)}"})
    return saida


def _data_br(iso: str) -> str:
    try:
        return datetime.strptime(iso[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        return iso


def _moeda(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _pagina(titulo: str, protocolo: str, codigo: str, corpo: str, aviso: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(titulo)} · {escape(protocolo)}</title>
<style>
  @page {{ size: A4; margin: 18mm; }}
  body {{ font-family: Georgia, 'Times New Roman', serif; color: #1d2433; background: #eceae4; margin: 0; }}
  .folha {{ background: #fff; max-width: 780px; margin: 24px auto; padding: 56px 64px; position: relative; overflow: hidden;
           box-shadow: 0 6px 30px rgba(0,0,0,.12); }}
  .marca {{ position: absolute; top: 42%; left: -10%; width: 120%; text-align: center; transform: rotate(-24deg);
           font: 700 46px Arial, sans-serif; color: rgba(160,30,30,.09); letter-spacing: 4px; pointer-events: none; }}
  header {{ display: flex; justify-content: space-between; align-items: flex-start; border-bottom: 2px solid #17695F;
           padding-bottom: 16px; margin-bottom: 28px; }}
  .inst b {{ display: block; font: 700 18px Arial, sans-serif; color: #17695F; }}
  .inst span {{ font: 13px Arial, sans-serif; color: #5b6676; }}
  .prot {{ text-align: right; font: 12px Arial, sans-serif; color: #5b6676; }}
  .prot b {{ display: block; font-size: 15px; color: #1d2433; }}
  h1 {{ font-size: 24px; text-align: center; letter-spacing: 1px; text-transform: uppercase; margin: 8px 0 28px; }}
  p {{ font-size: 16px; line-height: 1.8; text-align: justify; }}
  table {{ width: 100%; border-collapse: collapse; font: 13.5px Arial, sans-serif; margin: 12px 0 18px; }}
  th, td {{ border-bottom: 1px solid #ddd; padding: 7px 8px; text-align: left; }}
  th {{ background: #f3f1ec; font-size: 12px; text-transform: uppercase; letter-spacing: .5px; color: #5b6676; }}
  td.num {{ text-align: right; }}
  .resumo {{ display: flex; gap: 16px; font: 14px Arial, sans-serif; margin: 6px 0 22px; flex-wrap: wrap; }}
  .resumo div {{ background: #f3f1ec; border-radius: 8px; padding: 10px 14px; }}
  .resumo b {{ display: block; font-size: 18px; color: #17695F; }}
  .linha {{ font: 700 17px 'Courier New', monospace; letter-spacing: 1px; background: #f3f1ec; padding: 14px; border-radius: 8px;
           text-align: center; word-break: break-all; }}
  .campos {{ display: grid; grid-template-columns: 1fr 1fr; gap: 0; border: 1px solid #ccc; font: 14px Arial, sans-serif; margin: 18px 0; }}
  .campos div {{ padding: 10px 12px; border-bottom: 1px solid #ccc; border-right: 1px solid #ccc; }}
  .campos small {{ display: block; color: #5b6676; font-size: 11px; text-transform: uppercase; letter-spacing: .5px; }}
  .aviso {{ margin-top: 32px; padding: 12px 14px; border: 1px dashed #a01e1e; color: #a01e1e; font: 12.5px Arial, sans-serif; border-radius: 6px; }}
  footer {{ margin-top: 36px; font: 12px Arial, sans-serif; color: #5b6676; border-top: 1px solid #ddd; padding-top: 12px; }}
  .acoes {{ text-align: center; margin: 16px; font-family: Arial, sans-serif; }}
  .acoes button {{ background: #17695F; color: #fff; border: 0; border-radius: 10px; padding: 11px 20px; font-size: 15px; cursor: pointer; }}
  @media print {{ body {{ background: #fff; }} .folha {{ box-shadow: none; margin: 0; padding: 0; }} .acoes {{ display: none; }} }}
</style></head>
<body>
<div class="acoes"><button onclick="window.print()">Imprimir ou salvar em PDF</button></div>
<div class="folha">
  <div class="marca">DOCUMENTO FICTÍCIO · DEMONSTRAÇÃO</div>
  <header>
    <div class="inst"><b>Instituição de Ensino (fictícia)</b><span>Secretaria Acadêmica · atendimento automatizado</span></div>
    <div class="prot">Protocolo<b>{escape(protocolo)}</b>Código de verificação: {escape(codigo)}</div>
  </header>
  <h1>{escape(titulo)}</h1>
  {corpo}
  <div class="aviso">{aviso}</div>
  <footer>Emitido pelo agente de triagem da secretaria acadêmica (projeto da disciplina Agentes de IA com LLMs).
  A autenticidade se confere pelo protocolo e pelo código de verificação acima.</footer>
</div>
</body></html>"""


def _declaracao(aluno, doc, protocolo, codigo) -> str:
    emitida = doc["data_emissao"]
    try:
        validade = date.fromordinal(date.fromisoformat(emitida).toordinal() + VALIDADE_DECLARACAO_DIAS)
        validade_txt = validade.strftime("%d/%m/%Y")
    except ValueError:
        validade_txt = f"{VALIDADE_DECLARACAO_DIAS} dias a partir da emissão"
    corpo = (f"<p>Declaramos, para os devidos fins, que <b>{escape(aluno['nome'])}</b>, registro acadêmico "
             f"(RA) nº <b>{escape(aluno['ra'])}</b>, encontra-se regularmente matriculado(a) no curso de "
             f"<b>{escape(aluno['curso'])}</b> desta instituição, com situação de matrícula "
             f"<b>{escape(aluno['situacao_matricula'])}</b>.</p>"
             f"<p>Documento emitido em {_data_br(emitida)}, válido até {validade_txt} (Regimento, Art. 3º).</p>")
    return _pagina(TITULOS["declaracao_matricula"], protocolo, codigo, corpo,
                   "Documento de demonstração gerado com dados fictícios. Não tem validade para nenhum fim.")


def _historico(doc, protocolo, codigo) -> str:
    h = servicos.consultar_historico(doc["ra"])
    def nota(d: dict) -> str:
        return "—" if d["nota"] is None else f"{d['nota']:.1f}".replace(".", ",")
    linhas = "".join(
        f"<tr><td>{escape(d['semestre'])}</td><td>{escape(d['codigo'])}</td><td>{escape(d['nome'])}</td>"
        f"<td class='num'>{d['carga_horaria']} h</td><td class='num'>{nota(d)}</td>"
        f"<td>{escape(d['situacao'])}</td></tr>" for d in h["disciplinas"])
    cr = "—" if h["coeficiente_rendimento"] is None else f"{h['coeficiente_rendimento']:.2f}".replace(".", ",")
    corpo = (f"<p><b>{escape(h['nome'])}</b> · RA {escape(h['ra'])} · {escape(h['curso'])} · "
             f"matrícula {escape(h['situacao_matricula'])}</p>"
             f"<div class='resumo'><div><b>{cr}</b>coeficiente de rendimento</div>"
             f"<div><b>{h['aprovadas']}</b>aprovadas</div><div><b>{h['reprovadas']}</b>reprovadas</div>"
             f"<div><b>{h['cursando']}</b>em andamento</div></div>"
             f"<table><tr><th>Semestre</th><th>Código</th><th>Disciplina</th><th>Carga</th><th>Nota</th>"
             f"<th>Situação</th></tr>{linhas}</table>"
             f"<p>Segunda via emitida em {_data_br(doc['data_emissao'])}, com quitação financeira conferida "
             f"na data do pedido (Regimento, Art. 4º).</p>")
    return _pagina(TITULOS["segunda_via_historico"], protocolo, codigo, corpo,
                   "Documento de demonstração gerado com dados fictícios. Não tem validade para nenhum fim.")


def _boleto(aluno, bol, protocolo, codigo) -> str:
    corpo = (f"<div class='campos'>"
             f"<div><small>Beneficiário</small>Instituição de Ensino (fictícia)</div>"
             f"<div><small>Vencimento</small><b>{_data_br(bol['vencimento'])}</b></div>"
             f"<div><small>Pagador</small>{escape(aluno['nome'])} · RA {escape(aluno['ra'])}</div>"
             f"<div><small>Valor do documento</small><b>{_moeda(bol['valor'])}</b></div>"
             f"<div><small>Referência</small>Mensalidade {escape(bol['competencia'])}</div>"
             f"<div><small>Emitido em</small>{_data_br(bol['emitido_em'])}</div></div>"
             f"<p style='text-align:center;font:13px Arial,sans-serif;color:#5b6676'>Linha digitável (fictícia)</p>"
             f"<div class='linha'>{escape(bol['linha_digitavel'])}</div>"
             f"<p>Segunda via emitida pelo canal de atendimento, com vencimento em 5 dias corridos da "
             f"emissão (Regimento, Art. 11).</p>")
    return _pagina(TITULOS["segunda_via_boleto"], protocolo, codigo, corpo,
                   "SEM VALOR DE PAGAMENTO. Boleto de demonstração, com dados fictícios: não há banco, "
                   "código de barras nem conta associados. Não tente pagá-lo.")


def pagina_do_documento(protocolo: str, codigo: str) -> str:
    """A página do documento, se o código confere; senão DocumentoNaoEncontrado."""
    conexao = dados.conectar()
    esperado = conexao.execute("SELECT codigo FROM codigos_verificacao WHERE protocolo = ?",
                               (protocolo,)).fetchone()
    if esperado is None or not hmac.compare_digest(esperado["codigo"], codigo or ""):
        conexao.close()
        raise DocumentoNaoEncontrado(protocolo)
    if protocolo.startswith("BOL-"):
        bol = conexao.execute("SELECT * FROM boletos_emitidos WHERE protocolo = ?", (protocolo,)).fetchone()
        aluno = bol and conexao.execute("SELECT * FROM alunos WHERE ra = ?", (bol["ra"],)).fetchone()
        conexao.close()
        if not bol or not aluno:
            raise DocumentoNaoEncontrado(protocolo)
        return _boleto(aluno, bol, protocolo, codigo)
    doc = conexao.execute("SELECT * FROM documentos_emitidos WHERE protocolo = ?", (protocolo,)).fetchone()
    aluno = doc and conexao.execute("SELECT * FROM alunos WHERE ra = ?", (doc["ra"],)).fetchone()
    conexao.close()
    if not doc or not aluno:
        raise DocumentoNaoEncontrado(protocolo)
    if doc["tipo_documento"] == "segunda_via_historico":
        return _historico(doc, protocolo, codigo)
    return _declaracao(aluno, doc, protocolo, codigo)
