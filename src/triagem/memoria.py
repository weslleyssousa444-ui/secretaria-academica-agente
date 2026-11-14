# Memória entre execuções do sistema de triagem (docs/memoria.md).
#
# As três memórias, cada uma na estrutura certa (Aula 08):
#   episódica  — "o que aconteceu com este aluno": índice por SIMILARIDADE
#                (TF-IDF, abaixo), filtrado pelo RA;
#   semântica  — "fato estável sobre o aluno": chave-valor, lida por chave
#                (memoria_semantica.MemoriaSemantica, do Exercício 8);
#   procedural — "como agir", texto no prompt, SÓ depois de aprovada por uma
#                pessoa (memoria_procedural.MemoriaProcedural, do Ex. 8).
#
# POR QUE TF-IDF E NÃO EMBEDDING NA EPISÓDICA: o Exercício 8 usou
# sentence-transformers (torch, ~2 GB), que não cabe na imagem do agente.
# Os episódios daqui são resumos curtos, escritos por CÓDIGO a partir de um
# molde ("Pedido de X resultou em Y"): o vocabulário é controlado, e a
# similaridade lexical basta. A perda — paráfrase sem termo em comum — está
# declarada em docs/memoria.md §3.
#
# POLÍTICA DE ESCRITA: o CÓDIGO extrai, por regra, do que as ferramentas
# devolveram. O modelo nunca escolhe o que guardar (guardaria demais, e
# guardaria o que o aluno afirmou, não o que o sistema confirmou — e isso é o
# envenenamento de memória, ASI06). Volume: no máximo 1 episódio e 1 fato por
# turno, ~200 bytes cada.
#
# IDENTIDADE: leitura e escrita só acontecem com `ra_autenticado` (a sessão do
# portal). Sem ele não há memória: um RA digitado no chat não abre o histórico
# de ninguém.

from __future__ import annotations

import hashlib
import os
import json
import math
import re
import sqlite3
from collections import Counter
from datetime import date
from pathlib import Path

from memoria_procedural import MemoriaProcedural
from memoria_semantica import MemoriaSemantica
from triagem.regimento import termos_da_pergunta

DIAS_DE_DECAIMENTO = 180  # um semestre e meio: depois disso o episódio não orienta mais o atendimento
ORCAMENTO_TOKENS_MEMORIA = 400
MAX_EPISODIOS = 3


def _tokens(texto: str) -> list[str]:
    return termos_da_pergunta(texto) or re.findall(r"\w+", texto.lower())


class EpisodicaLexical:
    """Índice por similaridade (TF-IDF + cosseno) sobre os resumos de UM aluno."""

    def __init__(self, caminho: Path):
        self.caminho = caminho
        self.episodios: list[dict] = (
            json.loads(caminho.read_text(encoding="utf-8")) if caminho.exists() else [])

    def _salvar(self) -> None:
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        self.caminho.write_text(json.dumps(self.episodios, ensure_ascii=False, indent=2),
                                encoding="utf-8")

    def gravar(self, ra: str, data: str, tipo_pedido: str, resumo: str) -> dict:
        """Chave de idempotência derivada do CONTEÚDO (RA, tipo e resumo), não
        de uuid: o mesmo episódio gravado duas vezes é um só."""
        id_ = hashlib.sha1(f"{ra}|{tipo_pedido}|{resumo}".encode()).hexdigest()[:12]
        for existente in self.episodios:
            if existente["id"] == id_:
                return {**existente, "ja_existia": True}
        episodio = {"id": id_, "ra": ra, "data": data, "tipo_pedido": tipo_pedido,
                    "resumo": resumo}
        self.episodios.append(episodio)
        self._salvar()
        return {**episodio, "ja_existia": False}

    def recuperar(self, consulta: str, ra: str, k: int = MAX_EPISODIOS) -> list[dict]:
        doc_do_ra = [e for e in self.episodios if e["ra"] == ra]
        if not doc_do_ra:
            return []
        docs = [_tokens(e["resumo"]) for e in doc_do_ra]
        n = len(docs) + 1  # +1: a consulta entra no cálculo do IDF
        df = Counter(t for d in docs + [_tokens(consulta)] for t in set(d))
        idf = {t: math.log((1 + n) / (1 + c)) + 1 for t, c in df.items()}

        def vetor(tokens: list[str]) -> dict[str, float]:
            tf = Counter(tokens)
            return {t: tf[t] * idf[t] for t in tf}

        def cosseno(a: dict, b: dict) -> float:
            produto = sum(v * b.get(t, 0.0) for t, v in a.items())
            norma = math.sqrt(sum(v * v for v in a.values())) * math.sqrt(sum(v * v for v in b.values()))
            return produto / norma if norma else 0.0

        q = vetor(_tokens(consulta))
        pontuados = [(cosseno(q, vetor(d)), e) for d, e in zip(docs, doc_do_ra)]
        # empate de similaridade: o mais recente primeiro (carimbo de tempo)
        pontuados.sort(key=lambda p: (p[0], p[1]["data"]), reverse=True)
        return [e for pontos, e in pontuados[:k] if pontos > 0]

    def aplicar_decaimento(self, hoje: date, dias: int = DIAS_DE_DECAIMENTO) -> int:
        """Remove o episódio com mais de `dias` dias. Roda em rotina, não na leitura."""
        antes = len(self.episodios)
        self.episodios = [e for e in self.episodios
                          if (hoje - date.fromisoformat(e["data"])).days <= dias]
        if len(self.episodios) != antes:
            self._salvar()
        return antes - len(self.episodios)

    def remover(self, ra: str) -> int:
        antes = len(self.episodios)
        self.episodios = [e for e in self.episodios if e["ra"] != ra]
        if len(self.episodios) != antes:
            self._salvar()
        return antes - len(self.episodios)

    def contem_ra(self, ra: str) -> list[str]:
        return [e["id"] for e in self.episodios if ra in json.dumps(e, ensure_ascii=False)]


def estimar_tokens(texto: str) -> int:
    return len(texto) // 4


class Memoria:
    """Fachada das três memórias, numa pasta (`TRIAGEM_MEMORIA_DIR`)."""

    def __init__(self, pasta: Path):
        self.pasta = Path(pasta)
        self.episodica = EpisodicaLexical(self.pasta / "episodica.json")
        self.semantica = MemoriaSemantica(self.pasta / "semantica.json")
        self.procedural = MemoriaProcedural(self.pasta / "procedural.json")

    # ------------------------------------------------------------- leitura
    def ler_bloco(self, ra_autenticado: str | None, consulta: str,
                  teto_tokens: int = ORCAMENTO_TOKENS_MEMORIA) -> dict:
        """O bloco MEMÓRIA que entra no contexto. Ordem de montagem: procedural
        (estável) -> semântica -> episódica (a mais volumosa, perto da conversa).
        Estourou o teto: a episódica sai primeiro (docs/memoria.md §5.3)."""
        procedural = self.procedural.como_system_prompt()
        semantica = episodica = ""
        episodios: list[dict] = []
        if ra_autenticado:
            fato = self.semantica.ler(ra_autenticado, "situacao_financeira")
            if fato:
                semantica = (f"Fato conhecido: situação financeira = {fato['valor']} "
                             f"(registrada em {fato['data']}; confirme com a ferramenta).")
            episodios = self.episodica.recuperar(consulta, ra_autenticado)
            if episodios:
                episodica = "Atendimentos anteriores deste aluno:\n" + "\n".join(
                    f"- [{e['data']}] {e['resumo']}" for e in episodios)
        partes = [p for p in (procedural, semantica, episodica) if p]
        texto = "\n\n".join(partes)
        if estimar_tokens(texto) > teto_tokens:
            texto = "\n\n".join(p for p in (procedural, semantica) if p)
            episodios = []
        return {"texto": texto, "tokens": estimar_tokens(texto),
                "episodios_usados": len(episodios)}

    # ------------------------------------------------------------- escrita
    def escrever_depois_do_turno(self, ra_autenticado: str | None, passos_do_turno: list[dict],
                                 hoje: date | None = None) -> dict:
        """Política: o código extrai, do que as ferramentas devolveram. Só com
        identidade, e só para o RA autenticado (uma consulta a outro RA não
        grava nada na memória de ninguém)."""
        gravados = {"episodio": None, "fato": None}
        if not ra_autenticado:
            return gravados
        hoje = hoje or date.today()
        data = hoje.isoformat()
        for passo in passos_do_turno:
            if passo.get("erro") is not None or not passo.get("resultado"):
                continue
            r = passo["resultado"]
            if passo["ferramenta"] == "consultar_financeiro" and r.get("ra") == ra_autenticado:
                em_aberto = r.get("mensalidades_em_aberto", 0)
                valor = ("em dia" if em_aberto == 0 else
                         f"{em_aberto} mensalidade(s) em aberto (R$ {r.get('valor_em_aberto', 0):.2f})")
                gravados["fato"] = self.semantica.gravar(
                    ra_autenticado, "situacao_financeira", valor, data)
            if passo["ferramenta"] == "emitir_documento" and r.get("ra") == ra_autenticado:
                gravados["episodio"] = self.episodica.gravar(
                    ra_autenticado, data, r["tipo_documento"],
                    f"Pedido de {r['tipo_documento']} resultou em documento emitido "
                    f"(protocolo {r['protocolo']}).")
            if passo["ferramenta"] == "escalar_para_humano" and r.get("ra") == ra_autenticado:
                gravados["episodio"] = self.episodica.gravar(
                    ra_autenticado, data, r["tipo_pedido"],
                    f"Pedido de {r['tipo_pedido']} foi encaminhado à secretaria "
                    f"(protocolo {r['protocolo']}).")
        return gravados

    # ------------------------------------------------------------ esquecimento
    def varrer(self, ra: str, checkpoint_db: Path | None = None,
               pasta_registros: Path | None = None) -> list[tuple[str, str]]:
        """Onde o RA ainda aparece. A ENTREGA da remoção é esta busca não
        achar nada, e não a chamada de exclusão (Aula 08, nota 04 §3.2)."""
        achados = [("episodica", i) for i in self.episodica.contem_ra(ra)]
        achados += [("semantica", k) for k in self.semantica.contem_entidade(ra)]
        achados += [("procedural", r) for r in self.procedural.contem_texto(ra)]
        if checkpoint_db and Path(checkpoint_db).exists():
            achados += [("checkpoint", t) for t in _threads_com_ra(Path(checkpoint_db), ra)]
        if pasta_registros and Path(pasta_registros).exists():
            achados += [("registro", a.name) for a in Path(pasta_registros).glob("*.json*")
                        if ra in a.read_text(encoding="utf-8", errors="ignore")]
        return achados

    def remover_titular(self, ra: str, checkpoint_db: Path | None = None,
                        pasta_registros: Path | None = None, trace: Path | None = None) -> dict:
        """Remove o RA de TODAS as estruturas que o guardam: episódica,
        semântica, checkpoint (as conversas inteiras que o citam) e registros
        de execução. A procedural NÃO é editada sozinha: uma regra que cita o
        titular é devolvida para revisão humana (`regras_suspeitas`)."""
        relatorio = {"episodios": self.episodica.remover(ra),
                     "fatos": self.semantica.remover(ra),
                     "regras_suspeitas": self.procedural.contem_texto(ra),
                     "threads_de_checkpoint": 0, "registros": 0, "spans_do_trace": 0}
        if checkpoint_db and Path(checkpoint_db).exists():
            relatorio["threads_de_checkpoint"] = _apagar_threads_com_ra(Path(checkpoint_db), ra)
        if pasta_registros and Path(pasta_registros).exists():
            for arquivo in Path(pasta_registros).glob("*.json*"):
                if arquivo.name == "traces.jsonl":
                    continue   # o trace é editado por conversa, abaixo; não se apaga inteiro
                if ra in arquivo.read_text(encoding="utf-8", errors="ignore"):
                    arquivo.unlink()
                    relatorio["registros"] += 1
        if trace is None and os.environ.get("TRIAGEM_TRACES_DIR"):
            trace = Path(os.environ["TRIAGEM_TRACES_DIR"]) / "traces.jsonl"
        if trace:
            from triagem.retencao import remover_titular_do_trace
            relatorio["spans_do_trace"] = remover_titular_do_trace(Path(trace), ra)
        return relatorio


def _threads_com_ra(checkpoint_db: Path, ra: str) -> list[str]:
    """`thread_id` dos checkpoints cujo conteúdo (blob) contém o RA."""
    con = sqlite3.connect(checkpoint_db)
    try:
        linhas = con.execute(
            "SELECT DISTINCT thread_id FROM checkpoints WHERE instr(checkpoint, ?) > 0 "
            "OR instr(metadata, ?) > 0", (ra.encode(), ra.encode())).fetchall()
        escritas = con.execute(
            "SELECT DISTINCT thread_id FROM writes WHERE instr(value, ?) > 0",
            (ra.encode(),)).fetchall()
    finally:
        con.close()
    return sorted({l[0] for l in linhas} | {l[0] for l in escritas})


def _apagar_threads_com_ra(checkpoint_db: Path, ra: str) -> int:
    threads = _threads_com_ra(checkpoint_db, ra)
    con = sqlite3.connect(checkpoint_db)
    try:
        for t in threads:
            con.execute("DELETE FROM checkpoints WHERE thread_id = ?", (t,))
            con.execute("DELETE FROM writes WHERE thread_id = ?", (t,))
        con.commit()
    finally:
        con.close()
    return len(threads)
