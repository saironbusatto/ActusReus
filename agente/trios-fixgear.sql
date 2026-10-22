-- Trios: corrige as sementes que o autogear do playerbots equipou fora do padrão ilvl 200 PvP dos bots de arena.
-- Warrior (Celianeyii) e DK (Omasconii) ganharam azuis PvE: troca por Savage Plate/Dreadplate + Hateful of Triumph.
-- Medallion ilvl 264 (51377/51378) volta para o de ilvl 200 (42123 Aliança / 42122 Horda).
-- Encantos/gemas do item antigo ficam. Rodar com o worldserver PARADO. Só toca nas 7 sementes pelo nome.
USE acore_characters;
CREATE TEMPORARY TABLE fix (nome VARCHAR(12), slot TINYINT, item INT);
INSERT INTO fix VALUES
 ('Celianeyii',0,40816),('Celianeyii',1,42020),('Celianeyii',2,40856),('Celianeyii',4,40778),('Celianeyii',5,40877),
 ('Celianeyii',6,40836),('Celianeyii',7,40878),('Celianeyii',8,40887),('Celianeyii',9,40797),('Celianeyii',10,42112),
 ('Celianeyii',12,42123),('Celianeyii',14,42060),
 ('Omasconii',2,40857),('Omasconii',7,40878),('Omasconii',8,40887),('Omasconii',10,42112),('Omasconii',12,42123),
 ('Omasconii',14,42060);
UPDATE item_instance ii
  JOIN character_inventory ci ON ci.item = ii.guid AND ci.bag = 0
  JOIN characters c ON c.guid = ci.guid
  JOIN fix f ON f.nome = c.name AND f.slot = ci.slot
SET ii.itemEntry = f.item, ii.durability = (SELECT MaxDurability FROM acore_world.item_template t WHERE t.entry = f.item);
UPDATE item_instance ii
  JOIN character_inventory ci ON ci.item = ii.guid AND ci.bag = 0 AND ci.slot IN (12, 13)
  JOIN characters c ON c.guid = ci.guid AND c.name IN ('Beteranii','Heshoii','Kwongwegaii','Heruii','Amnesianxix')
SET ii.itemEntry = IF(ii.itemEntry = 51377, 42123, 42122)
WHERE ii.itemEntry IN (51377, 51378);
SELECT c.name, MIN(t.ItemLevel) mn, MAX(t.ItemLevel) mx, SUM(t.name LIKE '%Gladiator%') glad
FROM characters c JOIN character_inventory ci ON ci.guid=c.guid AND ci.bag=0 AND ci.slot<19 AND ci.slot NOT IN (3,18)
JOIN item_instance ii ON ii.guid=ci.item JOIN acore_world.item_template t ON t.entry=ii.itemEntry
WHERE c.name IN ('Heshoii','Kwongwegaii','Beteranii','Celianeyii','Omasconii','Heruii','Amnesianxix') GROUP BY c.name;
