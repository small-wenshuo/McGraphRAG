"""
简化关系抽取模块
功能：从文本中抽取实体间的关系，更容易调试和维护
"""

import json
import re
from typing import List, Dict, Any, Set
from pathlib import Path


class SimpleRelationExtractor:
    """简化关系抽取器"""

    def __init__(self):
        """初始化抽取器"""
        # 定义简单的实体列表（来自原始entities.json）
        self.entities = self._load_entities()

        # 定义关系模式（简化版本）
        self.relation_patterns = {
            # 掉落关系
            'drops': [
                # 英文 - 改进匹配模式
                (r'(?P<subject>\w+)\s+(?:drops?|dropping)\s+(?:and|or)?\s+(?P<object>\w+\s*\w*)',
                 1.0),
                (r'(?P<subject>\w+)\s+(?:drops?|dropping)\s+(?:and|or)?\s+(?P<object>\w+)',
                 1.0),
                (r'(?P<object>\w+\s*\w*)\s+(?:is|are)\s+(?:dropped|dropping)\s+(?:by|from)\s+(?P<subject>\w+)',
                 0.9),
                # 中文
                (r'(?P<subject>.+?)\s*掉落\s*(?:了|)?\s*(?P<object>.+)',
                 1.0),
                (r'(?P<object>.+?)\s*被\s*击败\s*后\s*会\s*掉\s*(?P<subject>.+)',
                 0.9)
            ],
            # 生成于关系
            'spawns_in': [
                # 英文
                (r'(?P<subject>\w+)\s*(?:spawns?|spawning)\s+(?:in|at|inside)\s+(?P<object>\w+)',
                 1.0),
                (r'(?P<subject>\w+)\s*(?:can\s+be\s+found\s+in|generates?\s+in)\s+(?P<object>\w+)',
                 0.9),
                # 中文
                (r'(?P<subject>.+?)\s*生成于\s*(?P<object>.+)',
                 1.0),
                (r'(?P<subject>.+?)\s*在\s*(?P<object>.+?)\s*生成',
                 0.9)
            ],
            # 合成关系
            'crafted_from': [
                # 英文
                (r'(?P<subject>\w+)\s*(?:is\s+made\s+from|crafted\s+from)\s+(?P<object>\w+)',
                 1.0),
                (r'(?P<subject>\w+)\s*(?:requires|needs?)\s+(?P<object>\w+)',
                 0.9),
                # 中文
                (r'(?P<subject>.+?)\s*由\s*(?P<object>.+?)\s*制成',
                 1.0),
                (r'(?P<object>.+?)\s*是\s*(?P<subject>.+?)\s*的\s*合成材料',
                 0.9)
            ],
            # 用于关系
            'used_for': [
                # 英文
                (r'(?P<subject>\w+)\s*(?:is\s+used\s+for|can\s+be\s+used\s+for)\s+(?P<object>\w+)',
                 1.0),
                # 中文
                (r'(?P<subject>.+?)\s*用于\s*(?P<object>.+)',
                 1.0),
                (r'(?P<object>.+?)\s*需要\s*(?P<subject>.+)',
                 0.9)
            ]
        }

    def _load_entities(self) -> Dict[str, Dict[str, Any]]:
        """加载实体数据"""
        entities = {}
        try:
            with open("F:/all project/mcGraphrag/data/raw/entities.json", 'r', encoding='utf-8') as f:
                entity_list = json.load(f)
                for entity in entity_list:
                    entities[entity['id']] = entity
        except FileNotFoundError:
            # 如果文件不存在，创建一些基础实体
            entities = {
                'minecraft:creeper': {'id': 'minecraft:creeper', 'name_zh': '苦力怕', 'name_en': 'Creeper'},
                'minecraft:gunpowder': {'id': 'minecraft:gunpowder', 'name_zh': '火药', 'name_en': 'Gunpowder'},
                'minecraft:blaze': {'id': 'minecraft:blaze', 'name_zh': '烈焰人', 'name_en': 'Blaze'},
                'minecraft:blaze_rod': {'id': 'minecraft:blaze_rod', 'name_zh': '烈焰棒', 'name_en': 'Blaze Rod'},
                'minecraft:nether_fortress': {'id': 'minecraft:nether_fortress', 'name_zh': '下界要塞', 'name_en': 'Nether Fortress'},
                'minecraft:the_nether': {'id': 'minecraft:the_nether', 'name_zh': '下界', 'name_en': 'The Nether'},
                'minecraft:crafting_table': {'id': 'minecraft:crafting_table', 'name_zh': '工作台', 'name_en': 'Crafting Table'},
                'minecraft:diamond_pickaxe': {'id': 'minecraft:diamond_pickaxe', 'name_zh': '钻石镐', 'name_en': 'Diamond Pickaxe'},
                'minecraft:diamond': {'id': 'minecraft:diamond', 'name_zh': '钻石', 'name_en': 'Diamond'},
                'minecraft:stick': {'id': 'minecraft:stick', 'name_zh': '木棍', 'name_en': 'Stick'}
            }
        return entities

    def extract_relations_from_text(self, text: str) -> List[Dict[str, Any]]:
        """
        从文本中抽取关系

        Args:
            text: 输入文本

        Returns:
            关系列表
        """
        relations = []

        # 打印调试信息
        print(f"\n处理文本: {text}")

        # 对于每种关系类型
        for rel_type, patterns in self.relation_patterns.items():
            print(f"\n尝试关系类型: {rel_type}")
            for pattern, confidence in patterns:
                try:
                    # 查找所有匹配
                    matches = re.finditer(pattern, text, re.IGNORECASE)
                    match_count = 0
                    for match in matches:
                        match_count += 1
                        # 提取实体名称
                        subject_name = match.group('subject').strip()
                        object_name = match.group('object').strip()

                        print(f"  匹配到: subject='{subject_name}', object='{object_name}'")

                        # 标准化实体名称
                        subject_id = self._find_entity_id(subject_name)
                        object_id = self._find_entity_id(object_name)

                        print(f"  标准化后: subject_id='{subject_id}', object_id='{object_id}'")

                        # 检查实体是否有效
                        if subject_id and object_id and subject_id != object_id:
                            # 创建关系
                            relation = {
                                'relation_type': rel_type,
                                'subject_id': subject_id,
                                'subject_name': self._get_entity_name(subject_id),
                                'object_id': object_id,
                                'object_name': self._get_entity_name(object_id),
                                'evidence_text': text[match.start():match.end()],
                                'confidence': confidence,
                                'source_text': text
                            }
                            relations.append(relation)
                            print(f"  成功添加关系: {subject_id} -> {rel_type} -> {object_id}")
                        else:
                            print(f"  无效实体，跳过")
                except re.error as e:
                    print(f"正则表达式错误: {e}")
                    continue
                print(f"  该模式匹配次数: {match_count}")

        print(f"\n总共找到 {len(relations)} 个关系")

        # 去重
        relations = self._deduplicate_relations(relations)

        return relations

    def _find_entity_id(self, name: str) -> str:
        """
        根据名称查找实体ID

        Args:
            name: 实体名称

        Returns:
            实体ID，如果找不到返回None
        """
        if not name or not name.strip():
            return None

        name = name.strip()

        # 直接匹配
        for entity_id, entity in self.entities.items():
            if name == entity['id'] or name == entity['name_zh'] or name == entity['name_en']:
                return entity_id

        # 检查别名
        for entity_id, entity in self.entities.items():
            aliases = entity.get('aliases', [])
            if name in aliases:
                return entity_id

        # 尝试部分匹配
        for entity_id, entity in self.entities.items():
            entity_names = [entity['id'], entity['name_zh'], entity['name_en']] + entity.get('aliases', [])
            for entity_name in entity_names:
                if name in entity_name or entity_name in name:
                    return entity_id

        return None

    def _get_entity_name(self, entity_id: str) -> str:
        """
        获取实体名称

        Args:
            entity_id: 实体ID

        Returns:
            实体中文名称
        """
        if entity_id in self.entities:
            return self.entities[entity_id]['name_zh']
        return entity_id

    def _deduplicate_relations(self, relations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        去重关系

        Args:
            relations: 关系列表

        Returns:
            去重后的关系列表
        """
        unique_relations = []
        seen = set()

        for relation in relations:
            # 创建唯一标识
            unique_key = (
                relation['subject_id'],
                relation['relation_type'],
                relation['object_id']
            )

            if unique_key not in seen:
                seen.add(unique_key)
                unique_relations.append(relation)

        return unique_relations

    def extract_relations_from_chunks(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        从chunks中抽取关系

        Args:
            chunks: chunk列表

        Returns:
            所有抽取的关系列表
        """
        all_relations = []

        for chunk in chunks:
            chunk_relations = self.extract_relations_from_text(chunk['content'])

            # 添加chunk来源信息
            for relation in chunk_relations:
                relation['source_chunk_id'] = chunk['chunk_id']
                relation['source_title'] = chunk['title']
                relation['source_url'] = chunk.get('source_url', '')

            all_relations.extend(chunk_relations)

        # 全局去重
        all_relations = self._deduplicate_relations(all_relations)

        return all_relations

    def extract_all_relations(self, chunks_file: str = "F:/all project/mcGraphrag/data/processed/cleaned_chunks.json",
                            output_dir: str = "F:/all project/mcGraphrag/data/processed"):
        """
        抽取所有关系并保存

        Args:
            chunks_file: chunks文件路径
            output_dir: 输出目录
        """
        # 加载chunks
        with open(chunks_file, 'r', encoding='utf-8') as f:
            chunks = json.load(f)

        # 抽取关系
        relations = self.extract_relations_from_chunks(chunks)

        # 保存关系
        output_file = f"{output_dir}/extracted_relations.json"
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(relations, f, ensure_ascii=False, indent=2)

        print(f"关系抽取完成，共提取 {len(relations)} 个关系")
        print(f"结果已保存到: {output_file}")

        # 统计关系类型分布
        relation_counts = {}
        for relation in relations:
            rel_type = relation['relation_type']
            relation_counts[rel_type] = relation_counts.get(rel_type, 0) + 1

        print("\n=== 关系类型统计 ===")
        for rel_type, count in relation_counts.items():
            print(f"{self.relation_types.get(rel_type, rel_type)}: {count} 个")

        return relations


def main():
    """主函数：测试关系抽取"""
    # 创建抽取器
    extractor = SimpleRelationExtractor()

    # 测试文本
    test_texts = [
        "Blaze drops blaze rods when killed.",
        "Creeper drops gunpowder.",
        "Blaze spawns in Nether fortresses.",
        "Blaze rods can be used to create brewing stands.",
        "Diamond pickaxe is crafted from 3 diamonds and 2 sticks."
    ]

    print("测试关系抽取...")
    for i, text in enumerate(test_texts, 1):
        print(f"\n测试文本 {i}: {text}")
        relations = extractor.extract_relations_from_text(text)
        print(f"抽取到 {len(relations)} 个关系:")
        for relation in relations:
            print(f"  - {relation['subject_name']} {relation['relation_type']} {relation['object_name']}")
            print(f"    证据: {relation['evidence_text']}")
            print(f"    置信度: {relation['confidence']}")


if __name__ == "__main__":
    main()