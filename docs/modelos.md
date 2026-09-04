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

> Preços conforme documentados no material da disciplina (`aula02-modelos-e-parametros/06-benchmark-modelos.py`). **Preço de LLM muda** — antes de fechar a decisão final, reconfirme em `https://mistral.ai/pricing` e anote a data da consulta aqui.

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
