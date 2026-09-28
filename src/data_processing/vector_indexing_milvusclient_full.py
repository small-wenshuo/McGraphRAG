"""
向量化索引模块
功能：使用BGE-M3模型进行embedding，构建Milvus向量数据库
"""

import json
import os
from typing import List, Dict, Any
from pathlib import Path
import numpy as np
from milvus_model.hybrid import BGEM3EmbeddingFunction
from base.config import Config
# 尝试导入向量数据库相关库
from pymilvus import MilvusClient, DataType,RRFRanker

MILVUS_AVAILABLE = True



class VectorIndexBuilder:
    """向量索引构建器"""

    def __init__(self, model_name: str = "BAAI/bge-m3"):
        """
        初始化构建器

        Args:
            model_name: BGE模型名称
        """
        self.model_name = model_name
        self.model = None
        self.milvus_config = Config().get_milvus_config()
        self.collection_name = self.milvus_config['collection_name']
        self.embedding_dim = 1024  # BGE-M3的默认维度

        # 检查依赖
        if not MILVUS_AVAILABLE:
            raise ImportError("请安装Milvus: pip install pymilvus")

        self.client = None

    def _has_sparse_embedding(self, sparse_vector) -> bool:
        """
        安全地检查sparse向量是否有非零元素

        Args:
            sparse_vector: sparse向量（可能是scipy sparse matrix或dict）

        Returns:
            bool: 是否有非零元素
        """
        if sparse_vector is None:
            return False

        # 如果是字典格式
        if isinstance(sparse_vector, dict):
            return len(sparse_vector) > 0

        # 如果是scipy sparse matrix
        if hasattr(sparse_vector, 'getnnz'):
            return sparse_vector.getnnz() > 0
        if hasattr(sparse_vector, 'nnz'):
            return sparse_vector.nnz > 0

        return False

    def _safe_dense_format(self, dense_vector):
        """
        安全地处理dense向量，确保是list格式

        Args:
            dense_vector: dense向量（可能是np.ndarray或list）

        Returns:
            list: 适合插入Milvus的列表格式
        """
        if dense_vector is None:
            return []
        if isinstance(dense_vector, np.ndarray):
            return dense_vector.tolist()
        return dense_vector

    def _safe_dict_length(self, sparse_dict) -> int:
        """
        安全地获取sparse字典的长度

        Args:
            sparse_dict: sparse字典

        Returns:
            int: 字典长度
        """
        if sparse_dict is None:
            return 0
        if isinstance(sparse_dict, dict):
            return len(sparse_dict)
        # """
        # 初始化构建器
        # Args:model_name: BGE模型名称
        # """
        # self.model_name = model_name
        self.model = None
        self.collection_name = "minecraft_knowledge"
        self.embedding_dim = 1024  # BGE-M3的默认维度

        # 检查依赖
        if not MILVUS_AVAILABLE:
            raise ImportError("请安装Milvus: pip install pymilvus")

        # 初始化模型
        self._init_model()

        # Milvus配置
        self.milvus_config = {
            'host': 'localhost',
            'port': '19530'
        }

        self.client = MilvusClient(
            uri=f"http://{self.milvus_config['host']}:{self.milvus_config['port']}"
        )

    def _init_model(self):
        """初始化BGE-M3模型"""
        if self.model is not None:
            return
        print(f"加载模型: {self.model_name}")
        model_path = Path(__file__).resolve().parents[2] / 'model' / 'bge-m3'
        self.model = BGEM3EmbeddingFunction(model_name_or_path=str(model_path))
        print("模型加载完成")

    def connect_to_milvus(self):
        """连接到Milvus"""
        try:
            if self.client is None:
                self.client = MilvusClient(
                    uri=f"http://{self.milvus_config['host']}:{self.milvus_config['port']}",
                    db_name=self.milvus_config['database_name']
                )
            self.client.list_collections()
            print("成功连接到Milvus")
            return True
        except Exception as e:
            self.client = None
            print(f"连接Milvus失败: {e}")
            return False

    def create_collection(self, replace_existing: bool = False):
        """使用MilvusClient创建集合"""

        if self.client.has_collection(self.collection_name):
            if not replace_existing:
                raise RuntimeError(f"集合 {self.collection_name} 已存在；拒绝覆盖现有数据")
            self.client.drop_collection(self.collection_name)

        schema = self.client.create_schema(
            auto_id=True,
            enable_dynamic_field=False
        )

        schema.add_field("id", DataType.INT64, is_primary=True)
        schema.add_field("chunk_id", DataType.VARCHAR, max_length=256)
        schema.add_field("content_type", DataType.VARCHAR, max_length=50)
        schema.add_field("content", DataType.VARCHAR, max_length=65535)
        schema.add_field("metadata", DataType.JSON)
        schema.add_field("source_id", DataType.VARCHAR, max_length=256)
        schema.add_field("title", DataType.VARCHAR, max_length=256)
        schema.add_field("embedding", DataType.FLOAT_VECTOR, dim=self.embedding_dim)
        schema.add_field("sparse_embedding", DataType.SPARSE_FLOAT_VECTOR, max_elements=250002)

        self.client.create_collection(
            collection_name=self.collection_name,
            schema=schema
        )

        # 添加索引
        index_params = self.client.prepare_index_params()
        # 添加dense向量索引
        index_params.add_index(
            field_name="embedding",
            index_type="FLAT",
            metric_type="IP",
            params={}
        )
        # sparse 向量索引
        index_params.add_index(
            field_name="sparse_embedding",
            index_type="SPARSE_INVERTED_INDEX",
            metric_type="IP",
            params={}
        )

        # 创建索引
        self.client.create_index(
            collection_name=self.collection_name,
            index_params=index_params
        )
        print(f"已为字段 embedding 创建索引，sparse_embedding 使用默认索引")

        print(f"集合 {self.collection_name} 创建完成")
        return self.client

    def prepare_embeddings_data(self) -> Dict[str, Any]:
        """
        准备用于embedding的数据

        Returns:
            包含文本和元数据的字典
        """
        # 加载chunks
        data_dir = Path(__file__).resolve().parents[2] / 'data' / 'processed'
        chunks_file = data_dir / 'cleaned_chunks.json'
        with open(chunks_file, 'r', encoding='utf-8') as f:
            chunks = json.load(f)

        # 加载实体
        entities_file = data_dir / 'extracted_entities.json'
        with open(entities_file, 'r', encoding='utf-8') as f:
            entities = json.load(f)

        # 准备文本列表
        texts_to_embed = []
        metadata_list = []

        # 1. 添加chunks
        for chunk in chunks:
            texts_to_embed.append(chunk['content'])
            metadata_list.append({
                'chunk_id': chunk['chunk_id'],
                'content_type': 'chunk',
                'source_id': chunk.get('source_id', ''),
                'title': chunk.get('title', ''),
                'content': chunk['content'],
                'metadata': chunk.get('metadata', {})
            })

        # 2. 添加实体描述
        for entity in entities:
            # 创建实体描述
            entity_desc = f"{entity['name']} ({entity.get('type', 'unknown')})"
            if entity.get('aliases'):
                entity_desc += f" 别名: {', '.join(entity['aliases'])}"
            entity_desc += f" 来源: {entity.get('source_title', '')}"

            texts_to_embed.append(entity_desc)
            metadata_list.append({
                'chunk_id': entity.get('id', ''),
                'content_type': 'entity',
                'source_id': entity.get('source_id', ''),
                'title': entity.get('source_title', ''),
                'content': entity_desc,
                'metadata': {
                    'entity_type': entity.get('type', ''),
                    'entity_id': entity.get('id', ''),
                    'confidence': entity.get('confidence', 0.0)
                }
            })

        # 3. 添加事实描述（从关系生成）
        relations_file = data_dir / 'extracted_relations.json'
        with open(relations_file, 'r', encoding='utf-8') as f:
            relations = json.load(f)

        for relation in relations:
            # 创建事实描述
            fact_desc = f"{relation.get('subject_name', '')} {self._get_relation_desc(relation['relation_type'])} {relation.get('object_name', '')}"
            fact_desc += f" 证据: {relation.get('evidence_text', '')}"

            texts_to_embed.append(fact_desc)
            metadata_list.append({
                'chunk_id': relation.get('source_chunk_id', ''),
                'content_type': 'fact',
                'source_id': relation.get('source_url', ''),
                'title': relation.get('source_title', ''),
                'content': fact_desc,
                'metadata': {
                    'relation_type': relation['relation_type'],
                    'subject_id': relation.get('subject_id', ''),
                    'object_id': relation.get('object_id', ''),
                    'confidence': relation.get('confidence', 0.0),
                    'evidence_text': relation.get('evidence_text', '')
                }
            })

        return {
            'texts': texts_to_embed,
            'metadata': metadata_list
        }

    def _get_relation_desc(self, relation_type: str) -> str:
        """获取关系类型的中文描述"""
        relation_descs = {
            'crafted_from': '由...合成',
            'drops': '掉落',
            'spawns_in': '生成于',
            'used_for': '用于',
            'requires': '需要',
            'transforms_to': '转变为',
            'counters': '克制',
            'found_in': '发现于',
            'enabled_by_version': '版本启用',
            'damaged_by': '被...伤害',
            'attacks_with': '使用...攻击',
            'affected_by': '受...影响',
            'smelts_to': '熔炼为',
            'can_brew_into': '可酿造为',
            'can_enchant_with': '可附魔为',
            'mentions': '提到'
        }
        return relation_descs.get(relation_type, relation_type)

    def generate_embeddings(self, texts: List[str]) -> Dict[str, Any]:
        """
        生成文本的embedding（BGE-M3返回dense+sparse混合向量）

        Args:
            texts: 文本列表

        Returns:
            混合向量字典，包含dense和sparse两部分
        """
        print(f"生成 {len(texts)} 个文本的embedding...")
        # BGEM3EmbeddingFunction 直接调用模型
        self._init_model()
        embeddings = self.model(texts)
        print(f"原始返回类型: {type(embeddings)}")

        # BGE-M3返回的混合向量格式
        # embeddings = {
        #     'dense': [array1, array2, ...],  # 密集向量列表
        #     'sparse': CSR矩阵               # 稀疏矩阵
        # }
        return embeddings

    def insert_embeddings_to_milvus(self, collection, embeddings: Dict[str, Any], metadata_list: List[Dict]):
        """
        将embedding数据插入Milvus

        Args:
            collection: Milvus集合（保留参数用于兼容）
            embeddings: BGE-M3返回的混合向量字典
            metadata_list: 元数据列表
        """
        print(f"插入 {len(embeddings)} 个混合向量到Milvus...")
        print(f"Embeddings键: {embeddings.keys()}")

        # 检查sparse向量格式 - 使用安全的检查方式
        sparse_sample = embeddings['sparse'][0] if embeddings['sparse'] is not None else None
        if sparse_sample is not None and self._has_sparse_embedding(sparse_sample):
            print(f"Sparse原始类型: {type(sparse_sample)}")
            print(f"Sparse.shape: {sparse_sample.shape}")
            if hasattr(sparse_sample, 'getnnz'):
                print(f"Sparse.getnnz(): {sparse_sample.getnnz()}")

        # 准备数据 - 直接构建插入数据，避免中间步骤
        insert_data = []
        for i, metadata in enumerate(metadata_list):
            # 获取dense向量（BGE-M3返回的是列表形式）
            dense_vector = embeddings['dense'][i]

            # 获取sparse向量
            sparse_vector = embeddings['sparse'][i]

            # 转换sparse向量为Milvus要求的Dict[int, float]格式
            # 确保使用CSR格式进行转换
            if hasattr(sparse_vector, 'tocsr'):
                sparse_csr = sparse_vector.tocsr()
                # 使用CSR的indices和data属性获取非零元素
                indices = sparse_csr.indices
                data = sparse_csr.data
                sparse_dict = {int(idx): float(val) for idx, val in zip(indices, data)}

                # 打印转换信息
                print(f"  转换后类型: {type(sparse_dict)}")
                print(f"  转换后非零元素数量: {self._safe_dict_length(sparse_dict)}")

            else:
                # 如果无法转换为CSR，尝试其他方法
                if hasattr(sparse_vector, 'tocoo'):
                    sparse_coo = sparse_vector.tocoo()
                    sparse_dict = {int(col): float(val) for col, val in zip(sparse_coo.col, sparse_coo.data)}
                    print(f"  使用COO转换，非零元素数量: {self._safe_dict_length(sparse_dict)}")
                else:
                    # 如果已经是字典，检查格式
                    if isinstance(sparse_vector, dict):
                        # 如果已经是Dict[int, float]格式，直接使用
                        if all(isinstance(k, int) and isinstance(v, (float, np.floating)) for k, v in sparse_vector.items()):
                            sparse_dict = sparse_vector
                            print(f"  使用现有字典格式，非零元素数量: {self._safe_dict_length(sparse_dict)}")
                        else:
                            # 尝试转换其他字典格式
                            print(f"  警告：字典格式不正确: {sparse_vector.keys()}")
                            sparse_dict = {}
                            print(f"  使用空字典格式")
                    else:
                        # 其他格式不支持
                        print(f"  警告：不支持的sparse格式: {type(sparse_vector)}")
                        sparse_dict = {}
                        print(f"  使用空字典格式")

            # 验证sparse字典格式
            if isinstance(sparse_dict, dict):
                # 检查是否是Dict[int, float]格式
                is_valid_format = True
                if self._safe_dict_length(sparse_dict) > 0:  # 非空字典
                    for k, v in sparse_dict.items():
                        if not isinstance(k, int) or not isinstance(v, (float, np.floating)):
                            is_valid_format = False
                            break

                if is_valid_format:
                    print(f"✅ Sparse向量格式正确: {self._safe_dict_length(sparse_dict)} 个非零元素")
                else:
                    print(f"❌ Sparse向量格式错误: {type(sparse_dict)}")
                    # 尝试修复
                    try:
                        if "indices" in sparse_dict and "values" in sparse_dict:
                            sparse_dict = {int(k): float(v) for k, v in zip(sparse_dict["indices"], sparse_dict["values"])}
                            print(f"✅ 修复后格式: {self._safe_dict_length(sparse_dict)} 个非零元素")
                    except Exception as e:
                        print(f"❌ 无法修复sparse格式: {e}")
                        sparse_dict = {}

            row = {
                "chunk_id": metadata['chunk_id'],
                "content_type": metadata['content_type'],
                "content": metadata['content'],
                "metadata": metadata,
                "source_id": metadata['source_id'],
                "title": metadata['title'],
                "embedding": self._safe_dense_format(dense_vector),
                "sparse_embedding": sparse_dict
            }
            insert_data.append(row)

        # 在插入前打印详细的sparse信息
        print(f"\n=== 插入前数据验证 ===")
        for i, row in enumerate(insert_data[:3]):  # 只检查前3条数据
            if 'sparse_embedding' in row:
                sparse_emb = row['sparse_embedding']
                print(f"数据 {i+1}:")
                print(f"  sparse_embedding类型: {type(sparse_emb)}")
                if isinstance(sparse_emb, dict):
                    print(f"  sparse_embedding长度: {self._safe_dict_length(sparse_emb)}")
                    if self._safe_dict_length(sparse_emb) > 0:
                        print(f"  前5个元素: {dict(list(sparse_emb.items())[:5])}")
                else:
                    print(f"  sparse_embedding: {sparse_emb}")

        print(f"\n准备插入 {len(insert_data)} 条数据...")
        self.client.insert(collection_name=self.collection_name, data=insert_data)
        print("数据插入完成")

    def create_vector_index(self, replace_existing: bool = False):
        """
        完整的向量索引创建流程
        """
        print("开始创建向量索引...")

        # 1. 连接到Milvus
        if not self.connect_to_milvus():
            return False

        # 2. 创建集合
        collection = self.create_collection(replace_existing=replace_existing)

        # 3. 准备数据
        print("准备embedding数据...")
        embedding_data = self.prepare_embeddings_data()
        print(f"准备嵌入的文本数量: {len(embedding_data['texts'])}")
        print(f"准备嵌入的元数据数量: {len(embedding_data['metadata'])}")

        # 4. 生成embedding
        print("开始生成embedding...")
        embeddings = self.generate_embeddings(embedding_data['texts'])

        # 5. 插入到Milvus
        print("开始插入数据...")
        self.insert_embeddings_to_milvus(
            collection,
            embeddings,
            embedding_data['metadata']
        )

        # 6. 加载数集以便查询
        print("加载集合...")
        self.client.load_collection(collection_name=self.collection_name)
        print("集合加载完成")

        # 等待加载完成（最多等待30秒）
        import time
        max_wait = 30
        wait_time = 0
        while wait_time < max_wait:
            state = self.client.get_load_state(collection_name=self.collection_name)
            print(f"加载状态: {state}")

            # 检查加载状态 - state是字典，'state'键值是LoadState枚举对象
            state_obj = state.get('state')
            if state_obj:
                # 将LoadState枚举对象转换为字符串进行比较
                state_str = str(state_obj)
                if state_str == "Loaded":
                    print("✅ 集合已成功加载")
                    break
                elif state_str == "Loading":
                    print("⏳ 集合正在加载中...")
                else:
                    print(f"📊 集合加载状态: {state_str}")
            else:
                print("❌ 无法获取加载状态")

            print(f"等待集合加载完成... ({wait_time}/{max_wait}秒)")
            time.sleep(1)
            wait_time += 1
        else:
            print("⚠️ 警告：集合加载超时，但仍继续执行")

        # 7. 保存配置
        self._save_config()

        print("向量索引创建完成！")
        return True

    def _save_config(self):
        """保存配置文件"""
        config = {
            'collection_name': self.collection_name,
            'model_name': self.model_name,
            'embedding_dim': self.embedding_dim,
            'milvus_config': self.milvus_config,
            'created_at': str(np.datetime64('now'))
        }

        config_file = "D:\codex\mcGraph\data\processed/vector_config.json"
        Path(config_file).parent.mkdir(parents=True, exist_ok=True)

        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

        print(f"配置已保存到: {config_file}")

    def search_vectors(self, query_text: str, top_k: int = 5) -> List[Dict]:
        """
        使用混合搜索（dense + sparse）搜索相似向量

        Args:
            query_text: 查询文本
            top_k: 返回前k个结果

        Returns:
            搜索结果列表
        """
        if not self.connect_to_milvus():
            return []

        # 加载集合
        if not self.client.has_collection(self.collection_name):
            return []
        self.client.load_collection(collection_name=self.collection_name)

        # 生成查询向量（BGE-M3返回dense+sparse混合向量）
        self._init_model()
        query_embedding = self.model([query_text])

        # 确保查询格式正确
        dense_vector = self._safe_dense_format(query_embedding['dense'][0])  # 第一个查询的dense向量
        sparse_vector = query_embedding['sparse'][0]  # 第一个查询的sparse向量

        # 转换sparse向为Milvus要求的Dict[int, float]格式
        if hasattr(sparse_vector, 'tocsr'):
            sparse_csr = sparse_vector.tocsr()
            # 使用CSR的indices和data属性获取非零元素
            indices = sparse_csr.indices
            data = sparse_csr.data
            sparse_dict = {int(idx): float(val) for idx, val in zip(indices, data)}
        elif hasattr(sparse_vector, 'tocoo'):
            # 如果是COO格式
            sparse_coo = sparse_vector.tocoo()
            sparse_dict = {int(col): float(val) for col, val in zip(sparse_coo.col, sparse_coo.data)}
        else:
            # 如果已经是字典，检查格式
            if isinstance(sparse_vector, dict):
                # 如果已经是Dict[int, float]格式，直接使用
                if all(isinstance(k, int) and isinstance(v, (float, np.floating)) for k, v in sparse_vector.items()):
                    sparse_dict = sparse_vector
                else:
                    # 尝试修复其他字典格式
                    print(f"警告：字典格式不正确: {list(sparse_vector.keys())[:5]}...")
                    sparse_dict = {}
            else:
                # 其他格式不支持
                print(f"警告：不支持的sparse格式: {type(sparse_vector)}")
                sparse_dict = {}

        # 创建AnnSearchRequest用于dense向量搜索
        from pymilvus import AnnSearchRequest
        dense_search_params = {
            "metric_type": "IP",
            "params": {"ef": 64}
        }

        dense_req = AnnSearchRequest(
            data=[dense_vector],
            anns_field="embedding",
            param=dense_search_params,
            limit=top_k
        )

        # 创建AnnSearchRequest用于sparse向量搜索
        sparse_search_params = {
            "metric_type": "IP",
            "params": {}  # sparse vector使用默认参数
        }

        sparse_req = AnnSearchRequest(
            data=[sparse_dict],
            anns_field="sparse_embedding",
            param=sparse_search_params,
            limit=top_k
        )

        # 执行混合搜索
        try:
            results = self.client.hybrid_search(
                collection_name=self.collection_name,
                reqs=[dense_req, sparse_req],
                ranker=RRFRanker(k=60),
                limit=top_k,
                output_fields=[
                    "id",
                    "chunk_id",
                    "content_type",
                    "content",
                    "title",
                    "metadata"
                ]
            )

            search_results = []

            for hits in results:
                for hit in hits:
                    entity = hit.get("entity", {})

                    search_results.append({
                        "id": hit.get("id"),
                        "distance": hit.get("distance"),
                        "score": hit.get("distance"),
                        "content": entity.get("content", ""),
                        "content_type": entity.get("content_type", ""),
                        "title": entity.get("title", ""),
                        "metadata": entity.get("metadata", {})
                    })

            print(f"混合搜索完成，返回 {len(search_results)} 个结果")
            return search_results

        except Exception as e:
            print(f"混合搜索失败: {e}")
            print("尝试回退到普通dense向量搜索...")

            try:
                results = self.client.search(
                    collection_name=self.collection_name,
                    data=[dense_vector],
                    anns_field="embedding",
                    search_params={
                        "metric_type": "IP",
                        "params": {"ef": 64}
                    },
                    limit=top_k,
                    output_fields=[
                        "id",
                        "chunk_id",
                        "content_type",
                        "content",
                        "title",
                        "metadata"
                    ]
                )

                search_results = []

                for hits in results:
                    for hit in hits:
                        entity = hit.get("entity", {})

                        search_results.append({
                            "id": hit.get("id"),
                            "distance": hit.get("distance"),
                            "score": hit.get("distance"),
                            "content": entity.get("content", ""),
                            "content_type": entity.get("content_type", ""),
                            "title": entity.get("title", ""),
                            "metadata": entity.get("metadata", {})
                        })

                print(f"回退搜索完成，返回 {len(search_results)} 个结果")
                return search_results

            except Exception as fallback_error:
                print(f"回退搜索也失败: {fallback_error}")
                return []

    def export_embeddings_to_json(self, output_file: str = "D:\codex\mcGraph\data\processed/embeddings.json"):
        """
        导出embedding数据到JSON（用于调试或备份）

        Args:
            output_file: 输出文件路径
        """
        if not self.connect_to_milvus():
            print("无法连接到Milvus")
            return

        # 加载集合
        collection = self.client
        self.client.load_collection(collection_name=self.collection_name)

        # 查询所有数据
        results = self.client.query(
            collection_name=self.collection_name,
            filter="",
            limit=16384,
            output_fields=[
                "id",
                "chunk_id",
                "content_type",
                "content",
                "metadata",
                "source_id",
                "title"
            ]
        )

        # 保存结果
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        print(f"embedding数据已导出到: {output_file}")


def main():
    """主函数：演示向量索引创建"""
    try:
        # 创建构建器
        builder = VectorIndexBuilder(model_name="BAAI/bge-m3")

        # 创建向量索引
        success = builder.create_vector_index()

        if success:
            # 演示搜索
            print("\n=== 演示向量搜索 ===")
            query = "钻石镐怎么制作"
            results = builder.search_vectors(query, top_k=3)

            print(f"查询: {query}")
            print(f"返回 {len(results)} 个结果:")
            for i, result in enumerate(results, 1):
                print(f"\n{i}. {result['title']}")
                print(f"   类型: {result['content_type']}")
                print(f"   内容: {result['content'][:100]}...")
                print(f"   距离: {result['distance']:.4f}")
                print(f"   元数据: {result['metadata']}")

            # 导出数据
            builder.export_embeddings_to_json()
        else:
            print("向量索引创建失败")

    except ImportError as e:
        print(f"错误: {e}")
        print("请安装必要的依赖：")
    except Exception as e:
        print(f"错误: {e}")
        print("请确保Milvus服务正在运行")


if __name__ == "__main__":
    main()
