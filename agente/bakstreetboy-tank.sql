USE acore_characters;
START TRANSACTION;
SELECT IF(online=0,'OK offline','PARE: online') FROM characters WHERE guid=1044;
UPDATE characters SET level=80, xp=0 WHERE guid=1044 AND online=0;
CREATE TEMPORARY TABLE eq (slot TINYINT PRIMARY KEY, item INT, ench TEXT, dur INT);
INSERT INTO eq VALUES (0,51306,'3818 0 0 0 0 0 3637 0 0 3537 0 0 0 0 0 3766 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 ',100),
 (1,50682,'0 0 0 0 0 0 3537 0 0 0 0 0 0 0 0 2868 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 ',0),
 (2,51309,'3811 0 0 0 0 0 3537 0 0 0 0 0 0 0 0 2868 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 ',100),
 (4,51305,'3832 0 0 0 0 0 3537 0 0 3532 0 0 0 0 0 3307 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 ',165),
 (5,50691,'0 0 0 0 0 0 3537 0 0 3532 0 0 3532 0 0 3307 0 0 3729 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 ',55),
 (6,51308,'3822 0 0 0 0 0 3575 0 0 3532 0 0 0 0 0 3307 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 ',120),
 (7,54579,'3232 0 0 0 0 0 3532 0 0 3532 0 0 0 0 0 3307 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 ',75),
 (8,50611,'3850 0 0 0 0 0 3575 0 0 0 0 0 0 0 0 2868 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 ',55),
 (9,51307,'3253 0 0 0 0 0 3575 0 0 0 0 0 0 0 0 2868 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 ',55),
 (10,50642,'0 0 0 0 0 0 3537 0 0 0 0 0 0 0 0 2868 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 ',0),
 (11,50622,'0 0 0 0 0 0 3537 0 0 0 0 0 0 0 0 2868 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 ',0),
 (12,54591,'0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 ',0),
 (13,50364,'0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 ',0),
 (14,50718,'3294 0 0 0 0 0 3575 0 0 0 0 0 0 0 0 2868 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 ',0),
 (15,49623,'3847 0 0 0 0 0 3537 0 0 3537 0 0 3537 0 0 3312 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 ',145),
 (17,50462,'0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 ',0);
UPDATE item_instance ii JOIN character_inventory ci ON ci.item=ii.guid AND ci.guid=1044 AND ci.bag=0
JOIN eq ON eq.slot=ci.slot SET ii.itemEntry=eq.item, ii.enchantments=eq.ench, ii.durability=eq.dur, ii.flags=1,
ii.count=1, ii.randomPropertyId=0 WHERE ii.owner_guid=1044;
INSERT INTO item_instance (guid,itemEntry,owner_guid,creatorGuid,giftCreatorGuid,count,duration,charges,flags,enchantments,randomPropertyId,durability,playedTime,text)
SELECT 30000000+eq.slot,eq.item,1044,0,0,1,0,'0 0 0 0 0 ',1,eq.ench,0,eq.dur,0,'' FROM eq
WHERE eq.slot NOT IN (SELECT slot FROM character_inventory WHERE guid=1044 AND bag=0);
INSERT INTO character_inventory (guid,bag,slot,item)
SELECT 1044,0,eq.slot,30000000+eq.slot FROM eq
WHERE eq.slot NOT IN (SELECT slot FROM character_inventory WHERE guid=1044 AND bag=0);
SELECT ci.slot, t.name, t.ItemLevel, ii.enchantments FROM character_inventory ci JOIN item_instance ii ON ii.guid=ci.item
JOIN acore_world.item_template t ON t.entry=ii.itemEntry WHERE ci.guid=1044 AND ci.bag=0 AND ci.slot<19 ORDER BY ci.slot;
COMMIT;
