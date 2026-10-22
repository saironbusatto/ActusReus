-- Trios: deixa cada família de clones novos com o MESMO equipamento (o do clone de referência), corrige Warrior/DK
-- (Savage Plate/Dreadplate + Hateful of Triumph) e garante o Medallion (trinket PvP) em todos. Worldserver PARADO.
-- Motivo: as sementes foram reequipadas a cada restart (o evento "fixedgear" não persistiu).
USE acore_characters;
CREATE TEMPORARY TABLE fam (id INT, rx VARCHAR(64), ref VARCHAR(12), horda TINYINT);
INSERT INTO fam VALUES
 (1,'^Hesho(ii|iv|v|vi)$','Heshoiv',1),(2,'^Kwongwega(ii|iv|v|vi)$','Kwongwegaiv',1),
 (3,'^Beteran(ii|iv|v|vi)$','Beteraniv',0),(4,'^Celianey(ii|iv|v|vi)$','Celianeyiv',0),
 (5,'^Omascon(ii|iv|v|vi)$','Omasconiv',0),(6,'^Heru(ii|iv|v|vi|vii|ix|x|xi)$','Heruiv',0),
 (7,'^Amnesian(xix|xxi|xxii|xxiv)$','Amnesianxxi',0);
CREATE TEMPORARY TABLE refitem AS
  SELECT f.id fam, ci.slot, ii.itemEntry, ii.enchantments, ii.durability
  FROM fam f JOIN characters c ON c.name = f.ref
  JOIN character_inventory ci ON ci.guid = c.guid AND ci.bag = 0 AND ci.slot < 19
  JOIN item_instance ii ON ii.guid = ci.item;
CREATE TEMPORARY TABLE membro AS
  SELECT c.guid, f.id fam, f.horda FROM characters c JOIN fam f ON c.name REGEXP f.rx WHERE c.guid NOT IN (1001,1044,1045);
SELECT COUNT(*) AS membros_esperados_32 FROM membro;

UPDATE item_instance ii JOIN character_inventory ci ON ci.item = ii.guid AND ci.bag = 0
  JOIN membro m ON m.guid = ci.guid JOIN refitem r ON r.fam = m.fam AND r.slot = ci.slot
SET ii.itemEntry = r.itemEntry, ii.enchantments = r.enchantments, ii.durability = r.durability;

CREATE TEMPORARY TABLE fix (fam INT, slot TINYINT, item INT);
INSERT INTO fix VALUES
 (4,0,40816),(4,1,42020),(4,2,40856),(4,4,40778),(4,5,40877),(4,6,40836),(4,7,40878),(4,8,40887),(4,9,40797),
 (4,10,42112),(4,14,42060),
 (5,0,40817),(5,1,42020),(5,2,40857),(5,4,40779),(5,5,40877),(5,6,40837),(5,7,40878),(5,8,40887),(5,9,40799),
 (5,10,42112),(5,14,42060);
UPDATE item_instance ii JOIN character_inventory ci ON ci.item = ii.guid AND ci.bag = 0
  JOIN membro m ON m.guid = ci.guid JOIN fix f ON f.fam = m.fam AND f.slot = ci.slot
SET ii.itemEntry = f.item, ii.durability = (SELECT MaxDurability FROM acore_world.item_template t WHERE t.entry = f.item);

-- Medallion: o de ilvl 200 da facção no slot 12 (o 13 fica com o melhor trinket que ele já tinha)
UPDATE item_instance ii JOIN character_inventory ci ON ci.item = ii.guid AND ci.bag = 0 AND ci.slot = 13
  JOIN membro m ON m.guid = ci.guid
  JOIN character_inventory c12 ON c12.guid = ci.guid AND c12.bag = 0 AND c12.slot = 12
  JOIN item_instance i12 ON i12.guid = c12.item
SET ii.itemEntry = i12.itemEntry WHERE ii.itemEntry IN (37864,37865,42122,42123,51377,51378);
UPDATE item_instance ii JOIN character_inventory ci ON ci.item = ii.guid AND ci.bag = 0 AND ci.slot = 12
  JOIN membro m ON m.guid = ci.guid
SET ii.itemEntry = IF(m.horda, 42122, 42123), ii.durability = 0;

SELECT m.fam, COUNT(DISTINCT g.items) AS variantes, COUNT(*) AS n, MIN(g.mn) ilvl_min, MAX(g.mx) ilvl_max
FROM membro m JOIN (SELECT ci.guid, GROUP_CONCAT(ii.itemEntry ORDER BY ci.slot) items, MIN(t.ItemLevel) mn, MAX(t.ItemLevel) mx
  FROM character_inventory ci JOIN item_instance ii ON ii.guid = ci.item JOIN acore_world.item_template t ON t.entry = ii.itemEntry
  WHERE ci.bag = 0 AND ci.slot < 19 AND ci.slot NOT IN (3, 18) GROUP BY ci.guid) g ON g.guid = m.guid GROUP BY m.fam;
