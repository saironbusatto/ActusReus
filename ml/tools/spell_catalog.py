"""Catálogo de habilidades de arena lido do Spell.dbc 3.3.5a do próprio servidor.

Uso: python spell_catalog.py <dir com Spell/SpellDuration/SpellRange/SpellCastTimes.dbc>
Saída: tabela markdown por classe (rank mais alto de cada magia).
"""
import struct
import sys
from pathlib import Path

# Índices de campo do SpellEntry 3.3.5a (AzerothCore DBCStructure.h)
F_ID, F_MECHANIC, F_ATTR, F_CAST, F_CD, F_CATCD, F_DUR, F_RANGE = 0, 3, 4, 28, 29, 30, 40, 46
F_SPELL_LEVEL, F_EFFECT_MECHANIC, F_NAME, F_RANK, F_GCD, F_FAMILY = 39, 83, 136, 153, 206, 208
ATTR_PASSIVE = 0x40

MECHANICS = {0: "", 1: "charm", 2: "disorient", 3: "disarm", 4: "distract", 5: "fear", 7: "root", 9: "silence",
             10: "sleep", 11: "snare", 12: "stun", 14: "knockout", 17: "polymorph", 18: "banish", 20: "shield",
             21: "shackle", 24: "horror", 26: "invulnerability", 30: "sapped"}

FAMILY = {"Rogue": 8, "Priest": 6, "Warlock": 5, "Druid": 7}

ARENA_SPELLS = {
    "Rogue": ["Sap", "Cheap Shot", "Kidney Shot", "Blind", "Gouge", "Garrote", "Kick", "Dismantle", "Shadowstep",
              "Shadow Dance", "Premeditation", "Preparation", "Vanish", "Cloak of Shadows", "Evasion", "Sprint",
              "Hemorrhage", "Ambush", "Backstab", "Eviscerate", "Rupture", "Slice and Dice", "Feint",
              "Tricks of the Trade", "Distract", "Shiv"],
    "Priest": ["Psychic Scream", "Psychic Horror", "Silence", "Pain Suppression", "Power Word: Shield", "Penance",
               "Dispel Magic", "Mass Dispel", "Shadowfiend", "Mana Burn", "Fear Ward", "Inner Focus",
               "Power Infusion", "Desperate Prayer", "Flash Heal", "Prayer of Mending", "Renew", "Holy Nova",
               "Shadow Word: Pain", "Mind Control", "Shadow Word: Death"],
    "Warlock": ["Fear", "Howl of Terror", "Death Coil", "Unstable Affliction", "Haunt", "Corruption",
                "Curse of Agony", "Curse of Tongues", "Curse of Exhaustion", "Drain Life", "Shadow Bolt",
                "Shadowflame", "Demonic Circle: Summon", "Demonic Circle: Teleport", "Soulshatter", "Fel Domination",
                "Life Tap", "Drain Mana", "Seed of Corruption"],
    "Druid": ["Cyclone", "Entangling Roots", "Bash", "Nature's Grasp", "Innervate", "Barkskin", "Nature's Swiftness",
              "Rejuvenation", "Regrowth", "Lifebloom", "Wild Growth", "Swiftmend", "Nourish", "Healing Touch",
              "Tranquility", "Hibernate", "Faerie Fire", "Feral Charge - Bear", "Dash", "Abolish Poison",
              "Remove Curse"],
}


def read_dbc(path):
    data = Path(path).read_bytes()
    _, records, fields, size, _ = struct.unpack("<4s4I", data[:20])
    body = data[20:20 + records * size]
    strings = data[20 + records * size:]
    rows = [struct.unpack_from(f"<{fields}I", body, i * size) for i in range(records)]
    return rows, strings


def cstr(strings, offset):
    return strings[offset:strings.index(b"\0", offset)].decode("utf-8", "replace")


def as_float(u):
    return struct.unpack("<f", struct.pack("<I", u))[0]


def load(dbc_dir):
    spells, strings = read_dbc(f"{dbc_dir}/Spell.dbc")
    durations = {r[0]: r[1] for r in read_dbc(f"{dbc_dir}/SpellDuration.dbc")[0]}
    ranges = {r[0]: as_float(r[3]) for r in read_dbc(f"{dbc_dir}/SpellRange.dbc")[0]}  # maxHostile
    casts = {r[0]: r[1] for r in read_dbc(f"{dbc_dir}/SpellCastTimes.dbc")[0]}
    # SkillLineAbility: só magias que um jogador aprende (exclui variantes de NPC e efeitos disparados)
    learnable = {r[2] for r in read_dbc(f"{dbc_dir}/SkillLineAbility.dbc")[0]}
    spells = [r for r in spells if r[F_ID] in learnable]
    return spells, strings, durations, ranges, casts


def best_rank(spells, strings, name, family):
    """Rank jogável mais alto: mesma família, não passivo, maior spellLevel."""
    hits = [r for r in spells if r[F_FAMILY] == family and not r[F_ATTR] & ATTR_PASSIVE
            and cstr(strings, r[F_NAME]) == name]
    return max(hits, key=lambda r: (r[F_SPELL_LEVEL], -r[F_ID])) if hits else None


def describe(row, strings, durations, ranges, casts):
    mech = row[F_MECHANIC] or next((m for m in row[F_EFFECT_MECHANIC:F_EFFECT_MECHANIC + 3] if m), 0)
    dur = durations.get(row[F_DUR], 0)
    return {
        "id": row[F_ID],
        "rank": cstr(strings, row[F_RANK]),
        "cast_s": casts.get(row[F_CAST], 0) / 1000,
        "cd_s": max(row[F_CD], row[F_CATCD]) / 1000,
        "dur_s": dur / 1000 if dur > 0 else 0,
        "range_yd": ranges.get(row[F_RANGE], 0.0),
        "gcd_s": row[F_GCD] / 1000,
        "mechanic": MECHANICS.get(mech, str(mech)),
    }


def main(dbc_dir):
    spells, strings, durations, ranges, casts = load(dbc_dir)
    for cls, names in ARENA_SPELLS.items():
        print(f"\n### {cls}\n")
        print("| Habilidade | ID | Rank | Cast (s) | CD (s) | Duração (s) | Alcance (yd) | GCD (s) | Mecânica |")
        print("|---|---|---|---|---|---|---|---|---|")
        for name in names:
            row = best_rank(spells, strings, name, FAMILY[cls])
            if not row:
                print(f"| {name} | — | não encontrado | | | | | | |")
                continue
            d = describe(row, strings, durations, ranges, casts)
            print(f"| {name} | {d['id']} | {d['rank']} | {d['cast_s']:g} | {d['cd_s']:g} | {d['dur_s']:g} "
                  f"| {d['range_yd']:g} | {d['gcd_s']:g} | {d['mechanic']} |")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).resolve().parent.parent / "dbc"))
