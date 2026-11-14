# Model card — sistema de triagem da secretaria acadêmica

**Governança do sistema entregue (Partes 2 e 3), com evidência.** Reescreve o *model card* do Exercício 12, que descrevia o agente da Parte 1 (4 ferramentas, sem grafo, sem memória, sem RAG, sem pausa humana). Aquele texto está no histórico do git (`b3f4596`).
**Grupo:** Weslley Soares de Sousa, Pedro Akira, Henrique Gomes Matos e Erick.
**Data:** 11/11/2026. **Commit-base auditado:** `57d5fa1` (o que muda depois dele entra no commit que traz este arquivo; `git log -- docs/model-card.md` o identifica).

## Como ler este documento

Cada campo traz **a afirmação** e **a evidência**. Os tipos de evidência são:

- `arquivo:linha`, com link para o trecho exato no repositório (as linhas foram **calculadas por script** sobre o commit-base, não digitadas);
- `teste::nome`: um teste em [`tests/`](../tests/) que roda offline, sem chave de API (`python -m pytest -q`; **263 passed, 1 deselected** em 13/11/2026; eram 210 em 11/11/2026, Python 3.11.18);
- `log`: o registro de uma execução real com o modelo real em [`logs/parte2/`](../logs/parte2/) ou [`evals/resultados/`](../evals/resultados/);
- `saída de comando`: arquivo em [`docs/evidencias/`](evidencias/), com o comando e a saída copiados. **Os de [`autoridade-efetiva.txt`](evidencias/autoridade-efetiva.txt), [`inventario-dados-pessoais.txt`](evidencias/inventario-dados-pessoais.txt) e [`historico-git.txt`](evidencias/historico-git.txt) são de 16/10/2026 e descrevem o agente da Parte 1**: valem como história, não como retrato do sistema atual (L26).

**LACUNA L-xx** marca uma afirmação sem evidência ou um controle que não existe. Todas estão reunidas, com a situação, na seção [Lacunas](#lacunas). Os testes de [`tests/test_lacunas.py`](../tests/test_lacunas.py) exercitam **o motor da Parte 1** (`src/agente.py`) chamado direto, e continuam passando descrevendo o defeito dele; **o sistema entregue o contorna** nos pontos que a seção Lacunas indica (L01, L02). O teste de cada controle novo está em [`tests/test_controles.py`](../tests/test_controles.py), e os de [`tests/test_api_seguranca.py`](../tests/test_api_seguranca.py) **também passam descrevendo defeitos da API** (§8).

**O que é "o sistema" aqui.** O pacote [`src/triagem/`](../src/triagem/): um grafo LangGraph de 15 nós e 24 arestas (12 condicionais) que usa [`src/agente.py`](../src/agente.py) como motor de ferramentas, o RAG do Regimento ([`regimento.py`](../src/triagem/regimento.py)), a memória de três tipos ([`memoria.py`](../src/triagem/memoria.py)), a pausa para a coordenação ([`humano.py`](../src/triagem/humano.py)), o contrato de saída ([`saida.py`](../src/triagem/saida.py)) e o trace ([`telemetria.py`](../src/triagem/telemetria.py)). Pontos de entrada: [`src/api.py`](../src/api.py), [`src/chat.py`](../src/chat.py), [`src/demo_grafo.py`](../src/demo_grafo.py) e a suíte [`evals/`](../evals/). Prompt: [`src/prompts/triagem-v2.txt`](../src/prompts/triagem-v2.txt). O servidor MCP do Ex.10 e a variante LangGraph do Ex.9 continuam **fora** do sistema ([`exercicios/`](../exercicios/)).

> **Todos os dados do repositório são sintéticos** ([`docs/case.md` §2.9](case.md)). Base legal, prazos e transferência internacional são avaliados **como se** o sistema fosse implantado com dados reais de alunos. É para isso que o documento serve. O sistema **não está em produção**.

---

## 1. Identificação

| Afirmação | Evidência |
|---|---|
| Nome: sistema de triagem da secretaria acadêmica (repositório `secretaria-academica-agente`). | [`README.md:1`](../README.md#L1) |
| Versão do sistema: **não há número de versão, mas há um carimbo calculado.** Todo trace e toda métrica carregam `<commit>/<hash do prompt>/<modelo>` (ex.: `57d5fa1/p-6df71c6c/qwen/qwen3.8-27b`). Não há *tag* de lançamento. | [`src/triagem/telemetria.py:145`](../src/triagem/telemetria.py#L145); `teste::test_a_raiz_traz_o_termino_e_a_versao`. Parcial: **L21** |
| Data deste documento: 11/11/2026. | — |
| Grupo: Weslley Soares de Sousa, Pedro Akira, Henrique Gomes Matos, Erick. | [`README.md:3`](../README.md#L3) |
| Responsáveis por papel, **nomeados pelo grupo em 30/10/2026** (matriz abaixo). Nomear não basta: o procedimento de interrupção e o aceite de risco continuam abertos (L15, L16). | **L15 fechada quanto aos nomes; aberta quanto ao aceite** |

Matriz informada pelo grupo em 30/10/2026 (os nomes vieram do grupo, não do documento):

| Papel | Responde por | Pessoa |
|---|---|---|
| Produto | finalidade, escopo, limiar de escalonamento | Weslley Soares de Sousa |
| Desenvolvimento | ferramentas, limites em código, registro | Pedro Akira |
| Operação | monitorar, interromper o sistema | Henrique Gomes Matos |
| Risco | aprovar esta especificação, aceitar riscos | Erick |

## 2. Finalidade

| Afirmação | Evidência |
|---|---|
| Para cada mensagem do aluno, o sistema decide entre: emitir **declaração de matrícula** ou **segunda via de histórico**; responder uma dúvida **citando o artigo do Regimento**; pedir o que falta; ou encaminhar à secretaria. O **trancamento** abre um caso e **pausa o grafo** até a coordenação decidir. | [`docs/case.md` §2.1, §2.4, §2.12](case.md); [`docs/grafo.md`](grafo.md); [`src/triagem/nos.py:412`](../src/triagem/nos.py#L412) |
| Usuário principal: a atendente da secretaria, cuja fila o sistema reduz. Quem conversa com o sistema é o aluno. Quem decide o trancamento é a coordenação. | [`docs/case.md` §2.2](case.md); [`docs/humano.md`](humano.md) |
| Regras de negócio: declaração exige matrícula ativa; segunda via exige zero mensalidades em aberto; trancamento é sempre humano. | [`docs/case.md` §2.1](case.md); campo 3 |

**Usos fora de escopo.** O sistema não deve ser usado para:

- **decidir ou executar trancamento.** Não existe ferramenta para isso, e o grafo **só tem ponte para a coordenação**: `teste::test_o_sistema_tem_exatamente_cinco_ferramentas_e_nenhuma_de_trancamento`;
- **emitir qualquer documento** fora dos dois do catálogo: `teste::test_emitir_recusa_documento_fora_do_catalogo`;
- **conferir comprovante de pagamento.** Anexos não são lidos, e a alegação do aluno não substitui o registro financeiro;
- **decidir exceções** (bolsista, liminar, convênio): vão sempre para humano ([`docs/case.md` §2.11](case.md));
- **responder fora do Regimento curado.** Pergunta sem artigo que a sustente é recusada com `suficiencia=false` (`teste::test_pergunta_fora_do_corpus_e_recusa_com_suficiencia_falsa`); o artigo revogado (Art. 9º) fica **fora do corpus** ([`docs/rag.md`](rag.md));
- **operar com dados reais** enquanto L06 e L26 (logs e traces com dado pessoal), L14 (provedor) e a premissa do portal (ASI03, §9) estiverem abertas.

**Classificação regulatória** (critérios da nota sobre legislação, situação de out. 2026; **sem parecer jurídico**):

| Regime | Conclusão | Justificativa |
|---|---|---|
| LGPD | Aplica-se a uma implantação real: o sistema trata RA, nome, curso, situação de matrícula e financeira, o texto livre do aluno e, agora, **memória entre conversas** e **traces**. | Campo 6 |
| LGPD, art. 20 | O sistema **não toma, por desenho, decisão final adversa**: o que é negativo para o aluno vai à fila humana. O que decide sozinho é favorável (emitir). Para trancamento, o **código** garante o escalonamento mesmo que o modelo não chame a ferramenta (L02); para pendência, divergência e RA não encontrado a propriedade ainda depende do modelo (L11). | `teste::test_trancamento_escalado_pelo_codigo_e_o_grafo_pausa` |
| ECA Digital | **Provavelmente não se aplica**: serviço interno ao portal, acesso por matrícula. Aluno de 16 ou 17 anos continua protegido pela LGPD, art. 14. Avaliação do grupo, sem parecer da ANPD. | **L23** |
| AI Act | Não se aplica: o resultado não é usado na União Europeia. | — |
| PL 2338/2023 | Não é lei; não cria obrigação. | — |

## 3. Autoridade

O que o sistema pode fazer, e **onde cada limite é aplicado** (ausência de ferramenta, código, credencial, plataforma ou prompt). Limite aplicado só no prompt é marcado como LACUNA.

### 3.1 Escopo, ações proibidas e obrigações

| # | Limite | Onde é aplicado | Evidência |
|---|---|---|---|
| A1 | O sistema tem **exatamente 7 ferramentas** (desde 13/11/2026; eram 5): `buscar_aluno`, `consultar_financeiro`, `consultar_regimento`, `consultar_historico` (leitura), `emitir_documento`, `emitir_boleto`, `escalar_para_humano` (escrita). Nenhuma decide trancamento. | ausência de ferramenta + código | [`src/agente.py`](../src/agente.py), [`src/triagem/servicos.py`](../src/triagem/servicos.py), [`src/triagem/nos.py`](../src/triagem/nos.py) (`FERRAMENTAS`, `ESCRITA`); `teste::test_o_sistema_tem_exatamente_sete_ferramentas_e_nenhuma_de_trancamento` |
| A2 | Uma ferramenta que o modelo invente (ex.: `trancar_matricula`) não é executada: o nó devolve erro como dado e nada é gravado. | código | [`src/triagem/nos.py:143`](../src/triagem/nos.py#L143); `teste::test_ferramenta_inventada_nao_executa_nada` |
| A3 | **Proibido** trancar matrícula, efetivar pagamento ou alterar cadastro e financeiro. As ferramentas do modelo só **inserem**. O único `UPDATE` do sistema (a decisão da coordenação no caso) fica num nó que **só é alcançável depois do `interrupt`**. | ausência de ferramenta + topologia do grafo | `teste::test_as_ferramentas_do_agente_nao_alteram_nem_apagam_nada` (o código do agente e do RAG não tem `UPDATE`/`DELETE`/`DROP`; `registrar_decisao` só tem aresta vinda de `aprovacao_coordenacao`) |
| A4 | **Proibido** emitir `trancamento_matricula` ou documento fora do catálogo. | código | [`src/agente.py:182-186`](../src/agente.py#L182-L186); `teste::test_emitir_recusa_trancamento`, `teste::test_emitir_recusa_documento_fora_do_catalogo` |
| A5 | **Proibido** emitir segunda via com mensalidade em aberto, mesmo que o aluno diga que pagou. | código (a ferramenta revalida na escrita) | [`src/agente.py:202-212`](../src/agente.py#L202-L212); `teste::test_segunda_via_com_pendencia_nao_emite_mesmo_se_o_modelo_tentar`, `teste::test_modelo_desobedece_prompt_e_codigo_barra_emissao` |
| A6 | **Proibido** emitir declaração sem matrícula ativa. | código | [`src/agente.py:195-200`](../src/agente.py#L195-L200); `teste::test_declaracao_bloqueada_matricula_nao_ativa` |
| A7 | **Proibido** emitir para RA inexistente. | código | [`src/agente.py:191-194`](../src/agente.py#L191-L194); `teste::test_emitir_ra_inexistente` |
| A8 | **Proibido** consultar ou emitir para o RA **de outra pessoa** que a sessão autenticada. | **código (ASI03), com uma premissa:** a identidade vem da sessão (`ra_autenticado`), não do texto do aluno; as ferramentas que recebem RA recusam RA diferente do autenticado, em código. **Premissa aberta:** não há portal que defina a sessão (§9). | [`src/triagem/nos.py:148-156`](../src/triagem/nos.py#L148-L156); [`src/triagem/sistema.py:101`](../src/triagem/sistema.py#L101); [`src/api.py:117`](../src/api.py#L117); `teste::test_ASI03_o_ra_de_outro_aluno_e_barrado_em_toda_ferramenta`, `teste::test_ASI03_sem_identidade_e_fail_closed_quando_exigida`, `teste::test_ASI03_a_api_responde_401_sem_identidade_quando_exigida`. Fechada em código; premissa **L01** |
| A9 | Emitir o mesmo documento duas vezes devolve o mesmo protocolo (`ja_existia=true`). | código | [`src/agente.py:214-218`](../src/agente.py#L214-L218); `teste::test_emitir_idempotente` |
| A10 | Escalar duas vezes não duplica o caso. Para **trancamento** a chave é calculada pelo **código** (`ra:tipo:trancamento`). Para os demais casos, a chave ainda é escrita pelo modelo. | código; parcial | [`src/agente.py:232-250`](../src/agente.py#L232-L250); `teste::test_modelo_que_escala_sozinho_nao_duplica_o_caso`; `teste::test_L03_chave_de_idempotencia_vem_do_modelo` (o motor). **L03** |
| A11 | Trancamento é **sempre** escalado, e o grafo **pausa** esperando a coordenação. | **código** (nó `garantir_trancamento`: abre o caso se o modelo não abriu) e prompt. Só vale com RA confirmado por `buscar_aluno`. | [`src/triagem/nos.py:174-190`](../src/triagem/nos.py#L174-L190), [`:324`](../src/triagem/nos.py#L324); `teste::test_trancamento_escalado_pelo_codigo_e_o_grafo_pausa`, `teste::test_trancamento_escalado_pelo_codigo_se_modelo_nao_escalar`, `teste::test_trancamento_sem_ra_confirmado_nao_abre_caso`. L02 fechada |
| A12 | A resposta final não pode citar **protocolo** que nenhuma ferramenta devolveu, **prazo** diferente de 48h nem **artigo** que a consulta não retornou. Resposta reprovada volta ao agente **uma vez**; reprovada de novo, sai de um molde em código, sem o modelo. | **código** (validador) | [`src/triagem/validacao.py:80`](../src/triagem/validacao.py#L80); `teste::test_protocolo_inventado_e_devolvido_ao_agente_uma_vez`, `teste::test_prazo_prometido_diferente_de_48h_e_reprovado`, `teste::test_artigo_citado_que_a_ferramenta_nao_devolveu_e_reprovado`, `teste::test_reprovou_duas_vezes_a_resposta_sai_do_molde_sem_o_modelo` |
| A13 | A suficiência (`[SUFICIENTE: sim\|não]`) é **declarada pelo modelo e exigida pelo código**; sem a marca, a resposta volta uma vez. | código (exige) e modelo (declara) | `teste::test_resposta_do_regimento_sem_a_marcacao_volta_ao_agente_uma_vez`, `teste::test_artigo_de_ruido_com_recusa_declarada_e_sem_acao` |
| A14 | Pedir o RA antes de qualquer ferramenta; pedir comprovante na divergência; confirmar o RA uma vez. | **só prompt** | [`src/prompts/triagem-v2.txt`](../src/prompts/triagem-v2.txt). **LACUNA L11** |
| A15 | **Não inventar canal nem passo do processo** (ex.: "a secretaria entrará em contato"). | **só prompt** e contrato de saída; o validador **não pega**. **Risco aceito (proposto)**, §9. | [`logs/parte2/04-trancamento-nao-e-decidido.json`](../logs/parte2/04-trancamento-nao-e-decidido.json); [`docs/seguranca.md` §4](seguranca.md). **LACUNA L11** |

### 3.2 Credenciais e privilégios

| # | Limite | Onde é aplicado | Evidência |
|---|---|---|---|
| C1 | Chave do provedor fora do repositório (`.env` ignorado pelo git). Uma chave exposta num arquivo local foi **apagada antes de qualquer commit**; **o usuário decidiu em 11/11/2026 não revogá-la**, então ela segue ativa (risco residual, `docs/seguranca.md` §6). | plataforma (git) | [`.gitignore:1`](../.gitignore#L1); [`docs/seguranca.md` §6](seguranca.md) |
| C2 | Chave **própria** do sistema. | **não aplicado.** Agente, RAG, juiz e memória usam a mesma `OPENAI_API_KEY`. | `teste::test_L08_uma_unica_chave_para_todos_os_componentes`. **LACUNA L08** |
| C3 | Privilégio mínimo no banco. | **só código.** O SQLite não tem usuário nem permissão; o limite é o SQL fixo de cada ferramenta (A3). | [`src/dados.py:67-71`](../src/dados.py#L67-L71). **LACUNA L12** |
| C4 | Endpoint de decisão da coordenação protegido por token; **sem `COORDENACAO_TOKEN`, responde 503** e não funciona. | código (fail-closed) | [`src/api.py:147-152`](../src/api.py#L147-L152); testes em [`tests/test_api.py`](../tests/test_api.py) |

**Revisão do que o sistema precisa contra o que tem:**

| Concessão | Precisa? | Decisão |
|---|---|---|
| `consultar_financeiro` devolve `valor_em_aberto` (R$) | **Não.** A regra usa só a contagem de mensalidades, mas o valor vai ao provedor e ao trace. | remover o campo: **L12** (continua aberto) |
| `buscar_aluno` faz `SELECT *` | Parcial. Nome e curso só servem ao texto do documento. | **L12** |
| Acesso a qualquer RA | **Não.** Só ao RA da sessão. | **Fechado em código** (A8) |
| `motivo` livre em `escalar_para_humano` | Parcial. Pode carregar dado que o aluno contou (ex.: motivo de saúde). | enum de motivos: **L03** |

### 3.3 Orçamento e gasto

| # | Limite | Onde é aplicado | Evidência |
|---|---|---|---|
| O1 | Por execução: no máximo 8 passos, 20.000 tokens e US$ 0,05, **e 120 s por turno**. | código | [`src/agente.py:122-138`](../src/agente.py#L122-L138), [`src/triagem/nos.py:249-265`](../src/triagem/nos.py#L249-L265), [`:36`](../src/triagem/nos.py#L36); `teste::test_orcamento_de_passos_interrompe`, `teste::test_teto_de_tempo_por_turno_interrompe_antes_da_proxima_chamada` |
| O2 | **Por volta do modelo (ASI02):** no máximo 4 chamadas de ferramenta e **1 escrita**; as demais recebem resposta de recusa (toda chamada recebe resposta, senão o provedor rejeita a conversa). | código | [`src/triagem/nos.py:45-46`](../src/triagem/nos.py#L45-L46); `teste::test_ASI02_doze_escritas_numa_resposta_executam_so_uma`, `teste::test_ASI02_toda_chamada_recebe_resposta_mesmo_a_recusada` |
| O3 | Laço: a mesma chamada, com os mesmos argumentos, 3 vezes seguidas interrompe. | código | [`src/triagem/nos.py:108-112`](../src/triagem/nos.py#L108-L112); `teste::test_laco_detectado_termina_com_o_motivo` |
| O4 | Teto de passos **do grafo** (`recursion_limit=60`), rede de segurança por baixo de O1: estourar não derruba (termina em `erro_fatal`) nem se confunde com a pausa. | código | [`src/triagem/sistema.py:119`](../src/triagem/sistema.py#L119); `teste::test_estourar_o_limite_de_passos_do_grafo_nao_derruba_nem_confunde_com_pausa` |
| O5 | O limite em dinheiro **não tem efeito** no provedor atual (preço 0), nem em modelo fora da tabela. Não há limite por **dia** ou **mês**. | inerte | [`src/agente.py:47-53`](../src/agente.py#L47-L53); `teste::test_L04_limite_de_custo_inerte_nos_modelos_groq`. **LACUNA L04** |
| O6 | Modelos permitidos (ASI10): **só `qwen/qwen3.8-27b`**; o sistema e a API **não sobem** com outro (o runner do eval é a única exceção, e o candidato fica marcado no trace). | código | [`src/triagem/modelos.py:19-25`](../src/triagem/modelos.py#L19-L25), [`src/triagem/sistema.py:55`](../src/triagem/sistema.py#L55), [`src/api.py:65`](../src/api.py#L65); `teste::test_ASI10_o_sistema_nao_sobe_com_modelo_fora_da_lista`, `teste::test_ASI10_a_api_nao_sobe_com_modelo_fora_da_lista`. L13 fechada quanto à lista |

### 3.4 Quando um controle falha

| # | Comportamento | Onde é aplicado | Evidência |
|---|---|---|---|
| F1 | Erro 4xx do provedor: termina em `erro_fatal`, sem nenhuma escrita (*fail-closed*). | código | [`src/agente.py:384`](../src/agente.py#L384); `teste::test_erro_fatal_do_provedor_termina_sem_escrita` |
| F2 | 429, 5xx ou conexão: até 8 novas tentativas, com espera lida do cabeçalho; depois, `erro_fatal`. | código | [`src/agente.py:345-385`](../src/agente.py#L345-L385) |
| F3 | **Exceção dentro de uma ferramenta** é capturada e vira resultado de erro (dado), não derruba o turno. | código | [`src/triagem/nos.py:162`](../src/triagem/nos.py#L162); `teste::test_excecao_dentro_da_ferramenta_nao_derruba_o_turno`. Corrige a F3 de 16/10 |
| F4 | Identidade ausente com `TRIAGEM_EXIGE_IDENTIDADE=1`: recusa, nenhuma chamada ao modelo (*fail-closed*); a API responde 401. | código | [`src/triagem/sistema.py:101`](../src/triagem/sistema.py#L101); `teste::test_recusa_de_identidade_e_um_termino_com_erro` |
| F5 | Modelo de reserva (*fallback*): não existe; não há desvio para provedor não aprovado. | — | [`src/agente.py:33-37`](../src/agente.py#L33-L37) |
| F6 | Se o modelo **servido** diferir do pedido, a divergência é **contada** nas métricas (não bloqueia). | trace | `teste::test_o_modelo_servido_diferente_do_pedido_e_contado` |

### 3.5 Quem pode suspender o sistema

**Responsável designado: Henrique Gomes Matos (Operação). Mecanismo próprio: não há.** Hoje existem só: encerrar o processo, ou revogar a chave no console da Groq (isso derruba juntos o RAG, o juiz e a memória, e nunca foi testado). **L15 fechada quanto ao nome; LACUNA L16 (interruptor lido a cada volta, procedimento e exercício) aberta.**

## 4. Ferramentas e integrações

| Ferramenta / integração | Permissão | Contra o quê | Evidência |
|---|---|---|---|
| `buscar_aluno(ra)` | leitura, **só o RA da sessão** | `alunos` | [`src/agente.py:147-158`](../src/agente.py#L147-L158) |
| `consultar_financeiro(ra)` | leitura, só o RA da sessão | `alunos`, `financeiro` | [`src/agente.py:161-175`](../src/agente.py#L161-L175) |
| `consultar_regimento(consulta)` | leitura | índice FTS5 do Regimento curado (sem dado pessoal) | [`docs/rag.md`](rag.md); `teste::test_duvida_do_regimento_cita_o_artigo_e_a_fonte_e_conferivel` |
| `emitir_documento(ra, tipo_documento)` | **escrita**: `documentos_emitidos`. Corrigível por reemissão, mas uma cópia entregue não se recolhe. | `alunos`, `financeiro`, `documentos_emitidos` | [`src/agente.py:178-229`](../src/agente.py#L178-L229) |
| `escalar_para_humano(ra, tipo_pedido, motivo, chave)` | **escrita**: `casos_pendentes` | `casos_pendentes` | [`src/agente.py:232-250`](../src/agente.py#L232-L250) |
| Provedor de modelo (Groq) | **envio a terceiro**: o prompt inteiro, com o resultado das ferramentas e **o bloco de memória**, sai a cada chamada | `api.groq.com` | [`src/agente.py:33-37`](../src/agente.py#L33-L37) |
| Memória (episódica, semântica, procedural) | leitura e escrita **só com `ra_autenticado`**; política escrita em código | arquivos em `TRIAGEM_MEMORIA_DIR` | [`src/triagem/memoria.py:162`](../src/triagem/memoria.py#L162); [`docs/memoria.md`](memoria.md) |
| Coordenação | decide casos pausados (token); grava em `decisoes_humanas` | `aprovacoes`, `decisoes_humanas` | [`src/triagem/humano.py:111-141`](../src/triagem/humano.py#L111-L141); [`src/dados.py:113-128`](../src/dados.py#L113-L128) |
| Servidor MCP `secretaria-academica` (13/11/2026) | **só leitura**: as 4 consultas e os casos aguardando; nenhuma escrita publicada | `alunos`, `financeiro`, `disciplinas_cursadas`, índice do Regimento, `aprovacoes` | [`src/mcp_secretaria.py`](../src/mcp_secretaria.py); `teste::test_mcp_nao_publica_escrita` |
| Assistente da coordenação (2º agente, 13/11/2026) | lê pelo MCP **só o RA do caso**; monta um parecer **sem recomendar**; não escreve | o que o servidor MCP publica | [`src/assistente_coordenacao.py`](../src/assistente_coordenacao.py); [`docs/multiagente-mcp-multimidia.md`](multiagente-mcp-multimidia.md) |

## 5. Modelo e provedor

| Afirmação | Evidência |
|---|---|
| Modelo do agente: `qwen/qwen3.8-27b`, `temperature=0`; **único aprovado** (O6). | [`src/triagem/modelos.py:19-25`](../src/triagem/modelos.py#L19-L25) |
| É um identificador fixo, não um *alias* `-latest`, mas **não é uma versão datada**: o provedor pode trocar os pesos sob o mesmo nome. O que o sistema faz é **registrar o modelo servido** (`resposta.model`) e contar a divergência (F6). A reconstrução do exemplo imprime `servido ?`, porque o modelo **roteirizado** do teste não o devolve; **não verifiquei** se o provedor real o devolve, porque não há trace real (L28). | `teste::test_o_modelo_servido_diferente_do_pedido_e_contado`; [`evals/reconstruir.py`](../evals/reconstruir.py). **LACUNA L13** |
| Juiz da fidelidade (**não adotado**): `openai/gpt-oss-120b`, de propósito outro modelo e outra cota. | [`docs/evals.md` §3](evals.md) |
| Provedor: Groq, endpoint compatível com OpenAI, *free tier* sem contrato. | [`.env.example:14`](../.env.example#L14); [`docs/modelos.md` §3.5](modelos.md) |
| Cota do *free tier* do modelo: 200 mil tokens por dia; **ela acabou no meio da rodada B** da suíte. | [`docs/evals.md` §4.2](evals.md) |
| **Região de processamento, prazo de retenção e uso dos dados para treino: não verificados.** | **LACUNA L14** |

## 6. Dados

### 6.1 Inventário: onde o dado pessoal entra, fica e para onde vai

Dado pessoal tratado: **RA, nome, curso, situação de matrícula, mensalidades e valor em aberto, e o texto livre do aluno** (que pode ter dado sensível, art. 11). A base legal é **proposta do grupo**: a decisão é jurídica e cabe à instituição (**L19**). O inventário detalhado de **16/10** está em [`inventario-dados-pessoais.txt`](evidencias/inventario-dados-pessoais.txt); abaixo, o que **mudou** com as Partes 2 e 3.

| Lugar | Dado | Prazo de guarda | Situação |
|---|---|---|---|
| **Prompt enviado à Groq** (a cada volta) | system prompt + janela da conversa + resultado das ferramentas (nome, curso, **valor em aberto**) + **bloco de memória** | **desconhecido** (L14) | fere a minimização: valor e nome não são necessários para decidir (L12) |
| **Banco** `casos_pendentes`, `documentos_emitidos` | RA, tipo, motivo (texto do modelo) | indefinido | L03, L20 |
| **Banco** `aprovacoes`, `decisoes_humanas` (novo) | protocolo, `thread_id`, prazo, **quem decidiu, quando, o quê, o que editou** | indefinido | é o registro da supervisão humana; L20 |
| **Checkpoint** (`TRIAGEM_CHECKPOINT`, SQLite) | a conversa inteira, incluindo o texto livre e o resultado das ferramentas | **sem prazo**: a pausa precisa que ele sobreviva | fora do git; L20 |
| **Memória** (`TRIAGEM_MEMORIA_DIR`) | episódios com resumo (TF-IDF), fato semântico, regras procedurais; **só gravada e lida com `ra_autenticado`** | **180 dias**: o decaimento **remove**, rodado **ao subir o processo** (sem agendador) | `teste::test_o_sistema_aplica_o_decaimento_ao_subir`; remoção a pedido com cobertura verificada ([`docs/memoria.md` §4.3](memoria.md)). **O trace não está nessa varredura** (L26) |
| **Trace** (`TRIAGEM_TRACES_DIR`, JSONL) (novo) | **RA, nome, valor em aberto** nos argumentos e resultados das ferramentas; texto do aluno e resposta (`AGENTE_TRACE_CONTEUDO`, ligado por padrão) | **90 dias**, apagado ao subir o processo; arquivo `0600`; entra na remoção por titular | [`src/triagem/retencao.py`](../src/triagem/retencao.py); `tests/test_retencao.py`. Desligar o conteúdo (`=0`) protege o dado, mas **o trace deixa de reconstruir a decisão** |
| **Logs de demonstração** `logs/0*.json`, `logs/parte2/*.json` | histórico inteiro, nome, valor em aberto, raciocínio do modelo | **indefinido e público**: versionados em repositório público (a Parte 2 acrescentou 8 execuções reais) | `teste::test_L06_log_versionado_guarda_dado_pessoal_e_raciocinio`. **L06** |
| **Índice do Regimento** (FTS5) | só o Regimento; nenhum titular | — | não é dado pessoal |

### 6.2 Onde a minimização falha, em resumo

1. **O log e o trace guardam nome e valor em aberto** (L06), quando bastaria o RA pseudonimizado; desde 13/11/2026 por no máximo 90 dias.
2. **O provedor recebe mais do que a decisão usa** (L12): valor em aberto e nome; **e agora também a memória** do aluno.
3. **Texto livre sem filtro** (L11): vai ao provedor, ao checkpoint, ao trace e, via `motivo`, à fila.
4. **Quase nenhuma estrutura tem prazo** (L20): só a memória episódica tem (180 dias).
5. **Os nomes "fictícios" incluem três integrantes do grupo** (`teste::test_L09_nomes_da_base_sintetica_coincidem_com_o_grupo`), o que contradiz [`docs/case.md` §2.9](case.md) (L09).

## 7. Avaliação

A avaliação do sistema entregue está em [`docs/evals.md`](evals.md); aqui, só o que **foi medido** e o que **não foi**.

| Afirmação | Evidência |
|---|---|
| *Golden dataset* **v1.2.0**: 37 casos, com a pergunta, o resultado esperado e a classe. | [`evals/dataset/golden_v1.2.0.json`](../evals/dataset/golden_v1.2.0.json); [`docs/evals.md` §1](evals.md); `tests/test_evals.py` |
| A **regra de promoção** (não-inferioridade por classe, com piso zero para a classe de identidade) foi **assinada antes** de a versão B existir. | [`evals/resultados/assinatura-regra-p3.txt`](../evals/resultados/assinatura-regra-p3.txt); [`evals/regra_de_promocao_p3.json`](../evals/regra_de_promocao_p3.json) |
| **Rodada A** (tag `parte-2`, **3 de 37 casos**: identidade): **0 de 3 aprovados**. O sistema **sem o controle** leu o cadastro e o financeiro de outra aluna e **emitiu a declaração dela**: é o ataque ASI03 medido com o modelo real. | [`evals/resultados/2026-11-11-A-r1/execucoes.jsonl`](../evals/resultados/2026-11-11-A-r1/execucoes.jsonl); [`docs/evals.md` §4.2](evals.md) |
| **Rodada B** (código atual, 37 casos): **não rodou.** A cota diária do modelo acabou; o runner é retomável. **A comparação A × B está PENDENTE**, e nenhum número dela está neste documento. | [`docs/evals.md` §4.2, §4.4](evals.md) |
| **Juiz de fidelidade: NÃO adotado.** No Exercício 11 a rubrica final deu 89% de concordância e **60% de recall** da classe "não fiel" no *hold-out* (limiar: 85% e 80%). **Os rótulos daquela validação são de uma IA, não de pessoas.** As 20 saídas da ficha foram rotuladas em 13/11/2026 **pelo Claude (IA), não por pessoas** ([`evals/rotulagem/rotulos_claude.csv`](../evals/rotulagem/rotulos_claude.csv): 13 fiéis, 7 não fiéis, com nota por caso); a ficha humana continua disponível. Falta o juiz julgar as mesmas 20 (`evals.juizar`, cota do `gpt-oss-120b`) para medir a concordância. | [`docs/evals.md` §3](evals.md); [`evals/rotulagem/LEIA-ME.md`](../evals/rotulagem/LEIA-ME.md); `tests/test_rotulagem.py`. **LACUNA L24** |
| **Uma repetição por caso**: o ruído do provedor **não foi medido** para este sistema; com 37 casos, um caso vale ~2,7 pontos. | [`docs/evals.md` §3, §4.5](evals.md) |
| Testes offline: **263 passed, 1 deselected** (13/11/2026; 18 do servidor MCP e do 2º agente, 7 da guarda do trace) (o deselecionado é o `eval`, que usa o modelo real). Os que **tentam a ação indevida** de cada controle estão em `tests/test_controles.py` (16 funções), o trace em `tests/test_telemetria.py` (18) e o grafo, a pausa e a decisão em `tests/test_triagem.py` (39). | `python -m pytest -q`; [`docs/evidencias/pytest.txt`](evidencias/pytest.txt) (regenerado em 13/11/2026) |
| 8 execuções reais da Parte 2 com o modelo real, fora da suíte. | [`logs/parte2/`](../logs/parte2/) |

## 8. Limites conhecidos

| Modo de falha observado | Evidência |
|---|---|
| **Invenção de canal** na resposta: *"A secretaria entrará em contato dentro desse prazo."* O validador **aprovou**. | [`logs/parte2/04-trancamento-nao-e-decidido.json`](../logs/parte2/04-trancamento-nao-e-decidido.json); [`docs/seguranca.md` §4](seguranca.md) |
| **Artigo de ruído marcado como suficiente** pelo modelo real (caso 5). Mitigado pela marca de suficiência exigida pelo código; **a marca é declarada pelo modelo**. | [`logs/parte2/05-fora-do-corpus.json`](../logs/parte2/05-fora-do-corpus.json); [`logs/parte2/ablacao-regra7.json`](../logs/parte2/ablacao-regra7.json) |
| **A API não autentica o aluno e a conversa é de quem tem o `conversa_id`:** qualquer cliente continua a conversa de outro se souber o identificador (128 bits, o que o torna difícil de adivinhar, mas não é credencial). Os testes passam **descrevendo** isso. | `tests/test_api_seguranca.py` (`test_ASI03_lacuna_a_api_atende_sem_nenhuma_credencial`, `test_ASI03_lacuna_qualquer_cliente_continua_a_conversa_de_outro`). **L27** |
| **Uma trava global** serializa os turnos de todos os alunos; as conversas **acumulam no checkpoint** sem limite nem expiração. | `tests/test_api_seguranca.py` (`test_ASI08_lacuna_a_trava_global_serializa_todos_os_alunos`, `test_ASI08_lacuna_conversas_acumulam_no_checkpoint_sem_limite_nem_expiracao`). L20 |
| **Pendência sem divergência**: o agente pergunta pelo comprovante e não conclui em um turno (verificador da Parte 1: pendência 2/6). **Não reavaliada no sistema novo**, porque a rodada B não rodou. | [`verificador-por-fatia.txt`](evidencias/verificador-por-fatia.txt) |
| **Cota do *free tier*** (200 mil tokens/dia) limita o que se mede: uma rodada completa custa ~170 mil tokens. | [`docs/evals.md` §4.2](evals.md) |
| **Concorrência:** o protocolo é `COUNT(*) + 1`; a trava do processo evita a colisão, e **dois processos** gerariam o mesmo protocolo. | [`src/api.py:52`](../src/api.py#L52); [`src/agente.py:221`](../src/agente.py#L221) |
| **A expiração não roda sozinha:** o prazo de 48h é conferido por `/coordenacao/expirar`, chamado por rotina; **não há agendador**. | [`src/triagem/humano.py:27`](../src/triagem/humano.py#L27); `teste::test_ninguem_responde_o_caso_vence_e_volta_a_fila` |
| **Exceções do regimento** (bolsista, liminar, convênio) não são cobertas e vão a humano. | [`docs/case.md` §2.11](case.md) |

**Não usar, mesmo dentro da finalidade:** com **dados reais**; em **mais de um processo**; quando o aluno anexar comprovante (o sistema não lê anexos); **sem portal** que defina a sessão (ASI03).

## 9. Riscos aceitos

"Aceito" exige quem aceitou. O responsável de risco é **Erick**. **Ele não registrou nenhum aceite neste documento nem em [`docs/seguranca.md` §4](seguranca.md), e eu não o faço por ele.** A tabela separa o que **o grupo já registrou como decisão** em documentos versionados do que **o documento propõe**, pendente do aceite dele.

| Risco | Razão | O que o limita | Situação | Evidência |
|---|---|---|---|---|
| Cobertura menor que o alvo de 60%: toda exceção vai a humano. | Errar para o lado conservador é mais barato que aprovar indevidamente. | A fila humana absorve. | **registrado pelo grupo** | [`docs/case.md` §2.5, §2.11](case.md) |
| Divergência nunca é resolvida a favor do aluno sem comprovante. | Não afrouxar a regra para inflar a cobertura. | A5, em código. | **registrado pelo grupo** | [`docs/case.md` §2.5](case.md) |
| Documento emitido por engano não é recolhido. | Inerente a entregar documento. | A4–A7 revalidam na escrita. | **registrado pelo grupo** | [`docs/arquitetura-v1.md` §7](arquitetura-v1.md) |
| **ASI09:** a resposta pode afirmar canal ou passo que nenhuma ferramenta informou. | A única mitigação completa (resposta por molde) elimina o diálogo livre, que é a razão de ser do produto. | Contrato de saída; prazo vindo da ferramenta; a decisão não depende do texto. | *proposto, **pendente do aceite de Erick*** | [`docs/seguranca.md` §4](seguranca.md) |
| **ASI04:** imagem e dependências por versão, não por *digest*/hash. | Este ambiente não tem Docker para gerar nem verificar. | *Actions* e imagens de análise por SHA; sem privilégio; **não está em produção**. | *proposto, **pendente*** | [`docs/seguranca.md` §4](seguranca.md) |
| **ASI03, o que sobra:** não há portal; qualquer cliente da API pode declarar qualquer RA no cabeçalho. | O controle é correto **dado** um portal; ele não existe. | Dados sintéticos; API só na máquina do grupo. **Deixa de valer antes de dado real, de expor a porta ou de ligar um portal.** | *proposto, **pendente*** | [`docs/seguranca.md` §4](seguranca.md) |
| *Free tier* da Groq sem contrato e sem termos verificados. | Protótipo acadêmico. | Nenhum dado real. **Deixa de valer com dado real.** | *proposto, pendente* | L14 |
| Repositório público com logs que contêm nomes. | Dados sintéticos. | Nenhum titular real, exceto a coincidência de L09. | *proposto, pendente* | L06, L09 |
| `temperature=0` não garante a mesma saída. | Limitação do provedor. | A decisão é medida pela trajetória, não pelo texto. | *proposto, pendente* | — |

## 10. Supervisão humana

| Afirmação | Evidência |
|---|---|
| **Trancamento pausa o grafo**: o sistema responde ao aluno, grava a espera (`aprovacoes`) e **para em `interrupt()`**; a coordenação retoma com `Command(resume=...)`. A pausa **sobrevive ao fim do processo** (checkpoint em arquivo). | [`src/triagem/nos.py:412`](../src/triagem/nos.py#L412); `teste::test_pausa_sobrevive_a_reiniciar_o_processo`, `teste::test_pausa_grava_a_espera_e_mostra_a_tela` |
| A decisão tem **quatro valores** (`aprovar`, `rejeitar`, `aprovar_editando`, `expirar`) e registra **quem, quando, o quê e o que a pessoa editou**: aprovar não é carimbar. | [`src/triagem/humano.py:111-141`](../src/triagem/humano.py#L111-L141); `teste::test_aprovar_editando_guarda_o_que_a_pessoa_corrigiu`, `teste::test_rejeitar_grava_rejeitado` |
| **Idempotente**: repetir a mesma decisão devolve a gravada; decisão **conflitante** não sobrescreve. | `teste::test_aprovar_duas_vezes_nao_grava_duas_vezes`, `teste::test_decisao_conflitante_nao_sobrescreve` |
| Prazo de **48h**; vencido, o caso volta à fila da secretaria. Rodado por rotina (`/coordenacao/expirar`), sem agendador. | [`src/triagem/humano.py:27`](../src/triagem/humano.py#L27); `teste::test_ninguem_responde_o_caso_vence_e_volta_a_fila` |
| Mensagem do aluno **durante a espera** não chama o modelo nem abre outro caso. | `teste::test_mensagem_durante_a_espera_nao_chama_o_modelo_nem_abre_outro_caso` |
| A tela da coordenação mostra o caso e o que o sistema fez; o endpoint exige token. | [`src/triagem/humano.py:82`](../src/triagem/humano.py#L82), [`src/api.py:147-152`](../src/api.py#L147-L152) |
| **Quem é "a coordenação":** quem tem o `COORDENACAO_TOKEN`. **Um único token compartilhado**: o campo `por` é **declarado por quem chama**, não verificado. **Não há tela própria nem identidade individual.** | [`src/api.py:81-84`](../src/api.py#L81-L84). **LACUNA L27** |
| O que **não** exige aprovação: pendência, divergência e RA não encontrado vão à fila **sem pausa**; emitir um documento permitido é automático. | [`docs/humano.md`](humano.md) |
| Interrupção do sistema: não há procedimento, interruptor nem teste (§3.5). | **LACUNA L16** |

## 11. Registro e retenção

O registro de cada decisão é o **trace** (ver [`docs/observabilidade.md`](observabilidade.md)), comparado com a tupla $R = (id, t, x, C, V, \Phi, P, H, y)$ da nota sobre provar a decisão:

| Campo | Guardado? | Evidência |
|---|---|---|
| $id$ | sim: `trace_id` e `gen_ai.conversation.id` (o `thread_id`); o **protocolo** vai na raiz (`agente.protocolo`), o que liga o caso ao trace. | [`src/triagem/telemetria.py:159`](../src/triagem/telemetria.py#L159); `teste::test_a_raiz_traz_o_termino_e_a_versao` |
| $t$ (instante) | **sim**, em cada span | `teste::test_a_arvore_de_spans_de_uma_execucao` |
| $x$ (entrada) | sim, evento `gen_ai.user.message` (se `AGENTE_TRACE_CONTEUDO` ligado) | `teste::test_a_entrada_e_a_saida_ficam_como_eventos_da_raiz` |
| $C$ (contexto recuperado) | sim: o artigo e o texto devolvidos viram o resultado do span da ferramenta `consultar_regimento` | `teste::test_o_span_da_ferramenta_traz_argumentos_e_resultado` |
| $V$ (modelo, prompt, sistema) | **sim**: `agente.versao` = `<commit>/<hash do prompt>/<modelo>`; modelo pedido e **servido** no span `chat` (L13). **O commit é lido de `.git/HEAD`:** fora de um repositório git, ele não é conhecido. | [`src/triagem/telemetria.py:145`](../src/triagem/telemetria.py#L145); `teste::test_o_span_chat_traz_modelo_e_tokens` |
| $\Phi$ (ferramentas, argumentos, resultados) | sim, um span por chamada, **inclusive a feita pelo código** (`agente.ferramenta.origem="codigo"`) e a **recusada** pelo controle | `teste::test_a_escrita_feita_pelo_codigo_tambem_e_um_span`, `teste::test_chamada_recusada_pelo_controle_aparece_marcada_no_trace` |
| $P$ (política e versão) | **parcial**: as regras estão no código; o commit é o substituto. Não há versão própria da política. | **L05** |
| $H$ (revisão humana, ou a ausência registrada) | **sim**: a retomada da coordenação é **um trace próprio** (protocolo, quem pediu, decisão, se já decidido, conflito, o que editou); **a ausência** aparece como `agente.termino=aguardando_humano` sem retomada. | `teste::test_a_aprovacao_humana_e_um_trace_de_retomada`, `teste::test_o_termino_aguardando_humano_e_distinto_de_respondeu` |
| $y$ (saída) | sim, evento `gen_ai.choice` e o objeto `SaidaTriagem` | `teste::test_a_entrada_e_a_saida_ficam_como_eventos_da_raiz` |

**O que o auditor faz com isso:** [`evals/reconstruir.py`](../evals/reconstruir.py) lê só o arquivo de trace e imprime a decisão (versão, identidade, o que o modelo chamou, o que o **código** executou, a resposta, a retomada). Exemplo, **de uma execução com modelo roteirizado em teste, não com o modelo real** (a execução real com trace **ainda não existe**: depende da rodada B, L28):

```text
CONVERSA conv-exemplo   versão do sistema: 57d5fa1/p-6df71c6c/qwen/qwen3.8-27b

TURNO 1   trace fa5d60b4   12 ms   término: aguardando_humano
  aluno:     'Quero trancar minha matrícula. Meu RA é 20229012.'   (identidade: autenticada)
  modelo:    3 chamada(s), pedido qwen/qwen3.8-27b, servido ?, 240 tokens de entrada e 60 de saída; modelo aprovado: True
  ferramenta 1: buscar_aluno({"ra": "20229012"}) -> {"ra": "20229012", "nome": "Bruno Castro", "curso": "Direito", "situacao_matricula": "ativa"}   [ok]
  ferramenta 2: escalar_para_humano({"ra": "20229012", "tipo_pedido": "trancamento_matricula", "motivo": "trancamento (aberto pelo código: o agente respondeu sem escalar)", "chave": "20229012:trancamento_matricula:trancamento"}) -> {"protocolo": "CASO-3001", "ra": "20229012", "tipo_pedido": "trancamento_matricula", "motivo": "trancamento (aberto pelo código: o agente respondeu sem escalar)", "prazo": "48h", "ja_existia": false}   [ok]  [executada PELO CÓDIGO, não pelo modelo]
  decisão:   escalar_trancamento   suficiente: True   protocolo: CASO-3001   aguardando humano: True
  resposta:  'Encaminhei seu pedido. Protocolo: CASO-3001. Prazo: 48h.'

RETOMADA DA COORDENAÇÃO (turno 2, trace bcef6bb7)
  caso:      CASO-3001
  quem:      coord-1   pediu: aprovar_editando
  decisão:   aprovado   (já decidido antes: False, conflito: False)
  editou:    {"semestre_efetivo": "2027.1"}
```

| Afirmação | Evidência |
|---|---|
| **Os chats e a API gravam o trace** quando `TRIAGEM_TRACES_DIR` está definida (a configuração acontece em `Sistema()`); sem a variável, é *no-op* e **nada é registrado**. A API também regrava o registro da conversa a cada turno, no volume. | [`src/triagem/sistema.py:65`](../src/triagem/sistema.py#L65); `teste::test_sem_configuracao_o_trace_e_noop_e_nada_quebra`; [`src/api.py:100-108`](../src/api.py#L100-L108). **L07 fechada só com a variável definida** |
| Armazenamento: arquivo JSONL comum, **editável**, sem *append-only* nem encadeamento por *hash*. | [`docs/observabilidade.md` §6](observabilidade.md). **LACUNA L05** |
| Prazo de guarda: **90 dias** (decisão de 13/11/2026, Weslley pelo grupo), aplicado ao subir o processo; trace com permissão `0600`. | [`src/triagem/retencao.py`](../src/triagem/retencao.py); [`docs/observabilidade.md` §6](observabilidade.md); `tests/test_retencao.py` |
| Remoção por titular: `Memoria.remover_titular` apaga do trace as conversas inteiras em que o RA aparece. | `teste::test_remover_titular_da_memoria_tambem_limpa_o_trace` |
| Métricas (p50/p95, tokens, motivos de término, erro por ferramenta) e **SLO ≥ 95% em 7 dias**: calculadas por [`evals/metricas.py`](../evals/metricas.py) **sobre execuções reais**; **ainda não há trinta**, então o valor é **PENDENTE**. | [`docs/observabilidade.md` §4, §5](observabilidade.md). **LACUNA L28** |

## 12. Histórico de mudanças

O histórico completo, com os defeitos achados em cada etapa, está em [`docs/mudancas.md`](mudancas.md). Resumo:

| Versão (commit) | Data | O que mudou | Quem aprovou |
|---|---|---|---|
| `069942e` … `9bc9f8f` | 04/09 a 02/10/2026 | Parte 1 e Exercícios 7 a 10 | *não registrado* |
| `b3f4596`, `5ade646`, `41d7a0c` | 16 a 20/10/2026 | *Model card* original; L02 fechada (trancamento pelo código) | *não registrado* |
| `5246a5b` | 02/11/2026 | Exercícios 11 a 15 | *não registrado* |
| `8fa0ae4`, `cbb82d6`, `706c599` | 11/11/2026 | **Parte 2:** grafo, RAG, memória, pausa humana, contrato, API, 8 demonstrações reais | *não registrado* |
| `51c278b` | 11/11/2026 | **Parte 3:** os três controles (ASI03, ASI10, ASI02) | *não registrado* |
| `616fea5` | 11/11/2026 | **Parte 3:** trace OpenTelemetry | *não registrado* |
| `1dfea71`, `31979bf` | 11/11/2026 | **Parte 3:** pacote `evals/`, rodada A parcial | *não registrado* |
| `57d5fa1` | 11/11/2026 | **Parte 3:** regra de promoção assinada antes da versão B, juiz, ficha de rotulagem, `seguranca.md` | *não registrado* |
| `2b1be33` … `45371ad` | 13/11/2026 | Site publicado (Render + Hostinger); boleto, notas e documento imprimível (prompt v3, 7 ferramentas); liberação de modelo para correção; apresentação | Weslley (pedido direto) |
| `db00614` … `59d6dca` | 13/11/2026 | Vídeo; ficha de rotulagem; **opcionais:** servidor MCP, assistente da coordenação, voz no site; medição e simulação do 2º agente | Weslley (pedido direto) |
| *este commit* | 13/11/2026 | Guarda de 90 dias do trace e dos registros, remoção por titular no trace (L26); rótulos do juiz pelo Claude (L24) | Weslley (decisão do prazo) |

Todos os commits têm um único autor e **nenhum passou por *pull request* nem revisão**. **Os commits da Parte 2 e da Parte 3 até `dd1415b` foram enviados ao GitHub com autorização do usuário; commits posteriores podem estar só locais (`git log origin/master..HEAD`).** Uma mudança de autoridade ou de destino do dado, como a troca de provedor em `4a41964`, ou os controles de `51c278b`, entrou sem aprovação registrada. **LACUNA L21.**

---

## Lacunas

Situação em 11/11/2026. Prioridade: **P1**, impede operar com dados reais; **P2**, corrigir antes de operar; **P3**, melhoria. As lacunas que a Parte 3 fechou **dizem com que evidência**, e as que ficaram abertas **dizem por quê**.

| ID | Lacuna | Situação | Prio. |
|---|---|---|---|
| L01 | Não havia verificação de identidade. | **Fechada em código** (A8, ASI03): as ferramentas recusam RA diferente do da sessão; sem identidade e com `TRIAGEM_EXIGE_IDENTIDADE=1`, o sistema recusa. **Premissa aberta:** não há portal que defina a sessão; qualquer cliente da API pode declarar o RA. Aceite **pendente de Erick** (§9). Medido: a versão sem o controle emitiu a declaração de outra aluna (rodada A, 3 de 3 casos). | **P1** (a premissa) |
| L02 | O escalonamento de trancamento dependia do modelo. | **Fechada** (A11). Verificador da Parte 1: 39/40, 0 falso negativo em trancamento (18 e 20/10/2026). No sistema novo: `teste::test_trancamento_escalado_pelo_codigo_e_o_grafo_pausa`; **sem rodada real completa (L28)**. | ~~P1~~ |
| L03 | A chave de idempotência e o `motivo` do escalonamento são texto livre do modelo. | **Parcial:** para trancamento a chave é calculada em código (A10). Para os demais casos, continua do modelo; `motivo` continua livre. | P2 |
| L04 | O limite em dinheiro é inerte (preço 0); não há limite por dia, mês ou chave. | **Aberta.** Há tetos por execução, por volta e por turno (O1–O4), mas nenhum agregado. | P2 |
| L05 | O registro não tinha instante, modelo servido, versão, campo $H$ nem ligação com o protocolo; era editável. | **Parcial:** o trace traz $t$, versão, modelo pedido e servido, protocolo e $H$ (§11). **Falta:** política com versão própria; armazenamento imutável (é JSONL editável). | P2 |
| L06 | Logs com nome, valor e raciocínio versionados em repositório público, sem prazo. | **Aberta, e cresceu:** `logs/parte2/` acrescentou 8 execuções reais ao git. | **P1** |
| L07 | O chat não gravava registro. | **Fechada com `TRIAGEM_TRACES_DIR` definida;** sem ela, nada é registrado. | P2 |
| L08 | Uma única chave para todos os componentes. | **Aberta.** | P2 |
| L09 | Três nomes "fictícios" coincidem com integrantes do grupo. | **Aberta.** | P3 |
| L10 | O protocolo do LangGraph do Ex.9 depende de `hash()` do processo. | **Aberta, fora do sistema entregue** (o sistema usa `agente.py`). | P3 |
| L11 | Regras só no prompt: pedir o RA, pedir comprovante, não inventar canal; texto livre sem filtro. | **Parcial:** protocolo, prazo e artigo citado são validados em código (A12); suficiência é exigida (A13). **Continuam só no prompt:** A14, A15 (invenção de canal, medida no caso 4). Sem filtro de dado sensível. | P2 |
| L12 | Sem privilégio mínimo; `valor_em_aberto` e nome vão ao provedor. | **Aberta.** | P2 |
| L13 | Modelo sem versão datada; modelo servido não registrado; sem lista aprovada. | **Parcial:** lista aprovada em código (O6); modelo servido **registrado e a divergência contada** (F6). **Falta:** versão datada (o provedor não a oferece) e **conferir, num trace real, se o provedor devolve o modelo servido**. | P2 |
| L14 | Região, retenção e uso para treino da Groq não verificados. | **Aberta.** Verificar os termos vigentes **exige acesso ao provedor** e não foi feito. | **P1** |
| L15 | Responsável de risco sem aceite. | **Nomes fechados (30/10/2026); aceite aberto:** §9 e [`docs/seguranca.md` §4](seguranca.md), três riscos propostos, **nenhum aceito por Erick**. | P2 |
| L16 | Sem procedimento de interrupção, interruptor nem responsável testado. | **Parcial:** exceção de ferramenta já não derruba o turno (F3). **Falta:** interruptor lido a cada volta, procedimento e exercício. | P2 |
| L17 | Fila humana sem consumidor, sem registro da decisão e sem controle do prazo. | **Fechada no código** (§10): tabelas `aprovacoes` e `decisoes_humanas`, quatro decisões, prazo de 48h. **Resta:** expiração por rotina, sem agendador; identidade individual da coordenação (L27). | ~~P2~~ |
| L18 | Suíte sem versão; relatório à mão; concordância do juiz não medida; comparação nunca rodada. | **Parcial:** dataset versionado (v1.2.0); runner grava modelo, commit e data; regra assinada antes. **Falta:** rodada B e comparação (L28); validação humana do juiz (L24). | P2 |
| L19 | Base legal não decidida pela instituição; sem encarregado. | **Aberta.** | P2 |
| L20 | Nenhuma estrutura tem prazo de guarda. | **Parcial:** a memória episódica **remove** aos 180 dias, ao subir o processo. **Sem prazo:** banco, checkpoint, trace, logs. | P2 |
| L21 | Sem número de versão nem aprovação das mudanças. | **Parcial:** carimbo `commit/prompt/modelo` em todo trace. **Falta:** *tag* por versão e revisão por outro integrante. | P3 |
| L23 | Classificação no ECA Digital não confirmada. | **Aberta.** | P3 |
| L24 | O juiz de fidelidade **não foi validado por humanos**: os 75 rótulos do Ex.11 e os 20 da ficha (13/11/2026) são de IA. | **Parcial:** os 20 rotulados pelo Claude, com nota; falta rodar o juiz sobre eles. O juiz fica **fora** da regra de promoção. | P2 |
| L26 | O trace tinha dado pessoal sem prazo, sem controle de acesso e fora da remoção por titular. | **Fechada em 13/11/2026:** 90 dias, arquivo `0600`, remoção por titular (`src/triagem/retencao.py`, `tests/test_retencao.py`); `pytest.txt` regenerado. Os demais arquivos de `docs/evidencias/` descrevem a Parte 1 e estão datados como tal. | — |
| L27 | **(nova)** A API não autentica o aluno e a conversa é de quem tem o `conversa_id`; a coordenação é **um token compartilhado**, com `por` declarado e não verificado, e sem tela. | **Aberta.** | P2 |
| L28 | **(nova)** **A rodada B está incompleta** (cota): em 12/11/2026 rodaram 33 dos 37 casos e parou em `dm01` (429); a rodada A tem 3 de 37. Sem comparação A × B, sem valor medido do SLO registrado aqui, sem a reconstrução com trace real. | **Aberta; depende de cota nova do provedor.** Comandos em [`docs/evals.md` §4.4](evals.md). | P2 |
| L29 | **(nova)** **O trace não registra por que o validador reprovou uma resposta.** Em `re05` e `rg03` (rodada B parcial, 12/11/2026) o modelo foi reprovado duas vezes e o sistema respondeu pela contingência, mas o **motivo** (`problemas` de `validar_resposta`) só existe numa mensagem de sistema do checkpoint, que a suíte apaga (`tempfile.TemporaryDirectory`, [`evals/rodar.py`](../evals/rodar.py)); o trace guarda só o nome do nó (`validar:devolveu`, `validar:contingencia`) e **os spans `chat` não guardam o rascunho**. A causa dessas duas reprovações **não foi apurada**; uma hipótese para `rg03` (o Art. 8º §3º remete ao Art. 9º §1º, que a busca não devolveu) **não está confirmada**. | **Aberta.** Proposta, só depois de A e B terminarem para não mudar o carimbo da versão sob teste: evento de validação no trace (problemas e rascunho, este só com `AGENTE_TRACE_CONTEUDO` ligado), com teste, e rodar `re05` e `rg03` de novo. | P2 |

*(L22 e L25 não existem: o Ex.12 não usou o número 22, e a numeração só cresce.)*

---

## Resposta à questão do enunciado

> *Um auditor que nunca falou com o grupo, com o model card e o repositório na mão, consegue decidir se uma decisão concreta do agente estava dentro da autoridade dele?*

**Em parte, e melhor do que antes, mas só para as execuções de demonstração.** O que um auditor consegue hoje: ler os limites que valem **fora do modelo** (A1–A13, O1–O4, F1–F4), cada um com um teste que **tenta a ação indevida** e roda sem chave; ver, nos 8 registros reais de `logs/parte2/`, o que o modelo chamou e o que o **código** executou; e, com a ferramenta [`evals/reconstruir.py`](../evals/reconstruir.py), reconstruir a decisão a partir **só do trace**, incluindo **quem aprovou, quando e o que corrigiu** (campo $H$).

O que ele **não** consegue, e por quê: **(1)** confirmar **quem** pediu: a identidade é a da sessão, e **não há portal** (L01, §9). **(2)** Conferir o **modelo servido** num registro real (L13). **(3)** Ler um trace **real**: o exemplo acima é de teste; **a rodada B não rodou** (L28). **(4)** Confiar que o registro é **o que aconteceu**: o arquivo é editável (L05). **(5)** Saber se alguém **aceitou** os riscos: o aceite de Erick **não existe** (L15). **(6)** Saber como **parar** o sistema (L16). **(7)** Dizer **por que** o validador reprovou uma resposta: o motivo não está no trace (L29). As lacunas P1 que restam (L01 pela premissa, L06, L14, L26) são as que separam "o sistema se comportou bem nos testes" de "o sistema pode operar com dados reais". **Ele não deve.**
