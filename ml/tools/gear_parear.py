#!/usr/bin/env python3
"""Pareia o gear dos bots de arena classe a classe (e spec a spec).

Alvo por grupo = o item PvP que o próprio grupo já usa em maioria; onde o grupo
não tem PvP no slot, usa o item PvP do catálogo (Hateful/Savage/Titan-Forged 200).
Gemas e encantos vão por consenso (moda campo a campo) de quem já veste o item alvo,
com presets para itens novos ou normalizados.

Uso:
    python3 ml/tools/gear_parear.py            # relatório (dry-run)
    python3 ml/tools/gear_parear.py --aplica   # gera agente/parear-gear.sql
"""
import collections
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "ml" / "policy"))
from espelho import sql

CLS = {1: "warrior", 2: "paladin", 3: "hunter", 4: "rogue", 5: "priest", 6: "dk", 7: "shaman",
       8: "mage", 9: "warlock", 11: "druid"}
FAM = ["Dreadplate", "Ornamented", "Scaled", "Plate", "Chain", "Linked", "Mail", "Ringmail",
       "Leather", "Dragonhide", "Kodohide", "Wyrmhide", "Mooncloth", "Satin", "Silk", "Felweave"]
EXCLUIR = {"Reload"}
SLOTS = (0, 1, 2, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17)
SLOT_NOME = {0: "cabeça", 1: "pescoço", 2: "ombro", 4: "peito", 5: "cintura", 6: "pernas", 7: "pés",
             8: "pulso", 9: "mãos", 10: "anel1", 11: "anel2", 12: "trinket", 13: "trinket2",
             14: "costas", 15: "arma", 16: "off-hand", 17: "dist/relíquia"}
G = {"war/plate": (1, "Plate"), "pal/holy": (2, "Ornamented"), "hunt/chain": (3, "Chain"),
     "rog/leather": (4, "Leather"), "prst/heal": (5, "Mooncloth"), "prst/shadow": (5, "Satin"),
     "dk": (6, "Dreadplate"), "sham/resto": (7, "Ringmail"), "sham/ele": (7, "Mail"),
     "mage": (8, "Silk"), "lock": (9, "Felweave"),
     "druid/resto": (11, "Kodohide"), "druid/balance": (11, "Wyrmhide")}

RESTO_SHAMANS = {
    "Kwongwegaii", "Kwongwegaiv", "Pokastranca", "Bovinus", "Kwongwegavi",
    "Kwongwegavii", "Kwongwegaix", "Kwongwegax", "Kwongwegaxi",
    "Kwongwegaxii", "Kwongwegaxiv", "Kwongwegaxv", "Kwongwegaxvi"
}

# alvos onde o grupo NÃO tem PvP em maioria (ou precisa de um item novo / remoção de off-hand)
EXTRA = {
    "war/plate":    {11: 45809, 13: 40684, 16: None},                          # Scarlet Signet; Mirror of Truth; 2H Pike
    "pal/holy":     {1: 42026, 7: 40973, 9: 40925, 10: 42110, 11: 45808, 16: 42558, 17: 42613}, # Salvation; Greaves; Gloves; Dominance; Runed Mana; Shield; Libram Justice
    "hunt/chain":   {0: 41155, 9: 41141, 11: 45809, 16: None},                 # Chain Helm/Gauntlets; Scarlet Signet; 2H Sword
    "rog/leather":  {11: 45809},                                               # Scarlet Signet
    "prst/heal":    {10: 42110, 11: 45808, 15: 42351, 16: 42530, 17: 42501},   # Dominance; Runed Mana; Gavel + Reprieve + Touch of Defeat
    "prst/shadow":  {4: 41919, 6: 41925, 9: 41938, 10: 42110, 11: 45808, 16: None}, # 5/5 Satin; Dominance; Runed Mana; 2H Focus Staff
    "dk":           {0: 40817, 11: 45809},                                     # Savage Helm (5/5); Scarlet Signet
    "sham/resto":   {0: 41011, 1: 42026, 2: 41036, 4: 40988, 5: 41050, 6: 41025, 7: 41049,
                     8: 41047, 9: 40999, 10: 42110, 11: 45808, 13: 40685, 14: 42058, 15: 42351, 16: 42558, 17: 42596}, # Full Ringmail/Salvation, Gavel + Shield Wall, Totem Third Wind
    "sham/ele":     {0: 41017, 2: 41042, 4: 40989, 5: 41068, 6: 41031, 7: 41073, 8: 41063,
                     9: 41005, 10: 42110, 11: 45808, 13: 40685, 15: 44417, 16: None, 17: 42601}, # Full Mail/Dominance, Runed Mana, War Staff 2H, Totem Survival
    "mage":         {0: 41944, 1: 42024, 4: 41950, 7: 41901, 10: 42110, 11: 45808, 16: None}, # 5/5 Silk, Dominance, Runed Mana, 2H Staff
    "lock":         {7: 41901, 10: 42110, 11: 45808},                          # Slippers; Dominance; Runed Mana Band
    "druid/resto":  {10: 42110, 11: 45808, 15: 42351, 16: 42530, 17: 42577},   # Dominance; Runed Mana; Gavel + Reprieve; Idol of Tenacity
    "druid/balance":{4: 41314, 6: 41302, 7: 41633, 10: 42110, 11: 45808, 16: None, 17: 42582}, # 5/5 Wyrmhide, Dominance, Runed Mana, Idol Steadfastness, 2H Staff
}

# Presets de enchantments para peças novas ou sem consenso prévio
PRESET_ENCH = {
    41155: "3817 0 0 0 0 0 3628 0 0 3519 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 ", # Chain Helm
    41141: "3222 0 0 0 0 0 3447 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 ",     # Chain Gauntlets
    41314: "3832 0 0 0 0 0 3560 0 0 3580 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 ", # Wyrmhide Robes
    41302: "3872 0 0 0 0 0 3520 0 0 3520 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 ", # Wyrmhide Legguards
    41633: "3826 0 0 0 0 0 3560 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 ",     # Wyrmhide Boots
    41944: "3820 0 0 0 0 0 3621 0 0 3520 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 ", # Silk Cowl
    41919: "3832 0 0 0 0 0 3560 0 0 3580 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 ", # Satin Robe
    41925: "3872 0 0 0 0 0 3520 0 0 3520 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 ", # Satin Leggings
    41938: "3246 0 0 0 0 0 3520 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 ",     # Satin Gloves
    40973: "3826 0 0 0 0 0 3558 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 ",     # Greaves of Salvation
    41011: "3820 0 0 0 0 0 3621 0 0 3520 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 ", # Ringmail Helm
    41036: "3811 0 0 0 0 0 3520 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 ",     # Ringmail Spaulders
    40988: "3832 0 0 0 0 0 3520 0 0 3580 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 ", # Ringmail Armor
    41025: "3872 0 0 0 0 0 3520 0 0 3520 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 ", # Ringmail Leggings
    40999: "3246 0 0 0 0 0 3520 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 ",     # Ringmail Gauntlets
    41049: "3826 0 0 0 0 0 3520 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 ",     # Sabatons Salvation
    41047: "3845 0 0 0 0 0 3520 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 ",     # Wristguards Salvation
    41050: "0 0 0 0 0 0 3520 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 ",         # Waistguard Salvation
    42058: "3831 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 ",         # Cloak Salvation
    42351: "3834 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 ",         # Gavel
    42558: "1128 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 ",         # Shield Wall
    42596: "0 " * 36,                                                                               # Totem Third Wind
    45808: "0 " * 36,                                                                               # Runed Mana Band
    45809: "0 " * 36,                                                                               # Scarlet Signet
}

PVP = ("Hateful Gladiator", "Savage Gladiator", "Titan-Forged")

rows = sql("""
SELECT c.name, c.class, c.race, ci.slot, ii.itemEntry, ii.enchantments, it.name, it.ItemLevel,
       it.stat_type1,it.stat_value1,it.stat_type2,it.stat_value2,it.stat_type3,it.stat_value3,
       it.stat_type4,it.stat_value4,it.stat_type5,it.stat_value5
FROM acore_characters.character_inventory ci
JOIN acore_characters.item_instance ii ON ii.guid = ci.item
JOIN acore_world.item_template it ON it.entry = ii.itemEntry
JOIN acore_characters.characters c ON c.guid = ci.guid
WHERE ci.bag = 0 AND ci.slot <= 18
  AND c.guid IN (SELECT guid FROM acore_characters.arena_team_member WHERE arenaTeamId BETWEEN 54 AND 89)
ORDER BY c.name, ci.slot""")

bots, ench_de, ench_grp = {}, {}, {}
for r in rows:
    nome, cls, race, slot, entry, ench, inome, ilvl, *sv = r
    if nome in EXCLUIR:
        continue
    slot, entry, race = int(slot), int(entry), int(race)
    res = sum(int(sv[i + 1]) for i in range(0, len(sv), 2) if sv[i] and int(sv[i]) == 35)
    d = bots.setdefault(nome, {"cls": int(cls), "race": race, "it": {}})
    d["it"][slot] = {"entry": entry, "ench": ench or "", "nome": inome,
                     "pvp": inome.startswith(PVP) or res > 0 or "Medallion" in inome}


def fam(n):
    h = bots[n]["it"].get(0, {}).get("nome", "")
    return next((f for f in FAM if f" {f} " in h), None)


def grupo(n):
    c, h = bots[n]["cls"], fam(n)
    if c == 7:
        return "sham/resto" if n in RESTO_SHAMANS else "sham/ele"
    if c == 5:
        return "prst/shadow" if h == "Satin" else "prst/heal"
    if c == 11:
        return "druid/balance" if h == "Wyrmhide" else "druid/resto"
    for g, (cc, ff) in G.items():
        if cc == c:
            return g
    return None


for n, d in bots.items():
    grp = grupo(n)
    for s, it in d["it"].items():
        e = it["entry"]
        ench_de.setdefault(e, []).append(it["ench"])
        ench_grp.setdefault((grp, e), []).append(it["ench"])


def normaliza(e):
    v = [x for x in (e or "").split()]
    arr = (v + ["0"] * 36)[:36] if len(v) <= 36 else v[:36]
    # Ignora TEMP_ENCHANTMENT_SLOT (índices 3, 4, 5) que variam a cada milissegundo por buffs de classe
    arr[3] = arr[4] = arr[5] = "0"
    return arr


def consenso(grp, entry):
    """Enchantments consensuais (moda campo a campo) com suporte a presets e fallback."""
    if grp == "war/plate" and entry in (42112, 45809):
        return "3839 " + "0 " * 35  # Warrior Enchanting +44 AP no anel
    if entry in PRESET_ENCH:
        return PRESET_ENCH[entry]
    nums = [normaliza(e) for e in ench_grp.get((grp, entry), [])]
    if not nums:
        nums = [normaliza(e) for e in ench_de.get(entry, [])]
    out = []
    for i in range(36):
        vals = [n[i] for n in nums if n[i] not in ("0", "")]
        out.append(collections.Counter(vals).most_common(1)[0][0] if vals else "0")
    return " ".join(out)


def alvo(g):
    """Entry alvo por slot: moda PvP do grupo, com EXTRA por cima."""
    (cl, _), membros = G[g], [n for n in bots if grupo(n) == g]
    out = {}
    for s in SLOTS:
        if s == 12:                     # Medallion tratado por facção
            continue
        if s == 13:                     # Trinket 2: PvE sem Medallion
            c = collections.Counter(bots[n]["it"][s]["entry"] for n in membros if s in bots[n]["it"]
                                    and "Medallion" not in bots[n]["it"][s]["nome"])
            if c:
                out[s] = c.most_common(1)[0][0]
            continue
        c = collections.Counter(bots[n]["it"][s]["entry"] for n in membros if s in bots[n]["it"])
        ok = set(e for e, _ in c.items()
                 for n in membros if s in bots[n]["it"] and bots[n]["it"][s]["entry"] == e
                 and bots[n]["it"][s]["pvp"])
        pvp = [(e, k) for e, k in c.items() if e in ok]
        if pvp:
            out[s] = max(pvp, key=lambda x: (x[1], x[0]))[0]
    out.update(EXTRA.get(g, {}))
    return out, membros


total, por_grupo = [], {}
for g in G:
    T, membros = alvo(g)
    ch = collections.Counter()
    for n in membros:
        race = bots[n]["race"]
        # Slot 12 Medallion normalizado por facção
        medallion_entry = 42123 if race in (1, 3, 4, 7, 11) else 42122
        cur12 = bots[n]["it"].get(12)
        if not cur12 or cur12["entry"] != medallion_entry:
            total.append((n, 12, medallion_entry, "0 " * 36))
            ch[(12, "item")] += 1

        for s, t in T.items():
            cur = bots[n]["it"].get(s)
            if t is None:
                if cur:
                    total.append((n, s, None))
                    ch[(s, "remover off-hand")] += 1
                continue
            novo = consenso(g, t)
            if not cur or cur["entry"] != t or normaliza(cur.get("ench")) != normaliza(novo):
                total.append((n, s, t, novo))
                ch[(s, "item" if (not cur or cur["entry"] != t) else "gema/encanto")] += 1
    por_grupo[g] = (membros, T, ch)

for g, (membros, T, ch) in por_grupo.items():
    print(f"\n### {g} — {len(membros)} bots")
    for s in SLOTS:
        if s == 12:
            dev = [(k[1], v) for k, v in ch.items() if k[0] == s]
            print(f"   {s:>2} {SLOT_NOME[s]:13} Medallion (42122 H / 42123 A)        " + (f"  [{', '.join(f'{t} {v}' for t, v in dev)}]" if dev else "  (ok)"))
            continue
        if s not in T:
            continue
        alvo_nome = "—" if T[s] is None else sql(f"SELECT name FROM acore_world.item_template WHERE entry={T[s]}")[0][0]
        dev = [(k[1], v) for k, v in ch.items() if k[0] == s]
        print(f"   {s:>2} {SLOT_NOME[s]:13} {alvo_nome:45}" + (f"  [{', '.join(f'{t} {v}' for t, v in dev)}]" if dev else "  (ok)"))

print(f"\nTOTAL: {len(total)} operações em {len({t[0] for t in total})} bots")

if "--aplica" in sys.argv:
    lines = []
    for entry in total:
        if len(entry) == 4 and entry[2] is not None:
            n, s, item, ench = entry
            lines.append(f"('{n}',{s},{item},'{ench}')")
        else:
            n, s = entry[0], entry[1]
            lines.append(f"('{n}',{s},NULL,'')")
    vals = ",\n".join(lines)
    out_file = REPO / "agente" / "parear-gear.sql"
    out_file.write_text(f"""USE acore_characters;
CREATE TEMPORARY TABLE p (nome VARCHAR(12), slot TINYINT, item INT NULL, ench VARCHAR(400));
INSERT INTO p VALUES
{vals};

-- Move escudo da bolsa (slot 31) para slot 16 caso o slot 16 esteja desequipado
UPDATE character_inventory ci
JOIN characters c ON c.guid = ci.guid
JOIN p ON p.nome = c.name AND p.slot = 16
LEFT JOIN character_inventory ci16 ON ci16.guid = c.guid AND ci16.bag = 0 AND ci16.slot = 16
SET ci.slot = 16
WHERE ci.bag = 0 AND ci.slot = 31 AND ci16.item IS NULL AND p.item IS NOT NULL;

-- Restaura itens que foram para a mailbox (ex: slot 11 ou 16)
INSERT INTO character_inventory (guid, bag, slot, item)
SELECT c.guid, 0, p.slot, box.item_guid
FROM p
JOIN characters c ON c.name = p.nome
JOIN (
    SELECT m.receiver, MAX(mi.item_guid) AS item_guid
    FROM mail m
    JOIN mail_items mi ON mi.mail_id = m.id
    GROUP BY m.receiver
) box ON box.receiver = c.guid
LEFT JOIN character_inventory ci ON ci.guid = c.guid AND ci.bag = 0 AND ci.slot = p.slot
WHERE ci.item IS NULL AND p.item IS NOT NULL;

DELETE mi FROM mail_items mi
JOIN character_inventory ci ON ci.item = mi.item_guid;

DELETE m FROM mail m
LEFT JOIN mail_items mi ON mi.mail_id = m.id
WHERE mi.item_guid IS NULL AND m.subject = 'Inventory Full';

-- Atualiza equipamentos no inventário
UPDATE item_instance ii
  JOIN character_inventory ci ON ci.item = ii.guid AND ci.bag = 0
  JOIN characters c ON c.guid = ci.guid
  JOIN p ON p.nome = c.name AND p.slot = ci.slot
  SET ii.itemEntry = p.item, ii.enchantments = p.ench,
      ii.durability = (SELECT MaxDurability FROM acore_world.item_template t WHERE t.entry = p.item)
  WHERE p.item IS NOT NULL;

-- Remove itens em slots marcados para desequipar (ex: off-hand de armas 2H)
DELETE ii, ci FROM character_inventory ci
  JOIN item_instance ii ON ii.guid = ci.item
  JOIN characters c ON c.guid = ci.guid
  JOIN p ON p.nome = c.name AND p.slot = ci.slot
  WHERE p.item IS NULL AND ci.bag = 0;

-- Glifos PvP de Subtlety Rogue para o char do usuario (Reload, guid 1045)
INSERT INTO character_glyphs (guid, talentGroup, glyph1, glyph2, glyph3, glyph4, glyph5, glyph6)
VALUES (1045, 0, 405, 464, 469, 716, 468, 408)
ON DUPLICATE KEY UPDATE glyph1=405, glyph2=464, glyph3=469, glyph4=716, glyph5=468, glyph6=408;

INSERT INTO character_glyphs (guid, talentGroup, glyph1, glyph2, glyph3, glyph4, glyph5, glyph6)
VALUES (1045, 1, 405, 464, 469, 716, 468, 408)
ON DUPLICATE KEY UPDATE glyph1=405, glyph2=464, glyph3=469, glyph4=716, glyph5=468, glyph6=408;
""")
    print(f"SQL -> {out_file}")
