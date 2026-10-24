"""Espelho 3v3 (rede x regras, mesma composição) por composição e por período, para o relatório do Obsidian.

Uso: uv run python -I tools/relatorio_v3.py
Exclui o time 60 (jogador real) e os 15 min após cada restart (aquecimento com lag).
"""
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "policy"))
from espelho import sql, wilson  # noqa: E402

ML = {54, 55, 58, 59, 62, 63, 66, 67, 70, 71, 74, 75, 78, 79, 82, 83, 86, 87}
EXCLUIR_TIMES = {60}
RESTARTS_UTC = ["2026-10-22 23:12", "2026-10-23 00:41", "2026-10-23 02:02", "2026-10-23 02:20",
                "2026-10-23 02:52", "2026-10-23 03:25", "2026-10-24 13:39"]
PERIODOS = {"v2b": ("2026-10-22 21:50", "2026-10-24 13:38"), "v3": ("2026-10-24 13:41", "2099-01-01 00:00")}
AQUECIMENTO = timedelta(minutes=15)


def aquecendo(t: datetime) -> bool:
    return any(r <= t < r + AQUECIMENTO for r in (datetime.fromisoformat(x) for x in RESTARTS_UTC))


def espelho(desde: str, ate: str) -> tuple[Counter, Counter, int]:
    rows = sql(f"""SELECT f.fight_id, f.time, f.winner, m.team, t.name
                   FROM acore_characters.log_arena_fights f
                   JOIN acore_characters.log_arena_memberstats m USING(fight_id)
                   JOIN acore_characters.arena_team t ON t.arenaTeamId = m.team
                   WHERE f.type = 3 AND f.duration >= 20 AND f.time >= '{desde}' AND f.time < '{ate}'
                   GROUP BY f.fight_id, m.team""")
    fights: dict[str, dict] = {}
    for fid, t, winner, team, name in rows:
        f = fights.setdefault(fid, {"t": datetime.fromisoformat(t), "w": int(winner), "teams": {}})
        f["teams"][int(team)] = name.rsplit(" ", 1)[0]
    lutas, vit, descartadas = Counter(), Counter(), 0
    for f in fights.values():
        teams = list(f["teams"].items())
        if len(teams) != 2 or teams[0][1] != teams[1][1]:
            continue
        if EXCLUIR_TIMES & f["teams"].keys() or aquecendo(f["t"]):
            descartadas += 1
            continue
        ml_side = [t for t, _ in teams if t in ML]
        if len(ml_side) != 1:
            continue
        comp = teams[0][1]
        lutas[comp] += 1
        vit[comp] += f["w"] == ml_side[0]
    return lutas, vit, descartadas


def main() -> None:
    for nome, (desde, ate) in PERIODOS.items():
        lutas, vit, desc = espelho(desde, ate)
        n, w = sum(lutas.values()), sum(vit.values())
        if not n:
            print(f"\n## {nome}: sem lutas")
            continue
        lo, hi = wilson(w, n)
        print(f"\n## {nome} ({desde} → {ate[:16]}) — espelho {w}/{n} = {w / n:.0%} (IC {lo:.0%}–{hi:.0%}),"
              f" {desc} descartadas (time 60/aquecimento)")
        for comp in sorted(lutas, key=lambda c: -vit[c] / lutas[c]):
            lo, hi = wilson(vit[comp], lutas[comp])
            print(f"| {comp} | {vit[comp]}/{lutas[comp]} | {vit[comp] / lutas[comp]:.0%} | {lo:.0%}–{hi:.0%} |")


if __name__ == "__main__":
    assert aquecendo(datetime(2026, 10, 24, 13, 50)) and not aquecendo(datetime(2026, 10, 24, 14, 0))
    main()
