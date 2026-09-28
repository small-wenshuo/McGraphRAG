import pymysql
import json
from typing import List, Dict, Any, Optional
from base.config import Config


class MySQLClient:
    def __init__(self):
        config = Config()
        db_config = config.get_database_config()

        self.connection = pymysql.connect(
            host=db_config['host'],
            port=db_config['port'],
            user=db_config['username'],
            password=db_config['password'],
            database=db_config['database_name'],
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )

        print("MySQL连接成功")
        self.create_tables()

    def create_tables(self):
        """
        创建必要的表
        """
        try:
            with self.connection.cursor() as cursor:
                # 创建知识库表
                create_knowledge_table = """
                CREATE TABLE IF NOT EXISTS knowledge_base (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    title VARCHAR(500) NOT NULL,
                    content TEXT NOT NULL,
                    category VARCHAR(100) DEFAULT 'general',
                    source VARCHAR(100) DEFAULT 'unknown',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT TRUE,
                    INDEX idx_title (title(50)),
                    INDEX idx_category (category),
                    INDEX idx_created_at (created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
                cursor.execute(create_knowledge_table)

                # 创建查询统计表
                create_stats_table = """
                CREATE TABLE IF NOT EXISTS query_stats (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    query_text VARCHAR(500) NOT NULL,
                    category VARCHAR(100),
                    is_cached BOOLEAN DEFAULT FALSE,
                    response_time FLOAT DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_query_text (query_text(50)),
                    INDEX idx_created_at (created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
                cursor.execute(create_stats_table)

            self.connection.commit()
            print("表创建成功")

        except Exception as e:
            print(f"创建表失败: {e}")
            self.connection.rollback()

    def insert_knowledge_data(self, title: str, content: str, category: str = 'general', source: str = 'manual') -> bool:
        """
        插入知识数据
        Args:
            title: 标题
            content: 内容
            category: 分类
            source: 来源
        Returns:
            bool: 是否插入成功
        """
        try:
            with self.connection.cursor() as cursor:
                sql = """
                INSERT INTO knowledge_base (title, content, category, source)
                VALUES (%s, %s, %s, %s)
                """
                cursor.execute(sql, (title, content, category, source))
            self.connection.commit()
            return True
        except Exception as e:
            print(f"插入知识数据失败: {e}")
            self.connection.rollback()
            return False

    def batch_insert_knowledge(self, data: List[Dict[str, Any]]) -> int:
        """
        批量插入知识数据
        Args:
            data: 知识数据列表，每个元素是包含title和content的字典
        Returns:
            int: 插入的记录数
        """
        try:
            with self.connection.cursor() as cursor:
                sql = """
                INSERT INTO knowledge_base (title, content, category, source)
                VALUES (%s, %s, %s, %s)
                """
                # 准备数据
                values = []
                for item in data:
                    category = item.get('metadata', {}).get('category', 'general')
                    source = item.get('metadata', {}).get('source', 'manual')
                    values.append((
                        item.get('title', ''),
                        item.get('content', ''),
                        category,
                        source
                    ))

                # 批量插入
                cursor.executemany(sql, values)
            self.connection.commit()
            return cursor.rowcount
        except Exception as e:
            print(f"批量插入知识数据失败: {e}")
            self.connection.rollback()
            return 0

    def search_knowledge(self, query: str, category: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """
        搜索知识
        Args:
            query: 查询字符串
            category: 分类筛选，可选
            limit: 返回结果数量限制
        Returns:
            List[Dict]: 搜索结果
        """
        try:
            with self.connection.cursor() as cursor:
                base_sql = """
                SELECT id, title, content, category, source, created_at
                FROM knowledge_base
                WHERE is_active = TRUE
                """

                params = []
                if query.strip():
                    pattern = f"%{query.strip()}%"
                    base_sql += " AND (title LIKE %s OR content LIKE %s)"
                    params.extend([pattern, pattern])
                if category:
                    base_sql += " AND category = %s"
                    params.append(category)

                base_sql += " ORDER BY created_at DESC LIMIT %s"
                params.append(limit)

                cursor.execute(base_sql, params)
                return cursor.fetchall()
        except Exception as e:
            print(f"搜索知识失败: {e}")
            return []

    def get_by_id(self, id: int) -> Optional[Dict[str, Any]]:
        """
        根据ID获取知识
        Args:
            id: 知识ID
        Returns:
            Dict: 知识详情
        """
        try:
            with self.connection.cursor() as cursor:
                sql = """
                SELECT id, title, content, category, source, created_at, updated_at
                FROM knowledge_base
                WHERE id = %s AND is_active = TRUE
                """
                cursor.execute(sql, (id,))
                result = cursor.fetchone()
                return result
        except Exception as e:
            print(f"根据ID获取知识失败: {e}")
            return None

    def query_question_answer(self, question: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        查询问题与答案
        Args:
            question: 问题
            limit: 返回结果数量
        Returns:
            List[Dict]: 匹配的结果
        """
        try:
            with self.connection.cursor() as cursor:
                sql = """
                SELECT id, title, content, category, created_at
                FROM knowledge_base
                WHERE
                    is_active = TRUE
                    AND (
                        title LIKE %s
                        OR content LIKE %s
                    )
                ORDER BY
                    CASE
                        WHEN title LIKE %s THEN 1
                        ELSE 2
                    END,
                    created_at DESC
                LIMIT %s
                """

                question_pattern = f"%{question}%"
                title_pattern = f"%{question}%"

                cursor.execute(sql, (question_pattern, question_pattern, title_pattern, limit))
                return cursor.fetchall()
        except Exception as e:
            print(f"查询问题答案失败: {e}")
            return []

    def record_query(self, query_text: str, category: str, is_cached: bool, response_time: float = 0) -> bool:
        """
        记录查询统计
        Args:
            query_text: 查询文本
            category: 分类
            is_cached: 是否命中缓存
            response_time: 响应时间（秒）
        Returns:
            bool: 是否记录成功
        """
        try:
            with self.connection.cursor() as cursor:
                sql = """
                INSERT INTO query_stats (query_text, category, is_cached, response_time)
                VALUES (%s, %s, %s, %s)
                """
                cursor.execute(sql, (query_text, category, is_cached, response_time))
            self.connection.commit()
            return True
        except Exception as e:
            print(f"记录查询统计失败: {e}")
            return False

    def get_query_stats(self, hours: int = 24) -> Dict[str, Any]:
        """
        获取查询统计
        Args:
            hours: 统计最近多少小时的数据
        Returns:
            Dict: 统计结果
        """
        try:
            with self.connection.cursor() as cursor:
                sql = """
                SELECT
                    COUNT(*) as total_queries,
                    SUM(is_cached) as cached_queries,
                    AVG(response_time) as avg_response_time,
                    COUNT(DISTINCT query_text) as unique_queries
                FROM query_stats
                WHERE created_at >= DATE_SUB(NOW(), INTERVAL %s HOUR)
                """
                cursor.execute(sql, (hours,))
                result = cursor.fetchone()
                return result or {}
        except Exception as e:
            print(f"获取查询统计失败: {e}")
            return {}

    def get_popular_categories(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        获取热门分类
        Args:
            limit: 返回数量限制
        Returns:
            List[Dict]: 热门分类列表
        """
        try:
            with self.connection.cursor() as cursor:
                sql = """
                SELECT
                    category,
                    COUNT(*) as count
                FROM knowledge_base
                WHERE is_active = TRUE
                GROUP BY category
                ORDER BY count DESC
                LIMIT %s
                """
                cursor.execute(sql, (limit,))
                return cursor.fetchall()
        except Exception as e:
            print(f"获取热门分类失败: {e}")
            return []

    def update_knowledge(self, id: int, title: Optional[str] = None, content: Optional[str] = None) -> bool:
        """
        更新知识内容
        Args:
            id: 知识ID
            title: 新标题
            content: 新内容
        Returns:
            bool: 是否更新成功
        """
        try:
            with self.connection.cursor() as cursor:
                updates = []
                params = []

                if title:
                    updates.append("title = %s")
                    params.append(title)

                if content:
                    updates.append("content = %s")
                    params.append(content)

                if updates:
                    params.append(id)
                    sql = f"UPDATE knowledge_base SET {', '.join(updates)} WHERE id = %s"
                    cursor.execute(sql, params)
                    self.connection.commit()
                    return cursor.rowcount > 0
                return False
        except Exception as e:
            print(f"更新知识失败: {e}")
            return False

    def deactivate_knowledge(self, id: int) -> bool:
        """
        停用知识
        Args:
            id: 知识ID
        Returns:
            bool: 是否停用成功
        """
        try:
            with self.connection.cursor() as cursor:
                sql = "UPDATE knowledge_base SET is_active = FALSE WHERE id = %s"
                cursor.execute(sql, (id,))
                self.connection.commit()
                return cursor.rowcount > 0
        except Exception as e:
            print(f"停用知识失败: {e}")
            return False

    def close(self):
        """
        关闭数据库连接
        """
        try:
            self.connection.close()
            print("MySQL连接已关闭")
        except Exception as e:
            print(f"关闭MySQL连接失败: {e}")


if __name__ == "__main__":
    # 测试代码
    client = MySQLClient()

    # 读取mc_data.json
    try:
        with open("../../mc_data.json", "r", encoding="utf-8") as f:
            data = json.load(f)

        print(f"读取到 {len(data)} 条数据")

        # 批量插入数据
        inserted_count = client.batch_insert_knowledge(data)
        print(f"成功插入 {inserted_count} 条数据")

    except Exception as e:
        print(f"读取或插入数据失败: {e}")

    # 测试搜索
    results = client.search_knowledge("末地", limit=5)
    print(f"搜索 '末地' 找到 {len(results)} 条结果")

    client.close()
