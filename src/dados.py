# Sistema acadêmico simulado — o "software tradicional" do item 4.2.
#
# É um SQLite de verdade, não um dicionário Python no meio do arquivo do
# agente: as ferramentas do agente atravessam a fronteira do processo (uma
# conexão de banco, com os erros que isso traz — registro ausente, por
# exemplo) em vez de ler uma estrutura já carregada em memória.
#
# Dados 100% sintéticos (docs/case.md §2.9) — nenhum aluno, RA ou valor aqui
# corresponde a uma pessoa real.

import sqlite3
from pathlib import Path

CAMINHO_DB = Path(__file__).parent.parent / "dados" / "academico.db"

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

    conexao.commit()
    conexao.close()


if __name__ == "__main__":
    inicializar(forcar=True)
    print(f"Banco criado em {CAMINHO_DB} com {len(ALUNOS)} alunos "
          f"({len(FINANCEIRO)} com pendência financeira).")
