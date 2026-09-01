"""Contact details prompt for one social circle."""

import json
from typing import Any, Dict, List, Optional

from .common import render_common_rules
from .contracts import contact_group_output_contract

PROMPT_VERSION = "persona-contact-group-v3"


def build_contact_group_prompt(
    profile: Dict[str, Any], slots: List[Dict[str, Any]], as_of_date: str,
    variant_blueprint: Optional[Dict[str, Any]] = None,
    employer_anchor: Optional[Dict[str, Any]] = None,
    grounding_context: Optional[Dict[str, Any]] = None,
    circle_anchor: Optional[Dict[str, Any]] = None,
) -> str:
    profile_without_relation = {key: value for key, value in profile.items() if key != "relation"}
    variant_blueprint = variant_blueprint or {}
    employer_anchor = employer_anchor or {}
    grounding_context = grounding_context or {}
    circle_anchor = circle_anchor or {}
    return f"""
根据固定关系槽位补全同一社交圈的联系人。
{render_common_rules(as_of_date)}
{contact_group_output_contract()}

要求：
- 输出人数和顺序必须与槽位完全一致，不得增删、合并或改换 relation/social_circle。
- 同圈人物的共同经历相互一致；家庭成员、同事和同学的年龄与时间线合理。
- birth_date 决定 age；程序会按基准日重算年龄。
- relation_description 说明相识方式、联系原因、方式和合理频率，不叙述推理过程。
- 地址和组织均为合理虚构，避免直接使用知名真实个人信息。
- 当前同事、上级、下属等当前工作关系的 organization 必须逐字使用内部雇主锚点 name；前同事、家属的同事及其他关系不受此约束。
- 联系人的地址字段必须输出 JSON 对象，禁止输出地址字符串。
- 所有联系人必须继承圈子共享锚点中的共同事实，并在 relation_description 中自然体现共同学校、场馆、活动或共同居住经历。
- organization 始终表示联系人当前主要单位：学校联系人毕业后的单位可以不同；健身房、球馆、跑团和兴趣小组不得被误填为工作单位。

主画像：
{json.dumps(profile_without_relation, ensure_ascii=False, indent=2)}

固定槽位：
{json.dumps(slots, ensure_ascii=False, indent=2)}

本次变体蓝图：
{json.dumps(variant_blueprint, ensure_ascii=False, indent=2)}

内部雇主锚点（只用于一致性，不得新增输出字段）：
{json.dumps(employer_anchor, ensure_ascii=False, indent=2)}

地理落地上下文（用于使工作关系和叙事地点一致）：
{json.dumps(grounding_context, ensure_ascii=False, indent=2)}

本圈共享锚点（只用于继承事实，不得新增输出字段）：
{json.dumps(circle_anchor, ensure_ascii=False, indent=2)}
""".strip()
