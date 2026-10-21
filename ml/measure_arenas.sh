#!/usr/bin/env bash
# Amostra a cada INTERVAL s, por DURATION s: lutas de arena concluídas, bots em mapas de arena,
# CPU/RAM do worldserver e RAM livre do host. Saída CSV em ml/runs/.
set -euo pipefail
DURATION=${DURATION:-3600}
INTERVAL=${INTERVAL:-60}
OUT=${OUT:-$(dirname "$0")/runs/arena_$(date +%Y%m%d_%H%M).csv}
ARENA_MAPS="559,562,572,617,618"

q() { docker exec ac-database sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -N -e "$0" 2>/dev/null' "$1"; }

echo "ts,fights_total,fights_2v2,avg_dur_s,in_arena_maps,online,ws_cpu_pct,ws_mem_mib,host_avail_mib" > "$OUT"
end=$(( $(date +%s) + DURATION ))
while [ "$(date +%s)" -lt "$end" ]; do
    read -r ft f2 avg < <(q "SELECT COUNT(*), COALESCE(SUM(type=2),0), COALESCE(ROUND(AVG(duration)/1000),0) FROM acore_characters.log_arena_fights")
    read -r inarena online < <(q "SELECT SUM(map IN ($ARENA_MAPS)), COUNT(*) FROM acore_characters.characters WHERE online=1")
    read -r cpu mem < <(docker stats --no-stream --format '{{.CPUPerc}} {{.MemUsage}}' ac-worldserver \
        | awk '{gsub("%","",$1); m=$2; u=m; gsub(/[0-9.]/,"",u); gsub(/[A-Za-z]/,"",m); if(u=="GiB") m*=1024; print $1, int(m)}')
    avail=$(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo)
    echo "$(date +%FT%T),$ft,${f2:-0},$avg,${inarena:-0},$online,$cpu,$mem,$avail" | tee -a "$OUT"
    sleep "$INTERVAL"
done
echo "done: $OUT"
