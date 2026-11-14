# Observabilidade

O plano do que se precisa saber sobre o sistema **enquanto ele roda**, e a instrumentação que o cumpre. O plano vem antes, porque é ele que decide o que instrumentar. Código: [`src/triagem/telemetria.py`](../src/triagem/telemetria.py) (o trace), [`evals/metricas.py`](../evals/metricas.py) (as métricas lidas do trace) e [`evals/reconstruir.py`](../evals/reconstruir.py) (a decisão reconstruída só pelo trace). Testes: [`tests/test_telemetria.py`](../tests/test_telemetria.py) (18).

## 0. Como ver os traces

O trace é **desligado por padrão** (sem configuração, o tracer é *no-op* do OpenTelemetry: instrumentar não custa nada a quem não liga). Para ligar:

```bash
export TRIAGEM_TRACES_DIR=logs/traces            # o Sistema grava <pasta>/traces.jsonl, um span por linha
python src/chat.py --dica --ra 20231045           # converse; cada turno vira um trace

python -m evals.metricas logs/traces/traces.jsonl --slo 0.95                      # p50/p95, tokens, término, SLI
python -m evals.reconstruir logs/traces/traces.jsonl --conversa <thread_id>       # a decisão, só pelo trace
jq 'select(.name | startswith("execute_tool"))' logs/traces/traces.jsonl           # ou direto, com jq
```

Na imagem Docker o destino é `/dados/traces` (`TRIAGEM_TRACES_DIR`), no volume. As rodadas da suíte (`python -m evals.rodar`) gravam o `traces.jsonl` na pasta da própria rodada. **Destino consultável:** arquivo JSONL (`grep`, `jq` e `evals/metricas.py` leem o mesmo); um *collector* OTLP seria o passo seguinte e **não está implementado** (nenhuma plataforma de observabilidade foi ligada: não havia onde, e não declaro que há).

## 1. As quatro perguntas

Uma por interessado, cada uma com **a decisão que a resposta muda**.

| Interessado | Pergunta | Decisão que a resposta muda | Sinal que a responde |
|---|---|---|---|
| **o negócio** | A fração das execuções **resolvidas sem atendente** (decisão `emitir_*` ou `responder_regimento`) está em **60% ou mais** (a promessa de `docs/case.md` §2.5), **e** todo trancamento e toda divergência continuam indo à secretaria? | manter o agente, ampliar o que ele decide sozinho, ou recuar | `agente.decisao` por `agente.versao`; a segunda metade é uma regra de **auditoria**: `agente.decisao = emitir_*` com pendência no retorno de `consultar_financeiro` do mesmo trace deve ser **zero** |
| **a operação** | Quantas execuções terminaram **sem decisão** (orçamento esgotado, laço, erro fatal, ou **contingência**) na última hora, **em que versão**? | investigar e, se a piora começou com uma mudança, **reverter a versão no ar** | `agente.termino` e `agente.contingencia`, cortados por `agente.versao` |
| **quem paga** | Quantos **tokens** custa uma execução, e o que domina: o prompt e as declarações de ferramenta reenviados a cada volta, ou o histórico? | encurtar o prompt (a regra da frase, `docs/prompts.md` §5), o retorno das ferramentas, ou rever o orçamento de passos | `gen_ai.usage.input_tokens` e `output_tokens` por span `chat`; `agente.chamadas_modelo` |
| **quem responde pelo sistema** | Alguma **escrita** aconteceu sem consulta prévia, **para um RA diferente do autenticado**, ou **duas vezes**? Alguém **tentou** ler o dado de outro aluno? | **suspender a escrita** (aprovação humana obrigatória), revisar as permissões e abrir auditoria dos casos afetados | spans `execute_tool` com `agente.ferramenta.recusada`; escrita sem `buscar_aluno` antes **no mesmo trace**; mais de um `emitir_documento` por trace |

*Perguntas que ficaram de fora:* "quantas vezes por dia `consultar_regimento` é chamada?" Nenhuma decisão muda com a resposta.

**A pergunta de quem responde pelo sistema só é respondível agora.** No Exercício 15 ela era "alguma conversa consultou o financeiro de um RA que não era o de quem perguntava?" e o sistema **não conseguia responder**, porque não sabia quem perguntava. Com `ra_autenticado` na sessão (ASI03) e a **tentativa recusada** registrada no span, ela virou uma consulta ao trace.

## 2. O trace de uma execução

Uma raiz por **turno** do aluno. Uma conversa de vários turnos tem vários traces, ligados por `gen_ai.conversation.id` (o `thread_id`). A aprovação da coordenação é **um trace próprio** (`agente.retomada = true`), ligado à mesma conversa. Árvore de uma execução típica (emissão de declaração), **gerada pelo código com o modelo roteirizado** (`tests/test_telemetria.py::test_a_arvore_de_spans_de_uma_execucao`), e não por uma execução real:

```text
invoke_agent triagem-secretaria
├── chat qwen/qwen3.8-27b
├── execute_tool buscar_aluno
├── chat qwen/qwen3.8-27b
├── execute_tool emitir_documento
├── chat qwen/qwen3.8-27b
```

**Os atributos da convenção GenAI** (a plataforma já os entende):

| Span | Atributos |
|---|---|
| raiz `invoke_agent triagem-secretaria` | `gen_ai.operation.name`, `gen_ai.agent.name`, `gen_ai.provider.name`, `gen_ai.conversation.id` |
| `chat <modelo>` | `gen_ai.request.model`, `gen_ai.response.model` (o modelo **servido**: o provedor pode trocá-lo sob o mesmo nome), `gen_ai.request.temperature`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`, `gen_ai.response.finish_reasons` |
| `execute_tool <ferramenta>` | `gen_ai.tool.name`, `gen_ai.tool.call.id`, `gen_ai.tool.type`, `gen_ai.tool.call.arguments`, `gen_ai.tool.call.result` |

**Os atributos próprios na raiz**, que a convenção não tem:

| Atributo | Valores | Para que serve |
|---|---|---|
| **`agente.termino`** | `respondeu`, `aguardando_humano`, `orcamento_esgotado`, `laco_detectado`, `erro_fatal`, `recusado_identidade`, `conversa_encerrada`, `vencido` | separa a execução que **acabou bem** da que **parou no meio**. O aluno recebe uma resposta nos dois casos; só este atributo os distingue. É a base do SLO. A taxonomia é a da Aula 05, com `aguardando_humano` separado de `respondeu` |
| **`agente.versao`** | `<commit>/p-<sha8 do prompt>/<modelo>` (ex.: `57d5fa1/p-6df71c6c/qwen/qwen3.8-27b`) | corta **toda** métrica por versão. Código, prompt e modelo mudam de forma independente (o prompt sem implantação, o modelo por variável); a versão só do código não separaria o antes e o depois de nenhuma dessas mudanças |
| `agente.decisao`, `agente.suficiente`, `agente.protocolo` | o rótulo da decisão (`docs/io.md`), a suficiência, o protocolo | a decisão que a execução tomou, sem ler o texto |
| `agente.contingencia`, `agente.correcoes` | bool, int | a resposta saiu do molde (o validador reprovou duas vezes), e quantas voltas de correção houve |
| `agente.contexto_recuperado` | os artigos que `consultar_regimento` devolveu | o contexto que sustentou a resposta |
| `agente.identidade`, `agente.modelo_aprovado` | bool | a sessão estava autenticada; o modelo está na lista aprovada |
| `agente.ferramenta.recusada`, `.erro`, `.origem` | bool, texto, `codigo` | a chamada foi **recusada por um controle** (ASI02, ASI03); o erro; e, quando a escrita foi feita **pelo código** (a pós-condição L02), a origem |

**O trace é também o registro da decisão.** Além dos atributos acima, a raiz tem a **entrada** (`gen_ai.user.message`) e a **saída** (`gen_ai.choice`) como eventos, e cada `execute_tool` carrega os **argumentos e o resultado**. A aprovação humana (quem, quando, o quê) está no trace de retomada. Isso é o que o campo Registro do model card usa para **reconstruir uma decisão** ([`evals/reconstruir.py`](../evals/reconstruir.py); o exemplo está em `docs/model-card.md`).

## 3. Os modos de falha

Cada um com o **sinal que o torna visível**. As duas colunas separam as falhas **ruidosas** (derrubam algo e aparecem) das **silenciosas** (o aluno recebe uma resposta, a taxa de erro não se mexe).

| Componente | Falha | Ruidosa ou silenciosa | Sinal |
|---|---|---|---|
| nó `agente` e validador | a resposta do modelo é reprovada **duas vezes** e sai do **molde de contingência** ("Não consegui concluir..."): o aluno recebe uma resposta, o sistema não resolveu | **silenciosa** | proporção de `agente.contingencia = true`, por `agente.versao` |
| laço e orçamento | o agente esgota o orçamento de passos, tokens ou tempo, ou entra em laço, e devolve a mensagem de "não consegui concluir" | **silenciosa** (resposta devolvida com sucesso) | proporção de `agente.termino ∈ {orcamento_esgotado, laco_detectado}`, por versão |
| modelo + prompt | o modelo **não escala o trancamento** e o **código** abre o caso (a pós-condição L02): o resultado é certo, mas **o modelo errou** e o sistema o escondeu | **silenciosa** | span `execute_tool escalar_para_humano` com `agente.ferramenta.origem = codigo`: **taxa de correção pelo código** |
| provedor do modelo | o provedor serve **outro modelo** sob o mesmo nome (sem versão datada: lacuna L13 do model card) | **silenciosa** | `gen_ai.response.model` ≠ `gen_ai.request.model` (`evals.metricas`: "servido diferente do pedido") |
| provedor do modelo | indisponibilidade, limite de taxa, **cota diária** (aconteceu: 18/10 e 11/11/2026) | **ruidosa** | `chat` com `error.type = erro_fatal` e `agente.termino = erro_fatal` |
| controles de segurança | alguém **tenta** ler ou escrever o RA de outro aluno | **silenciosa** (a ferramenta recusa e o aluno recebe "só posso atender o seu RA") | `execute_tool` com `agente.ferramenta.recusada = true` e erro "ra diferente do aluno autenticado": **cada ocorrência é uma tentativa de ataque** |

## 4. As métricas, sobre execuções reais

As quatro, com **corte por versão** (um número que mistura versões soma sistemas diferentes): **latência p50 e p95** (não a média; percentil por posto mais próximo, com o `n` impresso junto), **custo por execução**, a **distribuição dos motivos de término** e a **taxa de erro por ferramenta**.

**Custo:** o sistema roda no *free tier* da Groq, onde o preço registrado em `agente.PRECOS` é **zero** (lacuna L04 do model card), então o custo em US$ é **zero e não informa nada**. O que informa é o **consumo de tokens**, que é o que a cota limita e o que um preço pago multiplicaria. As métricas reportam tokens por execução (média e p95).

<!-- BLOCO:metricas -->
**PENDENTE.** Exigem **ao menos trinta execuções reais** com o trace ligado, e o sistema ainda não as tem: a rodada B da suíte (37 casos) as produzirá, mas a cota diária do `qwen/qwen3.8-27b` acabou antes (`docs/evals.md` §4). Quando existir, `python -m evals.atualizar_docs --traces evals/resultados/2026-11-11-B-r1/traces.jsonl --slo 0.95` cola aqui a saída **real** de `python -m evals.metricas`. Nenhum número desta seção é digitado à mão.
<!-- /BLOCO:metricas -->

**As quatro perguntas respondidas com esses números:** **PENDENTE**, pelo mesmo motivo. O que dá para dizer agora é **qual sinal responde a cada uma** (a última coluna do §1) e que todos eles **existem no trace** (testados em `tests/test_telemetria.py`). Uma pergunta que os sinais implementados não respondem é lacuna do plano ou da instrumentação: **a do negócio, na parte "decisão com pendência no retorno do financeiro"**, é uma regra de auditoria sobre o trace que **ainda não está implementada** em `evals.metricas` (o sinal existe, o cálculo não).

## 5. O objetivo: SLI e SLO

- **SLI** (a medida): a razão entre execuções **boas** e execuções **válidas**.
  - **Válida:** um turno em que o sistema **tentou decidir**: `agente.chamadas_modelo >= 1`, e `agente.termino ≠ recusado_identidade`. A saudação, o turno de espera da coordenação e a recusa de identidade **não** entram (não decidem nada).
  - **Boa:** `agente.termino ∈ {respondeu, aguardando_humano}` **e** `agente.contingencia = false`.
  - **De onde sai:** da raiz `invoke_agent` do trace, nada mais (`evals.metricas.valida` e `.boa`).
- **SLO:** **≥ 95%** das execuções válidas são boas, em janela de **7 dias**. O **orçamento de erro** é os 5% restantes: de cada 100 execuções, até 5 podem terminar mal sem violar o objetivo.
- **Por que este SLO:** é o de **qualidade**, e cobre a **degradação silenciosa**: execuções que terminam por orçamento esgotado ou por contingência **não dão erro**, a resposta é devolvida, e a taxa de erro não se mexe. Só um objetivo sobre o **motivo de término** as torna visíveis. Um SLO de disponibilidade (HTTP 200) não pegaria nada disso.
- **Por que 95%:** sem dado de produção, o alvo é uma **hipótese**. As 8 execuções reais da Parte 2 deram 8 de 8 boas, e 5% deixa folga para a variação do provedor; mas **8 execuções não sustentam um alvo**, e o valor deve ser revisto com as trinta.

**Valor medido, e o orçamento de erro consumido:** no bloco do §4 (PENDENTE). **Se o SLO estiver violado nas execuções medidas, o documento dirá isso e o que fariam: um objetivo violado e reportado é um resultado; um objetivo ajustado ao valor medido, para passar, não é objetivo.**

## 6. O que fica fora da telemetria, e a retenção

- **Dado pessoal.** Os atributos de conteúdo (`gen_ai.user.message`, `gen_ai.choice`, argumentos e resultados das ferramentas) carregam **RA, nome, valor em aberto**. Por padrão estão **ligados**, porque o trace é o registro da decisão (docs/model-card.md) e os dados de hoje são sintéticos. **Com dado real:** `AGENTE_TRACE_CONTEUDO=0` os desliga (o trace fica só com a estrutura e as métricas, e **deixa de servir para reconstruir uma decisão**), e o trace herda a classificação do dado que carrega (`docs/seguranca.md` §5).
- **Prazo de guarda: 90 dias** (decisão de 13/11/2026, Weslley Soares de Sousa pelo grupo). Spans com mais de 90 dias e registros da API (`api-*.json`) mais antigos que isso são apagados **ao subir o processo** da API, como o decaimento da memória ([`src/triagem/retencao.py`](../src/triagem/retencao.py); `TRIAGEM_RETENCAO_DIAS` muda o prazo). `teste::test_span_com_mais_de_90_dias_sai_e_o_recente_fica`, `teste::test_a_api_aplica_a_guarda_ao_subir`.
- **Acesso:** o `traces.jsonl` é criado com permissão `0600`, legível só pelo usuário do processo (`teste::test_trace_fica_legivel_so_pelo_dono`).
- **Remoção por titular:** `Memoria.remover_titular` também apaga do trace as **conversas inteiras** em que o RA aparece (`teste::test_remover_titular_da_memoria_tambem_limpa_o_trace`).

## 7. O plano é uma hipótese

Cada linha do §3 afirma que uma falha será vista por um sinal. A afirmação só se confirma **provocando** a falha. O que já foi provocado, em teste:

| Falha | Provocada em | Resultado |
|---|---|---|
| laço (`laco_detectado`) | `test_execucao_que_para_no_meio_e_erro_na_raiz` | a raiz sai com `agente.termino = laco_detectado` e status de erro |
| erro do provedor | `test_erro_fatal_do_provedor_marca_o_span_chat_e_a_raiz` | `error.type = erro_fatal` no `chat` e na raiz |
| tentativa de acesso a terceiro | `test_chamada_recusada_pelo_controle_aparece_marcada_no_trace` | `agente.ferramenta.recusada = true` |
| correção pelo código (L02) | `test_a_escrita_feita_pelo_codigo_tambem_e_um_span` | `agente.ferramenta.origem = codigo` |
| modelo servido ≠ pedido | `test_o_modelo_servido_diferente_do_pedido_e_contado` | contado em `evals.metricas` |
| recusa de identidade | `test_recusa_de_identidade_e_um_termino_com_erro` | `agente.termino = recusado_identidade` |
| **contingência** (a falha silenciosa) | `test_a_contingencia_aparece_na_raiz_do_trace_so_no_turno_em_que_ocorreu` | `agente.contingencia = true` na raiz, **sem status de erro**, e só no turno em que ocorreu |

**Não foi provocado** o modo de falha do **orçamento esgotado por tempo** com o trace ligado, nem o **desvio de custo** (tokens por execução subindo entre versões): os sinais existem (`agente.termino`, `agente.tokens_gastos`), mas sem teste que una as duas pontas. E o plano **envelhece**: um segundo agente criaria fronteiras e modos de falha novos, e o corte `gen_ai.agent.name`, hoje trivial, passaria a separar populações distintas.
