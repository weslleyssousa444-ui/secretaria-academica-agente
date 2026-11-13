# Sistema acadêmico simulado — o "software tradicional" do item 4.2.
#
# É um SQLite de verdade, não um dicionário Python no meio do arquivo do
# agente: as ferramentas do agente atravessam a fronteira do processo (uma
# conexão de banco, com os erros que isso traz — registro ausente, por
# exemplo) em vez de ler uma estrutura já carregada em memória.
#
# Dados 100% sintéticos (docs/case.md §2.9) — nenhum aluno, RA ou valor aqui
# corresponde a uma pessoa real.

import os
import sqlite3
from pathlib import Path

# ACADEMICO_DB aponta o banco para fora da imagem — no container, um volume
# montado em /dados (docs/empacotamento.md §4). Sem a variável, o caminho
# de sempre, dentro do repositório.
CAMINHO_DB = Path(os.environ.get(
    "ACADEMICO_DB", Path(__file__).parent.parent / "dados" / "academico.db"))

# RA usado nos casos de teste para o cenário "registro inexistente"
# (docs/case.md §2.8) — deliberadamente NÃO existe na tabela `alunos`.
RA_INEXISTENTE = "20240000"

ALUNOS = [
    # ra,         nome,                 curso,          situacao
    ("20231045", "Weslley Sousa",       "ADS",          "ativa"),
    ("20230198", "Marina Alves",        "ADS",          "ativa"),
    ("20229012", "Bruno Castro",        "Direito",      "ativa"),
    ("20221100", "Carla Nunes",         "Direito",      "trancada"),
    ("20233321", "Diego Ramos",         "Enfermagem",   "ativa"),
    ("20220087", "Elisa Prado",         "Enfermagem",   "formado"),
    ("20234456", "Fabio Teixeira",      "ADS",          "ativa"),
    ("20232210", "Gabriela Lima",       "Marketing",    "ativa"),
    ("20231987", "Henrique Matos",      "ADS",          "ativa"),
    ("20230555", "Isabela Farias",      "Direito",      "ativa"),
    ("20229999", "Joao Pedro Alencar",  "Marketing",    "ativa"),
    ("20233120", "Karina Souza",        "Enfermagem",   "ativa"),
    ("20221450", "Lucas Andrade",       "ADS",          "trancada"),
    ("20234789", "Mariana Costa",       "Direito",      "ativa"),
    ("20230321", "Nicolas Vieira",      "Marketing",    "ativa"),
    ("20232876", "Olivia Reis",         "ADS",          "ativa"),
    ("20231234", "Pedro Akira",         "ADS",          "ativa"),
    ("20230876", "Quintino Alves",      "Enfermagem",   "ativa"),
    ("20234321", "Rafaela Dias",        "Direito",      "ativa"),
    ("20229555", "Sofia Martins",       "ADS",          "formado"),
]

# ra, mensalidades_em_aberto, valor_em_aberto — só entra aqui quem tem
# pendência; quem não aparece é tratado como zero pendências.
FINANCEIRO = [
    ("20230198", 2, 890.00),   # divergência: aluno vai alegar "já paguei"
    ("20233321", 1, 445.00),
    ("20232210", 3, 1200.00),
    ("20233120", 1, 445.00),
    ("20230321", 2, 890.00),
    ("20234321", 1, 445.00),
]

# Disciplinas por curso (dados FICTÍCIOS), em dois semestres cursados e um em
# andamento. A nota de cada aluno é derivada do RA e do código (determinística:
# o mesmo banco sai igual em toda máquina e em todo teste).
DISCIPLINAS = {
    "ADS": [("ADS101", "Algoritmos e Lógica de Programação", 80), ("ADS102", "Banco de Dados I", 80),
            ("ADS103", "Fundamentos de Redes", 60), ("ADS201", "Programação Orientada a Objetos", 80),
            ("ADS202", "Engenharia de Software", 60), ("ADS203", "Desenvolvimento Web", 80)],
    "Direito": [("DIR101", "Introdução ao Estudo do Direito", 80), ("DIR102", "Teoria Geral do Estado", 60),
                ("DIR103", "Direito Romano", 40), ("DIR201", "Direito Constitucional I", 80),
                ("DIR202", "Direito Civil: Parte Geral", 80), ("DIR203", "Direito Penal I", 60)],
    "Enfermagem": [("ENF101", "Anatomia Humana", 80), ("ENF102", "Bioquímica", 60),
                   ("ENF103", "Fundamentos de Enfermagem", 80), ("ENF201", "Fisiologia", 80),
                   ("ENF202", "Microbiologia", 60), ("ENF203", "Semiologia e Semiotécnica", 80)],
    "Marketing": [("MKT101", "Fundamentos de Marketing", 60), ("MKT102", "Comportamento do Consumidor", 60),
                  ("MKT103", "Estatística Aplicada", 60), ("MKT201", "Marketing Digital", 80),
                  ("MKT202", "Pesquisa de Mercado", 60), ("MKT203", "Gestão de Marca", 60)],
}
SEMESTRES = ("2025.2", "2026.1", "2026.2")  # o último está em andamento


def _nota(ra: str, codigo: str) -> float:
    """Nota fictícia entre 5,0 e 10,0, fixa para cada par (RA, disciplina)."""
    semente = sum(ord(c) * (i + 7) for i, c in enumerate(ra + codigo))
    return round(5.0 + (semente % 51) / 10, 1)


def historico_sintetico() -> list[tuple]:
    """(ra, codigo, nome, semestre, carga_horaria, nota, situacao) de cada aluno."""
    linhas = []
    for ra, _nome, curso, situacao_matricula in ALUNOS:
        disciplinas = DISCIPLINAS[curso]
        for i, (codigo, nome, ch) in enumerate(disciplinas):
            semestre = SEMESTRES[min(i // 2, 2)]
            em_andamento = semestre == SEMESTRES[-1] and situacao_matricula == "ativa"
            if semestre == SEMESTRES[-1] and situacao_matricula != "ativa":
                continue  # trancado ou formado não cursa o semestre atual
            nota = None if em_andamento else _nota(ra, codigo)
            situacao = ("cursando" if em_andamento
                        else "aprovado" if nota >= 6.0 else "reprovado")
            linhas.append((ra, codigo, nome, semestre, ch, nota, situacao))
    return linhas


def mensalidades_sinteticas() -> list[tuple]:
    """(ra, competencia, valor, vencimento) das mensalidades EM ABERTO, coerentes
    com FINANCEIRO (mesma quantidade e mesmo total)."""
    competencias = ("2026-08", "2026-09", "2026-10")
    linhas = []
    for ra, quantidade, total in FINANCEIRO:
        valor = round(total / quantidade, 2)
        for competencia in competencias[-quantidade:]:
            linhas.append((ra, competencia, valor, f"{competencia}-10"))
    return linhas


# Documento já emitido antes — usado para exercitar a idempotência de
# `emitir_documento` (mesmo padrão de `abrir_chamado` em aula05-agentes).
DOCUMENTOS_SEMENTE = [
    ("DOC-1000", "20234456", "declaracao_matricula", "2026-08-20"),
]


def conectar() -> sqlite3.Connection:
    CAMINHO_DB.parent.mkdir(exist_ok=True)
    conexao = sqlite3.connect(CAMINHO_DB)
    conexao.row_factory = sqlite3.Row
    return conexao


def inicializar(forcar: bool = False) -> None:
    """Cria o schema e semeia os dados sintéticos, se ainda não existirem."""
    if forcar and CAMINHO_DB.exists():
        CAMINHO_DB.unlink()

    conexao = conectar()
    cur = conexao.cursor()
    cur.executescript("""
        CREATE TABLE IF NOT EXISTS alunos (
            ra TEXT PRIMARY KEY,
            nome TEXT NOT NULL,
            curso TEXT NOT NULL,
            situacao_matricula TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS financeiro (
            ra TEXT PRIMARY KEY,
            mensalidades_em_aberto INTEGER NOT NULL,
            valor_em_aberto REAL NOT NULL,
            FOREIGN KEY (ra) REFERENCES alunos (ra)
        );
        CREATE TABLE IF NOT EXISTS documentos_emitidos (
            protocolo TEXT PRIMARY KEY,
            ra TEXT NOT NULL,
            tipo_documento TEXT NOT NULL,
            data_emissao TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS casos_pendentes (
            protocolo TEXT PRIMARY KEY,
            ra TEXT,
            tipo_pedido TEXT NOT NULL,
            motivo TEXT NOT NULL,
            chave TEXT UNIQUE,
            status TEXT NOT NULL DEFAULT 'aberto'
        );
        -- Aprovação humana do trancamento (src/triagem/humano.py, docs/humano.md).
        -- `aprovacoes` guarda o que está esperando uma pessoa e até quando;
        -- `decisoes_humanas` guarda o que a pessoa decidiu. A chave da decisão
        -- é derivada do caso (`<protocolo>:decisao`): decidir duas vezes o
        -- mesmo caso não grava duas vezes.
        CREATE TABLE IF NOT EXISTS aprovacoes (
            protocolo TEXT PRIMARY KEY,
            thread_id TEXT NOT NULL,
            ra TEXT,
            criado_em TEXT NOT NULL,
            prazo_ate TEXT NOT NULL,
            estado TEXT NOT NULL DEFAULT 'aguardando'
        );
        -- Funções de 13/11/2026: histórico acadêmico, mensalidades em aberto,
        -- boletos (segunda via) e o código de verificação de cada documento.
        CREATE TABLE IF NOT EXISTS disciplinas_cursadas (
            ra TEXT NOT NULL,
            codigo TEXT NOT NULL,
            nome TEXT NOT NULL,
            semestre TEXT NOT NULL,
            carga_horaria INTEGER NOT NULL,
            nota REAL,
            situacao TEXT NOT NULL,
            PRIMARY KEY (ra, codigo)
        );
        CREATE TABLE IF NOT EXISTS mensalidades (
            ra TEXT NOT NULL,
            competencia TEXT NOT NULL,
            valor REAL NOT NULL,
            vencimento TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'aberta',
            PRIMARY KEY (ra, competencia)
        );
        CREATE TABLE IF NOT EXISTS boletos_emitidos (
            protocolo TEXT PRIMARY KEY,
            ra TEXT NOT NULL,
            competencia TEXT NOT NULL,
            valor REAL NOT NULL,
            vencimento TEXT NOT NULL,
            linha_digitavel TEXT NOT NULL,
            emitido_em TEXT NOT NULL,
            UNIQUE (ra, competencia)
        );
        CREATE TABLE IF NOT EXISTS codigos_verificacao (
            protocolo TEXT PRIMARY KEY,
            codigo TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS decisoes_humanas (
            chave TEXT PRIMARY KEY,
            protocolo TEXT NOT NULL,
            decisao TEXT NOT NULL,
            edicao TEXT,
            decidido_por TEXT NOT NULL,
            decidido_em TEXT NOT NULL
        );
    """)

    if cur.execute("SELECT COUNT(*) FROM alunos").fetchone()[0] == 0:
        cur.executemany(
            "INSERT INTO alunos (ra, nome, curso, situacao_matricula) "
            "VALUES (?, ?, ?, ?)", ALUNOS)
        cur.executemany(
            "INSERT INTO financeiro (ra, mensalidades_em_aberto, valor_em_aberto) "
            "VALUES (?, ?, ?)", FINANCEIRO)
        cur.executemany(
            "INSERT INTO documentos_emitidos "
            "(protocolo, ra, tipo_documento, data_emissao) VALUES (?, ?, ?, ?)",
            DOCUMENTOS_SEMENTE)
    # Semeadas à parte: um banco criado antes destas tabelas também as recebe.
    if cur.execute("SELECT COUNT(*) FROM disciplinas_cursadas").fetchone()[0] == 0:
        cur.executemany(
            "INSERT INTO disciplinas_cursadas (ra, codigo, nome, semestre, carga_horaria, "
            "nota, situacao) VALUES (?, ?, ?, ?, ?, ?, ?)", historico_sintetico())
    if cur.execute("SELECT COUNT(*) FROM mensalidades").fetchone()[0] == 0:
        cur.executemany(
            "INSERT INTO mensalidades (ra, competencia, valor, vencimento) VALUES (?, ?, ?, ?)",
            mensalidades_sinteticas())

    conexao.commit()
    conexao.close()


if __name__ == "__main__":
    inicializar(forcar=True)
    print(f"Banco criado em {CAMINHO_DB} com {len(ALUNOS)} alunos "
          f"({len(FINANCEIRO)} com pendência financeira).")
