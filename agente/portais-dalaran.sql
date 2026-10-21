-- Um "Portal to Dalaran" (201797: neutro, sem exigir grupo, spell 68328 -> Dalaran) em cada ponto de nascimento.
-- 5 jardas à frente do spawn de playercreateinfo, virado para o jogador. Guids fixos 5800001-5800009 (idempotente).
-- Spawns no acore_world só aparecem depois de reiniciar o worldserver.
USE acore_world;

DELETE FROM gameobject WHERE guid BETWEEN 5800001 AND 5800009;

CREATE TEMPORARY TABLE ponto (guid INT, map SMALLINT, zone SMALLINT, x FLOAT, y FLOAT, z FLOAT, o FLOAT, fases INT, nome VARCHAR(40));
INSERT INTO ponto VALUES
 (5800001,   0,    1, -6240.32,    331.03, 382.76, 6.18, 1,     'Coldridge Valley (anão/gnomo)'),
 (5800002,   0,   12, -8949.95,   -132.49,  83.53, 0.00, 1,     'Northshire (humano)'),
 (5800003,   0,   85,  1676.71,   1678.31, 121.67, 2.71, 1,     'Deathknell (morto-vivo)'),
 (5800004,   1,   14,  -618.52,  -4251.67,  38.72, 0.00, 1,     'Valley of Trials (orc/troll)'),
 (5800005,   1,  141, 10311.30,    832.46,1326.41, 5.70, 1,     'Shadowglen (elfo noturno)'),
 (5800006,   1,  215, -2917.58,   -257.98,  52.99, 0.00, 1,     'Camp Narache (tauren)'),
 (5800007, 530, 3431, 10349.60,  -6357.29,  33.40, 5.32, 1,     'Sunstrider Isle (elfo sangrento)'),
 (5800008, 530, 3526, -3961.64, -13931.20, 100.62, 2.08, 1,     'Ammen Vale (draenei)'),
 (5800009, 609, 4298,  2356.50,  -5664.00, 426.03, 3.66, 65535, 'Ebon Hold (DK, todas as fases)');

INSERT INTO gameobject (guid, id, map, zoneId, areaId, spawnMask, phaseMask, position_x, position_y, position_z, orientation,
                        rotation0, rotation1, rotation2, rotation3, spawntimesecs, animprogress, state, ScriptName, VerifiedBuild, Comment)
SELECT guid, 201797, map, zone, 0, 1, fases, x + 5 * COS(o), y + 5 * SIN(o), z, MOD(o + PI(), 2 * PI()),
       0, 0, SIN(MOD(o + PI(), 2 * PI()) / 2), COS(MOD(o + PI(), 2 * PI()) / 2), 0, 100, 1, '', 0,
       CONCAT('Portal Dalaran - ', nome)
FROM ponto;

SELECT guid, map, ROUND(position_x, 1) x, ROUND(position_y, 1) y, ROUND(position_z, 1) z, Comment FROM gameobject
WHERE guid BETWEEN 5800001 AND 5800009 ORDER BY guid;
