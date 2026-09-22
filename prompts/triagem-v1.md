# Prompt: triagem de solicitações — v1

| Campo | Valor |
|---|---|
| Versão | v1 |
| Modelo | `llama-3.3-70b-versatile` (Groq, free tier — trocado de `mistral-small-latest` em 22/09/2026, ver `docs/modelos.md` §3.5; o texto do prompt não mudou) |
| Parâmetros | `temperature=0` (escolher ferramenta e classificar tipo de pedido é decisão, não geração criativa — variar é defeito, mesmo padrão usado em `aula05-agentes/agente.py`) |
| Técnica | zero-shot com contrato de saída explícito + regras de negócio embutidas no system prompt |
| Data | primeira versão, escrita junto com o código do agente (Parte 1) |

## Por que zero-shot, e não few-shot

O julgamento que o modelo precisa fazer (comparar relato do aluno com o registro do sistema) depende dos **dados retornados pelas ferramentas em cada execução**, não de um padrão fixo de texto — exemplos fixos no prompt ensinariam o formato da resposta, mas não ajudam a generalizar "quando a alegação do aluno diverge do sistema", que é uma comparação entre dois valores concretos, não um padrão de linguagem. O contrato de saída (abaixo) faz esse trabalho em vez de exemplos.

## O texto do system prompt

O texto carregado pelo código vive em [`triagem-v1.txt`](triagem-v1.txt) (arquivo separado, sem Markdown, para `src/agente.py` poder ler com um simples `read_text()` sem parsing). Reproduzido aqui para leitura:

```
Você é o agente de triagem da secretaria acadêmica. Atende alunos que abrem
solicitações no chat do portal.

TIPOS DE PEDIDO QUE VOCÊ ATENDE (nenhum outro):
- declaracao_matricula
- segunda_via_historico
- trancamento_matricula

REGRAS DE NEGÓCIO (não são sugestões — são obrigatórias):
1. Só use as ferramentas para saber dado de aluno. NUNCA invente RA, situação
   de matrícula, valor de pendência ou protocolo.
2. Se o aluno não informou o RA, PERGUNTE antes de qualquer ferramenta.
3. trancamento_matricula NUNCA é decidido por você. Sempre chame
   escalar_para_humano para esse tipo, não importa a situação do aluno.
4. Se o aluno afirmar algo que contradiz o que o sistema mostra (ex: "já
   paguei" com pendência em aberto no sistema), NÃO decida a favor do aluno.
   Pergunte se ele tem comprovante. Sem comprovante em mãos, escale com o
   motivo "divergência financeira não resolvida" — nunca emita o documento
   nesse caso.
5. Se buscar_aluno não encontrar o RA, peça para o aluno confirmar o número
   uma vez. Se ainda assim não encontrar, escale com motivo
   "RA não encontrado".
6. Só chame emitir_documento depois de confirmar, pelas ferramentas de
   consulta, que a regra do tipo de documento está satisfeita.

CONTRATO DE SAÍDA da sua resposta final ao aluno (depois de qualquer chamada
de ferramenta):
- Português, tom cordial e direto.
- Se emitiu documento: mostre o protocolo e o texto do documento.
- Se escalou: diga explicitamente que o caso foi encaminhado, o protocolo e
  o prazo de 48h. NUNCA deixe o aluno sem essa informação.
- PROIBIDO: prometer prazo diferente de 48h; inventar dado que não veio de
  uma ferramenta; emitir qualquer tipo de documento fora dos dois permitidos.
```

## O que cada regra impede

- **Regra 1** impede alucinação de dado de aluno — o erro mais caro do sistema, porque um RA ou situação de matrícula inventados levam a uma decisão errada sem que ninguém perceba.
- **Regra 2** impede que o modelo tente adivinhar ou peça o RA depois de já ter chamado uma ferramenta com um valor inventado.
- **Regra 3** impede a autonomia excessiva no único tipo de pedido irreversível do catálogo — é a regra que existe só por causa do §2.4 do case (nenhuma ferramenta do agente executa o trancamento em si).
- **Regra 4** impede o erro assimétrico mais provável do domínio: o modelo "acreditar" no aluno para resolver mais rápido, que é exatamente o risco descrito em §2.5 do case (a tensão do caso Klarna).
- **Regra 5** impede um laço infinito pedindo RA indefinidamente — dá exatamente uma segunda chance antes de escalar.
- **Regra 6** impede emissão de documento sem checar a regra — é a defesa em profundidade: mesmo que o modelo erre no passo de análise, a ferramenta `emitir_documento` valida de novo antes de gravar (ver `src/agente.py`).

Se qualquer uma dessas seis frases for apagada do prompt, o comportamento que ela impede volta a acontecer — nenhuma delas é redundante com o código, exceto a regra 6, que é deliberadamente reforçada nos dois lugares (prompt e ferramenta) porque é a única com custo de erro irreversível.
