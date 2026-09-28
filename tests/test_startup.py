import json
import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, MagicMock
from unittest.mock import patch
import pymysql
import redis

from base.config import Config
from mysql_qa.retrieval.bm25_search import BM25Search
from mysql_qa.cache.redis_client import RedisClient
from mysql_qa.main import MySQLQASystem
from mysql_qa.db.mysql_client import MySQLClient
from src.data_processing.vector_indexing_milvusclient_full import VectorIndexBuilder
from main import IntegratedQASystem
from rag_qa.core.llm_response_generator import LLMResponseGenerator, ResponseContext
from rag_qa.core.retrieval_system import RetrievalConfig, RetrievalSystem
from rag_qa.core.evidence_fusion import Evidence, EvidenceFusion
from rag_qa.core.strategy_selector import StrategySelector


class ModelConfigurationTests(unittest.TestCase):
    def test_aliyun_settings_come_from_environment(self):
        settings = {
            'DASHSCOPE_BASE_URL': 'https://example.test/v1',
            'DASHSCOPE_MODEL_NAME': 'test-model',
            'DASHSCOPE_API_KEY': 'test-key',
        }
        with patch.dict(os.environ, settings):
            config = Config()
            self.assertEqual(config.get_llm_config(), {
                'base_url': settings['DASHSCOPE_BASE_URL'],
                'model_name': settings['DASHSCOPE_MODEL_NAME'],
                'api_key': settings['DASHSCOPE_API_KEY'],
            })
            self.assertEqual(config.get_rag_config()['model_name'], 'test-model')

    def test_strategy_uses_local_fallback_without_outbound_call(self):
        with patch.dict(os.environ, {'DASHSCOPE_API_KEY': ''}), \
             patch('rag_qa.core.strategy_selector.OpenAI') as client_type:
            selector = StrategySelector()
            self.assertEqual(selector.select_strategy('钻石镐怎么制作'), '直接检索')
            client_type.assert_not_called()

    def test_strategy_uses_configured_aliyun_client(self):
        settings = {
            'DASHSCOPE_BASE_URL': 'https://example.test/v1',
            'DASHSCOPE_MODEL_NAME': 'test-model',
            'DASHSCOPE_API_KEY': 'test-key',
        }
        with patch.dict(os.environ, settings), \
             patch('rag_qa.core.strategy_selector.OpenAI') as client_type:
            response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='直接检索'))])
            client_type.return_value.chat.completions.create.return_value = response
            selector = StrategySelector()
            self.assertEqual(selector.select_strategy('钻石镐怎么制作'), '直接检索')
            self.assertEqual(client_type.call_args.kwargs['base_url'], settings['DASHSCOPE_BASE_URL'])
            self.assertEqual(client_type.call_args.kwargs['api_key'], settings['DASHSCOPE_API_KEY'])
            request = client_type.return_value.chat.completions.create.call_args.kwargs
            self.assertEqual(request['model'], settings['DASHSCOPE_MODEL_NAME'])
            self.assertIn('钻石镐怎么制作', request['messages'][1]['content'])
            self.assertNotIn('temperature', request)

    def test_answer_generator_sends_evidence_and_handles_failure(self):
        settings = {
            'DASHSCOPE_BASE_URL': 'https://example.test/v1',
            'DASHSCOPE_MODEL_NAME': 'test-model',
            'DASHSCOPE_API_KEY': 'test-key',
        }
        context = ResponseContext(
            query='钻石镐怎么制作',
            evidence_list=[{'title': '钻石镐', 'content': '需要三个钻石', 'score': 1.0,
                            'source': 'test', 'metadata': {'source': 'fixture'}}],
            core_evidence=[{'title': '钻石镐', 'content': '需要三个钻石', 'score': 1.0,
                            'source': 'test', 'metadata': {'source': 'fixture'}}],
            quality_analysis={}, stats={},
        )
        with patch.dict(os.environ, settings), \
             patch('rag_qa.core.llm_response_generator.OpenAI') as client_type:
            response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='三个钻石。'))])
            client_type.return_value.chat.completions.create.return_value = response
            generator = LLMResponseGenerator()
            self.assertEqual(generator.generate_answer(context), '三个钻石。')
            request = client_type.return_value.chat.completions.create.call_args.kwargs
            self.assertEqual(request['model'], settings['DASHSCOPE_MODEL_NAME'])
            self.assertIn('需要三个钻石', request['messages'][1]['content'])
            self.assertIn('钻石镐怎么制作', request['messages'][1]['content'])
            self.assertNotIn('temperature', request)
            client_type.return_value.chat.completions.create.side_effect = RuntimeError('offline')
            self.assertIsNone(generator.generate_answer(context))
            client_type.return_value.chat.completions.create.reset_mock()
            self.assertIsNone(generator.generate_answer(ResponseContext(
                query='未知', evidence_list=[], core_evidence=[], quality_analysis={}, stats={}
            )))
            client_type.return_value.chat.completions.create.assert_not_called()


class BM25StartupTests(unittest.TestCase):
    def test_mysql_document_index_is_saved_and_reloaded(self):
        document = {
            "id": 1,
            "title": "钻石镐",
            "content": "钻石镐需要钻石和木棍",
            "created_at": datetime(2026, 9, 27, 12, 0),
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bm25.json"
            index = BM25Search()
            index.build_index([document])
            self.assertTrue(index.save_index_to_file(str(path)))
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["documents"][0]["created_at"], "2026-09-27T12:00:00")

            loaded = BM25Search()
            self.assertTrue(loaded.load_index_from_file(str(path)))
            self.assertEqual(loaded.total_docs, 1)
            self.assertGreater(loaded.search("钻石镐")[0][0], 0)

    def test_rebuilding_index_resets_document_lengths(self):
        index = BM25Search()
        doc = {"title": "钻石镐", "content": "钻石镐"}
        index.build_index([doc])
        first_lengths = list(index.doc_lengths)
        index.build_index([doc])
        self.assertEqual(index.doc_lengths, first_lengths)


class RedisStartupTests(unittest.TestCase):
    def test_startup_checks_ping_before_reporting_success(self):
        with patch('mysql_qa.cache.redis_client.redis.StrictRedis') as redis_type, \
             patch('mysql_qa.cache.redis_client.logger') as log:
            redis_type.return_value.ping.return_value = True
            cache = RedisClient()
            redis_type.return_value.ping.assert_called_once_with()
            log.info.assert_called_once()
            self.assertTrue(cache.is_connected())

    def test_offline_redis_disables_cache_without_false_success(self):
        with patch('mysql_qa.cache.redis_client.redis.StrictRedis') as redis_type, \
             patch('mysql_qa.cache.redis_client.logger') as log:
            redis_type.return_value.ping.side_effect = redis.ConnectionError('offline')
            cache = RedisClient()
            self.assertIsNone(cache.client)
            self.assertFalse(cache.is_connected())
            self.assertIsNone(cache.get('missing'))
            self.assertFalse(cache.set('key', {'answer': 'ok'}))
            cache.close()
            log.info.assert_not_called()
            log.warning.assert_called_once()

    def test_cache_api_supports_query_path_and_close(self):
        cache = RedisClient.__new__(RedisClient)
        cache.client = Mock()
        client = cache.client
        cache.logger = Mock()
        client.get.return_value = json.dumps({"answer": "ok"})
        self.assertEqual(cache.get("query:key"), {"answer": "ok"})
        cache.set("query:key", {"answer": "ok"}, expire=60)
        client.set.assert_called_with("query:key", json.dumps({"answer": "ok"}, ensure_ascii=False), ex=60)
        cache.close()
        client.close.assert_called_once()
        self.assertIsNone(cache.client)

    def test_mysql_outage_routes_to_rag(self):
        with patch("mysql_qa.main.MySQLClient", side_effect=pymysql.err.OperationalError(2003, "offline")), \
             patch("mysql_qa.main.RedisClient") as redis_type, \
             patch("mysql_qa.main.BM25Search") as bm25_type:
            redis_type.return_value.get.return_value = None
            bm25_type.return_value.load_index_from_file.return_value = True
            system = MySQLQASystem()
            self.assertIsNone(system.mysql_client)
            self.assertEqual(system.process_query("测试")['source'], 'rag_decision')
            system.close()

    def test_exact_title_uses_mysql_and_serializable_cache(self):
        with patch("mysql_qa.main.MySQLClient") as mysql_type, \
             patch("mysql_qa.main.RedisClient") as redis_type, \
             patch("mysql_qa.main.BM25Search") as bm25_type:
            redis_type.return_value.get.return_value = None
            bm25 = bm25_type.return_value
            bm25.load_index_from_file.return_value = True
            bm25.documents = [{'id': 7, 'title': '钻石'}]
            mysql_type.return_value.get_by_id.return_value = {
                'id': 7, 'title': '钻石', 'content': '一种物品',
                'category': 'item', 'source': 'test',
                'created_at': datetime(2026, 9, 27, 12, 0)
            }
            system = MySQLQASystem()
            result = system.process_query('钻石')
            self.assertEqual(result['source'], 'mysql')
            self.assertEqual(result['data']['results'][0]['created_at'], '2026-09-27T12:00:00')
            self.assertTrue(redis_type.return_value.set.called)

    def test_mysql_search_filters_nonempty_query(self):
        client = MySQLClient.__new__(MySQLClient)
        client.connection = MagicMock()
        cursor = client.connection.cursor.return_value.__enter__.return_value
        cursor.fetchall.return_value = []
        client.search_knowledge('钻石', limit=5)
        sql, params = cursor.execute.call_args.args
        self.assertIn('title LIKE %s OR content LIKE %s', sql)
        self.assertEqual(params, ['%钻石%', '%钻石%', 5])


class MilvusStartupTests(unittest.TestCase):
    def test_uses_configured_database_and_collection_without_loading_model(self):
        with patch("src.data_processing.vector_indexing_milvusclient_full.MilvusClient") as client_type, \
             patch("src.data_processing.vector_indexing_milvusclient_full.BGEM3EmbeddingFunction") as model_type, \
             patch("src.data_processing.vector_indexing_milvusclient_full.Config") as config_type:
            config_type.return_value.get_milvus_config.return_value = {
                "host": "localhost", "port": 19530,
                "database_name": "mcrag", "collection_name": "mc_123"
            }
            builder = VectorIndexBuilder()
            self.assertEqual(builder.collection_name, "mc_123")
            model_type.assert_not_called()
            self.assertTrue(builder.connect_to_milvus())
            client_type.assert_called_once_with(uri="http://localhost:19530", db_name="mcrag")
            model_type.assert_not_called()

    def test_index_records_keep_source_content(self):
        builder = VectorIndexBuilder()
        data = builder.prepare_embeddings_data()
        self.assertTrue(data['texts'])
        self.assertEqual(
            [record['content'] for record in data['metadata']], data['texts']
        )

    def test_existing_collection_is_not_dropped(self):
        builder = VectorIndexBuilder()
        builder.client = Mock()
        builder.client.has_collection.return_value = True
        with self.assertRaisesRegex(RuntimeError, "拒绝覆盖"):
            builder.create_collection()
        builder.client.drop_collection.assert_not_called()


class AnswerTests(unittest.TestCase):
    def test_crafting_answer_uses_structured_recipe(self):
        context = ResponseContext(
            query="钻石镐怎么制作", evidence_list=[], core_evidence=[],
            quality_analysis={}, stats={}
        )
        answer = IntegratedQASystem.__new__(IntegratedQASystem)._generate_evidence_answer(context)
        self.assertIn("3 个钻石", answer)
        self.assertIn("2 个木棍", answer)
        self.assertIn("data/raw/recipes.json", answer)

    def test_unrelated_partial_title_does_not_answer(self):
        context = ResponseContext(
            query="钻石镐怎么制作", evidence_list=[],
            core_evidence=[{
                "title": "钻石", "content": "钻石可以开采获得",
                "retrieval_method": "bm25", "source": "bm25", "metadata": {}
            }], quality_analysis={}, stats={}
        )
        with patch.object(IntegratedQASystem, "_recipe_answer", return_value=None):
            answer = IntegratedQASystem.__new__(IntegratedQASystem)._generate_evidence_answer(context)
        self.assertIn("证据不足", answer)

    def test_drop_answer_uses_graph_relation(self):
        graph_evidence = {
            "title": "苦力怕 DROPS 火药", "content": "A creeper can drop gunpowder when killed.",
            "retrieval_method": "graph", "source": "data/raw/relations.json",
            "metadata": {"predicate": "DROPS"}
        }
        context = ResponseContext(
            query="苦力怕掉落什么", evidence_list=[graph_evidence],
            core_evidence=[], quality_analysis={}, stats={}
        )
        answer = IntegratedQASystem.__new__(IntegratedQASystem)._generate_evidence_answer(context)
        self.assertIn("可能掉落火药", answer)
        self.assertIn("data/raw/relations.json", answer)


class EvidenceTests(unittest.TestCase):
    def test_graph_retrieval_uses_real_relations(self):
        retrieval = RetrievalSystem.__new__(RetrievalSystem)
        retrieval.config = RetrievalConfig(graph_top_k=4)
        evidence = retrieval.retrieve_graph("苦力怕掉落什么")
        self.assertEqual(len(evidence), 1)
        self.assertIn("gunpowder", evidence[0].content)
        self.assertEqual(evidence[0].source, "data/raw/relations.json")
        self.assertEqual(retrieval.retrieve_graph("不存在的东西"), [])

    def test_rrf_score_is_not_reported_as_relevance_quality(self):
        fusion = EvidenceFusion()
        evidence = Evidence(
            id="1", title="苦力怕", content="evidence", content_type="fact",
            score=0.0049, source="graph", metadata={}, retrieval_method="graph"
        )
        analysis = fusion.evidence_quality_analysis([evidence], scores_are_rrf=True)
        self.assertEqual(analysis['quality_level'], 'unassessed')
        self.assertEqual(analysis['score_kind'], 'rrf')

    def test_fusion_keeps_one_real_graph_candidate(self):
        fusion = EvidenceFusion()
        def evidence(prefix, position, method):
            return Evidence(
                id=f"{prefix}_{position}", title=f"{prefix} {position}",
                content="verified", content_type="fact", score=1.0,
                source=method, metadata={}, retrieval_method=method
            )
        result = fusion.fusion_evidence(
            bm25_evidence=[evidence("b", i, "bm25") for i in range(10)],
            milvus_evidence=[evidence("m", i, "milvus") for i in range(10)],
            graph_evidence=[evidence("g", 1, "graph")], max_evidence=10
        )
        self.assertEqual(len(result.evidence_list), 10)
        self.assertIn("graph", [e.retrieval_method for e in result.evidence_list])


if __name__ == "__main__":
    unittest.main()
