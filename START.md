# START — rodar e testar o sistema

Sistema de triagem da secretaria acadêmica: o aluno escreve em português, e o sistema emite o documento, responde uma dúvida do Regimento ou encaminha o caso para a secretaria humana. Os dados são sintéticos (SQLite). **Python 3.10 ou mais novo** (o ambiente do projeto é 3.11); só os scripts da Parte 1 (`demo.py`, `verificador.py`) rodam em 3.9.

## 1. Instalar (qualquer máquina)

```bash
git clone https://github.com/weslleyssousa444-ui/secretaria-academica-agente.git
cd secretaria-academica-agente
python3.11 -m venv .venv              # Windows: py -3.11 -m venv .venv
source .venv/bin/activate             # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt   # o sistema + os testes, versões fixadas
```

Confira com `ls` (Windows: `dir`): devem aparecer as pastas `src` e `tests`.

## 2. Sem chave de API

```bash
python -m pytest -q                   # esperado: 147 passed, 1 deselected
python conferir_grafo.py              # os 15 nós e 24 arestas do grafo entregue
OPENAI_API_KEY=x python src/suite/relatorio.py    # resultado da suíte do Exercício 11, a partir de logs/suite/
```

O `pytest` roda tudo offline, com o modelo roteirizado (o "modelo" faz de propósito o que um modelo ruim faria, e o teste prova que o **código** barra). O `relatorio.py` imprime o resultado já gravado da suíte de avaliação; a análise escrita está em [`exercicios/aula-11-suite-do-case.md`](exercicios/aula-11-suite-do-case.md). Windows (PowerShell): `$env:OPENAI_API_KEY="x"; python src/suite/relatorio.py`.

## 3. Conversar com o sistema (precisa de chave gratuita da Groq)

Crie a chave, sem cartão, em <https://console.groq.com/keys>.

```bash
cp .env.example .env                  # Windows: copy .env.example .env
# edite o .env e cole a chave em OPENAI_API_KEY=
python src/dados.py
python src/chat.py --dica --trilha
```

Digite `sair` para encerrar. Mensagens para testar:

| Digite | Esperado |
|---|---|
| `Preciso de uma declaração de matrícula. Meu RA é 20231045.` | emite, com protocolo `DOC-xxxx` |
| `Preciso de uma declaração de matrícula.` | pergunta o RA antes de usar ferramenta |
| `Quero a segunda via do meu histórico. Meu RA é 20230198.` | não emite (mensalidades em aberto); escala com protocolo `CASO-xxxx` e prazo de 48h |
| `Quero trancar minha matrícula. Meu RA é 20229012.` | **o grafo para** esperando a coordenação; você recebe o protocolo e o prazo |
| `O que vale como comprovante de pagamento?` | responde com o artigo do Regimento e declara a suficiência |
| `Quanto custa emitir a segunda via do histórico?` | o Regimento não responde: diz o que ele trata e oferece encaminhar |
| `Preciso de uma declaração. Meu RA é 20240000.` e depois `Tenho certeza, é esse.` | RA inexistente: confirma uma vez e escala |
| `Quero meu diploma impresso. Meu RA é 20220087.` | recusa e diz o que atende; nada é emitido |

**A coordenação decide o trancamento**, em outro terminal:

```bash
python src/coordenacao.py listar
python src/coordenacao.py decidir CASO-3001 aprovar_editando --por coord-1 --editar semestre_efetivo=2027.1
```

Outros comandos: `python src/demo_grafo.py` (as 8 demonstrações, contra o modelo real; `logs/parte2/`), `python src/verificador.py` (40 casos da Parte 1; demora vários minutos). A API: `python -m uvicorn api:app --app-dir src --port 8000` (a decisão da coordenação por HTTP exige `COORDENACAO_TOKEN` no `.env`).

## Se algo falhar

| Sintoma | Saída |
|---|---|
| `No such file` ao instalar ou rodar | você está na pasta errada; rode `cd` até a que contém `src` |
| `requires a different Python` ao instalar | falta o Python 3.10+; confira `python --version` dentro do `.venv` |
| `The api_key client option must be set` | falta o `.env` com a chave (só o passo 3 precisa dela) |
| `429` ou `tokens per day` | acabou a cota gratuita do modelo no dia; **espere** (a cota é uma janela de 24 h). Trocar `LLM_MODELO` não resolve: o sistema só sobe com modelo da lista aprovada (`src/triagem/modelos.py`), e o único aprovado é o `qwen/qwen3.8-27b` |
| `ModeloNaoAprovado` ao subir | o `LLM_MODELO` do `.env` não está em `MODELOS_APROVADOS`: volte a `qwen/qwen3.8-27b`, ou avalie o modelo (`python -m evals.rodar`) e aprove-o no código |
| `503` em `/coordenacao/...` | falta `COORDENACAO_TOKEN` no `.env`: sem ele o endpoint de decisão fica **fechado** de propósito |

Onde está cada exercício: [`README.md`](README.md). O sistema não confere quem é o aluno (lacuna L01 do [model card](docs/model-card.md)); use apenas dados sintéticos.
