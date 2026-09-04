# Case: Atendimento de solicitações na secretaria acadêmica

## 2.1 O problema

**O problema em uma frase.** Decidir, para cada solicitação de aluno recebida no chat da secretaria (declaração de matrícula, segunda via de histórico ou trancamento de matrícula), se ela pode ser atendida automaticamente ou se precisa ser encaminhada a um atendente humano — cruzando o que o aluno relata com o que o sistema acadêmico registra.

**Quem sofre com ele hoje.** A atendente da secretaria acadêmica do turno da tarde. Ela é quem recebe a fila de solicitações que chegam pelo balcão e pelo e-mail institucional, consulta três telas diferentes (cadastro, financeiro, histórico) para cada uma, e decide se atende na hora ou abre exceção.

**O contexto de onde o agente vai ser usado.**

- **Onde roda:** como um widget de chat dentro do portal do aluno, acionado quando o aluno abre uma nova solicitação (não é um processo em lote — é uma conversa, uma solicitação por vez).
- **O que existe antes e depois:** a entrada é a mensagem livre do aluno (às vezes já com o RA, às vezes não); a saída, quando o pedido é simples, é o documento emitido na hora e um protocolo; quando é escalado, é um registro na fila da secretaria, consumido pela atendente humana no dia seguinte.
- **O que acontece hoje sem ele:** o aluno manda e-mail ou vai ao balcão; a atendente consulta o sistema acadêmico (situação de matrícula), o financeiro (pendências) e, se for segunda via, o histórico. Isso leva entre 8 e 15 minutos por caso simples, e o retorno ao aluno demora de 1 a 3 dias úteis porque a fila não é atendida em tempo real.
- **Regras do domínio:**
  - declaração de matrícula exige matrícula **ativa**;
  - segunda via de histórico exige **quitação financeira total** (zero mensalidades em aberto);
  - trancamento de matrícula **nunca é decidido pela secretaria sozinha** — depende de aprovação da coordenação acadêmica, porque desfazer um trancamento exige um processo de rematrícula;
  - prazo institucional de resposta: 48h para casos escalados.
- **O que dá errado hoje:** aluno alega que já pagou e o sistema ainda não refletiu (pagamento em processamento no banco); RA digitado errado ou desatualizado; pedido duplicado (aluno já tinha pedido o mesmo documento na semana anterior); casos de exceção (bolsista, liminar judicial, convênio empresarial) que não seguem a regra padrão.

## 2.2 Os usuários, e como o agente conversa com eles

### Quem são

| Perfil | O que ele quer | O que ele sabe | O que ele **pode** fazer |
|---|---|---|---|
| **Atendente de secretaria** (usuário principal) | resolver a fila rápido e sem errar uma pendência | conhece as regras da secretaria; não conhece o funcionamento do agente | aprova, nega, pede mais informação ao aluno, escala para a coordenação |
| Aluno solicitante | resolver o próprio pedido rápido, sem precisar ir ao balcão | não conhece o processo interno nem os sistemas | descreve o pedido, informa RA, responde perguntas, anexa comprovante |
| Coordenação acadêmica | decidir corretamente os casos excepcionais (trancamento, exceções) | nem o processo de atendimento nem o funcionamento do agente | aprova ou nega trancamento, autoriza exceção à regra padrão |

O **usuário principal** é a atendente de secretaria: o agente é desenhado para reduzir a fila que chega até ela, não para substituir a decisão da coordenação nos casos irreversíveis.

**Quem pode aprovar uma ação irreversível?** Só a coordenação acadêmica aprova trancamento de matrícula. Por isso o agente **nunca executa** um trancamento — ele só faz a triagem e, quando o pedido é de trancamento, escala sempre, sem exceção (ver §2.3 e §2.4).

### Como é a interação

- **Por onde:** chat no portal do aluno. É o canal que o aluno já usa hoje para abrir solicitações (substitui o formulário de e-mail, que é o motivo do atraso de dias).
- **Quem começa:** o aluno procura o sistema — é reativo, não proativo. Não há necessidade de o agente "acordar sozinho".
- **Trocas até resolver:** em média 3 a 4 mensagens — descrição do pedido, pedido de RA (se não veio junto), pergunta de confirmação em caso de divergência, e a decisão final.
- **O que o sistema devolve:** texto (a decisão em linguagem natural) + um protocolo; em caso de aprovação, o documento em texto simples (declaração/segunda via); em caso de escalonamento, o prazo de resposta.
- **Como termina:** sucesso = aluno recebe o documento ou a confirmação com protocolo na hora; quando o agente não pode decidir sozinho, ele diz explicitamente que o caso foi encaminhado, dá o protocolo e o prazo de 48h — nunca deixa o aluno sem resposta.

### Diálogo de exemplo (caso simples)

```
Aluno:  Oi, preciso de uma declaração de matrícula pra levar no estágio.
Agente: Claro! Para emitir, preciso do seu RA (registro acadêmico). Pode informar?
Aluno:  20231045
Agente: Encontrei seu cadastro — Weslley Sousa, curso de Análise e
        Desenvolvimento de Sistemas, matrícula ativa. Aqui está sua
        declaração de matrícula (protocolo DOC-1042):

        [texto da declaração]

        Precisa de mais alguma coisa?
```

### Diálogo de exemplo (divergência)

```
Aluno:  Já paguei tudo, preciso da segunda via do meu histórico.
Agente: Para emitir, preciso do seu RA. Pode informar?
Aluno:  20230198
Agente: Encontrei seu cadastro, mas o sistema financeiro mostra 2
        mensalidades em aberto (R$ 890,00). Você tem o comprovante de
        pagamento em mãos?
Aluno:  Não, paguei ontem no banco.
Agente: Entendo — o sistema pode não ter processado ainda. Não posso
        emitir a segunda via com pendência em aberto, então vou
        encaminhar seu caso para a secretaria confirmar o pagamento.
        Protocolo CASO-3311, resposta em até 48h.
```

### E a complexidade que a disciplina pede

- **O que o usuário não informa de primeira:** o RA quase nunca vem na primeira mensagem; o motivo exato do pedido às vezes vem misturado com outras informações (ex.: "preciso de um documento pro estágio" sem dizer qual).
- **O que acontece quando o relato do aluno contradiz o sistema:** o agente não decide sozinho a favor do aluno — pede comprovante; sem comprovante, escala para a secretaria com o motivo "divergência financeira não resolvida" (nunca emite o documento nesse caso).
- **Como o sistema decide que já sabe o suficiente para agir:** quando tem RA identificado, tipo de pedido classificado, e já consultou cadastro e financeiro no sistema acadêmico.
- **Quando o sistema para e chama um humano** (chama a **atendente de secretaria**, via fila de casos pendentes): pedido de trancamento (sempre); divergência financeira não resolvida; RA não encontrado depois de uma segunda tentativa; tipo de pedido fora do catálogo (declaração, segunda via, trancamento) — qualquer exceção (bolsista, liminar, convênio) cai automaticamente aqui.

## 2.3 O workflow do agente

```
1. ENTRADA      o aluno descreve o pedido no chat                    [captura]
2. IDENTIFICAÇÃO o sistema classifica o tipo de pedido e pede o RA
                 se não veio informado                                [decide: MODELO]
3. CONSULTA     busca o cadastro e o financeiro do aluno no
                 sistema acadêmico (SQLite)                            [decide: CÓDIGO]
4. TRIAGEM      trancamento -> sempre vai para 6 (escalar)
                 RA não encontrado -> pede de novo, senão vai pra 6    [decide: CÓDIGO]
5. ANÁLISE      compara o relato do aluno com o registro do sistema
                 (situação de matrícula, pendências); decide se segue
                 para emissão automática ou se precisa escalar         [decide: MODELO]
6. AÇÃO         emite o documento (ESCRITA, reversível: pode ser
                 reemitido) OU registra o caso na fila da secretaria
                 (ESCRITA, reversível: fila pode ser reaberta)
7. RETORNO      informa o aluno (documento + protocolo, ou
                 encaminhamento + prazo)                               [captura]
```

**Quem decide em cada passo:** 4 dos 7 passos são decididos por código (as regras de negócio são determinísticas: matrícula ativa, zero pendência, trancamento sempre escala). Só os passos 2 e 5 pedem interpretação do modelo — classificar um pedido em texto livre, e julgar se a alegação do aluno resolve ou não a divergência com o sistema. Essa proporção não é acidente: é a aplicação da regra "menor autonomia que resolve" (ver §2.4).

**Passos de escrita e reversibilidade:** `emitir_documento` (passo 6, ramo de aprovação) é reversível — um documento pode ser reemitido sem custo real. `escalar_para_humano` (passo 6, ramo de escalonamento) também é reversível — é só um registro em fila. **Nenhum passo do agente executa a ação irreversível de verdade (o trancamento em si)** — essa sempre fica com a coordenação, fora do escopo do agente.

## 2.4 O sistema

**O que o sistema faz:** recebe o pedido de um aluno em linguagem natural, identifica o tipo de solicitação e o RA, consulta o sistema acadêmico simulado (cadastro + financeiro), decide se atende automaticamente (declaração ou segunda via, quando as regras permitem) ou encaminha para a secretaria (trancamento, pendência não resolvida, divergência, RA não encontrado, exceção fora do catálogo).

**Nível de autonomia pretendido: agente** (não workflow, não roteador).

- Não é **workflow** porque não há uma sequência fixa de passos que resolva sozinha: o passo 5 exige julgar, caso a caso, se a alegação do aluno em texto livre é compatível com o dado estruturado do sistema — isso é decisão em tempo de execução, não uma condição fixa (`if pendencia > 0`) porque a resposta do aluno pode trazer informação nova (ex.: "paguei ontem", "sou bolsista") que muda o que a próxima ferramenta deveria fazer.
- Não é apenas **roteador** porque um roteador classifica uma vez e despacha para um caminho fixo; aqui o sistema pode precisar de mais de uma pergunta ao aluno (RA faltando, comprovante faltando) antes de ter informação suficiente, e a decisão de "já sei o bastante para agir" muda a cada turno — exige um laço com estado, não uma classificação única.

**As ferramentas:**

| Ferramenta | O que faz | Leitura ou escrita? | Reversível? | Contra o que ela conversa |
|---|---|---|---|---|
| `buscar_aluno` | consulta cadastro e situação de matrícula pelo RA | leitura | — | banco SQLite `academico.db`, tabela `alunos` |
| `consultar_financeiro` | consulta mensalidades em aberto pelo RA | leitura | — | banco SQLite `academico.db`, tabela `financeiro` |
| `emitir_documento` | gera declaração de matrícula ou segunda via de histórico, valida a regra de negócio antes de emitir | **escrita** | reversível (pode reemitir) | banco SQLite `academico.db`, tabela `documentos_emitidos` |
| `escalar_para_humano` | registra o caso na fila de atendimento humano, com motivo | **escrita** | reversível (fila pode ser reaberta) | banco SQLite `academico.db`, tabela `casos_pendentes` |

## 2.5 A justificativa de negócio

### Por que um agente, e não software comum

O que exige decisão em tempo de execução é o cruzamento entre o relato do aluno em texto livre — que pode contradizer o sistema, vir incompleto, ou trazer uma exceção não catalogada — e o dado estruturado do sistema acadêmico. Um formulário fixo resolve o caso em que o aluno já sabe informar tudo de primeira; não resolve o caso em que ele diz "já paguei" e o sistema discorda. Um roteador (classificação única) resolve "que tipo de pedido é esse", mas não decide, turno a turno, se já há informação suficiente para agir ou se a resposta do aluno mudou o quadro — por isso o nível abaixo (roteador) não dava conta.

### O ganho esperado

**Eixo 1 — Velocidade de processo (do pedido à resposta).**

- **Linha de base (estimada, ver ressalva):** hoje, do pedido à resposta, o aluno espera **1 a 3 dias úteis**, porque a solicitação entra numa fila de e-mail que só é olhada uma vez por dia.
- **Alvo:** resposta **imediata** (segundos) para os casos que não têm pendência nem exceção.
- **A conta:** de ~48h úteis para ~1 minuto nos casos simples = **>99% de redução no tempo de espera** para essa fatia dos pedidos.
- **Ressalva:** os números da linha de base são uma **estimativa** baseada no processo relatado, não uma medição cronometrada — antes de qualquer entrega final, o grupo deve cronometrar os casos reais (ou obter os números com a secretaria) para substituir esta estimativa por uma medição.

**Eixo 2 — Cobertura (o que sai da fila humana).**

- **Linha de base:** hoje, **100%** dos pedidos passam pela atendente.
- **Alvo:** **~60%** dos pedidos (declaração + segunda via sem pendência, que são a maioria dos pedidos recebidos) resolvidos sem intervenção humana — mantendo **100%** dos trancamentos e divergências sempre escalados.
- **A conta:** `de 100% para 40% dos pedidos chegando à fila humana = -60% de carga`, sobre o volume total de pedidos recebidos por período.
- **Ressalva:** o percentual de 60% é uma estimativa baseada na proporção assumida entre tipos de pedido; precisa ser confirmado com a distribuição real de pedidos da secretaria.

### O ganho para o usuário, que não é o mesmo do negócio

- **Para o negócio:** menos carga na fila humana, resposta mais rápida sem aumentar o quadro de atendentes.
- **Para o aluno:** não precisa ir ao balcão nem esperar dias por um documento simples; não precisa repetir informação (dá o RA uma vez); recebe resposta mesmo quando o caso é escalado (sabe que não foi esquecido).
- **A tensão:** otimizar a métrica de cobertura (% resolvido sem humano) tem o risco do caso Klarna visto em aula — se o grupo for pressionado a aumentar esse número, a tentação é afrouxar a regra de divergência (deixar o agente "confiar" no aluno quando ele diz que já pagou). Isso pioraria exatamente a experiência do caso mais delicado — o aluno que pagou de verdade e foi tratado como pendente — para melhorar um número que não mede isso. A regra de negócio deste projeto é explícita: **divergência financeira nunca é resolvida a favor do aluno sem comprovante**, mesmo que isso reduza a cobertura.

### O outro lado da conta

- **Quanto custa rodar:** ver `docs/modelos.md` §3.2 para a estimativa de tokens e custo por execução.
- **Quanto custa construir:** o tempo do grupo nesta Parte 1 (case, modelos, agente, dados simulados, verificador) — ordem de algumas tardes de trabalho, sem custo de infraestrutura além da chave de API.
- **O que se perde:** qualquer exceção real do regimento acadêmico que não está no catálogo do agente (bolsista, liminar, convênio) é **sempre escalada por padrão** — o que é seguro, mas significa que a fila humana não cai tanto quanto o alvo de 60% sugere até o regimento completo ser mapeado (ver §2.10, RAG). Quem paga por isso, no curto prazo, é a atendente, que continua vendo esses casos na fila; o aluno nesses casos não perde nada, porque o padrão seguro é escalar, nunca decidir errado.

## 2.6 O verificador

O verificador é uma **regra de negócio determinística** aplicada sobre um **conjunto de 40 casos rotulados**, construído a partir dos mesmos dados simulados do agente (`dados/casos_verificador.json`). Cada caso tem: o RA, o pedido do aluno (texto livre), e o **rótulo correto** — a decisão esperada (`emitir_declaracao`, `emitir_segunda_via`, `escalar_pendencia`, `escalar_trancamento`, `escalar_ra_nao_encontrado`, `escalar_divergencia`) e o motivo esperado.

O rótulo de cada caso é derivado das regras de negócio de §2.1 aplicadas aos dados semeados em `src/dados.py` (matrícula ativa, mensalidades em aberto, RA existente) — não é opinião, é a mesma regra que a secretaria usa hoje. `src/verificador.py` roda os 40 casos contra o agente e compara a decisão final tomada com o rótulo.

## 2.7 O critério de sucesso

O agente acerta a decisão (qual ação tomar e, quando escala, o motivo correto) em **pelo menos 34 dos 40 casos rotulados (85%)**, **e** não deixa passar **nenhum** caso de trancamento sem escalonamento (0 falsos negativos nessa categoria — ver §2.5, o custo de errar para o lado da autonomia excessiva é assimétrico em relação a errar para o lado conservador).

## 2.8 Dados

Os dados são **simulados** — não há acesso a um sistema acadêmico real, e o tema toca dado sensível (ver §2.9). A base é gerada em `src/dados.py` com ~20 alunos fictícios, cobrindo deliberadamente os casos difíceis:

- **Caso de divergência:** RA com aluno que tem pendência financeira registrada, usado nos casos de teste em que a mensagem do aluno afirma "já paguei".
- **Registro inexistente:** um RA usado nos testes (`20240000`) que **não existe** na base — força o agente a lidar com erro de ferramenta.
- **Caso que não deve disparar a ação principal:** todo pedido de tipo `trancamento_matricula` — a ação principal (emitir/aprovar automaticamente) nunca deve disparar para esse tipo, não importa a situação do aluno.

## 2.9 Dado sensível

Sim: o tema toca dado **financeiro** (mensalidades, valores em aberto) e **acadêmico** (situação de matrícula, histórico) de aluno — dado pessoal protegido por LGPD num contexto real. Por isso, **nenhum dado sensível real entra no repositório nem no contexto do modelo**: a base inteira (`src/dados.py`) é sintética, com nomes fictícios e RAs que não correspondem a alunos reais.

## 2.10 Espaço para o que ainda vem

- [x] **RAG** (Parte 2) — o Regimento Acadêmico interno (normas de trancamento, prazos, exceções de bolsista/convênio/liminar), hoje um PDF de ~20 páginas, seria a base consultada para o agente parar de escalar toda exceção por padrão e passar a resolver as que o regimento já cobre.
- [x] **MCP** (Parte 2) — a consulta ao sistema acadêmico (hoje as 4 ferramentas contra o SQLite) vira um servidor MCP, para poder ser reaproveitada por outros agentes da secretaria (ex.: um agente de cobrança).
- [x] **LangChain** (Parte 2) — a orquestração do laço de ferramentas e da memória de conversa (hoje um laço manual em `src/agente.py`) migraria para um agente LangChain, para ganhar gerenciamento de memória multi-turno de fábrica.
- [x] **Multiagente** (Parte 3) — um agente de **triagem** (o atual), um agente **especialista em regras financeiras/regimento** (consultado quando a triagem encontra uma exceção) e um agente de **redação de documentos** (formata a declaração/segunda via no padrão oficial da instituição) — três responsabilidades hoje misturadas num único prompt.

## 2.11 O maior risco

O risco real não é "o modelo pode errar" — é que **a base de regras deste protótipo é uma simplificação do regimento acadêmico real**, e o grupo não tem acesso a um regimento real para validar contra ele (dado sensível, §2.9). Isso significa que casos de exceção genuínos (bolsista, convênio empresarial, liminar judicial) que existem na vida real não estão cobertos pelo catálogo de regras testado aqui.

**Plano B:** o comportamento padrão do agente diante de qualquer tipo de pedido ou situação que não reconhece é **sempre escalar para a secretaria**, nunca decidir por conta própria (`escalar_para_humano` é o caminho seguro por padrão — ver `src/agente.py`, a ferramenta `emitir_documento` recusa qualquer tipo de documento fora do catálogo de dois itens). Isso limita a cobertura real (§2.5), mas evita o erro caro: o agente aprovando algo que não devia.
