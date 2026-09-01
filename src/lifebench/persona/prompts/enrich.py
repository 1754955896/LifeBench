"""Enrichment prompt: add distinctive color to narrative description fields."""

import json
from typing import Any, Dict, List, Optional

from .common import render_common_rules
from .contracts import narrative_output_contract

PROMPT_VERSION = "persona-enrich-v1"

# 丰富化阶段允许重写的描述字段（其余结构事实保持冻结）。
ENRICH_FIELDS = ("description", "lifestyle_desc", "experience_desc")

# 随机补充的维度池，每次按种子抽取 2～4 个织入描述。
ENRICH_DIMENSIONS = (
    "一项独特的业余兴趣",
    "一个鲜明的饮食或消费偏好",
    "一个日常小习惯或仪式",
    "一个小癖好或口头禅",
    "一段有辨识度的过往经历",
    "一个审美或趣味上的偏好",
)


def build_enrich_prompt(
    profile: Dict[str, Any],
    as_of_date: str,
    dimensions: List[str],
    grounding_context: Optional[Dict[str, Any]] = None,
    circle_anchors: Optional[List[Dict[str, Any]]] = None,
) -> str:
    facts = {key: value for key, value in profile.items() if key not in ENRICH_FIELDS and key != "relation"}
    current = {key: profile.get(key, "") for key in ENRICH_FIELDS}
    grounding_context = grounding_context or {}
    circle_anchors = circle_anchors or []
    return f"""
在已冻结的画像事实与描述基础上，随机补充若干独特内容，使人物更具辨识度。
{render_common_rules(as_of_date)}
{narrative_output_contract(list(ENRICH_FIELDS))}

要求：
- 只能输出 {list(ENRICH_FIELDS)} 三个描述字段，不能新增、删除或修改其他结构事实。
- 本次随机选中的补充维度：{"、".join(dimensions)}。围绕这些维度，把具体、独特、可感知的细节织入上述三个描述字段。
- 所有地点、机构、人物、物品必须具体明确，禁止使用「某某」「某大学」「某中学」「某公司」「某医院」「某地」「某单位」等占位符。
- 优先引用「地理落地与关系圈上下文」中已落地的真实名称（学校 institution_name、运动场馆 venue_name、工作地 POI 名称等）来具体化过往经历与描述。
- 补充内容必须与冻结事实一致，不得创造冲突的职业、家庭、学历、资产或疾病；经历中的事件发生时间不得晚于基准日期。
- 三个字段避免互相重复，保持各自侧重：description 综合画像，lifestyle_desc 聚焦日常生活与习惯，experience_desc 按时间线叙述经历。

冻结事实：
{json.dumps(facts, ensure_ascii=False, indent=2)}

当前描述（在其基础上补充，可保留已有有用信息）：
{json.dumps(current, ensure_ascii=False, indent=2)}

地理落地与关系圈上下文（用于具体化实体名称，不得输出为新字段）：
{json.dumps(grounding_context, ensure_ascii=False, indent=2)}

关系圈锚点（含 institution_name / venue_name / meeting_place 等已落地名称，用于明确过往经历）：
{json.dumps(circle_anchors, ensure_ascii=False, indent=2)}
""".strip()


def build_enrich_consistency_prompt(
    profile: Dict[str, Any],
    enriched: Dict[str, Any],
    as_of_date: str,
    grounding_context: Optional[Dict[str, Any]] = None,
    circle_anchors: Optional[List[Dict[str, Any]]] = None,
) -> str:
    facts = {key: value for key, value in profile.items() if key not in ENRICH_FIELDS and key != "relation"}
    grounding_context = grounding_context or {}
    circle_anchors = circle_anchors or []
    return f"""
你是画像一致性审查员。下面是已冻结的结构事实，以及 enrich 阶段改写后的三个描述字段。
请逐条判断改写后的描述是否与冻结事实冲突，例如：改换学历、职业、行业、婚姻、家庭、经济状况、健康状况、所在城市/区县、雇主、学校、运动场馆等；经历中的事件时间晚于基准日期；或与地理落地/关系圈锚点中的已落地名称矛盾。
{render_common_rules(as_of_date)}
只输出一个 JSON 对象：{{"inconsistencies": ["具体冲突描述", ...]}}。若一致，inconsistencies 为空数组。不要输出多余字段。

冻结事实：
{json.dumps(facts, ensure_ascii=False, indent=2)}

改写后的描述字段：
{json.dumps(enriched, ensure_ascii=False, indent=2)}

地理落地与关系圈上下文：
{json.dumps(grounding_context, ensure_ascii=False, indent=2)}

关系圈锚点：
{json.dumps(circle_anchors, ensure_ascii=False, indent=2)}
""".strip()
