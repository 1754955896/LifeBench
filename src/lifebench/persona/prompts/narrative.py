"""Narrative-only profile prompt."""

import json
from typing import Any, Dict

from .common import render_common_rules
from .contracts import narrative_output_contract

PROMPT_VERSION = "persona-narrative-v3"
NARRATIVE_FIELDS = (
    "healthy_desc", "lifestyle_desc", "economic_desc", "work_desc",
    "experience_desc", "description",
)


def build_narrative_prompt(
    structured_profile: Dict[str, Any], as_of_date: str,
    source_description: str = "", variant_blueprint: Dict[str, Any] = None,
    grounding_context: Dict[str, Any] = None,
) -> str:
    facts = {key: value for key, value in structured_profile.items() if key not in NARRATIVE_FIELDS and key != "relation"}
    existing = {key: structured_profile.get(key, "") for key in NARRATIVE_FIELDS}
    variant_blueprint = variant_blueprint or {}
    grounding_context = grounding_context or {}
    return f"""
根据冻结的结构事实重写人物描述字段。
{render_common_rules(as_of_date)}
{narrative_output_contract(list(NARRATIVE_FIELDS))}

要求：
- 只能输出六个描述字段，不能提出或修改其他结构事实。
- 每段描述必须与冻结事实一致，避免空泛标签和互相重复。
- description 综合其他事实，但不能创造与输入冲突的新职业、家庭、资产或疾病。
- experience_desc 按时间顺序叙述，所有事件发生时间不得晚于基准日期。
- 若地理落地上下文包含工作地 POI，work_desc 必须原样提及该 POI 名称，并按其真实场所类型叙述，不能擅自改写为园区、写字楼或校园。
- lifestyle_desc 必须体现结构化交通偏好；不要把公共交通偏好写成自驾。
- 描述要丰富且独特：避免「性格开朗」「热爱生活」等空泛标签，补充可感知的具体细节、习惯、偏好与场景，使人物具有辨识度。
- 所有地点、机构、人物称谓必须具体明确，禁止使用「某某」「某大学」「某中学」「某公司」「某医院」「某地」等占位符；优先引用冻结事实与地理落地上下文中的具体名称（机构名可虚构但必须具体，不得留占位）。

冻结事实：
{json.dumps(facts, ensure_ascii=False, indent=2)}

原描述（可保留有用信息）：
{json.dumps(existing, ensure_ascii=False, indent=2)}

原始输入描述（只能保留与冻结事实一致的内容）：
{source_description}

本次变体蓝图：
{json.dumps(variant_blueprint, ensure_ascii=False, indent=2)}

地理落地与交通上下文（只用于叙事一致性，不得输出为新字段）：
{json.dumps(grounding_context, ensure_ascii=False, indent=2)}
""".strip()
