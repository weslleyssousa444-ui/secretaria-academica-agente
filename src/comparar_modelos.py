# A verificação mínima do item 3.3 de docs/modelos.md: os mesmos 5 casos do
# domínio, rodados nos três modelos candidatos, mesmo prompt. Não é
# estatística — é "olhar a saída dos três antes de escolher".
#
# Uso:
#   python src/comparar_modelos.py
#
# Exige OPENAI_API_KEY configurada no .env. Grava logs/comparar_modelos.csv
# e imprime a tabela que deve ser colada em docs/modelos.md §3.3.

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import agente
import dados
from agente import Estado, Orcamento, conversar
from verificador import classificar_decisao

MODELOS = ["llama-3.1-8b-instant", "llama-3.3-70b-versatile", "openai/gpt-oss-20b"]

# Os mesmos 5 casos listados em docs/modelos.md §3.3.
CASOS = [
    {"id": "1-simples", "esperada": "emitir_declaracao",
     "mensagens": ["Preciso de uma declaração de matrícula. Meu RA é 20231045."]},
    {"id": "2-divergencia", "esperada": "escalar_divergencia",
     "mensagens": ["Já paguei tudo, quero a segunda via do meu histórico. "
                   "Meu RA é 20230198.",
                   "Não tenho o comprovante agora, paguei ontem no banco."]},
    {"id": "3-ra-inexistente", "esperada": "escalar_ra_nao_encontrado",
     "mensagens": ["Preciso de uma declaração de matrícula. Meu RA é 20240000.",
                   "Tenho certeza, é esse mesmo: 20240000."]},
    {"id": "4-trancamento", "esperada": "escalar_trancamento",
     "mensagens": ["Quero trancar minha matrícula esse semestre. "
                   "Meu RA é 20229012."]},
    {"id": "5-segunda-via-ok", "esperada": "emitir_segunda_via",
     "mensagens": ["Preciso da segunda via do meu histórico escolar. "
                   "Meu RA é 20231045."]},
]


def main() -> None:
    dados.inicializar()
    linhas = []

    for modelo in MODELOS:
        agente.MODELO = modelo
        print(f"\n=== {modelo} ===")
        for caso in CASOS:
            estado = Estado(caso=f"{modelo}:{caso['id']}")
            orcamento = Orcamento()
            for mensagem in caso["mensagens"]:
                estado = conversar(estado, mensagem, orcamento, verboso=False)
                if estado.termino is not None and estado.termino.value != "respondeu":
                    break

            obtida = classificar_decisao(estado)
            acertou = obtida == caso["esperada"]
            print(f"  {caso['id']:<18} esperado={caso['esperada']:<26} "
                  f"obtido={obtida}  {'OK' if acertou else 'ERRO'}  "
                  f"({estado.tokens_gastos} tok, US$ {estado.custo_estimado:.5f})")
            linhas.append({
                "modelo": modelo, "caso": caso["id"], "esperado": caso["esperada"],
                "obtido": obtida, "acertou": acertou,
                "tokens": estado.tokens_gastos,
                "custo_usd": round(estado.custo_estimado, 6),
            })

    caminho = Path(__file__).parent.parent / "logs" / "comparar_modelos.csv"
    caminho.parent.mkdir(exist_ok=True)
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=list(linhas[0].keys()))
        escritor.writeheader()
        escritor.writerows(linhas)
    print(f"\nCSV salvo em {caminho} — cole os resultados na tabela de "
          f"docs/modelos.md §3.3.")


if __name__ == "__main__":
    main()
