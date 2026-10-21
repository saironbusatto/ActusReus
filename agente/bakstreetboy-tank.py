# Gera agente/bakstreetboy-tank.sql: DK Bakstreetboy (guid 1044) nível 80, T10 heroico (Sanctified 277) + BiS tank ICC/RS,
# gemas e encantamentos. Reaproveita os guids dos itens equipados; slots vazios ganham guids NOVO_GUID+n.
# Rodar só com o personagem OFFLINE (o UPDATE checa online=0).
GUID, NOVO_GUID = 1044, 30000000  # ponytail: guid fixo bem acima do gerador (~9.1M); recalcular se MAX(guid) chegar perto
GEMA = {1: 3637, 2: 3537, 4: 3575, 8: 3532}  # cor do encaixe -> enchant da gema (Austere, Shifting Dreadstone, Enduring Eye of Zul, Solid Majestic Zircon)
# slot: (item, cores dos encaixes, bônus de encaixe, encantamento permanente, durabilidade)
ITENS = {
    0: (51306, [1, 2], 3766, 3818, 100),   # Faceguard + Arcanum of the Stalwart Protector
    1: (50682, [2], 2868, 0, 0),           # Bile-Encrusted Medallion
    2: (51309, [2], 2868, 3811, 100),      # Pauldrons + Greater Inscription of the Pinnacle
    4: (51305, [2, 8], 3307, 3832, 165),   # Chestguard + Powerful Stats
    5: (50691, [2, 8], 3307, 0, 55),       # Belt of Broken Bones + Eternal Belt Buckle (abaixo)
    6: (51308, [4, 8], 3307, 3822, 120),   # Legguards + Frosthide Leg Armor
    7: (54579, [8, 8], 3307, 3232, 75),    # Treads of Impending Resurrection + Tuskarr's Vitality
    8: (50611, [4], 2868, 3850, 55),       # Bracers of Dark Reckoning + Major Stamina
    9: (51307, [4], 2868, 3253, 55),       # Handguards + Armsman
    10: (50642, [2], 2868, 0, 0),          # Juggernaut Band
    11: (50622, [2], 2868, 0, 0),          # Devium's Eternally Cold Ring
    12: (54591, [], 0, 0, 0),              # Petrified Twilight Scale
    13: (50364, [], 0, 0, 0),              # Sindragosa's Flawless Fang
    14: (50718, [4], 2868, 3294, 0),       # Royal Crimson Cloak + Mighty Armor
    15: (49623, [2, 2, 2], 3312, 3847, 145),  # Shadowmourne + Rune of the Stoneskin Gargoyle
    17: (50462, [], 0, 0, 0),              # Sigil of the Bone Gryphon
}
BUCKLE, GEMA_PRISMA = 3729, 3532

def enchants(slot, cores, bonus, perm):
    e = [0] * 36  # 12 slots x (id, duração, cargas): 0 perm, 2-4 encaixes, 5 bônus, 6 prismático
    e[0] = perm
    for i, c in enumerate(cores):
        e[(2 + i) * 3] = GEMA[c]
    if bonus:  # toda gema casa a cor do encaixe -> bônus ativo
        e[5 * 3] = bonus
    if slot == 5:
        e[6 * 3] = BUCKLE
        e[(2 + len(cores)) * 3] = GEMA_PRISMA
    return ' '.join(map(str, e)) + ' '

out = [
    "USE acore_characters;",
    "START TRANSACTION;",
    f"SELECT IF(online=0,'OK offline','PARE: online') FROM characters WHERE guid={GUID};",
    f"UPDATE characters SET level=80, xp=0 WHERE guid={GUID} AND online=0;",
    "CREATE TEMPORARY TABLE eq (slot TINYINT PRIMARY KEY, item INT, ench TEXT, dur INT);",
    "INSERT INTO eq VALUES " + ",\n ".join(
        f"({s},{it},'{enchants(s, c, b, p)}',{d})" for s, (it, c, b, p, d) in ITENS.items()) + ";",
    # slots já ocupados: troca o item no mesmo guid
    f"""UPDATE item_instance ii JOIN character_inventory ci ON ci.item=ii.guid AND ci.guid={GUID} AND ci.bag=0
JOIN eq ON eq.slot=ci.slot SET ii.itemEntry=eq.item, ii.enchantments=eq.ench, ii.durability=eq.dur, ii.flags=1,
ii.count=1, ii.randomPropertyId=0 WHERE ii.owner_guid={GUID};""",
    # slots vazios: item novo
    f"""INSERT INTO item_instance (guid,itemEntry,owner_guid,creatorGuid,giftCreatorGuid,count,duration,charges,flags,enchantments,randomPropertyId,durability,playedTime,text)
SELECT {NOVO_GUID}+eq.slot,eq.item,{GUID},0,0,1,0,'0 0 0 0 0 ',1,eq.ench,0,eq.dur,0,'' FROM eq
WHERE eq.slot NOT IN (SELECT slot FROM character_inventory WHERE guid={GUID} AND bag=0);""",
    f"""INSERT INTO character_inventory (guid,bag,slot,item)
SELECT {GUID},0,eq.slot,{NOVO_GUID}+eq.slot FROM eq
WHERE eq.slot NOT IN (SELECT slot FROM character_inventory WHERE guid={GUID} AND bag=0);""",
    f"""SELECT ci.slot, t.name, t.ItemLevel, ii.enchantments FROM character_inventory ci JOIN item_instance ii ON ii.guid=ci.item
JOIN acore_world.item_template t ON t.entry=ii.itemEntry WHERE ci.guid={GUID} AND ci.bag=0 AND ci.slot<19 ORDER BY ci.slot;""",
    "COMMIT;",
]
open(__file__.replace('.py', '.sql'), 'w').write('\n'.join(out) + '\n')
