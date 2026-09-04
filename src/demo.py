# Roda os 4 casos de demonstração exigidos pelo item 4.5 da entrega, e
# grava o log de cada execução em logs/ (item requerido: "o log das quatro
# execuções vai no repositório").
#
# Uso:
#   python src/demo.py
#
# Exige OPENAI_API_KEY configurada no .env (ver .env.example) — sem chave,
# a chamada à API falha e nada é gravado.

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import dados
from agente import Estado, Orcamento, conversar, salvar_log, resumo

CAMINHO_CASOS = Path(__file__).parent.parent / "dados" / "casos_demo.json"


def main() -> None:
    dados.inicializar()
    casos = json.loads(CAMINHO_CASOS.read_text(encoding="utf-8"))

    for caso in casos:
        nome, descricao, mensagens = caso["id"], caso["descricao"], caso["mensagens"]
        print(f"\n{'=' * 70}\n{nome}: {descricao}\n{'=' * 70}")
        estado = Estado(caso=nome)
        orcamento = Orcamento()
        for mensagem in mensagens:
            print(f"\naluno: {mensagem}")
            estado = conversar(estado, mensagem, orcamento)
            if estado.termino is not None and estado.termino.value != "respondeu":
                break  # orçamento estourado, laço detectado ou erro fatal

        caminho = salvar_log(estado, nome)
        print(f"\n{resumo(estado)}")
        print(f"log salvo em {caminho}")


if __name__ == "__main__":
    main()
