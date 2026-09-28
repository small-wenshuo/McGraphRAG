"""
检索系统
整合BM25、Milvus和知识图谱检索，并通过证据融合确定最佳证据集
"""

import time
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import json
from pathlib import Path

from base.config import Config
from mysql_qa.retrieval.bm25_search import BM25Search
from src.data_processing.vector_indexing_milvusclient_full import VectorIndexBuilder
from rag_qa.core.evidence_fusion import Evidence, EvidenceFusion, FusionResult


@dataclass
class RetrievalConfig:
    """检索配置"""
    bm25_top_k: int = 10
    milvus_top_k: int = 10
    graph_top_k: int = 8
    fusion_method: str = 'rrf'  # 'rrf' 或 'weighted'
    max_fused_evidence: int = 10
    max_core_evidence: int = 8
    core_max_tokens: int = 2000
    rrf_k: int = 60
    method_weights: Dict[str, float] = None


class RetrievalSystem:
    """检索系统"""

    def __init__(self,
                 bm25_index_path: Optional[str] = None,
                 milvus_ready: bool = True,
                 config: Optional[RetrievalConfig] = None):
        """
        初始化检索系统

        Args:
            bm25_index_path: BM25索引文件路径
            milvus_ready: Milvus是否已准备好
            config: 检索配置
        """
        self.config = config or RetrievalConfig()
        self.base_config = Config()

        # 设置方法权重
        if self.config.method_weights is None:
            self.config.method_weights = {
                'milvus': 0.5,
                'bm25': 0.3,
                'graph': 0.2
            }

        # 初始化证据融合器
        self.fusion = EvidenceFusion(
            rrf_k=self.config.rrf_k,
            method_weights=self.config.method_weights
        )

        # 初始化BM25检索器
        self.bm25 = BM25Search()
        if bm25_index_path and Path(bm25_index_path).exists():
            print(f"从文件加载BM25索引: {bm25_index_path}")
            self.bm25.load_index_from_file(bm25_index_path)
        else:
            print("警告：BM25索引未加载，需要先构建索引")

        # 初始化Milvus检索器
        self.milvus = None
        if milvus_ready:
            try:
                self.milvus = VectorIndexBuilder()
                if self.milvus.connect_to_milvus():
                    if self.milvus.client.has_collection(self.milvus.collection_name):
                        print("Milvus向量检索器初始化成功")
                    else:
                        print(f"Milvus集合不存在: {self.milvus.collection_name}，跳过向量检索")
                        self.milvus = None
                else:
                    print("警告：Milvus连接失败")
                    self.milvus = None
            except Exception as e:
                print(f"Milvus初始化失败: {e}")
                self.milvus = None

        print(f"检索系统初始化完成")
        print(f"配置: BM25_top_k={self.config.bm25_top_k}, "
              f"Milvus_top_k={self.config.milvus_top_k}, "
              f"Graph_top_k={self.config.graph_top_k}")

    def retrieve_bm25(self, query: str) -> List[Evidence]:
        """
        BM25检索

        Args:
            query: 查询文本

        Returns:
            BM25证据列表
        """
        if not self.bm25:
            print("BM25检索器未初始化")
            return []

        start_time = time.time()

        # 执行BM25检索
        results = self.bm25.search(query, top_k=self.config.bm25_top_k)

        # 转换为Evidence格式
        evidence_list = []
        for position, (score, doc) in enumerate(results, 1):
            evidence = Evidence(
                id=f"bm25_{doc.get('id', position)}",
                title=doc.get('title', ''),
                content=doc.get('content', ''),
                content_type='chunk',
                score=score,
                source='bm25',
                metadata=doc.get('metadata', {}),
                retrieval_method='bm25',
                position=position
            )
            evidence_list.append(evidence)

        elapsed = time.time() - start_time
        print(f"BM25检索耗时: {elapsed:.3f}s，返回 {len(evidence_list)} 个结果")

        return evidence_list

    def retrieve_milvus(self, query: str) -> List[Evidence]:
        """
        Milvus向量检索

        Args:
            query: 查询文本

        Returns:
            Milvus证据列表
        """
        if not self.milvus:
            print("Milvus检索器未初始化")
            return []

        start_time = time.time()

        try:
            # 执行Milvus检索
            results = self.milvus.search_vectors(query, top_k=self.config.milvus_top_k)

            # 转换为Evidence格式
            evidence_list = []
            for position, result in enumerate(results, 1):
                # 当前向量索引使用 IP，相似度越大越相关。
                score = result.get('score', result.get('distance', 0.0))

                evidence = Evidence(
                    id=f"milvus_{result.get('id', position)}",
                    title=result.get('title', ''),
                    content=result.get('content', ''),
                    content_type=result.get('content_type', 'chunk'),
                    score=score,
                    source='milvus',
                    metadata=result.get('metadata', {}),
                    retrieval_method='milvus',
                    position=position
                )
                evidence_list.append(evidence)

            elapsed = time.time() - start_time
            print(f"Milvus检索耗时: {elapsed:.3f}s，返回 {len(evidence_list)} 个结果")

            return evidence_list

        except Exception as e:
            print(f"Milvus检索失败: {e}")
            return []

    def retrieve_graph(self, query: str) -> List[Evidence]:
        """
        知识图谱检索

        Args:
            query: 查询文本

        Returns:
            图谱证据列表
        """
        start_time = time.time()
        raw_dir = Path(__file__).resolve().parents[2] / 'data' / 'raw'
        try:
            with (raw_dir / 'entities.json').open(encoding='utf-8') as f:
                entities = {item['id']: item for item in json.load(f)}
            with (raw_dir / 'relations.json').open(encoding='utf-8') as f:
                relations = json.load(f)
        except (OSError, ValueError) as e:
            print(f"图谱原始数据不可用: {e}")
            return []

        query_lower = query.lower()
        matched_ids = {
            entity_id for entity_id, entity in entities.items()
            if any(name and name.lower() in query_lower
                   for name in [entity.get('name_zh', ''), entity.get('name_en', ''),
                                *entity.get('aliases', [])])
        }
        evidence_list = []
        for relation in relations:
            if not ({relation['subject_id'], relation['object_id']} & matched_ids):
                continue
            subject = entities.get(relation['subject_id'], {})
            object_entity = entities.get(relation['object_id'], {})
            evidence_text = relation.get('evidence_text', '').strip()
            if not evidence_text:
                continue
            evidence_list.append(Evidence(
                id=f"graph_{relation['subject_id']}_{relation['predicate']}_{relation['object_id']}",
                title=f"{subject.get('name_zh', relation['subject_id'])} {relation['predicate']} {object_entity.get('name_zh', relation['object_id'])}",
                content=evidence_text,
                content_type='fact',
                score=float(relation.get('confidence', 0)),
                source='data/raw/relations.json',
                metadata={'subject_id': relation['subject_id'],
                          'object_id': relation['object_id'],
                          'predicate': relation['predicate']},
                retrieval_method='graph',
                position=len(evidence_list) + 1
            ))
            if len(evidence_list) >= self.config.graph_top_k:
                break

        print(f"图谱检索耗时: {time.time() - start_time:.3f}s，返回 {len(evidence_list)} 个结果")
        return evidence_list

    def _generate_graph_evidence(self, query: str, entity_seeds: List[str]) -> List[Evidence]:
        """
        基于实体种子生成图谱证据

        Args:
            query: 查询文本
            entity_seeds: 实体种子列表

        Returns:
            图谱证据列表
        """
        evidence_list = []

        # 1. 基于实体种子生成实体证据
        for seed in entity_seeds[:5]:  # 取前5个种子
            evidence = Evidence(
                id=f"graph_entity_{seed}",
                title=f"相关实体: {seed}",
                content=f"关于{seed}的实体信息",
                content_type='entity',
                score=0.8,  # 基于种子的相关性
                source='graph',
                metadata={
                    'entity_type': 'minecraft_entity',
                    'seed_entity': seed,
                    'query_relation': 'related'
                },
                retrieval_method='graph',
                position=len(evidence_list) + 1
            )
            evidence_list.append(evidence)

        # 2. 基于查询生成关系证据
        relation_keywords = ['制作', '获取', '生成', '行为', '特性']
        for keyword in relation_keywords:
            if keyword in query:
                evidence = Evidence(
                    id=f"graph_relation_{keyword}",
                    title=f"关系: {keyword}",
                    content=f"涉及{keyword}关系的游戏机制",
                    content_type='fact',
                    score=0.7,
                    source='graph',
                    metadata={
                        'relation_type': keyword,
                        'query_match': True
                    },
                    retrieval_method='graph',
                    position=len(evidence_list) + 1
                )
                evidence_list.append(evidence)

        # 3. 生成跨实体关系证据
        if len(entity_seeds) >= 2:
            for i, seed1 in enumerate(entity_seeds[:3]):
                for j, seed2 in enumerate(entity_seeds[i+1:i+3]):
                    evidence = Evidence(
                        id=f"graph_relation_{seed1}_{seed2}",
                        title=f"关系: {seed1} - {seed2}",
                        content=f"{seed1}与{seed2}之间的关系",
                        content_type='fact',
                        score=0.6,
                        source='graph',
                        metadata={
                            'subject': seed1,
                            'object': seed2,
                            'relation_type': 'related'
                        },
                        retrieval_method='graph',
                        position=len(evidence_list) + 1
                    )
                    evidence_list.append(evidence)

        return evidence_list

    def _generate_basic_graph_evidence(self, query: str) -> List[Evidence]:
        """
        生成基础图谱证据（当没有实体种子时）

        Args:
            query: 查询文本

        Returns:
            基础图谱证据列表
        """
        evidence_list = []

        # 基于查询关键词生成证据
        query_words = query.split()
        for i, word in enumerate(query_words[:5]):  # 取前5个词
            if len(word) > 2:
                evidence = Evidence(
                    id=f"graph_basic_{i}",
                    title=f"相关概念: {word}",
                    content=f"关于{word}的游戏知识",
                    content_type='entity',
                    score=0.7,
                    source='graph',
                    metadata={
                        'entity_type': 'concept',
                        'keyword': word
                    },
                    retrieval_method='graph',
                    position=i + 1
                )
                evidence_list.append(evidence)

        return evidence_list

    def retrieve_and_fuse(self, query: str) -> Tuple[FusionResult, Dict[str, Any]]:
        """
        执行检索并融合证据

        Args:
            query: 查询文本

        Returns:
            (融合结果, 统计信息)
        """
        print(f"\n=== 执行检索和证据融合 ===")
        print(f"查询: {query}")

        start_time = time.time()

        # 1. 并行检索
        print("1. 并行检索...")
        bm25_evidence = self.retrieve_bm25(query)
        milvus_evidence = self.retrieve_milvus(query)
        graph_evidence = self.retrieve_graph(query)

        # 2. 证据融合
        print("\n2. 证据融合...")
        fusion_result = self.fusion.fusion_evidence(
            bm25_evidence=bm25_evidence,
            milvus_evidence=milvus_evidence,
            graph_evidence=graph_evidence,
            fusion_method=self.config.fusion_method,
            max_evidence=self.config.max_fused_evidence
        )

        # 设置查询
        fusion_result.query = query

        # 3. 选择核心证据
        print("\n3. 选择核心证据...")
        core_evidence = self.fusion.select_core_evidence(
            fusion_result.evidence_list,
            max_tokens=self.config.core_max_tokens
        )

        # 4. 质量分析
        print("\n4. 质量分析...")
        quality_analysis = self.fusion.evidence_quality_analysis(
            core_evidence, scores_are_rrf=self.config.fusion_method == 'rrf'
        )
        fusion_result.core_evidence = core_evidence
        fusion_result.quality_analysis = quality_analysis

        # 5. 统计信息
        total_time = time.time() - start_time
        stats = {
            'query': query,
            'total_time': total_time,
            'retrieval_times': {
                'bm25': len(bm25_evidence),
                'milvus': len(milvus_evidence),
                'graph': len(graph_evidence)
            },
            'fusion_stats': {
                'total_fused': len(fusion_result.evidence_list),
                'core_evidence': len(core_evidence),
                'quality_level': quality_analysis['quality_level']
            },
            'config': {
                'fusion_method': self.config.fusion_method,
                'method_weights': self.config.method_weights
            }
        }

        print(f"\n=== 检索完成 ===")
        print(f"总耗时: {total_time:.3f}s")
        print(f"核心证据数: {len(core_evidence)}")
        print(f"质量等级: {quality_analysis['quality_level']}")

        return fusion_result, stats

    def get_optimal_evidence(self, query: str, use_core: bool = True) -> List[Evidence]:
        """
        获取最优证据

        Args:
            query: 查询文本
            use_core: 是否使用核心证据

        Returns:
            最优证据列表
        """
        _, stats = self.retrieve_and_fuse(query)

        # 融合结果会保存在系统状态中，这里简化处理
        # 实际应用中应该从retrieve_and_fuse的返回值中获取
        fusion_result = None
        if hasattr(self, '_last_fusion_result'):
            fusion_result = self._last_fusion_result

        if fusion_result and use_core:
            return self.fusion.select_core_evidence(
                fusion_result.evidence_list,
                max_tokens=self.config.core_max_tokens
            )
        elif fusion_result:
            return fusion_result.evidence_list
        else:
            return []

    def save_results(self, query: str, fusion_result: FusionResult,
                    stats: Dict[str, Any], output_path: str = None):
        """
        保存检索结果

        Args:
            query: 查询文本
            fusion_result: 融合结果
            stats: 统计信息
            output_path: 输出路径
        """
        if output_path is None:
            output_path = f"results/{query[:50].replace(' ', '_')}_fusion.json"

        # 确保目录存在
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        # 准备保存数据
        save_data = {
            'query': query,
            'timestamp': time.time(),
            'fusion_result': fusion_result.to_dict(),
            'stats': stats,
            'config': {
                'bm25_top_k': self.config.bm25_top_k,
                'milvus_top_k': self.config.milvus_top_k,
                'graph_top_k': self.config.graph_top_k,
                'fusion_method': self.config.fusion_method,
                'method_weights': self.config.method_weights
            }
        }

        # 保存为JSON
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, indent=2, ensure_ascii=False)

        print(f"结果已保存到: {output_path}")


# 测试函数
def test_retrieval_system():
    """测试检索系统"""
    print("=== 测试检索系统 ===")

    # 创建配置
    config = RetrievalConfig(
        bm25_top_k=5,
        milvus_top_k=5,
        graph_top_k=5,
        fusion_method='rrf',
        max_fused_evidence=8
    )

    # 初始化系统（注意：需要BM25索引）
    system = RetrievalSystem(
        bm25_index_path="data/processed/bm25_index.json",
        milvus_ready=True,
        config=config
    )

    # 测试查询
    test_queries = [
        "钻石镐怎么制作",
        "苦力怕的特性",
        "末地传送门建造"
    ]

    for query in test_queries:
        print(f"\n{'='*50}")
        print(f"测试查询: {query}")

        try:
            # 执行检索和融合
            fusion_result, stats = system.retrieve_and_fuse(query)

            # 保存结果
            system.save_results(query, fusion_result, stats)

        except Exception as e:
            print(f"处理查询时出错: {e}")


if __name__ == "__main__":
    test_retrieval_system()
