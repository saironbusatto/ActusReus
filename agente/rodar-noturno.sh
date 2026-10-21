#!/usr/bin/env bash
# Roda o agente programador (Antigravity + Gemini) sem supervisão, com a tarefa de agente/TAREFA-NOTURNA.md.
# Toda a sessão (cada comando e edição) fica gravada em agente/logs/ para auditoria.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p agente/logs
stamp=$(date +%Y%m%d_%H%M)

{
    echo "inicio: $(date -Is)"
    echo "modulo: $(git -C azerothcore-wotlk/modules/mod-playerbots rev-parse --short HEAD)"
    echo "actusreus: $(git rev-parse --short HEAD)"
} > "agente/logs/sessao-$stamp.info"

agy -p "$(cat agente/TAREFA-NOTURNA.md)" \
    --model gemini-3.8-flash-high \
    --dangerously-skip-permissions \
    --output-format stream-json \
    --print-timeout 12h \
    --log-file "agente/logs/agy-$stamp.log" \
    > "agente/logs/transcricao-$stamp.jsonl" 2> "agente/logs/stderr-$stamp.log" || echo "agy saiu com erro $?" >> "agente/logs/sessao-$stamp.info"

echo "fim: $(date -Is)" >> "agente/logs/sessao-$stamp.info"
