import numpy as np
from typing import List, Dict, Tuple, Optional
from collections import defaultdict, Counter
import json
import math
import os
import tempfile
from datetime import date, datetime

from base.config import Config
from mysql_qa.utils.preprocess import Preprocessor


class BM25Search:
    def __init__(self, k1: float = 1.2, b: float = 0.75):
        """
        初始化BM25搜索引擎
        Args:
            k1: BM25参数，控制词频饱和度
            b: BM25参数，控制文档长度归一化
        """
        self.k1 = k1
        self.b = b
        self.preprocessor = Preprocessor()

        # 文档集合
        self.documents = []

        # 文档长度
        self.doc_lengths = []

        # 平均文档长度
        self.avg_doc_length = 0

        # 倒排索引：词 -> 文档ID列表
        self.inverted_index = defaultdict(list)

        # 文档频率：词 -> 包含该词的文档数
        self.doc_frequencies = defaultdict(int)

        # 文档总数
        self.total_docs = 0

        # 搜索配置
        self.config = Config()
        self.search_config = self.config.get_search_config()

    def build_index(self, documents: List[Dict[str, any]]):
        """
        构建BM25索引
        Args:
            documents: 文档列表，每个文档是包含title和content的字典
        """
        self.documents = documents
        self.total_docs = len(documents)
        self.doc_lengths = []
        self.avg_doc_length = 0
        self.inverted_index.clear()
        self.doc_frequencies.clear()

        if self.total_docs == 0:
            return

        # 收集所有词和文档长度
        all_words = []
        doc_terms = []

        for doc in documents:
            # 预处理文档
            processed = self.preprocessor.preprocess_document(
                doc.get('title', ''),
                doc.get('content', '')
            )

            # 提取所有词
            words = processed['full_text']['tokens']
            doc_terms.append(words)
            self.doc_lengths.append(len(words))
            all_words.extend(words)

            # 构建倒排索引
            for word in words:
                self.inverted_index[word].append(len(doc_terms) - 1)
            for word in set(words):
                self.doc_frequencies[word] += 1

        # 计算平均文档长度
        self.avg_doc_length = float(np.mean(self.doc_lengths))

        print(f"BM25索引构建完成:")
        print(f"  文档数量: {self.total_docs}")
        print(f"  词汇数量: {len(self.inverted_index)}")
        print(f"  平均文档长度: {self.avg_doc_length:.2f}")

    def load_index_from_file(self, file_path: str):
        """
        从文件加载索引
        Args:
            file_path: 索引文件路径
        """
        if not os.path.exists(file_path):
            print(f"索引文件不存在: {file_path}")
            return False

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                index_data = json.load(f)

            self.documents = index_data['documents']
            self.doc_lengths = index_data['doc_lengths']
            self.avg_doc_length = index_data['avg_doc_length']
            self.inverted_index = defaultdict(list, index_data['inverted_index'])
            self.doc_frequencies = defaultdict(int, index_data['doc_frequencies'])
            self.total_docs = index_data['total_docs']

            print(f"索引加载成功: {file_path}")
            return True

        except Exception as e:
            print(f"加载索引失败: {e}")
            return False

    def save_index_to_file(self, file_path: str):
        """
        保存索引到文件
        Args:
            file_path: 保存路径
        """
        temporary_path = None
        try:
            index_data = {
                'documents': self.documents,
                'doc_lengths': self.doc_lengths,
                'avg_doc_length': self.avg_doc_length,
                'inverted_index': dict(self.inverted_index),
                'doc_frequencies': dict(self.doc_frequencies),
                'total_docs': self.total_docs
            }

            directory = os.path.dirname(os.path.abspath(file_path))
            os.makedirs(directory, exist_ok=True)
            with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=directory,
                                             prefix='.bm25-', suffix='.tmp', delete=False) as f:
                temporary_path = f.name
                json.dump(index_data, f, ensure_ascii=False, indent=2,
                          default=self._json_default)
            os.replace(temporary_path, file_path)

            print(f"索引保存成功: {file_path}")
            return True

        except Exception as e:
            print(f"保存索引失败: {e}")
            return False
        finally:
            if temporary_path and os.path.exists(temporary_path):
                os.remove(temporary_path)

    @staticmethod
    def _json_default(value):
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        if isinstance(value, np.integer):
            return int(value)
        if isinstance(value, np.floating):
            return float(value)
        raise TypeError(f"Unsupported index value: {type(value).__name__}")

    def bm25_score(self, query_terms: List[str], doc_id: int) -> float:
        """
        计算文档的BM25得分
        Args:
            query_terms: 查询词列表
            doc_id: 文档ID
        Returns:
            float: BM25得分
        """
        if doc_id >= len(self.doc_lengths):
            return 0.0

        score = 0.0
        doc_length = self.doc_lengths[doc_id]

        # 计算词频
        term_counts = Counter()
        for term in query_terms:
            if term in self.inverted_index:
                term_counts[term] = len([did for did in self.inverted_index[term] if did == doc_id])

        # BM25计算
        for term in query_terms:
            if term in self.doc_frequencies:
                df = self.doc_frequencies[term]
                idf = math.log((self.total_docs - df + 0.5) / (df + 0.5) + 1.0)

                tf = term_counts.get(term, 0)
                tf_normalized = (self.k1 + 1) * tf / (tf + self.k1 * (1 - self.b + self.b * doc_length / self.avg_doc_length))

                score += idf * tf_normalized

        return score

    def search(self, query: str, top_k: int = None, use_softmax: bool = True) -> List[Tuple[float, Dict[str, any]]]:
        """
        搜索文档
        Args:
            query: 查询字符串
            top_k: 返回结果数量
            use_softmax: 是否使用softmax归一化分数
        Returns:
            List[Tuple[float, Dict]]: 得分和文档的元组列表，按得分降序排列
        """
        if not query or self.total_docs == 0:
            return []

        # 设置默认top_k
        if top_k is None:
            top_k = self.search_config['bm25_top_k']

        # 预处理查询
        processed_query = self.preprocessor.preprocess_query(query)
        query_terms = processed_query['keywords']

        if not query_terms:
            return []

        # 计算所有文档的得分
        scores = []
        for doc_id in range(self.total_docs):
            score = self.bm25_score(query_terms, doc_id)
            if score > 0:
                scores.append((score, self.documents[doc_id]))

        # 如果使用softmax进行分数归一化
        if use_softmax and scores:
            scores_array = np.array([s[0] for s in scores])

            # 防止数值溢出
            max_score = np.max(scores_array)
            exp_scores = np.exp(scores_array - max_score)
            softmax_scores = exp_scores / np.sum(exp_scores)

            # 重新组合
            scores = [(softmax_scores[i], scores[i][1]) for i in range(len(scores))]

        # 排序并返回top_k结果
        scores.sort(key=lambda x: x[0], reverse=True)
        return scores[:top_k]

    def get_score_threshold(self, scores: List[float]) -> float:
        """
        获取分数阈值
        Args:
            scores: 分数列表
        Returns:
            float: 阈值分数
        """
        if not scores:
            return 0.0

        threshold = self.search_config['search_threshold']
        max_score = max(scores)

        # 如果最高分很低，降低阈值
        if max_score < 0.1:
            threshold = threshold * 0.5

        return threshold

    def should_use_rag(self, query: str) -> bool:
        """
        判断是否应该使用RAG系统
        Args:
            query: 查询字符串
        Returns:
            bool: True表示使用RAG，False表示使用MySQL
        """
        if self.total_docs == 0:
            return True

        # 执行搜索
        results = self.search(query, top_k=5)

        if not results:
            return True

        # 获取分数列表
        scores = [score for score, _ in results]

        # 计算决策
        threshold = self.get_score_threshold(scores)
        max_score = max(scores)

        # 如果最高分数低于阈值，使用RAG
        if max_score < threshold:
            print(f"BM25得分较低 ({max_score:.3f} < {threshold:.3f})，使用RAG系统")
            return True

        # 检查相关性
        top_doc = results[0][1]
        similarity = self.preprocessor.calculate_similarity(query, top_doc['title'] + ' ' + top_doc['content'])

        # 如果相似度很低，使用RAG
        if similarity < 0.1:
            print(f"文本相似度较低 ({similarity:.3f})，使用RAG系统")
            return True

        print(f"BM25得分较高 ({max_score:.3f})，使用MySQL系统")
        return False

    def get_stats(self) -> Dict[str, any]:
        """
        获取搜索引擎统计信息
        Returns:
            Dict: 统计信息
        """
        return {
            'total_documents': self.total_docs,
            'vocabulary_size': len(self.inverted_index),
            'avg_doc_length': self.avg_doc_length,
            'max_doc_length': max(self.doc_lengths) if self.doc_lengths else 0,
            'min_doc_length': min(self.doc_lengths) if self.doc_lengths else 0,
            'search_config': self.search_config
        }


# 使用示例
if __name__ == "__main__":
    # 创建搜索引擎
    bm25 = BM25Search()

    # 示例文档
    documents = [
        {
            "title": "末地（生物群系）",
            "content": "末地是生成于末地维度的生物群系。",
            "metadata": {"category": "entity", "source": "wiki.gg"}
        },
        {
            "title": "传送门",
            "content": "传送门是一种可以快速传送玩家的结构。",
            "metadata": {"category": "mechanic", "source": "wiki.gg"}
        },
        {
            "title": "苦力怕",
            "content": "苦力怕是一种会自爆的敌对生物。",
            "metadata": {"category": "mob", "source": "wiki.gg"}
        }
    ]

    # 构建索引
    bm25.build_index(documents)

    # 测试搜索
    test_queries = ["末地怎么去", "苦力怕的特性", "传送门建造方法"]

    for query in test_queries:
        print(f"\n查询: '{query}'")
        results = bm25.search(query, top_k=3)

        if results:
            for i, (score, doc) in enumerate(results, 1):
                print(f"  {i}. 得分: {score:.4f}")
                print(f"     标题: {doc['title']}")
                print(f"     内容: {doc['content'][:50]}...")
        else:
            print("  无结果")

        # 判断是否使用RAG
        use_rag = bm25.should_use_rag(query)
        print(f"  决策: {'使用RAG' if use_rag else '使用MySQL'}")

    # 获取统计信息
    print("\n统计信息:")
    stats = bm25.get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")
