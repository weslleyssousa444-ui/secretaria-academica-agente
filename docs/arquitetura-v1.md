# Exercício 5 — Arquitetura v1 da secretaria acadêmica

**Grupo:** Weslley Soares de Sousa, Pedro Akira, Henrique Gomes Matos e Erick.  
**Case:** atendimento de solicitações na secretaria acadêmica.  
**Versão:** arquitetura-v1, 11/09/2026.  
**Natureza da entrega:** projeto de arquitetura; não afirma que as mudanças já foram implementadas em `src/agente.py`.

## 1. Entrada

O aluno inicia uma conversa em texto livre, em português, no chat do portal acadêmico. Informa o pedido e, quando necessário, o RA; pode complementar uma mensagem anterior. O sistema é reativo: não acorda sozinho nem processa lotes. Nesta v1, anexos são encaminhados à secretaria para conferência, sem leitura automática de comprovantes.

Distribuição inicial **estimada, ainda não medida**:

| Tipo de pedido | Proporção | Exemplos |
|---|---:|---|
| Declaração de matrícula | 45% | “Preciso de uma declaração para o estágio.” |
| Segunda via de histórico | 30% | “Quero meu histórico novamente.” |
| Trancamento | 15% | “Quero trancar este semestre.” |
| Outros ou indefinidos | 10% | Exceções, pedido fora do catálogo ou “preciso de um documento”. |

Os tipos somam 100%; RA ausente e divergência financeira podem ocorrer em qualquer tipo e não são categorias adicionais dessa estimativa. As entradas são heterogêneas no significado, embora usem o mesmo canal. Isso justifica um Router. A proporção de pedidos por tipo não equivale à proporção de aprovações automáticas.

## 2. System

### System prompt, em uma frase

> Você é o assistente de triagem da secretaria acadêmica: extraia o pedido e os dados informados pelo aluno sem inventar fatos, peça os campos ausentes e encaminhe exceções; você não é a coordenação, não confirma pagamentos e não autoriza trancamentos.

### Ferramentas e efeitos

| Ferramenta | Função | Acesso | Reversibilidade e proteção |
|---|---|---|---|
| `buscar_aluno(ra)` | Consulta cadastro e situação da matrícula | Leitura | Não altera dados; RA inexistente retorna erro estruturado. |
| `consultar_financeiro(ra)` | Consulta pendências registradas | Leitura | Não altera dados; alegação do aluno não substitui o registro. |
| `emitir_documento(ra, tipo_documento)` | Registra declaração ou segunda via | **Escrita** | No protótipo, registro corrigível por cancelamento/reemissão; reemitir não desfaz uma cópia já entregue. Validar regras antes de gravar. |
| `escalar_para_humano(ra, tipo_pedido, motivo, chave)` | Abre caso na fila da secretaria | **Escrita** | Reversível por encerramento/reabertura; não executa o pedido escalado. |
| `salvar_estado(solicitacao_id, estado)` — proposta | Guarda progresso, consumo, falhas e protocolos | **Escrita** | Atualizável, com controle de versão; não altera matrícula. |

O código controla as ferramentas; o modelo da triagem devolve somente dados estruturados. Escritas usam chave calculada pelo código a partir de `solicitacao_id + ação + conteúdo normalizado`, com unicidade no armazenamento e retorno `ja_existia`. Uma retomada reutiliza a mesma chave. Uma nova solicitação tem outro identificador.

Não há ferramenta de trancamento. A decisão e execução dessa ação ficam com a coordenação, após confirmação humana explícita, fora deste fluxo. O RA informado deve corresponder ao aluno autenticado no portal antes de consultar ou entregar dados; a autenticação é uma integração prevista, não existente na demonstração local.

### Estado entre etapas e turnos

Persistir: `solicitacao_id`, identidade autenticada, objetivo, `ra`, `tipo_pedido`, `alega_pagamento`, campos faltantes, rota, evidências consultadas, decisão, trajetória resumida de ações e resultados, erros, tentativas de correção, chaves de escrita, protocolos, consumo acumulado, versão da arquitetura/prompt/modelo e motivo de término.

O texto bruto fica restrito à entrada/extração e ao histórico autorizado. Após a triagem, as etapas recebem campos extraídos e evidências, não a conversa inteira. A trajetória registra ações observáveis, não raciocínio interno do modelo.

### Orçamento inicial por solicitação

| Limite | Valor | Ao atingir |
|---|---:|---|
| Etapas executadas, contando repetições | 16 | Encaminhar para atendimento humano. |
| Chamadas ao modelo, incluindo novas tentativas | 3 | Encaminhar com os dados já extraídos. |
| Tokens totais, entrada + saída | 6.000 | Não iniciar chamada sem saldo; encaminhar. |
| Tokens de saída por chamada | 500 | Validar a saída; truncamento é falha, não decisão válida. |
| Tempo ativo total de processamento | 60 segundos | Interromper chamadas e registrar limite de tempo. |
| Tempo de uma chamada externa | 15 segundos, limitado pelo saldo global | Registrar falha; só repetir se houver orçamento. |
| Pedidos de complementação ao aluno | 2 | Na terceira falta/ambiguidade, encaminhar. |
| Correção de RA após consulta sem resultado | 1 | Se a segunda consulta falhar, encaminhar sem inventar RA. |
| Repetição da mesma ação sem dado novo | 2 | Interromper e encaminhar por laço. |

Os tetos são parâmetros, acumulados entre turnos; esperar o aluno não consome tempo ativo. Antes de cada chamada, reservar entrada estimada de forma conservadora mais o máximo de saída dentro do saldo. Na implementação, usar contabilização compatível com o provedor e conferir o consumo retornado. Não reiniciar orçamento em retries. Términos: `CONCLUIDO`, `AGUARDANDO_ALUNO`, `HUMANO`, `ORCAMENTO`, `LACO` e `ERRO`. Se a fila estiver indisponível, salvar a pendência e informar falha, sem inventar protocolo de encaminhamento.

## 3. Processamento — esboço do fluxo

```text
1. ENTRADA       recebe mensagem e identifica solicitação                 [—]
       |
2. EXTRAÇÃO      classifica pedido e extrai RA/alegações                   [ROUTER]
                 código para seleção explícita; LLM para texto livre
                 MAX_CHAMADAS=3; MAX_TOKENS=6.000; MAX_TEMPO=60s (globais)
                 declaração | histórico | trancamento | nenhuma
       |
3. PORTÃO        valida schema, identidade e campos                       [SEQUENCIAL]
                 falta/ambiguidade -> pergunta -> 1 (MAX_PERGUNTAS=2)
                 fora do catálogo -> decisão de encaminhar -> 6
       |
4. CONSULTA      busca cadastro e, para histórico, financeiro              [SEQUENCIAL]
                 RA ausente no banco -> 1 (MAX_CORRECOES_RA=1)
                 falha persistente -> decisão de encaminhar -> 6
       |
5. DECISÃO       aplica regras sobre dados confirmados                    [REGRA EM CÓDIGO]
                 matrícula ativa + declaração -> emitir
                 histórico sem pendência -> emitir
                 trancamento, divergência, impedimento -> humano
       |
6. REGISTRO      emite documento OU abre caso; persiste estado            [ESCRITA]
                 idempotente; registro corrigível/fila reversível
                 trancamento não é executado
       |
7. RETORNO       monta resposta com resultado real e protocolo            [—]
```

Todas as repetições respeitam também os limites globais de 16 etapas e 60 segundos ativos. O registro de estado ocorre ainda nas pausas e nas falhas, não apenas na conclusão da etapa 6. As consultas seguem uma ordem conhecida; não há necessidade de execução paralela nesta v1.

## 4. Contratos: o que entra e o que sai

Cada etapa preserva `solicitacao_id`. O estado acumula os campos produzidos, sem renomear campos entre produtor e consumidor. Exemplos abaixo são **ilustrativos, não logs reais**.

### 1. Entrada

- **Entra:** mensagem do aluno e contexto da sessão autenticada.
- **Sai:** `{"solicitacao_id":"SOL-001","ra_autenticado":"20231045","texto":"Preciso de uma declaração de matrícula. Meu RA é 20231045."}`.

### 2. Extração e Router

- **Entra:** saída de 1 e os campos já extraídos em turno anterior.
- **Sai:** `{"solicitacao_id":"SOL-001","ra":"20231045","tipo_pedido":"declaracao_matricula","rota":"declaracao","alega_pagamento":false,"campos_faltantes":[],"justificativa":"Pedido explícito de declaração de matrícula."}`.
- **Enums:** `rota ∈ {declaracao, historico, trancamento, nenhuma}`; `tipo_pedido ∈ {declaracao_matricula, segunda_via_historico, trancamento_matricula, outro, indefinido}`. Validar a correspondência entre os dois em código.
- **Escape:** `nenhuma` + `indefinido` pede esclarecimento; `nenhuma` + `outro` encaminha. JSON inválido nunca vira uma rota presumida.

### 3. Portão

- **Entra:** campos de 2, identidade da sessão e contadores do estado.
- **Sai:** `{"solicitacao_id":"SOL-001","validacao":{"status":"valido","erros":[],"pergunta":null}}`.
- **Alternativas:** `status="aguardando_aluno"` com `pergunta="Qual é o seu RA?"`, ou `status="encaminhar"` com `decisao={"acao":"encaminhar","motivo":"pedido fora do catálogo","regra":"R4"}`. Identidade incompatível impede consulta e entrega de dados.

### 4. Consulta

- **Entra:** `ra` e `tipo_pedido` validados, obtidos do estado.
- **Sai:** `{"solicitacao_id":"SOL-001","consulta":{"status":"ok","aluno":{"ra":"20231045","nome":"Weslley Sousa","curso":"ADS","situacao_matricula":"ativa"},"financeiro":null}}`.
- Para histórico, `financeiro={"mensalidades_em_aberto":0,"valor_em_aberto":0}`; `null` significa **não consultado**, nunca quitação. Falha retorna `status="erro"`, `erro`, `recuperavel` e `acao_sugerida`, sem seguir para emissão.

### 5. Decisão

- **Entra:** `tipo_pedido`, `alega_pagamento` e `consulta` do estado.
- **Sai:** `{"solicitacao_id":"SOL-001","decisao":{"acao":"emitir","tipo_documento":"declaracao_matricula","motivo":"Matrícula ativa confirmada no cadastro.","regra":"R1"}}`.
- **Regras do protótipo:** R1: declaração exige matrícula ativa; R2: segunda via exige zero pendências consultadas; R3: trancamento sempre humano; R4: exceção, divergência, informação insuficiente ou erro persistente sempre humano. Esses critérios reproduzem o case simulado do grupo, não constituem uma política institucional validada para uso real.
- Alegar pagamento com pendência registrada gera encaminhamento por divergência. Ter comprovante não comprova quitação automaticamente. Não há necessidade de um agente decidir se deve ignorar o cadastro.

### 6. Registro

- **Entra:** `decisao`, RA confirmado quando disponível, `solicitacao_id` e chave de idempotência calculada pelo código.
- **Sai:** `{"solicitacao_id":"SOL-001","registro":{"status":"sucesso","acao":"emitir","protocolo":"DOC-1042","ja_existia":false,"documento":"Declaramos que Weslley Sousa está regularmente matriculado no curso ADS.","prazo_horas":null}}`.
- Para encaminhamento: `acao="encaminhar"`, protocolo `CASO-...`, `documento=null`, `prazo_horas=48`. RA não confirmado pode ser nulo no caso humano. Em erro: `status="erro"`, `protocolo=null`, `erro="..."`; guardar a pendência para retomada.
- A ferramenta de emissão verifica novamente os requisitos no momento da escrita. Se os dados mudaram, recusa a emissão e encaminha; não confia apenas na decisão anterior.

### 7. Retorno

- **Entra:** `registro`, motivo da `decisao` e motivo de término.
- **Sai:** `{"solicitacao_id":"SOL-001","termino":"CONCLUIDO","texto":"Sua declaração de matrícula foi emitida. Protocolo DOC-1042.","documento":"Declaramos que Weslley Sousa está regularmente matriculado no curso ADS."}`.
- Usar template de código, até três linhas para a mensagem de status; o documento fica separado. Só mostrar protocolo retornado por uma escrita bem-sucedida. Na pausa, retornar a pergunta e `AGUARDANDO_ALUNO`; na falha, informar o que não foi concluído.

## 5. Saída que o aluno efetivamente vê

**Exemplo de emissão (ilustrativo):**

> Sua declaração de matrícula foi emitida. Protocolo DOC-1042.
>
> Declaramos que Weslley Sousa está regularmente matriculado no curso ADS.

**Exemplo de encaminhamento (ilustrativo):**

> Seu pedido de trancamento foi encaminhado à coordenação. Protocolo CASO-3311. Resposta em até 48h.

O segundo retorno confirma somente o encaminhamento, nunca a aprovação do trancamento.

## 6. Justificativa dos padrões — menor autonomia que resolve

| Padrão escolhido | Por que ele? | Por que algo mais simples não basta? |
|---|---|---|
| Router na extração | As mensagens têm intenções diferentes e precisam de uma rota explícita, incluindo escape. | Seleção explícita permite regra, mas palavras-chave isoladas não cobrem paráfrases e pedidos ambíguos do chat; usar uma chamada de classificação nesse caminho. |
| Sequencial no portão e nas consultas | Validar identidade/campos precede consultar dados; a consulta válida precede a decisão. | Uma classificação única não verifica existência do RA nem situação real; são etapas dependentes com bloqueio por falha. |

A decisão para no workflow com Router: **esta v1 é um workflow com estado, não um agente autônomo**. Conversar em vários turnos não basta para exigir agente; as perguntas e os próximos passos aqui são limitados e conhecidos. Regras resolvem aprovação/encaminhamento; um template resolve o retorno.

Não escolhemos orquestrador-trabalhador: não existem subtarefas descobertas em execução. Não escolhemos avaliador-otimizador: presença de protocolo, resultado da escrita e campos obrigatórios são verificáveis em código. Não escolhemos paralelização: o pequeno conjunto de consultas condicionais não justifica coordenação adicional nesta primeira versão.

Um agente poderá entrar se o escopo crescer para investigar exceções com diferentes fontes e decidir dinamicamente qual evidência consultar a seguir. Nesse caso, a futura v2 deverá justificar essa necessidade, declarar ferramentas e novos tetos e continuar deixando autorizações institucionais com humanos.

## 7. Ajustes em relação à Parte 1 e avaliação futura

O [case anterior](case.md) classifica o sistema inteiro como agente. A revisão separa interpretação de texto de decisão administrativa: “já paguei” não autoriza superar uma pendência, e trancamento sempre tem destino conhecido. Por isso retiramos da proposta a escolha livre de ferramentas para todo atendimento.

A arquitetura também corrige a ideia de que reemitir desfaz um documento entregue: a correção do registro não recolhe cópias. Idempotência, autenticação, persistência de estado e limites globais descritos aqui são requisitos da implementação futura e não resultados já demonstrados pelo código da Parte 1.

Casos mínimos derivados dos contratos: declaração com matrícula ativa → emitir; histórico com quitação → emitir; alegação de pagamento com pendência → encaminhar; trancamento → encaminhar sempre; RA inexistente em duas tentativas → encaminhar; rota `nenhuma` → esclarecer ou encaminhar; repetição da escrita → mesmo protocolo e `ja_existia=true`; limite excedido → término explícito; falha de escrita → nenhum protocolo inventado.

Manter esta v1 ao criar a v2, registrando o que mudou após implementação e por quê. Versionar arquitetura, prompt, identificação do modelo utilizado e parâmetros junto aos resultados de avaliação. Base desta entrega: enunciado “A arquitetura do agente do seu trabalho”, `docs/case.md` e leitura de `src/agente.py`/`src/dados.py`.
