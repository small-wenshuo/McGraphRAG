"""
Minecraft GraphRAG 数据处理主脚本
整合文本清洗、实体抽取、关系抽取、图谱构建和向量化索引
"""

import json
import os
from pathlib import Path
from typing import List, Dict, Any
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DataProcessor:
    """数据处理器"""

    def __init__(self, data_dir: str = "D:\codex\mcGraph\model"):
        """
        初始化处理器

        Args:
            data_dir: 数据目录
        """
        self.data_dir = Path(data_dir)
        self.processed_dir = self.data_dir / "processed"
        self.processed_dir.mkdir(exist_ok=True)

        # 模块路径
        self.modules = {
            'text_cleaning': r"D:\codex\mcGraph\src\data_processing\text_cleaning.py",
            'entity_extraction': r"D:\codex\mcGraph\src\data_processing\entity_extraction.py",
            'relation_extraction': r"D:\codex\mcGraph\src\data_processing\relation_extraction.py",
            'knowledge_graph': r"D:\codex\mcGraph\src\data_processing\knowledge_graph.py",
            'vector_indexing': r"D:\codex\mcGraph\src\data_processing\vector_indexing.py"
        }

    def step1_clean_and_chunk(self) -> bool:
        """
        步骤1: 文本清洗和切块

        Returns:
            是否成功
        """
        logger.info("步骤1: 开始文本清洗和切块...")

        try:
            # 导入文本清洗模块
            from data_processing.text_cleaning import TextCleaner

            # 创建清洗器
            cleaner = TextCleaner()

            # 加载文档
            md_dir = self.data_dir / "raw" / "firecrawl" / "pages"
            documents = cleaner.load_documents_from_markdown(str(md_dir))

            if not documents:
                logger.error("没有找到任何文档")
                return False

            logger.info(f"加载了 {len(documents)} 个文档")

            # 清洗并切块
            chunks = cleaner.clean_and_chunk_documents(documents, max_chunk_size=512)

            # 保存结果
            output_file = self.processed_dir / "cleaned_chunks.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(chunks, f, ensure_ascii=False, indent=2)

            logger.info(f"清洗完成，生成了 {len(chunks)} 个chunks")
            logger.info(f"结果已保存到: {output_file}")

            return True

        except Exception as e:
            logger.error(f"文本清洗失败: {e}")
            return False

    def step2_extract_entities(self) -> bool:
        """
        步骤2: 实体抽取

        Returns:
            是否成功
        """
        logger.info("步骤2: 开始实体抽取...")

        try:
            # 导入实体抽取模块
            from data_processing.entity_extraction import EntityExtractor

            # 创建抽取器
            extractor = EntityExtractor()

            # 抽取实体
            entities = extractor.extract_all_entities(str(self.processed_dir))

            if not entities:
                logger.error("没有抽取到任何实体")
                return False

            logger.info(f"实体抽取完成，共提取 {len(entities)} 个实体")

            # 实体统计
            entity_types = {}
            for entity in entities:
                entity_type = entity['type']
                entity_types[entity_type] = entity_types.get(entity_type, 0) + 1

            logger.info("实体类型统计:")
            for entity_type, count in entity_types.items():
                logger.info(f"  {entity_type}: {count}")

            return True

        except Exception as e:
            logger.error(f"实体抽取失败: {e}")
            return False

    def step3_extract_relations(self) -> bool:
        """
        步骤3: 关系抽取

        Returns:
            是否成功
        """
        logger.info("步骤3: 开始关系抽取...")

        try:
            # 导入关系抽取模块（使用简化的直接抽取）
            from data_processing.direct_relation_extraction import DirectRelationExtractor

            # 创建抽取器
            extractor = DirectRelationExtractor()

            # 抽取关系
            relations = extractor.extract_all_relations(
                chunks_file=str(self.processed_dir / "cleaned_chunks.json"),
                output_dir=str(self.processed_dir)
            )

            if not relations:
                logger.error("没有抽取到任何关系")
                return False

            logger.info(f"关系抽取完成，共提取 {len(relations)} 个关系")

            # 关系统计
            relation_types = {}
            for relation in relations:
                rel_type = relation['relation_type']
                relation_types[rel_type] = relation_types.get(rel_type, 0) + 1

            logger.info("关系类型统计:")
            for rel_type, count in relation_types.items():
                logger.info(f"  {rel_type}: {count}")

            return True

        except Exception as e:
            logger.error(f"关系抽取失败: {e}")
            return False

    def step4_build_knowledge_graph(self) -> bool:
        """
        步骤4: 构建知识图谱

        Returns:
            是否成功
        """
        logger.info("步骤4: 开始构建知识图谱...")

        try:
            # 导入知识图谱模块（使用简化版）
            from data_processing.simple_knowledge_graph import SimpleKnowledgeGraphBuilder

            # 创建构建器
            builder = SimpleKnowledgeGraphBuilder()

            # 加载数据
            entities_file = self.processed_dir / "extracted_entities.json"
            relations_file = self.processed_dir / "extracted_relations.json"

            if not entities_file.exists() or not relations_file.exists():
                logger.error("请先运行步骤2和步骤3")
                return False

            builder.load_data(str(entities_file), str(relations_file))

            # 导出为JSON
            graph_data = builder.export_to_json(str(self.processed_dir))

            # 导出为Neo4j
            builder.export_to_neo4j_simple(str(self.processed_dir))

            # 打印统计信息
            stats = builder.get_graph_statistics()
            logger.info("知识图谱统计信息:")
            logger.info(f"  总节点数: {stats['total_nodes']}")
            logger.info(f"  总边数: {stats['total_edges']}")
            logger.info(f"  节点类型数: {len(stats['node_types'])}")
            logger.info(f"  关系类型数: {len(stats['relation_types'])}")

            return True

        except Exception as e:
            logger.error(f"知识图谱构建失败: {e}")
            return False

    def step5_build_vector_index(self) -> bool:
        """
        步骤5: 构建向量索引

        Returns:
            是否成功
        """
        logger.info("步骤5: 开始构建向量索引...")

        try:
            # 导入向量化索引模块（使用简化版）
            from data_processing.vector_indexing_milvusclient_full import VectorIndexBuilder

            # 创建构建器
            builder = VectorIndexBuilder()

            # 创建向量索引
            success = builder.create_vector_index()

            if success:
                logger.info("向量索引创建成功")
            else:
                logger.error("向量索引创建失败")

            return success

        except ImportError as e:
            logger.error(f"向量索引模块导入失败: {e}")
            logger.info("请安装必要的依赖：")
            logger.info("pip install pymilvus sentence-transformers")
            return False
        except Exception as e:
            logger.error(f"向量索引构建失败: {e}")
            return False

    def run_all_steps(self) -> bool:
        """
        运行所有处理步骤

        Returns:
            是否全部成功
        """
        logger.info("开始运行数据处理流程...")

        # 检查数据目录
        if not self.data_dir.exists():
            logger.error(f"数据目录不存在: {self.data_dir}")
            return False

        # 定义步骤
        steps = [
            ("文本清洗和切块", self.step1_clean_and_chunk),
            ("实体抽取", self.step2_extract_entities),
            ("关系抽取", self.step3_extract_relations),
            ("知识图谱构建", self.step4_build_knowledge_graph),
            ("向量索引构建", self.step5_build_vector_index)
        ]

        # 执行步骤
        success_count = 0
        for step_name, step_func in steps:
            logger.info(f"\n{'='*50}")
            logger.info(f"执行步骤: {step_name}")
            logger.info(f"{'='*50}")

            try:
                if step_func():
                    logger.info(f"✓ {step_name} 成功")
                    success_count += 1
                else:
                    logger.error(f"✗ {step_name} 失败")
                    # 某些步骤失败时跳过后续步骤
                    if step_name in ["实体抽取", "关系抽取"]:
                        logger.error("实体或关系抽取失败，无法继续后续步骤")
                        break
                    elif step_name == "知识图谱构建":
                        logger.error("知识图谱构建失败，无法构建向量索引")
                        break
            except Exception as e:
                logger.error(f"✗ {step_name} 执行异常: {e}")

        logger.info(f"\n{'='*50}")
        logger.info(f"处理完成！成功 {success_count}/{len(steps)} 个步骤")
        logger.info(f"{'='*50}")

        return success_count == len(steps)

    def check_processed_data(self) -> Dict[str, Any]:
        """
        检查已处理的数据

        Returns:
            检查结果
        """
        logger.info("检查已处理的数据...")

        # 检查文件
        expected_files = [
            "cleaned_chunks.json",
            "extracted_entities.json",
            "extracted_relations.json",
            "knowledge_graph.json",
            "graph_nodes.json",
            "graph_edges.json",
            "neo4j_import.cypher",
            "vector_config.json"
        ]

        results = {
            'total_files': len(expected_files),
            'existing_files': 0,
            'missing_files': [],
            'file_sizes': {}
        }

        for file_name in expected_files:
            file_path = self.processed_dir / file_name
            if file_path.exists():
                results['existing_files'] += 1
                size = file_path.stat().st_size
                results['file_sizes'][file_name] = f"{size / 1024:.2f} KB"
            else:
                results['missing_files'].append(file_name)

        logger.info(f"已存在 {results['existing_files']}/{results['total_files']} 个文件")
        if results['missing_files']:
            logger.info("缺失的文件:")
            for file_name in results['missing_files']:
                logger.info(f"  - {file_name}")

        return results


def main():
    """主函数"""
    print("Minecraft GraphRAG 数据处理流程")
    print("=" * 50)

    # 创建处理器
    processor = DataProcessor()

    # 检查已处理的数据
    # processor.check_processed_data()

    # 询问用户
    choice = input("\n请选择操作:\n")
    if choice == "1":
        # 只运行数据清洗
        processor.step1_clean_and_chunk()
    elif choice == "2":
        # 只运行实体抽取
        processor.step2_extract_entities()
    elif choice == "3":
        # 只运行关系抽取
        processor.step3_extract_relations()
    elif choice == "4":
        # 只运行知识图谱构建
        processor.step4_build_knowledge_graph()
    elif choice == "5":
        # 只运行向量索引构建
        processor.step5_build_vector_index()
    else:
        # 运行所有步骤
        processor.run_all_steps()


if __name__ == "__main__":
    main()