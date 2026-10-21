"""Relatório das lutas de arena 2v2 num período, por composição, mais o uso das habilidades de arena.

Uso: python relatorio_lutas.py --desde "2026-10-21 03:00" [--ate "..."] [--log Playerbots.log ...]
Horários no relógio do servidor (log_arena_fights.time, UTC). Saída: markdown no terminal.
"""
import argparse
import re
import subprocess
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LOG = ROOT / "azerothcore-wotlk" / "env" / "dist" / "logs" / "Playerbots.log"

CLASS = {"4": "Rogue", "5": "Priest", "9": "Warlock", "11": "Druid"}
COMP = {frozenset({"Rogue", "Priest"}): "Rogue/Disc", frozenset({"Warlock", "Druid"}): "Warlock/Druid",
        frozenset({"Warlock", "Priest"}): "Warlock/Disc"}

# Habilidades de arena que o manual cobra (nome da ação no Playerbots.log)
ARENA_ACTIONS = {
    "Rogue": ["cheap shot", "kidney shot", "blind", "gouge", "sap", "kick", "shadowstep", "shadow dance",
              "hemorrhage", "preparation", "cloak of shadows", "vanish", "sinister strike"],
    "Priest": ["psychic scream", "psychic horror", "silence", "pain suppression", "penance", "dispel magic",
               "mass dispel", "shoot"],
    "Warlock": ["fear", "death coil", "howl of terror", "unstable affliction", "haunt", "curse of tongues",
                "spell lock"],
    "Druid": ["cyclone", "entangling roots", "bash", "barkskin", "nature's swiftness", "wrath", "moonfire"],
}

BOT_CLASS = {"Zebedeu": "Rogue", "Amnesian": "Priest", "Ominous": "Warlock", "Pehdicou": "Druid",
             "Pehdicouve": "Druid"}
SUFFIX = re.compile(r"(ii|tres|iv|v|vi|vii|ix|x|xi|xii|xiv|xv|xvi|xvii|xix)$")


def sql(query: str) -> list[list[str]]:
    out = subprocess.run(
        ["docker", "exec", "ac-database", "sh", "-c", 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -N -e "$0" 2>/dev/null',
         query], capture_output=True, text=True, check=True).stdout
    return [line.split("\t") for line in out.splitlines() if line]


def fights(since: str, until: str) -> list[dict]:
    rows = sql(f"""
        SELECT f.fight_id, f.duration, f.winner, m.name, c.class, m.damage, m.heal, m.kblows, m.team
        FROM acore_characters.log_arena_fights f
        JOIN acore_characters.log_arena_memberstats m USING(fight_id)
        JOIN acore_characters.characters c ON c.guid=m.guid
        WHERE f.type=2 AND f.time >= '{since}' AND f.time < '{until}' ORDER BY f.fight_id""")
    by_id: dict[str, dict] = {}
    for fid, dur, win, name, cls, dmg, heal, kb, team in rows:
        f = by_id.setdefault(fid, {"dur": int(dur), "win": win, "teams": {}})
        f["teams"].setdefault(team, []).append(
            {"name": name, "cls": CLASS.get(cls, cls), "dmg": int(dmg), "heal": int(heal), "kb": int(kb)})
    return list(by_id.values())


def comp_of(members: list[dict]) -> str:
    return COMP.get(frozenset(m["cls"] for m in members), "+".join(sorted(m["cls"] for m in members)))


def action_counts(logs: list[Path]) -> dict[str, Counter]:
    pattern = re.compile(r"(\w+) A:(.+?) - OK")
    counts: dict[str, Counter] = {}
    for log in logs:
        if not log.exists():
            continue
        with log.open(errors="replace") as fh:
            for line in fh:
                m = pattern.search(line)
                if m:
                    counts.setdefault(m.group(1), Counter())[m.group(2)] += 1
    return counts


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--desde", required=True)
    p.add_argument("--ate", default="2100-01-01")
    p.add_argument("--log", nargs="*", type=Path, default=[DEFAULT_LOG])
    a = p.parse_args()

    fs = fights(a.desde, a.ate)
    print(f"# Lutas 2v2 de {a.desde} a {a.ate} (horário do servidor)\n")
    print(f"Lutas: **{len(fs)}**, duração média {sum(f['dur'] for f in fs) / max(len(fs), 1):.0f} s\n")

    wins: Counter = Counter()
    games: Counter = Counter()
    per_class: dict[str, list[dict]] = {}
    for f in fs:
        comps = {team: comp_of(ms) for team, ms in f["teams"].items()}
        if len(comps) != 2:
            continue
        matchup = " × ".join(sorted(comps.values()))
        games[matchup] += 1
        winner_team = next((t for t, ms in f["teams"].items() if t == f["win"]), None)
        wins[(matchup, comps.get(winner_team, "?"))] += 1
        for ms in f["teams"].values():
            for m in ms:
                per_class.setdefault(m["cls"], []).append(m)

    print("| Confronto | Lutas | Vitórias |\n|---|---|---|")
    for matchup, n in games.most_common():
        detail = ", ".join(f"{c} {wins[(matchup, c)]}" for c in sorted(set(matchup.split(" × "))))
        print(f"| {matchup} | {n} | {detail} |")

    print("\n| Classe | Aparições | Dano médio | Cura média | Abates |\n|---|---|---|---|---|")
    for cls, ms in sorted(per_class.items()):
        n = len(ms)
        print(f"| {cls} | {n} | {sum(m['dmg'] for m in ms) / n:,.0f} | {sum(m['heal'] for m in ms) / n:,.0f} "
              f"| {sum(m['kb'] for m in ms)} |")

    counts = action_counts(a.log)
    print("\n## Uso das habilidades de arena (ações `- OK` no log, somando todos os bots da classe)\n")
    for cls, actions in ARENA_ACTIONS.items():
        total: Counter = Counter()
        for bot, c in counts.items():
            if BOT_CLASS.get(SUFFIX.sub("", bot)) == cls or BOT_CLASS.get(bot) == cls:
                total.update(c)
        print(f"- **{cls}**: " + ", ".join(f"{act} {total[act]}" for act in actions))


if __name__ == "__main__":
    main()
