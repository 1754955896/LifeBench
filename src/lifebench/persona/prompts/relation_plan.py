"""Relationship slot planning prompt."""

import json
from typing import Any, Dict, Optional

from .common import render_common_rules
from .contracts import relation_plan_output_contract

PROMPT_VERSION = "persona-relation-plan-v3"


def build_relation_plan_prompt(
    profile: Dict[str, Any], as_of_date: str, min_contacts: int = 16,
    max_contacts: int = 28, variant_blueprint: Optional[Dict[str, Any]] = None,
    employer_anchor: Optional[Dict[str, Any]] = None,
    grounding_context: Optional[Dict[str, Any]] = None,
) -> str:
    profile_without_relation = {key: value for key, value in profile.items() if key != "relation"}
    variant_blueprint = variant_blueprint or {}
    employer_anchor = employer_anchor or {}
    grounding_context = grounding_context or {}
    return f"""
为人物规划未来两年仍可能保持联系的联系人槽位。
{render_common_rules(as_of_date)}
{relation_plan_output_contract()}

要求：
- 生成 {min_contacts}～{max_contacts} 个槽位，具体数量根据年龄、家庭、教育、职业、迁移和兴趣决定。
- 先规划 circles，再规划各圈 members；circle_id 和 slot_id 在本次输出中分别唯一。
- circle_type 使用 current_work、school、household、family、sports_club、neighborhood、online_community、professional_community、hobby_group、other 之一。
- relation 简洁；social_circle 使用具体且稳定的圈子名称。
- 家庭结构必须与 family、经历一致；没有大学经历时不得生成大学同学。
- 只保留重要、经常联系或未来两年有现实联系动机的人，不生成二级关系。
- 同圈可以多人，但不要为每个独处型爱好强行创建圈子。
- 当前雇主下的产品线、部门、管理层等可以是不同子圈，但 parent_anchor_id 必须全部为 current_employer，不能分别创造公司。
- school 的 shared_facts 至少包含 institution_name 和 shared_period；同一学校的子圈使用相同 parent_anchor_id，联系人毕业后的当前单位允许不同。
- sports_club 的 shared_facts 至少包含 venue_name、activity 和 activity_schedule；同一场馆的子圈使用相同 parent_anchor_id，场馆不是联系人的工作单位，且应能在人物住宅日常生活半径内找到。
- household 的 shared_facts 说明 shared_period，实际共同住宅由程序注入。
- professional_community 的 shared_facts 至少包含 group_name；online_community 至少包含 platform 和 group_name。
- hobby_group 的 shared_facts 至少包含 group_name，可增加住宅附近的 meeting_place；neighborhood 的行政区域由程序根据居住地注入。
- mixed relation 选择一个主圈，其他关系写入 secondary_tags，不能因此丢失父级锚点。

人物画像：
{json.dumps(profile_without_relation, ensure_ascii=False, indent=2)}

本次变体的社交结构方向：
{json.dumps(variant_blueprint, ensure_ascii=False, indent=2)}

内部当前雇主锚点：
{json.dumps(employer_anchor, ensure_ascii=False, indent=2)}

地理落地上下文：
{json.dumps(grounding_context, ensure_ascii=False, indent=2)}
""".strip()
