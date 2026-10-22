#!/usr/bin/env bash
# Troca o servidor entre o modo ARENA (108 bots, 36 trios, avaliação da rede) e o modo AB (29 bots + você, 15x15).
#   agente/modo-ab.sh ab      -> guarda a config de arena em playerbots.conf.modo-arena e sobe a da AB
#   agente/modo-ab.sh arena   -> volta a config de arena
# Faz .saveall e reinicia o worldserver (~2 min). Rodar só quando quiser trocar: o restart interrompe as lutas.
set -euo pipefail
cd "$(dirname "$0")/../azerothcore-wotlk"
DIR=env/dist/etc/modules
CONF=$DIR/playerbots.conf

case "${1:-}" in
  ab)
    grep -q '^Playerbots.RandomBotAutoJoinBGABCount = 1' "$CONF" && { echo "já está no modo AB"; exit 0; }
    cp "$CONF" "$DIR/playerbots.conf.modo-arena"
    cp "$DIR/playerbots.conf.modo-ab" "$CONF"
    ;;
  arena)
    [ -f "$DIR/playerbots.conf.modo-arena" ] || { echo "sem playerbots.conf.modo-arena para voltar"; exit 1; }
    cp "$DIR/playerbots.conf.modo-arena" "$CONF"
    ;;
  *) echo "uso: $0 ab|arena"; exit 1 ;;
esac

python3 -c "import sys; sys.path.insert(0, '../ml/tools'); import wsconsole; wsconsole.run(['.saveall'])"
docker compose restart ac-worldserver
echo "modo $1 aplicado; bots online em ~2 min (MinRandomBots = $(grep -oP '^Playerbots.MinRandomBots = \K\d+' "$CONF"))"
