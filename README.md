# Atendimento de secretaria acadêmica — agente de triagem (Parte 1)

**Grupo:** Weslley Soares de Sousa, Pedro Akira, Henrique Gomes Matos, Erick

**O problema em uma frase:** decidir se uma solicitação de aluno (declaração de matrícula, segunda via de histórico ou trancamento de matrícula) pode ser atendida automaticamente ou precisa ser encaminhada a um atendente humano da secretaria, cruzando o que o aluno relata com o que o sistema acadêmico registra.

A pesquisa completa do case está em [`docs/case.md`](docs/case.md) (usuários, workflow, justificativa de negócio, verificador) e [`docs/modelos.md`](docs/modelos.md) (escolha do modelo).

---

## Como rodar

Testado do zero, em menos de 5 minutos.

```bash
git clone <url-do-repo-do-grupo>
cd secretaria-academica-agente

python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\Activate.ps1

pip install -r requirements.txt

cp .env.example .env
# edite .env e cole sua chave da Mistral em OPENAI_API_KEY
# (crie a chave em https://admin.mistral.ai/, menu API Keys)
```

Crie e semeie o banco simulado (idempotente — pode rodar de novo sem duplicar dados):

```bash
python src/dados.py
```

## Como usar

O agente conversa em texto livre, em português, como o widget de chat do portal do aluno faria. Não há interface gráfica nesta Parte 1 — as três formas de interagir são scripts de linha de comando:

| Script | O que faz |
|---|---|
| `python src/demo.py` | roda os **4 casos de demonstração** exigidos (§4.5): simples, divergência, RA inexistente, trancamento — e grava o log de cada um em `logs/` |
| `python src/verificador.py` | roda os **40 casos rotulados** (`dados/casos_verificador.json`) e reporta a taxa de acerto contra o critério de sucesso (`docs/case.md` §2.7) |
| `python src/comparar_modelos.py` | roda 5 casos nos 3 modelos candidatos, para preencher `docs/modelos.md` §3.3 |

**O que a pessoa digita:** uma mensagem em português descrevendo o pedido — com ou sem o RA já incluído. Exemplo: *"Preciso de uma declaração de matrícula. Meu RA é 20231045."* ou, em partes, *"Oi, preciso de uma declaração de matrícula pra levar no estágio."* seguido de *"20231045"* quando o agente perguntar.

**O que o sistema faz com aquilo:** identifica o tipo de pedido e o RA, consulta o sistema acadêmico simulado (cadastro + financeiro, em SQLite), e decide — segundo as regras de `docs/case.md` §2.1 — se emite o documento na hora ou encaminha o caso para a secretaria humana.

**Que saída ela recebe:** texto em português. Se aprovado: o protocolo do documento (`DOC-xxxx`) e o texto da declaração/segunda via. Se escalado: o protocolo do caso (`CASO-xxxx`), o motivo do encaminhamento e o prazo de resposta (48h).

**Exemplo completo (entrada e saída reais, copiadas de uma execução):**

> **Pendente.** Este exemplo precisa ser substituído pela cópia literal de uma execução real assim que o grupo configurar a `OPENAI_API_KEY` e rodar `python src/demo.py` — no momento em que este repositório foi montado, não havia uma chave da Mistral disponível para gerar uma execução de verdade, e a disciplina exige saída real, não inventada. Rode o comando, abra o arquivo gerado em `logs/01-caso-simples-*.json` e cole aqui a conversa (campo `historico`) e o resumo de término.

**O que o sistema não faz:**

- não decide trancamento de matrícula sozinho — todo pedido desse tipo é sempre encaminhado para a coordenação, mesmo que o aluno esteja em situação regular;
- não confia na palavra do aluno quando ela contradiz o sistema financeiro sem comprovante — nesse caso, sempre escala em vez de emitir;
- não emite nenhum documento fora dos dois do catálogo (declaração de matrícula, segunda via de histórico);
- quando não consegue confirmar o RA depois de uma segunda tentativa, não insiste indefinidamente — encaminha o caso e informa o aluno.

---

## Estrutura do repositório

```
docs/case.md          o tema, os usuários, o workflow, a justificativa de negócio
docs/modelos.md        a análise e a escolha do modelo
docs/fontes.md         tudo que foi consultado
prompts/               o system prompt do agente, versionado
src/dados.py           o "sistema acadêmico" simulado (SQLite)
src/agente.py          o laço do agente (estado, orçamento, ferramentas)
src/demo.py            roda os 4 casos de demonstração
src/verificador.py      roda os 40 casos rotulados
src/comparar_modelos.py roda a verificação mínima dos 3 modelos candidatos
dados/                  os dados simulados e os casos de teste
logs/                   as execuções gravadas (geradas ao rodar os scripts acima)
```

## Pendências antes da entrega final

- [ ] **Ativar o plano de uso na conta Mistral.** Uma chave já foi testada e é válida, mas a conta está com cota de requisições **zerada** (`x-ratelimit-limit-req-minute: 0` na resposta da API — ver `logs/README.md` para o diagnóstico completo). É preciso ativar o plano em admin.mistral.ai antes de qualquer chamada de chat funcionar.
- [ ] Depois disso, rodar `src/demo.py`, `src/verificador.py` e `src/comparar_modelos.py` e substituir os placeholders em `docs/modelos.md` §3.3 e neste README pelos resultados reais.
- [x] ~~Reconfirmar os preços da Mistral em `docs/modelos.md`~~ — feito em 22/09/2026, valores confirmados sem mudança (ver `docs/fontes.md`).
- [x] ~~Substituir a linha de base estimada de `docs/case.md` §2.5 por uma medição real~~ — decisão do grupo em 22/09/2026: sem acesso a uma secretaria real para cronometrar, a linha de base continua como **estimativa declarada** (a ressalva já está escrita em `case.md` §2.5, que é a resposta válida quando a medição real não é possível). Se o grupo conseguir acesso real depois, atualizar com a fonte da medição.
