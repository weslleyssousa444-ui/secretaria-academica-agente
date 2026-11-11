# Entrada e saída do sistema

O contrato do sistema com quem o usa, e por isso o primeiro documento da Parte 2: tudo o que vem depois existe para cumpri-lo. O código que o impõe está em [`src/triagem/saida.py`](../src/triagem/saida.py) (o objeto), [`src/triagem/validacao.py`](../src/triagem/validacao.py) (a conferência do texto) e [`src/triagem/sistema.py`](../src/triagem/sistema.py) (o ponto de entrada).

## 1. A entrada é texto

O sistema recebe **uma mensagem de texto livre, em português**, de até 2.000 caracteres (`Sistema.conversar`, `MAX_ENTRADA`; a API recusa acima disso com 422). Não há formulário, nem JSON montado por outro programa, nem arquivo no lugar da pergunta. É o texto que obriga o sistema a descobrir o que a pessoa quer: pedir o RA que faltou, estranhar um RA que não existe, perceber que "cancelar a matrícula" não é nenhum dos três pedidos do catálogo.

| O que entra | Onde |
|---|---|
| **texto livre** | **a entrada do sistema**: `POST /mensagens` ou `Sistema.conversar(thread_id, texto, ra_autenticado)` |
| consulta ao cadastro e ao financeiro | **por ferramenta** (`buscar_aluno`, `consultar_financeiro`), decidida pelo modelo |
| artigos do Regimento | **por ferramenta** (`consultar_regimento`), decidida pelo modelo |

**O que acompanha o texto sem ser digitado por ninguém:**

| Campo | Quem define | Para que serve |
|---|---|---|
| `thread_id` (`conversa_id` na API) | o sistema, na primeira mensagem (uuid de 128 bits) | endereça o checkpoint: mesma chave, mesma conversa (`docs/memoria.md` §5.1) |
| `ra_autenticado` | **o portal**, pelo cabeçalho `X-Aluno-RA`, e só com `TRIAGEM_CONFIA_NO_PORTAL=1` | abre a memória de longo prazo do aluno. Sem ele, não há memória. **Não** é o RA que a pessoa digita no chat: este é só texto, e o sistema não o usa para abrir histórico de ninguém |

## 2. A saída é um objeto validado

A saída **não é texto solto do modelo**. É um objeto Pydantic, montado pelo código a partir da trajetória do turno; o modelo escreve só o `resultado` (a resposta ao aluno).

| Campo | O que é | De onde vem |
|---|---|---|
| `resultado` | a resposta ao aluno (não vazia) | o modelo, depois da conferência de `validacao.py`; a marcação `[SUFICIENTE: ...]` é removida |
| `decisao` | `emitir_declaracao`, `emitir_segunda_via`, `escalar_trancamento`, `escalar_pendencia`, `escalar_divergencia`, `escalar_ra_nao_encontrado`, `escalar_outro`, `responder_regimento` ou `sem_acao` | o **código**, lendo a última ação bem-sucedida da trajetória (`saida.decisao_da_trajetoria`). Os mesmos rótulos do verificador da Parte 1 e do golden dataset |
| **`fonte`** | o que sustenta o resultado, conferível: `{tipo: "ferramenta", referencia: "emitir_documento:DOC-1002"}` ou `{tipo: "regimento", referencia: "Art. 6º"}` | o **código**: só entra ferramenta que de fato respondeu sem erro, e só entra artigo que a ferramenta devolveu **e** que o texto cita |
| **`suficiencia`** | `{suficiente, motivo}`: se o sistema teve base para responder | o código, a partir da decisão; para dúvida do Regimento, também a declaração do agente (ver §4) |
| `protocolo` | `DOC-xxxx` ou `CASO-xxxx` do turno, se houve | a ferramenta que gravou |
| `aguardando_humano` | o grafo parou esperando a coordenação (trancamento) | o código |
| `termino` | `respondeu`, `orcamento_esgotado`, `laco_detectado` ou `erro_fatal` | o código (taxonomia de término, `docs/arquitetura.md` §2) |

**A recusa faz parte do contrato.** `suficiencia.suficiente = false` com o motivo é uma saída **válida**, e é o que o sistema devolve quando falta o RA, quando o Regimento não responde ou quando o pedido está fora do escopo. Uma saída sem `fonte` e sem `resultado` não existe: `SaidaTriagem` recusa `resultado` vazio e `decisao` fora da lista (`tests/test_triagem.py::test_resultado_vazio_nao_e_saida_valida`).

**Na API** (`POST /mensagens`), a resposta é um recorte do objeto: `conversa_id`, `resposta` (= `resultado`), `decisao`, `protocolo`, `aguardando_coordenacao`, `termino`, `motivo`, `encerrada`. Nunca traz o retorno cru das ferramentas, que contém cadastro e financeiro do aluno (`tests/test_api.py::test_resposta_nao_expoe_resultado_de_ferramenta`).

## 3. Os exemplos

Todos **copiados de execuções reais** contra o modelo `qwen/qwen3.8-27b`, pelo sistema em grafo, com o log em `logs/parte2/`. O `commit` de cada log é o da execução; os casos 7 e 8 foram acrescentados ao `src/demo_grafo.py` depois da primeira rodada, sem alterar o sistema. Para refazer: `python src/demo_grafo.py`.

### 3.1 O caminho feliz

**Origem:** [`logs/parte2/01-caso-simples.json`](../logs/parte2/01-caso-simples.json) · commit `cbb82d6` · executado em 2026-11-11T14:40:32Z · modelo `qwen/qwen3.8-27b` · prompt `src/prompts/triagem-v2.txt` (sha256 `6df71c6cfcaddca0`) · turno 2 de 2.

**Entrada exata:**

```text
20231045
```

**Saída completa** (o objeto inteiro, com os campos vazios):

```json
{
  "resultado": "Pronto! A declaração de matrícula foi emitida com sucesso.\n\n**Protocolo:** DOC-1002\n\n**Declaração de Matrícula**\n- Aluno: Weslley Sousa\n- RA: 20231045\n- Curso: ADS\n- Situação: matrícula ativa\n- Data de emissão: 2026-11-11",
  "decisao": "emitir_declaracao",
  "fonte": [
    {
      "tipo": "ferramenta",
      "referencia": "buscar_aluno:20231045"
    },
    {
      "tipo": "ferramenta",
      "referencia": "emitir_documento:DOC-1002"
    }
  ],
  "suficiencia": {
    "suficiente": true,
    "motivo": "decisão tomada com o retorno de uma ferramenta"
  },
  "protocolo": "DOC-1002",
  "aguardando_humano": false,
  "termino": "respondeu"
}
```

**O que ler aqui:** `decisao: emitir_declaracao`, `suficiente: true`, e uma `fonte` que aponta para as duas ferramentas que de fato responderam (`buscar_aluno:20231045` e `emitir_documento:DOC-1002`). O protocolo do texto ao aluno é o mesmo de `protocolo`: o validador conferiu isso antes de a resposta sair.

### 3.2 A recusa (o Regimento não responde)

**Origem:** [`logs/parte2/05-fora-do-corpus.json`](../logs/parte2/05-fora-do-corpus.json) · commit `cbb82d6` · executado em 2026-11-11T14:44:55Z · modelo `qwen/qwen3.8-27b` · prompt `src/prompts/triagem-v2.txt` (sha256 `6df71c6cfcaddca0`) · turno 1 de 1.

**Entrada exata:**

```text
Quanto custa emitir a segunda via do histórico escolar?
```

**Saída completa** (o objeto inteiro, com os campos vazios):

```json
{
  "resultado": "O Regimento Acadêmico não informa valor de taxa para a segunda via do histórico escolar. O que ele trata é a condição de emissão:\n\n- **Art. 4º**: a segunda via do histórico exige quitação financeira total do aluno, apurada na data do pedido. Qualquer mensalidade em aberto impede a emissão até a regularização ou a confirmação do pagamento pela secretaria.\n\nOu seja, o Regimento não trata de custo/taxa — apenas da exigência de estar em dia com as mensalidades. Se você quiser, posso encaminhar o caso à secretaria para que ela informe se há cobrança de taxa.",
  "decisao": "sem_acao",
  "fonte": [],
  "suficiencia": {
    "suficiente": false,
    "motivo": "o agente declarou que o Regimento não responde à pergunta"
  },
  "protocolo": null,
  "aguardando_humano": false,
  "termino": "respondeu"
}
```

**O que ler aqui:** `decisao: sem_acao`, `suficiente: false` e **`fonte: []`**. O agente consultou o Regimento, achou o Art. 4º (a busca textual devolve artigo para quase qualquer pergunta que tenha um termo em comum), mas declarou que ele não responde ao preço da segunda via. O código **não** lista o Art. 4º como fonte: citar um artigo para dizer que ele não vale não é usá-lo como base. A resposta ao aluno é útil, e não uma recusa seca: diz o que o Regimento trata e oferece encaminhar. (Na primeira execução deste caso, antes de o agente declarar a suficiência, o objeto saiu com `suficiente: true` e fonte `Art. 4º`: era um erro do contrato, corrigido em `docs/rag.md` §4.)

## 4. A entrada que não dá para atender

Três situações. Responder a qualquer delas como se a entrada estivesse completa produz uma saída que parece boa e não é.

| Situação | O que o sistema faz | Exemplo real |
|---|---|---|
| entrada **incompleta** | pergunta o que falta; `decisao: sem_acao`, `suficiente: false` | §4.1 |
| entrada **ambígua** | desambigua perguntando, ou **escolhe e declara a escolha** | §4.2 |
| entrada **fora do escopo** | recusa e diz o que faz | §4.3 |

### 4.1 Incompleta (falta o RA)

**Origem:** [`logs/parte2/01-caso-simples.json`](../logs/parte2/01-caso-simples.json) · commit `cbb82d6` · executado em 2026-11-11T14:40:32Z · modelo `qwen/qwen3.8-27b` · prompt `src/prompts/triagem-v2.txt` (sha256 `6df71c6cfcaddca0`) · turno 1 de 2.

**Entrada exata:**

```text
Oi, preciso de uma declaração de matrícula pra levar no estágio.
```

**Saída completa** (o objeto inteiro, com os campos vazios):

```json
{
  "resultado": "Claro! Para eu emitir a declaração de matrícula, preciso do seu RA (registro acadêmico). Pode me passar?",
  "decisao": "sem_acao",
  "fonte": [],
  "suficiencia": {
    "suficiente": false,
    "motivo": "nenhuma ação tomada: falta informação do aluno, ou fora do escopo"
  },
  "protocolo": null,
  "aguardando_humano": false,
  "termino": "respondeu"
}
```

**O que ler aqui:** nenhuma ferramenta foi chamada (`fonte: []`), nenhum documento foi emitido e o sistema pediu exatamente o que falta. Quem decidiu pedir o RA foi o modelo, pela regra 2 do prompt; o que impede o contrário (emitir sem RA) é a ferramenta, que recusa um RA que não existe.

### 4.2 Ambígua ("cancelar" não é um pedido do catálogo)

**Origem:** [`logs/parte2/07-entrada-ambigua.json`](../logs/parte2/07-entrada-ambigua.json) · commit `cbb82d6` · executado em 2026-11-11T14:46:43Z · modelo `qwen/qwen3.8-27b` · prompt `src/prompts/triagem-v2.txt` (sha256 `6df71c6cfcaddca0`) · turno 1 de 1.

**Entrada exata:**

```text
Quero cancelar minha matrícula, como faço?
```

**Saída completa** (o objeto inteiro, com os campos vazios):

```json
{
  "resultado": "Entendo que você deseja cancelar sua matrícula. Esse pedido é tratado como **trancamento de matrícula** e, por regra, precisa ser analisado pela secretaria — não posso concluí-lo diretamente por aqui.\n\nPara eu encaminhar seu caso corretamente, preciso de uma informação:\n\n**Qual é o seu RA (registro acadêmico)?**\n\nAssim que você me informar, eu verifico seus dados e encaminho o pedido à secretaria para análise.",
  "decisao": "sem_acao",
  "fonte": [],
  "suficiencia": {
    "suficiente": false,
    "motivo": "nenhuma ação tomada: falta informação do aluno, ou fora do escopo"
  },
  "protocolo": null,
  "aguardando_humano": false,
  "termino": "respondeu"
}
```

**O que ler aqui:** o agente **escolheu e declarou a escolha**: tratou "cancelar" como trancamento e disse isso ("esse pedido é tratado como trancamento de matrícula"), em vez de agir em silêncio. Ainda não chamou ferramenta, porque falta o RA; quando vier, a pós-condição de trancamento do grafo (`garantir_trancamento`) só age se o aluno tiver dito "trancar" ou "trancamento", então a palavra "cancelar" depende do modelo escalar. É uma lacuna conhecida do detector (`docs/grafo.md` §5).

### 4.3 Fora do escopo (diploma impresso)

**Origem:** [`logs/parte2/08-fora-do-escopo.json`](../logs/parte2/08-fora-do-escopo.json) · commit `cbb82d6` · executado em 2026-11-11T14:47:00Z · modelo `qwen/qwen3.8-27b` · prompt `src/prompts/triagem-v2.txt` (sha256 `6df71c6cfcaddca0`) · turno 1 de 1.

**Entrada exata:**

```text
Quero meu diploma impresso. Meu RA é 20220087.
```

**Saída completa** (o objeto inteiro, com os campos vazios):

```json
{
  "resultado": "Entendo que você gostaria de um diploma impresso, mas esse não é um dos serviços que eu posso atender aqui. Eu atendo apenas:\n\n- Declaração de matrícula\n- Segunda via de histórico escolar\n- Trancamento de matrícula\n\nSe a sua necessidade for a **segunda via do histórico escolar**, posso te ajudar com isso — é só confirmar. Caso contrário, o pedido de diploma precisará ser encaminhado à secretaria acadêmica diretamente.\n\nComo posso te ajudar?",
  "decisao": "sem_acao",
  "fonte": [],
  "suficiencia": {
    "suficiente": false,
    "motivo": "nenhuma ação tomada: falta informação do aluno, ou fora do escopo"
  },
  "protocolo": null,
  "aguardando_humano": false,
  "termino": "respondeu"
}
```

**O que ler aqui:** nenhuma ferramenta foi chamada, nada foi emitido, e o sistema listou os três pedidos que atende e ofereceu encaminhar o resto à secretaria. O RA que o aluno informou não foi usado: um pedido fora do catálogo não consulta cadastro.

## 5. A suficiência e a marcação do agente

Para uma dúvida do Regimento, o código **não consegue** saber sozinho se os artigos devolvidos respondem à pergunta: a busca textual não tem piso de relevância e devolve artigo de ruído (`docs/rag.md` §4). Por isso o prompt (`src/prompts/triagem-v2.txt`) pede ao agente que termine a resposta com `[SUFICIENTE: sim]` ou `[SUFICIENTE: não]`, e o código:

1. **exige** a marcação sempre que a ferramenta devolveu artigo (sem ela, o validador devolve a resposta ao agente uma vez; reprovando de novo, a resposta sai de um molde);
2. **remove** a marcação do texto antes de mostrá-lo ao aluno;
3. **confere** o resto: o artigo citado precisa ter sido devolvido, e a `fonte` só lista artigo citado quando o agente declarou `sim`.

`suficiente` só é `true` para `responder_regimento` quando as duas condições valem (declaração `sim` **e** artigo devolvido citado). O agente poderia declarar `sim` sem base: a conferência do artigo é o que impede isso, e a avaliação da suíte (Parte 3) mede o quanto o agente declara certo.
