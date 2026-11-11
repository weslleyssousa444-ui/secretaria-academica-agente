# A memória do sistema de triagem

O que o sistema lembra entre execuções, o que ele esquece, e o que acontece **dentro** de uma conversa que dura. É a versão integrada ao grafo; a decisão de projeto original, sobre uma implementação com `torch`, está em [`docs/memoria-ex8.md`](memoria-ex8.md) e em [`exercicios/aula-08-memoria-do-case.md`](../exercicios/aula-08-memoria-do-case.md).

Código: [`src/triagem/memoria.py`](../src/triagem/memoria.py) (as três memórias, a política, o esquecimento), [`src/triagem/janela.py`](../src/triagem/janela.py) (a janela), [`src/triagem/sistema.py`](../src/triagem/sistema.py) (a conversa e o checkpoint). Testes: [`tests/test_memoria_triagem.py`](../tests/test_memoria_triagem.py).

## 1. Os dois níveis, e a fronteira entre três estruturas

| | curto prazo | longo prazo |
|---|---|---|
| o que é | a janela da conversa corrente | o que atravessa conversas e execuções |
| conteúdo no case | prompt de sistema (v2), a conversa, os retornos de ferramenta, o bloco MEMÓRIA do turno | episódica (o que aconteceu com o aluno), semântica (um fato estável), procedural (regra aprovada por uma pessoa) |
| persistido como | **checkpoint** (estado íntegro do grafo) | `episodica.json`, `semantica.json`, `procedural.json` |
| ciclo de vida | morre com a conversa (o arquivo, não) | acumula, com decaimento e remoção (§4) |

**O que precisa estar no checkpoint para a conversa ser retomável sem reaplicar efeito colateral:** `mensagens` (o que o modelo viu), `passos` (o resultado de cada `emitir_documento` e `escalar_para_humano` já executado), `caso_trancamento` e a **tarefa pendente** (o nó `aprovacao_coordenacao`, parado num `interrupt`). É esse conjunto que permite à coordenação decidir dias depois, em outro processo, sem reexecutar a escalada (`tests/test_triagem.py::test_pausa_sobrevive_a_reiniciar_o_processo`).

**A ordem de descarte** entre as fontes que disputam a janela, quando o contexto não cabe: **1º** o bloco de memória episódica (o mais volumoso e o mais fácil de refazer); **2º** os retornos de ferramenta antigos (trocados por um marcador, mantendo a estrutura assistente/ferramenta válida); **nunca** o prompt de sistema, a última mensagem do aluno e os retornos dos últimos seis itens (`janela.compactar`). Um sistema sem essa decisão a toma sozinho, truncando no fim, que é onde está o mais recente.

| | checkpoint | memória de longo prazo | RAG |
|---|---|---|---|
| escopo | uma conversa (`thread_id`) | todas as conversas do mesmo RA autenticado | nenhum: é externo |
| propósito | **retomar** | **lembrar** | **consultar** |
| forma | estado íntegro do grafo | fragmento selecionado (um episódio, um fato) | artigo do Regimento |
| leitura | no início de cada turno, por inteiro | por relevância, a cada turno | quando o modelo pede (ferramenta) |
| quem escreve | o framework, a cada nó | o **código**, por regra, no fim do turno | ninguém: o corpus é curado |

**O que a recuperação por relevância traz que a serialização integral não traria, e o que deixa para trás.** Serializar todas as conversas de todos os alunos produz arquivo morto: para decidir um pedido de hoje, o modelo não lê mil conversas. A memória entrega **no máximo 3 episódios e 1 fato**, num teto de 400 tokens (`ORCAMENTO_TOKENS_MEMORIA`), do aluno certo. O que ela deixa para trás é tudo o que um resumo não carrega: a redação exata do aluno, os retornos completos das ferramentas, a ordem dos turnos. Para reconstruir uma decisão em detalhe existe o checkpoint e o trace (Parte 3), não a memória.

## 2. As três memórias, e a política de escrita

| Tipo | O que guarda no case | Estrutura | Por que essa |
|---|---|---|---|
| **episódica** | `Pedido de declaracao_matricula resultou em documento emitido (protocolo DOC-1002).` | índice por **similaridade** (TF-IDF + cosseno), filtrado pelo RA **antes** de ordenar | a pergunta é de assunto ("o que já pedi sobre histórico?"), e a chave não resolve |
| **semântica** | `situacao_financeira = 2 mensalidade(s) em aberto (R$ 890.00)`, por RA | chave-valor, lido por chave exata | buscar um fato por similaridade é caro e impreciso quando a chave resolve |
| **procedural** | regra de triagem aprendida de um erro | texto no prompt, **só depois de aprovada** por uma pessoa | é a única sem filtro de relevância na leitura: uma regra errada vale para toda execução seguinte |

**Política de escrita: o código extrai, por regra, do retorno das ferramentas** (`Memoria.escrever_depois_do_turno`). Nunca o modelo, e nunca o que o aluno afirma:

| Política | Preço | Escolhida? |
|---|---|---|
| o **agente** decide o que guardar | guarda demais, e guarda o que o aluno **disse**, não o que o sistema confirmou: é o envenenamento de memória (ASI06) | não |
| o **código** extrai por regra | perde o que a regra não previu | **sim**: o que `consultar_financeiro`, `emitir_documento` e `escalar_para_humano` devolveram |
| o **humano** corrige | não escala | só para a procedural, que nasce com `aprovada = false` |

**Volume de escrita por turno:** no máximo **1 episódio** (~150 bytes) e **1 fato** (~100 bytes). Um aluno que diz "já paguei" não grava nada (`test_o_que_o_aluno_afirma_nao_vira_memoria`).

**A escrita de memória é escrita, e é idempotente.** A chave do episódio é derivada do **conteúdo** (`sha1` de RA, tipo e resumo), e o retorno traz `ja_existia`; o fato semântico tem chave `<RA>:<campo>`. Gravar o mesmo duas vezes é gravar uma (`test_episodio_gravado_duas_vezes_e_um_so`).

**Identidade.** Leitura e escrita só com `ra_autenticado`, a sessão do portal. Sem ela não há memória de aluno (só a procedural, que é global). Um RA que a pessoa **digita** no chat não abre o histórico de ninguém (`test_um_ra_autenticado_nao_le_a_memoria_de_outro`, `test_sem_ra_autenticado_nao_ha_memoria_de_aluno`).

## 3. O que a episódica perde por ser lexical

O Exercício 8 usou embedding (`sentence-transformers`, `torch`). O sistema da Parte 2 usa **TF-IDF**, porque a imagem do agente não carrega `torch` (`docs/rag.md` §2). A perda é a de sempre: **paráfrase sem termo em comum** não casa. Duas razões a tornam menor aqui do que no RAG: (1) o resumo é escrito pelo código a partir de um molde ("Pedido de X resultou em Y"), então o vocabulário é controlado, e não texto livre do aluno; (2) a busca é restrita aos episódios **de um aluno**, algumas unidades, e não a um corpus. **Não medi** a perda com paráfrases reais, e declaro como aberto: com poucos episódios por aluno, a diferença prática tende a ser pequena, mas isso é hipótese.

## 4. Como o sistema esquece

Das três causas, o case implementa as três, cada uma onde faz sentido:

| Causa | O que faz no sistema | Quando decide |
|---|---|---|
| **contradição** | o fato novo substitui o antigo na semântica; o valor anterior fica em `substituiu` (um nível) | na escrita |
| **decaimento** | episódio com mais de 180 dias é removido | **ao subir o processo** (`Sistema.__init__`), não por agendador |
| **remoção** | o titular solicitou: sai de todas as estruturas, e a saída é **verificada** | sob demanda, por chamada de código |

### 4.1 Contradição

A situação financeira muda com o tempo. `semantica.gravar` troca o valor e guarda o anterior, sem apagar (`test_contradicao_o_fato_novo_vale_e_o_antigo_fica_em_substituiu`). Não há contradição de **episódios**: um episódio é um evento que aconteceu, e eventos não se contradizem. O desempate entre dois episódios igualmente similares é pelo mais recente (carimbo de tempo, determinístico, sem modelo).

### 4.2 Decaimento

**Corte: 180 dias**, um semestre e meio: a unidade de tempo do domínio. Um episódio de trancamento ou pendência do semestre anterior já foi resolvido pela rematrícula ou pela quitação. **Efeito: remove** (diferente do Ex.8, que rebaixava o peso): numa memória de poucos episódios por aluno, rebaixar mantém ruído que o decaimento do domínio já tornou falso. **Limite declarado:** a rotina roda **ao subir o processo**; um serviço que fique meses sem reiniciar acumula episódios velhos, e um agendador resolveria. Não há (`tests/test_memoria_triagem.py::test_o_sistema_aplica_o_decaimento_ao_subir`).

### 4.3 Remoção, com cobertura verificada

`Memoria.remover_titular(ra, checkpoint_db, pasta_registros)` remove o RA de **todas** as estruturas que o guardam, e `Memoria.varrer(...)` é a verificação independente: a entrega é a varredura **não achar nada**, e não a chamada de exclusão.

| Estrutura | O que acontece | Por quê |
|---|---|---|
| memória **episódica** | removida (por RA) | campo `ra` e o texto do resumo |
| memória **semântica** | removida (prefixo da chave **e** varredura por conteúdo) | o RA pode aparecer dentro do valor de outro fato |
| memória **procedural** | **não é editada**: a regra que cita o RA volta em `regras_suspeitas`, para revisão humana | apagar uma regra aprovada sozinho mudaria o comportamento de toda execução |
| **checkpoint** | as **conversas inteiras** que citam o RA são apagadas (`checkpoints` e `writes`, por `thread_id`) | o checkpoint guarda os argumentos de cada chamada de ferramenta |
| **registros de execução** (`LOGS_DIR`, `api-*.json`) | os arquivos que citam o RA são apagados | a API grava a saída do turno |

`tests/test_memoria_triagem.py::test_remocao_do_titular_sai_de_todas_as_estruturas` roda o caminho inteiro: antes, a varredura acha as **cinco** estruturas; depois, só a procedural (que espera revisão humana).

**O que a remoção NÃO cobre, e fica aberto:**

- **As tabelas do sistema acadêmico** (`documentos_emitidos`, `casos_pendentes`, `aprovacoes`, `decisoes_humanas`): são o **registro do que a secretaria fez**, e não memória do agente. Apagar um documento emitido ou um caso decidido é uma decisão de retenção da secretaria, e não deste sistema.
- **Os logs versionados no repositório** (`logs/*.json`, evidência de entregas já avaliadas): tensão entre LGPD e auditabilidade acadêmica, declarada no model card (`L06`). Os dados são sintéticos.
- **O trace** (Parte 3): ainda não existe; quando existir, entra nesta lista.
- **A operação em si:** `remover_titular` é uma função, não um endpoint. Um endpoint de remoção sem autenticação própria seria um furo maior que a lacuna.

**Se o esquecimento exigisse reconstruir o índice inteiro:** não exige. O índice da episódica é uma lista filtrada e regravada; o do Regimento é recriado em milissegundos a cada subida (`docs/rag.md` §3). Uma memória envenenada sai por filtragem, sem janela de manutenção.

## 5. A conversa, e o que sobra dela

### 5.1 O que identifica uma conversa

O **`thread_id`**: o endereço do checkpoint. Mesma chave, mesma conversa; chave nova, histórico vazio. Na API é `conversa_id`, um `uuid4` de 128 bits gerado no primeiro turno (era 8 hexadecimais na Parte 1: `tests/test_api_seguranca.py::test_ASI03_mitigacao_o_conversa_id_tem_128_bits`). **A mesma pessoa abrindo duas conversas ao mesmo tempo tem dois `thread_id` e dois históricos independentes**; o que as liga é a memória de longo prazo, endereçada pelo RA autenticado. **O que não vincula a conversa a um dono:** quem conhece o `conversa_id` a continua (lacuna ASI03, registrada e testada).

### 5.2 Onde o checkpoint é gravado

Num arquivo **SQLite** (`TRIAGEM_CHECKPOINT`; `/dados/triagem.sqlite` no contêiner, em volume). Em arquivo, e não em memória: **a pausa para a coordenação sobrevive ao fim do processo**, e esse é o requisito que torna a aprovação humana possível em outro dia. Limites: o arquivo **cresce sem expiração** (`test_ASI08_lacuna_conversas_acumulam_no_checkpoint_sem_limite_nem_expiracao`) e guarda dado pessoal (mensagens e retornos de ferramenta), por isso entra na varredura de remoção (§4.3).

### 5.3 O que acontece quando a janela enche

`janela.compactar` (limite de 6.000 tokens estimados, `LIMITE_TOKENS_JANELA`): troca os retornos de ferramenta **antigos** por um marcador e preserva a estrutura. **Perde:** a chance de o modelo reler um retorno antigo (o cadastro consultado três turnos atrás); quem precisar chama a ferramenta de novo. **Nunca perde:** o prompt de sistema, a última mensagem do aluno e os seis itens mais recentes. Coberto por `test_janela_omite_retorno_antigo_e_preserva_o_resto`.

**Uma ressalva honesta:** nas 8 execuções reais (`logs/parte2/`), a compactação **foi acionada zero vezes** (nenhum evento `agente:janela-N` na trilha de nós). O maior consumo de uma conversa inteira foi de ~10 mil tokens somando todas as chamadas. **A política existe e é testada offline, mas nenhuma conversa real a acionou**, e a calibração do limite (6.000 tokens estimados, só sobre as mensagens, sem contar o prompt nem as declarações de ferramenta) é uma hipótese não confirmada. Quando uma conversa longa a acionar, a trilha do grafo e o trace da Parte 3 registram `janela-N`.

### 5.4 O que passa da conversa para a memória de longo prazo

**Pouco, de propósito.** Quando a conversa acaba, sobrevivem: **no máximo um episódio** ("pedido X resultou em Y, protocolo Z") e **um fato** (a situação financeira consultada), escritos por regra (§2). **O texto da conversa não passa.** O resto é o checkpoint, que é do processo, e não da memória.

## 6. O preço: a memória muda a resposta

A mesma pergunta, com memórias diferentes, produz respostas diferentes (medido no Ex.8, `docs/memoria-ex8.md` §2.4). Consequência para a avaliação: **a suíte roda sempre com a memória vazia** (`evals/`, Parte 3), e qualquer número que misture estados de memória não é comparável entre versões.
