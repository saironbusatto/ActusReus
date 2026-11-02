#!/usr/bin/env bash
# Mantém o Playerbots.log (log detalhado dos bots, ~0,5 GB/h; o treino não usa) abaixo de 5 GB: guarda o último 1 GB em
# Playerbots.log.1 e zera o original. O worldserver abre o log em modo append, então segue escrevendo sem reiniciar.
#   systemd-run --user --unit=apara-log --on-calendar=hourly agente/apara-log.sh
set -euo pipefail
LOG=$(cd "$(dirname "$0")/.." && pwd)/azerothcore-wotlk/env/dist/logs/Playerbots.log
LIMITE=$((5 * 1024 * 1024 * 1024))
[ -f "$LOG" ] && [ "$(stat -c %s "$LOG")" -gt "$LIMITE" ] || exit 0
tail -c 1G "$LOG" > "$LOG.1"
truncate -s 0 "$LOG"
