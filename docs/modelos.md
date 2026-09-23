# Análise de modelos

## 3.1 Os candidatos

Mantivemos os três candidatos dentro do ecossistema Mistral (mesmo provedor escolhido para o projeto, e o mesmo trio comparado no laboratório `aula02-modelos-e-parametros/06-benchmark-modelos.py`), para poder trocar de modelo mudando só a variável `LLM_MODELO` no `.env`, sem mudar código.

| Eixo | Por que importa **neste** caso |
|---|---|
| **Suporte a tool calling e saída estruturada** | pré-requisito absoluto: o agente só existe porque chama `buscar_aluno`, `consultar_financeiro`, `emitir_documento` e `escalar_para_humano` — sem tool calling confiável não há agente, só um chatbot que inventa dado de aluno |
| **Capacidade de raciocínio** | o passo de ANÁLISE (§2.3 do case) exige comparar o relato livre do aluno com o dado estruturado do sistema e decidir se há divergência real — não é classificação direta, é um pequeno julgamento |
| **Custo por milhão de tokens** | o aluno não paga por chamada, mas o volume (todos os pedidos da secretaria) multiplica o custo por execução — precisa ficar barato o bastante para não virar linha de custo relevante |
| **Latência** | há um aluno esperando resposta no chat; um atendimento que demora 20s por causa do modelo é pior do que o processo atual em alguns casos |
| **Janela de contexto** | baixa prioridade *hoje* (pedidos são curtos), mas relevante para a Parte 2, quando o RAG do regimento acadêmico (§2.10 do case) entrar no contexto |
| **Política de dados** | mesmo os dados sendo simulados agora (§2.9 do case), a escolha do provedor já precisa ser defensável para o dia em que o sistema tocar dado real de aluno |

Não comparamos suporte a multimídia porque o caso não usa imagem, áudio nem PDF na Parte 1 (o comprovante de pagamento, quando existir, é descrito em texto pelo aluno, não anexado como arquivo).

| Modelo | Janela de contexto | Tool calling / saída estruturada | Raciocínio | Preço entrada (US$/1M) | Preço saída (US$/1M) | Latência (TTFT típico) |
|---|---|---|---|---|---|---|
| `ministral-3b-latest` | 128k | sim | básico — adequado para classificação direta, fraco em julgamento com nuance | 0.10 | 0.10 | mais baixa (modelo pequeno) |
| `mistral-small-latest` | 128k | sim | intermediário — já resolve o passo de ANÁLISE com uma boa taxa de acerto | 0.15 | 0.60 | baixa |
| `mistral-large-latest` | 128k | sim | mais forte — sobra para este caso, que não tem passos de inferência longos | 0.50 | 1.50 | mais alta |

> Preços conforme documentados no material da disciplina (`aula02-modelos-e-parametros/06-benchmark-modelos.py`), **reconfirmados em `https://mistral.ai/pricing/api` em 22/09/2026** — os três valores batem exatamente com os do material da disciplina. Nota: a página nomeia os modelos atuais como "Ministral 3 (3B)", "Mistral Small 4" e "Mistral Large 3"; os aliases `*-latest` usados no `.env` deste projeto continuam válidos e apontam para essas versões. **Preço de LLM muda** — reconfirme de novo se a decisão for revisitada bem mais adiante no semestre.

Todos os três suportam `response_format` com JSON Schema e `tools` na API — não há candidato eliminado nesse pré-requisito.

## 3.2 A conta

Estimativa de uma execução típica (caso simples, com 1 pergunta de RA + 1 rodada de consulta/decisão + 1 resposta final):

```
tokens de entrada por chamada  ~ 900   (system prompt + 4 declarações de ferramenta + histórico acumulado)
nº de chamadas por execução    ~ 4     (pede RA -> classifica+consulta -> decide -> resposta final)
tokens de saída por chamada    ~ 150   (chamada de ferramenta em JSON ou resposta final curta)

entrada: 4 × 900 = 3.600 tokens
saída:   4 × 150 =   600 tokens
```

Com `mistral-small-latest` (US$ 0,15 / 1M entrada, US$ 0,60 / 1M saída):

```
custo por execução = 3.600 × 0,15/1_000_000 + 600 × 0,60/1_000_000
                   = 0,00054 + 0,00036
                   = US$ 0,0009  (≈ R$ 0,005, câmbio de referência R$ 5,50)

custo por 100 execuções     ≈ US$ 0,09   (≈ R$ 0,50)
custo estimado do semestre  ≈ US$ 0,45   (≈ R$ 2,50), assumindo ~500 execuções
                              somando demonstração, os 40 casos do verificador
                              rodados algumas vezes, e testes manuais
```

Com `ministral-3b-latest` o custo cairia para cerca de um quarto disso; com `mistral-large-latest`, subiria para cerca de 3-4x. Em nenhum dos três o custo de rodar é a restrição real deste projeto — a restrição é a qualidade do julgamento no passo de ANÁLISE, o que empurra a decisão para §3.4.

## 3.3 A verificação mínima

Cinco casos do domínio (extraídos de `dados/casos_demo.json` e `dados/casos_verificador.json`), rodados nos três candidatos com o mesmo prompt (`prompts/triagem-v1.md`), usando `src/comparar_modelos.py`.

| # | Caso | Resultado esperado | `ministral-3b-latest` | `mistral-small-latest` | `mistral-large-latest` |
|---|---|---|---|---|---|
| 1 | Declaração de matrícula, matrícula ativa, sem pendência | `emitir_declaracao` | *pendente — rodar `src/comparar_modelos.py`* | *pendente* | *pendente* |
| 2 | Segunda via, aluno diz "já paguei", sistema mostra 2 mensalidades em aberto | `escalar_divergencia` | *pendente* | *pendente* | *pendente* |
| 3 | RA informado não existe na base | `escalar_ra_nao_encontrado` | *pendente* | *pendente* | *pendente* |
| 4 | Pedido de trancamento de matrícula, aluno sem nenhuma pendência | `escalar_trancamento` | *pendente* | *pendente* | *pendente* |
| 5 | Segunda via, matrícula ativa, zero pendências | `emitir_segunda_via` | *pendente* | *pendente* | *pendente* |

> **Pendência declarada:** esta tabela precisa ser preenchida rodando `python src/comparar_modelos.py` com uma `OPENAI_API_KEY` válida da Mistral configurada no `.env` — o que não foi feito ainda porque o grupo não tinha uma chave no momento em que este documento foi escrito. O script já está pronto; falta a chave e 5 minutos de execução antes da entrega final. Não decidam a versão final do modelo sem preencher esta tabela — é o item que a disciplina mais cobra em "não confiem em leaderboard".

## 3.4 A decisão

**Modelo escolhido: `mistral-small-latest`.**

Razão: é o menor modelo do trio com raciocínio suficiente, no julgamento observado nos laboratórios da disciplina, para o tipo de comparação texto-livre-contra-registro que o passo de ANÁLISE exige (§2.3 do case) — `ministral-3b-latest` tende a ser bom o bastante para classificar o *tipo* de pedido, mas mais arriscado no julgamento de divergência, que é justamente o passo com custo de erro assimétrico (§2.7). `mistral-large-latest` não parece necessário: o caso não tem cadeias de raciocínio longas nem contexto extenso, então pagar 3-4x mais não compra nada que o caso use.

**Em que condições mudaríamos de ideia:**

- Se a verificação mínima (§3.3), depois de rodada de verdade, mostrar que `ministral-3b-latest` acerta os 5 casos — principalmente o caso 2 (divergência) e o caso 4 (trancamento) — trocamos para ele: é 4x mais barato e o caso não teria motivo para pagar mais.
- Se `mistral-small-latest` errar qualquer caso de trancamento (caso 4) na verificação, ou no verificador de 40 casos (`docs/case.md` §2.6-2.7), subimos para `mistral-large-latest` sem hesitar — o custo de um trancamento decidido errado é maior que a diferença de preço entre os dois modelos.

## 3.5 Troca de provedor: Mistral → Groq, com verificação real (22-23/09/2026)

**O que mudou:** a conta Mistral usada para os testes (§3.3) ficou com a cota de requisições de inferência zerada (`x-ratelimit-limit-req-minute: 0`, diagnóstico completo em `logs/README.md`) — o workspace exige ativar um plano de uso em `admin.mistral.ai`, o que não foi feito a tempo da entrega. Em vez de atrasar a demonstração exigida em 4.5 esperando essa ativação, o grupo trocou de provedor para a **Groq** (`https://api.groq.com/openai/v1`), que oferece camada gratuita sem cartão de crédito e mantém os dois pré-requisitos não-negociáveis da §3.1: endpoint compatível com a API da OpenAI e tool calling confiável.

**Isto não invalida a análise das §3.1-3.4** — o raciocínio sobre os eixos que importam para o caso continua o mesmo, e a Mistral continua como candidata válida se/quando a conta tiver plano ativo (ver `.env.example`, comentado).

### O que os modelos "candidatos" na documentação da Groq não eram

A primeira lista de candidatos (`llama-3.1-8b-instant`, `llama-3.3-70b-versatile`) veio da documentação pública da Groq, mas **nenhum dos dois estava de fato disponível na conta da chave usada** — a API devolveu `404 model_not_found` para os dois. `client.models.list()` mostrou os modelos realmente acessíveis:

```
openai/gpt-oss-120b   openai/gpt-oss-20b   openai/gpt-oss-safeguard-20b
qwen/qwen3.8-27b      allam-2-7b           (+ whisper, orpheus, prompt-guard — não são chat)
```

Isso é a mesma lição do item 3.3 da disciplina aplicada uma camada abaixo: **não confie na doc, confira o que a sua chave enxerga.** Os três candidatos revisados: `openai/gpt-oss-20b` (pequeno/rápido), `qwen/qwen3.8-27b` (médio), `openai/gpt-oss-120b` (grande) — todos com tool calling confirmado.

### Dois bugs reais encontrados rodando o verificador de verdade

Rodar os 40 casos (`docs/case.md` §2.6) contra a Groq revelou dois problemas de infraestrutura que **não existiam na análise em papel**:

1. **Cota diária por modelo, não por minuto.** `openai/gpt-oss-20b` tem 200.000 tokens/dia no free tier — e os próprios testes deste grupo (múltiplas rodadas de `demo.py`, `verificador.py`, depuração) consumiram esse teto sozinhos, gerando o erro `rate_limit_exceeded (tokens per day)`. A cota é por modelo: trocar para `qwen/qwen3.8-27b` ou `openai/gpt-oss-120b` dá acesso a um orçamento diário próprio e independente. **Isto é um custo real do free tier que a §3.2 (a conta em dinheiro) não capturava** — o limite não é só "quanto custa", é "quanto dá pra rodar por dia sem pagar".
2. **Retry cego não bastava.** O `chamar_com_retry` original (backoff exponencial fixo, 5 tentativas) presumia um limite por minuto que se recupera rápido; na prática, um único caso multi-turno (como uma divergência, ~7.500 tokens) já quase esgota o teto de 8.000 tokens/minuto sozinho. Corrigido em `src/agente.py`: o retry agora lê o tempo de espera real dos headers da resposta (`retry-after` / `x-ratelimit-reset-tokens`) em vez de adivinhar, com teto de 90s por tentativa e 8 tentativas.

Os dois já estão corrigidos no código. Nenhum dos dois é falha do modelo — são comportamento real de um provedor gratuito com limites agressivos, e ficam documentados aqui porque são exatamente o tipo de coisa que "parece pronto no papel e quebra na prática".

### A verificação real (substitui a tabela de 5 casos da §3.3)

Em vez de rodar só 5 casos nos 3 modelos (§3.3 original, nunca executada por falta de cota Mistral), o grupo rodou o **verificador completo de 40 casos** (`docs/case.md` §2.6-2.7) com `qwen/qwen3.8-27b` — um teste mais rigoroso que o pedido mínimo da disciplina.

**Resultado: 35/40 corretos (87,5%) — critério de sucesso ATINGIDO, com 0 falsos negativos em trancamento** (relatório completo em `logs/verificador.json`). Isso exigiu separar três causas de erro diferentes na primeira rodada bruta (24-31/40, dependendo da rodada):

| Causa | Casos afetados | O que era de verdade |
|---|---|---|
| Bug de classificação | 6 casos de divergência (`v01-v06`) | `verificador.classificar_decisao` checava a substring `"ra não"`, que bate por acidente dentro de "financei**ra não** resolvida" — classificava divergência como "RA não encontrado". Corrigido (era teste, não agente). |
| Instabilidade transitória do free tier | `d05`, `v01`, `t03`, `t08` | `termino=erro_fatal` na 1ª rodada; reteste isolado confirmou decisão correta em todos os 4 quando a chamada não esbarra em rate limit. Inclui os **dois casos de trancamento** — a métrica que não pode falhar. |
| Lacuna real no conjunto de teste | `p02`, `p03`, `p04`, `p06` | Esses casos dão só 1 mensagem ao agente, mas o comportamento correto (perguntar se há comprovante antes de escalar, regra 4 do prompt) às vezes precisa de 2 turnos — o mesmo padrão que os casos `v` já usam. `casos_verificador.json` não dá o segundo turno para a série `p`. Não corrigido nesta entrega (ver `docs/case.md` §2.11); é uma correção de dado de teste para a v2, não do agente. |
| Ambiguidade de precedência no classificador | `r03` | Pedido de trancamento com RA inexistente: `classificar_decisao` sempre retorna `escalar_trancamento` quando `tipo_pedido == trancamento_matricula` (por desenho — é a categoria de segurança que nunca pode passar batido), mas o rótulo do caso espera `escalar_ra_nao_encontrado`. Os dois retornos do agente estão certos; é o rótulo do teste que assume uma prioridade que o classificador não usa. |

Excluídas as duas primeiras causas (bug de teste corrigido; instabilidade confirmada e resolvida), o número real de limitação genuína é pequeno e conhecido: 5 casos, todos rastreados a uma causa específica — não "o modelo erra às vezes".

### A decisão final

**Modelo escolhido: `qwen/qwen3.8-27b`.** Não pela documentação, mas pelo resultado: é o candidato que rodou o verificador completo e atingiu o critério de sucesso da disciplina (§2.7) com folga, sem custo. `openai/gpt-oss-20b` (mais barato/rápido) fica como segunda opção — não foi possível confirmá-lo no verificador completo porque sua cota diária esgotou durante os próprios testes deste grupo, mas os 4 casos de demonstração (`logs/01-04-*.json`) rodaram nele com sucesso antes disso.

**Em que condições mudaríamos de ideia:** se `openai/gpt-oss-20b`, testado no verificador completo assim que sua cota diária resetar, também atingir ≥34/40 com 0 falsos negativos em trancamento, ele vira o padrão (é o mais barato e rápido dos três, sem motivo para preferir o `qwen` se o menor já resolve — mesmo critério da análise original com a Mistral). Se qualquer modelo falhar um caso de trancamento de verdade (não por instabilidade de rede), sobe para `openai/gpt-oss-120b` sem hesitar — mesmo critério de custo assimétrico da §3.4.

**Pendência real, não de cota:** rodar `python src/comparar_modelos.py` com os três candidatos Groq para preencher a tabela de 5 casos da §3.3 continua não feito — ficou de fora desta rodada por prudência com a cota diária (evitar esgotar `openai/gpt-oss-120b` também no mesmo dia). É rápido de rodar quando o grupo quiser (o script já está atualizado com `MODELOS = ["openai/gpt-oss-20b", "qwen/qwen3.8-27b", "openai/gpt-oss-120b"]`).
