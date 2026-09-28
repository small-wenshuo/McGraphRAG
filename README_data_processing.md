# Minecraft GraphRAG 数据处理模块

本模块实现了从原始数据到知识图谱和向量数据库的完整处理流程。

## 文件结构

```
src/
├── data_processing/
│   ├── text_cleaning.py      # 文本清洗和切块模块
│   ├── entity_extraction.py  # 实体抽取模块
│   ├── relation_extraction.py # 关系抽取模块
│   ├── knowledge_graph.py   # 知识图谱构建模块
│   └── vector_indexing.py    # 向量化索引模块
└── process_data.py          # 主处理脚本

tests/
└── test_data_processing.py   # 测试脚本

requirements.txt              # 依赖列表
```

## 使用方法

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 运行完整流程

```bash
python src/process_data.py
```

程序会提示选择操作：
- 输入1：只运行文本清洗和切块
- 输入2：只运行实体抽取
- 输入3：只运行关系抽取
- 输入4：只运行知识图谱构建
- 输入5：只运行向量索引构建
- 其他：运行所有步骤

### 3. 运行测试

```bash
python tests/test_data_processing.py
```

## 处理流程详解

### 步骤1：文本清洗与切块

**功能：**
- 去除噪声、导航、重复内容
- 按语义将文本切成 chunks
- 给每个 chunk 绑定来源、标题等元数据

**输入：**
- `data/raw/firecrawl/pages/` 目录下的 markdown 文件
- `data/raw/sources.json` 元数据文件

**输出：**
- `data/processed/cleaned_chunks.json` - 清洗后的 chunks

**特点：**
- 使用父子块切分策略
- 自动处理长段落
- 保留版本信息

### 步骤2：实体抽取

**功能：**
- 从 chunk 中识别实体（物品、生物、方块等）
- 实体标准化，统一别名和命名空间 ID
- 例如："苦力怕 / Creeper / creeper" 统一为同一个实体

**输入：**
- `data/processed/cleaned_chunks.json`

**输出：**
- `data/processed/extracted_entities.json` - 抽取的实体列表

**实体类型：**
- `item` - 物品
- `block` - 方块
- `mob` - 生物
- `biome` - 生物群系
- `structure` - 结构
- `recipe` - 配方
- `enchantment` - 附魔
- `potion` - 药水
- `command` - 命令
- `mechanic` - 机制

### 步骤3：关系抽取

**功能：**
- 抽取实体之间的关系
- 只保留原文明确表达的关系
- 同时保留证据句，方便追溯

**关系类型：**
- `crafted_from` - 合成自
- `drops` - 掉落物
- `spawns_in` - 生成于
- `used_for` - 用于
- `requires` - 需要
- `transforms_to` - 转变为
- `counters` - 克制
- `found_in` - 发现于
- `enabled_by_version` - 版本启用

**输入：**
- `data/processed/cleaned_chunks.json`
- `data/processed/extracted_entities.json`

**输出：**
- `data/processed/extracted_relations.json` - 抽取的关系列表

### 步骤4：图谱建模

**功能：**
- 把实体建成节点，关系建成边
- 节点和边都带有来源、版本、置信度、证据
- 导出为 JSON 格式和 Neo4j Cypher 脚本

**输入：**
- `data/processed/extracted_entities.json`
- `data/processed/extracted_relations.json`

**输出：**
- `data/processed/knowledge_graph.json` - 完整图谱
- `data/processed/graph_nodes.json` - 节点数据
- `data/processed/graph_edges.json` - 边数据
- `data/processed/neo4j_import.cypher` - Neo4j 导入脚本

### 步骤5：向量化索引

**功能：**
- 使用 BGE-M3 模型生成 embedding
- 写入 Milvus 向量数据库
- 支持后续语义召回

**输入：**
- `data/processed/cleaned_chunks.json`
- `data/processed/extracted_entities.json`
- `data/processed/extracted_relations.json`

**输出：**
- `data/processed/vector_config.json` - 向量配置
- Milvus 数据库中的向量数据

## 数据格式说明

### Chunk 格式
```json
{
  "chunk_id": "minecraft-wiki-creeper_0",
  "content": "苦力怕是一种危险的生物...",
  "source_id": "minecraft-wiki-creeper",
  "title": "苦力怕",
  "metadata": {
    "source_id": "minecraft-wiki-creeper",
    "title": "苦力怕",
    "version": "1.21.x",
    "edition": "java",
    "chunk_type": "paragraph"
  }
}
```

### 实体格式
```json
{
  "id": "minecraft:creeper",
  "name": "苦力怕",
  "type": "mob",
  "aliases": ["爬行者", "creeper"],
  "position": [0, 100],
  "confidence": 0.95,
  "evidence_text": "苦力怕是一种危险的生物..."
}
```

### 关系格式
```json
{
  "relation_type": "drops",
  "subject_id": "minecraft:creeper",
  "subject_name": "苦力怕",
  "object_id": "minecraft:gunpowder",
  "object_name": "火药",
  "evidence_text": "苦力怕掉落火药",
  "confidence": 0.98,
  "source_chunk_id": "minecraft-wiki-creeper_0"
}
```

### 图谱节点格式
```json
{
  "id": "minecraft:creeper",
  "type": "mob",
  "name_zh": "苦力怕",
  "name_en": "Creeper",
  "aliases": ["爬行者", "creeper"],
  "properties": {"hostile": true},
  "node_type": "entity",
  "sources": ["https://minecraft.wiki/w/Creeper"],
  "version": "1.0"
}
```

### 图谱边格式
```json
{
  "id": "edge_0",
  "source_id": "minecraft:creeper",
  "target_id": "minecraft:gunpowder",
  "relation_type": "drops",
  "evidence_text": "苦力怕掉落火药",
  "confidence": 0.98,
  "edge_type": "relation",
  "minecraft_version": "1.21.x"
}
```

## 配置说明

### Milvus 配置
- 默认连接地址：localhost:19530
- 集合名称：minecraft_knowledge
- 向量维度：1024（BGE-M3）
- 距离度量：内积（IP）

### BGE-M3 配置
- 模型：BAAI/bge-m3
- 向量维度：1024
- 批处理大小：32

## 注意事项

1. **版本控制**：所有知识都带版本标签，避免不同版本混在一起
2. **证据保留**：每个关系都保留证据句，支持溯源
3. **置信度**：实体和关系都有置信度评分
4. **去重处理**：自动处理重复的实体和关系
5. **错误处理**：各模块都有完善的错误处理机制

## 扩展建议

1. **自定义实体类型**：在 `entity_extraction.py` 中添加新的实体类型
2. **自定义关系类型**：在 `relation_extraction.py` 中添加新的关系抽取模式
3. **自定义清洗规则**：在 `text_cleaning.py` 中添加新的噪声模式
4. **自定义嵌入模型**：在 `vector_indexing.py` 中更换不同的 embedding 模型
5. **集成其他数据库**：支持 Neo4j、Elasticsearch 等其他数据库