# Plano de prompt engineering

Um documento sobre o **raciocínio**; os prompts, que são **fonte**, vivem em [`src/prompts/`](../src/prompts/), junto do código que os carrega. Estado em: prompt `triagem-v2` (sha256 `6df71c6cfcaddca0`).

## 1. O plano: uma linha por etapa em que o modelo é chamado

O grafo tem 15 nós e **um só chama o modelo**: `agente`. Os demais são código (`docs/arquitetura.md`, `docs/grafo.md` §2). O mesmo prompt serve às voltas do laço de ferramentas, e à volta de **correção** quando o validador reprova a resposta (o texto da correção é uma mensagem de sistema escrita pelo código, §6).

| Etapa | Técnica | Por que ela | Contrato de saída | Como é testada |
|---|---|---|---|---|
| **`agente`** (triagem) | **zero-shot** com **regras numeradas** e contrato de saída explícito; chamada de ferramenta (`tools`) em vez de texto para as ações | o julgamento depende dos **dados que as ferramentas devolvem em cada execução** (comparar o relato com o registro), e não de um padrão de linguagem que exemplos ensinariam. Regras numeradas porque cada uma impede um modo de falha nomeado (`src/prompts/triagem-v2.md`) | **(a)** uma chamada de ferramenta com argumentos JSON do esquema declarado, ou **(b)** texto final ao aluno em português, com: protocolo e texto do documento, **ou** "encaminhado + protocolo + prazo de 48 h", **ou** a regra com o **artigo citado** e a linha `[SUFICIENTE: sim\|não]` (dúvida do Regimento). **Proibido:** prazo diferente de 48 h, dado que não veio de ferramenta, passo ou canal inventado, artigo não devolvido, documento fora do catálogo | **offline:** 62 testes do sistema em grafo (`test_triagem.py` 35, `test_memoria_triagem.py` 14, `test_regimento.py` 7, `test_estado.py` 6), com o modelo roteirizado que faz o que um modelo ruim faria, mais 14 da API. **Modelo real:** as 8 execuções de `logs/parte2/`; o *golden dataset* de 24 casos (Exercício 11; a Parte 3 o roda sobre este sistema) |

Nenhuma outra etapa usa técnica de prompting: classificar o pedido, rotear, validar a resposta, escrever memória e montar a saída são **regras em código** (`docs/grafo.md` §2.3). Onde o código basta, não se paga uma chamada de modelo.

**Por que zero-shot e não few-shot.** Exemplos fixos ensinariam o **formato** da resposta, mas não ajudam a generalizar "quando a alegação do aluno diverge do sistema", que é uma comparação entre dois valores concretos. O contrato de saída faz o trabalho dos exemplos. **Não testei** few-shot contra zero-shot: a escolha é por argumento, e a Parte 3 (suíte) é o instrumento para comparar quando houver uma razão.

## 2. Os prompts em arquivo

| Arquivo | O que é | Quem o carrega |
|---|---|---|
| [`src/prompts/triagem-v2.txt`](../src/prompts/triagem-v2.txt) | **o prompt do sistema em grafo** | `src/triagem/nos.py` (`SYSTEM`), lido uma vez ao importar |
| [`src/prompts/triagem-v2.md`](../src/prompts/triagem-v2.md) | a nota da versão: o que mudou em relação à v1 e o que cada frase nova impede | (documentação) |
| [`src/prompts/triagem-v1.txt`](../src/prompts/triagem-v1.txt) e `.md` | o prompt da Parte 1; **mantido**: o laço de `src/agente.py` ainda o lê (é o motor das ferramentas) e os resultados medidos da Parte 1 (39/40) são dele | `src/agente.py` (`PROMPT_PATH`) |
| [`src/prompts/historico/juiz-rubrica-v1.0.0.txt`](../src/prompts/historico/juiz-rubrica-v1.0.0.txt) | a rubrica do juiz da suíte (Exercício 11), versão que não foi adotada | `src/suite/juiz.py` |

Um prompt **não** mora numa *f-string* do código: a v2 tem um arquivo, um histórico no git (o `prompts/` foi movido para `src/prompts/` com `git mv`, e o histórico foi junto) e uma nota de versão. A v1 e a v2 coexistem de propósito: a mudança de v1 para v2 é uma **mudança de versão do sistema**, e a comparação entre as duas é o que a suíte mede.

## 3. Prompt × modelo × parâmetros

O que cada execução registra no início, para que um número possa ser ligado ao que o produziu:

| | Valor | Onde fica registrado |
|---|---|---|
| prompt | `src/prompts/triagem-v2.txt`, sha256 `6df71c6cfcaddca0` | cada log de `logs/parte2/` (`prompt.sha256`) |
| modelo | `qwen/qwen3.8-27b` (Groq), variável `LLM_MODELO` | cada log (`modelo`); **o modelo servido** pelo provedor ainda não é gravado (lacuna L05/L13 do model card; a Parte 3 o grava no trace) |
| `temperature` | `0` | cada log (`parametros`). Escolher ferramenta e classificar o pedido é decisão, não geração criativa: variar é defeito. Não garante o mesmo texto: a Groq varia a redação entre execuções com `temperature = 0` (medido no Exercício 11: 11 de 24 respostas de A mudaram de redação entre duas execuções, **sem mudar nenhuma decisão**) |
| `max_tokens` | **não definido** | a omissão é uma decisão com custo: sem ele, a Groq **estima** a saída do pedido e recusa o que passar de 1.000 tokens/minuto no `qwen` (achado de 18/10/2026, `docs/modelos.md` §3.5): o agente parava em `erro_fatal`, não por erro de decisão. Declarado como risco operacional; a Parte 3 trata |
| `tool_choice` | automático | o modelo decide se chama uma ferramenta |
| orçamento | 8 chamadas de ferramenta, 20.000 tokens por conversa; `recursion_limit = 60` | `agente.Orcamento`, `triagem/grafo.py` |

**A API não grava o carimbo** (o registro `api-<id>.json` guarda a saída, a trilha e os tokens, mas não o hash do prompt): lacuna que o trace da Parte 3 fecha.

## 4. A conferência do texto, em código

O contrato de saída do prompt diz "não invente protocolo, prazo nem artigo". **Dizer não é garantir.** O validador ([`src/triagem/validacao.py`](../src/triagem/validacao.py)) confere o **texto** contra o que as ferramentas devolveram:

| Confere | Reprova quando |
|---|---|
| protocolos (`DOC-n`, `CASO-n`) | o texto cita um que nenhuma ferramenta devolveu |
| artigos (`Art. n`) | o texto cita um que `consultar_regimento` não devolveu (o prefixo basta: "Art. 7º" aceita "Art. 7º §1º") |
| prazos (`n h`, `n dias`) | o número não é 48 h nem consta no artigo devolvido |
| marcação `[SUFICIENTE: ...]` | há artigo devolvido e a resposta não a traz |

Reprovando, a resposta volta ao agente **uma vez**, com a lista de problemas numa mensagem de sistema (padrão avaliador-otimizador, `docs/grafo.md` §2.2); reprovando de novo, o nó `contingencia` monta a resposta por molde, **sem o modelo**, e só afirma o que as ferramentas devolveram. **Nas 8 execuções reais, o validador aprovou todas de primeira** (nenhum `validar:devolveu`), então ele nunca precisou agir com o modelo real em uso normal: o que ele faz está provado pelos testes offline, não pelas demonstrações.

**O que ele NÃO confere:** invenção de **canal** ("a secretaria entrará em contato", "acompanhe pelo portal"). Não há regra que a detecte sem falso positivo. O caso 4 real contém exatamente isso: *"A secretaria entrará em contato dentro desse prazo."* Nenhuma ferramenta disse que a secretaria entra em contato. É o risco aceito ASI09 (`docs/seguranca.md`); a suíte da Parte 3 mede com um juiz, e o juiz do Exercício 11 **não foi adotado** (recall de "não fiel" de 60%).

## 5. A regra da frase

> Se você apagar uma frase do prompt e não souber dizer o que ela impedia, ela não estava fazendo nada.

**A frase testada** (regra 7, segurança): *"...diga que o Regimento não trata disso e ofereça encaminhar o caso à secretaria; **não responda com conhecimento próprio**."* A hipótese: sem ela, o modelo responderia a pergunta do Regimento **de cabeça**, quando os artigos devolvidos não a respondem. Script: [`src/ablacao_prompt.py`](../src/ablacao_prompt.py); modelo real, `temperature = 0`.

| Tentativa | Perguntas | Resultado | Registro |
|---|---|---|---|
| 1 | duas **fora do domínio** (valor da mensalidade, previsão do tempo) | respostas **idênticas** com e sem a frase, porque o modelo **nem chamou** `consultar_regimento`: recusou por escopo. **O experimento não exercitou a frase** (ela só atua depois de a ferramenta ser chamada). Nada a concluir | [`ablacao-regra7-tentativa1-fora-de-dominio.json`](../logs/parte2/ablacao-regra7-tentativa1-fora-de-dominio.json) |
| 2 | `s01` e `s02` do conjunto do RAG (assunto do Regimento, **sem** resposta nele), 1 execução cada | `s01`: igual. **`s02`: sem a frase, a resposta virou o texto de contingência** ("Não consegui concluir sua solicitação") | [`ablacao-regra7-tentativa2-uma-execucao.json`](../logs/parte2/ablacao-regra7-tentativa2-uma-execucao.json) |
| 3 | `s02`, **3 repetições** por variante | com a frase: 3/3 aprovadas pelo validador. Sem a frase: **0/3**, todas caíram na contingência | [`ablacao-regra7-tentativa3-parser-rigido.json`](../logs/parte2/ablacao-regra7-tentativa3-parser-rigido.json) |
| **a causa** | | sem a frase, o modelo escrevia `[SUFICIENTE: não]` e **continuava o texto depois dela**. **Meu parser exigia a marcação no fim** e reprovava; duas reprovações levam ao molde. **A frase não impedia uma resposta errada: ela só mudava onde o modelo punha a marcação.** O defeito era do parser, e o custo era real (uma boa resposta virava "não consegui concluir") | |
| 4 | `s02`, 3 repetições, **depois de corrigir o parser** (aceita a marcação em qualquer posição) | com e sem a frase: **3/3 e 3/3** `sem_acao`, `suficiente = false`, validador aprovando. A redação muda ("não trata de" × "não prevê"); a decisão e a suficiência, não | [`ablacao-regra7.json`](../logs/parte2/ablacao-regra7.json) |

**O que isso quer dizer, sem exagerar:**

- O experimento **achou um defeito do código** (parser rígido), e ele foi corrigido (`tests/test_triagem.py::test_marcacao_no_meio_do_texto_e_aceita_e_removida`). Foi o resultado mais útil.
- **A frase não mostrou nenhum efeito observável** nas perguntas testadas (2 perguntas, 1 + 3 repetições por variante). Pela regra da frase, é candidata a sair.
- **Não a removi.** Duas perguntas e quatro repetições não provam que ela é inútil: o caso que a exercita de verdade é o em que a pergunta convida a resposta de cabeça ("qual o prazo de trancamento nas universidades em geral?"), e eu não o testei. Custa ~25 tokens por chamada. **Fica no prompt até o *golden dataset* da Parte 3 ter um caso que a teste** (`docs/evals.md`).
- A comparação "o modelo mudou de resposta" depende do que se mede: **a decisão e a suficiência** não mudaram; **o texto** mudou. Medir só o texto exagera a diferença.

## 6. Textos que o código escreve (e que não são prompt do modelo)

| Texto | Onde | Para quê |
|---|---|---|
| saudação fixa | `triagem/nos.py` (`SAUDACAO_FIXA`) | o sistema é reativo (`docs/case.md` §2.2): a saudação é do widget, e não custa uma chamada |
| mensagem de correção | `Nos.validar_resposta` (`[verificação automática] ...`) | devolve a resposta reprovada ao agente, com o motivo. **É mensagem de sistema escrita pelo código**; o único texto variável é a lista de problemas, que o próprio código produz |
| contingência | `validacao.resposta_de_contingencia` | a resposta por molde, quando o agente reprova duas vezes |
| a tela da coordenação | `humano.tela_da_aprovacao` | o que a pessoa vê na pausa (`docs/humano.md` §2) |
