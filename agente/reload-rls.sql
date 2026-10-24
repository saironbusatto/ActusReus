-- O usuário joga com o Reload (Rogue Orc, guid 1045) no RLS III (time 60, só regras), no lugar do Zebedeux (1020).
-- Rodar com o worldserver PARADO. Para desfazer: trocar 1045 por 1020 nas duas linhas de baixo.
USE acore_characters;
SELECT COUNT(*) INTO @ok FROM arena_team_member WHERE arenaTeamId = 60 AND guid = 1020;
SELECT COUNT(*) INTO @reload_em_3v3 FROM arena_team_member m JOIN arena_team t USING(arenaTeamId) WHERE m.guid = 1045 AND t.type = 3;
SELECT IF(@ok = 1 AND @reload_em_3v3 = 0, 'OK: troca Zebedeux -> Reload no RLS III', 'PARE: estado inesperado') AS checagem;

DELETE FROM arena_team_member WHERE arenaTeamId = 60 AND guid = 1020 AND @ok = 1 AND @reload_em_3v3 = 0;
INSERT INTO arena_team_member (arenaTeamId, guid, personalRating)
  SELECT 60, 1045, 1500 FROM DUAL WHERE @ok = 1 AND @reload_em_3v3 = 0;
REPLACE INTO character_arena_stats (guid, slot, matchMakerRating, maxMMR)
  SELECT 1045, 1, 1500, 1500 FROM DUAL WHERE @ok = 1 AND @reload_em_3v3 = 0;

SELECT t.name, GROUP_CONCAT(c.name) membros FROM arena_team t JOIN arena_team_member m USING(arenaTeamId)
  JOIN characters c ON c.guid = m.guid WHERE t.arenaTeamId = 60 GROUP BY t.name;
