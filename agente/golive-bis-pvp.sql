-- BiS PvP ilvl 200 (temporada Hateful, 2009) para os bots de arena. Mantém o set Savage de 5 peças
-- e troca as peças PvE fora do set pelas off-set Hateful, mais o Medallion (trinket PvP, por facção).
-- Encantamentos/gemas das peças antigas são mantidos no item novo. Rodar com o worldserver PARADO.
-- Nunca toca no Ominousy (guid 1001, personagem do usuário): lista exata de sufixos + guid excluído.
USE acore_characters;

CREATE TEMPORARY TABLE bis (classe TINYINT, slot TINYINT, item INT);  -- item 0 = Medallion pela facção
INSERT INTO bis VALUES
 -- Rogue Sub: Triumph (agilidade), adagas, Medallion no lugar do Incisor Fragment
 (4,1,42020),(4,5,41827),(4,7,41828),(4,8,41830),(4,10,42112),(4,14,42060),(4,12,0),
 (4,15,42241),(4,16,42247),(4,17,42449),
 -- Priest Disc: Salvation (cura), Medallion no lugar do Meteorite Whetstone
 (5,1,42026),(5,5,41877),(5,7,41879),(5,8,41878),(5,14,42058),(5,12,0),
 -- Warlock Affli: Dominance (spell), Band no lugar do anel 187, Medallion no lugar do Mark of the War Prisoner
 (9,1,42022),(9,5,41896),(9,7,41901),(9,8,41907),(9,11,42110),(9,14,42055),(9,13,0),
 -- Druid Resto: Salvation (couro de cura), Medallion no lugar do Meteorite Whetstone
 (11,1,42026),(11,5,41330),(11,7,41331),(11,8,41332),(11,14,42058),(11,12,0);

CREATE TEMPORARY TABLE alvo AS
  SELECT guid, class, race FROM characters
  WHERE name REGEXP '^(Zebedeu|Amnesian|Ominous|Pehdicou)(ve|ii|tres|iv|v|vi|vii|ix|x|xi|xii|xiv|xv|xvi|xvii|xix)?$'
    AND guid <> 1001;

SELECT COUNT(*) AS bots_alvo, SUM(guid = 1001) AS ominousy_incluido FROM alvo;

UPDATE item_instance ii
  JOIN character_inventory ci ON ci.item = ii.guid AND ci.bag = 0
  JOIN alvo a ON a.guid = ci.guid
  JOIN bis b ON b.classe = a.class AND b.slot = ci.slot
SET ii.itemEntry = IF(b.item = 0, IF(a.race IN (1,3,4,7,11), 42123, 42122), b.item),
    ii.durability = (SELECT MaxDurability FROM acore_world.item_template t
                     WHERE t.entry = IF(b.item = 0, IF(a.race IN (1,3,4,7,11), 42123, 42122), b.item));

SELECT a.class, ci.slot, t.name, COUNT(*) n FROM alvo a
  JOIN character_inventory ci ON ci.guid = a.guid AND ci.bag = 0 AND ci.slot < 19
  JOIN item_instance ii ON ii.guid = ci.item JOIN acore_world.item_template t ON t.entry = ii.itemEntry
  GROUP BY a.class, ci.slot, t.name ORDER BY a.class, ci.slot;
