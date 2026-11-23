# MCP (opcional da Parte 3, §5.2)

Feito em 13/11/2026. Quem consome o servidor é o assistente da coordenação ([`multiagente.md`](multiagente.md)).

## 1. O servidor

Um servidor, **próprio**: `secretaria-academica` ([`src/mcp_secretaria.py`](../src/mcp_secretaria.py)), feito com o SDK oficial `mcp` **1.30.0** (`FastMCP`, versão fixada em `requirements-agente.txt`). **Nenhum servidor de terceiros** é usado.

Publica **cinco ferramentas, todas de leitura**:

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


## 2. Ferramenta ou recurso

As cinco são **ferramentas** (o modelo decide chamar), e **nenhum recurso** é publicado (`list_resources` devolve vazio). A razão: o assistente precisa decidir **o que** consultar (o histórico só quando o motivo é acadêmico, o Regimento com a pergunta que ele formula), e um recurso seria incluído no contexto pela aplicação, sempre. A tela do caso, que **sempre** entra, não vem como recurso: o código do assistente a busca com `casos_aguardando_coordenacao` antes de chamar o modelo e a põe na mensagem inicial.

## 3. A descrição de cada ferramenta

A descrição é a *docstring*, que o SDK publica e o cliente passa ao modelo como está:

| Ferramenta | Descrição publicada | Argumentos | O que **não** faz |
|---|---|---|---|
| `buscar_aluno` | "Cadastro do aluno pelo RA: nome, curso e situação da matrícula. Só leitura." | `ra: str` | não devolve financeiro nem histórico |
| `consultar_financeiro` | "Mensalidades em aberto e valor em aberto do aluno. Só leitura." | `ra: str` | não emite boleto |
| `consultar_historico` | "Disciplinas cursadas, notas por semestre e coeficiente do aluno. Só leitura." | `ra: str` | não emite o histórico |
| `consultar_regimento` | "Artigos do Regimento Acadêmico que tratam da pergunta (busca FTS5). Só leitura." | `pergunta: str` | não interpreta o artigo |
| `casos_aguardando_coordenacao` | "Trancamentos que o agente do aluno encaminhou e que esperam a coordenação, com o motivo registrado e o prazo. Só leitura: decidir é da pessoa." | nenhum | não decide nem altera o caso |

## 4. Como subir e conectar

```bash
python src/mcp_secretaria.py               # transporte stdio: é assim que o assistente o abre
python src/mcp_secretaria.py --http 8765   # Streamable HTTP em 127.0.0.1:8765, para outro cliente MCP
```

O cliente é o `ClientSession` do mesmo SDK: `assistente_coordenacao.sessao_stdio()` sobe o servidor como subprocesso, apontado para o mesmo banco (`ACADEMICO_DB`). Os testes usam a sessão em memória do SDK (`create_connected_server_and_client_session`) e, num caso, o subprocesso stdio.

## 5. Quem consome

| Consumidor | Ferramentas que usa |
|---|---|
| assistente da coordenação | as cinco; as que recebem RA só com o RA do caso (recusa no código) |
| o agente do aluno | **nenhuma**: chama as mesmas funções diretamente, dentro do grafo, onde passam pelos controles de identidade e de escrita |

**ASI04 (cadeia de suprimentos):** o servidor é próprio, então nenhuma descrição de ferramenta de terceiro entra no contexto. O SDK `mcp` é dependência de terceiro, fixada por versão e não por hash (o mesmo risco ASI04 de `seguranca.md` §4, não aceito).
