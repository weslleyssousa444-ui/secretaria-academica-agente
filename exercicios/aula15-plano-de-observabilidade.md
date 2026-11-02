# Plano de observabilidade — agente de trocas

Grupo: Weslley Soares de Sousa, Pedro Akira, Henrique Gomes Matos e Erick · Data: 2026-10-30

> **Exercício 15.** O case é o agente de trocas de uma loja virtual (descrito no enunciado), e não o agente de triagem do grupo. O método é o mesmo que a Parte 3 pede para o sistema do grupo; o fim deste documento mostra o que, do plano, o agente de triagem já tem e o que falta.
>
> **Duas premissas que o enunciado não fixa**, declaradas para que o plano seja conferível:
> 1. **"Passo" = uma chamada ao modelo (`chat`).** Uma conversa típica usa 4 dos 6 passos (três voltas com ferramenta e a resposta final). Se "passo" for chamada de ferramenta, usa 3 de 6; a árvore da seção 2 não muda.
> 2. **Uma conversa = uma execução = um *trace*.** O cliente pode mandar várias mensagens, mas a decisão da troca é uma só por conversa. Se a conversa tiver vários turnos, o plano passa a um *trace* por turno com `gen_ai.conversation.id`.

---

## 1. Perguntas

| Interessado | Pergunta | Decisão que a resposta muda |
|---|---|---|
| o negócio | A fração de trocas resolvidas **sem atendente** está em 60% ou mais, **e** a fração das trocas aprovadas que estavam **fora da política** está abaixo de 1%? | manter o agente como está, ampliar o que ele decide sozinho, ou recuar (mandar mais casos ao atendente) |
| a operação | Quantas conversas terminaram **sem decisão** na última hora — orçamento esgotado, laço ou erro —, e em que versão do sistema? | investigar e, se a piora começou com uma mudança, **reverter a versão no ar** |
| quem paga | Quanto custa uma conversa, em média, e qual componente domina — o histórico reenviado a cada volta ou as declarações de ferramenta? | aplicar uma alavanca de custo (encurtar o retorno das ferramentas, modelo menor na parte fácil) ou rever o orçamento de 6 passos |
| quem responde pelo sistema | Alguma troca foi **registrada** sem que a política tivesse sido consultada antes, para um pedido diferente do consultado, ou duas vezes? | **suspender `registrar_troca`** (passar a exigir aprovação humana), revisar as permissões da ferramenta e abrir auditoria das trocas afetadas |

*Perguntas que ficaram de fora:* "quantas vezes por dia `consultar_politica` é chamada?" — nenhuma decisão muda com a resposta. Volume de `consultar_pedido` entra só se alguém dimensionar capacidade a partir dele.

---

## 2. O *trace* de uma conversa

**Árvore de *spans* de uma conversa típica (troca aprovada):**

```text
invoke_agent  agente-de-trocas
├── chat <modelo>                     (o modelo pede consultar_pedido)
├── execute_tool consultar_pedido
├── chat <modelo>                     (o modelo pede consultar_politica)
├── execute_tool consultar_politica
├── chat <modelo>                     (decide aprovar; pede registrar_troca)
├── execute_tool registrar_troca      (a única escrita)
└── chat <modelo>                     (responde ao cliente)
```

Atributos da convenção, que a plataforma já entende: na raiz, `gen_ai.agent.name = agente-de-trocas` e `gen_ai.provider.name`; em cada `chat`, `gen_ai.request.model`, `gen_ai.response.model` (o modelo **servido**, que o provedor pode trocar sob o mesmo nome), `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens` e `gen_ai.response.finish_reasons`; em cada `execute_tool`, `gen_ai.tool.name` e `gen_ai.tool.call.id`. O **número do pedido** vai como atributo do `execute_tool` (é por ele que se liga a consulta ao registro), nunca como atributo de métrica: cardinalidade.

**Atributos próprios na raiz:**

| Atributo | Valores possíveis | Para que serve |
|---|---|---|
| `agente.termino` | `respondeu`, `orcamento_esgotado`, `laco_detectado`, `erro` | separa as conversas que terminaram bem das que pararam no meio (o agente responde "encaminhado" nos dois casos, e só este atributo distingue). É a base do SLO operacional e do alerta de orçamento |
| `troca.decisao` | `aprovada`, `recusada`, `encaminhada`, `ausente` | o veredito extraído da execução. Sem ele não se calcula "resolvidas sem atendente" (promessa) nem "aprovadas fora da política" (silenciosa); `ausente` é a conversa que terminou sem decisão |
| `agente.versao` | composta: `<codigo>/<prompt>/<politica>`, p. ex. `1.4/p3/pol-2026-09` | corta qualquer métrica pela **versão composta**. Código, prompt e política mudam de forma independente (o prompt sem *deploy*, a política sem mexer no código); a versão só do código não separa o antes e o depois de nenhuma dessas mudanças |

---

## 3. Modos de falha

| Componente | Falha | Ruidosa ou silenciosa | Sinal que a torna visível |
|---|---|---|---|
| laço do agente | esgota os 6 passos e **encaminha ao atendente**: o cliente recebe uma resposta, mas a troca não foi resolvida — e é a promessa dos 60% que sangra | **silenciosa** (resposta devolvida com sucesso; a taxa de erro não se mexe) | proporção de `agente.termino = orcamento_esgotado`, cortada por `agente.versao` |
| `consultar_politica` (e a política que ela devolve) | devolve o prazo de **outra categoria** ou uma política desatualizada, e o agente aprova uma troca fora do prazo | **silenciosa** (a ferramenta devolve `200`; o agente raciocina corretamente sobre um dado errado) | auditoria determinística: recalcular, para cada `aprovada`, `dias entre a compra e o pedido ≤ prazo da categoria` com o que `consultar_pedido` e `consultar_politica` devolveram naquele *trace*; contar as que falham, cortando por `agente.versao` (que carrega a versão da política) |
| modelo + `registrar_troca` | registra a troca **sem ter consultado a política** (palpite que deu certo), para o **pedido errado**, ou **duas vezes** (nova tentativa) | **silenciosa** (a conversa termina normalmente e o texto ao cliente parece certo) | regras sobre o *trace*: `execute_tool registrar_troca` sem `execute_tool consultar_politica` antes na mesma raiz; mais de um `registrar_troca` por raiz ou por pedido; `numero` do registro diferente do consultado |
| provedor do modelo | indisponibilidade, limite de taxa ou cota diária | **ruidosa** | `chat` com status de erro e `agente.termino = erro`; alerta por sintoma na taxa de conversas com erro |

---

## 4. Objetivos

| Tipo | Indicador | Objetivo | Janela |
|---|---|---|---|
| operacional | (a) conversas com `agente.termino = respondeu` **e** `troca.decisao ≠ ausente`, sobre o total; (b) custo médio por conversa (tokens × preço, somados por *trace*) | (a) ≥ 95% · (b) ≤ R$ 0,05 *(valor a calibrar com uma semana de medição; o orçamento de 6 passos limita o pior caso)* | 28 dias |
| a promessa da loja | (i) trocas resolvidas sem atendente (`troca.decisao` em `aprovada` ou `recusada`) sobre o total de trocas; (ii) trocas aprovadas **fora da política** (auditoria determinística da seção 3) sobre as aprovadas | (i) ≥ 60% **e** (ii) < 1% — a promessa vale só se as **duas** valem | 28 dias |

*Por que a promessa tem os dois termos:* sozinha, a taxa de resolução (i) sobe se o agente passa a aprovar tudo; sozinha, (ii) cai a zero se ele encaminha tudo. O SLO existe para impedir que um número seja comprado com o outro. Com cerca de 500 conversas por dia, 28 dias dão ~14 mil conversas — o suficiente para (i); para (ii), a amostra são as aprovadas, algumas centenas por semana, e por isso a auditoria roda sobre **todas** as aprovadas (a regra é determinística e barata), e não sobre uma amostra.

---

## 5. Alertas

| Alerta | Condição e limiar | SLO de origem | Quem é avisado | O que faz |
|---|---|---|---|---|
| custo | custo médio por conversa **na última hora > R$ 0,10** (o dobro do objetivo), com pelo menos 10 conversas na janela | operacional (b): ≤ R$ 0,05 | o responsável pelo agente (plantão de operação) | abre o painel e desce pelos cortes: por `agente.versao` (a piora começou com uma mudança?), por `gen_ai.tool.name` (alguma ferramenta passou a devolver mais dado?) e por `gen_ai.usage.input_tokens` por conversa (histórico crescendo, laço). Se for uma versão, **reverte**; se for tráfego legítimo, registra e avisa quem paga. Um laço não detectado aparece aqui antes de aparecer na fatura |
| degradação silenciosa | **2 ou mais trocas aprovadas fora da política em 24 h** (≈ 1% das aprovadas, no volume esperado), pela auditoria determinística | promessa (ii): < 1% | o responsável pelo agente **e** o dono do produto | compara a versão no ar com a anterior (corte por `agente.versao`, que traz a versão da política); abre os *traces* das trocas apontadas; se a taxa persistir, **suspende `registrar_troca`** (aprovação humana obrigatória, *fail-closed*) até a causa ser achada, e devolve o caso ao *golden dataset* como caso permanente |

*Os dois alertas têm destinatário e procedimento.* O alerta de custo dispara por **sintoma** (custo por conversa), não por causa; o de degradação silenciosa usa o único sinal que a taxa de erro nunca dá — a decisão errada devolvida com sucesso.

---

## Resposta à questão do enunciado

> **Como saber, sem ler o código, se o agente de trocas está funcionando — e se está funcionando bem?**

**Funcionando** é o que a operação lê: a proporção de conversas com `agente.termino = respondeu` e decisão (SLO operacional) e o custo por conversa. Nenhum dos dois está na taxa de erro, que não se mexe quando o agente esgota o orçamento ou encaminha tudo.

**Funcionando bem** é o que o negócio lê: 60% sem atendente **e** menos de 1% fora da política, medidos juntos, sobre a decisão (`troca.decisao`) e sobre uma auditoria que recomputa a regra da política com o que as próprias ferramentas devolveram. É a diferença entre "o serviço responde" e "o serviço acerta" — e só a segunda se mede com sinais que a aplicação produz (`agente.termino`, `troca.decisao`, `agente.versao`), porque nenhuma convenção nem plataforma sabe o que "trocar certo" significa para a loja.

## O que fica fora da telemetria

Prompt e resposta ao cliente **não** são emitidos nos *spans*: carregam o conteúdo do pedido e, com ele, dado pessoal. A auditoria determinística precisa do que `consultar_pedido` e `consultar_politica` devolveram; esse conteúdo vai para um **armazenamento próprio**, ligado ao *trace* por `trace_id`, com acesso restrito e prazo de retenção declarado (suficiente para reconstruir uma troca contestada, e não mais que isso). O *Collector* remove os atributos sensíveis antes de a telemetria sair da rede.

## O plano é uma hipótese

Cada linha da seção 3 afirma que uma falha será vista por um sinal. A afirmação só se confirma **provocando** a falha: forçar a política a devolver o prazo da categoria errada e ver o alerta de degradação silenciosa disparar; remover `consultar_politica` do roteiro de um teste e ver a regra de trajetória acusar. Até lá, o plano é hipótese. E ele envelhece: um segundo agente cria fronteiras e modos de falha novos, e o corte `gen_ai.agent.name`, hoje trivial, passa a separar populações distintas.

---

## Apêndice — do agente de trocas para o agente de triagem (rascunho da Parte 3)

O método vale para o case do grupo. O que o agente de triagem **já tem** e o que **falta** para o plano acima valer para ele:

| Item do plano | No agente de triagem hoje | Falta |
|---|---|---|
| `agente.termino` | existe como dado: `Termino` com `respondeu`, `orcamento_esgotado`, `erro_fatal` e `laco_detectado` ([`src/agente.py:86-90`](../src/agente.py#L86-L90)); a API o devolve ([`src/api.py:97-99`](../src/api.py#L97-L99)) | emiti-lo como atributo de *span* em vez de só gravar no JSON |
| `troca.decisao` (aqui, o desfecho do pedido) | o verificador já extrai o desfecho da trajetória (`classificar_decisao`, [`src/verificador.py:30-56`](../src/verificador.py#L30-L56)) | rodá-lo em produção, sobre o registro de cada conversa |
| `agente.versao` composta | **não existe**: o *model card* registra que o registro não tem versão de prompt nem modelo servido ([`docs/model-card.md` §11](../docs/model-card.md), `L05`, `L13`) | gravar o hash do prompt, `resposta.model` e o *commit* — a mesma correção da `L05` |
| registro por conversa | `demo.py` e a API gravam; `chat.py` não (`L07`) | gravar em todo término |
| auditoria da regra | os limites de autoridade já estão em código e têm teste (`tests/test_autoridade.py`) | recomputar, sobre os registros reais, "documento emitido com pendência" e "trancamento sem caso aberto" — o análogo de "aprovada fora da política" |
| convenção OpenTelemetry | nenhuma: o formato é o JSON próprio de `salvar_log` | traduzir o `Estado` para `invoke_agent`, `chat` e `execute_tool` (a nota 03 da Aula 15, Exemplo 1) |

A pergunta de quem responde pelo sistema, no triagem, é a de `L01`: *alguma conversa consultou o financeiro de um RA que não era o de quem perguntava?* Hoje o sistema **não consegue responder**, porque não sabe quem perguntou — e é por isso que ela abre o plano de observabilidade da Parte 3.
