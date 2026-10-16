#!/usr/bin/env bash
# Gera docs/evidencias/empacotamento.txt (Exercício 13). Rodar da raiz do
# repositório, depois de `docker build -t secretaria-academica-agente:local .`:
#   bash scripts/evidencias_ex13.sh
export MSYS_NO_PATHCONV=1
IMG=secretaria-academica-agente:local
CTL="${1:-$(mktemp -d)}"   # diretório temporário (controle negativo, corpo JSON)
OUT=docs/evidencias/empacotamento.txt
mkdir -p "$CTL"

run() { echo "\$ $1"; bash -c "$1" 2>&1; echo; }

{
echo "# Evidências do Exercício 13 — empacotamento"
echo "# Geradas em $(date +%Y-%m-%d) com Docker $(docker version --format '{{.Server.Version}}'),"
echo "# imagem construída do working tree sobre o commit $(git rev-parse --short HEAD)."
echo
echo "## 1. A imagem"
echo
run "docker image ls $IMG --format '{{.Repository}}:{{.Tag}}  {{.ID}}  {{.Size}}'"
run "docker image inspect $IMG --format 'User={{.Config.User}}  Cmd={{.Config.Cmd}}'"
run "docker history $IMG --format '{{.Size}}\t{{.CreatedBy}}' | head -11"
run "docker run --rm $IMG id"
run "docker run --rm $IMG sh -c 'find /app -type f | sort'"
run "docker run --rm $IMG sh -c 'test ! -e /app/.env && echo sem-.env-na-imagem'"
run "docker run --rm $IMG python -c 'import torch' 2>&1 | tail -1"

echo "## 2. Portões de segurança (os mesmos comandos do job seguranca)"
echo
run "docker run --rm -i hadolint/hadolint:v2.12.0 hadolint --failure-threshold error - < Dockerfile; echo exit=\$?"
run "docker run --rm -i hadolint/hadolint:v2.12.0 hadolint - < Dockerfile; echo \"exit=\$? (sem limiar: nenhum aviso de nenhuma severidade)\""
run "docker run --rm -v \"\$PWD:/src:ro\" aquasec/trivy:0.58.1 config --skip-check-update --exit-code 1 --severity HIGH,CRITICAL /src 2>&1 | grep -vE 'INFO|^\s*\$'; echo exit=\${PIPESTATUS[0]}"
run "docker run --rm -v \"\$PWD:/src:ro\" aquasec/trivy:0.58.1 config --skip-check-update /src 2>&1 | grep -vE 'INFO|^\s*\$'; echo \"exit=\${PIPESTATUS[0]} (todas as severidades: nenhum achado)\""
grep -v '^USER' Dockerfile > "$CTL/Dockerfile"
echo "# Controle negativo: o mesmo Dockerfile sem a linha USER."
run "docker run --rm -v \"$CTL:/src:ro\" aquasec/trivy:0.58.1 config --skip-check-update --exit-code 1 --severity HIGH,CRITICAL /src 2>&1 | grep -E 'Tests:|AVD-'; echo exit=\${PIPESTATUS[0]}"

echo "## 3. Cache de build: mudar o código não reinstala as dependências"
echo
cp src/api.py "$CTL/api.py.bak"
echo "# linha temporária para invalidar a camada do código" >> src/api.py
run "docker build -t $IMG-cache . 2>&1 | grep -E '^#[0-9]+ \[[0-9]/[0-9]\]|CACHED' "
cp "$CTL/api.py.bak" src/api.py
docker image rm $IMG-cache >/dev/null 2>&1

echo "## 4. Execução: API com o estado num volume"
echo
printf '%s' '{"mensagem": "Preciso de uma declaração de matrícula. RA 20231045"}' > "$CTL/corpo.json"
docker volume rm -f estado-ex13 >/dev/null 2>&1
run "docker run -d --name ex13 -p 8000:8000 -v estado-ex13:/dados -e OPENAI_API_KEY=chave-invalida-de-teste $IMG >/dev/null && echo container-iniciado"
run "for i in \$(seq 1 30); do curl -fs localhost:8000/saude && break; sleep 1; done"
echo "# Chave inválida de propósito: o provedor recusa (401), o laço termina em"
echo "# erro_fatal sem nenhuma escrita (fail-closed) e o aluno recebe resposta."
run "curl -s -X POST localhost:8000/mensagens -H 'content-type: application/json; charset=utf-8' --data-binary @\"$CTL/corpo.json\""
run "docker exec ex13 sh -c 'ls /dados /dados/logs'"
run "docker exec ex13 python -c \"import sqlite3; c = sqlite3.connect('/dados/academico.db'); print('documentos_emitidos =', c.execute('select count(*) from documentos_emitidos').fetchone()[0], '(só a semente: nada emitido)')\""
run "docker exec ex13 sh -c 'grep -o \"\\\"termino\\\": \\\"[a-z_]*\\\"\" /dados/logs/*.json'"
run "for i in \$(seq 1 45); do s=\$(docker inspect ex13 --format '{{.State.Health.Status}}'); [ \"\$s\" != starting ] && break; sleep 1; done; echo health=\$s"

echo "## 5. Interrupção e efemeridade"
echo
run "time docker stop ex13"
run "docker rm ex13 >/dev/null && echo container-removido"
run "docker run --rm -v estado-ex13:/dados $IMG sh -c 'ls /dados /dados/logs'"
echo "# Mesma imagem, sem o volume: o estado não está na imagem."
run "docker run --rm $IMG sh -c 'ls -A /dados/logs; test -e /dados/academico.db && echo tem-banco || echo sem-banco'"
docker volume rm -f estado-ex13 >/dev/null 2>&1
} > "$OUT"
echo "gerado: $OUT"
