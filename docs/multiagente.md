# Multiagente (opcional da Parte 3, §5.1)

Feito em 13/11/2026; contrato de handoff e trace do segundo agente em 23/11/2026. O servidor MCP está em [`mcp.md`](mcp.md) e a voz em [`multimidia.md`](multimidia.md).

## 1. O diagrama

```
 aluno ──(texto ou voz)──> AGENTE DO ALUNO (src/triagem/, grafo LangGraph)
                              │  trancamento: abre o caso e PAUSA (Art. 6º)
                              ▼
                     tabela `aprovacoes` (caso aguardando, prazo 48 h)
                              ▲
                              │  lê, via MCP (só leitura)
 coordenação <──parecer── ASSISTENTE DA COORDENAÇÃO (src/assistente_coordenacao.py)
     │                        │
     │                        └─> SERVIDOR MCP (src/mcp_secretaria.py)
     └─ decide: python src/coordenacao.py decidir CASO-3001 aprovar --por coord-1
```

| Agente | Fala com | Pode | Não pode |
|---|---|---|---|
| **Agente do aluno** (já existia) | o aluno | consultar os dados do RA da sessão, emitir declaração, histórico e boleto, abrir caso | decidir trancamento (o grafo pausa) |
| **Assistente da coordenação** (novo) | a pessoa da coordenação | ler o caso, os dados do aluno do caso, o histórico e o Regimento, e montar um **parecer de apoio** | escrever qualquer coisa, consultar outro RA, **recomendar ou decidir** |

Os dois agentes não trocam mensagens entre si. Eles se coordenam pelo **estado gravado**: o primeiro escreve o caso **e o contrato de handoff** (§3), o segundo os lê. É a forma mais simples de multiagente que deixa claro quem fez o quê e não abre um canal pelo qual um modelo instrua o outro.


## 2. A topologia, e o que no case a justifica

É uma **pipeline de caminho fixo**, e portanto um **workflow** entre dois agentes: agente do aluno → caso gravado → assistente da coordenação → pessoa da coordenação. Nenhum agente chama o outro; o segundo só roda quando uma pessoa pede (`python src/coordenacao.py preparar <protocolo>`).

O critério da Aula 16 que a justifica é **isolamento de contexto**, com especialização como consequência:

| | Agente do aluno | Assistente da coordenação |
|---|---|---|
| prompt de sistema | `triagem-v3.txt`, 4.295 caracteres | `coordenacao-v1.txt`, 1.376 caracteres |
| ferramentas | 7, das quais **3 escrevem** | 5, **nenhuma escreve** (servidor MCP só leitura) |
| o que entra no contexto | a conversa com o aluno, que pode trazer texto hostil | só a tela do caso e o handoff, montados pelo **código** |
| quem lê a saída | o aluno | a coordenação, que decide |

A conversa do aluno é o canal de entrada não confiável do sistema (`seguranca.md` §1). Manter o parecer num agente separado faz com que a conversa **não** chegue ao contexto do agente que escreve para a coordenação: dela só passa o **motivo registrado**, um campo curto, como dado do caso (é o canal do ASI07, `seguranca.md` §2). E o agente com ferramentas de escrita não é o mesmo que fala com quem decide. Não há paralelismo: os dois nunca rodam ao mesmo tempo sobre o mesmo caso.

## 3. O contrato de handoff ([`src/triagem/handoff.py`](../src/triagem/handoff.py))

Um *schema* Pydantic (`Handoff`), montado e gravado pelo **código coordenador** (o nó `registrar_espera` do grafo, [`src/triagem/nos.py`](../src/triagem/nos.py)), não por um modelo:

| Campo | O que traz |
|---|---|
| `objetivo` | "preparar o parecer de apoio para a coordenação decidir o trancamento `<protocolo>`" |
| `decisoes` | decisão e razão: encaminhar à coordenação, porque o trancamento é dela (Art. 6º) |
| `escritas` | cada escrita executada, com o **identificador que ela devolveu** (`escalar_para_humano` → `CASO-3001`) |
| `erros` | os erros de ferramenta da trajetória (`buscar_aluno: aluno não encontrado`) |
| `fatos_numericos` | prazo da coordenação (48 h) e, se consultados, mensalidades e valor em aberto |
| `chave_idempotencia` | `hf-` + sha256 de protocolo, conversa e RA, **gerada pelo coordenador**: o mesmo caso dá a mesma chave |

O handoff é gravado na tabela `handoffs` com `INSERT OR IGNORE` pela chave: a retomada do LangGraph roda o nó de novo, e a segunda gravação devolve `ja_existia`. A tela da coordenação o mostra (`humano.tela_da_aprovacao`). O handoff carrega o RA e os erros da trajetória: é registro do caso, como `casos_pendentes`, e a remoção por titular da memória **não** o apaga (`docs/memoria.md`, a mesma regra das tabelas do sistema acadêmico).

O assistente **só trabalha sobre um caso cujo handoff valida** contra o *schema* e fala do mesmo protocolo e RA; sem isso, recusa antes de chamar o modelo. A chave do handoff sai no parecer (`handoff_chave`) e no trace (`agente.handoff.chave`), o que liga as duas execuções.

Testes ([`tests/test_handoff.py`](../tests/test_handoff.py), 8): o grafo grava o handoff com todos os campos; a chave é do conteúdo e repetir não cria outro; os erros entram; a tela mostra; caso **sem** handoff e handoff **de outro caso** são recusados sem chamar o modelo; o parecer carrega a chave; e cada agente tem a sua raiz no trace.

## 4. O que acontece quando um agente falha

| Falha | O que fica escrito no mundo | Quem decide |
|---|---|---|
| o agente do aluno falha antes de escalar | nada | o aluno tenta de novo; o caso não existe |
| falha depois de escalar | o caso (`casos_pendentes`), a espera (`aprovacoes`) e o handoff; todos idempotentes | o grafo, ao ser retomado, regrava as mesmas chaves |
| o assistente falha no meio | **nada**: ele não tem ferramenta de escrita | o código monta o parecer pela contingência; se nem isso, a coordenação decide sem parecer |
| o assistente produz parecer inválido | nada | o código reprova e, na 2ª vez, monta o parecer pela contingência |
| ninguém da coordenação responde | o caso vence em 48 h e volta à fila da secretaria | a secretaria |

Nenhum agente aborta o outro. Quem decide o caso é sempre a pessoa (`python src/coordenacao.py decidir`).

## 5. O trace dos dois agentes

Um `invoke_agent` **por agente** (Parte 3, §4.2): `invoke_agent triagem-secretaria` por turno do aluno, e `invoke_agent assistente-coordenacao` por preparação de parecer, com `chat <modelo>` e `execute_tool <ferramenta>` embaixo (recusas incluídas, com `agente.ferramenta.recusada = true`). Na raiz do assistente: `agente.termino`, `agente.versao`, `agente.origem` (modelo ou contingência), `agente.handoff.chave`, chamadas, tokens e recusas. A conversa do assistente é o protocolo do caso (`gen_ai.conversation.id`). Teste: `test_cada_agente_tem_a_sua_raiz_no_trace`.

## 6. O assistente da coordenação (`src/assistente_coordenacao.py`)

```bash
python src/coordenacao.py listar              # o que espera a coordenação
python src/coordenacao.py preparar CASO-3001  # o parecer (usa o modelo: poucos milhares de tokens)
python src/coordenacao.py decidir CASO-3001 aprovar --por coord-1   # a decisão continua da pessoa
```

O `preparar` abre o servidor MCP como **subprocesso** (stdio), apontado para o mesmo banco (`ACADEMICO_DB`), e o assistente só enxerga o sistema por ele. Usa o mesmo modelo aprovado (`qwen/qwen3.8-27b`, controle ASI10) e o prompt `src/prompts/coordenacao-v1.txt`.

A saída é um objeto validado:

```json
{"protocolo": "CASO-3001", "origem": "modelo",
 "parecer": {"protocolo": "CASO-3001", "ra": "20229012", "resumo": "...",
             "fatos": [{"texto": "...", "fonte": "consultar_financeiro"}],
             "artigos": ["Art. 6º"], "pontos_de_atencao": ["..."]},
 "decisao": "cabe à coordenação (Art. 6º)", "recusas": [], "chamadas_ao_modelo": 3}
```

### 6.1 Os controles, no código

| # | Controle | Teste que tenta a ação indevida |
|---|---|---|
| 1 | O caso tem de estar aguardando a coordenação, conferido **antes** de chamar o modelo | `test_caso_que_nao_esta_aguardando_nao_chama_o_modelo` |
| 2 | Ferramenta chamada com **outro RA** é recusada sem ir ao servidor (o débito da outra aluna não aparece) | `test_outro_ra_e_recusado_sem_ir_ao_servidor` |
| 3 | O parecer **não recomenda** decisão ("recomendo", "sugiro", "deve ser aprovado"...) | `test_recomendacao_e_reprovada_e_cai_na_contingencia` |
| 4 | Artigo citado tem de ter sido devolvido por `consultar_regimento` | `test_artigo_que_a_busca_nao_devolveu_e_reprovado` |
| 5 | A fonte de cada fato tem de ser uma ferramenta que respondeu | `test_fonte_inventada_e_reprovada` |
| 6 | Reprovado duas vezes, o parecer sai **montado pelo código** a partir dos retornos (`origem: contingencia`) | `test_contingencia_traz_dados_reais_do_caso` |
| 7 | No máximo 8 chamadas ao modelo | `test_laco_de_ferramentas_para_no_limite` |
| 8 | Só modelo aprovado (ASI10) | `test_modelo_nao_aprovado_e_recusado` |
| 9 | O assistente não grava decisão; o caso continua pendente | `test_assistente_nao_decide_o_caso` |

Os 18 testes estão em [`tests/test_multiagente_mcp.py`](../tests/test_multiagente_mcp.py). Rodam offline: o servidor MCP roda em memória (sessão MCP real) e, num teste, como subprocesso stdio, que é o caminho do `preparar`.

### 6.2 O que não foi medido

Até 13/11/2026 o assistente **não foi avaliado com o modelo real**: os testes provam os limites do código, não a qualidade do parecer. A medição está pronta e usa só os alunos **fictícios** do banco sintético, num banco separado:

```bash
python -m evals.avaliar_assistente --pasta evals/resultados/<data>-assistente-r1   # precisa da chave; ~6 pareceres
```

Para cada um de 6 alunos fictícios (em dia, com débito, sem motivo, mudança de cidade...), ela abre um trancamento aguardando a coordenação e pede o parecer pelo servidor MCP. As **metas foram declaradas antes de rodar**, no próprio arquivo: pelo menos 5 de 6 pareceres aceitos pelo validador sem contingência, e 0 com recomendação de decisão. Ela também confere por código se a situação da matrícula e o débito citados batem com o banco, e conta os tokens. O resultado vai para `resumo.json` na pasta. **Se a meta não for atingida, isso é o resultado**: não se ajusta a meta depois.

Gasta a cota do mesmo modelo da rodada B: rode em outro dia, ou depois dela.

### 6.3 Simulação (13/11/2026), **não é medição**

Para mostrar a medição funcionando sem chave, `python -m evals.simular_assistente` roda o mesmo script com um **modelo roteirizado**, offline. O roteiro erra de propósito em alguns casos, e o resultado ([`evals/resultados/simulacao-assistente-roteirizado/`](../evals/resultados/simulacao-assistente-roteirizado/)) mostra o que os controles fizeram com esses erros:

| Aluno fictício | O roteiro fez | O código fez |
|---|---|---|
| 20229012, 20234321 | parecer correto | aceito |
| 20230198 | recomendou aprovar, duas vezes | reprovado; parecer montado pelo código (contingência) |
| 20232210 | citou um artigo que a busca não devolveu | reprovado; aceito na 2ª tentativa, corrigido |
| 20231987 | consultou o débito de outra aluna | recusado sem ir ao servidor; o valor não aparece |
| 20230555 | entrou em laço de ferramentas | parou em 8 chamadas; contingência |

Nenhum fato citado divergiu do banco. **Esses números descrevem o roteiro, que foi escrito para exercitar os controles; não dizem nada sobre a qualidade do modelo real.**

