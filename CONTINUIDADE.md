# Continuidade — Exercícios 12 e 13

Situação em **16/10/2026**, ao sair do PC do Senac. A rede do Senac bloqueou o **push para o GitHub** e travou o **Docker Desktop**: o motor perdeu a conexão com a VM do WSL (`dialing 192.168.65.7:2376: context deadline exceeded`). Este arquivo diz o que está feito, o que falta e os comandos exatos para terminar em outro PC.

## ⚠️ Antes de tudo: o GitHub NÃO tem este trabalho

O remoto ainda está no commit `9bc9f8f`. Os dois commits novos existem **só neste PC**:

| Commit | Conteúdo |
|---|---|
| `b3f4596` | Exercício 12: model card com evidência |
| commit do Ex.13 | Exercício 13: imagem Docker, API, CI/CD |

Para levar o trabalho para o outro PC, use **um** destes caminhos:

- **Arquivo bundle (recomendado).** `secretaria-academica-agente.bundle`, gerado em `Downloads\secretaria-academica-agente-master\`, ao lado da pasta do projeto. É um arquivo único com todo o histórico. Leve por pendrive, e-mail ou Drive.
- **A pasta inteira**, incluindo a pasta oculta `.git` (zip da pasta do projeto). Não precisa levar `.venv`.

## 1. No outro PC: recuperar o repositório e subir no GitHub

Com o bundle:

```bash
git clone secretaria-academica-agente.bundle secretaria-academica-agente
cd secretaria-academica-agente
git remote set-url origin https://github.com/weslleyssousa444-ui/secretaria-academica-agente.git
git log --oneline -3          # os dois commits novos devem aparecer no topo
git push origin master        # abre o login do GitHub no navegador
```

Com a pasta zipada: descompacte, entre nela e rode só o `git push origin master`.

Para usar SSH (`git@github.com:...`), cadastre antes uma chave SSH na sua conta do GitHub e rode `git remote set-url origin git@github.com:weslleyssousa444-ui/secretaria-academica-agente.git`.

## 2. Conferir os testes offline (não precisam de chave nem de Docker)

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate      Linux/macOS: source .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest -v                     # esperado: 31 passed, 1 deselected
```

## 3. Criar o `.env` com a chave da Groq

```bash
cp .env.example .env
# edite .env: OPENAI_API_KEY=<sua chave da Groq>  (https://console.groq.com/keys)
```

O `.env` nunca vai para o git nem para a imagem: está no `.gitignore` e no `.dockerignore`.

## 4. Terminar as evidências do Exercício 13 (precisa de Docker)

```bash
docker build -t secretaria-academica-agente:local .
bash scripts/evidencias_ex13.sh          # no Windows, rode no Git Bash
```

O script **regenera** `docs/evidencias/empacotamento.txt` inteiro e cobre o que ficou pendente:

- [ ] cache de build: depois de mudar o código, a camada do `pip install` sai `CACHED`;
- [ ] `POST /mensagens` com chave inválida: termina em `erro_fatal`, sem escrita, e grava o registro em `/dados/logs`;
- [ ] `HEALTHCHECK` chegando a `healthy`.

Abra o arquivo gerado e confira os três itens. Se algum der diferente do esperado, **anote o resultado real** em `docs/empacotamento.md`; não ajuste o texto para parecer certo.

Se o Docker Desktop ficar "iniciando" para sempre, rode `wsl --shutdown` no PowerShell e abra o Docker de novo. Foi o que destravou no Senac, até a rede cair de vez.

## 5. Rodar o eval com o modelo real

```bash
python -m pytest -m eval -v -s           # usa a OPENAI_API_KEY do .env
```

Critério: trancamento 2/2 **e** pelo menos 5/6 no total. Leva cerca de 1 minuto (pausa de 8 s entre casos) e gasta tokens do *free tier*.

- [ ] Anote o resultado (quantos acertos, quais casos) em `docs/empacotamento.md` §6.

## 6. Ligar o pipeline no GitHub

1. **Settings → Secrets and variables → Actions → New repository secret:** nome `GROQ_API_KEY`, valor = a chave da Groq. Sem o secret, o job `eval` é pulado (aviso), e não reprovado.
2. **Settings → Actions → General → Workflow permissions:** se o push da imagem falhar com `denied`, marque *Read and write permissions*.
3. O push do passo 1 já dispara o workflow. Acompanhe em **Actions**:
   - [ ] `seguranca` verde (hadolint e Trivy);
   - [ ] `testes` verde (31 testes);
   - [ ] `eval` verde, ou o motivo anotado;
   - [ ] `imagem` verde, com a imagem em **Packages** como `ghcr.io/weslleyssousa444-ui/secretaria-academica-agente:<sha>`. O pacote nasce privado; para ficar público: *Package settings → Change visibility*.

## 7. Fechar a documentação

Em `docs/empacotamento.md`:

- tire o aviso "Situação em 16/10/2026" e os marcadores **PENDENTE** que você resolveu;
- registre o link da execução do workflow (URL da aba Actions).

Depois:

```bash
git add -A
git commit -m "Ex.13: evidências finais (cache, healthcheck, eval, pipeline no GitHub)"
git push origin master
```

Quando tudo estiver concluído, este arquivo pode ser apagado.

## O que já está feito

| Item | Onde |
|---|---|
| Model card nos 12 campos, 23 lacunas, 24 testes de governança | `docs/model-card.md`, `tests/test_autoridade.py`, `tests/test_lacunas.py` |
| Imagem: base fixada, 4 dependências, usuário sem privilégio, `COPY` por nome, sem `.env` | `Dockerfile`, `.dockerignore`, `requirements-agente.txt` |
| API (`/saude`, `/mensagens`) com 7 testes offline | `src/api.py`, `tests/test_api.py` |
| Estado no volume (banco e registros), testado com `stop`, `rm` e container novo | `docker-compose.yml`, `docs/evidencias/empacotamento.txt` §3–4 |
| hadolint sem avisos; Trivy sem achados; controle negativo (sem `USER`) reprova | `docs/evidencias/empacotamento.txt` §2 |
| Histórico do git sem chave vazada | `docs/empacotamento.md` §5 |
| Workflow: segurança, testes, eval, imagem → GHCR; *actions* e imagens fixadas por SHA ou *digest* | `.github/workflows/ci.yml` |
