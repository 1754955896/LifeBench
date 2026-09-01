"""Profile enrichment prompt: one-shot completion + richness for sparse base profiles."""

import json
from typing import Any, Dict, List, Optional

from .common import render_common_rules
from .contracts import persona_shape_contract, profile_output_contract

PROMPT_VERSION = "persona-profile-enrich-v1"


def build_profile_enrich_prompt(
    profile: Dict[str, Any],
    as_of_date: str,
    expected_keys: List[str],
    references: Optional[Dict[str, List[str]]] = None,
    locked_facts: Optional[Dict[str, Any]] = None,
    soft_clues: Optional[Dict[str, Any]] = None,
    source_description: str = "",
    variant_blueprint: Optional[Dict[str, Any]] = None,
) -> str:
    references = references or {}
    locked_facts = locked_facts or {}
    soft_clues = soft_clues or {}
    variant_blueprint = variant_blueprint or {}
    return f"""
对一份可能稀疏的基础画像做一次性补全与丰富，使人物立体、独特、可长期模拟。
{render_common_rules(as_of_date)}
{profile_output_contract(expected_keys)}
{persona_shape_contract()}

补全规则：
- 输出必须且只能包含上述字段，relation 保持为 []。
- locked_facts 中的值来自用户明确输入，必须逐项原样保留；地址对象可补充缺失子字段，但不得修改已有子字段。
- 自行判断哪些字段缺失或稀疏（值为“未知”、null、空字符串、空数组，或内容过于单薄），一次性补全；已明确且合理的事实不要无谓改动。
- 丰富性与独特性：
  - hobbies、favorite_foods 至少各 2～3 项，且具体（如“观鸟”“手冲咖啡”），避免“阅读”“运动”等空泛标签。
  - personality.traits 为 2～4 个稳定且能互相区分的特质，避免“善良”“开朗”等万能词。
  - memory_date 补充 1～3 条具体、有辨识度的过往记忆事件。
  - aim 补充 1～2 个具体、可感的目标。
  - belief 若输入未明确，可补一个与人物一致的具体信仰或“无宗教信仰”。
- 一致性：年龄、教育、工作、收入、家庭、城市、兴趣、健康、经历必须相互一致；不得引入与已给事实冲突的内容。
- 禁止占位符：不得出现“某某”“某大学”“某中学”“某公司”“某地”“待定”等。
- 优先参考软线索、变体蓝图与参考候选，但不为覆盖候选而硬塞无关内容。

参考候选：
{json.dumps(references, ensure_ascii=False, indent=2)}

当前画像（在此基础上补全与丰富）：
{json.dumps(profile, ensure_ascii=False, indent=2)}

锁定事实：
{json.dumps(locked_facts, ensure_ascii=False, indent=2)}

软线索：
{json.dumps(soft_clues, ensure_ascii=False, indent=2)}

原始描述：
{source_description}

本次变体蓝图：
{json.dumps(variant_blueprint, ensure_ascii=False, indent=2)}
""".strip()
