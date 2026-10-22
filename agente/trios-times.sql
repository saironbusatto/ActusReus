-- 20 trios de arena 3v3 (fase 1), uma facção por trio. Horda: 4 RMP, 4 RLS. Aliança: 4 Warlock/Hunter/Druid,
-- 4 Shadowplay, 4 TSG. Capitão = healer (é ele quem chama o time para a fila). Rodar com o worldserver PARADO.
-- Também põe o Medallion (trinket PvP) nos 8 Holy Paladins, que vieram sem ele.
USE acore_characters;
CREATE TEMPORARY TABLE trios (n INT, a VARCHAR(12), b VARCHAR(12), cap VARCHAR(12), team_name VARCHAR(24));
INSERT INTO trios VALUES
 (1,'Zebedeu','Heshoii','Amnesian','RMP I'),(2,'Zebedeuii','Heshoiv','Amnesianii','RMP II'),
 (3,'Zebedeuv','Heshov','Amnesianvi','RMP III'),(4,'Zebedeuvi','Heshovi','Amnesianvii','RMP IV'),
 (5,'Zebedeuvii','Ominousv','Kwongwegaii','RLS I'),(6,'Zebedeuix','Ominousxxi','Kwongwegaiv','RLS II'),
 (7,'Zebedeux','Ominousxxii','Kwongwegav','RLS III'),(8,'Zebedeuxi','Ominousxxiv','Kwongwegavi','RLS IV'),
 (9,'Ominous','Beteranii','Pehdicouve','Wild I'),(10,'Ominoustres','Beteraniv','Pehdicouii','Wild II'),
 (11,'Ominousiv','Beteranv','Pehdicoutres','Wild III'),(12,'Ominousvii','Beteranvi','Pehdicouiv','Wild IV'),
 (13,'Amnesianxix','Ominousix','Heruii','Shadowplay I'),(14,'Amnesianxxi','Ominousx','Heruiv','Shadowplay II'),
 (15,'Amnesianxxii','Ominousxi','Heruv','Shadowplay III'),(16,'Amnesianxxiv','Ominousxii','Heruvi','Shadowplay IV'),
 (17,'Celianeyii','Omasconii','Heruvii','TSG I'),(18,'Celianeyiv','Omasconiv','Heruix','TSG II'),
 (19,'Celianeyv','Omasconv','Herux','TSG III'),(20,'Celianeyvi','Omasconvi','Heruxi','TSG IV');

SELECT COUNT(*) INTO @achados FROM characters c JOIN trios t ON c.name IN (t.a, t.b, t.cap) WHERE c.guid NOT IN (1001,1044,1045);
SELECT IF(@achados = 60, 'OK: 60 personagens', CONCAT('PARE: só ', @achados, ' de 60')) AS checagem;

SET @base = (SELECT MAX(arenaTeamId) FROM arena_team);
INSERT INTO arena_team (arenaTeamId, name, captainGuid, type, rating, backgroundColor, emblemStyle, emblemColor,
                        borderStyle, borderColor)
  SELECT @base + t.n, t.team_name, c.guid, 3, 1500, 4279401323, 35, 4292282831, 5, 4293808578
  FROM trios t JOIN characters c ON c.name = t.cap WHERE @achados = 60;
INSERT INTO arena_team_member (arenaTeamId, guid, personalRating)
  SELECT @base + t.n, c.guid, 1500 FROM trios t JOIN characters c ON c.name IN (t.a, t.b, t.cap) WHERE @achados = 60;
REPLACE INTO character_arena_stats (guid, slot, matchMakerRating, maxMMR)
  SELECT c.guid, 1, 1500, 1500 FROM trios t JOIN characters c ON c.name IN (t.a, t.b, t.cap) WHERE @achados = 60;
UPDATE characters c JOIN trios t ON c.name IN (t.a, t.b, t.cap) SET c.at_login = 0 WHERE @achados = 60;

UPDATE item_instance ii
  JOIN character_inventory ci ON ci.item = ii.guid AND ci.bag = 0 AND ci.slot = 13
  JOIN characters c ON c.guid = ci.guid AND c.class = 2 AND c.name REGEXP '^Heru(ii|iv|v|vi|vii|ix|x|xi)$'
SET ii.itemEntry = 42123, ii.durability = 0 WHERE @achados = 60;

UPDATE acore_playerbots.playerbots_random_bots SET value = 60 WHERE event = 'bot_count' AND @achados = 60;

SELECT t.name, GROUP_CONCAT(c.name ORDER BY c.class) membros, COUNT(*) n
FROM arena_team t JOIN arena_team_member m USING(arenaTeamId) JOIN characters c ON c.guid=m.guid
WHERE t.arenaTeamId > @base GROUP BY t.arenaTeamId;
SELECT COUNT(DISTINCT c.guid) AS com_medallion FROM trios t JOIN characters c ON c.name IN (t.a, t.b, t.cap)
  JOIN character_inventory ci ON ci.guid = c.guid AND ci.bag = 0 AND ci.slot IN (12, 13)
  JOIN item_instance ii ON ii.guid = ci.item AND ii.itemEntry IN (42122, 42123);
