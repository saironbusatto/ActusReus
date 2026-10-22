-- Expansão 108 Bots: Criar times 74 a 89 (16 novos trios 3v3)
-- Thunder Cleave (74-77), Fireplay (78-81), RPS (82-85), LSD (86-89)
USE acore_characters;
CREATE TEMPORARY TABLE novos_trios (n INT, a VARCHAR(12), b VARCHAR(12), cap VARCHAR(12), team_name VARCHAR(24));
INSERT INTO novos_trios VALUES
 -- Thunder Cleave (Aliança: War, Ele Sham, Holy Paladin cap)
 (1, 'Celianeysete', 'Kwongelei', 'Herudoze', 'Thunder I'),
 (2, 'Celianeyoito', 'Kwongeleii', 'Herutreze', 'Thunder II'),
 (3, 'Celianeynove', 'Kwongeleitr', 'Heruquatorze', 'Thunder III'),
 (4, 'Celianeydez', 'Kwongeleiv', 'Heruquinze', 'Thunder IV'),
 -- Fireplay (Horda: Fire Mage, Destro Lock, Resto Sham cap)
 (5, 'Heshofirei', 'Ominousdesi', 'Kwongrestoi', 'Fireplay I'),
 (6, 'Heshofireii', 'Ominousdesii', 'Kwongrestoii', 'Fireplay II'),
 (7, 'Heshofiretr', 'Ominousdestr', 'Kwongrestotr', 'Fireplay III'),
 (8, 'Heshofireiv', 'Ominousdesiv', 'Kwongrestoiv', 'Fireplay IV'),
 -- RPS (Horda: Sub Rogue, Shadow Priest, Resto Sham cap)
 (9, 'Zebedeudoz', 'Amnesianshi', 'Kwongrpsi', 'RPS I'),
 (10, 'Zebedeutrez', 'Amnesianshii', 'Kwongrpsii', 'RPS II'),
 (11, 'Zebedeuquat', 'Amnesianshtr', 'Kwongrpstr', 'RPS III'),
 (12, 'Zebedeuquin', 'Amnesianshiv', 'Kwongrpsiv', 'RPS IV'),
 -- LSD (Horda: Destro Lock, Boomkin Druid, Resto Sham cap)
 (13, 'Ominouslsdi', 'Pehdiboomi', 'Kwonglsdi', 'LSD I'),
 (14, 'Ominouslsdii', 'Pehdiboomii', 'Kwonglsdii', 'LSD II'),
 (15, 'Ominouslsdtr', 'Pehdiboomtr', 'Kwonglsdtr', 'LSD III'),
 (16, 'Ominouslsdiv', 'Pehdiboomiv', 'Kwonglsdiv', 'LSD IV');

SET @base = 73; -- Último time atual é TSG IV (73)
INSERT INTO arena_team (arenaTeamId, name, captainGuid, type, rating, backgroundColor, emblemStyle, emblemColor, borderStyle, borderColor)
  SELECT @base + t.n, t.team_name, c.guid, 3, 1500, 4279401323, 35, 4292282831, 5, 4293808578
  FROM novos_trios t JOIN characters c ON c.name = t.cap;
INSERT INTO arena_team_member (arenaTeamId, guid, personalRating)
  SELECT @base + t.n, c.guid, 1500 FROM novos_trios t JOIN characters c ON c.name IN (t.a, t.b, t.cap);
REPLACE INTO character_arena_stats (guid, slot, matchMakerRating, maxMMR)
  SELECT c.guid, 1, 1500, 1500 FROM novos_trios t JOIN characters c ON c.name IN (t.a, t.b, t.cap);
UPDATE characters c JOIN novos_trios t ON c.name IN (t.a, t.b, t.cap) SET c.at_login = 0;
UPDATE acore_playerbots.playerbots_random_bots SET value = 108 WHERE event = 'bot_count';
SELECT 'OK: 16 novos trios configurados com sucesso' AS status;
