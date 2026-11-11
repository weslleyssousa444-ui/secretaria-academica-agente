# Human-in-the-loop: a coordenação decide o trancamento

O agente **nunca decide um trancamento**: a regra do case (Regimento, Art. 6º) o reserva à coordenação, "mediante confirmação humana explícita". O agente abre o caso na fila e o grafo **para** num `interrupt()`, esperando a coordenação. O aluno já recebeu o protocolo e o prazo; a decisão chega depois, por outro canal, possivelmente em outro dia e em outro processo.

Código: [`src/triagem/humano.py`](../src/triagem/humano.py) (a tela, o contrato da resposta, a gravação idempotente), os nós `registrar_espera`, `aprovacao_coordenacao` e `registrar_decisao` em [`src/triagem/nos.py`](../src/triagem/nos.py), os endpoints `/coordenacao/*` em [`src/api.py`](../src/api.py) e o terminal em [`src/coordenacao.py`](../src/coordenacao.py).

## 1. Onde o grafo para, e por qual critério

**Um ponto de parada**: o nó `aprovacao_coordenacao`, depois de `montar_saida` (o aluno já tem a resposta) e `escrever_memoria`, e antes de `registrar_decisao`. Está marcado no desenho de [`docs/arquitetura.md`](arquitetura.md).

| Critério | Vale no case? | Por quê |
|---|---|---|
| **ação irreversível ou reservada a uma pessoa** | **sim, é o critério do ponto de parada** | o trancamento altera a situação acadêmica do aluno, e a regra do case o reserva à coordenação |
| custo acima de um teto | não | o sistema não move dinheiro nem tem ação com custo variável |
| confiança baixa | **não implementado** | o agente não mede confiança; a insuficiência vira recusa (`suficiencia`, `docs/io.md`), e não pausa |

**A ação mais perigosa que o sistema faz sem pausar** é `emitir_documento` (declaração ou segunda via). Ela **não** pausa porque é reemitível e porque as regras que a protegem estão em código, dentro da ferramenta (matrícula ativa para declaração, zero pendência para segunda via, tipo no catálogo), e não no prompt (`docs/model-card.md`, A4 a A7). O que protege o aluno de um documento errado é a guarda, e não uma pessoa.

## 2. O que a pessoa vê, e o que ela devolve

A tela é montada pelo **código** a partir do banco (`humano.tela_da_aprovacao`), não pelo modelo: o motivo que o modelo escreveu aparece como dado do caso (`motivo_registrado`), mas **a ação, a consequência e as respostas aceitas são fixas**. Uma pergunta do tipo "confirma?" sem dizer o que acontece transfere a responsabilidade sem transferir a informação.

Gerada pelo próprio código, sobre um caso de trancamento (RA sintético):

```json
{
  "acao": "registrar a decisão da coordenação sobre o trancamento",
  "protocolo": "CASO-3001",
  "aluno": {
    "ra": "20229012",
    "nome": "Bruno Castro",
    "curso": "Direito",
    "situacao_matricula": "ativa"
  },
  "motivo_registrado": "trancamento",
  "prazo_ate": "2026-11-13T14:52:00Z",
  "consequencia": "Aprovar ou rejeitar grava a decisão no caso. O agente não altera a matrícula: a efetivação fica fora do sistema. Sem resposta em 48 h, o caso vence e volta à fila da secretaria com prioridade.",
  "respostas_aceitas": [
    "aprovar",
    "rejeitar",
    "aprovar_editando"
  ],
  "campos_editaveis": [
    "semestre_efetivo",
    "observacao"
  ]
}
```

**As respostas aceitas** (`DecisaoHumana`, validada **antes** de retomar o grafo, que nunca recebe uma resposta fora do contrato):

| Resposta | O que grava |
|---|---|
| `aprovar` | `casos_pendentes.status = aprovado` |
| `rejeitar` | `status = rejeitado` |
| **`aprovar_editando`** | `aprovado`, **e** o que a pessoa corrigiu (`semestre_efetivo`, `observacao`) em `decisoes_humanas.edicao`. É o que separa aprovação de carimbo |
| `expirar` | só o sistema a usa (§4); `status = vencido` |

Recusadas com 422 na API (e `ValueError` no código): campo editável fora da lista, `aprovar_editando` sem nenhum campo, edição em `aprovar` ou `rejeitar` (`tests/test_triagem.py::test_decisao_fora_do_contrato_e_recusada_antes_de_retomar`, `tests/test_api.py::test_decisao_fora_do_contrato_422_e_caso_desconhecido_404`).

**O que a decisão faz:** grava no caso. **Não altera a matrícula**: a efetivação do trancamento fica fora do sistema, como o case a define (`docs/case.md` §2.3). É declarado na tela (`consequencia`). Ligar a decisão ao sistema acadêmico seria uma ferramenta de escrita irreversível que o agente deliberadamente não tem (A3).

## 3. A implementação, e por que ela depende do checkpoint

A pausa é um `interrupt()` dentro do nó `aprovacao_coordenacao`; a retomada é uma nova invocação com `Command(resume=...)`, e o valor devolvido vira o retorno do `interrupt`. Isso só funciona porque existe um **checkpointer em arquivo** (`SqliteSaver`, `TRIAGEM_CHECKPOINT`): a pausa é um checkpoint gravado, endereçado por `thread_id`. Em memória, a aprovação pendente morreria com o processo; em arquivo, `tests/test_triagem.py::test_pausa_sobrevive_a_reiniciar_o_processo` abre **outro** `Sistema` no mesmo arquivo e retoma.

**A retomada executa o nó de novo, desde o começo.** Por isso o nó `aprovacao_coordenacao` só **lê** antes do `interrupt` (a tela). O que tem efeito colateral ficou em nós separados e **idempotentes**: `registrar_espera` (antes) e `registrar_decisao` (depois).

## 4. O que acontece se ninguém responder

**Prazo: 48 horas** (`PRAZO_HORAS`), o mesmo que o agente promete ao aluno. Gravado ao esperar (`aprovacoes.prazo_ate`), idempotente (esperar duas vezes mantém o prazo da primeira).

Passado o prazo, `Sistema.expirar_vencidos()` (também `POST /coordenacao/expirar` e `python src/coordenacao.py expirar`) retoma o grafo com `expirar`, e o caso **vence**: `casos_pendentes.status = vencido`, `aprovacoes.estado = vencido`. **O caminho padrão declarado:** o caso volta à fila da secretaria, marcado como vencido, em vez de seguir adiante sozinho em silêncio. Coberto por `test_ninguem_responde_o_caso_vence_e_volta_a_fila`.

**Limites, declarados:**

- **Não há agendador.** Alguém (um `cron`, a própria coordenação) precisa chamar `expirar`. Sem isso, nada vence.
- **Ninguém é notificado** do vencimento: o sistema não tem canal de saída (o aluno não recebe e-mail, e a coordenação não recebe alerta). O vencimento só existe como estado no banco.

## 5. Aprovar duas vezes

A ação **não acontece duas vezes** se a aprovação chegar repetida: a chave da decisão é derivada do caso (`<protocolo>:decisao`, `PRIMARY KEY`), e **a primeira decisão vale**. Demonstrado contra o modelo real, no caso 6 ([`logs/parte2/06-aprovacao-humana.json`](../logs/parte2/06-aprovacao-humana.json), commit `cbb82d6`, 2026-11-11T14:45:43Z):

```text
1ª aprovação (aprovar_editando, semestre_efetivo=2027.1): {"protocolo": "CASO-3001", "ja_decidido": false, "decisao": "aprovado", "conflito": false}
2ª aprovação (a mesma):                                  {"protocolo": "CASO-3001", "ja_decidido": true, "decisao": "aprovado", "conflito": false}
linhas em decisoes_humanas depois das duas:              1
decisão gravada:                                         {"chave": "CASO-3001:decisao", "protocolo": "CASO-3001", "decisao": "aprovado", "edicao": "{\"semestre_efetivo\": \"2027.1\"}", "decidido_por": "coord-demo", "decidido_em": "2026-11-11T14:45:43Z"}
```

A segunda chamada **não retoma o grafo** (ele já terminou) e devolve a decisão já gravada, com `ja_decidido: true`. Se chegar uma decisão **diferente** da gravada (`rejeitar` depois de `aprovar`), ela **não sobrescreve** e volta com `conflito: true` (`test_decisao_conflitante_nao_sobrescreve`). E se o nó rodar de novo por uma falha entre a escrita e o checkpoint, a gravação sozinha também é idempotente (`test_registrar_decisao_repetido_devolve_a_gravada`).

## 6. Limites deste desenho

- **A coordenação se identifica por um token compartilhado** (`COORDENACAO_TOKEN`), e o campo `por` é texto livre. Não há identidade individual: quem decidiu é o que a pessoa **disse** ser. Sem o token configurado, o endpoint fica **fechado** (503), e não aberto (`test_coordenacao_sem_token_configurado_fica_fechada`).
- **O aluno não é avisado da decisão.** Quando ele voltar à conversa, a resposta de "aguardando" já não vale, e o sistema não consulta `decisoes_humanas` para informá-lo. É a próxima melhoria mais óbvia, e depende de um canal de saída.
- **Uma pessoa por vez.** O endpoint usa a trava global do processo (`docs/seguranca.md`, ASI08).
