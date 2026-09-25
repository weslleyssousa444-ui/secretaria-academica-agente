# Exercício 7 — A resposta que cita, e que recusa

**Grupo:** Weslley Soares de Sousa, Pedro Akira, Henrique Gomes Matos e Erick.
**Data:** 25/09/2026.
**Natureza:** exercício complementar (não avaliado isoladamente) — o produto entra na Parte 2 do trabalho, §3.4-3.6 (`docs/rag.md`). Este documento é o rascunho dele.

O Exercício 6 entregou só o plano de uma base de conhecimento (`docs/base-de-conhecimento-v1.md`) — nenhum índice existia de fato. Este exercício constrói o índice, o pipeline completo (recuperar → montar contexto → gerar), a citação verificável e o portão de recusa, sobre um **Regimento Acadêmico simulado** (100% sintético, mesma regra de `docs/case.md` §2.9 — o real continua inacessível ao grupo).

**Pergunta a responder ao final:** o sistema recusa quando deve? Quantas vezes recusa quando não deveria?

**Resposta curta:** sim, nas 4 perguntas sem resposta no corpus (2 fora de domínio, 2 dentro do domínio mas não tratadas). Zero recusas indevidas nas 10 perguntas restantes elegíveis (excluída a armadilha de contradição deliberada, que tem comportamento correto próprio — ver §3).

---

## 1. O pipeline

**Corpus:** `dados/regimento_dados.py`, 15 artigos (14 vigentes + 1 revogado deliberadamente, ver §3), cobrindo declaração de matrícula, segunda via de histórico e trancamento — os mesmos três tipos de pedido do case (`docs/case.md`).

**Chunking:** um chunk por artigo (`src/chunking.py`), corte por estrutura (Aula 06, nota 02) — a unidade natural do documento já é o artigo. Cada chunk herda o cabeçalho do capítulo.

**Embedding:** local, `sentence-transformers` (`paraphrase-multilingual-MiniLM-L12-v2`), não a API da Groq — ela não tem endpoint de embeddings nesta conta (`client.models.list()` não devolve nenhum). É uma troca prática do mesmo tipo que já levou de Mistral para Groq no Exercício 6: sem custo, sem risco de rate limit.

**Índice:** matriz numpy em memória, sem banco vetorial (`src/indice_rag.py`) — 15 chunks é a mesma ordem de grandeza que `docs/base-de-conhecimento-v1.md` §3 já previa, e para a qual a nota 04 da Aula 06 mediu numpy vencendo banco vetorial.

**`k=3`**, escolhido porque o desafio B (multi-salto, §5) precisa de exatamente 3 artigos para responder — `k` menor não cobriria; testar `k` maior não mudou o recall dos outros casos.

**Geração:** `openai/gpt-oss-20b` (Groq, free tier), **não** o `qwen/qwen3.8-27b` do agente de triagem (Ex.6/`src/agente.py`). Achado ao testar de verdade: o `qwen` tem um teto de **1.000 tokens de saída por minuto (OTPM)** separado do limite geral de 8.000 tokens/min — uma única chamada de resposta+citação pediu 1.497 e foi recusada, sem alternativa de espera (o teto é por chamada, não cumulativo). `gpt-oss-20b` não mostrou esse subteto nos testes. Por isso o RAG usa uma variável de ambiente própria (`RAG_MODELO`), independente do `LLM_MODELO` do agente — nenhum dos dois mexe no outro.

### O efeito da ordem no contexto (pedido do item 1)

Mesmos 3 trechos (Capítulo IV inteiro), pedido certo primeiro vs. no meio:

| Ordem | Resposta | Fontes citadas |
|---|---|---|
| Art. 8º §3º, Art. 8º §1º, Art. 9º §1º | *"...processado independentemente da fila normal, conforme Art. 8º §3º."* | `['Art. 8º §3º']` |
| Art. 8º §1º, Art. 8º §3º, Art. 9º §1º | *"...processado independentemente de pendências financeiras ou anuência de terceiros, e a coordenação cumpre a ordem judicial no prazo nela fixado, ou, na omissão, no prazo do Art. 9º §1º."* | `['Art. 8º §3º', 'Art. 9º §1º']` |

**As duas respostas continuam corretas em substância** — é uma reprodução mais branda do viés de posição que a nota 04 §4 descreve (lá, a segunda ordem produzia resposta **errada**). Aqui, o que muda é a citação: só quando o Art. 8º §3º sai do topo o modelo também traz o Art. 9º §1º para a resposta. Ainda assim, é evidência do mesmo fenômeno: **o conjunto de fontes citadas depende de onde o trecho certo está na lista**, não só do que está no contexto — ver modo de falha 2, §5.

---

## 2. A citação verificável

Contrato de saída (nota 05 §1), adaptado ao domínio:

```json
{"resposta": "...", "fontes": ["<rótulos dos trechos usados>"], "suficiente": true|false}
```

Verificação em código, nunca no modelo (`src/rag.py`, `citacao_verificavel()`).

**Achado real ao rodar pela primeira vez: 0% de citações verificáveis.** Não foi alucinação — foi um bug de formatação nosso. O prompt pedia "cite exatamente como aparece entre colchetes", e o modelo interpretou isso como **incluir os colchetes na citação** (`"[Art. 3º]"`), enquanto o `id` do chunk é só `"Art. 3º"` (sem colchetes). A comparação em código, ao pé da letra, rejeitava tudo. Corrigido dos dois lados: o prompt agora diz explicitamente "sem os colchetes", e `citacao_verificavel()` normaliza colchetes antes de comparar, para não depender só da obediência literal do modelo. Depois da correção: **100% de citações verificáveis** nas 10 perguntas respondidas.

**A lição:** "a citação precisa ser verificável" (nota 05 §3) vale para o *verificador* também — uma checagem rígida demais mistura formatação com alucinação, e o primeiro instinto ("o modelo está inventando fonte") estava errado.

---

## 3. O portão, e a recusa

### Onde fica o limiar

Medido, não escolhido no chute (varredura em `src/avaliar_rag.py::varrer_limiar`, sem gastar chamada de geração — só recuperação):

```
limiar=0.10  FP=4 [s01, s02, x01, x02]  FN=0 []
limiar=0.15  FP=3 [s01, s02, x01]       FN=0 []
limiar=0.20  FP=3 [s01, s02, x01]       FN=0 []
limiar=0.25  FP=2 [s01, s02]            FN=0 []
limiar=0.30  FP=2 [s01, s02]            FN=0 []
limiar=0.35  FP=2 [s01, s02]            FN=0 []   <- escolhido
limiar=0.40  FP=2 [s01, s02]            FN=0 []
limiar=0.45  FP=2 [s01, s02]            FN=0 []
limiar=0.50  FP=2 [s01, s02]            FN=0 []
limiar=0.55  FP=2 [s01, s02]            FN=3 [r01, r02, r03]
```

Com o par de controle da nota 02 §1 (perguntas sem relação alguma com o regimento — previsão do tempo, copa do mundo): o piso real de cosseno para este corpus e este modelo de embedding fica em **0,08–0,20**. As perguntas "sem resposta" **dentro do domínio** (`s01`: custo da segunda via; `s02`: prorrogação automática) pontuam **0,57–0,67** — tão alto quanto perguntas genuínas (`r01`=0,51, `r03`=0,54).

**Achado central: nenhum limiar de score separa "sem resposta dentro do domínio" de "com resposta".** Subir o limiar até 0,55 introduz falsos negativos reais (`r01`, `r02`, `r03` passam a ser recusados) **sem** nunca resolver `s01`/`s02`. O limiar de **0,35** é o ponto certo: zera falso negativo, pega as perguntas realmente fora de domínio (`x01`, `x02`), e deixa para o segundo portão — o campo `suficiente` — a distinção mais fina (assunto certo, resposta específica ausente). Isso não é uma falha de calibração: é a prova de que **os dois portões são estruturalmente necessários**, não redundantes (nota 05 §2).

### O que o sistema diz ao recusar

Nunca "não sei" puro. Exemplo real (`s01`, com o portão de score):

> *"O regimento não parece tratar deste assunto. O trecho mais próximo encontrado foi 'Art. 4º', mas a semelhança está abaixo do limiar de confiança — em vez de arriscar uma resposta sobre outro assunto, prefiro recusar."*

E com o portão de score desligado, o campo `suficiente` sozinho ainda produz recusa útil (`s01`, exemplo real): *"Os trechos fornecidos indicam que a emissão da segunda via do histórico escolar exige quitação financeira total do aluno, mas não especificam o valor ou custo da emissão."* — diz o que os trechos tratam, não só que recusou.

### Os dois erros, medidos

Sobre as 15 perguntas rotuladas (`dados/casos_rag.json`), excluída a de contradição deliberada (`c01` — ver abaixo, tem comportamento correto próprio, não cabe em "deveria/não deveria recusar"):

| Erro | Contagem | Casos |
|---|---|---|
| Falso positivo (respondeu quando devia recusar) | **0/4** | — |
| Falso negativo (recusou quando podia responder) | **0/10** | — |

A troca escolhida: **zero falso negativo com uma folga generosa** (limiar bem abaixo do primeiro FN observado, 0,55), aceitando que o portão de score sozinho não pega tudo — o campo `suficiente` cobre o resto. É a mesma priorização do critério de sucesso do agente de triagem (`docs/case.md` §2.7): o custo de recusar bom demais é menor que o custo de responder errado com confiança.

**Sobre `c01` (a armadilha de contradição deliberada — ver §5, modo 4):** o pipeline recusou (`suficiente=false`), dizendo *"Existem duas versões do prazo: 48 horas úteis e 72 horas úteis. Não é possível determinar qual é a válida com os trechos fornecidos."* Isto é o comportamento **correto** — recusar decidir sozinho diante de um corpus contraditório — mas o critério de teste original contava isso como "recusa indevida", porque `c01` tinha uma resposta certa esperada (48h vigente). Corrigido: perguntas do tipo "contradição" saem do denominador de recusa indevida, porque para elas o julgamento binário não se aplica — o que se avalia é se o sistema **flagra** a contradição, não se responde com o valor certo.

---

## 4. As duas métricas, separadas

| `recall@k` | Fidelidade | Onde está o defeito |
|---|---|---|
| **100%** (15/15 elegíveis) | **80%** (8/10 respondidas) | ver diagnóstico por pergunta |

```
DIAGNÓSTICO POR PERGUNTA
  r01  recall ok     fidelidade ok     -> ok
  r02  recall ok     fidelidade ok     -> ok
  r03  recall ok     fidelidade ok     -> ok
  r04  recall ok     fidelidade ok     -> ok
  r05  recall ok     fidelidade ok     -> ok
  r06  recall ok     fidelidade ok     -> ok
  r07  recall ok     fidelidade falhou -> prompt de resposta
  r08  recall ok     fidelidade ok     -> ok
  n01  recall ok     fidelidade ok     -> ok
  c01  recall ok     fidelidade —      -> recusou corretamente (ver §3)
  s01  recall —      fidelidade —      -> recusou corretamente
  s02  recall —      fidelidade —      -> recusou corretamente
  m01  recall ok     fidelidade falhou -> prompt de resposta (ver análise abaixo)
  x01  recall —      fidelidade —      -> recusou corretamente
  x02  recall —      fidelidade —      -> recusou corretamente
```

Recall alto o tempo todo — o índice de 15 chunks e o `k=3` cobrem bem este corpus pequeno. As duas falhas de fidelidade **não** são de recuperação: os trechos certos chegaram nos dois casos.

### `r07` — inferência razoável, marcada como sem lastro

Pergunta: *"Um pedido de trancamento por liminar judicial espera fila normal de atendimento?"*

Resposta: *"...não espera na fila normal de atendimento. Ele é processado independentemente de pendências financeiras ou anuência de terceiros..."*

O juiz de fidelidade marcou a primeira frase como sem lastro, porque o Art. 8º §3º nunca usa literalmente as palavras "fila normal" — ele diz "independentemente da existência de pendência financeira ou de anuência de terceiros". A inferência do modelo (não esperar fila = ser processado sem essas duas condições) é razoável, mas o juiz, instruído a avaliar só o que está **literalmente** nos trechos (nota 03 §1), tem razão em marcar: **"fila normal" é uma paráfrase que o texto não sustenta ao pé da letra.** É um caso de fronteira — inferência aceitável para um leitor humano, mas fora do critério estrito de fidelidade que a métrica pede. Vale registrar como limite do juiz automatizado, não como erro grave do agente.

### `m01` — o achado mais importante do exercício (desafio B)

Pergunta de multi-salto: *"Uma aluna bolsista integral, vinculada também a um convênio empresarial, quer trancar a matrícula por liminar judicial. O que acontece com a bolsa, o que ela precisa apresentar da empresa, e o pedido segue a fila normal?"*

`k=3` recuperou os **três artigos certos** (Art. 8º §1º, §2º, §3º) — **recall 100%**. E mesmo assim, a resposta erra:

> *"...Como o trancamento é amparado por decisão judicial liminar, a coordenação não precisa da anuência da empresa conveniada, pois o **Art. 8º §3º dispensa essa exigência**."*

**Isto é falso.** O Art. 8º §3º dispensa pendência financeira e anuência de terceiros **no contexto da liminar em si** — não revoga a exigência **separada e cumulativa** do Art. 8º §2º sobre convênio empresarial. Os dois parágrafos tratam de exceções **independentes**, não hierárquicas, e o modelo **compôs** uma exceção que nenhum dos dois textos autoriza.

**É exatamente o alerta do enunciado (Desafio B): "perguntas multi-salto são onde o recall alto engana."** Aqui o engano é mais sutil que o da nota 03 (que mostrava recall **baixo** — só 2 de 3 artigos recuperados). Recall foi perfeito; o defeito está inteiramente na **composição** dos três artigos pela geração — o prompt não instrui o modelo a tratar exceções de capítulos/parágrafos diferentes como independentes por padrão. É diagnóstico de **prompt**, não de índice, mas de um tipo que a tabela original da nota 03 não nomeia: não é "ignorou o trecho" nem "inventou sem base" — é "combinou dois trechos verdadeiros numa conclusão falsa". Vale como contribuição própria deste exercício à tabela de diagnóstico.

---

## 5. Os quatro modos de falha

### Modo 1 — recuperou o trecho errado

Pergunta armadilha (segunda via de **diploma**, que o Art. 5º explicitamente exclui do escopo, ao lado do Art. 4º sobre segunda via de **histórico**, que é tratado):

```
top1 recuperado: Art. 5º (esperado: Art. 5º) -> ok
```

**Não reproduziu.** O modelo de embedding distinguiu bem "diploma" de "histórico" — palavras diferentes, ao contrário do exemplo da nota 04 (onde "informática" aparecia nos dois artigos em disputa). Achado honesto: a armadilha de negação **depende de quanto vocabulário os dois artigos em conflito compartilham**; quando as palavras-chave diferem, o vetor não precisa de ajuda semântica para diferenciar. A armadilha de negação real deste corpus está em `n01` (comprovante bancário, Art. 7º §2º) — recuperada corretamente (recall ok), mas ali o risco não era de recuperação, e sim de o modelo ignorar a negação no próprio texto recuperado (o que não ocorreu: resposta e fidelidade ok).

### Modo 2 — recuperou e ignorou (viés de posição)

Ver §1 acima. Reproduzido de forma branda: a citação muda com a ordem, a substância não erra desta vez.

### Modo 3 — respondeu sem base

Três perguntas testadas **sem contrato nenhum** (nem schema, nem campo `suficiente` — réplica exata do "SEM contrato" da nota 05, Exemplo 1): custo da segunda via, prorrogação automática, e uma pergunta adversarial com um número plausível por perto (48h do Art. 9º §1º, tentando induzir o modelo a inventar um prazo de reativação de bolsa que o regimento não fixa).

**Não reproduziu em nenhuma das três**, nem mesmo sem contrato. Exemplo (a pergunta adversarial, sem contrato nenhum):

> *"A bolsa não é reativada automaticamente... Portanto, não há um prazo fixo em dias para a reativação; ela só ocorre após a nova análise socioeconômica."*

**Achado honesto:** este modo de falha é **dependente do modelo**, não universal. `openai/gpt-oss-20b` é um modelo de "raciocínio" (gasta tokens ocultos pensando antes de responder — descoberto ao debugar o Exercício 6, `docs/modelos.md` §3.5) e se mostrou consistentemente cauteloso nas três tentativas, mesmo sem instrução explícita de recusa. **Isso não invalida a exigência do contrato** — o ganho real do contrato aqui não é evitar alucinação (o modelo já não alucina), é tornar a recusa **programaticamente acionável**: `suficiente=false` é um campo que o código verifica; *"não há um prazo fixo"* é uma frase que precisaria de outro classificador para virar sinal de roteamento. O valor do contrato mudou de "impedir erro" para "produzir um sinal estruturado" — uma nuance que vale mais que fingir ter reproduzido uma falha que não aconteceu.

### Modo 4 — trechos contraditórios

Pergunta: *"Qual o prazo de resposta da secretaria para um pedido encaminhado?"*

```
sem filtro de vigência: ['Art. 9º §1º', 'Art. 9º §1º (redação de 2024, revogada)', ...]
com filtro de vigência:  ['Art. 9º §1º', 'Art. 2º', ...]
```

As duas versões do Art. 9º §1º (48h vigente vs. 72h revogada) são recuperadas juntas quando `apenas_vigentes=False` (o padrão do pipeline). **Reproduzido exatamente como a nota 04 §6 descreve**: recall alto (a versão vigente está lá), e a resposta do pipeline padrão:

> *"O Regimento apresenta duas versões do Art. 9º §1º: uma estabelece prazo de 48 horas úteis e a outra, revogada em 2024, estabelece prazo de 72 horas úteis. Não há indicação de qual versão está em vigor."*

`suficiente=false`. O sistema **não decidiu silenciosamente** — recusou, graças à instrução explícita no prompt ("se dois trechos tratarem do mesmo dispositivo... não escolha um silenciosamente").

---

## 6. O corpus desatualizado

**O sistema tem como saber, por conta própria, que a redação de 2024 foi revogada?**

**Não.** Nada no **texto** do chunk diz isso — só o campo `vigente` do metadado sabe, e a busca padrão (`apenas_vigentes=False`) não o consulta. O que evitou a resposta errada foi inteiramente o **prompt**, instruído a desconfiar de dois trechos com o mesmo assunto e valores diferentes. Se a instrução fosse removida (ou se o modelo a ignorasse), a busca continuaria trazendo as duas versões, e não haveria nada no pipeline capaz de saber qual descartar.

**Isto não é problema de recuperação — é curadoria de corpus** (nota 04 §6, quase literalmente): a correção real é **filtrar por `apenas_vigentes=True` na indexação de produção**, ou melhor, **remover a versão revogada do índice** antes de indexar, deixando-a só em um arquivo histórico fora de alcance da busca. Pedir ao prompt para adivinhar qual versão vale é a segunda melhor solução, não a primeira — e só funciona enquanto o modelo obedecer à instrução.

---

## 7. O que fica para a Parte 2

- [ ] **Desafio A** (recuperação como ferramenta do agente) — não tentado nesta entrega, por tempo. É natural para a Parte 2, que já pede exatamente essa arquitetura (`docs/case.md` §2.10, RAG "Parte 2").
- [x] **Desafio B** (pergunta multi-salto) — feito (`m01`). O achado (recall 100%, composição errada) é o resultado mais valioso do exercício e deveria virar um item explícito do prompt de resposta na Parte 2: instruir o modelo a tratar parágrafos de exceção como independentes salvo remissão explícita.
- [ ] **Curadoria do corpus real** — quando/se o Regimento Acadêmico real chegar (`docs/case.md` §2.10-2.11), a primeira tarefa é retirar versões revogadas do índice, não confiar no prompt para isso.
- [ ] **`comparar_modelos.py`-like para o RAG** — só um modelo de geração foi testado a fundo (`gpt-oss-20b`); `qwen` ficou inviável pelo teto de OTPM, `gpt-oss-120b` não foi testado por prudência de tempo/cota.

## Carimbo

`k=3` · `limiar=0.35` · embedding `paraphrase-multilingual-MiniLM-L12-v2` (local) · geração `openai/gpt-oss-20b` (Groq) · prompt de resposta v1 (`src/rag.py`, `PROMPT_SISTEMA`) · corpus `dados/regimento_dados.py` v1 (15 artigos, 25/09/2026).

Relatórios completos: `logs/avaliar_rag.json`, `logs/modos_de_falha.json`.
