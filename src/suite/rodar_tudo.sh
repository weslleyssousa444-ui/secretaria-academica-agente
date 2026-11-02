#!/bin/sh
# Roda as quatro rodadas da suíte em sequência (A1, B1, B2, A2), retomando
# quando a cota diária da Groq interrompe (código 3). Uso: sh src/suite/rodar_tudo.sh <python>
PY="$1"
for rodada in "A 1" "B 1" "B 2" "A 2"; do
  set -- $rodada
  while :; do
    "$PY" -I src/suite/executor.py --versao "$1" --run "$2"
    codigo=$?
    [ "$codigo" -eq 3 ] || break
    echo "cota esgotada em $1$2; nova tentativa em 30 min"; sleep 1800
  done
done
echo "TODAS AS RODADAS COMPLETAS"
