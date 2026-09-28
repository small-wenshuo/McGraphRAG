import redis
import json
from base.config import Config
from base import logger

class RedisClient:
    def __init__(self):
        self.logger = logger
        self.client = None
        config = Config().get_cache_config()
        try:
            client = redis.StrictRedis(
                host=config['redis_host'],
                port=config['redis_port'],
                db=config['redis_db'],
                password=config['password'],
                decode_responses=True,
                socket_connect_timeout=1,
                socket_timeout=1,
            )
            if not client.ping():
                raise redis.ConnectionError('PING 未成功')
            self.client = client
            self.logger.info('Redis连接成功 (%s:%s).', config['redis_host'], config['redis_port'])
        except redis.RedisError as e:
            self.logger.warning('Redis不可用，缓存已禁用 (%s:%s): %s',
                                config['redis_host'], config['redis_port'], e)
    def set_data(self,key,value):
        if self.client is None:
            return False
        try:
            saved = self.client.set(key,json.dumps(value,ensure_ascii=False))
            if saved:
                self.logger.info(f'{key}写入成功.')
            return bool(saved)
        except redis.RedisError as e:
            self.logger.error(e)
            return False

    def set(self, key, value, expire=None):
        if self.client is None:
            return False
        try:
            return bool(self.client.set(key, json.dumps(value, ensure_ascii=False), ex=expire))
        except redis.RedisError as e:
            self.logger.error(e)
            return False

    def get(self, key):
        return self.get_data(key)

    def is_connected(self):
        if self.client is None:
            return False
        try:
            return bool(self.client.ping())
        except redis.RedisError:
            return False

    def close(self):
        if self.client is not None:
            self.client.close()
            self.client = None
    def get_data(self,key):
        if self.client is None:
            return None
        try:
            value = self.client.get(key)
            if value:
                value = json.loads(value)
                self.logger.info(f'{key}读取成功.')
            return value
        except redis.RedisError as e:
            self.logger.error(e)
    def get_answer(self,query):
        if self.client is None:
            return None
        try:
            answer = self.client.get(f"answer:{query}")
            if answer:
                self.logger.info(f'{query}读取成功.')
                return answer
        except redis.RedisError as e:
            self.logger.error(e)
    def get_keys(self):
        if self.client is None:
            return []
        try:
            return self.client.keys("*")
        except redis.RedisError as e:
            self.logger.error(e)
            return []
if __name__ == '__main__':
    redis_client = RedisClient()
    redis_client.set_data('name','小王')
    # print(redis_client.get_keys())
