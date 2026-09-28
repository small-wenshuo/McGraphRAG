"""
简化知识图谱构建模块
功能：将实体和关系构建为知识图谱，避免复杂的引号问题
"""

import json
import uuid
from typing import List, Dict, Any
from datetime import datetime
from pathlib import Path


class SimpleKnowledgeGraphBuilder:
    """简化知识图谱构建器"""

    def __init__(self):
        """初始化构建器"""
        # 图谱数据
        self.nodes = {}
        self.edges = {}

        # 实体映射
        self.entities = []

        # 关系列表
        self.relations = []

        # 版本信息
        self.version_info = {
            'minecraft_version': '1.21.x',
            'data_version': '1.0',
            'build_time': datetime.now().isoformat()
        }

    def load_data(self, entities_file: str, relations_file: str):
        """
        加载实体和关系数据

        Args:
            entities_file: 实体文件路径
            relations_file: 关系文件路径
        """
        # 加载实体
        with open(entities_file, 'r', encoding='utf-8') as f:
            self.entities = json.load(f)

        # 加载关系
        with open(relations_file, 'r', encoding='utf-8') as f:
            self.relations = json.load(f)

    def build_nodes(self) -> Dict[str, Dict[str, Any]]:
        """
        构建知识图谱节点

        Returns:
            节点字典 {node_id: node_data}
        """
        # 清空现有节点
        self.nodes = {}

        # 从实体数据构建节点
        for entity in self.entities:
            node_id = entity['id']

            # 构建节点数据（兼容不同的实体格式）
            node = {
                'id': node_id,
                'type': entity.get('type', 'unknown'),
                'name_zh': entity.get('name', entity.get('name_zh', '')),
                'name_en': entity.get('name_en', entity.get('name', '')),
                'aliases': entity.get('aliases', []),
                'properties': entity.get('properties', {}),
                'node_type': 'entity',
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat(),
                'version': self.version_info['data_version'],
                'sources': []  # 来源将在添加关系时补充
            }

            self.nodes[node_id] = node

        # 从chunk内容构建内容节点
        chunks_file = "F:/all project/mcGraphrag/data/processed/cleaned_chunks.json"
        with open(chunks_file, 'r', encoding='utf-8') as f:
            chunks = json.load(f)

        for chunk in chunks:
            # 创建内容节点ID
            content_node_id = f"chunk_{chunk['chunk_id']}"

            # 创建内容节点
            content_node = {
                'id': content_node_id,
                'type': 'content',
                'content': chunk['content'],
                'title': chunk['title'],
                'source_id': chunk.get('source_id', ''),
                'metadata': chunk.get('metadata', {}),
                'node_type': 'content',
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat(),
                'version': self.version_info['data_version'],
                'sources': [chunk.get('source_url', '')]
            }

            self.nodes[content_node_id] = content_node

        return self.nodes

    def build_edges(self) -> Dict[str, Dict[str, Any]]:
        """
        构建知识图谱边

        Returns:
            边字典 {edge_id: edge_data}
        """
        # 清空现有边
        self.edges = {}

        # 从关系数据构建边
        for i, relation in enumerate(self.relations):
            edge_id = f"edge_{i}"

            # 构建边数据
            edge = {
                'id': edge_id,
                'source_id': relation['subject_id'],
                'target_id': relation['object_id'],
                'relation_type': relation['relation_type'],
                'evidence_text': relation['evidence_text'],
                'confidence': relation['confidence'],
                'source_chunk_id': relation.get('source_chunk_id', ''),
                'source_title': relation.get('source_title', ''),
                'source_url': relation.get('source_url', ''),
                'edge_type': 'relation',
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat(),
                'version': self.version_info['data_version'],
                'minecraft_version': self.version_info['minecraft_version']
            }

            self.edges[edge_id] = edge

        # 添加内容节点到实体节点的引用边
        self._add_content_to_entity_edges()

        return self.edges

    def _add_content_to_entity_edges(self):
        """添加内容节点到实体节点的引用边"""
        chunks_file = "F:/all project/mcGraphrag/data/processed/cleaned_chunks.json"
        with open(chunks_file, 'r', encoding='utf-8') as f:
            chunks = json.load(f)

        for chunk in chunks:
            # 创建内容节点ID
            content_node_id = f"chunk_{chunk['chunk_id']}"

            # 简单的实体匹配
            entity_names = set()
            for entity in self.entities:
                # 安全地获取实体名称
                name_zh = entity.get('name_zh', entity.get('name', ''))
                name_en = entity.get('name_en', entity.get('name', ''))
                if name_zh:
                    entity_names.add(name_zh)
                if name_en:
                    entity_names.add(name_en)
                entity_names.update(entity.get('aliases', []))

            # 检查chunk内容中是否包含实体名称
            for entity_name in entity_names:
                if entity_name in chunk['content']:
                    entity_id = None
                    for entity in self.entities:
                        name_zh = entity.get('name_zh', entity.get('name', ''))
                    name_en = entity.get('name_en', entity.get('name', ''))
                    if (name_zh == entity_name or
                        name_en == entity_name or
                        entity_name in entity.get('aliases', [])):
                            entity_id = entity['id']
                            break

                    if entity_id:
                        # 创建引用边
                        edge_id = f"ref_{len(self.edges)}"
                        edge = {
                            'id': edge_id,
                            'source_id': content_node_id,
                            'target_id': entity_id,
                            'relation_type': 'mentions',
                            'evidence_text': f"Chunk {chunk['chunk_id']} mentions {entity_name}",
                            'confidence': 1.0,
                            'edge_type': 'reference',
                            'created_at': datetime.now().isoformat(),
                            'updated_at': datetime.now().isoformat(),
                            'version': self.version_info['data_version']
                        }
                        self.edges[edge_id] = edge

    def export_to_json(self, output_dir: str = "F:/all project/mcGraphrag/data/processed"):
        """
        导出图谱为JSON格式

        Args:
            output_dir: 输出目录
        """
        # 构建图谱
        nodes = self.build_nodes()
        edges = self.build_edges()

        # 更新节点来源
        self.update_node_sources()

        # 构建图谱数据
        graph_data = {
            'metadata': {
                'graph_type': 'minecraft_knowledge_graph',
                'minecraft_version': self.version_info['minecraft_version'],
                'data_version': self.version_info['data_version'],
                'build_time': self.version_info['build_time'],
                'node_count': len(nodes),
                'edge_count': len(edges),
                'entity_count': len(self.entities),
                'relation_count': len(self.relations)
            },
            'nodes': nodes,
            'edges': edges,
            'schema': {
                'node_types': list(set(node['type'] for node in nodes.values())),
                'relation_types': list(set(edge['relation_type'] for edge in edges.values())),
                'entity_types': list(set(entity['type'] for entity in self.entities))
            }
        }

        # 保存完整图谱
        output_file = f"{output_dir}/knowledge_graph.json"
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(graph_data, f, ensure_ascii=False, indent=2)

        # 分别保存节点和边
        nodes_file = f"{output_dir}/graph_nodes.json"
        with open(nodes_file, 'w', encoding='utf-8') as f:
            json.dump(nodes, f, ensure_ascii=False, indent=2)

        edges_file = f"{output_dir}/graph_edges.json"
        with open(edges_file, 'w', encoding='utf-8') as f:
            json.dump(edges, f, ensure_ascii=False, indent=2)

        print(f"知识图谱构建完成")
        print(f"  节点数量: {len(nodes)}")
        print(f"  边数量: {len(edges)}")
        print(f"  实体数量: {len(self.entities)}")
        print(f"  关系数量: {len(self.relations)}")
        print(f"  完整图谱已保存到: {output_file}")
        print(f"  节点数据已保存到: {nodes_file}")
        print(f"  边数据已保存到: {edges_file}")

        return graph_data

    def export_to_neo4j_simple(self, output_dir: str = "F:/all project/mcGraphrag/data/processed"):
        """
        导出为简单的Neo4j脚本（避免引号问题）

        Args:
            output_dir: 输出目录
        """
        # 构建图谱
        nodes = self.build_nodes()
        edges = self.build_edges()

        # 生成简单的Cypher脚本
        cypher_script = []
        cypher_script.append("// Minecraft 知识图谱 - 简化Neo4j导入脚本")
        cypher_script.append(f"// 构建时间: {datetime.now().isoformat()}")
        cypher_script.append("")

        # 创建约束
        cypher_script.append("// 创建约束")
        cypher_script.append("CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (e:Entity) REQUIRE e.id IS UNIQUE;")
        cypher_script.append("CREATE CONSTRAINT content_id IF NOT EXISTS FOR (c:Content) REQUIRE c.id IS UNIQUE;")
        cypher_script.append("")

        # 插入实体节点
        cypher_script.append("// 插入实体节点")
        for node in nodes.values():
            if node['node_type'] == 'entity':
                # 使用简单的属性设置
                props = []
                props.append(f"name_zh: '{node['name_zh']}'")
                props.append(f"name_en: '{node['name_en']}'")
                props.append(f"type: '{node['type']}'")
                props.append(f"node_type: '{node['node_type']}'")

                if node['aliases']:
                    props.append(f"aliases: {json.dumps(node['aliases'], ensure_ascii=False)}")
                if node['properties']:
                    props.append(f"properties: {json.dumps(node['properties'], ensure_ascii=False)}")

                props.append(f"created_at: '{node['created_at']}'")
                props.append(f"updated_at: '{node['updated_at']}'")
                props.append(f"version: '{node['version']}'")

                props_str = ', '.join(props)
                cypher_script.append(f"MERGE (e:Entity {{id: '{node['id']}'}}) SET {props_str};")

        cypher_script.append("")

        # 插入内容节点
        cypher_script.append("// 插入内容节点")
        for node in nodes.values():
            if node['node_type'] == 'content':
                props = []
                props.append(f"title: '{node['title']}'")
                props.append(f"content: '{node['content']}'")
                props.append(f"node_type: '{node['node_type']}'")
                props.append(f"created_at: '{node['created_at']}'")
                props.append(f"updated_at: '{node['updated_at']}'")
                props.append(f"version: '{node['version']}'")

                if node['metadata']:
                    props.append(f"metadata: {json.dumps(node['metadata'], ensure_ascii=False)}")

                props_str = ', '.join(props)
                cypher_script.append(f"MERGE (c:Content {{id: '{node['id']}'}}) SET {props_str};")

        cypher_script.append("")

        # 插入关系边
        cypher_script.append("// 插入关系边")
        for edge in edges.values():
            if edge['edge_type'] == 'relation':
                props = []
                props.append(f"relation_type: '{edge['relation_type']}'")
                props.append(f"evidence_text: '{edge['evidence_text']}'")
                props.append(f"confidence: {edge['confidence']}")
                props.append(f"edge_type: '{edge['edge_type']}'")
                props.append(f"created_at: '{edge['created_at']}'")
                props.append(f"updated_at: '{edge['updated_at']}'")
                props.append(f"version: '{edge['version']}'")

                if edge.get('source_chunk_id'):
                    props.append(f"source_chunk_id: '{edge['source_chunk_id']}'")
                if edge.get('source_title'):
                    props.append(f"source_title: '{edge['source_title']}'")
                if edge.get('source_url'):
                    props.append(f"source_url: '{edge['source_url']}'")
                if edge.get('minecraft_version'):
                    props.append(f"minecraft_version: '{edge['minecraft_version']}'")

                props_str = ', '.join(props)
                cypher_script.append(f"MERGE (e1:Entity {{id: '{edge['source_id']}'}})")
                cypher_script.append(f"MERGE (e2:Entity {{id: '{edge['target_id']}'}})")
                cypher_script.append(f"MERGE (e1)-[r:RELATION {{id: '{edge['id']}'}}]->(e2)")
                cypher_script.append(f"SET {props_str};")

        cypher_script.append("")

        # 保存Cypher脚本
        output_file = f"{output_dir}/neo4j_import_simple.cypher"
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(cypher_script))

        print(f"简化Neo4j Cypher脚本已保存到: {output_file}")

    def update_node_sources(self):
        """更新节点的来源信息"""
        # 为实体节点添加来源
        for edge in self.edges.values():
            if edge['edge_type'] == 'relation':
                # 添加到源节点的sources
                if edge['source_id'] in self.nodes:
                    source_node = self.nodes[edge['source_id']]
                    if edge['source_url'] not in source_node['sources']:
                        source_node['sources'].append(edge['source_url'])
                        source_node['updated_at'] = datetime.now().isoformat()

                # 添加到目标节点的sources
                if edge['target_id'] in self.nodes:
                    target_node = self.nodes[edge['target_id']]
                    if edge['source_url'] not in target_node['sources']:
                        target_node['sources'].append(edge['source_url'])
                        target_node['updated_at'] = datetime.now().isoformat()

    def get_graph_statistics(self) -> Dict[str, Any]:
        """
        获取图谱统计信息

        Returns:
            统计信息字典
        """
        if not self.nodes:
            self.build_nodes()
        if not self.edges:
            self.build_edges()

        # 统计节点类型
        node_type_counts = {}
        for node in self.nodes.values():
            node_type = node['type']
            node_type_counts[node_type] = node_type_counts.get(node_type, 0) + 1

        # 统计关系类型
        relation_type_counts = {}
        for edge in self.edges.values():
            relation_type = edge['relation_type']
            relation_type_counts[relation_type] = relation_type_counts.get(relation_type, 0) + 1

        # 统置信度分布
        confidence_stats = {
            'mean': sum(e['confidence'] for e in self.edges.values()) / len(self.edges),
            'min': min(e['confidence'] for e in self.edges.values()),
            'max': max(e['confidence'] for e in self.edges.values())
        }

        # 统计来源分布
        source_counts = {}
        for edge in self.edges.values():
            source = edge.get('source_url', 'unknown')
            source_counts[source] = source_counts.get(source, 0) + 1

        stats = {
            'total_nodes': len(self.nodes),
            'total_edges': len(self.edges),
            'node_types': node_type_counts,
            'relation_types': relation_type_counts,
            'confidence_stats': confidence_stats,
            'source_distribution': source_counts
        }

        return stats


def main():
    """主函数：演示知识图谱构建"""
    # 创建构建器
    builder = SimpleKnowledgeGraphBuilder()

    # 加载数据
    entities_file = "F:/all project/mcGraphrag/data/processed/extracted_entities.json"
    relations_file = "F:/all project/mcGraphrag/data/processed/extracted_relations.json"

    try:
        builder.load_data(entities_file, relations_file)

        # 导出为JSON
        graph_data = builder.export_to_json(str(Path("F:/all project/mcGraphrag/data/processed")))

        # 导出为Neo4j
        builder.export_to_neo4j_simple(str(Path("F:/all project/mcGraphrag/data/processed")))

        # 打印统计信息
        stats = builder.get_graph_statistics()
        print("\n=== 图谱统计信息 ===")
        print(f"总节点数: {stats['total_nodes']}")
        print(f"总边数: {stats['total_edges']}")
        print(f"节点类型数: {len(stats['node_types'])}")
        print(f"关系类型数: {len(stats['relation_types'])}")
        print(f"置信度统计:")
        print(f"  平均: {stats['confidence_stats']['mean']:.2f}")
        print(f"  最小: {stats['confidence_stats']['min']:.2f}")
        print(f"  最大: {stats['confidence_stats']['max']:.2f}")

    except FileNotFoundError as e:
        print(f"错误: {e}")
        print("请先运行实体抽取和关系抽取模块")


if __name__ == "__main__":
    main()