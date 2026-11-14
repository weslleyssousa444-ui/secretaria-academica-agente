# Guarda do trace e dos registros da API (L26). Decisão de 13/11/2026, tomada
# por Weslley Soares de Sousa pelo grupo: o trace e os registros da API ficam
# 90 dias e depois são apagados; o arquivo do trace só é legível pelo usuário
# do processo; o titular pode pedir a remoção das conversas em que aparece.
#
# Como a memória (docs/memoria.md §4), a varredura roda AO SUBIR O PROCESSO
# (api.py, ciclo de vida): não há agendador. `TRIAGEM_RETENCAO_DIAS` muda o prazo.

from __future__ import annotations

import json
import os
import time
from pathlib import Path

PRAZO_DIAS_PADRAO = 90


def prazo_dias() -> int:
    try:
        return max(1, int(os.environ.get("TRIAGEM_RETENCAO_DIAS", PRAZO_DIAS_PADRAO)))
    except ValueError:
        return PRAZO_DIAS_PADRAO


def _reescrever(caminho: Path, manter) -> int:
    """Reescreve o JSONL só com as linhas que `manter` aceita. Devolve quantas saíram."""
    if not caminho.exists():
        return 0
    linhas = caminho.read_text(encoding="utf-8").splitlines()
    ficam = [l for l in linhas if l.strip() and manter(l)]
    temporario = caminho.with_suffix(caminho.suffix + ".tmp")
    temporario.write_text("".join(l + "\n" for l in ficam), encoding="utf-8")
    os.chmod(temporario, 0o600)
    os.replace(temporario, caminho)
    return len([l for l in linhas if l.strip()]) - len(ficam)


def expurgar_trace(caminho: Path, dias: int | None = None, agora_ns: int | None = None) -> int:
    """Apaga os spans que começaram há mais de `dias`. Linha ilegível sai também:
    sem data, não dá para provar que está dentro do prazo."""
    limite = (agora_ns or time.time_ns()) - (dias or prazo_dias()) * 86_400 * 10**9

    def manter(linha: str) -> bool:
        try:
            return int(json.loads(linha)["start_ns"]) >= limite
        except (ValueError, KeyError, TypeError):
            return False
    return _reescrever(Path(caminho), manter)


def remover_titular_do_trace(caminho: Path, ra: str) -> int:
    """Remove as CONVERSAS inteiras (todos os spans do mesmo trace_id) em que o RA aparece."""
    caminho = Path(caminho)
    if not caminho.exists():
        return 0
    com_ra = set()
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        if ra in linha:
            try:
                com_ra.add(json.loads(linha)["trace_id"])
            except (ValueError, KeyError):
                pass

    def manter(linha: str) -> bool:
        if ra in linha:
            return False
        try:
            return json.loads(linha)["trace_id"] not in com_ra
        except (ValueError, KeyError):
            return True
    return _reescrever(caminho, manter)


def expurgar_registros(pasta: Path, dias: int | None = None, agora: float | None = None) -> int:
    """Apaga os registros da API (`api-*.json`) modificados há mais de `dias`."""
    pasta = Path(pasta)
    if not pasta.exists():
        return 0
    limite = (agora or time.time()) - (dias or prazo_dias()) * 86_400
    apagados = 0
    for arquivo in pasta.glob("api-*.json"):
        if arquivo.stat().st_mtime < limite:
            arquivo.unlink()
            apagados += 1
    return apagados


def aplicar_ao_subir() -> dict:
    """O que o processo da API roda ao subir: as duas varreduras, nos destinos configurados."""
    relatorio = {"prazo_dias": prazo_dias(), "spans_apagados": 0, "registros_apagados": 0}
    if os.environ.get("TRIAGEM_TRACES_DIR"):
        relatorio["spans_apagados"] = expurgar_trace(Path(os.environ["TRIAGEM_TRACES_DIR"]) / "traces.jsonl")
    if os.environ.get("LOGS_DIR"):
        relatorio["registros_apagados"] = expurgar_registros(Path(os.environ["LOGS_DIR"]))
    return relatorio
