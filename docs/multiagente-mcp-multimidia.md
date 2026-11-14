# Multiagente, MCP e multimídia (opcionais da Parte 3)

Feito em 13/11/2026. Os três opcionais do enunciado foram construídos **em volta** do agente do aluno, sem mexer nele: o grafo (15 nós, 24 arestas), o prompt v3 e as 7 ferramentas são os mesmos. Isso é de propósito, porque a rodada B da suíte ainda vai medir esse agente, e a comparação A × B exige que o código sob teste não mude no meio (`docs/evals.md` §4.4).

## 1. O desenho

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

Os dois agentes não trocam mensagens entre si. Eles se coordenam pelo **estado gravado**: o primeiro escreve o caso, o segundo o lê. É a forma mais simples de multiagente que deixa claro quem fez o quê e não abre um canal pelo qual um modelo instrua o outro.

## 2. O servidor MCP (`src/mcp_secretaria.py`)

Publica, pelo protocolo MCP (SDK `mcp` 1.30.0, `FastMCP`, o mesmo do Exercício 10), **cinco ferramentas, todas de leitura**:

| Ferramenta | O que devolve | Função reaproveitada |
|---|---|---|
| `buscar_aluno(ra)` | cadastro | `agente.buscar_aluno` |
| `consultar_financeiro(ra)` | mensalidades e valor em aberto | `agente.consultar_financeiro` |
| `consultar_historico(ra)` | disciplinas, notas, coeficiente | `servicos.consultar_historico` |
| `consultar_regimento(pergunta)` | artigos (FTS5) | `regimento.consultar_regimento` |
| `casos_aguardando_coordenacao()` | casos pausados, com motivo e prazo | `humano.pendentes` |

São **as mesmas funções** que o agente do aluno usa: o MCP não cria uma segunda versão da regra.

**Por que só leitura:** as escritas do sistema (emitir, escalar, decidir) passam pelos controles do grafo: RA da sessão (ASI03), no máximo 1 escrita e 4 chamadas por turno (ASI02). Um servidor MCP com escrita seria um caminho para contorná-los. `teste::test_mcp_nao_publica_escrita` trava isso.

Erro de domínio (RA inexistente) volta como **conteúdo**, com a sugestão, e não como falha de protocolo (`teste::test_mcp_ra_inexistente_volta_como_conteudo`), como no Exercício 10.

```bash
python src/mcp_secretaria.py               # stdio (é assim que o assistente o abre)
python src/mcp_secretaria.py --http 8765   # Streamable HTTP em 127.0.0.1, para outro cliente MCP
```

## 3. O assistente da coordenação (`src/assistente_coordenacao.py`)

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

### Os controles, no código

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

### O que não foi medido

Até 13/11/2026 o assistente **não foi avaliado com o modelo real**: os testes provam os limites do código, não a qualidade do parecer. A medição está pronta e usa só os alunos **fictícios** do banco sintético, num banco separado:

```bash
python -m evals.avaliar_assistente --pasta evals/resultados/<data>-assistente-r1   # precisa da chave; ~6 pareceres
```

Para cada um de 6 alunos fictícios (em dia, com débito, sem motivo, mudança de cidade...), ela abre um trancamento aguardando a coordenação e pede o parecer pelo servidor MCP. As **metas foram declaradas antes de rodar**, no próprio arquivo: pelo menos 5 de 6 pareceres aceitos pelo validador sem contingência, e 0 com recomendação de decisão. Ela também confere por código se a situação da matrícula e o débito citados batem com o banco, e conta os tokens. O resultado vai para `resumo.json` na pasta. **Se a meta não for atingida, isso é o resultado**: não se ajusta a meta depois.

Gasta a cota do mesmo modelo da rodada B: rode em outro dia, ou depois dela.

## 4. Multimídia: entrada por voz (`web/index.html`)

O site ganhou um botão de microfone ao lado do "Enviar". O aluno fala o pedido, o texto reconhecido aparece na caixa e **não é enviado sozinho**: ele confere, corrige se precisar, e envia. Para o agente, a mensagem é texto como qualquer outra, então nenhum controle muda.

- Usa o reconhecimento de fala **do próprio navegador** (Web Speech API, `pt-BR`): nenhum modelo novo, nenhuma cota e nenhuma mudança na lista de modelos aprovados.
- O botão só aparece se o navegador oferecer o recurso (Chrome e Edge oferecem; o Firefox não).
- **Risco registrado** (`docs/seguranca.md` §8): no Chrome, o áudio é processado pelo Google. Os dados são sintéticos, mas o aluno pode falar o próprio nome. Com dado real, isso teria de entrar na avaliação de privacidade (L14).

**O que não foi feito:** entrada por imagem (um print de comprovante). O sistema foi desenhado para **não ler anexos** (rubrica do juiz, regra 3), e não foi verificado se o modelo aprovado aceita imagem. Saída multimídia já existia: a declaração, o histórico e o boleto saem como página imprimível ou PDF (`src/triagem/documentos.py`).
