"""
文本清洗模块
功能：去除噪声、导航、重复内容、无关段落
"""

import re
import json
from typing import List, Dict, Any
from pathlib import Path


class TextCleaner:
    """文本清洗器"""

    def __init__(self):
        """初始化清洗器"""
        # 常见噪声模式
        self.noise_patterns = [
            r'\s*编辑\s*',  # 编辑标记
            r'\s*查看\s*',  # 查看标记
            r'\s*导航\s*',  # 导航标记
            r'\s*分类\s*',  # 分类标记
            r'\s*页面\s*',  # 页面标记
            r'\s*目录\s*',  # 目录标记
            r'\s*\[.*\]',  # 方括号内容
            r'\*\*.*?\*\*',  # 加粗标记
            r'<!--.*?-->',  # HTML注释
            r'<[^>]+>',  # HTML标签
        ]

        # Minecraft相关的噪声
        self.minecraft_noise = [
            r'\s*教程\s*',
            r'\s*攻略\s*',
            r'\s*模组\s*',
            r'\s*插件\s*',
            r'\s*数据包\s*',
        ]

    def clean_text(self, text: str) -> str:
        """
        清洗单个文本

        Args:
            text: 原始文本

        Returns:
            清洗后的文本
        """
        if not text:
            return ""

        # 移除空白行
        lines = [line.strip() for line in text.split('\n') if line.strip()]

        # 过滤噪声
        cleaned_lines = []
        for line in lines:
            # 检查是否包含噪声模式
            has_noise = False
            for pattern in self.noise_patterns + self.minecraft_noise:
                if re.search(pattern, line, re.IGNORECASE):
                    has_noise = True
                    break

            if not has_noise:
                cleaned_lines.append(line)

        # 合并连续的空行
        result = []
        prev_empty = False
        for line in cleaned_lines:
            if not line.strip() and prev_empty:
                continue
            result.append(line)
            prev_empty = not line.strip()

        return '\n'.join(result)

    def clean_and_chunk_documents(self, documents: List[Dict[str, Any]],
                                max_chunk_size: int = 512) -> List[Dict[str, Any]]:
        """
        清洗文档并切分chunk

        Args:
            documents: 文档列表，每个文档包含content等字段
            max_chunk_size: 每个chunk的最大字符数

        Returns:
            清洗后的chunk列表
        """
        chunks = []

        for doc in documents:
            # 获取文档基本信息
            doc_id = doc.get('id', '')
            title = doc.get('title', '')
            content = doc.get('content', '')

            if not content:
                continue

            # 清洗文本
            cleaned_content = self.clean_text(content)

            # 分chunk（简单的按段落分割）
            paragraphs = cleaned_content.split('\n')
            current_chunk = []
            current_size = 0

            for para in paragraphs:
                para = para.strip()
                if not para:
                    continue

                # 如果段落太大，需要进一步切分
                if len(para) > max_chunk_size:
                    # 先处理当前chunk
                    if current_chunk:
                        chunk = {
                            'chunk_id': f"{doc_id}_{len(chunks)}",
                            'content': '\n'.join(current_chunk),
                            'source_id': doc_id,
                            'title': title,
                            'metadata': {
                                'source_id': doc_id,
                                'title': title,
                                'version': doc.get('version', ''),
                                'edition': doc.get('edition', ''),
                                'chunk_type': 'paragraph'
                            }
                        }
                        chunks.append(chunk)
                        current_chunk = []
                        current_size = 0

                    # 切分长段落
                    sub_chunks = self._split_long_text(para, max_chunk_size)
                    for i, sub_chunk in enumerate(sub_chunks):
                        chunk = {
                            'chunk_id': f"{doc_id}_para_{len(chunks)}_{i}",
                            'content': sub_chunk,
                            'source_id': doc_id,
                            'title': title,
                            'metadata': {
                                'source_id': doc_id,
                                'title': title,
                                'version': doc.get('version', ''),
                                'edition': doc.get('edition', ''),
                                'chunk_type': 'sub_paragraph'
                            }
                        }
                        chunks.append(chunk)
                else:
                    # 检查是否需要新建chunk
                    if current_size + len(para) + 1 > max_chunk_size and current_chunk:
                        # 保存当前chunk
                        chunk = {
                            'chunk_id': f"{doc_id}_{len(chunks)}",
                            'content': '\n'.join(current_chunk),
                            'source_id': doc_id,
                            'title': title,
                            'metadata': {
                                'source_id': doc_id,
                                'title': title,
                                'version': doc.get('version', ''),
                                'edition': doc.get('edition', ''),
                                'chunk_type': 'paragraph'
                            }
                        }
                        chunks.append(chunk)
                        current_chunk = []
                        current_size = 0

                    current_chunk.append(para)
                    current_size += len(para) + 1

            # 处理最后一个chunk
            if current_chunk:
                chunk = {
                    'chunk_id': f"{doc_id}_{len(chunks)}",
                    'content': '\n'.join(current_chunk),
                    'source_id': doc_id,
                    'title': title,
                    'metadata': {
                        'source_id': doc_id,
                        'title': title,
                        'version': doc.get('version', ''),
                        'edition': doc.get('edition', ''),
                        'chunk_type': 'paragraph'
                    }
                }
                chunks.append(chunk)

        return chunks

    def _split_long_text(self, text: str, max_size: int) -> List[str]:
        """
        切分长文本

        Args:
            text: 长文本
            max_size: 最大字符数

        Returns:
            切分后的文本列表
        """
        chunks = []

        # 先按句子分割
        sentences = re.split(r'([。！？.!?])', text)
        sentences = [s for s in sentences if s.strip()]

        current_chunk = []
        current_size = 0

        for i in range(0, len(sentences), 2):
            # 获取完整的句子（包括标点）
            if i + 1 < len(sentences):
                sentence = sentences[i] + sentences[i + 1]
            else:
                sentence = sentences[i]

            # 如果句子太长，强制分割
            if len(sentence) > max_size:
                # 先处理当前chunk
                if current_chunk:
                    chunks.append(''.join(current_chunk))
                    current_chunk = []
                    current_size = 0

                # 分割长句子
                while len(sentence) > max_size:
                    chunks.append(sentence[:max_size])
                    sentence = sentence[max_size:]

                if sentence:
                    current_chunk.append(sentence)
                    current_size += len(sentence)
            else:
                # 检查是否需要新建chunk
                if current_size + len(sentence) + 1 > max_size and current_chunk:
                    chunks.append(''.join(current_chunk))
                    current_chunk = []
                    current_size = 0

                current_chunk.append(sentence)
                current_size += len(sentence)

        # 添加最后一个chunk
        if current_chunk:
            chunks.append(''.join(current_chunk))

        return chunks

    def load_documents_from_markdown(self, md_dir: str) -> List[Dict[str, Any]]:
        """
        从markdown文件加载文档

        Args:
            md_dir: markdown文件所在目录

        Returns:
            文档列表
        """
        documents = []
        md_path = Path(md_dir)

        # 从sources.json获取元数据
        sources_file = md_path.parent / "sources.json"
        sources = {}
        if sources_file.exists():
            with open(sources_file, 'r', encoding='utf-8') as f:
                sources_data = json.load(f)
                sources = {s['id']: s for s in sources_data}

        # 遍历markdown文件
        for md_file in md_path.glob("*.md"):
            with open(md_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # 从文件名推断id
            doc_id = f"minecraft-wiki-{md_file.stem}"

            # 从sources获取元数据
            source = sources.get(doc_id, {})

            # 提取标题（第一个#开头的行）
            title_match = re.search(r'^# (.+)$', content, re.MULTILINE)
            title = title_match.group(1) if title_match else md_file.stem

            doc = {
                'id': doc_id,
                'title': title,
                'content': content,
                'version': source.get('version_range', ''),
                'edition': source.get('edition', ''),
                'source_url': source.get('source_url', ''),
                'retrieved_at': source.get('retrieved_at', '')
            }

            documents.append(doc)

        return documents


def main():
    """主函数：演示文本清洗和切块"""
    # 创建清洗器
    cleaner = TextCleaner()

    # 从markdown文件加载文档
    md_dir = "F:/all project/mcGraphrag/data/raw/firecrawl/pages"
    documents = cleaner.load_documents_from_markdown(md_dir)

    # 清洗并切块
    chunks = cleaner.clean_and_chunk_documents(documents, max_chunk_size=512)

    # 保存结果
    output_file = "F:/all project/mcGraphrag/data/processed/cleaned_chunks.json"
    Path(output_file).parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)

    print(f"清洗完成，共生成 {len(chunks)} 个chunks")
    print(f"结果已保存到: {output_file}")


if __name__ == "__main__":
    main()