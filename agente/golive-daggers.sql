-- Sub de 2009: troca as espadas dos 15 Zebedeu por adagas do mesmo nível (ilvl 200, temporada Hateful).
-- MH Hateful Gladiator's Shanker (1.8, Ambush/Backstab), OH Hateful Gladiator's Shiv (1.4). Mantém encantamentos.
-- Rodar com o worldserver PARADO.
USE acore_characters;
UPDATE item_instance ii
  JOIN character_inventory ci ON ci.item = ii.guid AND ci.bag = 0
  JOIN characters c ON c.guid = ci.guid AND c.name REGEXP '^Zebedeu'
SET ii.itemEntry = IF(ci.slot = 15, 42241, 42247),
    ii.durability = IF(ci.slot = 15, (SELECT MaxDurability FROM acore_world.item_template WHERE entry = 42241),
                                     (SELECT MaxDurability FROM acore_world.item_template WHERE entry = 42247))
WHERE ci.slot IN (15, 16);
SELECT c.name, ci.slot, ii.itemEntry FROM characters c JOIN character_inventory ci ON ci.guid = c.guid AND ci.bag = 0 AND ci.slot IN (15,16)
  JOIN item_instance ii ON ii.guid = ci.item WHERE c.name REGEXP '^Zebedeu' ORDER BY c.name, ci.slot;
