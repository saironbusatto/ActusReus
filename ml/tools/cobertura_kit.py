"""Matriz de cobertura do kit: toda habilidade ativa que cada bot original sabe × ação existente no playerbots × uso.

Uso: python cobertura_kit.py --desde "2026-10-21 23:50" > ../.claude/skills/wotlk-arena-coach/reference/cobertura-kit.md
Fontes: character_spell dos 4 originais, Spell.dbc do servidor (nome, passiva, família), os creators de ação do
mod-playerbots (nome da ação = nome da magia em minúsculas) e as ações "- OK" do Playerbots.log no período.
"""
import argparse
import re
import struct
import subprocess
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "azerothcore-wotlk" / "modules" / "mod-playerbots" / "src"
LOG = ROOT / "azerothcore-wotlk" / "env" / "dist" / "logs" / "Playerbots.log"
DBC = ROOT / "ml" / "dbc" / "Spell.dbc"

BOTS = {304: ("Zebedeu", "Rogue", 8), 95: ("Amnesian", "Priest", 6), 399: ("Ominous", "Warlock", 5),
        410: ("Pehdicouve", "Druid", 7)}
RACIALS = {"Shadowmeld", "Cannibalize", "Will of the Forsaken", "Escape Artist", "Berserking",
           "Every Man for Himself", "Stoneform", "Gift of the Naaru", "Arcane Torrent", "War Stomp", "Blood Fury"}
F_ID, F_ATTR, F_NAME, F_FAMILY = 0, 4, 136, 208
ATTR_PASSIVE = 0x40


def sql(q: str) -> list[list[str]]:
    out = subprocess.run(["docker", "exec", "ac-database", "sh", "-c",
                          'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -N -e "$0" 2>/dev/null', q],
                         capture_output=True, text=True, check=True).stdout
    return [line.split("\t") for line in out.splitlines() if line]


def spell_table() -> dict[int, tuple[str, bool, int]]:
    d = DBC.read_bytes()
    _, n, f, rs, _ = struct.unpack("<4s4I", d[:20])
    strings = d[20 + n * rs:]
    table = {}
    for i in range(n):
        r = struct.unpack_from(f"<{f}I", d, 20 + i * rs)
        name = strings[r[F_NAME]:strings.index(b"\0", r[F_NAME])].decode(errors="replace")
        table[r[F_ID]] = (name, bool(r[F_ATTR] & ATTR_PASSIVE), r[F_FAMILY])
    return table


def action_names() -> set[str]:
    names = set()
    for path in SRC.rglob("*Context*"):
        names |= set(re.findall(r'creators\["([^"]+)"\]', path.read_text(errors="replace")))
    return names


def usage(since: str) -> Counter:
    pat = re.compile(r"^(\S+ \S+) \S+ A:(.+?) - OK")
    c = Counter()
    for line in LOG.open(errors="replace"):
        m = pat.match(line)
        if m and m.group(1) >= since:
            c[re.sub(r" on .*$", "", m.group(2))] += 1
    return c


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--desde", required=True)
    a = ap.parse_args()
    spells, actions, used = spell_table(), action_names(), usage(a.desde)
    known: dict[int, set[str]] = {}
    for guid, spell in sql(f"SELECT guid, spell FROM acore_characters.character_spell WHERE guid IN "
                           f"({','.join(map(str, BOTS))})"):
        info = spells.get(int(spell))
        if not info or info[1]:
            continue
        name, _, family = info
        if family == BOTS[int(guid)][2] or name in RACIALS:
            known.setdefault(int(guid), set()).add(name)

    print(f"# Cobertura do kit — usos desde {a.desde}\n")
    print("Legenda: **sem ação** = o playerbots não tem como usar; **0** = existe ação mas não foi usada no período.\n")
    for guid, (bot, cls, _) in BOTS.items():
        print(f"## {cls} ({bot})\n\n| Habilidade | Ação no playerbots | Usos |\n|---|---|---|")
        for name in sorted(known.get(guid, ())):
            key = name.lower()
            has = any(x == key or x.startswith(key + " ") for x in actions)
            n = used.get(key, 0)
            print(f"| {name}{' (racial)' if name in RACIALS else ''} | {'sim' if has else '**sem ação**'} | "
                  f"{n if has else '-'} |")
        print()


if __name__ == "__main__":
    main()
