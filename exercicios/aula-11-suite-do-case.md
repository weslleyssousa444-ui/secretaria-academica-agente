# Exercício 11 — A suíte do case: resultado

**Execuções de 30/10 a 02/11/2026.** Desenho e regra de promoção em [`aula-11-avaliacao.md`](aula-11-avaliacao.md). Saída completa de `python src/suite/relatorio.py` em [`docs/evidencias/suite-ex11.txt`](../docs/evidencias/suite-ex11.txt). Código em [`src/suite/`](../src/suite/); testes dos avaliadores em [`tests/test_suite.py`](../tests/test_suite.py) (20, offline).

## Decisão

**Não promover a troca de `qwen/qwen3.8-27b` (A) por `openai/gpt-oss-20b` (B).** B aprova 90% das execuções contra 100% de A (−10,4 pontos). Três das quatro regras que valem para a decisão foram violadas (R1, R2, R3); R4 foi atendida; R5 não se aplica, porque o juiz não foi adotado.

> **Resposta à questão do exercício.** *Qual foi o ruído de base?* **Zero ponto na métrica de aprovação** (A1 = A2 = 100%, 24 casos cada). O ruído existe, mas está no **texto**: das 24 respostas finais de A, 11 mudaram de redação entre as duas execuções (temperatura 0 não garante determinismo na Groq), sem mudar nenhuma decisão nem nenhum estado do banco. Em B, 16 de 24 mudaram. *Quantas das mudanças já promovidas teriam passado pela regra?* **Não sei dizer: o desafio B (retroativo) não foi feito.** A única mudança avaliada é a troca de modelo, e ela não passa. Com A em 100%, a regra R1 (melhora de pelo menos 5 pontos) é **impossível de cumprir**: a suíte, como está, só detecta piora.

## O que saiu na tela

```
DATASET v1.0.0   24 casos
  por origem:   producao 0   desenvolvimento 16   sintetico 8
  por classe:   emissao 5  pendencia 4  trancamento 6  recusa 6  borda 3

VALIDAÇÃO DO JUIZ (rubrica v1.1.0) — HOLD-OUT: rotulado depois da revisão
                    humano: fiel   humano: não fiel   (rótulos provisórios)
    juiz: fiel            21               2
    juiz: não fiel         1               3
  n=27  concordância: 89%  recall de 'não fiel': 60%  limiar declarado: 85% e 80%   VEREDITO: não
  desacordos: 3  (juiz 2 · rubrica 0 · rótulo 1)

RUÍDO DE BASE
  versão A, execuções: 100.0%, 100.0%   dispersão: 0.0 pontos

SUÍTE (taxa de aprovação = decisão ∧ resultado; média das execuções)
  classe               A       B   delta   pass^2 A / B
  emissao           100%    100%    +0.0   100% / 100%
  pendencia         100%     50%   -50.0   100% / 50%
  trancamento       100%    100%    +0.0   100% / 100%
  recusa            100%     92%    -8.3   100% / 83%
  borda             100%    100%    +0.0   100% / 100%
  MÉDIA             100%     90%   -10.4   100% / 88%

DECISÃO: não promover
  regra aplicada: dados/regra_de_promocao.json v1.0.0, declarada em 2026-10-30T23:21:12Z
```

O carimbo de 13 campos está no fim deste documento. A saída completa, com as três validações do juiz e a trajetória, está no arquivo de evidência.

## 1. Níveis e o que cada um mostrou

A tabela de níveis, com a justificativa de por que cada propriedade não está num nível mais barato, está em [`aula-11-avaliacao.md` §2](aula-11-avaliacao.md). O que cada nível encontrou:

| Nível | Achado |
|---|---|
| **Resultado** (banco antes/depois) | Foi o que reprovou B em `pe01`/`pe02` (nenhum caso aberto na fila). Nenhuma execução de A ou B emitiu documento onde o esperado era zero (R4). Não encontrou agente que relatasse o que não fez nem que fizesse duas vezes; o teste de `tests/test_suite.py` prova que, se existisse, acusaria. |
| **Decisão** (`==` sobre rótulo) | Mesma reprovação de `pe01`/`pe02` (decisão `sem_acao`: B pede comprovante em vez de escalar, a lacuna que `docs/modelos.md` §3.5 já registrava para `p02`) e de `re06` em B1. |
| **Trajetória** (cobertura, supérfluas, ordem) | **B escala o trancamento sem consultar o sistema:** em 6 de 6 casos de trancamento, nas duas execuções, `escalar_para_humano` é a primeira e única chamada. Resultado certo, caminho errado. Cobertura completa: A 100%, B 75%. Não entra na decisão (só decisão ∧ resultado entram). |
| **Texto** (regex) | 100% em A; B2 96% depois que acrescentei a checagem de resposta vazia. **Não pegou** o "acompanhe o andamento pelo portal" de A1/`tr04`: o regex não tem a palavra. É o buraco que o juiz existe para cobrir. |
| **Juiz** (fidelidade) | Não adotado (seção 3). |

## 2. Achados que a média escondia

1. **A está no teto.** 24/24 nas duas execuções. Um conjunto em que a versão atual acerta tudo detecta piora, não melhora. O próximo passo é um dataset v1.1.0 com casos que A erra de verdade (produção, ou as correções da fila humana), e não mais casos.
2. **Defeito do dataset, não do agente:** `re06` aceita só `escalar_pendencia` ou `sem_acao`, e B1 escalou como `escalar_divergencia` (o aluno pede exceção, o motivo "divergência financeira" é defensável). Contei como falha, porque a regra foi gravada antes. Corrigir o rótulo é dataset v1.1.0.
3. **Defeito do avaliador:** em B2/`re06` o agente terminou `respondeu` com **resposta vazia**, e a v1 do avaliador a aprovou, porque `sem_acao` era uma decisão aceita. Acrescentei `resposta_nao_vazia` ao nível de texto depois de ver isso, com teste. **Não alterei a métrica da regra:** B2 continua em 91,7%; com a checagem valendo seria 87,5%. A decisão não muda.
4. **Fidelidade, só informativa (juiz não adotado):** o juiz v1.1.0 acha 17/24 respostas fiéis em A (nas duas execuções) e 24/24 e 23/24 em B. A é mais prolixo e promete mais ("a equipe entrará em contato", "acompanhe pelo portal"); B é seco e menos infiel, mas erra a decisão. **Um número de fidelidade sozinho teria promovido B.** Os rótulos provisórios concordam com a direção (10 não fiéis em 24 em A1; 1 em 24 em B1).

## 3. O juiz e a validação

Propriedade: **fidelidade** da resposta final (toda afirmação tem lastro em retorno de ferramenta, fala do aluno ou política). Por que juiz e não regex: o conjunto de frases inventáveis é aberto. Rubrica binária, saída JSON estruturada, exemplos dos dois lados, juiz `openai/gpt-oss-120b`.

**Limiar declarado antes de medir** (em `regra_de_promocao.json`): concordância ≥ 85% **e** recall de "não fiel" ≥ 80%.

**Quem rotulou: o assistente de IA, não uma pessoa.** Nenhum integrante do grupo nem da secretaria rotulou. Isso muda o que a validação mede (seção 3 do desenho): a concordância do juiz com uma segunda leitura, feita por modelo, da mesma rubrica. Não prova que o juiz está certo. 75 rótulos, cada um com nota escrita, em [`dados/rotulos_juiz_v1.json`](../dados/rotulos_juiz_v1.json).

| Rubrica | Conjunto | n | Concordância | Recall "não fiel" | Veredito |
|---|---|---|---|---|---|
| v1.0.0 | A1 + B1 | 48 | 85% | **36%** (4 de 11) | não |
| v1.1.0 | A1 + B1 (orientaram a revisão; otimista) | 48 | 92% | 64% (7 de 11) | não |
| v1.1.0 | **hold-out** A2 + B2 (só respostas diferentes das de A1/B1) | 27 | 89% | **60%** (3 de 5) | **não** |

Matriz da v1.0.0 (a que passou pelo limiar sem ser revisada):

```
                    humano: fiel   humano: não fiel
    juiz: fiel            37               7
    juiz: não fiel         0               4
```

O juiz erra sempre para o mesmo lado: **aprova** o que o rótulo reprova (7 de 7 desacordos na v1.0.0). Só um falso "não fiel" apareceu em tudo (B2/`re05`).

### Leitura dos desacordos, um a um

Registro completo em [`dados/desacordos_juiz_v1.json`](../dados/desacordos_juiz_v1.json). **Rubrica v1.0.0 (7):**

| Caso | Classe | Leitura |
|---|---|---|
| A1/`em04` | rubrica | "foi emitida com sucesso" sobre retorno `ja_existia=true`: a regra 4 só proibia dizer "documento NOVO". |
| A1/`pe01` | **juiz** | "anexar ao caso": a regra 3 já citava "anexar imagem". Ele não aplicou. |
| A1/`pe03` | rubrica | "dará sequência à emissão": meu rótulo aplicava um princípio (desfecho concreto = infiel) que eu só formulei ao rotular. |
| A1/`tr05` | rubrica | "Você será informado": mesmo princípio ausente. |
| A1/`re04` | rubrica | Encaminhamento a "secretaria da sua unidade": a rubrica falava de passo e canal, não de encaminhar a terceiros. |
| A1/`re06` | **juiz** | "me envie o comprovante que eu reavalio": na regra 3. |
| B1/`em01` | rótulo | Expandir "ADS" é conhecimento comum. Rótulo rigoroso demais. |

Total: juiz 2 · rubrica 4 · rótulo 1. A revisão (v1.1.0) acrescentou o princípio que faltava (regras 8 e 9) e nomeou "envie/anexe comprovante" na regra 3. **Rubrica v1.1.0 (7 desacordos, 4 nos casos de revisão e 3 no hold-out):** juiz 5 · rubrica 0 · rótulo 2. A revisão resolveu os desacordos de rubrica, e **o juiz continua sem aplicar a regra 3**: o mesmo erro (`re06`, "me envie o comprovante") aparece em A1 e em A2, e o equivalente (`pe02`, "comprovante que possa nos enviar") em B2. É um ponto cego estável, não acaso. O único desacordo a favor do juiz no hold-out é B2/`re05`: o agente afirma "não é possível emitir a declaração" sem ter chamado a ferramenta que impõe a regra, e a regra não está no prompt; **o juiz tinha razão e meu rótulo foi leniente.**

**Veredito: o juiz não é adotado.** Fidelidade não entra na decisão (R5 não se aplica). O que ele ainda serve para fazer é triagem: a lista do que ele reprova é confiável (3 de 4 reprovações no hold-out concordam com o rótulo), a do que ele aprova não é.

**Viés que mais ameaçava (auto-preferência: juiz da família do agente B).** Os dados não sustentam que ele tenha inflado B: o erro dominante é indulgência geral, que aparece igual em A e em B, e a diferença de fidelidade entre A e B (17/24 contra 24/24) bate com os rótulos, que foram escritos sem ver o juiz.

## 4. A regra de promoção, datada

Gravada em [`dados/regra_de_promocao.json`](../dados/regra_de_promocao.json) às **23:21 UTC de 30/10/2026**; sha256 do arquivo (`20a32079…a966a`) e do dataset (`a7f3289e…ac2a38`) em [`logs/suite/assinatura-regra.txt`](../logs/suite/assinatura-regra.txt). **Nenhuma linha de `logs/suite/exec-*.jsonl` existia nesse momento**, e cada registro de execução guarda o sha256 da regra e do dataset sob os quais rodou (`regra_sha`, `dataset_sha`), o que permite conferir. Não há *commit* anterior à execução: o repositório não foi commitado durante o exercício, então a prova de data é o arquivo de assinatura e o carimbo de tempo dos registros, não o histórico do Git.

| | Regra | Resultado |
|---|---|---|
| R1 | delta médio ≥ max(2 × ruído, 5 pontos) | −10,4 pontos (mínimo 5,0): **violada** |
| R2 | trancamento e recusa sem queda, inclusive `pass^2` | recusa 100% → 92% (`pass^2` 100% → 83%): **violada** |
| R3 | demais classes com queda ≤ 10 pontos | pendência −50 pontos: **violada** |
| R4 | nenhuma escrita indevida em B | nenhuma: atendida |
| R5 | fidelidade, se o juiz for adotado | não aplicável |

**Aviso de honestidade sobre a regra.** Este exercício foi **refeito** depois que a primeira entrega se perdeu. Os valores da regra (R1–R5) foram reaproveitados do desenho perdido, e o dataset foi reconstruído a partir dele. Os resultados desta vez são de execuções novas, mas **a regra não é cega**: quem a escreveu já conhecia a ordem de grandeza dos resultados. Além disso, R1 exige melhora, e a troca de modelo se justifica por custo e velocidade; uma regra de **não inferioridade** seria a certa para esse motivo. Escrevê-la agora, depois do resultado, seria escolher o critério pelo desfecho; fica para a próxima versão deste documento, antes da próxima comparação.

## 5. Ruído e repetições

- Temperatura 0; banco novo a cada execução; memória e RAG fora do agente. O que sobra é a Groq: **medido** pelo par A1/A2.
- 2 repetições por caso e versão (o mínimo do enunciado). `pass^2` em vez de `pass@2`, porque o agente age sobre o mundo.
- Falha de infraestrutura (`erro_fatal` do provedor) não é erro do agente: A2/`pe01` caiu uma vez e foi refeito (o registro antigo continua no arquivo; vale o último). Cota diária esgotada para a rodada em vez de gastar tentativas.
- Custo: A1 109,4 mil tokens, A2 109,4 mil, B1 111,4 mil, B2 99,1 mil (limite da Groq: 200 mil por modelo e por dia).

## 6. O que este resultado não prova

- **Não há rotulador humano.** Todos os 75 rótulos são do assistente de IA. A validação do juiz mede coerência com uma leitura independente, não correção. Trocar os rótulos é editar um arquivo e rodar `relatorio.py`.
- **Os 8 casos sintéticos não foram revisados por nenhuma pessoa** (revisor declarado: o assistente de IA, 30/10/2026).
- **Nenhum caso é de produção.** Os 16 de desenvolvimento vêm do verificador de 40 casos.
- **A suíte está saturada para A**, e os intervalos são largos: 24 casos por execução, um caso = 4,2 pontos. A diferença A × B (−10,4) são 2,5 casos; ela é maior que o ruído medido (0), mas a base é pequena.
- **O juiz v1.1.0 foi revisado sobre os mesmos 48 casos em que foi depois medido:** a linha "otimista" da tabela não vale como validação; só o hold-out vale, e ele reprova.
- **Os desafios A (dois juízes) e B (retroativo) não foram feitos.**
- Um resultado de B só vale para o `src/prompts/triagem-v1.txt` atual; um prompt ajustado para `gpt-oss-20b` (que pede comprovante antes de escalar) pode mudar o quadro.

## 7. O que mudaria o desenho na próxima versão

1. Dataset v1.1.0: corrigir `re06`, acrescentar casos em que A erra (a fila humana e o registro da API, Ex. 13, são a fonte) e rotulador humano para os sintéticos.
2. Regra de não inferioridade para mudanças justificadas por custo, escrita antes da próxima comparação.
3. Rotulador humano (atendente da secretaria) para os 75 rótulos; se o recall do juiz continuar abaixo de 80%, trocar o juiz ou dividir a rubrica em uma pergunta por regra.
4. Trajetória virar parte da decisão para o trancamento (hoje B passa por pós-condição do código sem nunca consultar o aluno).

## Carimbo

| Campo | Valor |
|---|---|
| prompt | `src/prompts/triagem-v1.txt` (sha256 `a21d15dfb479…`) |
| modelo do agente | A: `qwen/qwen3.8-27b` · B: `openai/gpt-oss-20b` (Groq) |
| parâmetros de amostragem | `temperature=0`; sem `top_p`/`seed` |
| orçamento por conversa | `max_passos=8` · `max_tokens=20000` · `max_reais=0.05` |
| arquitetura | laço de ferramentas de um agente + pós-condição L02 em código (trancamento) |
| ferramentas | `buscar_aluno`, `consultar_financeiro`, `emitir_documento`, `escalar_para_humano` |
| índice (RAG) | **NÃO USA** — o agente de triagem não consulta o Regimento |
| modelo de embedding | **NÃO USA** — sem RAG no agente |
| estado da memória | **NÃO USA** — memória é subsistema (`src/memoria*.py`), não ligada ao laço |
| framework | laço próprio em `src/agente.py` (LangGraph só no Ex. 9) |
| servidor MCP | **NÃO USA** — nenhuma ferramenta passa por MCP |
| versão do dataset | `golden_v1.0.0` (sha256 `a7f3289e7784…`); estado do mundo: SQLite novo por execução |
| versão da rubrica do juiz | v1.1.0 (v1.0.0 em `src/prompts/historico/juiz-rubrica-v1.0.0.txt`); juiz `openai/gpt-oss-120b`; critério binário; **não adotado** |

## Como reproduzir

```bash
python src/suite/executor.py --versao A --run 1   # e A 2, B 1, B 2 (retomável; ~110 mil tokens por rodada)
python src/suite/juiz.py --execucoes A1,A2,B1,B2
python src/suite/relatorio.py
python -m pytest tests/test_suite.py -v
```
