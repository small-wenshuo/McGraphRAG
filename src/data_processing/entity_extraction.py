"""
实体抽取模块
功能：从文本中识别实体，进行实体标准化，统一别名和命名空间ID
"""

import re
import json
from typing import List, Dict, Any, Set, Tuple
from collections import defaultdict
from pathlib import Path


class EntityExtractor:
    """实体抽取器"""

    def __init__(self):
        """初始化抽取器"""
        # 定义实体类型
        self.entity_types = {
            'item': ['物品', 'item', 'material', 'ingredient'],
            'block': ['方块', 'block', 'terrain'],
            'mob': ['生物', 'mob', 'creature', 'monster', 'entity'],
            'biome': ['生物群系', 'biome'],
            'structure': ['结构', 'structure', 'building'],
            'recipe': ['配方', 'recipe', 'crafting'],
            'enchantment': ['附魔', 'enchantment', 'enchant'],
            'potion': ['药水', 'potion', 'brew'],
            'command': ['命令', 'command'],
            'mechanic': ['机制', 'mechanic', 'feature']
        }

        # 初始化实体名称映射（可以从entities.json加载）
        self.entity_mapping = self._load_entity_mapping()

        # 实体别名映射
        self.alias_mapping = defaultdict(set)

        # 初始化实体名称到ID的映射
        self.name_to_id = {}
        self._init_alias_mapping()

        # 实体描述模式
        self.entity_patterns = {
            'item': [
                r'\b(?:物品|item)\s*[:：]?\s*(.+?)(?:\s|\.|$)',
                r'\b(.+?)\s*(?:物品|item)\b',
                r'\b合成原料：(.+?)\b',
                r'\b需要：(.+?)\b'
            ],
            'mob': [
                r'\b(?:类型|Type)\s*[:：]?\s*\`(\w+)`\b',
                r'\b(.+?)\s*(?:生物|mob|怪物|怪物)\b',
                r'\b(.+?)\s*(?: spawns? in)\b',
                r'\b(.+?)\s*(?: can be found)\b'
            ],
            'block': [
                r'\b(.+?)\s*(?:方块|block)\b',
                r'\b(.+?)\s*(?:Block)\b',
                r'\b材质：(.+?)\b'
            ],
            'structure': [
                r'\b(.+?)\s*(?:结构|structure|建筑)\b',
                r'\b(.+?)\s*(?:生成于|generates? in)\b',
                r'\b(.+?)\s*(?: generates in)\b'
            ],
            'biome': [
                r'\b(.+?)\s*(?:生物群系|biome)\b',
                r'\b(.+?)\s*(?:Dimension)\b'
            ]
        }

    def _load_entity_mapping(self) -> Dict[str, Any]:
        """从entities.json加载实体映射"""
        try:
            entities_file = "F:/all project/mcGraphrag/data/raw/entities.json"
            with open(entities_file, 'r', encoding='utf-8') as f:
                entities = json.load(f)
                return entities
        except FileNotFoundError:
            return []

    def _init_alias_mapping(self):
        """初始化别名映射"""
        for entity in self.entity_mapping:
            entity_id = entity['id']
            name_zh = entity['name_zh']
            name_en = entity['name_en']
            aliases = entity.get('aliases', [])

            # 添加标准名称
            self.name_to_id[name_zh] = entity_id
            self.name_to_id[name_en] = entity_id

            # 添加别名
            for alias in aliases:
                self.name_to_id[alias] = entity_id
                self.alias_mapping[entity_id].add(alias)

            # 添加ID本身
            self.name_to_id[entity_id] = entity_id

    def extract_entities_from_text(self, text: str,
                                 entity_type: str = None) -> List[Dict[str, Any]]:
        """
        从文本中抽取指定类型的实体

        Args:
            text: 输入文本
            entity_type: 实体类型，如果为None则抽取所有类型

        Returns:
            实体列表，每个实体包含id、名称、类型、位置等信息
        """
        entities = []

        if entity_type:
            types_to_extract = [entity_type]
        else:
            types_to_extract = self.entity_types.keys()

        for etype in types_to_extract:
            # 检查是否有对应的模式
            patterns = self.entity_patterns.get(etype, [])
            for pattern in patterns:
                matches = re.finditer(pattern, text, re.IGNORECASE)
                for match in matches:
                    entity_name = match.group(1).strip()

                    # 标准化实体名称
                    normalized_entity = self._normalize_entity(entity_name, etype)

                    if normalized_entity:
                        entity = {
                            'id': normalized_entity['id'],
                            'name': normalized_entity['name'],
                            'type': etype,
                            'aliases': list(self.alias_mapping.get(normalized_entity['id'], set())),
                            'position': match.span(),
                            'confidence': 0.8,  # 基础置信度
                            'evidence_text': text[match.start():match.end()]
                        }
                        entities.append(entity)

        # 去重：对于相同的实体ID，保留位置更靠前的
        entities = self._deduplicate_entities(entities)

        return entities

    def _normalize_entity(self, entity_name: str, entity_type: str) -> Dict[str, Any]:
        """
        标准化实体名称

        Args:
            entity_name: 实体名称
            entity_type: 实体类型

        Returns:
            标准化后的实体信息，包含ID和名称
        """
        # 首先检查是否在已知实体中
        if entity_name in self.name_to_id:
            entity_id = self.name_to_id[entity_name]
            # 找到对应的实体信息
            for entity in self.entity_mapping:
                if entity['id'] == entity_id:
                    return {
                        'id': entity_id,
                        'name': entity['name_zh']  # 使用中文名称作为标准名称
                    }

        # 如果没有找到，尝试名称匹配
        for entity in self.entity_mapping:
            # 检查名称相似度
            if (self._is_name_similar(entity_name, entity['name_zh']) or
                self._is_name_similar(entity_name, entity['name_en']) or
                entity_name in entity.get('aliases', [])):

                # 更新名称映射
                self.name_to_id[entity_name] = entity['id']
                for alias in entity.get('aliases', []):
                    self.alias_mapping[entity['id']].add(alias)

                return {
                    'id': entity['id'],
                    'name': entity['name_zh']
                }

        # 如果还是没找到，创建新实体（谨慎使用）
        if self._should_create_new_entity(entity_name, entity_type):
            new_id = f"minecraft:{self._generate_entity_id(entity_name)}"
            self.entity_mapping.append({
                'id': new_id,
                'type': entity_type,
                'name_zh': entity_name,
                'name_en': entity_name,
                'aliases': [entity_name]
            })

            # 更新映射
            self.name_to_id[entity_name] = new_id
            self.alias_mapping[new_id].add(entity_name)
            self.name_to_id[new_id] = new_id

            return {
                'id': new_id,
                'name': entity_name
            }

        return None

    def _is_name_similar(self, name1: str, name2: str, threshold: float = 0.8) -> bool:
        """
        检查两个名称是否相似

        Args:
            name1: 第一个名称
            name2: 第二个名称
            threshold: 相似度阈值

        Returns:
            是否相似
        """
        # 简单的相似度计算
        # 去除特殊字符和空白
        n1 = re.sub(r'[^\w\u4e00-\u9fff]', '', name1.lower())
        n2 = re.sub(r'[^\w\u4e00-\u9fff]', '', name2.lower())

        # 完全匹配
        if n1 == n2:
            return True

        # 包含关系
        if n1 in n2 or n2 in n1:
            return True

        # 计算编辑距离
        return self._edit_distance_ratio(n1, n2) > threshold

    def _edit_distance_ratio(self, s1: str, s2: str) -> float:
        """
        计算编辑距离比例

        Args:
            s1: 字符串1
            s2: 字符串2

        Returns:
            相似度比例（0-1）
        """
        if len(s1) < len(s2):
            s1, s2 = s2, s1

        if len(s1) == 0:
            return 1.0 if len(s2) == 0 else 0.0

        # 简单的编辑距离计算
        distance = 0
        i = j = 0
        while i < len(s1) and j < len(s2):
            if s1[i] == s2[j]:
                i += 1
                j += 1
            else:
                distance += 1
                if len(s1) > len(s2):
                    i += 1
                elif len(s1) < len(s2):
                    j += 1
                else:
                    i += 1
                    j += 1

        distance += len(s1) - i + len(s2) - j

        return 1 - distance / max(len(s1), len(s2))

    def _should_create_new_entity(self, name: str, entity_type: str) -> bool:
        """
        判断是否应该创建新实体

        Args:
            name: 实体名称
            entity_type: 实体类型

        Returns:
            是否创建
        """
        # 检查名称是否包含明显的噪声
        noise_words = ['教程', '攻略', '模组', '插件', '合成', '制作', '方法', '指南']
        for noise in noise_words:
            if noise in name.lower():
                return False

        # 检查名称长度
        if len(name) < 2:
            return False

        return True

    def _generate_entity_id(self, name: str) -> str:
        """
        生成实体ID

        Args:
            name: 实体名称

        Returns:
            实体ID
        """
        # 转换为小写，移除特殊字符，用下划线连接
        id_part = re.sub(r'[^\w]', '_', name.lower())
        # 移除连续的下划线
        id_part = re.sub(r'_+', '_', id_part)
        # 移除开头和结尾的下划线
        id_part = id_part.strip('_')

        # 确保ID不重复
        counter = 1
        base_id = id_part
        while any(e['id'] == f"minecraft:{base_id}" for e in self.entity_mapping):
            base_id = f"{id_part}_{counter}"
            counter += 1

        return base_id

    def _deduplicate_entities(self, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        去重实体

        Args:
            entities: 实体列表

        Returns:
            去重后的实体列表
        """
        seen = {}
        unique_entities = []

        # 按置信度排序，置信度高的优先
        entities.sort(key=lambda x: x['confidence'], reverse=True)

        for entity in entities:
            entity_id = entity['id']

            if entity_id not in seen:
                seen[entity_id] = entity
                unique_entities.append(entity)
            else:
                # 如果已存在，比较置信度，保留置信度高的
                if entity['confidence'] > seen[entity_id]['confidence']:
                    # 移除旧的，添加新的
                    unique_entities.remove(seen[entity_id])
                    seen[entity_id] = entity
                    unique_entities.append(entity)

        return unique_entities

    def extract_entities_from_chunks(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        从chunks中抽取实体

        Args:
            chunks: chunk列表

        Returns:
            所有抽取的实体列表
        """
        all_entities = []

        for chunk in chunks:
            chunk_entities = self.extract_entities_from_text(
                chunk['content'],
                entity_type=None
            )

            # 添加chunk来源信息
            for entity in chunk_entities:
                entity['source_chunk_id'] = chunk['chunk_id']
                entity['source_title'] = chunk['title']
                entity['source_url'] = chunk.get('source_url', '')

            all_entities.extend(chunk_entities)

        # 全局去重
        all_entities = self._deduplicate_entities(all_entities)

        return all_entities

    def extract_all_entities(self, output_dir: str = "F:/all project/mcGraphrag/data/processed"):
        """
        抽取所有实体并保存

        Args:
            output_dir: 输出目录
        """
        # 加载清洗后的chunks
        chunks_file = "F:/all project/mcGraphrag/data/processed/cleaned_chunks.json"
        with open(chunks_file, 'r', encoding='utf-8') as f:
            chunks = json.load(f)

        # 抽取实体
        entities = self.extract_entities_from_chunks(chunks)

        # 保存实体
        output_file = f"{output_dir}/extracted_entities.json"
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(entities, f, ensure_ascii=False, indent=2)

        print(f"实体抽取完成，共提取 {len(entities)} 个实体")
        print(f"结果已保存到: {output_file}")

        return entities


def main():
    """主函数：演示实体抽取"""
    # 创建实体抽取器
    extractor = EntityExtractor()

    # 抽取所有实体
    entities = extractor.extract_all_entities()

    # 打印一些示例
    print("\n=== 实体抽取示例 ===")
    for i, entity in enumerate(entities[:5]):
        print(f"\n实体 {i+1}:")
        print(f"  ID: {entity['id']}")
        print(f"  名称: {entity['name']}")
        print(f"  类型: {entity['type']}")
        print(f"  别名: {entity['aliases']}")
        print(f"  来源: {entity['source_title']}")
        print(f"  证据: {entity['evidence_text']}")


if __name__ == "__main__":
    main()