"""
回答生成器集成示例
展示如何将回答生成器与检索系统结合使用
"""

import time
from typing import List, Dict, Any
from retrieval_system import RetrievalSystem, RetrievalConfig
from evidence_fusion import EvidenceFusion
from llm_response_generator import LLMResponseGenerator, ResponseContext


class QAIntegration:
    """问答系统集成类"""

    def __init__(self,
                 bm25_index_path: str = "data/processed/bm25_index.json",
                 milvus_ready: bool = True):
        """
        初始化问答系统集成

        Args:
            bm25_index_path: BM25索引文件路径
            milvus_ready: 是否启用Milvus
        """
        # 初始化检索系统
        retrieval_config = RetrievalConfig(
            bm25_top_k=10,
            milvus_top_k=10,
            graph_top_k=8,
            fusion_method='rrf',
            max_fused_evidence=10,
            max_core_evidence=8,
            core_max_tokens=2000
        )

        self.retrieval_system = RetrievalSystem(
            bm25_index_path=bm25_index_path,
            milvus_ready=milvus_ready,
            config=retrieval_config
        )

        # 初始化证据融合器
        self.evidence_fusion = EvidenceFusion(
            rrf_k=60,
            method_weights={'milvus': 0.5, 'bm25': 0.3, 'graph': 0.2}
        )

        # 初始化回答生成器
        self.response_generator = LLMResponseGenerator()

    def process_query(self,
                     query: str,
                     game_version: str = None,
                     modpack_version: str = None,
                     server_version: str = None,
                     generate_prompt: bool = False,
                     max_answer_length: int = 1000) -> Dict[str, Any]:
        """
        处理用户查询

        Args:
            query: 用户查询
            game_version: 游戏版本
            modpack_version: 模组包版本
            server_version: 服务器版本
            generate_prompt: 是否生成完整提示词
            max_answer_length: 最大回答长度

        Returns:
            处理结果
        """
        print(f"\n=== 处理查询 ===")
        print(f"查询: {query}")
        print(f"版本信息: {game_version or '未指定'} | {modpack_version or '未指定'} | {server_version or '未指定'}")

        start_time = time.time()

        try:
            # 1. 执行检索
            print("\n1. 执行检索...")
            fusion_result, retrieval_stats = self.retrieval_system.retrieve_and_fuse(query)

            # 2. 选择核心证据
            print("\n2. 选择核心证据...")
            core_evidence = self.evidence_fusion.select_core_evidence(
                fusion_result.evidence_list,
                max_tokens=2000
            )

            # 3. 质量分析
            print("\n3. 质量分析...")
            quality_analysis = self.evidence_fusion.evidence_quality_analysis(core_evidence)

            # 4. 准备回答上下文
            context = ResponseContext(
                query=query,
                evidence_list=fusion_result.evidence_list,
                core_evidence=core_evidence,
                quality_analysis=quality_analysis,
                stats=retrieval_stats,
                game_version=game_version,
                modpack_version=modpack_version,
                server_version=server_version
            )

            # 5. 生成回答
            print("\n4. 生成回答...")
            if generate_prompt:
                # 生成完整提示词
                response = self.response_generator.generate_response_prompt(context)
                response_type = "prompt"
            else:
                # 生成简洁回答
                response = self.response_generator.generate_simple_answer(context, max_answer_length)
                response_type = "answer"

            # 6. 验证回答
            print("\n5. 验证回答...")
            validation = self.response_generator.validate_response(response, context)

            # 7. 准备结果
            processing_time = time.time() - start_time

            result = {
                'query': query,
                'response': response,
                'response_type': response_type,
                'retrieval_stats': retrieval_stats,
                'validation': validation,
                'processing_time': processing_time,
                'context_info': {
                    'total_evidence': len(fusion_result.evidence_list),
                    'core_evidence': len(core_evidence),
                    'quality_level': quality_analysis['quality_level']
                },
                'version_info': {
                    'game_version': game_version,
                    'modpack_version': modpack_version,
                    'server_version': server_version
                }
            }

            print(f"\n=== 处理完成 ===")
            print(f"总耗时: {processing_time:.3f}s")
            print(f"回答类型: {response_type}")
            print(f"质量等级: {validation['quality_level']}")

            return result

        except Exception as e:
            error_msg = f"处理查询时出错: {str(e)}"
            print(f"❌ {error_msg}")

            return {
                'query': query,
                'response': error_msg,
                'response_type': 'error',
                'error': str(e),
                'processing_time': time.time() - start_time
            }

    def batch_process_queries(self,
                             queries: List[str],
                             game_version: str = None,
                             modpack_version: str = None,
                             server_version: str = None) -> List[Dict[str, Any]]:
        """
        批量处理查询

        Args:
            queries: 查询列表
            game_version: 游戏版本
            modpack_version: 模组包版本
            server_version: 服务器版本

        Returns:
            处理结果列表
        """
        results = []

        for i, query in enumerate(queries, 1):
            print(f"\n=== 处理查询 {i}/{len(queries)} ===")
            result = self.process_query(
                query=query,
                game_version=game_version,
                modpack_version=modpack_version,
                server_version=server_version
            )
            results.append(result)

        return results

    def save_results(self, results: List[Dict[str, Any]], output_file: str = "qa_results.json"):
        """
        保存结果到文件

        Args:
            results: 结果列表
            output_file: 输出文件路径
        """
        import json
        from pathlib import Path

        # 确保目录存在
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)

        # 保存结果
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        print(f"结果已保存到: {output_file}")


# 测试函数
def test_qa_integration():
    """测试问答系统集成"""
    print("=== 测试问答系统集成 ===")

    # 创建集成实例
    qa_system = QAIntegration(
        bm25_index_path="data/processed/bm25_index.json",
        milvus_ready=False  # 测试时可以关闭Milvus
    )

    # 测试查询
    test_queries = [
        "钻石镐怎么制作",
        "苦力怕的特性",
        "末地传送门建造方法"
    ]

    # 设置版本信息
    version_info = {
        'game_version': '1.20.1',
        'modpack_version': 'vanilla',
        'server_version': 'paper'
    }

    # 批量处理查询
    results = qa_system.batch_process_queries(
        queries=test_queries,
        **version_info
    )

    # 保存结果
    qa_system.save_results(results, "test_qa_results.json")

    # 打印部分结果示例
    print("\n=== 结果示例 ===")
    for i, result in enumerate(results[:2], 1):
        print(f"\n查询 {i}: {result['query']}")
        print(f"回答类型: {result['response_type']}")
        if result['response_type'] == 'answer':
            print(f"回答: {result['response'][:200]}...")
        print(f"质量等级: {result['validation']['quality_level']}")
        print(f"处理时间: {result['processing_time']:.3f}s")


if __name__ == "__main__":
    test_qa_integration()