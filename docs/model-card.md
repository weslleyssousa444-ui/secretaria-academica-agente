# Model card — agente de triagem da secretaria acadêmica

**Exercício 12 — Governança: o *model card* do agente, com evidência.**
**Grupo:** Weslley Soares de Sousa, Pedro Akira, Henrique Gomes Matos e Erick.
**Data:** 16/10/2026. **Commit-base auditado:** `9bc9f8f` (o *model card* e os testes entram no commit seguinte).

## Como ler este documento

Cada campo traz **a afirmação** e **a evidência**. Os tipos de evidência são:

- `arquivo:linha`, com link para o trecho exato no repositório;
- `teste::nome`: um teste em [`tests/`](../tests/) que roda offline, sem chave de API (`python -m pytest tests -v`). A saída de 16/10/2026 está em [`docs/evidencias/pytest.txt`](evidencias/pytest.txt);
- `log`: o registro de uma execução real em [`logs/`](../logs/);
- `saída de comando`: arquivo em [`docs/evidencias/`](evidencias/), com o comando e a saída copiados.

**LACUNA L-xx** marca uma afirmação sem evidência ou um controle que não existe. Todas estão reunidas, com a correção e a prioridade, na seção [Lacunas](#lacunas). Os testes de [`tests/test_lacunas.py`](../tests/test_lacunas.py) **passam descrevendo o defeito**. Quando uma lacuna for corrigida, o teste dela passa a falhar e deve ser invertido.

**O que é "o sistema" aqui.** É o agente de triagem: o laço em [`src/agente.py`](../src/agente.py), o prompt [`prompts/triagem-v1.txt`](../prompts/triagem-v1.txt) e o banco simulado [`src/dados.py`](../src/dados.py). Os pontos de entrada são [`src/chat.py`](../src/chat.py) (conversa), [`src/demo.py`](../src/demo.py) e [`src/verificador.py`](../src/verificador.py). O RAG (Ex.7), a memória (Ex.8), o grafo LangGraph (Ex.9) e o servidor MCP (Ex.10) existem no repositório, mas **não estão ligados ao agente**: `src/agente.py` importa só `dados` ([`src/agente.py:29`](../src/agente.py#L29)), e nenhum arquivo de `src/` menciona MCP ([`autoridade-efetiva.txt`](evidencias/autoridade-efetiva.txt), último comando). Esses componentes aparecem neste documento só onde tratam dado pessoal ou dividem a credencial com o agente.

> **Todos os dados do repositório são sintéticos** ([`docs/case.md` §2.9](case.md)). Base legal, prazos e transferência internacional são avaliados **como se** o sistema fosse implantado com dados reais de alunos. É para isso que o documento serve.

---

## 1. Identificação

| Afirmação | Evidência |
|---|---|
| Nome: agente de triagem da secretaria acadêmica (repositório `secretaria-academica-agente`). | [`README.md:1`](../README.md#L1) |
| Versão do sistema: **não há número de versão nem tag.** A versão é identificada pelo commit: base `9bc9f8f`, prompt `v1`. | [`historico-git.txt`](evidencias/historico-git.txt) (`git tag --list` vazio); [`prompts/triagem-v1.md`](../prompts/triagem-v1.md). **LACUNA L21** |
| Data deste documento: 16/10/2026. | — |
| Grupo: Weslley Soares de Sousa, Pedro Akira, Henrique Gomes Matos, Erick. | [`README.md:3`](../README.md#L3) |
| Responsáveis nomeados **por papel** (produto, desenvolvimento, operação, risco), isto é, quem responde quando algo dá errado: **não definidos.** Todos os commits são de um único autor, e nenhum documento atribui papéis. | [`historico-git.txt`](evidencias/historico-git.txt). **LACUNA L15** |

Matriz a preencher pelo grupo (o documento não inventa nomes):

| Papel | Responde por | Pessoa |
|---|---|---|
| Produto | finalidade, escopo, limiar de escalonamento | *a definir — L15* |
| Desenvolvimento | ferramentas, limites em código, registro | *a definir — L15* |
| Operação | monitorar, interromper o agente | *a definir — L15* |
| Risco | aprovar esta especificação, aceitar riscos | *a definir — L15* |

## 2. Finalidade

| Afirmação | Evidência |
|---|---|
| Para cada solicitação no chat do portal, o agente decide se emite na hora a **declaração de matrícula** ou a **segunda via de histórico**, ou se encaminha o caso à secretaria humana. | [`docs/case.md` §2.1, §2.4](case.md); [`src/agente.py:144`](../src/agente.py#L144) |
| Usuário principal: a atendente da secretaria, cuja fila o agente reduz. Quem conversa com o agente é o aluno. | [`docs/case.md` §2.2](case.md) |
| Regras de negócio: declaração exige matrícula ativa; segunda via exige zero mensalidades em aberto; trancamento é sempre humano. | [`docs/case.md` §2.1](case.md); aplicação no campo 3 |

**Usos fora de escopo.** O agente não deve ser usado para:

- **decidir ou executar trancamento de matrícula.** Não existe ferramenta para isso: `teste::test_nao_existe_ferramenta_de_trancamento`;
- **emitir qualquer documento** fora dos dois do catálogo: `teste::test_emitir_recusa_documento_fora_do_catalogo`;
- **conferir comprovante de pagamento.** Anexos não são lidos ([`docs/arquitetura-v1.md` §1](arquitetura-v1.md)), e a alegação do aluno não substitui o registro financeiro;
- **decidir exceções** (bolsista, liminar, convênio). Elas sempre vão para humano ([`docs/case.md` §2.11](case.md));
- **responder sobre o Regimento.** O RAG do Ex.7 não está ligado ao agente;
- **operar com dados reais de alunos** enquanto L01 (identidade), L05–L07 (registro) e L14 (provedor) estiverem abertas.

**Classificação regulatória** (critérios da nota sobre legislação, situação de out. 2026):

| Regime | Conclusão | Justificativa |
|---|---|---|
| LGPD | Aplica-se a uma implantação real: o agente trata RA, nome, curso, situação de matrícula e situação financeira. | Campo 6 |
| LGPD, art. 20 | O agente **não toma, por desenho, decisão final adversa**: o que é negativo para o aluno (pendência, divergência, RA não encontrado, trancamento) vai para a fila humana. O que ele decide sozinho é favorável (emitir). Essa propriedade depende do modelo chamar `escalar_para_humano`, o que nada no código obriga. | `teste::test_L02_trancamento_escala_so_se_o_modelo_quiser`. **LACUNA L02** |
| ECA Digital | **Provavelmente não se aplica.** O serviço é interno ao portal, o acesso depende de matrícula, não há atratividade para crianças nem interação social entre usuários (art. 1º, parágrafo único, I–III). Um aluno de 16 ou 17 anos atendido continua protegido pela LGPD, art. 14. | Avaliação do grupo, sem parecer da ANPD. **LACUNA L23** |
| AI Act | Não se aplica: o resultado não é usado na União Europeia. | — |
| PL 2338/2023 | Não é lei; não cria obrigação. | — |

## 3. Autoridade

O que o agente pode fazer, e **onde cada limite é aplicado** (ausência de ferramenta, código, credencial, plataforma ou prompt). Limite aplicado só no prompt é marcado como LACUNA.

### 3.1 Escopo, ações proibidas e obrigações

| # | Limite | Onde é aplicado | Evidência |
|---|---|---|---|
| A1 | O agente tem exatamente 4 ferramentas: `buscar_aluno`, `consultar_financeiro` (leitura), `emitir_documento`, `escalar_para_humano` (escrita). | ausência de ferramenta + código | [`src/agente.py:253-260`](../src/agente.py#L253-L260); `teste::test_nao_existe_ferramenta_de_trancamento` |
| A2 | Uma ferramenta que o modelo invente (ex.: `trancar_matricula`) não é executada: o laço devolve erro e nada é gravado. | código | [`src/agente.py:408-412`](../src/agente.py#L408-L412); `teste::test_modelo_pede_ferramenta_inexistente_nada_e_executado` |
| A3 | **Proibido** trancar matrícula, efetivar pagamento ou alterar cadastro e financeiro. | ausência de ferramenta | Só há `INSERT` em `documentos_emitidos` e `casos_pendentes`; nenhum `UPDATE` nem `DELETE` ([`autoridade-efetiva.txt`](evidencias/autoridade-efetiva.txt)) |
| A4 | **Proibido** emitir `trancamento_matricula` ou documento fora do catálogo. | código | [`src/agente.py:182-186`](../src/agente.py#L182-L186); `teste::test_emitir_recusa_trancamento`, `teste::test_emitir_recusa_documento_fora_do_catalogo` |
| A5 | **Proibido** emitir segunda via com mensalidade em aberto, mesmo que o aluno diga que pagou. | código (a ferramenta revalida no momento da escrita) | [`src/agente.py:202-212`](../src/agente.py#L202-L212); `teste::test_segunda_via_bloqueada_com_pendencia`, `teste::test_modelo_desobedece_prompt_e_codigo_barra_emissao` |
| A6 | **Proibido** emitir declaração sem matrícula ativa. | código | [`src/agente.py:195-200`](../src/agente.py#L195-L200); `teste::test_declaracao_bloqueada_matricula_nao_ativa` |
| A7 | **Proibido** emitir para RA inexistente. | código | [`src/agente.py:191-193`](../src/agente.py#L191-L193); `teste::test_emitir_ra_inexistente` |
| A8 | **Proibido** consultar ou emitir para o RA **de outra pessoa**. | **não aplicado.** Nenhuma ferramenta recebe a identidade de quem está no chat; qualquer RA digitado é atendido. | `teste::test_L01_sem_verificacao_de_identidade`; [`docs/arquitetura-v1.md` §2](arquitetura-v1.md) ("integração prevista, não existente"). **LACUNA L01** |
| A9 | Emitir o mesmo documento duas vezes devolve o mesmo protocolo (`ja_existia=true`). | código | [`src/agente.py:214-219`](../src/agente.py#L214-L219); `teste::test_emitir_idempotente` |
| A10 | Escalar duas vezes com a mesma chave não duplica o caso. | código, **mas a chave é escrita pelo modelo** | [`src/agente.py:237-241`](../src/agente.py#L237-L241); `teste::test_escalar_idempotente_pela_chave`; `teste::test_L03_chave_de_idempotencia_vem_do_modelo`. **LACUNA L03** |
| A11 | Trancamento é **sempre** escalado. | **só prompt** e descrição da ferramenta. A parte "não executa" é garantida por A3/A4; a parte "abre o caso" não é. | [`prompts/triagem-v1.txt:13-14`](../prompts/triagem-v1.txt#L13-L14); [`src/agente.py:317-321`](../src/agente.py#L317-L321); `teste::test_L02_trancamento_escala_so_se_o_modelo_quiser`. **LACUNA L02** |
| A12 | Divergência ("já paguei" com pendência): pedir comprovante e, sem ele, escalar. | **só prompt** para pedir e escalar; a proibição de emitir é código (A5) | [`prompts/triagem-v1.txt:15-19`](../prompts/triagem-v1.txt#L15-L19). **LACUNA L11** |
| A13 | Pedir o RA antes de qualquer ferramenta; confirmar o RA uma vez e depois escalar. | **só prompt** (mais a sugestão no erro da ferramenta) | [`prompts/triagem-v1.txt:12`](../prompts/triagem-v1.txt#L12), [`:20-22`](../prompts/triagem-v1.txt#L20-L22); [`src/agente.py:153-157`](../src/agente.py#L153-L157). **LACUNA L11** |
| A14 | Não inventar protocolo, prazo diferente de 48h nem canal de entrega. | **só prompt**: a resposta final ao aluno não é validada contra o resultado das ferramentas | [`prompts/triagem-v1.txt:26-38`](../prompts/triagem-v1.txt#L26-L38). **LACUNA L11** |

### 3.2 Credenciais e privilégios

| # | Limite | Onde é aplicado | Evidência |
|---|---|---|---|
| C1 | Chave do provedor de modelo fora do repositório (`.env` ignorado pelo git). | plataforma (git) | [`.gitignore:1`](../.gitignore#L1); [`.env.example:11`](../.env.example#L11) vazio |
| C2 | Chave **própria** do agente. | **não aplicado.** Agente, RAG, juiz de fidelidade, memória e LangGraph usam a mesma `OPENAI_API_KEY`. | `teste::test_L08_uma_unica_chave_para_todos_os_componentes`; [`autoridade-efetiva.txt`](evidencias/autoridade-efetiva.txt). **LACUNA L08** |
| C3 | Privilégio mínimo no banco (leitura em `alunos`/`financeiro`, escrita só em `documentos_emitidos`/`casos_pendentes`). | **só código.** O SQLite não tem usuário nem permissão; o processo pode ler e escrever tudo, e o limite é o SQL fixo de cada ferramenta. | [`src/dados.py:67-71`](../src/dados.py#L67-L71); [`autoridade-efetiva.txt`](evidencias/autoridade-efetiva.txt). **LACUNA L12** |

**Revisão do que o agente precisa contra o que ele tem:**

| Concessão | Precisa? | Decisão |
|---|---|---|
| `consultar_financeiro` devolve `valor_em_aberto` (R$) | **Não.** A regra usa só a contagem de mensalidades ([`src/agente.py:204-207`](../src/agente.py#L204-L207)), mas o valor vai ao provedor e ao log. | remover o campo: **L12** |
| `buscar_aluno` faz `SELECT *` | Parcial. Nome e curso só servem para o texto do documento, que hoje o modelo redige. | gerar o documento por template em código e tirar o nome do prompt: **L12** |
| Acesso a qualquer RA | **Não.** Só ao RA da sessão autenticada. | **L01** |
| `motivo` livre em `escalar_para_humano` | Parcial. Texto escrito pelo modelo pode carregar dado que o aluno contou (ex.: motivo de saúde para trancar). | enum de motivos: **L03** |

### 3.3 Orçamento e gasto

| # | Limite | Onde é aplicado | Evidência |
|---|---|---|---|
| O1 | Por execução: no máximo 8 passos, 20.000 tokens e US$ 0,05. | código | [`src/agente.py:121-137`](../src/agente.py#L121-L137), [`:446-449`](../src/agente.py#L446-L449); `teste::test_orcamento_de_passos_interrompe`, `teste::test_orcamento_de_tokens_interrompe` |
| O2 | O limite em dinheiro (US$ 0,05) **não tem efeito** nos modelos Groq (preço 0), nem em modelo fora da tabela de preços. | código, inerte | [`src/agente.py:47-64`](../src/agente.py#L47-L64); `teste::test_L04_limite_de_custo_inerte_nos_modelos_groq`. **LACUNA L04** |
| O3 | Laço: a mesma chamada com os mesmos argumentos 3 vezes seguidas interrompe a execução. | código | [`src/agente.py:429-433`](../src/agente.py#L429-L433), [`:451-454`](../src/agente.py#L451-L454); `teste::test_laco_detectado` |
| O4 | Limite por janela (dia ou mês) e por chave. | **não aplicado no código.** O único teto agregado é a cota do *free tier* da Groq, que o grupo não configurou e não controla (200 mil tokens/dia observados em `gpt-oss-20b`). | [`docs/modelos.md` §3.5](modelos.md). **LACUNA L04** |
| O5 | Modelos permitidos. | **não aplicado.** `LLM_MODELO` aceita qualquer valor; não há lista de modelos aprovados. | [`src/agente.py:37`](../src/agente.py#L37). **LACUNA L13** |

### 3.4 Quando um controle falha

| # | Comportamento | Onde é aplicado | Evidência |
|---|---|---|---|
| F1 | Erro 4xx do provedor: termina em `erro_fatal`, sem nenhuma escrita (*fail-closed*). | código | [`src/agente.py:380-384`](../src/agente.py#L380-L384), [`:481-483`](../src/agente.py#L481-L483); `teste::test_erro_da_api_termina_sem_escrita` |
| F2 | 429, 5xx ou falha de conexão: até 8 novas tentativas, com espera de até 90 s lida do cabeçalho; depois, `erro_fatal`. | código | [`src/agente.py:345-385`](../src/agente.py#L345-L385) |
| F3 | Erro do banco dentro de uma ferramenta não é tratado: a exceção derruba o processo. Não há escrita parcial, mas também não há término registrado nem resposta ao aluno. | código, por omissão | [`src/agente.py:414-421`](../src/agente.py#L414-L421) (só `ErroRecuperavel` e `TypeError` são capturados). **LACUNA L16** |
| F4 | Modelo de reserva (*fallback*). | não existe; não há desvio para provedor não aprovado | [`src/agente.py:33-37`](../src/agente.py#L33-L37) |

### 3.5 Quem pode suspender o agente

**Ninguém está designado, e não há mecanismo próprio.** Hoje só existem dois caminhos: encerrar o processo, ou revogar a chave no console da Groq. Essa revogação derruba juntos o RAG e a memória (C2), e nunca foi testada. **LACUNA L15, L16.**

## 4. Ferramentas e integrações

| Ferramenta / integração | Permissão | Contra o quê | Evidência |
|---|---|---|---|
| `buscar_aluno(ra)` | leitura | `alunos` | [`src/agente.py:147-158`](../src/agente.py#L147-L158) |
| `consultar_financeiro(ra)` | leitura | `alunos`, `financeiro` | [`src/agente.py:161-175`](../src/agente.py#L161-L175) |
| `emitir_documento(ra, tipo_documento)` | **escrita**: grava em `documentos_emitidos`. É corrigível por reemissão, mas uma cópia entregue não se recolhe. | `alunos`, `financeiro`, `documentos_emitidos` | [`src/agente.py:178-229`](../src/agente.py#L178-L229); [`docs/arquitetura-v1.md` §7](arquitetura-v1.md) |
| `escalar_para_humano(ra, tipo_pedido, motivo, chave)` | **escrita**: grava em `casos_pendentes` | `casos_pendentes` | [`src/agente.py:232-250`](../src/agente.py#L232-L250) |
| Provedor de modelo (Groq) | **envio a terceiro**: o prompt inteiro, com o resultado das ferramentas, sai a cada chamada | `api.groq.com` | [`src/agente.py:33-37`](../src/agente.py#L33-L37), [`:456-458`](../src/agente.py#L456-L458) |
| Servidores MCP | **nenhum** no agente de triagem | — | [`autoridade-efetiva.txt`](evidencias/autoridade-efetiva.txt) |
| *Fora do agente:* servidor MCP CNPJ/CEP (Ex.10) | envio a terceiro (BrasilAPI); dado de empresa, não de aluno | `brasilapi.com.br` | [`exercicios/aula10-mcp/servidor_cnpj_cep.py:27-30`](../exercicios/aula10-mcp/servidor_cnpj_cep.py#L27-L30) |
| *Fora do agente:* embeddings do RAG e da memória | local; nenhum dado sai | `sentence-transformers` | [`src/indice_rag.py:24`](../src/indice_rag.py#L24) |

## 5. Modelo e provedor

| Afirmação | Evidência |
|---|---|
| Modelo do agente: `qwen/qwen3.8-27b`, `temperature=0`. | [`.env.example:19`](../.env.example#L19); [`src/agente.py:37`](../src/agente.py#L37), [`:458`](../src/agente.py#L458) |
| É um identificador fixo, não um *alias* `-latest`, mas também **não é uma versão datada**: o provedor pode trocar os pesos sob o mesmo nome. | **LACUNA L13** |
| O **modelo efetivamente servido** (`resposta.model`) não é gravado no registro. Os 4 logs de demonstração rodaram, segundo o README, em `openai/gpt-oss-20b`, e nada no log comprova isso. | [`README.md:73`](../README.md#L73); `teste::test_L05_registro_sem_instante_modelo_prompt_nem_revisao`. **LACUNA L13** |
| RAG, juiz de fidelidade e memória usam `openai/gpt-oss-20b`. | [`.env.example:37`](../.env.example#L37); [`src/rag.py:43`](../src/rag.py#L43) |
| Provedor: Groq, endpoint compatível com OpenAI, *free tier* sem contrato. Antes era Mistral; a troca foi registrada em 22/09/2026. | [`.env.example:14`](../.env.example#L14); [`docs/modelos.md` §3.5](modelos.md) |
| **Região de processamento, prazo de retenção e uso dos dados para treino: não verificados.** Nenhum documento do repositório cita os termos de serviço ou o contrato vigentes da Groq. | **LACUNA L14** |

## 6. Dados

### 6.1 Inventário: onde o dado pessoal entra, fica e para onde vai

Dado pessoal tratado: **RA, nome, curso, situação de matrícula, número e valor de mensalidades em aberto, e o texto livre do aluno**. Neste último pode haver dado sensível (art. 11), como "quero trancar porque estou doente". A base legal é **proposta do grupo**: a decisão é jurídica e cabe à instituição (**L19**). A fonte do inventário é [`inventario-dados-pessoais.txt`](evidencias/inventario-dados-pessoais.txt).

| Lugar | Dado | Finalidade | Base legal proposta (art. 7º) | Prazo de guarda | Fere a minimização? |
|---|---|---|---|---|---|
| **Entrada / histórico da conversa** (`Estado.historico`) | mensagem livre do aluno, RA | identificar o pedido | V (execução do contrato educacional) | duração da conversa, em memória do processo | **sim**: o texto livre não é filtrado; dado sensível entra sem *guardrail* (**L11**) |
| **Prompt enviado à Groq** (a cada volta do laço) | system prompt + histórico inteiro + resultado das ferramentas: nome, curso, situação, mensalidades, **valor em aberto** | o modelo decidir e redigir a resposta | V; e transferência internacional pelo art. 33, **sem hipótese demonstrada** | **desconhecido** (termos não verificados) | **sim**: valor em aberto e nome não são necessários para decidir ([`src/agente.py:170`](../src/agente.py#L170), [`:388-389`](../src/agente.py#L388-L389)). **L12, L14** |
| **Banco** `dados/academico.db`: `alunos`, `financeiro` | cadastro e financeiro | sistema de origem (simulado) | V | indefinido (é o sistema acadêmico) | não; fora do controle de versão ([`.gitignore:8`](../.gitignore#L8)) |
| **Banco**: `documentos_emitidos`, `casos_pendentes` | RA, tipo, data, motivo (texto do modelo) | prova da emissão; fila humana | V; II para a emissão de documento acadêmico, se for obrigação regulatória (conferir) | **indefinido**: não há expurgo | **sim** no `motivo` livre (**L03**); prazo indefinido (**L20**) |
| **Índice RAG** (`dados/embeddings_regimento.npz`) | só o Regimento simulado; nenhum titular | responder sobre normas | — (não é dado pessoal) | — | não: o Regimento não contém RA ([`inventario-dados-pessoais.txt`](evidencias/inventario-dados-pessoais.txt), 1º comando) |
| **Memória** (Ex.8, não ligada ao agente): `dados/memoria_episodica.json`, `memoria_semantica.json`, `memoria_procedural.json` | episódios com RA e resumo, vetor, fato `RA:situacao_financeira` | lembrar pedidos anteriores do aluno | IX (legítimo interesse), **sem teste de balanceamento** | **nenhum prazo**: o decaimento de 180 dias rebaixa o episódio, não o apaga ([`src/memoria_episodica.py:62-77`](../src/memoria_episodica.py#L62-L77)) | prazo indefinido (**L20**). A remoção a pedido existe e é verificada ([`src/memoria.py:76-111`](../src/memoria.py#L76-L111)) |
| **Checkpoints** `checkpoints/` (Ex.8) e `exercicios/aula09-langgraph/checkpoints.sqlite` (Ex.9) | argumentos de ferramenta com RA | retomar execução | V | efêmero | o primeiro já estava fora do git ([`.gitignore:13`](../.gitignore#L13)); o do LangGraph **não estava** e foi incluído no `.gitignore` nesta entrega |
| **Log de execução** `logs/0*.json` | histórico inteiro: nome, curso, valor em aberto e **o raciocínio do modelo em texto livre** | demonstração e depuração | IX ou VI (prova, exercício regular de direitos) | **indefinido e público**: versionado no git de um repositório público desde 04/09/2026 | **sim**: guarda conteúdo onde a referência bastaria, inclusive o raciocínio. `teste::test_L06_log_versionado_guarda_dado_pessoal_e_raciocinio`. **L06** |
| **Relatórios** `logs/verificador.json`, `logs/avaliar_rag.json`, `logs/modos_de_falha.json` | ids de caso e perguntas; sem nome nem valor | avaliação | — | versionado | não |
| **Saída do terminal** (`verboso=True`) | resultado das ferramentas, truncado em 90 caracteres | depuração | — | sessão do terminal | baixo ([`src/agente.py:477-480`](../src/agente.py#L477-L480)) |

### 6.2 Onde a minimização falha, em resumo

1. **O log guarda tudo, para sempre, em público** (L06): nome e valor em aberto, quando bastaria o RA pseudonimizado e o *hash* do documento; e o raciocínio do modelo, que não é prova de nada.
2. **O provedor recebe mais do que a decisão usa** (L12): o valor em aberto e o nome.
3. **Texto livre sem filtro** (L11): o que o aluno digitar vai ao provedor, ao log e, via `motivo`, à fila.
4. **Nenhuma estrutura tem prazo de guarda** (L20): banco, memória e logs.
5. **Os nomes "fictícios" incluem três integrantes do grupo** (`teste::test_L09_nomes_da_base_sintetica_coincidem_com_o_grupo`), o que contradiz a afirmação de [`docs/case.md` §2.9](case.md) (L09).

## 7. Avaliação

| Afirmação | Evidência |
|---|---|
| Suíte: 40 casos rotulados ([`dados/casos_verificador.json`](../dados/casos_verificador.json)), rodados por [`src/verificador.py`](../src/verificador.py). O rótulo é regra de negócio determinística. Critério: ≥ 34/40 **e** 0 falsos negativos em trancamento. | [`src/verificador.py:27`](../src/verificador.py#L27), [`:80-81`](../src/verificador.py#L80-L81); [`docs/case.md` §2.7](case.md) |
| Versão da suíte: **sem número.** O conjunto é identificado só pelo commit `ba7fb89`. | **LACUNA L18** |
| Resultado agregado: **35/40 (87,5%), 0 falsos negativos em trancamento**, com `qwen/qwen3.8-27b`, em 23/09/2026. | [`logs/verificador.json`](../logs/verificador.json) |
| Por fatia: declaração 8/8, segunda via 8/8, divergência 6/6, trancamento 8/8, RA inexistente 3/4, **pendência 2/6**. | [`verificador-por-fatia.txt`](evidencias/verificador-por-fatia.txt) |
| **O relatório não é a saída direta do script.** O script grava `termino` e `n_passos` por caso e não grava modelo nem data; o arquivo versionado tem `modelo`, `data`, `metodologia` e `fonte_verificacao`, e combina duas rodadas com um reteste isolado. O número não se reproduz rodando o script uma vez. | [`verificador-por-fatia.txt`](evidencias/verificador-por-fatia.txt) (comandos 2 e 3); [`src/verificador.py:105-109`](../src/verificador.py#L105-L109). **LACUNA L18** |
| Juiz do verificador: não há LLM. A decisão é lida da trajetória por código, em `classificar_decisao`. A concordância desse classificador com avaliação humana **não foi medida**; um bug de *substring* já foi achado e corrigido, e há uma divergência conhecida de precedência (`r03`). | [`src/verificador.py:30-56`](../src/verificador.py#L30-L56); [`docs/modelos.md` §3.5](modelos.md). **LACUNA L18** |
| Juiz do RAG (fidelidade 80%): é um LLM, **o mesmo modelo que gera a resposta**. A concordância com avaliação humana **não foi medida**. | [`src/avaliar_rag.py:45-60`](../src/avaliar_rag.py#L45-L60); [`logs/avaliar_rag.json`](../logs/avaliar_rag.json). **LACUNA L18** |
| Comparação de 5 casos × 3 modelos: **nunca executada.** | [`README.md:160`](../README.md#L160); [`docs/modelos.md` §3.3](modelos.md). **LACUNA L18** |
| Testes de autoridade offline: 24 testes, todos passando em 16/10/2026: 14 provam os limites aplicados em código e 10 fixam as lacunas. | [`docs/evidencias/pytest.txt`](evidencias/pytest.txt) |

## 8. Limites conhecidos

| Modo de falha observado | Evidência |
|---|---|
| **Pendência sem divergência** (série `p`): o agente pergunta pelo comprovante e não conclui em um turno; o caso de teste só tem uma mensagem. Resultado: 4 de 6 sem decisão. | [`verificador-por-fatia.txt`](evidencias/verificador-por-fatia.txt); [`docs/modelos.md` §3.5](modelos.md) |
| **Trancamento com RA inexistente** (`r03`): o classificador dá precedência a trancamento. | [`src/verificador.py:43-44`](../src/verificador.py#L43-L44) |
| **Instabilidade do *free tier*:** `erro_fatal` transitório em `d05`, `v01`, `t03` e `t08` na primeira rodada. | [`docs/modelos.md` §3.5](modelos.md) |
| **Teto de 1.000 tokens de saída por minuto** do `qwen/qwen3.8-27b` inviabiliza o RAG nesse modelo. | [`src/rag.py:36-43`](../src/rag.py#L36-L43) |
| **Exceções do regimento** (bolsista, liminar, convênio) não são cobertas e vão sempre para humano. | [`docs/case.md` §2.11](case.md) |
| **Concorrência:** o protocolo é `COUNT(*) + 1`. Duas emissões simultâneas geram o mesmo protocolo e violam a chave primária. | [`src/agente.py:221`](../src/agente.py#L221), [`:243`](../src/agente.py#L243) |
| **Variante LangGraph:** o protocolo usa `hash()` do Python, que muda a cada processo, e o mesmo pedido recebe protocolos diferentes. | `teste::test_L10_protocolo_do_langgraph_depende_do_hash_do_processo`; [`exercicios/aula09-langgraph/agente_langgraph.py:91`](../exercicios/aula09-langgraph/agente_langgraph.py#L91) |

**Não usar, mesmo dentro da finalidade:** em mais de uma sessão simultânea; com dados reais enquanto L01 estiver aberta; quando o aluno anexar comprovante (o agente não lê anexos); como fonte de resposta sobre o Regimento.

## 9. Riscos aceitos

"Aceito" exige quem aceitou. Como não há responsável de risco nomeado (L15), a tabela separa os riscos que **o grupo já registrou como decisão** em documentos versionados dos que este documento **propõe** aceitar, pendentes de aprovação.

| Risco | Razão | O que o limita | Situação | Evidência |
|---|---|---|---|---|
| Cobertura menor que o alvo de 60%: toda exceção vai para humano. | Errar para o lado conservador é mais barato que aprovar indevidamente. | A fila humana absorve os casos. | **registrado pelo grupo** | [`docs/case.md` §2.5, §2.11](case.md) |
| Divergência nunca é resolvida a favor do aluno sem comprovante. | Evita afrouxar a regra para inflar a cobertura (caso Klarna). | A5, em código. | **registrado pelo grupo** | [`docs/case.md` §2.5](case.md) |
| Documento emitido por engano não é recolhido; reemitir não desfaz a entrega. | É inerente a entregar documento. | A4–A7 revalidam a regra no momento da escrita. | **registrado pelo grupo** | [`docs/arquitetura-v1.md` §7](arquitetura-v1.md) |
| O log de um exercício anterior com RA não é apagado num pedido de remoção. | Conflito entre LGPD e auditoria acadêmica. | Dados sintéticos. | **registrado como "risco aberto"**, sem decisão | [`docs/memoria.md` §2.3](memoria.md) |
| *Free tier* da Groq sem contrato e sem termos verificados. | Protótipo acadêmico, sem custo. | Nenhum dado real entra. **Deixa de valer com dado real.** | *proposto, pendente* | L14 |
| Repositório público com logs que contêm nomes. | Os dados são sintéticos. | Nenhum titular real, exceto a coincidência de L09. | *proposto, pendente* | L06, L09 |
| `temperature=0` não garante a mesma saída em execuções repetidas. | É limitação do provedor. | A decisão é medida pela trajetória, não pelo texto. | *proposto, pendente* | [`src/agente.py:458`](../src/agente.py#L458) |

## 10. Supervisão humana

| Afirmação | Evidência |
|---|---|
| No agente principal **nada pausa para aprovação.** O agente não espera um humano: ele *entrega* o caso à fila (`casos_pendentes`, `status='aberto'`) e encerra. | [`src/agente.py:232-250`](../src/agente.py#L232-L250); [`src/dados.py:100-107`](../src/dados.py#L100-L107) |
| Vão para a fila: trancamento, divergência não resolvida, pendência e RA não encontrado. **Quem encaminha é o modelo** (A11–A13). | [`prompts/triagem-v1.txt:13-22`](../prompts/triagem-v1.txt#L13-L22). **LACUNA L02, L11** |
| Quem decide os casos: a atendente; o trancamento, a coordenação. Isso é **declarado, não implementado**: não há tela, consumidor da fila nem registro da decisão humana. | [`docs/case.md` §2.2](case.md). **LACUNA L17** |
| Prazo: "48h" é um texto fixo devolvido pela ferramenta. Não há controle de vencimento nem o que fazer quando vence. | [`src/agente.py:250`](../src/agente.py#L250). **LACUNA L17** |
| A variante LangGraph (Ex.9) pausa com `interrupt()` antes de escalar um trancamento e retoma com `Command(resume=...)`. Não define quem aprova nem prazo, e uma recusa não abre caso nenhum. | [`exercicios/aula09-langgraph/agente_langgraph.py:158-188`](../exercicios/aula09-langgraph/agente_langgraph.py#L158-L188) |
| Interrupção do agente: não há procedimento, responsável nem teste (campo 3.5). | **LACUNA L16** |

## 11. Registro e retenção

O registro de cada decisão comparado com a tupla $R = (id, t, x, C, V, \Phi, P, H, y)$ da nota sobre provar a decisão:

| Campo | Guardado? | Evidência |
|---|---|---|
| $id$ | sim, `execucao_id` (8 caracteres hex). **Não** aparece na resposta ao aluno nem em `documentos_emitidos`/`casos_pendentes`: não se liga o protocolo `DOC-1002` ao log que o gerou. | [`src/agente.py:104`](../src/agente.py#L104); [`src/dados.py:94-107`](../src/dados.py#L94-L107). **LACUNA L05** |
| $t$ (instante) | **não** | `teste::test_L05_registro_sem_instante_modelo_prompt_nem_revisao` |
| $x$ (entrada) | sim, no `historico` | [`logs/01-caso-simples-695426dc.json`](../logs/01-caso-simples-695426dc.json) |
| $C$ (contexto recuperado) | não se aplica: o agente não recupera do índice | — |
| $V$ (modelo servido, prompt, versão do sistema) | **não** | `teste::test_L05_registro_sem_instante_modelo_prompt_nem_revisao`. **LACUNA L05, L13** |
| $\Phi$ (ferramentas, argumentos, resultados) | sim, em `passos` | [`logs/02-divergencia-9aee9313.json`](../logs/02-divergencia-9aee9313.json) |
| $P$ (política e versão) | **não**: as regras estão no código, sem versão própria; o commit é o único substituto. | **LACUNA L05** |
| $H$ (revisão humana, ou a ausência registrada) | **não** | **LACUNA L05** |
| $y$ (saída) | sim, a última mensagem do `historico` | log acima |

| Afirmação | Evidência |
|---|---|
| **`demo.py` e a API (Ex.13) gravam registro de execução**; a API regrava o registro da conversa a cada turno, no volume (`/dados/logs`). `chat.py` (teste manual) e `verificador.py` continuam sem gravar. | `teste::test_L07_chat_nao_grava_registro_de_execucao`; [`inventario-dados-pessoais.txt`](evidencias/inventario-dados-pessoais.txt) (último comando). **LACUNA L07** |
| O log é serializado com `default=str`: as mensagens do modelo viram texto, incluindo o raciocínio interno. | [`src/agente.py:486-494`](../src/agente.py#L486-L494); `teste::test_L06_log_versionado_guarda_dado_pessoal_e_raciocinio` |
| Armazenamento: arquivo JSON comum, editável, sem *append-only* nem encadeamento por *hash*. | [`src/agente.py:492`](../src/agente.py#L492). **LACUNA L05** |
| Prazo de guarda: **nenhum.** Os logs estão no git desde 04/09/2026 e ficam no histórico mesmo se apagados. | [`inventario-dados-pessoais.txt`](evidencias/inventario-dados-pessoais.txt). **LACUNA L20** |
| Acesso: qualquer pessoa, porque o repositório é público. | `git ls-remote` sem credencial ([`inventario-dados-pessoais.txt`](evidencias/inventario-dados-pessoais.txt)). **LACUNA L06** |

## 12. Histórico de mudanças

| Versão (commit) | Data | O que mudou | Quem aprovou |
|---|---|---|---|
| `069942e` | 04/09/2026 | Parte 1: case, modelos, agente, verificador | *não registrado* |
| `3757506`, `f1ac1ed` | 18/09/2026 | Arquitetura v1, base de conhecimento v1 | *não registrado* |
| `1679bb1` | 22/09/2026 | Reconfirmação de preços da Mistral | *não registrado* |
| `4a41964` | 22/09/2026 | **Troca de provedor Mistral → Groq**: muda para onde vai o dado | *não registrado* |
| `ba7fb89` | 23/09/2026 | Execução real: 4 demonstrações + verificador (35/40); logs com dado pessoal entram no git | *não registrado* |
| `8423133` | 25/09/2026 | RAG sobre o Regimento (Ex.7) | *não registrado* |
| `a4eefb3` | 25/09/2026 | Memória (Ex.8) | *não registrado* |
| `5fd36fb` | 02/10/2026 | LangGraph e MCP (Ex.9, Ex.10) | *não registrado* |
| `4a3452a`, `9bc9f8f` | 02/10/2026 | Chat interativo; regra do prompt contra inventar passo do processo | *não registrado* |
| `b3f4596` | 16/10/2026 | *Model card*, testes de governança, evidências; `.gitignore` passa a cobrir o checkpoint do LangGraph | *não registrado* |
| commit do Ex.13 | 16/10/2026 | Imagem Docker (usuário sem privilégio), API (`src/api.py`) com estado em volume, pipeline de CI/CD; `ACADEMICO_DB` e pasta de `salvar_log` configuráveis ([`docs/empacotamento.md`](empacotamento.md)) | *não registrado* |

Evidência: [`historico-git.txt`](evidencias/historico-git.txt). Todos os commits têm um único autor e não passaram por *pull request* nem revisão. Uma mudança que altera autoridade ou destino do dado, como a troca de provedor em `4a41964`, entrou sem aprovação registrada. **LACUNA L21.**

---

## Lacunas

Prioridade: **P1**, impede operar com dados reais; **P2**, corrigir antes da Parte 3; **P3**, melhoria.

| ID | Lacuna | Correção proposta | Prioridade |
|---|---|---|---|
| L01 | Não há verificação de identidade: qualquer pessoa consulta o financeiro e emite documento de qualquer RA (A8). | Passar o `ra_autenticado` da sessão ao `Estado` e fazer as 4 ferramentas recusarem, em código, RA diferente do autenticado. Inverter `test_L01`. | **P1** |
| L02 | O escalonamento de trancamento (e de todo caso negativo) depende do modelo (A11). | Pós-condição no fim de `conversar()`: se o término é `respondeu`, há RA identificado e nenhuma escrita bem-sucedida, abrir o caso em código, com motivo "sem decisão do agente". Classificar o pedido por roteador determinístico, como em `arquitetura-v1.md` §3. | **P1** |
| L05 | O registro não tem instante, modelo servido, versão de prompt e de política, campo $H$, nem ligação com o protocolo; é editável. | Acrescentar `t`, `modelo_pedido`, `modelo_servido` (`resposta.model`), `prompt_sha256`, `commit`, `revisao_humana` (com "não houve" explícito) ao `Estado`; gravar `execucao_id` em `documentos_emitidos`/`casos_pendentes`; arquivo só de acréscimo. | **P1** |
| L06 | Logs com nome, valor e raciocínio do modelo versionados em repositório público, sem prazo. | Registrar referência (RA pseudonimizado, *hash*) em vez de conteúdo; não serializar o raciocínio; tirar `logs/0*.json` do git em produção e definir o acesso. | **P1** |
| L07 | **Parcialmente corrigida no Ex.13:** a API, que é o ponto de entrada em produção, grava o registro a cada turno (`teste::test_conversa_em_dois_turnos_emite_e_grava_registro`); `chat.py` ainda não grava. | Chamar `salvar_log` em todo término de `chat.py`, inclusive em erro. | P2 |
| L14 | Região, retenção e uso para treino da Groq não verificados; sem contrato nem hipótese do art. 33. | Conferir os termos vigentes da Groq, registrar a data e o link aqui e em `docs/fontes.md`; para dado real, provedor com contrato de operador e cláusulas-padrão (Resolução CD/ANPD nº 19/2024). | **P1** |
| L15 | Nenhum responsável nomeado por papel; ninguém designado para suspender o agente. | Preencher a matriz do campo 1 e a matriz de responsabilidade da nota sobre governar a ação, §7.4. | **P1** |
| L03 | A chave de idempotência e o `motivo` do escalonamento são texto livre do modelo. | Calcular a chave em código (`ra:tipo_pedido:categoria`), com `motivo` como enum. Inverter `test_L03`. | P2 |
| L04 | O limite em dinheiro é inerte (preço 0), e não há limite por janela nem por chave. | Limitar tokens por dia e por mês, em código, com alerta a 80%; tratar modelo fora da tabela de preços como erro, não como custo 0. | P2 |
| L08 | Uma única chave para agente, RAG, juiz, memória e LangGraph. | Uma chave por carga de trabalho (`TRIAGEM_API_KEY`, `RAG_API_KEY`, ...), para atribuir gasto e revogar só uma. | P2 |
| L11 | Regras só no prompt: pedir o RA antes, pedir comprovante, confirmar o RA uma vez, não inventar protocolo, prazo ou canal; texto livre sem filtro. | Contadores de confirmação de RA no `Estado`; validar em código que todo protocolo citado na resposta veio de uma ferramenta; mascarar dado sensível antes do envio. | P2 |
| L12 | Sem privilégio mínimo no banco; `valor_em_aberto` e o nome vão ao provedor sem necessidade. | Tirar `valor_em_aberto` de `consultar_financeiro`; gerar o documento por template em código; para banco real, usuário de serviço com `SELECT` em `alunos`/`financeiro` e `INSERT` só nas duas tabelas. | P2 |
| L13 | Modelo sem versão datada; modelo servido não registrado; sem lista de modelos aprovados. | Gravar `resposta.model`; validar `LLM_MODELO` contra uma lista aprovada no início do processo. | P2 |
| L16 | Sem procedimento de interrupção nem responsável; erro de banco derruba o processo sem término registrado. No container, `docker stop` encerra a API em 1,1 s ([`evidencias/empacotamento.txt`](evidencias/empacotamento.txt) §4), mas não há exercício periódico nem dono. | Interruptor (variável ou arquivo) lido a cada volta do laço; capturar exceções de ferramenta como término `erro_fatal`; exercício de desligamento registrado. | P2 |
| L17 | Fila humana sem consumidor, sem registro da decisão humana e sem controle do prazo de 48h. | Tabela de decisões (`protocolo`, quem decidiu, quando, o quê); prazo controlado com alerta no vencimento. | P2 |
| L18 | Suíte sem versão; relatório montado à mão; série `p` sem segundo turno; concordância do classificador e do juiz de fidelidade com humanos não medida; comparação de modelos nunca rodada. | Versionar a suíte; o script grava modelo, data e commit; dar o segundo turno à série `p`; rotular à mão uma amostra e medir a concordância; rodar `comparar_modelos.py`. | P2 |
| L19 | Base legal não decidida pela instituição; sem encarregado. | Validar a tabela do campo 6 com o jurídico ou encarregado da instituição. | P2 |
| L20 | Nenhuma estrutura tem prazo de guarda; o decaimento da memória não elimina. | Prazo por finalidade (memória: um semestre; registro de decisão: prazo de contestação) e rotina de expurgo registrada. | P2 |
| L09 | Três nomes "fictícios" coincidem com integrantes do grupo. | Trocar por nomes sem relação com pessoas reais, ou corrigir a afirmação de `case.md` §2.9. | P3 |
| L10 | O protocolo do LangGraph depende de `hash()` do processo. | Derivar o protocolo de um contador ou de um *hash* estável (`hashlib`) do conteúdo. | P3 |
| L21 | Sem número de versão nem aprovação registrada das mudanças. A partir do Ex.13, a imagem publicada recebe a tag do SHA do commit (pipeline `imagem`). | Tag por versão entregue; mudanças em autoridade ou dados por *pull request* aprovado por outro integrante. | P3 |
| L23 | A classificação no ECA Digital não foi confirmada; aluno menor de 18 anos não tem tratamento próprio. | Registrar a análise e, se houver alunos menores de 18 anos, aplicar o padrão mais protetivo (sem memória persistente). | P3 |

---

## Resposta à questão do enunciado

> *Um auditor que nunca falou com o grupo, com o model card e o repositório na mão, consegue decidir se uma decisão concreta do agente estava dentro da autoridade dele?*

**Em parte, e só para as execuções de demonstração.** Para os 4 casos de `logs/0*.json`, sim: o log tem cada ferramenta chamada, com argumentos e resultado, e os limites que valem fora do modelo (A1–A10, O1–O3, F1) estão no código e são exercitados por testes que o auditor roda sem chave. Ele confirma, por exemplo, que no caso `02-divergencia` o agente não emitiu a segunda via e que, se tivesse tentado, a ferramenta teria recusado.

Para uma decisão real, não. Uma conversa pelo `chat.py` não deixa registro (L07). Mesmo num log, o auditor não sabe que modelo decidiu nem quando (L05, L13). Também não sabe se quem pediu era o titular do RA (L01). E não tem a quem perguntar (L15). As lacunas P1 são exatamente as que separam "o sistema se comportou bem nos testes" de "o sistema consegue provar o que fez".
