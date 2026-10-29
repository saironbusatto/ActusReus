#!/usr/bin/env bash
# Liga a IA de arena ao vivo: campeã (v3) nos times 54,58,...,86, desafiante (treinada ao vivo) nos 55,59,...,87,
# a rede decidindo em ArenaMlControl dos ticks; reinicia o worldserver com a imagem nova e sobe o treinador
# ml/policy/live.py como serviço do usuário (systemd --user, unidade ia-ao-vivo).
#   agente/ligar-ao-vivo.sh            -> config + restart + treinador
#   agente/ligar-ao-vivo.sh treinador  -> só (re)sobe os treinadores
# V9 (A/B): dois desafiantes. Braço A (55,59,...,87, unidade ia-ao-vivo) treina com o plano tático
# (ml/policy/planos.json); braço B (a cópia III: 56,64,...,88, unidade ia-ao-vivo-b, pesos arena-policy-live-b.txt)
# treina com os fatos do verificador por código + momento decisivo. Ver agente/SPRINT-LLM.md.
# V10: os dois braços passaram de +3 → os dois treinam com plano + fatos por código + momento; o braço B testa a
# fase B: no C++, o alvo de kill do plano vira o alvo dos DPS (Playerbots.ArenaPlanTeams/ArenaPlanFile).
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
CONF=$ROOT/azerothcore-wotlk/env/dist/etc/modules/playerbots.conf
ETC=$ROOT/azerothcore-wotlk/env/dist/etc
TIMES_A=55,59,63,67,71,75,79,83,87
TIMES_B=56,64,68,72,76,80,84,88  # a cópia III sem o 60 (o usuário)

subir_treinador() {
    systemctl --user stop ia-ao-vivo 2>/dev/null || true
    systemctl --user reset-failed ia-ao-vivo 2>/dev/null || true
    systemd-run --user --unit=ia-ao-vivo --working-directory="$ROOT/ml" --property=Restart=on-failure \
        "$HOME/.local/bin/uv" run python -I policy/live.py --plano policy/planos.json --fatos-codigo --outro "$TIMES_B"
    echo "treinador A no ar: journalctl --user -u ia-ao-vivo -f"
    subir_braco_b
}

subir_braco_b() {  # começa da desafiante atual (pesos, checkpoint e posição no log)
    [ -f "$ETC/arena-policy-live-b.txt" ] || cp "$ETC/arena-policy-live.txt" "$ETC/arena-policy-live-b.txt"
    [ -f "$ROOT/ml/runs/live-desafiante-b.pt" ] || cp "$ROOT/ml/runs/live-desafiante.pt" "$ROOT/ml/runs/live-desafiante-b.pt"
    [ -f "$ROOT/ml/runs/live-b.offset" ] || cp "$ROOT/ml/runs/live.offset" "$ROOT/ml/runs/live-b.offset"
    systemctl --user stop ia-ao-vivo-b 2>/dev/null || true
    systemctl --user reset-failed ia-ao-vivo-b 2>/dev/null || true
    systemd-run --user --unit=ia-ao-vivo-b --working-directory="$ROOT/ml" --property=Restart=on-failure \
        "$HOME/.local/bin/uv" run python -I policy/live.py --braco b --times "$TIMES_B" --outro "$TIMES_A" \
        --desafiante "$ETC/arena-policy-live-b.txt" --fatos-codigo --plano policy/planos.json
    echo "treinador B no ar: journalctl --user -u ia-ao-vivo-b -f"
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
set_opt ArenaMlChallengerTeams "\"$TIMES_A\""
[ -f "$ETC/arena-policy-live-b.txt" ] || cp "$ETC/arena-policy-live.txt" "$ETC/arena-policy-live-b.txt"
set_opt ArenaMlChallengerBFile '"/azerothcore/env/dist/etc/arena-policy-live-b.txt"'
set_opt ArenaMlChallengerBTeams "\"$TIMES_B\""
set_opt ArenaMlControl 0.25
(cd "$ROOT/ml/policy" && python3 plano.py --exporta "$ETC/arena-plan.txt")
set_opt ArenaPlanFile '"/azerothcore/env/dist/etc/arena-plan.txt"'
set_opt ArenaPlanTeams "\"$TIMES_B\""
grep -E "^Playerbots.ArenaMl" "$CONF"

python3 -c "import sys; sys.path.insert(0, '$ROOT/ml/tools'); import wsconsole; wsconsole.run(['.saveall'])"
cd "$ROOT/azerothcore-wotlk"
docker compose up -d --force-recreate --no-build ac-worldserver
subir_treinador
