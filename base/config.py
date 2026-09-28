import configparser
import os
from pathlib import Path
from dotenv import load_dotenv


class Config():
    def __init__(self, config_file='config.ini'):
        self.config = configparser.ConfigParser()
        config_path = Path(__file__).parent.parent / config_file
        self.config.read(config_path)
        load_dotenv(config_path.parent / '.env', override=False)
        self.LOG_FILE = 'logs.app.log'

    def get_llm_config(self):
        """阿里云百炼 OpenAI 兼容接口配置。系统环境变量优先于 .env。"""
        settings = {
            'base_url': os.getenv('DASHSCOPE_BASE_URL', '').strip(),
            'model_name': os.getenv('DASHSCOPE_MODEL_NAME', '').strip(),
            'api_key': os.getenv('DASHSCOPE_API_KEY', '').strip(),
        }
        if settings['api_key'] and not (settings['base_url'] and settings['model_name']):
            raise ValueError('配置 DASHSCOPE_API_KEY 时，也必须配置 DASHSCOPE_BASE_URL 和 DASHSCOPE_MODEL_NAME')
        return settings

    def get_database_config(self):
        return {
            'host': self.config['database']['host'],
            'port': int(self.config['database']['port']),
            'username': self.config['database']['username'],
            'password': self.config['database']['password'],
            'database_name': self.config['database']['database_name']
        }

    def get_cache_config(self):
        return {
            'redis_host': self.config['cache']['redis_host'],
            'redis_port': int(self.config['cache']['redis_port']),
            'redis_db': int(self.config['cache']['redis_db']),
            'password': self.config['cache']['password']
        }

    def get_rag_config(self):
        return {
            'model_name': self.get_llm_config()['model_name'],
            'embedding_model': self.config['rag']['embedding_model'],
            'chunk_size': int(self.config['rag']['chunk_size']),
            'chunk_overlap': int(self.config['rag']['chunk_overlap']),
            'top_k': int(self.config['rag']['top_k'])
        }

    def get_milvus_config(self):
        return {
            'host': self.config['milvus']['host'],
            'port': int(self.config['milvus']['port']),
            'database_name': self.config['milvus']['database_name'],
            'collection_name': self.config['milvus']['collection_name']
        }

    def get_search_config(self):
        return {
            'bm25_top_k': int(self.config['search']['bm25_top_k']),
            'search_threshold': float(self.config['search']['search_threshold'])
        }
print("Config file loaded successfully.")
