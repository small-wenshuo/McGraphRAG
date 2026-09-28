# MySQL 快速问答系统

这是 Minecraft GraphRAG 项目中的 MySQL 快速问答模块，实现了基于 Redis + MySQL 的快速问答通道。

## 架构设计

系统采用多通道架构：
- **快速通道**：Redis + MySQL（适用于常见问题、标准答案）
- **RAG通道**：Milvus + 知识图谱 + BM25（适用于复杂、多跳问题）

## 核心组件

### 1. Redis 客户端 (`cache/redis_client.py`)
- 功能：缓存热点答案，提高查询速度
- 主要方法：
  - `set(key, value, expire)`: 设置键值对
  - `get(key)`: 获取键值
  - `delete(key)`: 删除键
  - `exists(key)`: 检查键是否存在
  - 支持复杂对象的序列化和反序列化

### 2. MySQL 客户端 (`db/mysql_client.py`)
- 功能：管理标准问答库
- 数据表：
  - `knowledge_base`: 存储知识条目（id, title, content, category, source等）
  - `query_stats`: 记录查询统计信息
- 主要方法：
  - `insert_knowledge_data()`: 插入知识条目
  - `batch_insert_knowledge()`: 批量插入
  - `search_knowledge()`: 搜索知识
  - `query_question_answer()`: 查询问题答案
  - `record_query()`: 记录查询统计

### 3. BM25 搜索引擎 (`retrieval/bm25_search.py`)
- 功能：实现 BM25+softmax 算法，决定问题路由
- 主要特性：
  - 支持中文分词（jieba）
  - BM25 算法实现
  - Softmax 分数归一化
  - 决策阈值配置
- 主要方法：
  - `build_index()`: 构建索引
  - `search()`: 搜索文档
  - `should_use_rag()`: 判断是否使用RAG系统

### 4. 预处理工具 (`utils/preprocess.py`)
- 功能：文本预处理和分词
- 主要方法：
  - `clean_text()`: 清洗文本
  - `tokenize()`: 分词
  - `normalize()`: 规范化（小写等）
  - `get_keywords()`: 提取关键词
  - `preprocess_query()`: 查询预处理

### 5. 主程序 (`main.py`)
- 功能：整合所有组件，提供统一接口
- `MySQLQASystem` 类：
  - `process_query()`: 处理用户查询
  - `add_knowledge()`: 添加新知识
  - `get_system_stats()`: 获取系统统计

## 工作流程

### 1. 系统初始化
```
1. 创建各组件实例
2. 尝试从文件加载BM25索引
3. 如果索引不存在，从MySQL加载文档构建索引
```

### 2. 查询处理流程
```
1. 用户输入查询
2. 检查Redis缓存
   - 命中：直接返回缓存结果
   - 未命中：继续下一步
3. 预处理查询
4. 使用BM25评分决定路由
   - 高分（>阈值）：走MySQL通道
   - 低分（≤阈值）：建议走RAG通道
5. 如果走MySQL通道：
   - 搜索MySQL数据库
   - 缓存结果到Redis
   - 返回搜索结果
6. 记录查询统计
```

## 配置文件

系统使用 `config.ini` 进行配置。首次运行时复制项目根目录的 `config.example.ini`，再填写本机密码；真实配置不会提交到 Git。

```ini
[database]
host = localhost
port = 3306
username = root
password =
database_name = mcgraphrag

[cache]
redis_host = localhost
redis_port = 6379
redis_db = 0
password =

[search]
bm25_top_k = 10
search_threshold = 0.5
```

## 使用示例

### 1. 导入数据
```bash
cd mysql_qa
python import_data.py
```

### 2. 运行系统
```bash
python main.py
```

### 3. 代码中使用
```python
from main import MySQLQASystem

# 创建系统实例
qa_system = MySQLQASystem()

# 处理查询
result = qa_system.process_query("末地怎么去")
print(result)

# 添加知识
qa_system.add_knowledge(
    title="新知识",
    content="这是新知识的描述",
    category="general"
)

# 获取统计
stats = qa_system.get_system_stats()
print(stats)

# 关闭系统
qa_system.close()
```

## 性能优化

1. **Redis缓存**：缓存热点查询结果，减少数据库访问
2. **BM25索引**：预先构建索引，提高检索速度
3. **批量操作**：支持批量插入数据
4. **索引持久化**：BM25索引保存到文件，避免重复构建

## 扩展性

1. **添加新知识源**：通过 `add_knowledge()` 方法
2. **自定义预处理**：继承 `Preprocessor` 类
3. **调整BM25参数**：修改 `k1` 和 `b` 参数
4. **修改决策阈值**：调整 `search_threshold`

## 注意事项

1. 确保 MySQL 和 Redis 服务已启动
2. 检查配置文件中的连接信息
3. 首次运行时需要导入数据
4. 大数据量时注意内存使用
