"""
混合检索使用示例
演示如何使用检索系统进行证据融合
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from rag_qa.core.retrieval_system import RetrievalSystem, RetrievalConfig
from rag_qa.core.evidence_fusion import Evidence


def create_sample_bm25_index():
    """创建示例BM25索引"""
    from rag_qa.core.retrieval_system import RetrievalSystem

    # 示例文档
    sample_documents = [
        {
            "title": "钻石镐的制作方法",
            "content": "钻石镐需要3个钻石和2个木棍在工作台中制作。钻石是世界上最耐久的镐子，可以挖掘所有方块。",
            "metadata": {"type": "recipe", "material": "diamond"}
        },
        {
            "title": "苦力怕的行为",
            "content": "苦力怕是一种会自爆的敌对生物。它看到玩家时会靠近，并在3秒后爆炸。苦力怕掉落0-2个火药。",
            "metadata": {"type": "mob", "difficulty": "easy"}
        },
        {
            "title": "末地传送门",
            "content": "末地传送门需要12个末影眼和12个末影珍珠来建造。首先建造一个末地传送门框架，然后往每个框架中放入末影眼。",
            "metadata": {"type": "structure", "dimension": "the_end"}
        },
        {
            "title": "红石电路",
            "content": "红石是Minecraft中的电气材料，可以用来制作电路和机械装置。红石火把可以提供信号源。",
            "metadata": {"type": "mechanic", "material": "redstone"}
        },
        {
            "title": "村民交易",
            "content": "村民可以通过交易来获得物品或经验。村民的职业有农夫、铁匠、牧师等。每个职业有独特的交易选项。",
            "metadata": {"type": "mechanic", "difficulty": "medium"}
        }
    ]

    # 创建BM25索引文件路径
    index_path = project_root / "data" / "processed" / "bm25_sample_index.json"

    # 确保目录存在
    index_path.parent.mkdir(parents=True, exist_ok=True)

    # 创建临时BM25搜索器并保存索引
    from mysql_qa.retrieval.bm25_search import BM25Search

    bm25 = BM25Search()
    bm25.build_index(sample_documents)
    bm25.save_index_to_file(str(index_path))

    print(f"示例BM25索引已创建: {index_path}")
    return str(index_path)


def demo_basic_retrieval():
    """演示基础检索功能"""
    print("\n=== 基础检索演示 ===")

    # 创建示例索引
    index_path = create_sample_bm25_index()

    # 创建检索配置
    config = RetrievalConfig(
        bm25_top_k=3,
        milvus_top_k=3,
        graph_top_k=3,
        fusion_method='rrf'
    )

    # 创建检索系统（不使用Milvus）
    system = RetrievalSystem(
        bm25_index_path=index_path,
        milvus_ready=False,  # 演示时不使用Milvus
        config=config
    )

    # 测试查询
    query = "钻石镐怎么制作"
    print(f"查询: {query}")

    # 执行检索
    fusion_result, stats = system.retrieve_and_fuse(query)

    print(f"\n检索结果:")
    for i, evidence in enumerate(fusion_result.evidence_list[:5], 1):
        print(f"{i}. {evidence.title} [{evidence.retrieval_method}, score={evidence.score:.4f}]")


def demo_fusion_comparison():
    """演示不同融合方法的对比"""
    print("\n=== 融合方法对比演示 ===")

    # 创建示例索引
    index_path = create_sample_bm25_index()

    # 测试查询
    query = "苦力怕"
    print(f"查询: {query}")

    # RRF融合
    config_rrf = RetrievalConfig(fusion_method='rrf')
    system_rrf = RetrievalSystem(bm25_index_path=index_path, milvus_ready=False, config=config_rrf)
    rrf_result, rrf_stats = system_rrf.retrieve_and_fuse(query)

    print(f"\nRRF融合前3个结果:")
    for i, evidence in enumerate(rrf_result.evidence_list[:3], 1):
        print(f"{i}. {evidence.title} [{evidence.retrieval_method}, score={evidence.score:.4f}]")

    # 加权融合
    config_weighted = RetrievalConfig(fusion_method='weighted')
    system_weighted = RetrievalSystem(bm25_index_path=index_path, milvus_ready=False, config=config_weighted)
    weighted_result, weighted_stats = system_weighted.retrieve_and_fuse(query)

    print(f"\n加权融合前3个结果:")
    for i, evidence in enumerate(weighted_result.evidence_list[:3], 1):
        print(f"{i}. {evidence.title} [{evidence.retrieval_method}, score={evidence.score:.4f}]")


def demo_query_analysis():
    """演示查询分析和证据质量"""
    print("\n=== 查询分析和证据质量演示 ===")

    # 创建示例索引
    index_path = create_sample_bm25_index()

    # 测试不同类型的查询
    test_queries = [
        "钻石镐制作",  # 简单精确查询
        "苦力怕特性",  # 中等复杂度
        "Minecraft有什么机制"  # 复杂开放性查询
    ]

    config = RetrievalConfig(bm25_top_k=5, fusion_method='rrf')
    system = RetrievalSystem(bm25_index_path=index_path, milvus_ready=False, config=config)

    for query in test_queries:
        print(f"\n{'='*40}")
        print(f"查询: {query}")

        try:
            fusion_result, stats = system.retrieve_and_fuse(query)

            # 分析证据质量
            from rag_qa.core.evidence_fusion import EvidenceFusion
            fusion_analyzer = EvidenceFusion()
            quality_analysis = fusion_analyzer.evidence_quality_analysis(fusion_result.evidence_list)

            print(f"证据质量: {quality_analysis['quality_level']}")
            print(f"平均分数: {quality_analysis['avg_score']:.3f}")
            print(f"证据来源分布: {quality_analysis['method_distribution']}")

        except Exception as e:
            print(f"处理失败: {e}")


def demo_manual_evidence_fusion():
    """手动演示证据融合过程"""
    print("\n=== 手动证据融合演示 ===")

    from rag_qa.core.evidence_fusion import Evidence, EvidenceFusion

    # 创建模拟证据
    bm25_evidence = [
        Evidence("bm25_1", "钻石镐制作", "钻石镐需要3个钻石", "chunk", 0.9, "bm25", {}, "bm25"),
        Evidence("bm25_2", "钻石获取", "钻石来自矿石", "chunk", 0.7, "bm25", {}, "bm25")
    ]

    milvus_evidence = [
        Evidence("milvus_1", "钻石镐配方", "3钻石+2木棍=钻石镐", "chunk", 0.85, "milvus", {}, "milvus"),
        Evidence("milvus_2", "工具对比", "钻石镐最耐久", "chunk", 0.6, "milvus", {}, "milvus")
    ]

    graph_evidence = [
        Evidence("graph_1", "钻石镐实体", "钻石镐：耐久1561", "entity", 0.75, "graph", {}, "graph")
    ]

    # 初始化融合器
    fusion = EvidenceFusion()

    # 执行融合
    result = fusion.fusion_evidence(
        bm25_evidence, milvus_evidence, graph_evidence,
        fusion_method='rrf', max_evidence=5
    )

    print(f"融合结果: {len(result.evidence_list)} 个证据")
    for i, evidence in enumerate(result.evidence_list, 1):
        print(f"{i}. {evidence.title} [{evidence.retrieval_method}, score={evidence.score:.4f}]")

    # 质量分析
    quality = fusion.evidence_quality_analysis(result.evidence_list)
    print(f"\n质量分析:")
    print(f"总证据数: {quality['total_evidence']}")
    print(f"质量等级: {quality['quality_level']}")
    print(f"平均分数: {quality['avg_score']:.3f}")


if __name__ == "__main__":
    print("混合检索系统使用示例")
    print("="*50)

    # 运行各个演示
    try:
        demo_basic_retrieval()
        demo_fusion_comparison()
        demo_query_analysis()
        demo_manual_evidence_fusion()

        print("\n" + "="*50)
        print("所有演示完成!")

    except Exception as e:
        print(f"演示过程中出错: {e}")
        import traceback
        traceback.print_exc()