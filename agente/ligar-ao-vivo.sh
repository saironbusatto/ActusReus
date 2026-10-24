#!/usr/bin/env bash
# Liga a IA de arena ao vivo: campeã (v3) nos times 54,58,...,86, desafiante (treinada ao vivo) nos 55,59,...,87,
# a rede decidindo em ArenaMlControl dos ticks; reinicia o worldserver com a imagem nova e sobe o treinador
# ml/policy/live.py como serviço do usuário (systemd --user, unidade ia-ao-vivo).
#   agente/ligar-ao-vivo.sh            -> config + restart + treinador
#   agente/ligar-ao-vivo.sh treinador  -> só (re)sobe o treinador
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
CONF=$ROOT/azerothcore-wotlk/env/dist/etc/modules/playerbots.conf
ETC=$ROOT/azerothcore-wotlk/env/dist/etc

subir_treinador() {
    systemctl --user stop ia-ao-vivo 2>/dev/null || true
    systemctl --user reset-failed ia-ao-vivo 2>/dev/null || true
    systemd-run --user --unit=ia-ao-vivo --working-directory="$ROOT/ml" --property=Restart=on-failure \
        "$HOME/.local/bin/uv" run python -I policy/live.py
    echo "treinador no ar: journalctl --user -u ia-ao-vivo -f"
}

if [ "${1:-}" = "treinador" ]; then subir_treinador; exit 0; fi

cp "$CONF" "$CONF.bak-pre-live"
[ -f "$ETC/arena-policy-live.txt" ] || cp "$ETC/arena-policy-v3.txt" "$ETC/arena-policy-live.txt"
set_opt() {  # set_opt chave valor: troca a linha se existe, senão acrescenta no fim
    if grep -q "^Playerbots.$1 = " "$CONF"; then
        sed -i "s|^Playerbots.$1 = .*|Playerbots.$1 = $2|" "$CONF"
    else
        echo "Playerbots.$1 = $2" >> "$CONF"
    fi
}
set_opt ArenaMlPolicyFile '"/azerothcore/env/dist/etc/arena-policy-v3.txt"'
set_opt ArenaMlTeams '"54,58,62,66,70,74,78,82,86"'
set_opt ArenaMlChallengerFile '"/azerothcore/env/dist/etc/arena-policy-live.txt"'
set_opt ArenaMlChallengerTeams '"55,59,63,67,71,75,79,83,87"'
set_opt ArenaMlControl 0.25
grep -E "^Playerbots.ArenaMl" "$CONF"

python3 -c "import sys; sys.path.insert(0, '$ROOT/ml/tools'); import wsconsole; wsconsole.run(['.saveall'])"
cd "$ROOT/azerothcore-wotlk"
docker compose up -d --force-recreate --no-build ac-worldserver
subir_treinador
