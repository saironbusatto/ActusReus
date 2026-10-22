"""Placar do espelho: times com a política ML contra times só com regras, mesma composição.

Uso: uv run python -I policy/espelho.py --desde "2026-10-22 08:00" --times-ml 26,27,28 [--tipo 3]
Conta só lutas reais (>= 20 s) em que um time está na lista ML e o outro não, com a mesma composição de classes (dupla em 2v2, trio em 3v3).
Portão para manter o ML ligado: >= 200 lutas e >= 55% de vitórias do ML (com intervalo de 95%).
"""
import argparse
import math
import subprocess

GATE_FIGHTS, GATE_RATE = 200, 0.55


def sql(q: str) -> list[list[str]]:
    out = subprocess.run(["docker", "exec", "ac-database", "sh", "-c",
                          'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -N -e "$0" 2>/dev/null', q],
                         capture_output=True, text=True, check=True).stdout
    return [line.split("\t") for line in out.splitlines() if line]


def wilson(wins: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if not n:
        return 0.0, 1.0
    p = wins / n
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return c - h, c + h


def placar(rows: list[list[str]], ml: set[int]) -> tuple[int, int]:
    """rows: fight_id, winner, team, comp (classes ordenadas). Devolve (lutas espelho, vitórias do ML)."""
    fights: dict[str, dict] = {}
    for fid, winner, team, comp in rows:
        f = fights.setdefault(fid, {"winner": int(winner), "teams": {}})
        f["teams"][int(team)] = comp
    n = wins = 0
    for f in fights.values():
        teams = list(f["teams"].items())
        if len(teams) != 2 or teams[0][1] != teams[1][1]:
            continue
        ml_side = [t for t, _ in teams if t in ml]
        if len(ml_side) != 1:
            continue
        n += 1
        wins += f["winner"] == ml_side[0]
    return n, wins


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--desde", required=True)
    ap.add_argument("--times-ml", required=True)
    ap.add_argument("--tipo", type=int, choices=(2, 3), default=2, help="2 = 2v2, 3 = 3v3")
    a = ap.parse_args()
    ml = {int(t) for t in a.times_ml.split(",") if t.strip()}
    rows = sql(f"""SELECT f.fight_id, f.winner, m.team, GROUP_CONCAT(c.class ORDER BY c.class)
                   FROM acore_characters.log_arena_fights f
                   JOIN acore_characters.log_arena_memberstats m USING(fight_id)
                   JOIN acore_characters.characters c ON c.guid = m.guid
                   WHERE f.type = {a.tipo} AND f.duration >= 20 AND f.time >= '{a.desde}'
                   GROUP BY f.fight_id, m.team""")
    n, wins = placar(rows, ml)
    lo, hi = wilson(wins, n)
    rate = wins / n if n else 0
    ok = n >= GATE_FIGHTS and rate >= GATE_RATE
    print(f"espelho: {n} lutas, ML venceu {wins} ({rate:.0%}, IC95% {lo:.0%}-{hi:.0%}) -> "
          f"{'PASSA no portão' if ok else 'ainda não passa'} (>= {GATE_FIGHTS} lutas e >= {GATE_RATE:.0%})")


if __name__ == "__main__":
    # autoteste do placar: 3 lutas espelho, ML (26) vence 2; uma luta não-espelho é ignorada
    rows = [["1", "26", "26", "4,5"], ["1", "26", "16", "4,5"], ["2", "16", "26", "4,5"], ["2", "16", "16", "4,5"],
            ["3", "26", "26", "4,5"], ["3", "26", "27", "4,5"], ["4", "26", "26", "4,5"], ["4", "26", "19", "9,11"]]
    assert placar(rows, {26}) == (3, 2), placar(rows, {26})
    main()
