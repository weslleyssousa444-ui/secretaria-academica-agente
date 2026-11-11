# Reconstrói uma decisão passada SÓ A PARTIR DO TRACE (docs/model-card.md, campo
# Registro e retenção; enunciado da Parte 3, §2.3).
#
#   python -m evals.reconstruir evals/resultados/<rodada>/traces.jsonl --conversa eval-B-r1-dm04
#
# Não consulta o banco, os logs nem o checkpoint: se o trace não bastar para
# explicar por que o agente decidiu o que decidiu, o registro é insuficiente, e
# isso é uma lacuna do campo Registro do model card, não um defeito da ferramenta.

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from evals.metricas import carregar


def _texto(span: dict, nome: str) -> str:
    return next((e["attributes"].get("gen_ai.message.content", "") for e in span["events"] if e["name"] == nome), "(conteúdo desligado)")


def _json(valor) -> str:
    try:
        return json.dumps(json.loads(valor), ensure_ascii=False)
    except (TypeError, ValueError):
        return str(valor)


def reconstruir(spans: list[dict], conversa: str) -> str:
    raizes = sorted((s for s in spans if s["name"].startswith("invoke_agent") and s["parent_id"] is None
                     and s["attributes"].get("gen_ai.conversation.id") == conversa), key=lambda s: s["start_ns"])
    if not raizes:
        return f"nenhum trace da conversa {conversa!r}"
    por_trace = {}
    for s in spans:
        por_trace.setdefault(s["trace_id"], []).append(s)
    linhas = [f"CONVERSA {conversa}   versão do sistema: {raizes[0]['attributes'].get('agente.versao')}", ""]
    for n, raiz in enumerate(raizes, 1):
        a = raiz["attributes"]
        filhos = sorted((s for s in por_trace[raiz["trace_id"]] if s["parent_id"] is not None), key=lambda s: s["start_ns"])
        if a.get("agente.retomada"):
            linhas += [f"RETOMADA DA COORDENAÇÃO (turno {n}, trace {raiz['trace_id'][:8]})",
                       f"  caso:      {a.get('agente.aprovacao.protocolo')}",
                       f"  quem:      {a.get('agente.aprovacao.por')}   pediu: {a.get('agente.aprovacao.pedida')}",
                       f"  decisão:   {a.get('agente.aprovacao.decisao')}   (já decidido antes: {a.get('agente.aprovacao.ja_decidido')}, conflito: {a.get('agente.aprovacao.conflito')})"]
            if a.get("agente.aprovacao.edicao"):
                linhas.append(f"  editou:    {a['agente.aprovacao.edicao']}")
            linhas.append("")
            continue
        duracao = (raiz["end_ns"] - raiz["start_ns"]) / 1e6
        linhas += [f"TURNO {n}   trace {raiz['trace_id'][:8]}   {duracao:.0f} ms   término: {a.get('agente.termino')}"
                   + (f" ({a.get('agente.motivo')})" if a.get("agente.motivo") else ""),
                   f"  aluno:     {_texto(raiz, 'gen_ai.user.message')!r}   (identidade: {'autenticada' if a.get('agente.identidade') else 'sem sessão'})"]
        chats = [s for s in filhos if s["name"].startswith("chat ")]
        if chats:
            entrada = sum(s["attributes"].get("gen_ai.usage.input_tokens", 0) for s in chats)
            saida = sum(s["attributes"].get("gen_ai.usage.output_tokens", 0) for s in chats)
            servidos = {s["attributes"].get("gen_ai.response.model", "?") for s in chats}
            linhas.append(f"  modelo:    {len(chats)} chamada(s), pedido {chats[0]['attributes'].get('gen_ai.request.model')}, "
                          f"servido {', '.join(sorted(servidos))}, {entrada} tokens de entrada e {saida} de saída; modelo aprovado: {a.get('agente.modelo_aprovado')}")
        else:
            linhas.append("  modelo:    nenhuma chamada (turno sem modelo)")
        if list(a.get("agente.contexto_recuperado", [])):
            linhas.append(f"  recuperou: {', '.join(a['agente.contexto_recuperado'])}")
        for i, f in enumerate(s for s in filhos if s["name"].startswith("execute_tool")):
            fa = f["attributes"]
            estado = ("RECUSADA pelo controle: " + fa.get("agente.ferramenta.erro", "")) if fa.get("agente.ferramenta.recusada") \
                else ("ERRO: " + fa["agente.ferramenta.erro"]) if fa.get("agente.ferramenta.erro") else "ok"
            origem = "  [executada PELO CÓDIGO, não pelo modelo]" if fa.get("agente.ferramenta.origem") == "codigo" else ""
            linhas.append(f"  ferramenta {i + 1}: {fa['gen_ai.tool.name']}({_json(fa.get('gen_ai.tool.call.arguments'))}) -> "
                          f"{_json(fa.get('gen_ai.tool.call.result'))}   [{estado}]{origem}")
        linhas += [f"  decisão:   {a.get('agente.decisao')}   suficiente: {a.get('agente.suficiente')}   protocolo: {a.get('agente.protocolo') or '-'}"
                   f"   aguardando humano: {a.get('agente.aguardando_humano')}",
                   f"  resposta:  {_texto(raiz, 'gen_ai.choice')!r}", ""]
    return "\n".join(linhas).rstrip()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Reconstrói uma decisão a partir do trace")
    ap.add_argument("traces", nargs="+", type=Path)
    ap.add_argument("--conversa", required=True, help="o gen_ai.conversation.id (o thread_id)")
    args = ap.parse_args(argv)
    print(reconstruir(carregar(args.traces), args.conversa))
    return 0


if __name__ == "__main__":
    sys.exit(main())
