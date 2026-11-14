# A tela da coordenação, no terminal (docs/humano.md).
#
#   python src/coordenacao.py listar
#   python src/coordenacao.py decidir CASO-3001 aprovar --por coord-1
#   python src/coordenacao.py decidir CASO-3001 aprovar_editando --por coord-1 --editar semestre_efetivo=2027.1
#   python src/coordenacao.py decidir CASO-3001 rejeitar --por coord-1
#   python src/coordenacao.py expirar            # vence o que passou do prazo
#   python src/coordenacao.py preparar CASO-3001 # parecer do assistente (2º agente, via MCP; usa o modelo)
#
# Retoma o grafo pausado pelo MESMO arquivo de checkpoint que o chat e a API
# usam (`TRIAGEM_CHECKPOINT`). Repetir `decidir` não grava duas vezes.

from __future__ import annotations

import argparse
import json
import sys

import dados
from triagem import humano
from triagem.sistema import Sistema


def main() -> int:
    ap = argparse.ArgumentParser(description="Coordenação: decide os trancamentos que o agente encaminhou")
    sub = ap.add_subparsers(dest="comando", required=True)
    sub.add_parser("listar", help="mostra o que espera a coordenação")
    d = sub.add_parser("decidir", help="decide um caso")
    d.add_argument("protocolo")
    d.add_argument("decisao", choices=["aprovar", "rejeitar", "aprovar_editando"])
    d.add_argument("--por", required=True, help="quem decide")
    d.add_argument("--editar", action="append", default=[], metavar="CAMPO=VALOR",
                   help=f"campo editado ({', '.join(humano.CAMPOS_EDITAVEIS)})")
    sub.add_parser("expirar", help="vence as esperas que passaram do prazo")
    p = sub.add_parser("preparar", help="o assistente da coordenação prepara o parecer de um caso (não decide)")
    p.add_argument("protocolo")
    args = ap.parse_args()

    dados.inicializar()
    if args.comando == "preparar":
        import asyncio
        from assistente_coordenacao import preparar_pelo_servidor
        print(json.dumps(asyncio.run(preparar_pelo_servidor(args.protocolo)), ensure_ascii=False, indent=2))
        return 0
    sistema = Sistema()
    try:
        if args.comando == "listar":
            casos = humano.pendentes()
            print(json.dumps(casos, ensure_ascii=False, indent=2) if casos else "Nada aguardando a coordenação.")
        elif args.comando == "decidir":
            edicao = dict(item.split("=", 1) for item in args.editar)
            try:
                decisao = humano.DecisaoHumana(decisao=args.decisao, por=args.por, edicao=edicao)
                print(json.dumps(sistema.decidir(args.protocolo, decisao), ensure_ascii=False, indent=2))
            except (ValueError, KeyError) as e:
                print(f"recusado: {e}", file=sys.stderr)
                return 2
        else:
            print(json.dumps(sistema.expirar_vencidos(), ensure_ascii=False, indent=2))
    finally:
        sistema.fechar()
    return 0


if __name__ == "__main__":
    sys.exit(main())
