# RAG Core 模块说明

本目录包含RAG（检索增强生成）系统的核心组件。

## 文件说明

### 1. `llm_response_generator.py` - 大模型回答生成器
主要功能：
- 提供标准化的提示词模板
- 根据问题类型选择合适的回答模板
- 集成检索到的证据信息
- 生成高质量回答
- 支持版本信息处理
- 提供回答质量验证

### 2. `response_integration_example.py` - 回答生成器集成示例
主要功能：
- 展示如何将回答生成器与检索系统集成
- 提供完整的问答流程
- 支持批量处理
- 结果保存和统计分析

## 快速开始

### 1. 初始化回答生成器

```python
from llm_response_generator import LLMResponseGenerator

# 创建生成器实例
generator = LLMResponseGenerator()

# 准备回答上下文
context = ResponseContext(
    query="钻石镐怎么制作",
    evidence_list=[...],  # 检索到的证据列表
    core_evidence=[...],  # 核心证据
    quality_analysis={...},  # 质量分析
    stats={...},  # 统计信息
    game_version="1.20.1"  # 版本信息
)

# 生成提示词
prompt = generator.generate_response_prompt(context)

# 生成简洁回答
answer = generator.generate_simple_answer(context)
```

### 2. 使用集成系统

```python
from response_integration_example import QAIntegration

# 创建集成实例
qa_system = QAIntegration(
    bm25_index_path="data/processed/bm25_index.json",
    milvus_ready=True
)

# 处理单个查询
result = qa_system.process_query(
    query="钻石镐怎么制作",
    game_version="1.20.1",
    modpack_version="vanilla",
    server_version="paper"
)

# 处理批量查询
results = qa_system.batch_process_queries(
    queries=["怎么制作钻石镐", "苦力怕的特性"],
    game_version="1.20.1"
)

# 保存结果
qa_system.save_results(results, "results.json")
```

## 问题类型支持

系统自动识别以下问题类型：

1. **合成类问题**（crafting）
   - 关键词：合成、制作、配方、获得
   - 模板：`crafting_answer`

2. **生物行为类问题**（entity_behavior）
   - 关键词：苦力怕、僵尸、生物、掉落、行为
   - 模板：`entity_behavior`

3. **机制解释类问题**（mechanism）
   - 关键词：传送门、红石、指令、机制、系统
   - 模板：`mechanism_explanation`

4. **知识问答类问题**（knowledge）
   - 默认类型
   - 模板：`knowledge_answer`

## 版本控制

系统支持以下版本信息：
- `game_version`: 游戏版本
- `modpack_version`: 模组包版本
- `server_version`: 服务器版本

这些信息会被包含在回答中，确保答案的准确性。

## 质量验证

回答生成器会自动验证回答质量，评估维度包括：
- 内容完整性
- 证据相关性
- 回答长度
- 版本信息完整性

验证结果分为四个等级：
- `excellent`: 90-100分
- `good`: 70-89分
- `fair`: 50-69分
- `poor`: 0-49分

## 模板自定义

可以通过修改`_load_response_templates`方法来自定义回答模板：

```python
def _load_response_templates(self) -> Dict[str, str]:
    return {
        'your_custom_template': """你的自定义模板
{query}
{evidence}"""
    }
```

## 测试

运行测试函数：

```bash
python llm_response_generator.py
python response_integration_example.py
```

## 依赖

本模块依赖：
- `base.config`: 配置管理
- `retrieval_system`: 检索系统
- `evidence_fusion`: 证据融合

确保这些模块都已正确配置。