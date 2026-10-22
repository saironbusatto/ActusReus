"""Placar 3v3 por composição (fase 1 dos trios): vitórias, lutas, taxa com IC95% e confrontos.

Uso: python placar_trios.py --desde "2026-10-22 03:10" [--min-dur 15]
Composição = nome do time sem o numeral ("RMP I" -> "RMP"). Lutas mais curtas que --min-dur segundos ficam de
fora (portão aberto com time incompleto).
"""
import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "policy"))
from espelho import sql, wilson  # noqa: E402


def comp(team_name: str) -> str:
    return team_name.rsplit(" ", 1)[0]


def placar(rows: list[list[str]]) -> tuple[Counter, Counter, Counter]:
    wins, games, pairs = Counter(), Counter(), Counter()
    for winner, loser in rows:
        w, l = comp(winner), comp(loser)
        wins[w] += 1
        games[w] += 1
        games[l] += 1
        pairs[(w, l)] += 1
    return wins, games, pairs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--desde", required=True)
    ap.add_argument("--min-dur", type=int, default=15)
    a = ap.parse_args()
    rows = sql(f"""SELECT tw.name, tl.name FROM acore_characters.log_arena_fights f
                   JOIN acore_characters.arena_team tw ON tw.arenaTeamId = f.winner
                   JOIN acore_characters.arena_team tl ON tl.arenaTeamId = f.loser
                   WHERE f.type = 3 AND f.time >= '{a.desde}' AND f.duration >= {a.min_dur}""")
    wins, games, pairs = placar(rows)
    print(f"# Placar 3v3 desde {a.desde} — {len(rows)} lutas (>= {a.min_dur}s)\n")
    print("| Composição | Vitórias | Lutas | Taxa | IC95% |\n|---|---|---|---|---|")
    for c in sorted(games, key=lambda c: -wins[c] / games[c]):
        lo, hi = wilson(wins[c], games[c])
        print(f"| {c} | {wins[c]} | {games[c]} | {wins[c] / games[c]:.0%} | {lo:.0%}–{hi:.0%} |")
    names = sorted(games)
    print("\n## Confrontos (vitórias da linha – da coluna)\n")
    print("| | " + " | ".join(names) + " |\n" + "|---" * (len(names) + 1) + "|")
    for r in names:
        print(f"| {r} | " + " | ".join("-" if r == c else f"{pairs[(r, c)]}-{pairs[(c, r)]}" for c in names) + " |")


def _selftest() -> None:
    wins, games, pairs = placar([["RMP I", "TSG II"], ["RMP II", "TSG I"], ["TSG III", "RMP IV"]])
    assert wins["RMP"] == 2 and games["RMP"] == 3 and games["TSG"] == 3 and pairs[("TSG", "RMP")] == 1
    assert comp("Shadowplay III") == "Shadowplay"


if __name__ == "__main__":
    _selftest()
    main()
