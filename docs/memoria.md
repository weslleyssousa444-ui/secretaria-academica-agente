# Exercício 8 — A memória do agente de triagem

**Grupo:** Weslley Soares de Sousa, Pedro Akira, Henrique Gomes Matos e Erick.
**Data:** 25/09/2026.
**Natureza:** decisão de projeto (não se escreve código aqui); o par prático que implementa estas decisões está em [`exercicios/aula-08-memoria-do-case.md`](../exercicios/aula-08-memoria-do-case.md).

**O que o agente não guarda, e o que perde quando perde (resposta ao final do enunciado):** não guarda nada do sistema financeiro real (é sintético agora, mas a regra vale para quando deixar de ser — dado sensível não replicado fora do sistema de origem), não guarda latência/contagem de passos (ruído), e não guarda RA fora do campo de metadado dedicado (senão a remoção por titular vira varredura textual sobre tudo). O que perde ao não guardar: nada que dependa de reconstruir uma decisão passada em detalhe — para isso existe o *checkpoint*, não a memória.

---

## Decisão 1 — Como o agente lembra

### 1.1 Os dois níveis, no domínio da secretaria acadêmica

| | curto prazo | longo prazo |
|---|---|---|
| o que é | a conversa corrente com o aluno (Estado, `src/agente.py`) | o que atravessa conversas de alunos diferentes, em dias diferentes |
| conteúdo | prompt de triagem, RA sendo confirmado, campos extraídos, trajetória de ferramentas chamadas nesta solicitação | episódica (pedidos anteriores por RA), semântica (fatos estáveis sobre o aluno), procedural (regras de triagem aprendidas de erro) |
| persistido como | **checkpoint**: um JSON por execução, hoje já produzido por `salvar_log()` (`logs/NN-*.json`) — na prática, a mesma peça que a nota 01 §8 descreve, só sem o nome | índice vetorial local (`dados/memoria_episodica.json`), chave-valor (`dados/memoria_semantica.json`), texto (`dados/memoria_procedural.json`) |
| lido | uma vez, se a conversa for retomada (não implementado ainda — Ex.6 não tem confirmação assíncrona) | por relevância, filtrado pelo RA, a cada nova solicitação do mesmo aluno |
| acesso | por `execucao_id` | por RA (episódica e semântica) ou sempre (procedural) |
| ciclo de vida | morre com a solicitação resolvida | acumula entre solicitações |

**O que exatamente vai para o checkpoint, e por quê:** `passos` (ferramenta, argumentos, resultado, erro — cada consulta ao cadastro/financeiro e cada emissão/escalonamento), `historico`, `termino`, `tokens_gastos`, `motivo`. Isso responde às três perguntas do enunciado (§1.2):

- **Retomável sem repetir efeito colateral?** Sim — `passos` tem o resultado de cada `emitir_documento`/`escalar_para_humano` já executado; retomar não os reexecuta, só continua do próximo.
- **Aprovação humana chegando depois, de outro processo?** É o caso que falta implementar: hoje o trancamento é sempre encaminhado à coordenação (`docs/case.md` §2.4), mas o agente não pausa aguardando a decisão da coordenação — ele encerra com `HUMANO` e a conversa acaba ali. A Parte 2 precisaria fechar esse laço: retomar a conversa quando a coordenação decidir.
- **Estado defeituoso carregado para depuração?** Sim, já é assim: `logs/verificador.json` e os logs de demo já servem esse propósito hoje (Ex.6).

### 1.2 O orçamento da janela

Cinco fontes disputando a janela do agente de triagem:

| Fonte | Teto | Descartada primeiro? |
|---|---|---|
| System prompt (`prompts/triagem-v1.txt`) | ~400 tokens, fixo | nunca |
| Objetivo/pedido do aluno | ~200 tokens | nunca |
| Trajetória da conversa corrente | até o teto de 20.000 tokens do orçamento do agente (`Orcamento.max_tokens`, `src/agente.py`) | 3º |
| Memória de longo prazo (episódica + semântica + procedural) | **400 tokens** (`OrcamentoDeMemoria.max_tokens_memoria`, `src/memoria.py`) | **1º** |
| Trechos do Regimento Acadêmico (RAG, Ex.7) | `k=3` trechos, ~600 tokens | 2º |

**Ordem de descarte quando estoura:** memória de longo prazo primeiro (é a fonte mais fácil de reconstruir na próxima consulta — perder um episódio não perde o dado estruturado que o `buscar_aluno`/`consultar_financeiro` já resolve de qualquer forma), depois os trechos do RAG (perder um artigo do regimento é pior, mas ainda recuperável na próxima busca), e a trajetória da conversa corrente por último (perder isso é perder o que o aluno já disse nesta conversa, que não tem como ser refeito sem perguntar de novo).

Medido em `src/memoria.py::montar_bloco_memoria`: quando o bloco de memória excede 400 tokens, o episódico é cortado primeiro, mantendo procedural + semântica — a mesma lógica de descarte, em código.

### 1.3 As três memórias, no domínio

| Tipo | O que guarda no case | Estrutura | Como é recuperada |
|---|---|---|---|
| **episódica** | pedidos anteriores do mesmo aluno e o desfecho: *"RA 20230198 pediu segunda via em 01/08, escalado por divergência financeira"* | índice vetorial local (`sentence-transformers`, mesma escolha do Ex.7 — a Groq não tem endpoint de embeddings) | `recuperar(consulta, k, ra=...)` — filtra por RA **antes** de ordenar por similaridade (Aula 07, nota 02 §2), depois pondera por recência (decaimento, §2.2 abaixo) |
| **semântica** | fato estável sobre o RA: *"situação financeira = quitado (20/09/2026)"*, *"último canal de contato = chat do portal"* | chave-valor (`entidade:chave`), JSON | `ler(ra, chave)` — zero chamadas, zero ambiguidade |
| **procedural** | regra extraída de um erro de execução: *"RAs podem vir com espaço por erro de digitação; normalizar antes de consultar `buscar_aluno`"* | texto, injetado no system prompt via `MemoriaProcedural.como_system_prompt()` | sempre presente, sem filtro de relevância — por isso exige aprovação (`aprovada=True`) antes de valer |

**Por que a estrutura de cada uma não é intercambiável:** medido em `src/memoria_demo.py` — a consulta episódica levou **448 ms** (embedding da consulta + produto vetorial); a consulta semântica levou **0,00 ms** (é um `dict.get`). Perguntar "o RA X está com pendência financeira?" por similaridade, quando a resposta é um fato de chave exata, paga um custo cem vezes maior por nada.

### 1.4 Quem escreve, e o que não entra

**Política:** o código extrai por regra, ao final da execução do agente de triagem (nota 03 §1.2) — não o próprio agente via ferramenta `lembrar` (arriscaria registrar ruído a cada passo de uma triagem que já é curta) e não revisão humana em massa (não escala para o volume esperado de pedidos, `docs/case.md` §2.5). A exceção é a memória **procedural**: toda regra nasce com `aprovada=False` e só entra no prompt depois de revisão humana — é a única das três sem filtro de relevância na leitura, então uma regra errada contaminaria toda solicitação futura.

**Volume por execução:** ~2 registros episódicos (o pedido e o desfecho), ~1 fato semântico (o campo que mudou, se algum mudou), 0-1 regra procedural (só quando a execução corrigiu um erro generalizável).

**O que não entra:**

- **dado sensível não sintético** — nesta v1 tudo é fictício (`docs/case.md` §2.9); quando o sistema tocar dado real, nenhum dado financeiro ou de matrícula entra na memória além do que os campos já estruturados (`situacao_financeira`, não o extrato completo) exigem;
- **RA fora do campo de metadado dedicado** — nunca em texto livre sem o campo `ra` correspondente, porque senão a remoção por titular (§2.3) vira varredura textual sobre tudo, sem nenhuma garantia de cobertura;
- **latência, contagem de passos, tentativa de ferramenta já corrigida no mesmo turno** — ruído de execução (Aula 08, nota 02 §4); é exatamente o que `logs/*.json` (o checkpoint) já guarda, então guardá-lo de novo na memória é duplicar, não lembrar;
- **o que é derivável** — a situação de matrícula do aluno não vai para a memória: `buscar_aluno(ra)` já resolve isso em toda execução, sem custo de manutenção de uma cópia que pode ficar desatualizada.

---

## Decisão 2 — Como o agente esquece

### 2.1 Contradição — o fato que mudou

**O par encontrado no domínio:** a situação financeira de um RA muda com o tempo. Medido de verdade (`src/memoria_demo.py`, dados sintéticos sobre o RA 20230198):

| Data | Fato |
|---|---|
| 2026-08-01 | "RA 20230198 tem 2 mensalidades em aberto; pedido de segunda via escalado por divergência financeira." |
| 2026-09-20 | "RA 20230198 quitou as mensalidades em aberto; pendência financeira resolvida." |

Similaridade medida contra a pergunta *"o RA 20230198 tem pendência financeira?"*: **0,6927** (fato de setembro) contra **0,6715** (fato de agosto) — uma diferença de 0,021, que não é margem suficiente para confiar cegamente em qual dos dois "ganhou" por acaso. Neste caso específico o vetor favoreceu o fato certo; **isso é sorte, não garantia** — a mesma medição, com outra redação, poderia inverter (é exatamente o achado da Aula 08 nota 04 §1: o vetor mede parecença de assunto, não anterioridade).

**Regra de desempate:** determinística, `max()` sobre o campo `data` (`src/memoria_episodica.py::mais_recente`). Nenhuma chamada ao modelo. **O descarte é registrado**, não silencioso — `desempatar_por_tempo()` devolve o vencedor e a lista de descartados, para que uma auditoria distinga "o sistema não sabia da pendência antiga" de "o sistema sabia e descartou por ser anterior".

### 2.2 Decaimento — o fato que envelheceu sem ser contradito

**Corte:** meia-vida de **180 dias** (`meia_vida_dias=180` em `MemoriaEpisodica.recuperar`) — aproximadamente um semestre letivo, que é a unidade de tempo natural do domínio: um episódio de trancamento ou pendência do semestre anterior perde peso quando o semestre corrente já resolveu a questão (rematrícula, quitação), mas não some de imediato.

**Efeito:** **rebaixado**, não removido. O `score_ponderado` multiplica a similaridade por `0.5 ** (idade_dias / 180)` — um episódio de um ano atrás (365 dias) ainda é recuperável se for o único que trata do assunto (nenhum outro RA tem esse peso), mas perde a disputa contra um episódio recente equivalente. É a mesma decisão que a nota 04 §2 recomenda: apagar por idade descartaria o episódio raro e relevante (ex.: o único trancamento por liminar judicial que já ocorreu), e não fazer nada deixaria o antigo competir para sempre com o novo.

### 2.3 Remoção — o titular solicitou

**Estruturas em que o RA de um aluno pode ter caído**, e a lista tem mais que as três memórias (medido em `src/memoria_demo.py::verificar_remocao` — 6 vestígios encontrados na primeira varredura de um caso real):

| Estrutura | Por que o RA está lá |
|---|---|
| memória **episódica** | campo `ra` de metadado + o texto do `resumo` |
| memória **semântica** | prefixo da chave (`20230198:situacao_financeira`) |
| memória **procedural** | não deveria conter (nenhuma regra legítima menciona um titular) — verificado, não presumido |
| **checkpoint** (`checkpoints/*.json`) | argumentos de `consultar_financeiro({"ra": ...})` de uma execução ainda não encerrada |
| **log de execução** (`logs/*.json`, Ex.6) | mesma razão — `historico` guarda os argumentos de toda chamada de ferramenta, incluindo o RA |

**A verificação é o requisito, não a remoção em si** (nota 04 §3.2): `verificar_remocao()` roda depois de `remover_titular()` e varre as cinco estruturas de novo, por conteúdo textual — não só por campo de metadado, porque o RA pode aparecer dentro do texto de um resumo sem constar do metadado correspondente.

**O achado real ao rodar:** a primeira remoção (episódica + semântica) deixou vestígio em **duas** estruturas que a taxonomia não menciona — um checkpoint e um log de execução anterior (`logs/02-divergencia-9aee9313.json`, do Exercício 6). É exatamente o `FALHOU` que a nota 04, exemplo 2, descreve: *"apaguei das três memórias" é o ponto em que a maioria para*. A correção remove o checkpoint (efêmero por natureza — `checkpoints/` está fora do controle de versão). **O log de exercício anterior é um caso à parte, e fica registrado como risco aberto**, não corrigido nesta entrega: apagar um arquivo que é evidência de uma entrega já avaliada (Ex.6) para satisfazer uma solicitação de remoção é uma tensão real entre LGPD e auditabilidade acadêmica, que a Parte 2 precisa decidir — não este documento.

**Se o esquecimento exigisse reconstruir o índice inteiro:** não exige, neste desenho — a matriz de embeddings é recalculada por episódio (`hashlib` por conteúdo), e remover um episódio é só uma filtragem de lista antes de salvar. Isso continua válido enquanto o volume for de dezenas de episódios; se crescer para milhares, a reconstrução completa a cada remoção deixaria de ser barata, e a solução mudaria (índice com suporte a exclusão nativa).

### 2.4 O preço: não reprodutibilidade, medida

Mesma pergunta, mesmo modelo (`openai/gpt-oss-20b`), memórias diferentes:

> **Memória vazia:** *"Verificar situação financeira — Acesse o sistema de pagamentos (...) e confirme..."* — o agente não sabe, então instrui a verificar.
>
> **Memória cheia:** *"Sim. O RA 20230198 já está registrado como quitado (última atualização em 20 de setembro de 2026) e não há pendências financeiras. Assim, podemos emitir a segunda via..."* — decisão direta, com data.

A mesma entrada produziu comportamento qualitativamente diferente. Isto não é defeito — é a Decisão 1 sendo exercida. Registrado para a Aula 11: um conjunto de avaliação que rodar sobre este agente com memória precisa fixar o estado da memória junto com o modelo e os parâmetros, ou os números medidos não serão comparáveis entre execuções.

---

## Carimbo

Estado da memória nesta entrega: 2 episódios, 2 chaves semânticas, 1 regra procedural aprovada — sobre o RA sintético 20230198, único titular usado na demonstração. `src/memoria.py`, `src/memoria_episodica.py`, `src/memoria_semantica.py`, `src/memoria_procedural.py`, `src/memoria_demo.py`. Saída completa da demonstração em [`exercicios/aula-08-memoria-do-case.md`](../exercicios/aula-08-memoria-do-case.md).
