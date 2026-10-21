-- Engineering 450 (Grand Master) para os 60 bots de arena e Hyperspeed Accelerators nas luvas (encantamento 3604,
-- que em 3.3.5 ocupa o slot permanente da luva). As bombas (Cobalt Frag Bomb) são repostas pelo próprio servidor.
-- Rodar com o worldserver PARADO. Nunca toca no Ominousy (guid 1001).
USE acore_characters;

CREATE TEMPORARY TABLE alvo AS
  SELECT guid FROM characters
  WHERE name REGEXP '^(Zebedeu|Amnesian|Ominous|Pehdicou)(ve|ii|tres|iv|v|vi|vii|ix|x|xi|xii|xiv|xv|xvi|xvii|xix)?$'
    AND guid <> 1001;

SELECT COUNT(*) AS bots_alvo, SUM(guid = 1001) AS ominousy_incluido FROM alvo;

INSERT INTO character_skills (guid, skill, value, max)
  SELECT guid, 202, 450, 450 FROM alvo
  ON DUPLICATE KEY UPDATE value = 450, max = 450;

INSERT IGNORE INTO character_spell (guid, spell, specMask)
  SELECT guid, 51306, 255 FROM alvo;

UPDATE item_instance ii
  JOIN character_inventory ci ON ci.item = ii.guid AND ci.bag = 0 AND ci.slot = 9
  JOIN alvo a ON a.guid = ci.guid
SET ii.enchantments = CONCAT('3604 0 0 ', SUBSTRING(ii.enchantments, LENGTH(SUBSTRING_INDEX(ii.enchantments, ' ', 3)) + 2));

SELECT
  (SELECT COUNT(*) FROM character_skills s JOIN alvo a USING(guid) WHERE s.skill = 202 AND s.value = 450) AS com_engenharia,
  (SELECT COUNT(*) FROM item_instance ii JOIN character_inventory ci ON ci.item = ii.guid AND ci.bag = 0 AND ci.slot = 9
     JOIN alvo a ON a.guid = ci.guid WHERE ii.enchantments LIKE '3604 %') AS luvas_hyperspeed;
