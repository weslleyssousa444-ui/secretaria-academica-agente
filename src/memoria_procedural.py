# Memória procedural do agente de triagem — Exercício 8.
#
# Como agir, extraído de um erro observado. Texto no system prompt — a mais
# valiosa das três e a mais perigosa (Aula 08, nota 02 §3.3): não é filtrada
# por relevância como as outras duas, então uma regra errada se aplica a
# TODAS as execuções seguintes. Por isso exige `aprovada` (revisão humana,
# nota 03 §1.3) antes de entrar no prompt de produção.

from __future__ import annotations

import json
from pathlib import Path

CAMINHO_PADRAO = Path(__file__).parent.parent / "dados" / "memoria_procedural.json"


class MemoriaProcedural:
    def __init__(self, caminho: Path | None = None):
        self.caminho = caminho or CAMINHO_PADRAO
        self.regras: list[dict] = (
            json.loads(self.caminho.read_text(encoding="utf-8"))
            if self.caminho.exists() else [])

    def _salvar(self) -> None:
        self.caminho.parent.mkdir(exist_ok=True)
        self.caminho.write_text(json.dumps(self.regras, ensure_ascii=False, indent=2),
                                 encoding="utf-8")

    def gravar(self, regra: str, aprovada: bool = False) -> bool:
        """Idempotência por igualdade textual (nota 03 §3) — frágil a
        paráfrase, mas deduplicar por similaridade fundiria uma regra com a
        própria negação (Aula 07, cegueira de negação)."""
        if any(r["regra"] == regra for r in self.regras):
            return False
        self.regras.append({"regra": regra, "aprovada": aprovada})
        self._salvar()
        return True

    def aprovar(self, regra: str) -> bool:
        for r in self.regras:
            if r["regra"] == regra:
                r["aprovada"] = True
                self._salvar()
                return True
        return False

    def regras_ativas(self) -> list[str]:
        return [r["regra"] for r in self.regras if r["aprovada"]]

    def como_system_prompt(self) -> str:
        ativas = self.regras_ativas()
        if not ativas:
            return ""
        return "Procedimentos aprendidos em execuções anteriores:\n" + \
               "\n".join(f"- {r}" for r in ativas)

    def contem_texto(self, texto: str) -> list[str]:
        return [r["regra"] for r in self.regras if texto in r["regra"]]
