"""Gera os 48 clones e scripts para expandir o ecossistema de 60 bots (20 trios) para 108 bots (36 trios).

As 4 novas composições x 4 trios cada = 16 novos trios (48 bots):
  - Thunder Cleave (4x): Warrior Arms + Shaman Ele + Paladin Holy (Aliança)
  - Fireplay (4x): Mage Fire + Warlock Destro + Shaman Resto (Horda)
  - RPS (4x): Rogue Sub + Priest Shadow + Shaman Resto (Horda)
  - LSD (4x): Warlock Destro + Druid Balance (Boomkin) + Shaman Resto (Horda)

Uso:
  python3 ml/tools/gerar_expansao_108.py --dry-run
  python3 ml/tools/gerar_expansao_108.py --executar
"""
import argparse
import subprocess
import sys
from pathlib import Path

# Fontes dos clones (.pdump copy):
# guid -> (Nome base, spec desejada, lista de 4 nomes)
CLONES_NEEDED = [
    # Thunder Cleave (Aliança: Celianey, Kwongwega/Ele, Heru)
    (1063, "Celianey", "arms pvp", ["Celianeysete", "Celianeyoito", "Celianeynove", "Celianeydez"]),
    (1061, "Kwongwega", "ele pvp", ["Kwongelei", "Kwongeleii", "Kwongeleitr", "Kwongeleiv"]),
    (1065, "Heru", "holy pvp", ["Herudoze", "Herutreze", "Heruquatorze", "Heruquinze"]),
    
    # Fireplay (Horda: Hesho/Fire, Ominous/Destro, Kwongwega/Resto)
    (1060, "Hesho", "fire pvp", ["Heshofirei", "Heshofireii", "Heshofiretr", "Heshofireiv"]),
    (399, "Ominous", "destro pvp", ["Ominousdesi", "Ominousdesii", "Ominousdestr", "Ominousdesiv"]),
    (1061, "Kwongwega", "resto pvp", ["Kwongrestoi", "Kwongrestoii", "Kwongrestotr", "Kwongrestoiv"]),

    # RPS (Horda: Zebedeu/Sub, Amnesian/Shadow, Kwongwega/Resto)
    (304, "Zebedeu", "subtlety pvp", ["Zebedeudoz", "Zebedeutrez", "Zebedeuquat", "Zebedeuquin"]),
    (95, "Amnesian", "shadow pvp", ["Amnesianshi", "Amnesianshii", "Amnesianshtr", "Amnesianshiv"]),
    (1061, "Kwongwega", "resto pvp", ["Kwongrpsi", "Kwongrpsii", "Kwongrpstr", "Kwongrpsiv"]),

    # LSD (Horda: Ominous/Destro, Pehdicouve/Boomkin, Kwongwega/Resto)
    (399, "Ominous", "destro pvp", ["Ominouslsdi", "Ominouslsdii", "Ominouslsdtr", "Ominouslsdiv"]),
    (410, "Pehdicouve", "balance pvp", ["Pehdiboomi", "Pehdiboomii", "Pehdiboomtr", "Pehdiboomiv"]),
    (1061, "Kwongwega", "resto pvp", ["Kwonglsdi", "Kwonglsdii", "Kwonglsdtr", "Kwonglsdiv"]),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="Mostra o que sera feito sem alterar o banco")
    args = ap.parse_args()

    total_clones = sum(len(names) for _, _, _, names in CLONES_NEEDED)
    print(f"=== Expansão para 108 bots: {total_clones} novos clones (16 trios) ===")

    all_names = []
    for _, _, _, names in CLONES_NEEDED:
        for n in names:
            assert len(n) <= 12, f"Nome muito longo (>12): {n}"
            assert n[0].isupper() and n[1:].islower(), f"Formato inválido: {n}"
            all_names.append(n)
    assert len(all_names) == 48, f"Esperado 48, obtido {len(all_names)}"
    assert len(all_names) == len(set(all_names)), "Há nomes duplicados na lista!"

    print(f"Nomes validados com sucesso (48 nomes únicos, <= 12 chars).")

    # Gerar script SQL de criação dos times
    sql_path = Path("agente/trios-expansao-108.sql")
    linhas_sql = [
        "-- Expansão 108 Bots: Criar times 74 a 89 (16 novos trios 3v3)",
        "-- Thunder Cleave (74-77), Fireplay (78-81), RPS (82-85), LSD (86-89)",
        "USE acore_characters;",
        "CREATE TEMPORARY TABLE novos_trios (n INT, a VARCHAR(12), b VARCHAR(12), cap VARCHAR(12), team_name VARCHAR(24));",
        "INSERT INTO novos_trios VALUES",
        " -- Thunder Cleave (Aliança: War, Ele Sham, Holy Paladin cap)",
        " (1, 'Celianeysete', 'Kwongelei', 'Herudoze', 'Thunder I'),",
        " (2, 'Celianeyoito', 'Kwongeleii', 'Herutreze', 'Thunder II'),",
        " (3, 'Celianeynove', 'Kwongeleitr', 'Heruquatorze', 'Thunder III'),",
        " (4, 'Celianeydez', 'Kwongeleiv', 'Heruquinze', 'Thunder IV'),",
        " -- Fireplay (Horda: Fire Mage, Destro Lock, Resto Sham cap)",
        " (5, 'Heshofirei', 'Ominousdesi', 'Kwongrestoi', 'Fireplay I'),",
        " (6, 'Heshofireii', 'Ominousdesii', 'Kwongrestoii', 'Fireplay II'),",
        " (7, 'Heshofiretr', 'Ominousdestr', 'Kwongrestotr', 'Fireplay III'),",
        " (8, 'Heshofireiv', 'Ominousdesiv', 'Kwongrestoiv', 'Fireplay IV'),",
        " -- RPS (Horda: Sub Rogue, Shadow Priest, Resto Sham cap)",
        " (9, 'Zebedeudoz', 'Amnesianshi', 'Kwongrpsi', 'RPS I'),",
        " (10, 'Zebedeutrez', 'Amnesianshii', 'Kwongrpsii', 'RPS II'),",
        " (11, 'Zebedeuquat', 'Amnesianshtr', 'Kwongrpstr', 'RPS III'),",
        " (12, 'Zebedeuquin', 'Amnesianshiv', 'Kwongrpsiv', 'RPS IV'),",
        " -- LSD (Horda: Destro Lock, Boomkin Druid, Resto Sham cap)",
        " (13, 'Ominouslsdi', 'Pehdiboomi', 'Kwonglsdi', 'LSD I'),",
        " (14, 'Ominouslsdii', 'Pehdiboomii', 'Kwonglsdii', 'LSD II'),",
        " (15, 'Ominouslsdtr', 'Pehdiboomtr', 'Kwonglsdtr', 'LSD III'),",
        " (16, 'Ominouslsdiv', 'Pehdiboomiv', 'Kwonglsdiv', 'LSD IV');",
        "",
        "SET @base = 73; -- Último time atual é TSG IV (73)",
        "INSERT INTO arena_team (arenaTeamId, name, captainGuid, type, rating, backgroundColor, emblemStyle, emblemColor, borderStyle, borderColor)",
        "  SELECT @base + t.n, t.team_name, c.guid, 3, 1500, 4279401323, 35, 4292282831, 5, 4293808578",
        "  FROM novos_trios t JOIN characters c ON c.name = t.cap;",
        "INSERT INTO arena_team_member (arenaTeamId, guid, personalRating)",
        "  SELECT @base + t.n, c.guid, 1500 FROM novos_trios t JOIN characters c ON c.name IN (t.a, t.b, t.cap);",
        "REPLACE INTO character_arena_stats (guid, slot, matchMakerRating, maxMMR)",
        "  SELECT c.guid, 1, 1500, 1500 FROM novos_trios t JOIN characters c ON c.name IN (t.a, t.b, t.cap);",
        "UPDATE characters c JOIN novos_trios t ON c.name IN (t.a, t.b, t.cap) SET c.at_login = 0;",
        "UPDATE acore_playerbots.playerbots_random_bots SET value = 108 WHERE event = 'bot_count';",
        "SELECT 'OK: 16 novos trios configurados com sucesso' AS status;"
    ]
    sql_path.write_text("\n".join(linhas_sql) + "\n")
    print(f"Script SQL gerado com sucesso em: {sql_path}")


if __name__ == "__main__":
    main()
