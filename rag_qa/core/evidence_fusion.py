"""
证据融合模块
功能：融合来自不同检索方法的证据，通过倒数排序融合(RRF)等方法确定最佳证据集
"""

import math
import numpy as np
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass, field
from collections import defaultdict
import json
import os
from pathlib import Path

from base.config import Config


@dataclass
class Evidence:
    """证据数据类"""
    id: str
    title: str
    content: str
    content_type: str  # 'chunk', 'entity', 'fact'
    score: float
    source: str
    metadata: Dict[str, Any]
    retrieval_method: str  # 'bm25', 'milvus', 'graph'
    rank: int = 0
    position: int = 0  # 在各方法中的原始位置

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'id': self.id,
            'title': self.title,
            'content': self.content,
            'content_type': self.content_type,
            'score': self.score,
            'source': self.source,
            'metadata': self.metadata,
            'retrieval_method': self.retrieval_method,
            'rank': self.rank,
            'position': self.position
        }


@dataclass
class FusionResult:
    """融合结果数据类"""
    query: str
    evidence_list: List[Evidence]
    fusion_scores: Dict[str, float]  # 各证据的融合分数
    method_stats: Dict[str, int]  # 各方法贡献的证据数
    total_evidence: int
    fusion_method: str
    core_evidence: List[Evidence] = field(default_factory=list)
    quality_analysis: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'query': self.query,
            'evidence_count': self.total_evidence,
            'fusion_method': self.fusion_method,
            'method_stats': self.method_stats,
            'evidences': [e.to_dict() for e in self.evidence_list]
        }


class EvidenceFusion:
    """证据融合器"""

    def __init__(self, rrf_k: int = 60, method_weights: Optional[Dict[str, float]] = None):
        """
        初始化证据融合器

        Args:
            rrf_k: RRF平滑参数，通常取60
            method_weights: 各检索方法的权重
        """
        self.config = Config()
        self.rrf_k = rrf_k

        # 默认权重
        if method_weights is None:
            self.method_weights = {
                'milvus': 0.5,    # 向量检索权重最高
                'bm25': 0.3,      # BM25次之
                'graph': 0.2      # 图谱检索权重较低
            }
        else:
            self.method_weights = method_weights

        # 获取配置
        self.search_config = self.config.get_search_config()
        self.rag_config = self.config.get_rag_config()

        print(f"证据融合器初始化完成")
        print(f"方法权重: {self.method_weights}")
        print(f"RRF参数k: {self.rrf_k}")

    def reciprocal_rank_fusion(self, evidence_by_method: Dict[str, List[Evidence]]) -> List[Evidence]:
        """
        倒数排序融合（Reciprocal Rank Fusion）

        Args:
            evidence_by_method: 各检索方法的证据字典 {method: [evidence_list]}

        Returns:
            融合后的证据列表（按分数降序）
        """
        # 计算每个证据的RRF分数
        rrf_scores = defaultdict(float)
        evidence_map = {}  # id -> evidence

        # 对每种方法计算RRF分数
        for method, evidences in evidence_by_method.items():
            weight = self.method_weights.get(method, 1.0)
            for position, evidence in enumerate(evidences, 1):
                # RRF公式: 1 / (k + position)
                rrf_score = (1 / (self.rrf_k + position)) * weight
                rrf_scores[evidence.id] += rrf_score

                # 保存原始证据
                if evidence.id not in evidence_map:
                    # 创建副本，避免修改原始对象
                    evidence_copy = Evidence(
                        id=evidence.id,
                        title=evidence.title,
                        content=evidence.content,
                        content_type=evidence.content_type,
                        score=evidence.score,
                        source=evidence.source,
                        metadata=evidence.metadata,
                        retrieval_method=evidence.retrieval_method,
                        position=position
                    )
                    evidence_map[evidence.id] = evidence_copy

        # 按RRF分数排序
        sorted_evidence = []
        for evidence_id, rrf_score in sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True):
            evidence = evidence_map[evidence_id]
            evidence.score = rrf_score  # 更新为融合后的分数
            evidence.rank = len(sorted_evidence) + 1
            sorted_evidence.append(evidence)

        return sorted_evidence

    def weighted_score_fusion(self, evidence_by_method: Dict[str, List[Evidence]]) -> List[Evidence]:
        """
        加权分数融合

        Args:
            evidence_by_method: 各检索方法的证据字典

        Returns:
            融合后的证据列表
        """
        # 合并所有证据，保留各方法的原始分数
        all_evidence = []
        method_max_scores = {}  # 记录各方法的最大分数用于归一化

        for method, evidences in evidence_by_method.items():
            if evidences:
                method_max_scores[method] = max(e.score for e in evidences)
            else:
                method_max_scores[method] = 1.0

            for evidence in evidences:
                # 创建副本，添加原始分数
                evidence_copy = Evidence(
                    id=f"{method}_{evidence.id}",
                    title=evidence.title,
                    content=evidence.content,
                    content_type=evidence.content_type,
                    score=evidence.score,  # 原始分数
                    source=evidence.source,
                    metadata=evidence.metadata,
                    retrieval_method=method,
                    position=evidence.position
                )
                all_evidence.append(evidence_copy)

        # 归一化并计算融合分数
        fused_evidence = []
        for evidence in all_evidence:
            method = evidence.retrieval_method
            # 归一化分数
            normalized_score = evidence.score / method_max_scores[method]
            # 应用权重
            fused_score = normalized_score * self.method_weights[method]

            # 更新分数
            evidence.score = fused_score
            evidence.rank = 0  # 待重新分配
            fused_evidence.append(evidence)

        # 去重：选择相同ID中分数最高的
        unique_evidence = {}
        for evidence in fused_evidence:
            base_id = evidence.id.split('_', 1)[1]  # 去掉方法前缀
            if base_id not in unique_evidence or evidence.score > unique_evidence[base_id].score:
                unique_evidence[base_id] = evidence

        # 重新排序
        sorted_evidence = sorted(unique_evidence.values(), key=lambda x: x.score, reverse=True)

        # 重新分配排名
        for rank, evidence in enumerate(sorted_evidence, 1):
            evidence.rank = rank
            # 恢复原始ID
            original_id = evidence.id.split('_', 1)[1]
            evidence.id = original_id

        return sorted_evidence

    def fusion_evidence(self, bm25_evidence: List[Evidence],
                       milvus_evidence: List[Evidence],
                       graph_evidence: List[Evidence],
                       fusion_method: str = 'rrf',
                       max_evidence: int = 10) -> FusionResult:
        """
        融合证据

        Args:
            bm25_evidence: BM25检索的证据
            milvus_evidence: Milvus检索的证据
            graph_evidence: 图谱检索的证据
            fusion_method: 融合方法 ('rrf' 或 'weighted')
            max_evidence: 最大证据数量

        Returns:
            融合结果
        """
        print(f"\n开始证据融合...")
        print(f"融合方法: {fusion_method}")
        print(f"BM25证据数: {len(bm25_evidence)}")
        print(f"Milvus证据数: {len(milvus_evidence)}")
        print(f"图谱证据数: {len(graph_evidence)}")

        # 组织证据
        evidence_by_method = {
            'bm25': bm25_evidence,
            'milvus': milvus_evidence,
            'graph': graph_evidence
        }

        # 统计各方法的贡献
        method_stats = {
            'bm25': len(bm25_evidence),
            'milvus': len(milvus_evidence),
            'graph': len(graph_evidence)
        }

        # 执行融合
        if fusion_method == 'rrf':
            fused_evidence = self.reciprocal_rank_fusion(evidence_by_method)
        else:
            fused_evidence = self.weighted_score_fusion(evidence_by_method)

        # 每个有结果的检索通道至少保留一条，避免低权重的真实图谱证据被截断。
        active_methods = [method for method, items in evidence_by_method.items() if items]
        if max_evidence >= len(active_methods):
            reserved = [next(e for e in fused_evidence if e.retrieval_method == method)
                        for method in active_methods]
            reserved_ids = {e.id for e in reserved}
            remaining = [e for e in fused_evidence if e.id not in reserved_ids]
            final_evidence = sorted(
                reserved + remaining[:max_evidence - len(reserved)],
                key=lambda e: e.score, reverse=True
            )
        else:
            final_evidence = fused_evidence[:max_evidence]

        # 计算融合分数
        fusion_scores = {e.id: e.score for e in final_evidence}

        # 创建融合结果
        result = FusionResult(
            query="",  # 需要在外部设置
            evidence_list=final_evidence,
            fusion_scores=fusion_scores,
            method_stats=method_stats,
            total_evidence=len(final_evidence),
            fusion_method=fusion_method
        )

        # 输出结果摘要
        print(f"\n融合结果摘要:")
        print(f"总证据数: {len(final_evidence)}")
        for method, count in method_stats.items():
            print(f"  {method}: {count} 个证据")

        print(f"\nTop 5 证据:")
        for i, evidence in enumerate(final_evidence[:5], 1):
            print(f"  {i}. {evidence.title} [{evidence.retrieval_method}, score={evidence.score:.4f}]")

        return result

    def merge_and_dedupe_evidence(self, evidence_lists: List[List[Evidence]]) -> List[Evidence]:
        """
        合并并去重证据

        Args:
            evidence_lists: 多个证据列表

        Returns:
            去重后的证据列表
        """
        # 合并所有证据
        all_evidence = []
        for evidence_list in evidence_lists:
            all_evidence.extend(evidence_list)

        # 去重：基于ID和内容相似度
        unique_evidence = {}

        for evidence in all_evidence:
            # 计算内容简短特征用于去重
            content_key = evidence.content[:100].lower().strip()

            # 如果ID相同或内容高度相似，保留分数更高的
            if (evidence.id not in unique_evidence and
                content_key not in unique_evidence):
                unique_evidence[evidence.id] = evidence
                unique_evidence[content_key] = evidence
            else:
                # 找到匹配的现有证据
                existing_evidence = None
                if evidence.id in unique_evidence:
                    existing_evidence = unique_evidence[evidence.id]
                elif content_key in unique_evidence:
                    existing_evidence = unique_evidence[content_key]

                # 如果新证据分数更高，替换现有证据
                if existing_evidence and evidence.score > existing_evidence.score:
                    if existing_evidence.id in unique_evidence:
                        unique_evidence[evidence.id] = evidence
                    if content_key in unique_evidence:
                        unique_evidence[content_key] = evidence

        # 返回去重后的证据（只返回一次）
        final_evidence = []
        seen_ids = set()

        for evidence in all_evidence:
            if evidence.id not in seen_ids:
                final_evidence.append(evidence)
                seen_ids.add(evidence.id)

        # 按分数排序
        final_evidence.sort(key=lambda x: x.score, reverse=True)

        return final_evidence

    def select_core_evidence(self, evidence_list: List[Evidence],
                           max_tokens: int = 2000,
                           token_per_evidence: int = 300) -> List[Evidence]:
        """
        选择核心证据（基于分数和token限制）

        Args:
            evidence_list: 融合后的证据列表
            max_tokens: 最大token数
            token_per_evidence: 每个证据估计的token数

        Returns:
            核心证据列表
        """
        if not evidence_list:
            return []

        # 按分数排序
        sorted_evidence = sorted(evidence_list, key=lambda x: x.score, reverse=True)

        # 计算能容纳的证据数量
        max_count = min(len(sorted_evidence), max_tokens // token_per_evidence)

        # 选择前N个证据
        core_evidence = sorted_evidence[:max_count]

        print(f"从 {len(evidence_list)} 个证据中选择 {len(core_evidence)} 个核心证据")
        print(f"预计token数: {len(core_evidence) * token_per_evidence}")

        return core_evidence

    def evidence_quality_analysis(self, evidence_list: List[Evidence],
                                  scores_are_rrf: bool = False) -> Dict[str, Any]:
        """
        分析证据质量

        Args:
            evidence_list: 证据列表

        Returns:
            质量分析结果
        """
        if not evidence_list:
            return {
                'total_evidence': 0,
                'avg_score': 0,
                'score_distribution': {},
                'method_distribution': {},
                'quality_level': 'no_evidence'
            }

        scores = [e.score for e in evidence_list]
        methods = [e.retrieval_method for e in evidence_list]

        # 分析分数分布
        avg_score = sum(scores) / len(scores)
        max_score = max(scores)
        min_score = min(scores)

        # 分析方法分布
        method_counts = {}
        for method in methods:
            method_counts[method] = method_counts.get(method, 0) + 1

        # 确定质量等级
        if scores_are_rrf:
            quality_level = 'unassessed'
        elif avg_score > 0.8:
            quality_level = 'high'
        elif avg_score > 0.5:
            quality_level = 'medium'
        elif avg_score > 0.3:
            quality_level = 'low'
        else:
            quality_level = 'poor'

        return {
            'total_evidence': len(evidence_list),
            'avg_score': avg_score,
            'max_score': max_score,
            'min_score': min_score,
            'score_distribution': {} if scores_are_rrf else {
                'high_count': len([s for s in scores if s > 0.8]),
                'medium_count': len([s for s in scores if 0.5 <= s <= 0.8]),
                'low_count': len([s for s in scores if 0.3 <= s < 0.5]),
                'poor_count': len([s for s in scores if s < 0.3])
            },
            'method_distribution': method_counts,
            'score_kind': 'rrf' if scores_are_rrf else 'relevance',
            'quality_level': quality_level
        }


# 测试函数
def test_evidence_fusion():
    """测试证据融合功能"""
    print("=== 测试证据融合 ===")

    # 初始化融合器
    fusion = EvidenceFusion(rrf_k=60, method_weights={'milvus': 0.5, 'bm25': 0.3, 'graph': 0.2})

    # 创建模拟证据
    bm25_evidence = [
        Evidence(
            id="bm25_1",
            title="钻石镐的制作方法",
            content="钻石镐需要3个钻石和2个木棍制作",
            content_type="chunk",
            score=0.9,
            source="bm25",
            metadata={},
            retrieval_method="bm25"
        ),
        Evidence(
            id="bm25_2",
            title="钻石的获取方式",
            content="钻石可以通过挖掘矿石获得",
            content_type="chunk",
            score=0.7,
            source="bm25",
            metadata={},
            retrieval_method="bm25"
        )
    ]

    milvus_evidence = [
        Evidence(
            id="milvus_1",
            title="钻石镐制作配方",
            content="工作台配方：3个钻石 + 2个木棍 = 钻石镐",
            content_type="chunk",
            score=0.85,
            source="milvus",
            metadata={},
            retrieval_method="milvus"
        ),
        Evidence(
            id="milvus_2",
            title="镐子类型对比",
            content="钻石镐是最耐用的镐子",
            content_type="chunk",
            score=0.6,
            source="milvus",
            metadata={},
            retrieval_method="milvus"
        )
    ]

    graph_evidence = [
        Evidence(
            id="graph_1",
            title="钻石镐实体",
            content="钻石镐：镐子类工具，耐久1561",
            content_type="entity",
            score=0.75,
            source="graph",
            metadata={"entity_type": "tool"},
            retrieval_method="graph"
        )
    ]

    # 测试RRF融合
    print("\n--- RRF融合测试 ---")
    rrf_result = fusion.fusion_evidence(
        bm25_evidence, milvus_evidence, graph_evidence,
        fusion_method='rrf', max_evidence=5
    )

    # 测试加权融合
    print("\n--- 加权融合测试 ---")
    weighted_result = fusion.fusion_evidence(
        bm25_evidence, milvus_evidence, graph_evidence,
        fusion_method='weighted', max_evidence=5
    )

    # 质量分析
    print("\n--- 质量分析 ---")
    quality_analysis = fusion.evidence_quality_analysis(rrf_result.evidence_list)
    print(f"质量分析结果: {quality_analysis}")

    return rrf_result, weighted_result


if __name__ == "__main__":
    test_evidence_fusion()
