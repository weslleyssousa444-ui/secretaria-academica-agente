# Multimídia (opcional da Parte 3, §5.3)

Feito em 13/11/2026.

## 1. A entrada: voz (`web/index.html`)

O site ganhou um botão de microfone ao lado do "Enviar". O aluno fala o pedido, o texto reconhecido aparece na caixa e **não é enviado sozinho**: ele confere, corrige se precisar, e envia. Para o agente, a mensagem é texto como qualquer outra, então nenhum controle muda.

- Usa o reconhecimento de fala **do próprio navegador** (Web Speech API, `pt-BR`): nenhum modelo novo, nenhuma cota e nenhuma mudança na lista de modelos aprovados.
- O botão só aparece se o navegador oferecer o recurso (Chrome e Edge oferecem; o Firefox não).
- **Risco registrado** (`docs/seguranca.md` §8): no Chrome, o áudio é processado pelo Google. Os dados são sintéticos, mas o aluno pode falar o próprio nome. Com dado real, isso teria de entrar na avaliação de privacidade (L14).

**O que não foi feito:** entrada por imagem (um print de comprovante). O sistema foi desenhado para **não ler anexos** (rubrica do juiz, regra 3), e não foi verificado se o modelo aprovado aceita imagem. Saída multimídia já existia: a declaração, o histórico e o boleto saem como página imprimível ou PDF (`src/triagem/documentos.py`).

## 2. Onde vira texto

No **navegador**, antes do sistema: *pipeline* de transcrição pela Web Speech API (`pt-BR`), feita pelo serviço de reconhecimento do navegador (no Chrome, o do Google; nos outros navegadores, este projeto não verificou qual). O sistema **nunca recebe áudio**: o que chega à API é texto que o aluno conferiu. Por isso o limite de tamanho é o da mensagem de texto, e não há modelo multimodal.

## 3. A saída

Nenhuma mídia nova. Os documentos (declaração, histórico, boleto) já saíam como página imprimível, que o navegador salva em PDF (`src/triagem/documentos.py`).

## 4. O custo

**Zero** para o projeto: a transcrição roda no navegador do aluno e não passa pela Groq. O texto transcrito custa o mesmo que o digitado.

## 5. O que falta

- **A voz é canal de entrada** (`seguranca.md` §1 e §8), mas o *golden dataset* **não tem caso com mídia**: como o áudio vira texto no navegador, o caso equivalente seria um texto com os erros típicos de transcrição ("meu rá é dois zero dois três..."). Acrescentar esses casos exige uma nova versão do dataset e uma rodada com o modelo (cota). **LACUNA.**
- Entrada por imagem (print de comprovante) não foi feita, como dito no §1.
