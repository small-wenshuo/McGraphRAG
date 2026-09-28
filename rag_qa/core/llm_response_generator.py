"""
大模型回答生成器
为Minecraft知识问答提供标准化的提示词和回答生成功能
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import json
from datetime import datetime
from base.config import Config
from base.logger import logger
from openai import OpenAI


@dataclass
class ResponseContext:
    """回答上下文"""
    query: str
    evidence_list: List[Dict[str, Any]]
    core_evidence: List[Dict[str, Any]]
    quality_analysis: Dict[str, Any]
    stats: Dict[str, Any]
    game_version: Optional[str] = None
    modpack_version: Optional[str] = None
    server_version: Optional[str] = None


class LLMResponseGenerator:
    """大模型回答生成器"""

    def __init__(self):
        """初始化回答生成器"""
        self.config = Config()
        self.rag_config = self.config.get_rag_config()
        self.llm_config = self.config.get_llm_config()
        self.client = (OpenAI(
            api_key=self.llm_config['api_key'],
            base_url=self.llm_config['base_url'],
            timeout=30,
            max_retries=0,
        ) if self.llm_config['api_key'] else None)
        self.response_templates = self._load_response_templates()

    def generate_answer(self, context: ResponseContext) -> Optional[str]:
        """有证据时调用百炼；失败时由调用方使用本地证据回答。"""
        if self.client is None or not context.evidence_list:
            return None
        try:
            completion = self.client.chat.completions.create(
                model=self.llm_config['model_name'],
                messages=[
                    {'role': 'system', 'content': '你是 Minecraft 知识助手。只能根据提供的证据回答；证据无关或不足时明确说证据不足，不得编造事实或来源。'},
                    {'role': 'user', 'content': self.generate_response_prompt(context)},
                ],
            )
            answer = completion.choices[0].message.content if completion.choices else None
            return answer.strip() if answer and answer.strip() else None
        except Exception as exc:
            logger.warning('百炼回答生成失败：%s', type(exc).__name__)
            return None

    def _load_response_templates(self) -> Dict[str, str]:
        """加载回答模板"""
        return {
            'knowledge_answer': """你是一个专业的Minecraft知识助手。请基于提供的证据信息，准确、完整地回答用户的问题。

问题：{query}

关键证据：
{core_evidence}

辅助证据：
{auxiliary_evidence}

回答要求：
1. 基于提供的证据回答，不要编造信息
2. 如果证据不足，明确说明信息不足
3. 提供具体的操作步骤或数值
4. 涉及版本差异时，要明确说明适用版本
5. 如果需要多个步骤，请分点说明
6. 回答要简洁明了，避免冗余

版本信息：
- 游戏版本：{game_version}
- 模组包版本：{modpack_version}
- 服务器版本：{server_version}

请生成准确的回答：""",

            'crafting_answer': """Minecraft合成配方助手

问题：{query}

合成配方信息：
{crafting_evidence}

其他相关信息：
{auxiliary_evidence}

回答要求：
1. 列出完整的合成材料
2. 说明合成步骤
3. 如果有多种合成方式，请全部列出
4. 标注适用版本
5. 如果需要特殊条件（如工作台、锻造台等），请说明

版本信息：{version_info}

请提供详细的合成指导：""",

            'entity_behavior': """Minecraft生物行为分析助手

问题：{query}

行为特征信息：
{behavior_evidence}

其他相关特性：
{auxiliary_evidence}

回答要求：
1. 描述生物的基本行为特征
2. 说明生成条件
3. 描述掉落物信息
4. 说明特殊行为机制
5. 标注适用版本

版本信息：{version_info}

请提供详细的生物行为分析：""",

            'mechanism_explanation': """Minecraft机制解释专家

问题：{query}

机制相关信息：
{mechanism_evidence}

相关背景知识：
{auxiliary_evidence}

回答要求：
1. 解释机制的原理
2. 说明触发条件
3. 描述运行效果
4. 列出相关影响因素
5. 如果涉及版本差异，请分别说明

版本信息：{version_info}

请提供清晰的机制解释：""",

            'insufficient_info': """信息不足提示

问题：{query}

检索到的证据：{evidence_summary}

抱歉，根据现有的知识库无法回答这个问题。可能的原因：
1. 相关信息还未收录到知识库中
2. 问题过于模糊，需要更具体的描述
3. 涉及到非常新的游戏版本或模组

建议：
1. 尝试使用更具体的描述
2. 确认游戏版本信息
3. 稍后再次查询，知识库会持续更新

您也可以尝试重新表述您的问题。"""
        }

    def _format_evidence_text(self, evidence_list: List[Dict[str, Any]], max_items: int = 5) -> str:
        """格式化证据文本"""
        if not evidence_list:
            return "未找到相关信息"

        formatted = []
        for i, evidence in enumerate(evidence_list[:max_items], 1):
            title = evidence.get('title', '无标题')
            content = evidence.get('content', '无内容')
            score = evidence.get('score', 0)
            source = evidence.get('source', 'unknown')

            formatted.append(f"""
{i}. 【{source}】【{title}】
   内容：{content}
   相关度：{score:.2f}
   来源：{evidence.get('metadata', {}).get('source', 'unknown')}
""")

        return ''.join(formatted)

    def _determine_question_type(self, query: str) -> str:
        """判断问题类型"""
        query_lower = query.lower()

        # 合成类问题关键词
        crafting_keywords = ['合成', '制作', '怎么制作', '配方', '怎么获得', '如何获得']
        if any(keyword in query_lower for keyword in crafting_keywords):
            return 'crafting'

        # 生物行为类问题关键词
        entity_keywords = ['苦力怕', '僵尸', '骷髅', '蜘蛛', '僵尸猪人', '末影人',
                         '生物', '怪物', '掉落', '行为', '特性', '生成']
        if any(keyword in query_lower for keyword in entity_keywords):
            return 'entity_behavior'

        # 机制类问题关键词
        mechanism_keywords = ['传送门', '红石', '指令', '命令', '机制', '系统',
                            '功能', '如何', '怎么', '原理']
        if any(keyword in query_lower for keyword in mechanism_keywords):
            return 'mechanism'

        # 默认为知识问答
        return 'knowledge'

    def _select_template(self, question_type: str) -> str:
        """选择合适的模板"""
        template_map = {
            'knowledge': 'knowledge_answer',
            'crafting': 'crafting_answer',
            'entity_behavior': 'entity_behavior',
            'mechanism': 'mechanism_explanation'
        }
        return template_map.get(question_type, 'knowledge_answer')

    def _format_version_info(self, context: ResponseContext) -> str:
        """格式化版本信息"""
        version_parts = []
        if context.game_version:
            version_parts.append(f"游戏版本: {context.game_version}")
        if context.modpack_version:
            version_parts.append(f"模组包版本: {context.modpack_version}")
        if context.server_version:
            version_parts.append(f"服务器版本: {context.server_version}")

        return " | ".join(version_parts) if version_parts else "版本信息: 未指定"

    def generate_response_prompt(self, context: ResponseContext) -> str:
        """
        生成回答提示词

        Args:
            context: 回答上下文

        Returns:
            格式化的提示词
        """
        # 确定问题类型
        question_type = self._determine_question_type(context.query)
        template_key = self._select_template(question_type)
        template = self.response_templates[template_key]

        # 格式化证据
        core_evidence_text = self._format_evidence_text(context.core_evidence)
        auxiliary_evidence_text = self._format_evidence_text(
            [e for e in context.evidence_list if e not in context.core_evidence]
        )

        # 准备模板变量
        template_vars = {
            'query': context.query,
            'core_evidence': core_evidence_text,
            'auxiliary_evidence': auxiliary_evidence_text,
            'crafting_evidence': core_evidence_text,  # 合成问题使用核心证据
            'behavior_evidence': core_evidence_text,  # 行为问题使用核心证据
            'mechanism_evidence': core_evidence_text,  # 机制问题使用核心证据
            'evidence_summary': f"共找到{len(context.evidence_list)}条相关信息",
            'version_info': self._format_version_info(context),
            'game_version': context.game_version or '未指定',
            'modpack_version': context.modpack_version or '未指定',
            'server_version': context.server_version or '未指定'
        }

        # 如果证据不足，使用专门的模板
        if len(context.evidence_list) == 0:
            template = self.response_templates['insufficient_info']

        # 填充模板
        prompt = template.format(**template_vars)

        # 添加元数据信息
        metadata = f"""
---
生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
问题类型: {question_type}
证据数量: {len(context.evidence_list)}
核心证据数: {len(context.core_evidence)}
质量等级: {context.quality_analysis.get('quality_level', 'unknown')}
---
"""

        return metadata + prompt

    def generate_simple_answer(self, context: ResponseContext, max_length: int = 1000) -> str:
        """
        生成简洁回答（当证据充足时）

        Args:
            context: 回答上下文
            max_length: 最大回答长度

        Returns:
            简洁的回答文本
        """
        if len(context.evidence_list) == 0:
            return "抱歉，我没有找到相关的信息来回答这个问题。"

        # 提取最相关的证据
        top_evidence = sorted(context.evidence_list, key=lambda x: x.get('score', 0), reverse=True)[:3]

        # 根据问题类型生成不同风格的回答
        question_type = self._determine_question_type(context.query)

        if question_type == 'crafting':
            answer = self._generate_crafting_answer(top_evidence)
        elif question_type == 'entity_behavior':
            answer = self._generate_entity_answer(top_evidence)
        elif question_type == 'mechanism':
            answer = self._generate_mechanism_answer(top_evidence)
        else:
            answer = self._generate_knowledge_answer(top_evidence)

        # 确保回答长度不超过限制
        if len(answer) > max_length:
            answer = answer[:max_length-3] + "..."

        return answer

    def _generate_crafting_answer(self, evidence: List[Dict[str, Any]]) -> str:
        """生成合成类回答"""
        if not evidence:
            return "暂无合成配方信息。"

        # 提取第一个证据作为主要信息
        main_evidence = evidence[0]
        content = main_evidence.get('content', '')

        # 查找合成材料
        materials = []
        materials_start = content.find('材料：') if '材料：' in content else content.find('需要：')
        if materials_start != -1:
            materials_text = content[materials_start+3:].split('\n')[0]
            materials = [m.strip() for m in materials_text.split('、')]

        # 查找合成步骤
        steps = []
        steps_start = content.find('步骤：') if '步骤：' in content else content.find('制作：')
        if steps_start != -1:
            steps_text = content[steps_start+3:].split('\n')[0]
            steps = [s.strip() for s in steps_text.split('→')]

        answer_parts = []
        if materials:
            answer_parts.append(f"🔨 合成材料：{', '.join(materials)}")
        if steps:
            answer_parts.append(f"📝 合成步骤：{' → '.join(steps)}")

        return "\n".join(answer_parts) if answer_parts else content

    def _generate_entity_answer(self, evidence: List[Dict[str, Any]]) -> str:
        """生成生物行为类回答"""
        if not evidence:
            return "暂无生物相关信息。"

        # 提取主要信息
        main_evidence = evidence[0]
        content = main_evidence.get('content', '')

        # 提取关键信息
        info_parts = []

        # 生成条件
        spawn_keyword = '生成：' if '生成：' in content else '出现：'
        if spawn_keyword in content:
            spawn_info = content.split(spawn_keyword)[1].split('\n')[0]
            info_parts.append(f"🌍 {spawn_keyword}{spawn_info}")

        # 掉落物
        drops_keyword = '掉落：' if '掉落：' in content else '掉落物：'
        if drops_keyword in content:
            drops_info = content.split(drops_keyword)[1].split('\n')[0]
            info_parts.append(f"💎 {drops_keyword}{drops_info}")

        # 行为特征
        behavior_keyword = '行为：' if '行为：' in content else '特性：'
        if behavior_keyword in content:
            behavior_info = content.split(behavior_keyword)[1].split('\n')[0]
            info_parts.append(f"👀 {behavior_keyword}{behavior_info}")

        return "\n".join(info_parts) if info_parts else content

    def _generate_mechanism_answer(self, evidence: List[Dict[str, Any]]) -> str:
        """生成机制解释类回答"""
        if not evidence:
            return "暂无机制相关信息。"

        main_evidence = evidence[0]
        content = main_evidence.get('content', '')

        # 简化处理，返回主要内容
        return f"📖 {content[:200]}{'...' if len(content) > 200 else ''}"

    def _generate_knowledge_answer(self, evidence: List[Dict[str, Any]]) -> str:
        """生成知识问答类回答"""
        if not evidence:
            return "暂无相关信息。"

        # 提取主要内容
        main_evidence = evidence[0]
        content = main_evidence.get('content', '')

        # 简化处理，返回主要内容
        return f"💡 {content[:200]}{'...' if len(content) > 200 else ''}"

    def validate_response(self, response: str, context: ResponseContext) -> Dict[str, Any]:
        """
        验证回答质量

        Args:
            response: 生成的回答
            context: 回答上下文

        Returns:
            验证结果
        """
        validation_result = {
            'has_content': len(response.strip()) > 0,
            'has_evidence_reference': len(context.evidence_list) > 0,
            'length_appropriate': 50 <= len(response) <= 2000,
            'contains_version_info': context.game_version is not None,
            'quality_score': 0
        }

        # 计算质量分数
        score = 0
        if validation_result['has_content']:
            score += 30
        if validation_result['has_evidence_reference']:
            score += 40
        if validation_result['length_appropriate']:
            score += 20
        if validation_result['contains_version_info']:
            score += 10

        validation_result['quality_score'] = score

        # 质量等级
        if score >= 90:
            validation_result['quality_level'] = 'excellent'
        elif score >= 70:
            validation_result['quality_level'] = 'good'
        elif score >= 50:
            validation_result['quality_level'] = 'fair'
        else:
            validation_result['quality_level'] = 'poor'

        return validation_result


# 测试函数
def test_response_generator():
    """测试回答生成器"""
    print("=== 测试大模型回答生成器 ===")

    # 创建生成器实例
    generator = LLMResponseGenerator()

    # 创建测试上下文
    context = ResponseContext(
        query="钻石镐怎么制作",
        evidence_list=[
            {
                'id': '1',
                'title': '钻石镐合成配方',
                'content': '材料：3个钻石 + 2个木棍。步骤：在工作台按照口字型排列，钻石放在上中下，木棍放在左中和右中。',
                'score': 0.95,
                'source': 'crafting',
                'metadata': {'source': 'wiki'}
            },
            {
                'id': '2',
                'title': '钻石获取方法',
                'content': '钻石通常在地下16层以下被发现，需要铁镐才能挖掘。',
                'score': 0.80,
                'source': 'knowledge',
                'metadata': {'source': 'guide'}
            }
        ],
        core_evidence=[],
        quality_analysis={'quality_level': 'good'},
        stats={'total_time': 1.5},
        game_version='1.20.1'
    )

    # 生成提示词
    prompt = generator.generate_response_prompt(context)
    print("生成的提示词：")
    print("="*50)
    print(prompt[:1000])  # 只显示前1000个字符
    print("="*50)

    # 生成简洁回答
    simple_answer = generator.generate_simple_answer(context)
    print(f"\n简洁回答：{simple_answer}")

    # 验证回答
    validation = generator.validate_response(simple_answer, context)
    print(f"验证结果：{validation}")


if __name__ == "__main__":
    test_response_generator()
