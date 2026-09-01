"""Prompt for planning structural variation before persona completion."""

import json
from typing import Any, Dict, List

from ..diversity import diversity_directive
from ..variant_models import VARIANT_BLUEPRINT_KEYS

PROMPT_VERSION = "persona-variant-blueprint-v1"


def build_variant_blueprint_prompt(
    locked_facts: Dict[str, Any],
    soft_clues: Dict[str, Any],
    source_description: str,
    references: Dict[str, List[str]],
    diversity: str,
    variant_index: int,
    variant_seed: int,
    previous_blueprints: List[Dict[str, Any]],
) -> str:
    return f"""
为同一份稀疏人物输入设计第 {variant_index + 1} 个独立人生蓝图。
{diversity_directive(diversity)}

只输出一个 JSON 对象，且必须包含这些字段：
{json.dumps(list(VARIANT_BLUEPRINT_KEYS), ensure_ascii=False)}

字段要求：
- profile_direction、career_track、family_track、personality_track、economic_track、health_track 为字符串。
- interest_track、social_track、distinctive_details 为字符串数组。
- 锁定事实不可修改；软线索要保留核心语义但可以具体化。
- 不要仅更换姓名或措辞；与已有蓝图在未锁定的人生阶段、职业、家庭、人格、兴趣和社交结构上形成实质差异。
- 所有维度之间必须符合现实因果，不输出推理或解释。
- variant_seed={variant_seed} 仅用于区分本次方案，不要把它写入内容。

锁定事实：
{json.dumps(locked_facts, ensure_ascii=False, indent=2)}

软线索：
{json.dumps(soft_clues, ensure_ascii=False, indent=2)}

原始描述：
{source_description}

参考候选：
{json.dumps(references, ensure_ascii=False, indent=2)}

已有蓝图（必须避免重复）：
{json.dumps(previous_blueprints, ensure_ascii=False, indent=2)}
""".strip()
