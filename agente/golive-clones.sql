-- Liga os 40 clones de 2026-10-21 em 20 times 2v2. Rodar com o worldserver PARADO (ver golive-clones.md).
USE acore_characters;

CREATE TEMPORARY TABLE duplas (n INT, a VARCHAR(12), b VARCHAR(12), team_name VARCHAR(24));
INSERT INTO duplas VALUES
 (1,'Zebedeuv','Amnesianvi','Vision V'),        (2,'Zebedeuvi','Amnesianvii','Vision VI'),
 (3,'Zebedeuvii','Amnesianix','Vision VII'),    (4,'Zebedeuix','Amnesianx','Vision VIII'),
 (5,'Zebedeux','Amnesianxi','Vision IX'),       (6,'Zebedeuxi','Amnesianxii','Vision X'),
 (7,'Zebedeuxii','Amnesianxiv','Vision XI'),    (8,'Zebedeuxiv','Amnesianxv','Vision XII'),
 (9,'Zebedeuxv','Amnesianxvi','Vision XIII'),   (10,'Zebedeuxvi','Amnesianxvii','Vision XIV'),
 (11,'Ominousvii','Pehdicouvi','Killalot VI'),  (12,'Ominousix','Pehdicouvii','Killalot VII'),
 (13,'Ominousx','Pehdicouix','Killalot VIII'),  (14,'Ominousxi','Pehdicoux','Killalot IX'),
 (15,'Ominousxii','Pehdicouxi','Killalot X'),   (16,'Ominousxiv','Pehdicouxii','Killalot XI'),
 (17,'Ominousxv','Pehdicouxiv','Killalot XII'), (18,'Ominousxvi','Pehdicouxv','Killalot XIII'),
 (19,'Ominousxvii','Pehdicouxvi','Killalot XIV'),(20,'Ominousxix','Pehdicouxvii','Killalot XV');

-- Trava: os 40 nomes precisam existir antes de criar qualquer time
SELECT COUNT(*) INTO @achados FROM characters c JOIN duplas d ON c.name IN (d.a, d.b);
SELECT IF(@achados = 40, 'OK: 40 clones encontrados', CONCAT('PARE: só ', @achados, ' de 40 clones')) AS checagem;

SET @base = (SELECT MAX(arenaTeamId) FROM arena_team);

INSERT INTO arena_team (arenaTeamId, name, captainGuid, type, rating, backgroundColor, emblemStyle, emblemColor,
                        borderStyle, borderColor)
  SELECT @base + d.n, d.team_name, c.guid, 2, 1500, 4279401323, 35, 4292282831, 5, 4293808578
  FROM duplas d JOIN characters c ON c.name = d.b
  WHERE @achados = 40;                                      -- capitão: o healer (Priest/Druid)

INSERT INTO arena_team_member (arenaTeamId, guid, personalRating)
  SELECT @base + d.n, c.guid, 1500 FROM duplas d JOIN characters c ON c.name IN (d.a, d.b) WHERE @achados = 40;

REPLACE INTO character_arena_stats (guid, slot, matchMakerRating, maxMMR)
  SELECT c.guid, 0, 1500, 1500 FROM duplas d JOIN characters c ON c.name IN (d.a, d.b) WHERE @achados = 40;

UPDATE characters c JOIN duplas d ON c.name IN (d.a, d.b) SET c.at_login = 0 WHERE @achados = 40;  -- sem rename

UPDATE acore_playerbots.playerbots_random_bots SET value = 60 WHERE event = 'bot_count' AND @achados = 40;

SELECT t.arenaTeamId, t.name, GROUP_CONCAT(c.name) membros, COUNT(*) n
FROM arena_team t JOIN arena_team_member m USING(arenaTeamId) JOIN characters c ON c.guid=m.guid
WHERE t.arenaTeamId > @base GROUP BY t.arenaTeamId;
