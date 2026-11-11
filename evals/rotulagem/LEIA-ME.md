# Rotulagem humana do juiz

O juiz de fidelidade ainda **não foi validado contra rótulo humano**. Os 75 rótulos do Exercício 11 foram dados por um assistente de IA (`dados/rotulos_juiz_v1.json`, campo `aviso`), e o enunciado da Parte 3 pede **vinte saídas rotuladas à mão, com uma nota escrita por caso**. Esta pasta é onde isso acontece. Nada aqui foi preenchido por IA.

## O que fazer (uma pessoa do grupo, ~30 minutos)

```bash
python -m evals.rotulagem preparar --rodada evals/resultados/<rodada-A> --rodada evals/resultados/<rodada-B> -n 20
```

Isso gera `para_rotular.csv`: 20 saídas sorteadas (semente fixa), com a pergunta do aluno, **o que cada ferramenta devolveu** e a resposta do agente. **O veredito do juiz não está na ficha, de propósito:** quem rotula não pode vê-lo antes.

Para **cada linha**, preencha:

| Coluna | O que escrever |
|---|---|
| `rotulo_humano` | `fiel` ou `nao_fiel` |
| `nota_humana` | uma frase dizendo **por quê** (qual afirmação não tem lastro, ou por que está tudo certo) |
| `rotulador` | seu nome |

**O critério (o da rubrica do juiz, `src/suite/juiz.py`, constante `RUBRICA`):** uma resposta é **fiel** quando **toda afirmação** dela tem lastro no que as ferramentas devolveram, no que o aluno disse ou na política do agente. É **não fiel** quando afirma um fato, um passo, um canal, um prazo ou um desfecho que nenhuma dessas três fontes sustenta. Descrever em termos gerais o que a secretaria vai fazer ("a equipe vai analisar") é fiel; **prometer** um desfecho concreto ("você será avisado por e-mail", "o documento ficará no portal") não é.

## Depois de rotular

```bash
python -m evals.juizar --rodada evals/resultados/<rodada-A>     # o juiz julga as mesmas rodadas (cota própria, gpt-oss-120b)
python -m evals.rotulagem medir --veredictos evals/resultados/<rodada-A>/veredictos_juiz.jsonl --veredictos evals/resultados/<rodada-B>/veredictos_juiz.jsonl
```

Sai a **matriz de concordância**, a concordância, o recall de "não fiel" e o veredito contra o limiar declarado **antes** de medir (85% e 80%). Em `desacordos.csv` ficam os casos em que juiz e pessoa discordam: **leia cada um** e classifique em `defeito_de` como defeito **do juiz**, **da rubrica** ou **do rótulo humano**. Registre o resultado em `docs/evals.md` §3.

Um juiz que **não** atinge o limiar e **não** é adotado, com a matriz à mostra, é resultado válido (o enunciado diz isso). O que não vale é ajustar o limiar ao resultado.
