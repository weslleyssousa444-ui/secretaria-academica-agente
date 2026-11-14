# Guarda do trace e dos registros (L26): 90 dias, leitura restrita, remoção por titular.

from __future__ import annotations

import json
import os
import stat
import time

from triagem import retencao, telemetria

DIA_NS = 86_400 * 10**9


def _span(trace_id, dias_atras, ra="20231045"):
    return json.dumps({"trace_id": trace_id, "start_ns": time.time_ns() - dias_atras * DIA_NS,
                       "attributes": {"gen_ai.tool.call.arguments": json.dumps({"ra": ra})}})


def test_prazo_padrao_e_90_dias(monkeypatch):
    monkeypatch.delenv("TRIAGEM_RETENCAO_DIAS", raising=False)
    assert retencao.prazo_dias() == 90


def test_span_com_mais_de_90_dias_sai_e_o_recente_fica(tmp_path):
    arq = tmp_path / "traces.jsonl"
    arq.write_text("\n".join([_span("a", 120), _span("b", 10), "lixo sem data"]) + "\n", encoding="utf-8")
    assert retencao.expurgar_trace(arq) == 2
    ficou = [json.loads(l)["trace_id"] for l in arq.read_text().splitlines()]
    assert ficou == ["b"]


def test_trace_fica_legivel_so_pelo_dono(tmp_path):
    telemetria.ExportadorJsonl(tmp_path / "t" / "traces.jsonl")
    modo = stat.S_IMODE(os.stat(tmp_path / "t" / "traces.jsonl").st_mode)
    assert modo == 0o600


def test_remocao_por_titular_apaga_a_conversa_inteira(tmp_path):
    arq = tmp_path / "traces.jsonl"
    linhas = [_span("conv1", 1, ra="20230198"),
              json.dumps({"trace_id": "conv1", "start_ns": time.time_ns(), "attributes": {}}),
              _span("conv2", 1, ra="20231045")]
    arq.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    assert retencao.remover_titular_do_trace(arq, "20230198") == 2
    assert "20230198" not in arq.read_text() and "conv1" not in arq.read_text()


def test_registro_antigo_da_api_sai(tmp_path):
    velho, novo = tmp_path / "api-1.json", tmp_path / "api-2.json"
    velho.write_text("{}"); novo.write_text("{}")
    antigo = time.time() - 100 * 86_400
    os.utime(velho, (antigo, antigo))
    assert retencao.expurgar_registros(tmp_path) == 1
    assert not velho.exists() and novo.exists()


def test_a_api_aplica_a_guarda_ao_subir(banco, tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    import api
    pasta = tmp_path / "tr"; pasta.mkdir()
    (pasta / "traces.jsonl").write_text(_span("velho", 200) + "\n", encoding="utf-8")
    monkeypatch.setenv("TRIAGEM_TRACES_DIR", str(pasta))
    with TestClient(api.app):
        pass
    assert (pasta / "traces.jsonl").read_text() == ""


def test_remover_titular_da_memoria_tambem_limpa_o_trace(tmp_path):
    from triagem.memoria import Memoria
    arq = tmp_path / "traces.jsonl"
    arq.write_text(_span("c1", 1, ra="20230198") + "\n" + _span("c2", 1, ra="20231045") + "\n", encoding="utf-8")
    rel = Memoria(tmp_path / "mem").remover_titular("20230198", trace=arq)
    assert rel["spans_do_trace"] == 1 and "20230198" not in arq.read_text()
