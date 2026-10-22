-- Expansão para 108 bots: 16 trios 3v3 novos (times 74–89), UMA facção por trio (regra do usuário).
-- Thunder Cleave (Aliança): Arms Warrior (Humano) + Elemental Shaman (Draenei) + Holy Paladin (Humano)
-- Fireplay (Horda): Fire Mage (Troll) + Destro Warlock (Morto-vivo) + Resto Shaman (Tauren)
-- RPS (Horda): Sub Rogue (Troll) + Shadow Priest (Morto-vivo) + Resto Shaman (Tauren)
-- LSD (Horda): Destro Warlock (Morto-vivo) + Balance Druid (Tauren) + Resto Shaman (Tauren)
-- Capitão = healer (ele chama o time para a fila). Rodar com o worldserver PARADO, depois que os 48 existirem.
-- Trava: se faltar algum dos 48, ou se algum trio misturar facções, nada é gravado.
USE acore_characters;
CREATE TEMPORARY TABLE novos (n INT, a VARCHAR(12), b VARCHAR(12), cap VARCHAR(12), team_name VARCHAR(24));
INSERT INTO novos VALUES
 (1,'Celianeyvii','Naminii','Heruxii','Thunder I'),       (2,'Celianeyix','Naminiv','Heruxiv','Thunder II'),
 (3,'Celianeyx','Naminv','Heruxv','Thunder III'),         (4,'Celianeyxi','Naminvi','Heruxvi','Thunder IV'),
 (5,'Heshovii','Ominousdes','Kwongwegavii','Fireplay I'), (6,'Heshoix','Ominousdesii','Kwongwegaix','Fireplay II'),
 (7,'Heshox','Ominousdesiv','Kwongwegax','Fireplay III'), (8,'Heshoxi','Ominousdesv','Kwongwegaxi','Fireplay IV'),
 (9,'Zebedeuxii','Amnesianix','Kwongwegaxii','RPS I'),    (10,'Zebedeuxiv','Amnesianxxv','Kwongwegaxiv','RPS II'),
 (11,'Zebedeuxv','Amnesianxxvi','Kwongwegaxv','RPS III'), (12,'Zebedeuxvi','Amnesianxxix','Kwongwegaxvi','RPS IV'),
 (13,'Ominousdesvi','Pehdicouv','Kwongwegaxix','LSD I'),  (14,'Ominousdesix','Pehdibalii','Kwongwegaxx','LSD II'),
 (15,'Ominousdesx','Pehdibaliv','Kwongwegaxxi','LSD III'),(16,'Ominousdesxi','Pehdibalv','Kwongwegaxxv','LSD IV');

-- 48 personagens existentes, nenhum protegido, nenhum já num time 3v3
SELECT COUNT(*) INTO @achados FROM characters c JOIN novos t ON c.name IN (t.a, t.b, t.cap)
  WHERE c.guid NOT IN (1001, 1044, 1045)
    AND c.guid NOT IN (SELECT m.guid FROM arena_team_member m JOIN arena_team x USING(arenaTeamId) WHERE x.type = 3);
-- facção por raça: Aliança 1,3,4,7,11; trio misturado conta como erro
SELECT COUNT(*) INTO @misturados FROM (
  SELECT t.n FROM novos t JOIN characters c ON c.name IN (t.a, t.b, t.cap)
  GROUP BY t.n HAVING COUNT(DISTINCT c.race IN (1,3,4,7,11)) > 1) x;
SET @ok = (@achados = 48 AND @misturados = 0 AND (SELECT COUNT(*) FROM arena_team WHERE arenaTeamId BETWEEN 74 AND 89) = 0);
SELECT IF(@ok, 'OK: 48 personagens, 16 trios de uma facção',
          CONCAT('PARE: ', @achados, ' de 48 personagens, ', @misturados, ' trio(s) misturado(s)')) AS checagem;

INSERT INTO arena_team (arenaTeamId, name, captainGuid, type, rating, backgroundColor, emblemStyle, emblemColor,
                        borderStyle, borderColor)
  SELECT 73 + t.n, t.team_name, c.guid, 3, 1500, 4279401323, 35, 4292282831, 5, 4293808578
  FROM novos t JOIN characters c ON c.name = t.cap WHERE @ok;
INSERT INTO arena_team_member (arenaTeamId, guid, personalRating)
  SELECT 73 + t.n, c.guid, 1500 FROM novos t JOIN characters c ON c.name IN (t.a, t.b, t.cap) WHERE @ok;
REPLACE INTO character_arena_stats (guid, slot, matchMakerRating, maxMMR)
  SELECT c.guid, 1, 1500, 1500 FROM novos t JOIN characters c ON c.name IN (t.a, t.b, t.cap) WHERE @ok;
UPDATE characters c JOIN novos t ON c.name IN (t.a, t.b, t.cap) SET c.at_login = 0 WHERE @ok;
UPDATE acore_playerbots.playerbots_random_bots SET value = 108 WHERE event = 'bot_count' AND @ok;

SELECT t.name, GROUP_CONCAT(c.name ORDER BY c.class) membros, COUNT(*) n
FROM arena_team t JOIN arena_team_member m USING(arenaTeamId) JOIN characters c ON c.guid = m.guid
WHERE t.arenaTeamId BETWEEN 74 AND 89 GROUP BY t.arenaTeamId;
