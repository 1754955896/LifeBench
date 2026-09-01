"""Base structured profile prompt."""

import json
from typing import Any, Dict, List, Optional

from .common import render_common_rules
from .contracts import persona_shape_contract, profile_output_contract

PROMPT_VERSION = "persona-base-profile-v2"


def build_base_profile_prompt(
    seed_person: Dict[str, Any],
    references: Dict[str, List[str]],
    as_of_date: str,
    variant_instruction: Optional[str] = None,
    locked_facts: Optional[Dict[str, Any]] = None,
    soft_clues: Optional[Dict[str, Any]] = None,
    source_description: str = "",
    variant_blueprint: Optional[Dict[str, Any]] = None,
) -> str:
    expected_keys = list(seed_person.keys())
    variant = variant_instruction or "不进行额外变体，只补全未知值并清理格式。"
    locked_facts = locked_facts or {}
    soft_clues = soft_clues or {}
    variant_blueprint = variant_blueprint or {}
    return f"""
你要补全一份用于长期生活模拟的中文用户画像。
{render_common_rules(as_of_date)}
{profile_output_contract(expected_keys)}
{persona_shape_contract()}

生成规则：
- 所有标准字段必须保留，不允许增加、删除或改名；relation 此阶段必须为 []。
- locked_facts 中的值来自用户明确输入，必须逐项保持；部分地址对象可以补充缺失子字段，但不能修改已有子字段。
- 优先补全值为“未知”、null、空字符串或空数组的字段；软线索可以合理具体化，不能当成完全无关的自由生成。
- 年龄、教育、工作、收入、家庭、城市、兴趣、健康和经历必须相互一致。
- personality.mbti 只能使用标准 16 种 MBTI；traits 为 2～4 个价值观或稳定特质。
- 兴趣和目标从参考候选中选择时必须符合人物上下文，不为覆盖候选而硬塞。
- 变体要求：{variant}

参考候选：
{json.dumps(references, ensure_ascii=False, indent=2)}

输入画像：
{json.dumps(seed_person, ensure_ascii=False, indent=2)}

锁定事实：
{json.dumps(locked_facts, ensure_ascii=False, indent=2)}

软线索：
{json.dumps(soft_clues, ensure_ascii=False, indent=2)}

原始描述：
{source_description}

本次变体蓝图：
{json.dumps(variant_blueprint, ensure_ascii=False, indent=2)}
""".strip()
