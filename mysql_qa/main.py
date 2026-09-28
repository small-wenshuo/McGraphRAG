import sys
import os
import time
import hashlib
from typing import List, Dict, Any, Optional
import pymysql

# 直接运行此文件时仍可解析项目包；作为包导入时不修改 sys.path。
if __package__ in (None, ''):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mysql_qa.cache.redis_client import RedisClient
from mysql_qa.db.mysql_client import MySQLClient
from mysql_qa.retrieval.bm25_search import BM25Search
from mysql_qa.utils.preprocess import Preprocessor


class MySQLQASystem:
    def __init__(self):
        """初始化MySQL快速问答系统"""
        print("正在初始化MySQL快速问答系统...")

        # 初始化各个组件
        self.redis_client = RedisClient()
        try:
            self.mysql_client = MySQLClient()
        except pymysql.err.OperationalError as e:
            self.mysql_client = None
            print(f"MySQL不可用，改用本地索引和RAG: {e}")
        self.bm25_search = BM25Search()
        self.preprocessor = Preprocessor()

        # 加载已保存的索引；文件缺失或损坏时重新从 MySQL 构建。
        self.bm25_index_path = os.path.join(os.path.dirname(__file__), 'bm25_index.json')
        if not self.bm25_search.load_index_from_file(self.bm25_index_path):
            if self.mysql_client is not None:
                self._build_bm25_index()
            else:
                print("警告：MySQL和BM25索引都不可用，仅使用其他检索方式")

        print("系统初始化完成")

    def _build_bm25_index(self):
        """构建BM25索引"""
        if self.mysql_client is None:
            return False
        print("正在构建BM25索引...")

        # 从MySQL获取所有文档
        documents = self.mysql_client.search_knowledge("", limit=1000)

        # 构建BM25索引
        self.bm25_search.build_index(documents)

        # 保存索引到文件
        if not self.bm25_search.save_index_to_file(self.bm25_index_path):
            raise RuntimeError("BM25索引保存失败")

        print("BM25索引构建完成")

    def process_query(self, query: str) -> Dict[str, Any]:
        """
        处理用户查询
        Args:
            query: 查询文本
        Returns:
            Dict: 处理结果
        """
        start_time = time.time()

        # 记录原始查询
        original_query = query.strip()

        # 1. 检查Redis缓存
        cache_key = f"query:{hashlib.sha256(original_query.encode('utf-8')).hexdigest()}"
        cached_result = self.redis_client.get(cache_key)

        if cached_result:
            # 记录缓存命中
            response_time = time.time() - start_time
            if self.mysql_client is not None:
                self.mysql_client.record_query(
                    original_query, "general", is_cached=True,
                    response_time=response_time
                )
            return {
                'success': True,
                'source': 'cache',
                'data': cached_result,
                'response_time': response_time,
                'message': '命中缓存'
            }

        # 2. 预处理查询
        processed_query = self.preprocessor.preprocess_query(query)
        query_keywords = processed_query['keywords']

        if self.mysql_client is None:
            return {
                'success': True,
                'source': 'rag_decision',
                'data': {'query': original_query, 'decision': 'rag'},
                'response_time': time.time() - start_time,
                'message': 'MySQL不可用，转入RAG检索'
            }

        normalized_query = ''.join(original_query.lower().split())
        exact_doc = next((doc for doc in self.bm25_search.documents
                          if ''.join(doc.get('title', '').lower().split()) == normalized_query), None)
        if exact_doc and exact_doc.get('id') is not None:
            row = self.mysql_client.get_by_id(exact_doc['id'])
            if row and ''.join(row.get('title', '').lower().split()) == normalized_query:
                item = self._format_knowledge(row)
                result = {'query': original_query, 'decision': 'mysql',
                          'results': [item], 'total_found': 1,
                          'message': '标题精确匹配'}
                self.redis_client.set(cache_key, result, expire=3600)
                response_time = time.time() - start_time
                self.mysql_client.record_query(
                    original_query, 'general', is_cached=False,
                    response_time=response_time
                )
                return {'success': True, 'source': 'mysql', 'data': result,
                        'response_time': response_time, 'message': '标题精确匹配'}

        # 3. 使用BM25判断是否使用RAG或MySQL
        should_use_rag = self.bm25_search.should_use_rag(query)

        result = None
        source = None

        if should_use_rag:
            # 如果应该使用RAG，返回提示
            result = {
                'query': original_query,
                'processed_query': processed_query,
                'decision': 'rag',
                'bm25_score': None,
                'message': '此问题建议使用RAG系统处理，可以获得更准确的答案'
            }
            source = 'rag_decision'
        else:
            # 使用MySQL搜索
            mysql_results = self.mysql_client.search_knowledge(query, limit=5)

            if mysql_results:
                # 格式化结果
                formatted_results = []
                for item in mysql_results:
                    formatted_results.append(self._format_knowledge(item))

                result = {
                    'query': original_query,
                    'processed_query': processed_query,
                    'decision': 'mysql',
                    'results': formatted_results,
                    'total_found': len(mysql_results),
                    'message': f'找到 {len(mysql_results)} 相关结果'
                }
                source = 'mysql'

                # 缓存结果
                self.redis_client.set(cache_key, result, expire=3600)  # 缓存1小时

            else:
                source = 'rag_decision'
                result = {'query': original_query, 'decision': 'rag',
                          'message': 'MySQL没有匹配内容，转入RAG检索'}

        # 记录查询统计
        response_time = time.time() - start_time
        self.mysql_client.record_query(
            original_query,
            "general",
            is_cached=(source == 'cache'),
            response_time=response_time
        )

        return {
            'success': True,
            'source': source,
            'data': result,
            'response_time': response_time,
            'message': f'查询完成，耗时: {response_time:.3f}秒'
        }

    @staticmethod
    def _format_knowledge(item: Dict[str, Any]) -> Dict[str, Any]:
        return {
            'id': item['id'], 'title': item['title'],
            'content': item['content'], 'category': item['category'],
            'source': item['source'],
            'created_at': item['created_at'].isoformat()
            if hasattr(item['created_at'], 'isoformat') else item['created_at']
        }

    def add_knowledge(self, title: str, content: str, category: str = 'general', source: str = 'manual') -> bool:
        """
        添加新知识
        Args:
            title: 标题
            content: 内容
            category: 分类
            source: 来源
        Returns:
            bool: 是否添加成功
        """
        try:
            if self.mysql_client is None:
                return False
            # 添加到MySQL
            success = self.mysql_client.insert_knowledge_data(title, content, category, source)

            if success:
                # 重新构建BM25索引
                self._build_bm25_index()
                print(f"成功添加知识: {title}")
                return True
            else:
                print(f"添加知识失败: {title}")
                return False
        except Exception as e:
            print(f"添加知识时出错: {e}")
            return False

    def get_system_stats(self) -> Dict[str, Any]:
        """
        获取系统统计信息
        Returns:
            Dict: 统计信息
        """
        return {
            'redis_stats': {
                'connected': self.redis_client.is_connected()
            },
            'mysql_stats': self.mysql_client.get_query_stats(hours=24) if self.mysql_client else {'available': False},
            'bm25_stats': self.bm25_search.get_stats()
        }

    def close(self):
        """关闭系统"""
        try:
            self.redis_client.close()
        finally:
            if self.mysql_client is not None:
                self.mysql_client.close()
        print("系统已关闭")


def main():
    """主函数"""
    # 创建问答系统
    qa_system = MySQLQASystem()

    try:
        # 测试查询
        test_queries = [
            "末地怎么去",
            "苦力怕是什么",
            "末地传送门",
            "水的方块",
            "红石电路"
        ]

        print("\n=== 测试查询 ===")
        for query in test_queries:
            print(f"\n查询: '{query}'")
            result = qa_system.process_query(query)

            if result['success']:
                print(f"来源: {result['source']}")
                print(f"消息: {result['message']}")
                print(f"耗时: {result['response_time']:.3f}秒")

                if result['data']:
                    if 'decision' in result['data'] and result['data']['decision'] == 'mysql':
                        print("MySQL结果:")
                        for i, item in enumerate(result['data']['results'][:2], 1):
                            print(f"  {i}. {item['title']} ({item['category']})")
                    else:
                        print(f"决策: {result['data'].get('decision', 'unknown')}")
            else:
                print("查询失败")

        # 显示系统统计
        print("\n=== 系统统计 ===")
        stats = qa_system.get_system_stats()
        print("Redis连接:", stats['redis_stats']['connected'])
        print("MySQL统计:", stats['mysql_stats'])
        print("BM25统计:", stats['bm25_stats'])

    except KeyboardInterrupt:
        print("\n用户中断，正在关闭系统...")
    except Exception as e:
        print(f"系统运行时出错: {e}")
    finally:
        qa_system.close()


if __name__ == "__main__":
    main()
