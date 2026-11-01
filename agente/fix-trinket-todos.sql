-- Trinket PvP em TODOS os bots de arena (times 54-89). 43 estavam sem Medallion e isso envenena a observação da IA
-- (o trinket aparece como disponível para sair de CC). Medallion ilvl 200 = 42122 Horda / 42123 Aliança.
-- RODAR COM O WORLDSERVER PARADO: os itens equipados vivem em memória e o logout sobrescreve o banco.
USE acore_characters;
CREATE TEMPORARY TABLE fix (nome VARCHAR(12), slot TINYINT, item INT);
INSERT INTO fix VALUES
 ('Amnesianxxvi',12,42122),
 ('Beteranii',12,42123),
 ('Beteraniv',12,42123),
 ('Beteranv',12,42123),
 ('Beteranvi',12,42123),
 ('Bovinus',12,42122),
 ('Heruiv',12,42123),
 ('Heruix',12,42123),
 ('Heruvi',12,42123),
 ('Heruvii',12,42123),
 ('Herux',12,42123),
 ('Heruxi',12,42123),
 ('Heruxii',12,42123),
 ('Heruxiv',12,42123),
 ('Heruxvi',12,42123),
 ('Heshoiv',12,42122),
 ('Heshoix',12,42122),
 ('Heshov',12,42122),
 ('Heshovi',12,42122),
 ('Heshox',12,42122),
 ('Heshoxi',12,42122),
 ('Kwongwegaiv',12,42122),
 ('Kwongwegaix',12,42122),
 ('Kwongwegavi',12,42122),
 ('Kwongwegavii',12,42122),
 ('Kwongwegax',12,42122),
 ('Kwongwegaxi',12,42122),
 ('Kwongwegaxii',12,42122),
 ('Kwongwegaxiv',12,42122),
 ('Kwongwegaxix',12,42122),
 ('Kwongwegaxv',12,42122),
 ('Kwongwegaxvi',12,42122),
 ('Kwongwegaxx',12,42122),
 ('Kwongwegaxxv',12,42122),
 ('Naminv',12,42123),
 ('Naminvi',12,42123),
 ('Omasconiv',12,42123),
 ('Omasconvi',12,42123),
 ('Ominousdesii',12,42122),
 ('Ominousdesix',12,42122),
 ('Ominousdesv',12,42122),
 ('Ominousdesvi',12,42122),
 ('Pehdibalii',12,42122),
 ('Pokastranca',12,42122);

-- quem muda de item
-- Amnesianxxvi: slot 12 Spark of Life -> Medallion of the Horde
-- Beteranii: slot 12 Meteorite Whetstone -> Medallion of the Alliance
-- Beteraniv: slot 12 Meteorite Whetstone -> Medallion of the Alliance
-- Beteranv: slot 12 Meteorite Whetstone -> Medallion of the Alliance
-- Beteranvi: slot 12 Meteorite Whetstone -> Medallion of the Alliance
-- Bovinus: slot 12 Darkmoon Card: Berserker! -> Medallion of the Horde
-- Heruiv: slot 12 Meteorite Whetstone -> Medallion of the Alliance
-- Heruix: slot 12 Meteorite Whetstone -> Medallion of the Alliance
-- Heruvi: slot 12 Meteorite Whetstone -> Medallion of the Alliance
-- Heruvii: slot 12 Meteorite Whetstone -> Medallion of the Alliance
-- Herux: slot 12 Meteorite Whetstone -> Medallion of the Alliance
-- Heruxi: slot 12 Meteorite Whetstone -> Medallion of the Alliance
-- Heruxii: slot 12 Ancient Pickled Egg -> Medallion of the Alliance
-- Heruxiv: slot 12 Meteorite Whetstone -> Medallion of the Alliance
-- Heruxvi: slot 12 Ancient Pickled Egg -> Medallion of the Alliance
-- Heshoiv: slot 12 Forge Ember -> Medallion of the Horde
-- Heshoix: slot 12 Abyssal Rune -> Medallion of the Horde
-- Heshov: slot 12 Forge Ember -> Medallion of the Horde
-- Heshovi: slot 12 Forge Ember -> Medallion of the Horde
-- Heshox: slot 12 Forge Ember -> Medallion of the Horde
-- Heshoxi: slot 12 Abyssal Rune -> Medallion of the Horde
-- Kwongwegaiv: slot 12 Meteorite Whetstone -> Medallion of the Horde
-- Kwongwegaix: slot 12 Meteorite Whetstone -> Medallion of the Horde
-- Kwongwegavi: slot 12 Meteorite Whetstone -> Medallion of the Horde
-- Kwongwegavii: slot 12 Meteorite Whetstone -> Medallion of the Horde
-- Kwongwegax: slot 12 Meteorite Whetstone -> Medallion of the Horde
-- Kwongwegaxi: slot 12 Meteorite Whetstone -> Medallion of the Horde
-- Kwongwegaxii: slot 12 Meteorite Whetstone -> Medallion of the Horde
-- Kwongwegaxiv: slot 12 Meteorite Whetstone -> Medallion of the Horde
-- Kwongwegaxix: slot 12 Meteorite Whetstone -> Medallion of the Horde
-- Kwongwegaxv: slot 12 Meteorite Whetstone -> Medallion of the Horde
-- Kwongwegaxvi: slot 12 Meteorite Whetstone -> Medallion of the Horde
-- Kwongwegaxx: slot 12 Meteorite Whetstone -> Medallion of the Horde
-- Kwongwegaxxv: slot 12 Meteorite Whetstone -> Medallion of the Horde
-- Naminv: slot 12 Meteorite Whetstone -> Medallion of the Alliance
-- Naminvi: slot 12 Meteorite Whetstone -> Medallion of the Alliance
-- Omasconiv: slot 12 Seal of the Pantheon -> Medallion of the Alliance
-- Omasconvi: slot 12 Seal of the Pantheon -> Medallion of the Alliance
-- Ominousdesii: slot 12 Forge Ember -> Medallion of the Horde
-- Ominousdesix: slot 12 Forge Ember -> Medallion of the Horde
-- Ominousdesv: slot 12 Forge Ember -> Medallion of the Horde
-- Ominousdesvi: slot 12 Forge Ember -> Medallion of the Horde
-- Pehdibalii: slot 12 Spark of Life -> Medallion of the Horde
-- Pokastranca: slot 12 Meteorite Whetstone -> Medallion of the Horde

UPDATE item_instance ii
  JOIN character_inventory ci ON ci.item = ii.guid AND ci.bag = 0
  JOIN characters c ON c.guid = ci.guid
  JOIN fix f ON f.nome = c.name AND f.slot = ci.slot
SET ii.itemEntry = f.item,
    ii.durability = (SELECT MaxDurability FROM acore_world.item_template t WHERE t.entry = f.item);

-- conferência: nenhum bot de arena sem Medallion
SELECT COUNT(*) AS ainda_sem FROM (
  SELECT c.guid FROM acore_characters.characters c
  JOIN acore_characters.arena_team_member m ON m.guid = c.guid
  WHERE m.arenaTeamId BETWEEN 54 AND 89
    AND c.guid NOT IN (SELECT ci.guid FROM acore_characters.character_inventory ci
                       JOIN acore_characters.item_instance ii ON ii.guid = ci.item
                       JOIN acore_world.item_template it ON it.entry = ii.itemEntry
                       WHERE ci.bag = 0 AND ci.slot IN (12,13) AND it.name LIKE 'Medallion of the%')
) x;
