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
# edite .env e cole sua chave da Groq em OPENAI_API_KEY
# (crie a chave em https://console.groq.com/keys — free tier, sem cartão)
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
| `python src/comparar_modelos.py` | roda 5 casos nos 3 modelos candidatos, para preencher `docs/modelos.md` §3.5 |

> O agente roda por padrão na **Groq**, modelo `qwen/qwen3.8-27b` (free tier, `docs/modelos.md` §3.5 — 35/40 no verificador, 0 falsos negativos em trancamento) — a análise original comparando os três modelos Mistral (§3.1-3.4) continua no repositório e pode ser reativada trocando as três variáveis comentadas no fim do `.env.example`.

**O que a pessoa digita:** uma mensagem em português descrevendo o pedido — com ou sem o RA já incluído. Exemplo: *"Preciso de uma declaração de matrícula. Meu RA é 20231045."* ou, em partes, *"Oi, preciso de uma declaração de matrícula pra levar no estágio."* seguido de *"20231045"* quando o agente perguntar.

**O que o sistema faz com aquilo:** identifica o tipo de pedido e o RA, consulta o sistema acadêmico simulado (cadastro + financeiro, em SQLite), e decide — segundo as regras de `docs/case.md` §2.1 — se emite o documento na hora ou encaminha o caso para a secretaria humana.

**Que saída ela recebe:** texto em português. Se aprovado: o protocolo do documento (`DOC-xxxx`) e o texto da declaração/segunda via. Se escalado: o protocolo do caso (`CASO-xxxx`), o motivo do encaminhamento e o prazo de resposta (48h).

**Exemplo completo (entrada e saída reais, copiadas de [`logs/01-caso-simples-695426dc.json`](logs/01-caso-simples-695426dc.json)):**

> **Aluno:** Oi, preciso de uma declaração de matrícula pra levar no estágio.
>
> **Agente:** Olá! Para emitir a declaração de matrícula, preciso confirmar seu número de RA. Poderia me informar, por favor?
>
> **Aluno:** 20231045
>
> **Agente:**
> **Protocolo:** DOC‑1002
> **Documento emitido:** Declaração de Matrícula
>
> > *Declaração de Matrícula*
> >
> > Eu, responsável pela Secretaria Acadêmica, certifico que o aluno Weslley Sousa, RA 20231045, está regularmente matriculado no curso de Análise e Desenvolvimento de Sistemas (ADS) e encontra-se em situação ativa.
> >
> > Esta declaração é válida para fins de comprovação de matrícula em estágio.
>
> Caso precise de mais alguma coisa, estou à disposição.

Término: `respondeu` · 4.263 tokens gastos · modelo `openai/gpt-oss-20b` (Groq). Os outros 3 casos exigidos (divergência, RA inexistente, trancamento) estão em `logs/02-*.json` a `logs/04-*.json`.

**O que o sistema não faz:**

- não decide trancamento de matrícula sozinho — todo pedido desse tipo é sempre encaminhado para a coordenação, mesmo que o aluno esteja em situação regular;
- não confia na palavra do aluno quando ela contradiz o sistema financeiro sem comprovante — nesse caso, sempre escala em vez de emitir;
- não emite nenhum documento fora dos dois do catálogo (declaração de matrícula, segunda via de histórico);
- quando não consegue confirmar o RA depois de uma segunda tentativa, não insiste indefinidamente — encaminha o caso e informa o aluno.

## Exercício 7 — RAG sobre o Regimento Acadêmico

Complementar (Aula 07), sobre um Regimento Acadêmico **simulado**. Relatório completo em [`exercicios/aula-07-resposta-que-cita.md`](exercicios/aula-07-resposta-que-cita.md).

```bash
python src/indice_rag.py    # gera o índice (baixa o modelo de embedding na 1ª vez, ~470MB)
python src/avaliar_rag.py   # recall@k, fidelidade, citação verificável, varredura do limiar
python src/modos_de_falha.py  # reproduz os 4 modos de falha + teste de corpus desatualizado
```

Resultado: recall@k 100%, citações verificáveis 100%, fidelidade 80%, 0 recusas indevidas.

## Exercício 8 — Memória do agente de triagem

Complementar (Aula 08): episódica, semântica e procedural, com idempotência, desempate de contradição por carimbo de tempo, decaimento e esquecimento seletivo verificado. Decisão de projeto em [`docs/memoria.md`](docs/memoria.md); relatório da implementação em [`exercicios/aula-08-memoria-do-case.md`](exercicios/aula-08-memoria-do-case.md).

```bash
python src/memoria_demo.py   # roda tudo: fronteira, idempotência, contradição, não reprodutibilidade, esquecimento
```

Resultado: memória muda a resposta do agente para a mesma pergunta (não reprodutibilidade real, medida); remoção de titular só ficou completa depois de verificar — a primeira passada deixou vestígio num checkpoint.

---

## Estrutura do repositório

```
docs/case.md          o tema, os usuários, o workflow, a justificativa de negócio
docs/modelos.md        a análise e a escolha do modelo
docs/fontes.md         tudo que foi consultado
docs/base-de-conhecimento-v1.md  o plano da base de RAG (Exercício 6)
prompts/               o system prompt do agente, versionado
src/dados.py           o "sistema acadêmico" simulado (SQLite)
src/agente.py          o laço do agente (estado, orçamento, ferramentas)
src/demo.py            roda os 4 casos de demonstração
src/verificador.py      roda os 40 casos rotulados
src/comparar_modelos.py roda a verificação mínima dos 3 modelos candidatos
dados/                  os dados simulados e os casos de teste
logs/                   as execuções gravadas (geradas ao rodar os scripts acima)

# Exercício 7 — RAG sobre o Regimento Acadêmico (exercicios/aula-07-*.md)
dados/regimento_dados.py   o Regimento Acadêmico simulado (15 artigos)
dados/casos_rag.json       perguntas rotuladas do RAG (recall/fidelidade/recusa)
src/chunking.py            corte por estrutura (1 chunk por artigo)
src/indice_rag.py          índice de embeddings local (sentence-transformers, sem banco vetorial)
src/rag.py                 pipeline: recuperar -> contexto -> gerar, citação verificável, portão de recusa
src/avaliar_rag.py         recall@k, fidelidade, varredura do limiar
src/modos_de_falha.py      reproduz os 4 modos de falha + corpus desatualizado
exercicios/aula-07-resposta-que-cita.md  o relatório do Exercício 7

# Exercício 8 — Memória do agente (exercicios/aula-08-*.md, docs/memoria.md)
src/memoria_episodica.py   índice vetorial de episódios passados, por RA, com decaimento
src/memoria_semantica.py   chave-valor idempotente, com campo `substituiu`
src/memoria_procedural.py  regras aprendidas de erro, com aprovação humana
src/memoria.py             orçamento de janela, remoção sob solicitação com verificação
src/memoria_demo.py        roda a demonstração completa
docs/memoria.md                          a decisão de projeto (avaliada na Parte 2)
exercicios/aula-08-memoria-do-case.md    o relatório da implementação
```

## Pendências antes da entrega final

- [x] ~~Ativar o plano de uso na conta Mistral~~ — a conta Mistral ficou com cota zerada (diagnóstico em `logs/README.md`) e ativar exigia cadastrar pagamento; o grupo trocou o provedor padrão para **Groq** (free tier, sem cartão — ver `docs/modelos.md` §3.5), que resolve o mesmo requisito de tool calling sem esse bloqueio.
- [x] ~~Criar uma chave gratuita, rodar `demo.py` e `verificador.py` de verdade~~ — feito em 22-23/09/2026: os 4 casos de demonstração estão em `logs/01-*.json` a `logs/04-*.json`, e o verificador completo (40 casos) atingiu **35/40 (87,5%), 0 falsos negativos em trancamento** — critério de sucesso do `case.md` §2.7 atingido (relatório em `logs/verificador.json`, diagnóstico completo em `docs/modelos.md` §3.5, incluindo dois bugs de infraestrutura encontrados e corrigidos no caminho).
- [ ] **Rodar `python src/comparar_modelos.py`** para preencher a tabela de 5 casos × 3 modelos da §3.3/3.5 — adiado por prudência com a cota diária da Groq (o candidato `openai/gpt-oss-20b` já esgotou seu teto de 200k tokens/dia só com os testes deste grupo; ver `docs/modelos.md` §3.5). Rodar quando a cota resetar.
- [x] ~~Reconfirmar os preços da Mistral em `docs/modelos.md`~~ — feito em 22/09/2026, valores confirmados sem mudança (ver `docs/fontes.md`).
- [x] ~~Substituir a linha de base estimada de `docs/case.md` §2.5 por uma medição real~~ — decisão do grupo em 22/09/2026: sem acesso a uma secretaria real para cronometrar, a linha de base continua como **estimativa declarada** (a ressalva já está escrita em `case.md` §2.5, que é a resposta válida quando a medição real não é possível). Se o grupo conseguir acesso real depois, atualizar com a fonte da medição.
