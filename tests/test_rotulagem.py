# A ficha de rotulagem humana e a medição do juiz (evals/rotulagem.py).
# Dados sintéticos: nenhum rótulo real é preenchido por teste.

from __future__ import annotations

import csv
import json

import pytest

from evals import rotulagem


def rodada_com_casos_distintos(tmp_path, ids, nome="2026-11-11-A-r1"):
    pasta = tmp_path / nome
    pasta.mkdir()
    with (pasta / "execucoes.jsonl").open("w", encoding="utf-8") as f:
        for i in ids:
            f.write(json.dumps({"caso": i, "termino": "respondeu", "respostas": [f"resposta de {i}"],
                                "passos": [{"ferramenta": "buscar_aluno", "argumentos": {"ra": "20231045"},
                                            "resultado": {"nome": "X"}, "erro": None}]}) + "\n")
    return pasta


IDS = ["em01", "em02", "em03", "pe01", "pe02", "tr01", "tr02", "re01"]


def test_a_ficha_nao_traz_o_veredito_do_juiz_nem_nenhum_rotulo(tmp_path):
    saida = tmp_path / "ficha.csv"
    rotulagem.preparar([rodada_com_casos_distintos(tmp_path, IDS)], 5, 7, rotulagem.RAIZ / "evals/dataset/golden_v1.1.0.json", saida)
    linhas = list(csv.DictReader(saida.open(encoding="utf-8")))
    assert len(linhas) == 5 and set(linhas[0]) == set(rotulagem.CAMPOS)
    assert all(l["rotulo_humano"] == "" and l["nota_humana"] == "" for l in linhas)   # nada preenchido por IA
    assert not any("juiz" in c for c in rotulagem.CAMPOS) and "fiel" not in "".join(rotulagem.CAMPOS[:6])


def test_o_sorteio_e_reprodutivel_pela_semente(tmp_path):
    r = rodada_com_casos_distintos(tmp_path, IDS)
    ds = rotulagem.RAIZ / "evals/dataset/golden_v1.1.0.json"
    rotulagem.preparar([r], 4, 7, ds, tmp_path / "a.csv")
    rotulagem.preparar([r], 4, 7, ds, tmp_path / "b.csv")
    assert (tmp_path / "a.csv").read_text(encoding="utf-8") == (tmp_path / "b.csv").read_text(encoding="utf-8")


def ficha_preenchida(tmp_path, rotulos):
    caminho = tmp_path / "ficha.csv"
    with caminho.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rotulagem.CAMPOS)
        w.writeheader()
        for chave, rotulo in rotulos.items():
            w.writerow({"chave": chave, "caso": chave.split(":")[1], "rotulo_humano": rotulo, "nota_humana": "x", "rotulador": "teste"})
    return caminho


def veredictos(tmp_path, fieis):
    caminho = tmp_path / "juiz.jsonl"
    caminho.write_text("\n".join(json.dumps({"chave": k, "fiel": v, "nota": "n"}) for k, v in fieis.items()) + "\n", encoding="utf-8")
    return caminho


def test_a_matriz_a_concordancia_e_o_recall_de_nao_fiel():
    # 4 pares (juiz_fiel, humano_fiel): 2 fiéis certos, 1 não fiel achado, 1 não fiel perdido
    m = rotulagem.matriz([(True, True), (True, True), (False, False), (True, False)])
    assert (m["juiz_fiel_humano_fiel"], m["juiz_fiel_humano_nao"], m["juiz_nao_humano_nao"], m["juiz_nao_humano_fiel"]) == (2, 1, 1, 0)
    assert m["concordancia"] == 0.75 and m["recall_nao_fiel"] == 0.5 and m["precisao_nao_fiel"] == 1.0


def test_medir_aplica_o_limiar_e_escreve_os_desacordos(tmp_path):
    ficha = ficha_preenchida(tmp_path, {"r:a": "fiel", "r:b": "fiel", "r:c": "nao_fiel", "r:d": "nao_fiel"})
    juiz = veredictos(tmp_path, {"r:a": True, "r:b": True, "r:c": False, "r:d": True})   # perde 1 dos 2 não fiéis
    m = rotulagem.medir(ficha, [juiz], tmp_path / "desacordos.csv")
    assert m["concordancia"] == 0.75 and m["recall_nao_fiel"] == 0.5 and m["adotado"] is False
    desacordos = list(csv.reader((tmp_path / "desacordos.csv").open(encoding="utf-8")))
    assert len(desacordos) == 2 and desacordos[1][0] == "r:d"   # cabeçalho + 1 desacordo, para ler e classificar à mão


def test_juiz_perfeito_e_adotado(tmp_path):
    ficha = ficha_preenchida(tmp_path, {"r:a": "fiel", "r:b": "nao_fiel"})
    m = rotulagem.medir(ficha, [veredictos(tmp_path, {"r:a": True, "r:b": False})], tmp_path / "d.csv")
    assert m["adotado"] is True and m["desacordos"] == 0


def test_medir_recusa_ficha_com_linha_sem_rotulo(tmp_path):
    ficha = ficha_preenchida(tmp_path, {"r:a": "fiel", "r:b": ""})
    with pytest.raises(SystemExit) as erro:
        rotulagem.medir(ficha, [veredictos(tmp_path, {"r:a": True, "r:b": True})], tmp_path / "d.csv")
    assert "sem rótulo humano" in str(erro.value)


def test_medir_recusa_rotulo_invalido_e_exige_o_veredito_do_juiz(tmp_path):
    with pytest.raises(SystemExit):
        rotulagem.medir(ficha_preenchida(tmp_path, {"r:a": "talvez"}), [veredictos(tmp_path, {"r:a": True})], tmp_path / "d.csv")
    with pytest.raises(SystemExit) as erro:
        rotulagem.medir(ficha_preenchida(tmp_path, {"r:a": "fiel"}), [veredictos(tmp_path, {})], tmp_path / "d.csv")
    assert "sem veredito do juiz" in str(erro.value)


def test_os_limiares_sao_os_declarados_antes_de_medir():
    assert rotulagem.LIMIARES == {"concordancia": 0.85, "recall_nao_fiel": 0.80}
