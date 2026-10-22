-- Expansão 108: corrige as 5 sementes novas para o padrão ilvl 200 PvP dos outros trios, antes de cloná-las.
-- Fire Mage: Savage Silk + Hateful of Dominance no lugar dos Frostsavage 187. Destro Lock: Felweave no lugar do capuz
-- de cura e das luvas Frostsavage. Shadow Priest: botas de Dominance no lugar das de cura. Medallion de ilvl 200 da
-- facção no slot 12 de todas (Horda 42122, Aliança 42123). Encantos/gemas ficam. Rodar com o worldserver PARADO.
USE acore_characters;
CREATE TEMPORARY TABLE fix (nome VARCHAR(12), slot TINYINT, item INT);
INSERT INTO fix VALUES
 ('Heshovii',0,41943),('Heshovii',4,41949),('Heshovii',7,41901),('Heshovii',8,41907),('Heshovii',9,41968),
 ('Heshovii',12,42122),
 ('Ominousdes',0,41990),('Ominousdes',9,42014),('Ominousdes',12,42122),
 ('Amnesianix',7,41901),('Amnesianix',12,42122),
 ('Naminii',12,42123),
 ('Pehdicouv',12,42122);
UPDATE item_instance ii
  JOIN character_inventory ci ON ci.item = ii.guid AND ci.bag = 0
  JOIN characters c ON c.guid = ci.guid
  JOIN fix f ON f.nome = c.name AND f.slot = ci.slot
SET ii.itemEntry = f.item, ii.durability = (SELECT MaxDurability FROM acore_world.item_template t WHERE t.entry = f.item);
SELECT c.name, MIN(t.ItemLevel) mn, MAX(t.ItemLevel) mx, SUM(t.name LIKE '%Gladiator%') glad,
       SUM(ii.itemEntry IN (42122, 42123)) medallion
FROM characters c JOIN character_inventory ci ON ci.guid = c.guid AND ci.bag = 0 AND ci.slot < 19 AND ci.slot NOT IN (3, 18)
JOIN item_instance ii ON ii.guid = ci.item JOIN acore_world.item_template t ON t.entry = ii.itemEntry
WHERE c.name IN ('Naminii', 'Heshovii', 'Ominousdes', 'Amnesianix', 'Pehdicouv') GROUP BY c.name;
