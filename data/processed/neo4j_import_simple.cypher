// Minecraft 知识图谱 - 简化Neo4j导入脚本
// 构建时间: 2026-08-24T10:14:04.456666

// 创建约束
CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (e:Entity) REQUIRE e.id IS UNIQUE;
CREATE CONSTRAINT content_id IF NOT EXISTS FOR (c:Content) REQUIRE c.id IS UNIQUE;

// 插入实体节点
MERGE (e:Entity {id: 'minecraft:type'}) SET name_zh: 'Type: `', name_en: 'Type: `', type: 'mob', node_type: 'entity', aliases: ["Type: `"], created_at: '2026-08-24T10:14:04.456666', updated_at: '2026-08-24T10:14:04.456666', version: '1.0';
MERGE (e:Entity {id: 'minecraft:a_fiery_hostile'}) SET name_zh: 'A fiery hostile', name_en: 'A fiery hostile', type: 'mob', node_type: 'entity', aliases: ["A fiery hostile"], created_at: '2026-08-24T10:14:04.456666', updated_at: '2026-08-24T10:14:04.456666', version: '1.0';
MERGE (e:Entity {id: 'minecraft:it'}) SET name_zh: 'It', name_en: 'It', type: 'mob', node_type: 'entity', aliases: ["It"], created_at: '2026-08-24T10:14:04.456666', updated_at: '2026-08-24T10:14:04.456666', version: '1.0';
MERGE (e:Entity {id: 'minecraft:a_hostile'}) SET name_zh: 'A hostile', name_en: 'A hostile', type: 'mob', node_type: 'entity', aliases: ["A hostile"], created_at: '2026-08-24T10:14:04.456666', updated_at: '2026-08-24T10:14:04.456666', version: '1.0';
MERGE (e:Entity {id: 'minecraft:diamond'}) SET name_zh: '钻石', name_en: '钻石', type: 'item', node_type: 'entity', aliases: ["diamond"], created_at: '2026-08-24T10:14:04.456666', updated_at: '2026-08-24T10:14:04.456666', version: '1.0';
MERGE (e:Entity {id: 'minecraft:a_large_nether'}) SET name_zh: 'A large Nether', name_en: 'A large Nether', type: 'structure', node_type: 'entity', aliases: ["A large Nether"], created_at: '2026-08-24T10:14:04.456666', updated_at: '2026-08-24T10:14:04.456666', version: '1.0';
MERGE (e:Entity {id: 'minecraft:regions_for_nether'}) SET name_zh: 'regions for Nether', name_en: 'regions for Nether', type: 'structure', node_type: 'entity', aliases: ["regions for Nether"], created_at: '2026-08-24T10:14:04.456666', updated_at: '2026-08-24T10:14:04.456666', version: '1.0';
MERGE (e:Entity {id: 'minecraft:a_dangerous_volcanic_fungal'}) SET name_zh: 'A dangerous volcanic fungal', name_en: 'A dangerous volcanic fungal', type: 'biome', node_type: 'entity', aliases: ["A dangerous volcanic fungal"], created_at: '2026-08-24T10:14:04.456666', updated_at: '2026-08-24T10:14:04.456666', version: '1.0';

// 插入内容节点
MERGE (c:Content {id: 'chunk_minecraft-wiki-blaze_0'}) SET title: 'Blaze', content: '# Blaze
- Type: `Mob`
- Mob type: `Monster`
- Source: https://minecraft.wiki/w/Blaze
- Retrieved at: `2026-08-23T00:00:00Z`
## Summary
A fiery hostile mob found in Nether fortresses and the only source of blaze rods.
## Key Facts
- It has 20 HP.
- It spawns in Nether fortresses at light level 11 or less.
- It attacks with three small fireballs or melee attacks.
- It drops blaze rods and 10 XP when killed by a player or tamed wolf.
- It can ride boats and minecarts.
## Version Notes', node_type: 'content', created_at: '2026-08-24T10:14:04.456666', updated_at: '2026-08-24T10:14:04.456666', version: '1.0', metadata: {"source_id": "minecraft-wiki-blaze", "title": "Blaze", "version": "", "edition": "", "chunk_type": "paragraph"};
MERGE (c:Content {id: 'chunk_minecraft-wiki-blaze_1'}) SET title: 'Blaze', content: '- Java Edition and Bedrock Edition use different fortress spawn group sizes.
- Blaze spawner platforms can generate inside Nether fortresses.', node_type: 'content', created_at: '2026-08-24T10:14:04.456666', updated_at: '2026-08-24T10:14:04.456666', version: '1.0', metadata: {"source_id": "minecraft-wiki-blaze", "title": "Blaze", "version": "", "edition": "", "chunk_type": "paragraph"};
MERGE (c:Content {id: 'chunk_minecraft-wiki-crafting-table_2'}) SET title: 'Crafting Table', content: '# Crafting Table
- Type: `Block`
- Source: https://minecraft.wiki/w/Crafting_Table
- Retrieved at: `2026-08-23T00:00:00Z`
## Summary
A utility block that unlocks the full crafting grid.
## Key Facts
- It gives access to all crafting recipes, including ones unavailable in the inventory grid.
- It is best broken with an axe.
- It is renewable and stackable to 64.
- It naturally generates in structures such as swamp huts, igloos, trail ruins, and trial chambers.', node_type: 'content', created_at: '2026-08-24T10:14:04.456666', updated_at: '2026-08-24T10:14:04.456666', version: '1.0', metadata: {"source_id": "minecraft-wiki-crafting-table", "title": "Crafting Table", "version": "", "edition": "", "chunk_type": "paragraph"};
MERGE (c:Content {id: 'chunk_minecraft-wiki-crafting-table_3'}) SET title: 'Crafting Table', content: '- It can be used as furnace fuel and as a crafting ingredient for crafters.
## Version Notes
- In Java Edition 1.20.3, it can be used to craft crafters.
- In Java Edition 23w07a, the recipe is unlocked immediately on world creation.
- In Java Edition 1.14, banner dyeing moved to the loom.', node_type: 'content', created_at: '2026-08-24T10:14:04.456666', updated_at: '2026-08-24T10:14:04.456666', version: '1.0', metadata: {"source_id": "minecraft-wiki-crafting-table", "title": "Crafting Table", "version": "", "edition": "", "chunk_type": "paragraph"};
MERGE (c:Content {id: 'chunk_minecraft-wiki-creeper_4'}) SET title: 'Creeper', content: '# Creeper
- Type: `Mob`
- Mob type: `Monster`
- Source: https://minecraft.wiki/w/Creeper
- Retrieved at: `2026-08-23T00:00:00Z`
## Summary
A hostile mob that silently approaches players and explodes when close.
## Key Facts
- It has 20 HP.
- It naturally spawns in the Overworld at light level 0.
- Its explosion can destroy blocks and deal major damage.
- A lightning strike can turn it into a charged creeper.
- It drops gunpowder and can rarely drop music discs or creeper heads.
## Version Notes', node_type: 'content', created_at: '2026-08-24T10:14:04.456666', updated_at: '2026-08-24T10:14:04.456666', version: '1.0', metadata: {"source_id": "minecraft-wiki-creeper", "title": "Creeper", "version": "", "edition": "", "chunk_type": "paragraph"};
MERGE (c:Content {id: 'chunk_minecraft-wiki-creeper_5'}) SET title: 'Creeper', content: '- In Java Edition, wearing a creeper head reduces detection range by 50%.
- In Bedrock Edition, charged creeper explosions can cause all valid killed mobs to drop their heads.', node_type: 'content', created_at: '2026-08-24T10:14:04.456666', updated_at: '2026-08-24T10:14:04.456666', version: '1.0', metadata: {"source_id": "minecraft-wiki-creeper", "title": "Creeper", "version": "", "edition": "", "chunk_type": "paragraph"};
MERGE (c:Content {id: 'chunk_minecraft-wiki-diamond-pickaxe_6'}) SET title: 'Diamond Pickaxe', content: '# Diamond Pickaxe
- Type: `Item`
- Source: https://minecraft.wiki/w/Diamond_Pickaxe
- Retrieved at: `2026-08-23T00:00:00Z`
## Summary
A high-tier pickaxe crafted from diamonds and sticks.
## Key Facts
- It is crafted from diamonds and sticks.
- It has mining level 3 and can mine obsidian and ancient debris.
- Its attack damage is 5 HP in Java Edition and 6 HP in Bedrock Edition.
- Its durability is 1561 in Java Edition and 1562 in Bedrock Edition.
- It can be upgraded into a netherite pickaxe.', node_type: 'content', created_at: '2026-08-24T10:14:04.456666', updated_at: '2026-08-24T10:14:04.456666', version: '1.0', metadata: {"source_id": "minecraft-wiki-diamond-pickaxe", "title": "Diamond Pickaxe", "version": "", "edition": "", "chunk_type": "paragraph"};
MERGE (c:Content {id: 'chunk_minecraft-wiki-diamond-pickaxe_7'}) SET title: 'Diamond Pickaxe', content: '## Version Notes
- It is not stackable.
- It can appear in generated loot in Trial Chambers, End Cities, and Bastion Remnants.', node_type: 'content', created_at: '2026-08-24T10:14:04.456666', updated_at: '2026-08-24T10:14:04.456666', version: '1.0', metadata: {"source_id": "minecraft-wiki-diamond-pickaxe", "title": "Diamond Pickaxe", "version": "", "edition": "", "chunk_type": "paragraph"};
MERGE (c:Content {id: 'chunk_minecraft-wiki-nether-fortress_8'}) SET title: 'Nether Fortress', content: '# Nether Fortress
- Type: `Structure`
- Source: https://minecraft.wiki/w/Nether_Fortress
- Retrieved at: `2026-08-23T00:00:00Z`
## Summary
A large Nether structure made of Nether bricks with bridges, corridors, and towers.
## Key Facts
- It generates in all Nether biomes.
- It is made of Nether bricks and related fortress blocks.
- It is the only place where blazes and wither skeletons spawn.
- It contains Nether wart.
- Its layout includes bridges, corridors, and towers.
## Version Notes', node_type: 'content', created_at: '2026-08-24T10:14:04.456666', updated_at: '2026-08-24T10:14:04.456666', version: '1.0', metadata: {"source_id": "minecraft-wiki-nether-fortress", "title": "Nether Fortress", "version": "", "edition": "", "chunk_type": "paragraph"};
MERGE (c:Content {id: 'chunk_minecraft-wiki-nether-fortress_9'}) SET title: 'Nether Fortress', content: '- Java Edition uses 432x432 structure regions for Nether structure generation.
- Bedrock Edition uses 480x480 structure regions for Nether structure generation.
- In Java Edition, chickens can rarely spawn through jockeys in fortresses.', node_type: 'content', created_at: '2026-08-24T10:14:04.456666', updated_at: '2026-08-24T10:14:04.456666', version: '1.0', metadata: {"source_id": "minecraft-wiki-nether-fortress", "title": "Nether Fortress", "version": "", "edition": "", "chunk_type": "paragraph"};
MERGE (c:Content {id: 'chunk_minecraft-wiki-the-nether_10'}) SET title: 'The Nether', content: '# The Nether
- Type: `Dimension`
- Source: https://minecraft.wiki/w/The_Nether
- Retrieved at: `2026-08-23T00:00:00Z`
## Summary
A dangerous volcanic fungal dimension with lava seas, unique biomes, and hostile mobs.
## Key Facts
- It contains fire, lava seas, fungi, unique mobs, structures, resources, and biomes.
- It is accessed through a Nether portal built from obsidian.
- Travel in the Nether uses an 8:1 horizontal ratio versus the Overworld.
- It has no daylight cycle and no weather.', node_type: 'content', created_at: '2026-08-24T10:14:04.456666', updated_at: '2026-08-24T10:14:04.456666', version: '1.0', metadata: {"source_id": "minecraft-wiki-the-nether", "title": "The Nether", "version": "", "edition": "", "chunk_type": "paragraph"};
MERGE (c:Content {id: 'chunk_minecraft-wiki-the-nether_11'}) SET title: 'The Nether', content: '- Beds explode in the Nether, while respawn anchors can be used to respawn there.
## Version Notes
- Java Edition build limit in the Nether is 256 blocks.
- Bedrock Edition build limit in the Nether is 128 blocks.', node_type: 'content', created_at: '2026-08-24T10:14:04.456666', updated_at: '2026-08-24T10:14:04.456666', version: '1.0', metadata: {"source_id": "minecraft-wiki-the-nether", "title": "The Nether", "version": "", "edition": "", "chunk_type": "paragraph"};

// 插入关系边
MERGE (e1:Entity {id: 'minecraft:blaze'})
MERGE (e2:Entity {id: 'minecraft:blaze_rod'})
MERGE (e1)-[r:RELATION {id: 'edge_0'}]->(e2)
SET relation_type: 'drops', evidence_text: '# Blaze - Type: `Mob` - Mob type: `Monster` - Source: https://minecraft.wiki/w/Blaze - Retrieved at: `2026-08-23T00:00:00Z` ## Summary A fiery hostile mob found in Nether fortresses and the only source of blaze rods. ## Key Facts - It has 20 HP. - It spawns in Nether fortresses at light level 11 or less. - It attacks with three small fireballs or melee attacks. - It drops blaze rods and 10 XP when killed by a player or tamed wolf. - It can ride boats and minecarts. ## Version Notes', confidence: 0.9, edge_type: 'relation', created_at: '2026-08-24T10:14:04.456666', updated_at: '2026-08-24T10:14:04.456666', version: '1.0', source_chunk_id: 'minecraft-wiki-blaze_0', source_title: 'Blaze', minecraft_version: '1.21.x';
MERGE (e1:Entity {id: 'minecraft:blaze'})
MERGE (e2:Entity {id: 'minecraft:nether_fortress'})
MERGE (e1)-[r:RELATION {id: 'edge_1'}]->(e2)
SET relation_type: 'spawns_in', evidence_text: '# Blaze - Type: `Mob` - Mob type: `Monster` - Source: https://minecraft.wiki/w/Blaze - Retrieved at: `2026-08-23T00:00:00Z` ## Summary A fiery hostile mob found in Nether fortresses and the only source of blaze rods. ## Key Facts - It has 20 HP. - It spawns in Nether fortresses at light level 11 or less. - It attacks with three small fireballs or melee attacks. - It drops blaze rods and 10 XP when killed by a player or tamed wolf. - It can ride boats and minecarts. ## Version Notes', confidence: 0.9, edge_type: 'relation', created_at: '2026-08-24T10:14:04.456666', updated_at: '2026-08-24T10:14:04.456666', version: '1.0', source_chunk_id: 'minecraft-wiki-blaze_0', source_title: 'Blaze', minecraft_version: '1.21.x';
MERGE (e1:Entity {id: 'minecraft:creeper'})
MERGE (e2:Entity {id: 'minecraft:gunpowder'})
MERGE (e1)-[r:RELATION {id: 'edge_2'}]->(e2)
SET relation_type: 'drops', evidence_text: '# Creeper - Type: `Mob` - Mob type: `Monster` - Source: https://minecraft.wiki/w/Creeper - Retrieved at: `2026-08-23T00:00:00Z` ## Summary A hostile mob that silently approaches players and explodes when close. ## Key Facts - It has 20 HP. - It naturally spawns in the Overworld at light level 0. - Its explosion can destroy blocks and deal major damage. - A lightning strike can turn it into a charged creeper. - It drops gunpowder and can rarely drop music discs or creeper heads. ## Version Notes', confidence: 0.9, edge_type: 'relation', created_at: '2026-08-24T10:14:04.456666', updated_at: '2026-08-24T10:14:04.456666', version: '1.0', source_chunk_id: 'minecraft-wiki-creeper_4', source_title: 'Creeper', minecraft_version: '1.21.x';
MERGE (e1:Entity {id: 'minecraft:creeper'})
MERGE (e2:Entity {id: 'minecraft:nether_fortress'})
MERGE (e1)-[r:RELATION {id: 'edge_3'}]->(e2)
SET relation_type: 'spawns_in', evidence_text: '# Creeper - Type: `Mob` - Mob type: `Monster` - Source: https://minecraft.wiki/w/Creeper - Retrieved at: `2026-08-23T00:00:00Z` ## Summary A hostile mob that silently approaches players and explodes when close. ## Key Facts - It has 20 HP. - It naturally spawns in the Overworld at light level 0. - Its explosion can destroy blocks and deal major damage. - A lightning strike can turn it into a charged creeper. - It drops gunpowder and can rarely drop music discs or creeper heads. ## Version Notes', confidence: 0.9, edge_type: 'relation', created_at: '2026-08-24T10:14:04.456666', updated_at: '2026-08-24T10:14:04.456666', version: '1.0', source_chunk_id: 'minecraft-wiki-creeper_4', source_title: 'Creeper', minecraft_version: '1.21.x';
