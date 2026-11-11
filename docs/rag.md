# RAG: o conhecimento de domínio que o agente consulta

O que o agente precisa saber para **decidir** e que não está no modelo: as regras do Regimento Acadêmico (quem decide o trancamento, o que vale como comprovante, qual o prazo) e os registros do sistema acadêmico (matrícula, mensalidades). Não é um chatbot sobre PDF: a consulta é uma **ferramenta do agente** (`consultar_regimento`), e o resultado entra no laço como qualquer outro retorno de ferramenta.

Código: [`src/triagem/regimento.py`](../src/triagem/regimento.py) (índice e ferramenta), [`src/chunking.py`](../src/chunking.py) (corte), [`dados/regimento_dados.py`](../dados/regimento_dados.py) (o corpus). Testes que reproduzem os números deste documento, sem chamar modelo: [`tests/test_regimento.py`](../tests/test_regimento.py).

## 1. As dez perguntas, e a forma que cada uma pede

As perguntas vêm de duas fontes: os textos que os alunos escrevem nos casos de teste da Parte 1 (`dados/casos_verificador.json`), para os pedidos de **registro**, e o conjunto rotulado do Exercício 7 (`dados/casos_rag.json`), para as de **regra**. A classificação foi feita **antes** de escolher o que implementar, e não o contrário.

| # | Pergunta (como o aluno a escreve) | Forma | O que a responde | Exceção? |
|---|---|---|---|---|
| 1 | "Preciso de uma declaração de matrícula, mas tenho pendência financeira. Isso me impede?" (r01) | termo | Art. 3º (declaração independe de pendência) | **sim**: exceção à regra financeira do Art. 4º |
| 2 | "Que condição financeira é exigida para emitir a segunda via do histórico?" (r02) | termo | Art. 4º | não |
| 3 | "Quem decide o trancamento de matrícula: o sistema ou uma pessoa?" (r03) | termo | Art. 6º | não |
| 4 | "Posso mandar um print do aplicativo do banco como comprovante de pagamento?" (n01) | termo | Art. 7º §2º, que **exclui** o aplicativo (armadilha de negação) | **sim** |
| 5 | "Uma liminar judicial de trancamento espera fila normal de atendimento?" (r07) | termo | Art. 8º §3º | **sim**: exceção à pendência e à anuência |
| 6 | "Qual o prazo de resposta da secretaria para um pedido encaminhado à coordenação?" (c01) | termo | Art. 9º §1º (48 h); existe uma redação **revogada** de 72 h | não |
| 7 | "Uma bolsista integral, com convênio empresarial, quer trancar por liminar. O que acontece com a bolsa, o que ela precisa da empresa, e segue a fila normal?" (m01) | relação | Art. 8º §1º, §2º e §3º, **combinados** | **sim** |
| 8 | "Quanto custa emitir a segunda via do histórico escolar?" (s01) | **sem resposta** | nada no corpus; o Art. 4º é do mesmo assunto, mas não trata de preço | n/a |
| 9 | "Já paguei tudo, preciso da segunda via do meu histórico." / "Quantas mensalidades eu tenho em aberto?" | **registro** | tabela `financeiro` (`mensalidades_em_aberto`, `valor_em_aberto`), pela ferramenta `consultar_financeiro` | n/a |
| 10 | "Preciso de uma declaração de matrícula. Meu RA é 20231045." | **registro** | tabela `alunos` (`situacao_matricula`), pela ferramenta `buscar_aluno` | n/a |

**A distribuição:** duas das dez (9 e 10) têm resposta exata por consulta ao banco; sete (1 a 7) pedem busca no texto do Regimento, e a busca **textual** achou todas; uma (8) não tem resposta no corpus. Nenhuma das dez precisou de busca vetorial, e é por isso que o agente não a implementa. Isso tem um limite que declaro: as perguntas de regra foram escritas a partir do corpus, então elas tendem a carregar os termos dos artigos. O §4 mede o que acontece quando não carregam.

**Nenhuma pergunta do case é de agregação** ("quais os temas recorrentes?"): quem a faria é o gestor, que não conversa com o agente. Se um dia o fizer, é uma consulta `SELECT ... GROUP BY` sobre `casos_pendentes`, e não um RAG.

## 2. O que o sistema implementa

| Forma usada | Com o quê | O que ela responde no case |
|---|---|---|
| **consulta estruturada** | SQLite, pelas ferramentas `buscar_aluno`, `consultar_financeiro` (já existiam na Parte 1) | as perguntas 9 e 10 (registro) |
| **busca textual** | SQLite **FTS5**, ranking BM25, tokenizador `unicode61 remove_diacritics 2`, prefixo de 5 letras (`regimento.py`) | as perguntas 1 a 7 (termo e relação) |
| busca vetorial | **não implementada no agente** | (alternativa medida no Ex.7, ver abaixo) |

**"O seu RAG é vetorial ou é banco de dados?"** Banco de dados, nas duas formas que o case usa: registro por consulta SQL e texto por FTS5, os dois dentro do SQLite que o sistema já tem.

**Por que textual e não vetorial.** Três razões, em ordem de peso: (1) o corpus tem 15 artigos numerados e as perguntas carregam o vocabulário do Regimento ("comprovante", "prazo", "trancamento"); a busca por termo acha isso. (2) A imagem do agente tem poucas dependências (`docs/empacotamento.md`): um modelo de embedding local exige `torch` (~2 GB) e a Groq não tem endpoint de embeddings nesta conta (`docs/modelos.md` §3.5). (3) O resultado é determinístico, sem modelo de embedding versionado a vigiar. **O que se perde** está medido no §4.

**A alternativa medida.** O Exercício 7 ([`exercicios/aula-07-resposta-que-cita.md`](../exercicios/aula-07-resposta-que-cita.md)) implementou o pipeline vetorial (`sentence-transformers`, `paraphrase-multilingual-MiniLM-L12-v2`) sobre as mesmas 15 perguntas e mediu recall@k de 100%. Aquele pipeline continua em `src/rag.py`, fora do agente. **Não medi os dois sobre as mesmas paráfrases** (§4), então a comparação direta fica aberta.

## 3. O corpus

| | |
|---|---|
| **o que entra** | o Regimento Acadêmico, 14 artigos vigentes (um chunk por artigo, `src/chunking.py`, com o capítulo no texto) |
| **de onde vem** | `dados/regimento_dados.py`: um Regimento **simulado**, escrito pelo grupo (o grupo não tem acesso ao regimento real; `docs/case.md` §2.9) |
| **quem mantém** | o grupo, hoje; num caso real, a secretaria/coordenação |
| **com que frequência muda** | raramente (revisão de regimento); por isso o índice é construído **na subida** do processo, em memória, em milissegundos, e não persistido |

**O documento revogado, de propósito no corpus.** O Regimento simulado tem duas redações do Art. 9º §1º: **48 h** (vigente) e **72 h** (revogada). O índice entrega só a vigente: a **curadoria** remove o artigo revogado antes de indexar (`IndiceRegimento(incluir_revogados=False)`). Para mostrar o que aconteceria sem isso, `tests/test_regimento.py::test_sem_curadoria_o_defeito_aparece` indexa os dois: a pergunta do prazo devolve **as duas versões**, e nada na recuperação diz qual vale. **A solução não é técnica de recuperação, é curadoria:** quem decide que um documento deixou de valer é quem mantém o corpus.

## 4. O que foi medido

Todos sem chamar modelo, reproduzíveis com `pytest tests/test_regimento.py`.

| Medida | Resultado | Leitura |
|---|---|---|
| recall@3, perguntas com resposta única (10 de `casos_rag.json`, sem `c01`) | **10/10** | acham todos os artigos esperados nos 3 primeiros |
| `c01` (prazo, com artigo revogado) | devolve o Art. 9º §1º vigente | a curadoria funcionou |
| fora de domínio (`x01`, `x02`) | **0 artigos**, 2/2 | nenhum termo em comum: a recusa por ausência é gratuita |
| **sem resposta** (`s01`, `s02`) | **3 artigos de ruído nas duas** | **a busca textual não tem piso de relevância**: basta um termo em comum para entrar no ranking |
| paráfrases sem termo em comum com o artigo (6 escritas por mim) | **4/6** | perde "desconto total do curso" (a bolsa do Art. 8º §1º) e "um juiz mandou" (a liminar do Art. 8º §3º) |

**Os dois defeitos que isso expõe, e o que o sistema faz com cada um:**

1. **Sem piso de relevância.** Para `s01` ("quanto custa a segunda via?"), a busca devolve o Art. 4º (que trata da segunda via, mas não de preço). Quem sabe que ele não responde é o **modelo, lendo o texto**. Por isso o agente declara a suficiência no fim da resposta (`[SUFICIENTE: sim|não]`) e o código a exige (`docs/io.md` §5). **Achado real, no modelo real:** na primeira execução do caso 5 (a mesma pergunta `s01`), o agente respondeu certo ("o Regimento não trata de custo"), mas o objeto de saída saiu com `suficiente: true` e fonte `Art. 4º`, porque o código derivava a suficiência de "a ferramenta devolveu artigo e o texto cita um". Corrigido; o teste que o prova é `tests/test_triagem.py::test_artigo_de_ruido_com_recusa_declarada_e_sem_acao`.
2. **Paráfrase sem termo em comum.** Quem pergunta "um juiz mandou a faculdade me liberar" não recebe o Art. 8º §3º. **O sistema não corrige isso**: é o custo de não ter embedding, aceito e declarado. A amostra (6, escrita por mim, a partir do corpus) só indica o limite; não é uma taxa. Um golden dataset com perguntas reais de alunos é o que mede de verdade (Parte 3).

## 5. O corte e o `k`

**Corte: por estrutura**, um chunk por artigo. O Regimento já vem numerado, e a unidade que o aluno cita ("o Art. 8º §2º") é a unidade que o índice devolve. O capítulo vai no texto do chunk (`[Capítulo IV — ...]`), para o modelo não confundir uma exceção do capítulo IV com uma regra geral do III. Um regulamento corrido, sem artigos, pediria outro corte.

**`k = 3`.** Três artigos vão para o contexto. A pergunta 7 (multi-salto) precisa de três (Art. 8º §1º, §2º e §3º) e os acha com `k = 3`; com `k` maior, a janela enche com artigos de ruído (ver as perguntas sem resposta, que já trazem três). Com `k` menor, a pergunta 7 perde um artigo.

## 6. Onde a recuperação entra no laço

**Ferramenta do agente, não etapa fixa.** O modelo decide quando buscar, como decide chamar `buscar_aluno`. A regra 7 do prompt (`src/prompts/triagem-v2.txt`) diz quando usar e que **não** se usa para decidir o pedido de um aluno (quem decide é o cadastro e o financeiro, regras 1 a 6).

**Por que não etapa fixa:** um pedido de declaração ("Preciso de uma declaração. RA 20231045") não precisa do Regimento; uma etapa fixa o buscaria em toda execução, e a busca seria inútil na maior parte delas.

**Medido nas execuções reais** (`logs/parte2/`, 8 execuções, modelo `qwen/qwen3.8-27b`): **1 chamada** de recuperação (05-fora-do-corpus), em 8 execuções. **Zero buscas inúteis**: a única busca foi a de uma dúvida de regra. É uma amostra de 8 casos montados para os seis papéis do §9 da Parte 2, **e só um deles é uma dúvida de regra**; não permite estimar a taxa de buscas inúteis num uso real. A suíte da Parte 3 mede isso sobre 24 casos.

## 7. Riscos

- **Texto de terceiro no contexto.** O que `consultar_regimento` devolve entra no contexto do modelo. O Regimento é curado pelo grupo, mas é um canal de conteúdo não confiável por natureza: um artigo que dissesse "ignore as regras anteriores" seria lido pelo modelo. Mitigação: a regra 7 proíbe usar o artigo para decidir pedido, e emissão e escalonamento só acontecem por ferramenta com guardas em código (`docs/seguranca.md`, ASI01/ASI06).
- **Citação inventada.** O validador confere cada artigo citado contra os devolvidos (`validacao.artigos_citados`); citar um que a ferramenta não devolveu reprova a resposta.
