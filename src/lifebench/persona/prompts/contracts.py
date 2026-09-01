"""Prompt-visible contracts derived from the internal contract constants."""

import json
from typing import List

from ..internal_models import STANDARD_CONTACT_KEYS, VALID_MBTI


def profile_output_contract(expected_keys: List[str]) -> str:
    return "输出对象必须且只能包含这些字段并保持顺序：%s" % json.dumps(expected_keys, ensure_ascii=False)


def persona_shape_contract() -> str:
    return """
字段类型约定：
- name/birth/nationality/gender/education/job/occupation/belief/family 为字符串，birth 使用 YYYY-MM-DD。
- age 为整数，salary 为数值。
- home_address/workplace 为包含 province、city、district、street_name、street_number 的对象。
- birth_place 为至少包含 province、city、district 的对象。
- body 为包含 height、weight、BMI 的对象，三项均为数值。
- personality 为包含 mbti 字符串和 traits 字符串数组的对象。
- hobbies、favorite_foods、memory_date、aim 为字符串数组。
- healthy_desc、lifestyle_desc、economic_desc、work_desc、experience_desc、description 为字符串。
- relation 在基础阶段固定为空数组。
""".strip()


def narrative_output_contract(fields: List[str]) -> str:
    return "输出对象必须且只能包含这些描述字段：%s" % json.dumps(fields, ensure_ascii=False)


def relation_plan_output_contract() -> str:
    return (
        '输出对象格式为 {"items":[{'
        '"circle_id":"...","circle_type":"...","parent_anchor_id":"...",'
        '"social_circle":"...","shared_facts":{},'
        '"members":[{"slot_id":"...","name_hint":"...","relation":"...","secondary_tags":[]}]'
        '}]}。'
    )


def contact_group_output_contract() -> str:
    internal_keys = ["social_circle" if key == "social circle" else key for key in STANDARD_CONTACT_KEYS]
    return (
        '输出对象格式为 {"items":[...]}，每个联系人必须且只能包含字段：%s。'
        "personality 必须是以下 MBTI 之一：%s。"
    ) % (
        json.dumps(internal_keys, ensure_ascii=False),
        json.dumps(sorted(VALID_MBTI), ensure_ascii=False),
    )
