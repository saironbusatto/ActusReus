#!/usr/bin/env bash
# Liga os 40 clones (60 bots, 15 arenas) com a imagem nova. Só com o OK do usuário.
# Pré-requisito: backup recente em backups/ (ex.: *_pregolive.sql.gz).
set -euo pipefail
cd "$(dirname "$0")/../azerothcore-wotlk"
CONF=env/dist/etc/modules/playerbots.conf
NEW=",Zebedeuv,Zebedeuvi,Zebedeuvii,Zebedeuix,Zebedeux,Zebedeuxi,Zebedeuxii,Zebedeuxiv,Zebedeuxv,Zebedeuxvi,Amnesianvi,Amnesianvii,Amnesianix,Amnesianx,Amnesianxi,Amnesianxii,Amnesianxiv,Amnesianxv,Amnesianxvi,Amnesianxvii,Ominousvii,Ominousix,Ominousx,Ominousxi,Ominousxii,Ominousxiv,Ominousxv,Ominousxvi,Ominousxvii,Ominousxix,Pehdicouvi,Pehdicouvii,Pehdicouix,Pehdicoux,Pehdicouxi,Pehdicouxii,Pehdicouxiv,Pehdicouxv,Pehdicouxvi,Pehdicouxvii"
mysql() { docker exec -i ac-database sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -t 2>/dev/null'; }

docker compose stop ac-worldserver
mysql < ../agente/golive-fixgems.sql
out=$(mysql < ../agente/golive-clones.sql)
echo "$out" | head -5
grep -q 'OK: 40 clones encontrados' <<<"$out" || { echo "PARE: clones faltando, voltando com 20 bots"; docker compose up -d ac-worldserver; exit 1; }

cp "$CONF" "$CONF.bak-pre-golive"
grep -q 'Zebedeuxvi' "$CONF" || sed -i "s/^\(Playerbots.FixedRandomBots = \".*\)\"$/\1$NEW\"/" "$CONF"
sed -i 's/^Playerbots.MinRandomBots = .*/Playerbots.MinRandomBots = 60/; s/^Playerbots.MaxRandomBots = .*/Playerbots.MaxRandomBots = 60/; s/^Playerbots.RandomBotAutoJoinBGRatedArena2v2Count = .*/Playerbots.RandomBotAutoJoinBGRatedArena2v2Count = 15/' "$CONF"
grep -cE '^Playerbots\.(MinRandomBots|MaxRandomBots) = 60$' "$CONF"

docker compose up -d ac-worldserver
echo "ligado; conferir: '60 fixed random bots' no log e 60 online"
