# Exercício 8 (complementar) — A memória do case, implementada

**Grupo:** Weslley Soares de Sousa, Pedro Akira, Henrique Gomes Matos e Erick.
**Data:** 25/09/2026.
**Natureza:** exercício complementar (não avaliado isoladamente) — implementa as decisões de [`docs/memoria.md`](../docs/memoria.md), que é o documento avaliado via Parte 2 (§4).

**Questão do enunciado — o que o sistema não guarda, e por quê:** ver `docs/memoria.md` §1.4. Resumo: nada de dado financeiro real fora do campo estruturado, nenhum RA solto em texto sem metadado, e nenhum ruído de execução (latência, contagem de passos) — o checkpoint (`logs/*.json`, já produzido pelo Ex.6) já cobre isso, e duplicar na memória não ajuda em nada.

---

## 1. A fronteira com o checkpoint

O agente de triagem (Ex.6) já produz o que a Aula 08 chama de checkpoint — `src/agente.py::salvar_log()`, um JSON por execução em `logs/`. Faltava o outro lado: memória entre execuções.

```
FRONTEIRA
  arquivo morto (1 execução serializada) ...... 70 tokens
  memória recuperada por relevância ........... 25 tokens
```

O checkpoint de uma única execução (`consultar_financeiro` + resultado) já pesa quase 3× mais que os dois episódios relevantes recuperados por similaridade — e isso com só 1 execução serializada. Com 10, a proporção seria muito mais extrema (nota 02 desta aula, Exemplo 1, mede exatamente essa razão sobre um caso maior).

## 2. As três memórias, nas estruturas certas

```
AS TRÊS MEMÓRIAS
  episódica  2 registros   consulta: 448.4 ms
  semântica  2 chaves      consulta: 0.00 ms
  procedural 42 tokens no system prompt
```

A diferença de latência (448 ms × 0,00 ms) é o argumento em número, não em opinião, para nunca guardar fato de chave-valor num índice vetorial: a consulta episódica paga o custo de gerar o embedding da pergunta a cada chamada; a semântica é um `dict.get`.

## 3. A política de escrita

```
POLÍTICA DE ESCRITA: código extrai por regra, ao final da execução (nota 03 §1.2)
  volume por execução: ~2 registros episódicos, ~1 fato semântico, 0-1 regra procedural
  o que NÃO entra: RA em texto livre sem o campo `ra` de metadado; latência e contagem de
  passos da execução; tentativa de ferramenta já corrigida no mesmo turno; qualquer dado
  do sistema financeiro real (é sintético, mas a regra vale para quando deixar de ser)
```

Justificativa completa em `docs/memoria.md` §1.4.

## 4. A escrita é escrita (idempotência)

```
IDEMPOTÊNCIA
  1ª gravação -> 20230198:ultimo_canal_contato  ja_existia=False
  2ª gravação -> 20230198:ultimo_canal_contato  ja_existia=True
```

Chave derivada de `entidade:chave`, não de `uuid4()`. A segunda chamada, com o mesmo conteúdo, não cria registro novo.

## 5. A contradição

```
CONTRADIÇÃO
  fato [2026-09-20]: RA 20230198 quitou as mensalidades em aberto; pendência financeira res...   similaridade 0.6927
  fato [2026-08-01]: RA 20230198 tem 2 mensalidades em aberto; pedido de segunda via escala...   similaridade 0.6715
  desempate por carimbo: [2026-09-20] RA 20230198 quitou as mensalidades em aberto; pendência fina...
  descartado (registrado, não apagado): [2026-08-01]
```

Margem de similaridade entre os dois fatos: **0,021** — pequena o bastante para não ser garantia de nada. Neste caso o vetor favoreceu o fato certo por coincidência (a redação de "quitou" ficou, por acaso, mais próxima da pergunta que "tem 2 mensalidades"); o desempate por carimbo de tempo é o que **garante** a resposta certa independentemente de qual lado o vetor favorecer — é a diferença entre sorte e projeto, e é exatamente o ponto que `docs/memoria.md` §2.1 registra com essa ressalva.

## 6. Não reprodutibilidade

```
NÃO REPRODUTIBILIDADE
  execução com memória vazia .... "**Resposta ao pedido de segunda via do histórico**

1. **Verificar situação financeira**
   - Acesse o sistema de pagamentos (ou a planilha de controle de mensalidades) e confirm[e...]"

  execução com memória cheia .... "Sim.
O RA 20230198 já está registrado como **quitado** (última atualização em 20 de setembro de
2026) e não há pendências financeiras. Assim, podemos emitir a segunda via do hist[órico...]"

  bloco de memória usado: 127 tokens, 2 episódio(s)
```

Mesma pergunta, mesmo modelo (`openai/gpt-oss-20b`), mesma temperatura (0). A diferença inteira é a memória: sem ela, o agente propõe um procedimento de verificação; com ela, decide direto, citando a data do fato. É consequência de projeto (Decisão 1 de `docs/memoria.md`), não falha — e é exatamente o que torna este agente, a partir de agora, não reprodutível sem fixar o estado da memória junto com o resto do carimbo (Aula 11).

## 7. O esquecimento seletivo

```
ESQUECIMENTO
  antes da remoção: 6 estrutura(s) com vestígio de 20230198: ['episodica', 'episodica', 'semantica', 'semantica', 'checkpoint', 'log_de_exercicio_anterior']
  "Apaguei da episódica e da semântica." É o ponto em que a maioria para.
  A PROVA — verificar, não afirmar
  FALHOU — vestígio(s) fora das memórias: [('checkpoint', 'checkpoints/exec-demo-8f21.json'), ('log_de_exercicio_anterior', 'logs/02-divergencia-9aee9313.json')]
  A CORREÇÃO — removidos os checkpoints em checkpoints/ (efêmeros)
  AVISO — [('log_de_exercicio_anterior', 'logs/02-divergencia-9aee9313.json')] é um LOG de exercício anterior (entrega já commitada, ver §2.3 de exercicios/aula-08-memoria-do-case.md); não apagado por este demo de propósito.
```

A remoção das duas memórias (episódica, semântica) estava correta sobre o que fez, e incompleta sobre o resultado — exatamente a lição da nota 04, Exemplo 2. O checkpoint de demonstração (`checkpoints/exec-demo-8f21.json`, criado só para este exercício, não uma entrega real) foi corrigido na segunda passada. **O log `logs/02-divergencia-9aee9313.json` foi deixado de propósito**, porque é uma entrega já avaliada do Exercício 6, e apagá-lo para satisfazer uma remoção de titular fictício deste exercício destruiria evidência de outro trabalho — a tensão real entre LGPD e retenção de evidência de avaliação é registrada como risco aberto em `docs/memoria.md` §2.3, não resolvida aqui.

## 8. O que fica para a Parte 2

- **Fechar o laço de confirmação assíncrona** (`docs/memoria.md` §1.1): o agente de triagem hoje encerra com `HUMANO` sem retomar quando a coordenação decide.
- **Resolver a tensão remoção-vs-auditoria** de dado sintético em log de exercício avaliado — provavelmente com uma rotina de expurgo por prazo, separada do esquecimento sob demanda.
- **Wire real**: as três memórias existem como subsistema independente (`src/memoria*.py`), ainda não plugadas no laço de conversa de `src/agente.py`. Isso é decisão para a Parte 2, não um esquecimento desta entrega — o Exercício 6 já está validado (35/40) e plugar memória nele antes da Parte 2 arriscaria essa validação sem necessidade.

## Carimbo

Estado da memória: 2 episódios, 2 chaves semânticas, 1 regra procedural aprovada, sobre o RA sintético 20230198. Modelo de geração: `openai/gpt-oss-20b` (mesmo do Ex.7). Embedding: `paraphrase-multilingual-MiniLM-L12-v2` (local, mesmo do Ex.7). Código: `src/memoria.py`, `src/memoria_episodica.py`, `src/memoria_semantica.py`, `src/memoria_procedural.py`, `src/memoria_demo.py`.
