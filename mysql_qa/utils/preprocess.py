import re
import jieba
from typing import List, Optional


class Preprocessor:
    def __init__(self):
        # 初始化jieba分词器
        jieba.initialize()

        # Minecraft相关的停用词（可以扩展）
        self.minecraft_stopwords = {
            '的', '了', '是', '在', '和', '与', '或', '一个', '这个', '那个',
            '什么', '怎么', '如何', '为什么', '哪里', '何时', '哪些', '吗',
            '呢', '吧', '啊', '呀', '哦', '嗯', '好的', '对', '不对', '可以',
            '不能', '能够', '需要', '想要', '希望', '谢谢', '请', '麻烦',
            'minecraft', 'mc', '游戏', '版本', '模组', '插件', '服务器'
        }

    def clean_text(self, text: str) -> str:
        """
        清洗文本
        Args:
            text: 原始文本
        Returns:
            str: 清洗后的文本
        """
        if not text:
            return ""

        # 去除HTML标签
        text = re.sub(r'<[^>]+>', '', text)

        # 去除多余的空白字符
        text = re.sub(r'\s+', ' ', text)

        # 去除特殊字符，但保留中英文、数字和常用标点
        text = re.sub(r'[^\w\s一-鿿　-〿＀-￯]', '', text)

        # 去除首尾空格
        text = text.strip()

        return text

    def tokenize(self, text: str, use_stopwords: bool = True) -> List[str]:
        """
        分词
        Args:
            text: 文本
            use_stopwords: 是否使用停用词过滤
        Returns:
            List[str]: 分词结果
        """
        if not text:
            return []

        # 清洗文本
        text = self.clean_text(text)

        # 中文分词
        tokens = list(jieba.cut(text))

        # 英文分词（简单处理）
        english_pattern = re.compile(r'[a-zA-Z]+')
        english_words = english_pattern.findall(text.lower())
        tokens.extend(english_words)

        # 过滤空字符串
        tokens = [token for token in tokens if token.strip()]

        # 停用词过滤
        if use_stopwords:
            tokens = [token for token in tokens
                     if token not in self.minecraft_stopwords and len(token) > 1]

        return tokens

    def normalize(self, text: str) -> str:
        """
        文本规范化：转换为小写，标准化格式
        Args:
            text: 原始文本
        Returns:
            str: 规范化后的文本
        """
        if not text:
            return ""

        # 转换为小写
        text = text.lower()

        # 清洗文本
        text = self.clean_text(text)

        return text

    def get_keywords(self, text: str, top_k: int = 10) -> List[str]:
        """
        提取关键词
        Args:
            text: 文本
            top_k: 返回关键词数量
        Returns:
            List[str]: 关键词列表
        """
        tokens = self.tokenize(text, use_stopwords=True)

        # 统计词频
        word_freq = {}
        for token in tokens:
            word_freq[token] = word_freq.get(token, 0) + 1

        # 按频率排序
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)

        # 返回前top_k个关键词
        return [word for word, freq in sorted_words[:top_k]]

    def preprocess_query(self, query: str) -> dict:
        """
        查询预处理
        Args:
            query: 查询文本
        Returns:
            dict: 预处理结果
        """
        return {
            'original': query,
            'cleaned': self.clean_text(query),
            'normalized': self.normalize(query),
            'tokens': self.tokenize(query, use_stopwords=True),
            'keywords': self.get_keywords(query, top_k=10)
        }

    def preprocess_document(self, title: str, content: str) -> dict:
        """
        文档预处理
        Args:
            title: 标题
            content: 内容
        Returns:
            dict: 预处理结果
        """
        # 合并标题和内容
        full_text = f"{title} {content}"

        return {
            'title': {
                'original': title,
                'normalized': self.normalize(title),
                'tokens': self.tokenize(title, use_stopwords=True)
            },
            'content': {
                'original': content,
                'normalized': self.normalize(content),
                'tokens': self.tokenize(content, use_stopwords=True)
            },
            'full_text': {
                'original': full_text,
                'normalized': self.normalize(full_text),
                'tokens': self.tokenize(full_text, use_stopwords=True)
            },
            'keywords': self.get_keywords(full_text, top_k=20)
        }

    def calculate_similarity(self, text1: str, text2: str) -> float:
        """
        计算两个文本的相似度（基于词重叠）
        Args:
            text1: 文本1
            text2: 文本2
        Returns:
            float: 相似度分数（0-1）
        """
        tokens1 = set(self.tokenize(text1, use_stopwords=True))
        tokens2 = set(self.tokenize(text2, use_stopwords=True))

        if not tokens1 and not tokens2:
            return 1.0
        if not tokens1 or not tokens2:
            return 0.0

        intersection = len(tokens1 & tokens2)
        union = len(tokens1 | tokens2)

        return intersection / union if union > 0 else 0.0

    def extract_ngrams(self, text: str, n: int = 2) -> List[str]:
        """
        提取n-gram
        Args:
            text: 文本
            n: n-gram的n值
        Returns:
            List[str]: n-gram列表
        """
        tokens = self.tokenize(text, use_stopwords=False)
        ngrams = []

        for i in range(len(tokens) - n + 1):
            ngram = ' '.join(tokens[i:i+n])
            ngrams.append(ngram)

        return ngrams


# 使用示例
if __name__ == "__main__":
    preprocessor = Preprocessor()

    # 测试文本预处理
    test_text = "Minecraft末地生物群系有什么特点？"
    result = preprocessor.preprocess_query(test_text)
    print("查询预处理结果:")
    print(f"原始: {result['original']}")
    print(f"清洗后: {result['cleaned']}")
    print(f"规范化: {result['normalized']}")
    print(f"分词: {result['tokens']}")
    print(f"关键词: {result['keywords']}")

    # 测试文档预处理
    doc_result = preprocessor.preprocess_document(
        title="末地（生物群系）",
        content="末地是生成于末地维度的生物群系。"
    )
    print("\n文档预处理结果:")
    print(f"标题关键词: {doc_result['title']['tokens']}")
    print(f"内容关键词: {doc_result['content']['tokens']}")
    print(f"全文关键词: {doc_result['keywords']}")

    # 测试相似度计算
    text1 = "Minecraft末地传送门怎么建造"
    text2 = "末地传送门的建造方法"
    similarity = preprocessor.calculate_similarity(text1, text2)
    print(f"\n相似度: {similarity:.2f}")

    # 测试n-gram
    ngrams = preprocessor.extract_ngrams(test_text, n=2)
    print(f"\n2-grams: {ngrams}")