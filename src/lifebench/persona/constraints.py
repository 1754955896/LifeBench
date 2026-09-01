"""Deterministic derived fields and cross-field persona rules."""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, List

from .internal_models import INTERNAL_KEYS, InternalPersona, VALID_MBTI


@dataclass(frozen=True)
class Violation:
    rule_id: str
    path: str
    severity: str
    message: str
    actual: Any = None
    expected: Any = None
    auto_repairable: bool = False


def parse_date(value: Any, path: str = "date") -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        raise ValueError("%s 必须是 YYYY-MM-DD 字符串" % path)
    return datetime.strptime(value, "%Y-%m-%d").date()


def calculate_age(birth: date, as_of_date: date) -> int:
    if birth > as_of_date:
        raise ValueError("出生日期不能晚于基准日期")
    return as_of_date.year - birth.year - ((as_of_date.month, as_of_date.day) < (birth.month, birth.day))


def calculate_bmi(height_cm: float, weight_kg: float) -> float:
    height = float(height_cm)
    weight = float(weight_kg)
    if not 80 <= height <= 230:
        raise ValueError("身高超出允许范围")
    if not 20 <= weight <= 300:
        raise ValueError("体重超出允许范围")
    return round(weight / ((height / 100.0) ** 2), 1)


def apply_derived_values(persona: InternalPersona, as_of_date: date) -> None:
    birth = parse_date(persona.data.get("birth"), "birth")
    persona.data["birth"] = birth.strftime("%Y-%m-%d")
    persona.data["age"] = calculate_age(birth, as_of_date)
    body = persona.data.get("body")
    if isinstance(body, dict) and "height" in body and "weight" in body:
        body["BMI"] = calculate_bmi(body["height"], body["weight"])
    for group in persona.relation_groups:
        for contact in group:
            contact.age = calculate_age(contact.birth_date, as_of_date)


def _family_age_violations(persona: InternalPersona) -> List[Violation]:
    result = []
    ego_age = persona.data.get("age")
    if not isinstance(ego_age, int):
        return result
    parent_relations = {"父亲", "母亲", "父母", "继父", "继母", "岳父", "岳母", "公公", "婆婆"}
    child_relations = {"儿子", "女儿", "子女", "继子", "继女"}
    for group_index, group in enumerate(persona.relation_groups):
        for contact_index, contact in enumerate(group):
            path = "relation[%d][%d].age" % (group_index, contact_index)
            if contact.relation in parent_relations and contact.age < ego_age + 12:
                result.append(Violation("FAMILY-001", path, "error", "父母年龄至少应比本人高 12 岁", contact.age, ego_age + 12))
            if contact.relation in child_relations and contact.age > ego_age - 12:
                result.append(Violation("FAMILY-002", path, "error", "子女年龄至少应比本人低 12 岁", contact.age, ego_age - 12))
    return result


def validate_rules(persona: InternalPersona, as_of_date: date) -> List[Violation]:
    result = []
    personality = persona.data.get("personality")
    mbti = personality.get("mbti") if isinstance(personality, dict) else None
    if mbti not in VALID_MBTI:
        result.append(Violation("MBTI-001", "personality.mbti", "error", "本人 MBTI 不在完整 16 类型中", mbti))
    try:
        birth = parse_date(persona.data.get("birth"), "birth")
        expected_age = calculate_age(birth, as_of_date)
        if persona.data.get("age") != expected_age:
            result.append(Violation("AGE-001", "age", "error", "年龄与出生日期不一致", persona.data.get("age"), expected_age, True))
    except (TypeError, ValueError) as exc:
        result.append(Violation("DATE-001", "birth", "error", str(exc), persona.data.get("birth")))
    body = persona.data.get("body")
    if isinstance(body, dict):
        try:
            expected_bmi = calculate_bmi(body.get("height"), body.get("weight"))
            if body.get("BMI") != expected_bmi:
                result.append(Violation("BODY-001", "body.BMI", "error", "BMI 与身高体重不一致", body.get("BMI"), expected_bmi, True))
        except (TypeError, ValueError) as exc:
            result.append(Violation("BODY-002", "body", "error", str(exc), body))
    else:
        result.append(Violation("BODY-002", "body", "error", "body 必须是对象", body))

    seen = set()
    for group_index, group in enumerate(persona.relation_groups):
        circles = {contact.social_circle for contact in group}
        if "" in circles:
            result.append(Violation("REL-001", "relation[%d]" % group_index, "error", "联系人社交圈不能为空"))
        if len(circles) > 1:
            result.append(Violation("REL-002", "relation[%d]" % group_index, "error", "同一关系组只能包含一个社交圈", sorted(circles)))
        for contact_index, contact in enumerate(group):
            base = "relation[%d][%d]" % (group_index, contact_index)
            if not contact.name or contact.name == persona.data.get("name"):
                result.append(Violation("REL-003", base + ".name", "error", "联系人姓名为空或与本人相同", contact.name))
            dedup_key = (contact.name, contact.relation)
            if dedup_key in seen:
                result.append(Violation("REL-004", base, "error", "联系人重复", dedup_key))
            seen.add(dedup_key)
            try:
                expected_age = calculate_age(contact.birth_date, as_of_date)
                if contact.age != expected_age:
                    result.append(Violation("AGE-002", base + ".age", "error", "联系人年龄与出生日期不一致", contact.age, expected_age, True))
            except ValueError as exc:
                result.append(Violation("DATE-001", base + ".birth_date", "error", str(exc), str(contact.birth_date)))
            if contact.personality not in VALID_MBTI:
                result.append(Violation("MBTI-001", base + ".personality", "error", "联系人 MBTI 不在完整 16 类型中", contact.personality))
    result.extend(_family_age_violations(persona))

    for key in persona.data:
        if key in INTERNAL_KEYS:
            result.append(Violation("OUTPUT-001", key, "error", "内部字段不能进入画像数据", key))
    return result
