USE acore_characters;
-- Pokastranca (1068): equipa as 4 pecas Hateful que estavam na mochila (bag 30014424 slots 0-3)
-- slot 5 <- 41068 Hateful Gladiator's Waistguard of Dominance
-- slot 7 <- 41073 Hateful Gladiator's Sabatons of Dominance
-- slot 8 <- 41047 Hateful Gladiator's Wristguards of Salvation
-- slot 11 <- 42110 Hateful Gladiator's Band of Dominance
CREATE TEMPORARY TABLE troca (slot TINYINT, item INT);
INSERT INTO troca VALUES (5,41068),(7,41073),(8,41047),(11,42110);
UPDATE item_instance ii
  JOIN character_inventory ci ON ci.item = ii.guid AND ci.guid = 1068 AND ci.bag = 0
  JOIN troca t ON t.slot = ci.slot
SET ii.itemEntry = t.item,
    ii.durability = (SELECT MaxDurability FROM acore_world.item_template w WHERE w.entry = t.item);
DELETE ci FROM character_inventory ci WHERE ci.guid = 1068 AND ci.bag = 30014424 AND ci.slot IN (0,1,2,3);
DELETE ii FROM item_instance ii WHERE ii.guid IN (30014412,30014414,30014415,30014417) AND ii.guid NOT IN (SELECT item FROM character_inventory);
SELECT ci.slot, it.name FROM character_inventory ci JOIN item_instance ii ON ii.guid=ci.item
  JOIN acore_world.item_template it ON it.entry=ii.itemEntry WHERE ci.guid=1068 AND ci.bag=0 AND ci.slot IN (5,7,8,11) ORDER BY ci.slot;
