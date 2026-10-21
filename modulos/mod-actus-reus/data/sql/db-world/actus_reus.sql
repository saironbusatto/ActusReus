-- mod-actus-reus: Crânio de Tyrannistrasz em Dalaran. Tabelas de kit (preenchidas por actus_reus_kits.sql, gerado),
-- o objeto clicável e os textos do menu. Idempotente.

CREATE TABLE IF NOT EXISTS actus_kit_spec (
    classe   TINYINT UNSIGNED NOT NULL,
    spec     TINYINT UNSIGNED NOT NULL,
    nome     VARCHAR(40)  NOT NULL,
    papel    VARCHAR(10)  NOT NULL,
    link_pve VARCHAR(120) NOT NULL,           -- talentos no formato do playerbots.conf (árvores separadas por '-')
    link_pvp VARCHAR(120) NOT NULL,
    apelidos VARCHAR(200) NOT NULL,           -- palavras que o chat reconhece, separadas por vírgula
    PRIMARY KEY (classe, spec)
);

CREATE TABLE IF NOT EXISTS actus_kit_item (
    classe  TINYINT UNSIGNED NOT NULL,
    spec    TINYINT UNSIGNED NOT NULL,
    modo    TINYINT UNSIGNED NOT NULL,        -- 0 PvE, 1 PvP
    slot    TINYINT UNSIGNED NOT NULL,        -- EQUIPMENT_SLOT_*
    item    INT UNSIGNED NOT NULL,
    encanto INT UNSIGNED NOT NULL,            -- SpellItemEnchantment permanente (0 = nenhum)
    gema1   INT UNSIGNED NOT NULL,            -- itens de gema, na ordem dos encaixes; a do cinto vai no encaixe extra
    gema2   INT UNSIGNED NOT NULL,
    gema3   INT UNSIGNED NOT NULL,
    gema4   INT UNSIGNED NOT NULL,
    PRIMARY KEY (classe, spec, modo, slot)
);

CREATE TABLE IF NOT EXISTS actus_kit_extra (
    classe     TINYINT UNSIGNED NOT NULL,
    item       INT UNSIGNED NOT NULL,
    quantidade INT UNSIGNED NOT NULL,
    e_bolsa    TINYINT UNSIGNED NOT NULL       -- 1 = vai num slot de bolsa vazio
);

CREATE TABLE IF NOT EXISTS actus_kit_spell (
    classe TINYINT UNSIGNED NOT NULL,         -- 0 = toda classe
    raca   TINYINT UNSIGNED NOT NULL,         -- 0 = toda raça
    spell  INT UNSIGNED NOT NULL,
    tipo   TINYINT UNSIGNED NOT NULL,         -- 0 aprende sempre, 1 montaria terrestre (sorteia 1), 2 voadora (sorteia 1)
    PRIMARY KEY (classe, raca, spell)
);

-- objeto: tipo 2 (questgiver) para ter o cursor de conversa; modelo 7353 = crânio das ossadas de dragão de Wetlands
DELETE FROM gameobject_template WHERE entry = 920000;
INSERT INTO gameobject_template (entry, type, displayId, name, IconName, castBarCaption, unk1, size,
    Data0, Data1, Data2, Data3, Data4, Data5, Data6, Data7, Data8, Data9, Data10, Data11, Data12, Data13, Data14, Data15,
    Data16, Data17, Data18, Data19, Data20, Data21, Data22, Data23, AIName, ScriptName, VerifiedBuild)
VALUES (920000, 2, 7353, 'Crânio de Tyrannistrasz', '', '', '', 0.35,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, '', 'go_cranio_tyrannistrasz', 0);

-- posição: onde o personagem Reload estava em Dalaran, olhando para o mesmo lado
DELETE FROM gameobject WHERE guid = 5800100;
INSERT INTO gameobject (guid, id, map, zoneId, areaId, spawnMask, phaseMask, position_x, position_y, position_z, orientation,
    rotation0, rotation1, rotation2, rotation3, spawntimesecs, animprogress, state, ScriptName, VerifiedBuild, Comment)
VALUES (5800100, 920000, 571, 4395, 0, 1, 1, 5804.95, 658.56, 648.06, 4.69,
    0, 0, SIN(4.69 / 2), COS(4.69 / 2), 0, 100, 1, '', 0, 'Crânio de Tyrannistrasz (mod-actus-reus)');

-- textos do menu (npc_text): 920000 saudação, 920001 escolha do modo, 920002 confirmação
DELETE FROM npc_text WHERE ID BETWEEN 920000 AND 920002;
INSERT INTO npc_text (ID, text0_0, text0_1, BroadcastTextID0, lang0, Probability0) VALUES
(920000, 'Ossos não esquecem, mortal. Eu fui Tyrannistrasz, consorte da Rainha da Vida, e mesmo morto ainda guardo o poder dos que caíram em Northrend.$B$BEscolha seu caminho e eu te farei pronto para a guerra.', '', 0, 0, 1),
(920001, 'Sangue de batalha ou sangue de arena? Diga onde vai lutar, e eu escolho o aço.', '', 0, 0, 1),
(920002, 'Seu equipamento atual seguirá pelo correio. O que eu der, você levará consigo. Está certo disso?', '', 0, 0, 1);
