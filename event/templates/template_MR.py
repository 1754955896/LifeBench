# -*- coding: utf-8 -*-
"""MonthlyRefiner 模板文件，包含所有 LLM 调用的 prompt 模板（完整版）"""
import json
from typing import Dict, List


def habit_summary_template(month: str, persona: Dict, events: List[Dict]) -> str:
    """生成偏好习惯兴趣总结的 prompt 模板 - 逐事件影响分析"""
    return f"""
基于以下本月事件和人物画像，**逐事件分析对习惯、兴趣、人际关系的影响**。

**月份：** {month}

**人物画像：**
{json.dumps(persona, ensure_ascii=False)}

**本月事件：**
{json.dumps(events, ensure_ascii=False)}

**筛选标准：**
仅筛选并输出满足以下条件的事件：
- 涉及习惯养成或改变（作息、饮食、运动、学习等）
- 涉及兴趣爱好活动（阅读、音乐、运动、手工等）
- 涉及人际交往（聚会、拜访、合作、冲突等）
- 可能影响偏好形成的新体验
- 可能导致兴趣疏离的负面经历

**分析维度：**
对每个有影响的事件，分析其带来的变化：
1. **习惯变化**：是否养成新习惯/改掉旧习惯？频率或强度如何变化？
2. **兴趣偏好**：是否形成新的兴趣？是否对某些事物失去兴趣？投入程度如何？
3. **人际关系**：是否加深/疏远某段关系？是否结识新人？社交模式是否改变？
4. **其他影响**：是否有其他方面的变化（价值观、技能、生活方式等）？

**输出要求：**
- ✓ **只输出有影响的事件**，无影响的事件不提及
- ✓ 明确指出具体事件名称
- ✓ 说明该事件产生的具体影响（习惯/兴趣/关系变化）
- ✓ 简洁明确，不需要铺垫和总结
- ✗ 不要输出格式化结构或 JSON
- ✗ 如无显著影响事件，输出"本月生活稳定，习惯兴趣无明显波动"

**字数控制：** 300 字左右

直接输出分析报告。
    """


def health_summary_template(month: str, persona: Dict, events: List[Dict]) -> str:
    """生成运动健康体重作息变化总结的 prompt 模板 - 精简事件影响分析"""
    return f"""
基于以下本月事件和人物画像，**只输出对运动健康状况有影响的事件及其具体影响**。

**月份：** {month}

**人物画像：**
{json.dumps(persona, ensure_ascii=False)}

**本月事件：**
{json.dumps(events, ensure_ascii=False)}

**筛选标准：**
仅筛选并输出满足以下条件的事件：
- 涉及运动活动（跑步、健身、打球等）
- 影响身体状况（体重、气色、体能变化等）
- 影响作息时间（睡眠规律、质量改变等）
- 涉及伤病情况（受伤、生病、康复等）
- 其他显著影响健康的因素

**输出要求：**
- ✓ **只输出有影响的事件**，无影响的事件不提及
- ✓ 明确指出具体事件名称
- ✓ 说明该事件产生的具体健康影响
- ✓ 简洁明确，不需要铺垫和总结
- ✗ 不要输出格式化结构或 JSON
- ✗ 如无显著影响事件，输出"本月健康状况稳定，无显著波动事件"

**字数控制：** 300 字左右

直接输出分析报告。
    """


def event_summary_template(month: str, persona: Dict, events: List[Dict]) -> str:
    """生成本月事件生活总结的 prompt 模板 - 简洁明确的事件概览"""
    return f"""
基于以下本月事件和人物画像，生成一份**简洁明确的个人生活事件概览**。

**月份：** {month}

**人物画像：**
{json.dumps(persona, ensure_ascii=False)}

**本月事件：**
{json.dumps(events, ensure_ascii=False)}

请按照以下结构输出：

**一、本月主要生活主线**
- 全面覆盖所有事件，不遗漏任何重要活动
- 清晰展示事件的主要内容和发展流程
- 突出本月的核心活动和关键节点
- 保持简洁明确，避免文学性描述

**二、人际关系分析**
- 本月涉及的人际关系（家人、朋友、同事等）
- 社交活动的频率和性质
- 重要的人际互动及其影响

**三、生活习惯分析**
- 日常生活习惯的变化体现（作息、饮食、运动等）

**输出要求：**
- ✗ 不要创作性叙事，不要情感渲染
- ✓ 客观、简洁、明确地陈述事实
- ✓ 像生活日志一样清晰记录
- ✓ 确保所有事件都被提及和归类
- ✓ 使用条目式结构，便于快速阅读

直接输出一份结构化的生活事件概览（300字左右）。
    """


def initial_trends_template(persona: Dict) -> str:
    """生成初步年度趋势设计的 prompt 模板"""
    return f"""
基于以下人物画像，请设计一个多样化、真实可信的全年发展趋势。

**人物画像：**
{json.dumps(persona, ensure_ascii=False)}

请设计以下内容：

**一、偏好习惯兴趣变化趋势**
设计全年 12 个月的习惯兴趣演变路径，要求：
- 数据要有明显的波动性和发展性，避免单调线性增长
- 习惯要随月份或事件影响出现明显的变化
- 偏好包括感兴趣的领域话题、音乐、饮食、娱乐方式、休闲等具体类型，可根据画像合理生成或随机添加
- 一年的数据中至少要出现4种以上新偏好的生成（从0养成一种类型如开始唱歌/爬山，或类型转换如音乐从古典到phonk，饮食从美式到中餐，打羽毛球从单打到混双等）
- 符合人物性格和生活环境
- 包含季节性变化（如冬季室内活动增多）
- 包含突发事件影响（如某月突然迷上某项运动，或受伤忙碌暂停）
- 习惯的养成、巩固、淡化、消失的自然过程

**二、运动健康变化趋势**
设计全年 12 个月的运动健康状况变化，要求：
- 体重需要每月都有一定不同，体现波动性，或者趋势性（变重/减肥）
- 运动健康数据要分配好全年每个月的运动量
- 至少要有一个运动表现的里程碑突破
- 运动数据与体重等健康数据保持一致
- 运动强度和频率的起伏变化
- 伤病或低谷期的设定
- 突破和进步的时刻
- 外界因素影响（如工作压力导致运动减少）

**三、整体要求**
- 全年数据总体逻辑通顺，丰富多样
- 具有明显的发展变化和波折
- 体现人物生活的复杂性和真实感
- 各数据之间保持一致性和连贯性

输出 JSON 格式：
{{
    "habit_interest_trends": {{
        "overview": "全年习惯兴趣变化总体描述，强调波动性和发展性",
        "monthly_phases": [
            {{
                "month": "月份（如'1月'）",
                "main_habits": "当月主要习惯，体现变化",
                "new_interests": "当月新兴兴趣，具体类型",
                "fading_interests": "当月淡化兴趣",
                "characteristics": "当月特征，反映波动"
            }}
        ],
        "key_turning_points": [
            {{
                "month": "月份",
                "event": "转折事件",
                "impact": "对习惯兴趣的影响"
            }}
        ]
    }},
    "health_exercise_trends": {{
        "overview": "全年运动健康变化总体描述，强调波动性和发展性",
        "monthly_changes": [
            {{
                "month": "月份（如'1月'）",
                "weight_trend": "体重变化趋势，每月不同",
                "fitness_level": "体能水平",
                "exercise_frequency": "运动频率，每月分配",
                "highlights": "亮点时刻，包括里程碑突破",
                "challenges": "面临的挑战"
            }}
        ],
        "year_summary": {{
            "net_change": "净变化（如体重±X kg）",
            "major_achievements": "主要成就，包括运动里程碑",
            "setbacks": "挫折",
            "overall_trajectory": "整体轨迹，体现发展变化"
        }}
    }}
}}
    """


def refine_trends_template(initial_trends: Dict, monthly_highlights: List[Dict]) -> str:
    """优化年度趋势的 prompt 模板"""
    return f"""
基于初步设计的年度趋势和 12 个月的实际总结反馈，请重新优化年度趋势。

**初步设计的趋势：**
{json.dumps(initial_trends, ensure_ascii=False, indent=2)}

**12 个月的实际总结反馈（现有事件）：**
{json.dumps(monthly_highlights, ensure_ascii=False, indent=2)}

请对比初步设计和实际反馈，进行以下优化：

1. **验证一致性**：初步趋势是否与月度总结相符？有哪些偏差？
2. **吸收反馈**：从月度总结中发现哪些意想不到的变化？
3. **修正趋势**：基于反馈调整年度趋势曲线，确保与现有事件一致
4. **扩展丰富度**：在不与现有事件冲突的情况下，合理创作新事件和趋势，使一年的变化波动更加丰富多样。不局限于已有事件及其影响。
5. **整合优质情节**：初步设计的趋势中如果有设计不错的情节，可以调整润色后加入（比如修改发生时间、方式等）
6. **增强细节**：补充具体的习惯兴趣变化细节，体现人物生活的复杂性
7. **合理化解释**：解释重大变化的原因和逻辑，使趋势发展更加自然合理

**设计要求：**
- 确保一年的变化波动极其丰富，人物生活复杂多变
- 包含季节性变化和突发事件的影响
- 体现习惯的养成、巩固、淡化、消失的自然过程
- 展示运动健康状况的起伏变化
- 合理安排高潮和低谷，避免单调线性发展
- 新增事件要与现有事件不冲突，时间安排合理
- 调整已有情节时要保持逻辑连贯性，确保修改后的情节更加合理真实

**输出要求：**
- 直接逐月输出每个月的习惯偏好和运动健康的趋势发展
- 然后返回一个全年总结
- 不需要输出refinement_notes部分

输出优化后的 JSON 格式：
{{
    "habit_interest_trends": {{
        "overview": "全年习惯兴趣偏好变化总体描述",
        "monthly_phases": [
            {{
                "month": "月份（如'1月'）",
                "main_habits": "当月主要习惯",
                "new_interests": "当月新兴兴趣",
                "fading_interests": "当月淡化兴趣",
                "characteristics": "当月特征"
            }}
        ],
    }},
    "health_exercise_trends": {{
        "overview": "全年运动健康变化总体描述",
        "monthly_changes": [
            {{
                "month": "月份（如'1月'）",
                "weight_trend": "体重变化趋势",
                "fitness_level": "体能水平",
                "exercise_frequency": "运动频率",
                "highlights": "亮点时刻",
                "challenges": "面临的挑战"
            }}
        ]
    }}
}}
    """


def monthly_issues_template(month: str, summary: Dict, refined_trends: Dict) -> str:
    """分析每月问题的 prompt 模板"""
    return f"""
分析以下月份的总结报告，找出逻辑错误和不合理之处，并给出修改指导。

**月份：** {month}

**该月总结：**
{json.dumps(summary, ensure_ascii=False, indent=2)}

**年度趋势背景：**
{json.dumps(refined_trends, ensure_ascii=False, indent=2)}

请从以下方面分析：

**一、逻辑错误检查**
1. 事件之间是否存在时间冲突？
2. 习惯变化是否符合常理？
3. 健康数据变化是否合理（如体重骤变）？
4. 因果关系是否成立？

**二、不合理之处**
1. 是否有过于突兀的变化？
2. 是否有缺乏铺垫的重大决定？
3. 是否有违背人物性格的行为？
4. 是否有不符合季节/环境的活动？

**三、修改指导**
针对发现的问题，给出具体的修改建议：
1. 需要调整的事件或描述
2. 需要补充的铺垫或过渡
3. 需要删除的不合理内容
4. 需要强化的逻辑链条

输出 JSON 格式：
{{
    "month": "{month}",
    "logical_errors": [
        {{
            "issue": "问题描述",
            "location": "所在位置（事件/习惯/健康等）",
            "severity": "严重程度（高/中/低）",
            "explanation": "为什么这是问题"
        }}
    ],
    "unreasonable_parts": [
        {{
            "issue": "不合理之处描述",
            "reason": "不合理的原因",
            "suggestion": "改进建议"
        }}
    ],
    "modification_guidance": [
        {{
            "target": "修改目标",
            "action": "修改动作（调整/补充/删除/强化）",
            "details": "具体修改方案",
            "priority": "优先级（高/中/低）"
        }}
    ],
    "overall_assessment": "对该月总结的整体评价"
}}
    """


def all_months_issues_template(monthly_summaries: Dict[str, Dict], refined_trends: Dict) -> str:
    """一次性分析所有月份问题的 prompt 模板"""
    return f"""
分析以下所有月份的总结报告，找出逻辑错误和不合理之处，并给出修改指导。

**12 个月的总结报告：**
{json.dumps(monthly_summaries, ensure_ascii=False, indent=2)}

**年度趋势背景：**
{json.dumps(refined_trends, ensure_ascii=False, indent=2)}

请从以下方面分析每个月份：

**一、逻辑错误检查**
1. 事件之间是否存在时间冲突？
2. 习惯变化是否符合常理？
3. 健康数据变化是否合理（如体重骤变）？
4. 因果关系是否成立？

**二、不合理之处**
1. 是否有过于突兀的变化？
2. 是否有缺乏铺垫的重大决定？
3. 是否有违背人物性格的行为？
4. 是否有不符合季节/环境的活动？
5. 是否有不合理的频率？
6. 是否有不符合现实的事件？
7. 是否有缺少后续/前置的突兀事件？

**三、修改指导**
针对发现的问题，给出具体的修改建议：
1. 需要调整的事件或描述
2. 需要补充的铺垫或过渡
3. 需要删除的不合理内容
4. 需要强化的逻辑链条

**输出要求：**
- 对每个月份单独进行分析
- 输出格式清晰，便于后续处理

输出 JSON 格式：
{{
    "monthly_guidance": {{
        "月份": {{
            "logical_errors": [
                {{
                    "issue": "问题描述",
                    "location": "所在位置（事件/习惯/健康等）",
                    "severity": "严重程度（高/中/低）",
                    "explanation": "为什么这是问题"
                }}
            ],
            "unreasonable_parts": [
                {{
                    "issue": "不合理之处描述",
                    "reason": "不合理的原因",
                    "suggestion": "改进建议"
                }}
            ],
            "modification_guidance": [
                {{
                    "target": "修改目标",
                    "action": "修改动作（调整/补充/删除/强化）",
                    "details": "具体修改方案",
                    "priority": "优先级（高/中/低）"
                }}
            ],
            "overall_assessment": "对该月总结的整体评价"
        }}
    }}
}}
    """


def generate_monthly_final_summary_template(month: str, original_events: List[Dict], guidance: Dict, refined_trends: Dict) -> str:
    """生成每月最终优化总结的 prompt 模板"""
    return f"""
基于以下材料，为这个月份生成一份优化后的最终总结报告。

**月份：** {month}

**原始事件：**
{json.dumps(original_events, ensure_ascii=False, indent=2)}

**修改指导意见：**
{json.dumps(guidance, ensure_ascii=False, indent=2)}

**年度趋势背景：**
{json.dumps(refined_trends, ensure_ascii=False, indent=2)}

请根据修改指导，重新生成这个月份的完整总结，包括：

**一、本月趋势变化**
- 习惯兴趣的变化情况（对比年度趋势设计）
- 运动健康状况的变化（体重、体能等）
- 在年度趋势中的位置和重要性

**二、优化后的事件生活总结**
- 修正逻辑错误后的事件叙事
- 更合理的生活主线描述
- 情感与成长的真实呈现

**三、优化后的健康总结**
- 基于指导意见修正的健康数据
- 更合理的运动表现和身体变化
- 作息和伤病情况的准确描述

**四、优化后的习惯兴趣总结**
- 符合年度趋势的习惯变化
- 兴趣爱好的合理演变
- 频率和强度的真实记录

**输出要求：**
- 充分吸收修改指导，修正所有不合理之处
- 保持与年度趋势的一致性
- 叙事流畅、数据合理、逻辑自洽

输出 JSON 格式：
{{
    "month": "{month}",
    "trend_changes": {{
        "habit_interest_trend": "习惯兴趣变化趋势描述",
        "health_exercise_trend": "运动健康变化趋势描述",
        "position_in_year": "在年度趋势中的位置和意义"
    }},
    "optimized_event_summary": "优化后的事件生活总结（300-500 字）",
    "optimized_health_summary": {{
        "exercise": {{...}},
        "body_metrics": {{...}},
        "sleep": {{...}},
        "injuries_illnesses": "...",
        "trend": "..."
    }},
    "optimized_habit_summary": {{
        "current_habits": [...],
        "interests": [...],
        "changes": [...],
        "trends": "..."
    }},
    "modifications_applied": [
        {{
            "issue": "修正的问题",
            "modification": "应用的修改",
            "improvement": "改进效果"
        }}
    ]
}}
    """


def polish_events_template(month: str, original_events: List[Dict], guidance: Dict, refined_trends: Dict) -> str:
    """润色已有事件的 prompt 模板"""
    # 如果 guidance 和 refined_trends 相同，只使用一次
    if guidance == refined_trends:
        summary_info = json.dumps(guidance, ensure_ascii=False, indent=2)
        return f"""
基于以下材料，润色和优化 {month} 的已有事件。

**月份：** {month}

**原始事件列表：**
{json.dumps(original_events, ensure_ascii=False, indent=2)}

**优化指导与趋势背景（修改目标）：**
{summary_info}

请进行以下优化：

**一、时间分布调整**
- 检测并解决时间冲突
- 合理分配事件在月份中的分布
- 调整事件发生日期，使事件分布和生活流程更合理连贯
- 允许同时进行多个事件

**二、事件描述微调**
- 使事件描述更连贯自然
- 补充必要的细节和过渡
- 修正逻辑不合理之处

**三、吸收修改指导**
- 根据指导意见调整事件
- 强化需要突出的内容
- 删除或修改不合理事件

**输出要求：**
- 保持事件的真实性和可信度
- 与年度趋势保持一致
- 事件之间有良好的因果或时间关联
- 最小改动原则，没有明显冲突矛盾时不需要调整
- 不要遗漏任何事件


输出 JSON 格式：
{{
    "polished_events": [
        {{
            "id": "事件 ID",
            "title": "事件标题",
            "time": ["时间范围"],
            "description": "优化后的详细描述",
            "type": "事件类型",
            "adjustments_made": "应用的调整说明"
        }}
    ],
    "improvement_summary": "整体改进总结与思考过程（冲突有哪些，怎么调整）"
}}
    """
    else:
        # 原有逻辑，分别处理 guidance 和 refined_trends
        return f"""
基于以下材料，润色和优化 {month} 的已有事件。

**月份：** {month}

**原始事件列表：**
{json.dumps(original_events, ensure_ascii=False, indent=2)}

**修改指导意见：**
{json.dumps(guidance, ensure_ascii=False, indent=2)}

**年度趋势背景：**
{json.dumps(refined_trends, ensure_ascii=False, indent=2)}

请进行以下优化：

**一、时间分布调整**
- 检测并解决时间冲突
- 合理分配事件在月份中的分布
- 确保事件时间范围不重叠

**二、事件描述微调**
- 使事件描述更连贯自然
- 补充必要的细节和过渡
- 修正逻辑不合理之处

**三、吸收修改指导**
- 根据指导意见调整事件
- 强化需要突出的内容
- 删除或修改不合理事件

**输出要求：**
- 保持事件的真实性和可信度
- 与年度趋势保持一致
- 事件之间有良好的因果或时间关联
- 最小改动原则，没有明显冲突矛盾时不需要调整
输出 JSON 格式：
{{
    "polished_events": [
        {{
            "id": "事件 ID",
            "title": "事件标题",
            "time": ["时间范围"],
            "description": "优化后的详细描述",
            "type": "事件类型",
            "adjustments_made": "应用的调整说明"
        }}
    ],
    "time_conflicts_resolved": [
        {{
            "conflict": "冲突描述",
            "resolution": "解决方案"
        }}
    ],
    "improvement_summary": "整体改进总结"
}}
    """


def add_trend_based_events_template(month: str, current_events: List[Dict], trend_changes: Dict, guidance: Dict) -> str:
    """基于趋势新增事件的 prompt 模板"""
    # 如果 trend_changes 和 guidance 相同，只使用一次
    if trend_changes == guidance:
        summary_info = json.dumps(trend_changes, ensure_ascii=False, indent=2)
        return f"""
基于以下趋势变化和现有事件，为 {month} 安排新的事件来实现趋势。

**月份：** {month}

**当前事件列表：**
{json.dumps(current_events, ensure_ascii=False, indent=2)}

**趋势变化与指导意见：**
{summary_info}

请设计新的事件来体现和实现上述趋势变化，包括：

**一、习惯兴趣类事件**
- 体现新培养的习惯
- 展示兴趣爱好的发展
- 反映频率和强度的变化

**二、运动健康类事件**
- 体现运动计划的变化
- 反映身体状况的波动
- 展示健康目标的追求

**三、生活叙事类事件**
- 丰富本月生活主线
- 增加重要时刻和转折点
- 补充人际关系互动

**设计要求：**
- 与现有事件兼容，允许时间重叠但不要有时空冲突（如同时出现在两个地点）
- 符合人物画像和性格
- 有合理的起因和发展过程
- 时间安排合理（考虑节假日、工作日等）
- 事件可以跨日，时间格式为 "XXXX-XX-XX至XXXX-XX-XX"
- 对于多日事件，在 description 中详细描述每天的具体活动安排，多日事件不必在持续时间的每一天都有内容。

**时间格式说明：**
- 单天事件："2025-03-15至2025-03-15"
- 跨天事件："2025-03-15至2025-03-18"
- 允许多个事件在同一时间段发生（如上午工作、下午健身）
- 避免时空冲突（如同一时间在不同地点）

**多日活动描述示例：**
对于跨越多天的事件，在 description 中按日期详细说明：
{{
    "title": "周末登山露营",
    "time": ["2025-03-15至2025-03-17"],
    "description": "三天两夜的登山露营活动。3月15日：早上8点出发前往山区，下午到达营地搭建帐篷，晚上篝火晚会。3月16日：清晨登山看日出，上午探索周边步道，下午休息整理装备，晚上观星。3月17日：收拾营地，中午下山，下午返回市区。",
    "type": "休闲娱乐"
}}

输出 JSON 格式：
{{
    "new_events": [
        {{
            "title": "事件标题",
            "time": ["XXXX-XX-XX至XXXX-XX-XX"],
            "description": "详细描述，对于多日事件需按日期说明每天的活动",
            "type": "事件类型（习惯/健康/生活等）",
            "trend_alignment": "如何体现趋势变化",
            "rationale": "设计理由"
        }}
    ],
    "trend_implementation_notes": "趋势实现说明"
}}
    """
    else:
        # 原有逻辑
        return f"""
基于以下趋势变化和现有事件，为 {month} 安排新的事件来实现趋势。

**月份：** {month}

**当前事件列表：**
{json.dumps(current_events, ensure_ascii=False, indent=2)}

**该月趋势变化：**
{json.dumps(trend_changes, ensure_ascii=False, indent=2)}

**修改指导意见：**
{json.dumps(guidance, ensure_ascii=False, indent=2)}

请设计新的事件来体现和实现上述趋势变化，包括：

**一、习惯兴趣类事件**
- 体现新培养的习惯
- 展示兴趣爱好的发展
- 反映频率和强度的变化

**二、运动健康类事件**
- 体现运动计划的变化
- 反映身体状况的波动
- 展示健康目标的追求

**三、生活叙事类事件**
- 丰富本月生活主线
- 增加重要时刻和转折点
- 补充人际关系互动

**设计要求：**
- 与现有事件兼容，允许时间重叠但不要有时空冲突（如同时出现在两个地点）
- 符合人物画像和性格
- 有合理的起因和发展过程
- 时间安排合理（考虑节假日、工作日等）
- 事件可以跨日，时间格式为 "XXXX-XX-XX至XXXX-XX-XX"
- 对于多日事件，在 description 中详细描述每天的具体活动安排

**时间格式说明：**
- 单天事件："2025-03-15至2025-03-15"
- 跨天事件："2025-03-15至2025-03-18"
- 允许多个事件在同一时间段发生（如上午工作、下午健身）
- 避免时空冲突（如同一时间在不同地点）

**多日活动描述示例：**
对于跨越多天的事件，在 description 中按日期详细说明：
{{
    "title": "周末登山露营",
    "time": ["2025-03-15至2025-03-17"],
    "description": "三天两夜的登山露营活动。3月15日：早上8点出发前往山区，下午到达营地搭建帐篷，晚上篝火晚会。3月16日：清晨登山看日出，上午探索周边步道，下午休息整理装备，晚上观星。3月17日：收拾营地，中午下山，下午返回市区。",
    "type": "休闲娱乐"
}}

输出 JSON 格式：
{{
    "new_events": [
        {{
            "title": "事件标题",
            "time": ["XXXX-XX-XX至XXXX-XX-XX"],
            "description": "详细描述，对于多日事件需按日期说明每天的活动",
            "type": "事件类型（习惯/健康/生活等）",
            "trend_alignment": "如何体现趋势变化",
            "rationale": "设计理由"
        }}
    ],
    "trend_implementation_notes": "趋势实现说明"
}}
    """


def select_library_events_template(month: str, current_events: List[Dict], event_library: List[Dict], holidays: List[Dict]) -> str:
    """从事件库选择事件的 prompt 模板"""
    return f"""
为 {month} 丰富事件数据，包括从事件库中选择和合理新增事件。

**月份：** {month}

**当前事件列表：**
{json.dumps(current_events, ensure_ascii=False, indent=2)}

**该月节假日：**
{json.dumps(holidays, ensure_ascii=False, indent=2)}

**可用事件库：**
{json.dumps(event_library, ensure_ascii=False, indent=2)}

请执行以下两项任务：

**任务一：从事件库中选择合适的事件**
- 与现有事件不冲突
- 符合该月的节假日特点
- 与人物画像一致
- 补充不同类别的事件，增加生活丰富度

**任务二：合理新增事件（不在事件库中），新增事件不超过3个**
根据人物职业、生活习惯和当月特点，创造性地新增以下类型的事件：

**重要原则：**
- **局部性原则**：新增事件仅影响本月，不改变全年趋势或人物核心画像
- **时间局限**：所有事件必须严格限制在本月范围内，不跨月延伸
- **可逆性**：事件的影响应是暂时的，下个月可以恢复正常状态
- **重要性门槛**：不要生成过于细小的事件，事件应至少占用半天以上的时间或具有一定的重要性
  - ✅ **应该生成**：专门去某个超市的大采购、参加半天的培训课程、周末去爬山、与朋友聚餐聊天
  - ❌ **不应生成**：去商店买水喝、下楼取快递、简单的日常通勤、短暂的休息

1. **工作任务类事件**
   - 医院/职场中的具体任务（如：参与手术、值班、学术会议、病例讨论）
   - 职业发展相关活动（如：培训、考试准备、论文写作）
   - 同事协作项目或团队建设活动

2. **日常生活类事件**
   - 购物、家务、维修，采购等日常琐事
   - 处理个人事务（如：办理证件、缴费、预约）

3. **周末娱乐类事件**
   - 休闲娱乐活动（如：看电影、逛街、探店美食）
   - 户外运动（如：爬山、骑行、羽毛球）
   - 文化活动（如：看展、听音乐会、读书会）
   - 短途旅行或城市探索（city walk）
   - 兴趣培养活动（如：陶艺课、绘画、烹饪）

**设计要求：**
- 新增事件要符合人物画像和职业特点
- 时间分布合理，考虑工作日和周末的差异
- 与现有事件和节假日有良好的关联
- 事件描述具体、真实、有细节
- 时间格式为 "XXXX-XX-XX至XXXX-XX-XX"
- 对于多日事件，在 description 中按日期说明每天的活动

输出 JSON 格式：
{{
    "selected_events": [
        {{
            "source_id": "事件库中的 ID",
            "title": "事件标题",
            "time": ["建议的时间范围"],
            "description": "详细描述（可根据需要调整）",
            "type": "事件类型",
            "selection_reason": "选择理由"
        }}
    ],
    "new_events": [
        {{
            "title": "新增事件标题",
            "time": ["XXXX-XX-XX至XXXX-XX-XX"],
            "description": "详细描述，对于多日事件需按日期说明每天的活动",
            "type": "事件类型（工作/生活/娱乐/社交等）",
            "category": "事件类别（工作任务/日常生活/周末娱乐/社交互动）",
            "rationale": "新增理由"
        }}
    ],
    "rejected_events": [
        {{
            "source_id": "事件库中的 ID",
            "reason": "拒绝原因"
        }}
    ],
    "strategy_notes": "选择和新增策略说明"
}}
    """


def evaluate_monthly_events_template(month: str, events: List[Dict], guidance: Dict, refined_trends: Dict) -> str:
    """评估和调整事件的 prompt 模板"""
    # 如果 guidance 和 refined_trends 相同，只使用一次
    if guidance == refined_trends:
        summary_info = json.dumps(guidance, ensure_ascii=False, indent=2)
        return f"""
评估 {month} 的所有事件质量，并输出调整操作。

**月份：** {month}

**待评估事件列表：**
{json.dumps(events, ensure_ascii=False, indent=2)}

**评估指导与趋势背景：**
{summary_info}

请从以下三个维度进行评估：

**一、合理性评估**
1. **事件因果性**：事件之间是否有合理的因果关系？前因后果是否清晰？
2. **事件充分性**：事件描述是否充分完整？是否有足够的细节支撑？
3. **逻辑连贯性**：整体叙事是否连贯流畅？事件衔接是否自然？
4. **时空合理性**：事件的时间和空间安排是否合理？是否存在时空冲突？
5. **逻辑自洽性**：事件是否符合人物画像和常理？是否有矛盾或不合理之处？

**二、多样性评估**
1. **事件类型丰富度**：是否涵盖生活、工作、学习、休闲、社交等多个方面？
2. **变化和新意**：是否有足够的事件变化和新鲜感？避免单调重复？
3. **生活覆盖面**：是否全面反映人物的多维度生活？

**三、趋势一致性评估**
1. **习惯体现**：事件是否体现了习惯的养成、巩固或改变？
2. **趋势符合度**：是否符合年度趋势设计中该月的预期变化？
3. **健康数据体现**：运动、体重、作息等健康相关事件是否与趋势一致？

**输出要求：**
- 仅输出必要的调整操作，不要输出评估分数或评价文本
- 操作类型只有两种：
  1. **update**：修改现有事件（必须提供事件 ID）
  2. **add**：新增事件
- 每个操作需说明原因和具体修改内容
- 如果没有需要调整的地方，返回空数组

输出 JSON 格式：
{{
    "operations": [
        {{
            "action": "update",
            "event_id": "要修改的事件ID",
            "updates": {{
                "title": "新标题（可选）",
                "time": ["新时间范围（可选）"],
                "description": "新描述（可选）",
                "type": "新类型（可选）"
            }},
            "reason": "修改原因"
        }},
        {{
            "action": "add",
            "event": {{
                "title": "新事件标题",
                "time": ["XXXX-XX-XX至XXXX-XX-XX"],
                "description": "详细描述",
                "type": "事件类型"
            }},
            "reason": "新增原因"
        }}
    ]
}}
    """
    else:
        # 原有逻辑
        return f"""
评估 {month} 的所有事件质量，并输出调整操作。

**月份：** {month}

**待评估事件列表：**
{json.dumps(events, ensure_ascii=False, indent=2)}

**修改指导意见：**
{json.dumps(guidance, ensure_ascii=False, indent=2)}

**年度趋势背景：**
{json.dumps(refined_trends, ensure_ascii=False, indent=2)}

请从以下三个维度进行评估：

**一、合理性评估**
1. **事件因果性**：事件之间是否有合理的因果关系？前因后果是否清晰？
2. **事件充分性**：事件描述是否充分完整？是否有足够的细节支撑？
3. **逻辑连贯性**：整体叙事是否连贯流畅？事件衔接是否自然？
4. **时空合理性**：事件的时间和空间安排是否合理？是否存在时空冲突？
5. **逻辑自洽性**：事件是否符合人物画像和常理？是否有矛盾或不合理之处？

**二、多样性评估**
1. **事件类型丰富度**：是否涵盖生活、工作、学习、休闲、社交等多个方面？
2. **变化和新意**：是否有足够的事件变化和新鲜感？避免单调重复？
3. **生活覆盖面**：是否全面反映人物的多维度生活？

**三、趋势一致性评估**
1. **习惯体现**：事件是否体现了习惯的养成、巩固或改变？
2. **趋势符合度**：是否符合年度趋势设计中该月的预期变化？
3. **健康数据体现**：运动、体重、作息等健康相关事件是否与趋势一致？

**输出要求：**
- 仅输出必要的调整操作，不要输出评估分数或评价文本
- 操作类型只有两种：
  1. **update**：修改现有事件（必须提供事件 ID）
  2. **add**：新增事件
- 每个操作需说明原因和具体修改内容
- 如果没有需要调整的地方，返回空数组

输出 JSON 格式：
{{
    "operations": [
        {{
            "action": "update",
            "event_id": "要修改的事件ID",
            "updates": {{
                "title": "新标题（可选）",
                "time": ["新时间范围（可选）"],
                "description": "新描述（可选）",
                "type": "新类型（可选）"
            }},
            "reason": "修改原因"
        }},
        {{
            "action": "add",
            "event": {{
                "title": "新事件标题",
                "time": ["XXXX-XX-XX至XXXX-XX-XX"],
                "description": "详细描述",
                "type": "事件类型"
            }},
            "reason": "新增原因"
        }}
    ]
}}
    """


def generate_monthly_summary_template(month: str, final_events: List[Dict], original_persona: Dict) -> str:
    """生成新的月份总结的 prompt 模板（第一步）"""
    return f"""
基于最终确定的事件，生成 {month} 的新总结报告。

**月份：** {month}

**最终事件列表：**
{json.dumps(final_events, ensure_ascii=False, indent=2)}

**原始人物画像：**
{json.dumps(original_persona, ensure_ascii=False, indent=2)}

请生成以下三个维度的总结：

**一、事件生活总结**
撰写一份有血有肉的生活叙事，包括：
- 本月的主要生活主线和重要时刻
- 遇到的挑战和成长
- 人际关系的变化
- 情感和内心世界的波动
- 对未来的期待和规划

**二、运动健康体重作息变化总结**
分析并输出以下内容：
- 运动情况（项目、频率、强度变化）
- 身体数据变化（体重、BMI、外貌气色）
- 作息情况（睡眠时间、质量、精力状态）
- 伤病情况
- 整体变化趋势

**三、偏好习惯兴趣总结**
分析并输出以下内容：
- 本月主要习惯（日常生活、学习、工作、休闲、消费习惯）
- 兴趣偏好（热衷的兴趣、新培养的兴趣、投入程度）
- 习惯兴趣变化（新增/改掉、频率或强度变化）
- 趋势分析（正在形成的习惯、稳定的习惯、整体趋势）

**输出要求：**
- 事件生活总结要真实感人，300-500 字连贯叙事
- 健康总结和习惯兴趣总结使用 JSON 格式
- 总结要基于事件，体现真实性和情感

输出 JSON 格式：
{{
    "event_summary": "事件生活总结文本（300-500 字）",
    "health_summary": {{
        "exercise": {{
            "activities": "运动项目描述",
            "frequency": "频率",
            "changes": "变化情况"
        }},
        "body_metrics": {{
            "weight_change": "体重变化描述",
            "bmi_change": "BMI 变化",
            "appearance": "外貌气色变化"
        }},
        "sleep": {{
            "pattern": "作息规律",
            "quality": "质量变化",
            "energy": "精力状态"
        }},
        "injuries_illnesses": "伤病情况描述",
        "trend": "整体变化趋势"
    }},
    "habit_summary": {{
        "current_habits": [
            {{
                "category": "习惯类别",
                "habit": "具体习惯",
                "frequency": "频率",
                "description": "详细描述"
            }}
        ],
        "interests": [
            {{
                "type": "兴趣类型",
                "activity": "具体活动",
                "engagement": "投入程度",
                "description": "详细描述"
            }}
        ],
        "changes": [
            {{
                "change_type": "新增/改掉/增强/减弱",
                "item": "涉及的习惯/兴趣",
                "description": "变化描述"
            }}
        ],
        "trends": "习惯兴趣养成趋势描述"
    }}
}}
    """


def update_persona_template(month: str, final_events: List[Dict], monthly_summary: Dict, original_persona: Dict) -> str:
    """更新人物画像的 prompt 模板（第二步）"""
    return f"""
基于本月的最终事件和生成的总结报告，输出人物画像的修改操作。

**月份：** {month}

**最终事件列表：**
{json.dumps(final_events, ensure_ascii=False, indent=2)}

**本月总结报告：**
{json.dumps(monthly_summary, ensure_ascii=False, indent=2)}

**原始人物画像：**
{json.dumps(original_persona, ensure_ascii=False, indent=2)}

请分析本月事件和总结，识别需要更新的画像字段，仅输出修改操作。

**可修改的字段包括：**
1. **personality（性格特点）**：MBTI 类型和性格特征的微小变化
2. **hobbies（爱好）**：新增/改变/消失的兴趣爱好
3. **favorite_foods（喜爱食物）**：饮食偏好的变化
4. **memory_date（重要记忆日期）**：添加本月的重要事件日期
5. **aim（目标）**：根据实际情况调整或新增目标
6. **healthy_desc（健康状况描述）**：基于本月健康总结更新
7. **lifestyle_desc（生活方式描述）**：基于本月生活习惯变化更新
8. **economic_desc（经济状况描述）**：基于本月消费和投资情况更新
9. **work_desc（工作状况描述）**：基于本月工作经历更新
10. **experience_desc（人生经历描述）**：添加本月的重要经历
11. **description（综合描述）**：整合所有变化的完整画像描述
12. **relation（社会关系）**：人际关系的变化

**输出要求：**
- 仅输出有变化的字段，不要输出未修改的字段
- 每个修改操作需包含字段名和修改后的内容
- 对于 relation 字段中的人物修改，需指定具体人名和修改的字段
- 变化要合理、渐进，避免突兀
- 与全年趋势保持一致
- 如果没有需要修改的地方，返回空数组

**relation 字段的修改格式示例：**
如果修改某个人的信息，需要指定人名：
{{
    "field": "relation",
    "person_name": "张三",
    "updates": {{
        "relationship": "从同事变为好友",
        "contact_frequency": "从每月1次增加到每周2次"
    }}
}}

**普通字段的修改格式示例：**
{{
    "field": "hobbies",
    "value": ["跑步", "阅读", "摄影"]  // 完整的更新后内容
}}

输出 JSON 格式：
{{
    "modifications": [
        {{
            "field": "字段名",
            "value": "修改后的完整内容（普通字段）",
            "reason": "修改原因"
        }},
        {{
            "field": "relation",
            "person_name": "人名",
            "updates": {{
                "子字段1": "新值",
                "子字段2": "新值"
            }},
            "reason": "修改原因"
        }}
    ]
}}
    """


def generate_month_summary_and_persona_template(month: str, final_events: List[Dict], original_persona: Dict) -> str:
    """生成新的月份总结和动态画像的 prompt 模板（旧版，保留兼容）"""
    return f"""
基于最终确定的事件，生成 {month} 的新总结报告，并更新人物画像。

**月份：** {month}

**最终事件列表：**
{json.dumps(final_events, ensure_ascii=False, indent=2)}

**原始人物画像：**
{json.dumps(original_persona, ensure_ascii=False, indent=2)}

请生成以下内容：

**一、新的月份总结**
1. **事件生活总结**：300-500 字的连贯叙事
2. **健康总结**：JSON 格式（运动、身体数据、作息、伤病）
3. **习惯兴趣总结**：JSON 格式（当前习惯、兴趣、变化、趋势）

**二、动态画像更新**
基于本月事件和总结，更新人物画像的以下方面：
1. **习惯爱好**：新增/改变/消失的习惯和兴趣
2. **健康状况**：体重、体能水平等数据的变化
3. **性格特点**：可能的微小变化
4. **社交关系**：人际关系的变化
5. **技能能力**：新获得的技能或提升的能力
6. **价值观/目标**：可能的调整

**输出要求：**
- 总结要真实感人，有血有肉
- 画像更新要合理、渐进，避免突兀
- 保持与全年趋势的一致性

输出 JSON 格式：
{{
    "new_monthly_summary": {{
        "event_summary": "事件生活总结文本",
        "health_summary": {{...}},
        "habit_summary": {{...}}
    }},
    "updated_persona": {{
        "basic_info": {{...}},  // 基本信息保持不变
        "habits_hobbies": {{...}},  // 更新的部分
        "health_fitness": {{...}},  // 更新的部分
        "personality": {{...}},  // 如有变化则更新
        "relationships": {{...}},  // 如有变化则更新
        "skills_abilities": {{...}},  // 如有变化则更新
        "values_goals": {{...}}  // 如有变化则更新
    }},
    "change_log": [
        {{
            "aspect": "变化的方面",
            "before": "之前的状态",
            "after": "现在的状态",
            "reason": "变化原因"
        }}
    ]
}}
    """


def yearly_consistency_analysis_template(year: int, monthly_summaries: Dict[str, Dict], persona: Dict) -> str:
    """全年一致性分析的 prompt 模板"""
    return f"""
以全年视角分析 {year} 年的月度总结，识别不一致、矛盾或不合理之处。

**年份：** {year}

**人物画像：**
{json.dumps(persona, ensure_ascii=False, indent=2)}

**月度总结汇总：**
{json.dumps(monthly_summaries, ensure_ascii=False, indent=2)}

请从以下维度进行全年一致性分析：

**一、时间线一致性**
- 事件的时间顺序是否合理？是否有时间倒流或逻辑冲突？
- 跨月事件的衔接是否自然？（如某月开始的项目是否在后续月份有延续）
- 重要日期是否与人物画像一致？（如生日、纪念日等）

**二、人物画像一致性**
- 各月的习惯兴趣变化是否符合人物性格和发展轨迹？
- 健康状况的波动是否合理？是否有突兀的变化？
- 人际关系的发展是否连贯？（如某月结识的人是否在后续月份出现）
- 职业发展是否符合逻辑？（如晋升、跳槽等重大变化是否有铺垫）

**三、数据一致性**
- 体重、运动量等健康数据是否有明显的不合理波动？
- 经济状况的描述是否与收入和消费一致？
- 工作地点、居住地等信息是否前后矛盾？

**四、事件合理性**
- 是否有违背常理或人物特点的事件？
- 是否有过于密集或稀疏的时期？
- 节假日安排是否合理？（如春节是否回家、国庆是否有旅行等）

**输出要求：**
- 仅输出发现的问题，不要输出评价性文本
- 每个问题需说明类型、描述、涉及的月份和建议
- 如果没有发现问题，返回空数组

输出 JSON 格式：
{{
    "issues": [
        {{
            "type": "问题类型（时间线/人物画像/数据/事件合理性）",
            "description": "问题描述",
            "involved_months": ["涉及的月份列表"],
            "severity": "严重程度（high/medium/low）",
            "suggestion": "修改建议"
        }}
    ],
    "overall_assessment": "整体评估总结"
}}
    """


def monthly_reasonableness_analysis_template(month: str, events: List[Dict], persona: Dict) -> str:
    """月度合理性分析的 prompt 模板"""
    return f"""
分析 {month} 的事件数据，判断是否有不合理的地方，并输出需要修改的日期及其详细的修改指导。

**重要说明：** 本月事件的日期和节假日信息一定是正确的，不需要分析日期和节假日的正确性。

**月份：** {month}

**人物画像：**
{json.dumps(persona, ensure_ascii=False, indent=2)}

**本月事件：**
{json.dumps(events, ensure_ascii=False, indent=2)}

请从以下维度进行分析：

**一、逻辑冲突分析**
- 事件之间是否存在因果关系矛盾？（如先有结果后有原因）
- 事件发展是否符合逻辑链条？（如学习某技能后应该有相关应用）
- 是否存在前后不一致的描述？（如某天说生病，第二天却参加剧烈运动）
- 长跨度事件的描述是否连贯？中途是否有矛盾的状态变化？

**二、时空冲突分析**
- 同一时间段是否有多个地点冲突的事件？（如同时在武汉和在杭州）
- 事件的时间安排是否过于紧凑或不现实？（如一天内完成不可能的任务量）

**三、画像一致性分析**
- 事件是否符合人物的职业特点和工作习惯？
- 事件是否体现人物的兴趣爱好和生活方式？
- 是否有与人物性格明显不符的行为？（如内向者突然频繁社交）
- **注意**：允许少量新尝试或轻微不符合画像的事件，体现人物成长和变化

**四、充分性分析**
- 事件密度是否合理？是否有过长时间的空白期？
- 重要生活领域是否有充分体现？（工作、家庭、社交、健康、个人成长等）
- 关键节点是否有足够的事件支撑？（如项目启动、考试、旅行等）
- 人物的变化和成长是否有事件体现？
- 社交互动是否充分？人际关系是否有维护和发展？

**五、修改指导建议**
对于每个需要修改的日期，必须在 suggestion 字段中提供详细的文本描述，包括：
1. **增加事件**：明确说明需要增加什么类型的事件、为什么需要增加、建议的事件内容
2. **删除事件**：明确说明需要删除哪些事件、删除的原因
3. **修改事件**：明确说明需要修改哪些事件、如何修改（调整时间/地点/描述/参与人员等）
4. **状态调整**：如需调整起床时间、睡觉时间、心情状态等，需明确说明

**重要约束：**
- **只挑选明显不合理的日期进行修改**，不要过度修改
- **最多输出 10 个需要修改的日期**，优先选择问题最严重的日期
- 如果问题较少，可以输出更少的日期甚至空数组
- 避免为了修改而修改，保持事件的稳定性

**输出要求：**
- 仅输出需要修改的日期，不要输出评价性文本
- 每个日期的 suggestion 字段必须包含详细的修改指导，用文本清晰描述需要增加、删除或修改的内容
- 如果没有需要修改的地方，返回空数组

输出 JSON 格式：
{{
    "dates_to_modify": [
        {{
            "date": "YYYY-MM-DD",
            "reason": "需要修改的总体原因",
            "suggestion": "详细的修改建议，用文本描述：\n1. 需要增加的事件：...\n2. 需要删除的事件：...\n3. 需要修改的事件：...\n4. 状态调整建议：..."
        }}
    ],
    "analysis_summary": "分析总结"
}}
    """