# START — rodar e testar o agente

Agente de triagem da secretaria acadêmica: o aluno escreve em português, e o agente emite o documento ou encaminha o caso para a secretaria humana. Os dados são sintéticos (SQLite). Precisa de **Python 3.9 ou mais novo**.

## 1. Instalar (qualquer máquina)

```bash
git clone https://github.com/weslleyssousa444-ui/secretaria-academica-agente.git
cd secretaria-academica-agente
python3 -m venv .venv                 # Windows: py -m venv .venv
source .venv/bin/activate             # Windows: .venv\Scripts\Activate.ps1
pip install openai==2.48.0 python-dotenv==1.2.1 pytest
```

Confira com `ls` (Windows: `dir`): devem aparecer as pastas `src` e `tests`.

## 2. Sem chave de API

```bash
python -m pytest -q --ignore=tests/test_api.py
OPENAI_API_KEY=x python src/suite/relatorio.py       # Windows (PowerShell): $env:OPENAI_API_KEY="x"; python src/suite/relatorio.py
```

O primeiro comando roda os testes offline; esperado: `64 passed, 1 skipped`. O segundo imprime o resultado da suíte de avaliação do Exercício 11 a partir de `logs/suite/`, sem chamar modelo. A análise escrita está em [`exercicios/aula-11-suite-do-case.md`](exercicios/aula-11-suite-do-case.md).

## 3. Conversar com o agente (precisa de chave gratuita da Groq)

Crie a chave, sem cartão, em <https://console.groq.com/keys>.

```bash
cp .env.example .env                  # Windows: copy .env.example .env
# edite o .env e cole a chave em OPENAI_API_KEY=
python src/dados.py
python src/chat.py --dica
```

Digite `sair` para encerrar. Mensagens para testar:

| Digite | Esperado |
|---|---|
| `Preciso de uma declaração de matrícula. Meu RA é 20231045.` | emite, com protocolo `DOC-xxxx` |
| `Preciso de uma declaração de matrícula.` | pergunta o RA antes de usar ferramenta |
| `Quero a segunda via do meu histórico. Meu RA é 20230198.` | não emite (mensalidades em aberto); escala com protocolo `CASO-xxxx` e prazo de 48h |
| `Quero trancar minha matrícula. Meu RA é 20221100.` | trancamento sempre é escalado |
| `Preciso de uma declaração. Meu RA é 20240000.` e depois `Tenho certeza, é esse.` | RA inexistente: confirma uma vez e escala |
| `Quero meu diploma impresso. Meu RA é 20220087.` | recusa; nada é emitido |

Outros comandos: `python src/demo.py` (4 demonstrações) e `python src/verificador.py` (40 casos; demora vários minutos). A API HTTP exige Python 3.10 ou mais: `pip install fastapi uvicorn` e `python -m uvicorn api:app --app-dir src --port 8000`.

## Se algo falhar

| Sintoma | Saída |
|---|---|
| `No such file` ao instalar ou rodar | você está na pasta errada; rode `cd` até a que contém `src` |
| `The api_key client option must be set` | falta o `.env` com a chave (só o passo 3 precisa dela) |
| `429` ou `tokens per day` | acabou a cota gratuita do modelo no dia; espere, ou troque `LLM_MODELO` no `.env` para `openai/gpt-oss-20b` |

Onde está cada exercício: [`README.md`](README.md). O agente não confere quem é o aluno (lacuna L01 do [model card](docs/model-card.md)); use apenas dados sintéticos.
