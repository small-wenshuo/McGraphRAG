# Integrated Minecraft GraphRAG Question Answering System
# 整合Minecraft知识图谱RAG问答系统
# 实现热问题快速通道和冷问题RAG通道的统一问答入口

import sys
import os
import time
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
import json
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from base.config import Config
from mysql_qa.main import MySQLQASystem
from mysql_qa.retrieval.bm25_search import BM25Search
from rag_qa.core.retrieval_system import RetrievalSystem, RetrievalConfig
from rag_qa.core.strategy_selector import StrategySelector
from rag_qa.core.llm_response_generator import LLMResponseGenerator, ResponseContext
from rag_qa.core.evidence_fusion import Evidence, EvidenceFusion, FusionResult


@dataclass
class QAConfig:
    """问答系统配置"""
    # 热问题阈值（BM25+softmax得分）
    hot_query_threshold: float = 0.85
    # 缓存过期时间（秒）
    cache_expire_time: int = 3600
    # RAG系统配置
    rag_config: RetrievalConfig = None
    # 最大回答长度
    max_answer_length: int = 2000


class IntegratedQASystem:
    """集成问答系统"""

    def __init__(self, config: Optional[QAConfig] = None):
        """
        初始化集成问答系统

        Args:
            config: 问答系统配置
        """
        print("正在初始化集成问答系统...")

        self.config = config or QAConfig()
        if self.config.rag_config is None:
            self.config.rag_config = RetrievalConfig()

        self.base_config = Config()

        # 1. 初始化快速通道系统（MySQL + Redis）
        self.mysql_qa = MySQLQASystem()

        # 2. 初始化RAG系统
        self.rag_system = RetrievalSystem(
            bm25_index_path=str(Path(__file__).resolve().parent / "mysql_qa" / "bm25_index.json"),
            milvus_ready=True,
            config=self.config.rag_config
        )

        # 3. 初始化策略选择器
        self.strategy_selector = StrategySelector()

        # 4. 初始化大模型回答生成器
        self.llm_generator = LLMResponseGenerator()

        # 5. 初始化证据融合器
        self.fusion = EvidenceFusion()

        print("集成问答系统初始化完成")
        print(f"配置: 热问题阈值={self.config.hot_query_threshold}, "
              f"缓存过期时间={self.config.cache_expire_time}秒")

    def _is_hot_query(self, query: str) -> bool:
        """
        判断是否为热问题（基于BM25+softmax得分）

        Args:
            query: 查询文本

        Returns:
            bool: True表示是热问题
        """
        print(f"判断热问题: {query}")

        # 获取BM25搜索器
        bm25_searcher = self.mysql_qa.bm25_search

        if not bm25_searcher or bm25_searcher.total_docs == 0:
            print("没有可用的BM25索引，无法判断热问题")
            return False

        normalized_query = ''.join(query.lower().split())
        is_hot = self.mysql_qa.mysql_client is not None and any(
            ''.join(doc.get('title', '').lower().split()) == normalized_query
            for doc in bm25_searcher.documents
        )
        print(f"热问题判断结果: {'是' if is_hot else '否'}")

        return is_hot

    def _process_hot_query(self, query: str) -> Dict[str, Any]:
        """
        处理热问题（使用快速通道）

        Args:
            query: 查询文本

        Returns:
            Dict: 处理结果
        """
        print(f"处理热问题: {query}")

        start_time = time.time()

        # 使用MySQL快速通道
        result = self.mysql_qa.process_query(query)

        # 如果MySQL没有结果，尝试使用RAG作为后备
        if result['source'] == 'rag_decision':
            print("MySQL无结果，使用RAG作为后备")
            return self._process_cold_query(query)

        response_time = time.time() - start_time
        result['response_time'] = response_time
        result['message'] = f"热问题处理完成，耗时: {response_time:.3f}秒"

        return result

    def _process_cold_query(self, query: str) -> Dict[str, Any]:
        """
        处理冷问题（使用RAG系统）

        Args:
            query: 查询文本

        Returns:
            Dict: 处理结果
        """
        print(f"处理冷问题: {query}")

        start_time = time.time()

        # 1. 执行检索并融合证据
        fusion_result, stats = self.rag_system.retrieve_and_fuse(query)

        # 2. 选择检索策略
        strategy = self.strategy_selector.select_strategy(query)
        print(f"选择的检索策略: {strategy}")

        # 3. 生成回答上下文
        context = ResponseContext(
            query=query,
            evidence_list=[e.to_dict() for e in fusion_result.evidence_list],
            core_evidence=[e.to_dict() for e in fusion_result.core_evidence],
            quality_analysis=fusion_result.quality_analysis,
            stats=stats,
            game_version=None,
            modpack_version=None,
            server_version=None
        )

        # 4. 优先使用百炼模型，未配置或调用失败时回退到本地证据回答。
        answer = self.llm_generator.generate_answer(context) or self._generate_evidence_answer(context)

        # 5. 验证回答质量
        validation = self.llm_generator.validate_response(answer, context)

        response_time = time.time() - start_time
        result = {
            'success': True,
            'source': 'rag',
            'data': {
                'query': query,
                'strategy': strategy,
                'evidence_count': len(fusion_result.evidence_list),
                'core_evidence_count': len(fusion_result.core_evidence),
                'answer': answer,
                'validation': validation,
                'stats': stats
            },
            'response_time': response_time,
            'message': f"冷问题处理完成，耗时: {response_time:.3f}秒"
        }

        return result

    def _generate_evidence_answer(self, context: ResponseContext) -> str:
        """只返回与查询实体匹配的真实检索内容。"""
        normalized_query = ''.join(context.query.lower().split())
        subject = normalized_query
        crafting_question = False
        for suffix in ('怎么制作', '如何制作', '怎么合成', '合成配方', '的特性', '是什么', '怎么获得', '如何获得'):
            if subject.endswith(suffix):
                subject = subject[:-len(suffix)]
                crafting_question = suffix in ('怎么制作', '如何制作', '怎么合成', '合成配方')
                break

        if crafting_question:
            recipe_answer = self._recipe_answer(subject)
            if recipe_answer:
                return recipe_answer

        for evidence in context.core_evidence:
            if evidence.get('retrieval_method') not in ('bm25', 'milvus'):
                continue
            title = ''.join(evidence.get('title', '').lower().split())
            content = evidence.get('content', '').strip()
            if title and title == subject and content:
                source = evidence.get('metadata', {}).get('source_url') or evidence.get('source', 'unknown')
                return f"{content[:500]}\n来源：{source}"

        if '掉落' in normalized_query:
            for evidence in context.evidence_list:
                metadata = evidence.get('metadata', {})
                if evidence.get('retrieval_method') != 'graph' or metadata.get('predicate') != 'DROPS':
                    continue
                title = evidence.get('title', '')
                subject, _, object_name = title.partition(' DROPS ')
                if subject and object_name and subject.lower() in normalized_query:
                    return f"{subject}被击杀时可能掉落{object_name}。\n来源：{evidence.get('source', 'unknown')}"
        return "当前证据不足，无法可靠回答这个问题。"

    @staticmethod
    def _recipe_answer(subject: str) -> Optional[str]:
        root = Path(__file__).resolve().parent / 'data' / 'raw'
        with (root / 'entities.json').open(encoding='utf-8') as f:
            entities = {item['id']: item for item in json.load(f)}
        with (root / 'recipes.json').open(encoding='utf-8') as f:
            recipes = json.load(f)
        for recipe in recipes:
            output = entities.get(recipe.get('output_id'), {})
            names = [output.get('name_zh', ''), output.get('name_en', ''), *output.get('aliases', [])]
            if subject not in [name.lower().replace(' ', '') for name in names]:
                continue
            ingredients = []
            for ingredient in recipe.get('ingredients', []):
                item = entities.get(ingredient['id'], {})
                ingredients.append(f"{ingredient['count']} 个{item.get('name_zh', ingredient['id'])}")
            station = entities.get(recipe.get('station_id'), {}).get('name_zh', '工作台')
            return f"{output.get('name_zh', subject)}合成需要{'、'.join(ingredients)}，使用{station}。\n来源：data/raw/recipes.json"
        return None

    def process_query(self, query: str) -> Dict[str, Any]:
        """
        处理用户查询

        Args:
            query: 查询文本

        Returns:
            Dict: 处理结果
        """
        print(f"\n=== 处理查询: {query} ===")

        start_time = time.time()

        # 1. 判断是否为热问题
        is_hot = self._is_hot_query(query)

        # 2. 根据问题类型选择处理路径
        if is_hot:
            result = self._process_hot_query(query)
        else:
            result = self._process_cold_query(query)

        # 3. 记录查询统计
        response_time = time.time() - start_time
        self._record_query_stats(query, is_hot, result)

        result['total_time'] = response_time
        return result

    def _record_query_stats(self, query: str, is_hot: bool, result: Dict[str, Any]):
        """
        记录查询统计信息

        Args:
            query: 查询文本
            is_hot: 是否为热问题
            result: 处理结果
        """
        # 这里简化处理，实际应该记录到数据库或日志
        print(f"查询统计: 热问题={is_hot}, 来源={result.get('source', 'unknown')}, "
              f"耗时={result.get('response_time', 0):.3f}秒")

    def close(self):
        """关闭系统"""
        try:
            self.mysql_qa.close()
            print("集成问答系统已关闭")
        except Exception as e:
            print(f"关闭系统时出错: {e}")


def main():
    """主函数"""
    # 创建问答系统
    qa_system = IntegratedQASystem()

    try:
        # 测试查询
        test_queries = [
            "钻石镐怎么制作",      # 热问题（合成类）
            "苦力怕的特性",       # 热问题（生物类）
            "末地传送门建造",     # 冷问题（机制类）
            "红石电路原理",       # 冷问题（机制类）
            "水方块怎么获得"      # 热问题（获取类）
        ]

        print("\n=== 测试查询 ===")
        for query in test_queries:
            print(f"\n查询: '{query}'")
            result = qa_system.process_query(query)

            if result['success']:
                print(f"来源: {result['source']}")
                print(f"消息: {result['message']}")
                print(f"耗时: {result['total_time']:.3f}秒")

                if 'data' in result:
                    data = result['data']
                    if data.get('strategy'):
                        print(f"策略: {data['strategy']}")
                    if data.get('answer'):
                        print(f"回答: {data['answer'][:100]}...")
                    if data.get('evidence_count'):
                        print(f"证据数: {data['evidence_count']}")
            else:
                print("查询失败")

        # 显示系统统计
        print("\n=== 系统统计 ===")
        print("MySQL系统统计:")
        mysql_stats = qa_system.mysql_qa.get_system_stats()
        print(f"  Redis连接: {mysql_stats['redis_stats']['connected']}")
        print(f"  MySQL统计: {mysql_stats['mysql_stats']}")
        print(f"  BM25统计: {mysql_stats['bm25_stats']}")

    except KeyboardInterrupt:
        print("\n用户中断，正在关闭系统...")
    except Exception as e:
        print(f"系统运行时出错: {e}")
    finally:
        qa_system.close()


if __name__ == "__main__":
    main()
