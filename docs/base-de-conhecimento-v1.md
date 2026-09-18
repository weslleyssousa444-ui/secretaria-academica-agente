# Exercício 6 — Base de conhecimento v1 do agente de triagem

**Grupo:** Weslley Soares de Sousa, Pedro Akira, Henrique Gomes Matos e Erick.
**Case:** atendimento de solicitações na secretaria acadêmica ([`docs/case.md`](case.md)).
**Versão:** base-de-conhecimento-v1, 18/09/2026.
**Natureza da entrega:** decisão de projeto sobre a base de conhecimento (RAG) do agente; nada aqui está indexado ou implementado — é o insumo já anunciado como pendência em [`docs/case.md` §2.10](case.md) e [`docs/fontes.md`](fontes.md).

A arquitetura v1 ([`docs/arquitetura-v1.md`](arquitetura-v1.md)) resolveu o *fluxo* de decisão sem precisar de recuperação: as regras de negócio (matrícula ativa, quitação, trancamento sempre humano) estão em código, e cadastro/financeiro vêm de consulta direta ao SQLite. O que falta, e que esta entrega decide, é **o que o agente precisaria consultar por fora do código para parar de escalar toda exceção por padrão** — o Regimento Acadêmico e os textos institucionais que hoje não existem no repositório.

## 1. Qual informação especializada o agente precisa, e por que ela não está no modelo

| Item | Por que não está no modelo | Razão |
|---|---|---|
| Regimento Acadêmico — normas de trancamento, prazos processuais, condições de exceção (bolsista, convênio empresarial, liminar judicial) | É a norma **desta** instituição; o modelo conhece o conceito genérico de trancamento de matrícula em faculdades brasileiras, mas não qual documento este regimento exige, nem o prazo que ele fixa | é privado **e** específico demais |
| Catálogo de textos oficiais dos documentos emitidos (redação exata da declaração de matrícula e da segunda via de histórico, no padrão da instituição) | O agente já emite os dois hoje com um template fixo no código (`arquitetura-v1.md` §7, passo 7); se a instituição tiver um texto oficial diferente do que o grupo inventou, é ele que precisa entrar, não uma paráfrase do modelo | é privado |
| Tabela de prazos e SLAs institucionais por tipo de caso (os 48h usados hoje são suposição do grupo, `case.md` §2.1) | Prazo institucional pode variar por tipo de pedido e mudar por resolução do conselho; o modelo não tem como adivinhar o valor vigente | é privado **e** pode ficar desatualizado (recente demais) |
| FAQ da secretaria — perguntas que a atendente já responde hoje por e-mail e que hoje não têm registro nenhum (`case.md` §2.1, "o que existe antes e depois") | Não é conhecimento do modelo nem documento formal ainda: é conhecimento tácito da atendente. Só vira fonte depois de uma entrevista que o transforme em texto | é privado (e, por ora, nem existe como documento) |

**O que o modelo já sabe e não deve ser indexado:** o conceito genérico do que é uma declaração de matrícula ou um histórico escolar, redação formal em português, e o fluxo genérico de trancamento em instituições brasileiras (que existe, mas não substitui a norma local). Indexar isso seria pagar contexto por algo que qualquer chamada já produz sem consulta.

**E o que já é resolvido sem RAG:** o cadastro do aluno e a situação financeira **não entram nesta lista** — são dados estruturados, já servidos por `buscar_aluno` e `consultar_financeiro` (SQLite, `src/dados.py`), e voltam na pergunta 3 como o exemplo de "isso é consulta, não recuperação".

**Teste antes de indexar (pendência declarada, mesmo padrão de `docs/modelos.md` §3.3):** quando o grupo tiver acesso ao regimento real, rodar cinco perguntas específicas contra o modelo sem contexto e conferir contra o texto — por exemplo: *"qual o prazo de resposta para pedido de trancamento nesta instituição?"*, *"quais comprovantes um bolsista precisa anexar para pedir isenção de uma regra padrão?"*, *"um trancamento pode ser revertido no mesmo semestre?"*. O padrão esperado, dado o Regimento ser norma interna não publicada, é o modelo errar ou alucinar as cinco — o que confirma a necessidade da fonte em vez de presumi-la.

## 2. Onde esses dados estão, e em que estado

| Fonte | Onde vive | Formato | Dono / frequência de mudança | Acesso hoje |
|---|---|---|---|---|
| Regimento Acadêmico | Hipótese do grupo: pasta da coordenação acadêmica ou intranet institucional — **não confirmado** | Desconhecido; `case.md` §2.10 estima ~20 páginas; risco real de ser PDF digitalizado de cópia física, não nativo | Coordenação acadêmica / jurídico institucional; muda por resolução do conselho — raro, mas com adendos possíveis entre resoluções | **Sem acesso.** Já registrado como pendência em `docs/fontes.md` — dado sensível/institucional, o grupo não tem contato direto com a coordenação. Ação: solicitar cópia formal via professor da disciplina ou secretaria; até lá, v1 trabalha com um regimento simulado, marcado como placeholder |
| Catálogo de textos oficiais dos documentos | Provável pasta da secretaria (modelo Word/PDF usado para emitir manualmente hoje) | Word ou PDF nativo (documento produzido internamente, não escaneado) | Secretaria acadêmica; muda raramente, só quando a instituição atualiza o padrão de emissão | **Sem acesso.** Mesmo caminho do regimento: pedir o modelo em uso; v1 continua com o texto que o grupo já escreveu no código |
| Tabela de prazos e SLAs | Provavelmente parte do próprio Regimento ou de uma normativa interna separada | Mesma incerteza do regimento | Coordenação acadêmica | **Sem acesso** — mesma pendência |
| FAQ da secretaria | Não existe como documento — é o que a atendente já sabe responder | Nenhum ainda; precisaria ser escrito a partir de entrevista | Atendente de secretaria (usuário principal do case, `case.md` §2.2); mudaria conforme a rotina da secretaria | **Sem acesso formal.** Não é "documento perdido", é conhecimento que ainda não foi registrado — nenhuma ferramenta de RAG resolve isso sozinha; é trabalho de entrevista antes de virar fonte |
| Cadastro e financeiro do aluno | `dados/academico.db` (SQLite) | Registro de banco relacional | Grupo, dados sintéticos (`case.md` §2.9); atualização é transacional, a cada emissão/consulta | Acesso total — já implementado; **não é fonte de índice** (ver pergunta 3) |

**Isto mata a v1 por enquanto:** três das quatro fontes de conhecimento não estruturado não têm dono acessível ao grupo hoje. É melhor essa base de conhecimento nascer com placeholders explícitos do que fingir que o Regimento já foi lido — a Parte 2 do trabalho é o lugar certo para registrar se o acesso veio ou não.

Nenhuma fonte confirmada até agora é PDF escaneado, mas o Regimento é candidato a ser: é o cenário mais provável para um documento administrativo antigo mantido em papel. Se vier assim, extrair o texto é problema à parte (Aula 07) — a estratégia de corte da pergunta 4 assume texto já extraído.

## 3. O que vai para o índice — e o que não vai

**O que entra, com o acesso resolvido:** o Regimento Acadêmico (~20 páginas, `case.md` §2.10) e o catálogo de textos oficiais (2 templates curtos, poucas páginas). O FAQ entra só depois de virar texto por entrevista — não é decisão desta v1, é dependência.

**Volume e ordem de grandeza dos chunks:** ~20-25 páginas de Regimento, cortadas por artigo (pergunta 4), mais 2-4 páginas de templates. Isso dá **dezenas de chunks — não centenas, não milhares** (a nota 04 mediu 28 vetores como referência de "pequeno"; esta base fica na mesma faixa, talvez até 60-80 se o Regimento tiver muitos artigos curtos).

**Consequência direta para ferramenta:** com dezenas de chunks, **não há motivo para banco vetorial nenhum**. Uma lista de embeddings em memória (numpy), recarregada a cada start do processo do agente, resolve — o mesmo resultado que a nota 04 mediu, e sem operar infraestrutura adicional para um volume que cabe folgado em RAM.

**O que fica de fora, e por quê:**
- Cadastro e financeiro do aluno — não são texto para busca por similaridade, são registros com chave (`ra`). Continuam em `buscar_aluno`/`consultar_financeiro`.
- Protocolos de documentos já emitidos e casos pendentes (`documentos_emitidos`, `casos_pendentes`) — mesma razão: consulta por `protocolo` ou `ra`, não por sentido.
- Histórico de conversas passadas do aluno — não é base de conhecimento institucional, é estado de sessão (já coberto em `arquitetura-v1.md` §2, "Estado entre etapas").

**O que é consulta estruturada, não busca semântica (a distinção que a nota 04 pede):**

| Pergunta que o agente responderia | Como se resolve |
|---|---|
| "O aluno com este RA tem matrícula ativa?" | `buscar_aluno(ra)` — igualdade exata na chave primária |
| "Quantas mensalidades em aberto o aluno tem?" | `consultar_financeiro(ra)` — igualdade exata |
| "Este protocolo já foi emitido antes?" | consulta por `protocolo` em `documentos_emitidos` — igualdade exata |
| "O que o Regimento diz sobre a condição de bolsista para pular a regra padrão de trancamento?" | **Esta é busca semântica de verdade** — não há chave para "condição de bolsista", é preciso recuperar o trecho certo do texto |

A régua é simples: se a pergunta tem uma coluna e um operador (`==`, `<=`, `in`), é banco. Se a pergunta pede o trecho de um texto que discute um conceito, é recuperação — e é só a segunda linha da tabela acima que justifica esta base de conhecimento existir.

## 4. A estratégia de chunking

Duas fontes, dois cortes — nenhuma estratégia única serve às duas.

**Regimento Acadêmico.** Tem unidade natural: capítulo → artigo (a mesma estrutura que a nota 02 mediu, e por isso o corte estrutural deve vencer aqui também, contanto que o documento real preserve essa hierarquia). Corte por artigo, não por contagem de caracteres. Um artigo isolado que diga "nas condições do parágrafo anterior" fica órfão se cortado sozinho — a correção é o chunk herdar o cabeçalho do capítulo e o número do artigo anterior como prefixo, não o texto inteiro do capítulo. Metadado por chunk: `capitulo`, `numero_artigo`, `tipo_excecao` (`bolsista | convenio | liminar | trancamento_geral | nenhuma`, quando aplicável), `versao_regimento`, `data_vigencia`. O metadado de exceção é o que permitiria, futuramente, filtrar antes de buscar — por exemplo, restringir a busca aos artigos marcados `trancamento_geral` quando o pedido já foi classificado como trancamento pelo Router da arquitetura v1.

**Catálogo de textos oficiais dos documentos.** Unidade natural também existe, mas é mais grosseira: um chunk por tipo de documento (declaração de matrícula, segunda via de histórico) — o texto de cada template é curto o bastante para não precisar de corte interno. Cortar mais fino que isso quebraria o template no meio de uma frase que o agente precisa reproduzir inteira. Metadado: `tipo_documento`, `versao_template`.

**FAQ da secretaria (quando existir).** Unidade natural é o item pergunta-resposta — um chunk por par, sem dividir pergunta de resposta. Metadado: `categoria` (`declaracao | segunda_via | trancamento | geral`), `data_ultima_atualizacao`.

**Cadastro e financeiro.** Não se aplica — não há chunking porque não há indexação (pergunta 3).

O critério de aceite é sempre o mesmo, documento a documento: o chunk faz sentido para quem não leu o resto do texto? Um artigo do Regimento sem o cabeçalho do capítulo, ou uma resposta de FAQ sem a pergunta, falha nesse teste — por isso o cabeçalho e o par pergunta-resposta são herdados, não descartados no corte.
